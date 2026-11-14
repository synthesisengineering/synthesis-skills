# Detailed Protocols for synthesis-fact-checking v2.0

**Version:** 2.0.0
**Date:** 2026-05-18
**Status:** Reference companion to SKILL.md
**Provenance:** Unified merge of seven independent deep-research deliverables (Manus AI, Perplexity, Grok, ChatGPT, Gemini, DeepSeek) plus the original Claude bucket C index of 2026-05-18 and the Opus-4.7 expansion of 2026-05-18. Source document: `unified-03-bucket-c-fact-checking.md` Section C1.

This file is the index to the nine C1 protocols, which live in three parts so that each can be read in one pass. Open the part that holds the protocol you are applying:

- [detailed-protocols-quotes.md](detailed-protocols-quotes.md): C1-NESTED-001, C1-PARAPH-001, C1-COMPOSITE-001, C1-POSSHIFT-001. Read it when checking a quote, a paraphrase, or how a draft frames a source's position.
- [detailed-protocols-sources.md](detailed-protocols-sources.md): C1-TRANS-001, C1-URLROT-001, C1-SYNTH-001, C1-LAUNDER-001. Read it when a source is translated, a cited URL fails to resolve, a source may be AI-generated, or several sources may share one upstream.
- [detailed-protocols-model-families.md](detailed-protocols-model-families.md): C1-TOOLHALL-001 and the cross-protocol production-incident list. Read it when the model family that produced a draft is known, or when you need an incident as precedent.

Still in this file: how every protocol section is structured, and the em-dash audit for all three parts.

---

## How to use this file

This document is the long-form reference for the nine new C1 protocol sections introduced in synthesis-fact-checking v2.0. The user-facing SKILL.md summarizes each protocol; this file provides the full failure-mode catalog, the worked examples, the step-by-step verification procedures, the empirical grounding, the canonical cases drawn from production incidents, and the cross-references that bind the protocols to one another and to the v1.1.0 4a-4g patterns.

Each section follows a shared structure:

1. Pattern description
2. Why this happens (causal hypothesis)
3. Failure modes
4. Concrete examples in context (worked examples preserved from the unified bucket)
5. Detection protocol (how to catch it)
6. Step-by-step verification procedure
7. Sources
8. Signal strength, base rate, detection difficulty, false-positive risk
9. Remediation
10. Era status
11. Cross-references (to other C1 protocols and to v1.1.0 4a-4g patterns)

The framing is operational. Where the unified bucket recorded multiple LLM contributors offering different worked examples, all distinct examples are preserved with their per-source provenance. Where the unified bucket flagged a specific detail for synthesis verification (Mostafavi dollar amount, Goldberg Segalla figure, Lancet venue, RIKER threshold), the flag is preserved here. Where canonical cases were named in the Claude exec summary (Manchin stitch for COMPOSITE, Fetterman canonical for POSSHIFT, Le Monde canonical for TRANS, "Dr. Helena Marsh" and Springer book for SYNTH, "31 percent drop in problem-solving" for LAUNDER, Wegovy stress test for TOOLHALL), those cases are preserved with their full detail.

The audience is newsroom fact-checkers, journalism integrity organizations, academic citation auditors, and editors of AI-assisted publications. The protocols assume the reviewer has access to primary sources (or knows how to find them), some technical fluency with the open web (Wayback Machine, DOI resolution, archive snapshots), and the time to trace citation chains beyond one hop.

---

## Em-dash audit

This file is self-audited for em-dash use, per A3-SS-001 (em-dashes in articles) and A3-SR-005 (em-dashes in social posts) of the synthesis-content-quality v4.0 catalog. The audit applies to the U+2014 character only; en-dashes in numeric ranges (5-18 percent, 30 to 40 percent) and hyphens in compounds (URL-rot, multi-source) are not in scope.

Result: zero em-dashes in this file.
