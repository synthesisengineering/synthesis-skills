---
name: synthesis-agent-conformance
description: "Audit and verify that synthesis behaves the same in Claude Code, Codex and Muse: source lint, installed parity, hook wiring and trust, AGENTS.md/CLAUDE.md adapters, skill catalogs, and project handoff between harnesses. Use for parity audits, instruction migrations, or checks after install."
license: "Apache-2.0"
depends_on: ["synthesis-project-management", "synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Agent Conformance

Treat cross-agent portability as a continuously tested system, not a file-count
comparison. This skill audits five planes (source, installed, live, continuity,
capability) with the v5 tools, repairs from source, and keeps always-loaded
instructions small enough for every harness.

## Binding rules

1. **Parity is tested, never inferred.** Matching inventories or version labels are not parity; a self-report is a claim, so compare installed bytes and read each harness's own answers.
2. **Name the plane when facts conflict.** Runtime state is current behavior; source is what the next deployment produces.
3. **UNKNOWN never becomes PASS.** A check that could not run is reported as unknown, with what it needed.
4. **Never write a harness's trust state.** Codex `/hooks` trust and Muse hook approval are the person's decisions; report what needs approving.
5. **Repair from source, never in an installed copy or cache.** Keep shared behavior agent-neutral and put harness differences in adapters.
6. **`AGENTS.md` is canonical; `CLAUDE.md` is exactly `@AGENTS.md`.** Private skills go to `~/.claude/skills` and `~/.agents/skills`, never `~/.codex/skills`.
7. **Respect Codex's budgets.** Instructions stay under `project_doc_max_bytes` minus 4 KiB, and the skill catalog within 2% of context, with specialists explicit-only and the router routing.
8. **Follow a generator-backed artifact only when it is verifiably the generator's output.** A hand-made decision packet skips what the generator guarantees.
9. **When a desktop client cannot read a protected file, find the engine responsible** and report UNKNOWN until an observed check shows otherwise.

## Contents

- **Procedure** (below): the audit in order.
- [references/audit.md](references/audit.md): the five planes, the source lint, every doctor check, live and continuity checks, the skill catalog contract, skill-output provenance, repair rules. Read before an audit or when a check fails.
- [references/architecture.md](references/architecture.md): ownership, instruction discovery, deployment, lifecycle controls, project handoff, cross-machine sync, the conformance contract. Read when designing or changing an install, plugin, hook set or sync.
- [references/instruction-kernel-pattern.md](references/instruction-kernel-pattern.md): the thin-kernel structure, four enforcement classes, the not-weakening proof, the budget gate. Read when an always-loaded instruction file nears its budget or rules move to skills, hooks or config.
- [references/macos-file-access.md](references/macos-file-access.md): attributing a protected-file denial and accepting a permission across updates. Read when a desktop client cannot access a file.
- [references/autopilot-browser-quality.md](references/autopilot-browser-quality.md): reviewing an outcome on an external target (account, stored state, excluded items). Read for external-target work.
- [references/coverage-map.md](references/coverage-map.md): where every section of 1.14.1 went (ruling D8).
- [references/preserved.md](references/preserved.md), [references/preserved-architecture.md](references/preserved-architecture.md), [references/preserved-hermes-cli-pilot.md](references/preserved-hermes-cli-pilot.md), [references/preserved-provider-change-intake.md](references/preserved-provider-change-intake.md), [references/preserved-report-contract.md](references/preserved-report-contract.md), [references/preserved-signed-observations.md](references/preserved-signed-observations.md), [references/preserved-vendor-demo-protocol.md](references/preserved-vendor-demo-protocol.md), [references/preserved-vendor-review-packages.md](references/preserved-vendor-review-packages.md), [references/preserved-yaml-runtime.md](references/preserved-yaml-runtime.md): the 1.14.1 text verbatim. Read only to review what was cut.

## Procedure

1. **Source.** In the source checkout: `python3 -m pytest -q tests/test_source_lint.py`.
   Every failure names the file or skill to fix.
2. **Installed.** `synthesis doctor` (add `--latest` to compare with the published
   release). The first line says `healthy` or how many problems; each later line is
   `ok`, `warn`, `fail` or `info`, a check name, and what it found. Fix every `fail`
   from source, then rerun.
3. **Live.** Start a fresh session in each harness and confirm its SessionStart context
   names the active project. Ask the person to trust changed hooks in Codex's `/hooks`
   and to run `muse plugins approve synthesis-skills` when doctor lists pending hooks.
4. **Continuity.** `synthesis use <project>` and `synthesis brief` in one harness; open
   another harness with no pasted transcript and confirm the same phase, plan and next
   action. For another Mac, `synthesis handoff` pushes the records in this session's
   claims.
5. **Instructions.** For each folder doctor lists under `instruction adapters`, make
   `AGENTS.md` canonical and `CLAUDE.md` exactly `@AGENTS.md`; never overwrite a
   divergent pair blindly, merge it in source first.
6. **Close.** Record genuine harness differences as boundaries with evidence; report
   parity only when every plane passed.
