# Durable record operating protocols

These are mandatory sections of the context-lifecycle skill, moved here intact to keep its entrypoint bounded. Resolve script paths such as `scripts/context_edit.py` relative to the skill root, not this reference directory. The matching entrypoint heading routes to the complete section below.

## Editing a Durable Context File — MANDATORY for scripted edits

A scripted edit to `CONTEXT.md`, `REFERENCE.md`, or a session log is an
assertion that a specific change was made. A bare `str.replace()` asserts
nothing: when an anchor no longer matches — because another agent legitimately
rewrote that region between sessions — the replacement silently becomes a
no-op while the surrounding "updated" message stays cheerful and false. The
result is committed, and record-versus-git checks still pass, because the file
is committed. It is simply not current.

**Never hand-roll replacement logic against a durable context file.** Use
`scripts/context_edit.py`, which fails closed:

```bash
python3 scripts/context_edit.py set-field --file CONTEXT.md \
  --field Phase --value "Round 3 complete"

python3 scripts/context_edit.py replace --file CONTEXT.md \
  --anchor "$OLD" --replacement "$NEW" [--count N] [--max-lines 150]

python3 scripts/context_edit.py insert-before --file sessions/2026-08.md \
  --anchor "## 2026-08-20" --text "$NEW_ENTRY"

python3 scripts/context_edit.py delete-line --file REFERENCE.md \
  --anchor "| Completed item | Done |"
```

It refuses, without writing, when the anchor is absent, when it matches a
different number of times than declared, when the replacement would leave the
file byte-identical, when the result would exceed a stated line budget, or when
the target is a symlink. It writes atomically and then re-reads the file to
confirm the change is actually on disk. There is no flag that makes a missing
anchor succeed. `--dry-run` previews without writing and still refuses a bad
anchor. Import `replace_once`, `set_field` or `delete_line` to use it from Python.

For coordinated changes within one file, use `apply --file F --edits edits.json`.
The edits file is a JSON array of ordered `replace`, `set-field`, `insert-before`,
or `delete-line` operations, each with an `op` and its usual string arguments.
Anchors resolve against the preceding staged result. All edits preflight before
one atomic replacement; line budget and currency checks apply once to the final
result. `--dry-run` runs the same checks without writing. This is a single-file
batch, not a multi-file transaction. Hold the normal records claim: snapshot
comparison detects intervening edits but is not an atomic concurrent-writer lock.
The staged content and mode are synced before rename, then the parent directory
is synced. A failure after rename may already have committed the edit: read the
actual target before retrying. Abrupt process loss can retain a complete staging
file; preserve its custody until the owning session reconciles it.

For several existing records in one project, use `apply-transaction --project P
--files files.json --board B --native-payload event.json` (add `--dry-run` to
preflight). Each array member has a project-relative `file`, ordered `edits`,
and optional per-file line budget/currency flags. The public editor owns this
operation; PM verifies the current native session, project, checkout and exact
claims, including `P/.record-transactions` and its initial atomic
`P/.record-transactions.init-<id>` sibling. All targets preflight before any
record changes. See [record transactions](record-transactions.md) for
the commit boundary, retained custody and managed-reader contract.

After interrupted committed intent, use `recover-transaction` with the same
project, board and native payload under the original still-valid authority.
Do not delete the active journal, release its custody, manufacture a replacement
identity, or retry edits over partial results. Missing evidence, a changed claim,
and foreign bytes remain explicit recovery refusals. Installed source and
synthetic crash tests do not establish native-client acceptance.

Use `--anchor-file`, `--replacement-file`, and `--text-file` instead of the
corresponding literal flags to read exact UTF-8 bytes without shell escaping.
Literal/file alternatives are mutually exclusive; unreadable files and symlinks
refuse. A complete Markdown-table anchor may omit only its final LF or CRLF;
partial-table protections continue to apply. A failed preflight writes nothing;
a post-write verification error requires re-reading the actual file before retry.

