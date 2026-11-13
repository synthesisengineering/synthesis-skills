# The rituals' order and commands

Read every time, before the ritual's own checklist. Everything from "`<rituals>` is this skill's
folder" to the paragraph about the launcher and the nudge was the Procedure section of SKILL.md
until v3.7.0 (2026-11-11) and moved here word for word, to make room there for a binding rule.
The last paragraph is new in v3.7.0. The paragraph before it, about what other people rely on, is
new in v3.10.0.

`<rituals>` is this skill's folder; `<W>` the workspace (its folder under `~/workspaces/`). Scripts run with plain `python3`, standard library only.

**Day-start** ([day-start.md](day-start.md)): `date`; `synthesis who`, `synthesis inbox`; `synthesis doctor`; `python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --root <knowledge root>` (exit 0 healthy, 1 defects, 2 cannot tell); `python3 <rituals>/scripts/portfolio_review.py` (at most three stale projects as decisions); `ritual_state.py query summary --workspace <W>` and `query weekly-review`; context optimization; `repo_state.py --workspace-root ~/workspaces/<W> --fetch --ff`; channel sync under the watermark gate (Slack, Chat via `gchat_preflight.py`, email via `mailboxes.py`, documents, meeting transcripts); inbox hygiene; catch-up read with ownership routing; `pr_queue_scan.py --workspace <W>`; the day plan with decay tags; morning messages; `ritual_state.py record --direction day-start`.

**Mid-day sync** ([mid-day-and-modes.md](mid-day-and-modes.md)): every declared surface, every target re-read, the same gate.

**Day-end** ([day-end.md](day-end.md)): ask f, q or o; final capture under the gate; source sync; integration sweep; tomorrow's calendar review; `decay_sweep.py` and the send-or-release pass with lapses recorded; lessons keep or drop, then `stray_lessons.py`; the native-memory sweep; `python3 <synthesis-agent-guardrails>/scripts/provenance_scan.py --since <today> <files written today>`; context capture with stamped open items `(as of YYYY-MM-DD, review Nd)`; `ritual_state.py record --direction day-end`; the weekly review if owed; then `synthesis handoff` per project worked, the records doctor with `--project`, and `repo_state.py --discover ~/workspaces/<W>` for anything stranded.

**Desk** (only with a workers registry): `python3 <rituals>/scripts/ritual_workers.py coverage` prints the coverage line that opens every brief.

Every script's exact command line, what it prints and its exit codes: [scripts.md](scripts.md).

The v5 install puts the `day-end` launcher (`day-end -q` opens a harness on the ritual) beside the runtime; `install.py --day-end` loads the weekday 16:55 nudge: one fixed banner unless every workspace expected to close today has closed.

**What other people rely on**, in every ritual and every mode: `python3 <rituals>/scripts/relied_on.py --workspace <W>` first, after the date at day-start Step 1, before any surface at each mid-day sync and before the mode question at day-end. **A `DOWN` line is the first thing in the plan and in the reply to the principal, before anything else,** the critical deadlines included. It is an incident, so the principal is told first, with who is affected and what the fix is, and the people affected are told only on the principal's approval. Exit 2, a run that never started, or one that printed none of the lines [scripts.md](scripts.md) documents means nothing was checked: that is reported first, in the same place, as not checked, and never read as healthy.

**Critical deadlines** ([critical-deadlines.md](critical-deadlines.md)), in every ritual: `python3 <rituals>/scripts/decay_sweep.py --as-of <today> --workspace <W> --alert` at day-start Step 1, at each mid-day sync and at day-end Step 4b. Whatever it lists as critical leads the brief and the plan, and a deadline first seen in the run is classified in that run. `ritual_state.py record` refuses while a critical deadline is past due and open.
