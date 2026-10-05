# Coverage map: quick answers 1.3.1 to 2.0.0

Every part of the 1.3.1 SKILL.md and where it lives now. Nothing was removed, and the coverage check finds every old line verbatim.

| 1.3.1 section | Now |
|---|---|
| Frontmatter description | Shortened to 276 characters; the 1.3.1 text is kept below |
| `depends_on`, `source_repo`, `source_type` | Kept: `conformance.py source` (skill-contract check) and onboarding's `modular.py` dependency selection read them |
| Title | SKILL.md (verbatim), followed by a new two-sentence purpose paragraph |
| The Problem | references/background.md (verbatim) |
| The Pattern, including "Automatic" is a file, not a habit | references/setup.md (verbatim); Binding rules 8 and 9 |
| Configuration table | references/setup.md (verbatim); Binding rule 10 carries the model-tier row |
| Setup, steps 1 to 6 | references/setup.md (verbatim); Binding rules 8 to 10 |
| Operating Protocol, steps 1 to 5 with the tier table | references/operating-protocol.md (verbatim); Binding rules 1 to 6 |
| Scope Boundary — What This Is Not For | SKILL.md (verbatim); Binding rule 7 |
| Relationship to Other Skills | references/background.md (verbatim) |

Release and onboarding checks read this SKILL.md for fixed phrases (`synthesis workspace ensure`, `.agents/workspace-AGENTS.md`, `onboard.sh`, the three tier names, `synthesis-grounding-discipline`, `cache-vs-truth`, `AGENTS.md`, `CLAUDE.md`, `synthesis-onboarding`). Binding rules 2, 3, 8 and 9 carry all of them.

## The 1.3.1 description

> Stand up and operate a low-cost, read-mostly companion session for ad hoc workspace lookups without pulling a focused project session off task. Every answer carries its source and a Verified, Cached, or Uncertain confidence tier. The workspace's tracked instruction source routes future sessions to the companion automatically. Bootstraps a missing personal knowledge workspace through the public synthesis CLI. Use for an FAQ assistant, quick-answers session, lookup companion, ask-me-anything session, fast Q&A project, or one-off lookup that is not the focused project's task. Not for deep project work, decisions, drafting, sending messages, or work that belongs in its own project.