Line boundaries are protected too. `insert-before` requires an anchor at the
start of a line and text ending with a real newline. `replace` refuses an edit
whose outer boundary would fuse surviving lines, including repeated adjacent
matches. Whole-line deletions and deliberate restructuring inside the anchor
remain valid. To change a boundary intentionally, include the neighboring line
in both anchor and replacement. The helper preserves LF and CRLF bytes; it
does not insert or normalize separators to make an unsafe edit pass.

Use `delete-line` to remove one exact, unique physical line, including its
existing LF or CRLF ending; the anchor is the full line text without that ending.
Partial and ambiguous matches refuse. Markdown pipe tables remain a unit:
ordinary replacements cannot leave a blank or non-row line inside a table,
remove its header or delimiter while retaining its rows, or cross a table
boundary. Valid cell edits and complete data-row deletions pass. To replace
or remove an entire table deliberately, name the complete table in the anchor.
Fenced examples are not live tables. Archive durable facts before deleting them.

The helper also refuses to *create* a stale header: an edit that leaves
`**Phase:**` ahead of `**Last session:**` in the same ordinal family (round,
wave, phase, step, part) is refused with both fields named —
`--allow-header-lag` records an explicit override. Update `Last session`
first or in the same change; it may lead `Phase` mid-update. Independently,
the context doctor fails a project whose header describes an older state than
its own session log (`header-currency`), including same-day staleness where
date comparison sees nothing. Each field is judged separately, so a fresh
`Phase` cannot mask a stale `Last session`.

**Body currency.** Header freshness is necessary, not sufficient: three
real defects advanced the header while `Current State` kept routing agents to
superseded work — and a current header above stale operational sections is a
*stronger* false receipt than an obviously stale file. Operational sections
(`## Current State`, `## What's Next`) therefore end with an as-of marker:

```markdown
*State as of: 2026-08-24 (round 14)*
```

The marker converts prose currency into the structured comparison the header
already gets. With it in place: the doctor fails a section whose marker lags
the session log (`body-currency`); `context_edit.py` refuses a header advance
that leaves a marker behind (`--allow-stale-body` records an override); and
advancing a marker while its section's prose is byte-identical requires
`--state-reviewed`, which records the assertion that the section was re-read
and still holds — a silent bump would recreate the header defect one level
down. Markerless records are reported as *unverifiable*, never as clean.

The completion signal is deliberately honest: every gated edit's success line
names the body state (`as-of markers current`, `body lags`, or `body currency
unverifiable`). A tool that mechanizes the easy half of a task and prints
unqualified success for it manufactures a completion signal for partial work
— that mechanism-shaped failure caused all three real occurrences, and the
signal is the part of this design that addresses it.

Two companion rules, because the tool cannot enforce them alone:

- **Re-read before editing.** When re-taking a claim on a project another
  agent may have touched, read the current file and build anchors from what it
  says now — never from strings you remember writing. Alternating agents on
  one `CONTEXT.md` is a standing pattern in cross-agent work, not an accident.
- **Never report success you did not verify.** A message saying a record was
  updated is a claim about your own action, and nothing else in the system
  checks it.

## The Archival Protocol

### When to Archive

Archive when ANY of these conditions are true:
- CONTEXT.md exceeds 120 lines (approaching 150-line budget)
- Session logs in CONTEXT.md are older than 1 week
- A project phase transition occurs
- The user explicitly requests cleanup

### Step by Step

1. **Read** CONTEXT.md and count lines.
2. **Identify cold content:**
   - Completed task items
   - Session summaries older than 1 week
   - Stable facts that belong in REFERENCE.md
   - Detailed narratives that belong in sessions/
3. **Create files if needed:**
   - REFERENCE.md (if stable facts exist and no REFERENCE.md yet)
   - sessions/ directory
   - sessions/YYYY-MM.md for the relevant month
