---
name: synthesis-skills-manager
description: "Agent-native skill installer and manager for the synthesis skills ecosystem. Handles installation, drift detection, synthesis merge for conflicts, provenance tracking, and cross-repo coordination. Use when asked to: install skills, update skills, check skill drift, manage skills, skill status, skill inventory, sync skills."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.5.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Skills Manager

**Version 2.5.1** (2026-09-02) prioritizes the newest historical Codex roots
during recovery, so the version most likely to be pinned by a just-updated task
returns first instead of last. The onboarding update engine now consumes the
durable guardian synchronously before reporting a successful Codex refresh and
verifies the invoking task's exact hook tree. The budgeted, tag-backed archive,
single-writer transition lock, supervisor, refusal of unsafe or differing
content, and client-owned newest-version boundary remain unchanged.

**Version 2.5.0** established the durable background guardian and kept recovery
digests scoped to tracked release content rather than client-owned metadata.
The whole-system onboarding suite and its scaffold/component catalog audit
remain required release checks.

Manage synthesis skills across a three-repo architecture. Skills are executable
methodology. Public skills are also packaged as a native plugin for clients that
support plugins; private and shared skills remain native user/project skills.

## Architecture

Three skill repositories, each with a different access level:

| Repo | Type | Access | Purpose |
|------|------|--------|---------|
| `synthesis-skills` | public | Open source | General-purpose methodology skills |
| Personal skills repo | personal | Owner only | Owner-specific skills |
| Team shared skills repo | shared | Team members | Cross-project team skills |

**Deployment targets:**

1. Public `synthesis-skills` plugin — install through both the Claude and Codex
   marketplaces.
2. `~/.claude/skills/` — private personal skills for Claude Code.
3. `~/.agents/skills/` — private personal skills for Codex and the Agent Skills
   convention.
4. `~/.cursor/skills/` — direct deployment for Cursor when present.
5. `/path/to/project/.claude/skills/` — Claude project skills when a shared
   repository intentionally uses project scope.
6. `/path/to/project/.agents/skills/` — portable project skills, including
   Codex discovery.

`~/.codex/skills/` is not a source-managed deployment target. Codex may own
system skills there; copying synthesis skills into both `.codex` and `.agents`
creates duplicate discovery.

## Provenance Tracking

Every installed skill has a `.source.json` file (gitignored in source repos):

```json
{
  "source_repo": "github.com/synthesisengineering/synthesis-skills",
  "source_type": "public",
  "source_path": "skills/synthesis-thinking-framework/SKILL.md",
  "source_commit": "abc123...",
  "installed_at": "2026-03-23T14:30:00Z",
  "installed_by": "synthesis-skills-manager"
}
```

## Commands

When the user asks you to manage skills, execute the appropriate command:

### `install [repo] [skill-name]`

Install a skill from a source repo to the target location.

1. Read the skill's SKILL.md from the source repo
2. Check if a skill with the same name already exists at the target
3. If it exists, compare whole-directory checksums.
4. If different, preserve a backup and resolve drift in the source repository.
   Never merge only into the installed copy.
5. Copy the source skill directory to the target.
6. Write `.source.json` with current commit hash and timestamp.
7. Check dependencies across all active source/plugin/user-skill roots.
8. Report result.

### `update [repo]`

Update all skills from a source repo.

1. For each skill in the source repo, run the install flow
2. Report: updated, skipped (unchanged), merged (drift resolved)

### `status`

Show the state of all installed skills.

1. Inspect the enabled `synthesis-skills` plugin in Claude and Codex.
2. Scan private/shared target directories for skill directories.
3. Group copied skills by `source_repo` from `.source.json`.
4. For each copied skill:
   - Read `.source.json` for provenance
   - Compare installed SKILL.md checksum against source (if source repo is available locally)
   - Report: OK, DRIFT (local changes), MISSING (in source but not installed), ORPHAN (installed but not in any known source)
5. Detect duplicate public skills across plugin and user-skill roots.
6. Check all dependencies across the combined inventory.
7. Validate access hierarchy.

