# Ritual worker artifact contract — v1

The portable core of distributed ritual execution: **workers write files, the desk reads
files**. No worker ever messages the desk. A worker that ran leaves a fresh artifact; a
worker that did not run leaves nothing, and that absence is itself the signal — legible,
durable, and inspectable, unlike a message that exists only if someone was listening.

This contract is client-neutral. Any agent client (or a human) can produce a conforming
artifact; any client can act as the desk. Nothing in it names a scheduler, a dispatch
mechanism, or a vendor.

## Terms

- **Desk** — the seat that owns the ritual home. It frames the day, reads worker
  artifacts, reconciles them, and produces the **single** daily brief. The output never
  distributes: one brief, one to-do list, one console, regardless of worker count.
- **Worker** — a per-workspace execution of the ritual's sync-and-triage labor, holding
  that workspace's context only. Two modes, and the order matters:
  1. **DEFAULT — an attended session rooted in the workspace**, run by the principal when
     they are working in that workspace, on that workspace's own schedule. It holds its own
     claims, its own context, and its own working directory.
  2. **Opt-in — a desk-dispatched subagent** in an isolated context against the workspace's
     paths. Useful when the principal deliberately wants everything closed from one place.
     Never the assumed path.
  The desk never loads workspace detail inline; it reads worker summaries.

- **The principal is the dispatcher.** Nothing in this contract lets one session start work
  in another. The desk's job is to report which workspaces are owed; the human decides where
  to go next and opens that session. This is a statement of the actual mechanism, not a
  limitation being worked around — and it is why the substrate is files.

  *Evidence (recorded because the alternative keeps looking attractive):* a desk that tried
  to trigger workers by messaging their sessions went 0 for 2. The first attempt sent to a
  session that had gone stale two hours earlier; the second found no reachable session at
  all. Both times the work actually arrived through the artifact — written when the
  principal opened that workspace and worked in it. Session messaging delivers a user turn
  into a session that must already exist and be attended; it is a relay between
  humans-at-keyboards, not a dispatch primitive. A design that depends on every workspace's
  session being open and attended has relocated the multi-session overhead, not removed it.

- **The desk never nudges, triggers, blocks on, or waits for a worker.** It folds what
  exists and reports the rest as not covered. A desk pass is always complete on its own
  terms; absent workers make it thinner and honest, never late.

- **Workspaces close on independent schedules, by design.** One workspace may close at
  18:00 and another at 23:00, or a day apart. Artifacts carry `date`, `run_type`, and real
  timestamps precisely so this works: the desk folds the newest per (workspace, run_type)
  whenever it runs, and refolds later passes as fragments land. A fragment filed after a
  desk pass is not late — the next pass picks it up, and the coverage line tells the truth
  in the meantime.
- **Workers registry** — a private config declaring which workspace seats run workers and
  where each writes (see "Registry" below). A declared list, like the repo and surface
  lists elsewhere in this skill: the agent does not substitute its own judgment about
  which workspaces "feel active."

## Artifact path

```
<workspace-private-repo>/ritual-workers/YYYY-MM-DD-<run_type>.md
```

The personal workspace writes to the person repo's `ritual-workers/` directory. One file
per (date, run_type); a re-run of the same (date, run_type) overwrites its own file — git
history preserves the earlier pass. Workspace-confidential content stays in the
workspace-private repo by construction; the desk reads across repos on the same machine.

## Schema — YAML frontmatter

```yaml
---
contract_version: 1
workspace: <workspace-id>            # matches the registry key
seat: <project-id>                   # the operations seat that ran the worker
run_type: day-end                    # day-start | midday | day-end
date: 2026-08-17
started: 2026-08-17T20:05:00-04:00
finished: 2026-08-17T20:31:00-04:00
agent: "<client> (<model>) session <board-session-id>"
coverage:                            # one row per surface in the workspace's DECLARED set
  - surface: slack                   # slack | gchat | email | transcripts | docs | repos | calendar | ...
    status: synced                   # synced | partial | skipped | failed
    detail: "<window, counts, or reason — one line>"
gaps: []                             # human-readable omissions; [] only when NONE
---
```

Rules the frontmatter enforces:

- **`coverage` enumerates the workspace's full declared surface set** (its repos.yaml,
  sync configs, and established practices — the same declared lists the ritual already
  obeys). A surface missing from the list is a contract violation, not an implicit skip:
  skips are stated with `status: skipped` and a reason.
- **`gaps` is the honesty field.** Anything the run did not do that the declared set says
  it should have. An empty list is a positive claim of completeness.
- **Timestamps are real**, taken at run boundaries, never reconstructed.

## Body — fixed sections, fixed order

Every section present in every artifact; write "none" rather than omitting a section (an
absent section is indistinguishable from an unswept one).

```markdown
## Decisions needed        # items only the principal can decide, one line + pointer each
## Calendar & conflicts    # entries this workspace contributes to tomorrow's shared view
## On your behalf          # sends/drafts/replies staged or completed, with ledger refs
## Waiting on others       # open items with owners, oldest first
## Brief                   # everything else worth the desk's attention, one line each
## Backlog deltas          # additions/completions to carry into the converged plan
```

One line per item, each with a pointer (file path, thread id, ledger row) into the
workspace's own records. Detail stays workspace-side; the artifact is a summary the desk
can fold without loading the workspace.

## Desk obligations

1. **Fold newest-per-(workspace, run_type)** for the current date at every desk pass,
   using frontmatter timestamps. Mid-day artifacts supersede day-start ones per workspace;
   the desk's own pass reconciles across workspaces — reconciliation is the desk's job and
   no worker's.
