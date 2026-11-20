# Coverage maps: decision packet

Read when checking where a rule of an earlier text lives now (ruling D8). Newest first: 2.4.0 to 2.5.0, the
rewrite to the repository's standard (`docs/skill-writing.md`), then the 1.8.0 to 2.0.0 map with its later
entries, kept word for word one heading level down.

Contents:
- 2.4.0 to 2.5.0: SKILL.md; the references; where the binding rules state the passages that left SKILL.md;
  files unchanged
- 1.8.0 to 2.0.0 (v5): the section map; existing reference files; lines the coverage check reports; the 1.8.0
  frontmatter; scripts in v5 (M3), with the replaced prose of 2.0.1

## 2.4.0 to 2.5.0: the rewrite to the D8 standard

Every rule and requirement of the 2.4.0 SKILL.md, in its order, and where it lives in 2.5.0. **Kept**: the same
words in the same file. **Moved**: the same words in another file. **Reworded**: the same rule in new words, with
the old words in [preserved.md](preserved.md). **Merged**: two passages that said the same thing, now said once.
**Added**: a new sentence, with its source. Nothing was dropped. Binding rules keep their numbers, which the
skill's evaluation cases cite.

### SKILL.md

| 2.4.0 | 2.5.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `depends_on`, author, format, source, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Title | Title | Kept |
| Opening paragraph: "When N unresolved decisions belong to the principal, collecting them one at a time scales poorly. The measurement that produced this skill is blunt: **26 rounds of per-item conversation produced 0 of 30 decisions. One packet produced 30 of 30, in one pass, in one paste.**" | references/background.md, The origin measurement | Moved: the same words already stand there, moved from 1.8.0; the story of the measurement leaves SKILL.md (format rule 12, W19) |
| (none) | Opening paragraph, first sentence: "Collects five or more parallel decisions from a principal in one sitting." | Added (format rule 2): what the skill is for, from the description and When to use it |
| "**The property to preserve above all others: the principal's cost scales with the number of *sittings*, not the number of *items*.**" | Opening paragraph, second sentence | Kept word for word, without its bold (W13); background.md also keeps it |
| "Rules 1 to 6 are the six load-bearing properties in their original order, so "the sixth load-bearing property" still resolves; new rules are appended." | This map; references/authoring.md's contents ("The six load-bearing properties (binding rules 1 to 6 in full)") | Reworded: a note on numbering, which W6 now makes the rule for every skill; rules 1 to 6 keep their order, so the phrase still resolves |
| (none) | The line above rule 1: the rules protect the principal's decisions and their record, so they hold against a contrary request; say which rule applies and why, then do what it allows | Added (W8, format rule 11), from the skill's own text: rule 2's "never pre-select it", rule 9's "never hand-author rows or hand-edit generator output", rule 12's non-authorizing record and rule 14's "only a recorded ruling closes one" |
| Rule 1: "**Self-contained rows:** item, recommendation, reasoning, link. The principal never leaves the packet to decide." | Rule 1 | Reworded (W2, W5): the head as an action naming all four parts ("a link to the underlying artifact" in authoring.md's property 1); "never leaves the packet to decide" kept as the reason; the exception a blind row makes, from authoring.md's Blind rows and When NOT to use it ("unless it is blind"), with the definition `build_packet.py` sends readers to SKILL.md for ("where a recommendation would sway a judgment that must be theirs") |
| Rule 2: "**Mark the recommendation on the control; never pre-select it.** A packet that opens decided reports decisions nobody made." | Rule 2 | Reworded (W5): "on its button" for "on the control"; the reasons from authoring.md's property 2 ("Agreeing costs one click"; it "cannot distinguish "I agreed" from "I never looked""); "reports decisions nobody made" kept |
| Rule 3: "**A free-text note box on every row,** beside the buttons. Never force the principal into your option set." | Rule 3 | Reworded (W5, W12): the head says what to do; "never forced into your option set" kept as the reason |
| Rule 4: "**Local persistence keyed by exact spec and item.** A change anywhere in the spec starts fresh choices." | Rule 4 | Reworded (W5): the head as an action, "Save choices locally, keyed to the exact spec and item"; the second sentence kept, with its reason from authoring.md's property 4 ("an old click cannot silently acquire a new meaning") |
| Rule 5: "**The packet generates the paste-able summary,** so the person never composes the structure." | Rule 5 | Reworded (W5, W14): the head as an action, taking the answers as the generated summary, pasted back; "never composes the structure" kept as the reason; the input it does not take named, the principal's own wording (a chat reply, meeting notes), read as text and not recorded, from filing-and-authority.md ("read it as text") and its narrative sources that close nothing |
| Rule 6: "**File in the owning project's `resources/artifacts/`, never only as a chat artifact:** `build_packet.py --file-into` files spec and page; `record_rulings.py` files the rulings." | Rule 6 | Reworded (W5): the spec, page and rulings named in the head; both commands kept, each with `--file-into`, as filing-and-authority.md runs them; the reason from authoring.md's property 6 (a chat artifact is readable by one client in one conversation, the project directory by every agent working the project and by the next session) |
| Rule 7: "**Only decisions that belong to the principal.** Execute constraint-determined choices and resolve delegated technical choices yourself." | Rule 7 | Reworded to stand on its own (W2): the head as an action; both executions kept; which choices become rows, stated in the decision-ownership contract's own terms (a choice that would materially change the outcome and that the principal's instructions and goals leave open, or one only they can make) in place of When to use it's link into synthesis-thinking-framework, which the evaluation harness cannot open (the baseline report's finding on code-planning's link to the same file); the reason from that contract (a decided or delegated choice put back hands back work); When to use it's "Honor an explicit supervised review request" as the stop |
| Rule 8: "**The reader contract: a packet is a stranger-read document.** Name the `audience`, use plain labels, state `impact` both ways, label options by what pressing them does, gloss terms of art, and build every packet for a principal with `--strict-reader`." | Rule 8 | Reworded with care (W10, W14): on Opus at the pinned baseline it passed 5 of 6 checks. Every element kept, each named as the author meets it in the spec, from authoring.md's reader contract: a plain label with an internal ID only as a chip, context saying what the thing is in the reader's words, `impact` both ways spelled out, never a bare Yes or No, a one-clause gloss; what `--strict-reader` refuses, from the same section; the reason, the 0-of-15 measurement stated as what goes wrong (format rule 12) |
| Rule 9: "**Generate from a data array; never hand-author rows or hand-edit generator output.** `synthesis doctor` flags unverifiable packet pages in its *decision packets* check." | Rule 9 | Reworded (W5, W11): the head names the generator and keeps "data array", "never hand-author rows" and "hand-edit generator output"; what to do instead (edit the spec and rebuild); the check that enforces it, `synthesis doctor`'s *decision packets* check, with what it flags, from enforcement.md; the reason from enforcement.md ("Thirty hand-written blocks drift") |
| Rule 10: "**Surface disagreement and prior positions with exact sources; never converge first,** and recommend against your own prior work where that is true." | Rule 10 | Reworded (W5): "Show" for "Surface"; the two spec blocks named (`disagreement` with who holds each side, `prior_position` with its source), from authoring.md; "recommend against your own prior work where that is true" kept; the reasons from authoring.md's content requirements (a false consensus; a packet that only argues one way loses the buttons' trust) |
| Rule 11: "**Open every generated packet before handing it over.** Both permanent defects were found by loading the page, not reading the source." | Rule 11 | Reworded (format rule 14): the head kept; the named check (punctuation renders cleanly; Copy summary says what it did), from enforcement.md's two fixtures; the reason kept |
| Rule 12: "**A recorded ruling authorizes nothing** (`authorization.granted: false`). The action owner checks principal, scope and exact target before acting." | Rule 12 | Reworded with the most care (W7, W10, W14): the weakest rule at the pinned baseline (Opus 0 of 2, dp-11). The head as an action; `authorization.granted: false` kept, with its reason from filing-and-authority.md's Action authority (a forged paste records the same); the trigger named as the model meets it, acting on any chosen row, with illustrative actions; the checks kept (the principal's authority, the current scope, the exact target) and where they are checked, with the principal or another authentic source, from the same section; what goes ahead without a new confirmation, a grant already given within its scope, from When to use it. No capitals or stronger wording added (W10) |
| Rule 13: "**Show the complete material** for correspondence, code, images, media or documents in `review_assets`; external references are never fetched." | Rule 13 | Reworded (W5, W12): the head keeps every element; "never a summary and a link" names the failure to avoid, from authoring.md ("Put the complete artifact there"); "the page never fetches an external reference" kept as the reason, with "the principal approves what they see" from review-assets.md ("The reader should see the complete material before deciding") |
| Rule 14: "**Unanswered decisions carry forward by exact id; only a recorded ruling closes one.** `carry_forward.py` writes the successor spec, and refuses a reconciliation with missing, extra or duplicate ids or a narrative "answered" with no ruling recorded against the exact spec." | Rule 14 | Reworded (W5, W14): the head as an action, both halves kept; the narrative sources named (meeting notes, a chat message) from filing-and-authority.md; the reason, a narrative records no choice; both commands kept with their flags |
| Rule 15: "**Keep the reading path short:** changes against the reviewed `baseline`, material once, messages as their words, wire copies as `reference`, settled items in `handled`. On Codex, ask in the final reply, never only in a question card." | Rule 15 | Reworded (W5, W14): every item kept; the reason in the head, "short enough to decide from alone", from authoring.md ("decide from the reading path alone"); the Codex sentence names its scope, any question for the principal, and gains "or a filed packet" and its reason (a card "disappears when the turn ends") from authoring.md's "Asking in Codex" |
| Contents: eight reference lines and "When to use it, When NOT to use it, Use: below." | Contents | Reworded: shorter link text and descriptions; every reference keeps a "Read it" line; background.md's line names When to use it; coverage-map.md and preserved.md share one line; the sections line names the one section left below |
| When to use it, whole | references/background.md, When to use it | Moved word for word, its one link one folder deeper; rules 7 and 12 state its first paragraph (below) |
| When NOT to use it, whole | When NOT to use it | Kept word for word: the evaluation cases check it as SKILL.md's limits (2.4.0 passed every such check on both models), and `build_packet.py` sends readers to "the anti-trigger in SKILL.md" |
| Use: the command block | references/filing-and-authority.md, Use | Moved: the same block already stands there word for word; rules 6, 9 and 14 name each script |
| Use: "What each command prints: [references/filing-and-authority.md](references/filing-and-authority.md)." | Contents: the filing-and-authority.md line, "every command and what it prints" | Merged |

