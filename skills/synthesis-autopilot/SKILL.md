---
name: synthesis-autopilot
description: "Run an explicitly delegated whole task to the end from a plan file in the project, unattended when needed. Use only on clear end-to-end delegation ('autopilot this', 'handle this end to end', 'run overnight'), never on a single-step approval or a talk about autonomy."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework", "synthesis-context-lifecycle", "synthesis-checkpoint", "synthesis-anti-shortcuts", "synthesis-grounding-discipline", "synthesis-implementation-integrity", "synthesis-project-management", "synthesis-adversarial-review", "synthesis-decision-packet", "synthesis-fact-checking", "synthesis-writing-craft", "synthesis-agent-conformance"]
metadata:
  author: "Rajiv Pant"
  version: "4.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
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

## Contents

- **Procedure** (below): engagement to close. Read at engagement.
- [references/plan-file.md](references/plan-file.md): the plan-file convention, the template, and the lines the check reads. Read when writing or editing a plan.
- [references/continuation.md](references/continuation.md): continuation and backstop per harness (Claude Code, Codex, Muse), re-entry, runaway control. Read before the first turn of any run longer than one turn.
- [references/turn-end-check.md](references/turn-end-check.md): when the check asks and what bounds it, and every helper command with its output. Read when the check fires or before a helper.
- `scripts/autopilot_cli.py`: the helper commands (`$AP` below); the turn-end check itself is the core's `synthesis/autopilot.py`.
- [references/delegation.md](references/delegation.md): the 2.4.0 activation rules, delegation contract, decision protocol, orchestration, coordination, standing gates, fan-out and alerts. Read at engagement and before each decision or dispatch.
- [references/execution-doctrine.md](references/execution-doctrine.md): delivery versus acceptance, ready work, retries, external effects, children, verification. Read when a step fails, waits, touches an outside system, or a child returns.
- [references/domain-quality.md](references/domain-quality.md): what each kind of work must pass. Read before writing completion criteria and before accepting.
- [references/coverage-map.md](references/coverage-map.md): where every rule of 2.4.0 and 3.6.7 lives now (ruling D8).
- [references/preserved.md](references/preserved.md): what was not kept and why, the 3.6.7 SKILL.md verbatim, and 2.4.0 passages reworded; [references/preserved-engine.md](references/preserved-engine.md), [references/preserved-native.md](references/preserved-native.md) and [references/preserved-review.md](references/preserved-review.md) hold the 3.6.7 reference files verbatim. Read only to review the cut.

## Procedure

Helpers run as `python3 -S "$AP" <command>`, with
`AP="$HOME/.synthesis/v5/current/skills/synthesis-autopilot/scripts/autopilot_cli.py"`, the copy of this skill's script the install keeps in the runtime.

1. **Engage.** Tell the user in one line: mode plus plan path. Anchor with synthesis-checkpoint, read the board and inbox, and claim what the run will write.
2. **Plan.** Write the plan in the project from the template, then `engage --plan <path>`. If the horizon passes this turn, set up and record the continuation and backstop now, and put the plan path and next item in CONTEXT.md's current-state block so compaction brings them back.
3. **Phase loop.** Re-read the plan and board; work with anti-shortcut discipline; decide by class; dispatch by the fan-out rules; record the wake with `cycle --advanced` or `--waiting-on`; update the plan; move cited scratch into the project; refresh CONTEXT.md and the session log.
4. **Wait or block honestly.** Nothing ready: `Status: waiting` with `Waiting on:`. Only the principal can unblock: record the blocker (with a probe for any missing capability), run `alert --kind blocked --count N`, note the outcome on the blocker, set `Status: blocked`, and keep the report in the plan.
5. **Verify.** Run synthesis-implementation-integrity or the domain's equivalent and fix what it finds.
6. **Close.** Delete every scheduled job and read the deletion back; `close --done`, or `--incomplete "<reason>"`; release claims; write the completion report; `alert --kind done`.
