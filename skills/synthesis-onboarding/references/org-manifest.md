# Organization manifest — `.agents/onboarding.yaml`

An organization repository extends the public synthesis engine with
declarative data. It contains no installer, shell fragment, hook command, or
arbitrary verifier. The public engine owns every executable capability.

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

The engine accepts schema 2 only. A manifest that still declares `version: 1`
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
| `migrations` (skill renames) | removed; retired skill directories are handled by the direct-copy capability |
| `ecosystem`, `auth_help`, `welcome`, `org` | unchanged |

After editing, validate the manifest from a checkout of the public repository:

```bash
python3 skills/synthesis-onboarding/scripts/onboard.py doctor --manifest /path/to/.agents/onboarding.yaml
```

The organization wrapper scripts that schema 1 required are not needed:
members run `synthesis setup --org-repo URL` (or use an invite) and the
public engine performs every step.

## Field contract

| Field | Contract |
|---|---|
| `version` | Required integer `2`. Unknown fields fail closed. |
| `org.id` | Required safe identifier. |
| `org.name` | Optional display name used only in local welcome text. |
| `org.workspace` | Required safe directory identifier. |
| `ecosystem.plugin` | Optional Boolean; defaults to true. |
| `ecosystem.clients` | Optional subset of `claude` and `codex`. |
| `ecosystem.channel` | `stable` by default or explicit `edge`. |
| `ecosystem.version_pin` | Optional exact `X.Y.Z`; overrides the channel. |
| `skills_repos[]` | `name`, safe `repository`, and fixed `capability: skills-install`. The public engine performs the copy. |
| `knowledge_bases[]` | `name`, safe `repository`, `default_branch`, and optional `local_hooks`. |
| `instruction_sources[]` | Exactly one entry with a repository-relative `path` and Boolean `required`. The source must be Git-tracked and regular; traversal and symlinks are rejected. |
| `acceptance.task` | A capability ID in the public release catalog. The organization cannot provide code or arguments. |
| `auth_help` | Plain-text local guidance. It must not contain credentials. |
| `welcome` | Local title, suggested questions, and repository-relative docs. |

Repository URLs must use authenticated HTTPS or SSH transport and must not
embed credentials. Local paths, `file:` URLs, Git's unauthenticated protocol,
and destination escapes are refused.

## Enrollment

First-time full-system installation:

```bash
synthesis setup --profile full --org-repo ssh://git@example.test/example/onboarding-config.git
synthesis setup --profile full --invite invitation.json
```

Add the organization to an existing installation without reinitializing its
personal kernel, policies, or runtimes:

```bash
synthesis enroll --org-repo ssh://git@example.test/example/onboarding-config.git
synthesis enroll --invite invitation.json
```

Additive enrollment supports either saved profile, preserves the selected
clients and release policy, and records the organization for future update,
repair, and doctor. Its manifest must agree with that installation's client,
channel, and exact-pin selection. A conflicting policy, different organization,
or changed workspace identity is refused rather than taking over personal
configuration. Existing knowledge repositories are adopted without a pull or
configuration change; required pre-commit protection must already be configured.

A user may add a private personal instruction layer without putting its path or
repository in this shareable manifest:

```bash
synthesis setup --profile full \
  --org-repo ssh://git@example.test/example/onboarding-config.git \
  --personal-instruction-source /absolute/path/to/private-config/.agents/workspace-instructions.md
```

The same personal-source and archive-first adoption options are available on
`synthesis enroll`. The engine stores that declaration only in local desired
state. Update and repair replay it. A later setup or enrollment preserves it unless the user explicitly passes
`--clear-personal-instruction-source`.

An invite carries the repository URL, optional exact commit, issuance time,
expiry no more than seven days later, and a nonce. It carries no credential.
The engine records successful use and rejects replay. Repository authentication
uses the member's normal Git credential path.

## Repository behavior

The engine clones organization configuration under the XDG data root. A rerun
accepts the existing clone only when it is a real Git worktree, clean, and has
the exact declared origin. Update may fetch and advance a floating commit;
doctor inspects the recorded commit without fetching or changing state.

Knowledge bases use the workspace convention. Existing clones are accepted
only at their declared remote; the engine never silently repoints them.
Repository-local hooks are enabled only through the public engine's audited
capability.

Shared skills repositories are data sources, not execution authorities. The
engine validates the repository and installs `skills/*` using its fixed
direct-copy implementation. A repository-provided setup script is ignored and
an executable manifest field is rejected.

## Instruction provenance

The declared source must be a regular, committed, clean Git-tracked file in the
organization configuration repository. The engine records its repository,
commit, relative path, and digest. It renders the public baseline first, then
the organization source, then the optional user-local personal source, and
activates identical `AGENTS.md` and `CLAUDE.md` outputs as one transaction. If
either target collides or activation fails, neither new output remains active.
Doctor verifies source commits and digests plus both output digests against the
receipt.

Existing workspace-root instruction files remain untouched unless the user
passes `--adopt-workspace-instructions`. Adoption accepts regular files only,
archives and byte-verifies them before activation, and records their archive
paths and digests in the local receipt. A partial activation restores both
original files; the archives remain available.

## Public capability ownership

The release catalog owns acceptance IDs and their implementations. Schema 2
currently allows `workspace-grounding-check`, which proves a conventional
personal knowledge workspace has a readable, safe knowledge bundle. A manifest
can request that ID but cannot replace its logic. This keeps an organization
from marking its own installation healthy with an arbitrary command.
