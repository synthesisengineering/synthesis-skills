# Release notes: 1.0.0, 0.14.0, 0.13.0, and v0.2.0 to v0.5.3

Release notes that opened the 0.14.0 SKILL.md, in their original order. The v0.4.0 and v0.5.0 notes carry live rules, so they are in [transcript-primary-and-commit-gate.md](transcript-primary-and-commit-gate.md); v0.6.0 to v0.11.0 are in [earlier-version-history.md](earlier-version-history.md).

Contents:
- 1.0.0: the v5 script verdicts
- 0.14.0 and 0.13.0
- v0.5.3: a clean audit no longer looks like a broken one
- v0.5.2: inferred-speaker annotation format and version-stamped output
- v0.5.1: Plaud spaced timestamp ranges
- v0.3.0: mandatory verification and the do-not-extract-from-email rule
- v0.2.0: workspace-rooted paths

## 1.0.0 — the v5 script verdicts

Version 1.0.0 (2026-10-05, milestone M3) applies the v5 code evaluation. The
acquisition machinery of 0.12.0 to 0.14.0 is gone: the Google REST and
workspace-mcp custody adapters, recorder readiness receipts, the source-inventory
seam and the attribution receipt (`transcript_primary.py`). Its rules stay as
protocol text: unknown coverage is a gap, an error is not absence, the transcript
is chosen by tab ID, the watermark never passes an unsaved doc, and attribution
comes from the verbatim transcript. `fetch-meeting.py` is standard-library Python
again, with tab selection folded in and a `--window` listing of saved and unsaved
docs; `mcp_client.py` is a small standard-library client. `verify_transcripts.py`
and `extract_commitments.py` are unchanged in what they detect. The launchd label
is generic (`com.synthesis.workspace-mcp`). The skill and its scripts carry 1.0.0
together.

## 0.14.0 and 0.13.0

Version 0.14.0 adds account-bound workspace MCP observations and transcript
selection by title bound to tab ID. Its rendered Drive inventory omits the
provider completeness flag, so it cannot authorize interval completion or
watermark advancement. Use an explicitly configured structured reader for that
operation; credentials and adapters are never selected automatically.

Version 0.13.0 connects declared Google or MCP acquisition to exact transcript
files, source-bound verification and the existing watermark owner. Google Docs
tabs retain native identities; MCP dispatch requires successful matching protocol
and tools-capability negotiation. Unsupported source identity remains incomplete.

## v0.5.3 — A clean audit no longer looks like a broken one

v0.5.3 (2026-08-11) fixes a reporting defect in `verify_transcripts.py`. It is not a
detector change — no file's status moves — but it changes what an operator concludes
from a run, which is the same thing in practice.

`--only-incomplete` filtered the results list **before** the summary counters were
computed, so every counter described the filtered listing rather than the corpus. On a
clean corpus the script printed:

```
Total: 0 files — 0 incomplete, 0 skipped, 0 no-source-transcript.
```

That is a clean bill of health rendered byte-identical to *"the path was wrong / no `.md`
files were found."* Observed on 2026-08-11 against a 282-file corpus that was actually
0-incomplete, 2 skipped, 19 no-source-transcript; the only way to tell the two apart was
to read the source. `--json` carried the same defect through `total_files`.

This matters because **the daily ritual invokes the script with `--only-incomplete`**, so
the success path was the one that looked broken. That is how a fail-closed control gets
routed around — the same erosion the v0.5.1 false-positive fix existed to prevent,
arriving from the opposite direction. A control has two ways to lose an operator's trust:
crying wolf, and being unable to say "all clear" out loud.

**The fix:** counters and the file total always describe the audited corpus; the filter
narrows only which rows are listed. A run with filtering active now says so:

```
Total: 282 files — 0 incomplete, 2 skipped, 19 no-source-transcript. (listing filtered to incomplete only)
```

An empty listing prints `(none — no audited file matches the active listing filter)`
rather than a bare table. In `--json`, `total_files` stays the corpus count, and new
`listed_count` and `only_incomplete` keys describe the listing, so machine consumers see
the same split. Exit codes are unchanged (`0` clean, `1` incomplete found, `2` bad path).
`test_verify_transcripts.py` gains end-to-end coverage that runs the CLI against a
synthetic clean corpus and fails if the summary ever reports `Total: 0 files` again —
and CI now runs that test file, which it previously did not.

