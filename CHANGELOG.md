# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

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
