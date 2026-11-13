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

# HOOK APPROVALS since 2026-11-13. A harness whose hooks wait for the person's approval runs
# none of them (one asks again after every release). The doctor writes down which hooks
# wait when it runs, and a hook that runs strikes itself from that note; this reads the note
# through the doctor (no check is run, no harness is asked and nothing is written, `-B`
# keeping Python from leaving compiled files beside the runtime) and shows a fixed banner:
# one harness whose guard has not been seen to run since it was found waiting, or more than
# one; or that nothing has looked since synthesis was last updated. A note older than a day,
# or none, says nothing, and so does a doctor that cannot answer.
DOCTOR="$SELF_DIR/../current/synthesis/doctor.py"
waiting="$(python3 -S -B "$DOCTOR" --waiting 2>/dev/null | head -1 || true)"
case "$waiting" in
  1) /usr/bin/osascript -e 'display notification "One agent app has guards not confirmed running — details in your synthesis console" with title "Synthesis"' ;;
  2) /usr/bin/osascript -e 'display notification "More than one agent app has guards not confirmed running — details in your synthesis console" with title "Synthesis"' ;;
  unchecked) /usr/bin/osascript -e 'display notification "Agent app guards not checked since synthesis last updated — details in your synthesis console" with title "Synthesis"' ;;
esac

# RECORDS LEFT UNSAVED since 5.19.0 (the audit of 2026-11-11, gap 4). A record a seat claimed
# and left uncommitted, or committed and never pushed, longer than the config's `unsaved_hours`
# (24 by default) has not left this Mac. The doctor counts the repositories holding one, reading
# the board and git and writing nothing; a fixed banner says one, or more than one, and names
# nothing. A doctor that cannot answer says nothing.
unsaved="$(python3 -S -B "$DOCTOR" --unsaved 2>/dev/null | head -1 || true)"
case "$unsaved" in
  1) /usr/bin/osascript -e 'display notification "One repository has claimed records left unsaved — details in your synthesis console" with title "Synthesis"' ;;
  [2-9]|[1-9][0-9]*) /usr/bin/osascript -e 'display notification "More than one repository has claimed records left unsaved — details in your synthesis console" with title "Synthesis"' ;;
esac

# Fail OPEN (nudge) rather than silent if the tool is missing or errors: a
# reminder that never fires is indistinguishable from a day with nothing owed.
if [ -f "$STATE_TOOL" ] && python3 -S -B "$STATE_TOOL" --owed-today >/dev/null 2>&1; then
  exit 0  # every expected seat has closed today — stay silent
fi

/usr/bin/osascript -e 'display notification "Evening ritual window — details in your synthesis console" with title "Synthesis"'
