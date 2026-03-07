"""Offline license helpers for ThermoAnalyzer Professional."""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import os
import platform
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


APP_VERSION = "2.0"
TRIAL_DAYS = 14
LICENSE_PREFIX = "TAPRO-"
COMMERCIAL_MODE_ENV = "THERMOANALYZER_COMMERCIAL_MODE"
LICENSE_REQUIRED_FIELDS = {
    "license_key",
    "customer_name",
    "company_name",
    "sku",
    "seat_count",
    "issued_at",
    "expires_at",
    "allowed_major_version",
    "offline_grace_days",
    "signature",
}

# Demo-only signing secret. Commercial builds should override this via env var.
DEFAULT_LICENSE_SECRET = "thermoanalyzer-professional-demo-secret"


def commercial_mode_enabled() -> bool:
    """Return whether license enforcement is enabled for this runtime."""
    raw = os.getenv(COMMERCIAL_MODE_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def get_storage_dir() -> Path:
    """Return the local storage directory used for license payloads."""
    root = os.getenv("THERMOANALYZER_HOME")
    if root:
        return Path(root)
    return Path.home() / ".thermoanalyzer"


def get_machine_fingerprint() -> str:
    """Return a stable local fingerprint for optional per-device licenses."""
    raw = f"{platform.node()}::{uuid.getnode()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def create_signed_license(
    *,
    customer_name: str,
    company_name: str,
    sku: str,
    seat_count: int,
    expires_at: str | datetime,
    allowed_major_version: int | str,
    offline_grace_days: int = 30,
    issued_at: str | datetime | None = None,
    machine_fingerprint: str | None = None,
    license_key: str | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Create and sign a license payload."""
    issued = _coerce_datetime(issued_at) if issued_at is not None else datetime.now(UTC)
    expires = _coerce_datetime(expires_at)
    payload = {
        "license_key": license_key or f"TA-{issued.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        "customer_name": customer_name,
        "company_name": company_name,
        "sku": sku,
        "seat_count": int(seat_count),
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "allowed_major_version": int(allowed_major_version),
        "offline_grace_days": int(offline_grace_days),
        "machine_fingerprint": machine_fingerprint or "",
    }
    payload["signature"] = sign_license_payload(payload, secret=secret)
    return payload


def create_trial_payload(
    *,
    app_version: str = APP_VERSION,
    days: int = TRIAL_DAYS,
    now: datetime | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Create a locally signed 14-day trial payload."""
    now = now or datetime.now(UTC)
    return create_signed_license(
        customer_name="Trial User",
        company_name="Evaluation",
        sku="TRIAL",
        seat_count=1,
        issued_at=now,
        expires_at=now + timedelta(days=days),
        allowed_major_version=_major_version(app_version),
        offline_grace_days=days,
        machine_fingerprint=get_machine_fingerprint(),
        license_key=f"TRIAL-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        secret=secret,
    )


def sign_license_payload(payload: dict[str, Any], secret: str | None = None) -> str:
    """Return HMAC signature for a license payload."""
    secret_bytes = (secret or os.getenv("THERMOANALYZER_LICENSE_SECRET") or DEFAULT_LICENSE_SECRET).encode("utf-8")
    message = json.dumps(_canonical_payload(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hmac.new(secret_bytes, message, hashlib.sha256).hexdigest()


def encode_license_key(payload: dict[str, Any]) -> str:
    """Encode a signed payload as a compact license key string."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    encoded = base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")
    return f"{LICENSE_PREFIX}{encoded}"


def decode_license_key(license_key: str) -> dict[str, Any]:
    """Decode an encoded license key string into its JSON payload."""
    if not license_key or not license_key.startswith(LICENSE_PREFIX):
        raise ValueError("License key format is invalid.")
    encoded = license_key[len(LICENSE_PREFIX):]
    padding = "=" * (-len(encoded) % 4)
    try:
        raw = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("License key could not be decoded.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Decoded license payload is invalid.")
    return payload


def validate_license_payload(
    payload: dict[str, Any] | None,
    *,
    app_version: str = APP_VERSION,
    now: datetime | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Validate a signed payload and map it to app-facing license state."""
    now = now or datetime.now(UTC)
    state = {
        "status": "unlicensed",
        "message": "Enter a signed license key or start a 14-day trial.",
        "license": None,
        "days_remaining": None,
        "source": None,
        "machine_fingerprint": get_machine_fingerprint(),
    }
    if not payload:
        return state

    missing = sorted(LICENSE_REQUIRED_FIELDS - set(payload))
    if missing:
        state["message"] = f"License payload is missing required fields: {', '.join(missing)}."
        return state

    payload = copy.deepcopy(payload)
    expected_signature = sign_license_payload(payload, secret=secret)
    if payload.get("signature") != expected_signature:
        state["message"] = "License signature is invalid."
        return state

    machine_fingerprint = str(payload.get("machine_fingerprint") or "").strip()
    if machine_fingerprint and machine_fingerprint != get_machine_fingerprint():
        state["message"] = "This license key is bound to a different workstation."
        return state

    expires_at = _coerce_datetime(payload["expires_at"])
    issued_at = _coerce_datetime(payload["issued_at"])
    major_version = _major_version(app_version)
    allowed_major = int(payload["allowed_major_version"])
    days_remaining = int((expires_at - now).total_seconds() // 86400)

    status = "trial" if str(payload.get("sku", "")).upper() == "TRIAL" else "activated"
    message = (
        f"{payload['company_name']} - {payload['sku']} active until {expires_at.date().isoformat()}."
        if payload["company_name"]
        else f"{payload['sku']} active until {expires_at.date().isoformat()}."
    )

    if expires_at < now:
        status = "expired_read_only"
        message = f"License expired on {expires_at.date().isoformat()}. Export, report, and project save are locked."
    elif allowed_major < major_version:
        status = "expired_read_only"
        message = (
            f"License allows major version {allowed_major}. Current build {app_version} runs in read-only mode."
        )

    state.update(
        {
            "status": status,
            "message": message,
            "license": payload,
            "days_remaining": max(days_remaining, 0),
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
    )
    return state


def activate_license_key(
    license_key: str,
    *,
    app_version: str = APP_VERSION,
    secret: str | None = None,
) -> dict[str, Any]:
    """Decode, validate, and persist a signed license key."""
    payload = decode_license_key(license_key.strip())
    state = validate_license_payload(payload, app_version=app_version, secret=secret)
    if state["status"] == "unlicensed":
        raise ValueError(state["message"])
    _write_json(_license_file_path(), payload)
    return state


def start_trial(
    *,
    app_version: str = APP_VERSION,
    days: int = TRIAL_DAYS,
    now: datetime | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Create and persist a local trial key."""
    payload = create_trial_payload(app_version=app_version, days=days, now=now, secret=secret)
    _write_json(_trial_file_path(), payload)
    return validate_license_payload(payload, app_version=app_version, now=now, secret=secret)


def clear_saved_license() -> None:
    """Remove persisted activation and trial files."""
    for path in (_license_file_path(), _trial_file_path()):
        if path.exists():
            path.unlink()


def load_license_state(
    *,
    app_version: str = APP_VERSION,
    now: datetime | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Load installed license or trial from disk and validate it."""
    payload = _read_json(_license_file_path())
    source = "license"
    if payload is None:
        payload = _read_json(_trial_file_path())
        source = "trial" if payload is not None else None

    state = validate_license_payload(payload, app_version=app_version, now=now, secret=secret)
    original_status = state["status"]
    state["commercial_mode"] = commercial_mode_enabled()
    state["source"] = source
    if not state["commercial_mode"] and state["status"] == "unlicensed":
        state["status"] = "development"
        state["message"] = (
            "Development build: license enforcement is disabled. "
            "All import, analysis, export, and project-save actions are enabled."
        )
    if original_status == "unlicensed" and source == "license":
        # Invalid installed license should not silently block trial creation forever.
        try:
            _license_file_path().unlink()
        except FileNotFoundError:
            pass
    return state


def license_allows_write(state: dict[str, Any] | None) -> bool:
    """Return whether export/report/project-save actions are permitted."""
    if not commercial_mode_enabled():
        return True
    return (state or {}).get("status") in {"trial", "activated"}


def license_is_read_only(state: dict[str, Any] | None) -> bool:
    """Return whether the app should run in read-only mode."""
    if not commercial_mode_enabled():
        return False
    return (state or {}).get("status") == "expired_read_only"


def _license_file_path() -> Path:
    return get_storage_dir() / "license.json"


def _trial_file_path() -> Path:
    return get_storage_dir() / "trial.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} does not contain a valid license payload.")
    return data


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = copy.deepcopy(payload)
    canonical.pop("signature", None)
    return canonical


def _coerce_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _major_version(app_version: str) -> int:
    try:
        return int(str(app_version).split(".", 1)[0])
    except Exception:
        return 1
