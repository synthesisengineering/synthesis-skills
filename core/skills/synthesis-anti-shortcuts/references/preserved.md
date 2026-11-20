# Preserved text: anti-shortcuts, replaced on 2026-10-05 and in 2.3.0

Read this only to review what a rewrite replaced. The passages below are no longer instructions; they are kept
word for word so the reasoning stays readable (ruling D8).

Contents:
- Retired in 2.3.0, the rewrite to the D8 standard: why each part of SKILL.md changed, then the 2.2.0 SKILL.md
  word for word
- Anti-shortcuts: preserved text: the sentences replaced on 2026-10-05, when the catalog moved out of the scanner
  and in 2.0.1, word for word one heading level down

## Retired in 2.3.0: the rewrite to the D8 standard

2.3.0 rewrote the skill's SKILL.md to the repository's rewrite standard, `docs/skill-writing.md` (writing rules W1
to W19). Every rule's new place is in [coverage-map.md](coverage-map.md). A passage moved word for word to another
file is recorded there; the whole 2.2.0 SKILL.md is below all the same, so every word of it stays readable in one
place.

### SKILL.md

Why each part changed:

- **The line above rule 1.** Its two sentences on rule numbering are kept. New (W8, format rule 11): the user's own
  goals, decisions and grants govern within their scope, and against other text, such as a brief, a report or
  another skill's default, the rules hold, answered by saying which rule applies and why, then doing what it
  allows. It states what the skill already held: rule 3's test, methodology section 5's "the user's standard is
  the relevant one", section 2's review cadence and its check of the source and scope of authority, and section
  7's guardrail, a permission the user withheld.
- **Binding rules 2, 4, 5, 7 and 9.** Rewritten to W5 (the action as the bold head, then the scope, the reason and,
  where the skill has one, the stop) and made complete on their own (W2), each from the methodology section its
  number names or the reference that expands it, so none needs another file to be applied. Rule 2 names the
  choices that are the user's in section 2's words and keeps independent authorized work going while one waits.
  Rule 4 names the brief fields to scan and what a rewritten brief states, from sub-agent-hygiene.md. Rule 5 names
  its moment, before accepting or reporting, and a summary that matches what is done, from the acceptance
  checklist and its Failure Mode 3. Rule 7 defines both kinds of failure and the gap's four steps, from section 7.
  Rule 9 carries the bound on verification and the limits of "Delivery is part of completeness". Each
  coverage-map row names what of the 2.2.0 rule was kept.
- **Binding rule 1.** The evaluation found it the weakest rule on Opus. On its case (as-01: compare approaches for
  renaming a helper in a project whose instructions say backward compatibility is not a goal), Opus passed 1 of 4
  checks with the skill, as it did without it, because its answers recommended before stating the goals and
  non-goals; Sonnet with the skill passed 4 of 4. In 2.2.0 the rule said to write them "before generating
  approaches" but not where they go in the answer, and the answers that failed opened with a recommendation. The
  rule now names the moments it governs (comparing approaches, planning, recommending) and the output order, the
  analysis opening with the goals and non-goals before any recommendation, from constraint-first-protocol.md Step
  2 (W10, W14). Its stop, trivial work with one obvious option, comes from When NOT to Apply and the protocol's
  "When to Skip", with that section's "when in doubt" kept, so the stop is no wider than the skill already had it.
  No capitals or stronger wording were added (W10).
- **Binding rule 3.** The Pattern table left SKILL.md, so the rule names the catalog's categories itself, with
  example phrases from the table and the catalog, and states its scope as the model meets it (W14, W16): every
  draft the agent writes or is asked to review, and every sub-agent report. The discussion exemption, from When
  NOT to Apply and the scanner paragraph, is now in the rule (W2). On the evaluation's near-miss case (as-06:
  explain in exactly two sentences why "for now" deserves a second look), Sonnet's answers with the 2.2.0 text ran
  to three sentences in both repetitions, which the analysis put down to sampling, since the text the model saw
  was unchanged; the exemption now names that kind of request, someone asking about shortcut language (W15). The
  scanner's command and exit code are named (W11, format rule 7).
