# Daily rituals — version history and rationale

The operating checklists live in [SKILL.md](../SKILL.md). This file keeps the
release-by-release record of why each rule exists — the incidents, the
design choices, the config schemas each version introduced — so the main
document can stay within the repository's 500-line budget without losing
the reasoning. Newest first.

## v2.34.0 — Google Chat gets a declared target set; wholesale advance is refused

v2.34.0 (2026-09-02): the fifth sync defect from the field. A surface-level
watermark on the Chat surface recorded coverage that no per-space read
backed, and a colleague's four DMs asking to schedule a meeting went
unsurfaced through two syncs and a day-end. `scripts/gchat_preflight.py`
now derives the declared set — the config's explicit, labeled `targets`
plus the saved enumeration filtered client-side and marked BOUNDED when the
wrapper's page cap or a short page makes completeness unprovable — and
`sync_watermark.py advance` refuses a surface-level write on a surface that
carries per-target entries unless `--surface-level` asserts it. The
enumeration's defects (text output, an ignored type filter, no paging
cursor, undocumented order, every DM shown as "Unnamed Space") are stated
in the script and in references/sync-watermarks.md; the missing cursor is
an upstream wrapper defect to file, not a thing to design around silently.

## v2.33.0 — Placeholders resolve under the stable plugin path; parity checks the pointer

v2.33.0 (2026-09-01): SKILL.md says where every `<…-root>` placeholder
resolves on a machine provisioned by the gated release
(`~/.synthesis/plugins/synthesis-skills/current/skills/`) and that Day-Start
Step 1's parity check now fails when that pointer is missing, dangling, or
behind the installed version. Origin: a workspace's own day-start commands
had pinned a release twenty versions behind, and a session on a stale
cached engine read the shared board as corrupt.

## v2.32.0 — The watermark gate's declared set comes from the preflight script

v2.32.0 (2026-09-01): Day-Start 3b, Day-End 1, and the Mid-Day protocol
take `--targets-from` from the file synthesis-slack-sync's `preflight.py
--json --out` writes during the run, so the declared set has one source
(the sync config) and one resolver (the script), never a hand-maintained
copy.

## v2.31.0 — Restructured under the 500-line budget

v2.31.0 (2026-09-01) moves version history, plan formats, draft-grounding
detail, and rationale out of SKILL.md into `references/` (this file,
`plan-format.md`, `draft-grounding.md`), leaving every operating rule and
checklist step in the main document. A pinned test
(`scripts/test_skill_documents.py`) fails when SKILL.md reaches 500 lines,
when a load-bearing rule anchor leaves it, when a moved block is missing
from its reference, or when a reference is not linked from the main
document. Nothing in the protocol changed.

## v2.30.0 — Watermarks carry a time and a target, and a run proves its own coverage

v2.30.0 (2026-09-01) fixes what a day-granular watermark could not see: a
surface written at 09:15 counted as current for the rest of the day, so a
mid-day pass that re-read only what the morning had skipped let the
morning's own reads go stale — and an "unanswered" claim at 17:51 rested on
a 09:15 read while the answer had gone out at 09:27. Four defects, one
mechanism: watermarks are ISO-8601 timestamps (the last moment actually WRITTEN,
never the last attempted); a surface carries one watermark per
declared read target; `begin` stamps a run and
`status --since run` exits non-zero on every declared surface or target not
re-read during THIS run; and `window` echoes human-readable bounds beside
the epoch `oldest` a read call takes — a window parameter is a claim about
time and is computed, not typed. Every sync re-reads every declared target:
"already read today" is a statement about the past. Contract, store, and
rationale: [references/sync-watermarks.md](references/sync-watermarks.md).

## v2.27.0 — Sync windows follow the last write, and a recorded gap blocks

v2.27.0 (2026-08-27) replaces run-anchored sync windows with per-surface
watermarks, and makes a recorded gap something a later run must act on.

**The defect.** A window anchored on when the previous run *executed* cannot see
its own holes. Skip a run and the hole it leaves is never revisited, because the
next window starts at now-minus-a-bit rather than at the last day actually
written to disk. Nothing persisted "the mirror is complete through date X", so
no run could detect what it had missed. Compounding it, the `gaps` field was
honest and completely inert: writing a gap and closing a gap are different acts,
and nothing forced the second. A gap was recorded in three consecutive artifacts
and no run ever read those lines back.

**The rule.** Each surface carries a watermark — the last date actually
WRITTEN, never the last date attempted — in `~/.synthesis/sync-watermarks/`,
managed by `scripts/sync_watermark.py`:

- every sync computes its window from the watermark, so a hole is revisited
  automatically and nobody has to notice it;
- the watermark advances only after a successful write, so a run that fetches
  nothing, errors, or is interrupted cannot declare the day covered;
- `sync_watermark.py status --workspace W` exits non-zero while any surface has
  an unclosed gap. Run it in Day-Start Step 3 and Day-End Step 1. An open gap is
  closed this run or deferred with an explicit reason, and a deferral lasts one
  working day — an indefinite silence is how a recorded gap becomes furniture.

Surfaces are tracked independently: one surface closing never vouches for
another, which is the completeness claim that hid the original gap.

**The general lesson, worth more than the fix.** Detection that nothing consumes
changes nothing. The gap field was accurate every time it was written; what was
missing was any mechanism that read it back. When adding a check, ask what
consumes its output and what happens when the answer is bad — a finding with no
consumer is a note to self.

## v2.26.0 — Lead-time meeting preps: high-stakes meetings get prepared a business day ahead

Same-day prep packs (v2.12.0) are right for routine meetings and structurally wrong for
high-stakes ones: a strategy-bearing 1:1 prepared minutes before it starts gets a summary of
what the *agent* has been processing lately, not what the *counterpart* cares about —
recency bias with a deadline. The origin incident: an exec weekly was rescheduled onto the
current day, prep was requested sixteen minutes before the start, and the first draft led
with the week's loudest workstream instead of the principals' stated mandate; there was no
time to research either half. Preparing one business day ahead is what allows reading the
prior meeting's transcript, checking the mandate sources, and thinking strategically.

A workspace opts in by declaring **`.agents/meeting-preps.yaml`**:

```yaml
# .agents/meeting-preps.yaml — lead-time prep declarations (v1)
lead_time_preps:
  - name: exec-weekly            # slug used in the prep-pack filename
    title_contains: "Weekly - Principal and Exec"   # calendar title match (case-insensitive)
    attendees_any: [exec@example.com]               # OR-matched; either matcher may be omitted
    business_days_ahead: 1
    sources:                     # what the prep MUST be built from (the durable record)
      - prior-meeting-transcript # open loops and commitments from last time
      - mandate-sources          # the documents/transcripts where this person stated their priorities
      - project-contexts         # CONTEXTs naming the attendee or the meeting's subjects
