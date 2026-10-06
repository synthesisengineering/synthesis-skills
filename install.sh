#!/bin/sh
# Kept for old links: the install is onboard.sh, which runs the onboarding setup.py.
exec "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/onboard.sh" "$@"
