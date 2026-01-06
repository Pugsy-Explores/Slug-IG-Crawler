#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
APP="igscraper.mycelery.celery_app.app"
WORKER_LOG="celery_worker.log"
VENV_DIR=".venv3.10"   # path to your venv

usage() {
    echo "Usage:"
    echo "  $0 [--logs=terminal|--logs=file]    # start everything + scraper"
    echo "  $0 --stop                           # stop Celery worker (and optionally Redis)"
    exit 1
}

# Defaults
LOG_MODE="file"
MODE="start"

# Parse args
for arg in "$@"; do
    case $arg in
        --logs=terminal)
            LOG_MODE="terminal"
            ;;
        --logs=file)
            LOG_MODE="file"
            ;;
        --stop)
            MODE="stop"
            ;;
        *)
            echo "Unknown option: $arg"
            usage
            ;;
    esac
done

# Ensure venv exists
if [[ ! -d "$VENV_DIR" ]]; then
    echo "!! Virtual environment not found at $VENV_DIR"
    echo "   Create it first with: python3 -m venv $VENV_DIR"
    exit 1
fi

# Activate venv
source "$VENV_DIR/bin/activate"

if [[ "$MODE" == "stop" ]]; then
    echo "==> Stopping Celery workers..."
    pkill -f "celery -A $APP worker" || echo "   No Celery workers found."

    # Optional: stop Redis if it’s a Docker container
    if docker ps --format '{{.Names}}' | grep -q "^redis$"; then
        echo "==> Stopping Redis Docker container..."
        docker stop redis >/dev/null
        docker rm redis >/dev/null
    else
        echo "==> Leaving Redis running (managed by brew or system)."
    fi

    echo "==> All stopped."
    exit 0
fi

# ---------- START MODE ----------

echo "==> Checking Redis..."
if command -v brew >/dev/null 2>&1; then
    if ! brew services list | grep -q "redis.*started"; then
        echo "   Redis not running. Starting with brew..."
        brew services start redis
    else
        echo "   Redis already running (brew)."
    fi
elif docker ps --format '{{.Names}}' | grep -q "^redis$"; then
    echo "   Redis already running (docker)."
else
    echo "   No Redis found. Starting with docker..."
    docker run -d --name redis -p 6379:6379 redis:7
fi

echo "==> Checking for existing Celery worker..."
if pgrep -f "celery -A $APP worker" >/dev/null; then
    echo "   Celery worker already running."
else
    echo "   Starting Celery worker..."
    if [[ "$LOG_MODE" == "terminal" ]]; then
        echo "   (logs will appear here and also be written to $WORKER_LOG)"
        # stream logs to both terminal + file
        celery -A "$APP" worker --loglevel=INFO 2>&1 | tee "$WORKER_LOG" &
    else
        echo "   (logs will go to $WORKER_LOG)"
        celery -A "$APP" worker --loglevel=INFO >>"$WORKER_LOG" 2>&1 &
    fi
    CELERY_PID=$!
    echo "   Celery worker PID: $CELERY_PID"
    sleep 2
fi


echo "==> Running Python scraper (inside venv)..."
python3.10 -m igscraper.cli --config config.toml

echo "==> Done. Scraper finished. Celery + Redis kept running."