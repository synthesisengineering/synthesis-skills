# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

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
