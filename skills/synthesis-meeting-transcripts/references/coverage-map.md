# Coverage map: meeting transcripts 0.14.0 to 1.0.0 (v5)

Read when checking where a rule of the 0.14.0 text lives now (ruling D8). Every part of the earlier 0.14.0 SKILL.md and where it lives now. The prose restructure removed nothing and changed no script; the M3 script pass (below) then applied the code verdicts, and every passage it replaced is verbatim in [preserved.md](preserved.md).

## Version

The prose restructure kept `version: "0.14.0"` because `verify_transcripts.py` and `extract_commitments.py` (and the cut `transcript_primary.py`) carried `SCRIPT_VERSION = "0.14.0"` and three tests required parity. In M3 the skill and both remaining scripts moved to 1.0.0 together; `tests/test_meeting_version_parity.py` and the version check in `tests/test_meeting_verify_transcripts.py` hold the parity.

| 0.14.0 section | Now |
|---|---|
| Frontmatter description (336 characters) | Shortened to 275 characters, keeping fetch notes and full transcripts into local markdown, primary-source verification before attribution, tool-agnostic Gmail/Drive MCPs or local exports, and every trigger verb: fetch, pull, sync, download, import, classify, verify. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `version`, `source_repo`, `source_type` | Kept unchanged; `version` for the reason above |
| Opening notes for 0.14.0 and 0.13.0 | references/release-notes.md (verbatim); Binding rules 2, 3 and 5 carry their live rules |
| "The earlier release notes and rationale are retained in... Before a declared-window sweep, read the mandatory acquisition evidence contract..." | SKILL.md, after the opening paragraph; in M3 the sentence pointing at the deleted acquisition evidence contract was removed (old line in preserved.md) |
| v0.5.3, v0.5.2, v0.5.1, v0.3.0, v0.2.0 | references/release-notes.md (verbatim, original order). The v0.5.2 note's "this file's frontmatter `version`" means SKILL.md's |
| v0.5.0: fail-closed enforcement, with the pre-commit hook script | references/transcript-primary-and-commit-gate.md (verbatim); Binding rules 4, 7 and 11 |
| v0.4.0: transcript-primary sourcing | references/transcript-primary-and-commit-gate.md (verbatim, placed first); Binding rules 4 and 8 |
| Title | SKILL.md (verbatim) |
| Opening paragraph ("A protocol for fetching AI-generated meeting transcripts...") | SKILL.md (verbatim) |
| Protocol versus config paragraph, and the tool-agnostic list | references/setup.md (verbatim), under a new "Protocol and config" heading |
| Configuration | references/setup.md (verbatim) |
| Prerequisites | references/setup.md (verbatim) |
| Protocol, Step 0: Declared-window sweep | SKILL.md (verbatim, whole, until M3, which replaced the two acquisition paragraphs with the window inventory, `fetch-meeting.py --window` and the `sync_watermark.py advance --surface meetings` rule; old lines in preserved.md); Binding rule 1. It stays because synthesis-daily-rituals `test_sync_watermark.py` reads the heading `### Step 0: Declared-window sweep` and the phrases "does not get a vote", "after fetching", "Enumerate the declared set", "unclosed gap" and "Account for every member" from this SKILL.md |
| Steps 1, 2, 3, the email warning, Steps 4, 4.5, 4.6, 4.7, 4.8, 5, 6 | references/protocol-steps.md (verbatim; in M3 the Step 3 tab-selection paragraph was restated for the folded selector, and Step 4.6 became the attribution reading rule in place of `transcript_primary.py`; old text in preserved.md); Binding rules 4 to 9 and 11. A one-line pointer after Step 0 in SKILL.md names the file |
| When Multi-Account Matters | references/setup.md (verbatim) |
| Date Verification | references/protocol-steps.md (verbatim); Binding rule 10 |
| Integration With synthesis-daily-rituals | references/protocol-steps.md (verbatim) |
| Why Tool-Agnostic Matters | references/setup.md (verbatim) |
| references/earlier-version-history.md | Unchanged (119 lines, so no contents list was needed) |

## Pointers from scripts

- `optional-workspace-mcp/fetch-meeting.py` now points at `synthesis-meeting-transcripts/references/setup.md` for the schema (it said SKILL.md).
- A comment in `verify_transcripts.py` asks for "a matching entry to SKILL.md's changelog" when output changes. The release notes live in references/release-notes.md and references/earlier-version-history.md.

## Scripts in v5 (M3)

Verdicts from the v5 code evaluation (tool scripts, meeting transcripts). Line counts are `wc -l`.

