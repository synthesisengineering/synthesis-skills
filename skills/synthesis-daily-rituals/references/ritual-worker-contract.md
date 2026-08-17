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
  that workspace's context only. Two equally valid modes:
  1. an **attended session** rooted in the workspace (its own claims, its own context);
  2. a **desk-dispatched subagent** running in an isolated context against the
     workspace's paths.
  The desk never loads workspace detail inline; it reads worker summaries.
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

## Failure semantics

- Worker fails mid-run → it still writes its artifact with `status: failed` rows and a
  populated `gaps` list. A crash that prevents even that leaves no artifact — which the
  desk reports as *not covered*. Both outcomes are visible; neither is silent.
- Desk runs with zero fresh artifacts → the brief still publishes, with a coverage line
  saying exactly that. A thin honest brief beats a rich stale one.
