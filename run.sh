#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WINDOWS_PYTHON="$ROOT_DIR/venv/Scripts/python.exe"
DEFAULT_UNIX_PYTHON="$ROOT_DIR/venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-}"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$DEFAULT_WINDOWS_PYTHON" ]]; then
    PYTHON_BIN="$DEFAULT_WINDOWS_PYTHON"
  elif [[ -x "$DEFAULT_UNIX_PYTHON" ]]; then
    PYTHON_BIN="$DEFAULT_UNIX_PYTHON"
  else
    PYTHON_BIN="$(command -v python3 || command -v python || true)"
  fi
fi

if [[ -z "$PYTHON_BIN" ]] || [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found at $PYTHON_BIN"
  echo "Set PYTHON_BIN to your Python path or create the venv first."
  exit 1
fi

cd "$ROOT_DIR/backend"
"$PYTHON_BIN" -m uvicorn api:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
pnpm dev &
FRONTEND_PID=$!

echo "Backend running at http://127.0.0.1:8000"
echo "Frontend running at http://127.0.0.1:3000"

wait "$BACKEND_PID" "$FRONTEND_PID"
