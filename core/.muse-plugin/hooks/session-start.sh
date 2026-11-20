#!/bin/sh
# Muse adapter for SessionStart. Muse plugin hooks must name a script file, so
# each event has one; all four call the stable entry Claude Code and Codex use
# (R7.5), and their text never changes between releases.
# Muse runs plugin hooks with HOME and PATH kept and MUSE_PLUGIN_ROOT set; $0 is
# the installed copy of this file, so the plugin root is also two levels up.
# -B: never write bytecode into Muse's verified bundle.
h="$HOME/.synthesis/v5/bin/synthesis-hook"
r="${MUSE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
[ -x "$h" ] || python3 -B -S "$r/synthesis/install.py" "$r" >/dev/null
exec "$h" session-start "$r"
