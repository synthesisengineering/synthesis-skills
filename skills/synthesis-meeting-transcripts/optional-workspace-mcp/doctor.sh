#!/bin/bash
# Health check for the workspace-mcp auto-start service.
# Portable: macOS (launchd) and Linux (systemd user unit).
#
# Every other protective layer in the synthesis stack ships a health check;
# this one did not, which made it the fail-open control in a fail-closed
# stack. An auto-start service that dies stays dead silently: the supervisor
# retries on a throttle, the log fills with identical failures, and nothing
# surfaces until a task finally needs the server and finds it missing.
#
# The specific failure this exists to catch: the installed unit records an
# ABSOLUTE path to start.sh, captured at install time. Move the checkout,
# rename a directory, or restructure the repo, and the unit still points at
# the old path. The supervisor reports a configuration error, retries
# forever, and the only visible symptom is that the MCP tools are absent.
# install-autostart.sh derives the path correctly from its own location, so
# the fix is always "re-run the installer" — never "hand-edit the unit."
#
# Exit codes follow the synthesis guard contract:
#   0 — healthy
#   1 — defects found
#   2 — could not establish ground truth (a check that cannot run must never
#       look like a check that passed)
#
# Usage:
#   ./doctor.sh          # human-readable report
#   ./doctor.sh --quiet  # exit code plus a single summary line

set -uo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${WORKSPACE_MCP_PORT:-8765}"

DEFECTS=0
UNKNOWNS=0
FINDINGS=()

say() { [ "$QUIET" -eq 1 ] || echo "$@"; }
ok()      { say "  ok    $1"; }
fail()    { DEFECTS=$((DEFECTS+1)); FINDINGS+=("FAIL  $1"); say "  FAIL  $1"; [ -n "${2:-}" ] && say "        -> $2"; }
unknown() { UNKNOWNS=$((UNKNOWNS+1)); FINDINGS+=("UNKNOWN $1"); say "  ????  $1"; [ -n "${2:-}" ] && say "        -> $2"; }

say "workspace-mcp doctor"
say ""

OS="$(uname -s)"
case "$OS" in
  Darwin) UNIT="$HOME/Library/LaunchAgents/com.rajivpant.workspace-mcp.plist" ;;
  Linux)  UNIT="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/workspace-mcp.service" ;;
  *)      unknown "unsupported OS '$OS'" "auto-start checks only cover macOS and Linux"; UNIT="" ;;
esac

# ---------------------------------------------------------------- unit file
UNIT_PATH_TARGET=""
if [ -n "$UNIT" ]; then
  if [ ! -f "$UNIT" ]; then
    fail "auto-start unit not installed ($UNIT)" "run ./install-autostart.sh"
  else
    ok "auto-start unit installed"

    if [ "$OS" = "Darwin" ]; then
      UNIT_PATH_TARGET="$(plutil -extract ProgramArguments.0 raw "$UNIT" 2>/dev/null || true)"
    else
      UNIT_PATH_TARGET="$(sed -n 's/^ExecStart=//p' "$UNIT" | head -1)"
    fi

    if [ -z "$UNIT_PATH_TARGET" ]; then
      unknown "could not read the start-script path out of the unit" "inspect $UNIT by hand"
    elif [ ! -f "$UNIT_PATH_TARGET" ]; then
      # The headline check. A missing target is why the service silently dies.
      fail "unit points at a start script that does not exist:" \
           "re-run ./install-autostart.sh to regenerate the unit with the current path"
      say "        missing: $UNIT_PATH_TARGET"
      say "        current: $SCRIPT_DIR/start.sh"
    elif [ ! -x "$UNIT_PATH_TARGET" ]; then
      fail "unit's start script is not executable: $UNIT_PATH_TARGET" "chmod +x '$UNIT_PATH_TARGET'"
    elif [ "$UNIT_PATH_TARGET" != "$SCRIPT_DIR/start.sh" ]; then
      # Exists and runs, but is a different checkout than this one. Not a
      # defect (a second checkout is legitimate), but worth surfacing —
      # editing this copy would have no effect on what actually runs.
      say "  note  unit runs a different checkout than this one:"
      say "        unit: $UNIT_PATH_TARGET"
      say "        here: $SCRIPT_DIR/start.sh"
    else
      ok "unit points at this checkout's start.sh"
    fi
  fi
fi

