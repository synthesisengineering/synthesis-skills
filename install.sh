#!/bin/sh
# Synthesis Skills installer — no Node.js required
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rajivpant/synthesis-skills/main/install.sh | sh
#   ./install.sh install    # Install all skills
#   ./install.sh update     # Update to latest
#   ./install.sh uninstall  # Remove all installed skills
#   ./install.sh status     # Show installed skills and drift status

set -e

REPO_URL="https://github.com/rajivpant/synthesis-skills.git"
REPO_NAME="synthesis-skills"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/synthesis-skills"
SOURCE_REPO="github.com/rajivpant/synthesis-skills"
SOURCE_TYPE="public"

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

# Get current git commit hash from cache
get_source_commit() {
    if [ -d "$CACHE_DIR/.git" ]; then
        git -C "$CACHE_DIR" rev-parse HEAD
    else
        echo "unknown"
    fi
}

# Write .source.json provenance file for an installed skill
write_source_json() {
    skill_target_dir="$1"
    skill_name="$2"
    commit_hash="$3"

    cat > "${skill_target_dir}/.source.json" <<ENDJSON
{
  "source_repo": "${SOURCE_REPO}",
  "source_type": "${SOURCE_TYPE}",
  "source_path": "${skill_name}/SKILL.md",
  "source_commit": "${commit_hash}",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "installed_by": "install.sh"
}
ENDJSON
}

# Compute checksum of SKILL.md content (portable across macOS and Linux)
skill_checksum() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        # Fallback: use cksum
        cksum "$1" | cut -d' ' -f1
    fi
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

    COMMIT=$(get_source_commit)
    TARGETS=$(detect_targets)
    SKILL_COUNT=0
    DRIFT_COUNT=0

    for target in $TARGETS; do
        mkdir -p "$target"
        for skill_dir in $(list_skills "$CACHE_DIR"); do
            skill_name=$(basename "$skill_dir")
            # Skip non-skill directories
            case "$skill_name" in
                .git|node_modules|.github) continue ;;
            esac

            installed_dir="${target}/${skill_name}"

            # Check for drift before overwriting
            if [ -f "${installed_dir}/SKILL.md" ] && [ -f "${skill_dir}/SKILL.md" ]; then
                installed_sum=$(skill_checksum "${installed_dir}/SKILL.md")
                source_sum=$(skill_checksum "${skill_dir}/SKILL.md")
                if [ "$installed_sum" != "$source_sum" ]; then
                    # Check if this was from our repo
                    if [ -f "${installed_dir}/.source.json" ]; then
                        echo "  DRIFT: ${skill_name} — installed copy differs from source"
                        DRIFT_COUNT=$((DRIFT_COUNT + 1))
                    fi
                fi
            fi

            # Remove old version and copy fresh
            rm -rf "${installed_dir}"
            cp -R "$skill_dir" "${installed_dir}"
            # Write provenance
            write_source_json "${installed_dir}" "${skill_name}" "${COMMIT}"
            SKILL_COUNT=$((SKILL_COUNT + 1))
        done
        echo "  Installed to: $target"
    done

    UNIQUE_SKILLS=$(our_skill_names | wc -l | tr -d ' ')
    echo ""
    echo "Done. $UNIQUE_SKILLS skills installed to $(echo $TARGETS | wc -w | tr -d ' ') locations."
    if [ "$DRIFT_COUNT" -gt 0 ]; then
        echo "WARNING: $DRIFT_COUNT skill(s) had local modifications that were overwritten."
        echo "  Use './install.sh status' before install to review drift."
    fi
    echo "Restart your AI assistant to pick up the new skills."

    # Validate dependencies in the first target directory
    FIRST_TARGET=""
    for t in $TARGETS; do
        if [ -d "$t" ]; then
            FIRST_TARGET="$t"
            break
        fi
    done
    if [ -n "$FIRST_TARGET" ]; then
        check_dependencies "$FIRST_TARGET"
    fi
}

# Read depends_on from a SKILL.md frontmatter. Outputs one dependency name per line.
parse_depends_on() {
    skill_md="$1"
    # Extract the depends_on line, strip YAML array syntax, output one name per line
    dep_line=$(grep '^depends_on:' "$skill_md" 2>/dev/null || true)
    if [ -z "$dep_line" ]; then
        return
    fi
    # Remove 'depends_on:', brackets, quotes, spaces — split on commas
    echo "$dep_line" | sed 's/^depends_on: *//; s/\[//; s/\]//; s/"//g; s/ //g' | tr ',' '\n' | grep -v '^$'
}

# Read source_type from an installed skill's .source.json
read_source_type() {
    source_json="$1/.source.json"
    if [ -f "$source_json" ]; then
        grep '"source_type"' "$source_json" | sed 's/.*: *"//; s/".*//'
    else
        echo "unknown"
    fi
}

# Check dependency access hierarchy: public can only depend on public,
# private can depend on public+private, shared can depend on public+shared.
check_hierarchy() {
    my_type="$1"
    dep_type="$2"
    case "$my_type" in
        public)
            [ "$dep_type" = "public" ] && return 0
            return 1
            ;;
        private)
            case "$dep_type" in
                public|private) return 0 ;;
                *) return 1 ;;
            esac
            ;;
        shared)
            case "$dep_type" in
                public|shared) return 0 ;;
                *) return 1 ;;
            esac
            ;;
        *)
            return 0
            ;;
    esac
}

