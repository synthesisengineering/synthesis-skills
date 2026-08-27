# Slop Detection Skill Manifest

**Version:** 1.0
**Date:** 2026-05-19
**License:** CC0-1.0 (skill content) / MIT (this manifest)
**Canonical URL:** https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/tools/slop-detection/manifest.md

This file is the canonical index of skill files that constitute the synthesis engineering open-source slop detection system. It exists so a chatbot or AI agent can fetch a single stable URL, then follow the URLs below to load the full skill methodology without any local installation.

The manifest URL is stable. The skill files it points to can grow and refresh over time. Adding new skills or new pattern catalogs means editing this file; the user-facing prompt that consumers paste into their chatbots does not change.

## How to use this manifest

If you are an AI agent reading this file because a user asked you to apply the synthesis engineering slop detection system:

1. Fetch every URL in the **Required skill files** section below in order.
2. Read each file in full. The methodology, the pattern catalog, and the protocols are in these files.
3. Apply the methodology to the user's content. Produce a structured analysis covering: AI-provenance signals (which patterns triggered, with examples from the user's content), substance and depth (apply the A2 sub-pattern tests), fact-check items if any citations or quotes are in the content, top revision recommendations, and an overall verdict.
4. Honor the methodology's calibration discipline: ESL safe-harbor (do not flag uniform paragraph length + restricted vocabulary + heavy transitions as AI unless a register-specific AI marker is also present), zone-conditional detection (use artifact mode by default; ask the user if they want full-response mode), two-axis separation (AI-provenance and slop-independence are distinct; high AI signal does not mean slop and vice versa).

## Required skill files (essential, approximately 30K tokens)

These five SKILL.md files contain the complete methodology, the pattern catalog at section-summary level, the cross-cutting layer (causal taxonomy, combined-signal fingerprints, two-axis calibration), and the quick-reference checklist. An AI agent applying these files alone can produce a high-quality slop analysis. Fetch every URL in this section.

- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/SKILL.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-fact-checking/SKILL.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-writing-pitfalls/SKILL.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-writing-craft/SKILL.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-clean-text/SKILL.md

## Extended reference files (deep mode, approximately 250K tokens)

These are the references/ subfolders for the primary and companion skills. They contain the full per-pattern detail (all 14 fields per pattern), the per-family fingerprint catalogs, the combined-signal fingerprint catalog, the calibration tables, the historical patterns archive, the detailed fact-checking protocols, the per-family hallucination signatures, the citation-laundering detection protocol, the production incident archive, and consolidated bibliographies.

**Only fetch these in deep mode**, and only on models with at least 1M-token context windows (Anthropic Claude with the 1M-context beta header, Google Gemini 2.5 Pro 2M context). Fetching all extended files plus the user's content can push a 200K-context model over its input limit.

For most analyses on most chatbots, the Required skill files above are sufficient. Use Extended mode when you specifically need the full pattern catalog (for example, when investigating a specific named pattern, when doing forensic analysis of older content using the historical patterns, or when doing a deep fact-check that needs the full per-family hallucination signature detail).

- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/detailed-criteria.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/model-family-fingerprints.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/substance-and-depth.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/combined-signal-fingerprints.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/calibration-tables.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/historical-patterns.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-content-quality/references/bibliography.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-fact-checking/references/detailed-protocols.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-fact-checking/references/per-family-hallucination-signatures.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-fact-checking/references/citation-laundering-detection.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-fact-checking/references/production-incident-archive.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-fact-checking/references/bibliography.md
- https://raw.githubusercontent.com/synthesisengineering/synthesis-skills/main/skills/synthesis-writing-pitfalls/references/detailed-pitfalls.md

## Output format guidance for the agent

When you produce the analysis for the user, structure it as:

```
## AI-provenance signals (Axis 1)
- High-signal patterns triggered, each with up to 5 short quoted snippets from the user's content (keep quotes under 20 words per the copyright-respect rule).
- Combined-signal fingerprints (B2 combos) that fired.
- Family attribution if discernible: Claude, GPT, Gemini, Llama, Grok, DeepSeek, Mistral, Qwen, or mixed / unable to attribute / appears human.
- ESL safe-harbor check: did the cornerstone signature fire without a register-specific AI marker?
- Provenance confidence: Strong AI / Likely AI / Mixed / Likely human / Strong human.

## Slop-independence (Axis 2)
- 5-minute editorial workflow per substance-and-depth.md.
- Slop verdict: Substantive / Mostly substantive / Mixed / Slop-leaning / Heavy slop.

## Fact-check items (only if content has citations or quotes)
- Apply per-family hallucination signature checks.
- Apply C1 protocols where relevant (URL rot, synthetic sources, citation laundering, nested attribution, etc.).

## Top revision recommendations (3 to 5 specific changes)
- Line-anchored where possible.

## Overall verdict
- One paragraph synthesizing the two axes.
```

## Provenance and integrity

This manifest and the skill files it points to are open source. The methodology is the durable contract; the catalog refreshes as model behavior shifts.

- Repo: https://github.com/synthesisengineering/synthesis-skills
- License (skills): CC0-1.0
- Maintainer: Rajiv Pant
- Anyone is welcome to install the skills locally in their own AI agent at zero cost. The hosted convenience tools at tools.synthesiswriting.org charge a nominal fee only to cover token + hosting costs.

## Versioning

This manifest is versioned with the skill files it points to. When a skill file changes meaningfully (major version bump), this manifest is updated to reflect the new state but the canonical URL stays the same. Consumers who paste the prompt-template once and use it repeatedly always get the latest skill methodology.

If you maintain a fork or want to pin to a specific revision, use a commit-specific raw URL instead of the `main` branch URL above.

## Privacy

The skill files this manifest points to are static, public, open source. Fetching them sends nothing back. Apply the skills locally in your agent; nothing about the user's content needs to leave the user's session.

The hosted convenience tools at tools.synthesiswriting.org collect zero analytics, zero telemetry, zero submitted text, zero user identifiers. The BYOK path runs entirely in the user's browser; keys never touch the maintainer's servers.

---

*Part of the [synthesis engineering](https://synthesisengineering.org) open-source ecosystem. The writer writes; the AI assists.*