## v0.5.2 — Inferred-speaker annotation format + version-stamped output

v0.5.2 (2026-08-06) fixes two issues found while individually re-verifying 26 files that a
STALE plugin-cache copy (v4.9.0, predating v0.5.0 entirely) had flagged INCOMPLETE — the
live corpus was actually at 0 incomplete under the correctly-installed v4.14.1, but nothing
in the tool's own output could tell a reader which version had produced a given result.

1. **Detector fix: inferred-speaker parenthetical annotations.** When Plaud diarizes only by
   number, our agents annotate the inferred real name inline before the colon —
   `**[10:10] Jordan Lee (Plaud Speaker 4, mapped):**` or
   `**[09:10-09:42] Speaker 6 (Sam Rivera):**`. v0.5.1's speaker regex required the colon
   immediately after the name, so every annotated line silently failed to count. Confirmed
   against a production corpus: dozens of undercounted lines in each of several affected files.
   Every affected file still passed only because it had enough unannotated lines to clear the
   threshold regardless — a file with a different mix of annotated-vs-bare lines would have
   been a genuine false positive. The fix accepts an optional `(...)` annotation, but ONLY on
   the timestamp-led branch of the regex — never on the bare no-timestamp branch, where it
   would start matching ordinary markdown field headers (`**Attendees (Invited):**`, `**Decision
   (Gemini "Aligned"):**`) that appear in genuinely summary-only files. Verified against a
   263-file production corpus: zero status changes, only speaker-count increases on the files
   that actually contained the pattern.
2. **Version-stamped output.** The script previously had no way to tell a reader which version
   produced a given run — the failure mode that caused this incident. Every run now prints its
   `SCRIPT_VERSION` (must match this file's frontmatter `version`) in both the human-readable
   banner and the `--json` output, plus a standalone `--version` flag. If the printed version
   doesn't match what you expect, the copy being run is not the one you think it is — check
   `installed_plugins.json` for the actually-active plugin path rather than a remembered or
   hardcoded version-numbered directory.

## v0.5.1 — Plaud spaced timestamp ranges (completeness-gate false positive)

v0.5.1 (2026-08-04) fixes a false POSITIVE in `verify_transcripts.py`. v0.5.0 taught the speaker-line
detector about Plaud's timestamp-before-name format but matched only the UNSPACED range
`[00:00-00:08]`; Plaud actually emits `**[00:00 - 00:08] Name:**` with spaces around the separator.
Both live Plaud transcripts in a production corpus were flagged INCOMPLETE despite carrying 98 and
163 timestamps of real diarized dialogue. Whitespace around the separator is now optional and en/em
dashes are accepted alongside `-`.

Why a false positive matters as much as a false negative: this gate is fail-closed, and a control
that cries wolf on genuine work is a control agents learn to route around. `test_verify_transcripts.py`
ships alongside the script and pins every real-world line shape — Plaud spaced/unspaced/en-dash/em-dash,
hour-length ranges, undiarized `Speaker N`, Gemini bare names — plus negative controls proving a
summary body still cannot clear the thresholds.

## v0.3.0 — Mandatory verification step + don't-extract-from-email rule

In v0.3.0 (2026-06-03), the skill adds a **mandatory post-save verification step** (new Step 4.5) and an explicit "do not extract from the Gemini email" warning at Step 3. Both changes target a specific failure mode: an agent reads the Gemini-notes email body (which is a summary), writes that to the local file, and never fetches the underlying Drive doc that contains the verbatim word-for-word transcript. The verification step uses the bundled `verify_transcripts.py` script (counts timestamp markers + speaker-attribution lines) to detect summary-only saves before they silently land.

## v0.2.0 — Workspace-Rooted Paths

In v0.2.0 (2026-04-22), meeting transcripts land in the workspace-private repo (`ai-knowledge-<workspace>-<person>-private/transcripts/meetings/`), matching synthesis-slack-sync v2.0.0. The config schema updates accordingly: `ai_knowledge_repo` → `transcripts_repo`, with the workspace no longer included in the path (it's implicit in the repo name).
