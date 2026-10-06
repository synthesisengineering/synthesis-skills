# Catch-up ledger: background

Why the skill exists, its design rationale and its neighbors, moved verbatim from the 0.3.0 SKILL.md. Read it once, or when deciding between this skill and a neighboring one.

The 0.3.0 SKILL.md carried this version line under its title:

**Version 0.3.0** (2026-08-14)

## The problem

Falling behind is part of life. Travel, family visits, illness, and crunch weeks interrupt the daily-ritual cadence, and the interruption itself is never the failure. The failure mode is silent: commitments made before the gap decay invisibly, because every existing artifact is scoped to a unit of time that assumes continuity. Daily plans capture one day's intent. Weekly loose-ends reviews (synthesis-daily-rituals v2.8.0) assume Fridays happen. Project CONTEXT files capture project state, not personal commitments. When the cadence breaks, nothing reconciles what was promised against what happened.

The result, observed repeatedly in practice: items survive as anxiety rather than as records. The person knows they're behind but not on what, so the backlog feels larger than it is, and genuinely-expired items consume attention that live items need.

## Design rationale (thinking-framework summary)

- **First principles:** untracked decay is invisible; the missing primitive is periodic reconciliation, distinct from daily planning.
- **Systems:** sources → deterministic scan → judgment classification → routing → ratchet. The ratchet marker (last-sweep date in the ledger) makes sweeps compose instead of re-scanning history.
- **Complexity:** commitment states are not binary; the taxonomy below names six distinct states because each routes differently.
- **Analogy:** mark-and-sweep garbage collection for commitments. Roots = the source artifacts; live objects = items still referenced and still valuable; collection = explicit release with lesson extraction. Also: an accounting reconciliation — hence "ledger."
- **Design:** the reader experience is one document, kindest-possible honesty, biggest-leverage items first. Expired items get a *learning* section, not a guilt section.

## Relationship to neighboring skills

- **synthesis-daily-rituals** — the Weekly Loose-Ends Review (Day-End Step 10) is the steady-state catch; this skill is the broken-cadence recovery + long-window deep look. A daily ritual that detects 2+ missed days should suggest invoking this skill.
- **synthesis-checkpoint** — provides the date/state verification used in Step 1.
- **synthesis-context-lifecycle** — project-scoped memory management; this skill is person-scoped commitment management. The ledger may cite CONTEXT files but never replaces them.
- **synthesis-slack-sync / synthesis-meeting-transcripts** — produce the transcript sources Step 3 reads. Run syncs BEFORE the sweep so classification works from current truth.
