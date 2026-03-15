"""Managed cloud-library client for runtime search and coverage calls."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

from utils.license_manager import (
    APP_VERSION,
    commercial_mode_enabled,
    create_trial_payload,
    encode_license_key,
    load_license_state,
)


CLOUD_URL_ENV = "THERMOANALYZER_LIBRARY_CLOUD_URL"
CLOUD_ENABLED_ENV = "THERMOANALYZER_LIBRARY_CLOUD_ENABLED"
DEV_CLOUD_AUTH_ENV = "THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH"
LIBRARY_LICENSE_HEADER = "X-TA-License"
AUTHORIZATION_HEADER = "Authorization"
TOKEN_SKEW_SECONDS = 20
DEFAULT_TIMEOUT_SECONDS = 20.0


def _truthy(value: str | None) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "on"}


def _parse_expiry_epoch(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return float(parsed.timestamp())


class ManagedLibraryCloudClient:
    """HTTP client for ThermoAnalyzer-owned managed library endpoints."""

    def __init__(self, *, base_url: str | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_url = str(base_url or os.getenv(CLOUD_URL_ENV, "")).strip().rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self._token_value = ""
        self._token_expires_epoch = 0.0
        self._last_error = ""
        self._last_auth_mode = ""

    @property
    def configured(self) -> bool:
        if not self.base_url:
            return False
        enabled_override = os.getenv(CLOUD_ENABLED_ENV, "").strip()
        if not enabled_override:
            return True
        return _truthy(enabled_override)

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def dev_auth_override_used(self) -> bool:
        return self._last_auth_mode == "dev_override"

    @property
    def last_auth_mode(self) -> str:
        return self._last_auth_mode

    def _dev_auth_override_enabled(self) -> bool:
        return _truthy(os.getenv(DEV_CLOUD_AUTH_ENV, ""))

    def _local_dev_context(self) -> bool:
        if not commercial_mode_enabled():
            return True
        try:
            hostname = str(urlparse(self.base_url).hostname or "").strip().lower()
        except Exception:  # pragma: no cover - defensive URL parsing
            hostname = ""
        return hostname in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}

    def _with_dev_hint(self, message: str, *, payload_hint: bool = False) -> str:
        if not self._local_dev_context() or self._dev_auth_override_enabled():
            return message
        if payload_hint:
            return (
                f"{message} Local dev override can generate a temporary trial payload "
                f"when `{DEV_CLOUD_AUTH_ENV}=1`."
            )
        return f"{message} Set `{DEV_CLOUD_AUTH_ENV}=1` for local dev override."

    def _dev_override_license(self, *, failure_message: str) -> str | None:
        if not self._dev_auth_override_enabled():
            self._last_auth_mode = ""
            return None
        try:
            payload = create_trial_payload(app_version=APP_VERSION)
            encoded = encode_license_key(payload)
        except Exception as exc:  # pragma: no cover - malformed local env edge path
            self._last_auth_mode = ""
            self._last_error = (
                f"{failure_message} Dev cloud auth override is enabled, but a temporary trial payload "
                f"could not be generated: {exc}"
            )
            return None
        self._last_auth_mode = "dev_override"
        return encoded

    def _token_valid(self) -> bool:
        if not self._token_value:
            return False
        return (self._token_expires_epoch - TOKEN_SKEW_SECONDS) > datetime.now(UTC).timestamp()

    def _encoded_license(self) -> str | None:
        self._last_auth_mode = ""
        try:
            license_state = load_license_state(app_version=APP_VERSION)
        except Exception as exc:  # pragma: no cover - environment/license edge paths
            failure_message = f"License state could not be loaded: {exc}"
            encoded = self._dev_override_license(failure_message=failure_message)
            if encoded:
                return encoded
            self._last_error = self._with_dev_hint(failure_message)
            return None
        if str(license_state.get("status") or "") not in {"trial", "activated"}:
            failure_message = "Cloud library access requires trial or activated license status."
            encoded = self._dev_override_license(failure_message=failure_message)
            if encoded:
                return encoded
            self._last_error = self._with_dev_hint(failure_message)
            return None
        payload = license_state.get("license")
        if not isinstance(payload, Mapping):
            failure_message = "Cloud library access requires a signed license payload."
            encoded = self._dev_override_license(failure_message=failure_message)
            if encoded:
                return encoded
            self._last_error = self._with_dev_hint(failure_message, payload_hint=True)
            return None
        try:
            encoded = encode_license_key(dict(payload))
        except Exception as exc:  # pragma: no cover - malformed local license payload
            failure_message = f"License payload could not be encoded: {exc}"
            encoded = self._dev_override_license(failure_message=failure_message)
            if encoded:
                return encoded
            self._last_error = self._with_dev_hint(failure_message, payload_hint=True)
            return None
        self._last_auth_mode = "stored_license"
        return encoded

    def _acquire_token(self) -> str | None:
        if not self.configured:
            self._last_error = "Cloud library URL is not configured."
            self._last_auth_mode = ""
            return None
        if self._token_valid():
            return self._token_value

        encoded = self._encoded_license()
        if not encoded:
            return None
        try:
            response = httpx.post(
                f"{self.base_url}/v1/library/auth/token",
                headers={LIBRARY_LICENSE_HEADER: encoded},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            self._last_error = f"Cloud auth/token request failed: {exc}"
            self._last_auth_mode = ""
            return None

        token = str(payload.get("access_token") or "").strip()
        expires_epoch = _parse_expiry_epoch(payload.get("expires_at"))
        if not token or expires_epoch <= 0.0:
            self._last_error = "Cloud auth/token response is missing access_token or expires_at."
            self._last_auth_mode = ""
            return None
        self._token_value = token
        self._token_expires_epoch = expires_epoch
        self._last_error = ""
        return self._token_value

    def _request(
        self,
        *,
        method: str,
        path: str,
        json_payload: Mapping[str, Any] | None = None,
        requires_token: bool = True,
    ) -> dict[str, Any] | None:
        if not self.configured:
            self._last_error = "Cloud library URL is not configured."
            return None

        headers: dict[str, str] = {}
        if requires_token:
            token = self._acquire_token()
            if not token:
                return None
            headers[AUTHORIZATION_HEADER] = f"Bearer {token}"

        try:
            response = httpx.request(
                method.upper(),
                f"{self.base_url}{path}",
                json=dict(json_payload or {}),
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, Mapping):
                self._last_error = ""
                return dict(payload)
            self._last_error = f"Cloud {path} returned non-object payload."
            return None
        except Exception as exc:
            self._last_error = f"Cloud request failed ({path}): {exc}"
            return None

    def search(self, *, analysis_type: str, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        token = str(analysis_type or "").strip().upper()
        if token not in {"FTIR", "RAMAN", "XRD"}:
            self._last_error = f"Unsupported cloud analysis_type: {token or 'UNKNOWN'}"
            return None
        return self._request(
            method="POST",
            path=f"/v1/library/search/{token.lower()}",
            json_payload=payload,
            requires_token=True,
        )

    def providers(self) -> dict[str, Any] | None:
        return self._request(method="GET", path="/v1/library/providers", requires_token=True)

    def coverage(self) -> dict[str, Any] | None:
        return self._request(method="GET", path="/v1/library/coverage", requires_token=True)

    def prefetch(self, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        return self._request(
            method="POST",
            path="/v1/library/prefetch",
            json_payload=payload,
            requires_token=True,
        )


_CLIENT_INSTANCE: ManagedLibraryCloudClient | None = None


def get_library_cloud_client() -> ManagedLibraryCloudClient:
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is None:
        _CLIENT_INSTANCE = ManagedLibraryCloudClient()
    return _CLIENT_INSTANCE
