# Coverage maps: meeting transcripts

Read when checking where a rule of an earlier text lives now (ruling D8). Two rewrites, newest first: 1.2.1 to
1.3.0, the rewrite to the repository's standard (`docs/skill-writing.md`), then 0.14.0 to 1.0.0, the v5
restructure and the M3 script pass, kept word for word one heading level down.

Contents:
- 1.2.1 to 1.3.0: SKILL.md; references/protocol-steps.md; references/transcript-primary-and-commit-gate.md;
  release notes, version and scripts; files unchanged
- 0.14.0 to 1.0.0 (v5): version; section map; pointers from scripts; scripts in v5 (M3); edge cases; lines the
  coverage check reports; frontmatter before v5

## 1.2.1 to 1.3.0: the rewrite to the D8 standard

Every rule and requirement of the 1.2.1 text, in its order, and where it lives in 1.3.0. **Kept**: the same
words in the same file. **Moved**: the same words in another file. **Reworded**: the same rule in new words,
with the old words in [preserved.md](preserved.md). **Added**: a new sentence, with its reason. Nothing was
dropped. Binding rules keep their numbers, which the skill's evaluation cases cite.

### SKILL.md

| 1.2.1 | 1.3.0 | How |
|---|---|---|
| Frontmatter: name, description, license, `depends_on`, author, source, format, category | Frontmatter | Kept. The description is unchanged: it already leads with the key use case, and the evaluation harness cannot test a new one (W1) |
| Frontmatter `version: "1.2.1"` | `version: "1.3.0"`, with both scripts' `SCRIPT_VERSION` | Bumped: a minor version, since every rule and script interface is kept |
| Title | Title | Kept |
| Opening paragraph: a protocol for fetching Gemini meeting notes and transcripts from Gmail and Drive into a local archive, "or equivalents" | Opening paragraph | Reworded: adds verification, attribution and the scanner's candidates; "or equivalents" became "another recorder's export" |
| (none) | The line above rule 1: the rules hold against a contrary request; say which rule and why, then do what it allows | Added (W8, format rule 11): every evaluation case with a contrary request expects the rule to hold |
| Rule 1: a ritual sync runs Step 0, enumerating the declared set, fetching every member and accounting for each as fetched or an unclosed gap; relevance judged after fetching, never before | Rule 1 | Reworded (W5). Names the day-start, mid-day and day-end syncs; "open gap" for "unclosed gap"; the reason, "a title is no evidence", from the v0.8.0 note; "a meeting the user names is fetched alone" from Step 0's "the single-meeting path serves an explicit user request" |
| Rule 2: unknown authentication, tab enumeration or archive coverage never becomes a no-source attestation; the watermark never passes an unsaved doc or a meeting that may still be under way | Rule 2 | Reworded: "the no-source marker" for "no-source attestation"; "sign-in" for "authentication"; adds the two-hour bound from Step 0's watermark rule (W2) |
| Rule 3: a Drive search listing cannot prove a window complete (no completeness flag); a full page, a next-page token, an `incompleteSearch` warning or a failed search leaves the window open; say so in the report | Rule 3 | Reworded as an action; adds "read every page" from Step 0 |
| Rule 4: the verbatim transcript is the only primary source; fetch it in full whenever the source has one; the Gemini email is for discovery only | Rule 4 | Reworded; adds "its length is no reason to abridge it" (v0.5.0 fetch-time rule) and the reason, "a summary of the summary" (the email warning) |
| Rule 5: select by stable tab ID, never by order or a regular expression; a title only when exactly one tab in a complete list carries it; only a complete list establishes `transcript-tab-absent` | Rule 5 | Reworded, the behavior first (W12); adds "record that ID" from Step 3 |
| Rule 6: verify both halves with `verify_transcripts.py --file <exact saved file> --json` before calling a meeting fetched; a directory scan does not substitute | Rule 6 | Reworded; adds the reason (a scan reports on the corpus) |
| Rule 7: the no-source marker only when the source truly has no transcript, with a one-line reason | Rule 7 | Reworded; names the evidence (a complete tab list or the doc itself) and the failed-fetch case from Step 3 |
| Rule 8: never derive attribution from a tool summary; who warned, decided, approved or owns comes from the verbatim transcript; if it does not say, keep the passive form | Rule 8 | Reworded, the behavior first. Adds "asked" and "promised" (v0.4.0 note), "whether fetched or pasted by the user" (W16), "when a line names the actor, attribute directly" (W15: the evaluation's finding), the reason, and "say the actor is unknown" (Step 4.6) |
| Rule 9: a scanned commitment is a candidate until the principal confirms it in the same turn; stamp each confirmed one with exactly one owner; nothing created from scanner output alone | Rule 9 | Reworded to fix the evaluation's finding (W7, W14): names the commitment scanner (`extract_commitments.py`), says what to show (timestamp, speaker, quote, from Step 4.7), adds the reason, and limits the rule to scanner output, with commitments read from transcript lines left to rule 8. Same turn, one owner and "nothing created from scanner output alone" kept |
| Rule 10: cross-check every date against at least two independent signals before writing a dated file | Rule 10 | Reworded; names example signals from Date Verification, with `modifiedTime` in UTC and the date in the doc's name (Step 2 prefers the doc whose name contains the date); adds the reason |
| Rule 11: never leave transcripts in `~/Downloads/`; commit them to `transcripts_repo`, whose pre-commit gate refuses a summary saved as a transcript | Rule 11 | Reworded, the behavior first |
| Contents: protocol-steps.md line | Contents | Reworded for the steps it now lists |
| Contents: transcript-primary-and-commit-gate.md line ("the v0.4.0 hierarchy ... and the v0.5.0 pre-commit gate") | Contents | Reworded: the file now holds the rules as they stand |
| Contents: setup.md line | Contents | Kept |
| Contents: release notes line | Contents | Kept, the range now to 1.3.0 |
| Contents: optional-workspace-mcp/README.md line | Contents | Reworded, with when to read it |
| Contents: coverage-map.md and preserved.md lines | Contents | Reworded for both rewrites |
| Contents: "Protocol, Step 0: below." | Contents: "Which path: below" and the declared-window-sweep.md line | Reworded |
| Protocol heading; "Step 0: Declared-window sweep (v0.9.0 — how ... executes)" | references/declared-window-sweep.md, title | Reworded; the version tag went to the release notes |
| "The agent does not get a vote on which declared items are interesting." | declared-window-sweep.md, second paragraph | Reworded: "no judgment about which meetings look interesting stands between the list and the fetch" |
| "Relevance is judged after fetching, never before." | declared-window-sweep.md, second paragraph; rule 1 | Kept in substance |
| "Every declared item is fetched or retained as an unclosed gap." | declared-window-sweep.md, second paragraph | Reworded ("open gap") |
| Inventory with `fetch-meeting.py --window FROM THROUGH`: docs saved or unsaved, the watermark moment, `scope`, `undeclared` (declare a recurring one) | declared-window-sweep.md, step 1 | Kept, with what the command prints and its exit codes added (format rule 7) |
| With hosted connectors: one Drive search per declared pattern with `modifiedTime` bounds, every page followed, doc IDs compared in the three forms `--window` reads | declared-window-sweep.md, step 1 | Kept |
| "HTTP health alone is not sign-in: a read as the declared account shows which account answers." | declared-window-sweep.md, step 1, first paragraph | Reworded, and placed first, where the work starts |
| "Never filter by meeting title or perceived relevance." | declared-window-sweep.md, step 1, last paragraph | Reworded |
| Advance with `sync_watermark.py advance --workspace <W> --surface meetings --through <T>`; T with its offset, the earliest of the window's end (UTC), two hours before the check and one second before each unsaved doc was created | declared-window-sweep.md, step 5; the two-hour bound also in rule 2 | Kept; moved after the fetch and the report, where it runs |
| A failed search, a full page, a next-page token, the `incompleteSearch` warning or an unknown tab list keeps the watermark where it is | declared-window-sweep.md, step 5; rules 2 and 3 | Kept |
| The single-meeting path serves an explicit request; a ritual sync (Day-Start 3c, Day-End Step 1) runs the sweep instead, because the policy needs an execution path | declared-window-sweep.md, opening paragraph; SKILL.md, Which path | Reworded; adds the mid-day sync, which synthesis-daily-rituals also runs |
| Step 0.1: enumerate the declared set (patterns crossed with occurrences that ended in the window); the enumeration is the complete decision | declared-window-sweep.md, step 2 | Kept |
| Step 0.2: run Steps 2 to 5 for every member; relevance judged after fetching, from content | declared-window-sweep.md, step 3 | Kept |
| Step 0.3: one report line per member, fetched (with path) or an unclosed gap naming member, window and failure; a missing member is the defect; a gap is closed this run or carried as blocking, never dropped | declared-window-sweep.md, step 4 | Kept ("open gap") |
| Closing pointer: Steps 1 to 6 are in protocol-steps.md | SKILL.md, Which path, first bullet | Reworded as a route |
| (none) | SKILL.md, Which path | Added (W18): routes the four kinds of request, including a record the user brings |

### references/protocol-steps.md

| 1.2.1 | 1.3.0 | How |
|---|---|---|
| Title and opening: "the single-meeting path, as written in 0.14.0"; a ritual sync runs Step 0 in SKILL.md | Title and opening | Reworded; points to declared-window-sweep.md |
| Contents | Contents | Reworded with the step names |
| Step 1: take a natural-language meeting reference | Step 1 | Reworded; the example "Monday's PDE sync" is now "Monday's design sync" |
| Step 1: meeting name from `meeting_patterns`, else `generic_pattern`; date parsed against the system date and checked with `date`; account from `google_account` unless the user names another | Step 1 | Kept |
| Step 2: Drive search with a `modifiedTime` filter; the typical query | Step 2 | Kept; the query unchanged |
| Step 2: no match: retry a day wider, then the Gemini email in Gmail, then report and stop; do not guess or fabricate | Step 2, fallbacks 1 to 3 | Reworded: numbered in the order they run; "a guessed or reconstructed doc is never saved" (W12) |
| Step 2: several match: the doc whose name contains the date, else list them and ask | Step 2 | Kept |
| Step 3: fetch the whole doc; its two tabs, Notes and Transcript | Step 3 | Kept |
| Step 3: unwrap every tool-result envelope (`mcp_client.call_tool_text`); an outer or nested error is unknown coverage | Step 3 | Kept |
| Step 3: select by stable tab ID, never by order or a regular expression over flattened text; a title only when exactly one tab in a complete list carries it; record the ID; workspace-mcp's two tools | Step 3; binding rule 5 | Reworded, the behavior first |
| Step 3: distinct reasons for the six failures | Step 3 | Kept |
| Step 3: only a complete tab list establishes `transcript-tab-absent`; an error or a flattened summary never authorizes a no-source marker | Step 3; binding rule 7 | Reworded ("justifies the no-source marker") |
| Step 3: keep every returned byte and the tab IDs; a connector that cannot list tabs leaves the choice to you | Step 3 | Kept |
| Email warning: the email is a summary of the summary; saving it is the top way to lose most of the record; the transcript lives only in the Drive doc | "The Gemini email is for discovery only"; binding rule 4 | Reworded (W9: no alarm emoji or capitals) |
| Email "Rule": find the doc ID (the email's button or Step 2) and fetch the full doc; the email is for discovery only | Same section; binding rule 4 | Reworded |
| Step 4.5 catches an email saved as a transcript by counting timestamps and speaker lines | Same section | Kept |
| Step 4: the path and the header block | Step 4 | Kept; the header marked as the exact template (W17) |
| Step 4: an identical file is "already synced"; a different one is replaced and the old kept as `{path}.old-{timestamp}.md` | Step 4 | Reworded |
| Step 4.5: verify both halves before declaring a meeting fetched; a summary-only save fails silently and costs hours | Step 4.5; binding rule 6 | Reworded |
| Step 4.5: the verifier command; repeatable `--file` or `--saved-manifest` with paths and SHA-256 digests; a directory scan cannot substitute; bad paths refuse | Step 4.5 | Kept; what it prints and its exit codes added (format rule 7) |
| Step 4.5: timestamp counts (5 to 50 against 0 to 2); `INCOMPLETE` means fetch and save again | Step 4.5 | Kept |
| Step 4.5: reading the summary line (`--only-incomplete`, the `Total:` line, exit 2, `total_files` and `listed_count`) | Step 4.5 | Kept |
| Step 4.5: the four failures it catches | Step 4.5 | Kept |
| Step 4.5: "This step is not optional", with the failure that prompted it | Step 4.5 ("so it runs on every save") | Reworded (W9) |
| Step 4.5: a verifier that will not run is reported as unavailable; a grep threshold proves nothing and moves no watermark | Step 4.5 | Reworded |
| Step 4.5: the no-source marker when the doc has no transcript, with a one-line explanation; `OK (no-source-transcript)` | Step 4.5; binding rule 7 | Kept |
| Step 4.5: the three skipped prefixes; rename a file to audit it | Step 4.5 | Kept |
| Step 4.6 heading | Step 4.6 heading | Kept (`test_the_remainder_points_only_at_files_this_skill_ships` reads it) |
| Step 4.6: before a meeting record is cited, take the actor from the transcript's speaker line | Step 4.6; binding rule 8 | Kept; adds "the saved file, or transcript lines the user supplies" and "the attribution is settled; write it" (W15, W16: the evaluation's finding) |
| Step 4.6: a summary, decisions section or action-item list says what happened, never who | Step 4.6; binding rule 8 | Kept |
| Step 4.6: passive constructions are "attribution vacuums" | Step 4.6 ("have lost their actor") | Reworded |
| Step 4.6: when the transcript is silent, the passive form or "unknown", never the most salient person | Step 4.6; binding rule 8 | Kept |
| Step 4.6: the 2026-07-07 incident and the hierarchy are in transcript-primary-and-commit-gate.md | Step 4.6: the hierarchy in that file, the incident in release-notes.md (v0.4.0) | Reworded pointer, since the note moved |
| Step 4.6: the verifier tells a transcript from a summary; an `INCOMPLETE` file cannot support attribution | Step 4.6 | Kept |
| Step 4.7 heading "(v0.10.0)" | Step 4.7 heading | Version tag dropped |
| Step 4.7: verification proves fidelity, not what is owed; run the scanner | Step 4.7 | Reworded; the command unchanged; what it prints and its JSON added |
| Step 4.7: a Gemini timestamp carries across its block; missing times stay null; the commitment shapes it flags | Step 4.7 | Kept |
| Step 4.7: present every candidate in the same turn as the filing; neither the scanner nor the agent creates anything from its output alone; an unconfirmed candidate is not an obligation | Step 4.7; binding rule 9 | Kept |
| (none) | Step 4.7, last sentence: the step governs scanner output; a question about who committed in transcript lines is answered by Step 4.6 | Added (W15), the evaluation's finding |
| Step 4.8 heading "(v0.11.0)" | Step 4.8 heading | Version tag dropped |
| Step 4.8: one owning workspace (§3), routed by the ownership rules; the stamp command; `candidate-confirmed`; other seats record nothing; blank owner or unknown rule refused | Step 4.8 | Kept; what it prints and its exit code added |
| Step 5: add a reference; note the decisions and action items the Notes surfaced | Step 5 | Reworded: actors and owners from the transcript, so the step agrees with binding rule 8 |
| Step 6: never leave transcripts in `~/Downloads/`; commit with a descriptive message; push when pushed on save | Step 6; binding rule 11 | Reworded, the behavior first; points to the commit gate |
| Date Verification: two signals of three (system date, `modifiedTime`, the user's date); the Slack sync skill's same check; a cached `currentDate` goes stale | Date Verification; binding rule 10 | Kept; adds the UTC conversion and the date in the doc's name, as rule 10 does |
| Integration: called from Day-Start Step 2b with the day's calendar meetings, in place of scanning Downloads; the rituals skill holds the contract | Integration | Reworded: the current step names, and the rituals run Step 0 |

### references/transcript-primary-and-commit-gate.md

| 1.2.1 | 1.3.0 | How |
|---|---|---|
| Title, opening paragraph and contents | Title, opening paragraph and contents | Reworded: the file states the rules as they stand |
| v0.4.0 section, whole | release-notes.md, v0.4.0, between v0.5.1 and v0.3.0 as in 0.14.0 | Moved word for word |
| v0.4.0 item 1: the verbatim transcript is the only primary source; fetch it; a summary-only fetch is incomplete; the rule applies at fetch time | Evidence item 1; binding rule 4 | Restated in the present tense |
| v0.4.0 item 2: summaries, decisions sections and action-item lists are lossy; keep them as labeled verbatim appendices, for provenance, scanning, the docs with no transcript tab, and error tracing | Evidence item 2 | Restated |
| v0.4.0 item 3: never derive attribution from a summary; resolve against the transcript before an active-voice sentence enters a context file, plan or draft; passive constructions and the most salient person; the 2026-07-07 incident | Evidence item 3; binding rule 8; the incident in release-notes.md (v0.4.0) | Restated |
| v0.4.0 item 4: no verbatim transcript: tell the user in the same turn and stamp "⚠️ summary-only — no verbatim transcript exists." | Evidence item 4 | Restated; the stamp kept exactly, as output format (W9) |
| v0.4.0 item 5: headers and highlights the agent writes come from the transcript | Evidence item 5 | Restated |
| v0.5.0 section, whole | release-notes.md, v0.5.0, between v0.5.2 and v0.5.1 as in 0.14.0 | Moved word for word |
| v0.5.0 opening: the gap between the rule and its enforcement, and why a fail-closed gate | release-notes.md (v0.5.0) | Moved; history (format rule 12) |
| v0.5.0 item 1: install the completeness gate; the hook script; a cheap gate, the verifier as the precise check; the boundary that cannot be bypassed | Gate item 1 | Restated; the script byte-identical |
| v0.5.0 item 2: the fetch-time rule (never abridged, "omitted for brevity" or paraphrased; summary-only only when the source has no transcript, with the marker and a reason) | Gate item 2; binding rules 4 and 7 | Restated |
| v0.5.0 item 3: what the hardened verifier recognizes; structure, not counts, tells a transcript from a summary; save real line breaks | Gate item 3 | Restated in the present tense; "now recognizes" and the false positives it fixed stay in the release note |

### Release notes, version and scripts

| 1.2.1 | 1.3.0 | How |
|---|---|---|
| release-notes.md opening: the v0.4.0 and v0.5.0 notes are in transcript-primary-and-commit-gate.md | release-notes.md opening | Reworded, since they are back |
| release-notes.md title and contents | Title and contents | 1.3.0, v0.5.0 and v0.4.0 added, as `test_meeting_version_parity.py` requires |
| (none) | release-notes.md, 1.3.0 | Added |
| `SCRIPT_VERSION = "1.2.1"` in `verify_transcripts.py` and `extract_commitments.py` | `"1.3.0"` | Bumped with the skill (the parity tests); nothing else in the scripts changed |

### Files unchanged

`references/setup.md`, `optional-workspace-mcp/` (its README and every script), `agents/openai.yaml` and every
test. `references/earlier-version-history.md` keeps every word and gains an opening line and a contents list, since
it runs past 100 lines (format rule 3). In this file, the 0.14.0 map below is kept word for word one heading
level down; in preserved.md, the M3 sections are kept as they were, after the 1.3.0 section.

## Coverage map: meeting transcripts 0.14.0 to 1.0.0 (v5)

Read when checking where a rule of the 0.14.0 text lives now (ruling D8). Every part of the earlier 0.14.0 SKILL.md and where it lives now. The prose restructure removed nothing and changed no script; the M3 script pass (below) then applied the code verdicts, and every passage it replaced is verbatim in [preserved.md](preserved.md).

### Version

The prose restructure kept `version: "0.14.0"` because `verify_transcripts.py` and `extract_commitments.py` (and the cut `transcript_primary.py`) carried `SCRIPT_VERSION = "0.14.0"` and three tests required parity. In M3 the skill and both remaining scripts moved to 1.0.0 together; `tests/test_meeting_version_parity.py` and the version check in `tests/test_meeting_verify_transcripts.py` hold the parity.

| 0.14.0 section | Now |
|---|---|
| Frontmatter description (336 characters) | Shortened to 275 characters, keeping fetch notes and full transcripts into local markdown, primary-source verification before attribution, tool-agnostic Gmail/Drive MCPs or local exports, and every trigger verb: fetch, pull, sync, download, import, classify, verify. The full text is quoted below |
| Frontmatter `depends_on`, `author`, `version`, `source_repo`, `source_type` | Kept unchanged; `version` for the reason above |
| Opening notes for 0.14.0 and 0.13.0 | references/release-notes.md (verbatim); Binding rules 2, 3 and 5 carry their live rules |
| "The earlier release notes and rationale are retained in... Before a declared-window sweep, read the mandatory acquisition evidence contract..." | references/release-notes.md, at its head, moved word for word from SKILL.md (where it followed the opening paragraph) to make room for the runtime commands' `-s` and quotes, its link now naming the file beside it; in M3 the sentence pointing at the deleted acquisition evidence contract was removed (old line in preserved.md) |
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

### Pointers from scripts

- `optional-workspace-mcp/fetch-meeting.py` now points at `synthesis-meeting-transcripts/references/setup.md` for the schema (it said SKILL.md).
- A comment in `verify_transcripts.py` asks for "a matching entry to SKILL.md's changelog" when output changes. The release notes live in references/release-notes.md and references/earlier-version-history.md.
- `verify_transcripts.py`'s unverified remainder still said "use transcript_primary.py" after M3 cut that script. Since 2026-10-07 it points at the reading rule that replaced it, protocol-steps.md Step 4.6; `test_the_remainder_points_only_at_files_this_skill_ships` holds every file it names to one the skill ships.

### Scripts in v5 (M3)

Verdicts from the v5 code evaluation (tool scripts, meeting transcripts). Line counts are `wc -l`.

| Old file (lines) | Verdict | Now (lines) |
|---|---|---|
| `verify_transcripts.py` (492) | KEEP | Kept (505): version 1.0.0; its exact-file reader came from the cut daily-rituals acquisition module and is now local (`read_exact`); `from __future__ import annotations` added so Apple's Python 3.9 runs it |
| `extract_commitments.py` (178) | KEEP; make the docstring generic | Kept (180): the docstring tells the incident without names; version 1.0.0 |
| `transcript_primary.py` (461), `acceptance-suite.yaml`, `fixtures/` | CUT | Binding rule 8, Step 4.6, transcript-primary-and-commit-gate.md; fixtures verbatim in preserved.md |
| `optional-workspace-mcp/fetch-meeting.py` (678) | SLIM | Kept (351): fetch, tab selection by ID (folded `document_tabs.py`), an error is unknown, `--window` saved/unsaved listing; standard library only. Since 2026-10-05 its config is read by the plugin's shared `synthesis/yamlish.py` instead of an embedded reader |
| `optional-workspace-mcp/mcp_client.py` (329) | SLIM | Kept (181): event parsing, nested error unwrapping, the 8 MiB cap; `urllib` instead of httpx; raw-capture custody dropped |
| `optional-workspace-mcp/document_tabs.py` (207) | SLIM, fold into fetch-meeting | `tab_inventory` and `select_transcript` in fetch-meeting.py |
| `optional-workspace-mcp/google_read.py` (174), `workspace_mcp_read.py` (241) | CUT | — |
| `start.sh`, `stop.sh`, `install-autostart.sh`, `uninstall-autostart.sh`, `doctor.sh` | KEEP, generic launchd label | Kept; label `com.synthesis.workspace-mcp`; doctor's account line no longer names the cut acquisition route |
| Tests (3,600 lines) | Kept where they test kept code | `tests/test_meeting_verify_transcripts.py`, `tests/test_meeting_extract_commitments.py`, `tests/test_meeting_version_parity.py`, `tests/test_workspace_mcp_doctor.py`, `tests/test_workspace_mcp_fetch.py`; the four `test_acquisition_*.py` files and `test_transcript_primary.py` went with the cut code |

### Edge cases and where each is held

| Scenario | Test (in `tests/`) or rule |
|---|---|
| E15 a summary-only save fails unless it carries the no-source marker | `test_meeting_verify_transcripts.py::test_e15_*`; the v0.5.0 commit gate in transcript-primary-and-commit-gate.md |
| E16 inline timestamps and a transcript heading without dialogue are incomplete | `test_e16_*` |
| E17 Plaud single-speaker and undiarized transcripts pass | `test_e17_*` |
| E18 `--only-incomplete` keeps the corpus total; a wrong or empty path exits 2 | `test_e18_*` |
| E19 `_*`, `gdoc-*`, `email-*` files are skipped and named | `test_e19_*` |
| E20 transcript by stable tab ID; distinct reasons for empty, missing, incomplete, ambiguous | `test_workspace_mcp_fetch.py::test_e20_*` |
| E21 an outer or nested tool error is unknown, never "no transcript" | `test_e21_*` |
| E22 the bookmark does not pass an unsaved doc, which the report names; a doc named by a `**Source ID:**` header, a Google Doc link or a `> Source:` line's backticked ID is saved; a full page, a next-page token or Drive's incompleteSearch warning leaves the bookmark empty | `test_e22_*` (the provenance-line form: `test_e22_a_blockquote_source_line_marks_its_doc_saved`; the token and warning: `test_e22_a_next_page_token_or_an_incomplete_search_is_bounded_too`) |
| E23 commitment candidates listed with speaker and time; nothing created unconfirmed | `test_meeting_extract_commitments.py` (`test_gemini_bold_line_flags_shape`, `test_plaud_timestamp_is_captured`, `test_stamp_*`); binding rule 9 |
| E24 Gemini lines without timestamps take the preceding block's time | `test_meeting_extract_commitments.py::test_e24_a_gemini_time_carries_across_its_block_and_resets_at_a_section` |
| E25 a moved checkout is a stale service path (exit 1); unreadable state exits 2 | `test_workspace_mcp_doctor.py::test_e25_a_moved_checkout_is_a_stale_unit_path_defect`, `test_restricted_launchd_and_port_visibility_are_unknown` |
| E26 sparse launchd PATH and a recycled PID | `start.sh` (unchanged); `test_workspace_mcp_doctor.py::test_e26_sparse_path_finds_uvx_and_a_recycled_pid_is_not_a_running_server` |
| E27 attribution comes from the verbatim transcript or the passive form stays | Binding rule 8; protocol-steps.md Step 4.6; transcript-primary-and-commit-gate.md (v0.4.0 item 3) |
| E28 the bookmark suggestion is never later than two hours before the run (a meeting under way may have no doc yet), stops one second before an unsaved doc was created, and carries its offset (2026-10-08: a run at 11:23 offered 23:59:59 while two 11:00 meetings ran) | `test_workspace_mcp_fetch.py::test_e28_*` |
| E29 every `--window` run names the only patterns it searched, and lists the Gemini notes docs no declared pattern finds as `undeclared` without holding the bookmark | `test_workspace_mcp_fetch.py::test_e29_*` |

### Lines the coverage check reports

`v5-skill-coverage-check.py` reports no lines: every non-blank line of the 0.14.0 Markdown appears verbatim in SKILL.md or a reference file. None of the moved text had a relative link, so no link paths changed.

Since M3 the check reports two lines, deliberately: references/earlier-version-history.md, the v0.10.0 entry, the sentence about the spoken "of course" that sat in a filed transcript. The 0.14.0 lines named a private person and a personal event; this is a public repository (requirement R7.4, and section 5 item 7 of the tool-scripts evaluation), so the sentence now says "the principal's" and "a friend's memorial service" and the old lines are not quoted anywhere in the skill. They are readable with `git show origin/main:skills/synthesis-meeting-transcripts/SKILL.md` (the v0.10.0 note).

### Frontmatter before v5 (verbatim)

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
