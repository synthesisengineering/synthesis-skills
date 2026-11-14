# Coverage map: fact-checking 2.1.1 to 3.0.0

Every part of the 2.1.1 SKILL.md and where it lives now. Nothing was removed. Section numbers 1 to 13 are unchanged, so every citation of "SKILL.md section N" (section 2, 4a to 4g, sections 6 to 8) still resolves: binding rule N in SKILL.md summarizes it, and Contents names the file holding the full text.

| 2.1.1 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters, keeping its trigger words: fact-check, verify claims, verify sources, check accuracy, citations, validate references, audit AI-summarized content |
| Frontmatter `depends_on: ["synthesis-content-quality"]` | Kept: the modular installer (synthesis-onboarding `modular.py`) refuses a skill without an explicit dependency list |
| Frontmatter `author`, `source_repo`, `source_type` | Kept: the `source.skill-contract` check in synthesis-agent-conformance (a required release check) fails a skill without them |
| Title | SKILL.md (verbatim) |
| Purpose | references/background.md (verbatim); a one-paragraph summary opens SKILL.md |
| What v2.0 adds | references/background.md (verbatim apart from link paths, below) |
| Process Overview | SKILL.md (verbatim) |
| 1. Claim Extraction | references/verification-steps.md (verbatim); binding rule 1 |
| 2. Multi-Source Confidence Framework, including the v2.1 circular-grounding note | references/verification-steps.md (verbatim apart from link paths); binding rule 2 |
| 3. Verification Hierarchy | references/verification-steps.md (verbatim apart from link paths); binding rule 3 |
| 4. Common Error Patterns, 4a to 4g, with the canonical incidents | references/error-patterns.md (verbatim apart from link paths); binding rule 4 |
| 5. Nine New Protocol Sections (C1) | references/error-patterns.md (verbatim apart from link paths); binding rule 5 |
| 6. Per-Family Hallucination Signatures | references/error-patterns.md (verbatim apart from link paths); binding rule 6 |
| 7. Quote Verification Protocol | references/verification-steps.md (verbatim); binding rule 7 |
| 8. Study Verification Protocol | references/verification-steps.md (verbatim); binding rule 8 |
| 9. Temporal Verification | references/temporal-and-translation.md (verbatim); binding rule 9 |
| 10. Translation-Pass Re-Verification, with the worked example | references/temporal-and-translation.md (verbatim); binding rule 10 |
| 11. Documentation Template | references/review-log-and-checklist.md (verbatim); binding rule 11 |
| 12. Pre-Publish Checklist | references/review-log-and-checklist.md (verbatim); binding rule 12 |
| 13. Quick Decision Tree | references/verification-steps.md (verbatim), placed after section 8 because it routes each claim during verification; binding rule 13 |
| Related Skills | references/background.md (verbatim apart from link paths) |
| References (list of reference files) | SKILL.md Contents: each entry keeps its 2.1.1 wording and adds a "read when" clause |
| Closing line ("Part of the synthesis writing craft...") | references/background.md (verbatim) |

## Existing reference files

All six keep their content; the only edit inside one is a single punctuation fix in bibliography.md, listed below. The added text uses no em-dashes, matching the files' em-dash audits. autopilot-research-quality.md is unchanged: the autopilot domain controller loads it by path and records its digest.

- **bibliography.md, production-incident-archive.md, citation-laundering-detection.md:** a short contents list was added near the top of each, because each runs past 150 lines.
- **detailed-protocols.md (139 KB) and per-family-hallucination-signatures.md (99 KB)** were too long to read in one pass, so each was split by its own top-level sections into parts of at most 60 KB, text verbatim, each part opening with a short contents list. The original file names are now short indexes that list the parts and say when to read each, so every existing link and every "C1-... in detailed-protocols.md" mention still lands on a page that names the right part.

