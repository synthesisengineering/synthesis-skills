# The context doctor — verification, not diligence

## Contents

- [Why it exists](#why-it-exists)
- [Running it](#running-it)
- [What it checks](#what-it-checks)
- [Lessons built into it](#lessons-built-into-it)
- [Where it runs](#where-it-runs)

## Why it exists

Everything in the tiered architecture describes what a well-maintained context layer looks like. None of it verifies that yours *is* one. That gap matters more than it first appears: the durable layer is what makes cross-agent, cross-machine resumption possible, so it is the foundation every other guarantee stands on — and until you can check it, its health is an assertion by the same agent that was supposed to maintain it.

"The layer every other guard depends on was the one layer with no guard" (origin
commit, 2026-07-31). `scripts/context_doctor.py` is that guard. It runs on
demand and in the rituals, never in a per-call hook (R1.5).

## Running it

```bash
python3 <skill>/scripts/context_doctor.py                        # every knowledge root
python3 <skill>/scripts/context_doctor.py --root ~/workspaces/w/ai-knowledge-w
python3 <skill>/scripts/context_doctor.py --project <root>/projects/<id>
python3 <skill>/scripts/context_doctor.py --root <root> --json   # the full report
```

With neither flag it audits every knowledge root named by `knowledge_roots` in
`~/.synthesis/v5/config.json`, else every `~/workspaces/*/ai-knowledge-*`,
skipping those that hold no projects. A root named with `--root` must hold a
`projects/` folder.

Exit codes follow the guard contract: `0` healthy, `1` defects found, `2` the
doctor could not establish ground truth. The third is the important one — an
unreadable source, a source outside git, or a scan that found nothing to audit
exits 2 rather than reporting health, because a check that cannot run must
never look like a check that passed.

The text report leads with this session's active project (its full list of
findings, each with a remedy), then counts the rest: how many projects have
defects, how many only warnings, how many are clean, and the names and check
names of those with defects. A signal inside 200 warnings is not a signal, so
other projects' warnings are counted, not listed; run `--project` for any one
project's full list, or `--json` for everything. It ends with `HEALTHY` or
`DEFECTS` and the totals, after a `coverage` line for each check that skipped
projects.

## What it checks

| Check | Severity | Fires when |
|---|---|---|
| `context-present` | defect | no CONTEXT.md, or an empty one; an index entry with no folder (unless archived) |
| `context-budget` | defect | CONTEXT.md over 150 lines, or over 80 for a completed project |
| `reference-budget` | warning | REFERENCE.md over 300 lines, or over 150 once `reference/` exists; told to shard when `bounded: false` |
| `status-agreement` | defect | CONTEXT.md reads completed and index.yaml does not, or the reverse; a project folder with no index entry; project folders with no index.yaml (warning when the header is unreadable on a live project) |
| `status-vocabulary` | defect / warning | an unknown index status (defect); a retired one: `new`, `ongoing`, `superseded`, `complete` (warning naming its replacement) |
| `completed-date` | warning | a completed project with no `completed_date` |
| `freshness` | defect | CONTEXT.md `Last session` or index `last_session` behind or ahead of the newest dated session entry |
| `freshness-unverifiable` | warning | no valid dated session entry, an unreadable log, or an impossible date |
| `header-currency` | defect | a header field's round, wave, phase, step or part number behind the newest entry of that day |
| `header-lag` | defect | `Phase` moved to a later ordinal than `Last session` in the same family |
| `body-currency` | defect / warning | a `*State as of:*` marker behind the log (defect); an ordinal-paced record with no markers and no current-state block (warning) |
| `item-currency` | warning | a stamped open item past its review horizon; a live open list with no stamps; a malformed or impossible stamp |
| `terminal-project-active` | warning | a dated session after the completion date |
| `terminal-project-open-items` | warning | a completed project still listing unchecked open items |
| `post-close-review-unresolvable` | defect | `post_close_reviewed_through` names no commit in the repository |
| `uncommitted-context` | warning | uncommitted files under a project, or an uncommitted index.yaml |
| `untracked-context` | defect | CONTEXT.md or REFERENCE.md ignored or excluded by git |
| `unpushed-context` | defect / warning | no remote, detached HEAD or no upstream (defect); commits touching records not yet pushed (warning) |

## Lessons built into it

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

**Status wins over Phase.** The leading clause of the Status header is the
author's verdict ("Active — Phase 4 is COMPLETE" is active), "not complete" is
never read as completed, and Phase is consulted only when Status says nothing:
a project can be in a "Triage — inventory complete" phase while its status is
squarely Active.

**Nothing is skipped silently.** A check that cannot run reports that it could not run. Missing, invalid or unreadable dated session entries make freshness unverifiable and say so; when a CONTEXT.md has no parseable status header, the cross-check is reported as unavailable rather than passed. Silent skips are indistinguishable from clean results, and that is the property this tool exists to remove.

**A check must know when it does not apply** (v1.7.0). Several checks ask questions that only have meaning about work in progress: how fresh is this record, are its open items still current, is its status header parseable for a cross-check. Asked of a project that shipped in May, each is unanswerable *and* unactionable.

Measured on a 175-project corpus before this rule existed: **98%** of `freshness-unverifiable` and **90%** of `record-unreadable` were raised against dormant projects — completed, archived, or paused. They accounted for most of 193 warnings that nobody had acted on, and 193 unactioned warnings is the fail-open state the doctor exists to end. Applying the rule took the corpus from 193 warnings to 93 without weakening a single check that applies.

Two properties keep the suppression honest:

- **It errs toward live.** An unset or unrecognised status counts as active, because the records whose state cannot be read are the ones most likely to be wrong. Only an explicit dormant status suppresses.
- **It is paired with an inversion.** `terminal-project-active` reports a dated session entry or explicit session-field claim after the project's `completed_date`. It names the dated source and asks whether that activity changes the completion claim. A later commit alone cannot establish resumed work.

The general form, worth more than the fix: **suppressing an inapplicable check is only safe when you add the check that becomes applicable in its place.** Silence alone is indistinguishable from a guard that stopped working.

**A suppression must be answerable, and its answer must expire** (v1.8.0). The acknowledgment is an index field, and index-side is a correctness requirement rather than a preference: a marker written inside the project would itself be a new project commit.

```yaml
post_close_reviewed_through: 3e79b38...   # carries the comparison
post_close_reviewed_on: '2026-08-31'          # human readability only
```

It names a commit, not a date. A date over-covers by up to a day, and two disposition commits minutes apart either side of a recorded date would see the second silently swallowed. A sha that no longer resolves raises `post-close-review-unresolvable` as a **defect** — an acknowledgment whose evidence has vanished fails loudly rather than continuing to assert a review of history that was rewritten. One new project commit, including a bulk commit, re-arms the question, and so does uncommitted work in the project.

**Every gated check reports its denominator** (v1.8.0). A check that finds nothing and a check that examined nothing are indistinguishable in a findings list, and so is a deliberate skip. The report states both:

```
coverage  item-currency: examined 41, skipped 31 (dormant)
```

The pairing for the item-currency suppression is `terminal-project-open-items`: a project claiming to be finished while still listing obligations it owes. The general form, which covers both this and the case where a check simply reaches less than it appears to: **a guard's coverage is a claim that needs its own verification, separate from whether it passes.**

**Publication time and workday are different evidence.** Freshness uses dated session records, regardless of whether Git publishes them in a single-project commit, a bulk commit or a delayed archive pass. Git author/committer dates never replace the recorded workday, and a bulk commit touching many projects is a session for none of them. Missing narrative evidence remains explicit; a clean tree or matching commit date cannot certify current session state.

**A new convention starts as a warning.** Item stamping turned whole corpora red the day it landed when it was a defect; warnings surface it without blocking anyone, and defects stay reserved for structural problems.

## Where it runs

Day-start and day-end run it across the roots; a session runs `--project` on its
own project when it suspects drift or before a handoff. Uncommitted and
unpushed records are warnings, because the same Mac needs no commit (R1.3);
`synthesis handoff` is the step that refuses to call unpublished records ready.
