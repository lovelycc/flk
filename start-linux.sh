#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
PID_FILE="$PROJECT_DIR/instance/server.pid"
STDOUT_LOG="$PROJECT_DIR/instance/server.log"
STDERR_LOG="$PROJECT_DIR/instance/server-error.log"
HOST=${MFD_HOST:-127.0.0.1}
PORT=${MFD_PORT:-5000}

case "$PORT" in
  ''|*[!0-9]*) echo "MFD_PORT must be a number." >&2; exit 1 ;;
esac

if [ ! -x "$VENV_PYTHON" ]; then
  PYTHON_COMMAND=${PYTHON_COMMAND:-python3}
  if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
    echo "Python 3 was not found. Install python3 and python3-venv first." >&2
    exit 1
  fi
  "$PYTHON_COMMAND" -m venv "$PROJECT_DIR/.venv"
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt"
fi

mkdir -p "$PROJECT_DIR/instance"

if [ -f "$PID_FILE" ]; then
  EXISTING_PID=$(sed -n '1p' "$PID_FILE")
  case "$EXISTING_PID" in
    ''|*[!0-9]*) rm -f "$PID_FILE" ;;
    *)
      if kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo "The local server is already running (PID $EXISTING_PID): http://$HOST:$PORT"
        exit 0
      fi
      rm -f "$PID_FILE"
      ;;
  esac
fi

cd "$PROJECT_DIR"
nohup "$VENV_PYTHON" -m flask --app app run --host "$HOST" --port "$PORT" \
  >"$STDOUT_LOG" 2>"$STDERR_LOG" </dev/null &
SERVER_PID=$!
printf '%s\n' "$SERVER_PID" >"$PID_FILE"

CHECK_HOST=$HOST
if [ "$CHECK_HOST" = "0.0.0.0" ] || [ "$CHECK_HOST" = "::" ]; then
  CHECK_HOST=127.0.0.1
fi

ATTEMPT=0
while [ "$ATTEMPT" -lt 30 ]; do
  if "$VENV_PYTHON" -c "import urllib.request; urllib.request.urlopen('http://$CHECK_HOST:$PORT', timeout=1).read(1)" >/dev/null 2>&1; then
    echo "Deployment completed: http://$CHECK_HOST:$PORT"
    if [ "${MFD_OPEN_BROWSER:-0}" = "1" ] && command -v xdg-open >/dev/null 2>&1; then
      xdg-open "http://$CHECK_HOST:$PORT" >/dev/null 2>&1 || true
    fi
    exit 0
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "The server exited during startup. Check $STDERR_LOG" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
  ATTEMPT=$((ATTEMPT + 1))
  sleep 0.25
done

echo "The server did not become ready. Check $STDERR_LOG" >&2
exit 1