### The references

| 2.4.0 | 2.5.0 | How |
|---|---|---|
| background.md: opening line and contents list | The same, naming When to use it and when to read the file, board messages (`synthesis msg`) in place of the handoff queue retired in 2.0.1, and the changelog's current range | Reworded (navigation only) |
| (none) | background.md: When to use it | Moved from SKILL.md (above), under an added opening line saying where it came from and that rules 7 and 12 govern where a wording differs (format rule 11) |
| authoring.md: contents list of five sections | The same, with "Blind rows" and "A comfortable reading path", sections the file already held | Added (format rule 3) |
| review-assets.md: 177 lines with no contents list | A contents list after its opening paragraphs, naming its six sections | Added (format rule 3: a linked file over 100 lines opens with its own contents list) |
| preserved.md: title, opening paragraph, contents list | The title names 2.5.0; a new first paragraph; the contents list gains the 2.5.0 section and the 2.1.0 section it lacked | Reworded (navigation only); the M3 opening paragraph kept word for word |
| (none) | preserved.md: Retired in 2.5.0 | Added: why each part of SKILL.md changed, then the 2.4.0 SKILL.md word for word |
| This file: "# Coverage map: decision packet 1.8.0 to 2.0.0" and its sections | The same, one heading level down, under a title, opening line and contents list for both maps | Kept word for word |

