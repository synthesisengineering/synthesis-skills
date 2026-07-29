#!/usr/bin/env bash
# day-end-nudge.sh — state-aware evening nudge (notification ONLY).
#
# Shows one generic macOS banner during the evening-ritual window unless
# today's day-end has already run. Confidentiality: the banner text is
# generic and fixed — zero identifying content ever appears on this
# surface (others see banners on screen-shares). This script never
# mutates anything: it reads one JSON file and shows one notification.
# Scheduled by the companion LaunchAgent plist (weekdays 16:55).
set -euo pipefail
STATE="$HOME/.synthesis/day-end/state.json"
TODAY="$(date +%Y-%m-%d)"
if [ -f "$STATE" ] && python3 - "$STATE" "$TODAY" <<'PY'
import json, sys
try:
    state = json.load(open(sys.argv[1]))
    done = (state.get("last_day_end") or {}).get("date") == sys.argv[2]
except Exception:
    done = False
sys.exit(0 if done else 1)
PY
then
  exit 0  # day-end already ran today — stay silent
fi
/usr/bin/osascript -e 'display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
