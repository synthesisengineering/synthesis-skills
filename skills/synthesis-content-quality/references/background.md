# Content quality: background

Why the catalog changes while the method stays, where this skill sits among its siblings, when to use it, its core philosophy, related skills, and the reference-file list as 4.2.0 had it. Moved verbatim from SKILL.md 4.2.0 apart from link paths. Read it once per session, or when choosing between this skill and a sibling.

Contents:
- The durable methodology and the compounding-archive principle.
- Where this skill fits in the writing-quality family; When to Use This Skill.
- Core Philosophy: slop, not AI, is the target; three kinds of AI-collaborated content; the companion caveats. (Its four-axis inference boundary is in [review-method.md](review-method.md).)
- Related Skills; References (the 4.2.0 list of reference files).

The methodology is durable. The catalog refreshes as model behavior shifts and as new patterns emerge in production output. v4.0 adds model-family fingerprinting across eight families, a substance and depth section grounded in the Frankfurt-Pennycook-Hicks-Humphries-Slater framework, a cross-cutting causal-and-calibration layer, and zone-conditional detection. The compounding-archive principle means patterns are never deleted: when newer model versions train a pattern out, the catalog tags it Historical and retains it for forensic analysis of older published content.

## Where this skill fits in the writing-quality family

This skill catches AI-generation patterns and substance failures specifically. Three sibling skills handle adjacent concerns:

- **`synthesis-content-quality`** (this skill, v4.0): AI/LLM-generation patterns, substance and depth, calibration. Refreshes with new model releases.
- [`synthesis-writing-pitfalls`](../../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns (cringe, throat-clearing, caveat overload, cliché reliance). Stable across decades.
- [`synthesis-writing-craft`](../../synthesis-writing-craft/SKILL.md): Positive principles from the writing-craft tradition.

Use all three together for a comprehensive quality pass. Use this one alone when the focus is specifically slop in AI-collaborated or AI-generated content.

## When to Use This Skill

- Reviewing AI-assisted drafts before publication.
- Editing content that may contain unrevised AI output.
- Building or calibrating AI content detection tools.
- Training writers or editors on content quality standards.
- Performing editorial review of submitted content.
- Forensic analysis of older published content for AI authorship signals (use Historical and Deprecated era patterns).

## Core Philosophy

Slop is the enemy, not just AI. The tool catches AI-generation patterns specifically (by model family, with empirical anchors), and also catches slop in human-written content. AI-assisted content creation is legitimate and valuable. The distinction that matters is not "did AI help write this" but "is this worth publishing." Both questions get answered, on separate axes.

Three categories of AI-collaborated content:

- **Unedited AI output.** Raw generation copied and published without human refinement. Often fails substance and depth tests. The pattern catalog catches this efficiently.
- **AI-augmented work.** Human expertise enhanced by AI capabilities with proper oversight. Passes substance tests when the human contribution is real.
- **Systematic human-AI collaboration.** Methodical integration where humans maintain judgment, add genuine expertise, and ensure quality. Indistinguishable from skilled human writing on substance; sometimes carries minor stylistic AI fingerprints from the final draft pass.

The goal is quality assessment. Detection requires pattern recognition across multiple indicators. No single indicator proves AI generation definitively, and many AI-collaborated pieces are excellent content.

Three companion caveats complete that stance: LLMs are trained on human writing, so overlap exists; context matters — some indicators are stronger than others — and skilled human writers exhibit some of these patterns naturally; and the goal is quality assessment, not origin witch-hunting.

The full philosophical layer — the quality problem and the five characteristics of AI slop, the dual-use (GAN-dynamic) improvement model, application guidance for detection-tool builders and for readers, the path from "was this AI?" to "is this good?", and a concrete before/after revision example — lives in [references/philosophy-and-application.md](philosophy-and-application.md). It is the frame the catalog operates inside; read it when building tools on this skill or teaching the methodology.

## Related Skills

This skill is the AI-pattern-and-substance arm of the writing-quality family:

- [`synthesis-writing-pitfalls`](../../synthesis-writing-pitfalls/SKILL.md): Universal human-source bad-writing patterns (cringe, throat-clearing, caveat overload, sentence-level weakness, cliché reliance, stilted formality).
- [`synthesis-writing-craft`](../../synthesis-writing-craft/SKILL.md): Positive writing principles from the writing-craft tradition.
- [`synthesis-reader-briefing`](../../synthesis-reader-briefing/SKILL.md): Pre-writing audience analysis (prevents insider context collapse upstream).
- [`synthesis-article-writing`](../../synthesis-article-writing/SKILL.md): End-to-end article workflow with quality gates.
- [`synthesis-article-refresh`](../../synthesis-article-refresh/SKILL.md): Refresh and revitalize older articles.
- [`synthesis-voice-profiler`](../../synthesis-voice-profiler/SKILL.md): Generate a structured voice profile.
- [`synthesis-fact-checking`](../../synthesis-fact-checking/SKILL.md) v2.0: Companion skill for citation, quote, and source verification with per-family hallucination signatures.
- [`synthesis-clean-text`](../../synthesis-clean-text/SKILL.md): Enforce clean-character and no-hidden-marker requirements, audit inspectable text properties, and state the boundary on unverifiable statistical marks.
- [`synthesis-text-provenance`](../../synthesis-text-provenance/SKILL.md): Select hosted or local/open-weight generation paths, preserve manifests, audit text integrity, and report authorized provenance signals. It does not treat editorial rewriting as verified removal of a provider mark.

## References

Detailed catalog content lives in the [references/](./) subfolder:

- [philosophy-and-application.md](philosophy-and-application.md): The dual-use philosophy, characteristics of AI slop, application guidance for tool builders and readers, and the before/after revision example (restored pre-migration framing layer).
- [detailed-criteria.md](detailed-criteria.md): All 76 A3 criteria with 16-field detail and renumbering map from v3.1.0.
- [model-family-fingerprints.md](model-family-fingerprints.md): All A1 patterns across 8 families.
- [substance-and-depth.md](substance-and-depth.md): All 17 A2 sub-patterns with 5-minute editorial workflow.
- [combined-signal-fingerprints.md](combined-signal-fingerprints.md): All 86 B2 combos.
- [calibration-tables.md](calibration-tables.md): Two-axis calibration with per-family per-zone tables and ESL safe-harbor.
- [historical-patterns.md](historical-patterns.md): Historical and Deprecated patterns for forensic analysis of older content.
- [bibliography.md](bibliography.md): Consolidated bibliography with verification status.

---

Part of the [synthesis writing](https://synthesiswriting.org) craft. The methodology is durable. The catalog refreshes as model behavior shifts. Newsrooms and editorial workflows are the audience this skill serves.
