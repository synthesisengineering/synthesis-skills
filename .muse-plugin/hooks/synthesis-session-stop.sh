#!/bin/sh
export SYNTHESIS_HOOK_CLIENT=muse
# Spike wrapper: bind durable project state to the Stop event from THIS source
# tree (not the installed release). Final bundle uses `synthesis exec-public`.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/skills/synthesis-project-management/scripts/project_state.py" hook
