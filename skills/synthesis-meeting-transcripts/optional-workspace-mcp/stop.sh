#!/bin/bash
# Stops the workspace-mcp server started by start.sh.
# Portable: macOS and Linux.

set -euo pipefail

case "$(uname -s)" in
  Darwin) STATE_DIR="$HOME/Library/Logs/workspace-mcp" ;;
  Linux)  STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/workspace-mcp" ;;
  *)      STATE_DIR="$HOME/.workspace-mcp" ;;
esac

PID_FILE="$STATE_DIR/server.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file at $PID_FILE — server may not be running."
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    echo "Graceful kill failed, forcing..."
    kill -9 "$PID"
  fi
  echo "Stopped workspace-mcp (PID $PID)"
else
  echo "Server not running (stale PID $PID)"
fi

rm -f "$PID_FILE"
