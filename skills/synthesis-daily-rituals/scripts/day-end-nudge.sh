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
# Scheduled by the companion LaunchAgent plist (weekdays 16:55). Installed by
# the v5 install (synthesis/install.py) into <synthesis home>/bin/, beside the runtime it reads:
# <synthesis home>/current/synthesis/rituals.py --owed-today exits 0 only when
# no workspace still owes today's close.
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_TOOL="$SELF_DIR/../current/synthesis/rituals.py"

# Fail OPEN (nudge) rather than silent if the tool is missing or errors: a
# reminder that never fires is indistinguishable from a day with nothing owed.
if [ -f "$STATE_TOOL" ] && python3 -S "$STATE_TOOL" --owed-today >/dev/null 2>&1; then
  exit 0  # every expected seat has closed today — stay silent
fi

/usr/bin/osascript -e 'display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
