# Grounding discipline: background

Why this discipline exists, how it relates to other skills, and the principle under all twelve rules.

## Why this exists

A discipline for keeping AI-agent output anchored to external evidence. The failure family it catches is the mirror image of the one [synthesis-anti-shortcuts](../synthesis-anti-shortcuts/SKILL.md) catches: anti-shortcuts stops the agent from doing less than the work requires; grounding discipline stops the agent from claiming more than the evidence supports. Both are narrative-quality optimizations working against external truth — one dismisses real concerns to keep the story tidy, the other invents satisfying completions to keep the story moving.

The shapes in this catalog are universal to LLM agents, not quirks of one model or one workflow. A language model generates the most plausible continuation. Most of the time the plausible and the true coincide, which is exactly what makes the divergent cases dangerous: a fabricated reply reads like a real one, a stale cached fact reads like a fresh one, a null result from a broken probe reads like a verified absence. None of these announce themselves. The only defense is procedural — a set of checks applied at the moments where plausibility and truth come apart.

This skill is that set. Each catalog entry names the rule, the failure shape it prevents (with one anonymized incident vignette — every entry here was paid for in production), and the compliance procedure. A closing self-check compresses the catalog into the questions to ask before any output ships.

For [decisive uncertainty](../synthesis-thinking-framework/references/decisive-uncertainty.md), bind the question to the source that can change the decision. Exact quotes establish presence; a reviewer must still establish support. An executed observation can refute a prediction without becoming a successful acceptance result. Preserve those negative results, source generations and limitations when the plan changes.


## Relationship to Other Skills

- **[synthesis-anti-shortcuts](../synthesis-anti-shortcuts/SKILL.md)** — The effort-side sibling. Anti-shortcuts catches deferral, dismissal, and false consultation; this skill catches fabrication, stale propagation, and false absence. An output can fail both at once — a confabulated "already done" is simultaneously a shortcut and a grounding failure.
- **[synthesis-checkpoint](../synthesis-checkpoint/SKILL.md)** — The session-state instance of cache-vs-truth: verified time, git history, and context files re-synced on drift signals. Checkpoint covers "where are we"; this skill covers every fact leaving the session in an output.
- **[synthesis-fact-checking](../synthesis-fact-checking/SKILL.md)** — Verifies claims in *content being reviewed*; this skill governs claims the *agent itself* is about to make.
- **[synthesis-implementation-integrity](../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification that work is actually complete. Its "never claim a check that did not run" is this discipline applied to self-reports.
- **[synthesis-slack-sync](../synthesis-slack-sync/SKILL.md)** — Carries the messaging-platform instance of rules 2, 7, and 9: transcripts-first lookups, provenance for synced content, and bounded reads for absence claims.


## The Underlying Principle

Every entry in this catalog is one mechanism: **a claim's plausibility is not its evidence.** LLM agents are plausibility engines — that is what generation is — so the plausible-but-unverified claim is the native failure mode, the thing the system produces when nothing intervenes. The intervention cannot be "try to be accurate," because the confabulated reply, the stale approval, the mis-aimed probe, and the completed truncation all *feel* accurate from the inside.

The intervention is structural: bind every class of claim to the class of evidence that grounds it — a tool citation for quotes, a verifying command for system state, a count for quantifiers, a positive control for absences, a listing for existence, an independent validation for destructive targets. When the evidence class is missing, the claim does not ship. The agent that applies this discipline is not the one that never errs; it is the one whose errors cannot silently reach an output.