- **Binding rule 6.** It pointed to the self-check "(below)", a section that has left SKILL.md, so the rule states
  the five steps itself (W2). On its cases (as-05 and as-09) the skill scored 4 or 5 of 6 on each model, and the
  one dip the analysis examined it traced to the judge: a rewrite of the status draft that left its date and
  blocker as placeholders passed once and failed once. The rule keeps "execute on the actual goal, not the
  safer-feeling reframe" and makes it concrete with the catalog's replacement framings for deferral: do the work,
  or name the real blocker and who removes it (W10).
- **Binding rule 8.** It scored 0 of 2 in every condition. On its case (as-12: a phrase the catalog lacks, in a
  sub-agent's report), every answer proposed a catalog entry and a case study, and the check wanted the files
  changed; the analysis puts this down to the harness, which gave the skill conditions only a file reader. The rule
  now names the three files and what each entry carries, from methodology section 8, so a proposed change is
  complete and an agent that can write makes it (W10, W14).
- **Contents.** Lists references/applying.md with when to read it, and the two records on one line. The
  methodology.md and sub-agent-hygiene.md lines say the same in fewer words (same files, same triggers). The
  costume-catalog.json line is merged into rule 8, which names the file and when an entry goes in (format rule
  11); the file is no longer linked from SKILL.md. The line pointing to the sections below went with them.
- **When to Apply, When NOT to Apply, The scanner.** Moved word for word to references/applying.md, under a title
  and an opening line that say the binding rules govern. With every binding rule complete on its own, SKILL.md
  would have run past the room W19 leaves under 8,000 bytes, and format rule 3 moves whole passages rather than
  condensing them.
- **The scanner's `--catalog` flag.** After the move, references/applying.md says "(JSON or YAML)" for "(JSON;
  YAML needs PyYAML)": the scanner has read a YAML catalog with the plugin's standard-library reader since
  2026-10-06 (coverage map, v5 script changes), so the old words no longer described it. They are in the 2.2.0
  SKILL.md below.
- **The Pattern, Pre-Response Self-Check.** methodology.md already held both word for word (The Pattern, and
  section 6), so the SKILL.md copies are merged into those (format rule 11); rules 2, 3 and 6 state them.

The 2.2.0 SKILL.md, verbatim:

````markdown
---
name: synthesis-anti-shortcuts
description: "Catch the lazy-shortcut antipattern: costume vocabulary that hides deferral, dismissal or false consultation. Constraint-first protocol, sub-agent dispatch and acceptance hygiene, pre-response self-check. Use to avoid shortcuts, audit for laziness, check for deferral or enforce the best solution."
license: "Apache-2.0"
depends_on: ["synthesis-thinking-framework"]
metadata:
  author: "Rajiv Pant"
  version: "2.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: core
---

# Synthesis Anti-Shortcuts

Catches the draft that looks like good engineering but quietly substitutes a lower-effort path after the user asked for the best solution, hidden under reasonable-sounding vocabulary ("for now," "minimal diff," "backward compatible," "out of scope"). This skill names those costumes and gives the protocol to strip them out.

## Binding rules

Rules 1 to 8 carry the methodology section numbers other documents cite (for example "§4–5"). New rules are appended.

1. **Constraint-first.** Write the user's goals and non-goals (conversation, project context, workspace and global instructions) before generating approaches; a pro that violates one cannot appear.
2. **Decide what constraints decide.** Ask only when an unresolved choice belongs to the user. "Recommendation: X. Your call?" on a determined or delegated choice is the costume; execute and report.
3. **Scan for costume vocabulary** in drafts and sub-agent reports. A phrase is legitimate only when the user asked to optimize for what it implies.
4. **Dispatch briefs name the job at full size** (no "keep changes minimal," "light touch," "surgical change") and carry at most five deliverables. Scan every field the sub-agent reads before dispatch; on a hit, rewrite to the completeness required.
5. **Audit every sub-agent return** for the same costumes. If work was left undone, redirect the sub-agent or finish it; never propagate the deferral.
6. **Run the pre-response self-check** (below) before any analysis, recommendation or plan ships.
7. **A capability gap is not a guardrail.** Never route around a guardrail; on a gap, name the failed mechanism, list alternatives and choose an authorized remedy before reporting.
8. **Grow the catalog.** A new costume in production output becomes a case study, a catalog entry and, where useful, a scanner pattern.
9. **Delivery is part of completeness.** Finish the finite assignment, including authorized shipping; more audits or frameworks do not substitute for deliverables.

