#!/bin/sh
set -eu

SKILL_ROOT=$(cd "$(dirname "$0")/.." && pwd)
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
echo "inbox runtime installer tests passed"
