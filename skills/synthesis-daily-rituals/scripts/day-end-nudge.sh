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
# anything: it runs read-only queries and shows fixed notifications (the
# critical-deadline alert below is the sweep's own: a count and a pointer).
# Scheduled by the companion LaunchAgent plist (weekdays 16:55). Installed by
# the v5 install (synthesis/install.py) into <synthesis home>/bin/, beside the runtime it reads:
# <synthesis home>/current/synthesis/rituals.py --owed-today exits 0 only when
# no workspace still owes today's close.
#
# CRITICAL DEADLINES since 2026-11-06. Before the evening check it runs the deadline
# sweep's alert over every workspace's declared plan folders, so a day with no ritual
# still sounds for a deadline whose miss cannot be undone: one banner and one spoken
# line, a count and a pointer, posted by the sweep. If that check cannot run, a second
# fixed banner says so; silence there would read as "nothing is closing".
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_TOOL="$SELF_DIR/../current/synthesis/rituals.py"
SWEEP="$SELF_DIR/../current/skills/synthesis-daily-rituals/scripts/decay_sweep.py"

if ! python3 -S "$SWEEP" --alert-declared --as-of "$(date +%F)" >/dev/null 2>&1; then
  /usr/bin/osascript -e 'display notification "Critical-deadline check could not run — details in your synthesis console" with title "Synthesis"'
fi

# Fail OPEN (nudge) rather than silent if the tool is missing or errors: a
# reminder that never fires is indistinguishable from a day with nothing owed.
if [ -f "$STATE_TOOL" ] && python3 -S "$STATE_TOOL" --owed-today >/dev/null 2>&1; then
  exit 0  # every expected seat has closed today — stay silent
fi

/usr/bin/osascript -e 'display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
