# Context protocol details

These requirements are mandatory through the skill entrypoint.

## The Architecture

### Three Tiers

```
project/
├── CONTEXT.md      # Working memory (budget: ≤150 lines)
├── REFERENCE.md    # Semantic memory (stable facts, update in place)
├── reference/      # Semantic memory, sharded — once one file is not enough
│   └── <topic>.md  # One topic per file; REFERENCE.md becomes its index
├── sessions/       # Episodic memory (archived session logs)
│   └── YYYY-MM.md  # Monthly files
└── [other files]   # Transcripts, artifacts, etc.
```

This maps to both cognitive science and systems engineering:

| Human memory | CPU cache | Synthesis equivalent | Properties |
|-------------|-----------|---------------------|------------|
| Working memory | L1 cache | CONTEXT.md | Small capacity, constantly refreshed, always loaded |
| Semantic memory | L2 cache | REFERENCE.md | Facts and relationships, updated in place, loaded on demand |
| Episodic memory | L3 cache | sessions/ | Chronological events, append-only, searched when needed |
| Procedural memory | Firmware | CLAUDE.md / AGENTS.md + lessons/ | How to do things, rules, patterns |

These are design principles, not metaphors. Each memory type has different storage, retrieval, and maintenance characteristics.

For cross-agent work, the project context files are the durable memory layer. Chat history, model memory, and compaction summaries may help within one tool, but they are not the source of truth. Claude Code, Codex, Cursor, or another capable agent should be able to resume from the same `CONTEXT.md`, `REFERENCE.md`, and `sessions/` archive.

### CONTEXT.md — Working Memory

**Purpose:** Everything the AI collaborator needs to be effective in THIS session.

**Budget:** ≤150 lines (hard). For completed projects: ≤80 lines.

**Contains ONLY:**
- Phase/status header (~5 lines)
- Current state (~15 lines)
- Active tasks with priorities (~50 lines)
- Recent session summaries — last 1-2 only (~30 lines)
- Links to REFERENCE.md and sessions/ (~5 lines)
- Budget footer (~2 lines)

**Does NOT contain:**
- Completed task checklists (archive to sessions/ first, verify, then remove)
- Session logs older than 1 week (move to sessions/)
- Stable reference facts (live in REFERENCE.md)
- Detailed historical narrative (live in session archive)
- Per-session agent provenance (attribution lines live in sessions/; at most a short `(via Codex)`-style tag in the status header when agent identity changes how to interpret state — see Agent Attribution)

**Template — new project:**

```markdown
# [Project Name] — Working Context

**Phase:** Initial
**Status:** [description]
**Last session:** YYYY-MM-DD

---

## Current State

[What exists, what doesn't, starting conditions]

## What's Next

1. [ ] [First task]
2. [ ] [Second task]

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
```

**Template — mature project:**

```markdown
# [Project Name] — Working Context

**Phase:** [Current phase]
**Status:** [Active/Paused]
**Last session:** YYYY-MM-DD

For stable reference facts: see [REFERENCE.md](../REFERENCE.md)
For session history: see [sessions/](../sessions/)

---

## Current State

- **Production:** [version, deployment status]
- **Blockers:** [if any]

*State as of: YYYY-MM-DD (round N)*  ← as-of marker; see Editing below

## What's Next — Prioritized

**High:**
1. [ ] [Task with context]

**Medium:**
2. [ ] [Task]

**Deferred:**
3. [ ] [Task — reason for deferral]

## Recent Session: YYYY-MM-DD

[Summary: what was done, decisions made, outcomes]

---

*This file follows the Tiered Context Architecture. Budget: ≤150 lines.*
```

**Template — completed project:**

```markdown
# [Project Name] — Context

**Status:** Completed
**Completed:** YYYY-MM-DD
**Outcome:** [1-2 sentence summary]

---

## Summary

[What was built/accomplished, 5-10 lines]

## Key Decisions

[Notable decisions that might matter if revisited, 5-10 lines]

---

*Completed project. For historical sessions, see [sessions/](../sessions/).*
```

### REFERENCE.md — Semantic Memory

**Purpose:** Stable facts that don't change session-to-session.

