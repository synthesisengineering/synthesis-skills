#!/bin/sh
# One audited bootstrap for the synthesis work system.
#
#   curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
#   curl -fsSL .../onboard.sh | sh -s -- setup --profile skills-only
#   curl -fsSL .../onboard.sh | sh -s -- setup --channel edge
#   curl -fsSL .../onboard.sh | sh -s -- setup --pin X.Y.Z
#   curl -fsSL .../onboard.sh | sh -s -- fleet join [--kb URL-or-PATH]
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
SELECTED_PROFILE=""
OMIT_DORMANT=0

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
  if [ "$PREVIOUS" = "profile" ]; then
    SELECTED_PROFILE="$ARG"
    PREVIOUS=""
    continue
  fi
  case "$ARG" in
    --channel) PREVIOUS="channel" ;;
    --channel=*) CHANNEL=${ARG#--channel=} ;;
    --pin) PREVIOUS="pin" ;;
    --pin=*) VERSION_PIN=${ARG#--pin=} ;;
    --profile) PREVIOUS="profile" ;;
    --profile=*) SELECTED_PROFILE=${ARG#--profile=} ;;
    --no-dormant-core) OMIT_DORMANT=1 ;;
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
if [ -z "${SYNTHESIS_BOOTSTRAP_PYTHON:-}" ]; then
  SYNTHESIS_BOOTSTRAP_PYTHON=""
  for CANDIDATE in python3.12 python3.13 python3.14 python3; do
    if command -v "$CANDIDATE" >/dev/null 2>&1 && "$CANDIDATE" -I -B -c 'import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,12),(3,13),(3,14)) else 1)' >/dev/null 2>&1; then
      SYNTHESIS_BOOTSTRAP_PYTHON=$(command -v "$CANDIDATE")
      break
    fi
  done
fi
if [ -z "$SYNTHESIS_BOOTSTRAP_PYTHON" ] || [ ! -x "$SYNTHESIS_BOOTSTRAP_PYTHON" ]; then
  echo "A supported Python interpreter is unavailable; install Python 3.12, 3.13 or 3.14." >&2
  exit 2
fi
case "$SYNTHESIS_BOOTSTRAP_PYTHON" in /*) ;; *) echo "Bootstrap Python must be an absolute executable path." >&2; exit 2 ;; esac
SYNTHESIS_RUNTIME_POLICY=packaged-python-v1
export SYNTHESIS_RUNTIME_POLICY
if ! "$SYNTHESIS_BOOTSTRAP_PYTHON" -I -B -c 'import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,12),(3,13),(3,14)) and sys.version_info.releaselevel == "final" else 1)'; then
  echo "Bootstrap requires a final Python 3.12, 3.13 or 3.14 release." >&2
  exit 2
fi

SYNTHESIS_HOME_DIR="${SYNTHESIS_HOME:-$HOME}"
case "${1:-}" in
  update|repair)
    SAVED_SELECTION=$("$SYNTHESIS_BOOTSTRAP_PYTHON" -I -B - "${XDG_CONFIG_HOME:-$SYNTHESIS_HOME_DIR/.config}/synthesis/system-state.json" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
if path.is_symlink():
    raise SystemExit('Saved selection must be a regular file.')
if path.exists():
    value = json.loads(path.read_text())
    if value.get('profile') == 'modular' and value.get('modular', {}).get('stage_core') is False:
        print('modular-opt-out')
PY
    )
    if [ "$SAVED_SELECTION" = "modular-opt-out" ]; then
      SELECTED_PROFILE=modular
      OMIT_DORMANT=1
    fi
    ;;
esac
CACHE_ROOT="${SYNTHESIS_ONBOARD_CACHE_DIR:-${XDG_CACHE_HOME:-$SYNTHESIS_HOME_DIR/.cache}/synthesis}"
STATE_ROOT="${XDG_STATE_HOME:-$SYNTHESIS_HOME_DIR/.local/state}/synthesis"
BIN_ROOT="${SYNTHESIS_INSTALL_BIN_DIR:-$SYNTHESIS_HOME_DIR/.local/bin}"
RELEASES_DIR="$CACHE_ROOT/releases"
ACTIVE_DESCRIPTOR="$STATE_ROOT/active-release.json"
LAUNCHER="$BIN_ROOT/synthesis"
CHECKOUT=""
MIRROR=""
TRANSIENT_ACQUISITION=""

cleanup() {
  if [ -n "$MIRROR" ] && [ -n "$CHECKOUT" ] && [ -e "$CHECKOUT/.git" ]; then
    git --git-dir="$MIRROR" worktree remove --force "$CHECKOUT" >/dev/null 2>&1 || true
  fi
  if [ -n "${CHECKOUT_PARENT:-}" ] && [ -d "$CHECKOUT_PARENT" ]; then
    rmdir "$CHECKOUT_PARENT" >/dev/null 2>&1 || true
  fi
  if [ -n "$TRANSIENT_ACQUISITION" ]; then
    "$SYNTHESIS_BOOTSTRAP_PYTHON" -I -B - "$TRANSIENT_ACQUISITION" "$$" <<'PY'
import pathlib, shutil, sys
root = pathlib.Path(sys.argv[1])
marker = root / '.synthesis-acquisition-owner'
if (not root.is_absolute() or root.is_symlink() or not root.name.startswith('synthesis-acquisition.')
        or not marker.is_file() or marker.is_symlink() or marker.read_text().strip() != sys.argv[2]):
    raise SystemExit('Transient acquisition ownership is invalid; preserving it.')
shutil.rmtree(root)
PY
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
  ACQUISITION_ROOT="$CACHE_ROOT/acquisition"
  if { [ "$SELECTED_PROFILE" = "modular" ] || [ "${1:-}" = "stage-core" ]; } && [ "$OMIT_DORMANT" -eq 1 ]; then
    TRANSIENT_ACQUISITION=$(mktemp -d "${TMPDIR:-/tmp}/synthesis-acquisition.XXXXXX")
    printf '%s\n' "$$" > "$TRANSIENT_ACQUISITION/.synthesis-acquisition-owner"
    ACQUISITION_ROOT="$TRANSIENT_ACQUISITION"
  fi
  MIRROR="$ACQUISITION_ROOT/synthesis-skills.git"
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
  CHECKOUT_PARENT=$(mktemp -d "$ACQUISITION_ROOT/checkout.XXXXXX")
  CHECKOUT="$CHECKOUT_PARENT/source"
  git --git-dir="$MIRROR" worktree add --detach "$CHECKOUT" "$RESOLVED_COMMIT" >/dev/null
fi

if [ -n "${SYNTHESIS_ONBOARD_EXPECTED_COMMIT:-}" ]; then
  if [ "$(git -C "$CHECKOUT" rev-parse --verify 'HEAD^{commit}')" != "$SYNTHESIS_ONBOARD_EXPECTED_COMMIT" ]; then
    echo "Acquired release differs from the package's immutable source commit." >&2
    exit 1
  fi
fi

if [ "$#" -eq 0 ]; then
  set -- setup
fi
"$SYNTHESIS_BOOTSTRAP_PYTHON" -B "$CHECKOUT/$BOOTSTRAP_REL" \
  --checkout "$CHECKOUT" \
  --releases-dir "$RELEASES_DIR" \
  --launcher "$LAUNCHER" \
  --active-descriptor "$ACTIVE_DESCRIPTOR" \
  --channel "$DESCRIPTOR_CHANNEL" \
  --ref "$SOURCE_REF" \
  --source-url "$PUBLIC_REPO" \
  -- "$@"