### `drift [skill-name]`

Show what changed between installed and source versions.

1. Read both SKILL.md files
2. Show a diff summary (sections added, removed, modified)
3. Recommend: reinstall source, port the installed improvement into source, or
   perform a source-side synthesis merge.

### `merge [skill-name]`

Perform synthesis merge when drift is detected.

This is the key differentiator from package managers. Skills are methodology — when the installed copy and source both have legitimate changes, the right answer is synthesis merge, not "pick a version."

**Merge protocol:**

1. Read the source version (from repo)
2. Read the installed version (from target)
3. Read `.source.json` to find the common ancestor commit
4. Identify what changed in each:
   - Source changes: new sections, updated instructions, bug fixes
   - Local changes: customizations, environment-specific tweaks, improvements
5. Synthesize:
   - Keep all source structural changes (new sections, reordered steps)
   - Keep all local customizations that don't conflict with source intent
   - For true conflicts (both changed the same instruction differently), present both versions and ask the user
6. Write the merged result to the source repository.
7. Commit and push every configured source remote.
8. Reinstall or update the plugin/user-skill deployment.
9. Verify the installed result against source.

**What makes this different from git merge:** Git merges text. This merges methodology. An AI agent understands that moving a step from section 3 to section 2 is not a conflict with adding a new substep to section 3 — even though a text-based merge would flag it.

## Dependency Access Hierarchy

Strict rules — enforced on every install and status check:

| Skill Type | Can Depend On |
|------------|---------------|
| public | public only |
| private | public + private |
| shared | public + shared |

**No cross-collection private dependencies.** If a private skill needs functionality from a shared skill (or vice versa), the dependency must be promoted to public first.

### Checking Dependencies

Read `depends_on` from SKILL.md frontmatter:

```yaml
depends_on: ["synthesis-thinking-framework", "synthesis-content-quality"]
```

For each dependency:
1. Check the combined enabled-plugin and user/project-skill inventory.
2. Read `.source.json` for copied skills or plugin source metadata for public
   plugin skills.
3. Validate against the hierarchy table
4. Report warnings (missing) or violations (hierarchy breach)

## Configuration Separation

Skills with user-specific values have a `## Configuration` section with a table:

```markdown
## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| `daily_plans_path` | `daily-plans/` | Relative to the personal ai-knowledge repo; daily plans live at top-level after phase 2 |
```

When installing a skill that has a Configuration section:
1. Note the configuration table to the user
2. If the user has previously configured values for this skill (in a prior installation), preserve them
3. Never overwrite Configuration values during update — merge them

## Workflow Examples

### First-time setup

```
User: "Install all my synthesis skills"

1. Add the public repository as a marketplace in Claude and Codex.
2. Install and enable the `synthesis-skills` plugin in both clients.
3. Install personal skills to `~/.claude/skills/` and `~/.agents/skills/`.
4. Install shared project skills to `.claude/skills/` and `.agents/skills/`.
5. Write `.source.json` for every copied private/shared skill.
6. Run `synthesis-agent-conformance` to check duplicates and dependencies.
7. Report the source version and enabled runtime versions.
```

### Drift detected during update

```
User: "Update my skills"

1. Pull latest from each repo
2. For synthesis-daily-rituals: installed checksum ≠ source checksum
3. Read both versions
4. Installed has: added clickable link instruction (local improvement)
5. Source has: no changes since last install
6. Port the improvement into source, commit, push, and reinstall.
7. Report the source commit and zero-drift verification.
```

### Both sides changed

```
User: "Update my skills"

1. Pull latest from each repo
2. For synthesis-article-writing: installed checksum ≠ source checksum
3. Source has: new Phase 3 critical review section
4. Installed has: custom anonymization examples added
5. Decision: synthesis merge needed
6. Merge: keep new Phase 3 from source + keep custom examples from local
7. Report: "synthesis-article-writing: merged (source added Phase 3, kept local customizations)"
```

## Error Handling

