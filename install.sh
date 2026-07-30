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
USER_HOME="${SYNTHESIS_SKILLS_HOME:-$HOME}"
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd || true)
SCRIPT_SKILLS_DIR="${SCRIPT_DIR}/skills"
SOURCE_MODE="remote"
if [ -n "${SYNTHESIS_SKILLS_SOURCE_DIR:-}" ]; then
    CACHE_DIR=$(cd "$SYNTHESIS_SKILLS_SOURCE_DIR" && pwd)
    SOURCE_MODE="local"
else
    CACHE_DIR="${XDG_CACHE_HOME:-$USER_HOME/.cache}/synthesis-skills"
fi
# Backups live BESIDE the cache, not inside it: the cache dir is deleted on
# reclone and on uninstall, and backups must survive both.
BACKUP_ROOT="${XDG_CACHE_HOME:-$USER_HOME/.cache}/synthesis-skills-backups"
BACKUP_KEEP_RUNS=10
SOURCE_REPO="github.com/synthesisengineering/synthesis-skills"
SOURCE_TYPE="public"
SKILLS_DIR="${CACHE_DIR}/skills"

# Skill directories to install to (auto-detected)
detect_targets() {
    if [ -n "${SYNTHESIS_SKILLS_TARGETS:-}" ]; then
        echo "$SYNTHESIS_SKILLS_TARGETS"
        return
    fi

    TARGETS=""
    # Prefer each client's native plugin package. Direct user-skill copies are
    # the fallback for clients where the plugin is not installed.
    if ! claude_plugin_installed; then
        TARGETS="$TARGETS $USER_HOME/.claude/skills"
    fi
    if ! codex_plugin_installed; then
        TARGETS="$TARGETS $USER_HOME/.agents/skills"
    fi
    # Cursor
    if [ -d "$USER_HOME/.cursor" ]; then
        TARGETS="$TARGETS $USER_HOME/.cursor/skills"
    fi
    echo "$TARGETS"
}

# Each client's own shell puts its CLI on PATH, but other shells (the other
# client, cron, CI) usually do not — the Codex CLI ships inside the ChatGPT
# desktop app on macOS. Resolve through an explicit override first (a set but
# empty override means "treat as absent"), then PATH, then documented stable
# install locations, so plugin detection gives the same answer from every
# shell instead of silently reverting to direct-copy installs.
resolve_claude_bin() {
    if [ "${SYNTHESIS_CLAUDE_BIN+set}" = "set" ]; then
        if [ -n "$SYNTHESIS_CLAUDE_BIN" ] && [ -x "$SYNTHESIS_CLAUDE_BIN" ]; then
            printf '%s\n' "$SYNTHESIS_CLAUDE_BIN"
        fi
        return 0
    fi
    if command -v claude >/dev/null 2>&1; then
        command -v claude
        return 0
    fi
    for CLIENT_BIN_CANDIDATE in \
        "$HOME/.local/bin/claude" \
        /opt/homebrew/bin/claude \
        /usr/local/bin/claude; do
        if [ -x "$CLIENT_BIN_CANDIDATE" ]; then
            printf '%s\n' "$CLIENT_BIN_CANDIDATE"
            return 0
        fi
    done
    return 0
}

resolve_codex_bin() {
    if [ "${SYNTHESIS_CODEX_BIN+set}" = "set" ]; then
        if [ -n "$SYNTHESIS_CODEX_BIN" ] && [ -x "$SYNTHESIS_CODEX_BIN" ]; then
            printf '%s\n' "$SYNTHESIS_CODEX_BIN"
        fi
        return 0
    fi
    if command -v codex >/dev/null 2>&1; then
        command -v codex
        return 0
    fi
    for CLIENT_BIN_CANDIDATE in \
        "$HOME/.local/bin/codex" \
        /opt/homebrew/bin/codex \
        /usr/local/bin/codex \
        "/Applications/ChatGPT.app/Contents/Resources/codex"; do
        if [ -x "$CLIENT_BIN_CANDIDATE" ]; then
            printf '%s\n' "$CLIENT_BIN_CANDIDATE"
            return 0
        fi
    done
    return 0
}

claude_plugin_installed() {
    CLAUDE_CLIENT_BIN=$(resolve_claude_bin)
    [ -n "$CLAUDE_CLIENT_BIN" ] || return 1
    "$CLAUDE_CLIENT_BIN" plugin list --json 2>/dev/null |
        tr '\n' ' ' |
        grep -Eq '\{[^{}]*"id"[[:space:]]*:[[:space:]]*"synthesis-skills@[^"]*"[^{}]*"enabled"[[:space:]]*:[[:space:]]*true'
}

codex_plugin_installed() {
    CODEX_CLIENT_BIN=$(resolve_codex_bin)
    [ -n "$CODEX_CLIENT_BIN" ] || return 1
    "$CODEX_CLIENT_BIN" plugin list --json 2>/dev/null |
        tr '\n' ' ' |
        grep -Eq '\{[^{}]*"name"[[:space:]]*:[[:space:]]*"synthesis-skills"[^{}]*"enabled"[[:space:]]*:[[:space:]]*true'
}

