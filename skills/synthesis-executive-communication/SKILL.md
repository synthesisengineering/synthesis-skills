---
name: synthesis-executive-communication
description: >
  Translate technical work into clear, actionable communication for CEOs, CFOs, business-unit
  leaders, boards, and other non-technical executives. Applies persona tests, de-jargoning,
  mechanism-to-consequence translation, and trusted upward-report structure. Use for executive
  updates, progress reports, executive summaries, board updates, leadership status, business-term
  translations, or any technical message to a business audience.
license: "CC0-1.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Executive Communication for Technical Leaders

## The problem

Technical leaders write in the register of their craft, and their most consequential readers do not read that register. The CEO, the business-unit president, the CFO, the peers who run revenue and legal and HR — these are the people who decide budgets, headcount, and the leader's own standing, and they absorb exactly the fraction of a report they understand.

The failure is silent. Nobody replies asking what a pull request is. Nobody admits they skimmed past the codename they didn't recognize. They just take in less, value the work less, and quietly build their picture of the technology organization from the parts that read like business. For a technology leader, the upward progress report is a career-load-bearing document, and register failure taxes it invisibly.

The deeper trap: an engineering-literate reviewer — human or AI — cannot catch this by feel. A review pass tuned to "avoid engineering weeds" still waves through *staging*, *CI*, and *merged pull requests*, because to a technical reader those aren't weeds. This skill exists because the bar is different in kind, not degree.

This skill was distilled from real report-revision cycles between technology leaders and the non-technical business principals they report to. In those cycles, drafts that had survived multi-reviewer adversarial passes tuned for factual grounding, political risk, and "executive value" still needed the same categories of content removed by hand, sentence after sentence. Those categories are the kill-list below.

## The bar: the every-noun test

> Would the business executive you are writing to understand every noun in this sentence?

Not "is this too deep." Not "is the altitude right." Every **noun**, checked one at a time — and a few verbs (*merge*, *deploy*, *refactor*, *render*). Jargon hides in nouns, and a sentence with one opaque noun is a sentence the reader skips.

A sentence that fails the test gets translated to its **business consequence**, not simplified into slightly-less-technical vocabulary. "Deployed to staging" does not become "pushed to the pre-production environment." It becomes "on the internal test site; customers see it after the next release."

## The kill-list

Six categories that read as normal to the writer and as noise (or worse) to the executive reader. Scan for all six before anything ships upward or sideways to a non-technical audience.

### 1. Unexplained codenames and internal project names

Your project's codename is insider vocabulary the reader never agreed to learn. If the reader would ask "what is that?", the name is doing anti-work. Say what the thing does. If the codename must appear because the reader will hear it in other rooms, gloss it inline on first use — once.

### 2. Workflow and tooling vocabulary

Pull requests, merges, branches, repos, staging, CI, QA environments, framework names, cloud vendor names, API mechanics. None of it carries meaning for this reader. Translate to the business action: *finished review and accepted*, *on the internal test site*, *ships on the next scheduled release* — and reserve *live* and *shipped* for work that is actually in front of users.

### 3. Insider praise

Quoting your own team praising your own team's work — or your own in-meeting reaction to it — is not evidence to an outside reader; it reads as manufactured applause. Cut every instance. Show reception through facts an outsider can verify: what shipped, who outside the team adopted it, what happened next because of it.

### 4. Defect and error counts

"Fixed 37 bugs this sprint," "eliminated a recurring class of nightly failures," "caught the issue before launch" — operational exhaust. To the executive it communicates nothing except that things break. If reliability genuinely matters to this reader, state the consequence: what used to go wrong now cannot, and what protects it from recurring. Usually one sentence; often zero.

### 5. Engineering-culture credentials

Open-source contributions, test coverage, tooling choices, methodology names. These signal craft to peers and nothing to this reader — unless the item changes something the reader owns (cost, risk, speed, talent). If it does, state that change; if it does not, cut it.

### 6. Mechanism where consequence belongs

The default sentence describes what changed for the business. Mechanism appears only when the reader must act on it or fund it. "We rewrote the retry logic in the payments worker" is mechanism; "the payment failures customers hit last quarter cannot recur" is consequence. The reader funds consequences.

## Translation patterns

All examples below are invented. Note what the honest ones have in common: several right-column cells use knowledge the left-column sentence does not carry. That is the point — a faithful consequence-translation pulls the consequence from what you know to be true about the work. It never invents one. If you cannot state the business consequence truthfully, the sentence was not ready for this reader.

| The draft says | What the executive reads | Write instead |
|---|---|---|
| Merged 14 pull requests this week | *(nothing)* | This week's changes finished review and are queued for Thursday's release |
| Deployed the new checkout to staging | *(nothing)* | The new checkout is on the internal test site; customers see it after Thursday's release |
| The dedupe job is idempotent | *(nothing)* | The duplicate-detection step gives the same answer every time it runs, so its results can be trusted and audited |
| Project LANTERN cleared its last blocker | What is LANTERN? | The new customer-data feed cleared its last blocker |
| Fixed 37 bugs this sprint | Things break a lot | *(usually: cut. If reliability matters to this reader:)* The checkout failures customers hit last month cannot recur; monitoring now catches that class before customers do |
| Kicked off the API-contract workshop | A meeting about contracts? | The billing and CRM teams met to agree on how their systems share customer data |
| Shipped SSO | *(nothing)* | People sign in with the company account they already have |
| Refactored the invoicing service | *(nothing)* | We reorganized the invoicing code so future billing changes ship in days instead of weeks; nothing customers see changed |

The pattern behind every row: name the actor the reader knows, the action in plain verbs, and the consequence the business feels — truthfully, including the unflattering parts.

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

## Related Skills

- [`synthesis-reader-briefing`](../synthesis-reader-briefing/SKILL.md) — pre-writing audience analysis for public articles; this skill is its sibling for workplace reporting and correspondence
- [`synthesis-concise-messaging`](../synthesis-concise-messaging/SKILL.md) — brevity discipline for short-form business messages
- [`synthesis-writing-craft`](../synthesis-writing-craft/SKILL.md) — the positive craft principles underneath
- [`synthesis-writing-pitfalls`](../synthesis-writing-pitfalls/SKILL.md) — universal human bad-writing patterns (credential-stuffing and humble-bragging are near relatives of insider praise)
- [`synthesis-content-quality`](../synthesis-content-quality/SKILL.md) — AI-pattern and substance detection for anything drafted with AI assistance

---

Part of the [synthesis writing](https://synthesiswriting.org) craft — the writer writes, the AI assists. For technology leaders whose most important readers don't read code.
