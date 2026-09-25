# Synthesis Skills

Proven AI agent skills for code review, content creation, project management, and more. Built on the [Agent Skills](https://agentskills.io) open standard and portable across Claude Code, OpenAI Codex, Cursor, GitHub Copilot, and other capable agents.

Synthesis engineering is the durable layer beneath capable agent clients:
portable methods, version-controlled project state, concurrent-session
coordination, safety policy, and live runtime evidence. It complements native
clients instead of replacing them. Read [why it exists](docs/why-synthesis-engineering.md),
the [runtime integration contract](docs/runtime-integration.md), and the
[contributor guide](CONTRIBUTING.md).

## Fleet docs

Run a personal fleet of Macs as one system: [enroll a second
Mac](docs/fleet-setup.md), [move work between
machines](docs/fleet-handoff.md), and [daily fleet
care](docs/fleet-operations.md).

## What's new

Release **4.149.4** also restores bounded Codex compaction observation without replaying retained history or adding historical usage to measured cost. It refreshes the model-role catalog with public verification
sources and native API mappings. Explicit model and effort choices remain in
control; availability is verified separately for the actual client and account.

Release **4.149.3** reduces repeated Git metadata work during project resolution
and recognizes typed Codex routing metadata without granting execution authority.

Release **4.149.2** aligns native transcript and SessionStart identity checks,
rejects contradictory inbox routing, and recognizes observed Codex activity
and compaction records without granting execution or completion authority.

Release **4.149.1** streams large retained evidence and binds complete project
inventories in compact execution receipts. Fresh capture is required for the
new receipt schema; identity, content and resource checks remain enforced.

Release **4.149.0** adds autopilot 3.4.0: current native transport evidence,
consumer-bound domain quality, decisive uncertainty and explicit resource accounting.
It also delivers the native-observation controller, productive persistence,
current cancellation gates, verified project closure, qualified outcome
evaluation, shared decision ownership and verified decision pages. The reviewed
4.146.0 and 4.147.0 development candidates are included in this release.

Release **4.145.7** preserves each new native cache generation between refresh
commands and restores verified history when a native command is interrupted.

Release **4.145.6** preserves retained native Git recovery outside client-owned
cache trees and verifies the quiet window after mandatory restoration.

Release **4.145.5** preserves Codex's current native checkout during cache
recovery. Published content verification remains required, historical roots keep
their exact recovery checks, and displaced Git-backed trees remain available.

Release **4.145.4** fixes large-project checkpoint refresh and reconciles the
lifecycle transaction after each gated release, preserving adoption preferences
and strict source verification. Muse refresh verifies owned paths and staged
content while preserving previous bundles through replacement and interruption.

Release **4.145.3** reduces repeated path and directory work while retaining
full verification. Incomplete traversal and changes to the project root fail closed.

Release **4.145.2** reduces whole-project checkpoint overhead while retaining
complete content verification, live ownership checks and bounded Stop behavior.

Release **4.145.1** fixes checkpoint publication for large session manifests while
retaining exact-file ownership and ordinary commit protections.

Release **4.145.0** adds autopilot 3.0.0: durable outcome contracts, adaptive
workflows, shared resource budgets, verified repair and capability-based recovery.

Release **4.144.1** repairs public guard runtime dependencies and bounds repeated
Stop feedback while retaining failed health and unfinished work.

Release **4.144.0** hardens autopilot: read-only gate status, verified cron
continuations, scratch-only close refusal, and a per-agent search cap.

Release **4.143.0** adds the multi-workspace Slack registry with
placeholder tokens and the unified/isolated visibility doctrine.

Release **4.142.0** refuses worktree retirement while ignored files
remain, closing the data-loss hole behind intake 56.

Release **4.141.0** reports version drift as PENDING under live
install-plane claims and documents the concurrent-seats ritual mode.

Release **4.140.0** teaches the multi-session coordination loop in
synthesis-autopilot, fixes the CI change-base race, and names failing
cases in R5 output.

Release **4.139.0** declares the thirteen promoted hooks
verified-execution entrypoints for principal consumers.

Release **4.138.0** promotes the per-client hook suite: thirteen
detectors, all defaults-off with health checks and
principal-supplied catalogs.

Release **4.137.0** wires the publish guard into verified
execution and fixes the sites fixture's git identity for CI.

Release **4.136.0** adds the publication authority gate: site pushes
and deploys need a fresh single-use approval, with timeline invariants
and a rapid-redeploy brake above the ledger. Per-site descriptors drive
the content scan and principal naming.

Release **4.135.0** re-syncs the commit gate from the live release
on every install, closing a nine-release skew between the gate and
the claim writer that the health check could not see.

Release **4.134.0** fixes four fleet-reported defects: phantom project
candidates no longer block Stop, retirement narrows the caller's claims
in the same step, stale scopes report once against their owner, and the
rituals skill names its canonical script invocation.

Release **4.133.0** wires the account routing gate into verified
execution: hooks run it via `synthesis exec-public` from the verified
active release.

Release **4.132.0** adds the `synthesis-agent-guardrails` skill: a
fail-closed gate that blocks cross-account calendar and mail artifacts,
inert until you configure your workspaces. Also: push-by-commit-hash
lands cleanly, and CI acceptance reads green on release commits.

Release **4.131.0** retires flush entries per path on blocked
repositories: one foreign file no longer pins a whole root, own work
recommits without the foreign paths, and landed bytes retire even
while dirty.

Release **4.130.0** fixes two coordination defects: narrowing a
claim now keeps the seat file in sync with the board heartbeat,
and the claim-identity snapshot no longer trips on routine git
activity — with errors that name the moved claim.

Release **4.129.0** fixes the coordination `narrow` sense
inversion: `--release` is the explicit primary spelling,
`--keep` states the inverse intent directly, the deprecated
`--area` alias names its release sense aloud, and emptying a
claim warns loudly first.

Release **4.128.0** promotes the snapshot pruner and the
canonical-checkout landing hook to supported public API: orphan
snapshot maintenance is an opt-in ritual step, and explicit main
pushes land in the canonical checkout through the board-claim
contract.

Release **4.127.0** unifies seat/board machine-identity
comparison in one public place: `Seat.board_machine` is the
single comparison operand every reader uses, and the two
native-identity helpers the private control plane borrows are
supported public API instead of underscore internals.

Release **4.126.0** repairs the delivery/outcome receipt contract:
context-outcome records carry the delivery fields forward, so the
latest pointers keep passing the hook-live verifier after injection
instead of failing on the outcome-only record.

Release **4.125.0** delivers project-durable board mail: a message to
`<project> sessions [durable]` reaches whichever seat next owns the
project, across seat turnover, clients, and machines, with `--resolve`
retirement. It also names each session after its project where the
client supports rename, and reports personal layers as their own
skipped update phase instead of burying them in shared-runtime ok.

Release **4.124.0** makes resume invocation name-addressed: the R1
prompt is one sentence naming the skill and the workspace, with no
filesystem path, so it pastes identically into every harness on
every machine.

Release **4.123.1** patches the installed-plane guardian check to
compare resolved interpreter paths instead of argv spellings.

**Idle-holder narrow (September 2026).** Release **4.123.0** lets an
interactive session ask first and narrow second: request-narrow posts a
structured request the holder's next prompt honors automatically, and an
unanswered request older than 10 idle minutes escalates under the
standing direction, recorded on the bus. Every execution verifies before
running, and refused briefings say so instead of staying silent.

**Autopilot run profiles (September 2026).** Release **4.122.0**
resolves the standing checklist from profile layers at engagement,
freezes it into the plan file, and refuses a goals-met close until
every item is done with evidence or waived aloud.

**Skill-output provenance (September 2026).** Release **4.121.0**
verifies generator-backed skill output instead of trusting it: the
decision-packet generator stamps a spec-pinning provenance marker, the
rulings recorder requires a filed spec, and the context doctor fails
unmarked packet pages as defects.

**Seat-schema containment (September 2026).** Release **4.120.0**
binds desktop checkpoints to schema-2 seats by machine label, and makes
strict seat-directory reads skip and name stale seat files instead of
failing closed; an exited harness's seat can be parked on verified
evidence and a single resource succeeded off it.

**Fleet sync (September 2026).** Release **4.119.0** adds
`synthesis sync` for one-command second-Mac catch-up, and contains
stale-seat checkpoint failures to their own row.

**Rulings release (September 2026).** Release **4.118.0** ships
meeting-prep 1.1.0 (register samples, reader profiles, disclosure
default), year-default archive retention, and a preplan credit.

**Seat-heartbeat stability (September 2026).** Release **4.117.0**
reads the clock once for the board row and the seat, and the fleet
setup guide leads with the one-command onboard.

**Meeting-prep onboarding (September 2026).** Release **4.116.0**
scaffolds principal and reader configuration in one command.

**Dogfood corrections (September 2026).** Release **4.115.0** gives
the v2 resume state its own file and keeps the generated index out
of session detection.

**Session archiver (September 2026).** Release **4.114.0** archives
old session periods with the newest always protected.

**Versioned project formats (September 2026).** Release **4.113.0**
versions every project (v1/v2) and migrates on resume — additive,
verified, never overwriting.

**Resume anywhere (September 2026).** Release **4.112.0** ships the
`synthesis-project-resume` skill: one console prompt restarts any
project in any harness with full verified context.

**One command onboards any Mac (September 2026).** Release **4.111.0**
makes the bare installer detect, recommend, and interview through one
menu — install, upgrade, fleet join, workspaces, components, repair —
with robust enrollment (label collisions, renames, concurrent
publishes all handled).

**Flag-free fleet join (September 2026).** Release **4.110.0** replaces
the six-flag bootstrap with `synthesis fleet join`: zero required
flags, GitHub discovery, role from shared state, live progress, and
automatic enrollment publish-back.

**Multi-Mac fleet (September 2026).** Release **4.109.0** enrolls a
second Mac: machine identities, cross-Mac claim exclusion, parked
sessions, sealed handoffs, workspace subscriptions, vault-backed
secrets, and one idempotent bootstrap. See the fleet guides in docs/.

**Succession, shared calendar, review roles (September 2026).** Release **4.108.0**
adds atomic dead-seat claim succession, the §3 shared time-block layer with
a tested overlap service, and the review skill's adjudicator role with the
reproducer separation rule.

**Explicit read-only diagnostics (September 2026).** Release **4.107.0**
adds `--local` across all 17 conformance routes, a passive lease cache
for fetch-free board reads, and acceptance controls pinning the
read-only contract.

**Coordination defect follow-throughs (September 2026).** Release **4.106.0**
re-syncs the commit gate on every update, splits doctor severity into
blocking versus advisory, names dead paths in scope errors, and gives
every ritual sweep blind/unreachable states with denominators.

**Squash-merge gates (September 2026).** Release **4.105.0** lets
squash-merged branches retire by identical-tree proof and lets the
release gate resolve the change-base from single-parent release
commits.

**Three-client releases (September 2026).** Release **4.104.0** brings
Muse into the release train alongside Claude and Codex, makes
coordination claims merge by default with an explicit narrow verb,
advances the main checkout on worktree retirement, and adds ritual
mailbox manifests plus transcript commitment scans.

**Coordination hardening (September 2026).** Release **4.103.0** ships five
fixes from the September operations review: automatic advisory downgrade for
quiet claims, checkout sharing with a loud banner, snapshot retry, empty-seat
board-ref fallback, and annotated session ids in refusals.

**Muse hooks keep the install valid (September 2026).** Release **4.102.1**
stops the lifecycle hooks from writing bytecode into the digest-pinned
package, which had invalidated the install on its first fire.

**Muse adapter spike (September 2026).** Release **4.102.0** ships a native
`.muse-plugin` bundle with SessionStart/Stop lifecycle hooks, `muse:` peer
identity, and transcript binding against Muse's session store. Coordination
CLI usage errors now fail with an unmistakable FAILED banner instead of
echoing the caller's own input back as a false confirmation.

**Full setup from immutable releases (September 2026).** Release **4.101.1**
sets the required modes on copied Git-hook runtimes, so full setup can reconcile
files installed from read-only release caches. Existing policy files retain
their content and permissions; newly seeded policy files remain editable.

**Modular installation and package channels (September 2026).** Release **4.101.0**
adds individual-skill setup, optional inert core staging, explicit activation and
deactivation, and thin packages for Homebrew, npm and Bun. Package installation
runs no setup scripts. [Choose an installation path](https://synthesiswork.org/download/)
or read the [modular lifecycle contract](skills/synthesis-onboarding/references/modular-lifecycle.md).

**Installer failures and completed local pauses (September 2026).** Release **4.100.3**
stops recursive bootstrap fallback after native plugin failure and confines explicit
skill copies to their selected destinations. The Stop observer verifies committed
local source after a claim is released, preserving pending publication records
without issuing new checkpoint authority.

**The cache guardian understands exec-public hooks (September 2026).** Release **4.100.2**
lets the Codex cache guardian archive plugin roots whose hooks run through
`synthesis exec-public`, which stopped the 4.100.1 install at the guardian.

**Receipts name the loaded plugin root (September 2026).** Release **4.100.1**
corrects the 4.100.0 receipts written under `synthesis exec-public`: the
SessionStart receipt names the plugin root the client loaded and records the
execution root separately, and hook-live checks that both carry the same
version.

**Verified execution runtime and coordination contracts (September 2026).** Release **4.100.0**
lands the Python-only sprint of ADR-001: one board grammar and a canonical JSON
contract for receipts, a written lease fence, thirty-day board archival at
day-start, public hooks executed through the verified active release on the
interpreter recorded at setup, a cached pattern-validation step in the commit
sidecar, and bounded repository checks. Changed hook manifests re-trust once in
Codex; no Go code ships.

**Consequence-labeled packets and scoped weekly reviews (September 2026).** Release **4.99.0**
labels every decision-packet option by its consequence: each button carries the
consequence of pressing it, and `--strict-reader` refuses bare acknowledgements
and labels that share every content word. `--file-into` files the spec and the
page in the owning project's `resources/artifacts/`, and `record_rulings.py`
files the returned rulings beside them. `ritual_state.py query weekly-review` is
scoped by `--workspace`, so one workspace's review no longer silences another's
owed-weekly gate, and `sync_watermark.py advance --through` accepts the epoch
seconds `window` prints and Slack's fractional `ts`.

**Stranded manifests and required delegates (September 2026).** Release **4.98.0**
classifies pending-manifest entries beneath a removed, unrecorded worktree as
stranded, names the missing worktree root and the accepted remedy, and keeps
evaluating the other repositories. An operator-asserted `--drop-stranded` retires
such entries only after an append-only ledger record carries the assertion, and
every flush retires each published repository's entries, so long-lived manifests
no longer accrete. The global pre-commit chain fails closed for repositories that
declare `.githooks/required` when the delegate is missing or not executable, and
the doctor's `delegate-required` control reports the same verdict.

**Bitbucket queues and shell-aware peer sends (September 2026).** Release **4.97.0**
reads Bitbucket Cloud repositories in the pull-request queue scan through the
synthesis-bitbucket helper; GitHub is unchanged and other hosts stay named as
unscanned. The peer-send gate judges the command the shell would run,
so quoted heredoc text and quoted data are never a send. Cross-session merge
requests name the target head they were tested against, and worktree retirement
names the accepted base form when it refuses one.

**Checkpoint applicability (September 2026).** Release **4.96.6** distinguishes
ordinary projects from projects that adopted structured state. Ordinary projects
can finish checkpoint inspection without migration or a receipt; missing or
invalid adopted state remains blocking. Native discovery and refresh use the
same distinction, without treating non-applicability as project health.

**Metadata ownership across linked worktrees (September 2026).** Release **4.96.5**
uses one conflict policy for board admission and record-repair consumers. Claims
on the same project metadata conflict across verified linked checkouts, while
disjoint files and ordinary source branches remain independent. Write permission
still requires the actor's exact checkout, branch and paths. Onboarding updates
introduce the shared helper after verifying the installed bundle's origins.

**Successor feedback and session freshness (September 2026).** Release **4.96.4**
routes reports through explicit registry successor links while preserving their
source project and execution boundaries. Freshness checks use dated session
records, so delayed commits do not change the recorded workday; contradictions
and missing evidence remain visible.

**Recovery and daily record corrections (September 2026).** Release **4.96.3**
collects older unresolved deadlines, honors explicit no-plan declarations, and
protects Markdown tables during record edits. Checkpoint identity uses verified
native evidence; removed-checkout recovery requires exact preservation proof.
Shared protocols keep claims aligned with current work and release completed
areas promptly. Incomplete deadline coverage remains visible while other ritual
steps continue.

**Checkpoint output follows both native contracts (September 2026).**
Release **4.96.2** carries diagnostic verdicts in the supported systemMessage field.
Codex strict Stop validation and Claude completion use the same output format;
checkpoint authority and failure checks retain their existing meaning.

**Project inspections finish without a write claim (September 2026).**
Release **4.96.1** checks native identity, pending attribution and a clean project subtree
before marking an unclaimed inspection's checkpoint not applicable. It grants no
write authority or continuity receipt. Real checkpoint failures remain explicit;
repeated Claude Stop failures end with a visible reason instead of a retry loop.

**Refresh existing sessions with one skill (September 2026).** Release **4.96.0**
adds refresh-and-report mode to synthesis-checkpoint, with local deterministic
inspection, configurable campaigns and transactionally deduplicated feedback.
Recovery instructions agree on resolving before prose, and coordination mirror
refresh is serialized with same-machine claim mutations.

**Updates verify shared runtimes too (September 2026).** Release **4.95.7**
refreshes provenance-verified runtime code without resetting personal setup,
executes installed protective doctors, and preserves concurrent receipt edits.
Cross-project controlling plans use one confined resolver, and context edits
reject accidental line fusion while preserving line endings.

**Continuity comparisons leave messages unread (September 2026).**
Release **4.95.6** compares both client contexts without acknowledging inbox delivery or
refreshing project state. Corrupt or unreadable inbox evidence fails diagnosis
instead of appearing as an empty inbox. Normal lifecycle hooks still deliver
and acknowledge messages.

**Long conversations keep their startup evidence (September 2026).**
Release **4.95.5** validates structured session identity with bounded memory, including
large individual messages, and streams the full transcript digest. Doctor and
status expose receipt-validation failures instead of sending an already
reloaded conversation through another restart. Native history is retained;
identity, client-root and release-content checks remain required.

**Continue the existing conversation after a verified reload (September 2026).**
Release **4.95.4** gives consistent recovery advice across installation, update
and diagnosis. A new conversation is a fallback, not the default. Installed
currency and client-session evidence are not presented as proof that the
invoking task reloaded; verified uninstall no longer requests a restart.

**Updates respect existing work (September 2026).** Release **4.95.3** leaves
adopted knowledge checkouts under their owner's control and binds managed
updates to the original branch and upstream. Generated organization instructions
converge on canonical content plus a Claude import adapter, with verified
provenance, retained archives and concurrent-edit protection. Doctor exposes
migration or ownership problems without changing those files. The merged
weekly-review PR queue source is included too.

**Historical recovery shares storage, not mutable files (September 2026).**
Release **4.95.2** deduplicates recovery payloads while keeping every historical
version and the existing 512 MiB limit. Version records preserve file types,
permissions and content hashes. The publisher verifies the archive-aware
guardian before migrating storage or refreshing the client; interrupted
migration remains recoverable.

**SSH organization enrollment follows verified bootstrap acquisition (September
2026).** Release **4.95.1** separates the public HTTPS-only download policy from
the verified CLI's HTTPS/SSH organization operations. Local-file and external
helper transports remain blocked. Enrollment and rollback share the engine's
receipt directory under default, XDG, and explicitly selected state roots.

**Add an organization without resetting an existing installation (September
2026).** Release **4.95.0** adds `synthesis enroll` for saved full or skills-only
installations. It preserves personal configuration, selected clients, and release
policy while registering the organization for future updates. Exact-target
recovery journals protect generated instructions, selected organization skill
copies, receipts, and invite use. Replay, doctor, and uninstall enforce the same
ownership boundaries.

**Private instruction context is now a declared, durable organization overlay
(September 2026).** Release **4.94.0** lets a full organization setup layer one
user-owned committed source after the public and organization sources without
placing its repository or path in the shareable organization manifest. The
source persists in local desired state and is replayed by update and repair.
Existing unreceipted root instructions remain protected unless the user
explicitly requests archive-first adoption; partial activation restores both
client files. Doctor verifies the complete source and output chain. See the
[4.94.0 release notes](CHANGELOG.md).

**Stopped-task verification now follows the causally selected project copy
(September 2026).** Release **4.93.4** accepts an equal or newer resolved
checkout without demanding that recovery preserve the caller's original
worktree pathname. It still requires the same project identity, phase, status,
and controlling plan, while the separate resolver check proves causal
selection. See the [4.93.4 release notes](CHANGELOG.md).

**Structured state now has one readable current-state authority (September
2026).** Release **4.93.3** rejects duplicate current-looking prose outside the
generated state block while preserving explicitly historical snapshots. It
also binds existing-row claim changes, heartbeat, and normal release to the
exact claiming seat; a reason-bearing administrative operation is required to
release another session. See the
[4.93.3 release notes](CHANGELOG.md).

**A pointer left by another session can no longer silence a client's live
receipt (September 2026).** Release **4.93.2** records the SessionStart
receipt before building context, ignores with a notice a pointer it cannot
validate, and keeps the global pointer out of the board inbox. Stale-registry
detection from 4.93.1 remains; project selection remains with the causal
resolver. See the [4.93.2 release notes](CHANGELOG.md).

**The installed system now tells the truth about itself (September 2026).**
Release **4.93.0** makes organization enrollment work from an installed
immutable release, lets a fresh Claude session complete the live-loaded plane,
re-derives every doctor plane from current evidence, gives `synthesis status`
and `synthesis doctor` plain summaries with a next action, seeds a tracked
knowledge-base declaration in the workspace scaffold, adds
`synthesis uninstall --purge`, and pins the native plugin commands to the
stable ref. See the [4.93.0 release notes](CHANGELOG.md).

**Project recovery now follows evidence across checkouts instead of trusting a
remembered path (September 2026).** Release **4.92.1** adds causal discovery
across worktrees, refs, attributed interruptions, lifecycle receipts, pointers,
and claims; structured operational state with a compiled context block;
semantic freshness checks; and session-bound Stop receipts. Divergence and
unreadable evidence stay explicit, safe fast-forwarding cannot overwrite
unrelated work, and one project's autonomous lifecycle can no longer block an
unrelated session. The aggregate conformance path also ignores a valid pointer
owned by a different project while explicit pointer validation stays strict.
See the [4.92.1 release notes](CHANGELOG.md).

**One bootstrap now installs and manages the complete public system (September
2026).** Releases **4.91.0** through **4.91.4** add the stable `synthesis` CLI,
immutable release resolution, full and skills-only profiles, tracked dual-client workspace
instructions, declarative organization enrollment, transactional desired and
observed state, six-plane doctor results, and public outcome verification.
Updates remain explicit. The release gate activates the same content-addressed
generation that both clients verified. Existing plugin-only installations enter
that lifecycle without another setup interview, and running older tasks cannot
invalidate preserved roots merely by creating Python bytecode. The synchronous
post-update cache check waits through an
ordinary background guardian pass, while persistent lock contention remains a
bounded failure. See the [4.91.4 release notes](CHANGELOG.md).

**Peer sessions are addressed by resolver-issued receipts, never by name
(September 2026).** Releases **4.90.0** through **4.90.3** gate every direct session-to-session
send in both clients on a delivery receipt from `coordination.py resolve`,
delivers the board's message bus at each prompt, and reaches Codex threads
through `codex queue`. See the [4.90.3 release notes](CHANGELOG.md).

**A self-report is a claim, not evidence (September 2026).** Release
**4.88.0** makes daily parity read each client's installed manifest on disk
beside the CLI report, and makes the message guard's clean doctor control a
canonical signed message so a pattern that blocks real signed sends fails
the doctor. See the [4.88.0 release notes](CHANGELOG.md).

**The stable plugin path is checked every morning (September 2026).**
Release **4.85.1** creates both new state stores private (0600/0700).
Release **4.85.0** replaces two shared single-slot state files with
append-only logs: the message-guard grounding ledger is now keyed by message
sha, and the chief-of-staff holds ledger is an event log with a mechanical
`is-releasable` check and computed expiry. One slot with N writers loses data
by shape, and concurrent seats are the normal case.
See the [4.84.0 release notes](CHANGELOG.md).

**An "unanswered" claim now has to say when you last looked (September
2026).** Release **4.83.0** adds a config-adopted currency lane to the
message guard: claims about what is unanswered, unsent, or still open must
carry a fresh `read_at`, or the send is blocked. See the [4.83.0 release
notes](CHANGELOG.md).

**Pin a stable path, not a version (September 2026).** Release **4.82.0**
adds `~/.synthesis/plugins/synthesis-skills/current`, maintained by the
gated release and repointed only after both clients verify, and makes every
coordination command announce when it is running from an engine older than
the newest installed. See the [4.82.0 release notes](CHANGELOG.md).

**Slack read targets are resolved by a script that fails closed
(September 2026).** Release **4.81.0** ships the sync preflight: one read
id per target from the config, id prefixes validated per class, a census
that makes a wrong derivation visible, and the declared set the watermark
gate consumes written fresh each run. See the [4.81.0 release
notes](CHANGELOG.md).

**Two operational documents are back under the line budget, with a test
holding them there (September 2026).** Release **4.80.0** restructures the
daily-rituals and Slack-sync skills: every rule and checklist step stays in
`SKILL.md` (454 and 357 lines, down from 1,319 and 762), while history,
formats, examples, and rationale live in `references/`; regrowth now fails
CI. See the [4.80.0 release notes](CHANGELOG.md).

**A sync now proves what it re-read, to the minute (September 2026).**
Release **4.79.0** replaces day-granular sync watermarks with timestamps
per surface and per declared read target: `begin` stamps a run,
`status --since run` names every target the run skipped, `window` prints
the epoch bound a read call takes beside human-readable time, and the Slack
protocol treats the user's own outbound as sweep state. See the [4.79.0
release notes](CHANGELOG.md).

**A stale engine now diagnoses itself instead of blaming the board
(September 2026).** Release **4.78.0** makes the coordination engine refuse
a board newer than itself with a message naming the engine to run, reports
rows wider than it knows the same way, and stops every table rewrite from
growing the board by a blank line. See the [4.78.0 release
notes](CHANGELOG.md).

**Historical tasks now survive cache replacement after the release command
returns (September 2026).** Release **4.77.1** installs a durable, supervised
Codex cache guardian outside the client-owned version tree. It restores only
verified historical roots from the bounded recovery archive, never races the
newest client-owned version, shares the publisher's transition lock, and fails
closed on unsafe or differing content. See the [4.77.1 release
notes](CHANGELOG.md).

**Two release trains on one track now queue instead of colliding (September
2026).** Release **4.77.0** makes release serialization mechanical: a
virtual `release-train:synthesis-skills` claim on the coordination board is
the lock, and `release.py` preflight refuses to gate or publish on a
board-carrying machine unless the running session holds it — while machines
without a board pass with a notice. See the
[4.77.0 release notes](CHANGELOG.md).

**A documented check list that CI outgrew is now a test failure (September
2026).** Release **4.76.5** syncs AGENTS.md's Verification list with the CI
workflow and pins their equality with a test, and widens the
project-management test step to the full scripts directory in CI, the
release gate, and the docs. See the [4.76.5 release notes](CHANGELOG.md).

**Recovery checks separate plugin content from client metadata (September
2026).** Release **4.76.4** keeps source files, hooks, skills, links, and
unknown extras inside the strict recovery digest while excluding the clients'
own checkout, liveness, and install-record paths. This lets the 4.76.3
historical-root repair verify a newly installed Codex root without weakening
its fail-closed content boundary. See the [4.76.4 release notes](CHANGELOG.md).

**Codex refreshes preserve running tasks (September 2026).** Release
**4.76.3** reconstructs every historical plugin root retained by either
supported client before a Codex refresh. Tagged source is authoritative;
pre-tag roots must prove complete manifests, hooks, targets, skills, and safe
links. A single-writer transition lock, bounded recovery archive, partial-root
repair, and post-command quiet-window verification keep already-running tasks'
absolute hook paths valid. See the [4.76.3 release notes](CHANGELOG.md).

**A rule about document budgets now enforces itself (September 2026).**
Release **4.76.2** restructures the project-management skill back under the
repository's 500-line SKILL.md rule — every operating rule stays in the main
document; formats, rationale, and mechanics moved to `references/` — and
pins the budget with a test so regrowth fails CI instead of accumulating.
See the [4.76.2 release notes](CHANGELOG.md).

**An empty home no longer stops at Git identity (September 2026).** Release
**4.76.1** makes guided whole-system onboarding collect the personal
repository's author name and email before mutation when Git has no configured
identity. Non-interactive runs accept `git_name` and `git_email`; both paths
configure only the new repository and complete its initial commit. A rerun also
repairs the half-finished repository produced by 4.76.0. See the [4.76.1
release notes](CHANGELOG.md).

**The bootstrap now installs the system, not only its skills (September
2026).** Release **4.76.0** adds a guided eleven-layer `init`, generic personal
policy scaffolders, one-source kernel generation with a stable propagation
hook, an honest layer-aware doctor, and static CI catalogs covering every skill
and installer. Fresh-home tests run on macOS and Linux, including the WSL-first
Windows contract. See the [4.76.0 release notes](CHANGELOG.md).

**A peer session is addressed by what it owns, never by what a client calls
it (September 2026).** Release **4.75.0** joins the coordination board to
each client's native delivery handle: claims self-register a `client session
ref` (board schema v4, staged migration), `coordination.py resolve` turns a
project or any session identity into the one exact deliverable target —
refusing ambiguity and absence instead of guessing or broadcasting — the
board bus refuses unresolvable addressees, and message-guard v1.4.0 can
block any direct peer send whose target is not a registered active ref. See
the [4.75.0 release notes](CHANGELOG.md).

**A plugin update must not break the task applying it (September 2026).**
Release **4.74.1** repairs both failure surfaces found by the first 4.74.0
SessionStart: the stock python.org macOS runtime now resolves the stable release
through an existing operating-system CA bundle while retaining full TLS and
hostname verification, and the gated publisher preserves real Codex cache roots
across the client's destructive refresh so running tasks keep their loaded hook
code. See the [4.74.1 release notes](CHANGELOG.md).

**A captured directive is not a routed one (August 2026).** Release
**4.73.0** accepts a cited directory of scripts as a preserved target (an empty one still fails). Previously: **4.72.0** matches the open-items review horizon to what an item is — a backlog of intentions is not work owed by a date, and a recorded decision under an open-items heading needs moving rather than a longer horizon. Previously: **4.71.0** fixes five defects found by using 4.70.0 the day it shipped: a disposition finding that re-created itself, a suppression that shipped without its paired check, checks reporting their coverage so the next such gap is visible, the lifecycle rule extended to the tier and budget checks, and a status header that went unread when it was not first on its line. Previously: **4.70.0** makes the context health signal lifecycle-aware (a check that cannot apply no longer fires, and the check that *does* apply to a finished project takes its place) and gives the semantic tier a `reference/` shard so standing projects stop hitting a ceiling built for bounded ones. Previously: **4.69.0** makes persona-signature wire forms mechanically enforced at the send gate (HTML-path email, no visible-URL fallback on link-capable channels). Previously: **4.68.0** upgrades synthesis-autopilot for genuinely unattended runs: a verified continuation mechanism is now part of the delegation contract, enforced by a Stop-hook gate, with budget/runaway control and cycle ledgers. Previously: **4.67.0** adds the byte-faithful send-path rule (a provider-composed email path can rewrite your links; raw MIME stores your bytes). Previously: **4.66.0** makes persona signature links render as native hyperlinks per channel (HTML anchors in email, mrkdwn in Slack, plain fallback only where links are impossible). Previously: **4.65.0** makes the release gate verify installed bytes against source (version parity is not content parity), makes the currency audit refuse a zero scan, and adds dead-pattern and canonical-clean controls to the message-guard doctor. Previously: **4.64.0** teaches the context doctor to catch the failure that happens by
default: an intake artifact that records a directive, reads as handled, and
was never routed to numbered work, declined, or superseded. Intake-class
artifacts now need a CONTEXT reference or a terminal routing marker, or the
doctor warns. See the [4.73.0 release notes](CHANGELOG.md).

**A reviewer that did not write the code, reviewing the code (August 2026).**
Release **4.63.0** repairs what an external adversarial review of
4.55.0–4.57.0 found — a second vendor's model attacking four releases from
detached worktrees and runtime probes: item-currency stamps that failed
open, a blocking gap gate that could be walked past at bootstrap, sweep
steps that contradicted their own preflight rule, a declared-fetch policy
with no execution path, and packet ids that collided after browser
coercion. Seven ship-blocking findings, every valid one repaired in one
release. See the [4.63.0 release notes](CHANGELOG.md).

**Two directions that remove the principal as transport (August 2026).**
Release **4.62.0** pairs the decision packet with a generalized handoff
queue: work moves between agents as sha-pinned files in the project
(`synthesis-project-management`'s new `handoff.py`), decisions move between
agent and principal as one reviewable packet, and `synthesis-autopilot` now
calls the packet as its batched-questions mechanism instead of describing
one. Schema-2 acceptance manifests may now name any repository's
consume-acceptance boundary, so private repositories can run the same
transaction-bound release gate the public one does. See the
[4.62.0 release notes](CHANGELOG.md).

**Structure without comprehension collects nothing (August 2026).**
Release **4.61.0** gives decision packets a reader contract. A packet whose
mechanics all worked collected zero decisions because its rows spoke the
authoring session's internal language; the skill now requires an audience
line, per-row accept/decline impact in the principal's terms, and a glossary
for surviving terms of art — with `--strict-reader` making the contract
enforceable at build time. See the [4.61.0 release notes](CHANGELOG.md).

**A body-perfect article can still fail as a package (August 2026).**
Release **4.60.0** upgrades the writing-quality stack from a real 30-article
publication wave: article packages now get a title-only stranger test, a
title/description/body truth contract, batch headline budgets, and a
slug-closure invariant; content quality gains corpus-level repetition review
with an executable checker, and recovers the philosophy layer dropped in the
March runbook conversion. See the [4.60.0 release notes](CHANGELOG.md).

**Records that accumulate need an outflow, not just an intake (August 2026).**
Release **4.59.0** adds two review surfaces built from signals the system already
recorded and nobody read. A project index gains a capped daily review that names
at most three stale-active projects as decisions; the coordination board gains
the same for claims whose heartbeat has gone quiet, reporting physical evidence
and printing the release command without ever running it. Both exit 0 under
every degraded input, because a check that can break the ritual calling it gets
removed from the ritual. See the [4.59.0 release notes](CHANGELOG.md).

**A status the doctor cannot read is a check that never runs (August 2026).**
Release **4.58.0** makes the project status vocabulary enforceable. On a real
corpus one status was a typo the doctor had *absorbed* into its terminal set
rather than rejected, and another was missing from that set entirely — so five
projects parsed as making no completion claim and quietly skipped their
cross-tier check. Status now answers one question, does this claim attention,
with four values; everything orthogonal is a qualifier field, so the vocabulary
does not have to grow. A new `status-vocabulary` check fails on the unknown and
warns on the retired, naming what each should become. See the
[4.58.0 release notes](CHANGELOG.md).

**A coordination claim now reaches the Git index (August 2026).** Release
**4.53.0** adds `coordination.py check-staged`: before a configured commit can
proceed, the active board session must name the exact worktree and branch, and
its source-area claims must cover every staged path, including both sides of a
rename. Outside paths refuse unless an explicit reason is recorded atomically
on the lease-backed board. The lease read is CAS-fenced against concurrent
release, path aliases resolve before claim matching, and the hook consumes only
a receipt whose bound outcome authorizes the staged tree. Repositories that do
not configure coordination remain usable, while the hook states that this
control is absent and still runs its credential and exposure checks. Every
result names what remains unverified. See the [4.53.0 release notes](CHANGELOG.md).

**A heading cannot make a summary a primary transcript (August 2026).**
Release **4.52.0** adds an executable source-grade boundary to
`synthesis-meeting-transcripts`. Complete raw provider-message records pair an
identifier with bounded message content; loose or conflicting identifiers do
not establish transcript structure. An attribution-bearing claim still needs
an exact record-bound permalink or `message_ts` in the same hashed bytes before
the gate issues a receipt. Structured summaries remain derived regardless of
their filename or heading, and every result names what the checker does not
verify.
See the [4.52.0 release notes](CHANGELOG.md).

**A successful build is not a publication-safety signal (August 2026).**
Release **4.51.0** adds `synthesis-promotion-gate`: an isolated build and
rendered-output boundary that computes routes from frontmatter, checks DOM
text, headings, comments, and raw source under one marker policy, and refuses
missing or undeclared renderer outputs. Its ordinary `check` receipt carries
no authority. Declared DOM channels come from an identity-bound destination
parser or renderer rather than a hand-written HTML approximation; only the
fail-closed `enforce` caller can pass a captured content snapshot to a supplied
promotion command after immediate contract and snapshot revalidation. See the
[4.51.0 release notes](CHANGELOG.md).

**Adversarial review now has an outcome and a stop rule (August 2026).**
Release **4.50.0** adds `synthesis-adversarial-review`: differently shaped
agents attack a closed artifact universe, record concessions and terminal
verdicts, and stop when the principal's outcome is established. Its
fail-closed YAML ledger separates authority from enforcement and blocking
defects from improvements, while `synthesis-autopilot` directly transports
review packets and treats human courier crossings as a budgeted delivery
cost. See the [4.50.0 release notes](CHANGELOG.md).

**The engine that never updated (August 2026).** Release **4.49.0** fixes a
silent failure in `synthesis-inbox-cleanup`'s runtime installer: it repointed
`engine/current` with `mv -f`, but that path is a symlink to a directory, so
`mv` followed it and dropped the staged pointer *inside* the old release rather
than replacing the link. Installs reported success at every step while the
runtime stayed frozen on an older engine. The fix is `mv -fh`; the more useful
change is the regression test that installs twice with differing digests and
asserts the pointer actually moved — the previous suite passed happily against
the bug. See the [4.49.0 release notes](CHANGELOG.md).

**Pick the tier by diagnosis, not by task size (August 2026).** Release
**4.48.0** adds the missing half of `synthesis-model-tiers`: it mapped roles to
model ids but never said how to pick a role. Route by whether the CAUSE is
known — a settled specification is execution, while a symptom report
("this is broken", "the file will not open") is a differential over candidate
causes and belongs in `judgment` even when the subject is one file. Cost scales
with the search, not the fix, and where a mistake must be undone by a more
expensive process the cheap attempt is debt with interest. See the
[4.48.0 release notes](CHANGELOG.md).

**Body currency: stale prose is now checkable (August 2026).** Release
**4.47.0** extends durable-context currency from headers to the operational
body. `Current State` and `What's Next` end with an as-of marker that the
doctor compares against the session log, `context_edit.py` refuses a header
advance that leaves a marker behind, and advancing a marker without changing
the prose requires a recorded review assertion. Success output always names
the body state — a completion signal that says less than it verified
manufactures completion for partial work. See the
[4.47.0 release notes](CHANGELOG.md).

**Stale headers are now doctor defects (August 2026).** Release **4.46.0**
adds per-field header-currency checking to `synthesis-context-lifecycle`: the
context doctor fails when a `CONTEXT.md` header describes an older state than
the project's own session log — including same-day staleness, where date
comparison sees nothing — and `context_edit.py` refuses to create that state
at write time. Fields are judged separately, so a fresh `Phase` can no longer
mask a stale `Last session`. Every regression fixture derives from a real
defect. See the [4.46.0 release notes](CHANGELOG.md).

**Durable-context edits fail closed (August 2026).** Release **4.45.0** adds
`context_edit.py` to `synthesis-context-lifecycle`. A hand-rolled
`str.replace()` against a project record asserts nothing — when another agent
has rewritten the anchored region, the edit silently no-ops while the script
still reports success, and the stale record then passes every
committed-versus-git check. The helper refuses a missing, ambiguous, or
no-op edit without writing, writes atomically, and re-reads the file to
confirm the change landed. See the [4.45.0 release notes](CHANGELOG.md).

**Managed runtime choice and verified model updates (August 2026).** Release
**4.44.0** keeps Ollama as the default while adding an LM Studio adapter for
catalog planning, exact downloads, JSON inventory, and runtime-metadata
verification. llama.cpp and MLX-LM appear as direct runtimes with accurate
capability boundaries. `synthesis-local-model-runtime` **v1.1.0** also adds
dry-run-first Ollama updates with explicit scope and before-and-after identity
receipts. See the [4.44.0 release notes](CHANGELOG.md).

**Runtime configuration is part of model fit (August 2026).** Release
**4.43.6** detects Ollama KV-cache incompatibilities during planning. Its
dry-run-first Homebrew adapter can apply one validated setting with a private
backup, health check, and rollback. Benchmark receipts also reject truncated
responses and reasoning markup that leaks through a disabled-thinking request. See the
[4.43.6 release notes](CHANGELOG.md).

**Empty final responses fail closed in provenance runs (August 2026).** Release
**4.43.5** prevents a thinking model from producing a valid provenance manifest
for zero bytes of final text. The local OpenAI-compatible runner also records
an explicit reasoning-effort request. See the
[4.43.5 release notes](CHANGELOG.md).

**Benchmarks spend their budget on the final response (August 2026).** Release
**4.43.4** disables reasoning traces by default for bounded local samples and
records that choice in the receipt. Operators can still opt in with `--think`.
See the [4.43.4 release notes](CHANGELOG.md).

**Separate installs preserve the complete machine selection (August 2026).**
Release **4.43.3** makes installation transitions merge each verified artifact
into the machine's selected set. Explicit inventory refreshes still replace
that set with the current policy plan. See the
[4.43.3 release notes](CHANGELOG.md).

**Cached recovery now accounts for Ollama normalization (August 2026).**
Release **4.43.2** makes the recovery receipt distinguish zero network transfer
from possible runtime-layer materialization. Hard links avoid a separate
staging copy, but Ollama may normalize the GGUF into a model-sized runtime layer
and retain the registry cache. See the [4.43.2 release notes](CHANGELOG.md).

**Registry timeouts do not waste completed GGUF downloads (August 2026).**
Release **4.43.1** adds a catalog-pinned local-import recovery to
`synthesis-local-model-runtime` **v1.0.1**. If a Hugging Face registry
transaction fails after its GGUF layers are cached, the installer verifies
every full digest and size, uses Ollama's supported multi-file importer without
a separate staging copy, and records the resolved local identity only after
success. See the [4.43.1 release notes](CHANGELOG.md).

**Local model selection is a measured machine decision (August 2026).** Release
**4.43.0** added `synthesis-local-model-runtime` **v1.0.0**: a privacy-safe
profiler, dated artifact catalog, machine-fit planner, dry-run-first installer,
per-computer inventory, exact resolver, and bounded benchmark receipts. It
keeps model weights out of iCloud and source workspaces, records upstream model
owners separately from quantization publishers, and refuses to treat provider
origin or a successful local run as evidence of trust, authorship, or watermark
absence. `synthesis-repo-guard` **v2.3.0** can now transition one verified
session to remote readiness without coupling it to unrelated pending work. See
the [4.43.0 release notes](CHANGELOG.md).

**Writing quality and text provenance are separate axes (August 2026).**
Release **4.42.0** keeps every prior writing pattern and actionable rule while
adding nine editorial criteria for current source-loss, structure, residue,
voice, and agent-chronology failures. `synthesis-content-quality` **v4.1.0**
now separates quality, model-shaped style observation, technical provenance,
and authorship; inherited numerical detector claims remain available as dated
research hypotheses, not measured probabilities. A hash-bound semantic
preservation test makes any future removal or factual correction explicit.

The new `synthesis-text-provenance` **v1.0.0** records self-hashed manifests,
native runtime receipts, direct-parent lineage, local/open-weight one-shot
generation, and non-mutating text-integrity audits. It can document what a
generation path and an authorized detector establish; it will not defeat a
provider mark, optimize rewriting against a detector, disguise authorship, or
promise that text is watermark-free. See the [4.42.0 release notes](CHANGELOG.md).

**A named project is one signal, not an override (August 2026).** Release
**4.40.0** adds the project-name contradiction guard to
`synthesis-project-management` **v2.4.0**: when a request names a project
that contradicts the session's own evidence — its established conversation,
session name, active-project pointer, or working directory — the agent asks
a one-line clarifying question instead of silently switching. Humans
navigate many similarly-named projects, and sibling projects share
vocabulary; a wrong silent resolution sends a whole session's work to the
wrong project's records. The SessionStart recovery guidance
(`synthesis-agent-conformance` v1.6.1) now carries the same exception, so
the emitted guidance can no longer instruct the behavior the discovery
protocol forbids. See the [4.40.0 release notes](CHANGELOG.md).

**The chief-of-staff AI speaks as you; the EA AI speaks for you (August 2026).**
Release **4.39.0** gives `synthesis-agent-correspondence` **v3.0.0** a voice
axis: an assistant-archetype persona (the chief of staff) writes in the
principal's first person, on words the principal genuinely owns, while a
bot-archetype persona (the executive assistant) speaks in its own voice —
"I" means the agent, and the principal appears by name, in the third person.
The grammar itself becomes the disclosure: no excerpt of an agent-voiced
message can silently impersonate the principal, routine errors read as the
assistant's rather than the principal's, and the principal's own "I" stays
meaningful because it only ever appears on words they own. Appreciation and
other sincerity-bearing messages route to the principal's voice, always. The
model borrows the conventions of human chiefs of staff and EAs because they
work — and it is built as leverage for people in those roles, and as working
support for principals who have neither. See the
[4.39.0 release notes](CHANGELOG.md).

**A plan shell has to speak the renderer's vocabulary (August 2026).** Release
**4.33.0** closes a quiet failure in `synthesis-daily-rituals` **v2.24.2**:
renderers classify plan sections by heading vocabulary, so a shell written with
invented headings still renders — as undifferentiated prose — while every typed
region the reader actually works from comes up empty. The plan looks blank
precisely when it is full. Shells now reuse the established headings for any
region they populate and confine novelty to the coverage block and pointer
lines, with producer and consumer required to change together. See the
[4.33.0 release notes](CHANGELOG.md).

**Grounding discipline: the truth side of agent output (August 2026).** New
`synthesis-grounding-discipline` skill **v1.0.0** is the companion to
`synthesis-anti-shortcuts`: where anti-shortcuts stops output that does less
than the work requires, this stops output that claims more than the evidence
supports. Eleven rules in four groups — record only what a source surfaced
(anti-confabulation, quote provenance), caches are not truth (re-verify before
propagating, with a verifying-command-class table; runtime and IaC as distinct
layers; read the artifact in hand before theorizing; count the corpus before
writing "dominant"), proving absence (positive controls, truncated output as a
pointer rather than content, zero search results as no evidence at all), and
grounding writes and deletions (verify the path first; move-verify-delete,
independently validated recursive targets, non-path cleanup sentinels) — each
carrying an anonymized production incident. The same release adds the
instruction-kernel pattern reference to `synthesis-agent-conformance`
**v1.6.0**, a five-deliverable brief-size cap to `synthesis-anti-shortcuts`
**v1.1.0**, repo families and deletion units to `synthesis-context-lifecycle`
**v1.8.0**, and the question-shape trigger plus zero-result absence protocol to
`synthesis-slack-sync` **v3.4.0**. See the
[4.32.0 release notes](CHANGELOG.md).

**A release ships or it fails, with nothing in between (August 2026).** Release
**4.31.0** puts the whole cross-client release behind one fail-closed command in
`synthesis-skills-manager` **v2.1.0**: preflight, the required checks, publish
to every configured push remote, install into both clients using each client's
own commands, verify. Each client is verified twice — what its CLI reports, and
the plugin manifest at the path the CLI says it loads — because a client can
report the intended version while the tree it loads is stale, which is exactly
the drift a report-only check passes green. See the
[4.31.0 release notes](CHANGELOG.md).

Release **4.30.0** separates daily-plan storage by organization: workspace plan
content lives in each workspace's private repository (the worker artifact
doubles as the plan fragment) while the person-side plan is a shell that
consumers merge at display time — so leaving an organization means deleting its
folders, with no plan residue. See the [4.30.0 release notes](CHANGELOG.md).

