---
name: synthesis-agent-conformance
description: Audit, install, and verify a synthesis ecosystem across multiple AI agent runtimes. Use for Claude Code and OpenAI Codex parity audits, AGENTS.md and CLAUDE.md instruction migrations, skill or plugin deployment checks, lifecycle-hook health, Mac bootstrap validation, active-project handoffs, post-compaction recovery, and any request to make synthesis project management portable between agent clients.
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
4. **Continuity:** coordination leases, active pointers, pushed project state,
   and bidirectional handoff exercises.
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

Before activation writes, read and claim the source areas on
`~/.synthesis/coordination/active-sessions.md`. Conformance validates the board
shape; `synthesis-project-management` owns its operating protocol.

### 4. Verify handoff

Run:

```bash
python3 scripts/conformance.py handoff --project <project-directory>
python3 scripts/conformance.py pointer --project <project-directory>
```

The check verifies the project structure, current context fields, plan link,
git repository, and active-project pointer. Then open the project in the other
client and confirm its SessionStart or PostCompact context names the same phase,
status, plan, and next action.

### 5. Close the loop

Run the complete check:

```bash
python3 scripts/conformance.py all \
  --repo-root <current-repo> \
  --project <project-directory>
```

Fix every failed required check. Record genuine client-owned differences as
boundaries with evidence; do not report parity from matching inventories alone.

## Lifecycle hooks

The plugin’s `hooks/hooks.json` uses `session_context.py` at `SessionStart`.
Codex reruns `SessionStart` after root-session compaction with a `compact` start
source, so the same hook restores the active project without a second
behavior-producing implementation. The script:

- verifies the local clock;
- reads the active-project pointer;
- verifies that the project still exists;
- extracts the current phase, status, plan, and next actions from durable files;
- emits a compact context anchor;
- writes atomic generic and client-specific live receipts only when the client
  supplies a genuine `SessionStart` event and session id. Release conformance
  requires current public-plugin receipts from both Claude Code and Codex,
  plus the private Codex control-plane receipt.

Claude calls the same script from its native `SessionStart` hook. Client hook
configuration remains an adapter; the context-producing behavior is shared.
Codex hook trust is a separate human-controlled check within installed state:
`hook-trust` queries
Codex app-server's read-only `hooks/list` API for the current normalized hash,
source owner, and trust reason, and never edits `hooks.state`.

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