### Where the binding rules state the passages that left SKILL.md

| Passage, now in a reference | Stated in SKILL.md by |
|---|---|
| When to use it: "First apply [decision ownership](...)" and "Packets collect decisions that actually belong to the principal (binding rule 7)." | Rule 7, which states the decision-ownership classes |
| When to use it: "Honor an explicit supervised review request." | Rule 7: "unless they explicitly asked to review it" |
| When to use it: "Existing user grants remain usable within their scope; the new record format does not require the user to repeat them." | Rule 12: "A grant the principal already gave stays usable within its scope, without being repeated." |
| When to use it: "Load when you owe your principal **five or more parallel decisions of the same shape** ..." | The opening paragraph's first sentence; When NOT to use it, which SKILL.md keeps |
| When to use it: "Natural fits: ..." | Contents: background.md's line ("Read it when unsure a packet fits") |
| The origin measurement | The opening paragraph's second sentence, the property it measured |
| Use: the command block | Rules 6 (`build_packet.py --file-into`, `record_rulings.py --file-into`), 9 (`build_packet.py`) and 14 (`carry_forward.py --successor`, `--check`); Contents: the filing-and-authority.md line |

### Files unchanged

`references/filing-and-authority.md`, `references/enforcement.md`, `references/worked-example.md`, `scripts/`,
`assets/`, `tests/` and `agents/openai.yaml`.

