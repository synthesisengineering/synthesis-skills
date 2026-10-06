# Per-Family Hallucination Signatures

Reference detail for synthesis-fact-checking v2.0, Section 9. This file is the bucket-C parallel to bucket-A's per-family stylistic fingerprinting in synthesis-content-quality's [model-family-fingerprints.md](../../synthesis-content-quality/references/model-family-fingerprints.md). Where the A1 catalog identifies WHO produced the text, this file identifies WHAT factual errors that producer is most likely to have made. The two layers compose: identify the family via A1 stylistic detection, then apply the family-specific factual checks below rather than running every check on every piece.

The eight families covered, in order of evidence depth: Anthropic Claude, OpenAI GPT, Google Gemini, Meta Llama, xAI Grok, DeepSeek, Mistral, Qwen. Each family section follows the same structure: signature description, empirical base rates with citations, three to five concrete examples, family-specific detection workflow, cross-reference to the A1 stylistic fingerprint that helps identify the family before applying the hallucination check, and cross-reference to C1-TOOLHALL-001 in detailed-protocols.md.

This file is the index to the per-family signatures, which live in two parts so that each can be read in one pass. Each family section holds its signature description, base rates, examples, detection workflow and cross-references:

- [per-family-signatures-claude-gpt-gemini.md](per-family-signatures-claude-gpt-gemini.md): why per-family detection matters, its caveats, the empirical anchors used throughout, then Anthropic Claude, OpenAI GPT and Google Gemini. Read it first, and for a draft from any of those three families.
- [per-family-signatures-llama-grok-deepseek-mistral-qwen.md](per-family-signatures-llama-grok-deepseek-mistral-qwen.md): Meta Llama, xAI Grok, DeepSeek, Mistral and Qwen. Read it for a draft from any of those families.

Still in this file: how to compose the checks across families, and the em-dash audit for both parts.

---

## Composing the checks across families

The eight per-family workflows above are designed to be applied sequentially, not in parallel, after A1 stylistic identification:

1. Identify the family via A1 stylistic detection. The strongest single signals: em-dash density (Claude), sycophantic opener (GPT), vague attribution stylistic pattern (Gemini), low-em-dash baseline with assertive declarative (Llama), Twitter-style structural defaults (Grok), CJK characters in reasoning content (DeepSeek), French-influence syntax with concise default (Mistral), CJK punctuation slips (Qwen).

2. Apply the family-specific hallucination workflow above. Each workflow runs the highest-yield check first: DOI audit for Claude, URL audit for GPT, vague-attribution audit for Gemini, long-context fabrication audit for Llama, tweet and Musk-source audit for Grok, language-mixing and reasoning-trace audit for DeepSeek, European-source audit for Mistral, Chinese-source audit for Qwen.

3. Fall back to universal verification per SKILL.md sections 4 and the C1 protocols for residual coverage. The family-specific workflow does not replace universal verification; it prioritizes which checks to run first.

4. Document the family identification and the checks applied in the fact-check review log. Per ChatGPT bucket-C contribution: v2.0 should require model version, wrapper, and tool state as metadata whenever a reviewer records a pattern or failure. The log should include: identified family (via A1), version if known, wrapper if known, tool state if known, and the family-specific checks applied.

5. When family cannot be identified or when multiple family signatures are present (which may indicate editorial blending or multi-model workflow), apply all relevant family workflows. Multi-family blending is increasingly common in production workflows where different models produce different sections of the same draft.

The methodology preserves v1.1.0: claim extraction, multi-source confidence framework, verification hierarchy, common error patterns 4a through 4g, quote verification protocol, study verification protocol, temporal verification, translation-pass re-verification. The family-conditional layer is a prioritization mechanism stacked on top of v1.1.0, not a replacement.

---

## Em-dash audit

This file uses no em-dashes (U+2014). Self-audited via character search before saving. Commas, parentheses, colons, and sentence breaks substitute throughout. The constraint is part of the substantive subject matter: A1-CLAUDE-004 (em-dash density) is a high-signal Claude stylistic marker, and a reference document for the upgrade cannot itself produce the pattern it is cataloguing.
