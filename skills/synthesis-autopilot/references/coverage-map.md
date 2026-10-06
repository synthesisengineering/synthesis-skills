# Coverage map: autopilot 2.4.0 and 3.6.7 to 4.0.0 (v5)

Ruling D8: every rule of the old text has a new home, or sits in a preserved
file with the reason. "Verbatim" means the old lines appear unchanged in the
named file. "Reworded" means the rule is kept in plain words there, and the
original wording is in the named preserved file. "Cut" means not carried; the
reason is in [preserved.md](preserved.md).

## Contents

- [Coverage check results](#coverage-check-results)
- [2.4.0 SKILL.md](#240-skillmd)
- [2.4.0 scripts](#240-scripts)
- [3.6.7 SKILL.md](#367-skillmd)
- [3.6.7 reference files](#367-reference-files)
- [Evaluation scenarios and where each is held](#evaluation-scenarios-and-where-each-is-held)
- [Changes after 4.0.0](#changes-after-400)

## Coverage check results

Run on 2026-10-05 from the v5 worktree:

```text
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-autopilot
synthesis-autopilot: 2682 old lines, 0 not found verbatim
$ python3 v5-skill-coverage-check.py <v5 worktree> synthesis-autopilot ca5c6bb
synthesis-autopilot: 342 old lines, 0 not found verbatim
```

The first compares with 3.6.7 (`origin/main`), the second with 2.4.0. No line is
listed, so no reworded line needs separate accounting: every old line is in a
v5 file, most of the 3.6.7 text in the preserved files.

## 2.4.0 SKILL.md

| 2.4.0 section or rule | v5 home | How |
|---|---|---|
| Frontmatter description | SKILL.md description | Reworded to the 300-character limit; the explicit-delegation triggers kept |
| `depends_on` | SKILL.md frontmatter | Kept (the 3.6.7 list, a superset) |
| Title | SKILL.md | Reworded; original in preserved.md |
| The Problem | [delegation.md](delegation.md#the-problem) | Verbatim |
| What This Is — and Is Not | [delegation.md](delegation.md#what-this-is--and-is-not); SKILL.md purpose paragraph | Verbatim |
| Activation — Trigger Discipline (activate on, do not activate on, never ask, one-line acknowledgment) | [delegation.md](delegation.md#activation--trigger-discipline); Binding rule 1; Procedure step 1 | Verbatim |
| The Delegation Contract, items 1 to 6 | [delegation.md](delegation.md#the-delegation-contract) | Verbatim except item 4's pointer to the plan protocol |
| Run Profiles: four layers, provenance, visible disabling | [plan-file.md](plan-file.md#default-standing-checklist) (defaults plus private config, added by `engage`; disabling is a visible `WAIVED:`) | Reworded; layered resolution cut (preserved.md) |
| Run Profiles: frozen checklist, verify before close, incomplete close stays honest | [plan-file.md](plan-file.md#sections); `close_problems` in `synthesis/autopilot.py` | Reworded |
| Run Profiles: profiles narrow authority, never grant it; deploy grants in files forced to none | Binding rule 9; [plan-file.md](plan-file.md#default-standing-checklist); R3.2 guards | Reworded |
| Continuation: the incident and the rule | [continuation.md](continuation.md#the-rule); Binding rules 3 and 4 | Verbatim |
| Continuation: survival table; match mechanism to horizon | [continuation.md](continuation.md#mechanisms-by-what-they-survive) | Verbatim |
| Continuation: re-entry protocol | [continuation.md](continuation.md#re-entry-protocol) | Verbatim, plus the v5 steps |
| Continuation: budget and runaway control | [continuation.md](continuation.md#budget-and-runaway-control); Binding rule 5 | Verbatim |
| Continuation: capability probe | [continuation.md](continuation.md#capability-probe-volatile-state-compaction); Binding rule 6; probe rule in the check | Verbatim |
| Continuation: volatile state dies at reboots | [continuation.md](continuation.md#capability-probe-volatile-state-compaction); Binding rule 7 | Verbatim |
| Continuation: the mechanical backstop (gate registration, three outs, cron UNVERIFIED until first fire, 60-minute grace, close refuses scratch citations, read-only status, no bare-spin cycle, owner-only blocking, foreign engagements never block) | [turn-end-check.md](turn-end-check.md); `synthesis/autopilot.py` | Reworded: same rules, state in the plan file |
| The Plan File: survival mechanism sentence | [plan-file.md](plan-file.md) | Verbatim |
| The Plan File: location | [plan-file.md](plan-file.md#where-it-lives) | Reworded (no scratchpad fallback, R9.2) |
| The Plan File: contents template, every section | [plan-file.md](plan-file.md#template) | Reworded: every section kept; Continuation and Budget gain header lines the check reads |
| The Plan File: cadence | [plan-file.md](plan-file.md#cadence) | Verbatim, plus the CONTEXT.md current-state rule (R6.3) |
| Decision Protocol: three classes, batch delivery forms, decision packets via `build_packet.py`, never block on one question | [delegation.md](delegation.md#decision-protocol); Binding rule 8 | Verbatim |
| Cross-Agent Orchestration: direct dispatch, evidence package, acceptance audit | [delegation.md](delegation.md#cross-agent-orchestration) | Verbatim |
| Cross-Agent Orchestration: handoff queue | [delegation.md](delegation.md#cross-agent-orchestration) | Reworded to board messages |
| Cross-Agent Orchestration: provider boundary, courier crossings, scope-time dispatch, proportionality, sufficiency ruling, bounded control depth | [delegation.md](delegation.md#cross-agent-orchestration) | Verbatim |
| Multi-Session Coordination: poll the board and own triage; claim before writing, narrow before peer landings; shared mutations drain first | [delegation.md](delegation.md#multi-session-coordination) | Verbatim |
| Multi-Session Coordination: mechanics pointer; cross-harness handle | [delegation.md](delegation.md#multi-session-coordination) | Reworded to the v5 `synthesis` command and session ids |
| Multi-Session Coordination: long runs schedule a backstop | [continuation.md](continuation.md#the-backstop-is-visible-and-stoppable) | Verbatim |
| Standing Gates Survive Autonomy | [delegation.md](delegation.md#standing-gates-survive-autonomy); Binding rule 9 | Verbatim |
| The Execution Loop, steps 1 to 7 | [delegation.md](delegation.md#the-execution-loop); SKILL.md Procedure | Steps 2 and 6 verbatim; 1, 3, 4, 5, 7 reworded to v5 helpers |
| The Execution Loop: closing scratchpad sweep | [delegation.md](delegation.md#the-execution-loop) | Verbatim |
| Sub-Agent Fan-Out Hygiene, rules 1 to 3 | [delegation.md](delegation.md#sub-agent-fan-out-hygiene); Binding rule 11 | Verbatim |
| Sub-Agent Fan-Out Hygiene, rule 4 (search budget) | [delegation.md](delegation.md#sub-agent-fan-out-hygiene) | Reworded: the share is a line in each brief |
| Completion and Blocked-State Alerts: confidentiality, mute flag, report with every alert | [delegation.md](delegation.md#completion-and-blocked-state-alerts); Binding rule 12; `alert` helper | Verbatim, plus delivery states |
| Domain Neutrality | [delegation.md](delegation.md#domain-neutrality) | Verbatim |
| Composed Skills table | [delegation.md](delegation.md#composed-skills) | Verbatim |

## 2.4.0 scripts

| Rule | v5 home | Test |
|---|---|---|
| `autopilot_gate.py register`: mission required, binding to session and project, claim covers the plan | `engage` (checklist, criteria, horizon required; board claim on the plan) | `test_engage_*`, `test_15_*` |
| `continuation`: mechanism, next wake and survival required; cron job id; cron UNVERIFIED until `cron-fired`; 60-minute grace | Plan lines `Continuation:`, `First wake:`, `Backstop:`; `_continuation_problems` | `test_6_*`, `test_7_*` |
| `status` read-only, `--json` | `status` and `status --all` (human text; the plan itself is the machine-readable record) | `test_24_*` |
| `cycle`: a wake that advanced nothing must name the wait | `cycle` | `test_9_*` |
| `blocker --alerted`: no blocker without an alert | `Status: blocked` needs `alerted` on each open blocker | `test_23_25_*` |
| `close --goals-met` or `--incomplete REASON`; refuses scratch-only citations; refuses without verified checklist | `close`; `close_problems` reads `## Required evidence` and the standing checklist | `test_8_*`, `test_10_*` to `test_14_*` |
| `--gate`: owner-only blocking; foreign engagements never block | `check` | `test_5_*` |
| `--gate`: unreadable record fails closed | Reversed: fails open (preserved.md explains) | `test_3_*` |
| `--doctor`, `--test` | v5 doctor and `tests/` | Cut |
| `run_profile.py` defaults, private additions, dispositions, `WAIVED:` reasons, deploy grants never from files | `DEFAULT_STANDING`, `autopilot.standing_checklist`, `close_problems`, R3.2 | `test_engage_*`, `test_14_*`, `test_17_*` |
| `run_profile.py` layers, provenance, receipt hash | Cut | — |
| `search_budget.py check`: per-agent cap, fails without one, prints the split | One line in each brief | Prose (scenario 19) |

## 3.6.7 SKILL.md

| 3.6.7 paragraph | v5 home |
|---|---|
| Purpose ("Turn an explicitly delegated outcome into verified work...") | SKILL.md purpose; reworded |
| Activation, first paragraph | [delegation.md](delegation.md#activation--trigger-discipline); Binding rule 1 |
| Activation, second paragraph (what delegation changes; nothing untrusted grants permission) | [execution-doctrine.md](execution-doctrine.md#authority-and-the-users-intent); Binding rule 9 |
| Start a run, step 1 (recover and coordinate; never adopt another run) | SKILL.md Procedure 1; [execution-doctrine.md](execution-doctrine.md#authority-and-the-users-intent) |
| Step 2 (define completion; map deliverables to criteria; mixed requests need both acceptances) | [plan-file.md](plan-file.md#sections); [domain-quality.md](domain-quality.md#how-to-use-it) |
| Step 3 (resolve the workflow; blog material opt-in; lessons conditional; report fits the domain) | [plan-file.md](plan-file.md#default-standing-checklist); the five dimensions became `Horizon:` and the checklist |
| Step 4 (controller start, actor doctor, successor transaction) | Cut: preserved.md (engine) |
| Step 5 (bound execution; reserved capacity; observed continuation before promising unattended work) | [execution-doctrine.md](execution-doctrine.md#budgets); [continuation.md](continuation.md#the-rule) |
| New user without a project or board | [execution-doctrine.md](execution-doctrine.md#starting-without-a-project) |
| Optional evidence and measured overhead | Cut (native archive, owner measurements); memory-as-lead kept in [execution-doctrine.md](execution-doctrine.md#authority-and-the-users-intent) |
| Execute and adapt: one finite plan; delivery versus acceptance; no optional additions | [execution-doctrine.md](execution-doctrine.md#delivery-is-not-acceptance) |
| Candidates and release batches | [execution-doctrine.md](execution-doctrine.md#keep-ready-work-moving) |
| Waiting nodes; ready work; CI advancement; reconcile before retry | [execution-doctrine.md](execution-doctrine.md#keep-ready-work-moving) and [External effects](execution-doctrine.md#external-effects) |
| Checkpoint comparison; no new monitor; waits keep deadlines; amendments need approval | [execution-doctrine.md](execution-doctrine.md#keep-ready-work-moving), [Delivery is not acceptance](execution-doctrine.md#delivery-is-not-acceptance) |
| Decisive-uncertainty method | [execution-doctrine.md](execution-doctrine.md#verification-and-review) |
| Controller operations and request identities | Cut: preserved.md (engine) |
| At every checkpoint: board and inbox; verify artifacts; record outcomes or waits; retry allowance; consume new instructions; persist scripts and inputs; record facts and risks | [delegation.md](delegation.md#multi-session-coordination); [execution-doctrine.md](execution-doctrine.md); [continuation.md](continuation.md#capability-probe-volatile-state-compaction); the cycle ledger |
| Scratchpad question at each boundary | [delegation.md](delegation.md#the-execution-loop) (verbatim in 2.4.0's close step); Binding rule 7 |
| Shared install trees and inventories need the coordination protocol | [delegation.md](delegation.md#multi-session-coordination) ("Shared mutations drain first") |
| Decisions and delegation: decision ownership; batch human-only items; packets via `build_packet.py`; prepare the artifact before asking | [delegation.md](delegation.md#decision-protocol); [execution-doctrine.md](execution-doctrine.md#authority-and-the-users-intent) |
| Delegation briefs, budget reservation, search helper | [execution-doctrine.md](execution-doctrine.md#delegated-children), [Budgets](execution-doctrine.md#budgets); [delegation.md](delegation.md#sub-agent-fan-out-hygiene) |
| Immutable inputs; write boundaries; native worker observer | [execution-doctrine.md](execution-doctrine.md#delegated-children) (diff check, never edit global config); observer cut |
| Working as a delegated child | [execution-doctrine.md](execution-doctrine.md#working-as-a-child) |
| Session addressing and handoff queue | [delegation.md](delegation.md#cross-agent-orchestration) (board messages) |
| Inspect partial, failed, cancelled returns | [execution-doctrine.md](execution-doctrine.md#delegated-children); Binding rule 11 |
| Verify outcomes: domain acceptance, PASS/FAIL/UNKNOWN, independence | [domain-quality.md](domain-quality.md); [execution-doctrine.md](execution-doctrine.md#verification-and-review) |
| Receipts bound to run and hashes; `method: artifact` | Cut (journal); "never certify by writing verified" kept in [execution-doctrine.md](execution-doctrine.md#verification-and-review) |
| Integrity before completion; one adversarial review per package; no review restarts; no recursive controls | [execution-doctrine.md](execution-doctrine.md#verification-and-review) |
| Wait, stop and recover: observed continuation; first and later wakes; never invent a scheduler | [continuation.md](continuation.md#a-continuation-is-observed-not-assumed) |
| Waits resolved explicitly; user-only blocker alert; delivery states; generic alerts; mute | [execution-doctrine.md](execution-doctrine.md#waits-questions-and-alerts); Binding rule 12; `alert` |
| Stop boundary: one correction per condition; productive work does not spend retries; renames do not reset; unknown effects reconciled; failures end feedback explicitly | [turn-end-check.md](turn-end-check.md#what-bounds-it); [execution-doctrine.md](execution-doctrine.md#retries-what-counts-as-a-new-attempt) |
| Capsule and cold-resume protocol; supervision | Replaced by the plan file and session-start re-injection ([plan-file.md](plan-file.md#cadence)); supervision cut |
| Completion needs a current read-back; closure postamble | [execution-doctrine.md](execution-doctrine.md#closing); postamble cut |
| Close steps 1 to 5 | [execution-doctrine.md](execution-doctrine.md#closing); Binding rule 10; `close` |
| Reference routing; dependency ownership paragraph | SKILL.md Contents; [delegation.md](delegation.md#composed-skills) |

## 3.6.7 reference files

Each file is verbatim in the preserved file named; the kept doctrine is listed in
[preserved.md](preserved.md#the-367-reference-files) per file. By section:

| File: sections | Kept in | Rest |
|---|---|---|
| clients-and-recovery.md: surface table | [continuation.md](continuation.md) (Claude Code, Codex, Muse only) | preserved-native.md |
| clients-and-recovery.md: native worker capabilities | [execution-doctrine.md](execution-doctrine.md#delegated-children) (write boundaries need evidence; timeouts keep partial evidence) | preserved-native.md |
| clients-and-recovery.md: Stop behavior | [turn-end-check.md](turn-end-check.md#what-bounds-it) | preserved-native.md |
| clients-and-recovery.md: continuation is observed | [continuation.md](continuation.md#a-continuation-is-observed-not-assumed) | Lease renewal and receipt rules: preserved-native.md |
| clients-and-recovery.md: waits and human visibility | [execution-doctrine.md](execution-doctrine.md#waits-questions-and-alerts) | — |
| clients-and-recovery.md: diagnosis and migration; Codex managed permissions; protected turns; Claude context records; source doctor; bounded replay; protected work after recovery | — | preserved-native.md |
| controller.md: all sections | — | preserved-engine.md |
| domain-quality.md: family contracts; rubric rules; evidence limits | [domain-quality.md](domain-quality.md) | Rubric schema, calibration manifest, interfaces: preserved-review.md |
| efficiency-measurement.md | — | preserved-engine.md |
| evaluation.md: all sections | — (milestone M7) | preserved-review.md |
| journal-storage.md | — | preserved-engine.md |
| muse-launch-protocol.md | [continuation.md](continuation.md#muse) for Muse facts | preserved-native.md |
| native-adapter-sdk.md | — | preserved-native.md |
| native-worker-persistence.md | — | preserved-native.md |
| operator-experience.md: status, questions, handoffs | [turn-end-check.md](turn-end-check.md#helper-commands) (`status --all`) | preserved-engine.md |
| owner-resume.md | [plan-file.md](plan-file.md#ownership-and-takeover) | preserved-engine.md |
| portable-native-evidence.md: memory is a lead | [execution-doctrine.md](execution-doctrine.md#authority-and-the-users-intent) | Archive sections: preserved-native.md |
| run-contracts.md: required citations and durable closure | [plan-file.md](plan-file.md#sections) (Required evidence); `evidence_problems` | Inputs, commands, evidence, import: preserved-engine.md |
| successor-transactions.md | — | preserved-engine.md |
| supervision.md | [continuation.md](continuation.md#the-backstop-is-visible-and-stoppable) (visible backstop) | preserved-engine.md |
| workflow-and-evidence.md: defaults; graph; dispatch; attempts; resource accounting; progress; consumer checks; domain quality; effects; search reservation | [execution-doctrine.md](execution-doctrine.md); [delegation.md](delegation.md#sub-agent-fan-out-hygiene) | Command payloads and adapters: preserved-review.md |

## Evaluation scenarios and where each is held

Numbers are section 3 of the v5 code evaluation for autopilot. Tests are in
`tests/test_autopilot.py` unless named otherwise.

| # | Scenario | Held by |
|---|---|---|
| 1 | Owned running plan, nothing recorded: block once, name what is missing | `test_1_*` |
| 2 | Repeat flag: stop with a note, no further block | `test_2_*` (three in a row; unchanged plan counts; configurable) |
| 3 | Crash or bad input: never another turn | `test_3_*` |
| 4 | No plan or unknown client: nothing, fast | `test_4_*`, `test_the_check_takes_well_under_50_ms`, `test_a_cold_hook_process_*` |
| 5 | Another session's plan never blocks | `test_5_*` |
| 6 | Scheduled continuation without an observed first wake after 60 minutes is none | `test_6_*` |
| 7 | Overnight horizons need a mechanism that outlives the session | `test_7_*`; [continuation.md](continuation.md) |
| 8 | Close deletes every job with read-back; late wakes do nothing | `test_8_*` |
| 9 | No bare spin | `test_9_*` |
| 10 | Scratch or missing evidence refuses done; incomplete still works | `test_10_*` |
| 11 | Prose, fenced and commented paths do not block | `test_11_*` |
| 12 | Missing plan or no criteria refuses done | `test_12_*` |
| 13 | A blocker stays open until resolved | `test_13_*` |
| 14 | Standing item added mid-run needs a disposition | `test_14_*` |
| 15 | Second writer refused | `test_15_*`; `tests/test_commit_check.py` for commits |
| 16 | Silent owner taken over, items kept | `test_16_*` |
| 17 | Deploy grant in a file grants nothing | `test_17_*`; `tests/test_guards.py` |
| 18 | Only the principal's own prompt approves | `tests/test_guards.py` (R3.0) |
| 19 | Each research brief states its search share | [delegation.md](delegation.md#sub-agent-fan-out-hygiene) (prose) |
| 20 | Partial child returns are audited | [execution-doctrine.md](execution-doctrine.md#delegated-children) (prose) |
| 21 | Unknown external outcomes are read back before retry | [execution-doctrine.md](execution-doctrine.md#external-effects) (prose) |
| 22 | Renaming does not reset retries | [execution-doctrine.md](execution-doctrine.md#retries-what-counts-as-a-new-attempt) (prose) |
| 23 | Alerts: counts only, mute honored, suppressed recorded, one per question | `test_23_*` |
| 24 | Status shows open questions without the harness pane | `test_24_*` |
| 25 | Capability claims carry a probe | `test_23_25_*` |
| 26 | Child diff touches only its declared paths | [execution-doctrine.md](execution-doctrine.md#delegated-children) (prose) |
| 27 | Never edit global harness configuration | [execution-doctrine.md](execution-doctrine.md#delegated-children); [continuation.md](continuation.md#a-launchd-backstop-for-any-harness) (prose) |
| 28 | Low context: continue and rely on re-injection | [continuation.md](continuation.md#capability-probe-volatile-state-compaction); `test_session_start_brief_*` |
| 29 | Software acceptance rests on executed checks | [domain-quality.md](domain-quality.md); criteria need evidence (`test_12_*`) |
| 30 | Old engagement records are never read | `test_30_*` |

## Changes after 4.0.0

**2026-10-05: the helper commands moved out of the core.** The commands an agent
runs by hand (`engage`, `status`, `cycle`, `close`, `alert`, `wake-prompt`,
`takeover`, with `set_field`, `append_to_section`, `DEFAULT_STANDING` and the alert
text) moved from the core's `synthesis/autopilot.py` to this skill's
`scripts/autopilot_cli.py`, following the plugin's rule that code a hook or the
`synthesis` CLI needs lives in `synthesis/` and code an agent runs from a skill
lives in the skill. The core keeps what the Stop and SessionStart hooks call
(`check`, `evaluate`, `brief`) and the plan reader they use (`Plan`, `load`,
`close_problems`, `evidence_problems`, the continuation and backstop checks,
the pointer files); the script imports those from it. The install copies the
script into the runtime (`STABLE_SKILL_SCRIPTS` in `synthesis/install.py`), so
`$AP` in [SKILL.md](../SKILL.md), [continuation.md](continuation.md),
[turn-end-check.md](turn-end-check.md#helper-commands) and
[plan-file.md](plan-file.md) now names that copy. The blocked-run request and the
wake prompt name `autopilot_cli.py`. No rule changed. Every test in
`tests/test_autopilot.py` still holds; it runs the commands from the script, and
`test_the_documented_helper_path_is_the_copy_the_install_makes_and_it_runs` checks
that every documented `$AP` path is the installed copy and that it runs from there.

**2026-10-05, final v5 sweep: dated notes in the preserved files.** Two passages in
[preserved.md](preserved.md) described the deletion of the 3.6.7 scripts as still to come
(the muse-launch-protocol row: the JSON "stays beside these files only because the old
scripts' tests read it"; and "3.6.7 `scripts/` (51 modules): left in place"), and
[preserved-native.md](preserved-native.md) links the deleted `muse-launch-protocol.json`.
Each gained a dated note saying the files are gone and how to read them at release
`v4.154.12`; the preserved text itself is unchanged. SKILL.md is unchanged.