```

Four rules, enforced by the ritual steps below:

1. **Generation is owed at the day-end BEFORE the meeting's business day** (Step 4a) — the
   Calendar Guardian's tomorrow-review already looks at the right day in every mode
   including Quick Close, so the prep rides the review that is already mandatory. Day-Start
   Step 6 verifies presence for today's flagged meetings and regenerates stale packs; the
   owed-weekly week-ahead scan flags any flagged meeting in the coming week so multi-day
   research can start early.
2. **A reschedule triggers an immediate refresh at detection time.** A flagged meeting that
   MOVES onto today or tomorrow does not wait for the next ritual — whichever sync detects
   the move regenerates the prep then. Reschedules are precisely when prep is most likely
   to be stale and most likely to be skipped.
3. **Prep is built from the durable record, not from session memory.** The declared
   `sources` are read fresh: the prior meeting's transcript for open commitments, the
   counterpart's own stated priorities from mandate sources, and project state. The
   structural point of the lead time is that this reading takes longer than the minutes
   before a meeting provide — a prep that skips the sources has not used the lead time.
4. **The pack states its own basis.** Its header lists which declared sources were read and
   the date of the newest one, so a reader can tell a researched pack from a summary of
   recent activity. The v2.12.0 file contract (path, filename, H1/When/Who) is unchanged —
   this section governs *when* and *from what*, not the format.

Workspaces without the config keep v2.12.0 behavior unchanged.

## v2.25.0 — Per-workspace sessions are the default; the principal is the dispatcher

Distributed execution keeps the desk/worker split and the artifact contract, and corrects
which worker mode is assumed. **The default is now an attended session rooted in each
workspace, run on that workspace's own schedule** — the mode that matches where the
principal is actually working, with the right directory, claims, and context. Desk-
dispatched subagents demote to an opt-in for deliberately closing everything from one place.

Two rules are made explicit because their absence invited a design that cannot work.
**The principal is the dispatcher:** no session can start work in another, so the desk
reports which workspaces are owed and the human opens the one that owes. **The desk never
nudges, triggers, blocks on, or waits for a worker:** it folds what exists and reports the
rest as not covered, so a desk pass is always complete on its own terms.

Origin: a desk that tried to trigger workers by messaging their sessions went 0 for 2 —
once to a session stale by two hours, once with no reachable session at all — while the
artifact path delivered both times. Session messaging is a relay between humans at
keyboards, not a dispatch primitive; depending on it relocates multi-session overhead
rather than removing it. Independent close times per workspace are likewise now stated as
normal operation, which the timestamped artifact schema already supported. Detail:
`references/ritual-worker-contract.md`.

## v2.24.2 — The shell keeps the consumer's section vocabulary

Separating plan storage changes where content lives, not what the sections are called.
Renderers classify plan sections by heading vocabulary, so a shell written with invented
headings renders as undifferentiated prose while every typed region the reader works from
comes up empty — the plan looks blank exactly when it is full. Shells reuse the
established headings for any region they populate and confine novelty to the coverage
block and pointer lines; producer and consumer change together or not at all. Detail and
origin incident: `references/ritual-worker-contract.md` ("Plan storage separation").

## v2.24.1 — Fragment placement and consumer obligations

Clarifies two points in the plan-separation contract that adopters hit immediately: a
workspace's fragment belongs in the individual's **private** repository (not the
organization-shared one) when a workspace carries both, and a consumer that merges
fragments for display must never cache merged output back into the person-side store and
must render an unresolved pointer as an explicit marker rather than dropping it.

## v2.24.0 — Plan storage separation: workspace fragments, person-side shell

Organizational data must be erasable by deleting the organization's workspace folders —
a hard requirement in regulated environments (banks, government, contract exits) and good
hygiene everywhere. The daily plan therefore stops copying workspace content into the
person-side repository: **the worker artifact doubles as that workspace's plan fragment**
(it already holds the plan-facing sections, in the workspace-private repo), and the
person-side plan becomes a **shell** — coverage line, the principal's own timeline,
minimal cross-workspace conflict references, the permanent personal section, and pointer
lines to fragments. Consumers merge at display time; presentation stays converged
("one brief") while storage separates. The erasure boundary and the strict-shell option
for title-level erasure are specified in
[`references/ritual-worker-contract.md`](references/ritual-worker-contract.md) ("Plan
storage separation"). Pre-existing mixed plan files are left to a deliberate migration.

## v2.23.0 — Distributed ritual execution: desk and workers

The ritual can now fan its sync labor out per workspace while its output stays singular.
One seat — the **desk**, the ritual's home — frames the day and produces the single brief;
each workspace runs its labor as a **worker** that writes a structured summary artifact to
a declared path, and the desk folds artifacts instead of loading workspace detail inline.
Workers never message the desk: **worker→file, desk→file** — an artifact survives whether
or not anyone was listening, and a missing artifact is itself the legible "not covered"
signal. The full schema, path convention, registry format, desk obligations, and failure
semantics live in [`references/ritual-worker-contract.md`](references/ritual-worker-contract.md);
the operative rules are in "Distributed ritual execution" below. Every brief now carries a
mandatory **coverage line**. Design record: the ritual-home seat's 2026-08-11 distributed-
ritual-architecture artifact (decisions: output never distributes; fan out execution,
converge presentation).

## v2.22.0 — Local continuity during the day; remote readiness at day-end

Routine turns, day-start, and mid-day sync keep the filesystem-backed project
record current and rely on session-attributed local receipts. They do not
create Git commits or network pushes merely to switch Claude Code and Codex on
one machine. Day-end is the batched cross-machine publication boundary: it
publishes owned source work under repository policy, flushes exact private
project-context paths, runs remote-mode doctor and conformance, and verifies
remote heads. An interrupted task remains locally recoverable from its edit
manifest even when Stop never ran.

## v2.21.0 — Inbox hygiene joins the morning sync, scoped to the seat

Day-Start gains Step 3d: when `~/.synthesis/inbox-cleanup/scopes.yaml` exists,
the ritual resolves which accounts this workspace's seat may sweep (personal
seat: all; client seat: its own only — the inbox-cleanup skill's v1.5.0
workspace-scope contract) and runs the sweep dry-run-first. Unknown workspace
or missing config stops the step loudly; sweep results always name the scope
("7 of 9 in scope, 7 swept") so partial can never impersonate complete.

## v2.20.0 — Calendar Guardian: the rituals hold a perimeter around the calendar

Three additions, all cadence for the chief-of-staff skill's new **Calendar
guardian** doctrine (which owns the protocols; these steps own the schedule):
Day-End Step 4a reviews the next working day (plus the weekend on the last
working day of the week) and places id-tracked, auto-expiring holds over
tomorrow's open windows — in every mode including Quick Close, because it
generates the drafts Step 4 then handles. Day-Start Step 6 re-verifies the
morning against overnight arrivals and refreshes the same-day shield. The
owed-weekly review (Step 10) gains the week-ahead and month-ahead horizons; the
month pass is what starts absence-notification clocks while notifying is still
early and cheap. Requires `calendar_guardian` keys in the chief-of-staff
private config; without them the steps report "unconfigured" rather than
guessing thresholds.

## v2.19.0 — Every sync covers every configured surface (email + meeting transcripts + document comments join Slack/Chat)

v2.19.0 (2026-08-09) extends the complete-surface principle from v2.17.0 to its conclusion: a sync request — Day-Start Step 3, the Mid-Day Sync Protocol, or Day-End Step 1 — covers ALL surfaces the workspace routinely syncs, not only the chat surfaces. The declared set: Slack (always), Google Chat (`.agents/gchat-sync.yaml`), **email** (established `transcripts/email/` practice or explicit config), **meeting transcripts** (`.agents/meeting-transcripts.yaml` — any meeting ended in the window), and **document comments** (established `transcripts/docs/` practice or explicit config). The surface set is a declared list exactly like the repo list in the source-code sync — the agent does not re-apply its own judgment about which surfaces feel active (the v2.12.1 rule, applied to channels). A sync that runs fewer surfaces than the declared set must name the omission explicitly in its report; a sync reported without naming its gaps claims a completeness it does not have. Origin incident: 2026-08-09 — a mid-day sync ran Slack and Chat only, reported all-quiet, and missed that the day's most consequential correspondence (a CEO-facing email delivering two Google Docs) had happened entirely on the unswept surfaces.

## v2.18.0 — Dual-client parity in Day-Start; fail-closed context gate in Day-End

v2.18.0 (2026-08-03) adds two checks. Day-Start Step 1 gains the `conformance.py parity` dual-client drift check: the ecosystem's dual-runtime guarantee (Claude Code + Codex) previously had no daily detection layer, and a release that reached one client but not the other — or neither — stayed invisible until something broke. Proven necessary the day it was written: the first live run caught main at 4.12.0 with both installed clients at 4.11.0. Day-End Step 7 gains the fail-closed active-project context gate: `context_doctor.py --project` must be clean for each project worked today before the close-out proceeds. Posture decision recorded in establish-codex-first-class-synthesis: fail-closed for the actor's own active project (fixable in minutes by the session that caused it), report-only for the corpus (gating one session on another's legacy debt manufactures the false alarms that train bypass). Pairs with synthesis-context-lifecycle v1.5.0 and synthesis-agent-conformance parity mode.

## v2.17.0 — Google Chat joins the channel syncs

v2.17.0 (2026-08-03) adds Google Chat as a first-class channel sync beside Slack, in all three sync moments: Day-Start Step 3b, the Mid-Day Sync Protocol, and Day-End Step 1. A workspace opts in by declaring `.agents/gchat-sync.yaml` (sibling to `slack-sync.yaml`); workspaces without the config skip the step silently. Rationale: in many organizations executives and cross-functional teams live in Google Chat while delivery teams live in Slack — syncing only Slack leaves a systematic blind spot exactly where the highest-stakes correspondence happens.

The sub-step is tool-agnostic (any Google Chat-capable MCP; a self-hosted multi-account Workspace server works with plain user OAuth). Four disciplines it encodes, learned from the first production rollout:

1. **Enumerate spaces fresh each run** — per-meeting chat spaces are created for every recorded meeting; a hand-maintained space list is stale within a day. List spaces at sync time, then read what the config's scope selects.
2. **Window by `createTime`, treat a full page as truncated** — some Chat clients expose no pagination cursor on message listing; when a read returns exactly the page size, narrow the time window and re-read until complete.
3. **Preserve the raw `users/<id>` on every message line** alongside any resolved display name. Chat sender IDs are stable, workspace-universal profile IDs; keeping them beside inferred names means a later authoritative resolver (the People API) can correct every past attribution mechanically. Inference layers get names wrong; preserved primary keys make those errors repairable instead of permanent.
4. **Same confidentiality handling as Slack DMs** — Chat DMs carry executive and personnel correspondence; transcripts belong in the workspace-private repo only.

## v2.16.0 — Agent-neutral day-end runtime

v2.16.0 (2026-07-29) installs the launcher and macOS nudge under
`~/.synthesis/day-end/`, a stable runtime owned by synthesis rather than by one
agent client's skill cache. The launcher can open Codex or Claude Code; `auto`
prefers Codex when both CLIs are present, and `--agent codex|claude` persists an
explicit choice. The installer atomically writes exact files, refuses
symlinked runtime roots, never removes the runtime tree, and verifies source
survival in its tests.

## v2.16.0 — Context-integrity doctor joins Day-Start Step 1

v2.16.0 (2026-07-31) adds `context_doctor.py --quiet` beside the git-hooks and message-guard doctors in Step 1. Those two protect the commit and send boundaries; this one protects the durable project record itself — the tiered CONTEXT/REFERENCE/sessions layer that makes work resumable by a different agent on a different machine. It was the last protective layer in the stack with no health check, which meant its correctness rested entirely on an agent remembering to maintain it and reporting honestly that it had. Pairs with synthesis-context-lifecycle v1.4.0.

## v2.15.1 — Message-guard doctor joins Day-Start Step 1

v2.15.1 (2026-07-29) adds the `synthesis-message-guard --doctor` check beside the git-hooks doctor in Step 1. The message guard is the correspondence twin of the commit-boundary scanner: a fail-closed PreToolUse gate that blocks send/draft tool calls without a grounding ledger and a clean register scan. Both guards get their heartbeat in the same ritual step.

## v2.15.0 — Protection-health check in Day-Start Step 1

v2.15.0 (2026-07-28) adds one checkbox to Day-Start Step 1: run the synthesis-git-hooks `--doctor` self-check before any commit-bearing work. Rationale: the commit-boundary scanner is the enforcement layer for credential and confidentiality protection, and a scanner that fails open or drifts from source is invisible precisely because its job is to be invisible when healthy. The ritual is the monitoring loop it was missing. Pairs with synthesis-git-hooks v2.0.0 (fail-closed engine, dependency-free sidecar, drift detection).

## v2.14.0 — Day-End Closure: two-speed day-end, owed-weekly review, decay tags, day-end state

v2.14.0 (2026-07-08) redesigns the day-end around the observed failure mode: on busy or tired evenings the WHOLE ritual gets skipped, and three things decay invisibly — outbound-communication timing (appreciation and replies lose value overnight), lessons that were warm at 5 PM, and the user's own closure on the day. A four-week reconciliation (via `synthesis-catchup-ledger`) showed batch send-passes succeeding whenever a ritual ran, every decay clustering on the zero-ritual days, and the Friday-only Weekly Loose-Ends Review silently disabled for three straight weeks because it lived inside the ritual being skipped. The design principle: make the default evening close small enough to never skip, make starting it one word, make skipping it visible, and decouple the weekly safety net from the evening ritual entirely.

1. **Two-speed day-end, always ask.** The day-end gains a first-class **Quick Close** mode (~10 minutes, exactly three human moments) alongside full mode and observer mode. The session asks the one-letter mode question every time — no time-of-day silent defaults. Spec: "Day-End Modes" block at the top of the Day-End Checklist.
2. **Weekly Loose-Ends Review is owed weekly, not Friday-evening-bound.** The review runs at the FIRST ritual on or after Friday — day-start included, any day-end mode included — tracked via the state file. See the rewritten Step 10 gating.
3. **Decay tags.** Time-sensitive drafts carry a `**Decays:** YYYY-MM-DD (reason)` line from creation. Plan generation applies the tag automatically to the classes field evidence shows decay fastest: appreciation/kudos and acknowledgments, public corrections, and event-bound items. Day-End Step 4 becomes an explicit send-or-release pass over the tagged set — nothing decay-tagged carries silently past its date.
4. **No commitment line without a date or a park.** Every new commitment entering a daily plan gets a do-by, a Decays tag, or an explicit `parked (reason)` marker. Single-mention items that get none of the three are how commitments vanish without a trace.
5. **Lesson candidates accumulate during the day.** Daily plans gain a `## 🌱 Lesson candidates` H2. Any session — mid-day syncs, checkpoint moments, ad-hoc work — appends one-line candidates as insights occur. Day-end curates (keep/drop) instead of recalling from scratch; "warm" moves from 5 PM to the moment of insight.
6. **Day-end state file (producer).** Every ritual, both directions, every mode, writes `~/.synthesis/day-end/state.json` (atomic temp+rename) and appends one line to `~/.synthesis/day-end/history.jsonl`:

   ```json
   {
     "last_day_end":   { "date": "2026-07-08", "mode": "quick", "outcome": "clean", "sent": 3, "released": 1 },
     "last_day_start": { "date": "2026-07-08" },
     "last_weekly_review": "2026-07-03",
     "streak_day_end": 4
   }
   ```

   `streak_day_end` = consecutive workdays with a completed day-end, computed from history at write time. Consumers: the synthesis-console day-end chip, the nudge's suppression check, and the day-start brief line ("day-end: ran Mon ✓ quick · skipped Tue").