4. **Archive FIRST** (two-phase commit — write to destination before removing from source):
   - Session logs → sessions/YYYY-MM.md (append chronologically)
   - Stable facts → REFERENCE.md (organize by category)
   - Completed tasks → sessions/YYYY-MM.md (summarize, then remove from CONTEXT.md)
5. **Verify archives exist** — Confirm moved content is present in its destination file.
6. **Only then rewrite CONTEXT.md** with archived content removed.
7. **Verify:**
   - CONTEXT.md ≤150 lines
   - No information lost (everything archived before removal)
   - Cross-references updated (CONTEXT.md points to REFERENCE.md and sessions/)
8. **Record local readiness.** The client edit hook attributes the changed files automatically. Commit and push during an explicit remote handoff or day-end, scoped to the exact files and repository policy.

**CRITICAL: Archive FIRST, then delete. NEVER delete content from CONTEXT.md before confirming it exists in sessions/ or REFERENCE.md. Two-phase commit: write to destination, verify, then remove from source.**

**ALSO CRITICAL: local continuity and remote readiness are different states.** Do not create a network commit after every context edit. Keep the local tiers current, and publish them through explicit remote handoff or day-end.

### Decision Tree: Where Does This Content Belong?

```
Is this information needed for TODAY's work?
├── Yes → CONTEXT.md
└── No
    ├── Is it a stable fact (team, URL, architecture)?
    │   ├── Yes → REFERENCE.md (update in place)
    │   └── No
    │       ├── Is it a record of what happened during a session?
    │       │   ├── Yes → sessions/YYYY-MM.md
    │       │   └── No
    │       │       └── Is it a reusable lesson?
    │       │           ├── Yes → lessons/
    │       │           └── No → delete it
    └── Exception: completed milestones (≤10 lines) stay in CONTEXT.md
```

---

## Migration Guide

### For Projects Over 500 Lines

Full restructuring. Do NOT mechanically split — each project needs judgment about what is working memory vs reference vs archive.

1. Read the entire CONTEXT.md
2. Identify the four content types
3. Create REFERENCE.md with semantic content
4. Create sessions/ with episodic content (grouped by month)
5. Rewrite CONTEXT.md as fresh working memory
6. Verify nothing was lost

### For Projects 150-500 Lines

Moderate restructuring:
1. Extract obvious semantic content (team, URLs, architecture) → REFERENCE.md
2. Move session logs → sessions/
3. Tighten CONTEXT.md to ≤150 lines

### For Projects Under 150 Lines

Lightweight touch:
1. Add budget footer
2. If >20 lines of reference material exist, consider extracting to REFERENCE.md
3. If completed, simplify to completion summary format

---

## Project Status Transitions

| Transition | CONTEXT.md Action | Other Actions |
|-----------|-------------------|---------------|
| active → completed | Rewrite as completion summary (≤80 lines) | Simplify REFERENCE.md |
| active → paused | Add "Paused State" header with reason | Archive session logs |
| paused → active | Remove "Paused State" header, refresh | Update last_session |
| completed → archived | Freeze all files | Set status in index.yaml |
| active → spawned | Remove spawned scope | Create new project |

---

## Project Spawning

When a sub-scope exceeds the parent project's boundaries:

1. Create new project directory
2. Seed CONTEXT.md with fresh working memory (not a copy)
3. Add to index.yaml with `related:` linking to parent
4. Remove spawned scope from parent's CONTEXT.md
5. Cross-reference both projects

**The test:** Would a new team member reading only the parent's CONTEXT.md be confused by the spawned work? If yes, spawn it.

---

## Repo Families and Deletion Units

The three tiers describe how a project's context is structured. One level up sits a different question: **which repository may a piece of context live in at all?** For anyone whose work spans multiple professional relationships — clients, employers, partnerships — the durable-memory layer divides into two families with fundamentally different lifecycles:

