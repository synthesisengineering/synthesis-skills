#!/bin/sh
# Muse adapter: the stable synthesis hook entry (see session-start.sh).
# Muse native hooks take no matcher, so this runs for every tool; the hook
# itself guards only shell and send tools and returns at once for the rest.
# Muse lets a call through when this exits with an error and blocks on exit 2 with a reason (5.21.0), so a stable
# hook that is missing or crashes is held here; its deny exits 0 with its own reason, and passes through unchanged.
"$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use || { echo "synthesis guard could not run, so the call is held: run synthesis doctor" >&2; exit 2; }