- **Source repo not available locally:** Report which repo is missing, suggest cloning it
- **Circular dependencies:** Detect and report (should never happen with the hierarchy)
- **Corrupted .source.json:** Reinstall from verified source; do not infer
  provenance from the installed copy.
- **Skill with no frontmatter:** Warn — skill doesn't follow the standard. Install anyway but flag for review.

## Implementation Notes

This skill is designed to be executed by an AI agent. The agent reads files,
compares methodology, and resolves conflicts in source. Deterministic installers
and conformance scripts own copying, manifests, checksums, and health checks.

The `install.sh` scripts in each repo serve as bootstrap/fallback installers for environments without an AI agent. They handle the mechanical parts (copy, provenance, checksums) but cannot do synthesis merge — they overwrite on conflict. Drift detection covers the whole skill directory (scripts, references, data tables — not just SKILL.md); every drifted copy is saved to `${XDG_CACHE_HOME:-~/.cache}/<repo-name>-backups/<UTC-run-stamp>/<target>/<skill>/` before overwrite, and the end-of-run warning names each drifted skill and the backup path. Backups are pruned to the 10 most recent runs.

## `release.py` — the gated cross-client plugin release

For the **public plugin**, steps 3–7 of the protocol below are automated by
`scripts/release.py`, which exists because that sequence has exactly one
failure mode that matters and it is silent: the repository is the plugin (the
marketplace manifests carry no version and point at `./`), so pushing IS
publishing — but each client keeps a **version-pinned installation that does
not follow the remote**. A pushed-but-uninstalled release leaves the running
clients behind their own source with nothing visibly wrong.

```bash
python3 skills/synthesis-skills-manager/scripts/release.py --repo-root .
python3 .../release.py --dry-run       # print the plan, mutate nothing
python3 .../release.py --check-only    # preflight + required checks, no publish
python3 .../release.py --acceptance-only # consume the bound acceptance result (CI)
python3 .../release.py --install-only  # refresh + verify clients (new machine, drift recovery)
```

The sequence, each stage gating the next:

**preflight → required checks → publish → install both clients → verify**

- **Preflight** refuses to proceed unless both plugin manifests agree, the
  newest CHANGELOG entry matches them, and the tree is clean. It also refuses
  to run against an installed cache mistaken for the source checkout.
- **Acceptance consumption** derives the base-to-head change universe from
  Git at the release boundary, requires exact manifest coverage, and parses a
  fresh result bound to a one-use transaction, head commit and tree, manifest
  digest, and changed-path digest. The boundary recomputes those fields and
  rechecks the clean worktree before it can authorize publication. The
  accepted-state object survives the check phase and expires when any binding
  changes. CI invokes the same consumer with the pull request base supplied by
  its event record.
- **Publish** revalidates the accepted state immediately before every remote
  mutation and atomically pushes the immutable accepted commit SHA to three
  lifecycle refs: `refs/heads/main` (edge), `refs/heads/stable` (default), and
  `refs/tags/vX.Y.Z` (exact org pins). It never publishes a mutable local
  branch name. A per-remote atomic push prevents a channel or pin from moving
  without the others. This is the PRINCIPAL RULE D4 repair for `R5-REV-002`
  extended to the release-channel contract.
- **Install** uses each client's own commands, in the order each client
  requires. For Codex that means `plugin marketplace upgrade` **before**
  `plugin add`, because Codex installs *from* its git marketplace snapshot —
  skipping the upgrade installs the previous release while appearing to
  succeed. Before that destructive Codex refresh, the publisher snapshots every
  real versioned cache root retained by either client into a durable recovery archive.
  Immutable release tags supply authoritative tracked bytes. For releases that
  predate immutable tags, a peer-client or prior archive root is accepted only
  after its manifests, complete hook target set, and skill tree validate. Known
  Codex installation metadata is retained; arbitrary untracked cache files are
  not promoted into recovery state. The
  publisher holds a single-writer transition lock, restores missing Codex roots,
  repairs partial ones, and repeats the check until the tree has remained
  unchanged for ten seconds after the client command returned. That synchronous
  receipt covers the release transaction; it cannot prove that the client will
  not create another cache generation minutes later. The publisher therefore
  installs `cache_guardian.py` under the durable recovery root and verifies its
  user-level launchd or systemd supervisor before returning. The guardian shares
  the release lock, protects every archived version except the newest
  client-owned version, and rehydrates missing historical roots after any later
  cache replacement. It never deletes a cache path or overwrites differing
  existing content. Restoration runs newest-history-first so the immediately
  preceding version is available before older roots during a large recovery.
  The onboarding engine invokes the installed guardian synchronously after a
  Codex refresh and refuses to report success until the invoking task's exact
  version root and hook targets are present. The watcher continues protecting
  those roots against later reconciliation after either command exits.
  The archive has a 512 MiB hard budget and never deletes a historical root
  automatically when that budget is reached; unverifiable cleanup fails the
  release closed. Symlink recovery artifacts and client liveness markers are not
  preserved.
