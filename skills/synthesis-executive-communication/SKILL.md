---
name: synthesis-executive-communication
description: "Translate technical work for CEOs, CFOs, boards and other non-technical executives: persona tests, de-jargoning, consequence over mechanism, trusted upward reports. Use for executive updates, progress reports, executive summaries, board updates, leadership status or business-term translation."
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  format: v5
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Executive Communication for Technical Leaders

Make technical work readable to the business executives a technology leader reports to: every noun understood, every sentence a business consequence, every fact still true.

## Binding rules

1. **Name the actual reader,** the person rather than "executives"; their background decides what counts as jargon.
2. **Every noun must pass.** Would this reader understand every noun in the sentence, and verbs like *merge*, *deploy*, *refactor*, *render*? A sentence with one opaque noun is a sentence the reader skips.
3. **Translate to the business consequence, not to softer jargon,** and never invent one. If you cannot state the consequence truthfully, the sentence is not ready for this reader.
4. **Scan all six kill-list categories** before anything goes to a non-technical reader: unexplained codenames, workflow and tooling vocabulary, insider praise, defect and error counts, engineering-culture credentials, and mechanism where consequence belongs.
5. **Every sentence does something for the reader:** something to repeat, decide with, own, or trust you more for. Cut the rest.
6. **Honest flags stay.** Change the vocabulary and the selection, never the truth; state what slipped or is unproven in one plain clause.
7. **Write for forwarding:** no confidences, no criticism of named people, no claim a colleague would dispute, and a five-minute read (about 1,200 words).
8. **Review in persona before sending.** An engineering-literate reviewer, human or AI, cannot catch this by feel, so brief one as the non-technical reader.

## Contents

- [references/kill-list.md](references/kill-list.md): the six kill-list categories in full, and the translation table with invented examples. Read for step 3 of the review protocol, and whenever you translate a sentence.
- [references/background.md](references/background.md): the problem this skill solves, where it came from, and related skills. Read once, or when choosing between this and a sibling writing skill.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.0.0 text now lives (ruling D8).
- The bar: below. The every-noun test.
- Structure of an upward report that earns trust: below. Read when writing a progress report, executive summary or board update.
- Review protocol, What this is not: below. The six-step review to run before anything ships, and the limits of the skill.

## The bar: the every-noun test

> Would the business executive you are writing to understand every noun in this sentence?

Not "is this too deep." Not "is the altitude right." Every **noun**, checked one at a time — and a few verbs (*merge*, *deploy*, *refactor*, *render*). Jargon hides in nouns, and a sentence with one opaque noun is a sentence the reader skips.

A sentence that fails the test gets translated to its **business consequence**, not simplified into slightly-less-technical vocabulary. "Deployed to staging" does not become "pushed to the pre-production environment." It becomes "on the internal test site; customers see it after the next release."

## Structure of an upward report that earns trust

Observed in real report cycles with non-technical principals:

- **Done first, ordered by importance to the reader** — not by your effort, not by chronology. The reader's priorities set the sequence.
- **A short numbers strip up top** — only numbers the reader can repeat in their next meeting: dates held, adoption counts, money, days ahead or behind. Never internal-volume metrics (word counts, ticket counts, commit counts) — and note that a *translated* volume count is still a volume count; it belongs in body text at most, never in the strip.
- **A closed-loop section for the things this reader raised**, in their own framing. It converts the report from a broadcast into a conversation, and it is the section a boss reads most carefully.
- **Honest flags, plainly stated.** What slipped, what is unproven, what you don't know yet. Calibration earns trust; spin spends it. One clause, no drama, no burying.
- **Value shown, never told.** No self-praise adjectives anywhere. The moves that work: shipped fact plus business consequence; "this is now standard practice" (institutionalization); the reader's own ownership reflected back ("the initiative you commissioned," "the order you chose"); speed as evidence ("scoped Tuesday, live the following week").
- **The forwardability test.** Assume the reader forwards the document to their boss and their peers. Every line must survive the trip: no confidences, no criticism of named people, no claim a colleague would dispute, no detail that embarrasses anyone who helped you.
- **A five-minute read.** Executives read between meetings. Past roughly 1,200 words, each marginal section costs attention from the sections that matter.

## Review protocol

1. **Name the actual reader.** Not "executives" — the person. Their background decides what counts as jargon.
2. **Run the every-noun test** on each sentence, as that person.
3. **Run the kill-list scan** — all six categories, mechanically.
4. **Ask of each sentence: what does the reader *do* with this?** Repeat it, decide with it, feel ownership of it, or trust you more because of it. A sentence that does none of these gets cut.
5. **Stage an adversarial read in persona.** Brief a reviewer — human or AI — as the reader: "You run a business unit and have never worked in engineering. Mark every word you would skip and every sentence that tells you nothing." This catches what an engineering-literate review pass structurally cannot.
6. **Read it aloud** as if presenting to the person. The ear catches register the eye forgives.

## What this is not

- **Not dumbing down.** Precision about consequences is harder than precision about mechanisms. The executive version of a sentence usually takes longer to write than the technical one.
- **Not spin.** The honest flags stay, and every translation must remain true to the underlying facts — including the unflattering ones. This skill changes the vocabulary and the selection, never the truth.
- **Not only for reports.** The same bar governs email, chat messages, meeting remarks, and board material. The report is just where the failure costs the most.
