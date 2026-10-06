#!/bin/sh
# Muse adapter: the stable synthesis hook entry (see session-start.sh).
# Muse native hooks take no matcher, so this runs for every tool; the hook
# itself guards only shell and send tools and returns at once for the rest.
exec "$HOME/.synthesis/v5/bin/synthesis-hook" pre-tool-use
