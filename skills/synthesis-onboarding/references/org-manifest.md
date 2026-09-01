# Org Onboarding Manifest — `.agents/onboarding.yaml`

How an organization gives its members a one-command synthesis install.
The org ships **configuration, not installer code**: one manifest in its
knowledge-base repo plus a thin wrapper script. The generic engine
(`synthesis-onboarding/scripts/onboard.py`) does everything else, so every
org inherits idempotence, receipts, migrations, doctor, and welcome behavior
without maintaining an installer.

## Complete example (generic names — substitute your org's)

```yaml
version: 1

org:
  id: exampleco                # short slug, stable
  name: Example Co             # display name for welcome text
  workspace: exampleco         # lands under ~/workspaces/<workspace>/

ecosystem:
  plugin: true                 # install the public synthesis-skills plugin
  clients: [claude, codex]     # attempted only where the client is present
  channel: stable              # stable (default) or edge
  version_pin: "4.74.0"        # optional exact org pin; overrides channel

skills_repos:                  # org shared skills (optional)
  - name: example-shared-skills
    primary: git@github.example.com:exampleco/example-shared-skills.git
    fallbacks:
      - https://github.example.com/exampleco/example-shared-skills.git
    installer: install.sh      # that repo's own installer, relative path
    installer_args: ["$HOME"]  # $HOME expands to the user's home
    source_env: EXAMPLE_SHARED_SKILLS_SOURCE_DIR   # engine pins source to its fresh cache
    status_args: ["status", "$HOME"]               # lets doctor verify installs

knowledge_bases:
  - name: ai-knowledge-exampleco
    primary: git@git.example.com:exampleco/ai-knowledge-exampleco.git
    default_branch: main       # documented branch for fresh clones and guidance
    superseded_remotes:        # old URLs; clones found on these are repointed
      - https://github.example.com/old-owner/ai-knowledge-exampleco.git
    local_hooks: true          # wire repo-local .githooks when no global engine

auth_help: |
  You need SSH access to git.example.com first (the one-time auth step):
    1. Ask #help-desk for repository access to ai-knowledge-exampleco.
    2. Create an SSH key:  ssh-keygen -t ed25519
    3. Add ~/.ssh/id_ed25519.pub to your git account settings.
  Then re-run this installer — it picks up exactly where it left off.

welcome:
  title: Welcome to the Example Co knowledge base
  try_asking:
    - "Who owns the payments platform?"
    - "What is our release process?"
    - "Summarize the current quarter's priorities."
  docs:
    - docs/guides/quickstart.md

migrations:                    # optional; how re-runs clean up history
  skills:
    - from: example-legacy-skill
      action: remove
      note: superseded by the public synthesis-example skill
    - from: example-old-name
      action: rename
      to: example-new-name

workspace_instructions: true   # generate ~/workspaces/<workspace>/AGENTS.md
```

## Field reference

| Key | Required | Meaning |
|-----|----------|---------|
| `version` | yes | Manifest schema version; currently `1`. Unknown keys anywhere are hard errors — the engine fails closed rather than guessing. |
| `org.id`, `org.workspace` | yes | Slug and workspace directory name. `org.name` optional display name. |
| `ecosystem` | no | `plugin` (default true), `clients` list, `channel` (`stable` default or `edge`), and optional exact `version_pin` (`X.Y.Z`). A pin overrides the channel and resolves to the immutable `vX.Y.Z` release tag. |
| `skills_repos[]` | no | `name` + `primary` required. `installer` is invoked as `sh <installer> install <installer_args...>` from the engine's cache clone; `source_env` names the env var your installer honors to skip its own network fetch; `status_args` enables `doctor` verification. |
| `knowledge_bases[]` | no | `name` + `primary` required. `default_branch` documents the branch contributors should use (the remote default remains authoritative when omitted). `superseded_remotes` powers remote migrations (e.g., moving from a personal mirror to the canonical host). `local_hooks` wires `.githooks` on machines without a global hooks engine. |
| `auth_help` | no | Printed verbatim when a repo is unreachable — write it for a non-engineer, with the exact clicks. |
| `welcome` | no | `title`, `try_asking[]`, `docs[]` — shown at the end of a successful run and embedded in the generated workspace AGENTS.md. |
| `migrations.skills[]` | no | `from` + `action` (`remove` or `rename`, `rename` needs `to`), optional `note`. Applied to user-level skill copies; everything is archived before removal. |
| `workspace_instructions` | no | Set `false` to skip generating workspace AGENTS.md/CLAUDE.md. |

## The wrapper script

Put this at your KB repo root as `install.sh` (adjust nothing but the
public-source location if you mirror it):

```sh
#!/bin/sh
# One-command onboarding for this organization's synthesis setup.
set -eu
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC="${SYNTHESIS_ONBOARD_SOURCE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/synthesis-skills}"
if ! command -v git >/dev/null 2>&1; then
  echo "git is required. On macOS run:  xcode-select --install  (then re-run)"; exit 2
fi
if [ -e "$SRC/.git" ]; then
  git -C "$SRC" fetch origin stable && git -C "$SRC" checkout --detach FETCH_HEAD || {
    [ "${SYNTHESIS_ONBOARD_ALLOW_STALE:-}" = "1" ] || {
      echo "Could not refresh $SRC and refusing to run stale."; exit 1; }; }
else
  git clone --branch stable --single-branch https://github.com/synthesisengineering/synthesis-skills.git "$SRC"
fi
CMD="init"
case "${1:-}" in
  init|install|update|kernel|doctor|init-workspace|uninstall) CMD="$1"; shift ;;
esac
exec python3 "$SRC/skills/synthesis-onboarding/scripts/onboard.py" "$CMD" \
  --manifest "$REPO_ROOT/.agents/onboarding.yaml" "$@"
```

A member's whole flow becomes:

```bash
git clone <your-kb-ssh-url> ~/workspaces/<workspace>/<kb-name>   # the auth step lives here
~/workspaces/<workspace>/<kb-name>/install.sh
```

Cloned somewhere else? Fine — the engine adopts existing clones in place by
matching remotes; it never moves anyone's directories.

## YAML subset note

On machines without PyYAML the engine parses a documented subset: nested
maps (2-space indent), lists (`- `), scalars, literal blocks (`|`), and
full-line comments. Everything in the example above is inside the subset.
Anchors, flow style, and multi-line folded scalars are not — the parser
rejects them with a line number rather than misreading them. When PyYAML is
present it is used instead; validation is identical on both paths.

## Renames, removals, and generalization over time

When your org later renames a skill, splits one, or replaces a private
skill with a public synthesis skill, encode it in `migrations` and every
member's next `install.sh` run reconciles their machine — old copies
archived, new names in place, no manual cleanup instructions to broadcast.
