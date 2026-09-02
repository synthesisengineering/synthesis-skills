---
name: synthesis-agent-conformance
description: Audit, install, and verify a synthesis ecosystem across multiple AI agent runtimes. Use for Claude Code and OpenAI Codex parity audits, AGENTS.md and CLAUDE.md instruction migrations, skill or plugin deployment checks, lifecycle-hook health, Mac bootstrap validation, active-project handoffs, post-compaction recovery, and any request to make synthesis project management portable between agent clients.
license: "Apache-2.0"
depends_on: ["synthesis-project-management", "synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "1.8.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Agent Conformance

Treat cross-agent portability as a continuously tested system, not a file-count
comparison.

## Operating model

Verify five planes:

1. **Source:** version-controlled skills, instructions, client adapters, hooks,
   project state, and configuration.
2. **Installed:** deployed plugins and skills, generated files, catalogs,
   instruction budgets, runtime configuration, and Codex's authoritative hook
   trust state. Never infer or write trust state.
3. **Live:** client-specific receipts created by genuine lifecycle events. A
   static script probe is not live evidence.
4. **Continuity:** coordination leases, active pointers, attributed local
   working state, explicit remote publication, and bidirectional handoff
   exercises.
5. **Capability:** authenticated read-only outcomes and explicitly supported,
   unsupported, or unverifiable product surfaces.

Name the plane whenever two facts appear to conflict. Runtime state determines
current behavior; canonical state determines what the next deployment should
produce.

## Workflow

### 1. Inventory

Run:

```bash
python3 scripts/conformance.py source
python3 scripts/conformance.py runtime
python3 scripts/conformance.py parity
python3 scripts/conformance.py catalog
python3 scripts/conformance.py instructions --repo-root <repo>
python3 scripts/conformance.py instruction-budget --repo-root <repo>
python3 scripts/conformance.py hook-definition
python3 scripts/conformance.py hook-trust --repo-root <repo>
python3 scripts/conformance.py hook-live
python3 scripts/conformance.py coordination
python3 scripts/conformance.py capabilities --repo-root <repo>
python3 scripts/conformance.py surfaces
```

`hook-live` without selectors answers the current-health question: it checks
the newest Claude and Codex receipt pointers and keeps the 24-hour freshness
gate. To reverify a release or handoff against its exact accepted sessions,
select the preserved event records explicitly:

```bash
python3 scripts/conformance.py hook-live \
  --claude-receipt-session-id <claude-session-uuid> \
  --codex-receipt-session-id <codex-session-uuid>
```

Do not substitute one scope for the other. A newer unrelated start may make
current health fail without erasing an earlier accepted event; an accepted
session check does not establish that the newest global start is healthy.
Preserved events are local runtime evidence and have no automatic age-based
deletion. Exact-session checks waive only the 24-hour freshness limit; they
still require the original client-owned transcript, matching session UUID,
plugin version, and exact plugin root to validate.

Use `--json` for a machine-readable report. Each check carries a plane and one
of PASS, FAIL, WARN, UNKNOWN, or UNSUPPORTED. A required UNKNOWN fails the
aggregate command; "not tested" cannot become parity.

### 2. Repair from source

- Edit source repositories, never installed skill or plugin caches.
- Keep shared behavior agent-neutral.
- Use native adapters for platform differences.
- Make `AGENTS.md` canonical for tracked repository instructions.
- Make `CLAUDE.md` a small documented import adapter: `@AGENTS.md`.
- Install public skills as the `synthesis-skills` plugin on Claude and Codex.
- Install private skills to `~/.claude/skills` and `~/.agents/skills`.
- Do not create a second source-managed copy under `~/.codex/skills`.

### 3. Activate durable project state

When starting or switching a synthesis project:

```bash
python3 scripts/conformance.py activate \
  --project <project-directory> \
  --session-id <coordination-session-id>
```

The command writes a local pointer only. `CONTEXT.md`, `REFERENCE.md`,
`sessions/`, and plan artifacts remain the source of truth. The pointer records
the owning session and coordination-board lease URL, plus its worktree,
branch, and source commit; `pointer` verifies those fields against disk.
Activation and pointer validation share the local-continuity record contract:
uncommitted project edits are acceptable exactly when session-attributed
pending manifests record every dirty path, and any unattributed path fails
closed. A live owner holding an attributed stopped-task record
(`LOCAL_READY` or `LOCAL_RECOVERABLE`) can therefore activate without
committing first.

Before activation writes, read and claim the source areas on
`~/.synthesis/coordination/active-sessions.md`. Conformance validates the board
shape; `synthesis-project-management` owns its operating protocol.

### 4. Verify handoff

Run:

```bash
python3 scripts/conformance.py handoff --project <project-directory>
python3 scripts/conformance.py pointer --project <project-directory>
python3 scripts/conformance.py continuity \
  --project <project-directory> --readiness local
python3 scripts/conformance.py continuity \
  --project <project-directory> --readiness remote
```

`pointer` verifies a live owner's leased cache. Local continuity verifies that
Claude and Codex reconstruct identical project state with no pointer. A clean,
readable record with no attributed task edits is `LOCAL_READY` without creating
empty evidence. When a task changes repository files, a current Stop receipt is
required for `LOCAL_READY`; the attributed manifest without that receipt is
`LOCAL_RECOVERABLE` after interruption. Remote continuity additionally requires
no pending manifest and complete branch-head equality with the fetched upstream,
not merely equality for commits touching the project subdirectory. Then open
the project in the other client and confirm its SessionStart or first
named-project turn recovers the same state.

### 5. Close the loop

Run the complete check:

```bash
python3 scripts/conformance.py all \
  --repo-root <current-repo> \
  --project <project-directory>
```

Fix every failed required check. Record genuine client-owned differences as
boundaries with evidence; do not report parity from matching inventories alone.
Since 1.7.0 parity also reads each client's installed manifest on disk beside
the CLI report (`parity.<client>-on-disk`): a self-report is a claim, not
evidence — it once stayed green while the loaded tree sat three releases behind.

## Lifecycle hooks

The plugin’s `hooks/hooks.json` uses `session_context.py` at `SessionStart`.
Codex reruns `SessionStart` after root-session compaction with a `compact` start
source, so the same hook restores the active project without a second
behavior-producing implementation. The script:

- verifies the local clock;
- reads the active-project pointer;
- discovers a stopped project directly when the task directory is inside its
  durable project tree;
- when neither route identifies a project, instructs the receiving agent to
  resolve the user's named project through the git-tracked registry and run
  the Session Start Protocol automatically;
- verifies that the project still exists;
- extracts the current phase, status, plan, and next actions from durable files;
- emits a compact context anchor;
- appends an immutable event record for every genuine `SessionStart`, then
  advances atomic generic and client-specific latest pointers monotonically.
  Exact-session conformance reads the event registry, so a later unrelated
  start cannot erase the addressability of accepted evidence. Claude may name its
  client-owned transcript before creating its first JSONL record; the receipt
  preserves that lifecycle event and records whether the binding existed at
  hook time. Release conformance still requires the exact transcript to bind
  the same session UUID. Claude evidence must use the canonical
  `projects/<encoded-cwd>/<session-id>.jsonl` root shape; subagent descendants,
  symlinks, and contradictory UUID declarations fail closed. Current-health
  checks still require the latest public-plugin receipts from both Claude Code
  and Codex. Release and handoff reverification must select the exact durable
  session UUIDs rather than trusting whichever global receipt happens to be
  newest. The private Codex control-plane receipt remains a separate opt-in
  check.

Claude calls the same script from its native `SessionStart` hook. Client hook
configuration remains an adapter; the context-producing behavior is shared.
Codex hook trust is a separate human-controlled check within installed state:
`hook-trust` queries
Codex app-server's read-only `hooks/list` API for the current normalized hash,
source owner, and trust reason, and never edits `hooks.state`.

The active pointer is deliberately not synchronized as one global current
project. Parallel root sessions may work on different projects. Same-machine
cross-client continuity consumes project files plus attributed working-tree
state. Cross-computer continuity requires the explicit `REMOTE_READY`
transition and a fast-forwarded destination checkout.

## Skill catalog contract

Codex budgets the combined model-visible skill catalog at 2% of the active
model context. Audit the resolved catalog through app-server `skills/list`;
do not infer safety from the public plugin's file count. Public specialist
skills may set `policy.allow_implicit_invocation: false` in
`agents/openai.yaml`: they remain enabled and explicitly invocable, while
`synthesis-skill-router` supplies natural-language routing. Claude Code ignores
that OpenAI-specific prompt policy and retains its native trigger behavior.

## Detailed architecture

Read [references/architecture.md](references/architecture.md) when designing or
changing an installation, plugin package, hook set, or cross-machine sync.

## Instruction-kernel pattern

Read [references/instruction-kernel-pattern.md](references/instruction-kernel-pattern.md)
when an always-loaded instruction file approaches its budget or rules migrate
to skill, hook, or config homes: the thin-kernel structure, the four
enforcement classes, the not-weakening proof obligation, and the budget gate.
