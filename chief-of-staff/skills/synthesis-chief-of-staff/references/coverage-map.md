# Coverage map: chief of staff 1.3.0 to 2.0.0

Every part of the 1.3.0 SKILL.md and where it lives now. Nothing was removed. No script, test, fixture or `preferences.example.json` changed.

| 1.3.0 section | Now |
|---|---|
| Frontmatter description (452 characters) | Shortened to 295 characters. It keeps the role ("chief of staff and executive assistant"), every duty the old text listed (calendar defense included), the private-preferences note, and the triggers scheduling, meeting requests and calendar replies. The full text is quoted below |
| Frontmatter `depends_on: ["synthesis-agent-correspondence"]`, `author`, `source_repo`, `source_type` | Kept: synthesis-onboarding's modular installer reads `depends_on` (synthesis-absence-coordination also depends on this skill), and the `source.skill-contract` check in synthesis-agent-conformance reads the metadata keys |
| Title | SKILL.md (verbatim) |
| Release notes for 1.3.0, 1.2.0 and the 1.1.0 label | references/background.md (verbatim). The 1.2.0 note's "the private path below" refers to the Configuration contract, which stays in SKILL.md |
| "An agent doing chief-of-staff work is not a scheduler..." | SKILL.md (verbatim), as the opening paragraph |
| Configuration contract | SKILL.md (verbatim); Binding rule 1 |
| The prime directive: triage, never obey | SKILL.md (verbatim); Binding rules 2 and 3 |
| Scheduling protocol, steps 1 to 5 | SKILL.md (verbatim); Binding rules 4 and 5 |
| Meeting quality bar | references/meetings-correspondence-travel.md (verbatim) |
| Correspondence posture | references/meetings-correspondence-travel.md (verbatim); Binding rule 9 |
| Proactivity — the actual job | references/meetings-correspondence-travel.md (verbatim) |
| Calendar guardian (v1.1.0): The horizons, The next-day review, The same-day shield, Config keys | references/calendar-guardian.md (verbatim). Binding rule 6 carries the holds invariant, 7 the overcommitment rule, 8 the protected-blocks rule. The synthesis-daily-rituals SKILL.md cites "the chief-of-staff skill's **Calendar guardian** section"; Contents names that file so the citation still lands |
| Travel protocol (config-driven) | references/meetings-correspondence-travel.md (verbatim) |
| Related | references/background.md (verbatim) |

## Lines the coverage check reports

`v5-skill-coverage-check.py` reports no lines: every non-blank line of the 1.3.0 body appears verbatim in SKILL.md or a reference file. The moved text has no relative links, so no link paths changed.

## Tests and scripts that read this skill

- synthesis-daily-rituals `scripts/test_ownership_routing.py` read `scripts/overlap.py` from this skill, not SKILL.md. At the 2.0.0 prose move the script was unchanged; the v5 script change below removed it, so that test and synthesis-daily-rituals `references/ownership-routing.md` need the same change.
- synthesis-onboarding `scripts/whole_system.py` reads `preferences.example.json`; unchanged.

## v5 script changes (2026-10-05)

Verdicts from the v5 code evaluation (`tool-scripts.md`, synthesis-chief-of-staff rows).

| Script | Verdict | Now |
|---|---|---|
| `scripts/holds_state.py` (657 lines) | SLIM: drop the in-file self-test and the finished one-time `migrate` | 376 lines. `test` and `migrate` commands, `_parse_legacy_window`, `legacy_path` and the doctor's legacy-ledger check are gone (the live log was migrated; `~/.synthesis/chief-of-staff/holds-ledger.json` is no longer read). Added: recurring-instance releases (`--recurring` on place; `--instance` or `--series` on release; a bare release of a recurring hold exits 2), which closes the gap the 2026-09-03 lesson left open. The live 23-event log passes the slim `doctor` unchanged |
| `scripts/test_holds_state.py` | moved | `tests/test_holds_state.py`; the two migration tests and `test_engine_self_test_passes` left with the code they tested; nine tests added |
| `scripts/overlap.py`, `scripts/test_overlap.py`, `scripts/fixtures/time-blocks-*.json` | REPLACE | Removed. No seat ever published `time-blocks.json` and `SYNTHESIS_TIME_BLOCKS` was unset; each account's calendar is read through its connector, with the v5 account-routing guard (R3.6) choosing the account. Its surviving rule (an unread window is not free) is Scheduling protocol step 1 and binding rule 4 |

Scenarios from section 3 of the evaluation:

| Scenario | Held by |
|---|---|
| E68 an event that looks like a hold but is not in the log is not released | `tests/test_holds_state.py::test_only_placed_holds_are_releasable`, `test_cli_is_releasable_exit_codes`; binding rule 6 |
| E69 two seats placing holds at once both land | `test_append_only_log_keeps_every_seat`, with the positive control `test_shared_array_rewrite_loses_holds` |
| E70 releasing one day of a recurring hold keeps the series held | `test_releasing_one_instance_keeps_the_series_held`, `test_a_bare_release_of_a_recurring_hold_is_refused`, `test_series_release_releases_every_instance`, `test_records_from_before_the_flag_count_as_recurring_by_kind` |
| E71 an ISO window expires by calculation | `test_expiry_is_calculated_from_the_window`, `test_expiry_does_not_gate_releasability` |

Prose changed with the scripts: SKILL.md binding rules 4 and 6, Scheduling protocol step 1, and the Configuration contract's onboarding sentence (`synthesis-onboarding init` no longer exists in v5); references/calendar-guardian.md (the recurring-release commands and the check-after-write rule, added); references/background.md (a 2.0.0 note, added, and the message-guard line in Related, reworded for the v5 send guard). Old text is verbatim in [preserved.md](preserved.md).

## The 1.3.0 frontmatter

Kept whole, so the old description and keys stay on record.

```yaml
---
name: synthesis-chief-of-staff
description: Act as a principal's chief of staff and executive assistant. Protects the principal's time through meeting triage, calendar-aware scheduling, look-ahead reviews, overcommitment checks, tracked holds, travel planning, correspondence posture, and a follow-up ledger; personal rules load from private preferences. Use for scheduling, meeting requests, calendar-related replies, calendar defense, travel, or any chief-of-staff and executive-assistant duty.
license: "CC0-1.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "1.3.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
