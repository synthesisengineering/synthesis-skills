# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

## [4.69.0] - 2026-08-30

**`synthesis-message-guard` engine v1.3.0 — signature wire forms become
mechanical.** One day after the per-platform signature doctrine shipped, a
persona-signed email to executives went out `body_format: plain` — composed
from a compaction summary instead of the loaded skill — so the signature
rendered as a bare visible URL and dropped its method link. Correct,
freshly-updated, ABSOLUTE doctrine naming the exact tool and parameter did
not bind, because nothing read it and nothing checked the result.

- New optional `signature_link_enforcement` config: when an outgoing
  message carries a persona marker, the gate refuses (1) persona-signed
  email without `body_format: "html"`, (2) markdown link notation in email
  bodies, and (3) any configured persona domain appearing as visible text
  rather than inside a link construct (href, Slack mrkdwn, or markdown
  notation) — with a configured exempt list for genuinely link-incapable
  channels, where the visible form is the legitimate form.
- Unsigned traffic is never taxed: the checks trigger only on marker
  presence. Absent config = checks off; adopt deliberately.
- The self-attested branding boolean in grounding ledgers now has a
  mechanical backstop: the gate verifies the link form itself instead of
  trusting the typed field.

## [4.68.0] - 2026-08-30

**`synthesis-autopilot` v2.0.0 — unattended time is a scheduled property.**
The motivating incident: an overnight delegation engaged the mode correctly,
ran two phases, and then its turn ended — nothing runs between turns, so the
session idled all night (a mid-night reboot passed unnoticed) and the phase
that was the point never started. Every discipline held; the work still did
not happen.

- **Continuation contract:** an engagement whose horizon exceeds the current
  turn must establish a VERIFIED continuation mechanism before its first turn
  ends (background work that re-invokes the session, self-scheduled wakeups,
  scheduler/cron re-entry, or a declared principal-side relaunch) — or say
  plainly that it cannot run unattended. A survival table (turn end / session
  death / reboot) matches mechanism to horizon; long horizons layer a
  scheduler-class dead-man's switch under the inner loop.
- **Mechanical stop-gate:** new `scripts/autopilot_gate.py` + a plugin Stop
  hook refuse to let a session stop while a registered engagement is active,
  unfinished, and has neither a recorded continuation nor an alerted blocker
  nor an honest close. Abandoned engagements block later stops by design.
- **Runaway and budget control:** plan files gain Continuation, Budget, and
  Cycle-ledger sections; `autopilot_gate.py cycle` refuses to record a wake
  that advanced nothing and names no external wait — a bare spin cannot be
  logged. Stop conditions: goals met · blocker + alert · budget + alert.
- **Capability probe before asserting absence:** a blocker claiming a
  capability is missing must carry probe evidence — an agent that wrongly
  believes it is blocked stops (a headless CLI was reported unreachable from
  stale memory in the incident's aftermath while the same session had been
  using it).
- **Volatile-state rule:** scratchpad dies at reboots; derived state moves
  into the project at EVERY phase boundary, not only at close.
- **Adversary at scope time:** dispatching the counterpart during scope
  definition (not only review) caught silently dropped artifacts in the real
  case; now doctrine for discovery-shaped phases.

## [4.67.0] - 2026-08-29

- **`synthesis-agent-correspondence` v3.1.1 — the send path is part of the
  channel.** A provider-composed send path can rewrite clean hrefs at
  ingestion (observed live: Gmail's composer wrapping every link in an
  expiring redirect), while a raw-MIME path stores the bytes you built.
  Prefer the byte-faithful path and verify a path once by reading the
  stored message back in raw form. Proven by raw-MIME comparison of two
  drafts filed minutes apart through the two paths.

## [4.66.0] - 2026-08-29

- **`synthesis-agent-correspondence` v3.1.0 — signature links render natively
  per channel.** The persona name in a signature is a named hyperlink on every
  channel that can render one; the visible-URL form is a last-resort fallback,
  never a choice. Email is the load-bearing case: markdown link syntax never
  renders in mail clients, so email sends and drafts carry an HTML body with
  real anchors, with the plain form as the multipart alternative. Motivated by
  a live Gmail signature that displayed its URL wrapped in a provider redirect
  because the body went out as plain text.

## [4.65.0] - 2026-08-29

Three fail-closed controls, each from a board-filed defect that had waited
for an owner.

- **`synthesis-skills-manager` release.py verifies installed CONTENT, not
  only versions.** `verify.<client>.content` compares every source
  `skills/` file byte-for-byte against the installed tree and refuses
  success on drift — closing the 2026-08-24 false-green where an unbumped
  version left one client loading stale files while both reported current.
  Version parity is not content parity; now the release gate knows it.