- **Verify** is the point of the whole script, and it checks each client
  **twice**: what the CLI reports, and the plugin manifest at the path the CLI
  says it loads. Agreement of both with the source version is the only pass.

### Why a client's own version report is not sufficient evidence

A client can report the intended version while the tree it actually loads is
older — a stale marketplace snapshot, a partial install, or a hand-made cache
directory all produce that state, and a report-only check passes green through
every one of them. This was not hypothetical: it is the regression that
motivated the script, and `test_release.py` pins it as a test that must fail
when reported-version and on-disk-version disagree.

The general rule this encodes, worth applying beyond releases: **when a
verification asks a system to describe itself, verify the description against
the artifact.** A self-report is a claim, not evidence.

## The stable path — never pin a version

Instruction files and long-lived sessions that pin a versioned cache path
(`…/synthesis-skills/4.59.0/…`) go stale on the next release — on 2026-09-01
a session on a months-old engine read the shared coordination board as
corrupt, and a workspace's own day-start commands pinned a release twenty
versions behind. The gated release therefore maintains a synthesis-owned,
version-independent path:

```
~/.synthesis/plugins/synthesis-skills/current  ->  <the verified install root>
```

It lives outside the client-owned caches (which the clients replace on their
own schedule), is repointed atomically by `release.py` only after both
clients verified the version, and is refused when the target root is not a
verified install (`install.stable-path`). Reference it from instruction
files and scripts instead of a version; `--install-only` repoints it on a
new machine. `SYNTHESIS_STABLE_PLUGIN_ROOT` overrides the parent for tests.

Two kinds of caller, two paths. Hooks and guards that must run even when no
plugin is installed, or while an install is mid-transition, resolve their
engine from a source checkout (a resolver that does so belongs with the
hook, not in an instruction file). Everything an agent is *instructed* to
run — day-start commands, board verbs, gates — pins the stable path: the
installed pointer is the verified release, while a source checkout may be
mid-transaction on a feature branch. `conformance.py parity` checks the
pointer daily (`parity.stable-path`): missing, dangling, or behind the
installed version all fail, so a stale pin is caught before a command runs
from it.

## The release train — one publisher at a time

On 2026-09-01, two agent sessions releasing this repository in parallel
overtook each other five times — each merge to `main` turned the other's open
PR CONFLICTING with checks never run — and once both authored the same
version number. Coordination-board messages failed as a serializer because
an autonomous session mid-transaction does not re-read the board between
authoring a version and merging.

Serialization is now mechanical. The train is a **virtual coordination-board
resource**, `release-train:synthesis-skills`, claimed like any source area:

```bash
python3 <synthesis-project-management-root>/scripts/coordination.py claim \
  ... --area release-train:synthesis-skills --area <your real areas>
```

The board's existing claim-overlap refusal is the mutual exclusion (two
holders cannot coexist; the lease serializes it across machines), and
`release.py`'s preflight enforces possession: on any machine that has a
coordination board, every mode except `--install-only` refuses unless the
running process's session — from `SYNTHESIS_COORDINATION_SESSION` or an
owned active-project pointer — holds the train. Machines without a board
(outside contributors) pass with a notice; adoption travels with the board.

