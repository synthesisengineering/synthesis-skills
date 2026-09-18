#!/bin/sh
export SYNTHESIS_HOOK_CLIENT=muse
# Never write bytecode into the installed package: Muse verifies the cached
# bundle against its lock record, and fresh __pycache__ entries invalidate the
# install (capabilities blocked) on the first hook fire.
export PYTHONDONTWRITEBYTECODE=1
# Spike wrapper: run session_context.py from THIS source tree (not the installed
# release) so the spike validates without a release. Final bundle uses
# `synthesis exec-public` once the adapter ships. Emits --format text.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/skills/synthesis-agent-conformance/scripts/session_context.py" --format text
