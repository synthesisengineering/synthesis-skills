# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

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
