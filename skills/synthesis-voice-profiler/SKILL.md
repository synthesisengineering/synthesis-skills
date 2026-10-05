---
name: synthesis-voice-profiler
description: "Build a writing voice profile from the user's samples and diagnostic questions, output as a voice section for CLAUDE.md or AGENTS.md that writing skills consume. Use when asked to create a voice profile, analyze writing style, extract voice, profile my writing or build a voice section."
license: "CC0-1.0"
user-invocable: true
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Voice Profiler

A utility that analyzes your writing samples and generates a structured voice profile for agent instruction files such as `CLAUDE.md` or `AGENTS.md`. Once added, every skill that says to apply voice and style preferences from agent instructions will automatically use your profile. You run this once and update it when your style evolves.

## Binding rules

1. **Profile only the user's own writing:** 3-5 samples they are proud of, at least 300 words each, not collaborative or heavily edited by others. Anyone else's hand in the samples profiles someone else.
2. **Ask 3-5 diagnostic questions, only about what the samples leave ambiguous;** never ask about a pattern the samples already show.
3. **Analyze all six dimensions,** including the negative constraints, which are found by absence across every sample.
4. **Adapt the template to the analysis:** add sections where patterns are strong and remove sections where the writer has no strong preference.
5. **The user reviews the profile and you revise it** until it reads as a mirror they recognize, not a prescription they would resist.
6. **The output is a section for the agent instruction file** (`CLAUDE.md` or `AGENTS.md`). That file is the integration layer, so no other wiring is needed.

## Contents

- [references/diagnostics-and-analysis.md](references/diagnostics-and-analysis.md): the ten-question bank for Step 2 and the checklist under each of the six analysis dimensions for Step 3. Read it after reading the samples, before asking questions.
- [references/profile-template.md](references/profile-template.md): the voice profile template for Step 4. Read it when writing the profile.
- [references/integration.md](references/integration.md): which skills consume the profile and how. Read it when the user asks how the profile will be used.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives.
- What This Produces, Process (Steps 1 to 5), When to Re-Run: below.

## What This Produces

A structured voice profile section formatted for direct paste into your global or project-level agent instruction file. The profile includes:

- **Positive patterns** — what your writing sounds like (sentence rhythm, vocabulary preferences, rhetorical devices, formatting habits)
- **Negative constraints** — what your writing avoids (specific words, phrases, tonal patterns, structural tendencies)
- **Contextual notes** — how your voice shifts across different content types

This output integrates with the existing synthesis skills ecosystem. Skills like synthesis-article-writing, synthesis-blog-refresh, synthesis-concise-messaging, and synthesis-content-distribution already look for voice preferences in agent instructions; this skill generates what they consume.

## Process

### Step 1: Collect Writing Samples

Ask the user to provide 3-5 samples of their own writing. The samples should:

- Be pieces the user is proud of (representative of their best voice)
- Span different content types if possible (blog post, email, technical writing, social media)
- Be substantial enough to reveal patterns (at least 300 words each, ideally 500+)
- Be genuinely the user's writing, not collaborative or heavily edited by others

If the user provides URLs, fetch and read them. If they provide filenames, read the files.

### Step 2: Ask Diagnostic Questions

After reading the samples, ask 3-5 targeted questions to surface preferences that sample analysis alone cannot reveal. Adapt the questions based on what the samples show — do not ask about patterns already evident.

Select the questions from the question bank in [references/diagnostics-and-analysis.md](references/diagnostics-and-analysis.md).

### Step 3: Analyze

With samples read and questions answered, analyze across six dimensions:

Lexical Profile, Syntactic Signature, Rhetorical Devices, Structural Patterns, Tonal Identity, and Negative Constraints. What to look for under each is in [references/diagnostics-and-analysis.md](references/diagnostics-and-analysis.md).

### Step 4: Generate the Voice Profile

Output the profile in this format, ready for the user to paste into an agent instruction file:

The format is the template in [references/profile-template.md](references/profile-template.md).

**Adapt the template to the actual analysis.** Not every writer needs every section. Add sections for formatting preferences, content structure, or audience awareness if the analysis reveals strong patterns. Remove sections where the writer has no strong preference.

### Step 5: Review and Refine

Present the profile to the user and ask:

1. "Does this sound like you?"
2. "Is anything important missing?"
3. "Is anything here wrong — a pattern I identified that you don't actually want?"

Revise based on feedback. The profile should feel like a mirror the writer recognizes, not a prescription they'd resist.

## When to Re-Run

- After a significant writing style shift (new role, new audience, deliberate evolution)
- When adding a new content type to your workflow (e.g., you start writing for a different platform)
- Periodically (every 6-12 months) to ensure the profile still matches your current voice
- After receiving feedback that your AI-assisted writing doesn't sound like you

## Related

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.