retirement_target_allowed() {
    case "$1" in
        "$USER_HOME/.claude/skills"|"$USER_HOME/.agents/skills"|"$USER_HOME/.codex/skills")
            return 0
            ;;
        *)
            echo "ERROR: refusing unexpected direct-copy retirement target: $1" >&2
            return 1
            ;;
    esac
}

retire_direct_copies() {
    RETIRE_TARGET="$1"
    retirement_target_allowed "$RETIRE_TARGET"
    [ -e "$RETIRE_TARGET" ] || return 0
    if [ -L "$RETIRE_TARGET" ]; then
        echo "ERROR: refusing symlinked direct-copy retirement target: $RETIRE_TARGET" >&2
        return 1
    fi

    RETIRE_TAG=$(printf '%s' "$RETIRE_TARGET" |
        sed "s|^${USER_HOME}/||; s|^\.||; s|/|-|g")
    for RETIRE_SOURCE in $(list_skills "$SKILLS_DIR"); do
        RETIRE_NAME=$(basename "$RETIRE_SOURCE")
        RETIRE_INSTALLED="${RETIRE_TARGET}/${RETIRE_NAME}"
        [ -d "$RETIRE_INSTALLED" ] || continue
        if [ -L "$RETIRE_INSTALLED" ]; then
            echo "ERROR: refusing symlinked direct skill copy: $RETIRE_INSTALLED" >&2
            return 1
        fi

        RETIRE_BACKUP="${BACKUP_DIR}/retired-${RETIRE_TAG}/${RETIRE_NAME}"
        mkdir -p "$(dirname "$RETIRE_BACKUP")"
        cp -R "$RETIRE_INSTALLED" "$RETIRE_BACKUP"
        if [ "$(skill_dir_checksum "$RETIRE_INSTALLED")" != \
             "$(skill_dir_checksum "$RETIRE_BACKUP")" ]; then
            echo "ERROR: direct-copy retirement backup verification failed: $RETIRE_INSTALLED" >&2
            return 1
        fi
        rm -rf "${RETIRE_INSTALLED:?}"
        RETIRED_COUNT=$((RETIRED_COUNT + 1))
    done
}

retire_plugin_fallbacks() {
    if claude_plugin_installed; then
        retire_direct_copies "$USER_HOME/.claude/skills"
    fi
    if codex_plugin_installed; then
        retire_direct_copies "$USER_HOME/.agents/skills"
        retire_direct_copies "$USER_HOME/.codex/skills"
    fi
}

# List skill directories (directories containing SKILL.md)
list_skills() {
    find "$1" -maxdepth 2 -name "SKILL.md" -exec dirname {} \; | sort
}

# Get list of our skill names from the repo
our_skill_names() {
    list_skills "$SKILLS_DIR" | while read -r dir; do
        basename "$dir"
    done
}

