#!/bin/sh
# synthesis-onboarding bootstrap — one command from a bare Mac to a working
# synthesis ecosystem. Safe to re-run anytime; it updates and repairs.
#
#   curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/onboard.sh | sh
#   curl -fsSL .../onboard.sh | sh -s -- install --with-personal-workspace alice
#
# Running from a checkout uses that checkout as the source; otherwise the
# public repo is cloned (or refreshed) under the user's cache directory.
# Stale caches fail loudly: pass SYNTHESIS_ONBOARD_ALLOW_STALE=1 to accept.
set -eu

PUBLIC_REPO="https://github.com/synthesisengineering/synthesis-skills.git"
ENGINE_REL="skills/synthesis-onboarding/scripts/onboard.py"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required and not found."
  echo "On macOS, run:  xcode-select --install"
  echo "Accept the dialog, wait for it to finish, then re-run this command."
  exit 2
fi

# Prefer a local checkout when this script runs from one.
SCRIPT_DIR=""
case "${0:-}" in
  */*) SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" 2>/dev/null && pwd) || SCRIPT_DIR="" ;;
esac
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/$ENGINE_REL" ]; then
  SRC="$SCRIPT_DIR"
else
  SRC="${SYNTHESIS_ONBOARD_SOURCE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/synthesis-skills}"
  # -e, not -d: .git is a file in git worktrees
  if [ -e "$SRC/.git" ]; then
    if ! git -C "$SRC" pull --ff-only; then
      if [ "${SYNTHESIS_ONBOARD_ALLOW_STALE:-}" = "1" ]; then
        echo "warning: continuing with the cached copy at $SRC (allow-stale)"
      else
        echo "Could not refresh $SRC — refusing to install from stale sources."
        echo "Fix network access and re-run, or set SYNTHESIS_ONBOARD_ALLOW_STALE=1."
        exit 1
      fi
    fi
  else
    mkdir -p "$(dirname "$SRC")"
    git clone "$PUBLIC_REPO" "$SRC"
  fi
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required and not found."
  echo "On macOS, run:  xcode-select --install   (it provides python3 and git)"
  exit 2
fi

if [ "$#" -eq 0 ]; then
  set -- install
fi
exec python3 "$SRC/$ENGINE_REL" "$@"
