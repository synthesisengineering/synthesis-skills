# Coverage map: anti-shortcuts 1.2.1 to 2.0.0

Every part of the 1.2.1 SKILL.md and where it lives now. Nothing was removed.

| 1.2.1 section | Now |
|---|---|
| Frontmatter description (long keyword list) | Shortened to under 300 characters; keeps the core triggers (avoid shortcuts, audit for laziness, check for deferral, enforce best solution) and names the constraint-first protocol, sub-agent hygiene and self-check |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type`, `license` | Kept (the modular installer and the source checks read them); version bumped to 2.0.0; `format: v5` added |
| Title | SKILL.md (verbatim) |
| Three opening paragraphs | references/background.md, "Why this exists" (verbatim); a one-paragraph summary opens SKILL.md |
| When to Apply, When NOT to Apply | SKILL.md (verbatim) |
| The Pattern | references/methodology.md (verbatim); the costume table is also in SKILL.md (verbatim) |
| Delivery is part of completeness | references/methodology.md (verbatim); binding rule 9 distills it |
| The Methodology, sections 1 to 8 | references/methodology.md (verbatim, numbering unchanged); binding rules 1 to 8 distill them with the same numbers, because other documents cite "§4–5" |
| 6. Pre-Response Self-Check | SKILL.md, "Pre-Response Self-Check" (verbatim body) and references/methodology.md (verbatim) |
| How the Pieces Fit | references/background.md (verbatim) |
| Relationship to Other Skills | references/background.md (verbatim apart from link paths) |
| The Underlying Principle | references/background.md (verbatim) |
| (new) The scanner | SKILL.md: the exact command line, what it prints and its exit codes, taken from the docstring of `scripts/scan_output.py` (format rule 7) |

## Existing reference files

costume-vocabulary.md, case-studies.md and sub-agent-hygiene.md are over 150 lines, so each gained a short contents list under its title; no other line changed. constraint-first-protocol.md is unchanged. The scanner's `see:` lines still name `case-studies.md#case-N`, and those case headings are unchanged.

## Scripts and tests

At the 2.0.0 prose move, `scripts/scan_output.py` and `scripts/test_scan_output.py` were unchanged. No test reads text from this SKILL.md.

## v5 script changes (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-anti-shortcuts/scripts/scan_output.py`) ruled SLIM: move the embedded catalog to a data file, keep about 350 lines of Python, and make the data file the one public catalog.

