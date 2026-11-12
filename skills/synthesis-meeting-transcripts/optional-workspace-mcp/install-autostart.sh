#!/bin/bash
# Cross-platform auto-start installer for workspace-mcp.
# Supports macOS (launchd user LaunchAgent) and Linux (systemd user unit).
# Windows: prints manual instructions (PRs welcome).
#
# Run interactively — it prints the unit it's about to install and asks for confirmation.
#
# Env vars passed through to the service:
#   GOOGLE_CLIENT_SECRET_PATH — required
#   WORKSPACE_MCP_PORT        — default 8765
#   WORKSPACE_MCP_TOOL_TIER   — default complete
#   GOOGLE_MCP_CREDENTIALS_DIR — default ~/.google_workspace_mcp/credentials
#   SYNTHESIS_HOME            — written into the unit when it is set (see below); otherwise
#                               the unit names none and start.sh uses ~/.synthesis/v5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
START_SCRIPT="$SCRIPT_DIR/start.sh"

if [ ! -x "$START_SCRIPT" ]; then
  echo "ERROR: $START_SCRIPT not found or not executable. chmod +x the scripts in this directory first." >&2
  exit 1
fi

# GOOGLE_CLIENT_SECRET_PATH must be set, or the service will fail at boot.
if [ -z "${GOOGLE_CLIENT_SECRET_PATH:-}" ]; then
  echo "ERROR: GOOGLE_CLIENT_SECRET_PATH is not set in your shell."
  echo "       Set it to the absolute path of your Google Cloud OAuth client_secret.json and re-run."
  echo "       Example: export GOOGLE_CLIENT_SECRET_PATH=\"\$HOME/secrets/workspace-mcp/client_secret.json\""
  exit 1
fi

PORT="${WORKSPACE_MCP_PORT:-8765}"
TIER="${WORKSPACE_MCP_TOOL_TIER:-complete}"
CREDS_DIR="${GOOGLE_MCP_CREDENTIALS_DIR:-$HOME/.google_workspace_mcp/credentials}"

# The synthesis home this is installed with goes into the unit. start.sh derives
# the outbox it starts the server to read from SYNTHESIS_HOME, and launchd and
# systemd give a server only what the unit carries. Without it, a server installed
# from a session with another synthesis home was started to read the default
# outbox, while its sessions staged attachments in theirs, and no restart changed
# that. Unset, the unit names none and start.sh keeps its default.
SYN_HOME="${SYNTHESIS_HOME:-}"

