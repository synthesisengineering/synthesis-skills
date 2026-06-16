#!/bin/bash
#
# synthesis-inbox-cleanup installer.
#
# Idempotent. Run multiple times safely. Creates ~/.synthesis/inbox-cleanup/,
# seeds config.yaml and rules.yaml from the bundled templates (only if no
# existing files — does not overwrite), and prints next-step instructions.
#
# Usage:
#   ~/.claude/skills/synthesis-inbox-cleanup/scripts/install.sh
#
# Or directly from the skill's source:
#   ~/workspaces/<you>/synthesis-skills/synthesis-inbox-cleanup/scripts/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$SKILL_DIR/templates"

TARGET_DIR="$HOME/.synthesis/inbox-cleanup"
CONFIG_PATH="$TARGET_DIR/config.yaml"
RULES_PATH="$TARGET_DIR/rules.yaml"

mkdir -p "$TARGET_DIR"
chmod 700 "$TARGET_DIR"   # private dir: rules.yaml/config.yaml/imap.secret live here

echo "→ Skill location:  $SKILL_DIR"
echo "→ Private rules:   $TARGET_DIR"
echo ""

# config.yaml — account + behavior configuration
if [ -f "$CONFIG_PATH" ]; then
    echo "✓ Config already exists at $CONFIG_PATH — not overwriting."
else
    echo "→ Seeding initial config at $CONFIG_PATH from template"
    cp "$TEMPLATES_DIR/config.example.yaml" "$CONFIG_PATH"
    chmod 600 "$CONFIG_PATH"
    echo ""
    echo "  ⚠️  Edit $CONFIG_PATH and:"
    echo "      - Replace YOUR-EMAIL@example.com with your IMAP account address"
    echo "      - Adjust 'host' if not using iCloud"
    echo "      - Optionally configure 'catchall' if you own a catch-all domain"
    echo ""
fi

# rules.yaml — sender rules manifest
if [ -f "$RULES_PATH" ]; then
    echo "✓ Rules already exist at $RULES_PATH — not overwriting."
else
    echo "→ Seeding initial rules at $RULES_PATH from template"
    cp "$TEMPLATES_DIR/rules.example.yaml" "$RULES_PATH"
    chmod 600 "$RULES_PATH"
    echo ""
    echo "  ⚠️  Edit $RULES_PATH and add your personal:"
    echo "      - never_touch domains (banks, payroll, healthcare, employer)"
    echo "      - never_touch addresses (family, close contacts)"
    echo "      - sender rules (promo / newsletter / notification senders)"
    echo ""
fi

# Verify Python + PyYAML available
if ! python3 -c 'import yaml' 2>/dev/null; then
    echo ""
    echo "⚠️  PyYAML not installed. The scripts need it."
    echo "   Install with: pip3 install --user PyYAML"
    echo ""
fi

# Check for Keychain credential
if ! security find-generic-password -s inbox-cleanup-imap -w >/dev/null 2>&1; then
    echo "⚠️  No IMAP password found in Keychain (service: inbox-cleanup-imap)."
    echo "   Generate an app-specific password at your mail provider, then:"
    echo ""
    echo "       security add-generic-password -s inbox-cleanup-imap -a \"\$USER\" -w"
    echo ""
    echo "   (Paste the password when prompted — never put it in shell history.)"
    echo ""
    echo "   Fallback: write the password to $TARGET_DIR/imap.secret (chmod 600)."
    echo ""
fi

echo "─────────────────────────────────────────────────────────────────"
echo "✓ synthesis-inbox-cleanup installed."
echo ""
echo "  Next steps:"
echo "    1. Edit $CONFIG_PATH"
echo "    2. Edit $RULES_PATH"
echo "    3. Store the IMAP password in Keychain (see above)"
echo "    4. Sanity-check:"
echo "         cd $SCRIPT_DIR"
echo "         python3 icloud_census.py"
echo ""
echo "  Adversarial fixture tests (verify defenses):"
echo "         python3 $SKILL_DIR/tests/run_poisoned.py"
echo ""
