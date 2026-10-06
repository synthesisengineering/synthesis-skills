# Coverage map: catch-up ledger 0.3.0 to 1.0.0

Every part of the 0.3.0 SKILL.md and where it lives now. Nothing was removed. The six protocol steps keep their numbers and headings. `catchup_scan.py` reads no text from SKILL.md and is unchanged; its command line is kept exactly as written. The version goes from 0.3.0 to 1.0.0, the next major version.

The ledger template's headings ("Do now", "Verify before re-adding", "Done late", "Expired", "Released") and table shapes are unchanged in references/protocol.md, so synthesis-console's ledger parser is unaffected.

| 0.3.0 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters, keeping its trigger words: missed and pending commitments, catch-up ledger, post-vacation catch-up, what did I miss |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title | SKILL.md (verbatim) |
| "**Version 0.3.0** (2026-08-14)" line | references/background.md (verbatim) |
| Consumer note (v0.2.0) | references/protocol.md (verbatim), under a new "Console consumer note" heading; binding rule 9 |
| The problem | references/background.md (verbatim) |
| What this skill produces | SKILL.md (verbatim paragraph); the heading became a lead-in sentence, because the purpose paragraph must come before Binding rules |
| Design rationale (thinking-framework summary) | references/background.md (verbatim) |
| Classification taxonomy | SKILL.md (verbatim); binding rules 3 and 6 |
| When to run | SKILL.md (verbatim) |
| Protocol, Steps 1 to 6, with the ledger template | references/protocol.md (verbatim); binding rules 1, 2, 4, 5, 7, 8 and 11; step names and the scan command repeated in SKILL.md under Protocol in brief |
| Tone requirements for the ledger | references/protocol.md (verbatim); binding rule 10 |
| Configuration | references/protocol.md (verbatim) |
| Relationship to neighboring skills | references/background.md (verbatim); its "Run syncs BEFORE the sweep" is repeated in Protocol in brief, Step 3 |

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports 1 line as not found verbatim: the heading "## What this skill produces". It was replaced by the sentence "Reconcile what was promised against what happened after a break in the daily-ritual cadence. What this skill produces:", which leads into the same paragraph, verbatim. A `##` heading there would come before Binding rules, which the format forbids.

## The 0.3.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-catchup-ledger
description: "Reconcile pending, missed, and incomplete commitments after any gap in the daily-ritual cadence (travel, family visits, crunch weeks). Sweeps daily plans, transcripts, and project context over an arbitrary window; classifies every surfaced item (including expired-for-learning); produces a dated catch-up ledger document; routes survivors without flooding the daily plan. Use when asked to: catch up on missed tasks, sweep pending items, catch-up ledger, reconcile backlog, what did I miss, post-vacation catch-up, falling behind recovery."
license: "CC0-1.0"
depends_on: ["synthesis-daily-rituals", "synthesis-project-management", "synthesis-context-lifecycle"]
metadata:
  author: "Rajiv Pant"
  version: "0.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
