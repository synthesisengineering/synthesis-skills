# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

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
npx skills add rajivpant/synthesis-skills --global --all --copy
```
