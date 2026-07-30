#!/bin/sh
set -eu

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
TEST_ROOT=$(mktemp -d)
TARGET="${TEST_ROOT}/installed"

cleanup() {
    rm -rf "$TEST_ROOT"
}
trap cleanup EXIT INT TERM

SYNTHESIS_SKILLS_HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" install >/dev/null

expected=$(find "$REPO_ROOT/skills" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
actual=$(find "$TARGET" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
[ "$actual" = "$expected" ]

grep -q '"source_path": "skills/synthesis-agent-conformance/SKILL.md"' \
    "$TARGET/synthesis-agent-conformance/.source.json"

SYNTHESIS_SKILLS_HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" status >/dev/null

printf '\nDRIFT\n' >> "$TARGET/synthesis-agent-conformance/SKILL.md"
if SYNTHESIS_SKILLS_HOME="$TEST_ROOT" \
   SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
   SYNTHESIS_SKILLS_TARGETS="$TARGET" \
       "$REPO_ROOT/install.sh" status >/dev/null 2>&1; then
    echo "status accepted a drifted installation" >&2
    exit 1
fi

SYNTHESIS_SKILLS_HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" install >/dev/null

SYNTHESIS_SKILLS_HOME="$TEST_ROOT" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
SYNTHESIS_SKILLS_TARGETS="$TARGET" \
    "$REPO_ROOT/install.sh" uninstall >/dev/null

[ ! -d "$TARGET/synthesis-agent-conformance" ]

PLUGIN_HOME="${TEST_ROOT}/plugin-home"
PLUGIN_BIN="${TEST_ROOT}/plugin-bin"
mkdir -p "$PLUGIN_BIN"
printf '%s\n' '#!/bin/sh' 'printf '\''[{"id":"synthesis-skills@test","enabled":true}]\n'\''' \
    > "$PLUGIN_BIN/claude"
printf '%s\n' '#!/bin/sh' 'printf '\''{"installed":[{"name":"synthesis-skills","enabled":true}]}\n'\''' \
    > "$PLUGIN_BIN/codex"
chmod +x "$PLUGIN_BIN/claude" "$PLUGIN_BIN/codex"

for plugin_target in \
    "$PLUGIN_HOME/.claude/skills" \
    "$PLUGIN_HOME/.agents/skills" \
    "$PLUGIN_HOME/.codex/skills"; do
    SYNTHESIS_SKILLS_HOME="$PLUGIN_HOME" \
    SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
    SYNTHESIS_SKILLS_TARGETS="$plugin_target" \
        "$REPO_ROOT/install.sh" install >/dev/null
done

PATH="$PLUGIN_BIN:$PATH" \
SYNTHESIS_SKILLS_HOME="$PLUGIN_HOME" \
SYNTHESIS_SKILLS_SOURCE_DIR="$REPO_ROOT" \
XDG_CACHE_HOME="$TEST_ROOT/plugin-cache" \
    "$REPO_ROOT/install.sh" install >/dev/null

PLUGIN_STATUS=$(
    PATH="$PLUGIN_BIN:$PATH" \
    SYNTHESIS_SKILLS_HOME="$PLUGIN_HOME" \
    XDG_CACHE_HOME="$TEST_ROOT/stale-plugin-cache" \
        "$REPO_ROOT/install.sh" status 2>&1
)
printf '%s\n' "$PLUGIN_STATUS" | grep -q 'Claude Code plugin: installed and enabled'
printf '%s\n' "$PLUGIN_STATUS" | grep -q 'Codex plugin:       installed and enabled'
if printf '%s\n' "$PLUGIN_STATUS" | grep -q '^find:'; then
    echo "plugin-native status tried to read a missing cache skill tree" >&2
    exit 1
fi

printf '%s\n' '#!/bin/sh' 'printf '\''[{"id":"synthesis-skills@test","enabled":false}]\n'\''' \
    > "$PLUGIN_BIN/claude"
printf '%s\n' '#!/bin/sh' 'printf '\''{"installed":[{"name":"synthesis-skills","enabled":false}]}\n'\''' \
    > "$PLUGIN_BIN/codex"
DISABLED_STATUS=$(
    PATH="$PLUGIN_BIN:$PATH" \
    SYNTHESIS_SKILLS_HOME="$PLUGIN_HOME" \
    SYNTHESIS_SKILLS_TARGETS="$TEST_ROOT/disabled-target" \
        "$REPO_ROOT/install.sh" status 2>&1 || true
)
printf '%s\n' "$DISABLED_STATUS" | grep -q 'Claude Code plugin: not installed or disabled'
printf '%s\n' "$DISABLED_STATUS" | grep -q 'Codex plugin:       not installed or disabled'

for plugin_target in \
    "$PLUGIN_HOME/.claude/skills" \
    "$PLUGIN_HOME/.agents/skills" \
    "$PLUGIN_HOME/.codex/skills"; do
    [ -z "$(find "$plugin_target" -mindepth 1 -maxdepth 1 -type d -name 'synthesis-*' -print -quit)" ]
done
find "$TEST_ROOT/plugin-cache/synthesis-skills-backups" \
    -path '*/retired-*/*/SKILL.md' -type f | grep -q .

echo "installer tests passed"
