# Coverage maps: anti-shortcuts

Read when checking where a rule of an earlier text lives now (ruling D8). Newest first: 2.2.0 to 2.3.0, the rewrite
to the repository's standard (`docs/skill-writing.md`), then the earlier map, 1.2.1 to 2.0.0 with its 2.0.1 change,
kept word for word one heading level down.

Contents:
- 2.2.0 to 2.3.0: SKILL.md; references/applying.md; where the binding rules state the moved sections; files
  unchanged
- 1.2.1 to 2.0.0 (v5): the section map, the existing reference files, scripts and tests, the v5 script changes, the
  lines the coverage check reports, the 1.2.1 frontmatter, and the 2.0.1 change
- The full description, word for word

## 2.2.0 to 2.3.0: the rewrite to the D8 standard

Every rule and requirement of the 2.2.0 SKILL.md, in its order, and where it lives in 2.3.0. **Kept**: the same
words in the same file. **Moved**: the same words in another file. **Reworded**: the same rule in new words, with
the old words in [preserved.md](preserved.md). **Merged**: two passages that said the same thing, now said once.
**Added**: a new sentence, with its source. Nothing was dropped. Binding rules keep their numbers, which other
documents ("§4–5") and the skill's evaluation cases cite; rules 1 to 8 still match methodology sections 1 to 8.

### SKILL.md

