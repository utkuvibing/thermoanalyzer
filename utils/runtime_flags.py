"""Runtime feature flags for shaping the app surface by deployment profile."""

from __future__ import annotations

import os


PREVIEW_MODULES_ENV = "MATERIALSCOPE_ENABLE_PREVIEW_MODULES"


def _truthy(value: str | None) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "on"}


def preview_modules_enabled(*, default: bool = False) -> bool:
    """Return whether experimental preview modules should be exposed in navigation."""
    raw = os.getenv(PREVIEW_MODULES_ENV)
    if raw is None:
        return bool(default)
    return _truthy(raw)