# Get current git commit hash from cache
git_source_available() {
    git -C "$CACHE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

get_source_commit() {
    if git_source_available; then
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
  "source_path": "skills/${skill_name}/SKILL.md",
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
    if [ "$SOURCE_MODE" = "local" ]; then
        echo "Using local source: $CACHE_DIR"
    elif git_source_available; then
        echo "Updating cached repo..."
        git -C "$CACHE_DIR" pull --quiet
    else
        echo "Cloning repository..."
        rm -rf "$CACHE_DIR"
        git clone --quiet "$REPO_URL" "$CACHE_DIR"
    fi

    COMMIT=$(get_source_commit)
    RUN_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
    BACKUP_DIR="${BACKUP_ROOT}/${RUN_STAMP}"
    RETIRED_COUNT=0
    retire_plugin_fallbacks
    TARGETS=$(detect_targets)
    SKILL_COUNT=0
    DRIFT_COUNT=0
    DRIFT_NAMES=""

    for target in $TARGETS; do
        mkdir -p "$target"
        for skill_dir in $(list_skills "$SKILLS_DIR"); do
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
                    target_tag=$(printf '%s' "$target" | sed "s|^${USER_HOME}/||; s|^\.||; s|/|-|g")
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
    if [ "$RETIRED_COUNT" -gt 0 ]; then
        echo "Retired $RETIRED_COUNT direct plugin-fallback copies after verified backups:"
        echo "  $BACKUP_DIR"
    fi
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

    for skill_dir in $(list_skills "$SKILLS_DIR"); do
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
        return 1
    fi
}

do_update() {
    if [ "$SOURCE_MODE" = "local" ]; then
        do_install
        return
    fi
    if ! git_source_available; then
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

    CLAUDE_PLUGIN="not installed or disabled"
    CODEX_PLUGIN="not installed or disabled"
    if claude_plugin_installed; then
        CLAUDE_PLUGIN="installed and enabled"
    fi
    if codex_plugin_installed; then
        CODEX_PLUGIN="installed and enabled"
    fi
    echo "Claude Code plugin: $CLAUDE_PLUGIN"
    echo "Codex plugin:       $CODEX_PLUGIN"
    echo ""

    # Resolve the authoritative source tree. A checked-out repository or
    # installed native plugin is self-contained and must not depend on a
    # separate legacy cache. Only a standalone downloaded script uses cache.
    STATUS_SKILLS_DIR=""
    if [ "$SOURCE_MODE" = "local" ]; then
        STATUS_SKILLS_DIR="$SKILLS_DIR"
    elif [ -d "$SCRIPT_SKILLS_DIR" ]; then
        STATUS_SKILLS_DIR="$SCRIPT_SKILLS_DIR"
    elif git_source_available; then
        if ! git -C "$CACHE_DIR" pull --quiet; then
            echo "ERROR: could not refresh cached source: $CACHE_DIR" >&2
            return 1
        fi
        STATUS_SKILLS_DIR="${CACHE_DIR}/skills"
    else
        echo "ERROR: no authoritative skill source is available." >&2
        echo "Run './install.sh install' or execute status from a source checkout or native plugin." >&2
        return 1
    fi
    if [ ! -d "$STATUS_SKILLS_DIR" ]; then
        echo "ERROR: authoritative skill directory is missing: $STATUS_SKILLS_DIR" >&2
        return 1
    fi

    TARGETS=$(detect_targets)
    STATUS_FAILURES=0

    if claude_plugin_installed; then
        for skill_dir in $(list_skills "$STATUS_SKILLS_DIR"); do
            skill_name=$(basename "$skill_dir")
            if [ -d "$USER_HOME/.claude/skills/$skill_name" ]; then
                echo "  DUPLICATE: $USER_HOME/.claude/skills/$skill_name"
                STATUS_FAILURES=$((STATUS_FAILURES + 1))
            fi
        done
    fi
    if codex_plugin_installed; then
        for target in "$USER_HOME/.agents/skills" "$USER_HOME/.codex/skills"; do
            for skill_dir in $(list_skills "$STATUS_SKILLS_DIR"); do
                skill_name=$(basename "$skill_dir")
                if [ -d "$target/$skill_name" ]; then
                    echo "  DUPLICATE: $target/$skill_name"
                    STATUS_FAILURES=$((STATUS_FAILURES + 1))
                fi
            done
        done
    fi
    for target in $TARGETS; do
        if [ ! -d "$target" ]; then
            continue
        fi
        echo "Location: $target"
        echo ""

        INSTALLED=0
        DRIFTED=0
        ORPHANED=0

        for skill_dir in $(list_skills "$STATUS_SKILLS_DIR"); do
            skill_name=$(basename "$skill_dir")
            case "$skill_name" in
                .git|node_modules|.github) continue ;;
            esac

            installed_dir="${target}/${skill_name}"

            if [ ! -d "$installed_dir" ]; then
                echo "  MISSING: $skill_name"
                STATUS_FAILURES=$((STATUS_FAILURES + 1))
                continue
            fi

            INSTALLED=$((INSTALLED + 1))

            installed_sum=$(skill_dir_checksum "$installed_dir")
            source_sum=$(skill_dir_checksum "$skill_dir")
            if [ "$installed_sum" != "$source_sum" ]; then
                echo "  DRIFT:   $skill_name"
                DRIFTED=$((DRIFTED + 1))
                STATUS_FAILURES=$((STATUS_FAILURES + 1))
            else
                echo "  OK:      $skill_name"
            fi
        done

        # Check for skills installed but not in our repo (from other repos)
        if [ -d "$target" ]; then
            for installed_dir in "$target"/synthesis-*; do
                [ -d "$installed_dir" ] || continue
                skill_name=$(basename "$installed_dir")
                if [ ! -d "${STATUS_SKILLS_DIR}/${skill_name}" ]; then
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

    if [ "$STATUS_FAILURES" -gt 0 ]; then
        echo "FAILED: $STATUS_FAILURES missing or drifted installation(s)."
        return 1
    fi
    echo "PASS: all direct-copy targets match source."
}

do_uninstall() {
    echo "Uninstalling Synthesis Skills..."

    TARGETS=$(detect_targets)
    REMOVED=0
    SOURCE_SKILL_NAMES=""

    if git_source_available; then
        SOURCE_SKILL_NAMES=$(our_skill_names)
    else
        echo "No source repository found. Scanning install provenance..."
    fi

    for target in $TARGETS; do
        SKILL_NAMES="$SOURCE_SKILL_NAMES"
        if [ -z "$SKILL_NAMES" ] && [ -d "$target" ]; then
            SKILL_NAMES=$(
                find "$target" -mindepth 2 -maxdepth 2 \
                    -name .source.json -type f |
                while IFS= read -r source_json; do
                    if grep -q \
                        "\"source_repo\": \"${SOURCE_REPO}\"" \
                        "$source_json"; then
                        basename "$(dirname "$source_json")"
                    fi
                done
            )
        fi
        for skill_name in $SKILL_NAMES; do
            if [ -d "${target}/${skill_name}" ]; then
                rm -rf "${target}/${skill_name}"
                REMOVED=$((REMOVED + 1))
            fi
        done
    done

    if [ "$SOURCE_MODE" != "local" ]; then
        rm -rf "$CACHE_DIR"
    fi
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
