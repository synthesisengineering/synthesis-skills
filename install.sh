#!/bin/sh
# Synthesis Skills installer — no Node.js required
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/install.sh | sh
#   ./install.sh install    # Install all skills
#   ./install.sh update     # Update to latest
#   ./install.sh uninstall  # Remove all installed skills
#   ./install.sh status     # Show installed skills and drift status

set -e

REPO_URL="https://github.com/synthesisengineering/synthesis-skills.git"
REPO_NAME="synthesis-skills"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/synthesis-skills"
# Backups live BESIDE the cache, not inside it: the cache dir is deleted on
# reclone and on uninstall, and backups must survive both.
BACKUP_ROOT="${CACHE_DIR}-backups"
BACKUP_KEEP_RUNS=10
SOURCE_REPO="github.com/synthesisengineering/synthesis-skills"
SOURCE_TYPE="public"

# Skill directories to install to (auto-detected)
detect_targets() {
    TARGETS=""
    # Claude Code
    TARGETS="$TARGETS $HOME/.claude/skills"
    # OpenAI Codex
    TARGETS="$TARGETS $HOME/.codex/skills"
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

# Checksum tooling (portable across macOS and Linux).
# Word-split on use is intentional; do not quote $CHECKSUM_TOOL.
if command -v shasum >/dev/null 2>&1; then
    CHECKSUM_TOOL="shasum -a 256"
elif command -v sha256sum >/dev/null 2>&1; then
    CHECKSUM_TOOL="sha256sum"
else
    # Fallback: cksum is POSIX
    CHECKSUM_TOOL="cksum"
fi

checksum_stdin() {
    $CHECKSUM_TOOL | cut -d' ' -f1
}

# Checksum of an entire skill directory: every file except installer-written
# provenance (.source.json) and Finder noise (.DS_Store), keyed by relative
# path so an installed copy and its source dir compare equal. Whole-directory
# coverage matters: drift in scripts/, references/, or data tables
# (e.g. tiers.yaml) must be detected, not just drift in SKILL.md.
skill_dir_checksum() {
    (cd "$1" 2>/dev/null || exit 0
     find . -type f ! -name '.source.json' ! -name '.DS_Store' -print0 \
        | LC_ALL=C sort -z \
        | xargs -0 $CHECKSUM_TOOL 2>/dev/null) | checksum_stdin
}

# Drop backup runs beyond the newest BACKUP_KEEP_RUNS. Run-stamp dirs are
# UTC timestamps, so lexicographic order is chronological order.
prune_backups() {
    [ -d "$BACKUP_ROOT" ] || return 0
    total=$(ls -1 "$BACKUP_ROOT" 2>/dev/null | wc -l | tr -d ' ')
    [ "$total" -gt "$BACKUP_KEEP_RUNS" ] || return 0
    ls -1 "$BACKUP_ROOT" | LC_ALL=C sort | head -n $((total - BACKUP_KEEP_RUNS)) \
        | while IFS= read -r old_run; do
            rm -rf "${BACKUP_ROOT:?}/${old_run}"
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

    COMMIT=$(get_source_commit)
    TARGETS=$(detect_targets)
    SKILL_COUNT=0
    DRIFT_COUNT=0
    DRIFT_NAMES=""
    RUN_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    BACKUP_DIR="${BACKUP_ROOT}/${RUN_STAMP}"

    for target in $TARGETS; do
        mkdir -p "$target"
        for skill_dir in $(list_skills "$CACHE_DIR"); do
            skill_name=$(basename "$skill_dir")
            # Skip non-skill directories
            case "$skill_name" in
                .git|node_modules|.github) continue ;;
            esac

            installed_dir="${target}/${skill_name}"

            # Check for drift before overwriting. Any existing directory that
            # differs from source — whatever the reason: a local edit, an
            # installed copy older than source, or a same-name directory this
            # installer never wrote — is backed up before it is replaced.
            if [ -d "$installed_dir" ]; then
                installed_sum=$(skill_dir_checksum "$installed_dir")
                source_sum=$(skill_dir_checksum "$skill_dir")
                if [ "$installed_sum" != "$source_sum" ]; then
                    target_tag=$(printf '%s' "$target" | sed "s|^${HOME}/||; s|^\.||; s|/|-|g")
                    mkdir -p "${BACKUP_DIR}/${target_tag}"
                    cp -R "$installed_dir" "${BACKUP_DIR}/${target_tag}/${skill_name}"
                    DRIFT_COUNT=$((DRIFT_COUNT + 1))
                    DRIFT_NAMES="$DRIFT_NAMES $skill_name"
                    if [ -f "${installed_dir}/.source.json" ]; then
                        echo "  DRIFT: ${skill_name} in ${target} — installed copy differs from source"
                    else
                        echo "  DRIFT: ${skill_name} in ${target} — same-name directory without install provenance differs from source"
                    fi
                    echo "         pre-overwrite copy saved: ${BACKUP_DIR}/${target_tag}/${skill_name}"
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
        # Word-split $DRIFT_NAMES on purpose: one name per list entry.
        DRIFTED_SKILLS=$(printf '%s\n' $DRIFT_NAMES | LC_ALL=C sort -u)
        DRIFTED_SKILL_COUNT=$(printf '%s\n' "$DRIFTED_SKILLS" | grep -c .)
        echo "WARNING: $DRIFTED_SKILL_COUNT skill(s) differed from source and were overwritten ($DRIFT_COUNT installed copies):"
        printf '%s\n' "$DRIFTED_SKILLS" | sed 's/^/  - /'
        echo "  Pre-overwrite copies saved under: $BACKUP_DIR"
        echo "  A difference can be a local edit or an installed copy older than source."
        echo "  Use './install.sh status' before install/update to review drift first."
    fi
    prune_backups
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
    awk '
        /^---$/ {
            frontmatter_count++
            if (frontmatter_count == 2) exit
            next
        }
        frontmatter_count == 1 {
            if ($0 ~ /^depends_on:[[:space:]]*\[/) {
                line = $0
                sub(/^depends_on:[[:space:]]*/, "", line)
                gsub(/[\[\]"[:space:]]/, "", line)
                count = split(line, deps, ",")
                for (i = 1; i <= count; i++) {
                    if (deps[i] != "") print deps[i]
                }
                exit
            }
            if ($0 ~ /^depends_on:[[:space:]]*$/) {
                in_depends = 1
                next
            }
            if (in_depends) {
                if ($0 ~ /^[[:space:]]*-/) {
                    line = $0
                    sub(/^[[:space:]]*-[[:space:]]*/, "", line)
                    gsub(/["[:space:]]/, "", line)
                    if (line != "") print line
                    next
                }
                if ($0 !~ /^[[:space:]]/) exit
            }
        }
    ' "$skill_md"
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

            installed_sum=$(skill_dir_checksum "$installed_dir")
            source_sum=$(skill_dir_checksum "$skill_dir")
            if [ "$installed_sum" != "$source_sum" ]; then
                echo "  DRIFT:   $skill_name"
                DRIFTED=$((DRIFTED + 1))
            else
                echo "  OK:      $skill_name"
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
        SKILL_NAMES="synthesis-article-writing synthesis-blog-refresh synthesis-clean-text synthesis-code-audit synthesis-code-integration synthesis-code-planning synthesis-codebase-review synthesis-concise-messaging synthesis-content-distribution synthesis-content-framing synthesis-content-quality synthesis-context-lifecycle synthesis-creative-writer synthesis-fact-checking synthesis-implementation-integrity synthesis-link-research synthesis-llm-setup synthesis-mac-sync synthesis-preflight synthesis-pr-review synthesis-project-management synthesis-response-merger synthesis-review-triage synthesis-skills-manager synthesis-slack-sync synthesis-technical-advisor synthesis-thinking-framework synthesis-tree-of-thought synthesis-voice-profiler"
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
