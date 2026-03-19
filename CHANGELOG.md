# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

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
