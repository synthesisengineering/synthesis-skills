#!/bin/sh
# Muse adapter for SessionStart. Muse plugin hooks must name a script file, so
# each event has one; all four call the stable entry Claude Code and Codex use
# (R7.5). The session start first runs this release's own installer, which
# leaves a newer runtime, or this release as it installs it, as it is.
# Muse runs plugin hooks with HOME and PATH kept and MUSE_PLUGIN_ROOT set; $0 is
# the installed copy of this file, so the plugin root is also two levels up.
# -B: never write bytecode into Muse's verified bundle.
h="$HOME/.synthesis/v5/bin/synthesis-hook"
r="${MUSE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
python3 -B -S "$r/synthesis/install.py" "$r" --forward-only >/dev/null
exec "$h" session-start "$r"