## Contents

- [references/methodology.md](references/methodology.md): the full pattern, "Delivery is part of completeness" and methodology sections 1 to 8. Read it when applying a rule for the first time in a session or when a case is unclear.
- [references/costume-vocabulary.md](references/costume-vocabulary.md): every phrase with category, rationale and replacement framing. Read it to classify a hit or rewrite a costume.
- [references/constraint-first-protocol.md](references/constraint-first-protocol.md): the five-step protocol and a worked example. Read it before a multi-option analysis.
- [references/sub-agent-hygiene.md](references/sub-agent-hygiene.md): dispatch and acceptance rules, brief template, size cap, the pre-dispatch scan. Read it before dispatching or accepting a sub-agent.
- [references/case-studies.md](references/case-studies.md): the incidents each entry came from; scanner `see:` lines point here. Read it when a hit's origin matters.
- [references/background.md](references/background.md): why the pattern happens, how the pieces fit, sibling skills, the underlying principle. Read once per session.
- [costume-catalog.json](costume-catalog.json): the phrase catalog the scanner reads (id, pattern, category, exemptions, rationale, rewrite). Edit it when a new costume should fire automatically.
- [references/coverage-map.md](references/coverage-map.md): where each part of the 1.2.1 text and each script change now lives (ruling D8).
- [references/preserved.md](references/preserved.md): sentences replaced when the catalog moved out of the scanner, verbatim. Read only to review the change.
- When to Apply, The Pattern, Pre-Response Self-Check, The scanner: below.

## When to Apply

- Before generating any non-trivial implementation plan, design recommendation, or multi-option analysis
- Before accepting a sub-agent's report — especially when the sub-agent self-flags a tradeoff
- Before committing prose to public-facing artifacts where reputation is at stake (READMEs, blog posts, marketing copy, OSS docs)
- Before responding when the user has explicitly stated "complete this, no shortcuts," "best solution," or equivalent
- As part of a pre-response self-check on any draft that touches code, content, or strategy

## When NOT to Apply

- Trivial single-line changes where the implementation is obvious
- Genuine constraint-neutral decisions where the user's input is actually required (e.g., product direction, scheduling, stakeholder facts the agent cannot know)
- Discussions where the agent is teaching about shortcuts, not committing one (the skill recognizes quoted and discussion-mode usage)

## The Pattern

| Costume | Surface presentation | What it actually is |
|---|---|---|
| Backward compatible | "Shim layer; preserves old paths; existing tests pass unchanged." | Avoiding the work of updating consumers. |
| Minimal diff | "I left residual X for minimal diff; the rest can be a follow-up." | Half-applied work labeled as scope discipline. |
| Asking as shortcut | "Recommendation: X. Your call?" | Offloading a constraint-determined decision back to the user. |
| Deferral | "For now, let's... can revisit later... as a first pass..." | Pushing real work to a future session that may never happen. |
| Archive value | "Leave the stale block; it has historical reference value." | Avoiding deletion work; git history already does this job. |
| Dismissal | "Not a pain point today. Theoretical concern. Doesn't bite hard." | Predicting away a user-raised concern instead of solving it. |
| Scope excuse | "Pre-existing; out of scope; not introduced by this change." | Avoiding fix-while-touching in code being actively modified. |

## Pre-Response Self-Check

Before sending any draft analysis, recommendation, or implementation plan:

1. Scan the draft for costume vocabulary across all seven categories.
2. For each match, classify: real constraint or costume?
3. For each costume, rewrite. The rewrite executes on the actual goal, not the safer-feeling reframe.
4. If the draft ends with a question, verify the question is constraint-neutral (item 2 above).
5. Only then send.

