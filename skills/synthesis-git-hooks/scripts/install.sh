#!/bin/bash
#
# synthesis-git-hooks installer.
#
# Idempotent. Run multiple times safely. Copies the engine to
# ~/.synthesis/git-hooks/, sets git's `core.hooksPath`, and seeds an
# initial ~/.synthesis/git-hook-config.yaml from the bundled template
# (only if no config exists yet — does not overwrite existing config).
#
# Usage:
#   <synthesis-git-hooks-root>/scripts/install.sh
#
# Or directly from the skill's source:
#   ~/workspaces/<you>/synthesis-skills/skills/synthesis-git-hooks/scripts/install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SKILLS_DIR="$(cd -- "$SCRIPT_DIR/../.." &> /dev/null && pwd)"
COORDINATION_SOURCE="$SKILLS_DIR/synthesis-project-management/scripts"
COORDINATION_REFERENCES="$SKILLS_DIR/synthesis-project-management/references"

TARGET_DIR="$HOME/.synthesis/git-hooks"
TARGET_REFERENCES="$HOME/.synthesis/references"
CONFIG_PATH="$HOME/.synthesis/git-hook-config.yaml"

for source in \
    "$COORDINATION_SOURCE/coordination.py" \
    "$COORDINATION_SOURCE/coordination_schema.py" \
    "$COORDINATION_SOURCE/pointer_lock.py" \
    "$COORDINATION_SOURCE/peer_addressing.py" \
    "$COORDINATION_REFERENCES/session-words-v1.txt.zlib.b85"; do
    [ -f "$source" ] || {
        echo "✖ Required synthesis-project-management dependency missing: $source" >&2
        exit 1
    }
done

mkdir -p "$TARGET_DIR"
mkdir -p "$TARGET_REFERENCES"
mkdir -p "$(dirname "$CONFIG_PATH")"

echo "→ Copying engine to $TARGET_DIR/"
cp -f "$SCRIPT_DIR/pre-commit" "$TARGET_DIR/pre-commit"
cp -f "$SCRIPT_DIR/commit-msg" "$TARGET_DIR/commit-msg"
cp -f "$SCRIPT_DIR/_load_config.py" "$TARGET_DIR/_load_config.py"
cp -f "$COORDINATION_SOURCE/coordination.py" "$TARGET_DIR/coordination.py"
cp -f "$COORDINATION_SOURCE/coordination_schema.py" "$TARGET_DIR/coordination_schema.py"
cp -f "$COORDINATION_SOURCE/pointer_lock.py" "$TARGET_DIR/pointer_lock.py"
cp -f "$COORDINATION_SOURCE/peer_addressing.py" "$TARGET_DIR/peer_addressing.py"
printf '%s\n' "$SCRIPT_DIR" > "$TARGET_DIR/source-path"
cp -f "$COORDINATION_REFERENCES/session-words-v1.txt.zlib.b85" \
    "$TARGET_REFERENCES/session-words-v1.txt.zlib.b85"
chmod +x \
    "$TARGET_DIR/pre-commit" \
    "$TARGET_DIR/commit-msg" \
    "$TARGET_DIR/_load_config.py" \
    "$TARGET_DIR/coordination.py" \
    "$TARGET_DIR/coordination_schema.py" \
    "$TARGET_DIR/pointer_lock.py" \
    "$TARGET_DIR/peer_addressing.py"
chmod 644 "$TARGET_DIR/source-path"

if [ -f "$CONFIG_PATH" ]; then
    echo "→ Config already exists at $CONFIG_PATH — not overwriting."
    echo "  (Edit it manually; the template is at $SCRIPT_DIR/git-hook-config.example.yaml.)"
else
    echo "→ Seeding initial config at $CONFIG_PATH from template"
    cp "$SCRIPT_DIR/git-hook-config.example.yaml" "$CONFIG_PATH"
    echo ""
    echo "  ⚠️  Edit $CONFIG_PATH and replace 'YOUR-PERSONAL-ORG' in"
    echo "      'personal_remote_patterns' with your actual GitHub user/org."
    echo ""
fi

CURRENT=$(git config --global core.hooksPath 2>/dev/null || true)
if [ "$CURRENT" = "$TARGET_DIR" ]; then
    echo "→ core.hooksPath already points to $TARGET_DIR"
else
    if [ -n "$CURRENT" ]; then
        echo "→ Current core.hooksPath: $CURRENT"
        echo "  Updating to: $TARGET_DIR"
    else
        echo "→ Setting core.hooksPath to: $TARGET_DIR"
    fi
    git config --global core.hooksPath "$TARGET_DIR"
fi

# v2: the sidecar is stdlib-only — no PyYAML or any third-party dependency.
# Any python3 >= 3.6 on PATH works identically. Verify the whole chain:
echo ""
echo "→ Running the health check (doctor)…"
if python3 "$TARGET_DIR/_load_config.py" --doctor; then
    echo ""
    echo "✓ synthesis-git-hooks installed and HEALTHY."
else
    echo ""
    echo "✖ synthesis-git-hooks installed but the doctor found problems (above)."
    echo "  Commits are BLOCKED (fail closed) until they are fixed."
    exit 1
fi
echo ""
echo "  Engine:  $TARGET_DIR/pre-commit"
echo "  Sidecar: $TARGET_DIR/_load_config.py"
echo "  Config:  $CONFIG_PATH"
echo ""
echo "  Health check any time:  python3 $TARGET_DIR/_load_config.py --doctor"
echo "  Repo classification:    cd <repo> && $TARGET_DIR/_load_config.py --classify"
echo ""
