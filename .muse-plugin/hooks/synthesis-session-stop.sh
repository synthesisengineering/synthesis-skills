#!/bin/sh
export SYNTHESIS_HOOK_CLIENT=muse
# Never write bytecode into the installed package: Muse verifies the cached
# bundle against its lock record, and fresh __pycache__ entries invalidate the
# install (capabilities blocked) on the first hook fire.
export PYTHONDONTWRITEBYTECODE=1
# The setup-owned launcher verifies the active release and bounds Stop errors.
# Compose checkpoint and autopilot so a terminal result cannot hide its sibling.
LAUNCHER="${SYNTHESIS_INSTALL_BIN_DIR:-$HOME/.local/bin}/synthesis"
if [ ! -x "$LAUNCHER" ]; then
    printf '%s\n' '{"continue":false,"stopReason":"Synthesis launcher is unavailable; protection remains unverified.","systemMessage":"UNRESOLVED: Synthesis launcher is unavailable; protection remains unverified."}'
    exit 0
fi
exec "$LAUNCHER" exec-public --hook-event Stop --timeout-seconds 13 synthesis-autopilot/scripts/autopilot_gate.py --combined-stop
