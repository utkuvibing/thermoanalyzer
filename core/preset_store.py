"""Local processing-preset store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.processing_schema import ensure_processing_payload
from utils.license_manager import get_storage_dir


MAX_PRESETS_PER_ANALYSIS = 10
PRESET_DB_FILE = "analysis_presets.db"
VALID_ANALYSIS_TYPES = frozenset({"DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD"})


class PresetStoreError(ValueError):
    """Raised when preset payload or identity is invalid."""


class PresetLimitError(PresetStoreError):
    """Raised when the per-analysis preset limit is reached."""


def _timestamp_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_analysis_type(analysis_type: str) -> str:
    token = str(analysis_type or "").strip().upper()
    if token not in VALID_ANALYSIS_TYPES:
        raise PresetStoreError(f"Unsupported analysis type: {analysis_type!r}")
    return token


def _normalize_preset_name(preset_name: str) -> str:
    token = str(preset_name or "").strip()
    if not token:
        raise PresetStoreError("Preset name cannot be empty.")
    if len(token) > 80:
        raise PresetStoreError("Preset name cannot exceed 80 characters.")
    return token


def _db_path() -> Path:
    root = get_storage_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / PRESET_DB_FILE


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_presets (
            analysis_type TEXT NOT NULL,
            preset_name TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (analysis_type, preset_name)
        )
        """
    )


def _normalize_payload(analysis_type: str, processing_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(processing_payload, dict):
        raise PresetStoreError("processing_payload must be a dict.")

    if "processing" in processing_payload and isinstance(processing_payload.get("processing"), dict):
        raw_processing = dict(processing_payload.get("processing") or {})
        workflow_template_id = str(processing_payload.get("workflow_template_id") or raw_processing.get("workflow_template_id") or "").strip()
    else:
        raw_processing = dict(processing_payload)
        workflow_template_id = str(raw_processing.get("workflow_template_id") or "").strip()

    normalized_processing = ensure_processing_payload(
        raw_processing,
        analysis_type=analysis_type,
        workflow_template=workflow_template_id or None,
    )
    resolved_template_id = str(normalized_processing.get("workflow_template_id") or workflow_template_id or "").strip()
    if not resolved_template_id:
        raise PresetStoreError("workflow_template_id is required in preset payload.")

    payload = {
        "workflow_template_id": resolved_template_id,
        "processing": normalized_processing,
    }
    # Validate JSON serialization eagerly.
    json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return payload


def list_presets(analysis_type: str) -> list[dict[str, Any]]:
    normalized_type = _normalize_analysis_type(analysis_type)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT analysis_type, preset_name, payload_json, created_at, updated_at
            FROM analysis_presets
            WHERE analysis_type = ?
            ORDER BY updated_at DESC, preset_name ASC
            """,
            (normalized_type,),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        workflow_template_id = ""
        try:
            payload = json.loads(str(row["payload_json"]))
            workflow_template_id = str(payload.get("workflow_template_id") or "")
        except Exception:
            workflow_template_id = ""
        items.append(
            {
                "analysis_type": str(row["analysis_type"]),
                "preset_name": str(row["preset_name"]),
                "workflow_template_id": workflow_template_id,
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
        )
    return items


def count_presets(analysis_type: str) -> int:
    normalized_type = _normalize_analysis_type(analysis_type)
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count_value FROM analysis_presets WHERE analysis_type = ?",
            (normalized_type,),
        ).fetchone()
    return int((row or {"count_value": 0})["count_value"] or 0)


def load_preset(analysis_type: str, preset_name: str) -> dict[str, Any] | None:
    normalized_type = _normalize_analysis_type(analysis_type)
    normalized_name = _normalize_preset_name(preset_name)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM analysis_presets
            WHERE analysis_type = ? AND preset_name = ?
            """,
            (normalized_type, normalized_name),
        ).fetchone()
    if row is None:
        return None

    try:
        payload = json.loads(str(row["payload_json"]))
    except Exception as exc:
        raise PresetStoreError(f"Stored preset payload is invalid JSON: {exc}") from exc
    return _normalize_payload(normalized_type, payload)


def save_preset(analysis_type: str, preset_name: str, processing_payload: dict[str, Any]) -> dict[str, Any]:
    normalized_type = _normalize_analysis_type(analysis_type)
    normalized_name = _normalize_preset_name(preset_name)
    payload = _normalize_payload(normalized_type, processing_payload)
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    now = _timestamp_utc()

    with _connect() as conn:
        with conn:
            existing = conn.execute(
                """
                SELECT 1
                FROM analysis_presets
                WHERE analysis_type = ? AND preset_name = ?
                """,
                (normalized_type, normalized_name),
            ).fetchone()
            if existing is None:
                count_row = conn.execute(
                    "SELECT COUNT(*) AS count_value FROM analysis_presets WHERE analysis_type = ?",
                    (normalized_type,),
                ).fetchone()
                current_count = int((count_row or {"count_value": 0})["count_value"] or 0)
                if current_count >= MAX_PRESETS_PER_ANALYSIS:
                    raise PresetLimitError(
                        f"{normalized_type} preset limit reached ({MAX_PRESETS_PER_ANALYSIS})."
                    )
                conn.execute(
                    """
                    INSERT INTO analysis_presets (
                        analysis_type, preset_name, payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (normalized_type, normalized_name, payload_json, now, now),
                )
            else:
                conn.execute(
                    """
                    UPDATE analysis_presets
                    SET payload_json = ?, updated_at = ?
                    WHERE analysis_type = ? AND preset_name = ?
                    """,
                    (payload_json, now, normalized_type, normalized_name),
                )

    return {
        "analysis_type": normalized_type,
        "preset_name": normalized_name,
        "workflow_template_id": payload["workflow_template_id"],
        "updated_at": now,
    }


def delete_preset(analysis_type: str, preset_name: str) -> bool:
    normalized_type = _normalize_analysis_type(analysis_type)
    normalized_name = _normalize_preset_name(preset_name)
    with _connect() as conn:
        with conn:
            cursor = conn.execute(
                """
                DELETE FROM analysis_presets
                WHERE analysis_type = ? AND preset_name = ?
                """,
                (normalized_type, normalized_name),
            )
    return bool(cursor.rowcount)
