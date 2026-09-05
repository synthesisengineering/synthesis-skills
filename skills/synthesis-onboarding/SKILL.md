---
name: synthesis-onboarding
description: "Install, update, repair, diagnose, and uninstall the synthesis work system through one stable public CLI. Covers immutable release acquisition, stable and edge channels, exact pins, full and skills-only profiles, tracked dual-client workspace instructions, optional declarative organization enrollment, transactional desired and observed state, plugin currency, and outcome verification. Use when asked to onboard, install synthesis, set up the ecosystem, configure a knowledge workspace, update or repair an installation, enroll an organization, verify an install, or diagnose onboarding."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.3.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Onboarding

One bootstrap and one stable `synthesis` command manage the public synthesis
work system. The engine is convergent and transactional: it records desired
state separately from machine observations, stages each mutation, commits only
after its probes pass, and preserves an aborted receipt when work fails.

## Start here

Full system, the default:

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
```

Skills only, through the same bootstrap:

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- setup --profile skills-only
```

After bootstrap, use the installed public command:

```bash
synthesis setup [--profile full|skills-only] [--clients claude,codex]
                [--channel stable|edge] [--pin X.Y.Z]
                [--answers PATH] [--org-repo URL | --invite PATH]
                [--personal-instruction-source PATH]
                [--adopt-workspace-instructions]
                [--clear-personal-instruction-source]
synthesis enroll --org-repo URL | --invite PATH
                 [--personal-instruction-source PATH]
                 [--adopt-workspace-instructions]
                 [--clear-personal-instruction-source]
synthesis update
synthesis repair
synthesis status [--json]
synthesis doctor [--json]
synthesis workspace ensure --name NAME [--remote URL]
synthesis outcome verify --task TASK --workspace PATH --source-class CLASS
synthesis uninstall [--purge]
```

`synthesis status` and `synthesis doctor` print a plain summary by default:
profile, policy, release, generation, each truth plane, and one next action.
`--json` returns the structured payload instead.

`synthesis update` and `synthesis repair` migrate an older plugin-only receipt
automatically when it contains no workspace, organization, or generated-resource
state. Richer or unreadable legacy state is never guessed; run `synthesis setup`
to select the intended profile explicitly. An update that finds each client
already at the selected release on the selected marketplace ref reports
"no refresh needed" and leaves the client installations untouched; only a
version change or a policy transition reconfigures a marketplace.

`synthesis uninstall` removes the client plugins, receipt-owned generated
files, and hook entries, then lists what it retained: the launcher, the
release cache, the acquisition mirror, state, and configuration. `synthesis
uninstall --purge` removes those too after the removal verifies, archiving
the desired state and observation history under the synthesis home first.

`install.sh` remains a compatibility entry point. With explicit direct-copy
targets it invokes the audited copy capability; otherwise it routes through
the same bootstrap and stable CLI.

## Profiles and visible layers

`references/release-capabilities.json` is the public capability source.
`references/layers.json` defines the layer catalog used by setup and doctor.

- `full` selects skills, session context, hooks and gates, agent kernel,
  runtime engines, coordination, doctors and conformance, personal policy,
  knowledge bases, and lifecycle. Organization enrollment is conditional.
- `skills-only` selects skills, session context, and lifecycle. Additive
  organization enrollment is available without selecting any personal layers.

Each selected layer ends as verified or non-green. A declined layer is not
silently reported as installed merely because plugin source contains its code.

## Release identity and acquisition

`onboard.sh` may fetch a mutable channel name, but never executes mutable
content. It resolves the ref once, then the Python bootstrap verifies the exact
version tag, commit, Git tree, client manifests, canonical tree digest, regular
file types, and collision-safe launcher before activating a read-only,
content-addressed generation.

- `stable` is the default and follows the release-gated `stable` branch.
- `edge` follows `main` and is explicit.
- `--pin X.Y.Z` resolves the immutable `vX.Y.Z` tag and overrides a channel.
- An unrefreshable source is refused unless the operator explicitly accepts a
  previously verified immutable generation.

Release-currency checks retain full TLS and hostname verification. On macOS
Python installations without a configured CA path, the engine retries through
an existing operating-system CA bundle; it never disables certificate checks.

The trust contract protects against transport errors, moving refs, local path
replacement, and content drift. It does not claim to defend against compromise
of the source host and its credentials; that requires an independent signing
channel.

