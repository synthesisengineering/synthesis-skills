# Model-Family Fingerprints (A1)

This file is split by section so that each file fits one read. The opening sections stay here; the rest is in the parts below, in order.

Contents:
- In this file: How to read this file: the per-pattern template, era status, zone tags, provenance flags, the two known corrections, the em-dash constraint and section organization.
- Part 1, [model-family-fingerprints-1-claude.md](model-family-fingerprints-1-claude.md): A1.1 Anthropic Claude family (A1-CLAUDE-001 to A1-CLAUDE-013, 13 entries)
- Part 2, [model-family-fingerprints-2-claude-continued.md](model-family-fingerprints-2-claude-continued.md): A1.1 Anthropic Claude family, continued (A1-CLAUDE-014 to A1-CLAUDE-028, 15 entries)
- Part 3, [model-family-fingerprints-3-gpt.md](model-family-fingerprints-3-gpt.md): A1.2 OpenAI GPT family (A1-GPT-001 to A1-GPT-020, 18 entries)
- Part 4, [model-family-fingerprints-4-gemini-llama.md](model-family-fingerprints-4-gemini-llama.md): A1.3 Google Gemini family (A1-GEMINI-001 to A1-GEMINI-013, 13 entries); A1.4 Meta Llama family (A1-LLAMA-001 to A1-LLAMA-010, 10 entries)
- Part 5, [model-family-fingerprints-5-grok-deepseek.md](model-family-fingerprints-5-grok-deepseek.md): A1.5 xAI Grok family (A1-GROK-001 to A1-GROK-010, 10 entries); A1.6 DeepSeek family (A1-DEEPSEEK-001 to A1-DEEPSEEK-010, 10 entries)
- Part 6, [model-family-fingerprints-6-mistral-qwen.md](model-family-fingerprints-6-mistral-qwen.md): A1.7 Mistral / Mixtral family (A1-MISTRAL-001 to A1-MISTRAL-009, 9 entries); A1.8 Qwen / Alibaba family (A1-QWEN-001 to A1-QWEN-010, 10 entries); Summary and Cross-References: Related references files; Detection mode selection (zone-conditional); Em-dash audit

Reference detail for synthesis-content-quality v4.0, Section A1. The eight model-family fingerprinting subsections below carry the full per-pattern entry that the SKILL.md cannot accommodate. Each entry follows a fixed 14-field template plus era status and a machine-actionable zone tag, drawn directly from the unified bucket A catalog produced 2026-05-18.

## How to read this file

### Per-pattern template (14 fields plus era and zone)

Every pattern entry below carries the same fixed structure. The order is stable so that the file reads as a relational table when scanned column-wise across patterns:

1. **ID.** `A1-<FAMILY>-NNN`. The family code is one of CLAUDE, GPT, GEMINI, LLAMA, GROK, DEEPSEEK, MISTRAL, QWEN. The numeric suffix is the order of appearance in the unified bucket A merge. Numbering is not contiguous in every family because the merge preserved original LLM contributors' numbering where possible; gaps are intentional.
2. **Name.** A short label for the pattern. Aim is recognition, not summary.
3. **Description.** What the pattern looks like in production output, with cross-references to sibling patterns in other families and to the v3.1.0 criterion (if the pattern maps to one).
4. **Concrete examples.** A minimum of three observable instances. Where multiple LLMs contributed independent examples, all examples are preserved with attribution so the reader can see the convergent vs. divergent observation.
5. **Location and register.** Where the pattern lives in a response (opener, body paragraph, closer, mid-paragraph insert) and which registers (analytical, advisory, conversational, technical, creative) it appears most densely in.
6. **Model attribution.** Which models in the family produce this pattern, ranked by confidence. Where other families produce a sibling-but-different version, the cross-references are listed inline.
7. **Time evolution.** When the pattern emerged, when it peaked, whether it is declining, and what model-version inflection points changed the rate.
8. **Sources.** A minimum of two citations. Provenance flags from the unified bucket A are preserved verbatim (e.g., `[cross-validated:perplexity+deepseek]`, `[verified-arxiv:2406.07016]`, `[correction]`).
9. **Signal strength tier.** HIGH, MEDIUM, or LOW, with cluster-amplification notes when present.
10. **Base rate (per-family).** Estimated proportion of unedited outputs in which the pattern occurs, with the specific register or prompt-class qualifications where they matter.
11. **Causal hypothesis (ranked).** Primary, secondary, and tertiary causal drivers, drawn from the B1 twelve-code causal taxonomy: training-data skew, RLHF reward shaping, alignment and safety tuning, tokenizer and architecture effects, system-prompt and product-wrapper artifacts, refusal-avoidance behavior, helpfulness optimization, length optimization, chain-of-thought scaffolding, multilingual training corpus effects, fine-tuning data choices, and feedback-loop contamination.
12. **Detection difficulty.** Easy (greppable exact phrase or character search), Medium (requires multi-sentence pattern analysis), Hard (requires aggregate statistical analysis or domain expertise).
13. **False positive risk.** The realistic rate at which the pattern surfaces in skilled human prose, with the specific human-author profiles most likely to trigger false positives (academic writers, ESL writers, journalists, technical writers, ghostwriters).
14. **Fix or remediation.** What a human editor or revision pass should do when the pattern is identified.

### Era status field

In addition to the 14 fields, every pattern carries an explicit **era status** with one of four values:

- **Active.** Pattern still appears at meaningful base rate in current frontier models as of 2026-05.
- **Declining.** Base rate has measurably dropped at a specific model-version inflection point but the pattern still appears.
- **Historical.** Pattern is largely trained out of post-X model versions but remains useful for forensic analysis of content produced during the pattern's era of prevalence.
- **Deprecated.** Pattern is effectively absent from current models; retained in the catalog per the compounding-archive principle for audit-trail completeness.

Historical and Deprecated patterns are not included in this file. They live in [historical-patterns.md](historical-patterns.md) with cross-references back to the active pattern IDs in this file where lineage exists.

### Zone tag field

Per the GATE 2 zone-conditional detection methodology added to v4.0, every pattern carries an explicit zone tag indicating where in the LLM response the pattern is most likely to appear. The five values are:

- **WRAPPER-OPENER.** Pattern occurs almost exclusively in the first one to three sentences of the response. Examples: "You're absolutely right!" sycophancy openers, "Certainly!" compliance markers, "Great question!" affirmations, "Let me walk you through this" framing.
- **WRAPPER-CLOSER.** Pattern occurs almost exclusively in the final one to three sentences of the response. Examples: "I hope this helps!", "Is there anything else?", "Feel free to reach out if you have more questions."
- **BODY-PERSISTENT.** Pattern occurs in the substantive content of the response, distributed across body paragraphs. Most stylistic fingerprints fall here. Examples: em-dash density, saturated vocabulary, balanced two-handed sentences, bulleted bolded lead-ins, uniform paragraph length.
- **HYBRID.** Pattern occurs in both wrapper and body at meaningful rates. Examples: "It is important to note" (appears both as preamble and mid-body insert), focal vocabulary like "delve" (appears both in openers and throughout the body).
- **MID-BODY-INSERT.** Pattern is specific to mid-paragraph or mid-section inserts that interrupt the body flow. Examples: safety-hedge inserts ("It's important to remember that this advice depends on your situation"), reasoning-trace "Wait" / "Actually" leakage in chain-of-thought outputs.

The detector operates in two modes per the design-considerations.md note:

- **Artifact mode (default for editorial use):** apply only `BODY-PERSISTENT`, `HYBRID`, and `MID-BODY-INSERT` patterns. Skip wrapper-only patterns. False-positive rate stays low when only the artifact body is audited, which is the operative case for editors reviewing AI-assisted submissions where the conversational wrapper has already been stripped.
- **Full-response mode (for forensic chat-log analysis):** apply all patterns including wrapper-only.

The zone tag in each entry is the load-bearing field for mode selection.

### Provenance flag scheme

Provenance flags appear verbatim from the unified bucket A merge. They are preserved here so that downstream verification passes can trace each claim to its origin LLM and to the underlying citations:

- `[claude-exec-2026-05-18]`: drawn from the Claude 2026-05-18 executive summary or index produced for this upgrade.
- `[opus-expansion]`: from the Opus-4.7 inlined expansion of the Claude index, derived from Opus-4.7 training knowledge.
- `[verified-arxiv:XXXX.XXXXX]`, `[verified-github:org/repo#N]`, `[verified-web:source-name]`: independently verified during the expansion pass.
- `[cross-validated:<llm>]`: pattern appears in the named LLM's inlined bucket A contribution.
- `[cross-validated:<llm1>+<llm2>+...]`: multi-LLM convergent agreement.
- `[correction]`: an inaccuracy in an upstream source was identified and corrected; the correction is documented inline.
- `[manus-ai]`, `[perplexity]`, `[grok]`, `[chatgpt]`, `[gemini]`, `[deepseek]`: source attribution for any single-LLM contribution.

### Two known corrections from the unified bucket A merge

Two corrections to upstream claims are preserved exactly as they appear in the unified bucket A. They are flagged at the patterns where they apply.

1. **arxiv 2503.01659 was originally framed as a Copyleaks publication** in the Claude exec summary. The paper itself does not list Copyleaks as the publishing organization. The paper reports 0.9988 precision for cross-family detection but is not a Copyleaks-authored work. The `[correction]` flag appears at A1-DEEPSEEK-016 where this citation is used.
2. **The "106 occurrences in two weeks" figure for A1-CLAUDE-003 is not in GitHub Issue anthropics/claude-code#3382** as originally claimed. The GitHub issue describes the pattern qualitatively ("a sizeable fraction of responses") but does not contain the 106 figure. The `[correction]` flag appears at A1-CLAUDE-003.

### Em-dash constraint

This file uses no em-dashes (the U+2014 character). Commas, parentheses, colons, and sentence breaks substitute throughout. The constraint is part of the substantive subject matter: criterion 11 and criterion 42 of the v3.1.0 catalog under upgrade flag em-dash density as a high-signal AI marker, so a reference document for the upgrade cannot itself produce the pattern it is cataloguing.

### Section organization

The eight family subsections appear below in the order Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen. The order reflects the depth of available evidence: Claude and GPT have the deepest stylometric literature and the largest production-deployment footprints; Gemini has substantial evidence; the remaining five families have thinner peer-reviewed coverage and rely more on practitioner observation.

Patterns within each family are numbered in the order they appear in the unified bucket A merge. Where two LLMs contributed independent observations of the same underlying pattern, the merged entry preserves both observations with attribution. Where one LLM made a unique observation, the contributor is named.

---
