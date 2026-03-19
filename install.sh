#!/bin/sh
# Synthesis Skills installer — no Node.js required
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rajivpant/synthesis-skills/main/install.sh | sh
#   ./install.sh install    # Install all skills
#   ./install.sh update     # Update to latest
#   ./install.sh uninstall  # Remove all installed skills

set -e

REPO_URL="https://github.com/rajivpant/synthesis-skills.git"
REPO_NAME="synthesis-skills"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/synthesis-skills"

# Skill directories to install to (auto-detected)
detect_targets() {
    TARGETS=""
    # Claude Code (primary)
    TARGETS="$TARGETS $HOME/.claude/skills"
    # Cross-platform convention
    TARGETS="$TARGETS $HOME/.agents/skills"
    # Cursor
    if [ -d "$HOME/.cursor" ]; then
        TARGETS="$TARGETS $HOME/.cursor/skills"
    fi
    echo "$TARGETS"
}

# List skill directories (directories containing SKILL.md)
list_skills() {
    find "$1" -maxdepth 2 -name "SKILL.md" -exec dirname {} \; | sort
}

# Get list of our skill names from the repo
our_skill_names() {
    list_skills "$CACHE_DIR" | while read -r dir; do
        basename "$dir"
    done
}

do_install() {
    echo "Installing Synthesis Skills..."

    # Clone or update cache
    if [ -d "$CACHE_DIR/.git" ]; then
        echo "Updating cached repo..."
        git -C "$CACHE_DIR" pull --quiet
    else
        echo "Cloning repository..."
        rm -rf "$CACHE_DIR"
        git clone --quiet "$REPO_URL" "$CACHE_DIR"
    fi

    TARGETS=$(detect_targets)
    SKILL_COUNT=0

    for target in $TARGETS; do
        mkdir -p "$target"
        for skill_dir in $(list_skills "$CACHE_DIR"); do
            skill_name=$(basename "$skill_dir")
            # Skip non-skill directories
            case "$skill_name" in
                .git|node_modules|.github) continue ;;
            esac
            # Remove old version and copy fresh
            rm -rf "${target}/${skill_name}"
            cp -R "$skill_dir" "${target}/${skill_name}"
            SKILL_COUNT=$((SKILL_COUNT + 1))
        done
        echo "  Installed to: $target"
    done

    UNIQUE_SKILLS=$(our_skill_names | wc -l | tr -d ' ')
    echo ""
    echo "Done. $UNIQUE_SKILLS skills installed to $(echo $TARGETS | wc -w | tr -d ' ') locations."
    echo "Restart your AI assistant to pick up the new skills."
}

do_update() {
    if [ ! -d "$CACHE_DIR/.git" ]; then
        echo "No existing installation found. Running install instead."
        do_install
        return
    fi

    echo "Updating Synthesis Skills..."
    git -C "$CACHE_DIR" pull --quiet
    do_install
}

do_uninstall() {
    echo "Uninstalling Synthesis Skills..."

    if [ ! -d "$CACHE_DIR/.git" ]; then
        echo "No cached repo found. Scanning for installed skills..."
    fi

    TARGETS=$(detect_targets)
    REMOVED=0

    # Get our skill names from cache (or scan known names)
    if [ -d "$CACHE_DIR/.git" ]; then
        SKILL_NAMES=$(our_skill_names)
    else
        # Fallback: list of known synthesis-skills names
        SKILL_NAMES="synthesis-ai-content-quality synthesis-anti-watermarking synthesis-blog-promotion synthesis-blog-revitalization synthesis-code-generation synthesis-codebase-review synthesis-content-framing synthesis-content-promotion synthesis-context-lifecycle synthesis-creative-writer-setup synthesis-fact-checking synthesis-hyperlink-research synthesis-llm-project-setup synthesis-message-condensation synthesis-multi-contributor-coding synthesis-pr-review synthesis-project-management synthesis-response-merging synthesis-social-media-post synthesis-technical-advisor-setup synthesis-thought-leadership-writing synthesis-tree-of-thought"
    fi

    for target in $TARGETS; do
        for skill_name in $SKILL_NAMES; do
            if [ -d "${target}/${skill_name}" ]; then
                rm -rf "${target}/${skill_name}"
                REMOVED=$((REMOVED + 1))
            fi
        done
    done

    rm -rf "$CACHE_DIR"
    echo "Done. Removed $REMOVED skill installations."
}

# Default to install when piped (curl | sh)
COMMAND="${1:-install}"

case "$COMMAND" in
    install)  do_install ;;
    update)   do_update ;;
    uninstall) do_uninstall ;;
    *)
        echo "Usage: $0 {install|update|uninstall}"
        echo ""
        echo "  install    Install all Synthesis Skills"
        echo "  update     Update to latest version"
        echo "  uninstall  Remove all installed skills"
        exit 1
        ;;
esac
