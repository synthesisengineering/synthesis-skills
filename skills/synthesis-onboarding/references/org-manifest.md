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

```bash
synthesis setup --profile full --org-repo ssh://git@example.test/example/onboarding-config.git
synthesis setup --profile full --invite invitation.json
```

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

The declared source must be a regular Git-tracked file in the organization
configuration repository. The engine records its repository, commit, relative
path, and digest, then activates identical `AGENTS.md` and `CLAUDE.md` outputs
as one transaction. If either target collides or activation fails, neither new
output remains active. Doctor verifies both output digests against the receipt.

## Public capability ownership

The release catalog owns acceptance IDs and their implementations. Schema 2
currently allows `workspace-grounding-check`, which proves a conventional
personal knowledge workspace has a readable, safe knowledge bundle. A manifest
can request that ID but cannot replace its logic. This keeps an organization
from marking its own installation healthy with an arbitrary command.
