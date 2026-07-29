#!/bin/sh
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
TEST_ROOT=$(mktemp -d)
TARGET="${TEST_ROOT}/installed"

cleanup() {
    rm -rf "$TEST_ROOT"
}
trap cleanup EXIT INT TERM

HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" install >/dev/null

expected=$(find "$REPO_ROOT/skills" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
actual=$(find "$TARGET" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
[ "$actual" = "$expected" ]

grep -q '"source_path": "skills/synthesis-agent-conformance/SKILL.md"' \
    "$TARGET/synthesis-agent-conformance/.source.json"

HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" status >/dev/null

printf '\nDRIFT\n' >> "$TARGET/synthesis-agent-conformance/SKILL.md"
if HOME="$TEST_ROOT" \
   SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
   SYNTHESIS_SKILLS_TARGETS="$TARGET" \
       "$REPO_ROOT/install.sh" status >/dev/null 2>&1; then
    echo "status accepted a drifted installation" >&2
    exit 1
fi

HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" install >/dev/null

HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" uninstall >/dev/null

[ ! -d "$TARGET/synthesis-agent-conformance" ]
echo "installer tests passed"