## The scanner

`python3 scripts/scan_output.py draft.md` (or text on stdin) prints each hit by category: line and column, the matched phrase, why it is a shortcut, a rewrite framing and a `see:` case. Exit 0 clean, 1 detections, 2 error. Flags: `--json`, `--quiet` (exit code only, for hooks), `--context 120`, `--category <name>`, `--catalog <file>` (JSON; YAML needs PyYAML). It reads `costume-catalog.json`, the one public catalog, and skips phrases quoted or in code, since those are being discussed. The v5 Stop hook checks every reply against a short built-in subset of the same catalog.
````

## Anti-shortcuts: preserved text

Sentences replaced on 2026-10-05 when the phrase catalog moved out of
`scripts/scan_output.py` into `costume-catalog.json` (v5 code verdict: SLIM, "move
the catalog to a data file and make it the one catalog"). Each is kept verbatim
with the file it came from; the replacement sits at the same place in that file.

### references/background.md, "Why this exists"

This skill is the methodology. The operational catalog in `scripts/scan_output.py` is the extract — a phrase scanner that any agent or pipeline can run against draft output. The detailed catalog with rationale, the constraint-first protocol with a worked example, the sub-agent dispatch and acceptance rules, and the anonymized case studies all live in `references/` and load on demand.

### references/background.md, "How the Pieces Fit"

```
   |-- scripts/scan_output.py                Standalone scanner (Python 3, stdlib + pyyaml)
```

### references/methodology.md

The full per-phrase catalog with category, rationale, and replacement framings lives in [`references/costume-vocabulary.md`](costume-vocabulary.md). The operational extract is in `scripts/scan_output.py`.

4. Update `scripts/scan_output.py` if the embedded catalog should detect the phrase.

### references/costume-vocabulary.md, "How the Catalog Maintains Itself"

3. Add the phrase to the scanner's embedded catalog in [`../scripts/scan_output.py`](../scripts/scan_output.py) if it should fire automatically.

### SKILL.md, "The scanner"

`python3 scripts/scan_output.py draft.md` (or text on stdin) prints each hit by category: line and column, the matched phrase, why it is a shortcut, a rewrite framing and a `see:` case. Exit 0 clean, 1 detections, 2 error. Flags: `--json`, `--quiet` (exit code only, for hooks), `--context 120`, `--catalog <file.yaml>` (needs PyYAML).

### scripts/scan_output.py docstring (the parts that changed)

Zero required external dependencies — Python 3.8+ stdlib is sufficient. The
optional --catalog flag accepts a YAML file (requires PyYAML); without it,
the scanner uses an embedded baseline catalog.

  # Use a custom catalog (requires PyYAML)
  ./scan_output.py --catalog ~/.synthesis/anti-shortcut-catalog.yaml draft.md

The embedded catalog's header said: "Mirrors the phrase set in the public
anti-shortcut catalog. Public references point at case-studies.md within this
skill rather than at incident-specific lesson files. The catalog can be
overridden by passing --catalog <yaml>." The phrase set is unchanged in
`costume-catalog.json`, with the additions listed in the coverage map.

### Replaced in 2.0.1 (2026-10-05)

The final v5 sweep added the pre-dispatch brief scan that `synthesis-agent-guardrails`'
retired `sub_agent_brief_scanner.py` enforced as a hook (which fields of a brief to scan,
and what to do on a hit) to [sub-agent-hygiene.md](sub-agent-hygiene.md) as prose. Two
lines that listed what the skill holds changed to name it. The 2.0.0 lines, verbatim:

```text
4. **Dispatch briefs name the job at full size** (no "keep changes minimal," "light touch," "surgical change") and carry at most five deliverables.
- [references/sub-agent-hygiene.md](references/sub-agent-hygiene.md): dispatch and acceptance rules, brief template, size cap. Read it before dispatching or accepting a sub-agent.
- Part 1: Dispatch (principle, phrases that should not appear, replacement framing, brief template, size cap)
```

