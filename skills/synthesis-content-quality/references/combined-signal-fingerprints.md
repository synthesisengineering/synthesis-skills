# Combined-Signal Fingerprints (B2)

This file is split by section so that each file fits one read. The opening sections stay here; the rest is in the parts below, in order.

Contents:
- In this file: Why combinations matter, how to read this document, and the top high-yield combos (read first).
- Part 1, [combined-signal-fingerprints-1-family-rlhf-wrapper.md](combined-signal-fingerprints-1-family-rlhf-wrapper.md): Family-identifying combos (28 combos: B2-COMBO 001, 003, 019, 021, 025, 026, 027, 028, 030, 032, 034, 043, 046, 047, 048, 049, 050, 051, 052, 055, 056, 057, 058, 060, 083, 084, 085, 086); RLHF and substance-evasion combos (14 combos: B2-COMBO 002, 008, 011, 018, 020, 029, 033, 053, 054, 061, 062, 070, 076, 081); Wrapper-zone combos (5 combos: B2-COMBO 014, 024, 037, 063, 082)
- Part 2, [combined-signal-fingerprints-2-content-sourcing-esl.md](combined-signal-fingerprints-2-content-sourcing-esl.md): Substantive-content combos (body-zone) (33 combos: B2-COMBO 004, 005, 006, 009, 013, 015, 016, 017, 022, 023, 035, 036, 038, 039, 040, 041, 042, 044, 045, 059, 064, 065, 066, 068, 069, 071, 072, 073, 074, 077, 078, 079, 080); Citation and sourcing combos (2 combos: B2-COMBO 007, 067); Markdown-leakage and wrapper-artifact combos (1 combo: B2-COMBO 012); Social-register combos (2 combos: B2-COMBO 031, 075); ESL safe-harbor (negative markers) (1 combo: B2-COMBO 010); Historical and era-tagged combos; GPT-5-stripped combos; Convergent clusters; Cross-references; Self-audit

Reference subfile for synthesis-content-quality v4.0. Companion to [`detailed-criteria.md`](detailed-criteria.md), [`model-family-fingerprints.md`](model-family-fingerprints.md), and the main [`SKILL.md`](../SKILL.md).

## Why combinations matter

The v3.1.0 catalog presents each criterion in isolation, with a coarse heuristic ("5+ medium-confidence indicators clustering equals very likely AI"). The v4.0 layer replaces that count rule with specific high-fidelity combinations where co-occurrence is a sharper signal than count.

Independent occurrence of any single medium-confidence marker is consistent with skilled human writing. The signature comes from co-occurrence of independent patterns emerging from different mechanisms (RLHF reward shaping, training-data skew, system-prompt artifacts, tokenizer effects) in the same response. Random co-occurrence of unrelated medium-signal markers is rare.

The research hypothesis is that specified combinations may outperform a raw count because they preserve which features co-occur. The inherited false-positive numbers were not produced from a preserved labeled corpus and are not validated performance claims.

> **August 2026 correction.** Preserve every combination below as a dated research and editorial pattern, including its constituent rules and fixes. Treat every `False-positive estimate`, `definitive`, `near-deterministic`, and provider-confidence statement as an inherited, unvalidated hypothesis unless a later record supplies the exact model, surface, prompt/task distribution, human comparison corpus, sample size, labeling procedure, and calculation. Do not infer authorship from these combinations. A literal tool marker may establish tool involvement; a verified nonexistent citation establishes a factual defect. Neither identifies the author of the surrounding prose.

## How to read this document

Each combo entry contains: ID and name; constituent criteria (referencing v3.1.0 numbers 1-42, A1 family IDs, or A2 substance IDs); why the combination is stronger; FP estimate; primary model attribution; concrete example; fix; zone applicability (`BODY-PERSISTENT`, `WRAPPER-OPENER`, `WRAPPER-CLOSER`, `HYBRID`, `MID-BODY-INSERT`); era status; contributor.

Zero em-dashes; alternatives used throughout: commas, parentheses, colons, sentence breaks.

## Top high-yield combos (read first)

Four combinations to recognize before the rest. They are high-yield editorial research hypotheses, not near-deterministic authorship signatures.

- **B2-COMBO-001 ChatGPT 4o tell.** Saturated vocabulary plus exhausted metaphors plus section-ending summary. Canonical GPT-4o body-zone fingerprint. FP below 1 percent at full co-occurrence. Active for GPT-4o, declining post-GPT-5.1.
- **B2-COMBO-003 Claude.ai default.** Em-dashes plus bulleted bolded lead-ins plus uniform paragraph length. Strongest single-family fingerprint in current frontier output. FP below 0.5 percent. Five independent contributors converge on this as the most reliable Claude signature.
- **B2-COMBO-007 Fake-expertise stack.** Vague attribution plus hallucinated citation plus generic insight. Complete fake-expertise package. FP below 1 percent when the citation can be verified absent. All families produce it; GPT and Claude at notable density.
- **B2-COMBO-010 ESL false-positive trap (NEGATIVE marker).** Uniform paragraph length plus restricted vocabulary range plus heavy transition words, in the absence of register-specific AI markers, is more likely non-native English human writing than AI. The detector should NOT flag this combination as AI when register-specific markers (focal-word cluster, em-dash density, system-prompt artifacts, chatbot reflex) are absent. The ESL safe-harbor (per Liang et al. arxiv 2304.02819) is a primary structural constraint on the methodology, not an exception or escape hatch. See section "ESL safe-harbor (negative markers)" below.

---
