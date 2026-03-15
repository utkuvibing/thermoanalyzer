"""Backend service entrypoint for local desktop bootstrap."""

from __future__ import annotations

import argparse

import uvicorn

from backend.app import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ThermoAnalyzer backend service.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--token", default="", help="Optional API token for desktop shell calls")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(api_token=args.token or None)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
