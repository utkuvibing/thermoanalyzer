"""Managed cloud-library service helpers for auth, search, and coverage routes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
from fastapi import HTTPException

from core.reference_library import ReferenceLibraryManager, get_reference_library_manager
from utils.license_manager import APP_VERSION, get_storage_dir, validate_encoded_license_key


_TOKEN_TTL_SECONDS = 15 * 60
_DEFAULT_RATE_LIMIT_PER_MINUTE = 60
_TOKEN_SECRET_ENV = "THERMOANALYZER_LIBRARY_CLOUD_TOKEN_SECRET"
_TOKEN_TTL_ENV = "THERMOANALYZER_LIBRARY_CLOUD_TOKEN_TTL_SECONDS"
_RATE_LIMIT_ENV = "THERMOANALYZER_LIBRARY_CLOUD_RATE_LIMIT_PER_MINUTE"
_AUDIT_FILE_NAME = "cloud_library_audit.jsonl"
_ALLOWED_STATUSES = {"trial", "activated"}

_DEFAULT_PROVIDER_SCOPE = {
    "FTIR": ["openspecy"],
    "RAMAN": ["openspecy", "rod"],
    "XRD": ["cod", "materials_project"],
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _coerce_float_array(values: list[float] | None) -> np.ndarray:
    if not values:
        return np.asarray([], dtype=float)
    try:
        parsed = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid numeric array: {exc}") from exc
    if parsed.ndim != 1:
        raise HTTPException(status_code=400, detail="Input arrays must be one-dimensional.")
    return parsed


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(f"{token}{padding}".encode("ascii"))


def _token_secret() -> bytes:
    secret = str(os.getenv(_TOKEN_SECRET_ENV, "thermoanalyzer-cloud-dev-secret")).strip()
    return secret.encode("utf-8")


def _token_ttl_seconds() -> int:
    raw = str(os.getenv(_TOKEN_TTL_ENV, _TOKEN_TTL_SECONDS)).strip()
    try:
        return max(60, int(raw))
    except (TypeError, ValueError):
        return _TOKEN_TTL_SECONDS


def _rate_limit_per_minute() -> int:
    raw = str(os.getenv(_RATE_LIMIT_ENV, _DEFAULT_RATE_LIMIT_PER_MINUTE)).strip()
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_RATE_LIMIT_PER_MINUTE


def _normalize_provider(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"materialsproject", "materials_project", "mp"}:
        return "materials_project"
    if token in {"cod"}:
        return "cod"
    if token in {"openspecy"}:
        return "openspecy"
    if token in {"rod"}:
        return "rod"
    return token


class ManagedLibraryCloudService:
    """Encapsulates managed cloud auth, search, coverage, and fallback prefetch."""

    def __init__(self, manager: ReferenceLibraryManager | None = None) -> None:
        self.manager = manager or get_reference_library_manager()
        self._rate_windows: dict[str, list[float]] = {}

    def _audit_path(self) -> Path:
        root = get_storage_dir() / "libraries"
        root.mkdir(parents=True, exist_ok=True)
        return root / _AUDIT_FILE_NAME

    def _append_audit(self, payload: Mapping[str, Any]) -> None:
        line = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        with self._audit_path().open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def _issue_access_token(self, *, encoded_license: str, state: Mapping[str, Any]) -> tuple[str, str, str]:
        now_epoch = int(time.time())
        ttl_seconds = _token_ttl_seconds()
        expires_epoch = now_epoch + ttl_seconds
        license_hash = hashlib.sha256(encoded_license.encode("utf-8")).hexdigest()[:24]
        request_id = f"libreq_{uuid.uuid4().hex}"
        claims = {
            "sub": license_hash,
            "status": str(state.get("status") or ""),
            "scope": ["library.search", "library.meta", "library.prefetch"],
            "iat": now_epoch,
            "exp": expires_epoch,
            "rid": request_id,
            "app_version": APP_VERSION,
        }
        claims_bytes = json.dumps(claims, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        claims_b64 = _b64url_encode(claims_bytes)
        signature = hmac.new(_token_secret(), claims_b64.encode("ascii"), hashlib.sha256).digest()
        token = f"{claims_b64}.{_b64url_encode(signature)}"
        expires_at = datetime.fromtimestamp(expires_epoch, tz=UTC).isoformat()
        return token, expires_at, request_id

    def issue_token(self, *, x_ta_license: str | None) -> dict[str, Any]:
        if not x_ta_license:
            raise HTTPException(status_code=401, detail="Missing X-TA-License header.")
        try:
            state = validate_encoded_license_key(
                x_ta_license,
                app_version=APP_VERSION,
                enforce_machine_binding=False,
            )
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"License could not be decoded: {exc}") from exc
        if str(state.get("status") or "") not in _ALLOWED_STATUSES:
            raise HTTPException(status_code=403, detail=state.get("message") or "Cloud library access is not allowed.")
        token, expires_at, request_id = self._issue_access_token(encoded_license=x_ta_license, state=state)
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires_at,
            "scope": ["library.search", "library.meta", "library.prefetch"],
            "request_id": request_id,
        }

    def _decode_bearer_token(self, authorization: str | None) -> dict[str, Any]:
        header = str(authorization or "").strip()
        if not header.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token.")
        token = header[7:].strip()
        if not token or "." not in token:
            raise HTTPException(status_code=401, detail="Malformed bearer token.")
        claims_b64, signature_b64 = token.split(".", 1)
        expected_sig = hmac.new(_token_secret(), claims_b64.encode("ascii"), hashlib.sha256).digest()
        try:
            actual_sig = _b64url_decode(signature_b64)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Malformed token signature: {exc}") from exc
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=401, detail="Invalid bearer token signature.")
        try:
            claims = json.loads(_b64url_decode(claims_b64).decode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Malformed token claims: {exc}") from exc
        if not isinstance(claims, Mapping):
            raise HTTPException(status_code=401, detail="Malformed token payload.")
        exp = int(claims.get("exp") or 0)
        if exp <= int(time.time()):
            raise HTTPException(status_code=401, detail="Bearer token is expired.")
        if str(claims.get("status") or "") not in _ALLOWED_STATUSES:
            raise HTTPException(status_code=403, detail="License status does not allow cloud search.")
        return dict(claims)

    def _enforce_rate_limit(self, *, subject_key: str, modality: str) -> None:
        now_epoch = time.time()
        key = f"{subject_key}:{modality.upper()}"
        window = [stamp for stamp in self._rate_windows.get(key, []) if (now_epoch - stamp) < 60.0]
        if len(window) >= _rate_limit_per_minute():
            raise HTTPException(status_code=429, detail="Cloud library rate limit exceeded.")
        window.append(now_epoch)
        self._rate_windows[key] = window

    def _provider_scope(self, analysis_type: str, rows: list[dict[str, Any]]) -> list[str]:
        seen: set[str] = set()
        for row in rows:
            token = _normalize_provider(row.get("library_provider"))
            if token:
                seen.add(token)
        if seen:
            return sorted(seen)
        defaults = _DEFAULT_PROVIDER_SCOPE.get(str(analysis_type or "").upper(), [])
        return sorted({str(item).strip().lower() for item in defaults if str(item).strip()})

    def _build_spectral_response(
        self,
        *,
        analysis_type: str,
        request_id: str,
        rows: list[dict[str, Any]],
        minimum_score: float,
    ) -> dict[str, Any]:
        top = rows[0] if rows else None
        top_score = float(top.get("normalized_score") or 0.0) if top else 0.0
        matched = bool(top) and top_score >= float(minimum_score)
        provider_scope = self._provider_scope(analysis_type, rows)
        caution_code = ""
        caution_message = ""
        if not matched:
            caution_code = "spectral_no_match"
            caution_message = (
                "A best-ranked candidate was identified, but it did not meet the configured qualitative acceptance threshold."
                if top
                else "No spectral candidates were available for qualitative matching."
            )
        elif str(top.get("confidence_band") or "").lower() == "low":
            caution_code = "spectral_low_confidence"
            caution_message = (
                "The accepted candidate remains low confidence; review similarity evidence before interpretation."
            )
        return {
            "request_id": request_id,
            "analysis_type": analysis_type,
            "match_status": "matched" if matched else "no_match",
            "candidate_count": len(rows),
            "rows": rows,
            "caution_code": caution_code,
            "caution_message": caution_message,
            "library_provider": str(top.get("library_provider") or "") if top else "",
            "library_package": str(top.get("library_package") or "") if top else "",
            "library_version": str(top.get("library_version") or "") if top else "",
            "library_access_mode": "cloud_full_access",
            "library_result_source": "cloud_search",
            "library_provider_scope": provider_scope,
            "library_offline_limited_mode": False,
            "summary": {
                "top_match_id": top.get("candidate_id") if matched and top else None,
                "top_match_name": top.get("candidate_name") if matched and top else None,
                "top_match_score": round(top_score, 4),
                "confidence_band": str(top.get("confidence_band") or "no_match") if matched and top else "no_match",
                "caution_code": caution_code,
                "caution_message": caution_message,
                "library_provider": str(top.get("library_provider") or "") if top else "",
                "library_package": str(top.get("library_package") or "") if top else "",
                "library_version": str(top.get("library_version") or "") if top else "",
            },
        }

    def _build_xrd_response(
        self,
        *,
        request_id: str,
        rows: list[dict[str, Any]],
        minimum_score: float,
        metadata: Mapping[str, Any],
        observed_space: str,
        reference_count: int,
    ) -> dict[str, Any]:
        from core.batch_runner import _build_xrd_top_candidate_summary

        top = rows[0] if rows else None
        top_score = float(top.get("normalized_score") or 0.0) if top else 0.0
        matched = bool(top) and top_score >= float(minimum_score) and str(top.get("confidence_band") or "") != "no_match"
        top_candidate_summary = _build_xrd_top_candidate_summary(
            top_match=top,
            matched=matched,
            minimum_score=float(minimum_score),
            dataset=SimpleNamespace(metadata=dict(metadata or {})),
            observed_space=str(observed_space or "two_theta"),
        )
        provider_scope = self._provider_scope("XRD", rows)
        if reference_count <= 0:
            match_status = "not_run"
            caution_code = "xrd_reference_library_unavailable"
            caution_message = (
                "No XRD provider index is currently available for qualitative phase matching."
            )
        else:
            match_status = "matched" if matched else "no_match"
            caution_code = ""
            caution_message = ""
            if not matched:
                reason = str(top_candidate_summary.get("top_candidate_reason_below_threshold") or "").strip()
                if reason:
                    reason = f" Primary limiting factors: {reason}."
                caution_code = "xrd_no_match"
                caution_message = (
                    "A best-ranked candidate was identified, but it did not meet the configured qualitative acceptance threshold."
                    " The candidate shows partial peak agreement, but unmatched major peaks and/or limited coverage prevent an accepted phase call."
                    f"{reason} Interpret as a screening result rather than a confirmed identification."
                )
            elif str(top.get("confidence_band") or "").lower() == "low":
                caution_code = "xrd_low_confidence"
                caution_message = (
                    "An accepted XRD candidate was retained, but confidence remains low."
                    " Review shared peaks, coverage, and unmatched major peaks before interpretation."
                )
        return {
            "request_id": request_id,
            "analysis_type": "XRD",
            "match_status": match_status,
            "candidate_count": len(rows),
            "rows": rows,
            "caution_code": caution_code,
            "caution_message": caution_message,
            "library_provider": str(top.get("library_provider") or "") if top else "",
            "library_package": str(top.get("library_package") or "") if top else "",
            "library_version": str(top.get("library_version") or "") if top else "",
            "library_access_mode": "cloud_full_access",
            "library_result_source": "cloud_search",
            "library_provider_scope": provider_scope,
            "library_offline_limited_mode": False,
            "summary": {
                "match_status": match_status,
                "top_phase_id": top.get("candidate_id") if matched and top else None,
                "top_phase": top.get("candidate_name") if matched and top else None,
                "top_phase_score": round(top_score, 4),
                "confidence_band": str(top.get("confidence_band") or "no_match") if matched and top else "no_match",
                "caution_code": caution_code,
                "caution_message": caution_message,
                "library_provider": str(top.get("library_provider") or "") if top else "",
                "library_package": str(top.get("library_package") or "") if top else "",
                "library_version": str(top.get("library_version") or "") if top else "",
                **top_candidate_summary,
            },
        }

    def _authorize(self, *, authorization: str | None, modality: str) -> dict[str, Any]:
        claims = self._decode_bearer_token(authorization)
        subject_key = str(claims.get("sub") or "anonymous")
        self._enforce_rate_limit(subject_key=subject_key, modality=modality)
        return claims

    def _audit_search(
        self,
        *,
        request_id: str,
        claims: Mapping[str, Any],
        modality: str,
        provider_scope: list[str],
        candidate_count: int,
        source: str,
    ) -> None:
        self._append_audit(
            {
                "request_id": request_id,
                "modality": modality,
                "license_hash": str(claims.get("sub") or ""),
                "license_status": str(claims.get("status") or ""),
                "provider_scope": provider_scope,
                "candidate_count": int(candidate_count),
                "timestamp": _utc_now_iso(),
                "source": source,
            }
        )

    def search_spectral(
        self,
        *,
        analysis_type: str,
        request_payload: Mapping[str, Any],
        authorization: str | None,
    ) -> dict[str, Any]:
        from core.batch_runner import (
            _apply_spectral_smoothing,
            _detect_spectral_peaks,
            _normalize_spectral_signal,
            _rank_spectral_matches,
            _sorted_axis_signal,
        )

        token = str(analysis_type or "").upper()
        if token not in {"FTIR", "RAMAN"}:
            raise HTTPException(status_code=400, detail=f"Unsupported analysis_type for spectral cloud search: {analysis_type}")
        claims = self._authorize(authorization=authorization, modality=token)
        request_id = f"libreq_{uuid.uuid4().hex}"
        axis = _coerce_float_array(list(request_payload.get("axis") or []))
        signal = _coerce_float_array(list(request_payload.get("signal") or []))
        if axis.size <= 2 or signal.size != axis.size:
            raise HTTPException(status_code=400, detail="axis and signal arrays are required and must have equal length.")
        axis, signal = _sorted_axis_signal(axis, signal)
        smoothed = _apply_spectral_smoothing(signal, {"method": "none"})
        normalized_signal = _normalize_spectral_signal(smoothed, {"method": "vector"})
        top_n = max(1, int(request_payload.get("top_n") or 5))
        minimum_score = float(request_payload.get("minimum_score") or 0.45)
        peak_config = {"prominence": 0.05, "min_distance": 6, "max_peaks": 12}
        observed_peaks = _detect_spectral_peaks(axis, normalized_signal, peak_config)
        rows = _rank_spectral_matches(
            axis=axis,
            normalized_signal=normalized_signal,
            observed_peaks=observed_peaks,
            references=self.manager.load_entries(token),
            matching_config={"top_n": top_n, "minimum_score": minimum_score},
            peak_config=peak_config,
        )
        response = self._build_spectral_response(
            analysis_type=token,
            request_id=request_id,
            rows=rows,
            minimum_score=minimum_score,
        )
        self._audit_search(
            request_id=request_id,
            claims=claims,
            modality=token,
            provider_scope=list(response.get("library_provider_scope") or []),
            candidate_count=int(response.get("candidate_count") or 0),
            source="cloud_search",
        )
        return response

    def search_xrd(
        self,
        *,
        request_payload: Mapping[str, Any],
        authorization: str | None,
    ) -> dict[str, Any]:
        from core.batch_runner import (
            _apply_xrd_smoothing,
            _detect_xrd_peaks,
            _estimate_xrd_baseline,
            _rank_xrd_phase_candidates,
            _sorted_axis_signal,
        )

        claims = self._authorize(authorization=authorization, modality="XRD")
        request_id = f"libreq_{uuid.uuid4().hex}"

        observed_peaks: list[dict[str, float]] = []
        for peak in list(request_payload.get("observed_peaks") or []):
            if not isinstance(peak, Mapping):
                continue
            try:
                position = float(peak.get("position")) if peak.get("position") not in (None, "") else None
            except (TypeError, ValueError):
                position = None
            try:
                d_spacing = float(peak.get("d_spacing")) if peak.get("d_spacing") not in (None, "") else None
            except (TypeError, ValueError):
                d_spacing = None
            if position is None and d_spacing is None:
                continue
            try:
                intensity = float(peak.get("intensity") or 1.0)
            except (TypeError, ValueError):
                intensity = 1.0
            payload = {"intensity": float(max(intensity, 1e-9))}
            if position is not None:
                payload["position"] = float(position)
            if d_spacing is not None:
                payload["d_spacing"] = float(d_spacing)
            observed_peaks.append(payload)

        if not observed_peaks:
            axis = _coerce_float_array(list(request_payload.get("axis") or []))
            signal = _coerce_float_array(list(request_payload.get("signal") or []))
            if axis.size >= 3 and signal.size == axis.size:
                axis, signal = _sorted_axis_signal(axis, signal)
                smoothed = _apply_xrd_smoothing(signal, {"method": "savgol", "window_length": 11, "polyorder": 3})
                baseline = _estimate_xrd_baseline(smoothed, {"method": "rolling_minimum", "window_length": 31})
                corrected = np.maximum(smoothed - baseline, 0.0)
                observed_peaks, _resolved = _detect_xrd_peaks(
                    axis,
                    corrected,
                    {"method": "scipy_find_peaks", "prominence": 0.08, "distance": 6, "width": 2, "max_peaks": 12},
                )
        axis_role = str(request_payload.get("xrd_axis_role") or "").strip().lower()
        axis_unit = str(request_payload.get("xrd_axis_unit") or "").strip().lower()
        observed_space = (
            "d_spacing"
            if axis_role in {"d_spacing", "d"} or axis_unit in {"angstrom", "a", "d_spacing", "d"}
            else "two_theta"
        )
        wavelength = request_payload.get("xrd_wavelength_angstrom")
        try:
            wavelength_angstrom = float(wavelength) if wavelength not in (None, "") else None
        except (TypeError, ValueError):
            wavelength_angstrom = None
        minimum_score = float(request_payload.get("minimum_score") or 0.42)
        top_n = max(1, int(request_payload.get("top_n") or 5))
        matching_config = {
            "metric": "peak_overlap_weighted",
            "tolerance_deg": 0.28,
            "top_n": top_n,
            "minimum_score": minimum_score,
            "intensity_weight": 0.35,
            "major_peak_fraction": 0.4,
        }
        matching_peaks = [dict(item) for item in observed_peaks]
        if observed_space == "d_spacing":
            for peak in matching_peaks:
                if "d_spacing" not in peak and peak.get("position") not in (None, ""):
                    peak["d_spacing"] = float(peak["position"])
                if wavelength_angstrom is not None:
                    peak["wavelength_angstrom"] = float(wavelength_angstrom)
        references = self.manager.load_entries("XRD")
        rows = _rank_xrd_phase_candidates(
            observed_peaks=matching_peaks,
            references=references,
            matching_config=matching_config,
            comparison_space=observed_space,
            wavelength_angstrom=wavelength_angstrom,
        )
        response = self._build_xrd_response(
            request_id=request_id,
            rows=rows,
            minimum_score=minimum_score,
            metadata={
                "xrd_axis_role": request_payload.get("xrd_axis_role"),
                "xrd_axis_unit": request_payload.get("xrd_axis_unit"),
                "xrd_wavelength_angstrom": wavelength_angstrom,
                "import_review_required": bool(request_payload.get("import_metadata", {}).get("import_review_required")),
            },
            observed_space=observed_space,
            reference_count=len(references),
        )
        self._audit_search(
            request_id=request_id,
            claims=claims,
            modality="XRD",
            provider_scope=list(response.get("library_provider_scope") or []),
            candidate_count=int(response.get("candidate_count") or 0),
            source="cloud_search",
        )
        return response

    def providers(self, *, authorization: str | None) -> dict[str, Any]:
        claims = self._authorize(authorization=authorization, modality="META")
        request_id = f"libreq_{uuid.uuid4().hex}"
        catalog = self.manager.catalog()
        providers: dict[str, dict[str, Any]] = {}
        for row in catalog:
            provider = _normalize_provider(row.get("provider"))
            if not provider:
                continue
            item = providers.setdefault(
                provider,
                {
                    "provider_id": provider,
                    "name": row.get("provider"),
                    "analysis_types": set(),
                    "package_count": 0,
                    "entry_count": 0,
                },
            )
            item["analysis_types"].add(str(row.get("analysis_type") or "").upper())
            item["package_count"] += 1
            item["entry_count"] += int(row.get("entry_count") or 0)
        for defaults in _DEFAULT_PROVIDER_SCOPE.values():
            for provider in defaults:
                providers.setdefault(
                    provider,
                    {
                        "provider_id": provider,
                        "name": provider,
                        "analysis_types": set(),
                        "package_count": 0,
                        "entry_count": 0,
                    },
                )
        rows = []
        for payload in sorted(providers.values(), key=lambda item: str(item["provider_id"])):
            rows.append(
                {
                    "provider_id": payload["provider_id"],
                    "name": payload["name"],
                    "analysis_types": sorted(payload["analysis_types"]),
                    "package_count": payload["package_count"],
                    "entry_count": payload["entry_count"],
                }
            )
        self._audit_search(
            request_id=request_id,
            claims=claims,
            modality="META",
            provider_scope=[item["provider_id"] for item in rows],
            candidate_count=len(rows),
            source="cloud_search",
        )
        return {
            "request_id": request_id,
            "providers": rows,
            "library_access_mode": "cloud_full_access",
        }

    def coverage(self, *, authorization: str | None) -> dict[str, Any]:
        claims = self._authorize(authorization=authorization, modality="META")
        request_id = f"libreq_{uuid.uuid4().hex}"
        catalog = self.manager.catalog()
        coverage: dict[str, dict[str, Any]] = {}
        for modality in ("FTIR", "RAMAN", "XRD"):
            rows = [row for row in catalog if str(row.get("analysis_type") or "").upper() == modality]
            coverage[modality] = {
                "package_count": len(rows),
                "entry_count": sum(int(row.get("entry_count") or 0) for row in rows),
                "providers": sorted({_normalize_provider(row.get("provider")) for row in rows if row.get("provider")}),
            }
        self._audit_search(
            request_id=request_id,
            claims=claims,
            modality="META",
            provider_scope=sorted({provider for item in coverage.values() for provider in item.get("providers", [])}),
            candidate_count=sum(int(item.get("entry_count") or 0) for item in coverage.values()),
            source="cloud_search",
        )
        return {
            "request_id": request_id,
            "coverage": coverage,
            "library_access_mode": "cloud_full_access",
        }

    def prefetch(self, *, request_payload: Mapping[str, Any], authorization: str | None) -> dict[str, Any]:
        claims = self._authorize(authorization=authorization, modality="PREFETCH")
        request_id = f"libreq_{uuid.uuid4().hex}"
        package_ids = request_payload.get("package_ids")
        if package_ids is not None and not isinstance(package_ids, list):
            raise HTTPException(status_code=400, detail="package_ids must be an array when provided.")
        status = self.manager.sync(
            package_ids=[str(item) for item in (package_ids or [])],
            force=bool(request_payload.get("force")),
        )
        self._audit_search(
            request_id=request_id,
            claims=claims,
            modality="PREFETCH",
            provider_scope=[],
            candidate_count=int(status.get("fallback_entry_count") or 0),
            source="limited_fallback_cache",
        )
        return {
            "request_id": request_id,
            "status": "ok",
            "synced_package_ids": [item.package_id for item in self.manager.installed_packages()],
            "fallback_package_count": int(status.get("fallback_package_count") or 0),
            "fallback_entry_count": int(status.get("fallback_entry_count") or 0),
        }


_SERVICE_INSTANCE: ManagedLibraryCloudService | None = None


def get_library_cloud_service() -> ManagedLibraryCloudService:
    global _SERVICE_INSTANCE
    if _SERVICE_INSTANCE is None:
        _SERVICE_INSTANCE = ManagedLibraryCloudService()
    return _SERVICE_INSTANCE

