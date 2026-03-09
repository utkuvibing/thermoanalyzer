"""Build the desktop backend executable with PyInstaller (Windows-focused)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ThermoAnalyzer desktop backend executable.")
    parser.add_argument("--clean", action="store_true", help="Clean previous build/dist outputs before building.")
    return parser.parse_args()


def run_command(command: list[str], *, cwd: Path) -> None:
    print(f"[backend-build] running: {' '.join(command)}")
    subprocess.run(command, cwd=str(cwd), check=True)


def ensure_pyinstaller_available(python_exe: str, repo_root: Path) -> None:
    probe = [python_exe, "-m", "PyInstaller", "--version"]
    try:
        subprocess.run(probe, cwd=str(repo_root), check=True, capture_output=True, text=True)
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PyInstaller is not available. Install it in your build environment with: "
            f"'{python_exe} -m pip install pyinstaller'"
        ) from exc


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    build_dir = script_dir / "build"
    dist_dir = script_dir / "dist"
    hooks_dir = script_dir / "pyinstaller_hooks"
    entrypoint = script_dir / "backend_entrypoint.py"
    python_exe = sys.executable

    if args.clean:
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.rmtree(dist_dir, ignore_errors=True)

    ensure_pyinstaller_available(python_exe, repo_root)

    command = [
        python_exe,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "thermoanalyzer_backend",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(build_dir),
        "--paths",
        str(repo_root),
        "--additional-hooks-dir",
        str(hooks_dir),
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        str(entrypoint),
    ]
    run_command(command, cwd=repo_root)

    exe_name = "thermoanalyzer_backend.exe" if sys.platform.startswith("win") else "thermoanalyzer_backend"
    built_exe = dist_dir / "thermoanalyzer_backend" / exe_name
    if not built_exe.exists():  # pragma: no cover - environment dependent
        raise RuntimeError(f"Backend build did not produce expected executable: {built_exe}")

    print(f"[backend-build] backend executable ready: {built_exe}")


if __name__ == "__main__":
    main()
