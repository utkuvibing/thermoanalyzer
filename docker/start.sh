#!/bin/sh
set -eu

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