**Budget:** ≤300 lines (soft) for a **bounded** project. Exceeding it signals the scope may be too broad — the right response is usually to split the project or move narrative into `sessions/`.

**For a standing project, that reading is wrong**, and saying it anyway produces advice nobody can take. A project declared `bounded: false` in `index.yaml` — an operations seat, a standing stewardship — exists precisely to accumulate durable operating knowledge. Its reference has no natural ceiling, and "your scope is too broad" is not a defect report about a seat, it is a description of what a seat is. See **Sharding the semantic tier** below.

**Contains:**
- Project overview and goals (if not obvious from name)
- Team roster with roles
- URLs, repos, remotes, deployment configuration
- Architecture decisions and conventions
- File indexes (transcript logs, artifact locations)
- Setup and cleanup instructions

**Key property:** Update IN PLACE, not append. When a team member leaves, update the roster — do not add a dated note. When a URL changes, change the URL. This is a living reference document, not a log.

**Template:**

```markdown
# [Project Name] — Reference

Stable facts for this project. Updated in place when facts change.

---

## Quick Reference

| Resource | Location |
|----------|----------|
| [Key URL] | [value] |
| [Key command] | [value] |

## Team

| Name | Role | Notes |
|------|------|-------|
| [Name] | [Role] | [Status] |

## Architecture

[Key decisions, conventions, patterns]

## Related Files

[Index of transcripts, artifacts, external documents]
```

### Sharding the semantic tier — `reference/`

The episodic tier solved unbounded growth years ago: `sessions/` is a directory, and no single file has to hold every session. The semantic tier never got that treatment. `REFERENCE.md` was a single file with a soft cap and **no overflow mechanism**, which is fine for a bounded arc whose scope really is limited, and structurally broken for a standing project whose whole function is accumulating operating knowledge.

`reference/` is the same move, one tier over.

**When to shard.** A bounded project should not: hitting 300 lines is real information about its scope. A standing project shards when one file stops being readable — in practice around the same 300 lines.

**What changes when you do.** `REFERENCE.md` stops being the content and becomes the **index over it**:

```markdown
# [Project] — Reference

Stable facts, sharded by topic. Each entry links one file in `reference/`.

| Topic | What lives there |
|---|---|
| [People and roles](../reference/people.md) | roster, reporting lines, who owns what |
| [Tooling and auth](../reference/tooling.md) | CLIs, credentials posture, known limitations |
| [Routing](../reference/routing.md) | what this seat owns and where work goes |
```

**Budgets after sharding.** The index is working-memory-shaped and held to **≤150 lines**; each `reference/<topic>.md` gets the old **≤300**. The scope signal moves from one line count to the *number of topics* — which is the honest measure for a standing project anyway.

**The invariant that keeps sharding safe:** every topic file is linked from the index. A topic nothing points at is unreachable from session start, which makes sharding a way to lose content rather than organise it. The doctor reports an unlinked topic (`reference-index-orphan`) and a `reference/` with no index at all (`reference-index-missing`, a defect).

**Migration is not required.** A project under the budget keeps one `REFERENCE.md` and nothing changes. `bounded` defaults to `true` when unset, so projects that never declare themselves standing behave exactly as before.

**The whole vocabulary, so a finding is a remedy and not just a string.** A report names the check that fired; a name absent from this skill leaves its reader nothing to do.

| Check | Fires when | Severity |
|---|---|---|
| `reference-budget` | a **bounded** project's `REFERENCE.md` is over 300 lines | warning |
| `reference-shard` | a **standing** project's `REFERENCE.md` is over 300 lines — outgrown one file, not overbroad in scope | warning |
| `reference-index-budget` | once sharded, `REFERENCE.md` is over 150 lines — the index has started holding content again | warning |
| `reference-topic-budget` | a `reference/<topic>.md` is over 300 lines | warning |
| `reference-index-orphan` | a topic file is not linked from the index | warning |
| `reference-index-missing` | `reference/` exists with no `REFERENCE.md` index at all | defect |

### sessions/ — Episodic Archive

**Purpose:** Historical record of what happened and when. Rarely read, but searchable when historical context is needed.

**Organization:** Monthly files named `YYYY-MM.md`.

**Template:**

