---
name: synthesis-writing-craft
description: "Positive writing principles from the writing-craft tradition for AI agents drafting, editing or reviewing prose on a writer's behalf: sentences, pacing, voice, register, structure, revision. Use with synthesis-content-quality and synthesis-writing-pitfalls."
license: CC0-1.0
depends_on: []
metadata:
  author: Rajiv Pant
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Writing Craft

Positive principles from the centuries-old writing-craft tradition, as an operating guide for an AI agent drafting, editing or reviewing prose on a writer's behalf. The skill is the operational shorthand; the books on the recommended-reading list are where the depth lives.

## Binding rules

For any agent working on someone's prose. Rules 1 to 7 and 9 are principles from references/principles.md, named as there; rule 8 condenses its section on voice across registers, and rule 10 the writing outcome review.

1. **Make every edit earn its place.** Name the problem a change solves; if it does not improve truth, clarity, structure, register or rhythm, keep the original.
2. **Preserve the source's causal mechanism.** Keep who acted, what changed and why; a smoother generalization is less accurate even when it sounds polished.
3. **Preserve decisive detail.** Keep the names, quantities, constraints, sequence and exceptions that make a claim true; compression removes repetition, not evidence.
4. **Protect meaningful voice variation during editing.** Keep deliberate fragments, changes of pace and characteristic diction unless a specific defect requires intervention.
5. **Cut every word that does not earn its place.** The oldest rule in the craft; adverbs and adjectives propping up weak words go first.
6. **Specificity beats abstraction.** A specific example beats a general claim; it is the closest thing to a craft principle that always works.
7. **Keep structure in proportion to the material.** Never force a fixed number of sections, bullets, examples or takeaways onto material shaped otherwise.
8. **Write in the register of where the piece will appear** (article, social post, email, speech) and test it by reading aloud. Article voice in a social post reads as AI-generated even when a human wrote it.
9. **Trust the reader.** Most writing problems improve when the writer trusts the reader more.
10. **In autonomous review, reject only for a stated requirement violation or concrete reader harm,** with exact evidence, and label taste separately. A reviewer who polishes away sound prose has failed.

## Contents

- [references/principles.md](references/principles.md): the craft tradition and the full principles by craft level (sentences, paragraphs and pacing, voice and honesty, voice across registers, structure, process, revision), each with its reasoning and examples. Read it when drafting or revising, or when a binding rule needs its full reasoning.
- [references/autopilot-writing-quality.md](references/autopilot-writing-quality.md): writing outcome review: how to judge, reject, calibrate and repair in an autonomous review. Read it before reviewing prose without the writer present.
- [references/recommended-reading.md](references/recommended-reading.md): the ten recommended books and where to start with each. Read it when someone asks where to learn the craft.
- [references/background.md](references/background.md): what this skill is, the recommended-reading list, related skills. Read it once, or when choosing between this skill and a sibling.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.1.1 text now lives.
- When to Use, What This Skill Is NOT, Quick-Reference Principles, Working with the Sibling Skills: below.

## When to Use This Skill

This skill is primarily for AI agents at runtime, not for human writers studying the craft.

- AI agent reviewing or editing prose on a writer's behalf
- AI agent drafting prose where craft principles need to be applied actively
- Pre-publication revision pass on AI-assisted work
- Reference during the synthesis-writing-pitfalls scan (the positive complement to the negative catalog)

## What This Skill Is NOT

- Not a substitute for reading the canonical writing-craft books
- Not teaching material for human writers learning the craft
- Not a comprehensive theory of writing
- Not a summary or distillation of any specific book on the recommended-reading list

If you are a human writer who wants to learn writing craft, buy and read the books on the recommended list. This skill is what an AI agent loads when it needs to apply craft principles to a specific piece of prose.

## Quick-Reference Principles

When pressed for time, these are the principles that produce the largest improvement per minute of editing:

1. Cut every word that does not earn its place
2. Move the lede to the first paragraph
3. Replace abstract claims with specific examples
4. Cut adverbs and adjectives that prop up weak words
5. Vary sentence length deliberately
6. Read aloud
7. Trust the reader
8. Preserve the source's mechanism and decisive details
9. Make every edit earn its place

## Working with the Sibling Skills

For autonomous review, apply [writing outcome review](references/autopilot-writing-quality.md). Preserve distinctive sound prose in positive controls, distinguish reader harm from optional taste, and retain false-rejection findings alongside missed substantive defects.

This skill is the positive half of a pair:

- For pattern detection (what to AVOID), use [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md)
- For AI-generation pattern detection, use [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md)

A typical workflow combines all three: use this skill to apply positive principles during drafting and revision; use pitfalls to detect human-source weaknesses; use content-quality to detect AI-source weaknesses.
