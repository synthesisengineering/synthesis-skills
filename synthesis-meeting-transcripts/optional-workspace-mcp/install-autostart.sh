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

install_macos() {
  local label="com.rajivpant.workspace-mcp"
  local plist="$HOME/Library/LaunchAgents/$label.plist"
  local log_dir="$HOME/Library/Logs/workspace-mcp"

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
    <string>$START_SCRIPT</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>GOOGLE_CLIENT_SECRET_PATH</key>
    <string>$GOOGLE_CLIENT_SECRET_PATH</string>
    <key>WORKSPACE_MCP_PORT</key>
    <string>$PORT</string>
    <key>WORKSPACE_MCP_TOOL_TIER</key>
    <string>$TIER</string>
    <key>GOOGLE_MCP_CREDENTIALS_DIR</key>
    <string>$CREDS_DIR</string>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
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
  <string>$log_dir/launchd-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$log_dir/launchd-stderr.log</string>
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

  mkdir -p "$unit_dir"

  cat > "$unit" <<UNIT
[Unit]
Description=Self-hosted Google Workspace MCP server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$START_SCRIPT
Environment="GOOGLE_CLIENT_SECRET_PATH=$GOOGLE_CLIENT_SECRET_PATH"
Environment="WORKSPACE_MCP_PORT=$PORT"
Environment="WORKSPACE_MCP_TOOL_TIER=$TIER"
Environment="GOOGLE_MCP_CREDENTIALS_DIR=$CREDS_DIR"
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