7. **Launcher + nudge ship in `scripts/`.** The ritual is an Agent Skill and always runs INSIDE an agentic coding session — nothing here changes that. `scripts/day-end` is a *launcher, not a runner*: it opens Codex or Claude Code with the ritual invocation as the first prompt, purely to remove cold-start friction at the end of the day. `DAY_END_AGENT_CMD` selects a CLI for one run; the installed `agent-cli` file persists `auto`, `codex`, or `claude`. `scripts/day-end-nudge.sh` shows one generic macOS banner at 16:55 on weekdays unless the state file says today's day-end already ran — notification only, never a mutation, generic fixed text (see the alert-confidentiality rule below). Install steps follow.
8. **Audio-alert section aligned with alert confidentiality.** Spoken alerts and banners carry zero identifying content and honor the `~/.synthesis/quiet-audio` mute flag — matching the synthesis-repo-guard v2 alert model. The old `say "[user], [task description] is complete"` pattern is retired: task descriptions can name clients, repos, or people, and speakers/screen-shares leak.

**Consumer coupling:** synthesis-console renders `state.json` (day-end chip) and `**Decays:**` lines (draft badges). Producer-grammar changes here require the console's `docs/cockpit-design.md` to change in the same wave — the document-as-contract rule.

### Installing the launcher and nudge (macOS)