## State and recovery

Desired configuration lives under the XDG config root. Machine observations,
transactions, release descriptors, and invite-use receipts live under the XDG
state root. Writes use a process lock, unique temporary files, atomic replace,
and monotonic generations. Startup recovers interrupted pending transactions as
aborted before accepting another mutation.

Setup commits the engine's validated effective selection, not preflight
placeholders: the profile, present selected clients, personal workspace,
normalized personal configuration, optional runtime choice, and layer choices
in desired state are the ones the successful engine run actually installed.
Repair reads that committed state, can regenerate missing derived policy files,
holds organization policy at its recorded commit, and reconciles the selected
layers. Legacy resource receipts remain ownership and conffile evidence; they
do not choose desired policy.

`synthesis update` refreshes only on an explicit user or agent request. A
floating installation that is already ahead of the newest stable release is
informational; it is never told to downgrade. Exact pins remain exact.

## Tracked instructions for both clients

`synthesis workspace ensure --name NAME` creates or repairs the conventional
personal knowledge repository and its tracked instruction source:

```text
~/workspaces/<workspace>/ai-knowledge-<workspace>/.agents/workspace-AGENTS.md
```

The workspace-root `AGENTS.md` is a relative symlink to that one complete
source, and `CLAUDE.md` is the minimal `@AGENTS.md` adapter. Existing files with
another owner are preserved and make the run non-green. The scaffold also
seeds `.agents/knowledge-base.yaml` (declaring the `source/` bundle for the
knowledge-base skills and the public outcome verifier), `projects/index.yaml`,
and `lessons/`; every seeded file is user content from the moment it exists
and is never regenerated. The tracked sources are included in the
repository's first commit; adding them to an existing repository creates an
exact-path commit rather than leaving them untracked. A refused commit is
reported with Git's own reason, so a hook refusal is never mislabeled as a
missing identity. Edit and commit the tracked source, never the workspace
entry points.

Organization instructions use the same provenance rule. The rendered graph is
public baseline, exactly one organization source, then an optional user-owned
personal source. Every repository source must be a committed, clean, regular
Git-tracked file; untracked, dirty, traversing, and symbolic-link sources are
refused. Both outputs activate or neither does. Doctor verifies each source
commit and digest plus both output digests against the receipt.

The optional personal layer is local desired state, never organization data:

```bash
synthesis setup --profile full --org-repo URL \
  --personal-instruction-source /absolute/path/to/private-config/.agents/workspace-instructions.md
```

Setup persists the source repository and relative path, so `synthesis update`
and `synthesis repair` replay and revalidate it. Omitting the option on a later
setup preserves the declared source; removing it requires
`--clear-personal-instruction-source`.

An existing workspace-root `AGENTS.md` or `CLAUDE.md` without an engine receipt
is preserved by default. After the complete instruction content is represented
in committed graph sources, `--adopt-workspace-instructions` explicitly archives
each existing regular file, verifies the archive bytes, and then activates the
pair. The receipt records archive paths, prior digests, modes, and time. A
failure after the first activation restores both original outputs while keeping
the verified archives.

## Declarative organization enrollment

An organization repository contains data only: `.agents/onboarding.yaml`, one
tracked instruction source, and optional documentation. It cannot select or
execute an installer. Shared skill repositories are copied through the public
engine's fixed direct-copy capability. Knowledge repositories are cloned or
updated only when their exact remote and cleanliness checks pass.

The copy capability accepts either `skills/<name>/SKILL.md` or top-level
`<name>/SKILL.md` organization repositories, never both layouts at once.
Existing shared copies require matching repository identity and exact source
bytes at their recorded commit before enrollment can adopt their ownership.

Enrollment, engine locking, and rollback use the same receipt directory:
`SYNTHESIS_ONBOARD_STATE_DIR` when set, otherwise
`${XDG_STATE_HOME:-$HOME/.local/state}/synthesis`. Legacy receipts are not the
default destination for new enrollment transactions.

Public bootstrap acquisition remains HTTPS-only. After verifying the immutable
release, the CLI permits HTTPS and SSH repository transports; local-file and
external-helper transports remain forbidden.

For a new installation, use `synthesis setup --org-repo URL`. For an existing
enabled full or skills-only installation, use `synthesis enroll --org-repo URL`.
Enrollment preserves the base profile, personal workspace, configuration, layer
choices, selected clients, and release policy. It adds only the organization
overlay and an explicitly selected personal instruction source; it never calls
the personal initializer or reinstalls the public plugin.

