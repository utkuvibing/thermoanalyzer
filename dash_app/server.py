"""Combined FastAPI + Dash server entrypoint.

Run with: python -m dash_app.server
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from a2wsgi import WSGIMiddleware

from backend.app import create_app as create_backend
from dash_app.app import create_dash_app

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MaterialScope (Dash + FastAPI).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--token", default="")
    return parser.parse_args()


def create_combined_app(*, api_token: str | None = None):
    """Create a FastAPI app with the Dash UI mounted as WSGI fallback."""
    api = create_backend(api_token=api_token)
    dash = create_dash_app()
    api.mount("/", WSGIMiddleware(dash.server))
    return api


def main() -> None:
    load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
    args = parse_args()
    app = create_combined_app(api_token=args.token or None)
    print(f"MaterialScope (Dash) starting on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