Release **4.29.0** adds distributed ritual execution to the daily rituals: a
desk seat folds per-workspace worker artifacts into one daily brief with a
mandatory coverage line, under a client-neutral worker-artifact contract
(workers write files, the desk reads files — absence of an artifact is itself
the signal). See the [4.29.0 release notes](CHANGELOG.md).

**Accepted SessionStart evidence is no longer a singleton (August 2026).**
Release **4.27.0** preserves every genuine Claude Code and Codex SessionStart
under its client and session identity, while retaining separate monotonic
latest pointers for current-health checks. Conformance can now reverify exact
accepted sessions without hiding drift in the newest unrelated start. See the
[4.27.0 release notes](CHANGELOG.md).

**The pointer and continuity share one stopped-task contract (August 2026).**
Release **4.26.0** lets the active-project pointer accept the same
session-attributed uncommitted record that local continuity accepts, so a live
owner can activate mid-handoff without an off-contract commit. Unattributed
edits still fail closed, the attribution primitives are shared so the two
contracts cannot drift, and board workspace claims may carry their
conventional parenthetical annotations. See the
[4.26.0 release notes](CHANGELOG.md).

**Claude Code SessionStart evidence follows the real lifecycle (August 2026).**
Release **4.25.3** records the genuine hook event even when Claude creates its
transcript immediately after the hook returns. Acceptance still requires that
exact client-owned transcript to bind the same session UUID, so a static script
probe cannot satisfy the live gate. See the [4.25.3 release notes](CHANGELOG.md).

