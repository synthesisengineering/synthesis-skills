# Organization manifest — `.agents/onboarding.yaml`

An organization repository extends the public synthesis engine with
declarative data. It contains no installer, shell fragment, hook command, or
arbitrary verifier. The public engine owns every executable capability. In v5 that
engine is onboarding's `setup.py` (`scripts/workspace.py` holds the organization
code). The 2.10.4 guide is in [preserved-org-manifest.md](preserved-org-manifest.md).

## Contents

- Schema 2 example
- Migrating from schema 1
- Checking a manifest
- Field contract
- Enrollment
- Repository behavior
- Instruction provenance

## Schema 2 example

```yaml
version: 2

org:
  id: example-team
  name: Example Team
  workspace: example-team

ecosystem:
  plugin: true
  clients: [claude, codex]
  channel: stable
  version_pin: "4.91.0"

skills_repos:
  - name: example-shared-skills
    repository: ssh://git@example.test/example/example-shared-skills.git
    capability: skills-install

knowledge_bases:
  - name: ai-knowledge-example-team
    repository: ssh://git@example.test/example/ai-knowledge-example-team.git
    default_branch: main
    local_hooks: true

instruction_sources:
  - path: .agents/workspace-instructions.md
    required: true

acceptance:
  task: workspace-grounding-check

auth_help: |
  Sign in to the repository host, confirm that your account can read the
  repositories above, then run the same synthesis command again.

welcome:
  title: Your workspace is ready
  try_asking:
    - "What projects are active?"
    - "Where is the release process documented?"
  docs:
    - docs/getting-started.md
```

## Migrating from schema 1

Setup accepts schema 2 only. A manifest that still declares `version: 1`
or any schema-1 field is refused before anything is mutated, and the refusal
names this section. Organizations that shipped installer logic in schema 1
migrate as follows; every executable capability now belongs to the engine.

| Schema 1 | Schema 2 |
|---|---|
| `version` `1` | `version` `2` |
| `skills_repos[].primary` and `skills_repos[].fallbacks` | one `repository` URL per entry; a fallback host is a second entry only when both are genuine sources |
| `skills_repos[].installer`, `installer_args`, `source_env`, `status_args` | removed; declare `capability` as `skills-install` and the engine copies the tracked skills itself |
| `knowledge_bases[].primary` | `repository` |
| `knowledge_bases[].superseded_remotes` | removed; an existing clone with another remote is refused rather than repointed, so members re-clone or repoint explicitly |
| `workspace_instructions` `true` | `instruction_sources` naming exactly one tracked Markdown file in this repository; the engine materializes `AGENTS.md` and `CLAUDE.md` from it |
| `migrations` (skill renames) | removed; setup copies the repository's current skills and keeps copies someone edited |
| `ecosystem`, `auth_help`, `welcome`, `org` | unchanged |

## Checking a manifest

After editing, validate the manifest from a checkout of the public repository:

```bash
python3 skills/synthesis-onboarding/scripts/workspace.py check /path/to/.agents/onboarding.yaml
```

It prints `valid schema-2 manifest for <org id>` (exit 0) or `invalid: <reason>` (exit 2);
unknown fields and every schema-1 field are invalid.

The organization wrapper scripts that schema 1 required are not needed:
members run setup with the organization's repository URL and the
public engine performs every step.

## Field contract

