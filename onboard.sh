#!/bin/sh
# One audited bootstrap for the synthesis work system.
#
#   curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
#   curl -fsSL .../onboard.sh | sh -s -- setup --profile skills-only
#   curl -fsSL .../onboard.sh | sh -s -- setup --channel edge
#   curl -fsSL .../onboard.sh | sh -s -- setup --pin X.Y.Z
#
# Acquisition is mutable; execution is not. This script refreshes a bare Git
# mirror, resolves one ref, checks out that exact object into a temporary tree,
# and lets the release-owned bootstrap verify tag, commit, Git tree, manifests,
# canonical SHA-256 tree digest, and object types before activation.
set -eu

# A syntactically HTTPS source must remain HTTPS after Git applies ambient
# configuration.  This allowlist blocks url.*.insteadOf and external transport
# helpers from turning the public acquisition boundary into local execution.
GIT_ALLOW_PROTOCOL=https
GIT_PROTOCOL_FROM_USER=0
export GIT_ALLOW_PROTOCOL GIT_PROTOCOL_FROM_USER

PUBLIC_REPO="https://github.com/synthesisengineering/synthesis-skills.git"
BOOTSTRAP_REL="skills/synthesis-onboarding/scripts/bootstrap.py"
CHANNEL="${SYNTHESIS_ONBOARD_CHANNEL:-stable}"
VERSION_PIN="${SYNTHESIS_ONBOARD_VERSION_PIN:-}"
PREVIOUS=""

for ARG in "$@"; do
  if [ "$PREVIOUS" = "channel" ]; then
    CHANNEL="$ARG"
    PREVIOUS=""
    continue
  fi
  if [ "$PREVIOUS" = "pin" ]; then
    VERSION_PIN="$ARG"
    PREVIOUS=""
    continue
  fi
  case "$ARG" in
    --channel) PREVIOUS="channel" ;;
    --channel=*) CHANNEL=${ARG#--channel=} ;;
    --pin) PREVIOUS="pin" ;;
    --pin=*) VERSION_PIN=${ARG#--pin=} ;;
  esac
done
if [ -n "$PREVIOUS" ]; then
  echo "--$PREVIOUS requires a value." >&2
  exit 2
fi

case "$CHANNEL" in
  stable) SOURCE_REF="stable" ;;
  edge) SOURCE_REF="main" ;;
  *)
    echo "Release channel must be stable or edge (got: $CHANNEL)." >&2
    exit 2 ;;
esac
DESCRIPTOR_CHANNEL="$CHANNEL"
if [ -n "$VERSION_PIN" ]; then
  case "$VERSION_PIN" in
    *[!0-9.]*|.*|*..*|*.)
      echo "Release pin must be an exact X.Y.Z version." >&2
      exit 2 ;;
  esac
  if ! (
    IFS=.
    set -- $VERSION_PIN
    [ "$#" -eq 3 ] && [ -n "$1" ] && [ -n "$2" ] && [ -n "$3" ] &&
      [ "$1" -eq "$1" ] 2>/dev/null && [ "$2" -eq "$2" ] 2>/dev/null &&
      [ "$3" -eq "$3" ] 2>/dev/null
  ); then
    echo "Release pin must be an exact X.Y.Z version." >&2
    exit 2
  fi
  SOURCE_REF="v$VERSION_PIN"
  DESCRIPTOR_CHANNEL="pin"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required and not found." >&2
  echo "On macOS, install the command-line developer tools, then run this command again." >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required and not found." >&2
  echo "Install Python 3 with your operating system package manager, then run this command again." >&2
  exit 2
fi

SYNTHESIS_HOME_DIR="${SYNTHESIS_HOME:-$HOME}"
CACHE_ROOT="${SYNTHESIS_ONBOARD_CACHE_DIR:-${XDG_CACHE_HOME:-$SYNTHESIS_HOME_DIR/.cache}/synthesis}"
STATE_ROOT="${XDG_STATE_HOME:-$SYNTHESIS_HOME_DIR/.local/state}/synthesis"
BIN_ROOT="${SYNTHESIS_INSTALL_BIN_DIR:-$SYNTHESIS_HOME_DIR/.local/bin}"
RELEASES_DIR="$CACHE_ROOT/releases"
ACTIVE_DESCRIPTOR="$STATE_ROOT/active-release.json"
LAUNCHER="$BIN_ROOT/synthesis"
CHECKOUT=""
MIRROR=""

