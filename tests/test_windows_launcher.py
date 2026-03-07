from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_windows_launcher():
    launcher_path = Path(__file__).resolve().parents[1] / "packaging" / "windows" / "launcher.py"
    spec = importlib.util.spec_from_file_location("thermoanalyzer_windows_launcher", launcher_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ensure_user_runtime_creates_expected_directories_and_config(monkeypatch, tmp_path):
    launcher = _load_windows_launcher()
    resource_root = tmp_path / "bundle"
    user_root = tmp_path / "runtime"

    (resource_root / ".streamlit").mkdir(parents=True, exist_ok=True)
    (resource_root / ".streamlit" / "config.toml").write_text("[server]\nheadless = true\n", encoding="utf-8")

    monkeypatch.delenv("THERMOANALYZER_HOME", raising=False)
    monkeypatch.delenv("STREAMLIT_BROWSER_GATHER_USAGE_STATS", raising=False)

    launcher._ensure_user_runtime(resource_root, user_root)

    assert (user_root / "support_logs").is_dir()
    assert (user_root / ".streamlit").is_dir()
    assert (user_root / ".streamlit" / "config.toml").exists()
    assert (user_root / ".streamlit" / "config.toml").read_text(encoding="utf-8").startswith("[server]")
    assert not (user_root / ".thermoanalyzer_write_probe").exists()
    assert not (user_root / "support_logs" / ".thermoanalyzer_write_probe").exists()
    assert not (user_root / ".streamlit" / ".thermoanalyzer_write_probe").exists()
    assert launcher.os.environ["THERMOANALYZER_HOME"] == str(user_root)
    assert launcher.os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] == "false"