| Old file (lines) | Verdict | Now (lines) |
|---|---|---|
| `verify_transcripts.py` (492) | KEEP | Kept (505): version 1.0.0; its exact-file reader came from the cut daily-rituals acquisition module and is now local (`read_exact`); `from __future__ import annotations` added so Apple's Python 3.9 runs it |
| `extract_commitments.py` (178) | KEEP; make the docstring generic | Kept (180): the docstring tells the incident without names; version 1.0.0 |
| `transcript_primary.py` (461), `acceptance-suite.yaml`, `fixtures/` | CUT | Binding rule 8, Step 4.6, transcript-primary-and-commit-gate.md; fixtures verbatim in preserved.md |
| `optional-workspace-mcp/fetch-meeting.py` (678) | SLIM | Kept (351): fetch, tab selection by ID (folded `document_tabs.py`), an error is unknown, `--window` saved/unsaved listing; standard library only |
| `optional-workspace-mcp/mcp_client.py` (329) | SLIM | Kept (181): event parsing, nested error unwrapping, the 8 MiB cap; `urllib` instead of httpx; raw-capture custody dropped |
| `optional-workspace-mcp/document_tabs.py` (207) | SLIM, fold into fetch-meeting | `tab_inventory` and `select_transcript` in fetch-meeting.py |
| `optional-workspace-mcp/google_read.py` (174), `workspace_mcp_read.py` (241) | CUT | — |
| `start.sh`, `stop.sh`, `install-autostart.sh`, `uninstall-autostart.sh`, `doctor.sh` | KEEP, generic launchd label | Kept; label `com.synthesis.workspace-mcp`; doctor's account line no longer names the cut acquisition route |
| Tests (3,600 lines) | Kept where they test kept code | `tests/test_meeting_verify_transcripts.py`, `tests/test_meeting_extract_commitments.py`, `tests/test_meeting_version_parity.py`, `tests/test_workspace_mcp_doctor.py`, `tests/test_workspace_mcp_fetch.py`; the four `test_acquisition_*.py` files and `test_transcript_primary.py` went with the cut code |

## Edge cases and where each is held

| Scenario | Test (in `tests/`) or rule |
|---|---|
| E15 a summary-only save fails unless it carries the no-source marker | `test_meeting_verify_transcripts.py::test_e15_*`; the v0.5.0 commit gate in transcript-primary-and-commit-gate.md |
| E16 inline timestamps and a transcript heading without dialogue are incomplete | `test_e16_*` |
| E17 Plaud single-speaker and undiarized transcripts pass | `test_e17_*` |
| E18 `--only-incomplete` keeps the corpus total; a wrong or empty path exits 2 | `test_e18_*` |
| E19 `_*`, `gdoc-*`, `email-*` files are skipped and named | `test_e19_*` |
| E20 transcript by stable tab ID; distinct reasons for empty, missing, incomplete, ambiguous | `test_workspace_mcp_fetch.py::test_e20_*` |
| E21 an outer or nested tool error is unknown, never "no transcript" | `test_e21_*` |
| E22 the bookmark does not pass an unsaved doc, which the report names | `test_e22_*` |
| E23 commitment candidates listed with speaker and time; nothing created unconfirmed | `test_meeting_extract_commitments.py` (`test_gemini_bold_line_flags_shape`, `test_plaud_timestamp_is_captured`, `test_stamp_*`); binding rule 9 |
| E24 Gemini lines without timestamps take the preceding block's time | `test_meeting_extract_commitments.py::test_e24_a_gemini_time_carries_across_its_block_and_resets_at_a_section` |
| E25 a moved checkout is a stale service path (exit 1); unreadable state exits 2 | `test_workspace_mcp_doctor.py::test_e25_a_moved_checkout_is_a_stale_unit_path_defect`, `test_restricted_launchd_and_port_visibility_are_unknown` |
| E26 sparse launchd PATH and a recycled PID | `start.sh` (unchanged); `test_workspace_mcp_doctor.py::test_e26_sparse_path_finds_uvx_and_a_recycled_pid_is_not_a_running_server` |
| E27 attribution comes from the verbatim transcript or the passive form stays | Binding rule 8; protocol-steps.md Step 4.6; transcript-primary-and-commit-gate.md (v0.4.0 item 3) |

## Lines the coverage check reports

`v5-skill-coverage-check.py` reports no lines: every non-blank line of the 0.14.0 Markdown appears verbatim in SKILL.md or a reference file. None of the moved text had a relative link, so no link paths changed.

Since M3 the check reports two lines, deliberately: references/earlier-version-history.md, the v0.10.0 entry, the sentence about the spoken "of course" that sat in a filed transcript. The 0.14.0 lines named a private person and a personal event; this is a public repository (requirement R7.4, and section 5 item 7 of the tool-scripts evaluation), so the sentence now says "the principal's" and "a friend's memorial service" and the old lines are not quoted anywhere in the skill. They are readable with `git show origin/main:skills/synthesis-meeting-transcripts/SKILL.md` (the v0.10.0 note).

## Frontmatter before v5 (verbatim)

The 0.14.0 frontmatter, kept whole so the old description stays on record.

```yaml
---
name: synthesis-meeting-transcripts
description: "Fetch AI-generated meeting notes and full transcripts into local markdown files, and verify that an artifact is primary before it supports attribution-bearing claims. Tool-agnostic: works with Gmail/Drive MCPs and local transcript exports. Use when asked to fetch, pull, sync, download, import, classify, or verify a meeting transcript."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "0.14.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---
```
