# Fact-checking: background

Why this skill exists, what version 2.0 added, and how it relates to sibling skills.

## Purpose

This skill provides a repeatable process for verifying factual accuracy of articles, blog posts, and news content before publication. v2.0 is specifically calibrated for the recursive-contamination problem: AI-generated text now constitutes a plurality of newly indexed English-language web pages (per Ahrefs measurement of newly indexed pages in April 2025), which means AI outputs become source material for the next generation of AI outputs and human research. Multi-source confidence requires graph independence, not raw count.

The companion skill, [synthesis-content-quality](../../synthesis-content-quality/SKILL.md), addresses stylistic and substantive quality. This skill addresses factual correctness.

## What v2.0 adds

- **Nine new protocol sections (C1)** for the structural gaps in v1.1.0: nested attribution, paraphrase boundary drift, composite quotes, position-shifting, source-translation drift, URL rot vs hallucination, AI-generated synthetic sources, citation laundering chains, tool-specific hallucination patterns. Full detail in [references/detailed-protocols.md](detailed-protocols.md).
- **Per-family hallucination signatures.** Claude over-produces plausible-seeming DOIs; GPT invents URLs on real domains; Gemini drifts to vague "studies show"; DeepSeek language-mixes under reasoning; Llama fabricates above approximately 32K context per RIKER benchmark; Grok fabricates X/Twitter quotes. Family-conditional detection is the bucket-C parallel to bucket-A's family-conditional stylistic detection. Full detail in [references/per-family-hallucination-signatures.md](per-family-hallucination-signatures.md).
- **Graph-independence revision to section 2** (Multi-Source Confidence Framework). Citation laundering chains collapse cross-source corroboration to a single AI-generated upstream. Confidence conditions on graph independence, not on raw count. Full detail in [references/citation-laundering-detection.md](citation-laundering-detection.md).
- **Section 4 refresh.** Updated examples from 2025-2026 production incidents: Mostafavi sanction ($10,000), Goldberg Segalla sanction ($59,500 total), Chicago Sun-Times summer reading list, Springer "Mastering ML" book retraction, BBC/EBU 45 percent significant-issues rate, Topaz et al. May 2026 Lancet letter (1 in 277 PubMed papers referencing fabricated paper, twelvefold rise from 2023), Damien Charlotin's database of 1,455+ sanctioned legal cases, Mata v. Avianca, Stanford RegLab Magesh measurement (17 to 33 percent legal-AI hallucination rate). Full incident archive in [references/production-incident-archive.md](production-incident-archive.md).
- **Section 4f demote.** Hallucinated citations as a single bucket is demoted. The failure mode splits into the C1-URLROT-001 / C1-SYNTH-001 / C1-LAUNDER-001 trio plus residual pure-fabrication.

The methodology in v1.1.0 (the tier system, the confidence-based evaluation process, the verification hierarchy) is preserved. v2.0 refreshes the catalog under the same methodology.

## Related Skills

- [`synthesis-content-quality`](../../synthesis-content-quality/SKILL.md) v4.0: Companion skill for stylistic and substantive quality. Family-conditional A1 detection feeds the per-family hallucination check (section 6) in this skill.
- [`synthesis-writing-pitfalls`](../../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns.
- [`synthesis-writing-craft`](../../synthesis-writing-craft/SKILL.md): Positive writing principles.
- [`synthesis-reader-briefing`](../../synthesis-reader-briefing/SKILL.md): Pre-writing audience analysis.
- [`synthesis-article-writing`](../../synthesis-article-writing/SKILL.md): End-to-end article workflow with quality gates.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft. The methodology is durable. The catalog refreshes as AI-generated content reshapes the source ecosystem. Newsroom fact-checkers, journalism integrity organizations, and academic citation auditors are the audience this skill serves.
