#!/bin/sh
export SYNTHESIS_HOOK_CLIENT=muse
# Spike wrapper: run session_context.py from THIS source tree (not the installed
# release) so the spike validates without a release. Final bundle uses
# `synthesis exec-public` once the adapter ships. Emits --format text.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/skills/synthesis-agent-conformance/scripts/session_context.py" --format text
