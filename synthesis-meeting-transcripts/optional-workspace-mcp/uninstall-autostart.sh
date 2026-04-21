#!/bin/bash
# Removes the workspace-mcp auto-start configuration installed by install-autostart.sh.

set -euo pipefail

uninstall_macos() {
  local label="com.rajivpant.workspace-mcp"
  local plist="$HOME/Library/LaunchAgents/$label.plist"

  if [ ! -f "$plist" ]; then
    echo "No LaunchAgent found at $plist. Nothing to do."
    return 0
  fi

  # Modern then legacy
  launchctl bootout "gui/$UID" "$plist" 2>/dev/null || launchctl unload "$plist" 2>/dev/null || true
  rm -f "$plist"
  echo "Removed $plist"
}

uninstall_linux() {
  local unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  local unit="$unit_dir/workspace-mcp.service"

  if [ ! -f "$unit" ]; then
    echo "No systemd unit found at $unit. Nothing to do."
    return 0
  fi

  systemctl --user disable --now workspace-mcp.service 2>/dev/null || true
  rm -f "$unit"
  systemctl --user daemon-reload
  echo "Removed $unit"
}

case "$(uname -s)" in
  Darwin) uninstall_macos ;;
  Linux)  uninstall_linux ;;
  *)      echo "Unsupported OS. Remove manually."; exit 1 ;;
esac
