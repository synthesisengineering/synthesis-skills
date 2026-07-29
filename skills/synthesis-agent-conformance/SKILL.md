---
name: synthesis-agent-conformance
description: Audit, install, and verify a synthesis ecosystem across multiple AI agent runtimes. Use for Claude Code and OpenAI Codex parity audits, AGENTS.md and CLAUDE.md instruction migrations, skill or plugin deployment checks, lifecycle-hook health, Mac bootstrap validation, active-project handoffs, post-compaction recovery, and any request to make synthesis project management portable between agent clients.
---

# Synthesis Agent Conformance

Treat cross-agent portability as a continuously tested system, not a file-count
comparison.

## Operating model

Verify four planes:

1. **Canonical:** version-controlled skills, instructions, project state, and
   configuration.
2. **Adapters:** client-native manifests, instruction files, settings, and
   hooks.
3. **Deployment:** installed plugins/skills, generated files, authenticated
   tools, and runtime configuration.
4. **Verification:** source checks, client doctors, hook health, and handoff
   exercises.

Name the plane whenever two facts appear to conflict. Runtime state determines
current behavior; canonical state determines what the next deployment should
produce.

## Workflow

### 1. Inventory

Run:

```bash
python3 scripts/conformance.py source
python3 scripts/conformance.py runtime
python3 scripts/conformance.py instructions --repo-root <repo>
python3 scripts/conformance.py coordination
```

Use `--json` for a machine-readable report. A warning is not a pass. Any
required check that cannot run fails the command.

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
python3 scripts/conformance.py activate --project <project-directory>
```

The command writes a local pointer only. `CONTEXT.md`, `REFERENCE.md`,
`sessions/`, and plan artifacts remain the source of truth.

Before activation writes, read and claim the source areas on
`~/.synthesis/coordination/active-sessions.md`. Conformance validates the board
shape; `synthesis-project-management` owns its operating protocol.

### 4. Verify handoff

Run:

```bash
python3 scripts/conformance.py handoff --project <project-directory>
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
Codex reruns `SessionStart` after root-session compaction with a `compact`
start source, so the same hook restores the active project without a second
client-specific implementation. The script:

- verifies the local clock;
- reads the active-project pointer;
- verifies that the project still exists;
- extracts the current phase, status, plan, and next actions from durable files;
- emits a compact context anchor.

Claude calls the same script from its native `SessionStart` hook. Client hook
configuration remains an adapter; the context-producing behavior is shared.

## Detailed architecture

Read [references/architecture.md](references/architecture.md) when designing or
changing an installation, plugin package, hook set, or cross-machine sync.
