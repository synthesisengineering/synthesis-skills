# Session protocols: start, mid-session refresh, and switching harness or Mac

## Contents

- [Session Start Protocol](#session-start-protocol)
- [Mid-Session Refresh Protocol](#mid-session-refresh-protocol)
- [Compaction](#compaction)
- [Switching harness or Mac](#switching-harness-or-mac)
- [Scope and index safety](#scope-and-index-safety)

## Session Start Protocol

The tiered architecture (CONTEXT.md / REFERENCE.md / sessions/) is only useful if the agent reads it. LLMs default to working from in-context memory; rules at session start lose salience as conversation grows. The Session Start Protocol makes the read explicit and non-skippable.

When you begin substantive work on any project — at client session start, when
the user first mentions it, or after switching from another project — run these
steps in order before substantive action. First establish the project: the
conversation's own project, confirmed with `synthesis resume <id>` (which asks
before switching a session that holds another project, and warns about newer
or diverged copies of the records). Nothing outside this session decides its
project: there is no global "current project" pointer. A reported conflict
stops dependent project reads and writes until it is reconciled.

1. **Verify current time.** Run `date "+%Y-%m-%d %H:%M:%S %Z (%A)"`. The model has no clock; the OS does. Use the output as your authoritative "today" anchor for the rest of the session. The harness may have injected a date earlier, but that injection drifts; `date` does not.
2. **Inspect Git publication and working state.** Run `git log -10 --pretty=format:"%h %ai %ci %s" -- <project-path>` and `git status --short -- <project-path>`. These establish commit author/committer times and pending changes. Commit times do not define session workdays; delayed publication, overnight work and timezone boundaries may put them on different dates.
3. **Read CONTEXT.md.** Read the full working-memory file. Treat its "Last session" header as a claim to compare with dated session records and current source evidence. A commit-date difference alone does not make it stale, and matching dates alone do not establish semantic currency.
4. **Read the latest dated entries in sessions/YYYY-MM.md.** Locate the newest recorded workday across the archive, not just the file's final heading. Compare the narrative with CONTEXT.md and index metadata. Report older or newer cache dates with both sources; recover missing, invalid or unreadable evidence without inventing a session date from Git. When archiving older work, retain its verified workday and label the current recording time separately. A repair done today may have its own entry; it must not rewrite the earlier workday to match its commit.
5. **Skim REFERENCE.md if you have not recently.** This is the project's stable facts and design spec. Full read on the first session resumption of the day; quick skim of section headers otherwise.
6. **Name this session after the project where the client allows it.** When the client exposes session/thread renaming, set this conversation's own title to the project's id (e.g. `synthesis-ecosystem-engineering`) so the thread list reads as the work queue. Claude Code: MCP tool `mcp__ccd_session_mgmt__set_session_title` with `{session_id: "self", title: "<project-id>"}` (verified 2026-09-21; a user-set title asks approval first, auto-generated titles replace silently). No verified equivalent on other clients as of that date — check yours and apply the same convention if one exists; if not, this step does not apply.
7. **Only then begin substantive work.**

`synthesis resume` (or `synthesis use <id>` when nothing needs printing)
records the project on this session's own board file. From then on the
SessionStart hook re-injects the project's directive and current-state block at
every session start and after every compaction. That is an acceleration; the
project files and git history remain authoritative.

**Why this order matters.** Steps 1 and 2 establish ground truth from external sources (OS clock, git). Step 3 reads the cache. Step 4 reads the most recent narrative. The order means by the time you act, you have verified facts AND the project's own framing — and you have noticed any discrepancy between them.

**Visible to the user.** Show the verification step in your first response of the session. Example:

> Session start verified. Today: 2026-05-27 10:49 EDT (Wednesday). Last project commit: 2026-05-26 12:47 EDT (`51b8e6d`, "Maintain context: refresh inbox-cleanup CONTEXT.md"). CONTEXT.md matches git log. Proceeding with [next task].

The visible verification is the L4 cross-tool drift-detection mechanism — the user must be able to see that ground truth was checked.

## Mid-Session Refresh Protocol

Long conversations cause context drift. The mid-session refresh protocol re-syncs the agent against ground truth without requiring a full restart.

**Mandatory triggers.** Re-run the Session Start Protocol (or invoke the `synthesis-checkpoint` skill, which is the codified version of these steps) under ANY of these conditions:

- **Before any time-interval claim in output.** "Yesterday", "N days ago", "last session", "this week", "earlier today" — verify the clock and the dated evidence for the event BEFORE generating the claim. Use `git log` for commit intervals; use session records for session dates, and do not infer an exact elapsed interval from a date-only entry. After-the-fact correction is more expensive than upfront verification.
- **After a long real-time pause.** If `date` reveals more than 1 hour has passed since you last checked, re-read CONTEXT.md and re-run `git log`. Long pauses correlate with the user resuming after a break — the world may have changed.
- **After ~25 substantive tool calls** since the last refresh. This is the unconditional cadence: even with no drift signal, re-read CONTEXT.md and `git log` to verify your accumulated context still matches disk.
- **On any drift signal:**
  - You say or think "I don't recall" about a recent decision
  - A file read returns content you didn't expect
  - The user references a decision you have no record of
  - The user corrects you ("that's not right", "actually...", "you said earlier...")
  - You notice the conversation has touched many topics and feel uncertain about project state
- **Before writing to a session-log file** (a markdown file under `sessions/`). The date you write into the header MUST be from `date`, not from memory.
- **Before generating a commit message that mentions dates or intervals.** The interval claim must be backed by `git log`.

**The protocol itself.** Run the steps from synthesis-checkpoint (preferred if loaded), or as a fallback the same steps inline:

1. `date "+%Y-%m-%d %H:%M:%S %Z (%A)"` — verify current time
2. `git log -10 --pretty=format:"%h %ai %s" -- <project-path>` — verify project history
3. Re-read CONTEXT.md from disk
4. Re-read the latest sessions/YYYY-MM.md entry
5. Reconcile: where does in-context memory disagree with disk/git? Report the discrepancy in the next response.
6. If CONTEXT.md is stale, update it under your claim. The files on disk are the same-Mac handoff; publish them with `synthesis handoff` when the work moves to another Mac.

**Delegation.** When the `synthesis-checkpoint` skill is available, prefer invoking it — it is the canonical codification of this protocol, runs the same steps every time, and produces consistent visible output the user can spot. Use the inline fallback only when synthesis-checkpoint is not loaded.

## Compaction

**Compaction detection signals.** Context-window compaction (the harness summarizing older turns) is opaque — you cannot reliably detect when it happened. Treat these as red flags suggesting compaction may have occurred:

- You suddenly cannot recall the user's stated goal for the session
- A task you remember as in-progress has unclear next steps
- Tool outputs reference files or decisions you have no context for
- Your last few tool calls feel disconnected from the current request

When any of these fire, run the Mid-Session Refresh Protocol unconditionally.
Where the harness supports it, the SessionStart hook has already put the
directive and current-state block back after compaction; read the files it
points to rather than trusting the summary.

## Switching harness or Mac

The principal never has to run this protocol or save state manually. The
working agent owns the checkpoint before it yields. A normal transition is:

1. the agent updates `CONTEXT.md`, stable `REFERENCE.md` facts, the current
   session log, and the controlling plan as the work changes;
2. **same Mac, another harness:** nothing is committed and nothing touches the
   network; the files on disk are the handoff (R1.3);
3. **another Mac:** `synthesis handoff` commits only the files this session
   changed inside its claims, fetches, pushes only as a fast-forward, and ends
   READY or NOT READY with the reason (R1.4); day-end does the same;
4. when the principal names the project, the receiving session runs
   `synthesis resume <id>`, which reports changes the other Mac pushed (after a
   fetch), refuses to have you pull over local uncommitted changes, and then
   this Session Start Protocol runs.

A new session reads the durable tiers and linked plan, then treats Git status
and diff as newer truth than cached prose. If a task was interrupted, it
reconstructs the incomplete work from the working tree rather than discarding
it.

The guarantee has explicit boundaries: do not switch while a task is still
running; an offline origin can preserve a local checkpoint but cannot make it
available on another computer; divergence, a behind checkout, missing
authentication, and overlapping claims must surface visibly instead of being
called seamless.

## Scope and index safety

Never run a workspace-wide commit over dirty files. Remote publication uses
only the paths this session changed inside its own claims. Source repos follow
their own branch, review, and deployment policies. Before every commit, inspect
status and the staged index; do not include another session's paths. Never
bypass hooks.