2. **The coverage line is mandatory** in every produced brief: one line naming each
   registered workspace and its state — artifact folded (with run_type and finish time),
   pending (briefed but no fresh artifact), or not scheduled. A brief without a coverage
   line claims a completeness it cannot prove; write the line first.
3. **Absence is reported, never inferred around.** A registered-active workspace with no
   fresh artifact appears in the brief as *not covered* — the desk does not reconstruct
   that workspace's state from stale artifacts or its own guesses.
4. **Cross-workspace conflicts belong to the desk.** Workers cannot see them by
   construction; the desk checks the converged calendar and commitments explicitly.

## Registry

Private file (never in a public repo), e.g. `~/.synthesis/ritual/workers.yaml`:

```yaml
contract_version: 1
desk_seat: <project-id>              # the seat that owns the ritual home
workers:
  <workspace-id>:
    status: active                   # active | on-demand | dormant
    artifact_dir: <absolute path to that workspace's ritual-workers/>
    seat: <project-id>
```

`active` workers appear in every coverage line. `on-demand` workers appear only on days
they run. `dormant` workers are skipped entirely and never counted against coverage.

## Plan storage separation — fragments and the shell (added 2026-08-17; schema unchanged)

The separation the artifact path already enforces for *sync* content extends to the daily
plan itself, for one reason: **organizational data must be erasable by deleting the
organization's workspace folders.** A person who parts ways with an organization — or is
required by that organization's policy (banks, governments, regulated institutions commonly
mandate this) to purge its data on exit — must be able to remove the workspace's
repositories and be done. A converged plan file that copies workspace content into the
person-side repository defeats that with every day it accretes.

- **The worker artifact doubles as the workspace's plan fragment.** Its body sections
  (Decisions needed, Calendar & conflicts, On your behalf, Waiting on others, Brief,
  Backlog deltas) are exactly the plan-facing content for that workspace, already stored in
  the workspace-private repository. No second file, no copy.
- **The person-side daily plan is a SHELL**, holding only person-scoped and structural
  content: the coverage line; the day's timeline (the principal's time is person-scoped
  data — one calendar, one life); cross-workspace conflicts stated at the minimum
  cross-reference needed; the permanent personal section; person-scoped carryover; and
  **pointer lines** to each workspace's fragment instead of inlined workspace content.
- **Pointer convention:** a coverage-line or section entry references the fragment as
  `<workspace> → <artifact path>`. Consumers that cannot resolve pointers still show a
  legible shell; consumers that can (a console, a rendering tool) merge fragments into the
  one view at **display time**. Converged presentation, separated storage — the "one brief,
  one list, one console" constraint governs the view, not the files.
- **The erasure boundary, stated honestly:** deleting a workspace's folders removes all its
  *content*. The shell (and the person repository's git history) retains workspace *names*,
  dangling pointers, and the principal's own timeline. Content never persists outside the
  workspace folders; names as references do. Regimes that treat even event titles or the
  organization's name as erasable data should run a **strict shell**: generic labels in the
  timeline ("committed — see fragment") with all titles resolved from fragments at display
  time. The default shell carries titles; strictness is a per-person policy choice, made
  once and recorded in the workers registry as `shell: default | strict`.
- **Shared vs private repositories.** A workspace often carries two repositories: one
  shared with colleagues in that organization, and one private to the individual. The
  fragment belongs in the **private** one — it is the individual's own working record of
  the engagement (their triage, judgments, drafts, and read of what matters), and it sits
  beside the other material that is theirs alone about that organization. Both live under
  the same workspace directory, so both are removed by the same deletion; the distinction
  governs who may read the fragment while the engagement is live, not erasure.
- **Who writes what:** each worker writes only its own artifact/fragment (in its own
  claimed area); the desk writes only the shell. The desk never copies fragment content
  into the shell — it reads, reconciles, and points.
- **Consumers render, never relocate.** A tool that merges fragments for display must not
  cache merged output back into the person-side store, and must render an unresolved
  pointer as an explicit marker rather than omitting it silently — a deleted workspace or
  a worker that never ran has to stay visible as such.
- **The shell keeps the consumer's section vocabulary.** Separating storage changes WHERE
  plan content lives; it must not change WHAT the sections are called. Renderers classify
  plan sections by heading vocabulary, so a shell written with invented headings still
  renders — as undifferentiated prose — while every typed region the reader actually works
  from (what must be done today, what needs deciding, what is drafted) comes up empty. The
  plan looks blank precisely when it is full.

  A shell therefore reuses the established headings for any region it populates
  (decisions-needed, priority tasks, calendar, drafts, on-your-behalf, waiting-on, brief)
  and confines its novelty to the coverage block and the pointer lines. **Producer and
  consumer change together**, in the same session, or not at all — the same rule that
  governs any other typed artifact with a downstream reader.

  *Origin (2026-08-17/18): the first shell was written with fresh headings that read well
  and matched nothing. The file rendered, the cockpit regions did not, and the day's plan
  appeared empty to its only reader.*
- Historical plan files that predate this separation stay as they are until a deliberate
  migration project splits them; the contract governs plans produced after adoption.

## Failure semantics

- Worker fails mid-run → it still writes its artifact with `status: failed` rows and a
  populated `gaps` list. A crash that prevents even that leaves no artifact — which the
  desk reports as *not covered*. Both outcomes are visible; neither is silent.
- Desk runs with zero fresh artifacts → the brief still publishes, with a coverage line
  saying exactly that. A thin honest brief beats a rich stale one.
