#!/bin/sh
#
# synthesis-inbox-cleanup installer (v5).
#
# Idempotent. Creates the private rules folder (~/.synthesis/inbox-cleanup/,
# mode 700), seeds config.yaml and rules.yaml from the bundled templates only
# when they are absent (it never overwrites), and reports what is still
# missing: certifi, the Keychain password, and the engine's stable path.
#
# The engine is no longer copied here. The v5 runtime installs it at
#   ~/.synthesis/v5/current/skills/synthesis-inbox-cleanup/scripts
# which survives Claude Code and Codex plugin updates (lesson 2026-08-27:
# durable runtime state must not pin to versioned paths). Private extensions
# and scheduled jobs import the engine from that path.
#
# Usage: <synthesis-inbox-cleanup-root>/scripts/install.sh
# SYNTHESIS_INBOX_HOME and SYNTHESIS_HOME override the two folders (tests).

set -eu

SKILL_DIR=$(cd "$(dirname "$0")/.." && pwd)
TEMPLATES_DIR="$SKILL_DIR/templates"
TARGET_DIR=${SYNTHESIS_INBOX_HOME:-$HOME/.synthesis/inbox-cleanup}
V5_HOME=${SYNTHESIS_HOME:-$HOME/.synthesis/v5}
ENGINE="$V5_HOME/current/skills/synthesis-inbox-cleanup/scripts"

refuse() {
    echo "ERROR: $1" >&2
    exit 1
}

case "$TARGET_DIR" in
    "" | / | "$HOME" | "$HOME/") refuse "refusing unsafe inbox runtime root: '$TARGET_DIR'" ;;
esac
if [ -L "$TARGET_DIR" ]; then
    refuse "refusing symlinked inbox runtime root: $TARGET_DIR"
fi
if [ -e "$TARGET_DIR" ] && [ ! -d "$TARGET_DIR" ]; then
    refuse "refusing non-directory inbox runtime root: $TARGET_DIR"
fi

mkdir -p "$TARGET_DIR"
chmod 700 "$TARGET_DIR"   # private: rules.yaml, config.yaml and imap.secret live here
echo "→ Skill location:  $SKILL_DIR"
echo "→ Private rules:   $TARGET_DIR"

seed() {   # seed <template> <target> <what to edit>
    if [ -e "$2" ]; then
        echo "✓ $2 already exists — not overwriting."
    else
        cp "$TEMPLATES_DIR/$1" "$2"
        chmod 600 "$2"
        echo "→ Seeded $2 from $1. Edit it: $3"
    fi
}
seed config.example.yaml "$TARGET_DIR/config.yaml" \
    "your IMAP account address, 'host' if not iCloud, and 'catchall' if you own a catch-all domain."
seed rules.example.yaml "$TARGET_DIR/rules.yaml" \
    "never_touch domains and addresses first (banks, payroll, healthcare, employer, family), then sender rules."

missing=0
note() {
    echo "⚠️  $1"
    missing=$((missing + 1))
}

engine_ok=1
for file in _lib.py icloud_plan.py icloud_apply.py; do
    [ -f "$ENGINE/$file" ] || engine_ok=0
done
if [ "$engine_ok" -eq 0 ]; then
    note "The engine is not at its stable path $ENGINE. Start a session with the synthesis plugin (its SessionStart hook installs the v5 runtime), or run python3 -S <plugin>/synthesis/install.py <plugin>."
fi
if [ -d "$TARGET_DIR/engine" ]; then
    note "An engine copy from version 1.x is still at $TARGET_DIR/engine. Anything reading it runs old code: point it at $ENGINE, then remove that folder."
fi
python3 -c 'import certifi' 2>/dev/null || note "certifi is not installed; verified IMAP TLS needs its CA bundle: pip3 install --user certifi"
if command -v security >/dev/null 2>&1 && ! security find-generic-password -s inbox-cleanup-imap -w >/dev/null 2>&1; then
    note "No IMAP password in the Keychain (service inbox-cleanup-imap). Generate an app-specific password at your provider, then run: security add-generic-password -s inbox-cleanup-imap -a \"\$USER\" -w (paste when prompted, never in shell history). Fallback: $TARGET_DIR/imap.secret, mode 600."
fi

echo ""
echo "✓ synthesis-inbox-cleanup installed ($missing item(s) above to resolve)."
echo "  Sanity-check: python3 $ENGINE/icloud_census.py"
echo "  Adversarial fixtures: python3 $SKILL_DIR/tests/run_poisoned.py"
