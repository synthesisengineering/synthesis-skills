# Coverage map: knowledge capture 1.2.0 to 2.0.0

Every part of the 1.2.0 SKILL.md and where it lives now. Nothing was removed, and no line needed rewording, so the coverage check finds every old line verbatim.

| 1.2.0 section | Now |
|---|---|
| Frontmatter description | Shortened to under 300 characters; keeps OKF, deduplication, confidentiality routing, conflict reconciliation, provenance, shipping through synthesis-kb-edit, and the triggers (session end, capture or update knowledge, corrected facts about people, organizations, products, decisions). "Merge facts into ai-knowledge", "validation" and "strategy" from the old trigger list are covered by "capture or update knowledge" and the workflow |
| Frontmatter `depends_on` (YAML list), `author`, `source_repo`, `source_type`, `license` | Kept in the same form (the modular installer and the source checks read them); version bumped to 2.0.0; `format: v5` added |
| Title | SKILL.md (verbatim) |
| Version 1.2.0 and 1.1.0 notes | references/background.md, "Release notes" (verbatim), with a 2.0.0 note added and a one-line pointer saying where the 1.1.0 opening paragraph went |
| Opening paragraph ("A fact learned in a session...") | SKILL.md (verbatim), as the purpose paragraph |
| Why it exists | references/background.md (verbatim) |
| The configuration contract | references/configuration.md (verbatim); binding rule 5 distills the stop conditions |
| The capture workflow | SKILL.md (verbatim) |
| Merge discipline — the four hard rules | references/merge-rules.md (verbatim); binding rules 1 to 4 distill them in the same order |
| Confidentiality routing | references/merge-rules.md (verbatim); binding rules 6 and 7 |
| Reconcile, never blind-flip | references/merge-rules.md (verbatim); binding rule 3 |
| Provenance | references/merge-rules.md (verbatim); binding rules 4 and 8 |
| Tools (`kb_scan.py` commands) | SKILL.md (verbatim; every command and flag unchanged) |
| Integration | references/shipping-and-integration.md (verbatim); binding rule 9 |
| Commit hygiene | references/shipping-and-integration.md (verbatim); binding rule 9 |
| Related | references/shipping-and-integration.md (verbatim) |

## Scripts and config

`scripts/kb_scan.py` and `config.example.json` are unchanged. This skill has no tests of its own; no test elsewhere reads text from its SKILL.md.

**2026-10-06.** `kb_scan.py` reads frontmatter through the plugin's YAML reader (`synthesis/yamlish.py`) instead of its own line-by-line scalar parser, which printed escaped quotes as `\"` and cut a title continued on a second line. On every knowledge base on the author's Mac the `--list` and `--stale` output is otherwise unchanged; a block the reader cannot read is reported on stderr and counts as undated. Its first tests are `tests/test_kb_scan.py`.

## The 1.2.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-knowledge-capture
description: Capture durable session facts in an OKF knowledge base with corpus-wide deduplication, confidentiality routing, conflict reconciliation, provenance, validation, and repository-aware shipping through synthesis-kb-edit. Use at session end, when asked to capture or update knowledge, merge facts into ai-knowledge, or preserve corrected facts about people, organizations, products, decisions, or strategy.
license: CC0-1.0
depends_on:
  - synthesis-okf
  - synthesis-kb-edit
metadata:
  author: Rajiv Pant
  version: "1.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
