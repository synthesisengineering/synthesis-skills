#!/usr/bin/env bash
# day-end-nudge.sh — state-aware evening nudge (notification ONLY).
#
# Shows one generic macOS banner during the evening-ritual window unless every
# workspace that is EXPECTED to close today has already closed.
#
# WORKSPACE-AWARE since 2026-09-02. The previous version asked only "did any
# day-end run today?" and went silent on the first one. A principal running
# several workspace seats closes them at different clock times — one at 18:00,
# another after 18:30 — so the first close silenced the nudge for every other
# seat, which is part of how one desk's closes went missing for days at a time.
#
# Confidentiality: the banner text is generic and fixed — zero identifying
# content ever appears on this surface (others see banners on screen-shares).
# It names no workspace, no count, and no state. This script never mutates
# anything: it runs one read-only query and shows one notification.
# Scheduled by the companion LaunchAgent plist (weekdays 16:55).
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_TOOL="$SELF_DIR/ritual_state.py"
TODAY="$(date +%Y-%m-%d)"

# Fail OPEN (nudge) rather than silent if the tool is missing or errors: a
# reminder that never fires is indistinguishable from a day with nothing owed.
if [ ! -f "$STATE_TOOL" ]; then
  /usr/bin/osascript -e 'display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
  exit 0
fi

if python3 - "$STATE_TOOL" "$TODAY" <<'PY'
import json, subprocess, sys
tool, today = sys.argv[1], sys.argv[2]
try:
    out = subprocess.run([sys.executable, tool, "query", "summary", "--json", "--today", today],
                         capture_output=True, text=True, timeout=20)
    data = json.loads(out.stdout)
    # Silent only when no workspace that runs rituals is still open for today.
    open_today = [o for o in data.get("open_workdays", [])
                  if o.get("date") == today and o.get("workspace") not in (None, "unknown")]
    # A seat with a streak configured is one that owes a close.
    owing = [w for w, v in (data.get("workspaces") or {}).items()
             if v.get("streak") is not None
             and (v.get("last_day_end") or {}).get("date") != today]
    done = not open_today and not owing
except Exception:
    done = False          # any failure -> nudge
sys.exit(0 if done else 1)
PY
then
  exit 0  # every expected seat has closed today — stay silent
fi

/usr/bin/osascript -e 'display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
