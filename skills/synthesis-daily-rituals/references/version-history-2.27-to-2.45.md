# Daily rituals version history: 2.27.0 to 2.45.1 (verbatim)

Moved word for word from `version-history.md` when v5 split it to fit one read. Index: [version-history.md](version-history.md).

Contents:
- v2.45.1 — Preserve acquisition clock precision
- v2.45.0 — Connector evidence and partial source coverage
- v2.44.0 — Executable acquisition and verified saved coverage
- v2.43.0 — Bound repository evidence
- v2.42.0 — Verified ritual evidence and acquisition custody
- v2.41.0 — Concurrent-seats mode; PENDING parity under live claims
- v2.40.0 — Ownership-vs-visibility triage; the shared time-block layer
- v2.39.0 — Every sweep names its denominator; BLIND vs UNREACHABLE everywhere
- v2.38.0 — Email sync runs off a mailbox manifest; blind accounts fail the ritual
- v2.37.0 — The weekly-review query answers for one workspace; `advance --through` takes the epoch `window` prints
- v2.36.0 — The PR-queue scan dispatches by origin host; Bitbucket joins GitHub
- v2.35.0 — The pull-request queue joins the weekly review's declared sources
- v2.34.2 — The deadline sweep selects by target date across the declared plan scope; commit dates are not session dates
- v2.34.1 — The day-end installer ships its state helper as one release
- v2.34.0 — Google Chat gets a declared target set; wholesale advance is refused
- v2.33.0 — Placeholders resolve under the stable plugin path; parity checks the pointer
- v2.32.0 — The watermark gate's declared set comes from the preflight script
- v2.31.0 — Restructured under the 500-line budget
- v2.30.0 — Watermarks carry a time and a target, and a run proves its own coverage
- v2.29.0 — The open-items horizon matches what the item is
- v2.28.0 — The watermark gate cannot be walked past; ritual state derives from an append-only log
- v2.27.0 — Sync windows follow the last write, and a recorded gap blocks

## v2.45.1 — Preserve acquisition clock precision

Acquisition evidence is checked against the full current timestamp so an
observation captured earlier in the same second is not mistaken for future
evidence. Future observations still refuse advancement. Watermark selectors,
durable timestamps, and displayed values retain their whole-second format.

## v2.45.0 — Connector evidence and partial source coverage

v2.45.0 (2026-10-02): declared connector adapters connect recorded Slack reads
and workspace document reads to the existing acquisition owners. Quiet coverage
requires independent history and search controls; incomplete sources keep their
previous watermarks while proven sources can advance.

## v2.44.0 — Executable acquisition and verified saved coverage

v2.44.0 (2026-09-28): declared meeting and Slack transports connect the
existing read, save, exact-file verification and watermark owners. Incomplete
paging, source identity or archive custody refuses advancement. Full source
bodies remain in durable files while status responses summarize exact results.

## v2.43.0 — Bound repository evidence

v2.43.0 (2026-09-27): preserve exact Git repository and ref identity when
collecting ritual and portfolio evidence; refuse changed or foreign bindings.

## v2.42.0 — Verified ritual evidence and acquisition custody

v2.42.0 (2026-09-26): worker completion consumes the declared workspace's
artifact, complete coverage and actual outcome before appending a durable
receipt. Bounded writer locking, exact readback and failure retention protect
interrupted or concurrent records. Migration markers cannot open or close a
workday. Lesson candidates retain local custody and explicit acceptance.

The verified public launcher now registers the ritual helper entry points and
their required dependencies. Credential-path coverage reports tracked names
without reading secret contents. Acquisition watermarks require source-bound
coverage evidence and positive controls; unread or failed surfaces remain
visible. See [ritual evidence](ritual-evidence.md) and
[acquisition evidence](acquisition-evidence.md) for the complete contracts.
Existing owner authority, workspace separation and historical records remain
explicit; these checks do not fabricate work or native acceptance.

## v2.41.0 — Concurrent-seats mode; PENDING parity under live claims

v2.41.0 (2026-09-23): the ritual stops fighting live seats (ITEM23,
operations-seat findings 10–11). The dual-client parity check reports
PENDING with the holder named when a live seat holds install-plane
claims, and the ritual reports the line instead of refreshing clients
under the seat. Step 3a fast-forwards only branches no live seat
holds. The new Concurrent-Seats Mode section beside observer mode
states the six mechanical rules: claim file-by-file, fetch-all with
fast-forward-only-unheld, report parity without repairing, skip
shared-state maintenance while seats are live, fold peer artifacts
instead of re-running them, and release claims at end.

## v2.40.0 — Ownership-vs-visibility triage; the shared time-block layer