**Verified cleanup is part of continuity (August 2026).** Release **4.25.2**
makes worktree retirement a resumable handoff transaction. One lifecycle lock
spans durable intent, removal, manifest reconciliation, and receipt
invalidation. The ancestry authority is a freshly fetched remote-tracking
commit, the reconciler is content-addressed outside the target before removal,
and interrupted recovery executes that exact pinned copy. Optional remote
branch deletion uses a lease bound to the verified remote head. Missing paths
without that proof still block Stop. See the [4.25.2 release notes](CHANGELOG.md).

**Codex catalog pressure is now engineered, not tolerated (August 2026).**
Release **4.24.1** adds an implicit-core/explicit-specialist catalog with a
public routing skill, app-server-backed hook and skill audits, live capability
evidence, leased active-project validation, session-safe plugin refresh semantics,
and an explicit supported-surface matrix. Claude Code keeps its complete
native trigger behavior; Codex keeps every specialist explicitly available
with measurable prompt reserve. See the [4.24.1 release notes](CHANGELOG.md).

**Release surfaces can no longer drift apart (August 2026).** Conformance
gains `source.changelog-version-parity` **(4.23.0)**: both plugin manifests
must match the CHANGELOG's top release heading, failing closed when either is
missing. The gap it closes shipped twice with every other check green.
Suggested by Emil Peñaló during the `synthesis-preplan` review. See the
[4.23.0 release notes](CHANGELOG.md).