- **The permanent knowledge root.** The person's own long-lived knowledge base — their projects, lessons, daily plans, accumulated career record. It survives every professional relationship and is never deleted wholesale.
- **Per-engagement private repos.** Workspace-scoped context repositories created for one client, employer, or engagement. Each one is a **deletion unit**: if the counterparty exercises a delete-my-data request — at contract end, under a nondisclosure obligation, during offboarding — the repo is deleted or returned *as a unit*. The repo boundary is what makes the promise keepable. Design for that day from the first commit.

### The routing test

Before writing engagement-adjacent content into any repository, ask: **would this survive the relationship's end?**

- Material the counterparty could rightfully ask to have deleted — information they shared in confidence, their internal discussions, work products they own, context learned inside their walls — routes to the engagement repo, the deletion unit.
- The person's own permanent record routes to the permanent root.

The test is about the content's rightful owner and lifecycle, not about where the content happened to arrive or which window was open when it was learned.

### Both misplacement directions fail — asymmetrically

**Engagement material in the permanent root is a compliance failure.** When the deletion request comes, the misplaced material silently survives a deletion the person promised — or is legally bound — to perform. Nothing in the permanent root's lifecycle will ever remove it, and honoring the request now requires hunting down every stray copy, which is exactly the manual process repo-level deletion units exist to make unnecessary. The failure is against someone else, and it is discovered (if ever) by the counterparty.

**Permanent material in an engagement repo is self-inflicted loss.** When the deletion unit is deleted — correctly, on request — the person's own records are destroyed along with the counterparty's data: records they were entitled to keep and may one day need. Recovery is impossible precisely because the deletion was performed properly.

Neither direction is curable after deletion day. That is why routing happens at write time, not at cleanup time.

### The ALWAYS-PRESERVE class

Some records concern an engagement but belong to the person: they document the person's own side of the professional relationship, and a counterparty's delete-my-data request does not reach them. The generic class:

- contracts and signed agreements
- pay, equity, and benefits records
- hiring and negotiation correspondence
- termination and separation records
- performance reviews, given and received
- IP assignments and licensing grants
- evidence relevant to an actual or foreseeable dispute

ALWAYS-PRESERVE material routes to the permanent root **always** — even when it arrives through engagement channels, even mid-engagement, even when the surrounding conversation is otherwise engagement-confidential. A copy may exist inside the deletion unit for working convenience; the canonical record may never live *only* there, because the deletion unit's lifecycle would take it.

### Inventories count; they never itemize

When an inventory of one repository is produced for any audience beyond its owner — a deletion attestation, an offboarding report, a migration plan — items outside the inventory's scope are **counted, never itemized**. An identifier plus a descriptive title is already a disclosure of the item's existence and subject. "Four items out of scope for this inventory" conveys completeness; a filename-and-title listing of out-of-scope material leaks the very content the repo boundary protects.

### Instance specifics live in private configuration

This section is the mechanism. Which repositories are deletion units, which root is permanent, and any additions to the preserve class are facts about one person's setup — declared in that person's private agent instructions or configuration, never in this public skill. An agent applying the mechanism reads the instance declarations first, and asks rather than guesses when a repository's family is undeclared.

---

## Measuring Context Quality

### Quantitative

| Metric | Target |
|--------|--------|
| CONTEXT.md line count | ≤150 (active) / ≤80 (completed) |
| REFERENCE.md line count | ≤300 (bounded projects); standing projects shard into `reference/` |
| REFERENCE.md as index, once sharded | ≤150 |
| `reference/<topic>.md` line count | ≤300 each |
| Unlinked files in `reference/` | 0 |
| Stale session logs (>1 week old in CONTEXT.md) | 0 |
| Completed tasks remaining in CONTEXT.md | 0 |
| Budget footer present | Yes |

### Qualitative