| 2.1.1 section | Now |
|---|---|
| detailed-protocols.md: title and metadata block, How to use this file, Em-dash audit | detailed-protocols.md, now the index (verbatim) |
| detailed-protocols.md: C1-NESTED-001, C1-PARAPH-001, C1-COMPOSITE-001, C1-POSSHIFT-001 | detailed-protocols-quotes.md (verbatim) |
| detailed-protocols.md: C1-TRANS-001, C1-URLROT-001, C1-SYNTH-001, C1-LAUNDER-001 | detailed-protocols-sources.md (verbatim) |
| detailed-protocols.md: C1-TOOLHALL-001, Production-incident archive (cross-protocol reference) | detailed-protocols-model-families.md (verbatim) |
| per-family-hallucination-signatures.md: title, two opening paragraphs, Composing the checks across families, Em-dash audit | per-family-hallucination-signatures.md, now the index (verbatim) |
| per-family-hallucination-signatures.md: Why per-family hallucination detection matters, Caveats, Empirical anchors, Anthropic Claude, OpenAI GPT, Google Gemini | per-family-signatures-claude-gpt-gemini.md (verbatim) |
| per-family-hallucination-signatures.md: Meta Llama, xAI Grok, DeepSeek, Mistral, Qwen | per-family-signatures-llama-grok-deepseek-mistral-qwen.md (verbatim) |

Each index keeps its em-dash audit, and each part says that audit covers it. The two links that name C1-URLROT-001 (section 3's "For URLs" line and the section 4f C1-URLROT-001 bullet) now point at detailed-protocols-sources.md; links that mean all nine protocols, or the whole per-family catalog, still point at the indexes. Plain-text mentions such as "C1-TOOLHALL-001 in detailed-protocols.md" inside the existing references are not links and are unchanged; the index names the part for every C1 ID.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports 21 lines as not found verbatim: the 20 link-path lines from the 2.1.1 SKILL.md and the one bibliography.md line, all below. The two lines of the old References section are also listed below; the check finds them only because this map quotes them. None is lost:

- **20 lines with link paths adjusted.** Text moved from SKILL.md into references/ keeps its wording, but a relative link written for SKILL.md would break one directory down, so `references/x.md` targets became `x.md` and `../synthesis-x/SKILL.md` targets became `../../synthesis-x/SKILL.md`. The lines:
  - Purpose: "The companion skill, [synthesis-content-quality]..."
  - What v2.0 adds: the four bullets "Nine new protocol sections (C1)", "Per-family hallucination signatures", "Graph-independence revision to section 2" and "Section 4 refresh"; the fifth bullet ("Section 4f demote") has no link and is verbatim
  - Section 2: "For multi-source claims, build a citation graph..." and "A convergence case the graph must catch..."
  - Section 3: "**For URLs:** apply the C1-URLROT-001 protocol..." (its link now targets detailed-protocols-sources.md, where C1-URLROT-001 lives)
  - Section 4f: the C1-URLROT-001 bullet (link now targets detailed-protocols-sources.md), the C1-LAUNDER-001 bullet and "**Canonical 2025-2026 incidents**..."
  - Section 5: "The nine new protocol sections address structural gaps...", the C1-LAUNDER-001 and C1-TOOLHALL-001 bullets
  - Section 6: "Full per-family detail with detection workflows..."
  - Related Skills: all five bullets
- **"## References" heading:** renamed; the list is now SKILL.md's Contents.
- **`Detailed catalog content lives in the [references/](references/) subfolder:`** replaced by the Contents section, which lists every file in references/ with its 2.1.1 description.
- **bibliography.md, section 5, the line beginning "Paths below are relative to the author's workspace root":** its one em-dash became a colon. The file declares zero em-dashes in its opening notes; this line was the only exception.

## The 2.1.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-fact-checking
description: >
  Systematic fact-checking for articles, blog posts, news content, and AI-synthesized
  material. v2.0 adds nine new protocol sections covering nested attribution, paraphrase
  drift, composite quotes, position-shifting, source-translation drift, URL rot vs
  hallucination, AI-generated synthetic sources, citation laundering chains, and
  tool-specific hallucination patterns by LLM family. Use when asked to: fact-check,
  verify claims, verify sources, check accuracy, citation verification, review factual
  accuracy, validate references, audit AI-summarized content.
license: "CC0-1.0"
depends_on: ["synthesis-content-quality"]
metadata:
  author: "Rajiv Pant"
  version: "2.1.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