Protocol: claim the train **before authoring the version bump**, hold it
through merge and `release.py`, and release or narrow the claim immediately
after the gated release completes. A crashed holder blocks the train by
design; the user — never another agent on its own initiative — frees it via
the stale-claim review (`coordination.py stale`).

## Source Update Protocol (NON-NEGOTIABLE)

When updating any skill — whether one file or several — follow this exact sequence. Do not deviate. **Manual file copies to install targets are NOT installation.** They create drift between what is committed, what is pushed, and what is locally active. The protocol below exists because that drift has happened before and must not happen again.

### The sequence

1. **Edit the skill in its source repo.** Public skill paths are
   `<source-repo>/skills/<skill-name>/SKILL.md`; private/shared repositories use
   their declared source layout. Never edit plugin caches or installed copies
   under `~/.claude/skills/`, `~/.agents/skills/`, or client caches.

2. **Verify the source repo state.** `git status` to confirm only the intended files changed. `git diff` to review the actual content of every change.

3. **Commit with a generic message** per public-repo commit hygiene. "Update skills" or similar. No skill names, no version arc, no rationale that exposes the work that motivated the edit.

4. **Identify all configured push remotes.** `git remote -v`. The skills repos may have multiple push remotes; the source-of-truth state is "the union of all configured push remotes is up to date."

5. **Push to EVERY configured push remote**, not just `origin`. Loop over the remote names from step 4. Single-remote repos still use this step — it just iterates once.

6. **Refresh deployments using the source’s canonical path.** For public
   skills, update/reinstall the `synthesis-skills` plugin in Claude and Codex.
   For private/shared skills, run the repository installer, which deploys to
   `~/.claude/skills/` and `~/.agents/skills/` (plus declared project/Cursor
   targets), writes provenance, and reports whole-directory drift.

7. **Verify zero drift.** After `install.sh` completes, `diff -q` each installed copy against the source. They must be byte-identical:
   ```bash
   for target in ~/.claude/skills ~/.agents/skills ~/.cursor/skills; do
     for skill in <changed-skill-names>; do
       diff -q "<source-repo>/$skill/SKILL.md" "$target/$skill/SKILL.md"
     done
   done
   ```
   Any output from `diff -q` is a failure. Investigate and re-run `install.sh update`.

### What you must NOT do

- **DO NOT** manually `cp` SKILL.md files from the source repo to install targets. The install targets are managed by `install.sh`, which writes `.source.json` provenance and runs drift detection. Manual `cp` skips both and produces files that look installed but are not canonically so.
- **DO NOT** edit plugin caches or installed copies under
  `~/.claude/skills/`, `~/.agents/skills/`, or client caches directly.
- **DO NOT** skip the push step before reinstalling. `install.sh` pulls from the configured remote; if you have not pushed, the install will refresh from a stale remote state and silently revert your local edits.
- **DO NOT** skip the verify step. "I ran install.sh" is not the same as "the install matches the source." The drift check (`diff -q`) is the proof.
- **DO NOT** ask for permission to push as if push were optional. Push is part of the install workflow, not a separate decision. If you have permission to update a skill, you have permission to push the source repo. Pausing between commit and push is the failure pattern that produced the 2026-04-29 incident — it leaves three different states of the truth (working tree, remote, installs) and the agent in the middle.

### Why these rules are non-negotiable

The 2026-04-29 incident: an agent edited four skill files in source, manually copied them to install targets to "install" them, then waited at the wrong gate before pushing. The result was three different states of the truth — source repo working tree (had the changes), GitHub (did not have the changes), install targets (had locally-copied files that drifted from what `install.sh update` would have produced). When `install.sh update` was finally run, it detected and overwrote the manually-copied drift. That detection-and-overwrite happened to be safe in that case, but it was luck, not design — the manual copies could just as easily have included an in-flight edit that the agent had not yet propagated to the source.

The protocol above eliminates the asymmetry. Source is the only edit point. Push happens before install. Install runs the canonical script. The verify step proves the canonical state. There is no place for three-states-of-truth to sit.