```bash
# Auto-select Codex first when both supported clients are available
python3 <synthesis-daily-rituals-root>/scripts/install_day_end.py

# Or persist one client explicitly
python3 <synthesis-daily-rituals-root>/scripts/install_day_end.py --agent codex
python3 <synthesis-daily-rituals-root>/scripts/install_day_end.py --agent claude
```

The installer copies the launcher and nudge into
`~/.synthesis/day-end/bin/`, links `~/.local/bin/day-end` to that stable
runtime, writes the LaunchAgent with an absolute program path, and reloads it.
Re-run the installer after the skill changes. Use `--no-launchctl` only for CI
or an installation audit that should write and verify artifacts without
loading the LaunchAgent.

## v2.13.0 — Per-workspace `repos.yaml` is the machine-readable repo list

In v2.13.0 (2026-07-08), the source-code sync steps (Day-Start 3a, Day-End 2) enumerate from the workspace repo manifest when one exists: `<workspace>/.agents/repos.yaml` — a symlink into the workspace's private context repo, generated and maintained per synthesis-mac-sync v1.6.0 (which owns the file's schema and lifecycle). Sync every repo with `ritual_sync: yes`. A manifest with `status: dormant` means "skip this workspace's source-code sync entirely — and never delete anything" (retention rule). The workspace `AGENTS.md` "Workspace Repos" table remains the human-readable view and the FALLBACK source when no `repos.yaml` exists. The v2.12.1 rule applies identically to both sources: the declared list is the complete decision — no agent activity-judgment.

