from __future__ import annotations

from utils.runtime_flags import preview_modules_enabled


def test_preview_modules_default_to_disabled(monkeypatch):
    monkeypatch.delenv("MATERIALSCOPE_ENABLE_PREVIEW_MODULES", raising=False)
    assert preview_modules_enabled() is False


def test_preview_modules_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("MATERIALSCOPE_ENABLE_PREVIEW_MODULES", "true")
    assert preview_modules_enabled() is True


def test_preview_modules_can_be_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("MATERIALSCOPE_ENABLE_PREVIEW_MODULES", "false")
    assert preview_modules_enabled(default=True) is False
