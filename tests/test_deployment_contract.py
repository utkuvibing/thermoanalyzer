from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_dockerfile_keeps_streamlit_runtime_contract():
    dockerfile = _repo_text("Dockerfile")

    assert "FROM python:3.12-slim" in dockerfile
    assert "chromium" in dockerfile
    assert "curl" in dockerfile
    assert "BROWSER_PATH=/usr/bin/chromium" in dockerfile
    assert "CHROME_BIN=/usr/bin/chromium" in dockerfile
    assert "EXPOSE 8501" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8501/_stcore/health" in dockerfile
    assert 'CMD ["/app/docker/start.sh"]' in dockerfile


def test_container_entrypoint_waits_for_backend_before_ui():
    start_script = _repo_text("docker/start.sh")

    assert 'timeout_seconds="${BACKEND_STARTUP_TIMEOUT_SECONDS:-30}"' in start_script
    assert 'curl --silent --fail http://127.0.0.1:8000/health' in start_script
    assert ': "${THERMOANALYZER_LIBRARY_CLOUD_URL:=http://127.0.0.1:8000}"' in start_script
    assert "python -m backend.main --host 127.0.0.1 --port 8000 &" in start_script
    assert "wait_for_backend" in start_script
    assert "streamlit run app.py --server.address=0.0.0.0 --server.port=8501 &" in start_script


def test_env_example_documents_runtime_surface_flags():
    env_example = _repo_text(".env.example")

    assert "THERMOANALYZER_LIBRARY_CLOUD_URL=http://127.0.0.1:8000" in env_example
    assert "THERMOANALYZER_LIBRARY_CLOUD_ENABLED=true" in env_example
    assert "THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH=true" in env_example
    assert "MATERIALSCOPE_ENABLE_PREVIEW_MODULES=false" in env_example


def test_readme_documents_preview_and_backend_startup_runtime_flags():
    readme = _repo_text("README.md")

    assert "Streamlit waits for backend health before the UI process starts" in readme
    assert "MATERIALSCOPE_ENABLE_PREVIEW_MODULES=false" in readme
    assert "Set `MATERIALSCOPE_ENABLE_PREVIEW_MODULES=true` only in builds" in readme
    assert "BACKEND_STARTUP_TIMEOUT_SECONDS=30" in readme