After reading CONTEXT.md, the AI collaborator should be able to answer:
1. What is the current state of this project?
2. What should I work on next?
3. What was done in the last session?
4. Where do I find stable reference information?

If any question cannot be answered from CONTEXT.md alone (with a pointer to REFERENCE.md), the working memory is incomplete.

---

## Executable Working State — resources/scripts/

Durable prose is incomplete when its cited computation exists only in the
session that wrote it. If a script produces a number or conclusion cited in a
durable record, preserve the script and every required input before recording
the result. Put that executable working state under `resources/scripts/` and
cite its canonical, project-relative path from the artifact or session record.

Each preserved computation carries a `resources/scripts/README.md` that names:

- the script and its purpose;
- every input, dependency, and expected output;
- the regeneration order and exact invocation;
- whether each input is immutable, append-only, or intentionally refreshed;
- the success and failure exit behavior.

Portable means a cold resumer can run the script from repository state. A
script that depends on a session-temporary download, chat attachment, shell
variable, or scratchpad value is not preserved until that required state is
also stored at a project-relative path or documented as an independently
obtainable immutable input.

The context doctor reports `artifact-cites-missing-script` when a Markdown file
directly under `resources/artifacts/` cites a nonexistent, non-regular, escaped,
or symlink-traversing `resources/scripts/` target. That check establishes path
existence and portability at the citation boundary; it does not prove the
script is correct, the inputs are sufficient, or the regenerated conclusion is
valid. Those questions remain with the artifact's acceptance evidence and the
implementation-integrity review.

The context doctor reports `skill-outputs` when a packet page under
`resources/artifacts/` is not verifiable generator output: no provenance
marker and no filed rulings is a defect (rebuild it with `build_packet.py
--strict-reader --file-into`, or remove it if superseded); a marker whose
hash disagrees with the embedded spec, or a marker with no embedded spec,
is a defect (do not hand-edit generator output); an unmarked page with
filed rulings, or a verified page with no filed `-spec.json`, is a
warning (closed record, respectively incomplete filing).

## The Context Doctor — verification, not diligence

Everything above describes what a well-maintained context layer looks like. None of it verifies that yours *is* one. That gap matters more than it first appears: the durable layer is what makes cross-agent, cross-machine resumption possible, so it is the foundation every other guarantee stands on — and until you can check it, its health is an assertion by the same agent that was supposed to maintain it.

Every other protective layer in the synthesis stack carries a health check. `synthesis-git-hooks` has `--doctor`. Conformance has its own suite. The context layer had none, which made it the one fail-open control in a stack built on fail-closed ones.

`scripts/context_doctor.py` closes that. It audits every project in every configured source and reports what would degrade a cold resumption:

```bash
python3 <skill>/scripts/context_doctor.py            # all sources from console.yaml
python3 <skill>/scripts/context_doctor.py --source ~/kb   # explicit source roots
python3 <skill>/scripts/context_doctor.py --project ~/kb/projects/alpha
python3 <skill>/scripts/context_doctor.py --json     # for consoles and rituals
python3 <skill>/scripts/context_doctor.py --quiet --readiness local
python3 <skill>/scripts/context_doctor.py --project ~/kb/projects/alpha --readiness remote
```

What it checks:

