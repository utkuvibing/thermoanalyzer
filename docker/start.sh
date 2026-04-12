#!/bin/sh
set -eu

wait_for_backend() {
  timeout_seconds="${BACKEND_STARTUP_TIMEOUT_SECONDS:-30}"
  elapsed=0
  while [ "${elapsed}" -lt "${timeout_seconds}" ]; do
    if curl --silent --fail http://127.0.0.1:8000/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  echo "MaterialScope backend did not become healthy within ${timeout_seconds}s." >&2
  return 1
}

cleanup() {
  for pid in ${BACKEND_PID:-} ${STREAMLIT_PID:-}; do
    if [ -n "${pid:-}" ] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

: "${THERMOANALYZER_LIBRARY_CLOUD_URL:=http://127.0.0.1:8000}"
export THERMOANALYZER_LIBRARY_CLOUD_URL

python -m backend.main --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

wait_for_backend

streamlit run app.py --server.address=0.0.0.0 --server.port=8501 &
STREAMLIT_PID=$!

while kill -0 "${BACKEND_PID}" 2>/dev/null && kill -0 "${STREAMLIT_PID}" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
  wait "${BACKEND_PID}" || true
  exit 1
fi

wait "${STREAMLIT_PID}"
