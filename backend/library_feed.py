"""FastAPI feed service for curated reference-library packages."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Response

from core.reference_library import MANIFEST_FILE
from utils.license_manager import APP_VERSION, validate_encoded_license_key


def _mirror_root(path: str | Path | None) -> Path:
    if path is None:
        return Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    return Path(path).resolve()


def _load_manifest(root: Path) -> dict:
    manifest_path = root / MANIFEST_FILE
    if not manifest_path.exists():
        raise FileNotFoundError(f"Mirror manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _require_feed_license(x_ta_license: str | None) -> dict:
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

    if state.get("status") not in {"trial", "activated"}:
        raise HTTPException(status_code=403, detail=state.get("message") or "Library feed access is not allowed.")
    return state


def create_library_feed_app(*, mirror_root: str | Path | None = None) -> FastAPI:
    root = _mirror_root(mirror_root)
    app = FastAPI(title="ThermoAnalyzer Reference Library Feed", version="1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "thermoanalyzer-library-feed"}

    @app.get("/v1/library/manifest")
    def manifest(
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
        x_ta_license: str | None = Header(default=None, alias="X-TA-License"),
    ) -> Response:
        _require_feed_license(x_ta_license)
        payload = _load_manifest(root)
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        etag = str(payload.get("etag") or "")
        if if_none_match and etag and if_none_match == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return Response(content=body, media_type="application/json", headers={"ETag": etag})

    @app.get("/v1/library/packages/{package_id}")
    def package_download(
        package_id: str,
        x_ta_license: str | None = Header(default=None, alias="X-TA-License"),
    ) -> Response:
        _require_feed_license(x_ta_license)
        manifest = _load_manifest(root)
        packages = manifest.get("packages") or []
        package = next((item for item in packages if str(item.get("package_id")) == str(package_id)), None)
        if package is None:
            raise HTTPException(status_code=404, detail=f"Unknown package_id: {package_id}")

        archive_name = str(package.get("archive_name") or package.get("file_name") or "").strip()
        archive_path = root / "packages" / archive_name
        if not archive_path.exists():
            raise HTTPException(status_code=404, detail=f"Package archive not found: {archive_name}")

        return Response(
            content=archive_path.read_bytes(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{archive_name}"'},
        )

    return app