| Group | Checks |
|-------|--------|
| Tier structure | CONTEXT.md present; sessions/ once there is history to archive; REFERENCE.md once a project has accumulated stable facts |
| Budgets | CONTEXT.md ≤150 active / ≤80 completed; REFERENCE.md ≤300 (warning). A standing project (`bounded: false`) over budget is told to shard, not to narrow its scope |
| Semantic shard | once `reference/` exists: index ≤150, each topic ≤300, every topic linked from the index, and an index actually present (defect if not) |
| Cross-tier agreement | index.yaml status agrees with the CONTEXT.md header; completed projects carry `completed_date`; indexed projects have directories and vice versa |
| Freshness | CONTEXT.md and any index `last_session` agree with valid dated session entries; even a one-day record mismatch names both sources. Commit dates are separate publication evidence. Terminal projects are checked for dated activity after completion |
| Semantic current state | `CURRENT_STATE.json` validates; its bounded compiled block agrees with it; a current phase or accepted baseline older than a later release in the same record is a defect; structured projects reject a second current-looking prose authority outside the generated block |
| Durability | tier files are tracked by git; local mode reports recoverable uncommitted or ahead state as warnings; remote mode requires a clean upstream-current branch |
| Executable state | artifact citations to missing, non-regular, escaped, or symlink-traversing `resources/scripts/` targets warn; existence does not establish correctness |
| Disclosure | anything unverifiable is reported rather than skipped — unreadable status headers and freshness that cannot be established both surface as findings |

Exit codes follow the guard contract: `0` healthy, `1` defects found, `2` the doctor could not establish ground truth. The third is the important one — an unreadable source or a source outside git exits 2 rather than reporting health, because a check that cannot run must never look like a check that passed.

**Structured operational state (v1.19.0).** Mature projects may carry
`CURRENT_STATE.json` as the authoritative mutable state: project id, phase,
status, accepted baseline, controlling plan, next actions, last session,
owning coordination session, Git identity, durable-file hashes, and source
heads. `CONTEXT.md` remains the human entry point, but its bounded block between
`synthesis-current-state` markers is compiled from that object. Narrative and
historical acceptance stay in Markdown. The doctor reports
`semantic-current-state` when the object is invalid, its compiled block drifts,
its plan is missing, or mutable current-looking prose appears outside the
generated block — including `Current ...`, singular `Accepted baseline`,
`Next checkpoint`, or `State as of:` labels in context or reference shards.
Historical snapshots remain valid when their headings label them as history.
For a structured project, the state object, content hashes, and generated block
replace the older body-marker currency convention; the doctor records that
check as an explicit structured-state skip rather than demanding a second
mutable authority.

**The status vocabulary is enforced, not assumed** (v1.13.0). `status` answers
one question — does this project claim attention — with four values: `active`,
`paused`, `completed`, `archived`. Everything orthogonal is a qualifier field
(`bounded`, `superseded_by`, `wake_when`, `blocked_by`, `completed_date`), so the
vocabulary does not have to grow as new distinctions appear.

The `status-vocabulary` check reports an unrecognised status as a **defect** and
a retired one as a **warning** naming what it should become. This exists because
an unvalidated vocabulary is not a vocabulary: on a real corpus, `complete`
survived for months as a typo of `completed` and this tool *absorbed* it,
hardcoding it into the terminal set rather than rejecting it. Worse, `superseded`
was absent from that set while also not being a completion word to the header
parser, so five projects parsed as making no completion claim at all — they sat
permanently as `record-unreadable` and never received their cross-tier check. A
status the doctor does not recognise silently disables every check keyed off it,
which is the most expensive kind of quiet failure a health check can have.

**Nothing is skipped silently.** A check that cannot run reports that it could not run. Missing, invalid or unreadable dated session entries make freshness unverifiable and say so; when a CONTEXT.md has no parseable status header, the cross-check is reported as unavailable rather than passed. Silent skips are indistinguishable from clean results, and that is the property this tool exists to remove.

**A check must know when it does not apply** (v1.7.0). Several checks ask questions that only have meaning about work in progress: how fresh is this record, are its open items still current, is its status header parseable for a cross-check. Asked of a project that shipped in May, each is unanswerable *and* unactionable.

Measured on a 175-project corpus before this rule existed: **98%** of `freshness-unverifiable` and **90%** of `record-unreadable` were raised against dormant projects — completed, archived, or paused. They accounted for most of 193 warnings that nobody had acted on, and 193 unactioned warnings is the fail-open state the doctor exists to end. Applying the rule took the corpus from 193 warnings to 93 without weakening a single check that applies.