**Architecture decisions locked before the plan exists (August 2026).** New
`synthesis-preplan` skill **v1.0.0** (Engineering family): a structured Q&A loop
that locks the load-bearing design choices, then hands a reviewable decision set
to your planning step, on the premise that the hard part of planning is deciding
what to build rather than breaking the build into commits. Three decision-quality
checks sit in the rubric because nothing downstream catches a wrong decision: an
audit verifies an implementation *against* locked decisions, which makes a locked
row the one thing it never re-opens. Bundles two execution lanes it carries
itself, the multi-commit workflow and a single-commit companion, with the routing
test stated explicitly so the lane is never inherited silently. Pairs with
`synthesis-code-planning` (code-level approaches) and `synthesis-preflight` (the
pre-merge gate). See the [4.22.0 release notes](CHANGELOG.md).

**The EA layer: absence coordination and the calendar guardian (August 2026).**
New `synthesis-absence-coordination` skill **v1.0.0**: an absence treated as a
handoff with a scheduled reversal, not an announcement — principals hear it
first in one email with their assistants cc'd, group channels are hard-gated
behind that message, every work-facing notice must answer *who decides, what
waits, how to reach me*, and a `personal_continuity` tier keeps the trainer or
therapist whose standing sessions travel disrupts informed with time zones and
researched facilities. A quiet type notifies the minimum while suppressing
broadcasts. Config-validated (guard-contract exit codes, subprocess-tested);
ships with per-tier message templates and a fifteen-minute quickstart. And
`synthesis-chief-of-staff` **v1.1.0** adds the **calendar guardian** doctrine —
next-day/week/month look-ahead horizons, per-entry review checklists,
overcommitment checks with named move-candidates, and id-tracked auto-expiring
holds that shield open time from same-day ambush — wired into the
daily-rituals cadence by `synthesis-daily-rituals` **v2.20.0**. See the
[4.19.0 and 4.20.0 release notes](CHANGELOG.md).

