#!/bin/sh
export SYNTHESIS_HOOK_CLIENT=muse
# Never write bytecode into the installed package: Muse verifies the cached
# bundle against its lock record, and fresh __pycache__ entries invalidate the
# install (capabilities blocked) on the first hook fire.
export PYTHONDONTWRITEBYTECODE=1
# Spike wrapper: deliver addressed board messages to this seat on every turn
# from THIS source tree (not the installed release). Final bundle uses
# `synthesis exec-public` once the adapter ships. Emits hook JSON.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/skills/synthesis-project-management/scripts/board_inbox.py" --hook "$@"