Two properties keep the suppression honest:

- **It errs toward live.** An unset or unrecognised status counts as active, because the records whose state cannot be read are the ones most likely to be wrong. Only an explicit dormant status suppresses.
- **It is paired with an inversion.** `terminal-project-active` reports a dated session entry or explicit session-field claim after the project's `completed_date`. It names the dated source and asks whether that activity changes the completion claim. A later commit alone cannot establish resumed work.

  The inversion anchors on `completed_date`, falling back to `last_session` only when the completion date is missing or unreadable. Publishing a completion record later does not move its workday or reopen the project.

The general form, worth more than the fix: **suppressing an inapplicable check is only safe when you add the check that becomes applicable in its place.** Silence alone is indistinguishable from a guard that stopped working.

**A suppression must be answerable, and its answer must expire** (v1.8.0). `terminal-project-active` shipped in v1.7.0 with a remedy the system could not accept: "record why the commits are maintenance rather than work," and no field to record it in. Worse than unactionable — it was self-sustaining, because the commits that dispose of a project are themselves post-completion commits, so resolving the finding re-created it.

The acknowledgment is an index field, and index-side is a correctness requirement rather than a preference: the freshness walk is `git log -- <project_path>`, so a marker written inside the project would re-extend newest-commit by the act of writing it.

```yaml
post_close_reviewed_through: 3e79b38...   # carries the comparison
post_close_reviewed_on: '2026-08-31'          # human readability only
```

It names a commit, not a date. A date over-covers by up to a day, and two disposition commits minutes apart either side of a recorded date would see the second silently swallowed. A sha that no longer resolves raises `post-close-review-unresolvable` as a **defect** — an acknowledgment whose evidence has vanished fails loudly rather than continuing to assert a review of history that was rewritten. One new project commit, including a bulk commit, re-arms the question. Dirty or untracked project evidence, changed index session/completion dates and archive coverage gaps cannot inherit an earlier review. Writing the acknowledgment fields alone does not invalidate it. Git ancestry bounds the reviewed snapshot; dated records determine whether there is post-completion activity to review.

**Every gated check reports its denominator** (v1.8.0). A check that finds nothing and a check that examined nothing are indistinguishable in a findings list, and so is a deliberate skip. The report now states both:

```
coverage  item-currency: examined 41, skipped 31 (31 dormant)
```

This is the general form of the pairing rule, and the cheaper half of it. v1.7.0 suppressed open-item checks on dormant projects and shipped **no paired check** — in the release whose headline principle forbids that, asserted in the changelog, in this file, and in the project record, and enforced by none of them. A printed `skipped 141` invites the question nobody asked. The pairing itself is `terminal-project-open-items`: a project claiming to be finished while still listing obligations it owes.

The general form, which covers both this and the case where a check simply reaches less than it appears to: **a guard's coverage is a claim that needs its own verification, separate from whether it passes.**

**Publication time and workday are different evidence.** Freshness uses dated session records, regardless of whether Git publishes them in a single-project commit, a bulk commit or a delayed archive pass. Git author/committer dates never replace the recorded workday. Missing narrative evidence remains explicit; a clean tree or matching commit date cannot certify current session state.

**The report cache.** Every full-corpus run writes its JSON report to `$SYNTHESIS_HOME/context-doctor/last-report.json` (v1.2.0+), so fast surfaces — SessionStart hooks, console pages — can show the latest corpus state without paying for a fresh audit. Single-project runs never touch the cache: a one-project result must not masquerade as corpus state. Suppress with `--no-report-cache`.

**Enforcement posture.** Day-start and ordinary same-machine handoffs use `--readiness local`: structural defects still fail, while attributed uncommitted or ahead state is visible as a warning. Explicit cross-machine handoff and day-end use `--readiness remote` for every project worked and fail closed until its context is committed, pushed, and upstream-current. Corpus-wide findings remain report-only.

