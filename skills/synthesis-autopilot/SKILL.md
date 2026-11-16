---
name: synthesis-autopilot
description: "Run an explicitly delegated whole task to the end from a plan file in the project, unattended when needed. Use only on clear end-to-end delegation ('autopilot this', 'handle this end to end', 'run overnight'), never on a single-step approval or a talk about autonomy."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework", "synthesis-context-lifecycle", "synthesis-checkpoint", "synthesis-anti-shortcuts", "synthesis-grounding-discipline", "synthesis-implementation-integrity", "synthesis-project-management", "synthesis-adversarial-review", "synthesis-decision-packet", "synthesis-agent-conformance"]
metadata:
  author: "Rajiv Pant"
  version: "4.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: project-management
---

# Synthesis Autopilot

Carry a delegated whole task to the end, through compaction, waits and nights
away, with one plan file in the project as the run's record. The mode changes
how often the agent interrupts, never what it may do, and it sequences the
skills that already exist rather than restating them.

## Binding rules

1. **Engage only on explicit whole-task delegation.** Ambiguous wording means normal supervised work; never ask "should I use autopilot?" Over-firing removes supervision the user chose to keep.
2. **The run is its plan file in the project.** Write it from the template and run `engage` before the first phase; read it first after any compaction or wake. Chat compacts; the file does not.
3. **End a turn only four ways:** start the next open item; wait on a named external event with a continuation that will wake the session; record a blocker and alert; or close honestly. A summary that announces the next step without taking it is how an overnight run sat idle; the turn-end check asks for one of the four.
4. **Unattended time is scheduled.** If the horizon passes this turn, set up a continuation before the first turn ends; overnight or longer also needs a backstop that outlives the session, is visible, and says how to stop it. A scheduled job counts once its first wake is observed.
5. **No bare spins.** A cycle that advanced nothing names the external wait. Stop exactly at goals met, blocker plus alert, or budget used up plus alert; "still running" is not value.
6. **Probe before claiming a capability is missing,** and record the command and its output with the claim. Memory is not evidence of absence.
7. **Move what records cite into the project at every phase boundary.** Scratch and temp folders die at reboots, and lost findings get paid for twice.
8. **Decide by class.** Constraint-determined: execute. Open and important: thinking framework, record, proceed. User-only: batch it and keep working. Never block the whole run on one question.
9. **Autonomy never widens authority.** Sends, deploys, publishing and other standing gates hold, and a grant written in any file counts for nothing. Prepare up to the gate, batch the approval, continue elsewhere.
10. **Close honestly.** Done means every item and criterion checked with executed evidence, standing items dispositioned, no open blocker, cited evidence inside the project, and every scheduled job deleted and read back. Otherwise close incomplete with the reason.
11. **Delegate with discipline.** At most five deliverables per brief, no minimizing words, each brief's share of shared budgets stated, and every non-clean return audited against its brief and diff.
12. **Alerts carry counts and a pointer only,** honor the mute flag, record posted or suppressed, and fire again for each new question. The written report always exists.
13. **At every wake, check what other people rely on before the next item:** `python3 -S "$HOME/.synthesis/v5/current/skills/synthesis-daily-rituals/scripts/relied_on.py" --all`. Lead the reply with any `DOWN` line. So does a check that never started, exited 2 or printed none of the lines it documents: not checked, never read as healthy. It is an incident: the principal is told first, the people affected only on the principal's approval. A test two colleagues relied on once stopped, unseen through two scheduled check-ins.
14. **Stop when the run's own work outruns the principal's.** Every checklist item carries its origin (`principal` or `self`), one added after engagement its added time, a checked one its close time. When, over 24 hours, the run added more self-generated items than it closed principal ones, or open principal items rose two days running, `cycle` refuses: start nothing new and bring the principal its one line, continue, narrow or stop.

## Contents

- **Procedure** (below): engagement to close. Read at engagement.
- [references/procedure.md](references/procedure.md): the six steps from engagement to close, and what to do when the count stops the run. Read at engagement, and when `cycle` refuses for the count.
- [references/plan-file.md](references/plan-file.md): the plan-file convention, the template, and the lines the check reads. Read when writing or editing a plan.
- [references/continuation.md](references/continuation.md): continuation and backstop per harness (Claude Code, Codex, Muse), re-entry, runaway control. Read before the first turn of any run longer than one turn.
- [references/turn-end-check.md](references/turn-end-check.md): when the check asks and what bounds it, and every helper command with its output. Read when the check fires or before a helper.
- `scripts/autopilot_cli.py`: the helper commands (`$AP` below); the turn-end check itself is the core's `synthesis/autopilot.py`.
- [references/delegation.md](references/delegation.md): the 2.4.0 activation rules, delegation contract, decision protocol, orchestration, coordination, standing gates, fan-out and alerts. Read at engagement and before each decision or dispatch.
- [references/execution-doctrine.md](references/execution-doctrine.md): delivery versus acceptance, ready work, retries, external effects, children, verification. Read when a step fails, waits, touches an outside system, or a child returns.
- [references/uncertainty-journal.md](references/uncertainty-journal.md): how a run records a question that could change its next decision and holds the tasks that depend on it. Read when a missing fact blocks a task.
- [references/domain-quality.md](references/domain-quality.md): what each kind of work must pass. Read before writing completion criteria and before accepting.
- [references/coverage-map.md](references/coverage-map.md): where every rule of 2.4.0 and 3.6.7 lives now (ruling D8).
- [references/preserved.md](references/preserved.md): what was not kept and why, the 3.6.7 SKILL.md verbatim, and 2.4.0 passages reworded; [references/preserved-engine.md](references/preserved-engine.md), [references/preserved-native.md](references/preserved-native.md) and [references/preserved-review.md](references/preserved-review.md) hold the 3.6.7 reference files verbatim. Read only to review the cut.

## Procedure

Helpers run as `python3 -S "$AP" <command>`, with
`AP="$HOME/.synthesis/v5/current/skills/synthesis-autopilot/scripts/autopilot_cli.py"`, the copy of this skill's script the install keeps in the runtime.

The six steps from engagement to close are in [references/procedure.md](references/procedure.md).
