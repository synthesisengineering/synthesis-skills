# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

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
