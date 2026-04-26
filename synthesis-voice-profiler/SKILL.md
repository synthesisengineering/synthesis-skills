---
name: synthesis-voice-profiler
description: "Generate a structured writing voice profile from sample texts and diagnostic questions. Outputs an agent-instruction voice section that other skills automatically consume. Use when asked to: create voice profile, analyze writing style, extract voice, profile my writing, build voice section, writing DNA, style analysis."
license: "CC0-1.0"
user-invocable: true
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Voice Profiler

A utility that analyzes your writing samples and generates a structured voice profile for agent instruction files such as `CLAUDE.md` or `AGENTS.md`. Once added, every skill that says to apply voice and style preferences from agent instructions will automatically use your profile. You run this once and update it when your style evolves.

---

## What This Produces

A structured voice profile section formatted for direct paste into your global or project-level agent instruction file. The profile includes:

- **Positive patterns** — what your writing sounds like (sentence rhythm, vocabulary preferences, rhetorical devices, formatting habits)
- **Negative constraints** — what your writing avoids (specific words, phrases, tonal patterns, structural tendencies)
- **Contextual notes** — how your voice shifts across different content types

This output integrates with the existing synthesis skills ecosystem. Skills like synthesis-article-writing, synthesis-blog-refresh, synthesis-concise-messaging, and synthesis-content-distribution already look for voice preferences in agent instructions; this skill generates what they consume.

---

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

**Question bank** (select 3-5 based on what the samples leave ambiguous):

1. **Formality range:** "Your samples lean [formal/casual/mixed]. Is that representative, or do you deliberately shift formality for different audiences?"
2. **Jargon tolerance:** "I notice you [use/avoid] technical terminology. Do you prefer domain-specific language when writing for peers, or do you always aim for accessibility?"
3. **Structure preference:** "Do you prefer short, punchy paragraphs or longer, developed ones? Your samples show [observed pattern] — is that intentional?"
4. **Rhetorical devices:** "I see you [use/rarely use] rhetorical questions, fragments, and direct reader address. Are there devices you specifically like or dislike?"
5. **Humor and tone:** "How important is humor or wit in your writing? Your samples [show evidence/lack evidence] of it."
6. **Forbidden patterns:** "Are there specific words, phrases, or writing patterns you actively avoid? Many writers have a 'never use' list."
7. **Punctuation style:** "I notice [em-dash usage / semicolon avoidance / serial comma preference / etc.]. Is that a conscious choice?"
8. **Opening strategy:** "How do you prefer to open a piece — anecdote, bold claim, question, context-setting?"
9. **Conclusion style:** "How do you prefer to end — call to action, callback to the opening, forward-looking, or just stop when done?"
10. **Content length:** "Do you tend toward concise or comprehensive? Your samples suggest [pattern]."

### Step 3: Analyze

With samples read and questions answered, analyze across six dimensions:

**Lexical Profile:**
- Characteristic vocabulary — words and phrases that recur across samples
- Vocabulary the writer avoids — notably absent words or categories
- Register — formal, conversational, technical, hybrid
- Jargon level — specialist terms vs. plain language

**Syntactic Signature:**
- Average sentence length and variation pattern
- Paragraph length and structure
- Use of fragments, run-ons, or deliberately long sentences
- List usage — bulleted, numbered, inline, or avoided

**Rhetorical Devices:**
- Questions (rhetorical, genuine, leading)
- Analogies and metaphors (original vs. borrowed, frequency)
- Direct reader address ("you")
- Repetition for emphasis
- Understatement or overstatement as a tool

**Structural Patterns:**
- Opening approach (anecdote, claim, question, scene)
- Transition style (explicit connectives, white space, thematic)
- Section organization (progressive, thematic, narrative)
- Closing approach (callback, action, restatement, abrupt)

**Tonal Identity:**
- Confidence level — assertive, tentative, measured
- Humor — present/absent, dry/overt, frequency
- Emotional register — controlled, expressive, matter-of-fact
- Relationship to reader — peer, teacher, advisor, reporter

**Negative Constraints:**
- Words and phrases the writer never uses (identified by absence across all samples)
- Structural patterns avoided (e.g., never uses bullet lists, never uses subheadings)
- Tonal patterns avoided (e.g., never sycophantic, never hedging)
- AI-typical patterns already absent from this writer's work

### Step 4: Generate the Voice Profile

Output the profile in this format, ready for the user to paste into an agent instruction file:

```markdown
## Voice & Writing Style

### Characteristics
- [Observation 1 — e.g., "Conversational but substantive. Writes like explaining to a smart colleague."]
- [Observation 2 — e.g., "Short paragraphs. Rarely more than 4 sentences. Single-sentence paragraphs for emphasis."]
- [Observation 3 — e.g., "Opens with specific anecdotes, not abstractions."]
- [Observation 4+]

### Sentence Structure
- [Pattern — e.g., "Varies length deliberately. Short sentences for emphasis, longer for complexity."]
- [Pattern — e.g., "Uses fragments sparingly but deliberately."]
- [Pattern — e.g., "Favors active voice. Passive only for emphasis on the object."]

### Vocabulary Preferences
- [Preference — e.g., "Plain language over jargon, even for technical topics."]
- [Preference — e.g., "Concrete over abstract. 'Revenue dropped 40%' over 'significant decline.'"]

### Avoid
- [Constraint — e.g., "Never use: delve, tapestry, nuanced, robust, foster, beacon"]
- [Constraint — e.g., "No em-dashes (use commas, periods, or colons instead)"]
- [Constraint — e.g., "No section-ending summaries. If a section needs a summary, restructure it."]
- [Constraint — e.g., "No AI-typical phrases: 'it's important to note,' 'in conclusion,' 'delve into'"]
- [Constraint — e.g., "No sycophantic or concierge language. No 'great question!' or 'I'd be happy to help.'"]

### Tone
- [Tone note — e.g., "Confident without arrogance. Direct without being rude."]
- [Tone note — e.g., "Humor is dry and infrequent — used for relief, not performance."]
- [Tone note — e.g., "Takes positions. Disagrees when warranted. Does not hedge every conclusion."]
```

**Adapt the template to the actual analysis.** Not every writer needs every section. Add sections for formatting preferences, content structure, or audience awareness if the analysis reveals strong patterns. Remove sections where the writer has no strong preference.

### Step 5: Review and Refine

Present the profile to the user and ask:

1. "Does this sound like you?"
2. "Is anything important missing?"
3. "Is anything here wrong — a pattern I identified that you don't actually want?"

Revise based on feedback. The profile should feel like a mirror the writer recognizes, not a prescription they'd resist.

---

## Integration

After the user adds the voice profile to their agent instruction file:

- **synthesis-article-writing** will apply it during Phase 2 (Writing)
- **synthesis-blog-refresh** will use it for voice consistency checks
- **synthesis-concise-messaging** will apply voice preferences to condensed messages
- **synthesis-content-distribution** will adapt posts to match voice across platforms
- **synthesis-content-quality** will flag deviations from the negative constraints during quality review
- Any custom skills that say to apply voice preferences from agent instructions will consume it automatically

No additional wiring is needed. Agent instruction files are the integration layer.

---

## When to Re-Run

- After a significant writing style shift (new role, new audience, deliberate evolution)
- When adding a new content type to your workflow (e.g., you start writing for a different platform)
- Periodically (every 6-12 months) to ensure the profile still matches your current voice
- After receiving feedback that your AI-assisted writing doesn't sound like you

## Related

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists.