cleanup() {
  if [ -n "$MIRROR" ] && [ -n "$CHECKOUT" ] && [ -e "$CHECKOUT/.git" ]; then
    git --git-dir="$MIRROR" worktree remove --force "$CHECKOUT" >/dev/null 2>&1 || true
  fi
  if [ -n "${CHECKOUT_PARENT:-}" ] && [ -d "$CHECKOUT_PARENT" ]; then
    rmdir "$CHECKOUT_PARENT" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if [ -n "${SYNTHESIS_ONBOARD_SOURCE_DIR:-}" ]; then
  CHECKOUT=$(CDPATH= cd -- "$SYNTHESIS_ONBOARD_SOURCE_DIR" && pwd)
  if [ ! -f "$CHECKOUT/$BOOTSTRAP_REL" ]; then
    echo "SYNTHESIS_ONBOARD_SOURCE_DIR is not a synthesis-skills checkout." >&2
    exit 2
  fi
else
  MIRROR="$CACHE_ROOT/acquisition/synthesis-skills.git"
  mkdir -p "$(dirname "$MIRROR")" "$RELEASES_DIR" "$STATE_ROOT" "$BIN_ROOT"
  if [ -e "$MIRROR" ]; then
    if [ ! -d "$MIRROR" ] || ! git --git-dir="$MIRROR" rev-parse --is-bare-repository >/dev/null 2>&1; then
      echo "Acquisition path exists but is not a bare Git repository: $MIRROR" >&2
      exit 1
    fi
    CURRENT_ORIGIN=$(git --git-dir="$MIRROR" remote get-url origin 2>/dev/null || true)
    if [ "$CURRENT_ORIGIN" != "$PUBLIC_REPO" ]; then
      echo "Acquisition repository has an unexpected origin; refusing to reuse it." >&2
      exit 1
    fi
  else
    git init --bare -q "$MIRROR"
    git --git-dir="$MIRROR" remote add origin "$PUBLIC_REPO"
  fi

  if [ "$DESCRIPTOR_CHANNEL" = "pin" ]; then
    FETCH_SPEC="+refs/tags/$SOURCE_REF:refs/tags/$SOURCE_REF"
    RESOLVED_REF="refs/tags/$SOURCE_REF"
  else
    FETCH_SPEC="+refs/heads/$SOURCE_REF:refs/remotes/origin/$SOURCE_REF"
    RESOLVED_REF="refs/remotes/origin/$SOURCE_REF"
  fi
  if ! git --git-dir="$MIRROR" fetch --force --prune origin "$FETCH_SPEC" "+refs/tags/*:refs/tags/*"; then
    if [ "${SYNTHESIS_ONBOARD_ALLOW_STALE:-}" != "1" ] || \
       ! git --git-dir="$MIRROR" rev-parse --verify "$RESOLVED_REF^{commit}" >/dev/null 2>&1; then
      echo "Could not verify $SOURCE_REF from the public repository; refusing stale execution." >&2
      exit 1
    fi
    echo "Warning: using an explicitly accepted cached immutable release for $SOURCE_REF." >&2
  fi
  RESOLVED_COMMIT=$(git --git-dir="$MIRROR" rev-parse --verify "$RESOLVED_REF^{commit}")
  CHECKOUT_PARENT=$(mktemp -d "$CACHE_ROOT/acquisition/checkout.XXXXXX")
  CHECKOUT="$CHECKOUT_PARENT/source"
  git --git-dir="$MIRROR" worktree add --detach "$CHECKOUT" "$RESOLVED_COMMIT" >/dev/null
fi

if [ "$#" -eq 0 ]; then
  set -- setup
fi
python3 -B "$CHECKOUT/$BOOTSTRAP_REL" \
  --checkout "$CHECKOUT" \
  --releases-dir "$RELEASES_DIR" \
  --launcher "$LAUNCHER" \
  --active-descriptor "$ACTIVE_DESCRIPTOR" \
  --channel "$DESCRIPTOR_CHANNEL" \
  --ref "$SOURCE_REF" \
  --source-url "$PUBLIC_REPO" \
  -- "$@"
