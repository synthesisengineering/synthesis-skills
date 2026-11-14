# Discovery, session start and end, handoff and sub-agents

## Contents

- [Project discovery](#project-discovery)
- [File requirements by project status](#file-requirements-by-project-status)
- [Session start](#session-start)
- [During work](#during-work)
- [Session end](#session-end)
- [Cross-agent handoff](#cross-agent-handoff)
- [Work handed between agents](#work-handed-between-agents)
- [Parallel sub-agent dispatch](#parallel-sub-agent-dispatch)
- [Common mistakes](#common-mistakes)

## Project discovery

When a user mentions a project:

1. Read `projects/index.yaml`.
2. Match the user's phrase against project `name`, `description`, `id` and
   `tags`.
3. **Check the match against the session's own context before switching.**
   A session usually carries project evidence of its own: the conversation's
   established project, the session name, the project on its board row
   (`synthesis who`), the working directory. When the named project
   *contradicts* that evidence, surface the contradiction and ask ("This
   session has been working project Y — did you mean X, or should this stay in
   Y?"); never silently resolve to the name. Names are typed by humans
   navigating many similarly-named projects, so a name is one signal, not an
   override; a silent wrong resolution sends a full session's work to the
   wrong project's records (this happened on 2026-08-20). Resolve without
   asking only when name and session evidence agree, or when the session
   carries no project evidence at all.
4. If matched (and confirmed where step 3 required it), run
   `synthesis resume <id>`. It refuses to switch a session that holds another
   project, offers to start a project for an unknown id instead of picking a
   near match, and warns about newer or diverged copies of the records. A
   reported conflict stops dependent reads and writes until it is reconciled;
   never pick a copy by date. Then run the context-lifecycle Session Start
   Protocol.
5. Summarize current state and next steps.
6. **Re-verify scope before dispatching work, especially for a paused
   project.** CONTEXT.md's "N items remaining" (or any count a plan document
   asserts is current) is a claim made at write time, not a live query — it
   goes stale the moment anything else touches the same corpus, even a
   workstream that has nothing to do with this project and doesn't know it
   exists. Before batch-dispatching agents against a stated scope, re-derive it
   from live state with a cheap direct check (`find`, `grep`, `wc -l` against
   the actual files or repos) rather than trusting the document's count. This
   is cheapest immediately before dispatch — the highest-leverage moment to
   catch drift, before agent-hours are spent at the wrong scope — and it
   applies even within a single session, since a count computed early in a
   long run can go stale by the time a later phase acts on it. If the recount
   disagrees with the document, update the document in the same pass rather
   than silently working around the discrepancy. (Distinct from
   context-lifecycle's Session Start Protocol, which verifies CONTEXT.md's own
   freshness against this project's git log — that catches a stale *file*;
   this catches a stale *scope claim* that can drift even when the file itself
   looks current.)
7. Begin work from where it left off.

## File requirements by project status

| Status | CONTEXT.md | REFERENCE.md | sessions/ | CONTEXT.md budget |
|--------|------------|-------------|-----------|------------------|
| active | Required | When needed | When needed | ≤150 lines |
| paused | Required | When needed | When needed | ≤150 lines |
| completed | Required (summary) | Optional | Optional | ≤80 lines |
| archived | Frozen | Frozen | Frozen | N/A |

A standing project with no end state is `active` or `paused` plus
`bounded: false` in its index entry (the retired `ongoing` status conflated
attention with boundedness). Resuming a `paused` project carries the highest
scope-drift risk of any status — see step 6 of project discovery before
dispatching work against one.

## Session start

1. **Read the board.** `synthesis who` and `synthesis inbox` before any write.
2. **Resume.** `synthesis resume <id>` prints the directive, current-state
   block, phase, next actions and plan, and the warnings to resolve first.
3. **Read the files.** CONTEXT.md, the plan, REFERENCE.md and the latest
   session entry, per the context-lifecycle Session Start Protocol.
4. **Check line count.** If CONTEXT.md is over 150 lines, archive before
   starting work.
5. **Search lessons/** for relevant past experiences.
6. **Check related projects** through the `related:` tags in index.yaml.
7. **Claim** what this session will write.

## During work

```
Complete task → Update CONTEXT.md → Next task
```

**NOT:** task → task → task → (context compaction) → lost details. Preserve
material inputs (facts, rationale, temporary conditions, uncertainty and
amendments) in the project before dependent work, compaction or handoff; see
the context-lifecycle skill.

## Session end

1. **Final CONTEXT.md update.** Ensure all sections are current (≤150 lines).
2. **Archive if needed.** Move old sessions to sessions/, stable facts to
   REFERENCE.md.
3. **Attribute if warranted.** If multiple agents or models contributed
   materially, end the session-log entry with Attribution lines
   ([records-and-conventions.md](records-and-conventions.md#agent-attribution--full-rules)).
4. **Hand off.** Same Mac: nothing more; another Mac: `synthesis handoff`.
5. **Release claims.** `synthesis release` before pausing. Only the session
   that holds a claim releases it; age, app closure or a typed reason never
   authorizes releasing another session's.

## Cross-agent handoff

Before pausing work that may continue in another tool, the outgoing agent runs
this protocol automatically. The principal does not invoke lifecycle commands
or save state by hand:

1. Update `CONTEXT.md` with current state, decisions, and next actions.
2. Move stable facts into `REFERENCE.md`.
3. Append chronological detail to `sessions/YYYY-MM.md`.
4. End the session-log entry with an Attribution line for the departing agent
   — the receiving agent should know who did what, with what verification.
5. Save substantial plans, audits, or checklists under `resources/artifacts/`.
6. **Same Mac, another harness:** nothing needs committing; the files on disk
   are the handoff (R1.3). The next session's SessionStart hook re-injects the
   project's directive and current-state block once it runs `synthesis use` or
   `synthesis resume`.
7. **Another Mac:** run `synthesis handoff -m "<message>"`. It commits only the
   files this session changed inside its own claims (`git commit --only`, every
   hook running), fetches, pushes only as a fast-forward, leaves an existing
   `index.lock` alone, and reads the result back from `git log` and the
   remote-tracking ref. Its last line is READY or NOT READY; NOT READY lists
   what is dirty, unpushed, diverged or without an upstream, and nothing is
   forced. Day-end performs the same step.
8. Release or transfer this session's claims.

Resuming from another agent: run `synthesis resume` before reading prose, read
`CONTEXT.md` and the linked plan, and inspect Git status and diff before
acting. Working-tree truth supersedes cached project prose after an
interrupted task. The continuity source of truth is the filesystem-backed
synthesis record, not the previous assistant's chat transcript.

## Work handed between agents

The protocol above hands a project's *state* between tools. When two root
sessions collaborate on one project, the *work item* itself also needs a
transport that is not the principal's clipboard ("the principal is not the
courier"). Write the brief as a file under `resources/artifacts/` and send its
path with `synthesis msg <session or project:id> "<path and one line>"`. Two
rules keep this supervised:

- **Nothing self-triggers.** An agent picks up a brief when the principal, or a
  board message the principal's protocol allows, says the other side is done.
  Supervision by exception is the point; unattended is not uncontrolled.
- **There are two directions.** Messages move work *between agents*. Decisions
  *between agent and principal* travel as a decision packet
  (`synthesis-decision-packet`). Together they remove the principal as the
  transport layer while leaving every crossing visible in the project.

## Parallel sub-agent dispatch

Fan-out to multiple sub-agents working the same project concurrently — a batch of parallel repo migrations, a multi-agent reorganization run, several research tasks feeding one project — is now a common pattern, not an edge case. Two risks are specific to concurrent writers and aren't covered by the sequential protocols above.

**Git-index collisions.** When more than one agent (or background process) can commit to the same repo in the same window, `git add <your files>` followed by a bare `git commit` does not commit only what you just added — it commits everything currently staged, including anything another agent staged first. `git add` extends the index; it does not replace it. Before every commit in a repo where concurrent writers are plausible, run `git status --short` and `git diff --cached --name-only` first, and commit only the paths this invocation intends (`git commit -o <paths>`, or unstage what isn't yours). Treat this as a mechanical prefix to the commit step, not a judgment call reserved for commits that "feel risky" — the risk lives in what might already be staged, which by definition isn't visible without looking first.

**Tracking-doc aggregation.** A sub-agent dispatched against its own slice of a project — its own repo, its own batch — correctly leaves its siblings' in-flight work alone. That discipline has a side effect: no single agent sees the combined result. A shared tracking doc (CONTEXT.md, index.yaml) updated only by whichever agent happened to touch it last will under- or overstate what the batch actually accomplished. After any parallel dispatch, the orchestrator — not an individual sub-agent — reads every report as a set, reconciles them, and updates CONTEXT.md/index.yaml to reflect the true combined state.

Sub-agents spawned by one orchestrator remain governed by that orchestrator.
Independent root sessions use the board; do not mistake a shared git worktree
or shared chat history for coordination.

## Common mistakes

| Mistake | Consequence | Prevention |
|---------|-------------|------------|
| Not updating CONTEXT.md | Lost progress after compaction | Update after EVERY task |
| Deferring updates to "session end" | Forget to update | Update immediately |
| Putting management files in project repos | Exposes internal process | Keep in ai-knowledge-{workspace} |
| Not checking lessons/ | Repeat mistakes | Grep at session start |
| Creating separate patterns.md | Duplicate, gets stale | Use `type: pattern` in lessons/ |
| Maintaining index files for lessons | Gets stale | Use date prefixes, `ls -t` |
| Trusting a paused project's stated remaining-scope count | Batch-dispatches the wrong amount of work — wastes agent-hours on already-done items, or silently leaves new items undone | Re-derive the count from live disk/repo state immediately before dispatch, even when the document looks current |
| Bare `git commit` in a repo where sub-agents dispatch concurrently | Sweeps another agent's staged work into your commit | `git status --short` / `git diff --cached --name-only` before every commit; commit only your own paths |
| Editing before reading or claiming the board | Two root sessions overwrite or invalidate each other's work | `synthesis who` at session start and checkpoints; claim before writes |
| Resolving a named project over the session's own contradicting context | A full session's work lands in the wrong project's records while the intended project's ask goes unfulfilled | When the name and the session's evidence disagree, ask a one-line clarifying question before switching (Project discovery step 3) |
| Treating a valid claim as completed project recovery | Retained obligations or handoff usability remain unverified | Check separately that every open obligation has a current record, owner and next action, and that the handoff names the remaining outcome, sources, boundaries and next step |
