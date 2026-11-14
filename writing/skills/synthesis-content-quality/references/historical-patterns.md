# Historical Patterns Reference

This file is split by section so that each file fits one read. The opening sections stay here; the rest is in the parts below, in order.

Contents:
- In this file: Preface: the compounding-archive principle.
- Part 1, [historical-patterns-1-retained-v3.md](historical-patterns-1-retained-v3.md): Section 1: Patterns retained from v3.1.0 with Historical or Deprecated status (A1-GPT-007, A1-GPT-006, A1-GPT-018, A1-GPT-021, A1-GEMINI-019, A1-CLAUDE-006)
- Part 2, [historical-patterns-2-net-new-and-forensics.md](historical-patterns-2-net-new-and-forensics.md): Section 2: Net-new historical entries (A1-BARD-001, A1-LLAMA-HISTORICAL-001, A1-GROK-HISTORICAL-001, A1-DEEPSEEK-HISTORICAL-001, A1-MISTRAL-HISTORICAL-001, A1-QWEN-HISTORICAL-001, A1-GPT-HISTORICAL-001); Section 3: How to use historical patterns in forensic analysis of older published content: Step 1: Establish the artifact's era; Step 2: Select era-appropriate patterns; Step 3: Weight by base rate at the artifact's era; Step 4: Distinguish direct AI generation from quoted or parodied patterns; Step 5: Combine era-appropriate signals; Step 6: Document the era-tagged forensic conclusion; Step 7: Avoid era confusion; Section 4: Cross-references and next steps

> **Compounding-archive companion file.** This is the long-tail catalog of patterns whose era of prevalence has passed for current frontier models but remains diagnostic for forensic analysis of older AI-generated content. The patterns are retained (not deleted) and tagged with their era of prevalence, base rates by year, and the dates during which each is a reliable signal.

---

## Preface: the compounding-archive principle

The synthesis-content-quality catalog grows over time. Some patterns that were canonical AI tells in 2023 are now near-extinct in current frontier models because the labs that built those models trained the patterns out. The temptation, when a pattern fades, is to delete it from the catalog so the catalog stays lean and current.

This catalog does not delete. It retires.

A 2026 newsroom editor reviewing a 2023 article for AI provenance needs the 2023 catalog, not the 2026 one. A media-history researcher studying the early ChatGPT era needs to read content with the era-appropriate lens. A litigator examining a 2024 deposition exhibit needs the patterns that were diagnostic in 2024, regardless of which patterns are diagnostic today. Deleting trained-out patterns from the catalog would erase the very tools those audiences need.

The catalog therefore operates on a compounding-archive principle: every pattern that ever earned a place stays in the catalog forever, with explicit era-of-prevalence metadata. Patterns move from `Active` (still prevalent in current frontier models) to `Declining` (still occurs but at much lower base rate) to `Historical` (largely trained out of post-X models but still useful for forensic analysis of content from that pattern's era) to `Deprecated` (effectively absent from current models, retained for archival use only). Patterns never move to `Deleted`.

This file collects every pattern currently at `Historical` or `Deprecated` status, plus net-new historical entries that fill audit-identified gaps in coverage of older model families. Each entry carries a "useful for analyzing content from" date range so an editor can map the pattern to the era of the artifact they are auditing.

The methodology in [SKILL.md](../SKILL.md) is the durable part. The active-pattern catalog in [detailed-criteria.md](detailed-criteria.md) and the model-family fingerprints in [model-family-fingerprints.md](model-family-fingerprints.md) are refreshed as model behavior shifts. This file is the depth dimension that makes the catalog work across the entire LLM era from 2020 to today, not only on the current crop.

---
