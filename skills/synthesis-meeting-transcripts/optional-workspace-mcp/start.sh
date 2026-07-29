#!/bin/bash
# Starts the workspace-mcp server in the background.
# Portable: macOS and Linux.
#
# Env vars:
#   WORKSPACE_MCP_PORT       — default 8765
#   GOOGLE_CLIENT_SECRET_PATH — path to client_secret.json (required)
#   GOOGLE_MCP_CREDENTIALS_DIR — where per-user tokens are stored (default ~/.google_workspace_mcp/credentials)
#   WORKSPACE_MCP_TOOL_TIER  — core|extended|complete (default complete)
#   WORKSPACE_MCP_FOREGROUND — set to 1 when invoked by a process supervisor
#                              (launchd, systemd). Causes the script to `exec`
#                              uvx so the supervisor manages the actual server
#                              process. Default 0 (backgrounded via nohup).
#
# Logs: $XDG_STATE_HOME/workspace-mcp/server.log (or ~/.local/state/workspace-mcp/server.log on Linux,
#        ~/Library/Logs/workspace-mcp/server.log on macOS)
# PID:  same dir, server.pid

set -euo pipefail

# Ensure uv tooling is on PATH. macOS launchd and Linux systemd start
# processes with a sparse PATH that does not include ~/.local/bin, where
# `uv` installs `uvx` by default. Without this export, the `nohup uvx ...`
# call below fails with "nohup: uvx: No such file or directory" even when
# the launch agent / unit file sets PATH in its environment block, because
# that PATH does not always propagate cleanly to script subshells.
export PATH="$HOME/.local/bin:$PATH"

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

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE")"
  if kill -0 "$OLD_PID" 2>/dev/null && ps -p "$OLD_PID" -o command= 2>/dev/null | grep -q "workspace-mcp"; then
    echo "workspace-mcp already running (PID $OLD_PID). To restart: ./stop.sh && ./start.sh"
    exit 0
  fi
  # Stale PID file: the process exited, or (after a reboot) the OS recycled the
  # PID for an unrelated process. kill -0 alone cannot tell these apart — it
  # only proves *some* process has that PID — so verify the command line before
  # trusting it. Otherwise this script no-ops with exit 0 forever and a
  # KeepAlive={SuccessfulExit=false} supervisor never restarts the server.
  rm -f "$PID_FILE"
fi

TOOL_TIER="${WORKSPACE_MCP_TOOL_TIER:-complete}"

# Resolve uvx explicitly. With a sparse PATH, `nohup uvx` backgrounds a child
# that dies immediately when uvx is not found, and the failure surfaces as
# the unhelpful "nohup: uvx: No such file or directory" in the log. Failing
# fast here produces a clearer error and lets KeepAlive loops surface the
# real problem instead of thrashing.
UVX_BIN="$(command -v uvx || true)"
if [ -z "$UVX_BIN" ]; then
  echo "ERROR: uvx not found on PATH ($PATH)." >&2
  echo "Install uv (https://docs.astral.sh/uv/) so that uvx lands in \$HOME/.local/bin, then retry." >&2
  exit 1
fi

if [ "${WORKSPACE_MCP_FOREGROUND:-0}" = "1" ]; then
  # Supervisor-managed (launchd, systemd). Backgrounding would orphan the
  # server: the supervisor sees the wrapper script exit 0, reclaims the
  # process group, and kills the workspace-mcp child. Exec replaces this
  # shell with uvx so the supervisor tracks the actual server PID.
  echo $$ > "$PID_FILE"
  exec "$UVX_BIN" workspace-mcp --single-user --transport streamable-http --tool-tier "$TOOL_TIER" \
    >>"$LOG_FILE" 2>&1
fi

# Interactive / manual launch: background via nohup so the user can close the
# terminal without killing the server.
nohup "$UVX_BIN" workspace-mcp --single-user --transport streamable-http --tool-tier "$TOOL_TIER" \
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
