#!/usr/bin/env bash
# Called by the GUI dashboard to start the backend inside WSL.
# Usage: bash tools/start_backend_wsl.sh /path/to/project
set -e

PROJECT_DIR="${1:-.}"
cd "$PROJECT_DIR"
mkdir -p logs

# Kill any previous backend
pkill -f 'uvicorn Start:app' 2>/dev/null || true
sleep 0.3

# Set permissive local-dev defaults
export STRICT_PRODUCTION_STARTUP="${STRICT_PRODUCTION_STARTUP:-0}"
export API_KEY="${API_KEY:-}"
export RATE_LIMIT_REQUESTS_PER_MINUTE="${RATE_LIMIT_REQUESTS_PER_MINUTE:-0}"
export REQUIRED_PRODUCTION_AGENTS="${REQUIRED_PRODUCTION_AGENTS:-}"

# Start uvicorn directly, bind 0.0.0.0 so Windows can reach it
nohup .venv/bin/python -m uvicorn Start:app \
    --host 0.0.0.0 \
    --port "${UVICORN_PORT:-8000}" \
    > logs/backend-wsl.log 2>&1 &

echo "$!" > .backend-wsl.pid
echo "STARTED_PID:$(cat .backend-wsl.pid)"
