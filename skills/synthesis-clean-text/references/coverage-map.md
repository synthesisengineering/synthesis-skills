# Coverage map: clean text 2.0.0 to 3.0.0

Every part of the 2.0.0 SKILL.md and where it lives now. Nothing was removed or moved out of SKILL.md; `v5-skill-coverage-check.py` finds all 31 old lines verbatim.

| 2.0.0 section | Now |
|---|---|
| Frontmatter | Unchanged except `version` (2.0.0 to 3.0.0) and the added `format: v5`. The description stays as it was (296 characters). The whole 2.0.0 frontmatter is quoted below, because the writing-quality no-removals gate (`synthesis-content-quality/tests/test_no_removals.py`) requires every frozen line to survive in the skill folder |
| Opening paragraphs 1 and 2 | SKILL.md (verbatim); summarized in Binding rules 2 and 4 |
| Requirements | SKILL.md (verbatim); summarized in Binding rule 1 |
| Capability Boundary | SKILL.md (verbatim); summarized in Binding rule 3 |
| Rationale | SKILL.md (verbatim) |
| Application | SKILL.md (verbatim); summarized in Binding rules 1 and 5 |
| Related | SKILL.md (verbatim) |

## v5 script change (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-text-provenance/scripts/text_integrity_audit.py`) ruled KEEP and "move it into clean-text", which had no script of its own for its no-hidden-marker rule. `scripts/text_integrity_audit.py` (191 lines) moved here unchanged, with its five tests from synthesis-text-provenance's `scripts/test_provenance_tools.py` (IntegrityTests) as `tests/test_text_integrity_audit.py`, plus two command-line tests (scenario E88: each hidden character reported with its position, the text and its folder unchanged). SKILL.md gained binding rule 6 and "The character audit" with the exact command lines and output; nothing was removed, so the no-removals gate still finds every 2.0.0 line. The "Related" section's pointer to synthesis-text-provenance for "non-mutating text-integrity inspection" is a frozen line and stays; that skill now points back here for the audit.

## The 2.0.0 frontmatter, verbatim

Kept on record so the old description and metadata are not lost.

```yaml
---
name: synthesis-clean-text
description: "Enforce clean-text and no-hidden-marker requirements, audit inspectable characters and provenance, and state the verification boundary for statistical text marks. Use when generating clean text, checking hidden characters, addressing watermark concerns, or selecting a controlled generation path."
license: "CC0-1.0"
user-invocable: false
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "2.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
