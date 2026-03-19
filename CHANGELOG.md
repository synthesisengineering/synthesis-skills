# Changelog

All notable changes to Synthesis Skills are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version numbers follow [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-03-18

### Changed
- **All skills renamed with `synthesis-` prefix** for namespace protection. This prevents collisions with skills from other repositories that may use the same generic names.
- `multi-contributor-synthesis-coding` → `synthesis-multi-contributor-coding`
- `response-synthesis` → `synthesis-response-merging`

### Migration
If you installed v1.0.0, uninstall and reinstall:
```bash
./install.sh uninstall && ./install.sh install
# Or: npx skills remove synthesis-skills && npx skills add rajivpant/synthesis-skills --global --all --copy
```

## [1.0.0] - 2026-03-18

### Added

Initial release: 22 public Agent Skills.

**Engineering:** `synthesis-codebase-review`, `synthesis-pr-review`, `synthesis-multi-contributor-coding`, `synthesis-code-generation`

**Content Creation:** `synthesis-thought-leadership-writing`, `synthesis-content-promotion`, `synthesis-social-media-post`, `synthesis-blog-promotion`, `synthesis-hyperlink-research`

**Content Enhancement:** `synthesis-ai-content-quality`, `synthesis-fact-checking`, `synthesis-blog-revitalization`

**Communication:** `synthesis-message-condensation`

**Project Management:** `synthesis-context-lifecycle`, `synthesis-project-management`

**Synthesis Engineering:** `synthesis-content-framing`

**Reasoning & Templates:** `synthesis-tree-of-thought`, `synthesis-llm-project-setup`, `synthesis-creative-writer-setup`, `synthesis-technical-advisor-setup`

**Background Instructions:** `synthesis-anti-watermarking`, `synthesis-response-merging`

### Installation

```bash
npx skills add rajivpant/synthesis-skills --global --all --copy
```