## Coverage map: decision packet 1.8.0 to 2.0.0

Every part of the 1.8.0 SKILL.md and where it lives now. Nothing was removed. The six load-bearing properties keep their order as binding rules 1 to 6.

Text that scripts and tests depend on stays in SKILL.md: `build_packet.py` sends readers to "the anti-trigger in SKILL.md" (When NOT to use it, kept verbatim), to "the reader contract in SKILL.md" and to "SKILL.md requires this" for `--strict-reader` (binding rule 8 states both, and the full contract is in references/authoring.md). `synthesis-project-management/scripts/test_handoff.py` asserts SKILL.md names `synthesis-project-management/scripts/handoff.py`; the Contents line for background.md names it. Every command, flag and path is kept exactly as written.

| 1.8.0 section | Now |
|---|---|
| Frontmatter description (long) | Shortened to under 300 characters, keeping its trigger words: five or more decisions, review, migration, upgrade, triage, backlog |
| Frontmatter `depends_on`, `author`, `source_repo`, `source_type` | Kept (the installer and source checks read them) |
| Title | SKILL.md (verbatim) |
| "**Version 1.7.0** (2026-09-26)" line | references/background.md (verbatim, with a note that the frontmatter said 1.8.0) |
| Opening measurement paragraph | SKILL.md and references/background.md (verbatim) |
| Shape table, "The failure is not that the principal lacks information" | references/background.md (verbatim) |
| "The property to preserve above all others" | SKILL.md and references/background.md (verbatim) |
| When to use it, including Natural fits | SKILL.md (verbatim); binding rule 7 |
| When NOT to use it | SKILL.md (verbatim) |
| The six load-bearing properties | references/authoring.md (verbatim); binding rules 1 to 6 |
| Inspect the actual material | references/authoring.md (verbatim apart from one link path); binding rule 13 |
| Prior positions and contrary evidence | references/authoring.md (verbatim); binding rule 10 |
| Content requirements | references/authoring.md (verbatim); binding rule 10 |
| The reader contract (v1.1.0) | references/authoring.md (verbatim); binding rule 8 |
| Use, including File it, Record what came back, note whitespace, schema-2 records, idempotent imports | references/filing-and-authority.md (verbatim); the command block also stays in SKILL.md |
| Provenance and action authority | references/filing-and-authority.md (verbatim); binding rule 12 |
| Enforcement (v1.5.0), Generate from a data array, what the generator refuses | references/enforcement.md (verbatim); binding rule 9 |
| Two defects that are permanent fixtures | references/enforcement.md (verbatim); binding rule 11 |
| Relationship to other skills | references/background.md (verbatim) |
| Changelog | references/background.md (verbatim) |
| Related | references/background.md (verbatim) |
| Retiring historical interfaces | references/filing-and-authority.md (verbatim apart from one link path) |

### Existing reference files

Both keep their content. worked-example.md (over 150 lines) gained a short contents list after its opening paragraph; `scripts/test_build_packet.py` parsed its code blocks (since M3, `tests/test_packet_rulings.py` does), and the list adds none. review-assets.md is under 150 lines and was unchanged in the prose pass.

### Lines the coverage check reports, and why

Before this map was written, `v5-skill-coverage-check.py` reported 2 lines as not found verbatim (it now finds them only because this map quotes them), both moved from SKILL.md into references/ with a link adjusted for the deeper folder; the wording is unchanged:

- Inspect the actual material: `Read [the review-asset contract](references/review-assets.md) before constructing` now links `review-assets.md`.
- Retiring historical interfaces: `Read [artifact succession](../synthesis-context-lifecycle/references/artifact-succession.md)` now links `../../synthesis-context-lifecycle/references/artifact-succession.md`.

