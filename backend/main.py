"""Backend service entrypoint for local desktop bootstrap."""

from __future__ import annotations

import argparse
import socket
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from backend.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_DOTENV_PATH = REPO_ROOT / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ThermoAnalyzer backend service.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--token", default="", help="Optional API token for desktop shell calls")
    return parser.parse_args()


def _preflight_bind(host: str, port: int) -> None:
    family = socket.AF_INET6 if ":" in str(host or "") and host != "0.0.0.0" else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))


def main() -> None:
    load_dotenv(dotenv_path=REPO_DOTENV_PATH, override=False)
    args = parse_args()
    bind_url = f"http://{args.host}:{args.port}"
    print(f"ThermoAnalyzer backend starting on {bind_url}", flush=True)
    if REPO_DOTENV_PATH.exists():
        print(f"ThermoAnalyzer backend env: {REPO_DOTENV_PATH}", flush=True)
    try:
        _preflight_bind(args.host, int(args.port))
    except OSError as exc:
        raise SystemExit(f"ThermoAnalyzer backend failed preflight bind on {bind_url}: {exc}") from exc
    app = create_app(api_token=args.token or None)

    @app.on_event("startup")
    async def _log_bound_address() -> None:
        print(f"ThermoAnalyzer backend listening on {bind_url}", flush=True)
        bootstrap_status = dict(getattr(app.state, "cloud_library_bootstrap_status", {}) or {})
        state = str(bootstrap_status.get("state") or "").strip()
        if bootstrap_status:
            print(
                "ThermoAnalyzer hosted library bootstrap "
                f"state={state or 'unknown'} "
                f"hosted_root={bootstrap_status.get('hosted_root') or 'n/a'} "
                f"source_root={bootstrap_status.get('source_root') or 'n/a'} "
                f"reason={bootstrap_status.get('upgrade_reason') or bootstrap_status.get('message') or 'n/a'}",
                flush=True,
            )
            print(
                "ThermoAnalyzer hosted library XRD coverage "
                f"previous={bootstrap_status.get('previous_xrd_count', 'n/a')}/"
                f"{bootstrap_status.get('previous_coverage_tier', 'n/a')} "
                f"selected_source={bootstrap_status.get('selected_source_xrd_count', 'n/a')}/"
                f"{bootstrap_status.get('selected_source_total_count', 'n/a')} "
                f"active={bootstrap_status.get('active_xrd_count', bootstrap_status.get('new_xrd_count', 'n/a'))}/"
                f"{bootstrap_status.get('active_coverage_tier', bootstrap_status.get('new_coverage_tier', 'n/a'))}",
                flush=True,
            )
        if state == "published":
            print(
                "ThermoAnalyzer hosted library bootstrap published "
                f"{bootstrap_status.get('dataset_count', 0)} datasets from {bootstrap_status.get('source_root')}",
                flush=True,
            )
        elif state == "upgraded":
            print(
                f"ThermoAnalyzer hosted library upgraded: "
                f"XRD {bootstrap_status.get('previous_xrd_count', '?')} → {bootstrap_status.get('new_xrd_count', '?')} "
                f"(tier {bootstrap_status.get('previous_coverage_tier', '?')} → {bootstrap_status.get('new_coverage_tier', '?')}) "
                f"from {bootstrap_status.get('source_root')} "
                f"[reason: {bootstrap_status.get('upgrade_reason', 'unknown')}]",
                flush=True,
            )
        elif state == "already_present":
            print(
                f"ThermoAnalyzer hosted library already present "
                f"(XRD {bootstrap_status.get('previous_xrd_count', '?')}, "
                f"tier={bootstrap_status.get('previous_coverage_tier', '?')}, "
                f"reason={bootstrap_status.get('upgrade_reason', 'n/a')})",
                flush=True,
            )
        elif state in ("publish_failed", "upgrade_failed"):
            print(
                f"ThermoAnalyzer hosted library bootstrap failed: {bootstrap_status.get('message')}",
                flush=True,
            )

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except Exception as exc:
        raise SystemExit(f"ThermoAnalyzer backend failed to start on {bind_url}: {exc}") from exc


if __name__ == "__main__":
    main()
