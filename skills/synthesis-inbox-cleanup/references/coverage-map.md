# Coverage map: inbox cleanup 1.6.2 to 2.0.0

Every part of the 1.6.2 SKILL.md and where it lives now. Nothing was removed. The prompt-injection rules keep their numbers 1 to 8, so any citation of "Rule N" still resolves: binding rule N in SKILL.md summarizes it and references/injection-rules.md holds it in full. No script or test reads text from SKILL.md; every command, flag and path is kept exactly as written.

| 1.6.2 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters, keeping its trigger words: clean up inbox, sweep email, categorize senders, build email rules, archive promotions, set up Gmail filters |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `platform` | Kept (the installer and source checks read them) |
| Title and the two opening paragraphs | SKILL.md (verbatim) |
| v1.6.2, v1.6.0, v1.5.0 and v1.4.0 notes | references/release-notes.md (verbatim); the v1.6.0 impersonation rule is binding rule 13 |
| Architecture: public engine, private rules | references/setup-and-scoping.md (verbatim) |
| Workspace scoping | references/setup-and-scoping.md (verbatim); binding rule 12 |
| When to invoke this skill, When NOT to invoke | SKILL.md (verbatim) |
| Three tool stacks, one methodology | references/workflow.md (verbatim apart from one link path) |
| The categorization taxonomy | references/workflow.md (verbatim); binding rule 10 |
| The workflow, steps 1 to 6, Microsoft 365 and outlook.com, Gmail paths A and B | references/workflow.md (verbatim apart from link paths); binding rules 9, 11 and 14 |
| Prompt-injection defenses, Rules 1 to 8 | references/injection-rules.md (verbatim apart from one link path); binding rules 1 to 8 |
| Pitfalls table | references/workflow.md (verbatim apart from one link path) |
| Setup | references/setup-and-scoping.md (verbatim apart from one link path) |
| License, Author | references/release-notes.md (verbatim) |

## Existing reference files

All five keep their content. Short contents lists were added at the top of the three over 150 lines: manifest-schema.md, pitfalls.md and prompt-injection-defenses.md. `scripts/sanitize.py` and `tests/run_poisoned.py` cite references/prompt-injection-defenses.md by path; it stays where it was.

## Lines the coverage check reports, and why

`v5-skill-coverage-check.py` reports 5 lines as not found verbatim. Each is a line moved from SKILL.md into references/ whose relative link gained the change a move one folder down needs: `references/x.md` targets became `x.md` and `templates/x` became `../templates/x`. The wording is unchanged.

- Three tool stacks: "The methodology — census new senders, draft a plan, apply with dry-run-first — is the same across all three..."
- Gmail: "**Path B — server-side filters:** the LLM agent uses `manage_gmail_filter`..."
- Prompt-injection defenses: "See [`references/prompt-injection-defenses.md`]... for the full threat model, attack vectors, and design rationale."
- Pitfalls: "The IMAP substring pitfall and the circumstantial-inference pitfall are documented in detail in [`references/pitfalls.md`]..."
- Setup: "For Gmail and M365 setup details, see [`references/three-tool-stacks.md`]..."

## The 1.6.2 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-inbox-cleanup
description: "Manifest-driven email inbox cleanup across three tool stacks: iCloud / generic IMAP via Python + YAML rules; Microsoft 365 + outlook.com via Mail.app AppleScript; Gmail via workspace-mcp Gmail API and server-side filters. Engine is public; per-user rules live privately at ~/.synthesis/inbox-cleanup/. Ships with prompt-injection defenses (sanitization module + adversarial test fixtures) for any LLM-augmented path. Use when asked to: clean up inbox, sweep email, categorize senders, build email rules, archive promotions, set up Gmail filters, build email cleanup automation."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.6.2"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  platform: "macOS (Apple Silicon and Intel)"
---
```
