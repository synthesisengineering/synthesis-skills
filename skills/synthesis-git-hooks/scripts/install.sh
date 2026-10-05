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
CONFORMANCE_SOURCE="$SKILLS_DIR/synthesis-agent-conformance/scripts"

TARGET_DIR="$HOME/.synthesis/git-hooks"
TARGET_REFERENCES="$HOME/.synthesis/references"
CONFIG_PATH="$HOME/.synthesis/git-hook-config.yaml"

for source in \
    "$COORDINATION_SOURCE/coordination.py" \
    "$COORDINATION_SOURCE/claim_scope.py" \
    "$COORDINATION_SOURCE/native_git.py" \
    "$COORDINATION_SOURCE/coordination_schema.py" \
    "$COORDINATION_SOURCE/board_grammar.py" \
    "$COORDINATION_SOURCE/team_contract.py" \
    "$COORDINATION_SOURCE/native_identity.py" \
    "$COORDINATION_SOURCE/coordination_archive.py" \
    "$COORDINATION_SOURCE/pointer_lock.py" \
    "$COORDINATION_SOURCE/peer_addressing.py" \
    "$COORDINATION_SOURCE/fleet_identity.py" \
    "$COORDINATION_SOURCE/fleet_paths.py" \
    "$COORDINATION_SOURCE/fleet_bootstrap.py" \
    "$COORDINATION_SOURCE/fleet_doctor.py" \
    "$COORDINATION_SOURCE/fleet_handoff.py" \
    "$COORDINATION_SOURCE/fleet_logical.py" \
    "$COORDINATION_SOURCE/fleet_subscriptions.py" \
    "$COORDINATION_SOURCE/coordination_process.py" \
    "$COORDINATION_SOURCE/coordination_lock.py" \
    "$COORDINATION_SOURCE/project_recipient.py" \
    "$CONFORMANCE_SOURCE/native_transcript_identity.py" \
    "$CONFORMANCE_SOURCE/client_binaries.py" \
    "$SKILLS_DIR/synthesis-project-management/scripts/run_admission.py" \
    "$SKILLS_DIR/synthesis-project-management/scripts/project_state.py" \
    "$SKILLS_DIR/synthesis-project-management/scripts/plan_reference.py" \
    "$SKILLS_DIR/synthesis-context-lifecycle/scripts/context_currency.py" \
    "$SKILLS_DIR/synthesis-context-lifecycle/scripts/context_edit.py" \
    "$SKILLS_DIR/synthesis-context-lifecycle/scripts/record_succession.py" \
    "$SKILLS_DIR/synthesis-context-lifecycle/scripts/record_transaction.py" \
    "$SKILLS_DIR/synthesis-decision-packet/scripts/build_packet.py" \
    "$SKILLS_DIR/synthesis-decision-packet/scripts/record_rulings.py" \
    "$SKILLS_DIR/synthesis-onboarding/scripts/release_runtime.py" \
    "$SKILLS_DIR/synthesis-repo-guard/publication_receipt.py" \
    "$SKILLS_DIR/synthesis-repo-guard/pending_manifest.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/scripts/yaml_runtime.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/__init__.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/composer.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/constructor.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/cyaml.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/dumper.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/emitter.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/error.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/events.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/loader.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/nodes.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/parser.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/reader.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/representer.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/resolver.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/scanner.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/serializer.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/tokens.py" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/manifest.json" \
    "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/LICENSE" \
    "$SKILLS_DIR/synthesis-daily-rituals/scripts/repo_state.py" \
    "$SKILLS_DIR/synthesis-daily-rituals/scripts/ritual_workers.py" \
    "$SKILLS_DIR/synthesis-daily-rituals/scripts/credential_paths.py" \
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
cp -f "$SCRIPT_DIR/pre-merge-commit" "$TARGET_DIR/pre-merge-commit"
cp -f "$SCRIPT_DIR/commit-msg" "$TARGET_DIR/commit-msg"
# The scanner reuses this grammar from captured source, without pyc execution.
cp -f "$SCRIPT_DIR/_load_config.py" "$TARGET_DIR/_load_config.py"
cp -f "$SCRIPT_DIR/_scan_staged.py" "$TARGET_DIR/_scan_staged.py"
cp -f "$COORDINATION_SOURCE/coordination.py" "$TARGET_DIR/coordination.py"
cp -f "$COORDINATION_SOURCE/claim_scope.py" "$TARGET_DIR/claim_scope.py"
cp -f "$COORDINATION_SOURCE/native_git.py" "$TARGET_DIR/native_git.py"
cp -f "$COORDINATION_SOURCE/coordination_schema.py" "$TARGET_DIR/coordination_schema.py"
cp -f "$COORDINATION_SOURCE/board_grammar.py" "$TARGET_DIR/board_grammar.py"
cp -f "$COORDINATION_SOURCE/team_contract.py" "$TARGET_DIR/team_contract.py"
cp -f "$COORDINATION_SOURCE/native_identity.py" "$TARGET_DIR/native_identity.py"
cp -f "$COORDINATION_SOURCE/coordination_archive.py" "$TARGET_DIR/coordination_archive.py"
cp -f "$COORDINATION_SOURCE/pointer_lock.py" "$TARGET_DIR/pointer_lock.py"
cp -f "$COORDINATION_SOURCE/peer_addressing.py" "$TARGET_DIR/peer_addressing.py"
cp -f "$COORDINATION_SOURCE/fleet_identity.py" "$TARGET_DIR/fleet_identity.py"
cp -f "$COORDINATION_SOURCE/fleet_paths.py" "$TARGET_DIR/fleet_paths.py"
cp -f "$COORDINATION_SOURCE/fleet_bootstrap.py" "$TARGET_DIR/fleet_bootstrap.py"
cp -f "$COORDINATION_SOURCE/fleet_doctor.py" "$TARGET_DIR/fleet_doctor.py"
cp -f "$COORDINATION_SOURCE/fleet_handoff.py" "$TARGET_DIR/fleet_handoff.py"
cp -f "$COORDINATION_SOURCE/fleet_logical.py" "$TARGET_DIR/fleet_logical.py"
cp -f "$COORDINATION_SOURCE/fleet_subscriptions.py" "$TARGET_DIR/fleet_subscriptions.py"
cp -f "$COORDINATION_SOURCE/coordination_process.py" "$TARGET_DIR/coordination_process.py"
cp -f "$COORDINATION_SOURCE/coordination_lock.py" "$TARGET_DIR/coordination_lock.py"
cp -f "$COORDINATION_SOURCE/project_recipient.py" "$TARGET_DIR/project_recipient.py"
cp -f "$CONFORMANCE_SOURCE/native_transcript_identity.py" "$TARGET_DIR/native_transcript_identity.py"
cp -f "$CONFORMANCE_SOURCE/client_binaries.py" "$TARGET_DIR/client_binaries.py"
# Registry transactions use the complete release-owned cross-skill closure.
mkdir -p "$TARGET_DIR/yaml"
cp -f "$SKILLS_DIR/synthesis-project-management/scripts/run_admission.py" "$HOME/.synthesis/git-hooks/run_admission.py"
chmod 755 "$HOME/.synthesis/git-hooks/run_admission.py"
cp -f "$SKILLS_DIR/synthesis-project-management/scripts/project_state.py" "$HOME/.synthesis/git-hooks/project_state.py"
chmod 755 "$HOME/.synthesis/git-hooks/project_state.py"
cp -f "$SKILLS_DIR/synthesis-project-management/scripts/plan_reference.py" "$HOME/.synthesis/git-hooks/plan_reference.py"
chmod 755 "$HOME/.synthesis/git-hooks/plan_reference.py"
cp -f "$SKILLS_DIR/synthesis-context-lifecycle/scripts/context_currency.py" "$HOME/.synthesis/git-hooks/context_currency.py"
chmod 755 "$HOME/.synthesis/git-hooks/context_currency.py"
cp -f "$SKILLS_DIR/synthesis-context-lifecycle/scripts/context_edit.py" "$HOME/.synthesis/git-hooks/context_edit.py"
chmod 755 "$HOME/.synthesis/git-hooks/context_edit.py"
cp -f "$SKILLS_DIR/synthesis-context-lifecycle/scripts/record_succession.py" "$HOME/.synthesis/git-hooks/record_succession.py"
chmod 755 "$HOME/.synthesis/git-hooks/record_succession.py"
cp -f "$SKILLS_DIR/synthesis-context-lifecycle/scripts/record_transaction.py" "$HOME/.synthesis/git-hooks/record_transaction.py"
chmod 755 "$HOME/.synthesis/git-hooks/record_transaction.py"
cp -f "$SKILLS_DIR/synthesis-decision-packet/scripts/build_packet.py" "$HOME/.synthesis/git-hooks/build_packet.py"
chmod 755 "$HOME/.synthesis/git-hooks/build_packet.py"
cp -f "$SKILLS_DIR/synthesis-decision-packet/scripts/record_rulings.py" "$HOME/.synthesis/git-hooks/record_rulings.py"
chmod 755 "$HOME/.synthesis/git-hooks/record_rulings.py"
cp -f "$SKILLS_DIR/synthesis-onboarding/scripts/release_runtime.py" "$HOME/.synthesis/git-hooks/release_runtime.py"
chmod 755 "$HOME/.synthesis/git-hooks/release_runtime.py"
cp -f "$SKILLS_DIR/synthesis-repo-guard/publication_receipt.py" "$HOME/.synthesis/git-hooks/publication_receipt.py"
chmod 755 "$HOME/.synthesis/git-hooks/publication_receipt.py"
cp -f "$SKILLS_DIR/synthesis-repo-guard/pending_manifest.py" "$HOME/.synthesis/git-hooks/pending_manifest.py"
chmod 755 "$HOME/.synthesis/git-hooks/pending_manifest.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/scripts/yaml_runtime.py" "$HOME/.synthesis/git-hooks/yaml_runtime.py"
chmod 755 "$HOME/.synthesis/git-hooks/yaml_runtime.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/__init__.py" "$HOME/.synthesis/git-hooks/yaml/__init__.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/__init__.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/composer.py" "$HOME/.synthesis/git-hooks/yaml/composer.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/composer.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/constructor.py" "$HOME/.synthesis/git-hooks/yaml/constructor.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/constructor.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/cyaml.py" "$HOME/.synthesis/git-hooks/yaml/cyaml.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/cyaml.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/dumper.py" "$HOME/.synthesis/git-hooks/yaml/dumper.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/dumper.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/emitter.py" "$HOME/.synthesis/git-hooks/yaml/emitter.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/emitter.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/error.py" "$HOME/.synthesis/git-hooks/yaml/error.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/error.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/events.py" "$HOME/.synthesis/git-hooks/yaml/events.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/events.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/loader.py" "$HOME/.synthesis/git-hooks/yaml/loader.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/loader.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/nodes.py" "$HOME/.synthesis/git-hooks/yaml/nodes.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/nodes.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/parser.py" "$HOME/.synthesis/git-hooks/yaml/parser.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/parser.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/reader.py" "$HOME/.synthesis/git-hooks/yaml/reader.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/reader.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/representer.py" "$HOME/.synthesis/git-hooks/yaml/representer.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/representer.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/resolver.py" "$HOME/.synthesis/git-hooks/yaml/resolver.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/resolver.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/scanner.py" "$HOME/.synthesis/git-hooks/yaml/scanner.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/scanner.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/serializer.py" "$HOME/.synthesis/git-hooks/yaml/serializer.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/serializer.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/yaml/tokens.py" "$HOME/.synthesis/git-hooks/yaml/tokens.py"
chmod 644 "$HOME/.synthesis/git-hooks/yaml/tokens.py"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/manifest.json" "$HOME/.synthesis/references/pyyaml-manifest.json"
chmod 644 "$HOME/.synthesis/references/pyyaml-manifest.json"
cp -f "$SKILLS_DIR/synthesis-agent-conformance/vendor/pyyaml/LICENSE" "$HOME/.synthesis/references/pyyaml-LICENSE"
chmod 644 "$HOME/.synthesis/references/pyyaml-LICENSE"
cp -f "$SKILLS_DIR/synthesis-daily-rituals/scripts/repo_state.py" "$TARGET_DIR/repo_state.py"
chmod 755 "$TARGET_DIR/repo_state.py"
cp -f "$SKILLS_DIR/synthesis-daily-rituals/scripts/ritual_workers.py" "$TARGET_DIR/ritual_workers.py"
chmod 755 "$TARGET_DIR/ritual_workers.py"
cp -f "$SKILLS_DIR/synthesis-daily-rituals/scripts/credential_paths.py" "$TARGET_DIR/credential_paths.py"
chmod 755 "$TARGET_DIR/credential_paths.py"
printf '%s\n' "$SCRIPT_DIR" > "$TARGET_DIR/source-path"
cp -f "$COORDINATION_REFERENCES/session-words-v1.txt.zlib.b85" \
    "$TARGET_REFERENCES/session-words-v1.txt.zlib.b85"