# A value written as the text of a plist string, and inside the double quotes of a
# systemd Environment= line: an ampersand or an angle bracket ends a plist, and
# systemd reads a backslash, a quote and a percent sign as its own. Every value
# the person chose goes through one of them (a client secret under a folder
# named with an ampersand gave a plist that did not parse). A value with none of
# those characters is written exactly as before. ExecStart= is a command line,
# which has rules of its own, and is written as it was.
as_xml()  { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
as_unit() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/%/%%/g'; }

install_macos() {
  local label="com.synthesis.workspace-mcp"
  local plist="$HOME/Library/LaunchAgents/$label.plist"
  local log_dir="$HOME/Library/Logs/workspace-mcp"
  local synthesis_home=""
  if [ -n "$SYN_HOME" ]; then
    synthesis_home="
    <key>SYNTHESIS_HOME</key>
    <string>$(as_xml "$SYN_HOME")</string>"
  fi

  mkdir -p "$log_dir"

  cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(as_xml "$START_SCRIPT")</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>GOOGLE_CLIENT_SECRET_PATH</key>
    <string>$(as_xml "$GOOGLE_CLIENT_SECRET_PATH")</string>
    <key>WORKSPACE_MCP_PORT</key>
    <string>$(as_xml "$PORT")</string>
    <key>WORKSPACE_MCP_TOOL_TIER</key>
    <string>$(as_xml "$TIER")</string>
    <key>GOOGLE_MCP_CREDENTIALS_DIR</key>
    <string>$(as_xml "$CREDS_DIR")</string>
    <key>WORKSPACE_MCP_FOREGROUND</key>
    <string>1</string>$synthesis_home
    <key>PATH</key>
    <string>$(as_xml "$HOME")/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$(as_xml "$log_dir")/launchd-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$(as_xml "$log_dir")/launchd-stderr.log</string>
</dict>
</plist>
PLIST

  echo "Will install macOS LaunchAgent:"
  echo "  $plist"
  echo
  cat "$plist"
  echo
  read -r -p "Proceed? [y/N] " answer
  if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    rm -f "$plist"
    echo "Cancelled."
    exit 0
  fi

  # Modern launchctl (macOS 10.11+). Fallback to `load` for older.
  if launchctl bootstrap "gui/$UID" "$plist" 2>/dev/null; then
    echo "Loaded via launchctl bootstrap."
  else
    launchctl load "$plist"
    echo "Loaded via launchctl load (legacy fallback)."
  fi

  echo "workspace-mcp will now start on login."
  echo "Logs: $log_dir/"
  echo "To uninstall: $SCRIPT_DIR/uninstall-autostart.sh"
}

install_linux() {
  local unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  local unit="$unit_dir/workspace-mcp.service"
  local synthesis_home=""
  if [ -n "$SYN_HOME" ]; then
    synthesis_home="
Environment=\"SYNTHESIS_HOME=$(as_unit "$SYN_HOME")\""
  fi

  mkdir -p "$unit_dir"

  cat > "$unit" <<UNIT
[Unit]
Description=Self-hosted Google Workspace MCP server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$START_SCRIPT
Environment="GOOGLE_CLIENT_SECRET_PATH=$(as_unit "$GOOGLE_CLIENT_SECRET_PATH")"
Environment="WORKSPACE_MCP_PORT=$(as_unit "$PORT")"
Environment="WORKSPACE_MCP_TOOL_TIER=$(as_unit "$TIER")"
Environment="GOOGLE_MCP_CREDENTIALS_DIR=$(as_unit "$CREDS_DIR")"
Environment="WORKSPACE_MCP_FOREGROUND=1"$synthesis_home
Environment="PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin"
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
UNIT

  echo "Will install systemd user unit:"
  echo "  $unit"
  echo
  cat "$unit"
  echo
  read -r -p "Proceed? [y/N] " answer
  if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    rm -f "$unit"
    echo "Cancelled."
    exit 0
  fi

  systemctl --user daemon-reload
  systemctl --user enable --now workspace-mcp.service

  echo "workspace-mcp enabled and running."
  echo "Status: systemctl --user status workspace-mcp.service"
  echo "Logs:   journalctl --user -u workspace-mcp.service -f"
  echo "To uninstall: $SCRIPT_DIR/uninstall-autostart.sh"
}

install_windows() {
  cat <<'EOF'
Windows auto-start is not automated by this script (PRs welcome).

Manual setup using Task Scheduler:
  1. Open Task Scheduler → Create Task
  2. Trigger: At log on
  3. Action: Start a program
     Program/script: bash.exe (from WSL or Git Bash)
     Arguments: -c "/path/to/start.sh"
  4. Or use the Startup folder: place a shortcut to start.sh there

Alternative using PowerShell and a scheduled task:
  schtasks /Create /SC ONLOGON /TN "WorkspaceMCP" /TR "bash /path/to/start.sh"

Set GOOGLE_CLIENT_SECRET_PATH and other env vars in System Properties → Environment Variables before registering the task.
EOF
}

OS="$(uname -s)"
case "$OS" in
  Darwin) install_macos ;;
  Linux)  install_linux ;;
  MINGW*|MSYS*|CYGWIN*) install_windows ;;
  *)
    echo "Unsupported OS: $OS"
    echo "Manual setup required. See start.sh and wire it into your platform's login-startup mechanism."
    exit 1
    ;;
esac
