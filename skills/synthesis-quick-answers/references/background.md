# Quick answers: background

Why the companion exists and which skills it leans on.

## The Problem

Focused project sessions accumulate context on purpose — that's what makes them good at the work they're for. But not every question belongs there. "When is a colleague back from vacation" and "has a release shipped yet" are real, frequent, and usually urgent-feeling questions that have nothing to do with whatever a focused session is mid-task on. Answering them inline does two kinds of damage:

- **Context pollution.** The focused session's window fills with unrelated lookups, and its summarized history gets noisier every time it compacts.
- **Cost mismatch.** A one-line factual lookup doesn't need the reasoning depth or the model tier a hard architecture or strategy session runs at. Paying Max-effort-tier prices for "when is X back" is waste, repeated daily.

The fix is not "be disciplined about not asking." The questions are legitimate and often time-sensitive. The fix is a separate, cheap, low-ceremony surface built for exactly this shape of question — one that exists specifically so the *other* sessions can stay clean.

## Relationship to Other Skills

- **`synthesis-project-management`** supplies the project itself (index entry, tiered `CONTEXT.md`/`REFERENCE.md`, cross-agent handoff so the same project works from Claude Code and Codex identically).
- **`synthesis-context-lifecycle`** governs the tiered-memory mechanics once the project exists.
- **`synthesis-grounding-discipline`** is why step 2 of the protocol is not skippable, and its cache-vs-truth vocabulary (verified vs. cached, name the layer) is exactly what step 3's confidence trailer reuses rather than inventing a parallel scheme.
- **`synthesis-concise-messaging`** shapes the answer format.
- **`synthesis-model-tiers`** supplies the `routine` tier recommendation and the vocabulary for stating it without attempting to switch it.
- **`synthesis-knowledge-capture`** is where durable facts actually get saved, not this skill.
- **`synthesis-onboarding`** provides the stable `synthesis workspace ensure` command used in Setup step 1 — this skill never scaffolds a substitute of its own.