# Validate dependencies for all installed skills from this repo
check_dependencies() {
    target_dir="$1"
    echo ""
    echo "Checking dependencies..."

    WARN_COUNT=0
    VIOLATION_COUNT=0
    CHECKED=0

    for skill_dir in $(list_skills "$CACHE_DIR"); do
        skill_name=$(basename "$skill_dir")
        case "$skill_name" in
            .git|node_modules|.github) continue ;;
        esac

        installed_dir="${target_dir}/${skill_name}"
        [ -f "${installed_dir}/SKILL.md" ] || continue

        deps=$(parse_depends_on "${installed_dir}/SKILL.md")
        [ -z "$deps" ] && continue

        for dep in $deps; do
            CHECKED=$((CHECKED + 1))
            dep_dir="${target_dir}/${dep}"

            if [ ! -d "$dep_dir" ] || [ ! -f "${dep_dir}/SKILL.md" ]; then
                echo "  WARNING: ${skill_name} depends on ${dep} (not installed)"
                WARN_COUNT=$((WARN_COUNT + 1))
            else
                # Dependency is installed — check hierarchy
                dep_source_type=$(read_source_type "$dep_dir")
                if ! check_hierarchy "$SOURCE_TYPE" "$dep_source_type"; then
                    echo "  VIOLATION: ${skill_name} (${SOURCE_TYPE}) depends on ${dep} (${dep_source_type}) — cross-collection dependency not allowed"
                    VIOLATION_COUNT=$((VIOLATION_COUNT + 1))
                fi
            fi
        done
    done

    if [ "$WARN_COUNT" -eq 0 ] && [ "$VIOLATION_COUNT" -eq 0 ]; then
        echo "  All dependencies satisfied."
    else
        if [ "$WARN_COUNT" -gt 0 ]; then
            echo "  $WARN_COUNT missing dependency warning(s)."
        fi
        if [ "$VIOLATION_COUNT" -gt 0 ]; then
            echo "  $VIOLATION_COUNT hierarchy violation(s)."
        fi
    fi
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

do_status() {
    echo "Synthesis Skills Status"
    echo "======================"
    echo ""

    # Update cache if present
    if [ -d "$CACHE_DIR/.git" ]; then
        git -C "$CACHE_DIR" pull --quiet 2>/dev/null || true
    else
        echo "No cached repo. Run './install.sh install' first."
        return
    fi

    TARGETS=$(detect_targets)
    for target in $TARGETS; do
        if [ ! -d "$target" ]; then
            continue
        fi
        echo "Location: $target"
        echo ""

        INSTALLED=0
        DRIFTED=0
        ORPHANED=0

        for skill_dir in $(list_skills "$CACHE_DIR"); do
            skill_name=$(basename "$skill_dir")
            case "$skill_name" in
                .git|node_modules|.github) continue ;;
            esac

            installed_dir="${target}/${skill_name}"

            if [ ! -d "$installed_dir" ]; then
                echo "  MISSING: $skill_name"
                continue
            fi

            INSTALLED=$((INSTALLED + 1))

            if [ -f "${installed_dir}/SKILL.md" ] && [ -f "${skill_dir}/SKILL.md" ]; then
                installed_sum=$(skill_checksum "${installed_dir}/SKILL.md")
                source_sum=$(skill_checksum "${skill_dir}/SKILL.md")
                if [ "$installed_sum" != "$source_sum" ]; then
                    echo "  DRIFT:   $skill_name"
                    DRIFTED=$((DRIFTED + 1))
                else
                    echo "  OK:      $skill_name"
                fi
            fi
        done

        # Check for skills installed but not in our repo (from other repos)
        if [ -d "$target" ]; then
            for installed_dir in "$target"/synthesis-*; do
                [ -d "$installed_dir" ] || continue
                skill_name=$(basename "$installed_dir")
                if [ ! -d "${CACHE_DIR}/${skill_name}" ]; then
                    if [ -f "${installed_dir}/.source.json" ]; then
                        other_repo=$(grep '"source_repo"' "${installed_dir}/.source.json" 2>/dev/null | sed 's/.*: *"//;s/".*//' || echo "unknown")
                        echo "  OTHER:   $skill_name (from $other_repo)"
                    else
                        echo "  OTHER:   $skill_name (no provenance)"
                    fi
                    ORPHANED=$((ORPHANED + 1))
                fi
            done
        fi

        echo ""
        echo "  $INSTALLED installed, $DRIFTED drifted, $ORPHANED from other repos"
        echo ""
    done
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
        SKILL_NAMES="synthesis-article-writing synthesis-blog-refresh synthesis-clean-text synthesis-code-integration synthesis-code-planning synthesis-codebase-review synthesis-concise-messaging synthesis-content-distribution synthesis-content-framing synthesis-content-quality synthesis-context-lifecycle synthesis-creative-writer synthesis-fact-checking synthesis-link-research synthesis-llm-setup synthesis-mac-sync synthesis-pr-review synthesis-project-management synthesis-response-merger synthesis-technical-advisor synthesis-thinking-framework synthesis-tree-of-thought"
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
    install)   do_install ;;
    update)    do_update ;;
    status)    do_status ;;
    uninstall) do_uninstall ;;
    *)
        echo "Usage: $0 {install|update|status|uninstall}"
        echo ""
        echo "  install    Install all Synthesis Skills (writes .source.json provenance)"
        echo "  update     Update to latest version"
        echo "  status     Show installed skills, drift detection, cross-repo inventory"
        echo "  uninstall  Remove all installed skills"
        exit 1
        ;;
esac
