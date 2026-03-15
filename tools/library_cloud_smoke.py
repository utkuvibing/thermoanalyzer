"""Local smoke helper for managed cloud-library endpoints.

Usage:
    python tools/library_cloud_smoke.py --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.license_manager import APP_VERSION, create_signed_license, encode_license_key


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cloud-library local smoke checks.")
    parser.add_argument(
        "--base-url",
        default=str(os.getenv("THERMOANALYZER_LIBRARY_CLOUD_URL") or "http://127.0.0.1:8000").strip(),
        help="Backend base URL (default: THERMOANALYZER_LIBRARY_CLOUD_URL or http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds (default: 20).",
    )
    parser.add_argument(
        "--license-key",
        default="",
        help="Optional encoded X-TA-License value. If omitted, a local trial key is generated.",
    )
    return parser.parse_args()


def _major_version(app_version: str) -> int:
    try:
        return int(str(app_version).split(".", 1)[0])
    except Exception:
        return 1


def _generated_license_key() -> str:
    now = datetime.now(UTC)
    payload = create_signed_license(
        customer_name="Local Smoke User",
        company_name="ThermoAnalyzer Dev",
        sku="TRIAL",
        seat_count=1,
        issued_at=now,
        expires_at=now + timedelta(days=30),
        allowed_major_version=_major_version(APP_VERSION),
        machine_fingerprint="local-cloud-smoke",
    )
    return encode_license_key(payload)


def _request_json(
    client: httpx.Client,
    *,
    method: str,
    path: str,
    headers: Mapping[str, str] | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method=method, url=path, headers=dict(headers or {}), json=dict(payload or {}))
    if response.status_code != 200:
        raise RuntimeError(f"{method} {path} failed: {response.status_code} {response.text}")
    data = response.json()
    if not isinstance(data, Mapping):
        raise RuntimeError(f"{method} {path} returned non-object JSON payload.")
    return dict(data)


def _assert_cloud_payload(payload: Mapping[str, Any], *, require_result_source: bool = False) -> None:
    if str(payload.get("library_access_mode") or "") != "cloud_full_access":
        raise RuntimeError(f"Expected library_access_mode=cloud_full_access, got {payload.get('library_access_mode')!r}")
    if not str(payload.get("request_id") or "").strip():
        raise RuntimeError("Expected non-empty request_id in cloud payload.")
    if require_result_source and str(payload.get("library_result_source") or "") != "cloud_search":
        raise RuntimeError(f"Expected library_result_source=cloud_search, got {payload.get('library_result_source')!r}")


def main() -> None:
    args = _build_args()
    base_url = str(args.base_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("Missing base URL.")

    encoded_license = str(args.license_key or "").strip() or _generated_license_key()
    with httpx.Client(base_url=base_url, timeout=float(args.timeout)) as client:
        auth_payload = _request_json(
            client,
            method="POST",
            path="/v1/library/auth/token",
            headers={"X-TA-License": encoded_license},
        )
        access_token = str(auth_payload.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("auth/token response did not include access_token.")
        bearer = {"Authorization": f"Bearer {access_token}"}

        providers_payload = _request_json(client, method="GET", path="/v1/library/providers", headers=bearer)
        _assert_cloud_payload(providers_payload, require_result_source=False)

        coverage_payload = _request_json(client, method="GET", path="/v1/library/coverage", headers=bearer)
        _assert_cloud_payload(coverage_payload, require_result_source=False)

        ftir_payload = _request_json(
            client,
            method="POST",
            path="/v1/library/search/ftir",
            headers=bearer,
            payload={
                "axis": [600.0, 900.0, 1200.0, 1500.0, 1800.0],
                "signal": [0.12, 0.35, 0.56, 0.34, 0.18],
                "top_n": 3,
                "minimum_score": 0.45,
            },
        )
        _assert_cloud_payload(ftir_payload, require_result_source=True)

        raman_payload = _request_json(
            client,
            method="POST",
            path="/v1/library/search/raman",
            headers=bearer,
            payload={
                "axis": [450.0, 700.0, 1000.0, 1350.0, 1600.0],
                "signal": [0.11, 0.42, 0.68, 0.39, 0.21],
                "top_n": 3,
                "minimum_score": 0.45,
            },
        )
        _assert_cloud_payload(raman_payload, require_result_source=True)

        xrd_payload = _request_json(
            client,
            method="POST",
            path="/v1/library/search/xrd",
            headers=bearer,
            payload={
                "observed_peaks": [
                    {"position": 18.4, "intensity": 0.72},
                    {"position": 33.2, "intensity": 1.0},
                    {"position": 47.8, "intensity": 0.85},
                ],
                "xrd_axis_role": "two_theta",
                "xrd_axis_unit": "degree_2theta",
                "xrd_wavelength_angstrom": 1.5406,
                "top_n": 3,
                "minimum_score": 0.42,
            },
        )
        _assert_cloud_payload(xrd_payload, require_result_source=True)

    print("Cloud library smoke passed: auth/token -> providers -> coverage -> ftir/raman/xrd")


if __name__ == "__main__":
    main()