| Field | Contract |
|---|---|
| `version` | Required integer `2`. Unknown fields fail closed. |
| `org.id` | Required safe identifier. |
| `org.name` | Optional display name used only in local welcome text. |
| `org.workspace` | Required safe directory identifier. |
| `ecosystem.plugin` | Optional Boolean; defaults to true. |
| `ecosystem.clients` | Optional subset of `claude`, `codex` and `muse`; defaults to `claude` and `codex`. |
| `ecosystem.channel` | `stable` by default or explicit `edge`. |
| `ecosystem.version_pin` | Optional exact `X.Y.Z`; overrides the channel. |
| `skills_repos[]` | `name`, safe `repository`, and fixed `capability: skills-install`. Setup performs the copy. |
| `knowledge_bases[]` | `name`, safe `repository`, `default_branch`, and optional `local_hooks` (accepted; in v5 the global commit check already runs each repository's own `.githooks/pre-commit`). |
| `instruction_sources[]` | Exactly one entry with a repository-relative `path` and Boolean `required`. The source must be Git-tracked and regular; traversal and symlinks are rejected. |
| `acceptance.task` | A safe identifier, accepted for compatibility; v5 runs no acceptance task. The organization cannot provide code or arguments. |
| `auth_help` | Plain-text local guidance. It must not contain credentials. |
| `welcome` | Local title, suggested questions, and repository-relative docs. |

Repository URLs must use authenticated HTTPS or SSH transport and must not
embed credentials. Local paths, `file:` URLs, Git's unauthenticated protocol,
and destination escapes are refused.

## Enrollment

A new member's whole installation, using the manifest's clients and release:

```bash
python3 <checkout>/skills/synthesis-onboarding/scripts/setup.py --org-repo ssh://git@example.test/example/onboarding-config.git
```

Add the organization to an existing installation without touching the plugin:

```bash
python3 <checkout>/skills/synthesis-onboarding/scripts/setup.py org --org-repo ssh://git@example.test/example/onboarding-config.git
```

A user may add a private personal instruction layer without putting its path or
repository in this shareable manifest: `--personal-source /path/to/my-instructions.md`.
Setup records it locally (`~/.synthesis/v5/organizations.json`), and a rerun keeps it;
`--personal-source none` removes it. Invites are retired: share the repository URL.
Repository authentication uses the member's normal Git credential path; when a clone
fails, setup prints the manifest's `auth_help` beside that repository, marks it as
needing action, and a rerun picks up where it stopped.

## Repository behavior

Setup clones organization configuration under the XDG data root
(`$XDG_DATA_HOME/synthesis/organizations/`, default `~/.local/share`), in a folder named
for the repository plus a hash of its URL, so two organizations with the same
repository name never share a folder. A rerun accepts the existing clone only when it
is a real git clone, clean, and has the exact declared origin; it then fetches and
checks out the remote's default branch. The manifest must be a tracked, regular file.

Organization git runs with only HTTPS and SSH transports allowed
(`GIT_ALLOW_PROTOCOL=https:ssh`, `protocol.file.allow=never`,
`protocol.ext.allow=never`) and with injected `GIT_CONFIG_*` variables removed, while
the member's own credentials keep working.

Knowledge bases use the workspace convention, `~/workspaces/<org.workspace>/<name>`.
Existing clones are accepted only at their declared remote; setup never repoints them.
A clean clone fast-forwards to its upstream; one with uncommitted work, unpushed or
diverged commits is skipped and named.

Shared skills repositories are data sources, not execution authorities. Setup
copies `skills/<name>/` (or top-level `<name>/`, never both layouts at once) into
`~/.claude/skills/` and `~/.agents/skills/`, never `~/.codex/skills/`. It records what
it wrote (`~/.synthesis/v5/org-skills.json`), and a copy someone edited since, or one
setup did not write, is kept and named. A repository-provided setup script is ignored
and an executable manifest field is rejected.

## Instruction provenance

The declared source must be a regular, Git-tracked file in the organization
configuration repository. Setup writes the workspace's `AGENTS.md` as the public
baseline ([kernel.example.md](kernel.example.md)), then the organization source, then
the optional personal source, under a generated marker, and `CLAUDE.md` as the literal
`@AGENTS.md`. It rewrites `AGENTS.md` only when the file is absent or carries that
marker. Existing workspace-root instruction files remain untouched unless the user
passes `--adopt-workspace-instructions`, which moves both to
`~/.synthesis/v5/archive/<timestamp>/` first.