v2.40.0 (2026-09-20): tasks route to exactly one workspace while calendar
time stays visible to every seat ([ownership routing](ownership-routing.md)).
Step 4 applies the routing rules at intake — manifest owner, deletion-unit
test, movable-item seat — and stamps each item `owner:`/`owner_rule:`;
whatever no rule claims becomes a same-turn CANDIDATE, never
double-recorded and never dropped. The same step publishes the seat's
owned blocks (real titles, hand-entered blocks for unreachable accounts)
to `coordination/time-blocks.json` in the personal repo and calls the
chief-of-staff `overlap.py` service for the look-ahead window; conflict
reports name the movable side and the layer's denominator. Nothing here
writes to a calendar — shared reads first, agent writes a later design.

## v2.39.0 — Every sweep names its denominator; BLIND vs UNREACHABLE everywhere

v2.39.0 (2026-09-19): the coverage-state vocabulary from the mailbox
manifest spreads to the other sweeps. The code-sync report puts every
declared repo in exactly one of synced / decision / BLIND / UNREACHABLE
and closes with the denominator — "not scanned" once hid seven repos
on branches with no upstream and 39 invisible commits for weeks. The
PR queue carries the same two states per unscanned repo (unsupported
origin or missing remote is BLIND, our defect; missing clone, CLI,
or API is UNREACHABLE, the world's). The deadline sweep reports
obligations and scanned sources, not bare due counts. The doctor
step reads the new blocking/advisory severities: blocking problems
refuse commits, advisory conditions (drift, unwired hooks) degrade
protection while commits proceed.

## v2.38.0 — Email sync runs off a mailbox manifest; blind accounts fail the ritual

v2.38.0 (2026-09-18): the email step sweeps `.agents/mailboxes.yaml`
([mailbox manifest](mailbox-manifest.md)) instead of one designated
account — the class of failure was a friend's seven emails over four weeks in
an iCloud mailbox no ritual read. `scripts/mailboxes.py plan` enumerates
the due accounts; `report` judges each SWEPT / BLIND / UNREACHABLE /
DEFERRED from the watermark store and exits non-zero on any BLIND
account. UNREACHABLE (defer reason starting `unreachable:`) passes loud:
an attempted failure is information, silence is a lie.

## v2.37.0 — The weekly-review query answers for one workspace; `advance --through` takes the epoch `window` prints

v2.37.0 (2026-09-14): `ritual_state.py query weekly-review --workspace <W>`
returns the latest weekly-review record for that workspace only, and the
`summary` and `open` views scope to `--workspace` the way `last` already
did; `summary` carries each workspace's last review in its own row instead
of one log-wide field. Without `--workspace` the weekly-review query refuses
and names the accepted form, unless the log names exactly one workspace,
which it then uses and names. Origin: `record --direction weekly-review` has
required `--workspace` since v2.28.0, but the query returned the newest
review in the log regardless, so one workspace's Friday review silenced
every other workspace's owed-weekly gate — the single-slot shape v2.28.0
removed for closes, found again in the weekly review on 2026-09-14.
Day-Start Step 1 and Day-End Step 10 show the scoped command, and
`scripts/test_ritual_state.py` pins, per query view, that `--workspace` is
honored or refused and never dropped.

Also in v2.37.0 (2026-09-14): `sync_watermark.py advance --through` and `status --since` accept Unix epoch seconds — the bare integer `window` prints as `latest=` and Slack's fractional `ts` (the fraction is dropped, never rounded up) — beside ISO-8601, `YYYY-MM-DD`, and `now`; every form is stored as ISO-8601 to the second with a UTC offset, so the store's shape is unchanged. Origin: on 2026-09-14 `window` printed `latest=1789397434` and `advance --through 1789397434` refused it as not a timestamp, so the pipeline the reference itself instructs failed on every Slack target. The refusal names every accepted form, and `scripts/test_sync_watermark.py` round-trips `window`'s printed `latest=` into `advance` through the CLI and pins the reference's `advance` bullet to name the form.

## v2.36.0 — The PR-queue scan dispatches by origin host; Bitbucket joins GitHub

v2.36.0 (2026-09-10): `scripts/pr_queue_scan.py` dispatches each declared
repo by its origin host. GitHub origins are queried as before; `bitbucket.org`
origins are scanned through the `pr_queue` helper the synthesis-bitbucket
skill ships; every other host stays NOT SCANNED with the host named as the
reason. v2.35.0 reported every non-GitHub origin as unscanned, and a queue
that is named unscanned on every run is a gap the review keeps announcing
without closing — for Bitbucket-hosted repos it is now read. The rule from
v2.35.0 is unchanged: an unscanned queue must never read as an empty one, so
the hosts the scan cannot reach are still listed with a reason rather than
dropped.

## v2.35.0 — The pull-request queue joins the weekly review's declared sources

v2.35.0 (2026-09-05): Day-End Step 10 scans the pull-request queue for the
workspace's own repos. `scripts/pr_queue_scan.py --workspace <W>` reads the
workspace's `.agents/repos.yaml` — the same declaration the source-code sync
uses, so scope follows the manifest and no second list is maintained — and
reports, oldest first: review requests naming the principal, their own open
PRs, and PRs in the declared repos that nobody else was asked to review. The
scan is deliberately NOT filtered by `ritual_sync`: that flag governs whether
a working copy is fast-forwarded, not whether a repo has a request waiting on
a human, and skill sources and context repos carry `ritual_sync: no` while
still having PRs. It exits 0 always and names every repo it could not read.
Origin: on 2026-08-28 the review reported one waiting-on item past seven days
while a review request naming the principal sat 139 days old — the review had
not missed it, it had not looked. The step carried this label from the day it
landed while the frontmatter stayed at 2.34.0 and then took two patch bumps,
which is why this entry sits above two releases whose changes postdate it;
the record is ordered by version, and `scripts/test_version_record.py` now
fails when a label and the frontmatter disagree.

## v2.34.2 — The deadline sweep selects by target date across the declared plan scope; commit dates are not session dates

v2.34.2 (2026-09-09): Day-End Step 4 runs `scripts/decay_sweep.py --as-of
<verified-current-date> --plans-dir <declared-daily-plans-directory> --json`
(repeating declared roots, adding `--artifacts-dir` for worker artifacts) and
collects every unresolved `**Decays:**` date on or before today across the
complete declared plan and archive scope, with no lookback cutoff. A deadline
noticed in an older plan stays visible when due, even after a long
interruption; the previous step read only today's plan. The collector is
read-only and grants no send authority: it reports every selected, skipped,
excluded, malformed, unreadable, and refused source; missing or empty declared
roots, incomplete enumeration, invalid tags, and ambiguous identity produce
`BLOCKED` (exit 2); due candidates produce `REVIEW`; only a complete scan with
nothing due is `CLEAR`. A gap blocks a clean sweep conclusion, not the rest of
the ritual. Items may carry a stable `**Decay ID:**` so carry-forward and
re-dating keep one identity per obligation. Contract and boundaries:
[decay-sweep.md](decay-sweep.md). In the same release Day-Start
Step 1 stops treating a commit timestamp as a verified session date: dated
session entries are the evidence, `git log` and status are inspected
separately for publication and pending changes, and a disagreement between
records is reported with both sources instead of overwritten — a commit that
lands overnight, in another timezone, or after a delay does not redate the
work it records. Step 2's archive keeps the archived session's verified
workday and labels today's recording time separately.

## v2.34.1 — The day-end installer ships its state helper as one release

v2.34.1 (2026-09-06): `scripts/install_day_end.py` copies the launcher, the
nudge, and the `ritual_state.py` query helper from the same release as
executable files, so the nudge and the launcher never run against a state
helper from a different version. Reinstallation refreshes all three without
changing the selected agent unless asked, and the LaunchAgent keeps its
template schedule. The nudge queries ritual state without writing it and
stays quiet once every expected workspace has closed.

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

## v2.29.0 — The open-items horizon matches what the item is

v2.29.0 (2026-08-31): Day-End Step 7 distinguishes owed work from a backlog.
The 14-day default horizon is for something owed — blocked on a named person,
with a consequence if it slips. A list of feature ideas, article ideas, or a
bug inventory is a record of intent nobody promised by a date, so it is
stamped `(as of YYYY-MM-DD, review 180d)`; measured once on a real corpus, 17
of 38 open-item findings were wishlists ageing at the owed-work horizon. A
recorded decision parked under an open-items heading is moved under a
decisions heading rather than given a longer horizon, because the section
heading is what the checker reads. No code change; the full note is under
"Rationale notes moved from the checklists" below.

## v2.28.0 — The watermark gate cannot be walked past; ritual state derives from an append-only log

v2.28.0 (2026-08-29): both ritual checklists carry the exact
`sync_watermark.py status --workspace <W> --surface <s>` invocation with every
declared surface passed explicitly. The store only knows surfaces that have
already been written, so a status that consults only the store exits 0
straight past a declared surface that has never been swept; the command
refuses an empty surface set for exactly that reason, and a non-zero exit is
a gap to close or defer with a reason before the ritual proceeds. The same
label marks the ritual-state steps that replaced
`~/.synthesis/day-end/state.json` on 2026-09-02: `scripts/ritual_state.py`
derives per-workspace last-close, streak, and open workdays from an
append-only log (one O_APPEND write per record, capped at 2048B so appends
stay atomic under concurrent seats), and `record --date` is the logical
workday being closed, never inferred from the clock. Origin: the predecessor
kept one `last_day_end` slot written by every seat, and on 2026-09-02 one
seat's close overwrote another's; a lock would not have saved a single-slot
shape with many writers, so the shape was deleted rather than guarded.

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