**Where it runs.** Day-start refreshes the corpus cache in local mode. Day-end and explicit remote handoff run per-project remote mode. SessionStart and Synthesis Console surface the cached result. The JSON output includes its readiness mode so a local pass cannot masquerade as remote readiness.

---

## Context as Infrastructure

In traditional engineering, code is managed as infrastructure — version control, CI/CD, testing, deployment. In synthesis engineering (human-AI collaborative development), there is a third infrastructure layer: **context infrastructure** — the structured information that enables an AI collaborator to be effective across sessions.

The three infrastructure layers:

1. **Code infrastructure** — git, CI/CD, deployment (solved by traditional engineering)
2. **Knowledge infrastructure** — lessons, runbooks, compiled knowledge bases (the organizational learning layer)
3. **Context infrastructure** — working memory, reference facts, session history (the novel contribution — no equivalent in traditional engineering because human engineers carry context in their heads)

---

## Evolution Stages

1. **Ad hoc** — Re-explain everything each session (most AI users today)
2. **Monolithic** — Single context file that grows forever (common early approach)
3. **Tiered** — Working memory + reference + archive with lifecycle management (this skill)
4. **Compiled** — Context automatically assembled from project state, code, and history (future vision)

Stage 3 is the 80/20 solution that makes long-running AI-assisted projects sustainable. Stage 4 is the long-term vision where context at session start is compiled from live project state rather than manually maintained.

---

## Local Continuity and Remote Readiness Protocol

Context is maintained continuously, but it is not published after every
prompt or response. The system exposes three honest states:

- **LOCAL_READY:** project tiers and working-tree edits are available on the
  shared local filesystem. PostToolUse records every repository edit in a
  client-session manifest; Stop adds an atomic content receipt when such edits
  exist. A clean task with no project-file edits needs no empty receipt. Claude
  Code and Codex can switch on the same machine without a commit or network
  call.
- **LOCAL_RECOVERABLE:** an interrupted task left its edit manifest but never
  reached Stop. The receiving client reads project files, Git status and diff,
  the controlling plan, and the manifest before continuing.
- **REMOTE_READY:** complete source-repository branch heads are clean and
  equal to their fetched upstreams;
  private project context has been committed and pushed in exact-path batches;
  pending manifests are retired; remote-mode context doctor and conformance
  pass.

### Automatic same-machine handoff

Before a natural pause, the agent updates CONTEXT.md, REFERENCE.md, the
current session log, plan artifacts, and index.yaml as the work requires. It
releases or narrows coordination claims. The hooks record local evidence.
Rajiv does not run a lifecycle command, save state manually, or wait for a
network commit before opening the project in the other client.

A new client resolves the named project from projects/index.yaml, reads the
durable tiers and linked plan, then treats Git status and diff as newer truth
than cached prose. If a task was interrupted, it reconstructs the incomplete
work from the attributed manifest and working tree rather than discarding it.

### Explicit cross-machine handoff

Before changing computers, invoke synthesis-mac-sync in remote-handoff mode.
That workflow checks coordination, refreshes project tiers, publishes source
repositories under their own branch and review policies, flushes exact private
context paths, runs the doctor and conformance in remote mode, and verifies
upstream equality. Day-end performs the same transition automatically.

On the destination computer, synchronize repositories first, verify no
divergence or overlapping lease, then resume through the normal Session Start
Protocol. Offline, behind, diverged, or policy-blocked state is not
REMOTE_READY and must be reported explicitly.

### Scope and index safety

Never run a workspace-wide commit over dirty files. Remote publication uses
only session-attributed context paths. Source repos follow their own branch,
review, and deployment policies. Before every commit, inspect status and the
staged index; do not include another session's paths. Never bypass hooks.

Use synthesis-repo-guard for local receipts and pending publication;
synthesis-agent-conformance `continuity --readiness local|remote` for the two
gates; and context_doctor with the matching readiness mode.
