#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_WINDOWS_PYTHON="$ROOT_DIR/venv/Scripts/python.exe"
DEFAULT_UNIX_PYTHON="$ROOT_DIR/venv/bin/python"
PYTHON_BIN="${PYTHON_BIN:-}"
BACKEND_PID=""
FRONTEND_PID=""

usage() {
  cat <<'EOF'
Usage: ./run.sh [command] [args...]

Commands:
  install         Install backend and frontend dependencies
  run [args...]   Run the backend CLI scraper
  api             Run the backend API server
  dev             Run the frontend dev server
  test            Run backend tests
  stack           Run backend API and frontend dev server together

If no command is provided, `stack` is used.
EOF
}

cleanup() {
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}

resolve_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return
  fi

  if [[ -x "$DEFAULT_WINDOWS_PYTHON" ]]; then
    PYTHON_BIN="$DEFAULT_WINDOWS_PYTHON"
  elif [[ -x "$DEFAULT_UNIX_PYTHON" ]]; then
    PYTHON_BIN="$DEFAULT_UNIX_PYTHON"
  else
    PYTHON_BIN="$(command -v python3 || command -v python || true)"
  fi
}

ensure_python() {
  resolve_python
  if [[ -z "$PYTHON_BIN" ]] || [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python executable not found at ${PYTHON_BIN:-<unset>}"
    echo "Set PYTHON_BIN to your Python path or create the venv first."
    exit 1
  fi
}

ensure_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name"
    exit 1
  fi
}

run_install() {
  ensure_python
  ensure_command pnpm

  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/backend/requirements.txt"
  "$PYTHON_BIN" -m playwright install chromium
  (
    cd "$ROOT_DIR/frontend"
    pnpm install
  )
}

run_scraper_cli() {
  ensure_python
  (
    cd "$ROOT_DIR/backend"
    "$PYTHON_BIN" scraper.py "$@"
  )
}

run_api() {
  ensure_python
  (
    cd "$ROOT_DIR/backend"
    exec "$PYTHON_BIN" -m uvicorn api:app --host 127.0.0.1 --port 8000
  )
}

run_frontend_dev() {
  ensure_command pnpm
  (
    cd "$ROOT_DIR/frontend"
    exec pnpm dev
  )
}

run_tests() {
  ensure_python
  (
    cd "$ROOT_DIR/backend"
    exec "$PYTHON_BIN" -m pytest -q
  )
}

run_stack() {
  ensure_python
  ensure_command pnpm

  trap cleanup EXIT INT TERM

  (
    cd "$ROOT_DIR/backend"
    "$PYTHON_BIN" -m uvicorn api:app --host 127.0.0.1 --port 8000
  ) &
  BACKEND_PID=$!

  (
    cd "$ROOT_DIR/frontend"
    pnpm dev
  ) &
  FRONTEND_PID=$!

  echo "Backend running at http://127.0.0.1:8000"
  echo "Frontend running at http://127.0.0.1:3000"

  wait "$BACKEND_PID" "$FRONTEND_PID"
}

COMMAND="${1:-stack}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$COMMAND" in
  install)
    run_install
    ;;
  run)
    run_scraper_cli "$@"
    ;;
  api)
    run_api
    ;;
  dev)
    run_frontend_dev
    ;;
  test)
    run_tests
    ;;
  stack)
    run_stack
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $COMMAND"
    usage
    exit 1
    ;;
esac
