#!/bin/bash
#
# synthesis-inbox-cleanup installer.
#
# Idempotent. Run multiple times safely. Creates ~/.synthesis/inbox-cleanup/,
# installs an immutable engine release behind a stable `engine/current`
# symlink, seeds config.yaml and rules.yaml from the bundled templates (only
# if no existing files — does not overwrite), and prints next-step
# instructions.
#
# Usage:
#   <synthesis-inbox-cleanup-root>/scripts/install.sh
#
# Or directly from the skill's source:
#   ~/workspaces/<you>/synthesis-skills/skills/synthesis-inbox-cleanup/scripts/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$SKILL_DIR/templates"

TARGET_DIR="${SYNTHESIS_INBOX_HOME:-$HOME/.synthesis/inbox-cleanup}"
CONFIG_PATH="$TARGET_DIR/config.yaml"
RULES_PATH="$TARGET_DIR/rules.yaml"
ENGINE_ROOT="$TARGET_DIR/engine"
ENGINE_RELEASES="$ENGINE_ROOT/releases"
ENGINE_CURRENT="$ENGINE_ROOT/current"

validate_runtime_root() {
    case "$TARGET_DIR" in
        /|"$HOME")
            echo "ERROR: refusing unsafe inbox runtime root: $TARGET_DIR" >&2
            return 1
            ;;
    esac
    for path in "$TARGET_DIR" "$ENGINE_ROOT" "$ENGINE_RELEASES"; do
        if [ -L "$path" ]; then
            echo "ERROR: refusing symlinked inbox runtime path: $path" >&2
            return 1
        fi
    done
    if [ -e "$TARGET_DIR" ] && [ ! -d "$TARGET_DIR" ]; then
        echo "ERROR: refusing non-directory inbox runtime root: $TARGET_DIR" >&2
        return 1
    fi
}

engine_digest() {
    directory="$1"
    (
        cd "$directory"
        for file in *.py *.applescript; do
            [ -f "$file" ] || continue
            printf '%s  ' "$file"
            shasum -a 256 "$file"
        done
    ) | shasum -a 256 | awk '{print $1}'
}

install_engine_runtime() {
    source_digest="$(engine_digest "$SCRIPT_DIR")"
    release_dir="$ENGINE_RELEASES/$source_digest"

    mkdir -p "$ENGINE_RELEASES"
    chmod 700 "$ENGINE_ROOT" "$ENGINE_RELEASES"

    if [ -L "$release_dir" ]; then
        echo "ERROR: refusing symlinked engine release: $release_dir" >&2
        return 1
    fi

    if [ -d "$release_dir" ]; then
        installed_digest="$(engine_digest "$release_dir")"
        if [ "$installed_digest" != "$source_digest" ]; then
            echo "ERROR: engine release content does not match its digest: $release_dir" >&2
            return 1
        fi
    else
        stage_dir="$(mktemp -d "$ENGINE_ROOT/.engine-stage.XXXXXX")"
        for source in "$SCRIPT_DIR"/*.py "$SCRIPT_DIR"/*.applescript; do
            [ -f "$source" ] || continue
            cp -p "$source" "$stage_dir/"
        done
        if [ ! -f "$stage_dir/_lib.py" ] || [ ! -f "$stage_dir/icloud_plan.py" ]; then
            echo "ERROR: staged engine is incomplete: $stage_dir" >&2
            return 1
        fi
        staged_digest="$(engine_digest "$stage_dir")"
        if [ "$staged_digest" != "$source_digest" ]; then
            echo "ERROR: staged engine failed digest verification: $stage_dir" >&2
            return 1
        fi
        chmod 700 "$stage_dir"
        mv "$stage_dir" "$release_dir"
    fi

    if [ -e "$ENGINE_CURRENT" ] && [ ! -L "$ENGINE_CURRENT" ]; then
        echo "ERROR: refusing non-symlink engine/current: $ENGINE_CURRENT" >&2
        return 1
    fi

    link_stage="$ENGINE_ROOT/.current.$$.tmp"
    if [ -e "$link_stage" ] || [ -L "$link_stage" ]; then
        echo "ERROR: temporary current-link path already exists: $link_stage" >&2
        return 1
    fi
    ln -s "releases/$source_digest" "$link_stage"
    # AGENT HEURISTIC: os.replace supplies the same atomic pointer swap on macOS
    # and Linux. BSD mv needs -h to replace a symlink to a directory, while GNU
    # mv rejects that option.
    python3 - "$link_stage" "$ENGINE_CURRENT" <<'PY'
import os
import sys

os.replace(sys.argv[1], sys.argv[2])
PY

    resolved_current="$(cd "$ENGINE_CURRENT" && pwd -P)"
    resolved_release="$(cd "$release_dir" && pwd -P)"
    if [ "$resolved_current" != "$resolved_release" ]; then
        echo "ERROR: engine/current did not resolve to the installed release" >&2
        return 1
    fi
    echo "✓ Stable engine runtime: $ENGINE_CURRENT"
}

validate_runtime_root
mkdir -p "$TARGET_DIR"
chmod 700 "$TARGET_DIR"   # private dir: rules.yaml/config.yaml/imap.secret live here

echo "→ Skill location:  $SKILL_DIR"
echo "→ Private rules:   $TARGET_DIR"
echo ""

install_engine_runtime

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

# Verify certifi — CA bundle for verified IMAP TLS (python.org Python lacks one)
if ! python3 -c 'import certifi' 2>/dev/null; then
    echo ""
    echo "⚠️  certifi not installed. Verified IMAP TLS needs a CA bundle."
    echo "   Install with: pip3 install --user certifi"
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
echo "         cd $ENGINE_CURRENT"
echo "         python3 icloud_census.py"
echo ""
echo "  Adversarial fixture tests (verify defenses):"
echo "         python3 $SKILL_DIR/tests/run_poisoned.py"
echo ""