# ------------------------------------------------------------ supervisor state
SUPERVISOR_UNKNOWN=0
if [ "$OS" = "Darwin" ] && [ -f "$UNIT" ]; then
  LAUNCH_OUTPUT="$(launchctl print "gui/$UID/com.rajivpant.workspace-mcp" 2>&1)"
  LAUNCH_EXIT=$?
  if [ "$LAUNCH_EXIT" -eq 0 ]; then
    LAST_EXIT="$(printf '%s\n' "$LAUNCH_OUTPUT" | sed -n 's/^[[:space:]]*last exit code = //p' | head -1)"
    STATE="$(printf '%s\n' "$LAUNCH_OUTPUT" | sed -n 's/^[[:space:]]*state = //p' | head -1)"
    if [ -z "$LAST_EXIT" ] || [ "$LAST_EXIT" = "0" ] || [ "$STATE" = "running" ]; then
      ok "LaunchAgent loaded (state: ${STATE:-unknown}; last exit: ${LAST_EXIT:-not reported})"
    else
      HINT="check $HOME/Library/Logs/workspace-mcp/launchd-stderr.log"
      [ "$LAST_EXIT" = "78" ] && HINT="EX_CONFIG — usually a stale unit path; re-run ./install-autostart.sh"
      fail "LaunchAgent last exit status $LAST_EXIT" "$HINT"
    fi
  elif printf '%s' "$LAUNCH_OUTPUT" | grep -Eqi \
    'operation not permitted|permission denied|not privileged|could not connect|input/output error'; then
    SUPERVISOR_UNKNOWN=1
    unknown "launchd state is not visible in this execution environment" \
            "run the doctor in an unrestricted local shell"
  elif printf '%s' "$LAUNCH_OUTPUT" | grep -Eqi \
    'could not find service|service.*not found|no such process'; then
    fail "LaunchAgent is not loaded" "launchctl bootstrap gui/\$UID '$UNIT'"
  else
    SUPERVISOR_UNKNOWN=1
    unknown "launchd state could not be established (exit $LAUNCH_EXIT)" \
            "$(printf '%s' "$LAUNCH_OUTPUT" | head -1)"
  fi
elif [ "$OS" = "Linux" ] && [ -f "$UNIT" ]; then
  if systemctl --user is-active --quiet workspace-mcp.service 2>/dev/null; then
    ok "systemd unit active"
  else
    fail "systemd unit not active" "systemctl --user status workspace-mcp.service"
  fi
fi

# -------------------------------------------------------------- credentials
SECRET="${GOOGLE_CLIENT_SECRET_PATH:-}"
if [ -z "$SECRET" ] && [ -n "$UNIT" ] && [ -f "$UNIT" ] && [ "$OS" = "Darwin" ]; then
  SECRET="$(plutil -extract EnvironmentVariables.GOOGLE_CLIENT_SECRET_PATH raw "$UNIT" 2>/dev/null || true)"
fi
if [ -z "$SECRET" ]; then
  unknown "GOOGLE_CLIENT_SECRET_PATH not set and not readable from the unit" \
          "export it, or re-run ./install-autostart.sh"
elif [ ! -f "$SECRET" ]; then
  fail "client secret file missing: $SECRET" "restore it, then re-run ./install-autostart.sh"
else
  ok "client secret present"
fi

# ------------------------------------------------------------------ liveness
LISTENING=0
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 && LISTENING=1
elif command -v ss >/dev/null 2>&1; then
  ss -ltn 2>/dev/null | grep -q ":$PORT " && LISTENING=1
else
  unknown "no lsof or ss available to check port $PORT" "install lsof or iproute2"
  LISTENING=-1
fi

if [ "$LISTENING" = "1" ]; then
  ok "listening on port $PORT"
elif [ "$LISTENING" = "0" ]; then
  if [ "$SUPERVISOR_UNKNOWN" = "1" ]; then
    unknown "port $PORT visibility is inconclusive in this execution environment" \
            "run the doctor in an unrestricted local shell"
  else
    fail "nothing listening on port $PORT" "./start.sh, or fix the unit above"
  fi
fi

if command -v curl >/dev/null 2>&1 && [ "$LISTENING" = "1" ]; then
  # An MCP streamable-http endpoint rejects a plain GET. Any HTTP status
  # means the server answered. Preserve curl's exit code independently: the
  # old `curl ... || echo 000` form could turn one failure into `000000` and
  # accidentally classify it as a nonzero HTTP response.
  CURL_OUTPUT="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 6 "http://localhost:$PORT/mcp" 2>&1)"
  CURL_EXIT=$?
  if [ "$CURL_EXIT" -ne 0 ]; then
    if printf '%s' "$CURL_OUTPUT" | grep -Eqi \
      'operation not permitted|permission denied|not allowed'; then
      unknown "endpoint reachability is blocked by this execution environment" \
              "run the doctor in an unrestricted local shell"
    else
      fail "port $PORT is open but the endpoint did not respond (curl exit $CURL_EXIT)" \
           "check the server log"
    fi
  elif ! printf '%s' "$CURL_OUTPUT" | grep -Eq '^[0-9]{3}$'; then
    unknown "curl returned a malformed HTTP status: $CURL_OUTPUT" \
            "verify the curl binary and run again"
  elif [ "$CURL_OUTPUT" = "000" ]; then
    fail "port $PORT is open but the endpoint did not respond" "check the server log"
  else
    ok "endpoint responding (HTTP $CURL_OUTPUT)"
  fi
fi

# -------------------------------------------------------------------- verdict
say ""
if [ "$UNKNOWNS" -gt 0 ] && [ "$DEFECTS" -eq 0 ]; then
  echo "UNVERIFIED: $UNKNOWNS check(s) could not run. Health is unknown, not confirmed."
  exit 2
elif [ "$DEFECTS" -gt 0 ]; then
  echo "DEFECTS: $DEFECTS defect(s), $UNKNOWNS unverifiable."
  exit 1
else
  echo "HEALTHY: workspace-mcp auto-start is installed, loaded, and serving on port $PORT."
  exit 0
fi