- **`synthesis-context-lifecycle` context_currency.py fails closed on a
  zero scan.** Pointed at a directory holding no project records (the
  documented misuse: a project's own subdirectory), it now exits 2 naming
  what it expected instead of printing a green zero-finding result, and a
  project directory carrying CONTEXT.md at its root is audited directly —
  matching the sibling doctor's `--project` convention.
- **`synthesis-message-guard` doctor gains two config controls.** A
  pattern authored with surrogate-escape sequences (which can never match
  real decoded text — the 2026-08-07 dead-emoji-pattern incident) now
  fails the doctor, and `doctor_clean_controls` in patterns.json runs
  canonical real messages through the live scanner so a pattern change
  that starts blocking legitimate traffic fails loudly (the 2026-08-03
  incident class).

## [4.64.0] - 2026-08-29

### Added

- **`synthesis-context-lifecycle` v1.15.0 — captured directives cannot fall
  through silently.** A principal directive was captured in an intake
  artifact, endorsed in prose, and routed to no numbered work; nothing
  warned for four days, exactly as the intake itself predicted ("not
  evaluating is the only bad outcome, and it is the one that happens by
  default"). The context doctor now warns (`intake-routing`) on any
  intake-class artifact — filename carrying intake/brief/directive/catalogue
  — that CONTEXT.md never references and that carries no terminal
  `**Routed:**` / `**Declined:**` / `**Superseded:**` marker line. The check
  is mechanical coverage per the extraction taxonomy: the script narrows,
  and whether a recorded routing is honest stays the reader's judgment.
  Five fixtures pin the failure shape, both coverage paths, the
  outputs-are-not-asks boundary, and that a mid-sentence mention of the
  marker is not a routing.

## [4.63.0] - 2026-08-29

The repair release for the external adversarial review of 4.55.0–4.57.0
(R-02: a second vendor's model reviewing four releases it did not write,
from detached historical worktrees and runtime probes — 14 findings, seven
ship-blocking). Every valid runtime and doctrine finding is repaired here;
the review's two historical manifest-closure findings stand as audit records
of already-shipped transactions.

### Fixed

- **`synthesis-context-lifecycle` v1.14.0 — item currency no longer fails
  open.** A suffix that looks like a stamp but is not one ("(as of
  yesterday)") passed as stamped, and a date-shaped impossibility
  ("2026-02-30") was silently skipped; both now surface as
  `item-marker-malformed`. An explicit `review 0d` horizon is honored
  instead of being silently replaced with the 14-day default. The review
  ledger's expiry suppression is per lifecycle, not per item text: an item
  expired, carried, and re-stamped records its later expiry as the new miss
  it is, with the governing stamp on every new event.
- **`synthesis-daily-rituals` v2.28.0 — the blocking gap gate cannot be
  walked past.** `sync_watermark.py status` refuses an empty surface set:
  the store only knows surfaces already written, so a store-only status
  exits 0 straight past a declared surface that has never been swept. Both
  ritual checklists now carry the exact status invocation with every
  declared surface passed explicitly — the release prose said to run it and
  no operational step did.
- **`synthesis-slack-sync` v3.7.0 — the sweep consumes preflight instead of
  contradicting it.** v3.6.0 banned config-derived ids while the numbered
  steps still said "for each channel in the config." Step 0 now defines the
  mandatory resolved-target preflight; Steps 1/3/3b iterate only its output;
  an empty resolved set refuses the sweep; unresolved surfaces are reported
  as unresolved. Stale frontmatter metadata caught up.
- **`synthesis-meeting-transcripts` v0.9.0 — "declared means fetched" gets
  an execution path.** Step 0 enumerates the declared window, fetches every
  member, and accounts for every member with machine-readable unclosed
  gaps; the single-meeting protocol serves explicit requests only. Stale
  frontmatter metadata caught up.
- **`synthesis-decision-packet` v1.3.0 — ids survive browser coercion.**
  Row ids must be non-empty strings: JSON `1` and `"1"` become the same
  localStorage key, so JSON-distinct ids could silently share saved state.
  The schema comment claiming a recommendation "pre-selects" a button now
  says marked-never-pre-selected, matching the shipped behavior, and the
  control-marker fixture is mutation-hardened — it previously passed with
  the marker implementation deleted.

## [4.62.0] - 2026-08-29

### Added

- **The handoff queue reaches the public toolkit.** `synthesis-project-management`
  v2.7.0 ships `scripts/handoff.py`, generalized from the working project
  reference that removed a principal from twenty-plus prompt-courier
  crossings in one engagement: a writer stores the counterpart's prompt as a
  durable, sha256-pinned file under `resources/handoffs/`, the queue is
  written atomically, and `read` refuses a payload whose bytes changed after
  handoff. Reader identity is fail-closed — `--as` or
  `SYNTHESIS_HANDOFF_SELF`, never a guess, because a guessed identity could
  claim another agent's work. Nothing self-triggers: an agent acts on the
  queue only when the principal's protocol says the other side is done.
  Eleven tests, including the doctrine contracts.
- **Autopilot calls the decision packet instead of describing one.**
  `synthesis-autopilot` v1.4.0 wires `synthesis-decision-packet` in as the
  batched-questions mechanism its protocol always required: simple user-only
  batches stay chat prompts, complex batches are built with
  `build_packet.py` — never reimplemented inline — and the packet's
  integrity rules travel with it (recommendations marked, never
  pre-selected; bulk recorded as bulk; one packet is one round-trip against
  the plan's budget). Packet rows are rebuilt against any principal
  corrections issued since drafting, so a correction-erased row cannot ride
  through a rebuild. The handoff queue is named as the agent-to-agent
  transport; queue and packet together are the two directions that remove
  the principal as transport.

### Changed

- **Schema-2 acceptance manifests may name any consume-acceptance boundary.**
  `synthesis-implementation-integrity`'s validator previously accepted
  exactly one receipt consumer — the public release gate — which made an
  honest transaction-bound gate impossible for any other repository; three
  private releases shipped in one week on suite-green alone for lack of one.
  The validator now enforces a format contract
  (`*.consume-acceptance.vN`), and honesty stays enforced where it is
  checkable: every consumer verifies at its own boundary that the receipt
  names itself, exactly as the public release gate already does.

## [4.61.0] - 2026-08-29

### Added

- **`synthesis-decision-packet` v1.1.0 — the reader contract.** The origin
  measurement gained a dark twin, measured on the same principal: a 15-row
  packet written in project-internal language collected **0 of 15**
  decisions — every mechanical property worked and none of it mattered,
  because the rows named things only the authoring session knew. The
  principal's verdict: "written in some alien or machine language."
  Structure without comprehension collects nothing.

  A packet is now doctrinally a stranger-read document, authored against
  `synthesis-reader-briefing`'s four questions. The spec gains `audience`
  (who reads this and what they already know), a packet-level `glossary`
  (one-clause meanings, rendered as a collapsible band), and per-row
  `impact` blocks stating the consequences of accepting and of declining
  the recommendation — in the principal's terms, never internal treatment
  vocabulary. The generator renders all three, warns on missing
  audience/impact, and refuses outright under `--strict-reader`, which the
  skill requires for any packet handed to a principal. Options are to be
  labeled by consequence, and internal IDs may chip but never name a row.
  Seven new regression tests; existing specs build unchanged.

## [4.60.0] - 2026-08-29

### Added

- **`synthesis-content-quality` v4.2.0 — restored philosophy layer and
  corpus-level review.** The March 2026 runbook-to-skill conversion carried
  the criteria forward and dropped the framing sections around them. They are
  restored verbatim-faithful in `references/philosophy-and-application.md`:
  the quality problem and the five characteristics of AI slop, the critical
  understanding caveats, the dual-use (GAN-dynamic) improvement philosophy,
  application guidance for detection-tool builders and for readers, the path
  from "was this AI?" to "is this good?", and the before/after revision
  example. The executable no-removals gate proves the restoration changed no
  pre-existing rule line (fidelity to the pre-migration source is anchored by
  the source snapshot preserved in the author's project records, outside this
  repo); the four-axis inference boundary governs wherever the restored
  framing touches authorship, restated inline where the restored tool-builder
  checklist could otherwise be read as licensing origin scoring.

  The same version adds **corpus-level review**: a defect class per-artifact
  review cannot see by construction — repetition that only appears when a
  body of work is read together (thirty staged articles shared constructions
  every individual review passed). `scripts/corpus_repetition.py` takes a
  corpus or a titles list and reports maximal cross-document word runs with
  thresholds that survive ordinary English (function-word runs filtered,
  high-document-frequency runs classified as boilerplate candidates, ignore
  lists with containment semantics) plus batch title-shape measurements
  (repeated two-word openings, watch-token concentration,
  imperative/second-person share). Sixteen deterministic tests ship with the
  tool — the original acceptance fixtures, including the
  cure-worse-than-the-disease case where a replacement title set must be
  measured on the same axes as the diagnosis, plus five adversarial
  regressions from the pre-release review (frontmatter without a trailing
  newline, a distinct document pair's run surviving a longer run elsewhere,
  small-corpus boilerplate misclassification, mirrored-tree content
  deduplication, and a `--strict` mode that refuses to exit clean while
  boilerplate candidates await confirmation). The tool measures; the reviewer
  adjudicates; nothing it reports establishes authorship.

- **`synthesis-article-writing` v2.3.0 — Phase 4 publication-package
  review.** A real 30-article batch passed full-body review 29/30 and then
  failed a title-only skim (6 keep / 8 tune / 16 replace), with two
  descriptions broadening their bodies' claims and 21 stale slugs from
  superseded headlines. The new phase reviews the package, not the draft:
  the title-only stranger test as an executable per-article obligation (six
  recorded fields; a description cannot rescue a failed title row; batch
  review requires the full N-row disposition table), the newcomer entry lens
  (hype is the forbidden repair), the title/description/lede/body truth
  contract extended to section headings, batch headline-monotony review with
  a batch-shape budget and mandatory re-measurement of any replacement set,
  the positive reader-value row, and the slug/metadata closure invariant for
  unpublished articles (deterministic re-slug or a recorded exception —
  "unchanged" is not an adjudication; a clean build proves consistency, not
  correctness). Phase 3 gains lede protection from provenance scaffolding
  (standfirst → note → body) and two-axis semantic sibling search (within
  the article and across the batch). Seventeen worked acceptance fixtures,
  including a recorded negative result, live in
  `references/publication-review-fixtures.md`. A load-with contract states
  when the framing plane (reader briefing, content framing, this skill)
  must join the prose stack. Three pre-migration prohibition lines lost in
  the conversion are restored under Ethical Storytelling.

- **`synthesis-reader-briefing` v1.1.0 — series-dependency contract.** Five
  short fields and exactly three output states: `standalone`, `standalone
  after compact context`, or `true prerequisite` (which requires a link plus
  a one-sentence reason). Dependency drives linking; blanket cross-reference
  quotas produce formulaic over-context and are explicitly rejected.

- **`synthesis-fact-checking` v2.1.0 — circular grounding.** A new terminal
  class in the citation graph, DERIVATIVE-SELF: the claim's "supporting
  source" is a document the author wrote from the same claim. Doctrine
  repeating a claim is the claim republished; propagation cannot upgrade
  source grade. (SKILL.md remains marginally over the 500-line guideline, a
  pre-existing condition this release did not restructure.)

### Changed

- **`synthesis-content-framing` v1.1.0** — the blanket "at least one
  cross-reference to another article in the series" gate is replaced by the
  dependency-driven rule from the reader briefing's series-dependency
  contract. This is the release's one non-additive change, made on the
  recorded rejection of formulaic over-context in the same evidence intake
  that motivated the batch gates.

## [4.59.0] - 2026-08-29

### Added

- **Two hygiene surfaces for records that accumulate without an outflow.** Both
  fix the same shape of defect at different layers: a signal the system already
  records, that nothing ever promotes to a decision.

  **`synthesis-daily-rituals` v2.27.0 — portfolio review.** A project index has
  an intake and no outflow: projects enter and never leave. On the corpus that
  motivated this, 37 of 63 projects claiming to be live had not moved in over 90
  days, one of them for 619, and nothing surfaced it. The context doctor already
  computed freshness but reported it among 200+ warnings, and a signal inside 200
  warnings is not a signal. `scripts/portfolio_review.py` names at most three
  stale-active projects per run and asks one question about each: close it, pause
  it, or pick it up. It discovers indexes through `console.yaml`, exits 0 under
  every degraded input so it can never break a ritual, and never decides.

  **`synthesis-project-management` v2.6.0 — coordination-claim review.** A dead
  session's `active` row is worse than a stale project: it does not merely
  clutter, it denies work to every future claim that overlaps it. Three abandoned
  rows blocked real work for up to ten days on the corpus that motivated this.
  `coordination.py stale` reports quiet claims with physical evidence — a claimed
  worktree that no longer exists is close to proof, while elapsed time alone is
  not — and prints the exact release command **without ever running it**.
  Releasing another session's claim stays the user's decision; an agent that
  could clear one on a timer would turn the advisory lock into a suggestion.

## [4.58.0] - 2026-08-29

### Added

- **`synthesis-context-lifecycle` v1.13.0 — the status vocabulary is enforced,
  not assumed.** An unvalidated vocabulary is not a vocabulary. Two failures on
  a real 127-project corpus made the case. `complete` survived for months as a
  typo of `completed`, and rather than reject it the doctor *absorbed* it,
  hardcoding the typo into its terminal set. Worse, `superseded` was absent from
  that set while also not being a completion word to the header parser, so a
  superseded project parsed as making no completion claim at all: it sat
  permanently as `record-unreadable` and never received its cross-tier check.
  Five projects were silently exempt, two of them for months.

  A status the doctor does not recognise silently disables every check keyed off
  it, which is the most expensive kind of quiet failure a health check can have
  — indistinguishable from passing.

  This release declares the canonical set — `active`, `paused`, `completed`,
  `archived` — where status answers exactly one question: does this project
  claim attention. Everything orthogonal becomes a qualifier field (`bounded`,
  `superseded_by`, `wake_when`, `blocked_by`, `completed_date`), so the
  vocabulary should not have to grow as new distinctions appear. The new
  `status-vocabulary` check reports an unknown status as a defect and a retired
  one as a warning naming its replacement; retired values stay readable so an
  unmigrated corpus is diagnosed rather than rejected. Run against a live corpus
  the check immediately found two retired statuses in workspaces that had not
  been migrated.

## [4.57.0] - 2026-08-28

### Added

- **`synthesis-decision-packet` reaches both clients.** The skill collects N
  parallel decisions into one self-contained HTML packet a principal can work
  through in a single sitting, with `scripts/build_packet.py` refusing to emit a
  broken packet (duplicate ids, a recommendation outside its own option set, a
  packet with no recommendations). It was merged without a version bump,
  changelog entry, or acceptance declaration, so it existed in source while
  neither client could load it — built and merged is not shipped. This release
  declares and ships it.

### Fixed

- **A test name that contradicted the behaviour it guarded.** The packet
  deliberately pre-selects nothing: pressed state is computed from the saved
  decision for a row and from nothing else, because a packet that opens fully
  decided cannot distinguish "I agreed" from "I never looked" and would report
  decisions nobody made. The fixture asserting the recommendation is *marked on
  the control* was nonetheless named `..._is_a_preselected_button_...`. A name is
  read far more often than a body, and this one invited a future reader to
  "fix" the implementation toward the wrong behaviour — a near miss already
  reported once. The fixture is renamed to what it asserts, and the no-default
  property now has its own explicit guard.

## [4.56.0] - 2026-08-27

### Added

- **Sync windows follow the last write, not the last run.** `synthesis-daily-rituals`
  gains `scripts/sync_watermark.py`: each surface records the last date actually
  WRITTEN, every sync computes its window from that watermark, and the watermark
  advances only after a successful write. A window anchored on when the previous
  run executed cannot see its own holes — skip a run and the gap is never
  revisited, because the next window starts near today rather than at the last
  day on disk. Surfaces are tracked independently, so one closing never vouches
  for another.
- **A recorded gap is now blocking.** `sync_watermark.py status` exits non-zero
  while any surface has an unclosed gap, so a ritual step can fail on it. A gap
  that genuinely cannot close is deferred with an explicit reason, and the
  deferral lasts one working day — an indefinite silence is how a recorded gap
  becomes furniture. This closes a loop that was previously open: the `gaps`
  field was honest and completely inert, because writing a gap and closing one
  are different acts and nothing forced the second.

### Changed

- **`synthesis-meeting-transcripts`: declared means fetched.** Agent judgment is
  removed from deciding which declared transcripts are worth fetching. Relevance
  is judged after fetching, when content is visible, never before from a title.
  The workspace retired this same failure shape once already when activity-based
  gating was removed from repository syncing.
- **`synthesis-slack-sync`: read targets come from preflight.** Deriving ids from
  config inside a sweep is banned. Where an entry carries two id-like fields, the
  wrong one usually resolves — so the bug hides for months and then surfaces as a
  phantom dead surface for exactly one person. Resolution belongs in one place
  that fails closed, and readers take the resolved value from it.

## [4.55.1] - 2026-08-27

### Fixed

- **Item currency no longer demands stamps from narrative prose.** The
  open-section pattern matched "current", which reads as though it belongs but
  makes "Current State" — the commonest section name in practice — an obligation
  list. Those sections hold prose that section-level `*State as of:*` markers
  already govern, so the match demanded a date from narrative and double-covered
  body currency. Measured against a live corpus before adopting the convention,
  that single word accounted for 140 of 294 flagged items across 18 projects.
  Obligation sections (open, next, action, todo, blocked, waiting, pending, in
  progress) are unchanged and now carry a fixture proving the narrowing did not
  silently exempt them.

## [4.55.0] - 2026-08-27

### Added

- **Open-item currency is checked at read time.** `synthesis-context-lifecycle`
  gains item-level stamps: a live entry in an open-items section carries
  `(as of YYYY-MM-DD, review Nd)`, and `context_doctor.py` reports it as
  `item-currency` once it passes its horizon. Section markers already stopped a
  fresh header sitting above stale prose; this stops the failure one level down,
  where an entry keeps the present tense it was written in long after that
  stopped being true. Rewriting open-items lists each run was considered and
  rejected: it drops whatever today's evidence fails to surface, turning a
  visible stale entry into an invisible missing one, and it only acts on the
  days the ritual runs — which is not when records rot. An omitted horizon
  defaults to 14 days, because silence must not read as "never stale". Findings
  are warnings, not defects: a convention that turns a corpus red the day it
  lands teaches people to route around guards.
- **Per-workspace review ledger.** `review_ledger.py` keeps an append-only
  record of open-item transitions — opened, closed, carried, and
  expired-unactioned — so weekly, monthly, and quarterly reviews can answer what
  slipped. A tiered record describes what is open now and loses the evidence
  that anything was ever open the moment it closes. The ledger is per-workspace
  by design rather than global: engagement workspaces are deletion units, and a
  shared store would keep a counterparty's items alive in a file that outlives
  the delete-my-data request they belonged to. Reporting federates across
  workspaces at read time and copies nothing. Expiry is derived from the item
  stamps rather than remembered, so the common case needs no discipline at the
  moment discipline fails.

### Changed

- `synthesis-daily-rituals` Day-End Step 7 documents the stamp convention and
  states that advancing a stamp without re-checking the item is a false receipt.

## [4.54.0] - 2026-08-26

### Added

- **Executable working state has a durable project tier.**
  `synthesis-context-lifecycle` v1.12.0 defines `resources/scripts/` for
  portable computation and required inputs cited by durable records. The
  context doctor warns when an artifact cites a missing, escaped, non-regular,
  or symlink-traversing script target while explicitly leaving correctness to
  acceptance evidence.
- **Closed acceptance manifests are executable release evidence.**
  `synthesis-implementation-integrity` v1.2.0 supplies a fail-closed manifest
  validator and runner with declared membership, defect-pinned fixtures,
  exact changed-surface closure against a boundary-supplied Git diff, expected
  polarity, full terminal coverage, named enforcement boundaries, and explicit
  unverified remainder. Receipts bind a one-use transaction, exact head/tree,
  manifest digest, and changed-path digest while explicitly denying that the
  runner itself issues authority. Doctrine now requires extraction from
  authoritative sources and locates enforcement at the state-changing receipt
  consumer.
- **Disclosure categories preserve attention without weakening the gate.**
  `synthesis-disclosure-policy` v1.1.0 defines one-time category approval with
  frozen evidence predicates, narrow register and surface scope, positive or
  neutral claims, Class-X exclusion, and fail-closed ambiguity.

### Changed

- **Checkpoint and autonomous closeout sweep executable scratch state.**
  `synthesis-checkpoint` v1.6.0 and `synthesis-autopilot` v1.3.0 require cited
  scripts and inputs to reach the durable tier before a checkpoint closes.
- **The gated release and repository CI consume the R5 acceptance universe.**
  `synthesis-skills-manager` v2.2.0 runs the lifecycle and integrity tests plus
  the closed acceptance manifest before publication. The release boundary and
  CI use the same receipt consumer: it derives the authoritative change base,
  parses the fresh result, recomputes every Git and content binding, verifies
  closed terminal coverage, carries the accepted state through the release,
  expires it on any source change, and pushes the immutable accepted commit
  rather than a mutable branch name. CI checks out the history required to
  resolve the event-supplied base commit before deriving the change universe.

### Fixed

- **AGENT HEURISTIC — pointer-fallback tests remain hermetic in coordinated
  shells.** The pointer-resolution fixture now removes the caller's real
  coordination selector before exercising fallback identity, so the release
  gate tests fixture state rather than the executor's ambient session.

## [4.53.1] - 2026-08-26

### Fixed

- **Git-backed acceptance fixtures remain isolated from user-level Git hooks.**
  Synthetic Git operations now disable inherited hooks, so an active global
  coordination gate cannot block fixture setup before the behavior under test
  runs.

## [4.53.0] - 2026-08-26

### Added

- **`synthesis-project-management` v2.5.0 — staged-path claim enforcement.**
  `coordination.py check-staged` takes a lock/CAS-fenced snapshot of the
  lease-backed board, resolves the committing session through an explicit
  selector, environment, or owned active-project pointer, and requires an
  exact registered worktree and branch.
  Every staged path is compared with that session's source-area claims using a
  rename-disabled index view, so a rename's source and destination both enter
  the closed path universe. Missing board, lease, selector, session, worktree,
  branch, or index evidence refuses. Workspace-conflict errors now name the
  isolated-worktree, distinct-branch, and exact-claim remedy. Claim globs use
  path-segment semantics: `*` cannot silently authorize a deeper directory,
  while `**` remains the explicit recursive form. Claims and staged paths are
  resolved to the same filesystem identity before matching, including macOS
  path aliases.
- **Recorded outside-claim overrides.** An exception can proceed only after
  the reason, repository, branch, staged tree, and outside paths are appended
  atomically to the board's existing Messages section and the unchanged index
  is revalidated. No board schema changes were introduced.
- **AGENT HEURISTIC — hash-bound receipt serialization.** Successful checks
  expose a compact JSON receipt bound to the board content, canonical session
  UUID, exact worktree and branch, staged tree, staged path list, enforcement
  outcome, and outside-path list. Every result separates authority label from
  enforcement outcome and names the state changes that invalidate the receipt
  plus the semantic work it does not verify.

### Changed

- **`synthesis-git-hooks` v2.4.0 — config-gated claim checks at pre-commit.**
  A configured `coordination_board` makes `check-staged` a fail-closed boundary
  before content scanning and repository-local hooks. The installer and doctor
  copy, monitor, and drift-check the project-management runtime and its
  versioned session-word asset. The hook consumes the checker's JSON, requires
  an authorizing outcome and the receipt's boundary fields, recomputes its
  binding digest, and revalidates the board hash, worktree, branch, staged tree,
  outside-path set, and rename-closed path universe before continuing. A
  coordination refusal is reported as an authority refusal, distinct from a
  broken content-policy engine. Without that setting, commits are not blocked by
  coordination, and the hook reports the control's absence before running its
  established credential and exposure checks.

### Fixed

- **Fresh git-hook installs now produce a parseable v2 policy.** The template
  previously declared `config_version: 1` even though the engine refused
  versions below 2, and represented empty groups with flow-style lists that
  the strict parser also refuses. A clean installer could therefore copy its
  own template and immediately fail its doctor. The generation-zero installer
  fixture now executes that path end to end.
- **Fresh git-hook installs retain their drift baseline.** The installer writes
  the absolute source directory into the installed runtime. Both the installer
  doctor and later direct doctor runs compare all installed engine files and
  the coordination asset with that source. A present pointer that is malformed
  or no longer resolves a complete source fails the doctor closed.
- **Coordination authority cannot be resurrected by a stale refresh.** The
  check's lease snapshot now passes through the existing compare-and-swap
  mutation boundary. A concurrent release advances the lease, forces a retry,
  and is read before any authority receipt can be issued.

## [4.52.0] - 2026-08-26

### Added

- **`synthesis-meeting-transcripts` v0.7.0 — executable transcript-primary
  sourcing.** A new checker rejects a structured summary even when its heading
  calls it a primary transcript, classifies source grade from complete raw
  provider-message records that pair an identifier with bounded message
  content, and requires a record-bound permalink or `message_ts` before issuing
  an attribution receipt. Bare or conflicting identifiers cannot establish
  source grade. The receipt binds the
  artifact hash and exact location; a `thread_ts` is deliberately insufficient
  for quote-level authority. A synthetic 128-line summary fixture preserves the
  motivating defect's structure without private content, alongside a raw-message
  positive control and a closed executable acceptance manifest.
- **Version-stamped transcript controls.** Both the established completeness
  verifier and the new source-grade checker report the skill's 0.7.0 version.
  Their standalone acceptance suite executes this parity, so the existing
  “must match” banner is no longer an unchecked claim.

### Changed

- **The gated release and repository CI run both transcript boundaries and the
  release-wiring tests that require them.** The
  existing completeness verifier and the new primary-source gate execute before
  either client can receive a release. Every checker result distinguishes its
  control class and names the unverified remainder.

## [4.51.0] - 2026-08-26

### Added

- **`synthesis-promotion-gate` v1.0.0 — rendered publication boundaries.**
  The new gate extracts a declared publishable range, builds into an isolated
  output root, derives every expected route from frontmatter, and inspects
  DOM text, heading text, HTML comments, and raw page source under one
  canonical marker policy. A versioned surface manifest must agree exactly
  with configured renderer inspections; missing outputs and inputs consumed
  by no renderer refuse the run. Symlinked config and rendered-output paths
  are refused before their targets can be inspected. The output universe is
  closed, policy examples execute against every projection, and the shipped
  acceptance schema is consumed by the production loader. The engine does not
  approximate HTML grammar: a strict command protocol consumes identity-bound
  representations from the repository's destination parser or renderer. A
  parse5-derived corpus executes the Round-15 inline, entity, comment,
  attribute, code, hidden-container, and malformed-input matrix.
- **Executable authority topology.** `check` emits a non-authoritative
  acceptance receipt. `enforce` captures each inspected output exactly once,
  passes a separate content snapshot to the supplied promotion command, and
  revalidates config, policy, inputs, sidecars, and snapshot hashes at that
  boundary. It issues an enforced-gate receipt only after that command
  succeeds. Engine-owned limits remain present in every receipt and cannot be
  erased by repository configuration.

### Changed

- **The gated release and repository CI run the promotion acceptance suite.**
  A release cannot install a promotion-gate change on either client unless
  its fail-closed behavioral cases pass.
- **AGENT HEURISTIC — `synthesis-skill-router` v1.4.0** routes publication
  boundary, publishable-range, and promotion-receipt work to the new
  prompt-hidden specialist.

## [4.50.0] - 2026-08-26

### Added

- **`synthesis-adversarial-review` v1.0.0 — bounded, outcome-focused review.**
  The new protocol gives differently shaped agents a closed artifact universe,
  rotating attack planes, explicit concessions, per-artifact dispositions,
  production-topology handoffs, sufficiency rulings, and a bounded
  post-publication acceptance phase. Review ends at the principal's outcome;
  reviewer satisfaction and unbounded control growth are not completion
  criteria.
- **A fail-closed finding ledger.** `finding_ledger.py` records separate
  authority labels, enforcement outcomes, and `ship-blocking` versus
  `ship-improving` classifications. Compare-before-write transitions,
  evidence-bearing principal-courier counts, strict schema validation, and
  atomic read-back verification turn review state into an executable contract.

### Changed

- **`synthesis-autopilot` v1.2.0** directly orchestrates adversarial
  counterparts where the runtime permits it, budgets and counts any genuine
  principal courier crossings, writes proportionality before round one, and
  binds completion to the principal's outcome. Control verification stops
  after one generation unless a requested artifact or enforcing boundary is
  still defective.
- **AGENT HEURISTIC — `synthesis-skill-router` v1.3.0** makes the prompt-hidden
  adversarial-review specialist reachable from outcome-shaped requests.

### Fixed

- **`synthesis-inbox-cleanup` v1.6.2 — portable atomic runtime-pointer swaps.**
  The 4.49.0 repair used BSD-only `mv -h`; GNU `mv` rejected the option and
  left the Linux validation workflow red. The installer now uses Python's
  atomic `os.replace` on both macOS and Linux. Its repoint fixture models the
  GNU refusal on every host, and the skill metadata now matches the release
  line that 4.49.0 intended to advance.

## [4.49.0] - 2026-08-24

### Fixed

- **`synthesis-inbox-cleanup` v1.6.1 — the engine runtime never updated.**
  `install.sh` repointed `engine/current` with `mv -f`, but that path is a
  symlink to a directory: `mv` followed it and deposited the staged pointer
  *inside* the old release instead of replacing the link. Every install step
  reported success while the runtime stayed pinned to whatever release it
  already had, and the mismatch only surfaced at the final verification, after
  the work appeared done. Found in production when a sweep needed
  `resolve_scope.py` (the v1.5.0 workspace-scoping guard) and the installed
  engine predated it, with a stray `.current.<pid>.tmp` sitting in the old
  release directory as the tell. Fixed with `mv -fh`, which refuses to follow a
  symlinked directory. The runtime-installer test suite gained a regression case
  that installs twice with differing digests and asserts the pointer actually
  moves, no staged pointer leaks into the old release, and `engine/current`
  serves the new code — it fails without the fix.

## [4.48.0] - 2026-08-24

### Added

- **`synthesis-model-tiers` v2.1.0 — role selection by diagnostic difficulty.**
  The skill mapped roles to model ids but never said how to pick a role, and
  the common misroute is sending a *small-sounding* task to a cheap tier.
  Size is not the variable; whether the CAUSE is known is. A settled
  specification is execution and belongs in `routine`/`bulk`; a symptom
  report ("X isn't working", "the file won't open") is a differential over a
  chain of candidate causes and belongs in `judgment` even when the subject
  is one file — cost scales with the search, not the fix.

  Three properties now force `judgment`, any one sufficient: the cause is
  unknown, the blast radius includes a deliverable or durable record, or the
  work will not be independently reviewed before it lands. Two consequences
  are stated because they are what make this a cost rather than a
  preference: where a mistake must be caught and undone by a more expensive
  process the cheap attempt is debt with interest, and a plausible-sounding
  wrong explanation transfers the whole verification burden back to the
  human, inverting the reason for delegating.

  New resolution rule 6: an agent that finds itself under-tiered must say so
  *before* acting rather than proceed and report a confident result — the
  failure it is least able to detect in itself afterward.

## [4.47.0] - 2026-08-24

### Added

- **`synthesis-context-lifecycle` v1.11.0 — body currency.** Third occurrence
  of the stale-record defect, and the diagnosis finally names the design
  flaw: the prior fixes addressed *header* currency, while the defect moved
  to the *body* — `Current State` and `What's Next` kept routing agents to
  superseded work under a fully current header, which is a stronger false
  receipt than an obviously stale file. Worse, the edit helper had
  mechanized the easy half of the record update and printed unqualified
  success for it, manufacturing a completion signal for partial work.

  Operational sections now end with an as-of marker —
  `*State as of: 2026-08-24 (round 14)*` — which converts prose currency
  into the per-field, first-ordinal comparison the header already gets:

  - the context doctor (v1.5.0) fails a section whose marker lags the
    session log (`body-currency` defect) and warns when an ordinal-paced
    record carries no markers at all — unverifiable is reported as
    unverifiable, never as clean;
  - `context_edit.py` refuses a header advance that leaves a marker behind
    (`--allow-stale-body` records an explicit override) — the control that
    would have interrupted all three real occurrences, which each advanced
    the header and stopped;
  - advancing a marker while its section's prose is byte-identical requires
    `--state-reviewed`, recording the assertion that the section was re-read
    and still holds, so the marker cannot be bumped as mechanically as the
    header was;
  - every gated edit's success line now names the body state, because a
    completion signal must say what it did not verify.

  Regression fixtures derive from all three real occurrences, including the
  third encoded verbatim from the live record in both its literal markerless
  form (must surface as unverifiable) and its marked form (must be a
  staleness defect while every header check passes).
## [4.46.0] - 2026-08-23

### Added

- **`synthesis-context-lifecycle` v1.10.0 — durable header-currency checking.**
  The prior currency control missed the defect it was built for, twice, and
  this release replaces it with checked semantics rather than another patch.
  New `scripts/context_currency.py` judges each `CONTEXT.md` header field
  separately against the session log: a field's identity is its FIRST ordinal
  per family (round/wave/phase/step/part), the log's current value is the max
  across newest-date entries' identities, and fields are never unioned — the
  failure in the shipped check was exactly that a fresh `Phase` masked a stale
  `Last session` under a shared `max()`. Families never compare across each
  other, and coverage limits (unparseable headers, missing logs) are reported
  as what the check cannot see, never as staleness.
- **The context doctor now fails on stale headers.** `context_doctor` v1.4.0
  runs the currency check as a required `header-currency` defect, so semantic
  staleness surfaces where every session already looks instead of in an
  opt-in script. "Records agree with git" means committed; this check is what
  makes it also mean current.
- **`context_edit.py` refuses to create the defect at write time.** An edit
  that leaves `Phase` ahead of `Last session` in the same ordinal family is
  refused with the fields named; `--allow-header-lag` records an explicit
  override. `Last session` may lead `Phase` (the normal two-call transition,
  noted in output), unrelated edits on a pre-existing incoherent header warn
  rather than block, and the read-time doctor catches whatever is left
  lagging.
- **Every regression fixture derives from a real defect.** The four live
  instances — the round-10/11 union-masking miss, the round-2/3 same-day
  miss, and the two cross-day stale records — are encoded verbatim in
  `test_context_currency.py`, applying the artifact-derived-evidence rule to
  this tooling itself.
## [4.45.0] - 2026-08-23

### Added

- **`synthesis-context-lifecycle` v1.9.0 — fail-closed durable-context edits.**
  New `scripts/context_edit.py` replaces hand-rolled `str.replace()` when a
  script edits `CONTEXT.md`, `REFERENCE.md`, or a session log. A bare replace
  asserts nothing: when an anchor no longer matches — because another agent
  legitimately rewrote that region between sessions — the edit silently becomes
  a no-op while the surrounding "updated" message stays false. The result gets
  committed, and record-versus-git checks still pass, because the file *is*
  committed; it is simply not current. This is an unverified success claim
  about the agent's own action, a class nothing else in the system checks,
  because a claim about one's own completed action has no natural contradictor.

  The helper refuses, without writing, when the anchor is absent, matches a
  different number of times than declared, would leave the file
  byte-identical, would exceed a stated line budget, or targets a symlink. It
  writes atomically and then re-reads the file to confirm the change reached
  disk. No flag makes a missing anchor succeed; `--dry-run` still refuses a bad
  one. `replace_once` and `set_field` are importable for use from Python.

  `SKILL.md` gains a mandatory section for scripted edits, with the two rules a
  tool cannot enforce alone: re-read a record before editing it when another
  agent may have touched it, and never report success you did not verify.

## [4.44.0] - 2026-08-23

### Added

- `synthesis-local-model-runtime` **v1.1.0** adds a capability-graded runtime
  matrix. Ollama remains the default managed environment; LM Studio is an
  optional managed adapter for catalog planning, exact noninteractive Hugging
  Face downloads, JSON inventory, and runtime-metadata verification. llama.cpp
  and MLX-LM are reported as direct execution and serving runtimes without
  unsupported lifecycle claims.
- Catalog schema 2 carries separate LM Studio repository, quantization,
  publisher, and unambiguous inventory-match evidence for eight Qwen, GLM,
  Kimi, and DeepSeek artifacts. Schema 1 remains readable as Ollama-only input.
- A dry-run-first `update` command refreshes explicit installed Ollama models
  or an explicit `--all` set. It records before-and-after digest and size,
  distinguishes changed artifacts from already-current no-ops, writes optional
  receipts, and refreshes matching per-machine inventory records only after
  verified success. LM Studio updates remain blocked because its CLI does not
  expose a stable model-content identity contract.

### Changed

- Runtime profiling now reports the detected capability map for Ollama,
  LM Studio, llama.cpp, and MLX-LM. Pipx-installed MLX-LM versions are read from
  their own interpreter environment when the entry point lacks `--version`.

## [4.43.6] - 2026-08-23

### Fixed

- `synthesis-local-model-runtime` **v1.0.5** now treats effective Ollama
  KV-cache configuration as a model-fit constraint. Kimi Linear artifacts
  declare their `f16` requirement; an incompatible Homebrew service blocks the
  plan instead of failing only at generation time.
- A dry-run-first `configure-ollama` command validates the standard current-user
  Homebrew LaunchAgent, backs it up, applies one allowlisted KV-cache setting,
  reloads it, proves loopback health, and rolls back on failure. Ollama HTTP
  error bodies are retained with a fixed size bound for actionable diagnostics.
- Benchmark receipts now distinguish a complete final response from a bounded
  performance sample. A length stop or raw `<think>` markup in a
  reasoning-disabled run is preserved but cannot pass the final-response gate.

## [4.43.5] - 2026-08-23

### Fixed

- `synthesis-text-provenance` **v1.0.1** now rejects an empty or
  whitespace-only final response instead of sealing a zero-byte output as a
  successful generation. Its OpenAI-compatible runner also accepts an explicit
  `--reasoning-effort` control and records that request parameter, allowing
  Ollama thinking models to reserve the bounded output budget for final text.

## [4.43.4] - 2026-08-23

### Fixed

- `synthesis-local-model-runtime` **v1.0.4** now disables reasoning traces by
  default in bounded benchmarks and records the setting in each receipt. This
  keeps the token budget focused on the requested final response for
  thinking-capable models; `--think` remains an explicit opt-in.

## [4.43.3] - 2026-08-23

### Fixed

- `synthesis-local-model-runtime` **v1.0.3** now merges verified selections
  across separate installation commands. Installing several explicitly named
  artifacts one at a time no longer leaves only the last artifact resolvable;
  an explicit inventory refresh still replaces the selection set with the
  current policy plan.

## [4.43.2] - 2026-08-23

### Fixed

- `synthesis-local-model-runtime` **v1.0.2** reports cached recovery as a
  zero-network operation with explicit worst-case runtime materialization.
  Ollama can normalize a verified GGUF into a new runtime layer and retain the
  original registry cache, so recovery plans no longer imply that hard-linked
  staging prevents all model-sized disk growth.

## [4.43.1] - 2026-08-23

### Fixed

- `synthesis-local-model-runtime` **v1.0.1** can recover from a failed Hugging
  Face Ollama registry transaction after the large GGUF layers are already
  cached. Catalog-pinned layer digests, media types, and exact sizes gate a
  supported local multi-GGUF import; every layer is re-hashed, hard links avoid
  a separate staging copy, temporary import links are removed, and the
  runtime-resolved model identity is verified before inventory is updated.

## [4.43.0] - 2026-08-23

### Added

- `synthesis-local-model-runtime` **v1.0.0**: a privacy-safe hardware profiler,
  dated multi-tier model catalog, policy-driven fit planner, dry-run-first
  Ollama installer, atomic per-machine inventory, exact model resolver, runtime
  verification, and bounded benchmark receipts. The profiler uses an allowlist
  and never records serials, hardware UUIDs, hostnames, or account data; the
  storage guard rejects iCloud, workspace, repository, and declared protected
  roots. The initial catalog covers practical Qwen, GLM, Kimi, and DeepSeek
  artifacts from 16 to 128 GiB machines while keeping upstream ownership,
  quantization publishers, base lineage, and resolved local digests separate.

### Changed

- `synthesis-repo-guard` **v2.3.0** adds `--flush-session <session-id>` for a
  fail-closed, exact-session remote handoff. It applies the existing source and
  context readiness gates to one manifest without reading, publishing, or
  deleting unrelated sessions, removing the global all-or-nothing coupling
  while preserving the existing batch command.

## [4.42.0] - 2026-08-23

### Added

- `synthesis-text-provenance` **v1.0.0**: a provider-neutral provenance
  workflow for hosted and local/open-weight text generation. It records a
  canonical self-hashed schema-2 manifest, hash-bound native runtime receipts,
  path-free direct-parent lineage, one-shot OpenAI-compatible generation, and
  non-mutating Unicode and normalization audits. The skill refuses watermark
  defeat, detector-guided rewriting, disguised authorship, and unsupported
  watermark-free claims.
- Nine additive content-quality criteria for source-detail and causal-mechanism
  loss, disproportionate structure, current deliverable padding, tool and
  reference residue, intent-only stopping, voice normalization, private
  working-language leakage, and non-material work chronology. Current-model
  overlays are dated, task- and surface-bounded, unmeasured for prevalence, and
  never establish authorship.
- A semantic no-removals gate that freezes every pre-release writing-rule line
  in order. The only replacements permitted are exact SHA-256-bound factual
  corrections in a separately reviewed allowlist; additions remain allowed.

### Changed

- `synthesis-content-quality` **v4.1.0** separates editorial quality,
  model-shaped style observations, technical provenance, and authorship. It
  preserves the complete historical catalog while correcting unsupported
  false-positive rates, probability semantics, provider certainty, and the
  stale universal text-watermark statement.
- `synthesis-writing-pitfalls` **v1.1.0** adds unnecessary editorial
  intervention; `synthesis-writing-craft` **v1.1.0** adds source-mechanism,
  voice, proportional-structure, and edit-materiality principles.
- `synthesis-clean-text` **v2.0.0** keeps the no-hidden-marker production policy
  and adds an enforceability boundary: characters and declared lineage are
  inspectable, while an undisclosed statistical mark cannot be verified or
  removed by ordinary prose revision.
- `synthesis-skill-router` **v1.2.0** routes integrity, lineage, generation
  receipt, and provenance requests to `synthesis-text-provenance` without
  implying authorship or watermark absence.

## [4.41.0] - 2026-08-20

### Added

- `synthesis-anti-shortcuts`: **The Capability-Limit Probe** (methodology
  procedure 7; the maintenance loop moves to 8). Distinguishes a *guardrail* -
  a withheld permission, a safety gate, an action reserved for a human, which
  must never be routed around - from a *capability gap* - an unconfigured app,
  an ungranted scope, a transport that does not expose the feature, which is a
  problem to solve. Treating the second like the first wears the costume of
  discipline while delivering less than the task required, and agents holding
  strong, correct rules about not bypassing governance gates are the most
  prone to it. On a capability gap: name the exact mechanism that failed,
  enumerate alternative paths, separate what the agent can do from what only
  the user can do, and report options with a recommendation rather than the
  limitation alone.
- `synthesis-anti-shortcuts/references/costume-vocabulary.md`: category 8
  `capability_surrender`, covering "not something I'll work around", "blocked
  at the X level" / "hit a limitation", "not possible right now" / "there's no
  way to", and premature "you'll have to do this manually" - the last exempt
  when the action is genuinely reserved to the user.

## [4.40.0] - 2026-08-20

### Added

- `synthesis-project-management` v2.4.0: the **project-name contradiction
  guard** in Project Discovery. When a request names a project that
  contradicts the session's own evidence — the conversation's established
  project, the chat or session name, the active-project pointer, the task's
  working directory — the agent surfaces the contradiction and asks a
  one-line clarifying question instead of silently resolving to the name.
  Names are one signal, not an override: humans navigate many
  similarly-named projects, and sibling projects in one program share
  vocabulary. Silent resolution stays correct only when name and session
  evidence agree, or the session carries no project evidence at all. Origin:
  a misnamed sibling project sent an entire working session's output to the
  wrong project's records while the intended project's ask went unfulfilled.
  Companion Common Mistakes row added.

### Changed

- `synthesis-agent-conformance` v1.6.1: the SessionStart stopped-task
  recovery guidance carries the same exception — automatic resolution of a
  user-named project now explicitly excludes the case where the name
  contradicts the session's established context, closing the gap where the
  emitted guidance instructed the exact behavior the discovery protocol now
  forbids.

## [4.39.0] - 2026-08-20

### Changed

- **`synthesis-agent-correspondence` v3.0.0 — the voice axis: archetype binds the
  narrator.** Bot-archetype personas now speak in their own voice — the persona
  says "I" about itself and names the principal in the third person — while
  assistant-archetype personas speak as the principal. The model follows the
  executive-staff convention the skill was always grounded in: a chief of staff
  is authorized to speak *as* the principal; an executive assistant speaks in
  their own voice *for* the principal's office. Grammar becomes the disclosure
  that survives forwarding and quoting; routine errors read as the assistant's
  rather than putting false words in the principal's mouth, which is what lets
  standing direction safely carry more; and the principal's first person stays
  meaningful because it appears only on words the principal owns. Sincerity
  classes (appreciation, kudos, condolences, relationship-touching messages)
  route to principal-voice lanes even when low-stakes. Bot-lane signature
  examples rewritten in the persona's voice — one narrator per message. Includes
  a v2→v3 migration section covering signature rewrites, sincerity re-routing,
  and retargeting fail-closed register guards that banned third-person agent
  phrasing wholesale. The analogy honors the professions it borrows from: these
  personas are leverage for human chiefs of staff and EAs, and working support
  for principals who have neither — the agent extends the office, never
  competes with it.

## [4.38.0] - 2026-08-19

### Added

- **`synthesis-daily-rituals` v2.26.0 — lead-time meeting preps.** Same-day prep
  packs are right for routine meetings and structurally wrong for high-stakes
  ones: prep written minutes before a strategy-bearing 1:1 summarizes what the
  agent has been processing lately, not what the counterpart cares about.
  Workspaces declare `.agents/meeting-preps.yaml` (title/attendee matchers,
  `business_days_ahead`, and the durable `sources` the prep must be built from);
  generation rides the Calendar Guardian's tomorrow-review in every mode
  including Quick Close, Day-Start verifies and regenerates, the owed-weekly
  scan flags the coming week, and **a rescheduled flagged meeting triggers an
  immediate refresh at detection time** — reschedules being exactly when prep is
  most likely stale and most likely skipped. Packs state their own basis so a
  researched pack is distinguishable from a summary of recent activity.

## [4.37.0] - 2026-08-19

### Added

- **`synthesis-grounding-discipline` v1.1.0 — entry 12, "Archived history is not
  current state."** Imported material — a channel backfilled to its first message,
  an exported mailbox, a migrated tracker — arrives with every item in the same
  present-tense voice and none of it is evidence about today. The rule: reconcile
  against the newest material already held before reporting anything from an import
  as currently open; if the newest thing you can find is inside the import, you have
  only observed that the import ends. Scope findings to where you looked, title the
  output by what it establishes (where conversations *stopped*, not what is
  unresolved), stamp every archive with its span and capture date, and raise the bar
  for personnel and commercial matters, where calling a settled thing unresolved asks
  someone to re-litigate finished work.

  The catalog intro now also states that **entry numbers are load-bearing** — other
  documents cite these rules by number, so new entries are appended rather than
  inserted. Renumbering silently repoints existing citations to different real rules,
  which is worse than a broken link because it still resolves.

- **`synthesis-slack-sync` v3.5.0 — backfills and archive imports.** A backfill is a
  different operation from a windowed sync and fails differently. Retrieval rules
  (page to the true beginning and report the earliest date as proof; expand every
  thread, since replies never appear in channel history; name a partial capture by
  its date range rather than "full history") plus the analysis rule that matters
  more: nothing from a backfill may be reported as currently open without
  reconciliation. Candidate items route through `synthesis-catchup-ledger`'s triage
  rather than being reported raw.

## [4.36.0] - 2026-08-19

### Changed

- **`synthesis-daily-rituals` v2.25.0 — per-workspace sessions become the
  default worker mode, and the principal is named as the dispatcher.** The
  desk/worker split and the artifact contract are unchanged; what changes is
  which mode is assumed. A worker now defaults to an attended session rooted in
  its own workspace, run on that workspace's own schedule, with desk-dispatched
  subagents demoted to an opt-in for closing everything from one place. Two
  rules are stated explicitly: no session can start work in another, so the desk
  reports which workspaces are owed and the human opens the one that owes; and
  the desk never nudges, triggers, blocks on, or waits for a worker — it folds
  what exists and reports the rest as not covered. Recorded origin: dispatch-by-
  session-messaging went 0 for 2 (a session stale by two hours, then none
  reachable) while the file-based artifact path delivered both times, because
  session messaging requires the target to already be open and attended.
  Independent close times per workspace are now documented as normal operation,
  which the timestamped artifact schema already supported.

## [4.35.0] - 2026-08-18

### Added

- **`synthesis-inbox-cleanup` v1.6.0 — impersonation scanning** — a read-only
  adversarial pass (`scripts/scan_impersonation.py`) for a gap that was
  structural, not incidental: every disposition class sorts mail by
  desirability, so hostile mail had no cell in the taxonomy and a tidy sweep
  walked past it. Flags display-name brand impersonation where the sending
  domain does not belong to the claimed brand — the pattern behind live
  campaigns that send through authenticated bulk-mail carriers and put the
  spoofed brand only in the display name, defeating "the domain checks out"
  as a safety verdict. Reports only; removal stays human-reviewed. Also adds
  the standing rule that a human sender is not the same as your mail, for
  catch-all domains where real people's misdirected threads accumulate.

## [4.34.0] - 2026-08-18

### Fixed

- **`synthesis-skill-router` v1.1.0 — routes grounding requests correctly.**
  The router had no entry for `synthesis-grounding-discipline`, so requests to
  verify evidence, check provenance, or establish an absence resolved to
  `synthesis-anti-shortcuts` — the wrong skill by the new skill's own framing.
  The two are now distinguished explicitly on both bullets: anti-shortcuts is
  the effort-side discipline, grounding-discipline the truth-side one.

- **`README.md` — catalog and release notes reconciled.** The skill catalog
  listed 43 rows against 57 skill directories; all 14 missing skills are added
  and the table now matches the tree exactly in both directions. Release notes
  for 4.31.0 through 4.33.0 were never added despite the repo's own
  contribution rules requiring it; they are in. A headline about SessionStart
  evidence had been orphaned from its 4.27.0 paragraph by later prepends and is
  reattached.

### Changed

- **`synthesis-autopilot` v1.1.0** — `synthesis-grounding-discipline` added to
  `depends_on` and the composed-skills table. An autonomous run states facts
  without a human checking each one, which is exactly where evidence discipline
  earns its place.

- **`synthesis-anti-shortcuts` v1.1.1** — names grounding-discipline as its
  truth-side companion, making a link that was one-directional reciprocal.

## [4.33.0] - 2026-08-18

### Changed

- **`synthesis-daily-rituals` v2.24.2 — plan shells keep the consumer's
  section vocabulary** — storage separation governs where plan content lives,
  not what its sections are called. Renderers classify plan sections by heading
  vocabulary, so a shell written with invented headings still renders, as
  undifferentiated prose, while every typed region the reader actually works
  from comes up empty — the plan looks blank precisely when it is full. Shells
  now reuse the established headings for any region they populate and confine
  novelty to the coverage block and pointer lines, with producer and consumer
  required to change together.

## [4.32.0] - 2026-08-18

### Added

- **NEW skill: `synthesis-grounding-discipline` v1.0.0** — evidence and
  provenance discipline for AI-agent output; the truth-side companion to
  synthesis-anti-shortcuts' effort-side discipline. An eleven-rule catalog in
  four groups (record only what a source surfaced; caches are not truth;
  proving absence; grounding writes and deletions): anti-confabulation, quote
  provenance, cache-vs-truth with a verifying-command-class table,
  runtime-vs-IaC as distinct truths, evidence-in-hand before theorizing,
  conventions-are-corpus-claims, negative-findings-need-a-positive-control,
  truncated-output-is-a-pointer, zero-results-are-never-absence,
  search-first/verify-paths, and file-and-process safety (including
  cleanup-sentinel and recursive-delete-target invariants). Each entry carries
  an anonymized production incident vignette and a compliance procedure; a
  closing self-check compresses the catalog.

- **`synthesis-agent-conformance` v1.6.0 — instruction-kernel pattern
  reference** (`references/instruction-kernel-pattern.md`): keeping an
  always-loaded instruction file small and enforceable — the three-part thin
  kernel (identity + invariants, routing table, enforcement declarations), the
  four enforcement classes, the not-weakening proof obligation, the fail-closed
  budget gate with warn band, and homes-first/kernel-last migration mechanics.

### Changed

- **`synthesis-anti-shortcuts` v1.1.0** — sub-agent dispatch hygiene gains the
  brief-size cap: at most five deliverables per dispatch, with the
  late-failure shape oversized briefs produce; split substantial phases at
  dispatch time. Added to both SKILL.md §4 and
  `references/sub-agent-hygiene.md`.

- **`synthesis-context-lifecycle` v1.8.0** — new "Repo Families and Deletion
  Units" section: the permanent knowledge root vs per-engagement private repos
  as deletion units, the write-time routing test, the asymmetric misplacement
  failures, the generic ALWAYS-PRESERVE class, count-never-itemize
  inventories, and instance specifics declared in private configuration.

- **`synthesis-slack-sync` v3.4.0** — the transcripts-first rule gains the
  question-shape trigger (verification questions are lookups wearing a
  different hat) and the zero-result absence protocol (bounded direct reads
  with stated bounds; re-run modifier-bearing queries without the modifier
  before trusting a null), cross-linked to synthesis-grounding-discipline.

## [4.31.0] - 2026-08-17

### Added

- **`synthesis-skills-manager` v2.1.0 — gated cross-client release script**
  (`scripts/release.py`) — sequences a release behind one fail-closed command:
  preflight (both manifests agree, newest CHANGELOG entry matches, tree clean,
  repo root is a checkout and not an installed cache) → the required checks →
  publish to every configured push remote → install into both clients with each
  client's own commands → verify. Codex's marketplace snapshot is upgraded
  before installing from it, because installing without that step ships the
  previous release while appearing to succeed.

  Each client is verified **twice**: what its CLI reports, and the plugin
  manifest at the path the CLI says it loads. A client can report the intended
  version while the tree it loads is stale, so a report-only check passes green
  through exactly the drift the script exists to catch; `test_release.py` pins
  that case as a required failure. `--install-only` recovers drift or provisions
  a new machine; `--dry-run` prints the plan without mutating anything.

## [4.30.1] - 2026-08-17

### Changed

- **`synthesis-daily-rituals` v2.24.1** — plan-separation contract clarifies that a
  workspace's plan fragment belongs in the individual's private repository when a
  workspace carries both a shared and a private one, and that consumers merging
  fragments for display must not cache merged output person-side and must render
  unresolved pointers as explicit markers rather than omitting them.

## [4.30.0] - 2026-08-17

### Added

- **`synthesis-daily-rituals` v2.24.0 — plan storage separation** — the daily
  plan stops copying workspace content into the person-side repository. Each
  workspace's worker artifact doubles as its plan fragment (already stored in
  the workspace-private repository); the person-side plan becomes a shell:
  coverage line, the principal's own timeline, minimal cross-workspace conflict
  references, the permanent personal section, and pointer lines to fragments.
  Consumers merge fragments into the converged view at display time, so
  presentation stays singular while storage separates. Motivation: erasing an
  organization's data by deleting its workspace folders — a hard requirement in
  regulated environments and clean hygiene everywhere. The contract's new "Plan
  storage separation" section states the erasure boundary honestly (content
  never persists outside workspace folders; names as references do) and adds a
  strict-shell mode for regimes that treat event titles as erasable data.
  Historical mixed plan files are left to a deliberate migration.

## [4.29.0] - 2026-08-17

### Added

- **`synthesis-daily-rituals` v2.23.0 — distributed ritual execution (desk and
  workers)** — the ritual can fan its per-workspace sync labor out while the
  output stays singular. A private workers registry declares which workspace
  seats run workers and where each writes; every worker ends by writing a
  structured summary artifact (schema, path convention, coverage and gaps
  fields, fixed body sections) defined in the new
  `references/ritual-worker-contract.md`. The desk — the ritual-home seat —
  folds the newest artifact per workspace instead of loading workspace detail
  inline, owns cross-workspace conflict reconciliation, and opens every brief
  with a mandatory coverage line. Workers never message the desk
  (worker→file, desk→file): a missing artifact is the legible "not covered"
  signal. Absent registry = classic single-session ritual, unchanged. The
  contract is client-neutral by construction — any agent client or a human can
  produce a conforming artifact or act as the desk.

## [4.28.1] - 2026-08-17

### Fixed

- **Aggregate local continuity without an active pointer** — the complete
  conformance command now honors the stopped-task contract when the optional
  active-project cache is absent. The explicit `pointer` command remains
  strict, and an existing malformed pointer still fails in every scope.

## [4.28.0] - 2026-08-17

### Added

- **`synthesis-project-management` v2.3.0 — durable UUIDv7 session identity** —
  coordination schema v3 stores a full UUIDv7 plus compact Crockford Base32
  and speakable word-number aliases that encode the same 60 random bits.
  Claims remain resource paths attached to a session. The lease-backed
  allocator checks collisions inside the compare-and-swap transaction; every
  command and active-project consumer accepts the UUID, compact, speakable, or
  migrated legacy selector.
- **Atomic v1/v2 board migration** — `coordination.py migrate` assigns all
  historical rows their canonical and human-facing identities while retaining
  letters under an explicit `legacy id` column and preserving messages. The
  versioned offline vocabulary vendors the MIT-licensed BIP-39 English list
  with a pinned digest and exact round-trip tests.

### Changed

- **`synthesis-checkpoint` v1.5.0 — receipt-based restart recovery** — a stale
  startup registry now asks for a genuine client process restart first. The
  same root conversation continues only when a new transcript-bound
  SessionStart event proves the current plugin version/root and loaded skill
  metadata; a new conversation/task is required only when rehydration is
  unsupported or that verification fails.
- **`synthesis-onboarding` v1.2.0 — correct post-update guidance** — installer
  output and documentation distinguish installed cache replacement from the
  subsequent lifecycle reload and state the same restart-first verification
  ladder for Claude Code and Codex.
- **`synthesis-agent-conformance` v1.5.0 — coordination schema v3** — source,
  SessionStart, pointer activation, and semantic doctor paths resolve every
  identity representation to the canonical UUID; newly activated pointers no
  longer persist a compact, speakable, or legacy selector.

## [4.27.0] - 2026-08-17

### Added

- **`synthesis-agent-conformance` v1.4.0 — retained SessionStart evidence** —
  every genuine Claude Code or Codex SessionStart now creates a preserved
  per-session event before monotonic latest pointers advance. `hook-live`
  keeps its unqualified current-health semantics and adds exact Claude and
  Codex session selectors for release and handoff reverification. A later
  unrelated start can therefore surface current drift without making an
  earlier accepted session unreachable. Event identity, transcript binding,
  plugin version/root, UUID shape, atomicity, and fail-closed registry parsing
  remain part of the live-evidence gate.

### Changed

- **`synthesis-checkpoint` v1.4.0 — explicit evidence scopes** — checkpoint
  recovery reports current global hook health separately from any exact
  accepted-session evidence named by the durable project record. Neither scope
  may stand in for the other. A ten-minute inter-turn pause is the default
  automatic freshness boundary when timestamps are available, and installed
  plugin changes still require a genuinely fresh client task before live
  acceptance.

## [4.26.0] - 2026-08-17

### Changed

- **`synthesis-agent-conformance` v1.3.0 — pointer activation accepts the
  attributed stopped-task record** — the active-project pointer and local
  continuity now share one record contract. `activate` and pointer validation
  accept uncommitted project edits exactly when session-attributed pending
  manifests record every dirty path (the `LOCAL_READY` /
  `LOCAL_RECOVERABLE` states), and keep failing closed on any unattributed
  path or unreadable manifest. Previously activation rejected the same
  attributed dirty record that local continuity accepted, so a live owner
  mid-switch could not hold a pointer without an off-contract commit. The
  attribution primitives (`porcelain_paths`, `project_pending_manifests`,
  `unattributed_dirty_issues`) now live in `active_project.py` and the
  continuity checks import them, so the two contracts cannot drift apart; a
  regression test asserts their agreement on the same fixtures. Workspace
  claims on the coordination board may carry the conventional trailing
  parenthetical annotation — `repo @ branch (new branch)` — without breaking
  exact worktree/branch matching.

## [4.25.3] - 2026-08-15

### Fixed

- **`synthesis-agent-conformance` v1.2.2 — Claude Code live SessionStart
  evidence** — preserve the client-delivered
  receipt when Claude names its client-owned transcript before creating or
  populating the JSONL file. The receipt records whether the binding existed
  at hook time; conformance still fails closed until that exact transcript
  binds the same session UUID. Canonical root-transcript shape validation
  rejects subagent descendants, symlinks, and existing contradictory UUIDs.
  Static script output without a real matching client transcript remains
  insufficient.

## [4.25.2] - 2026-08-14

### Fixed

- **Transactional worktree-retirement continuity** — manifest writers, Stop
  receipts, remote flushes, and retirement now share one lifecycle lock. The
  helper pins a freshly fetched remote-tracking commit, stages a known-capable
  reconciler outside the target, and fsyncs a resumable intent before removal.
  Interrupted completion selects and verifies that exact content-addressed
  reconciler even after an upgrade. Optional remote branch deletion is bound
  to the recorded remote and head with Git's compare-and-delete lease.
  Completion is idempotent; unexplained missing or unpublished paths continue
  to block Stop.

## [4.25.1] - 2026-08-14

### Fixed

- **Remote-readiness integrity** — continuity conformance compares complete
  branch heads with the fetched upstream, so an unpublished commit outside the
  project subdirectory cannot produce a false `REMOTE_READY` result.
- **Local evidence semantics** — a stopped task with attributed edits requires
  its current content receipt; a clean no-edit task does not create empty
  evidence. Documentation and conformance now state the same contract.
- **Readiness naming** — local-ready, local-recoverable, and remote-ready are
  consistently described as three states.

## [4.25.0] - 2026-08-14

### Added

- **Three-state project continuity** — local-ready and local-recoverable evidence
  support same-machine Claude Code and Codex switching without per-turn Git or
  network activity; remote-ready provides the explicit cross-machine gate.
- **Continuity conformance** — local and remote readiness checks verify edit
  attribution, Stop receipts, repository state, and upstream equality.

### Changed

- **Project lifecycle** — SessionStart resolves named projects from the tracked
  registry when no leased pointer exists; Stop records local content receipts;
  explicit remote handoff and day-end publish the attributed batch.
- **Context doctor** — local mode keeps structural defects fail-closed while
  reporting recoverable Git state as warnings; remote mode remains strict.

### Fixed

- **Interrupted-task recovery** — a PostToolUse manifest remains sufficient
  evidence to reconstruct unfinished work when a task never reaches Stop.

## [4.24.2] - 2026-08-14

### Fixed

- **Installed-to-source conformance** — forbidden-pattern scans exclude the
  conformance checker's own definitions by source-relative identity, so an
  installed checker auditing a canonical checkout produces the same source
  result as the source checkout itself.

## [4.24.1] - 2026-08-14

### Fixed

- **Installed catalog parity** — source-checkout Python and pytest caches no
  longer create false drift against clean plugin packages; substantive skill
  content remains digest-bound.
- **Codex plugin skill discovery** — authoritative `skills/list` namespaced
  names are matched to their canonical public skill names, so a healthy
  enabled plugin no longer reports every public skill as missing.

## [4.24.0] - 2026-08-14

### Added

- **New `synthesis-skill-router`** — keeps specialist workflows explicitly
  invocable in Codex while routing natural-language requests to their exact
  skill bodies. Claude Code retains its complete native trigger catalog.
- **`synthesis-agent-conformance`** — five evidence planes and dedicated
  checks for hook definitions, human trust, genuine SessionStart receipts,
  the resolved Codex catalog budget, instruction reserve, leased
  active-project pointers, authenticated capability evidence, and supported
  product surfaces. Read-only Codex app-server adapters ask `hooks/list` and
  `skills/list` for runtime truth.
- **Capability evidence ledger** — sanitized, timestamped PASS, FAIL, UNKNOWN,
  and UNSUPPORTED outcomes for Claude Code, Codex desktop, and Codex CLI.
- **Client-specific live receipts** — public plugin SessionStart evidence is
  recorded separately for Claude Code and Codex, so one client's successful
  start cannot be mistaken for the other's.
- **Public integration and contributor system** — rationale, five-plane
  runtime contract, governance, issue templates, pull-request evidence gates,
  runtime stewardship, and contribution lanes for skills, adapters,
  accessibility, documentation, and compatibility fixtures.

### Changed

- **Skill discovery** — OpenAI-specific metadata now divides the public
  catalog into an implicit core and explicit specialists. The supported
  272,000-token Codex configuration projects to 3,405 of its 5,440-token
  catalog budget while all skills remain enabled.
- **`synthesis-onboarding`** — `update` explicitly refreshes installed native
  plugins, verifies the exact version when run from source, and states the
  new-session/new-task boundary. Ordinary install and doctor runs leave live
  versioned caches untouched. Claude Code, Codex desktop, and Codex CLI are
  first-class; Codex IDE is reported as unsupported instead of inheriting a
  false plugin-parity claim.
- **`synthesis-project-management`** — active-project pointers carry their
  coordination owner, lease, worktree, branch, plan, and source commit;
  releasing the owner recoverably archives the pointer.
- **`synthesis-checkpoint`** — compares the task's SessionStart plugin receipt
  with source and installed truth before claiming that a registry is current.

### Fixed

- **`synthesis-meeting-transcripts`** — workspace-MCP doctor distinguishes
  service absence from restricted observability, parses curl exit and HTTP
  status independently, and rejects the former double-`000` false success.
- **Active project injection** — SessionStart now refuses missing plans or
  worktrees, released or expired owners, non-owner context roles, wrong
  worktree claims, symlinked or out-of-tree paths, stale branch or commit
  identity, and checkouts behind local `origin/main`. Activation and release
  share one cross-process pointer lock so release cannot archive a successor's
  newly activated pointer.
- **Concurrent evidence writes** — capability ledgers, conformance reports,
  and client SessionStart receipts use unique atomic replacements; the
  read-modify-write capability ledger also holds a cross-process lock.
- **App-server response handling** — malformed `hooks/list` and `skills/list`
  payloads become explicit unknown evidence instead of unclassified errors;
  malformed nested hook rows cannot collapse into an empty PASS.
- **Live SessionStart provenance** — public receipts require a UUID session,
  a client-owned transcript that declares that same session, and the exact
  enabled immutable plugin root; private control-plane receipts require the
  same transcript binding, and missing source-version truth fails the live
  plane closed.
- **Installed catalog parity** — exact-version Claude and Codex caches must
  match the source skills tree by content digest, including scripts and
  OpenAI policy metadata; matching names or file counts cannot mask drift.
- **Installed evidence resolution** — conformance honors `CODEX_HOME` and
  `CLAUDE_CONFIG_DIR`, parses valid TOML integer forms without changing the
  Apple Python 3.9 floor, fails closed on invalid instruction configuration,
  and binds catalog and live-receipt checks to the marketplace reported by
  the enabled plugin inventory rather than an arbitrary same-version cache.
- **Portable handoff state** — active-project validation rejects dirty project
  records and commits not reachable from a fetched remote ref, so another
  client or machine can recover the recorded state.
- **Coordination pointer archives** — arbitrary session identifiers are encoded
  into filesystem-safe basenames and cannot create nested archive paths.
- **Skill dependency contracts** — source conformance rejects missing or cyclic
  dependencies; the daily-ritual and Slack-sync graph is now acyclic.

## [4.23.0] - 2026-08-13

### Added

- **`synthesis-agent-conformance`** — new `source.changelog-version-parity`
  check: both plugin manifests must match the CHANGELOG's top release heading,
  failing closed when the heading or a manifest is missing. A release is
  manifests + CHANGELOG moving together; this miss shipped twice (the 4.18.0
  repair commit, and again caught in review on the 4.22.0 release) while every
  other check stayed green. Suggested by Emil Peñaló in synthesis-preplan's
  review thread (PR #5).

## [4.22.0] - 2026-08-13

### Changed

- **`synthesis-pr-review`** — the "Where This Fits" lifecycle table gains the
  `synthesis-preplan` row, so the engineering arc reads end to end: preplan →
  code-planning → implementation-integrity → code-audit → preflight →
  pr-review.

### Added

- **New skill `synthesis-preplan` (v1.0.0)** — architecture-decision pre-planning for tickets or issues with real design choices. Runs a structured Q&A loop that locks the load-bearing architectural decisions (branch base, scope boundary, dependency graph, execution lane, and the open questions a competent engineer could resolve more than one way) before any commit plan is drafted, writes a reviewable locked-decisions file, then hands off to the planning step with a previewed prompt. Declares `depends_on: ["synthesis-code-audit"]` — the review dimensions the decision rubric leans on live there. Bundles three files it carries itself: `references/commit-by-commit.md` (the multi-commit execution discipline: Step 0, the per-commit brief/fast-check/audit/amend/full-gate cycle, and a nine-item close-out list that opens with five review gates), `references/single-commit.md` (the companion lane for work that is one reviewable commit and decides nothing), and `assets/handoff-template.md` (the agent-neutral prompt scaffold the skill fills before handing off). Fully project- and agent-agnostic: git is the only assumed baseline, while trackers, build tools, planners, and agent harnesses are all illustrative examples.

  Notable pieces of the methodology, each earned from a real run rather than
  theorized:

  - **Three decision-quality checks in the Q&A rubric.** Nothing downstream
    catches a wrong decision: an audit verifies an implementation *against*
    locked decisions, which makes a locked row the one thing it will never
    re-open. So the rubric tests each decision against what the downstream
    tickets consume, names what each mechanism makes unobservable (any
    guarantee or floor pins a variable, and whatever measured that variable now
    measures the guarantee), and asks whether the outcome a mechanism prevents
    is a defect or the model working correctly. A mechanism invented inside a
    lean becomes its own numbered decision rather than riding on another
    decision's authority without its scrutiny.
  - **Verification split into fast checks and a single full gate.** The
    whole-tree suite runs once per commit, after the audit's findings are
    amended in, because a pre-audit run tests code the amend replaces.
  - **Step 0** — write the full todo list, then create the branch, before any
    file is touched. Neither becomes visibly missing until commit time.
  - **Two gates no per-commit pause can see:** a plan-conformance review (which
    also asks whether the plan's own remaining gates are still executable), and
    a branch-wide reconciliation that re-derives shared append-only numbers
    against the merge target rather than the branch base.
  - **Gates reference their subject instead of restating its content,** and any
    gate that can resolve negative carries a pre-written negative branch.
  - **Execution-lane routing.** Stated explicitly with its reason, backed by
    five checkable disqualifiers, because judgment calls under time pressure
    default to "small".

### Rationale

The hard part of planning is deciding what to build, not breaking the build into commits. Once the architectural decisions are locked, the commit-by-commit plan is mechanical. `synthesis-preplan` makes the decision-locking explicit and reviewable so the planner inherits a clear input instead of designing inside its own output. It pairs with `synthesis-code-planning` (which evaluates code-level approaches) and `synthesis-preflight` (the pre-merge gate) to cover the pre-implementation arc.

## [4.21.0] - 2026-08-12

### Added

- `synthesis-inbox-cleanup` v1.5.0: **workspace scoping — cleanup reach follows
  the seat that invokes it.** New `scopes.yaml` contract plus
  `scripts/resolve_scope.py`: a personal operations seat's ritual sweeps every
  account; a client-workspace seat's ritual sweeps only that workspace's
  accounts, so a client engagement's session never reads personal mail and the
  boundary is mechanical rather than remembered. The caller states its
  workspace explicitly — no environment sniffing. Guard-contract exit codes,
  and an **unknown workspace is unverifiable (exit 2), never an empty list**:
  a typo'd workspace must not resolve to zero accounts and read as a clean
  sweep. Seven subprocess tests pin the contract.
- `synthesis-daily-rituals` v2.21.0: Day-Start **Step 3d — Inbox Hygiene**.
  When `scopes.yaml` exists, the morning ritual resolves this seat's scope and
  runs the inbox-cleanup sweep dry-run-first over exactly the resolved
  accounts, reporting per account against the scope. Inbox cleanup becomes a
  standing chief-of-staff duty of the ritual rather than a separate session.

## [4.20.0] - 2026-08-12

### Added

- `synthesis-chief-of-staff` v1.1.0: **the calendar guardian** — doctrine for
  holding a perimeter around the principal's calendar rather than merely
  reading it. Three horizons, each with its own question (next working day:
  *can tomorrow be lived as booked?*; week ahead: *what should move while
  there is still time?*; month ahead: *what needs a lead-time clock started
  now?*); a six-point per-entry review (real, answered, prepared, outcome,
  shape, physically possible) plus a whole-day overcommitment check that must
  produce **named candidates to move with drafted reschedule notes** — a
  warning without candidates delegates the thinking back to the principal;
  and the **same-day shield**: id-tracked, auto-expiring hold events over open
  windows, releasable only from the agent's own holds ledger, converting
  same-day ambush into triage (VIP tiers pass per config). New
  `calendar_guardian` config keys documented in the skill.
- `synthesis-daily-rituals` v2.20.0: the guardian's cadence. Day-End **Step
  4a** reviews the next working day (plus the weekend on the last working day
  of the week) and places tomorrow's holds — in every mode including Quick
  Close, because it generates the drafts the send-or-release pass handles.
  Day-Start Step 6 re-verifies the morning against overnight arrivals and
  refreshes the shield. The owed-weekly review gains the week-ahead and
  month-ahead horizons; the month pass starts absence-coordination
  notification clocks (`notify_on_commit`) while notifying is still early,
  cheap, and conflict-preventing. Unconfigured thresholds report as
  "unconfigured" rather than being guessed.

## [4.19.0] - 2026-08-12

### Added

- **New skill: `synthesis-absence-coordination` v1.0.0** — coordinate an absence
  end to end the way a good chief of staff would. An absence is treated as a
  **handoff with a scheduled reversal**, not an announcement: every work-facing
  notice must answer *who decides in my place, what waits, and how to reach me*,
  or the skill refuses to send it.

  What distinguishes it from ordinary out-of-office tooling:

  - **The ordering fix.** Principals hear it first, from the person — in one
    email with their assistants cc'd, so the assistants get identical lead time
    with no sequencing risk. Group channels are hard-gated behind that message:
    a manager must never learn of a report's absence from a team channel.
  - **Two triggers, not one.** `lead_time_days` schedules the full
    announcement; `notify_on_commit` fires a small cohort (calendar-protecting
    assistants, family) the moment a plan is real — which is what actually
    prevents conflicts, because it lands before conflicting things get booked.
  - **A `personal_continuity` tier** — the tier most absence systems lack:
    trainers, therapists, tutors, caregivers, whose standing commitments travel
    disrupts. Its content is unlike any other tier's: time zone (not city),
    lodging, and agent-researched local facilities, attributed and dated.
  - **A quiet type.** `visibility: minimal` holds the calendar and notifies the
    smallest set while suppressing broadcasts — because a system that can only
    broadcast is abandoned exactly when discretion matters most.
  - **Mechanical disclosure.** Content policies (`dates_only`,
    `dates_city_coverage_reach`, …) are set per tier in config, so what each
    audience learns is enforced rather than re-decided under time pressure.
  - **Config validation with the guard contract.** `validate_config.py` exits
    0/1/2 (valid / defects / unverifiable) and catches the traps that fail
    silently in production: an unverified travel-service sender (forwards are
    discarded with no bounce), distribution-alias recipients (unauditable,
    die in provider migrations), agent-sendable principal tiers, ungated group
    posts. 14 subprocess-level tests pin the CLI contract.
  - **Return handling.** Departure is half the workflow: auto-responder set
    *and* cleared, declined recurrences restored, and the re-entry sweep hands
    off to `synthesis-catchup-ledger`.

  Ships with a fully commented `example-config.yaml` (placeholder names only),
  a schema reference, per-tier message templates, and a fifteen-minute
  quickstart whose rollout doctrine is: pilot on the tiers that forgive
  mistakes (trainer, family) before pointing anything at your workplace.

## [4.18.0] - 2026-08-12

### Added

- `synthesis-meeting-transcripts` v0.6.0: **the optional workspace-mcp auto-start
  service gets a heartbeat.** New `optional-workspace-mcp/doctor.sh`. The bundle
  shipped an installer for a supervised background service and no way to ask
  whether that service was still alive — the one fail-open control in a stack
  whose other guards all ship a health check.

  `install-autostart.sh` records an **absolute** path to `start.sh` into the
  launchd/systemd unit at install time. Move the checkout, rename a parent
  directory, or restructure the repo, and the unit still points at the old path.
  launchd exits `78` (`EX_CONFIG`), `KeepAlive` retries every 30 seconds
  indefinitely, and the log fills with thousands of identical failures. Nothing
  surfaces. The only symptom is that the MCP tools are quietly absent — and
  because "my tools are missing" reads as a client problem, the investigation
  starts in the wrong place. Restarting the client cannot help; the client never
  owned the process. Observed 2026-08-12 against a checkout that had gained a
  `skills/` directory level, after an unknown period of silent failure.

  `doctor.sh` verifies the unit exists; that its recorded start-script path still
  exists and is executable; that the supervisor has it loaded, and with what exit
  status (`78` gets a targeted hint); that the client secret is present; that the
  port is listening; and that the endpoint answers. It also flags the case where
  the unit runs a *different* checkout than the one being edited. Exit codes
  follow the guard contract — `0` healthy, `1` defects, `2` a check could not run
  — because a check that cannot run must never look like a check that passed.
  `--quiet` gives an exit code and one summary line for hooks and rituals.

  The remedy is always to re-run `install-autostart.sh`, never to hand-edit the
  unit: the installer derives the path from its own location and is correct by
  construction. The defect was never in the generator — only in the absence of
  anything that noticed the generated artifact had gone stale.

## [4.17.1] - 2026-08-11

### Fixed

- `synthesis-meeting-transcripts` v0.5.3: **a clean transcript audit no longer
  looks like a broken one.** `verify_transcripts.py --only-incomplete` filtered
  the results list *before* computing the summary counters, so every counter
  described the filtered listing instead of the audited corpus. A clean corpus
  printed `Total: 0 files — 0 incomplete, 0 skipped, 0 no-source-transcript` —
  a clean bill of health rendered byte-identical to "the path was wrong / no
  `.md` files found." Observed 2026-08-11 against a 282-file corpus that was
  actually 0-incomplete, 2 skipped, 19 no-source-transcript; only reading the
  source told the two apart. `--json` carried the same defect through
  `total_files`. This is the flag `synthesis-daily-rituals` uses, so the
  success path was the one that read as a failure — the way a fail-closed
  control gets routed around, and the mirror image of the v0.5.1
  false-positive fix. Counters and the file total now always describe the
  corpus; the filter narrows only the listed rows, and the summary discloses
  that with `(listing filtered to incomplete only)`. An empty listing prints
  `(none — no audited file matches the active listing filter)` rather than a
  bare table. `--json` keeps `total_files` as the corpus count and adds
  `listed_count` plus `only_incomplete` for the listing. Exit codes unchanged.

### Added

- `test_verify_transcripts.py` gains 14 end-to-end reporting checks that invoke
  the CLI against a synthetic clean corpus (complete + skipped +
  no-source-transcript, zero incomplete) and fail if the summary ever reports
  `Total: 0 files` again, plus the inverse case proving filtering still filters
  and a real incomplete file still exits 1. CI and `AGENTS.md` now run this test
  file, which no check previously invoked.

## [4.17.0] - 2026-08-09

### Changed

- `synthesis-daily-rituals` v2.19.0: **every sync covers every configured
  surface.** A sync request (Day-Start Step 3, the Mid-Day Sync Protocol, or
  Day-End Step 1) now covers the workspace's full declared surface set — Slack,
  Google Chat, **email** (inbound AND the user's own sent mail), **meeting
  transcripts** (any meeting ended in the window), and **document comments** —
  not the chat surfaces alone. The surface set is a declared list, exactly like
  the repo list in the source-code sync: the agent does not re-apply its own
  judgment about which surfaces feel active, and a sync that runs fewer
  surfaces than the declared set must name the omission explicitly in its
  report. Origin incident (2026-08-09): a mid-day sync ran Slack and Chat only
  and reported all-quiet while the day's most consequential correspondence — a
  CEO-facing email delivering two Google Docs — had happened entirely on the
  unswept surfaces. Day-Start Step 3b retitled "Channel Sync (Slack + Google
  Chat + email + documents)" with two new checklist items; Day-End Step 1 gains
  the matching final-capture item; the Mid-Day Sync Protocol now enumerates all
  five surfaces and the name-any-gap rule.

## [4.16.0] - 2026-08-07

### Changed

- `synthesis-agent-correspondence` v2.0.0 (BREAKING restructure, one day after
  v1.0.0, from first real-world adoption): the recipient-facing model is now
  **three lanes on a single axis — how much of the principal is in the
  words** — replacing v1's review-tiers-as-primary framing. The lanes:
  principal-direct (their words, their hands — no disclosure), the assistant
  lane (their words, the agent's hands — a single authorship signature), and
  the bot lane (their direction, the agent's words — a handled-for-me
  signature). Review depth (`exact_text`, `per_message_directive`,
  `standing_direction`, `autonomous_initiative`) is demoted to internal
  governance — approval workflow, content limits, logging — and explicitly
  removed from recipient-facing disclosure, because recipients care whose
  words they are reading, not which approval path ran. The `archetype` field
  becomes **binding** rather than tonal: an `assistant` persona carries
  assistant-lane semantics and exactly one signature (exact-text ownership
  required, always); a `bot` persona carries bot-lane semantics and may vary
  its signature by review depth. Motivating discovery: under v1's
  personas-x-tiers matrix, the assistant-persona "unreviewed" cell produced
  self-contradictory signature wording on every attempt — "these are my
  words" cannot honestly combine with "I never saw these words." The v2
  model deletes the impossible cell instead of rewording it, and adds the
  two-direction doubt rule (approval doubt routes toward more review;
  authorship doubt routes toward the weaker claim — when in doubt, claim
  less). Adds the recipient-learnable legend (no marker = all the principal;
  assistant marker = the principal's words; bot marker = the principal's
  direction), a lane-aware guard-pattern note for brand-integrity
  enforcement, and a v1→v2 migration section. The persona-registry example
  bumps to `registry_version: 2` with archetype-binding comments.

## [4.15.0] - 2026-08-06

### Added

- `synthesis-agent-correspondence` v1.0.0 (NEW skill, Communication family):
  how AI agents compose and send correspondence on a human principal's
  behalf, generalized from a mature private communications skill into a
  config-driven public skill (the same public-methodology / private-config
  split as `synthesis-bitbucket` + org-specific companions, or
  `synthesis-model-tiers` + org-specific tier mappings). Covers the core
  disclosure principle (strength scales with how much the principal
  reviewed the exact text before it went out, not with abstract
  categories, following the long-standing ghostwriting/executive-assistant
  pattern); three universal review tiers (`reviewed`,
  `standing_direction`, `unreviewed_substantive`) with hard content limits
  and an always-route-up-never-down ambiguity rule; the default
  human-sends-it-themselves lane, which carries no disclosure question on
  any channel; a persona-registry YAML schema (`id`, `display_name`,
  `archetype`, `emoji`, `url`, `scope`) so a user can brand and route
  between multiple agent identities; the `bot` vs. `assistant` archetype
  distinction that sets whether a persona's signature centers the tool or
  the human as actor; empirically-verified channel disclosure facts
  (Slack's connector force-stamps a visible send tag; most other channels
  don't); a routing heuristic from content type to lane; and the three
  compose/send gates (reply-history, compose-time voice/anti-slop,
  pre-send relevance/grounding) that protect the work underneath the
  disclosure, pointing to `synthesis-message-guard` as their mechanical
  enforcement layer rather than duplicating it.

## [4.14.2] - 2026-08-06

### Fixed

- `synthesis-meeting-transcripts` v0.5.2: `verify_transcripts.py` undercounted
  speaker-attribution lines that carry an inferred-speaker parenthetical
  annotation before the colon (e.g. `**[10:10] Name (Plaud Speaker 4,
  mapped):**`) — the v0.5.1 regex required the colon immediately after the
  name, so every annotated line silently failed to count. Confirmed against a
  production corpus: dozens of undercounted lines across several files, each
  still passing only because it had enough unannotated lines to clear the
  threshold anyway. The fix accepts the annotation only on the timestamp-led
  branch, so it cannot start matching generic markdown field headers that
  share the same "Word (parenthetical):" shape. Also added a `SCRIPT_VERSION`
  banner to every run's output (plus a `--version` flag): the script
  previously had no way to reveal which version produced a result, which is
  exactly what let a stale, orphaned plugin-cache copy go unnoticed and
  produce a batch of false-positive INCOMPLETE flags against an already-fixed
  corpus. `test_verify_transcripts.py` gained matching regression coverage
  plus negative controls for the header false-positive risk.

## [4.14.1] - 2026-08-04

### Fixed

- `synthesis-meeting-transcripts` v0.5.1: `verify_transcripts.py` flagged
  genuine Plaud transcripts as INCOMPLETE. v0.5.0 added Plaud's
  timestamp-before-name format but matched only the unspaced range
  `[00:00-00:08]`; Plaud emits `**[00:00 - 00:08] Name:**` with spaces. Two
  live transcripts carrying 98 and 163 timestamps of real diarized dialogue
  were reported incomplete. Whitespace around the separator is now optional
  and en/em dashes are accepted. A false positive on a fail-closed gate is
  as damaging as a false negative — it teaches bypass. New
  `test_verify_transcripts.py` pins every real-world line shape plus
  negative controls proving a summary still cannot pass.

## [4.14.0] - 2026-08-04

### Added

- `synthesis-executive-communication` v1.0.0 (NEW skill, Communication
  family): translating technical work into communications non-technical
  executives can absorb — for CTOs, CPOs, and product/engineering leaders
  writing to CEOs, division presidents, CFOs, and business peers. The
  every-noun persona test, the six-category kill-list (unexplained
  codenames, workflow/tooling vocabulary, insider praise, defect counts,
  engineering-culture credentials, mechanism-where-consequence-belongs),
  a translation-pattern table, upward-report structure (done-first by
  reader importance, numbers strip, a closed-loop section for the reader's own asks, honest flags,
  forwardability test), and an in-persona adversarial review protocol.
  Distilled from real executive report-revision cycles in which
  engineering-literate review passes structurally missed register
  failures only the intended non-technical reader could reveal.

## [4.13.3] - 2026-08-03

### Fixed

- `synthesis-onboarding` v1.0.1: on a fresh machine with a client present
  but the plugin CLI unavailable, the file-copy fallback was skipped —
  `install.sh status` exits 0 when the target skill directories do not
  exist yet, and the engine's probe read that as "already current." The
  probe now also requires copies to actually be present. Found by the
  post-merge QA run of a live org quickstart; regression test added.

## [4.13.2] - 2026-08-03

### Fixed

- Context doctor v1.2.2: the status header's LEADING CLAUSE decides
  completion. Headers like "Active — Phase 4 is COMPLETE" or "active,
  essentially complete" were read as completed because completion vocabulary
  anywhere in the value outranked the author's leading verdict — four of the
  eight status disagreements in the corpus census were this false positive.
  With corpus-derived regression tests.

## [4.13.1] - 2026-08-03

### Fixed

- `synthesis-context-lifecycle` doctor v1.2.1: explicit `--source` runs no
  longer write the corpus report cache — only full config-discovered runs
  do. The first thing to overwrite the real cache with partial state was the
  doctor's own test suite, caught minutes after 4.13.0 deployed by the new
  SessionStart surfacing reading "1 project" as the corpus. Fixture runs are
  now also isolated via SYNTHESIS_HOME, with regressions for both.

## [4.13.0] - 2026-08-03

### Added

- `synthesis-agent-conformance`: new `parity` mode — fast, filesystem-only
  dual-client drift detection. Verifies the two source manifests agree, both
  clients carry the plugin, both carry the SAME newest version, and that
  version matches source main. The missing daily layer of the dual-runtime
  guarantee; its first live run caught a real release that had reached
  neither client. Fails closed when pointed at a plugin cache instead of the
  source checkout.
- `synthesis-context-lifecycle` v1.5.0 (doctor v1.2.0): every full-corpus
  doctor run writes `$SYNTHESIS_HOME/context-doctor/last-report.json`, so
  session-start hooks and consoles can surface corpus health without paying
  for a fresh audit. Single-project runs never touch the cache. Enforcement
  posture documented: fail-closed for the session's own worked projects at
  day-end, report-only for the corpus.
- `synthesis-daily-rituals` v2.18.0: the parity check joins Day-Start
  Step 1; Day-End Step 7 gains the fail-closed active-project context gate.

## [4.12.0] - 2026-08-03

### Changed

- `synthesis-daily-rituals` v2.17.0: Google Chat joins the channel syncs as a
  first-class source beside Slack — in Day-Start Step 3b (retitled "Channel
  Sync (Slack + Google Chat)"), the Mid-Day Sync Protocol, and Day-End
  Step 1. Workspaces opt in by declaring `.agents/gchat-sync.yaml` (sibling
  to `slack-sync.yaml`); without the config the step skips silently. The
  sub-step encodes four disciplines from the first production rollout:
  enumerate spaces fresh each run (per-meeting spaces churn daily), window
  reads by `createTime` and treat a full page as truncated, preserve the raw
  `users/<id>` on every line beside any resolved name (stable
  workspace-universal keys make later authoritative correction mechanical),
  and apply Slack-DM-grade confidentiality to Chat transcripts.

## [4.11.0] - 2026-08-03

### Added

- New skill `synthesis-onboarding` v1.0.0: one-command onboarding for the
  whole ecosystem. A stdlib-only convergence engine (`onboard.py`) installs
  the synthesis-skills plugin into Claude Code and/or Codex (native plugin
  CLI first, file-copy fallback), scaffolds `ai-knowledge-<workspace>`
  repositories (`init-workspace`), and layers organization knowledge bases
  and shared skills from a declarative `.agents/onboarding.yaml` manifest —
  organizations ship configuration, never installer code. Idempotent
  re-runs with receipts and conffile semantics (user-edited files are never
  overwritten), adopt-in-place of existing clones, superseded-remote
  migration, skill rename/removal tombstones (archive-first), a `doctor`
  with the guard exit contract, plain-language guidance for non-engineers,
  and a closing welcome that says what to try asking. Manifest schema and
  the org wrapper-script template: `references/org-manifest.md`.
- Root `onboard.sh`: curl-able bootstrap (POSIX sh + git only) that clones
  or refreshes this repository and hands off to the engine. Stale caches
  fail loudly instead of installing silently outdated content.

## [4.10.0] - 2026-08-03

### Changed

- `synthesis-git-hooks` v2.3.0: the doctor's drift check no longer assumes
  a personal checkout path for the skill source — a hardcoded default that
  degraded the check on every other machine and violated this repository's
  own no-personal-paths rule. Resolution now mirrors the conformance
  suite's client-binary pattern: `$SYNTHESIS_GIT_HOOKS_SOURCE` when set
  (authoritative; an empty value skips the check deliberately, and an
  invalid value is reported as a doctor problem instead of silently
  comparing against nothing), else the running script's own directory when
  it is not itself an installed engine copy (repo checkouts, worktrees,
  client plugin caches), else the documented locations the ecosystem's own
  installers create. A source directory must carry all three engine files
  to qualify, so a partial copy can no longer report "no drift" for the
  files it lacks, and the doctor names the resolved source in its output.

### Added

- `synthesis-agent-conformance`: a `source.no-personal-workspace-paths`
  scan enforcing the no-personal-paths repository rule mechanically —
  workspace path segments in this public repository must be placeholders
  or documented generic sample names, never a real username, and
  home-anchored personal checkout paths are rejected wherever they appear.

## [4.9.0] - 2026-07-31

### Added

- `synthesis-context-lifecycle` v1.4.1: a context-integrity doctor
  (`context_doctor.py`) for the durable project layer — the one protective
  layer in the stack that had no health check. Audits every project in every
  configured source for tier completeness, budgets, cross-tier status
  agreement, freshness against real git history, and durability (tracked,
  committed, pushed), with the guard exit contract (0 healthy / 1 defects /
  2 cannot establish ground truth) and no silent skips: anything unverifiable
  is reported. Hardened against 30 adversarially-confirmed findings before
  merge, including a fail-open push-state collapse that let never-pushed
  context report healthy.
- `synthesis-daily-rituals` v2.16.0: the context doctor joins Day-Start
  Step 1 beside the git-hooks and message-guard doctors.

## [4.8.1] - 2026-07-30

### Fixed

- `synthesis-git-hooks` v2.2.1: the doctor and hook runs no longer print
  Python `FutureWarning` noise while validating POSIX bracket expressions
  (`[[:alnum:]]`) that are valid ERE for grep. A protective tool that emits
  benign warnings teaches its user to ignore its output.

## [4.8.0] - 2026-07-30

### Added

- `synthesis-disclosure-policy`: two-category disclosure governance for
  people who publish under their own name while handling sensitive
  client work. Published-precedent facts (deliberately public biography, recorded
  in an evidence-cited ledger) are restatable; unapproved disclosures —
  anything learned from private context, negative statements, operational
  detail, identifying descriptions, aggregation — stay closed. Ships the
  ledger schema, five decision tests, surface-class model, and an adoption
  quickstart with a ledger template.
- `synthesis-git-hooks` v2.2.0: publication-surface classification.
  `strict_repo_patterns` pins public OSS repos strict regardless of
  remotes; `public_surface_patterns` classifies author-published site
  repos as `public-surface` — full Tier 1 enforcement (previously these
  either skipped Tier 1 entirely under personal remotes or blocked the
  author's own published biography under strict), minus only the exact
  name patterns the `disclosure_ledger` records as published precedent.
  Evidence-free ledger entries, missing ledgers, and unparsable ledgers
  fail closed; the doctor validates ledger allowances against the policy
  and flags stale ones; commit-message scanning now also covers
  public-surface repos.

## [4.7.0] - 2026-07-30

### Added

- Record-freshness verification: `conformance.py` activation and handoff, and
  the shared SessionStart context, now compare the local project record with
  its last-fetched upstream and flag how many upstream commits touching the
  project subtree are missing locally. A stale checkout can no longer report
  phase, status, and plan with silent confidence; activation refuses to write
  a pointer from a stale record.
- Payload-parity handoff check: `handoff` runs the shared SessionStart script
  in both client envelope formats against the live pointer and verifies the
  enveloped context is identical, without needing either client binary.
- Lease self-declaration (`synthesis-project-management` v1.8.0): a
  lease-managed board carries a `Lease: <remote>` header line that travels
  with the board content. A lease-aware helper on a machine whose
  `lease.json` has not arrived (or was lost) refuses to mutate instead of
  writing a local-only change that the next lease refetch would drop. The
  `lease-disable` command retires a lease sanctionedly — publishing the
  undeclared board through the compare-and-swap path and moving the local
  config to a timestamped `.disabled-` file — with `--local-only` reserved
  for unreachable-remote recovery; the doctor flags declared-but-unconfigured
  boards.
- `retire_worktree.py`: fail-closed retirement of merged feature worktrees.
  Takes the repository explicitly (never inferred from the working
  directory), refuses main worktrees, dirty trees, detached heads, branch
  mismatches, and a working directory inside the target; verifies branch
  ancestry against the freshly fetched remote base before removing anything;
  deletes local branches with safe delete only and remote branches only on
  request.

## [4.6.0] - 2026-07-30

### Added

- Client-binary resolution for verification tooling
  (`synthesis-agent-conformance/scripts/client_binaries.py` and matching
  installer shell helpers): explicit `SYNTHESIS_CLAUDE_BIN` /
  `SYNTHESIS_CODEX_BIN` overrides (a set-but-empty override means absent),
  then `PATH`, then documented stable install locations, so conformance,
  doctors, and plugin detection give the same answer from either client's
  shell, cron, or CI.
- An opt-in git-backed coordination lease (`lease.json` beside the board):
  every board mutation publishes through an atomic git ref compare-and-swap
  on a shared remote, with bounded retry on concurrent advance, fail-closed
  behavior on unreachable remotes, mirror refresh in `status`, and sync
  verification in `doctor`. Enables safe same-resource coordination across
  machines; `synthesis-project-management` v1.7.0.

### Fixed

- `conformance.py runtime` no longer crashes with an unhandled traceback when
  a client CLI is missing; every runtime check reports a structured failure
  and the remaining check groups still run.
- Coordination claim overlap detection now normalizes `~`, absolute, and
  repository-relative claim spellings onto path segments, so two spellings of
  one real path conflict instead of passing silently; ambiguous alignments
  are treated as conflicts.
- Plugin inventory checks validate JSON shape and count only enabled
  installations for both clients.
- The `day-end` launcher resolves its agent CLI through the same override /
  PATH / known-locations order, honors `DAY_END_AGENT_CMD` as a documented
  executable path, and no longer silently degrades "auto" to whichever client
  happens to be on the terminal's PATH.

## [4.5.0] - 2026-07-30

### Added

- A content-addressed inbox-cleanup engine runtime under
  `~/.synthesis/inbox-cleanup/engine/`, with an atomic `current` link shared by
  Claude Code, Codex, and direct Agent Skills clients.
- Installer regression coverage that proves the source tree and working
  directory survive installation, repeated installs are idempotent, and
  drifted immutable releases fail closed.

### Changed

- `synthesis-inbox-cleanup` v1.4.0 no longer requires operational scripts to
  resolve a client-owned, version-numbered plugin cache.
- The installer recognizes both regular Git checkouts and linked worktrees,
  and provenance replaces the obsolete hardcoded fallback list during
  source-free uninstall.

## [4.4.4] - 2026-07-30

### Fixed

- Completed projects now emit no pending actions during activation or
  SessionStart instead of relabeling completed checklist items as next work.

## [4.4.3] - 2026-07-30

### Added

- Tracked, agent-neutral repository instructions for contributors working in
  Codex, Claude Code, or another `AGENTS.md`-aware client.
- A one-line Claude Code import adapter that keeps both clients on the same
  repository rules.

### Changed

- CI now rejects missing or divergent repository instruction adapters.

## [4.4.2] - 2026-07-30

### Fixed

- Installer status now resolves its authoritative skill tree from the current
  source checkout or native plugin before consulting the legacy cache.
- Claude Code and Codex plugin checks require the plugin to be enabled and
  report each client's state explicitly.
- A stale or unavailable cache now fails with a clear diagnosis instead of
  emitting filesystem errors followed by a false pass.

## [4.4.1] - 2026-07-30

### Fixed

- Active-project activation now records the pending items from a project's
  `What's Next` checklist instead of copying the first five lines regardless
  of completion state.
- SessionStart context and active-project activation share one checklist
  parser, including multiline items.

## [4.4.0] - 2026-07-30

### Added

- Cross-agent coordination schema v2, with machine/project identity,
  checkpoint heartbeats, isolated worktree/branch registration, and explicit
  project-context roles.
- Same-project parallelism through one canonical context owner plus
  non-overlapping contributor sessions and session-specific reconciliation
  artifacts.
- Fail-closed checks for overlapping claims, shared worktrees or branches, two
  context owners, and contributor claims on canonical project context.
- Migration, heartbeat, strict status, JSON status, and doctor commands for the
  coordination helper.

### Changed

- `synthesis-project-management` v1.6.0 distinguishes different-project
  parallelism, same-project contribution, git-state isolation, and the
  cross-machine locking boundary.
- SessionStart context and conformance accept and validate the v2 active-session
  table.

## [4.3.0] - 2026-07-29

### Added

- Codex `agents/openai.yaml` interfaces for every public synthesis skill, with
  source conformance that requires the interface, invocation token, and a
  correctly sized short description.
- An agent-neutral day-end installer that atomically places the launcher and
  nudge under `~/.synthesis/day-end/`, refuses symlinked runtime roots, and
  supports persisted `auto`, `codex`, or `claude` selection.
- Dual-client message-guard diagnosis: every installed Claude Code and Codex
  hook configuration must independently gate the complete correspondence tool
  family.
- Regression coverage for day-end source survival, Codex-first auto selection,
  symlink refusal, both client hook shapes, and client-bound runtime paths.
- Commit-hook calibration for exact canonical-file copies: unchanged committed
  content is not reclassified as newly introduced, while a paired control proves
  genuinely new sensitive lines still block.

### Changed

- `synthesis-daily-rituals` v2.16.0 uses the stable synthesis runtime for its
  background automation instead of a client-owned skill cache.
- `synthesis-slack-sync` v3.3.1 resolves its checker from the active skill root.
- `synthesis-inbox-cleanup` v1.3.2 and `synthesis-git-hooks` v2.1.2 make native
  Codex and Claude Code plugins their primary setup path.
- `synthesis-message-guard` v1.1.0 treats an unwired installed client as an
  unhealthy protection layer.

## [4.2.0] - 2026-07-29

### Added

- `synthesis-kb-edit` v1.0.0: a plain-language, config-driven knowledge-base
  editing and shipping workflow backed by `.agents/knowledge-base.yaml`.
- A deterministic knowledge-base contract validator and path classifier.
- `synthesis-okf` v1.1.0 metadata-consistency checks for configured
  frontmatter, date-field aliases, inline duplicates and conflicts, taxonomy
  values, title/H1 agreement, filenames, and topic routing.
- Codex UI metadata for the knowledge-base skill family, with conformance
  checks that keep invocation prompts aligned with skill names.
- Coordination message writes now accept annotated Protocol headings and
  return a clean failure instead of a traceback when the board schema is
  invalid.

### Changed

- `synthesis-knowledge-capture` v1.1.0 now composes the configured OKF
  validation and knowledge-base shipping layers instead of discovering
  tool-owned repository skill copies.

## [4.1.0] - 2026-07-29

### Added

- Cross-agent session coordination for independent Claude Code, Codex, and
  other root sessions: a stable active-session table, source-area advisory
  claims, asynchronous messages, explicit release, OS-locked atomic updates,
  verified backups, overlap detection, and tests.
- SessionStart and checkpoint coordination reads, plus a conformance command
  that validates the shared board schema.

### Changed

- `synthesis-project-management` v1.5.0 makes claim-before-write part of the
  session protocol.
- `synthesis-checkpoint` v1.1.0 treats concurrent-session state as another
  source of drift.
- `synthesis-autopilot` records, refreshes, and releases coordination claims.

## [4.0.0] - 2026-07-29

### Added

- Dual-runtime plugin manifests and marketplaces for ChatGPT/Codex and Claude
  Code.
- `synthesis-agent-conformance`, with source/runtime/instruction/handoff checks,
  active-project activation, and lifecycle context recovery.
- A shared lifecycle hook that restores verified project state at client
  startup, resume, and Codex post-compaction session restart.

### Changed

- Moved the canonical public skills under `skills/`, giving the repository one
  plugin-native source tree.
- Updated project-management, context-lifecycle, checkpoint, skills-manager,
  repo-guard, daily-ritual, git-hook, inbox, transcript, and Mac-sync guidance
  for agent-neutral instructions and native client adapters.
- Removed `~/.codex/skills` as a source-managed deployment target. Codex uses
  the public plugin plus private `~/.agents/skills`; product-owned system skills
  remain client-managed.
- Replaced whole-file Codex config synchronization with an owned-key overlay
  and runtime conformance check.

## [3.19.0] - 2026-07-21

### Changed

- **`install.sh` drift handling: whole-directory detection, pre-overwrite backups, named warnings.** Three changes to how the bootstrap installer treats an installed skill copy that differs from source. (1) Drift detection now checksums the entire skill directory (excluding installer-written `.source.json` and Finder `.DS_Store`) instead of `SKILL.md` alone — a modified script, reference file, or data table (e.g. `tiers.yaml`) now registers as drift instead of being silently replaced. (2) Every drifted copy is saved to `${XDG_CACHE_HOME:-~/.cache}/synthesis-skills-backups/<UTC-run-stamp>/<target>/<skill>/` before the overwrite, including same-name directories that carry no install provenance; backups sit beside the cache directory rather than inside it, so recloning or uninstalling never deletes them, and the newest 10 runs are retained. (3) The end-of-run warning now lists each drifted skill by name, distinguishes unique skills from per-location copies, points at the backup directory, and no longer asserts "local modifications" — a checksum mismatch can equally be an installed copy that is merely older than freshly pulled source, and the installer cannot tell the difference. Motivating incident (2026-07-21): an update run piped through `tail` preserved only the count line — "3 skill(s) had local modifications" — while the per-skill DRIFT lines above it were cut off, and with no backups there was no way to reconstruct which copies had been replaced or what they contained. Investigation showed the count itself was misleading: one skill, one commit behind source, counted once per install location. The summary block now carries the names, so even a truncated tail answers the question, and the backups make it recoverable either way. `synthesis-skills-manager` bumped to v1.1.1 — its bootstrap-installer paragraph now describes the whole-directory drift coverage and backup behavior.

## [3.18.0] - 2026-07-21

### Added

- **`synthesis-project-management` bumped to v1.3.0 — project naming convention.** New "Project Naming" section keys the naming rule to whether a project has a defined end state. Bounded projects (ones that will someday reach `completed`) get verb-first outcome names — `migrate-blog-to-astro`, `release-kb-company-wide` — so the finish line lives in the name, "is this done?" answers itself, and zombie `active` entries become visible on sight. Ongoing projects (operations seats, product stewardships) keep noun names, because there is no finish line to state; time-boxed instances of a standing role (`platform-2026-q3`) already carry their end in the date suffix, and wrapping them in a generic verb (`do-platform-2026-q3-work`) adds ceremony, not information. Generic verbs (`do-`, `work-on-`, `handle-`, `manage-`, `run-`, `support-`) are banned outright, which makes the rule double as a classification diagnostic: if no specific verb fits, the project probably isn't bounded — model it as `ongoing` or split it until concrete outcomes emerge. Existing projects keep their names; the convention applies going forward, and a mixed index is expected since `status` remains the machine-readable lifecycle field. The index.yaml example now shows all three shapes (bounded active, ongoing stewardship, completed).

### Rationale

Observed failure mode in long-running indexes: bounded projects named as nouns (`vendor-contract`, `bedrock-failover`) rot as `active` for months because nothing in the name says what done means — the reader can't tell a stalled arc from a standing stewardship without opening the project. Naming the outcome at creation forces scope definition exactly once, at the cheapest moment, and the generic-verb ban keeps the convention from decaying into `do-X-work` wrappers that carry no information.

## [3.17.0] - 2026-07-18

### Added

- **`synthesis-implementation-integrity` bumped to v1.1.0 — skip-vs-pass aggregation trap in the Test Honesty pass.** New Step 6 names a specific reading error: "X passed, Y skipped, 0 failed" gets read as "tests pass," but it's a different claim — the tests that ran didn't fail, and some didn't run at all. A skip is an absence of information, not evidence. The new step asks whether the skipped set could plausibly contain the one test that validates the exact property a decision depends on, and treats a confident "no" as the bar for proceeding — not the aggregate count. The condensed Quick Integrity Check gets the same one-clause reminder. Field case included, genericized: a suite reporting "911 passed, 29 skipped, 0 failed" looked green; the skips were exactly the tests gated behind a live database connection, including the one that validated a workspace-isolation security control — which turned out to be a silent no-op once that test finally ran.

### Rationale

The existing Test Honesty pass already caught mock gaps and misleading test names, but had no check for the specific shape of this failure: a suite-level summary that aggregates skips and passes into one green verdict. That gap is most dangerous exactly where the stakes are highest — security, data-integrity, and irreversibility claims — because a skip there is silent, and "0 failed" is what a reader's eye catches on the way past it.

## [3.16.0] - 2026-07-18

### Added

- **`synthesis-project-management` bumped to v1.2.0 — parallel sub-agent dispatch hygiene and paused-project scope re-verification.** New "Parallel Sub-Agent Dispatch" section names two risks specific to concurrent writers in the same project: git-index collisions (a bare `git commit` after `git add <your files>` commits everything currently staged, not just what you added — `git add` extends the index, it does not replace it — so `git status --short` / `git diff --cached --name-only` needs to run as a mechanical prefix to every commit, not a judgment call reserved for commits that "feel risky") and tracking-doc aggregation (a sub-agent that correctly leaves its siblings' in-flight work alone also means no single agent sees the combined result — the orchestrator, not any one sub-agent, reads every report as a set and reconciles the shared CONTEXT.md/index.yaml). Separately, Project Discovery gains a scope re-verification step: a paused project's stated "N items remaining" is a claim made at write time, not a live query, and goes stale the moment anything else touches the same corpus — even a workstream with no awareness the paused project exists. Re-derive the count from live disk/repo state immediately before batch-dispatching work against it. This is distinct from context-lifecycle's Session Start Protocol, which checks a file's own freshness against git log, not whether the file's scope claim still matches live reality.

### Rationale

Both additions come from real multi-agent orchestration incidents, not speculation: a git-index collision that swept a background agent's in-progress deletions into an unrelated commit, and a paused project whose recorded "remaining work" count was stale in both directions (some of it already done elsewhere, some of it newly created and uncounted) by the time it was resumed. Fan-out to concurrent sub-agents against one project, and pausing/resuming projects over weeks-to-months gaps, are now routine enough in practice that the skill should name the failure modes explicitly rather than leave them to be rediscovered.

## [3.15.0] - 2026-07-17

### Added

- **New skill: `synthesis-okf` v1.0.0 — validate, convert, and author content for Google's Open Knowledge Format.** OKF v0.1 (announced 2026-06-12 by Google Cloud's Sam McVeety and Amir Hormati) formalizes the markdown-plus-YAML-frontmatter "LLM wiki" pattern this skill family already assumes — the spec's own §10 names it as a target use case. Google's reference repo ships an enrichment agent and an HTML visualizer, but no conformance validator or converter; this skill fills that gap with `okf_validate.py` (checks the spec's three hard conformance rules — parseable frontmatter, non-empty `type`, correct reserved-filename structure — plus soft-guidance warnings and link-checking) and `okf_convert.py` (idempotent frontmatter backfill: never overwrites existing metadata, derives `title`/`timestamp` from H1/git history, renames in-bundle `README.md` to the reserved `index.md` and regenerates it in spec style, walking every ancestor directory to the bundle root so purely-organizational subdirectories don't get skipped). Proven across multiple real conversions from a public 26-doc reference repo up through a 72-doc personal knowledge base and several others of varying size, with the lessons from each folded into the skill's own reference material.

### Rationale

A specification only helps if adopting it is cheap. Google's OKF repo defines the format precisely but doesn't ship the tooling to check or achieve conformance — exactly the gap synthesis skills exist to fill for the broader agent-skills ecosystem. Packaging the validator and converter as a portable skill (rather than leaving them as one-off project scripts) means any Claude Code, Codex, Cursor, or other Agent-Skills-compatible session can adopt OKF for its own knowledge base without re-deriving the tooling.

## [3.14.0] - 2026-07-14

### Changed

- **`synthesis-model-tiers` v2.0.0 — BREAKING: role labels renamed `frontier/efficient/light` → `judgment/routine/bulk`.** The old top label collided with live vendor vocabulary within a day of shipping: the industry uses "frontier" for a vendor's entire current generation (OpenAI applies it to all three GPT-5.6 models, including the cost-optimized one), the opposite of our top-rung meaning — and a tier vocabulary whose primary readers are LLM agents must be corpus-collision resistant, because agents resolve collided words the vendor's way. The new labels promote the roles' own definitions into the label position: they name the WORK (judgment calls where being wrong is expensive; routine rule-following execution; high-volume bulk), which no vendor's marketing will ever collide with. New `references/naming-rationale.md` records the selection criteria, the cross-industry analogies (fuel grades, airline cabins, shipping classes — durable grade vocabularies name the buyer's decision, not the product), the full rejected-candidates table (critical, premium/standard/economy, performance/balanced/efficiency, heavy, lite, base, deep, and others — each with its specific collision or inversion), and the borrowing rule: use an industry word only where you mean exactly what the industry means (`flagship` stays; `frontier` goes). tiers.yaml bumps to `version: 2`; consumers (Ragbot v3.6.0 `tier:` values, global agent instructions, agent memory) rename in the same coordinated pass.

## [3.13.0] - 2026-07-14

### Changed

- **`synthesis-model-tiers` v1.1.0 — one tier vocabulary across policy and product catalogs, plus local-model coverage.** Product catalogs (reference implementation: Ragbot's `engines.yaml` as of v3.6.0) now carry the same `frontier` / `efficient` / `light` labels in a per-model `tier:` field, replacing the older `small` / `medium` / `large` capability classes — one vocabulary for one concept, everywhere it appears. `tiers.yaml` gains an `ollama` provider block (hardware-gated: role lists carry only laptop-fit local models; bigger MoEs remain catalog-only), and the resolution rules document the catalog ⊇ role-lists containment. Consistency between the two files is now ENFORCED, not observed: Ragbot's `tests/test_engines_yaml.py` validates every catalog tier against the vocabulary and cross-checks the installed `tiers.yaml` (models named in role lists must exist in the catalog under the same tier), skipping cleanly on machines without the skill.

### Rationale

The initial release framed role labels and catalog capability classes as intentionally separate vocabularies. In practice they are the same three-rung concept wearing two sets of words, and the correspondence between the files was maintained only by editing them in the same sitting. Renaming the catalog field and adding the cross-check turns silent drift into a loud test failure.

## [3.12.0] - 2026-07-14

### Added

- **New skill: `synthesis-model-tiers` v1.0.0 — cross-provider model-tier convention.** Three role labels — **frontier** (judgment, novel patterns, skill authorship), **efficient** (routine rule-following execution), **light** (high-volume bulk) — resolved to current model identifiers per provider in a single canonical `tiers.yaml`. Skills, project docs, and agent memory reference the labels and never hardcode model names; when a vendor ships a new generation, one file changes. Per role and provider the mapping is an ORDERED PREFERENCE LIST (first = preferred, rest = supported fallbacks), which lets a four-rung vendor ladder express itself inside three roles (e.g., a newest-flagship-first frontier list with the prior flagship as the cost-conscious fallback) and absorbs future rung-merges without schema change. Ships with an update protocol (verify ids against official provider docs, never training data; per-provider verification dates; literal `unknown` over guesses; models only move forward) and consumer guidance for skills, memory, and products. Deliberately NOT a capability catalog — context windows/pricing/thinking metadata stay in each product's own config.

### Rationale

Model names were creeping into skills, memory files, and standing instructions across multiple agentic tools, each copy going stale on its own schedule. One role-to-id table — the same canonical-YAML-plus-readable-mirror pattern already used for the workspace repo manifests — makes tier language portable across Claude Code, Codex, and future runtimes, and makes vendor refreshes a one-file change.

## [3.11.2] - 2026-07-09

### Fixed

- **`synthesis-meeting-transcripts` bumped to v0.4.1** — `optional-workspace-mcp/start.sh`'s already-running check no longer trusts `kill -0` alone: after a reboot the OS can recycle the recorded PID for an unrelated process, making the stale PID file look live, so the script no-ops with exit 0 and a `KeepAlive={SuccessfulExit=false}` supervisor never restarts the server. The check now also verifies the PID's command line matches workspace-mcp and clears the stale PID file otherwise. Field case: the server was down for ~24 hours while launchd reported a healthy last-exit-0, because the pidfile pointed at a recycled macOS system-service PID.

## [3.11.1] - 2026-07-09

### Changed

- **`synthesis-catchup-ledger` bumped to v0.2.1** — Step 3 (judgment pass) gains the owning-CONTEXT rule: before classifying a cross-project item, read the owning project's CONTEXT.md; index descriptions, roll-up summaries, and third-project mentions are secondary caches that lose to the owner's working memory. Extracted from a field case where a stale index description said "pending" while the owning CONTEXT recorded the approval.

## [3.11.0] - 2026-07-08

### Added

- **`synthesis-daily-rituals` bumped to v2.14.0 — Day-End Closure: two-speed day-end, owed-weekly review, decay tags, day-end state.** The day-end gains a first-class **Quick Close** mode (~10 minutes, exactly three human moments: a send-or-release pass over decay-tagged drafts, keep/drop curation of the day's lesson candidates, and a closure read-back), with the session asking the one-letter mode question every time. The Weekly Loose-Ends Review decouples from Friday evening: it becomes owed-weekly, running at the first ritual on/after Friday — day-start included, any mode — tracked via a new `~/.synthesis/day-end/state.json` producer (consumers: the synthesis-console day-end chip, a state-aware evening nudge, the day-start brief line). New plan-generation conventions: time-sensitive drafts carry a `**Decays:** YYYY-MM-DD (reason)` line from creation, and Day-End Step 4 becomes an explicit send-or-release pass over the tagged set; every new commitment line gets a do-by, a Decays tag, or an explicit park; daily plans gain a `## 🌱 Lesson candidates` H2 any session can append to during the day so the day-end curates warm insights instead of recalling them. New `scripts/`: a `day-end` LAUNCHER (opens an agentic session with the ritual invocation as the first prompt — the ritual itself always runs inside the agent session) and a notification-only LaunchAgent nudge (weekdays 16:55, suppressed once today's day-end ran, generic fixed banner text). The autonomous-alerts section is aligned with the alert-confidentiality model: spoken alerts and banners carry zero identifying content and honor the `~/.synthesis/quiet-audio` mute flag.

### Rationale

Field evidence from a four-week catch-up reconciliation: batch send-passes succeeded on every day a ritual ran, every communication decay clustered on the zero-ritual days, and the Friday-only weekly review was silently disabled for three consecutive weeks because it lived inside the ritual being skipped. The redesign makes the default evening close small enough to never skip, decouples the weekly safety net from the most-skipped ritual, moves lesson capture to the moment of insight, and makes skipping visible. The launcher-not-runner distinction is explicit — rituals are Agent Skills that run inside agentic coding sessions; the shipped script only removes cold-start friction — and the only scheduled artifact is a notification, never a mutation.

## [3.10.0] - 2026-07-08

### Added

- **New skill: `synthesis-autopilot` v1.0.0 — autonomous-execution mode for explicitly delegated work.** A thin composition layer, not a new methodology: one explicit delegation phrase ("take care of this for me," "autopilot this," "handle this end to end," "run with it — minimal check-ins") engages a mode that sequences the existing stack — synthesis-thinking-framework for open decisions, synthesis-project-management + synthesis-context-lifecycle + synthesis-checkpoint for compaction-proof state, synthesis-anti-shortcuts for solution quality and sub-agent hygiene, synthesis-implementation-integrity before any completion claim. Protocol unique to the mode: strict trigger discipline (explicit whole-task delegation only; ambiguity resolves to NOT engaging; never ask "should I use autopilot?"); a one-line activation acknowledgment (mode + plan-file path); a self-carrying plan file whose standing-instructions section restores the mode itself after compaction; a three-class decision protocol (constraint-determined → execute; open-and-important → thinking framework; user-only → batch at checkpoints while parallelizable work continues — never block the run on one question); an explicit standing-gates clause (delegation of a task is not delegation of reserved authority — deploy permissions, send-as-user prohibitions, confirmation-first rules, commit hygiene, and verification hooks all survive autonomy); sub-agent fan-out hygiene (≤5 deliverables per dispatch, no minimizing vocabulary in briefs, mandatory acceptance audit on non-clean returns); and confidentiality-safe completion/blocked alerts honoring the environment's mute convention. Domain-neutral: engineering, research, writing, analysis, and operations runs differ only in their verification analog.

### Rationale

Users who repeatedly delegate whole tasks retype the same standing-instruction paragraph per task, and the retyped block fails three ways: clauses drop between retellings (verification and the decision protocol go first), long runs outlive their own instructions when context compacts, and a paraphrase of a discipline is weaker than the skill that defines it. Encoding the delegation contract once — as a mode that composes the six skills already governing decisions, state, quality, and verification — removes the retyping and makes the contract itself compaction-proof via the plan file. Trigger discipline is the load-bearing design constraint: the same user closely supervises some work by choice, so the mode fires only on explicit delegation phrasing, and the asymmetry is stated in the skill (under-firing costs a few extra check-ins; over-firing removes supervision the user chose to keep).

## [3.9.0] - 2026-07-08

### Added

- **`synthesis-mac-sync` bumped to v1.6.0 — per-workspace repo manifests (decentralized inventory).** The repo inventory moves from the central iCloud `git-repos.yaml` to one `repos.yaml` per workspace, living in the workspace's private context repo at `.agents/repos.yaml` and symlinked to `<workspace>/.agents/` by the existing v1.4.0 symlink layer — so cross-machine propagation is git (history, diffs, conflict detection), not iCloud. Schema separates scan-refreshed **fact** fields (path, remotes, default branches) from declared **policy** fields (workspace `status: active|dormant`, per-repo `ritual_sync`, `push_policy`, category, notes) that scans never touch. Two standing rules encoded: **retention** (departure or shutdown retires a workspace to `dormant` — retained on disk, sync paused, nothing ever auto-deleted; dead remotes report once and the clone is kept) and **selective cloning** (the manifest records chosen clones; never enumerate a remote org; listed-but-missing repos are surfaced as decisions unless a machine subscription opts into `auto_clone`). A thin router (`machines.yaml`) keeps the only centralized state: machine inventory, per-machine workspace subscriptions (supports restricted machines such as client-issued hardware), and the workspace → context-repo bootstrap map. The legacy `repositories:` section is transitional with a mandatory drift check until archived.
- **`synthesis-daily-rituals` bumped to v2.13.0** — Day-Start 3a and Day-End 2 enumerate from `<workspace>/.agents/repos.yaml` (`ritual_sync: yes`) when present, honoring `status: dormant`; the workspace CLAUDE.md table remains the human-readable view and the fallback. The v2.12.1 no-activity-judgment rule applies to both sources.

### Rationale

Two independent repo lists (the central mac-sync manifest and the per-workspace CLAUDE.md tables) drifted in the same week — the central one was missing four repos and carried a three-week-stale remote layout. Decentralizing puts the list next to the workspace it describes (where agents already work daily), replaces the fragile additive-merge-over-iCloud discipline with git semantics, and compartmentalizes client inventories so a future restricted machine never holds other clients' names. The facts-vs-policy split is the drift fix: facts regenerate from disk safely; policy survives regeneration.

## [3.8.1] - 2026-07-08

### Changed

- **`synthesis-daily-rituals` bumped to v2.12.1** — source-code sync scope hardening. Day-Start Step 3a and Day-End Step 2 drop the v2.7.0 "associated with active work" qualifier: the workspace `CLAUDE.md` "Workspace Repos" table is the complete decision about what to sync — every repo marked Yes syncs on every ritual run, and the agent must not re-apply its own judgment about which repos seem "active". A workspace excludes a repo by marking it No in the table, with the reason.

### Rationale

The "active work" qualifier delegated a scoping decision to per-run agent judgment, which reliably under-syncs: a collaborator repo judged inactive drifted for ~6 weeks, its default branch still tracking a legacy remote after a Git-host migration and silently accumulating "unpushed" commits that the repo guard flagged repeatedly. Declared configuration beats inferred activity — the table is cheap to edit, visible in diffs, and consistent across runs.

## [3.8.0] - 2026-07-05

### Added

- **Agent Attribution convention** across the project-management skill family. `synthesis-context-lifecycle` bumped to v1.3.0 with the canonical "Agent Attribution" section: when multiple agents (Claude Code, Codex, Cursor, subagents, or different model/effort settings) contribute materially to a project, the session log records one compact attribution line per contributing agent — `agent / model / effort / scope / verified / ref` — at the end of the session entry. Field rules: `model`/`effort` recorded only when the current session or user explicitly provides them, otherwise the literal `unknown` (never inferred — git authorship and `Co-Authored-By` trailers are authored claims, not harness-verified facts); `verified` names only checks that actually ran; no secrets, OAuth/callback URLs, or private config values in any field. Placement follows the tier lifecycle: attribution lines live in `sessions/YYYY-MM.md`; CONTEXT.md gets at most a short `(via <agent>)` tag when identity changes interpretation; REFERENCE.md carries only stable agent facts; substantial artifacts may open with a short Provenance block. Session template updated with the optional line; CONTEXT.md "does not contain" list now excludes per-session provenance explicitly. Three worked examples: routine single-agent, cross-agent handoff with a capability-gap scope note, and multi-model/subagent orchestration.
- **`synthesis-project-management` bumped to v1.1.0** — new "Agent Attribution" component (standalone summary of the same convention, pointing to synthesis-context-lifecycle for full field definitions); Session End protocol gains an "Attribute if warranted" step; Cross-Agent Handoff protocol gains an attribution step so the receiving agent knows who did what, with what verification.

### Rationale

Different agent tools commonly commit under the same human author identity, so git history alone cannot answer "which agent did this, at what capability, verified how." The convention makes provenance durable exactly where it helps future work — the episodic session log — without turning working memory into a telemetry stream. Attribution is opt-in by usefulness (cross-agent handoffs, capability-gap scoping, multi-model work, verification trust), never a per-edit log.

## [3.7.1] - 2026-06-17

### Fixed

- **`synthesis-inbox-cleanup` bumped to v1.3.1** — the v1.3.0 explicit-TLS hardening (`ssl.create_default_context()`) broke IMAP connectivity on the python.org macOS Python, which ships without a usable system CA store: every iCloud/IMAP run failed with `CERTIFICATE_VERIFY_FAILED`. `_lib.py` now prefers certifi's CA bundle (`ssl.create_default_context(cafile=certifi.where())`) when certifi is installed, falls back to the system default otherwise, and surfaces a clear "install certifi" message if verification still fails. Certificate verification is preserved — this fixes the regression without reverting to an unverified connection. `install.sh` now checks for certifi alongside PyYAML.

### Rationale

The hardening was correct in intent (the pre-v1.3.0 `IMAP4_SSL(host)` default did not verify certificates) but was shipped without testing against a live IMAP connection. certifi is the standard remedy for python.org Python's missing CA store; preferring its bundle restores connectivity while keeping certificate-chain + hostname verification.

## [3.7.0] - 2026-06-16

### Changed

- **`synthesis-inbox-cleanup` bumped to v1.3.0** — hardened the prompt-injection sanitizer (`scripts/sanitize.py`) against delimiter-breakout and several adjacent attack classes. The `<UNTRUSTED_EMAIL>` demarcation is now **nonce-bearing**: each message is fenced with a fresh CSPRNG token (`<UNTRUSTED_EMAIL nonce="...">`), and the wrapper token is **scrubbed out of the content entirely**, so an attacker who reads the open-source delimiter still cannot forge a closing tag to break out of the fence. Also added: repeated HTML-entity decoding (defeats entity- and full-width-encoded markers); stripping of bidi isolates (U+2066–2069) and the Unicode Tags block (U+E0000–E007F, "ASCII smuggling"); From-header split into address vs. attacker-controlled display name; URL defang; a `mixed_script_address()` homoglyph advisory flag (IDNA-aware) for the human-review gate; and a shipped output-side gate (`parse_and_validate` / `validate_disposition`) so callers stop hand-rolling the constrained-action-space check. Five new adversarial fixtures (delimiter breakout, encoded delimiter, tag smuggling, envelope spoof, homoglyph sender) and two standalone checks (output validator, mixed-script flag) added to `tests/run_poisoned.py`.
- **Additional hardening from a full security audit** (same v1.3.0 release): a `RAW_INPUT_CAP` (256 KB) applied before the sanitizer's regex/NFKC/entity pipeline (resource-exhaustion DoS guard); scrubbing of the sanitizer's own structural labels (`[envelope …]`, `From-address:`, `(attacker-controlled)`) from content so a body cannot forge a fake verified envelope; a fail-closed credential-at-rest permission check on the `imap.secret` fallback (refused if group/other-readable) plus a `0700` private dir; explicit `ssl.create_default_context()` for the IMAP connection (cert-chain + hostname verification); and YAML `safe_load` inside a context manager. The deterministic engine audited clean — `SEARCH ALL` + filter-in-Python (no IMAP injection), hardcoded move targets, dry-run default, recoverable Trash.

### Rationale

The skill is open source, so the wrapper delimiter is public knowledge. A fixed `<UNTRUSTED_EMAIL>` tag is therefore forgeable: an attacker pastes a closing tag into an email body, then their own instructions, then a re-opening tag, and a naive wrapper lets the injected text escape the "treat as data" fence. The per-message nonce makes the closing delimiter unpredictable, and scrubbing the token from content removes the marker entirely — two independent locks, both of which must fail for a breakout. The same review surfaced adjacent gaps (encoded/invisible markers, body-forged envelopes, homoglyph senders, unvalidated model output) that the release closes together. The architectural layers (deterministic engine writes, LLM only proposes, human-gated `--apply`) already contained the blast radius; this hardens the demarcation layer so it is no longer the trivially-bypassable link.

## [3.6.3] - 2026-06-15

### Changed

- **`synthesis-inbox-cleanup` bumped to v1.2.4** — scoped the v1.2.3 `google_subject_trash` lifecycle-trash to Google's personal-account system only, via a new `catchall.google_lifecycle_senders` (default `accounts.google.com`). Workspace/billing senders (`workspace-noreply@google.com`, `payments-noreply@google.com`) are never matched, so admin/billing/renewal notices for a domain the user administers are never trashed — even with a "subscription is being deleted / account inactive" subject. The decision moved into a unit-testable `should_lifecycle_trash()`, and notices naming a protected domain (`spare_subject_keywords`) stay spared as a second layer.

### Rationale

v1.2.3 matched any Google sender by subject. A domain administrator receives genuine lifecycle/billing notices for managed domains from Workspace and Payments senders, addressed to their catch-all — so a future suspension/deletion notice could have been trashed. Real mail confirmed these arrive from `workspace-noreply@google.com` / `payments-noreply@google.com`, distinct from the `accounts.google.com` personal-account system that sends the stranger-recovery notices; scoping by sender removes the risk without weakening the stranger-recovery cleanup.

## [3.6.2] - 2026-06-15

### Added

- **`synthesis-inbox-cleanup` bumped to v1.2.3** — `icloud_catchall_google_purge.py` gains a `catchall.google_subject_trash` config list. Google account-lifecycle notices (inactivity / "being deleted" / "sign in to keep it") are now trashed by subject even when addressed to a real/spare recipient on the catch-all, not only to stranger aliases.

### Rationale

A catch-all domain owner's real address can be set by a stranger as the recovery address on the stranger's own Google account; Google then mails account-lifecycle notices to the owner's inbox. The manifest keeps them unconditionally because the Google sender lives in `never_touch` (to protect the owner's genuine security mail), and `never_touch` outranks `subject_rules` — so only a separate purge can remove them. The owner's own accounts are active and never receive lifecycle notices, so the subject is a safe deterministic signal; the account being warned about is named only in the body, which no rule reads. Security-alert and sign-in subjects do not match the list and stay in the inbox.

## [3.6.1] - 2026-06-12

### Changed

- **`synthesis-daily-rituals` bumped to v2.10.1** — grounding-protocol hardening for the higher-volume agent-assisted-send era. The "No stale information" verification item now requires checking beyond the target thread: a topic may be resolved in any other channel, DM, or email, and a message rendered obsolete anywhere is obsolete everywhere. Temporal Integrity gains check #5 (cross-channel / cross-medium obsolescence sweep; full-thread re-pull before any email reply; full fact re-verification for drafts older than 24 hours) and points agent send-paths at enforcing this as a mandatory send-time gate.

### Rationale

When an agent sends a small percentage of a user's messages, a stale send is an occasional embarrassment; when it sends a large percentage, staleness checking must be structural. Same-day proof case: a plan asserted a "4 PM meeting today" that a newly-synced channel showed had already happened the prior afternoon — caught by exactly this class of cross-surface sweep before any message referenced it.

## [3.6.0] - 2026-06-12

### Changed

- **`synthesis-daily-rituals` bumped to v2.10.0 — Cockpit Mode.** Adds an alternative canonical day-plan mode for users whose discretionary time is scarce and preemption-prone: (1) budget-bound plans that read the calendar first and commit ≤70% of discretionary windows (preemption buffer explicit in the header); (2) stakes-routed outbound communications via a three-tier authority matrix (Tier A agent-sends with bot labeling + an "On your behalf" digest log; Tier B one-tap APPROVE/EDIT/SKIP batches of ≤5; Tier C user-original work capped at 3 items per plan, each bound to a named calendar window); (3) preemption-is-normal semantics — same-day meetings drop the lowest Tier-C item to the queue automatically, with the synthesis-catchup-ledger ratchet as the safety net. Day-start Steps 1-5 unchanged; only Step 6 (Day Plan) and Step 7 (Morning Messages) behave differently in this mode. Classic mode remains valid.

### Rationale

Six weeks of operating data from a heavy-meeting-load user showed a single structural fault: intake (syncs, transcripts, plans, drafts) runs at machine speed while every outbound action routes through one synchronous human review step regardless of stakes — so time-boxed communications expire in queue while operational work survives. Plans sized to the backlog rather than the calendar shattered on routine same-day meetings, compounding into guilt rather than throughput. Cockpit Mode re-routes the work instead of optimizing the documents: low-stakes operational sends move to the labeled agent tier, voice-and-judgment items become one-tap batches, and the human's plan shrinks to what their actual calendar can absorb. The companion consumer changes (one-tap surfaces, budget bar, Tier-A ticker) are specified in the synthesis-console cockpit design.

## [3.5.0] - 2026-06-10

### Added

- **`synthesis-catchup-ledger` v0.1.0** — NEW skill. Reconciles pending, missed, and incomplete commitments after any gap in the daily-ritual cadence (travel, family visits, illness, crunch weeks). Sweeps daily plans + transcripts + project context over an arbitrary window; classifies every surfaced item into a six-state taxonomy (DONE-LATE / OPEN-ACTIONABLE / OPEN-DECAYING / DELEGATED-UNVERIFIED / OBSOLETE / EXPIRED→LESSON); produces a dated catch-up ledger at `catchup-ledgers/YYYY-MM-DD.md` (sibling to `daily-plans/`); routes survivors into daily plans in small slices (3-7 items) instead of flooding; carries a ratchet marker so successive sweeps compose incrementally. Ships with `catchup_scan.py`, a deterministic candidate generator that scans dated daily plans for unchecked task items, unsent draft blocks, undecided decision headings, and carryover/backlog sections — the same script-plus-judgment architecture as `thread_checker.py` and `verify_transcripts.py`.

### Rationale

The Weekly Loose-Ends Review (synthesis-daily-rituals v2.8.0) assumes Fridays happen; daily plans assume days happen. When the cadence breaks — a normal part of life, not a failure — commitments decay invisibly and the backlog survives as anxiety instead of as records. The ledger is the accounting close for a period of interrupted attention. The EXPIRED→LESSON category is deliberately first-class: items whose window closed are data about detection latency, recorded for learning and then explicitly released, never carried as guilt.

## [3.4.1] - 2026-06-03

### Changed

- **`synthesis-meeting-transcripts`** bumped to **v0.3.1** — verifier-script ergonomics: (a) silently skips files matching `SKIP_PREFIXES = ('_', 'gdoc-', 'email-')` so meta/TODO files, Google Doc imports, and synced email threads don't trip false positives; (b) accepts files containing the literal marker `<!-- VERIFIER: no-source-transcript -->` as `OK (no-source-transcript)` for the legitimate case where Google Meet was recorded but transcription was never enabled at the source. The skill prose documents both mechanisms at Step 4.5. New `--no-skip` flag for debug audits. The 5 → 10 speaker-line threshold from v0.3.0 stays.

### Rationale

The v0.3.0 verifier was strict and produced two classes of false positives in production use: (a) audit noise from non-meeting files in the meetings directory (the TODO doc, gdoc imports), and (b) a real-but-not-fixable category — meetings whose source Doc never had a transcript section because transcription was off at meet-time. Without the no-source marker, the only way to satisfy the verifier was to fabricate a transcript, which the prior rules explicitly forbid. The marker closes that loophole the right way: explicit + grep-able + human-visible. Skip-prefixes are a separate concern (filing hygiene) but ride the same patch.

## [3.4.0] - 2026-06-03

### Changed

- **`synthesis-meeting-transcripts`** bumped to **v0.3.0** — adds a mandatory post-save verification step (new Step 4.5) and an explicit "DO NOT extract content from the Gemini email summary" warning at Step 3. Both changes target the failure mode where an agent reads the Gemini-notes email body (which is a summary of the summary) and writes that to the local file without ever fetching the underlying Drive doc that contains the verbatim word-for-word transcript. The new Step 4.5 invokes a bundled `verify_transcripts.py` script that counts timestamp markers + speaker-attribution lines in each saved file and flags any file with fewer than (default) 5 timestamps + 10 speaker lines as INCOMPLETE. Wire-in points: the skill's protocol Step 4.5, optional integration into `synthesis-daily-rituals` Day-Start Step 2b, and an optional pre-commit hook on the workspace-private repo. The script's exit code is 0 (all OK) or 1 (incomplete files listed) for clean automation.

### Rationale

Skills with multi-component output mandates (notes + transcript, channels + DMs + group DMs, all 10 audit dimensions, etc.) silently fail when an agent stops at the first component because no mechanical check confirms the rest landed. This release embeds the check in the protocol the agent reads and provides the deterministic script the check calls — so future sessions can't substitute partial output for the protocol's full output without the verifier flagging it. Surfaced 2026-06-03 from a real session where multiple weeks of transcripts were saved as summary-only because the skill's mandate was not mechanically verified. Generalized lesson at `ai-knowledge-rajiv/lessons/2026-06-03-skill-output-verification.md`. The same architecture (skill mandate + deterministic verifier) is the recommended pattern for other multi-component skills in this suite.

## [3.3.2] - 2026-06-05

### Changed

- **`synthesis-inbox-cleanup`** bumped to **v1.2.2** — adds two `references/pitfalls.md` entries from a Gmail-to-Gmail mailbox migration session: (a) `imapsync` flag names must be verified against `--help` before destructive runs — `--delete1` / `--delete2` / `--maxerror` / `--expunge1` / `--expunge2` are the actual names, and a typo silently fails with exit 64 instead of doing what you asked; (b) Gmail IMAP throttle makes the `imapsync` ETA throttle-bound, not bandwidth-bound — observed rates of ~0.10 msgs/sec for a fresh account-pair migration, two orders of magnitude below the "1.5 MiB/sec" documented IMAP ceiling. Documentation-only refresh; no engine code change.

### Rationale

Both pitfalls came out of a single migration session where: (1) two flag typos (`--delete` and `--maxerrors`) silently exited the script and the failure went undetected for hours, and (2) the initial 15–30 minute ETA was off by a factor of 6× because Gmail throttled aggressively. Codifying both so future migrations check flag spelling before launch and budget realistic wall-clock from observed throughput rather than byte-count math.

## [3.3.1] - 2026-06-01

### Changed

- **`synthesis-inbox-cleanup`** bumped to **v1.2.1** — adds a pitfall entry to `references/pitfalls.md`: "DKIM / SPF / DMARC pass confirms identity, not intent — do not use authentication as evidence of legitimacy." Operational lesson captured from a real session where the agent over-weighted technical authentication signals against the user's stated context ("I didn't order this"). The fix is a framing rule for LLM-agent inspection paths: present authentication results as evidence of domain ownership only, never as evidence of benign intent. When user-stated context contradicts technical signals, default to user context — they know what they bought, who they met, where they were; the agent only sees headers. No engine code change; documentation-only refresh.

### Rationale

Spoofed-brand domains routinely pass full authentication because they are real domains controlled by the impersonator, just registered on cheaper TLDs (`.support`, `.info`, `.org` siblings of a `.ai` brand). The DKIM / SPF / DMARC stack confirms "this domain authenticated as itself" — never "this sender is benign." Codifying the two-axis verdict (authenticated-by-claimed-domain AND wanted-by-recipient) so future sessions don't repeat the same misweighting.

## [3.3.0] - 2026-06-01

### Changed

- **`synthesis-inbox-cleanup`** bumped to **v1.2.0** — extends the manifest engine's `subject_rules` to support (a) domain-less rules (omit the `domain` clause to match any sender) and (b) a new `subject_starts_with` operator for prefix-anchored matching alongside the existing `subject_contains` substring operator. Both extensions are backward-compatible with v1.1.0 rules.yaml entries — every existing financial subject_rule (Chase / JPM / Bilt / etc. with `subject_contains` + `domain`) continues to behave identically. Use case that drove the extension: calendar protocol responses (`Accepted:`, `Declined:`, `Tentative:`, `Canceled event:`) come from any colleague's domain, and the natural rule is "any sender, subject starts with one of these → archive." Pre-v1.2.0, that rule shape wasn't expressible. The `references/pitfalls.md` entry on this gap is updated with the second occurrence and the fix.

### Rationale

The second instance of the engine being unable to express a natural rule shape (the first was the Zoom no-negation case in v1.0.0). Two specific gaps showed up together: required `domain` clause and `subject_contains`-only matching. The two extensions are tightly scoped and don't touch the disposition vocabulary or precedence order; rule evaluation remains: `never_touch` > `subject_rules` > `senders` > `class_defaults` > `unmatched`. The `subject_not_contains` negation operator was deliberately NOT added in the same pass — that gap remains real (Zoom case) but its shape is sender-anchored not subject-anchored, so the API design is different. Document each occurrence; abstract per case.

## [3.2.0] - 2026-05-31

### Changed

- **`synthesis-inbox-cleanup`** bumped to **v1.1.0** — adds two scripts that emerged from the first production triage session. (a) `scripts/icloud_inspect_senders.py` — per-sender deep inspection (read-only): aggregates all matching INBOX messages, lists distinct From variants + counts + date range + every unique subject most-frequent first, and prints one sanitized body sample from the most recent matching message via `sanitize.py`. This closes a discipline gap: the existing `icloud_tail.py` shows ONE example subject per unmatched sender, which is exactly the circumstantial signal the circumstantial-inference pitfall warns against. The inspector provides the primary evidence a categorization decision should be grounded in. (b) `scripts/icloud_archive_senders.py` — one-time imperative archive of INBOX messages from specific senders (dry-run default, `--apply` gate). This is the escape hatch for the past-archive-but-future-keep pattern: when a personal contact's existing backlog should leave the inbox but their future mail should stay visible, the manifest engine can't express that because it routes by sender pattern, not by date or thread state. Two-step solution documented in SKILL.md: add a `people_known` rule, then run the archiver. Also: `references/pitfalls.md` gains a "Subject rules support only positive `subject_contains`, not negation" entry documenting the engine gap that drove a Zoom-specific one-off during the same session. Adversarial test fixtures unchanged; all 4 still pass.

### Rationale

After the first real triage session using the v1.0.0 skill (28 senders examined with content, 287 messages relocated, ~20 new manifest rules), two helper scripts emerged from /tmp/ that filled clear engine gaps. The inspector enforces the rg@-lesson discipline (examine before classifying) and ensures `sanitize.py` is always in the loop when an LLM agent sees email content — without canonical tooling, sub-agents in future sessions would re-roll inspection logic without the defense layer. The archiver makes the recurring "past archive, future keep" pattern expressible without abusing the manifest engine.

## [3.1.0] - 2026-05-31

### Added

- **`synthesis-inbox-cleanup`** (v1.0.0) — new skill packaging a manifest-driven email cleanup engine across three macOS tool stacks. iCloud and generic IMAP via Python + `imaplib` + YAML rules manifest (planner / executor / census / tail / catch-all Google purge). Microsoft 365 and outlook.com via Mail.app AppleScript template with idempotent whole-set `whose` clauses. Gmail via the workspace-mcp Gmail API for backlog cleanup plus native server-side filters for going-forward routing. Public engine; per-user rules live privately at `~/.synthesis/inbox-cleanup/`. Ships with a dedicated prompt-injection defense layer: a `sanitize.py` module (HTML stripping, NFKC normalization, invisible/bidi-control Unicode stripping, byte-budget truncation, `<UNTRUSTED_EMAIL>` demarcation) and four adversarial test fixtures (subject injection, body injection, HTML-hidden injection, Unicode trickery) with a runner that gates regressions in CI. Documentation includes a full threat model with ten-layer defense architecture, manifest schema, three-tool-stack decision tree, Gmail filter patterns, and a pitfalls catalog covering IMAP substring matching, threads-vs-messages, MOVE capability fallback, circumstantial-inference traps, and the homoglyph cross-script limitation.

### Rationale

Email cleanup at scale needs deterministic rules — LLMs in the decision path on every message are slow, expensive, and a prompt-injection target. The skill encodes the methodology that cleaned ~11,000 messages across 8 accounts and 3 tool stacks in production use, and surfaces the security architecture for any LLM-augmented path explicitly. The public-engine + private-rules separation lets the methodology be shared without exposing per-user data; the adversarial fixtures make the defense layer testable rather than implicit.

## [3.0.0] - 2026-05-21

Quality skills upgrade: the largest revision of the content-quality and fact-checking skills since the suite's creation. Anchors the open-source slop-detection system at [tools.synthesiswriting.org/slopcheck/](https://tools.synthesiswriting.org/slopcheck/).

### Changed

- **`synthesis-content-quality`** bumped from v3.1.0 to **v4.0** — the most comprehensive open-source slop-detection methodology in the suite. New `references/` subfolder structure (7 supporting files) holding the full pattern catalog separately from the SKILL.md prose. New top-level sections: A1 model-family fingerprinting (per-family pattern catalog across Anthropic Claude, OpenAI GPT, Google Gemini, Meta Llama, xAI Grok, DeepSeek, Mistral, Qwen), A2 substance and depth detection (the "beautiful word salad" axis, promoted from a single criterion in v3.1.0 to a full top-level section with 14 co-equal sub-criteria). Cross-cutting layer added: B1 causal-layer attribution (each pattern annotated with likely origin — RLHF reward shaping, training-data skew, alignment tuning, refusal-avoidance, helpfulness optimization, system-prompt artifacts, tokenizer/architecture, product-wrapper effects), B2 combined-signal fingerprints (22 high-fidelity co-occurrence patterns replacing v3.1.0's count-based heuristic), B3 calibration data (signal strength times base rate per family, year-stratified for historical patterns). Era metadata applied to every pattern (active/declining/historical/deprecated) so the catalog works on the entire LLM era as a **compounding archive** — newsrooms doing forensic review of 2023 articles get the same depth of analysis as editors checking today's drafts. ESL safe-harbor calibration codified.
- **`synthesis-fact-checking`** bumped from v1.1.0 to **v2.0** — new `references/` subfolder (5 supporting files). Nine new protocol sections (C1.1 through C1.9): nested attribution and second-party quote handling, paraphrase boundary drift, composite quote detection, position-shifting checks, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, tool-specific hallucination signature checks per LLM family. Refresh of the existing 4a-4g common-error patterns.
- Related skills cross-referenced and lightly updated: `synthesis-writing-pitfalls`, `synthesis-writing-craft`, `synthesis-clean-text`.

### Added

- **`tools/slop-detection/manifest.md`** — stable URL listing every skill file the slop-detection methodology needs. Used by the hosted web app, the Slopcheck GPT, the Slopcheck Claude Project, and the prompt-mode chatbot path so all of them load the same canonical methodology.
- **`tools/slop-detection/prompt-template.md`** — user-facing template for invoking the methodology in any chatbot with web-fetch.

### Rationale

The v3.1.0 catalog was strong on general AI patterns but had four gaps: (1) no family-specific fingerprinting (a "% AI-generated" score is less useful to an editor than "this looks like Claude / GPT / Gemini output"); (2) substance-and-depth was buried in one criterion when it deserved a full axis (slop is the deeper enemy than AI provenance; the tool catches both axes and reports them separately); (3) no causal-layer attribution (editors want to know *why* a pattern exists, not just spot it); (4) no era metadata (the catalog became stale as patterns got trained out of newer model versions).

v4.0 addresses all four gaps. The compounding-archive principle (patterns never deleted, only retired with era tags) is what makes the catalog uniquely valuable: it works on the entire LLM era, not just the current crop. The two-axis discipline (AI-provenance signals plus slop-independence) reframes the problem from yes/no provenance judgments (increasingly unhelpful as AI assistance becomes normal) to substance-and-depth quality (what editors and readers actually care about).

## [2.5.0] - 2026-04-21

### Added
- **`synthesis-meeting-transcripts`** (v0.1.0) — new skill for fetching AI-generated meeting transcripts (Gemini notes + full word-for-word dialogue) from Gmail/Drive into local markdown archives. Tool-agnostic core — works with Anthropic's hosted Gmail/Drive connectors (single account) or self-hosted multi-account MCPs. Per-project config via `.claude/meeting-transcripts.yaml` with named meeting patterns plus a generic fallback. Includes an `optional-workspace-mcp/` bundle with cross-platform auto-start (macOS launchd + Linux systemd user units), start/stop helpers, and a deterministic Python fetcher for shell/cron use. Replaces the manual Gmail → Google Doc → export-markdown → Downloads workflow.

### Changed
- **`synthesis-daily-rituals`** bumped to v2.2.0 — Step 2b "Meeting Transcripts" now documents an automated path via `synthesis-meeting-transcripts` as the preferred option, with the manual Downloads-folder path retained as a fallback for users without Gmail/Drive tooling.

### Rationale
Google Meet + Gemini produces excellent meeting notes + full transcripts, but accessing them requires a tedious manual flow: open Gmail, find the notes email, open the linked Doc, export as markdown with both tabs checked, move the file out of Downloads, archive the email. This new skill collapses that into a single invocation and integrates with the daily ritual so transcripts land in the project archive automatically. The tool-agnostic design keeps the common single-account path simple while making multi-account setups feasible for users with work spanning several Google Workspaces.

## [2.4.1] - 2026-04-20

### Changed
- **`synthesis-code-integration`** bumped to v1.3.1 — the new "Branch Hygiene" section is now branch-name-agnostic. Previous wording hardcoded `main`/`develop`, which tied the rule to Gitflow-style teams and excluded GitHub Flow, trunk-based, environment-branch, and other workflows. The rule is now framed around generic terms ("PR target branch" and "staging branch"), with a Gitflow example kept as one concrete illustration rather than the default.

## [2.4.0] - 2026-04-20

### Changed
- **`synthesis-code-integration`** bumped to v1.3.0 — added mandatory "Branch Hygiene: PR Branches Stay Clean of Staging Content" section with the anti-pattern explanation, the correct per-operation sequence for getting a commit on both PR branch and staging, rationale for why a polluted PR diff is harmful (reviewer time, scope concerns, squash-merge risk), and the incident that motivated the rule.

### Rationale
A one-commit chore PR was opened against `main`. To fast-forward a push to `develop` for staging, the agent merged `develop` into the PR branch. The PR diff ballooned to 6,900 changes from unreleased staging work. The team opened "request changes" on scope grounds. The correct pattern — push to develop as a separate operation, keep PR branch clean — is now codified in the skill.

## [2.3.0] - 2026-04-16

### Changed
- **`synthesis-context-lifecycle`** bumped to v1.1.0 — replaced "Session-End Commit Requirement" with a "Commit Protocol" section that is not deferred to day-end. Added explicit scope rule: only commit repos touched in the current invocation, never workspace-wide. Added reasoning for why point-of-modification commits beat session-end commits (session never ends cleanly, modified rituals skip day-end, compounding uncommitted work).
- **`synthesis-daily-rituals`** bumped to v2.1.0 — added full **Vacation / Observer Mode Ritual** section codifying the sync+context+commit pattern for users who are not actively working. Added top-level **Commit Protocol** section with the same scope rule. Added explicit commit-after-sync requirement to Mid-Day Sync Protocol. Documents what observer mode skips deliberately (messages, comms, amplification) vs. what it must keep (sync, transcripts, commits).
- **`synthesis-repo-guard`** bumped to v1.1.0 — clarified that the skill is a detector, not a committer. Added "Detection vs. Commit" distinction explaining why detection is workspace-wide but commits must be per-invocation-scoped. Updated Claude Code hook recommendation: removed `--quiet` default (silent hooks teach nothing), added `--dirty-only` for scannable output. Added "Defense in Depth" section recommending both `Stop` and `SessionEnd` hooks for long-running conversation scenarios.

### Rationale
Context changes were going uncommitted during long-running and resumed sessions because the commit step was buried in day-end checklists that partial/modified rituals skipped. This release makes commit-and-push part of the same action as context modification, scoped to the current invocation's actual changes.

## [2.2.0] - 2026-04-09

### Added
- **`synthesis-code-audit`** v1.0.0 — 10-dimension diff-based quality framework with PASS/WARNING/FAIL scoring, PR review mode cross-referencing, and context isolation principle
- **`synthesis-preflight`** v1.0.0 — pre-merge quality gate framework with 6 orthogonal dimensions, temporary considerations pattern for tracking workarounds, and mechanical go/no-go verdict
- **`synthesis-review-triage`** v1.0.0 — PR prioritization methodology with weighted scoring (review gap, CI, age, size, labels), author-response detection, queue classification, and prior-review gate

### Changed
- **`synthesis-pr-review`** — expanded "Where This Fits" table from 4 to 8 engineering skills covering the full development lifecycle; added code-audit cross-reference section
- **`synthesis-implementation-integrity`** — expanded "Where This Fits" table to include code-audit and preflight in the verification chain
- **`synthesis-codebase-review`** — expanded "Relationship to Other Verification Skills" to include code-audit and preflight
- **README** — added 3 new skills to Engineering table, updated skill count to 29

### Fixed
- **install.sh** — added 7 missing skills to uninstall fallback list (4 pre-existing: implementation-integrity, skills-manager, slack-sync, voice-profiler + 3 new: code-audit, preflight, review-triage)

## [2.1.0] - 2026-03-19

### Added
- **`synthesis-thinking-framework`** — new skill: four-mode thinking methodology (first principles → systems → complexity → design) with pre-response protocol
- **`synthesis-mac-sync`** — new skill: multi-Mac configuration sync via iCloud with git repo sync, machine inventory, and one-time action system

### Changed
- **`synthesis-pr-review`** bumped to v1.1.0 — 6 improvements from CSA review sprint:
  - Project-specific extension points (convention debt patterns, CLAUDE.md hooks)
  - Scope governance check (PR title vs. actual file scope)
  - Bundled test file detection
  - Structured review comment format with severity labels ([M1], [S1], [C1], [N1])
  - AI-assisted review verification step
  - Post-merge verification reference (generic extension point)
- **README** — added "Learn More" link to launch blog post, updated skill count to 22

## [2.0.0] - 2026-03-18

### Changed (BREAKING)
- **All skills renamed with `synthesis-` prefix** for namespace protection
- **3 content skills merged into 1:** `blog-promotion` + `social-media-post` + `content-promotion` → `synthesis-content-distribution`
- **Skills renamed for clarity** (not just prefixed):
  - `multi-contributor-synthesis-coding` → `synthesis-code-integration`
  - `code-generation` → `synthesis-code-planning`
  - `thought-leadership-writing` → `synthesis-article-writing`
  - `hyperlink-research` → `synthesis-link-research`
  - `ai-content-quality` → `synthesis-content-quality`
  - `blog-revitalization` → `synthesis-blog-refresh`
  - `message-condensation` → `synthesis-concise-messaging`
  - `llm-project-setup` → `synthesis-llm-setup`
  - `creative-writer-setup` → `synthesis-creative-writer`
  - `technical-advisor-setup` → `synthesis-technical-advisor`
  - `anti-watermarking` → `synthesis-clean-text`
  - `response-synthesis` → `synthesis-response-merger`

### Migration from v1.x
```bash
./install.sh uninstall && ./install.sh install
```

### Why breaking
Generic skill names (`pr-review`, `fact-checking`) collide with other skill repos. The `synthesis-` prefix makes every skill globally unique and immediately identifiable as part of this collection.

## [1.0.0] - 2026-03-18

Initial release: 22 public Agent Skills. Superseded by v2.0.0 on the same day.

### Installation

```bash
npx skills add synthesisengineering/synthesis-skills --global --all --copy
```