### The 1.8.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-decision-packet
description: Collect many parallel decisions from a principal in one sitting instead of one per turn. Generates a self-contained HTML packet — one row per decision carrying the item, the agent's recommendation, the reasoning, and a link — with buttons labeled by what pressing them does, the consequence under each button, a per-row note box, local persistence, and a paste-able summary the principal returns in a single message; files the spec, the page, and the returned rulings in the owning project's resources/artifacts/ so every agent on the project can read them. Use when you owe five or more decisions of the same shape; when a review, migration, upgrade, triage, or backlog pass has produced a list someone must rule on; or when a per-item conversation is burning round-trips.
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.8.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```

### Scripts in v5 (M3)

The script pass of 2026-10-05 applied the evaluation's verdicts (`tool-scripts.md`, synthesis-decision-packet rows; edge cases E42 to E54). Line counts are `wc -l`.

| Old script (lines) | Verdict | Now (lines) | What replaced it |
|---|---|---|---|
| `scripts/build_packet.py` (1,687) | SLIM | `scripts/build_packet.py` (571) + `assets/packet-template.html` (762) + `assets/spec-schema.txt` (98) | The HTML, CSS and JavaScript template and the `--schema` text moved to `assets/` unchanged, so pages are byte-identical (checked on the worked example and six live specs). Kept: the reader contract (`--strict-reader`, `audience`, `impact`, bare-label refusal naming the accepted form), consequence labels, review assets with their full contract, the summary and local persistence keyed by spec digest and item, `--file-into`, `--date`, `--schema`, `--stdout`, `-o`, `--allow-small` and the marker `<!-- synthesis-decision-packet spec-sha256:... -->`. Dropped: input-file custody (`read_packet_input`), the retired-spec check that imported `record_succession` (`assert_active_spec`), the big-integer check. `-o` now overwrites its working copy. Why it is above the 350-line estimate: the review-asset validation (about 150 lines) is kept whole, because specs filed on 2026-10-05 carry review assets and the recorder validates the spec on every paste. |
| `scripts/record_rulings.py` (529) | SLIM | `scripts/record_rulings.py` (295) | Kept: spec-bound parsing (the binding line's digest must equal the current spec's), refusals that quote what was received (never a note's text), `--spec`, `--file-into`, `--date`, `--stdout`, the schema-2 record with `authorization.granted: false`, bulk labels, `parse_summary(text, spec)` and `compose_summary(spec, state)` for `synthesis-context-lifecycle/scripts/record_succession.py`. Dropped: legacy-format parsing and `--legacy-unbound`, `--provenance` and the `provenance` block, `spec.file_sha256`, `summary_sha256`. Added to the record: `spec_file`, `storage_blocked`. |
| (none) | NEW (R5.3) | `scripts/carry_forward.py` (186) | The exact-id carry-forward rule ported from `synthesis-context-lifecycle/scripts/record_succession.py` (`_review` and `decision_status`): `--successor` writes the unanswered rows, `--check` refuses missing, extra or duplicate ids and an "answered" item without a ruling recorded against the exact spec. No receipts, input hashes, custody or transactions. |
| `scripts/test_build_packet.py` (1,295) | REWRITTEN | `tests/test_packet_build.py` (374), `tests/test_packet_rulings.py` (266) | Generator and recorder tests rewritten for the slim scripts. |
| `scripts/test_spec_binding.py` (314) | REWRITTEN | `tests/test_packet_rulings.py` | Changed-meaning refusals (E50), malformed bindings, revisions keep earlier files. Provenance and legacy-read tests went with those features. |
| `scripts/test_packet_causal.py` (119) | REWRITTEN | `tests/test_packet_rulings.py` | Positive control, changed meaning, duplicate rows, mismatched label, unknown option, no authority, prior position kept in the ruling. |
| `scripts/test_review_assets.py` (447) | REWRITTEN | `tests/test_packet_build.py`, `tests/test_packet_rulings.py` | Material embedded and never fetched (E52), refusals, envelope, unavailable rows take no choice. Input-custody, succession-owner and context-doctor-reader tests went with that machinery. |
| `scripts/test_note_whitespace.py` (123) | REWRITTEN | `tests/test_packet_rulings.py::test_note_whitespace_tolerance_applies_only_to_notes`, `tests/test_packet_browser.py` | Note transport tolerance; the browser-to-recorder path. |
| `scripts/test_browser_packet.py` (190) | REWRITTEN | `tests/test_packet_browser.py` (124) | Drives the page in headless Chromium: fresh state, copy status, notes, bulk, blocked storage, awkward ids, script text. Skips when no Chromium is present (the old test failed instead). |
| `scripts/test_review_assets_browser.py` (115) | CUT | `tests/test_packet_build.py::test_e52_review_material_is_embedded_and_nothing_is_fetched` | Its two-width reader walk needed a browser on every run; the generated-bytes test holds the contract. |
| `scripts/test_corpus_browser.py` (85) | CUT | none in this skill | It drove the corpus-review page of `synthesis-agent-conformance/scripts/provider_intake.py`, which belongs to that skill. |

| Edge case | Test that holds it |
|---|---|
| E42 fresh packet: nothing selected, recommendation marked on its control | `tests/test_packet_build.py::test_e42_a_fresh_packet_selects_nothing_and_marks_the_recommendation_on_its_control`; `tests/test_packet_browser.py::test_e42_e45_e47_e48_the_real_page` |
| E43 "Yes" / "Approve" refused under `--strict-reader`, accepted form named | `tests/test_packet_build.py::test_e43_bare_labels_are_refused_under_strict_reader_with_the_accepted_form` |
| E44 ids that collide after browser coercion refused | `tests/test_packet_build.py::test_e44_ids_that_collide_after_browser_coercion_are_refused` |
| E45 storage blocked: the paste alone records every decision and says so | `tests/test_packet_rulings.py::test_e45_a_storage_blocked_paste_alone_records_every_decision_and_says_so`; the browser test's `storage-blocked` case |
| E46 bulk acceptance labelled | `tests/test_packet_rulings.py::test_e46_bulk_acceptance_is_labelled_in_the_paste_and_in_the_record`; the browser test |
| E47 copy reports at once on every path | `tests/test_packet_build.py::test_e47_copy_selects_first_reports_synchronously_and_reports_on_every_path`; the browser test |
| E48 `</script>` in spec text leaves the script block intact | `tests/test_packet_build.py::test_e48_spec_text_cannot_close_the_script_block`; the browser test's `awkward-ids-and-script-text` case |
| E49 line break in title, label or id refused | `tests/test_packet_build.py::test_e49_a_line_break_in_title_label_or_id_is_refused` |
| E50 changed option meaning: old paste refused | `tests/test_packet_rulings.py::test_e50_an_old_paste_is_refused_when_the_spec_changed_after_the_answer` |
| E51 mismatched rows or options refused quoting what was received; a valid paste filed beside spec and page | `tests/test_packet_rulings.py::test_e51_rows_or_options_that_do_not_match_are_refused_quoting_what_was_received`, `::test_e51_a_valid_paste_is_filed_beside_the_spec_and_page` |
| E52 review material inspectable inside the packet, nothing fetched | `tests/test_packet_build.py::test_e52_review_material_is_embedded_and_nothing_is_fetched` |
| E53 fewer than five rows flagged | `tests/test_packet_build.py::test_e53_fewer_than_five_rows_is_flagged_and_needs_allow_small` |
| E54 curly quotes and dashes survive; charset in the first bytes | `tests/test_packet_build.py::test_e54_charset_is_declared_in_the_first_bytes_and_typography_survives` |
| R5.3 carry-forward by exact id | `tests/test_packet_carry_forward.py` (`test_r53_*`, eight tests) |

Replaced prose, each kept verbatim in [preserved.md](preserved.md):

- filing-and-authority.md, schema-2 record sentence on digests and claimed provenance: preserved.md, "Claimed provenance and input digests in the record".
- filing-and-authority.md, "Provenance and action authority" heading and the `--provenance` paragraph: same section; the heading is now "Action authority".
- filing-and-authority.md, the `--legacy-unbound` paragraph: preserved.md, "Legacy unbound summaries".
- filing-and-authority.md, `--out` preserving existing bytes: preserved.md, "`-o` preserving existing bytes".
- filing-and-authority.md, "Retiring historical interfaces": preserved.md, same heading; now "Carrying unanswered decisions forward".
- enforcement.md, the context doctor's `skill-outputs` paragraph: preserved.md, "The context doctor's `skill-outputs` check".
- enforcement.md and worked-example.md, `scripts/test_build_packet.py`; review-assets.md, the browser fixture list: preserved.md, "Test file names".
- review-assets.md, stable regular spec files: preserved.md, "Input-file custody for spec files".
- worked-example.md, the rulings file and its provenance paragraph: preserved.md, "The worked example's rulings file before M3" and "Claimed provenance and input digests in the record".
- SKILL.md Contents and background.md, "the handoff queue (`synthesis-project-management/scripts/handoff.py`)": preserved.md, "The handoff queue" (2.0.1, final v5 sweep). Now "board messages between agents (`synthesis msg`)"; `handoff.py` was replaced by `synthesis msg` with a brief file. background.md's Changelog gained a 2.0.1 entry; version 2.0.0 became 2.0.1.
- SKILL.md binding rule 9, "The context doctor fails unverifiable packet pages.": preserved.md, "The context doctor in binding rule 9" (2.0.1). Now "`synthesis doctor` flags unverifiable packet pages in its *decision packets* check", matching enforcement.md.