```markdown
# Session Archive — [Month] [Year]

Archived from CONTEXT.md on YYYY-MM-DD. See REFERENCE.md for stable project facts.

---

### YYYY-MM-DD: [Session title — what was accomplished]

[Summary: 5-15 lines per session. What was done, decisions made, outcomes.]

*Attribution — agent: … · model: … · effort: … · scope: … · verified: … · ref: …*  ← optional; see Agent Attribution
```

### Agent Attribution — recording which agent did what

Multiple agents can write to the same project files — Claude Code, Codex, Cursor, subagents, or the same tool at different model/effort settings — and git authorship often cannot distinguish them: different tools commonly commit under the same human author identity, and `Co-Authored-By` trailers are authored claims, not harness-verified facts. When agent provenance would help future work, record it explicitly.

**When to attribute.** Only when it helps future work: cross-agent handoffs; sessions where an agent's tool or capability gap shaped the scope; multi-model or subagent contributions; work whose verification status a future reader must trust or re-check. Routine sessions in a single-agent project need no attribution line. This is provenance, not telemetry — never log every edit, and never let attribution bloat CONTEXT.md.

**Format.** One italic line at the end of the session entry in `sessions/YYYY-MM.md`, one line per materially-contributing agent:

```
*Attribution — agent: <app/tool> · model: <version string or unknown> · effort: <setting or unknown> · scope: <what this agent did> · verified: <checks actually run, or none> · ref: <commit hash / artifact path or unknown>*
```

Field rules:

- **agent** — the app or tool: `Claude Code`, `Codex CLI`, `Cursor`, `Claude Code subagent (Explore)`.
- **model** — the exact model/version string, ONLY if the current session or the user explicitly provides it (e.g., the session's own environment states it). Otherwise the literal word `unknown`.
- **effort** — reasoning-effort or mode setting (`max`, `high`, `default`) when explicitly known; otherwise `unknown`.
- **scope** — what this agent contributed to this entry, one clause.
- **verified** — the verification actually performed (`plan re-run to zero`, `tests green`, `none`). Never claim a check that did not run.
- **ref** — durable pointer: commit hash or `resources/artifacts/` path; `unknown` if none exists yet.

**Unknown means unknown.** Never infer model/effort from memory, prior sessions, vibes, or git trailers. A wrong provenance claim is worse than an explicit `unknown`.

**Never record secrets.** No token values, OAuth or callback URLs, credential material, or private config values in any attribution field.

**Placement by tier:**

- `sessions/YYYY-MM.md` — the home for attribution lines (episodic, append-only).
- `CONTEXT.md` — at most a short parenthetical tag — `(via Codex)` — in the status/Last-session line, and only when agent identity changes how to interpret state. Never full attribution lines.
- `REFERENCE.md` — no per-session provenance. Stable agent facts only (e.g., "Codex sessions lack the Gmail connector; scope sweeps accordingly"), updated in place and removed when no longer true.
- `resources/artifacts/` — a substantial standalone artifact MAY open with a short Provenance block (agent / model / effort / date / verification / commit) when it will outlive its session entry.

**Cache-vs-truth still applies.** An attribution line is a claim recorded at write time by the writing agent. When provenance matters downstream, re-verify against `git log` and the artifact itself rather than trusting the line.

**Examples.**

Routine single-agent session (line optional; include once a project becomes multi-agent):

```
*Attribution — agent: Claude Code · model: claude-fable-5 · effort: unknown · scope: full sweep + session log · verified: plan re-run to zero · ref: a1b2c3d*
```

Cross-agent handoff (each agent's entry carries its own line; a capability gap that shaped scope belongs in `scope`):

```
*Attribution — agent: Codex CLI · model: unknown · effort: unknown · scope: single-stack sweep only (session lacked the Gmail connector) · verified: plan re-run to zero · ref: d4e5f6a*
```

Multi-model / subagent work (one line per contributor under the orchestrating entry):

```
*Attribution — agent: Claude Code · model: claude-fable-5 · effort: max · scope: orchestration + final review · verified: acceptance audit of subagent output · ref: b7c8d9e*
*Attribution — agent: Claude Code subagent (Explore) · model: unknown · effort: unknown · scope: repo-wide call-site inventory · verified: none (inventory only) · ref: resources/artifacts/2026-07-05-call-sites.md*
```

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
