"""Windows launcher for packaged ThermoAnalyzer beta builds.

This keeps the current Streamlit architecture intact:
- start the app locally
- open the default browser
- keep writable user data/logs out of Program Files
"""

from __future__ import annotations

import ctypes
import os
import shutil
import socket
import sys
from pathlib import Path

import streamlit.web.bootstrap as bootstrap


APP_NAME = "ThermoAnalyzer Beta"
APP_EXE_NAME = "ThermoAnalyzerLauncher"
PREFERRED_PORT = 8501
MAX_PORT_ATTEMPTS = 25


def _resource_root() -> Path:
    """Return the packaged resource root or repo root in dev mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _user_data_root() -> Path:
    """Return the writable per-user runtime directory."""
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME
    return Path.home() / f".{APP_NAME.lower().replace(' ', '_')}"


def _show_startup_error(message: str) -> None:
    """Show a visible startup error when the packaged app has no console."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)
    except Exception:
        print(message, file=sys.stderr)


def _assert_writable_directory(path: Path) -> None:
    """Fail early with a clear message if the runtime path is not writable."""
    probe = path / ".thermoanalyzer_write_probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def _ensure_user_runtime(resource_root: Path, user_root: Path) -> None:
    """Create writable runtime directories and seed Streamlit config."""
    user_root.mkdir(parents=True, exist_ok=True)
    (user_root / "support_logs").mkdir(parents=True, exist_ok=True)
    user_streamlit_dir = user_root / ".streamlit"
    user_streamlit_dir.mkdir(parents=True, exist_ok=True)
    _assert_writable_directory(user_root)
    _assert_writable_directory(user_root / "support_logs")
    _assert_writable_directory(user_streamlit_dir)

    bundled_config = resource_root / ".streamlit" / "config.toml"
    target_config = user_streamlit_dir / "config.toml"
    if bundled_config.exists() and not target_config.exists():
        shutil.copy2(bundled_config, target_config)

    os.environ.setdefault("THERMOANALYZER_HOME", str(user_root))
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")


def _pick_available_port(preferred_port: int = PREFERRED_PORT, attempts: int = MAX_PORT_ATTEMPTS) -> int:
    """Pick a local TCP port, preferring 8501 for familiarity."""
    for port in range(preferred_port, preferred_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free localhost port was available for the packaged ThermoAnalyzer beta.")


def main() -> None:
    resource_root = _resource_root()
    app_script = resource_root / "app.py"
    if not app_script.exists():
        _show_startup_error(
            f"{APP_NAME} could not locate app.py inside the packaged runtime.\n\n"
            "Rebuild the beta package and try again."
        )
        raise SystemExit(1)

    user_root = _user_data_root()
    _ensure_user_runtime(resource_root, user_root)
    os.chdir(user_root)

    try:
        port = _pick_available_port()
        flag_options = {
            "server.headless": False,
            "server.address": "127.0.0.1",
            "server.port": port,
            "server.fileWatcherType": "none",
            "server.runOnSave": False,
            "browser.serverAddress": "127.0.0.1",
            "browser.gatherUsageStats": False,
            "global.developmentMode": False,
        }
        bootstrap.run(str(app_script), False, [], flag_options)
    except Exception as exc:
        _show_startup_error(
            f"{APP_NAME} could not start.\n\n"
            f"Reason: {exc}\n\n"
            f"Support files are stored in:\n{user_root}"
        )
        raise


if __name__ == "__main__":
    main()
