#!/bin/sh
# One command for the synthesis work system on a Mac:
#
#   curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
#   curl -fsSL .../onboard.sh | sh -s -- workspace            # a workspace on a new Mac
#   curl -fsSL .../onboard.sh | sh -s -- --org-repo URL       # an organization member
#
# It keeps a source checkout at ~/.synthesis/v5/source (durable, never a temporary
# folder) on the stable branch (SYNTHESIS_REF overrides: main or vX.Y.Z), then runs
# skills/synthesis-onboarding/scripts/setup.py with the arguments given. setup.py asks
# its questions on the terminal even though stdin is this pipe. With --dry-run it leaves
# that checkout alone: setup.py runs from a clone in a temporary folder, removed after.
set -eu
GIT_ALLOW_PROTOCOL=https
GIT_PROTOCOL_FROM_USER=0
export GIT_ALLOW_PROTOCOL GIT_PROTOCOL_FROM_USER
REF="${SYNTHESIS_REF:-stable}"
SRC="${SYNTHESIS_SOURCE:-$HOME/.synthesis/v5/source}"
REPO="https://github.com/synthesisengineering/synthesis-skills.git"
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    TMP=$(mktemp -d "${TMPDIR:-/tmp}/synthesis-dry-run.XXXXXX")
    trap 'rm -rf "$TMP"' EXIT
    git clone --quiet --depth 1 --branch "$REF" "$REPO" "$TMP/source"
    status=0
    python3 "$TMP/source/skills/synthesis-onboarding/scripts/setup.py" "$@" || status=$?
    exit "$status"
  fi
done
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch --quiet origin "$REF"
  git -C "$SRC" checkout --quiet --detach FETCH_HEAD
else
  mkdir -p "$(dirname "$SRC")"
  git clone --quiet --branch "$REF" "$REPO" "$SRC"
fi
exec python3 "$SRC/skills/synthesis-onboarding/scripts/setup.py" "$@"
