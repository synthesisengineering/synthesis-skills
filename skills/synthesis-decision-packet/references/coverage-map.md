# Coverage map: decision packet 1.8.0 to 2.0.0

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

## Existing reference files

Both keep their content. worked-example.md (over 150 lines) gained a short contents list after its opening paragraph; `scripts/test_build_packet.py` parsed its code blocks (since M3, `tests/test_packet_rulings.py` does), and the list adds none. review-assets.md is under 150 lines and was unchanged in the prose pass.

## Lines the coverage check reports, and why

Before this map was written, `v5-skill-coverage-check.py` reported 2 lines as not found verbatim (it now finds them only because this map quotes them), both moved from SKILL.md into references/ with a link adjusted for the deeper folder; the wording is unchanged:

- Inspect the actual material: `Read [the review-asset contract](references/review-assets.md) before constructing` now links `review-assets.md`.
- Retiring historical interfaces: `Read [artifact succession](../synthesis-context-lifecycle/references/artifact-succession.md)` now links `../../synthesis-context-lifecycle/references/artifact-succession.md`.

## The 1.8.0 frontmatter

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

## Scripts in v5 (M3)

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