| 2.2.0 | 2.3.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `depends_on`, author, source, format, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Frontmatter `version: "2.2.0"` | `version: "2.3.0"` | Bumped: a minor version, since every binding rule keeps its number and meaning and no script interface changed. No script prints the skill's version and the skill keeps no release notes, so this map and preserved.md are the record of the change |
| Title | Title | Kept |
| Opening paragraph | Opening paragraph | Kept word for word |
| The line above rule 1: "Rules 1 to 8 carry the methodology section numbers other documents cite (for example "§4–5"). New rules are appended." | The line above rule 1, its first two sentences | Kept word for word |
| (none) | The line above rule 1, its last sentence: the user's own goals, decisions and grants govern within their scope; against other text (a brief, a report, a skill's default) these rules hold; say which applies and why, then do what it allows | Added (W8, format rule 11), from the skill's own text: rule 3's test (a phrase is legitimate only when the user asked to optimize for what it implies), methodology section 2 (the user's requested review cadence; "Verify the source and scope of authority rather than relying on a summary"), section 5 ("the user's standard is the relevant one") and section 7 (a guardrail is a permission the user withheld) |
| Rule 1: constraint-first; write the user's goals and non-goals (conversation, project context, workspace and global instructions) before generating approaches; a pro that violates one cannot appear | Rule 1 | Reworded to fix the evaluation's finding (W10, W14): the head as an action; the four sources, "before" and "a pro that violates one cannot appear" kept; the moments it governs, comparing approaches, planning and recommending; the output order, the analysis opening with the goals and non-goals before any recommendation, from constraint-first-protocol.md Step 2 ("The first section of the analysis is "Constraints""); the reason, from that file's "Why the Order Matters"; the stop, trivial work with one obvious option, from When NOT to Apply and the protocol's "When to Skip", with its "When in doubt, run the protocol" |
| Rule 2: decide what constraints decide; ask only when an unresolved choice belongs to the user; "Recommendation: X. Your call?" on a determined or delegated choice is the costume; execute and report | Rule 2 | Reworded (W5, W7): the head joins the first two sentences; the check before drafting a question for a constraint, decision or delegation that settles it, from methodology section 2's protocol; "execute and report" and the costume sentence kept, with the Pattern table's reason (offloading a constraint-determined decision back to the user); the user's own choices named as section 2 names them (product direction outside the delegated outcome, a preference that changes the promised result, stakeholder facts evidence cannot establish), asked with the consequence that makes the answer necessary, while independent authorized work continues, from section 2's last paragraph |
| Rule 3: scan for costume vocabulary in drafts and sub-agent reports; a phrase is legitimate only when the user asked to optimize for what it implies | Rule 3 | Reworded (W2, W5, W14, W16): the head names what it scans, every draft the agent writes or is asked to review and every sub-agent report (2.2.0 said "drafts", unqualified); the categories named from costume-vocabulary.md, since the Pattern table left SKILL.md, with example phrases from the table and the catalog; the test kept, with "explicitly or through standing constraints" from section 3; the reason, from background.md ("The substitution hides under reasonable-sounding vocabulary"); the stop, a use in quotes, in code or under discussion, from When NOT to Apply and the scanner paragraph; the scanner's command and exit code (W11, format rule 7) |
| Rule 4: dispatch briefs name the job at full size (no "keep changes minimal," "light touch," "surgical change") and carry at most five deliverables; scan every field the sub-agent reads before dispatch; on a hit, rewrite to the completeness required | Rule 4 | Reworded (W5, W7): every 2.2.0 element kept; the fields named, from sub-agent-hygiene.md, "Scan the Brief Before Every Dispatch", and the scope, any brief the agent writes or is asked to check; the reason, from section 4 (the brief's framing is the sub-agent's permission slip; an oversized brief runs out of budget and returns partial work; plan the split at dispatch time); "do not dispatch", the completeness required (the change wanted, its boundaries, the signal of completion) and the second scan, from that section's steps 1, 3 and 4 |
| Rule 5: audit every sub-agent return for the same costumes; if work was left undone, redirect the sub-agent or finish it; never propagate the deferral | Rule 5 | Reworded (W5): the head kept, with its moment, before accepting or reporting; the whole report read, tradeoffs and follow-ups included, and each hit judged by the user's standard rather than a reasonable engineer's, from section 5 and sub-agent-hygiene.md's acceptance checklist; "redirect the sub-agent or finish it" and "never propagate the deferral" kept; the exact gap, and a summary that matches what is done, from the checklist's steps 4 and 5 and Failure Mode 3; the reason, section 5's "Sub-agents inherit the same conservative defaults" |
| Rule 6: run the pre-response self-check (below) before any analysis, recommendation or plan ships | Rule 6 | Reworded (W2, W10): the head kept; the five steps of the Pre-Response Self-Check stated in the rule, since that section left SKILL.md (it stays word for word in methodology section 6); "the rewrite executes on the actual goal, not the safer-feeling reframe" kept, made concrete by the catalog's replacement framings for deferral (do the work, or name the blocker and who removes it); step 4's "constraint-neutral (item 2 above)" as "the constraints leave it open (rule 2)"; the reason, from background.md, "The Underlying Principle" |
| Rule 7: a capability gap is not a guardrail; never route around a guardrail; on a gap, name the failed mechanism, list alternatives and choose an authorized remedy before reporting | Rule 7 | Reworded (W2, W5, W7): the head says what to do; both kinds defined in section 7's words; the guardrail response (stop the dependent action, record what is needed, continue other authorized work) and the gap's four steps (name the mechanism, list alternative paths, separate what only the user can do, choose and verify an authorized remedy), from section 7; "never route around a guardrail" and "before reporting" kept; the reason, from section 7 (it wears the costume of discipline while delivering less than the task required) |
| Rule 8: grow the catalog; a new costume in production output becomes a case study, a catalog entry and, where useful, a scanner pattern | Rule 8 | Reworded to fix the evaluation's finding (W10, W14): the head as an action; production output named as the model meets it (a reply, a draft, a sub-agent report); the three products named with their files and what each holds, from section 8's steps 1 to 4, "where useful" as "if the scanner should catch it" (step 4); the test that checks a catalog entry, from step 4; the reason, from step 1 ("the documented teardown is the artifact that survives context loss") |
| Rule 9: delivery is part of completeness; finish the finite assignment, including authorized shipping; more audits or frameworks do not substitute for deliverables | Rule 9 | Reworded (W5): the head joins the 2.2.0 head's meaning and its first instruction; "more audits or frameworks" kept as the reason, with "revision instructions", from "Delivery is part of completeness"; from the same section, verification widened only for a concrete gap, a changed input or an explicit gate, defects fixed in the work touched without an open-ended redesign, and the limit that none of it permits omitting requested work, accepting a known failure, weakening a guard or deleting unresolved evidence |
| Contents: the methodology.md line | Contents | Reworded: "sections 1 to 8" for "methodology sections 1 to 8", and "Read it the first time a rule applies in a session, or when a case is unclear" for "Read it when applying a rule for the first time in a session or when a case is unclear": the same file and the same two triggers |
| (none) | Contents: the applying.md line | Added (format rule 4) |
| Contents: the costume-vocabulary.md, constraint-first-protocol.md, case-studies.md and background.md lines | Contents | Kept word for word |
| Contents: the sub-agent-hygiene.md line, "dispatch and acceptance rules, brief template, size cap, the pre-dispatch scan." | Contents | Reworded: "dispatch and acceptance in full, with the brief template."; the size cap and the pre-dispatch scan are stated in rule 4; the "Read it" sentence kept |
| Contents: the costume-catalog.json line, "the phrase catalog the scanner reads (id, pattern, category, exemptions, rationale, rewrite). Edit it when a new costume should fire automatically." | Rule 8 | Merged (format rule 11): rule 8 names the file, says when an entry goes in and what its test checks; the file is no longer linked from SKILL.md, so Contents does not list it. The field list is the file's own (its `schema` and every entry), and background.md's "How the Pieces Fit" and applying.md's scanner section name the file |
| Contents: the coverage-map.md and preserved.md lines | Contents, one line | Reworded for this rewrite, with when to read them |
| Contents: "When to Apply, The Pattern, Pre-Response Self-Check, The scanner: below." | (none) | Removed with the sections it named: each moved or merged (below), so nothing follows Contents |
| When to Apply, whole | references/applying.md | Moved word for word; the binding rules state it (below) |
| When NOT to Apply, whole | references/applying.md | Moved word for word; rules 1, 2 and 3 state it (below) |
| The Pattern, whole (heading and table) | references/methodology.md, The Pattern | Merged: methodology.md already held the same table word for word (the 2.0.0 restructure put it in both files); rules 2 and 3 state it |
| Pre-Response Self-Check, whole | references/methodology.md, section 6 | Merged: section 6 already held the same lead and steps word for word; rule 6 states it whole |
| The scanner, whole | references/applying.md, The scanner | Moved word for word; rule 3 names the command and its exit code. With every binding rule complete on its own, SKILL.md would have run past the room W19 leaves under 8,000 bytes, and format rule 3 moves whole passages rather than condensing them |

### references/applying.md

| 2.2.0 | 2.3.0 | How |
|---|---|---|
| (none) | Title and opening line: what the file holds, when to read it, and that the binding rules govern where a wording differs | Added (format rules 4 and 11) |
| SKILL.md: When to Apply, When NOT to Apply, The scanner | The same three sections, in the same order | Moved word for word |
| The scanner: "`--catalog <file>` (JSON; YAML needs PyYAML)" | "`--catalog <file>` (JSON or YAML)" | Corrected after the move, as its own change: the scanner reads a YAML catalog with the plugin's standard-library reader (its docstring: "`--catalog` also accepts a YAML catalog in the same shape"), as the v5 script changes below record (since 2026-10-06); the old words are in preserved.md, in the 2.2.0 SKILL.md |

### Where the binding rules state the moved sections

| Moved or merged passage | Stated in SKILL.md by |
|---|---|
| When to Apply: before a non-trivial implementation plan, design recommendation or multi-option analysis | Rules 1 and 6 |
| When to Apply: before accepting a sub-agent's report, above all one that self-flags a tradeoff | Rule 5 ("tradeoffs and follow-ups included") |
| When to Apply: before committing prose to public-facing artifacts | Rule 3 (every draft the agent writes or is asked to review) |
| When to Apply: when the user has said "complete this, no shortcuts," "best solution" or the like | Rule 3's test and the line above rule 1 |
| When to Apply: the pre-response self-check on any draft touching code, content or strategy | Rules 3 and 6 |
| When NOT to Apply: trivial single-line changes | Rule 1's last sentence |
| When NOT to Apply: constraint-neutral decisions where the user's input is required | Rule 2's second sentence |
| When NOT to Apply: teaching about shortcuts, quoted and discussion-mode usage | Rule 3's sentence on uses in quotes, in code or under discussion |
| The Pattern: the seven costumes | Rule 3's categories; rule 2 for asking as shortcut |
| Pre-Response Self-Check: steps 1 to 5 | Rule 6 |
| The scanner: the command line and exit codes | Rule 3's last sentence |

### Files unchanged

`references/methodology.md`, `references/costume-vocabulary.md`, `references/constraint-first-protocol.md`,
`references/sub-agent-hygiene.md`, `references/case-studies.md`, `references/background.md`,
`costume-catalog.json`, `scripts/scan_output.py`, `tests/test_scan_output.py` and `agents/openai.yaml`. In this
file, the earlier map below is kept word for word one heading level down; preserved.md keeps its earlier text the
same way.

## Coverage map: anti-shortcuts 1.2.1 to 2.0.0

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

### Existing reference files

costume-vocabulary.md, case-studies.md and sub-agent-hygiene.md are over 150 lines, so each gained a short contents list under its title; no other line changed. constraint-first-protocol.md is unchanged. The scanner's `see:` lines still name `case-studies.md#case-N`, and those case headings are unchanged.

### Scripts and tests

At the 2.0.0 prose move, `scripts/scan_output.py` and `scripts/test_scan_output.py` were unchanged. No test reads text from this SKILL.md.

### v5 script changes (2026-10-05)

The v5 code evaluation (`tool-scripts.md`, row `synthesis-anti-shortcuts/scripts/scan_output.py`) ruled SLIM: move the embedded catalog to a data file, keep about 350 lines of Python, and make the data file the one public catalog.

| Change | Where now | Test |
|---|---|---|
| 54 embedded catalog entries and the 8 category descriptions | `costume-catalog.json` at the skill root, generated from the old embedded list so every id, pattern, exemption, rationale, rewrite and `case_ref` is unchanged | `tests/test_scan_output.py::test_catalog_is_well_formed` |
| `df_for_now` pattern `\bfor now[,.\s]` | `\bfor now\b`, so a reply ending in "for now" is caught too | `test_for_now_is_flagged_at_the_end_of_a_reply` |
| Five deferral phrases the v5 Stop hook carried and the catalog lacked: `document-and-defer`, `execute or defer`, `defer this`, `deferred to`, `future fix needed` | New entries `df_document_and_defer`, `df_execute_or_defer`, `df_defer_this`, `df_deferred_to`, `df_future_fix_needed`; a new heading in references/costume-vocabulary.md, Category 4 | `tests/test_shortcut_catalog.py` (repository `tests/`) |
| One catalog, no drift | `synthesis/reply_check.py` keeps its built-in list for speed; `tests/test_shortcut_catalog.py` fails when any of its phrases is missing here | same |
| Scenario E89: a quoted or code use is discussion, a bare use is a costume | `scan_output.discussion_spans` skips matches inside double, curly or backtick quotes and fenced code, as `reply_check` does; per-entry `exempt_when` still applies | `test_quoted_or_code_use_is_exempt`, `test_bare_use_is_flagged` |
| `--catalog` needed PyYAML | Takes JSON or YAML; YAML reads through the plugin's standard-library reader (since 2026-10-06; before, it needed PyYAML) (Rajiv's private catalog at `~/.synthesis/anti-shortcut-catalog.yaml` keeps working until M4 folds it into v5 config) | `test_cli_exit_codes_and_report` |
| Duplicate ids and patterns that do not compile were accepted | Refused with exit 2 | `test_duplicate_ids_and_bad_patterns_are_refused` |
| `scripts/test_scan_output.py` | `tests/test_scan_output.py`, the seven Case 7 tests unchanged in substance plus the tests above | — |

Prose that named the embedded catalog changed in four places (references/background.md twice, references/methodology.md twice, references/costume-vocabulary.md once, and the scanner paragraph of SKILL.md). Each old sentence is verbatim in [preserved.md](preserved.md). Line counts: `scan_output.py` 991 before, 311 after; the catalog is 589 lines of JSON.

### Lines the coverage check reports, and why

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

### The 1.2.1 frontmatter

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

### Changed in 2.0.1 (2026-10-05)

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


## The full description

The description in SKILL.md's frontmatter was shortened to fit Claude Code's skill listing (BACKLOG C6, 2026-11-20); this is the full description it replaced, word for word.

```yaml
description: "Catch the lazy-shortcut antipattern: costume vocabulary that hides deferral, dismissal or false consultation. Constraint-first protocol, sub-agent dispatch and acceptance hygiene, pre-response self-check. Use to avoid shortcuts, audit for laziness, check for deferral or enforce the best solution."
```
