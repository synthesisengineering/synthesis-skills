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
DRY_RUN=no
for arg in "$@"; do [ "$arg" = "--dry-run" ] && DRY_RUN=yes; done
# Prerequisites before anything is fetched, so a missing one is named and fixed rather than met as an error
# partway through (2026-10-30). On a Mac, git and python3 come with Apple's Command Line Tools: open Apple's
# installer, as Homebrew's does, and carry on when it finishes.
if [ "$(uname -s)" = Darwin ] && ! xcode-select -p >/dev/null 2>&1; then
  echo "synthesis: this Mac needs Apple's Command Line Tools, which provide git and python3."
  if [ "$DRY_RUN" = yes ]; then
    echo "synthesis: a dry run installs nothing; run without --dry-run to install them." >&2
    exit 1
  fi
  echo "synthesis: click Install in the window that opens; setup carries on by itself when they finish (Ctrl-C stops)."
  xcode-select --install >/dev/null 2>&1 || true
  waited=0
  until xcode-select -p >/dev/null 2>&1; do
    if [ "$waited" -ge 3600 ]; then
      echo "synthesis: the Command Line Tools are still missing; run this command again once they are installed." >&2
      exit 1
    fi
    sleep 5
    waited=$((waited + 5))
  done
fi
for tool in git python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "synthesis: $tool is missing; install it, then run this command again." >&2; exit 1; }
done
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || {
  echo "synthesis: this python3 is $(python3 -V 2>&1); synthesis needs 3.9 or newer." >&2
  exit 1
}
if [ "$DRY_RUN" = yes ]; then
  TMP=$(mktemp -d "${TMPDIR:-/tmp}/synthesis-dry-run.XXXXXX")
  trap 'rm -rf "$TMP"' EXIT
  git clone --quiet --depth 1 --branch "$REF" "$REPO" "$TMP/source"
  status=0
  python3 "$TMP/source/skills/synthesis-onboarding/scripts/setup.py" "$@" || status=$?
  exit "$status"
fi
echo "synthesis: getting the $REF source into $SRC ..."  # a first clone is about 15 MB, with nothing else printed
if [ -d "$SRC/.git" ]; then
  git -C "$SRC" fetch --quiet origin "$REF"
  git -C "$SRC" checkout --quiet --detach FETCH_HEAD
else
  mkdir -p "$(dirname "$SRC")"
  git clone --quiet --branch "$REF" "$REPO" "$SRC"
fi
exec python3 "$SRC/skills/synthesis-onboarding/scripts/setup.py" "$@"