The organization's client and release requirements must match the saved
selection. Conflicts, a different organization, or a workspace collision are
refused. The saved additive mode and workspace identity apply to update, repair,
and doctor too. Skills-only repair does not rewrite independently managed
personal layers or their receipt metadata. Full repair continues to reconcile
its already-selected personal layers.

Enrollment journals exact generated targets before mutation. Engine, doctor,
or state-commit failure restores instructions, selected skill copies, ownership
receipts, and invite use. Mutating commands recover interrupted enrollment;
doctor remains non-green until recovery finishes. Verified archives, organization
source caches, and new knowledge clones are retained. Existing knowledge clones
are adopted without pulling or changing their configuration during enrollment;
required executable pre-commit protection must already be configured.

Organization skill ownership is checked before every replay. Changed private
copies are preserved; unchanged legacy copies can be adopted only after their
bytes match their recorded Git revision. Removed skills and removed sources are
archived using exact ownership receipts. Uninstall consumes that inventory and
reports edited retained copies as non-green.

Each organization copy commits its ownership receipt before a later phase can
fail. A partial copy restores both the previous bytes and receipt. Interrupted
copy recovery precedes outer enrollment rollback; doctor only reports pending
recovery. Repair returns a clean managed organization cache to its recorded
commit without fetching, then replays the saved selection.

Either setup or enrollment can use a credential-free, time-bounded invite file.
Invites are validated before mutation, expire within
seven days, may pin the organization commit, and are protected against replay.
See `references/org-manifest.md` and `references/invite.schema.json`. A
schema-1 manifest is refused before any mutation with a message naming the
migration section of that guide; the public source baseline for the rendered
instruction pair comes from the digest-verified installed release, so
enrollment works from the installed CLI, not only from a source checkout.

## Doctor and truth planes

Doctor does not fetch repositories, change refs, update plugins, or rewrite
desired state. It reads the selected release channel's manifest over HTTPS and
caches that answer in `plugin-currency.json` under the state root, and it
attaches fresh client SessionStart receipts from the conformance registry to
the current generation: Claude runs its SessionStart hook before it creates
the session transcript, so a fresh Claude session records a pending receipt
that doctor or status promotes once the transcript binds the session. Every
plane is re-derived at doctor time; the active release root is re-hashed
against its descriptor rather than trusted from the last transaction. It
reports six planes independently:

1. desired
2. resolved
3. installed
4. source provenance
5. live loaded
6. outcome verified

A plugin version, directory, or generated instruction file proves only its own
plane. `live-loaded` requires a fresh client lifecycle receipt after restart.
An outcome verifier is release-owned; organization data may name only a trusted
verifier ID, never provide a command.

Exit `0` means the selected checks are green, `1` means a verified defect or
required action, and `2` means ground truth could not be established.

## Update lifecycle

An update is the initiating task's last action before client restart. On
machines with the durable historical-cache guardian, the update also verifies
the exact historical root used by the invoking task before returning. Resume
the same conversation only after a genuine fresh SessionStart receipt reports
the installed release and loaded skills. Codex hook trust remains a human
setting and is never auto-approved.

## Ownership boundaries

- Public engine: acquisition, validation, mutations, direct-copy behavior,
  transactions, capability IDs, doctor logic, and release descriptors.
- Organization repository: declarative repositories, welcome text, trusted
  acceptance IDs, and one tracked instruction source.
- User: credentials, personal policy content, optional personal instruction
  source and explicit adoption, source edits, client restart, and deployment
  decisions.

Unknown fields, unsafe paths, embedded credentials, dirty or wrong-remote
clones, symlinked release files, and executable organization fields fail closed.

## Maintainer contract

```bash
python3 -m pytest skills/synthesis-onboarding/scripts/ -q
python3 skills/synthesis-onboarding/scripts/check_scaffolds.py .
python3 skills/synthesis-onboarding/scripts/check_capabilities.py .
sh -n install.sh onboard.sh tests/test_installer.sh
./tests/test_installer.sh
```

The gated publisher runs the same checks, atomically advances the release refs,
materializes the published descriptor through the bootstrap verifier, refreshes
both supported clients, and verifies installed bytes. Release claims remain
serialized by `release-train:synthesis-skills`.