## v2.12.1 — Source-code sync scope: the workspace table decides (no agent activity judgment)

In v2.12.1 (2026-07-08), the source-code sync steps (Day-Start 3a, Day-End 2) drop the "associated with active work" qualifier from v2.7.0. The workspace's `AGENTS.md` "Workspace Repos" table is the COMPLETE decision about what to sync: every repo the table marks **Yes** gets synced on every ritual run, whether or not it feels active. The agent must not re-apply its own judgment about which repos are "active" — that judgment layer is exactly what let a collaborator repo drift unnoticed for ~6 weeks (its default branch still tracked a legacy remote after a Git-host migration, silently accumulating "unpushed" commits that the repo guard then flagged repeatedly). Wherever the "associated with active work" phrasing survives in older version notes below, this rule supersedes it. A workspace that wants a repo excluded marks it **No** in the table, with the reason.

## v2.12.0 — Cockpit Mode: meeting-prep packs (`meeting-preps/` + `## 📋 Prep packs`)

In v2.12.0, the Day-Start ritual gains an optional **meeting-prep step** (runs inside Step 6, after the calendar fetch): for each substantive meeting on today's calendar, write a one-pager prep pack to `<knowledge-root>/meeting-preps/YYYY-MM-DD-HHMM-slug.md` and index today's packs in the day plan under a `## 📋 Prep packs` H2 (one list line per pack, linking to the consumer's `/prep/<source>/<slug>` route or the file path).

**What a prep pack joins** (the chief-of-staff briefing-book function): the calendar event (when/who) × relevant transcripts (search by attendee across the workspace's transcripts) × hot items from project CONTEXTs that mention the attendee or the meeting's subject × open commitments in both directions (their waiting-on entries; your unsent drafts to them).

**File contract:**
- Filename `YYYY-MM-DD-HHMM-slug.md` (24h start time; slug identifies the meeting, e.g. `jessica-payne-1-1`). Packs sort chronologically; "today's packs" is a filename-prefix scan.
- H1 = meeting title. A `**When:**` line and a `**Who:**` line (comma-separated attendees) near the top.
- Body H2s are free-form; the recommended skeleton is `Context` / `Open commitments` / `Since last time` / `Suggested agenda`.
- Packs are ritual-generated and updated by mid-day sweeps when new signals land (a transcript posts, a commitment discharges). Never hand-maintained.

**Which meetings get packs:** 1:1s, externals, and any meeting with an attendee who appears in waiting-on tables or open drafts. Routine standups don't need packs unless something notable is queued.

## v2.11.0 — Cockpit Mode: `## 📅 Calendar` section (typed consumer support)

In v2.11.0, Cockpit Mode plans gain a canonical `## 📅 Calendar` H2 that the plan-generation step (Day-Start Step 6) writes from the user's calendar. This is the file-based bridge that lets consumers (synthesis-console v0.12+) render the day's events, bind Tier-C slots to windows, and visualize preemption — without the consumer needing calendar access of its own. The agent fetches events via the user's calendar tool (e.g. Apple Calendar MCP) at plan-generation time and refreshes the section during mid-day sweeps, so same-day meetings appear within one sweep cadence.

**Canonical item shape** (one list line per event):

```markdown
## 📅 Calendar

- 09:00–09:30 · Exec staff sync · Tony, Jane, Marcelo
- 11:30–12:00 · CSA standup · CSA team
- 15:00–15:30 · 1:1 · Jessica Payne
```

Rules: 24-hour `HH:MM–HH:MM` range first, then ` · `, then the event title, then optionally ` · ` and a comma-separated attendee list. En-dash or hyphen both parse. Lines that don't match still render as plain markdown (Postel's Law — nothing is dropped). All-day events use the title-only fallback form (no time range).

**Tier-C window binding:** each `## 🎯 Today` slot H3 SHOULD name its window in the heading (e.g. `### Deep 1 — board memo (window 09:30–11:00)`). Consumers match slot windows against calendar events; an overlapping event that is not the slot itself renders as a preemption flag on the slot. The plan-generation step keeps slot windows consistent with the `**Budget:**` line's windows.

## v2.10.0 — Cockpit Mode: Budget-Bound, Stakes-Routed Day Plans

In v2.10.0 (2026-06-12), the day plan gains an alternative canonical mode — **Cockpit Mode** — for users whose discretionary time is scarce and preemption-prone (heavy meeting load, frequent same-day scheduling). The classic mode (full prioritized task board) remains valid; Cockpit Mode is the recommended default when the user's open-item count persistently exceeds what their calendar can absorb. Design rationale and the originating six-week evidence base live with the user's working-system design doc; the durable protocol is here.

**The three rules of Cockpit Mode:**

1. **Budget before backlog.** The plan generation step reads the user's calendar FIRST, computes discretionary windows, and commits at most ~70% of them — the remainder is an explicit preemption buffer. The plan header states the arithmetic (`Budget: windows … = N min. Committed: M min (≤70%). Buffer: N−M min`). A plan that ignores the calendar is a wish list.

2. **Stakes-routed outbound (the tier matrix).** Every outbound communication is classified at creation:
   - **Tier A — agent sends, clearly agent-labeled** (per the user's bot-labeling rule): routing/triage pings, scheduling requests, receipt acknowledgments, info relays with citations, follow-up nudges on delegated items. Sent within the work block; every send logged to a `## On your behalf` section in the day plan (the TICKER). Tier A never expresses the user's opinions, makes commitments, or touches sensitive relationships. Requires the user's standing approval of the matrix before activation; until then, Tier A routes to Tier B.
   - **Tier B — one-tap queue:** drafts in the user's voice (kudos, substantive replies) and decisions-with-recommendation, presented in batches of ≤5 with APPROVE / EDIT / SKIP affordances answerable in one line. Two review windows per day.
   - **Tier C — user-original:** deep work and relationship-critical writing. **Maximum 3 per plan**, each assigned to a named calendar window.
   Ambiguity routes to Tier B, never to Tier A.

3. **Preemption is normal, not failure.** When a same-day meeting lands on a committed window, the lowest-priority Tier-C item drops to the queue automatically — no re-planning ceremony. Dropped and expired items are caught by the `synthesis-catchup-ledger` ratchet (see that skill); decay rules apply at plan-generation time (stale kudos auto-expire to a consolidated-send; DECAYING items carry do-by dates; event-bound items expire at their event).

**Plan format additions (cockpit-vocabulary compatible):** a `**Budget:**` line in the header; one `## ⚡ Decision needed` H2 when a decision is pending (max ONE per day where possible); `## 🎯 Today — N deep items` (the Tier-C slots); `## ☑️ One-tap batch` (Tier B, with a queued-overflow paragraph); `## On your behalf` (Tier A log); `## 📰 Brief` (readable in ≤90 seconds). Consumers (synthesis-console) treat `On your behalf` as a new lower-row collapsible until typed support ships.

**Relationship to rituals:** day-start still runs the full sync stack (Steps 1–5 unchanged) — Cockpit Mode changes only Step 6 (Day Plan) and Step 7 (Morning Messages: Tier A items send instead of queueing, once the matrix is approved). The user's ritual calendar blocks become review windows; briefs should be prepared BEFORE the block begins whenever the agent runs scheduled/continuous.

## v2.9.0 — Temporal & State Verification as Day-Start Step 1; new synthesis-checkpoint dependency

In v2.9.0 (2026-05-27), the Day-Start ritual gains a new Step 1 — "Temporal & State Verification" — that runs BEFORE all other day-start steps. It anchors today's date from `date`, runs `git log` per active project to verify "last session," and reconciles cached `last_session` fields against git timestamps. Triggered by the 2026-05-27 inbox-cleanup mis-dated-session-log incident; codified to prevent recurrence in any synthesis project.

Step renumbering across the day-start: NEW Step 1 = Temporal & State Verification. Old Step 1 (Context Optimization) → Step 2. Old Step 2 (Sync) → Step 3, with sub-steps 3a/3b/3c. Old Step 3 (Catch-Up Read) → Step 4. Old Step 4 (PR Review Queue) → Step 5. Old Step 5 (Day Plan) → Step 6. Old Step 6 (Morning Messages) → Step 7. The Day-End checklist is unchanged in numbering; Day-End Step 7 (Context Capture) gains explicit push-confirmation language matching the new discipline.

New dependency: `synthesis-checkpoint` — a lightweight skill that codifies the date-verification + state-verification protocol. The day-start ritual delegates to synthesis-checkpoint for the per-project verification work in Step 1.

The discipline this enforces (cross-tool, codified in the active global agent
instructions and the synthesis-context-temporal-continuity project): treat
session-log entry dates, "N days ago" claims, and CONTEXT.md fields as caches
subject to drift. Verify against `date` and `git log` before quoting them into
any output.

## v2.8.0 — Weekly Loose-Ends Review on Fridays

In v2.8.0 (2026-05-22), the Day-End ritual gains a Friday-only "Weekly Loose-Ends Review" step that scans the prior two weeks of work for incomplete, missed, or forgotten items and consolidates the surviving ones into a carryover list for Monday's day-start.

**Rule:** on Fridays, before the Repo Guard final-verification step, scan the past 14 calendar days of daily plans + project context files + open commitment tables. For every surfaced item, classify it as STILL RELEVANT (carry into Monday), OBSOLETE (annotate-and-close in place), or AMBIGUOUS (surface to user). The output is a `## Weekly Loose-Ends Review` section in Friday's daily plan plus a populated `## Carried Items` section in Monday's plan.

**Why:** the workweek's cracks accumulate invisibly. A missed close-of-business ritual on Wednesday means Thursday's plan doesn't pick up Wednesday's open threads. By Friday, several items can be quietly stranded. Without an explicit weekly catch, the user's mental model of "what's open" drifts from reality — and the longer the drift, the harder the eventual reconciliation. Running this on Friday afternoon catches stale items WHILE context is still warm; Monday begins with a clean carryover instead of an archaeological dig.

**Why Friday and not Monday:** Monday is when the carryover gets ACTIONED. Friday is when the carryover gets ASSEMBLED. Assembling on Monday means starting the week with backwards-looking work; assembling on Friday means closing the week with a clean handoff to next week. The split also lets the user (or the agent) drop OBSOLETE items into context that's still fresh — Monday's view of "is this still relevant?" is fuzzier than Friday's.

**Where in the day-end checklist:** new Step 10, just before Repo Guard (which stays the terminal step). The skill detects day-of-week and skips silently on non-Fridays. See Day-End Checklist below.

**Idempotent re-runs:** if a Friday day-end ritual is missed and the agent runs the Weekly Loose-Ends Review on a later weekday (Saturday catch-up, Monday morning if Friday was skipped), it should still produce the same scan output — the scan is date-bounded, not weekday-bounded. The Friday-default is about WHEN it normally fires, not about whether the scan is meaningful on other days.

## v2.7.0 — Source-Code Sync as a First-Class Ritual Step

In v2.7.0 (2026-05-21), source-code synchronization becomes an explicit, first-class step in both the day-start and day-end rituals — running BEFORE the daily plan is drafted (so any drafts that need to be grounded in code can read current source) and BEFORE end-of-day verification (so tomorrow's day-start begins from a clean, current state).

**Rule:** for every source-code repo associated with active work in the current workspace, fetch from all configured remotes and fast-forward the default branches (typically `main` and `develop`, plus any other long-running branches the team uses) BEFORE drafting the daily plan and BEFORE the end-of-day repo-guard verification. The skill stays generic — the list of repos per workspace is declared in the workspace `AGENTS.md` (with any client adapter importing it), not hardcoded.

**Why:**

- **Drafts must be grounded in current code.** The grounding protocol (see below) requires draft messages to be grounded in primary sources before sending. If local source is days behind origin, a draft that cites a function or PR may be quoting a stale version. Pulling first means the grounding research uses the current code.
- **Avoid surprise conflicts at end-of-day.** Running fetch + fast-forward at day-end (just before the repo-guard verification) surfaces upstream divergence early — the user doesn't discover at 6 PM that develop moved fifty commits and a feature branch needs rebasing.
- **One step, not "I'll do it later."** Folding it into the ritual makes it deterministic. The earlier `git fetch --all` checkbox in v2.6.0 and prior was easy to skip and only fetched (no fast-forward) — v2.7.0 makes the step substantive and visible.

**What goes where:**

- This skill defines the GENERIC pattern (fetch from all push remotes, fast-forward default branches, surface diverged or behind-state, report which repos were touched).
- The WORKSPACE-SPECIFIC list of repos lives in the workspace's canonical
  `AGENTS.md` (the Claude adapter imports it). Each repo's specific multi-remote
  configuration is implicit from `git remote -v` inside that repo.
- The PROJECT-SPECIFIC supplement may add per-project considerations (e.g., "after fetch, check whether feature/X is stale and needs rebase"). See "How to Create a Project Supplement" near the end of this file.

**Sequence within day-start:** Context Optimization (Step 1) → **Source-code sync (Step 2a — NEW)** → Slack sync (Step 2b — was Step 2) → Meeting transcripts (Step 2c — was Step 2b) → Catch-up read (Step 3) → PR review queue (Step 4) → Day plan (Step 5) → Morning messages (Step 6).

**Sequence within day-end (v2.8.0+):** Transcript sync (Step 1) → **Source-code sync (Step 2 — v2.7.0)** → Integration sweep (Step 3) → … → **Weekly Loose-Ends Review (Step 10 — v2.8.0, Fridays only)** → Repo guard final verification (Step 11 — was Step 10 in v2.7.0).

## v2.6.0 — Draft Numbering Convention (numbers, not letters)

In v2.6.0 (2026-04-29 very late evening), the convention for labeling drafts in a daily plan is fixed to **sequential integers** (Draft 1, Draft 2, Draft 3, …) rather than alphabet letters (Draft A, Draft B, …).

**Rule:** the first draft of the day is Draft 1. Each subsequent draft increments by 1. No letter labels. No K-2 / K-3 sub-versioning — if a single piece of work produces multiple draft messages (e.g., the same praise routed to two audience-specific channels), each one gets its own integer (Draft 11, Draft 12, Draft 13). The chronological count of drafts in the plan equals the highest integer in use, which makes it easy to answer "how many drafts today?" by reading a single label.

**Why:** numbers are easier to count at a glance, have no 26-item ceiling, and don't impose a mental "is K the 11th letter?" tax. The K-2 / K-3 sub-versioning that letter-labels invite is uglier than 11 / 12 / 13 and creates label-shape inconsistency in the file. Letter labels also make it harder to grep for "all drafts from #N onward" because alphabet ordering is lexicographic, not arithmetic.

**Retraction handling:** if a draft is retracted (caught fabrication, sent-then-deleted, etc.), reserve the number with a brief marker — e.g., `### Draft 8 — retracted` plus a one-line note pointing to the session log — rather than renumbering subsequent drafts. Renumbering after a retraction creates label-drift across the file and any cross-references in chat. The reserved number is the durable record that the slot existed.

**Cross-file consistency:** when renumbering a daily plan that's already been referenced from CONTEXT.md or session logs (those use the labels in effect at the time), update only the daily plan and add a brief note acknowledging the cross-reference gap. Historical narrative in session logs preserves the labels in use at the time — that's the right behavior, not a bug.

**Pre-draft check:** when adding a new draft to a daily plan, the first thing the agent does is scan the file for the highest existing `Draft N` integer and use N+1. No alphabet thinking.

## v2.5.0 — Draft Fence Convention (nested code blocks)

In v2.5.0 (2026-04-29), the canonical fence convention for draft message bodies is documented to handle the case where a draft contains its own triple-backtick code blocks (install commands, code samples, log excerpts).

**Rule:**

- **Default fence for a draft body is 3 backticks** (` ``` `). Use this when the message body contains no triple-backtick code blocks.
- **If the draft body contains ANY internal triple-backtick blocks**, the outer fence must be at least one backtick longer than the longest internal fence. In practice this means **4-backtick outer fence** (` ```` `) when the message contains 3-backtick blocks.

**Why:** CommonMark closes a fenced code block at the first fence of equal-or-greater length. A 3-backtick outer wrapper is closed by the first 3-backtick inner fence — splitting the draft into multiple disjoint blocks and breaking the synthesis-console renderer (which attaches its action bar to the first fenced block after `**Send to:**`). A 4-backtick outer wrapper survives 3-backtick inner blocks unchanged; the inner fences become literal content of the outer fence, which is exactly what we want for a draft body containing install snippets or code samples.

**Pasting into Slack:** when the user clicks Copy in synthesis-console, the action reads `.innerText` from the rendered `<pre>` block — outer fence delimiters are stripped, inner ` ``` ` markers are preserved as literal text. Slack then re-interprets the inner ` ``` ` as Slack code blocks. End-to-end behavior is correct.

**Cross-reference:**

- Consumer-side handling lives in synthesis-console `docs/cockpit-design.md` "Drafts" section (the consumer is being updated to handle multi-segment drafts robustly via `augmentDraftBlocks`, but the producer-side convention here is independently correct and should be applied regardless).
- Lesson backing this rule: `lessons/2026-04-29-document-as-contract-with-llm-producers.md`.

## v2.4.0 — Canonical Plan Format Contract

In v2.4.0 (2026-04-29), the daily plan file format became a versioned contract between this skill (the producer) and synthesis-console v0.8+ (the consumer that renders plans as a cockpit dashboard).

The contract is defined by the **canonical H2 vocabulary** below. The console's parser is tolerant of synonyms and emoji prefixes, but agentic skills (LLMs) must prefer the canonical names where possible because:

- Canonical names are unambiguously typed by the console (NEEDS YOU / TODAY / DRAFTS / lower-row collapsibles)
- Synonyms are accepted via substring + case-insensitive match, but each new variant adds parser maintenance burden
- Non-canonical names fall through to "other" and render as plain markdown — visible but not specially typed

When the LLM driving this skill decides to deviate from the template, it MUST stay within the recognized vocabulary table (next section). New section types should be proposed as additions to this contract, not invented ad-hoc.

The **producer-consumer contract** is documented in two places:
- This file's "Canonical Plan Format" section below (authoritative for skill writers).
- `synthesis-console/docs/cockpit-design.md` (authoritative for parser implementers).

These two files must stay in sync. When changing one, update the other in the same commit.

## v2.3.0 — Workspace-Rooted Paths

In v2.3.0 (2026-04-22), path configuration changed to reflect the ai-knowledge phase 2 architecture: transcripts live per-workspace in `ai-knowledge-<workspace>-<person>-private/transcripts/`; daily plans and lessons live person-scoped in `ai-knowledge-<person>/` at top-level (no `_` prefix). See synthesis-slack-sync v2.0.0 for the complementary configuration schema.

## Rationale notes moved from the checklists (v2.31.0)

### Day-End Step 7 — why open items carry their own age

Appending is safe under this rule and rewriting is not required, which is the point. The failure being prevented is an entry that keeps the present tense it was written in ("today", "this week") long after that stopped being true; re-deriving the whole list each run would also drop anything today's evidence happens not to surface, turning a visible stale entry into an invisible missing one. A stamped entry ages in public instead: `context_doctor.py` reports it as `item-currency` once it passes its review horizon (14 days when `review Nd` is omitted), so the check runs for any reader at any time rather than only on days this ritual runs.
**Match the horizon to what the item is.** The 14-day default is the horizon for something *owed* — blocked on a named person, with a consequence if it slips. A backlog is not that: a list of feature ideas, article ideas, or a bug inventory is a record of intent, and nobody promised it by a date. Stamp those `(as of YYYY-MM-DD, review 180d)`. Measured once on a real corpus, 17 of 38 open-item findings were wishlists ageing at the owed-work horizon, and a check that reports intentions as overdue is how the whole open-items signal gets read as noise.

**A recorded decision is not an open item at all.** If a bullet under an open-items heading says a thing was settled — "not needed", "kept", "declined" — the fix is structural rather than a longer horizon: move it under a decisions heading, where the checker does not read it as owed. The section HEADING is what decides, so a settled decision parked under "What's Next" will keep being asked to prove it is still current no matter how it is worded.

### Day-End Step 10 — why the weekly review exists, and its idempotency

This step exists because work falls through the cracks during a week. A missed close-of-business ritual means the next day's plan doesn't pick up the open threads from the day before. By Friday, several items can be stranded invisibly. The Friday review catches these BEFORE the weekend disconnects fresh context, and assembles a clean carryover list for Monday.

**Idempotency:** if a Friday review was missed and the agent runs this step on a later weekday, the scan still works because it's date-bounded (past 14 calendar days from today), not weekday-bounded. The Friday-default is about WHEN it normally fires; the scan output is meaningful on any day.

### Observer mode — why it is codified

When observer mode is reinvented per conversation, the agent often drops durable state. The rule is now explicit: every observer run leaves attributed local state, while day-end or remote-handoff mode owns publication.

## Principles Behind These Checklists

- **Dependency-ordered:** Each step feeds the next. Sync before reading. Read before planning. Plan before messaging.
- **Information entropy reduction:** The primary purpose is closing the gap between what happened and what you know.
- **Human investment:** Motivational messages are not optional — they are a force multiplier on a distributed team.
- **Career compounding:** Every day produces raw material for thought leadership. The discipline is noticing it.
- **State capture:** If you do not capture today's state, tomorrow's start takes longer. This compounds.