| Change | Where now | Test |
|---|---|---|
| 54 embedded catalog entries and the 8 category descriptions | `costume-catalog.json` at the skill root, generated from the old embedded list so every id, pattern, exemption, rationale, rewrite and `case_ref` is unchanged | `tests/test_scan_output.py::test_catalog_is_well_formed` |
| `df_for_now` pattern `\bfor now[,.\s]` | `\bfor now\b`, so a reply ending in "for now" is caught too | `test_for_now_is_flagged_at_the_end_of_a_reply` |
| Five deferral phrases the v5 Stop hook carried and the catalog lacked: `document-and-defer`, `execute or defer`, `defer this`, `deferred to`, `future fix needed` | New entries `df_document_and_defer`, `df_execute_or_defer`, `df_defer_this`, `df_deferred_to`, `df_future_fix_needed`; a new heading in references/costume-vocabulary.md, Category 4 | `tests/test_shortcut_catalog.py` (repository `tests/`) |
| One catalog, no drift | `synthesis/reply_check.py` keeps its built-in list for speed; `tests/test_shortcut_catalog.py` fails when any of its phrases is missing here | same |
| Scenario E89: a quoted or code use is discussion, a bare use is a costume | `scan_output.discussion_spans` skips matches inside double, curly or backtick quotes and fenced code, as `reply_check` does; per-entry `exempt_when` still applies | `test_quoted_or_code_use_is_exempt`, `test_bare_use_is_flagged` |
| `--catalog` needed PyYAML | Takes JSON; YAML still loads when PyYAML is installed (Rajiv's private catalog at `~/.synthesis/anti-shortcut-catalog.yaml` keeps working until M4 folds it into v5 config) | `test_cli_exit_codes_and_report` |
| Duplicate ids and patterns that do not compile were accepted | Refused with exit 2 | `test_duplicate_ids_and_bad_patterns_are_refused` |
| `scripts/test_scan_output.py` | `tests/test_scan_output.py`, the seven Case 7 tests unchanged in substance plus the tests above | — |

Prose that named the embedded catalog changed in four places (references/background.md twice, references/methodology.md twice, references/costume-vocabulary.md once, and the scanner paragraph of SKILL.md). Each old sentence is verbatim in [preserved.md](preserved.md). Line counts: `scan_output.py` 991 before, 311 after; the catalog is 589 lines of JSON.

## Lines the coverage check reports, and why

Thirteen lines of the 1.2.1 SKILL.md are not carried over verbatim in the live text; `v5-skill-coverage-check.py` reported them until this block quoted them. Each is text moved from SKILL.md into references/ with its wording unchanged and only a relative link target adjusted, because a link written for SKILL.md breaks one directory down (`references/x.md` became `x.md`, `../synthesis-x/...` became `../../synthesis-x/...`). Eight are in references/methodology.md, five in references/background.md. The lines below are exactly as 1.2.1 had them, with links written for SKILL.md's folder, kept only as a record.

````markdown
Each costume sounds reasonable in isolation. Each is the same shortcut wearing different clothes. The full catalog with rationale per phrase lives in [`references/costume-vocabulary.md`](references/costume-vocabulary.md).
A worked example, including the constraint-extraction order and the forbidden-criteria mapping, lives in [`references/constraint-first-protocol.md`](references/constraint-first-protocol.md).
Two question shapes look alike but behave differently. Check both whether the user's stated constraints determine the answer and who owns the remaining choice. The shared [decision-ownership contract](../synthesis-thinking-framework/references/decision-ownership.md) distinguishes already-decided choices, delegated technical choices, material principal ambiguity and human-only actions.
The full per-phrase catalog with category, rationale, and replacement framings lives in [`references/costume-vocabulary.md`](references/costume-vocabulary.md). The operational extract is in `scripts/scan_output.py`.
Full dispatch protocol lives in [`references/sub-agent-hygiene.md`](references/sub-agent-hygiene.md).
The scanner at `scripts/scan_output.py` automates step 1. The classification at step 2 is judgment; the catalog at [`references/costume-vocabulary.md`](references/costume-vocabulary.md) supports it.
3. Update [`references/costume-vocabulary.md`](references/costume-vocabulary.md) with the new entry.
The methodology stays stable. The catalog refreshes as the failure modes evolve. The anonymized case studies in [`references/case-studies.md`](references/case-studies.md) are the durable record of where each entry came from.
- **[synthesis-grounding-discipline](../synthesis-grounding-discipline/SKILL.md)** — The truth-side companion. This skill catches output that does less than the work requires; grounding discipline catches output that claims more than the evidence supports — confabulated events, quotes with no tool-surfaced source, stale cached facts, absences established by a broken probe. One output can fail both at once: a fabricated "already handled" is a shortcut and a grounding failure in the same sentence.
- **[synthesis-thinking-framework](../synthesis-thinking-framework/SKILL.md)** — Foundational reasoning methodology. The constraint-first protocol is a specialization of first-principles thinking applied to the option-evaluation step.
- **[synthesis-code-planning](../synthesis-code-planning/SKILL.md)** — Multi-approach evaluation for code tasks. This skill's constraint-first protocol slots in as the first step before the approach-generation step in code-planning.
- **[synthesis-implementation-integrity](../synthesis-implementation-integrity/SKILL.md)** — Post-implementation verification. This skill catches shortcuts before they're built; implementation-integrity catches incomplete work after it's built. Use both.
- **[synthesis-content-quality](../synthesis-content-quality/SKILL.md)** — AI-pattern detection in prose. Different domain (prose patterns vs decision patterns) but a similar shape — both maintain a catalog that grows as failure modes evolve.
````

## The 1.2.1 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-anti-shortcuts
description: "Discipline for catching the lazy-shortcut antipattern in AI-assistant output. Makes the costume vocabulary explicit so agents recognize when their drafts have slid into deferral, dismissal, or false consultation. Includes the constraint-first protocol, sub-agent dispatch and acceptance hygiene, and a pre-response self-check. Use when asked to: avoid shortcuts, audit for laziness, check for deferral, enforce best solution, no shortcuts, anti-shortcut, constraint-first, sub-agent hygiene, costume vocabulary."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework"]
metadata:
  author: "Rajiv Pant"
  version: "1.2.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

## Changed in 2.0.1 (2026-10-05)

`synthesis-agent-guardrails` 2.0.0 retired the PreToolUse hook `sub_agent_brief_scanner.py`
and listed its rules under "What moves to synthesis-anti-shortcuts" in its preserved.md.
The generic ones now live here as prose; no private catalog, block log or calibration
example came with them.

| Rule from the retired hook | Now |
|---|---|
| Scan a dispatch brief before dispatch: its `prompt`, `instructions`, `message`, `task` or `description` | [sub-agent-hygiene.md](sub-agent-hygiene.md), Part 1, "Scan the Brief Before Every Dispatch"; binding rule 4 |
| On a hit, block the dispatch and revise the brief to specify the completeness required, not the minimization of effort | Same section, steps 1, 3 and 4 |
| The block reason lists each phrase with its category, severity and rewrite hint | Same section, step 2: category and rewrite framing, the fields the public catalog carries (`costume-catalog.json` has no severity field; severities were in the private catalog) |
| Blocking a dispatch is not a harm-class action under R3.5, so this is skill prose, not a hook | Same section, last paragraph |

Binding rule 4 gained one sentence; the Contents line for sub-agent-hygiene.md and that
file's own contents line name the new section. The three 2.0.0 lines are verbatim in
[preserved.md](preserved.md#replaced-in-201-2026-10-05). Version 2.0.0 became 2.0.1. The
escalation policy and the private phrase catalog listed in the same guardrails section are
not part of this change.

