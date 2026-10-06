# The checkpoint protocol in full

## Contents

- [The Problem](#the-problem)
- [When To Invoke](#when-to-invoke)
- [The Protocol](#the-protocol)
- [Output Format](#output-format)
- [What Counts as "Substantive Work"](#what-counts-as-substantive-work)
- [Relationship to Other Synthesis Skills](#relationship-to-other-synthesis-skills)
- [Why This Works](#why-this-works)

## The Problem

LLMs are stateless at the model level. Across a long conversation, an LLM's sense of "what's true now" can drift from what's actually on disk and in git. Drift sources:

- **Time drift.** The model has no clock. If the conversation started Tuesday and continues Wednesday, the model often still thinks it's Tuesday.
- **State drift.** Project CONTEXT.md may have been edited (by user, by sub-agent, by another session) since the model last read it.
- **Compaction drift.** When the context window approaches its limit, the harness may summarize older turns. Details disappear. The model often cannot detect that this happened.
- **Cached-fact drift.** Facts the model read earlier in the conversation (last commit, last session date, last decision) may no longer be true.
- **Coordination drift.** Another live root session may have claimed or changed
  the same source area since the last tool call.

Self-discipline degrades with conversation length. Rules read at session start lose salience as turns accumulate. Even a model that "knows" to verify often skips verification under the weight of accumulated context.

This skill is the recovery primitive. It is a tight, low-friction protocol the agent runs on demand or on a detected drift signal — and the act of running it restores ground truth.

## When To Invoke

Invoke synthesis-checkpoint when any of these conditions fire:

**Triggered by the user:**
- User asks "where are we?" / "what's the status?" / "what's been done?"
- User asks the agent to continue work after a pause
- User says "remember to..." or "you forgot..."
- User indicates the agent has drifted ("that's not right", "you said earlier...", "actually...")
- User invokes this skill by name or by keyword (checkpoint, re-sync, refresh)

**Triggered by the agent's own self-monitoring:**
- Before generating any time-interval claim ("N days ago", "yesterday", "last session", "this week")
- Before quoting any project status from cached memory
- After at least 10 minutes between user turns when the client exposes message
  timestamps. Ten minutes is the default freshness boundary: long enough to
  avoid checkpointing ordinary back-and-forth, short enough to catch another
  client session changing shared state. If timestamps are unavailable, any
  resume/continue phrasing after an apparent pause triggers the checkpoint.
- After ~25 substantive tool calls, regardless of perceived need
- When the model says or thinks "I don't recall" about a recent decision
- When a file read reveals content the model didn't expect (state drift signal)
- When the user references a decision the model has no record of (compaction signal)
- When resuming work on a project after working on something else in the same session
- When the shared coordination board changes or another root session becomes active

**Triggered automatically by lifecycle hooks:**

- SessionStart re-injects this session's project directive and current-state
  block at session start and after compaction (R1.2), and reports unread board
  messages. Treat that re-injection as the start of a checkpoint, not its end:
  the files it points to are the evidence.
- UserPromptSubmit delivers board messages at the next prompt; a new message
  from a peer working the same files is a coordination-drift trigger.

## The Protocol

Use the full protocol for session recovery, material drift and explicit refresh.
During continuous work with a verified project identity, check the live facts
needed for the next claim or mutation and update only changed recovery state.
A timestamp question requires a current clock; it does not by itself require
another project audit. A status claim still requires its actual current source.
Read current ownership before writes. New contradictions trigger full recovery.

Checkpoint work does not recursively trigger another checkpoint. Logging this
checkpoint, answering its status question or publishing its record belongs to
the same invocation. Reuse immutable source and retained evidence by reference;
do not copy or re-review unchanged artifacts merely to make a new checkpoint.
Then return to the next deliverable or the user's requested safe stop.

### Step 0 — Read cross-agent coordination

Run `synthesis who` and `synthesis inbox` before any write. Confirm that this
session's claims still cover the intended files, read new messages addressed
to this session, and stop writes on any overlap. At normal execution
checkpoints and task/phase changes, compare held areas with current needs:
exact files for independent edits, directories when coordinated multi-file work
requires them. Keep the smallest coherent area; claim more before additional
writes, and release completed areas promptly after their required closure
(`synthesis release <paths>`). Do not preclaim future work or alter another
session's claims (synthesis-project-management, coordination). In read-only
refresh-and-report mode, report needed scope changes without changing claims.

### Step 1 — Verify current time

```bash
date "+%Y-%m-%d %H:%M:%S %Z (%A)"
```

Read the output. Set this as your authoritative "current time" anchor. Compare to whatever you previously believed about the current time. Note any difference larger than a few minutes — that's drift, and it means in-context time impressions are unreliable.

### Step 2 — Verify project state from disk

Use this conversation's established project: the one on this session's own
board file (`synthesis who` shows it), or the one the conversation has been
working. Nothing outside this session chooses it; a project named by someone
else's file must not silently switch an established conversation.

`synthesis brief` prints the project's directive, current-state block and plan
line; `synthesis resume <id>` adds warnings about a fetched upstream that moved,
newer or diverged copies on other worktrees or branches, and other live
sessions on the project. A reported CONFLICT stops dependent reads and all
project writes until it is reconciled; never pick a copy by date, and never
run a migration or rewrite to make a warning go away.

For the selected project, read:
1. `CONTEXT.md`, including its current-state block.
2. The controlling plan (the one `Plan:` field) and the latest entry in `sessions/YYYY-MM.md`.
3. `REFERENCE.md` (full read on first recovery, section-skim on a repeated checkpoint).

Missing required inputs stay explicit. A doctor result or a hash does not prove
that the agent read or understood these project tiers.

Note the "Last session" header in CONTEXT.md. Do not trust it as authoritative — it is a cache. Treat it as a starting hypothesis to verify in Step 3.

### Step 3 — Verify session evidence and Git publication separately

Read the latest dated session entries under `sessions/`, including entries
newer than the cached header. Compare their recorded workdays and outcomes
with CONTEXT.md and `index.yaml`.

```bash
git log -10 --pretty=format:"%h %ai %ci %s" -- <project-path>
git status --short -- <project-path>
```

Git author/committer timestamps describe commits. They do not establish when
the recorded session happened: overnight work, delayed publication, timezone
boundaries, backdated authorship and bulk maintenance can all separate them.
Never rewrite a recorded workday merely to match a commit date, and never
infer uncommitted work from a date difference; inspect Git status for that.

- Matching dated session records establish date agreement, not full semantic
  currency. Verify outcomes, current fields and source state as well.
- A header or index date behind **or ahead of** the dated narrative is a record
  mismatch. Cite both records and reconcile against actual work evidence.
- Missing, unreadable or invalid dated entries make session-date verification
  unavailable. State that limit; a commit timestamp cannot fill the gap.
- Keep commit publication and upstream ancestry checks separate. A clean tree
  can still contain stale claims, and a valid session date can precede its commit.

The context doctor checks the same agreement mechanically:
`python3 <synthesis-context-lifecycle>/scripts/context_doctor.py --project <path>`
(exit 0 healthy, 1 defects, 2 cannot tell).

### Step 4 — Cross-reference tasks and recent decisions

Check material context separately from structural health: are the declared
inputs, rationale, temporary conditions, uncertainty and amendments that the
current work depends on actually in the record
(synthesis-context-lifecycle, material context)? Restore a missing link
without replaying the incident. A clean doctor run cannot certify meaning.

If the client provides an in-session task or plan surface, read it. Treat that
as the third source of truth—ephemeral session memory to compare against disk
and git.

If there's a planning artifact (a plan file, a design doc, a checklist) referenced from CONTEXT.md — re-read it.

### Step 5 — Reconcile and report

For a full recovery or an explicit runtime-readiness report, also run
`synthesis version` and `synthesis doctor` (see
[refresh-and-report.md](refresh-and-report.md)). Installing or copying files
is not a reload of the running harness; the evidence comes from the next
lifecycle event.

In one short paragraph in the next response to the user, state:
- Today's verified date and time
- The latest recorded session date and its dated evidence source; say when verification is unavailable
- Where the agent's mental state diverged from disk/git, if anywhere
- What the agent will do next, grounded in the verified facts
- Current coordination claim and any conflict or new inter-session message

Show this verification step in the response. It is the L4 visible-verification mechanism from the synthesis-context-temporal-continuity project — the user must be able to see that the checkpoint ran and what it produced.

### Step 6 — Update CONTEXT.md if it was stale

If Step 3 reveals stale context, claim the exact files before editing
(`synthesis claim <paths> --project <id>`). Use an isolated worktree when a
concurrent session owns the same checkout. If the claim is refused, report the
blocking session as `id (project · harness)` from `synthesis who` and preserve
the work; never infer release authority from app closure, age or a typed
reason.

Under the claim, make the verified correction and keep it on disk; publish it
at the next handoff to another Mac or at day-end (`synthesis handoff`). Release
claims taken only for the checkpoint before pausing.

Before the checkpoint closes, ask: **What executable state or required input
data still exists only in this session's scratchpad?** If a durable record
cites its output, preserve the script and required inputs under
resources/scripts/ before the checkpoint can close.

## Output Format

The agent's response after invoking this skill should include something like:

> **Checkpoint complete.** Verified facts:
> - Today: 2026-05-27 10:49 EDT (Wednesday)
> - Latest recorded session: 2026-05-25, from `sessions/2026-05.md`
> - Latest project commit: 2026-05-26 12:47 EDT; this is publication evidence
> - CONTEXT.md and the index agree with the dated entry; current claims were also checked
> - No precise elapsed-session interval claimed: the entry supplies a workday, not an end timestamp
> - In-progress task: [task summary from the client task/plan surface]
>
> Proceeding with [next action].

If discrepancies were found:

> **Checkpoint complete — drift detected.** Verified facts:
> - Today: 2026-05-27 10:49 EDT
> - CONTEXT.md said: "Last session: 2026-05-18 (PM)"
> - `sessions/2026-05.md` records a later session on 2026-05-25
> - Git records publication on May 26; that does not change the recorded workday
> - Action: under an accepted claim, reconcile the stale header and current claims against the May 25 entry and source evidence.

## What Counts as "Substantive Work"

Verify the relevant current facts BEFORE these kinds of work, not after. Use the full protocol when recovery or drift requires it:

- Writing a session-log entry
- Computing or claiming a time interval ("X days ago", "yesterday", "this week")
- Quoting project status to the user
- Making a planning decision based on "where we left off"
- Generating a commit message that mentions dates or intervals

After-the-fact verification catches some errors but lets stale facts propagate into outputs first. Verifying first is cheaper than correcting later.

## Relationship to Other Synthesis Skills

This skill is the recovery primitive that other skills delegate to:

- **synthesis-context-lifecycle** — references this skill in its Session Start Protocol and Mid-Session Refresh Protocol. The lifecycle skill defines the architecture of CONTEXT.md / REFERENCE.md / sessions/; this skill is the per-invocation drift-check.
- **synthesis-daily-rituals** — references this skill in its day-start ritual. Day-start always runs a checkpoint before any project work begins.
- **synthesis-project-management** — references this skill in its project-discovery protocol. When the user mentions a project, the agent runs a checkpoint on that project's files.

These skills are independent. Each works standalone. But they are stronger when they all delegate the drift-check to this single skill, which guarantees a consistent protocol.

## Why This Works

The synthesis project management system already has the durable layer (CONTEXT.md, REFERENCE.md, sessions/, git history). The failure mode is not lack of data — it's the agent's in-context memory drifting from that data over time. This skill's only job is to force a re-sync against the durable layer at the moments when it matters most.

It is intentionally lightweight (~5 tool calls), intentionally codified (no variation between invocations), and intentionally visible (the user sees the verification step). All three properties matter:

- **Lightweight** — runs without the agent rationalizing "this isn't worth the steps"
- **Codified** — runs the same way every time, so users can recognize when it ran and when it didn't
- **Visible** — users can spot when verification was skipped and intervene early

This is the **NTP** of the synthesis project management system: periodic, authoritative-source-driven, automatic.
