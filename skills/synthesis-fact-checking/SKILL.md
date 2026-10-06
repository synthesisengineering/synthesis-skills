---
name: synthesis-fact-checking
description: "Fact-check articles, posts, news and AI-synthesized content before publication: claims, quotes, studies, URLs and laundered citations. Use to fact-check, verify claims or sources, check accuracy, verify citations, validate references, or audit AI-summarized content."
license: "CC0-1.0"
depends_on: ["synthesis-content-quality"]
metadata:
  author: "Rajiv Pant"
  version: "3.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Fact-Check Process for Articles and AI-Synthesized Content

A repeatable process for verifying the factual accuracy of articles, blog posts, news and AI-synthesized content before publication. It is calibrated for recursive contamination: AI output now feeds the sources the next AI and the next researcher cite, so agreement among sources counts only when they are independent. [synthesis-content-quality](../synthesis-content-quality/SKILL.md) covers style and substance; this skill covers factual correctness.

## Binding rules

Rule numbers are the section numbers that other files cite as "SKILL.md section N" (section 2, 4a to 4g, sections 7 and 8). Contents names the file that holds each section in full.

1. **Extract every verifiable claim before verifying any:** numbers, studies, authors, dates, quotes, organizations, causal and comparative claims, URLs, DOIs, nested attributions. Claims that "sound right" are often the subtly wrong ones.
2. **Agreement counts only among graph-independent sources.** Sources that trace to one AI-generated upstream, or to the author's own doctrine, are single-sourced however many there are.
3. **Verify against the primary source.** Secondary and tertiary sources help you find it; AI output is what you check, never what you check against.
4. **Check the framing, not just the number.** The common errors are 4a to 4g: wrong framing, conflated findings, wrong specifics, wrong entity, misattribution, fabricated citation, superseded data.
5. **Apply the nine C1 protocols wherever their claim type appears:** nested attribution, paraphrase drift, composite quotes, position shifting, translation drift, URL rot, synthetic sources, citation laundering, per-family hallucination.
6. **When the producing model family is known, run its signature check first** (Claude: DOIs; GPT: URLs; Gemini: vague attribution), rather than every check on every piece.
7. **A quote is verified only when** it exists, its wording is exact, its speaker and context are right, and it is one continuous utterance traced to the original speaker; paraphrase never gains quotation marks. A misquote damages trust out of proportion.
8. **A study is verified only when** existence, paper number, every author, venue, method, findings and retraction status check out. An unfindable study's citation is removed; its claim is re-sourced, hedged or cut.
9. **A backdated article cites only sources that predate its date**, unless marked "Updated on", and its time-relative words are true as of that date.
10. **After any de-jargoning, anonymization or accessibility pass, re-verify every replaced term.** Accessible wording can stop being true.
11. **Log every claim checked** in a `review-log.md` beside the draft, with status, source, finding and correction.
12. **Nothing publishes until the pre-publish checklist passes.**
13. **Route each claim through the quick decision tree.** Opinion needs no check; a claim you cannot source is re-sourced or hedged if essential, removed if not.

## Contents

- [references/verification-steps.md](references/verification-steps.md): sections 1, 2, 3, 7, 8 and 13 in full: claim extraction, the confidence table and graph-independence check, the source hierarchy, the quote and study protocols, the decision tree. Read it when starting a fact-check.
- [references/error-patterns.md](references/error-patterns.md): sections 4 to 6: errors 4a to 4g with examples, summaries of the nine C1 protocols and of the family signatures. Read it when a claim looks wrong, to name the error and pick the deeper protocol.
- [references/temporal-and-translation.md](references/temporal-and-translation.md): sections 9 and 10. Read it when the article is backdated or has been de-jargoned, anonymized or simplified.
- [references/review-log-and-checklist.md](references/review-log-and-checklist.md): sections 11 and 12, the review-log template and pre-publish checklist. Read it when logging claims and before publishing.
- [detailed-protocols.md](references/detailed-protocols.md): All nine C1 protocol sections with full failure modes, worked examples, and detection procedures. An index to three parts; read the part with the protocol you are applying:
  - [references/detailed-protocols-quotes.md](references/detailed-protocols-quotes.md): C1-NESTED, PARAPH, COMPOSITE, POSSHIFT
  - [references/detailed-protocols-sources.md](references/detailed-protocols-sources.md): C1-TRANS, URLROT, SYNTH, LAUNDER
  - [references/detailed-protocols-model-families.md](references/detailed-protocols-model-families.md): C1-TOOLHALL, incident list
- [autopilot-research-quality.md](references/autopilot-research-quality.md): Decision-changing primary evidence, counterevidence and task-specific research acceptance. Read it when research must support a decision.
- [per-family-hallucination-signatures.md](references/per-family-hallucination-signatures.md): Detailed per-family signature catalog with empirical anchors. An index to two parts; read it for rule 6 in depth:
  - [references/per-family-signatures-claude-gpt-gemini.md](references/per-family-signatures-claude-gpt-gemini.md): why, caveats, anchors; Claude, GPT, Gemini
  - [references/per-family-signatures-llama-grok-deepseek-mistral-qwen.md](references/per-family-signatures-llama-grok-deepseek-mistral-qwen.md): Llama, Grok, DeepSeek, Mistral, Qwen
- [citation-laundering-detection.md](references/citation-laundering-detection.md): Graph-traversal protocol for detecting citation laundering chains. Read it when sources may share an upstream.
- [production-incident-archive.md](references/production-incident-archive.md): Documented 2024-2026 production incidents (Mostafavi, Goldberg Segalla, Chicago Sun-Times, Springer book, BBC/EBU, Topaz Lancet, and others) with detection lessons. Read it for precedent.
- [bibliography.md](references/bibliography.md): Consolidated bibliography with verification status. Read it before repeating a figure from this skill.
- [references/background.md](references/background.md): purpose, what v2.0 added, related skills. Read it once, or when choosing between this skill and a sibling.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 2.1.1 text now lives.
- Process Overview: below.

## Process Overview

1. Claim Extraction
2. Multi-Source Confidence Assessment (with graph independence per v2.0)
3. Verification by Source Hierarchy
4. Common Error Pattern Detection (4a through 4g, refreshed)
5. **Nine new protocol sections for v2.0 (C1)**
6. **Per-family hallucination signatures (v2.0)**
7. Quote Verification (with nested attribution per v2.0)
8. Study Verification
9. Temporal Verification (if backdated)
10. Translation-Pass Re-Verification
11. Documentation
12. Pre-Publish Checklist
