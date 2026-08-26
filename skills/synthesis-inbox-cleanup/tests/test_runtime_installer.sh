#!/bin/sh
set -eu

SKILL_ROOT=$(cd "$(dirname "$0")/.." && pwd)
FIXTURE_ROOT="$SKILL_ROOT/tests/fixtures"
TEST_ROOT=$(mktemp -d)
SOURCE_SENTINEL="$SKILL_ROOT/.runtime-installer-source-sentinel"
CWD_SENTINEL="$TEST_ROOT/cwd-sentinel"

cleanup() {
    if [ -d "$TEST_ROOT" ]; then
        rm -rf "$TEST_ROOT"
    fi
    if [ -f "$SOURCE_SENTINEL" ]; then
        rm -f "$SOURCE_SENTINEL"
    fi
}
trap cleanup EXIT INT TERM

touch "$SOURCE_SENTINEL" "$CWD_SENTINEL"

(
    cd "$TEST_ROOT"
    SYNTHESIS_INBOX_HOME="$TEST_ROOT/runtime" \
        "$SKILL_ROOT/scripts/install.sh" >/dev/null
)

test -f "$SOURCE_SENTINEL"
test -f "$CWD_SENTINEL"
test -L "$TEST_ROOT/runtime/engine/current"
test -f "$TEST_ROOT/runtime/engine/current/_lib.py"
test -f "$TEST_ROOT/runtime/engine/current/icloud_plan.py"

FIRST_TARGET=$(readlink "$TEST_ROOT/runtime/engine/current")
(
    cd "$SKILL_ROOT"
    SYNTHESIS_INBOX_HOME="$TEST_ROOT/runtime" \
        "$SKILL_ROOT/scripts/install.sh" >/dev/null
)
SECOND_TARGET=$(readlink "$TEST_ROOT/runtime/engine/current")

test "$FIRST_TARGET" = "$SECOND_TARGET"
test -f "$SOURCE_SENTINEL"
test -f "$CWD_SENTINEL"

SYMLINK_TARGET="$TEST_ROOT/symlink-target"
SYMLINK_RUNTIME="$TEST_ROOT/symlink-runtime"
mkdir -p "$SYMLINK_TARGET"
touch "$SYMLINK_TARGET/preserved"
ln -s "$SYMLINK_TARGET" "$SYMLINK_RUNTIME"
if SYNTHESIS_INBOX_HOME="$SYMLINK_RUNTIME" \
    "$SKILL_ROOT/scripts/install.sh" >/dev/null 2>&1; then
    echo "runtime installer accepted a symlinked runtime root" >&2
    exit 1
fi
test -f "$SYMLINK_TARGET/preserved"

release_dir="$TEST_ROOT/runtime/engine/$FIRST_TARGET"
printf '\nDRIFT\n' >> "$release_dir/_lib.py"
if SYNTHESIS_INBOX_HOME="$TEST_ROOT/runtime" \
    "$SKILL_ROOT/scripts/install.sh" >/dev/null 2>&1; then
    echo "runtime installer accepted a drifted immutable release" >&2
    exit 1
fi

test -f "$SOURCE_SENTINEL"
test -f "$CWD_SENTINEL"

# Regression: engine/current must be REPOINTED when it already exists as a
# symlink to a directory. Without `mv -h`, mv follows the link and deposits the
# staged pointer INSIDE the old release, leaving the runtime pinned to the
# previous version while every earlier install step reports success. Observed in
# production 2026-08-24: a stale runtime missing resolve_scope.py, with a stray
# .current.<pid>.tmp found inside the old release directory.
REPOINT_ROOT="$TEST_ROOT/repoint"
mkdir -p "$REPOINT_ROOT"
SYNTHESIS_INBOX_HOME="$REPOINT_ROOT" "$SKILL_ROOT/scripts/install.sh" >/dev/null 2>&1
OLD_TARGET=$(readlink "$REPOINT_ROOT/engine/current")
OLD_RELEASE="$REPOINT_ROOT/engine/$OLD_TARGET"
test -d "$OLD_RELEASE"

# Force a different source digest so the installer must stage a NEW release and
# move the pointer onto the existing symlink.
STAGED_SOURCE="$TEST_ROOT/altered-skill"
cp -R "$SKILL_ROOT" "$STAGED_SOURCE"
printf '\n# regression-marker\n' >> "$STAGED_SOURCE/scripts/_lib.py"
PORTABLE_BIN="$TEST_ROOT/portable-bin"
mkdir -p "$PORTABLE_BIN"
cp "$FIXTURE_ROOT/mv-no-h" "$PORTABLE_BIN/mv"
chmod 700 "$PORTABLE_BIN/mv"
SYNTHESIS_TEST_REAL_MV=$(command -v mv) \
    PATH="$PORTABLE_BIN:$PATH" \
    SYNTHESIS_INBOX_HOME="$REPOINT_ROOT" \
    "$STAGED_SOURCE/scripts/install.sh" >/dev/null 2>&1 || {
    echo "installer failed while repointing an existing engine/current" >&2
    exit 1
}
NEW_TARGET=$(readlink "$REPOINT_ROOT/engine/current")
if [ "$NEW_TARGET" = "$OLD_TARGET" ]; then
    echo "engine/current was NOT repointed to the new release" >&2
    exit 1
fi
if ls -A "$OLD_RELEASE" | grep -q '^\.current\.'; then
    echo "staged pointer leaked into the old release directory" >&2
    exit 1
fi
grep -q 'regression-marker' "$REPOINT_ROOT/engine/current/_lib.py" || {
    echo "engine/current does not serve the newly installed release" >&2
    exit 1
}

echo "inbox runtime installer tests passed"