# Source generations are read-only; installed runtime modes are independent.
chmod 755 \
    "$TARGET_DIR/pre-commit" \
    "$TARGET_DIR/pre-merge-commit" \
    "$TARGET_DIR/commit-msg" \
    "$TARGET_DIR/_load_config.py" \
    "$TARGET_DIR/_scan_staged.py" \
    "$TARGET_DIR/coordination.py" \
    "$TARGET_DIR/claim_scope.py" \
    "$TARGET_DIR/native_git.py" \
    "$TARGET_DIR/coordination_schema.py" \
    "$TARGET_DIR/board_grammar.py" \
    "$TARGET_DIR/team_contract.py" \
    "$TARGET_DIR/native_identity.py" \
    "$TARGET_DIR/coordination_archive.py" \
    "$TARGET_DIR/pointer_lock.py" \
    "$TARGET_DIR/peer_addressing.py" \
    "$TARGET_DIR/fleet_identity.py" \
    "$TARGET_DIR/fleet_paths.py" \
    "$TARGET_DIR/fleet_bootstrap.py" \
    "$TARGET_DIR/fleet_doctor.py" \
    "$TARGET_DIR/fleet_handoff.py" \
    "$TARGET_DIR/fleet_logical.py" \
    "$TARGET_DIR/fleet_subscriptions.py" \
    "$TARGET_DIR/coordination_process.py" \
    "$TARGET_DIR/coordination_lock.py" \
    "$TARGET_DIR/project_recipient.py" \
    "$TARGET_DIR/native_transcript_identity.py" \
    "$TARGET_DIR/client_binaries.py"
chmod 644 "$TARGET_DIR/source-path" "$TARGET_REFERENCES/session-words-v1.txt.zlib.b85"

if [ -f "$CONFIG_PATH" ]; then
    echo "→ Config already exists at $CONFIG_PATH — not overwriting."
    echo "  (Edit it manually; the template is at $SCRIPT_DIR/git-hook-config.example.yaml.)"
else
    echo "→ Seeding initial config at $CONFIG_PATH from template"
    cp "$SCRIPT_DIR/git-hook-config.example.yaml" "$CONFIG_PATH"
    chmod 644 "$CONFIG_PATH"
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

# The sidecar is stdlib-only; registry transaction readers carry their verified
# release-owned pure Python YAML package in this installed runtime.
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
