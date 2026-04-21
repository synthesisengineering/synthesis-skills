#!/bin/bash
# Starts the workspace-mcp server in the background.
# Portable: macOS and Linux.
#
# Env vars:
#   WORKSPACE_MCP_PORT       — default 8765
#   GOOGLE_CLIENT_SECRET_PATH — path to client_secret.json (required)
#   GOOGLE_MCP_CREDENTIALS_DIR — where per-user tokens are stored (default ~/.google_workspace_mcp/credentials)
#   WORKSPACE_MCP_TOOL_TIER  — core|extended|complete (default complete)
#
# Logs: $XDG_STATE_HOME/workspace-mcp/server.log (or ~/.local/state/workspace-mcp/server.log on Linux,
#        ~/Library/Logs/workspace-mcp/server.log on macOS)
# PID:  same dir, server.pid

set -euo pipefail

# Determine OS-idiomatic state directory
case "$(uname -s)" in
  Darwin) STATE_DIR="$HOME/Library/Logs/workspace-mcp" ;;
  Linux)  STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/workspace-mcp" ;;
  *)      STATE_DIR="$HOME/.workspace-mcp" ;;
esac

mkdir -p "$STATE_DIR"
PID_FILE="$STATE_DIR/server.pid"
LOG_FILE="$STATE_DIR/server.log"

# Required env
if [ -z "${GOOGLE_CLIENT_SECRET_PATH:-}" ]; then
  echo "ERROR: GOOGLE_CLIENT_SECRET_PATH not set. Point it at your Google Cloud OAuth client_secret.json." >&2
  exit 1
fi
if [ ! -f "$GOOGLE_CLIENT_SECRET_PATH" ]; then
  echo "ERROR: GOOGLE_CLIENT_SECRET_PATH '$GOOGLE_CLIENT_SECRET_PATH' does not exist." >&2
  exit 1
fi

export WORKSPACE_MCP_PORT="${WORKSPACE_MCP_PORT:-8765}"
export GOOGLE_MCP_CREDENTIALS_DIR="${GOOGLE_MCP_CREDENTIALS_DIR:-$HOME/.google_workspace_mcp/credentials}"
export OAUTHLIB_INSECURE_TRANSPORT=1  # permits http://localhost redirect

mkdir -p "$GOOGLE_MCP_CREDENTIALS_DIR"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "workspace-mcp already running (PID $(cat "$PID_FILE")). To restart: ./stop.sh && ./start.sh"
  exit 0
fi

TOOL_TIER="${WORKSPACE_MCP_TOOL_TIER:-complete}"

# Launch detached. uvx comes from `uv` (install via https://docs.astral.sh/uv/)
nohup uvx workspace-mcp --single-user --transport streamable-http --tool-tier "$TOOL_TIER" \
  >"$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
sleep 2

if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "workspace-mcp started (PID $(cat "$PID_FILE"))"
  echo "URL: http://localhost:$WORKSPACE_MCP_PORT/mcp"
  echo "Log: $LOG_FILE"
else
  echo "workspace-mcp failed to start. Last 20 log lines:" >&2
  tail -20 "$LOG_FILE" >&2
  exit 1
fi