**Agent correspondence, generalized (August 2026).** New `synthesis-agent-correspondence` skill (Communication family): how AI agents compose and send correspondence on a human principal's behalf, honestly. v2 models it as three lanes on one axis — how much of the principal is in the words: principal-direct (their words, their hands — no disclosure), the assistant lane (their words, the agent's hands — one authorship signature), and the bot lane (their direction, the agent's words — a handled-for-me signature) — with review depth demoted to internal governance and the bot-vs-assistant archetype binding a persona to its lane. Recipients learn the legend from the emoji alone. Includes the persona-registry config schema, verified channel-disclosure facts, and the three compose/send gates that pair with `synthesis-message-guard`. See the [4.16.0 release notes](CHANGELOG.md).

**Executive communication for technical leaders (August 2026).** New `synthesis-executive-communication` skill (Communication family): translating technical work for the non-technical executives who fund it — the every-noun persona test, the six-category kill-list, mechanism-to-consequence translation patterns, upward-report structure, and an in-persona adversarial review protocol. See the [4.14.0 release notes](CHANGELOG.md).

**One-command onboarding for people and whole organizations (August 2026).**
New skill `synthesis-onboarding` **v1.0.0**: a convergence engine that takes
a bare Mac to a working synthesis setup — plugin into Claude Code and/or
Codex, an `ai-knowledge-<workspace>` scaffold, receipts-backed idempotent
re-runs that repair half-finished installs and never overwrite files you
edited, skill rename/removal reconciliation, and a built-in doctor. An
organization onboards its members by shipping one declarative
`.agents/onboarding.yaml` manifest in its knowledge-base repo — no
installer code — and the curl-able `onboard.sh` covers individuals. See the
[4.13.2 release notes](CHANGELOG.md).

**Portable drift detection, mechanically enforced (August 2026).**
The `synthesis-git-hooks` **v2.3.0** doctor no longer assumes where the
skill source lives: its drift baseline resolves through an explicit
override, the running copy itself, or documented install locations, so the
same health check works from a fresh machine, a worktree, or a plugin
cache — and a misconfigured override fails closed instead of silently
skipping. `synthesis-agent-conformance` now scans the repository for
personal workspace paths so this class of defect cannot return. See the
[4.10.0 release notes](CHANGELOG.md).

**Disclosure governance by precedent, not blacklist (July 2026).**
`synthesis-disclosure-policy` distinguishes the names you deliberately
publish in your own biography from disclosures nobody approved, backed by
an evidence-cited precedent ledger. `synthesis-git-hooks` **v2.2.0**
enforces it by publication surface: your site repos get full protection
minus your ledgered names, public OSS repos stay pinned strict, and a
missing or unverifiable ledger fails closed. See the
[4.9.0 release notes](CHANGELOG.md).


**Trustworthy resumption and safe retirement (July 2026).**
Activation, handoff, and SessionStart context now detect stale project
checkouts by comparing the record with its fetched upstream, and handoff
verifies that both client envelope formats carry identical context.
`synthesis-project-management` **v1.8.0** makes lease-managed boards
self-declaring — a machine without the lease config refuses to write rather
than losing changes silently, with a sanctioned `lease-disable` path — and
adds `retire_worktree.py` for fail-closed, remote-verified retirement of
merged worktrees. See the [4.7.0 release notes](CHANGELOG.md).

**Symmetric verification and cross-machine coordination (July 2026).**
Conformance checks, doctors, and installers now resolve the Claude and Codex
CLIs through overrides, `PATH`, and documented install locations, so the same
verification runs from either client's shell. `synthesis-project-management`
**v1.7.0** adds an opt-in git-backed coordination lease — an atomic ref
compare-and-swap on a shared remote — for safe same-resource sessions across
machines, and claim-overlap detection now matches mixed absolute, `~`, and
relative claim spellings. See the [4.6.0 release notes](CHANGELOG.md).

**A stable inbox engine across native clients (July 2026).**
`synthesis-inbox-cleanup` **v1.4.0** installs verified, immutable engine
releases under `~/.synthesis/inbox-cleanup/engine/`. Claude Code and Codex
private workflows now share `engine/current` instead of depending on either
client's version-numbered plugin cache. See the
[4.5.0 release notes](CHANGELOG.md).

**Clean handoff after project completion (July 2026).** A completed synthesis
project now emits no pending actions during activation or SessionStart; checked
items are never relabeled as future work. See the
[4.4.4 release notes](CHANGELOG.md).

**One repository contract for every agent (July 2026).** The public source now
tracks its own `AGENTS.md`, with Claude Code importing that same contract
through a one-line adapter. CI verifies both files so contributors using Codex
and Claude Code receive the same repository rules. See the
[4.4.3 release notes](CHANGELOG.md).

**Trustworthy native-plugin status (July 2026).** Installer status now reads
the checked-out or plugin-packaged skill tree directly, verifies that the
Claude Code and Codex plugins are enabled, and fails clearly when no
authoritative source is available. A stale legacy cache can no longer produce
filesystem errors followed by a false pass. See the
[4.4.2 release notes](CHANGELOG.md).

**Accurate cross-client project recovery (July 2026).** Active-project
activation and SessionStart now share one parser that selects pending,
multiline project actions. See the [4.4.1 release notes](CHANGELOG.md).

**Parallel Claude Code and Codex sessions without shared-state collisions
(July 2026).** `synthesis-project-management` **v1.6.0** registers the machine,
project, heartbeat, isolated worktree/branch, source claims, and context role
for every root session. Different projects can proceed independently.
Same-project sessions use one canonical context owner plus non-overlapping
contributors with session-specific reconciliation artifacts. The helper
refuses shared worktrees, branches, claims, and context ownership. See the
[4.4.0 release notes](CHANGELOG.md).

**First-class Codex interfaces and agent-neutral automation (July 2026).**
Every public skill now carries a Codex interface with an explicit invocation
prompt. Day-end automation installs under stable `~/.synthesis/` ownership and
can launch Codex or Claude Code from one configuration, while the
correspondence safety doctor validates both clients independently. Source
conformance rejects client-bound runtime paths before they ship. See the
[4.3.0 release notes](CHANGELOG.md).

**One knowledge-base contract across agents (July 2026).** New
`synthesis-kb-edit` reads `.agents/knowledge-base.yaml` for editable and
generated paths, topic routing, the one frontmatter schema, confidentiality
controls, Git host, and review policy. `synthesis-okf` v1.1.0 adds a
config-driven seven-point consistency checker, and
`synthesis-knowledge-capture` v1.1.0 hands validation and shipping to those
shared layers. A knowledge-base edit can now move between Claude Code and Codex
without tool-owned workflow copies or date-field drift. See the
[4.2.0 release notes](CHANGELOG.md).

**A skip is not a pass (July 2026).** `synthesis-implementation-integrity` **v1.1.0** adds a Test Honesty check for a specific reading error: "X passed, Y skipped, 0 failed" gets read as "tests pass," but a skip is an absence of information, not a green light. The new step asks whether the skipped set could plausibly contain the one test that validates the exact property a decision depends on — most load-bearing for security, data-integrity, and irreversibility claims, where a skip in that territory is never neutral. See the [3.17.0 release notes](CHANGELOG.md).

**Multi-agent dispatch hygiene for project management (July 2026).** `synthesis-project-management` **v1.2.0** adds a "Parallel Sub-Agent Dispatch" section covering two risks specific to concurrent writers on one project: git-index collisions (a bare `git commit` after `git add <your files>` commits everything currently staged, not just what you added, so checking `git status --short` / `git diff --cached --name-only` first has to be a mechanical prefix, not a judgment call) and tracking-doc aggregation (sub-agents that each correctly leave siblings' work alone also mean no single agent sees the combined result, so the orchestrator reconciles all reports before updating the shared CONTEXT.md/index.yaml). Project Discovery also gains a scope re-verification step: before dispatching work against a paused project's stated "N items remaining," re-derive that count from live disk/repo state — the claim goes stale the moment anything else touches the same corpus, even a workstream unaware the paused project exists. See the [3.16.0 release notes](CHANGELOG.md).

**Google's Open Knowledge Format, validated and converted (July 2026).** New skill `synthesis-okf` **v1.0.0** fills the one gap Google's own OKF repo leaves open: a conformance validator and an idempotent frontmatter converter for OKF v0.1 (announced 2026-06-12 by Google Cloud's Sam McVeety and Amir Hormati). `okf_validate.py` checks the spec's three hard rules plus soft-guidance warnings and link-checking; `okf_convert.py` backfills frontmatter onto an existing markdown corpus without ever overwriting what's already there. Proven across several real conversions, from a small public reference repo up to a 72-doc personal knowledge base. See the [3.15.0 release notes](CHANGELOG.md).

**Day-end that survives tired evenings (July 2026).** `synthesis-daily-rituals` **v2.16.0** provides full and Quick Close modes, owed-weekly loose-ends review, explicit `Decays:` dates, and a state-aware notification. Its launcher and nudge live under `~/.synthesis/day-end/`, independent of client skill caches, and the launcher can open Codex or Claude Code. See the [4.3.0 release notes](CHANGELOG.md).

**Autonomous execution as a mode (July 2026).** New skill `synthesis-autopilot` **v1.0.0** encodes the delegation contract users otherwise retype per task: one explicit phrase ("take care of this for me," "autopilot this," "handle this end to end") engages a mode that sequences the existing stack — thinking framework for decisions, plan file + context lifecycle + checkpoint for compaction survival, anti-shortcuts for quality, implementation integrity before "done." Strict trigger discipline (explicit delegation only — ambiguity resolves to not engaging), batched user-only questions at checkpoints instead of blocking, and an explicit rule that standing gates survive autonomy: delegating a task never delegates authority the user has reserved. See the [3.10.0 release notes](CHANGELOG.md).

**Agent attribution for multi-agent projects (July 2026).** When Claude Code, Codex, Cursor, or subagents contribute to the same project, git history alone cannot tell you which agent did what: different tools commonly commit under the same human author identity. `synthesis-context-lifecycle` **v1.3.0** defines the convention — one compact line per contributing agent at the end of a session-log entry, recording agent, model, effort, scope, verification performed, and a durable ref. Unknown values stay the literal word `unknown` (never inferred from git trailers, which are authored claims rather than verified facts), and secrets never go in attribution fields. `synthesis-project-management` **v1.1.0** adds the convention to its Session End and Cross-Agent Handoff protocols, so a receiving agent knows who did what, with what verification. See the [3.8.0 release notes](CHANGELOG.md).

**Slop detection is now a free hosted tool.** [Slopcheck](https://tools.synthesiswriting.org/slopcheck/) at `tools.synthesiswriting.org/slopcheck/` runs the upgraded `synthesis-content-quality` and `synthesis-fact-checking` skills as a web app, with zero data collection and no signup. Same engine that ships with these skills, available without installing anything.

**Two major skill upgrades shipped in May 2026.** `synthesis-content-quality` reached **v4.0** with model-family fingerprinting across eight LLM families (Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen), a substance-and-depth section grounded in the Frankfurt-Pennycook-Hicks-Humphries-Slater framework, the compounding-archive principle that retains patterns across the LLM era, and per-family two-axis calibration with an ESL safe-harbor. `synthesis-fact-checking` reached **v2.0** with nine new protocol sections covering nested attribution, paraphrase drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, and tool-specific hallucination patterns by LLM family. See [CHANGELOG.md](CHANGELOG.md) for the full release history.

## Install

### Complete synthesis work system

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh
```

This is the primary install path for a new machine. It resolves one immutable
release, verifies its tag, commit, Git tree, manifests, and content digest,
then installs the stable `synthesis` command. Guided setup converges skills,
SessionStart context, gates, a Git-backed personal knowledge workspace, one
tracked instruction source for both clients, runtime engines, coordination,
conformance tools, policy, and lifecycle state.

Useful lifecycle commands after setup:

```bash
synthesis status
synthesis doctor
synthesis update
synthesis repair
synthesis enroll --org-repo URL
synthesis workspace ensure --name my-workspace
synthesis uninstall --purge
```

Stable is the default. Use `--channel edge` to follow `main`, or `--pin X.Y.Z`
for an exact release. New users can include an organization in full setup;
existing users use `synthesis enroll` without reinitializing personal layers.
Organization enrollment uses `--org-repo URL` or a
credential-free, time-bounded `--invite FILE`; organization repositories carry
declarative data and one tracked instruction source, never installer code.
Users who need private context at the organization workspace root can declare a
separate committed source with `--personal-instruction-source PATH`. That local
declaration is not written to the organization repository and update and repair
continue to enforce it. Existing root instruction files are preserved unless
the user explicitly selects verified archive-first adoption.

Updates are explicit. Make an update the initiating task's last action, restart
the selected clients, and verify a fresh lifecycle receipt before treating the
new release as live-loaded.

### Skills-only alternative

The same audited bootstrap can install only the portable skill and lifecycle
layers:

```bash
curl -fsSL https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh | sh -s -- setup --profile skills-only
```

Native plugin commands are the client-specific alternative when you only want
the skill catalog:


```bash
# Codex / ChatGPT desktop
codex plugin marketplace add synthesisengineering/synthesis-skills --ref stable
codex plugin add synthesis-skills@synthesis-engineering

# Claude Code
claude plugin marketplace add synthesisengineering/synthesis-skills@stable
claude plugin install synthesis-skills@synthesis-engineering
```

| Client surface | Support |
|---|---|
| Claude Code | First-class native plugin |
| ChatGPT Codex desktop | First-class native plugin |
| Codex CLI | First-class native plugin |
| Codex IDE extension | Explicitly unsupported: the IDE does not load plugins, and installing duplicate public user-skill copies would collide with desktop/CLI |
| Generic chat-only products | Unsupported for filesystem-backed execution; published prompts or copied text are not runtime parity |

`install.sh` remains a compatibility entry point for explicit direct-copy
targets. New users should use `onboard.sh`; it is the only bootstrap that binds
release identity, transactional state, doctor behavior, and both-client
lifecycle verification in one flow.

## Durable Project Memory

The project-management skills use a three-tier memory structure:

- `CONTEXT.md` for current working state
- `REFERENCE.md` for stable project facts
- `sessions/` for historical session archives

That structure keeps project memory in the repo, not inside one assistant's chat transcript or tool-native memory. A project can move between Claude Code and Codex, and between synced workstations, because every agent reloads the same durable project files.

When multiple agents work on one project, the session log also records provenance: one attribution line per contributing agent, capturing agent, model, effort, scope, verification performed, and a durable reference. Git authorship cannot make that distinction on its own, because different tools commonly commit under the same human identity.

## Available Skills

All skills are prefixed with `synthesis-` to prevent namespace collisions with skills from other repositories.

### Engineering
| Skill | Description |
|-------|-------------|
| `synthesis-codebase-review` | Enterprise-scale codebase audit with tiered review system |
| `synthesis-code-audit` | 10-dimension quality scan of code diffs with scored PASS/WARNING/FAIL verdicts |
| `synthesis-pr-review` | Delta review methodology with security scanning and AI-analysis verification |
| `synthesis-review-triage` | PR queue prioritization: scoring, author-response detection, and review routing |
| `synthesis-bitbucket` | Bitbucket Cloud through the open-source bkt CLI: PR lifecycle, repo and branch reads, auth setup, gh-to-bkt command map |
| `synthesis-code-integration` | Adopt-and-adapt pattern for integrating multi-contributor code with cherry-pick safety |
| `synthesis-code-planning` | Structured multi-approach evaluation before coding |
| `synthesis-preplan` | Architecture-decision pre-planning: locks design choices via a Q&A loop, then hands off to a commit-by-commit plan |
| `synthesis-preflight` | Pre-merge quality gate: tests, types, audit, commit hygiene, go/no-go verdict |
| `synthesis-implementation-integrity` | Adversarial self-review: verify implementations are genuinely complete before shipping |

### Content Creation
| Skill | Description |
|-------|-------------|
| `synthesis-reader-briefing` | Pre-writing reader briefing: catches insider context collapse before internal source material becomes a public draft |
| `synthesis-article-writing` | Two-phase workflow: research/validation then strategic writing |
| `synthesis-content-distribution` | Strategic content sharing and distribution across platforms with quick-start templates |
| `synthesis-link-research` | Find authoritative links for people, organizations, and entities |

### Content Enhancement
| Skill | Description |
|-------|-------------|
| `synthesis-content-quality` | v4.0 slop-detection methodology: model-family fingerprinting (8 families), substance-and-depth tests, two-axis calibration, compounding archive |
| `synthesis-fact-checking` | v2.0 fact-checking with 9 new protocols: nested attribution, composite quotes, paraphrase drift, citation laundering, AI-synthetic sources, tool-specific hallucination signatures |
| `synthesis-writing-pitfalls` | Human-authored bad-writing patterns: cringe, throat-clearing, caveat overload, cliché reliance, stilted formality |
| `synthesis-writing-craft` | Positive principles from the writing-craft tradition: sentence-level craft, pacing, voice, structure, revision |
| `synthesis-article-refresh` | Refresh old blog posts while maintaining temporal integrity |

### Communication
| Skill | Description |
|-------|-------------|
| `synthesis-agent-correspondence` | How AI agents compose and send correspondence on a human's behalf — the three-lane authorship model (my words / my words via my agent / my agent under my direction), a persona-registry schema with binding archetypes, channel disclosure facts, and the compose/send gates |
| `synthesis-message-guard` | Fail-closed pre-send hook: a deterministic register scan plus a message-bound grounding ledger gate every send and draft |
| `synthesis-concise-messaging` | High-Five Habit — condense messages to 5 sentences or less |
| `synthesis-executive-communication` | Translate technical work for non-technical executives — the every-noun test, the six-category kill-list, and upward-report structure for CTOs and product/engineering leaders |
| `synthesis-absence-coordination` | Coordinate an absence as a handoff: notification order, coverage and reachability, personal-continuity tier, return sweep |

### Project Management
| Skill | Description |
|-------|-------------|
| `synthesis-autopilot` | Autonomous-execution mode for explicitly delegated work: plan-file protocol, batched decisions, standing gates preserved |
| `synthesis-agent-conformance` | Cross-agent control plane: native plugin/runtime checks, instruction migration, lifecycle-hook health, and durable handoff verification |
| `synthesis-context-lifecycle` | Three-tier context architecture for managing AI working memory, with agent attribution for multi-agent provenance and repo families as per-engagement deletion units |
| `synthesis-checkpoint` | Mid-session refresh and drift recovery: verified date, project state from disk, git history, concurrent-session claims |
| `synthesis-project-management` | Lightweight PM system for human-agent collaboration, with cross-agent handoff, agent attribution, and parallel sub-agent dispatch protocols |
| `synthesis-project-resume` | Start or resume any project in any harness with full verified context: session classification, resumption brief, cross-machine surfacing |
| `synthesis-daily-rituals` | Day-start and day-end checklists with dependency-ordered rituals |
| `synthesis-catchup-ledger` | Reconcile missed and incomplete commitments after a gap in the ritual cadence into a dated catch-up ledger |
| `synthesis-chief-of-staff` | Chief-of-staff duty: meeting triage, calendar-aware scheduling, look-ahead reviews, overcommitment checks, tracked holds |
| `synthesis-quick-answers` | Low-cost, read-mostly lookup companion for ad hoc questions — keeps focused project sessions from absorbing quick lookups, with question-routing, strict grounding, and a self-building FAQ log |

### Knowledge Bases

| Skill | Description |
|-------|-------------|
| `synthesis-kb-edit` | Config-driven plain-language editing, validation, branching, review, and synchronization |
| `synthesis-knowledge-capture` | Reconcile durable session facts into the correct knowledge base with provenance |
| `synthesis-okf` | Validate OKF conformance, metadata consistency, taxonomy use, and convert existing bundles |

### Synthesis Engineering
| Skill | Description |
|-------|-------------|
| `synthesis-anti-shortcuts` | Deterministic enforcement of anti-shortcut discipline: costume-vocabulary catalog, constraint-first protocol, sub-agent hygiene, case studies |
| `synthesis-grounding-discipline` | Evidence and provenance catalog, the truth-side companion to anti-shortcuts: anti-confabulation, quote provenance, cache-vs-truth, absence proof, safe writes and deletions |
| `synthesis-content-framing` | Content framing with topic, sophistication, and engagement gates |
| `synthesis-disclosure-policy` | Two-category disclosure governance: published-precedent facts vs unapproved disclosures, with a precedent ledger, surface classes, and five decision tests |

### Reasoning & Templates
| Skill | Description |
|-------|-------------|
| `synthesis-thinking-framework` | Five-mode thinking methodology: first principles, systems, complexity, analogical, and design thinking |
| `synthesis-voice-profiler` | Generate a structured writing voice profile from samples for agent instruction files |
| `synthesis-tree-of-thought` | Multi-expert collaborative reasoning technique |
| `synthesis-llm-setup` | Configure Claude Projects, ChatGPT GPTs, and Gemini Gems |
| `synthesis-model-tiers` | Cross-provider model-tier convention: three role labels resolved to current model IDs, so nothing hardcodes a model name |
| `synthesis-creative-writer` | Creative writer persona template |
| `synthesis-technical-advisor` | Technical advisor persona template |

### DevOps & Sync
| Skill | Description |
|-------|-------------|
| `synthesis-git-hooks` | YAML-driven pre-commit policy: auto-classifies each repo by push remotes (personal vs strict), enforces tiered patterns for credentials and exposure-sensitive content |
| `synthesis-inbox-cleanup` | Manifest-driven email cleanup across iCloud / generic IMAP (Python), Microsoft 365 / outlook.com (Mail.app AppleScript), and Gmail (workspace-mcp API + native server-side filters). Public engine + private rules. Ships with prompt-injection defenses and adversarial test fixtures for any LLM-augmented path. macOS. |
| `synthesis-mac-sync` | Multi-Mac config sync via iCloud with git repo sync and machine inventory |
| `synthesis-meeting-prep` | Chief-of-staff meeting prep and debrief: 64-factor packs, reader profiles, capture half, prep linter |
| `synthesis-meeting-transcripts` | Fetch transcripts and verify primary-source eligibility for attribution |
| `synthesis-local-model-runtime` | Privacy-safe hardware profiling, Ollama and LM Studio managed adapters, direct-runtime discovery, catalog-driven fit, dry-run-first installation and updates, per-machine mapping, exact resolution, and bounded Ollama benchmarks |
| `synthesis-repo-guard` | Workspace sync guard: detect unsynced repos, confidentiality-safe alerts, local receipts, batch publication, and exact-session remote handoff |
| `synthesis-slack-sync` | Slack channel sync protocol: read channels, threads, DMs to local transcripts, with transcripts-first verification and bounded reads for absence claims |
| `synthesis-skills-manager` | Agent-native skill installer: drift detection, synthesis merge, provenance tracking |
| `synthesis-onboarding` | One-command installer and doctor for the ecosystem: plugin install, knowledge-base scaffold, org manifest, idempotent re-runs |
| `synthesis-skill-router` | Route a request to the narrowest matching skill while keeping specialist metadata out of a bounded prompt |

### Background Instructions
| Skill | Description |
|-------|-------------|
| `synthesis-clean-text` | Produce text without AI watermarking patterns |
| `synthesis-response-merger` | Combine multiple LLM responses into one unified document |

## How Skills Work

Skills use progressive disclosure:

1. **Tier 1** (always loaded): name + description (~50 tokens) — matches your requests
2. **Tier 2** (on activation): SKILL.md body — the actual instructions
3. **Tier 3** (on demand): reference files for detailed material

The plugin layout is:

```text
.codex-plugin/plugin.json
.claude-plugin/plugin.json
hooks/hooks.json
skills/<skill-name>/SKILL.md
```

When you ask your AI assistant to do something that matches a skill's description, it loads automatically. Skills that involve writing include defaults that work standalone. If you have personal preferences in agent instruction files such as `CLAUDE.md` or `AGENTS.md`, those override the defaults.

## Related

Many of these skills are practical artifacts of [synthesis engineering](https://synthesisengineering.org), including [synthesis coding](https://synthesiscoding.org), [synthesis writing](https://synthesiswriting.org), and [synthesis project management](https://synthesisengineering.org/articles/ai-native-project-management/).

## Licensing

- **[CC0 1.0](LICENSE-CC0)** — methodology and content skills (no attribution required)
- **[Apache 2.0](LICENSE-APACHE)** — skills with executable scripts

## Learn More

Read the launch article: [Synthesis Skills: Install Methodology Into Your AI Workflow](https://synthesiscoding.org/articles/synthesis-skills-install-methodology-into-your-ai-workflow/)

## Part of the Synthesis Engineering Ecosystem

- **[Synthesis coding](https://synthesiscoding.org)** — AI-assisted software development
- **[Synthesis engineering](https://synthesisengineering.org)** — broader human-AI collaboration methodology
- **[Agent Skills standard](https://agentskills.io)** — the open format these skills use

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Support posture: [SUPPORT.md](SUPPORT.md).

## Author

[Rajiv Pant](https://rajiv.com) — technology executive, AI practitioner, and creator of synthesis coding.
