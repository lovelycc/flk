#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PID_FILE="$PROJECT_DIR/instance/server.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "The local server is not running."
  exit 0
fi

SERVER_PID=$(sed -n '1p' "$PID_FILE")
case "$SERVER_PID" in
  ''|*[!0-9]*) echo "Invalid PID file; removing it."; rm -f "$PID_FILE"; exit 1 ;;
esac

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "The server process has already ended."
  rm -f "$PID_FILE"
  exit 0
fi

if [ -e "/proc/$SERVER_PID/cwd" ]; then
  PROCESS_DIR=$(readlink "/proc/$SERVER_PID/cwd" 2>/dev/null || true)
  if [ "$PROCESS_DIR" != "$PROJECT_DIR" ]; then
    echo "Refusing to stop PID $SERVER_PID: its working directory is not this project." >&2
    exit 1
  fi
fi

kill "$SERVER_PID"
ATTEMPT=0
while kill -0 "$SERVER_PID" 2>/dev/null && [ "$ATTEMPT" -lt 20 ]; do
  ATTEMPT=$((ATTEMPT + 1))
  sleep 0.25
done

if kill -0 "$SERVER_PID" 2>/dev/null; then
  echo "The process did not stop in time; PID $SERVER_PID is still running." >&2
  exit 1
fi

rm -f "$PID_FILE"
echo "The local server has stopped."
