# Calibration Tables

This file is split by section so that each file fits one read. The opening sections stay here; the rest is in the parts below, in order.

Contents:
- In this file: B3.1 Methodology: two-axis calibration, per-family and zone split, Empirical or Estimated labels, recency floor.
- Part 1, [calibration-tables-1-master-table.md](calibration-tables-1-master-table.md): B3.2 Master calibration table: A3 (refreshed v3.1.0 criteria): Claude + GPT split; A3 (refreshed): Gemini + Llama split; A3 (refreshed): Grok + DeepSeek split; A3 (refreshed): Mistral + Qwen split; A1 (model-family fingerprints): Claude family; A1: GPT family; A1: Gemini family; A1: Llama family; A1: Grok family; A1: DeepSeek family; A1: Mistral family; A1: Qwen family; A2 (substance and depth); A3-NEW (net-new criteria independent of A1 and A2)
- Part 2, [calibration-tables-2-framework-esl-recalibration.md](calibration-tables-2-framework-esl-recalibration.md): B3.3 Framework for calibrating new criteria: Reasoning-chain template for Estimated entries; B3.4 ESL safe-harbor (Liang et al. arxiv 2304.02819 verified): The mechanical safe-harbor rule; Why this matters editorially; Liang anchor measurements (from arxiv 2304.02819); B3.5 Quarterly re-calibration discipline: The empirical anchor; The discipline; Per-family calibration adjustments (ChatGPT contribution); B3.6 Zone-conditional notes: Patterns with meaningful BR-artifact-body vs. BR-full-response differential; Detector mode implications; Boundary detection between wrapper and body; Cross-file references

Companion to [SKILL.md](../SKILL.md). The per-pattern calibration data the skill's confidence-based evaluation depends on.

This file preserves the v4.0 calibration hypothesis set: signal-strength-when-present (SSWP) scores, base-rate estimates by model family, zone-conditional splits, the ESL safe-harbor rule, and the recalibration design. The inherited numerical tables were not generated from a preserved labeled corpus and are not operational detector performance. A citation beside a row may support a related phenomenon without supporting that row's probability or model-specific rate.

> **August 2026 correction.** SSWP is not `P(AI | pattern)`. A posterior probability requires a population prior and measured likelihoods for AI output and relevant human comparison classes. Read every SSWP and BR number below as a dated, unvalidated hypothesis unless the row identifies the exact model, surface, task distribution, sample size, collection date, comparator corpus, and calculation. Do not aggregate these values into an authorship probability, threshold an individual, or advertise false-positive performance from them. The pattern catalog and safe-harbor remain active; the unsupported calibration claims do not.

Recency floor: **2026-05**. Patterns from older models carry Era-status tags (Active, Declining, Historical, Deprecated). See [historical-patterns.md](historical-patterns.md) for full retired-pattern entries; see [bibliography.md](bibliography.md) for full source list.

---

## B3.1 Methodology

### Two-axis calibration

A single pattern observation does not justify a single confidence number. Calibration in this catalog is two-axis:

1. **Signal-strength-when-present (SSWP, legacy label).** An ordinal hypothesis about how salient a pattern may be in a bounded comparison. It is not a conditional probability and cannot ignore the population prior while remaining `P(AI | pattern)`. The inherited numerical bands are retained for research continuity, while the plain-language labels are non-probabilistic editorial tiers:

   | SSWP | Qualitative tier | Plain-English reading |
   |------|------------------|------------------------|
   | above 0.85 | "smoking gun" / very high / definitive | The marker is near-diagnostic on its own when present. |
   | 0.60 to 0.85 | strong / high | The marker is strong evidence but should be combined with at least one corroborating signal. |
   | 0.40 to 0.60 | moderate / medium | The marker contributes evidence but is not by itself sufficient. |
   | below 0.40 | ambient / low | The marker is observable but provides weak standalone evidence; it earns weight only in cluster. |

2. **Base rate in unedited AI output (BR, legacy estimates unless fully identified).** The intended quantity is the percentage of unedited outputs in a specified model/surface/task corpus that contain the pattern. A family name without that sampling frame is not a measured base rate. The inherited bands remain as hypotheses:

   | BR | Tier | Plain-English reading |
   |----|------|------------------------|
   | above 60% | Very common | The pattern is present in most unedited outputs. |
   | 30% to 60% | Common (also "Frequent") | The pattern is present in a substantial minority. |
   | 10% to 30% | Occasional | The pattern is present in a minority. |
   | below 10% | Rare | The pattern is uncommon. |

### Per-family resolution and zone-conditional split

Base rate is resolved by model family because per-family BR rankings can vary by 30+ points within a single model release. The base-rate column is further split by zone (per the design-considerations.md 2026-05-18 entry on zone-conditional detection):

- **BR-artifact-body** is the rate within the substantive content the user requested. This is what editorial reviewers actually see in submitted drafts.
- **BR-full-response** is the rate across the full LLM response including wrapper-opener (sycophancy, polite framings) and wrapper-closer (concierge tone, "Is there anything else?") zones.

For body-zone patterns the two values are equal. For wrapper-only patterns BR-artifact-body is near-zero and BR-full-response is high. The split matters because flagging "You're absolutely right!" sycophancy on a clean article body is a calibration failure that erodes editorial trust in the detector.

### Empirical or Estimated label

Every inherited entry carries one of two provenance labels. These labels classify the claimed source type; they do not by themselves validate the row's numerical value:

- **Empirical** means a published measurement is cited. The measurement must match the row's claimed variable, population, model, surface, and date before the number can be reused.
- **Estimated** means no matching measurement was preserved. Treat the number as a hypothesis, regardless of whether a reasoning chain is present.

### Recency floor and per-pattern era

The inherited tables used 2026-05 as their recency floor. They are therefore a historical snapshot, not current calibration for August 2026 model labels. Patterns from older models remain with explicit dating under the compounding-archive principle.

---
