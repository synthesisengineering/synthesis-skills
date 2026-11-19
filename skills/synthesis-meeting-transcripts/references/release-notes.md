# Release notes: 1.3.0, 1.2.1, 1.2.0, 1.1.1, 1.1.0, 1.0.1, 1.0.0, 0.14.0, 0.13.0, and v0.2.0 to v0.5.3

The earlier release notes and rationale are retained in [earlier-version-history.md](earlier-version-history.md). Unknown authentication, tab enumeration, or archive coverage is a visible gap, never a no-source attestation.

The notes for 1.0.0 and later, newest first, then the release notes that opened the 0.14.0 SKILL.md, in their original order, the v0.5.0 and v0.4.0 notes among them; the rules those two set, as they stand now, are in [transcript-primary-and-commit-gate.md](transcript-primary-and-commit-gate.md). v0.6.0 to v0.11.0 are in [earlier-version-history.md](earlier-version-history.md).

Contents:
- 1.3.0: the rewrite to the D8 standard; rule 9 covers the scanner's output only
- 1.2.1: every script runs from the runtime's copy
- 1.2.0: the mail connector reads the outbox, and runs one release
- 1.1.1: the second image host
- 1.1.0: the window never suggests passing a meeting still under way
- 1.0.1: saved meetings found by their blockquote source line
- 1.0.0: the v5 script verdicts
- 0.14.0 and 0.13.0
- v0.5.3: a clean audit no longer looks like a broken one
- v0.5.2: inferred-speaker annotation format and version-stamped output
- v0.5.0: fail-closed enforcement, the transcripts repository's commit gate
- v0.5.1: Plaud spaced timestamp ranges
- v0.4.0: transcript-primary sourcing, summaries never trusted for attribution
- v0.3.0: mandatory verification and the do-not-extract-from-email rule
- v0.2.0: workspace-rooted paths

## 1.3.0 — the rewrite to the D8 standard; rule 9 covers the scanner's output only

The skill's instruction text is rewritten to the repository's rewrite standard (`docs/skill-writing.md`), every
rule kept: the coverage map places each one, and preserved.md holds the 1.2.1 text word for word. With the skill
loaded, a model asked the user to confirm a commitment it had read straight from transcript lines the user pasted,
which it did not do without the skill: binding rule 9's "a scanned commitment" meant the scanner's output but read
as any commitment. Rule 9 now names the commitment scanner and covers its output only, rule 8 says to attribute
directly when a transcript line names the actor, and Steps 4.6 and 4.7 say the same. The binding rules keep their
numbers and say what each governs, and a line above them says they hold against a contrary request. Step 0 moves to
`references/declared-window-sweep.md`, its steps in the order they run, and SKILL.md routes each kind of request to
its procedure. The evidence reference states its rules in the present tense, and the v0.4.0 and v0.5.0 notes are
back in this file. The scripts are unchanged but for their version.

## 1.2.1 — every script runs from the runtime's copy

The synthesis runtime now carries this skill's scripts, its server kit included, and the guard trusts only the copy
inside the runtime: a copy in a harness's plugin cache waits for the principal's code when its text names a
protected folder, as the fetcher's does. The skill's commands name `$HOME/.synthesis/v5/current/skills/` paths, and
the server kit's messages name the folder it runs from. A launchd or systemd unit installed from another folder is
reported by the runtime's `doctor.sh`; running the runtime's `install-autostart.sh` once points it at the runtime's
stable path, which plugin upgrades no longer move. The fetch and verify scripts are unchanged but for their version
and their usage lines.

## 1.2.0 — the mail connector reads the outbox, and runs one release

A mail send with a file attached was approved and then refused by the connector, which reads a local file only
from its own attachment folder and the folders it was started with (2026-11-12). The optional connector's
`start.sh` now makes the synthesis outbox and adds it to `ALLOWED_FILE_DIRS`, and runs one release of the server,
`workspace-mcp@2.1.0`, the one whose rules for a local file the send guard copies (`WORKSPACE_MCP_VERSION` names
another). `install-autostart.sh` carries `SYNTHESIS_HOME` into the unit when it is set, escapes every value it
writes for a plist or a systemd unit, refuses by name before writing either a value that holds a control
character (neither can carry one as it is), and quotes a start path systemd would misread. `doctor.sh` reports the
outbox the unit gives the server and reads a quoted start path back. The fetch and verify scripts are unchanged
but for their version.

## 1.1.1 — the second image host

Gemini meeting notes also link screenshots on `docs.google.com/docs-images-rt/…?key=…`, with the same kind of
access key. Redaction, the audit and the commit check knew only `googleusercontent.com`, so 14 live keys were
committed in five records before a day-end sweep found them (2026-10-20). All three now cover both hosts, and
a hand redaction written `key=[REDACTED]` counts as redacted.

## 1.1.0 — the window never suggests passing a meeting still under way

`fetch-meeting.py --window` suggested the end of the day as the new watermark even while meetings were in
progress, which would have skipped their transcripts (reported 2026-10-08). The suggestion is now the earliest
of the window's end (UTC, as Drive reads it), two hours before the run, and one second before each unsaved
doc was created, always with an explicit offset; `advance_reason` says which. Each run names the patterns it
searched, and lists Gemini notes docs no declared pattern found under `undeclared`. A next-page token or an
incomplete-search warning bounds a listing like a full page. The pre-0.2.0 config hint is gone: a config
missing `transcripts_repo` is refused with the missing keys.

Docs screenshots exported to markdown link `googleusercontent.com` with an access key that opens the image to
anyone holding the URL (94 had reached saved transcripts by 2026-10-13). `fetch-meeting.py` now redacts each
key to `REDACTED` when it saves, and `verify_transcripts.py` fails a file that still carries one, naming it,
with `keyed_image_files` in its JSON. A transcript saved by hand is redacted with
`verify_transcripts.redact_image_keys`.

## 1.0.1 — saved meetings found by their blockquote source line

- `fetch-meeting.py --window` also counts a meeting as saved when its file names the doc on a
  `> Source:` line in backticks (``> Source: Gemini doc `<id>` ``), so it no longer reports those as
  unsaved or holds the meetings watermark back.
- `verify_transcripts.py` no longer points at `transcript_primary.py`, which 1.0.0 removed; it names
  the attribution reading rule in `protocol-steps.md` Step 4.6.

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

## v0.5.0 — Fail-closed enforcement: a summary cannot be committed in place of a transcript

v0.5.0 (2026-07-31) closes the gap between the rule and its enforcement. v0.2.0–v0.4.0 stated the rule (the verbatim transcript is the only primary source) and added a post-save verifier — yet the failure kept recurring: an agent fetches the transcript, saves only the summary, and sometimes writes "full transcript omitted for brevity" or relabels a paraphrase as "verbatim" while doing it. Prose plus an advisory verifier is not enough. The fix is a **fail-closed commit gate** — the same pattern as credential and message guards: a mechanical check at the commit boundary an agent physically cannot skip.

**1. Install the completeness gate in the transcripts-repo pre-commit hook.** Any file added or modified under `transcripts/meetings/*.md` must contain a real verbatim transcript OR carry the explicit no-source marker; otherwise the commit is blocked. Drop this into the repo's `.githooks/pre-commit` (or the pre-commit chained by your hook engine):

```bash
# Meeting-transcript completeness gate — a summary cannot be committed in place of a transcript.
viol=0
while IFS= read -r f; do
  case "$f" in
    transcripts/meetings/gdoc-*|transcripts/meetings/email-*|transcripts/meetings/_*) ;;  # not meetings
    transcripts/meetings/*.md)
      [ -f "$f" ] || continue
      grep -q 'VERIFIER: no-source-transcript' "$f" && continue
      # Count timestamp markers in BOTH formats real transcribers emit:
      #   Gemini  inline HH:MM:SS   ·   Plaud  bracketed [M:SS]/[MM:SS]/[H:MM:SS]/[t-t]
      ts=$(grep -oE '[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?' "$f" | wc -l | tr -d ' ')
      if [ "${ts:-0}" -lt 5 ]; then
        echo "TRANSCRIPT-INCOMPLETE: $f — ${ts:-0} timestamp marker(s); looks summary-only."
        echo "  Fetch the source (Doc's transcript section, or the recorder's get_transcript) and save the"
        echo "  FULL verbatim transcript. If the source genuinely has none, add on its own line:"
        echo "  <!-- VERIFIER: no-source-transcript --> <reason>"
        viol=1
      fi ;;
  esac
done < <(git diff --cached --name-only --diff-filter=AM -- 'transcripts/meetings')
[ "$viol" -ne 0 ] && { echo "Blocked — see synthesis-meeting-transcripts v0.5.0. Fix and re-commit."; exit 1; }
```

The gate is deliberately cheap (a timestamp-marker floor, not a full parse) so it is fast and hard to argue with; `verify_transcripts.py` is the richer, higher-precision cross-check for Step 4.5 and periodic audits. The gate is the boundary that cannot be bypassed.

**2. Fetch-time rule, as a non-negotiable.** Saving a summary when the source has a transcript is a failure, not a shortcut. If the source provides a transcript, it MUST be fetched and saved in full — never abridged, never "omitted for brevity," never replaced by a paraphrase or a smoothed reconstruction. A summary-only save is legitimate ONLY when the source has no transcript, and it MUST carry the `<!-- VERIFIER: no-source-transcript -->` marker with a one-line reason.

**3. Verifier detector hardened.** `verify_transcripts.py` now recognizes the recorder timestamp-led speaker line (`**[00:00] Name:**` and the range form `[00:00-00:32] Name:`), and treats a dense run of standalone-timestamp lines as a complete undiarized transcript. This removes the false positives — full transcripts flagged incomplete because only one speaker was diarized; unattributed running transcripts — that previously trained agents to distrust the verifier. Total-timestamp count alone cannot separate a transcript from a summary whose "Details" bullets carry inline timestamps (a summary can even wear a "Verbatim transcript" heading); **standalone-timestamp-line and speaker-line structure can.** A verbatim record that was saved with escaped `\r\n` sequences instead of real newlines reads as summary-only to every tool and to humans — always save real line breaks.

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

## v0.4.0 — Transcript-primary sourcing (summaries demoted, never trusted for attribution)

In v0.4.0 (2026-07-07), the skill codifies the **hierarchy of evidence** for every fetched meeting record:

1. **The verbatim transcript is the only primary source.** Always fetch it when the tool provides one — a summary-only fetch is an incomplete fetch. (The v0.3.0 verification step detects this; v0.4.0 makes the expectation explicit at fetch time, not just at verify time.)
2. **Tool-generated summaries, decisions sections, and action-item lists are lossy derivatives.** Keep them in the saved file — they carry provenance and scanning value — but only as clearly-labeled verbatim appendices (e.g., "Tool AI note — lossy derivative; verify against transcript before citing"). Do NOT discard them: they are sometimes the only record (some docs ship without a transcript tab), and preserving the tool's exact output is what makes error tracing possible.
3. **Never derive attribution-bearing claims from the tool summary.** Who warned/decided/approved/asked/promised, quotes, and action owners must be resolved against the verbatim transcript before any active-voice rendering is written into context files, plans, or draft messages. **Passive constructions in AI summaries ("he was warned", "it was decided") are attribution vacuums** — the summarizer dropped the actor, and a downstream writer will fill the slot with the most salient person (usually the meeting counterpart), which is how misattributions propagate. Canonical incident: 2026-07-07, a Plaud note's "He was warned that previous transitions (X, Y) were disastrous" — where X and Y were actually the WARNERS emailing the user directly — was rendered as a warning from the meeting counterpart and propagated into a draft message before the user caught it.
4. **Summary-only docs get a warning.** If the tool provides no verbatim transcript, tell the user in the same turn and stamp the saved file header: "⚠️ summary-only — no verbatim transcript exists."
5. **Agent-authored headers and highlights** in the saved file must be derived from the transcript, not paraphrased from the tool's summary.

## v0.3.0 — Mandatory verification step + don't-extract-from-email rule

In v0.3.0 (2026-06-03), the skill adds a **mandatory post-save verification step** (new Step 4.5) and an explicit "do not extract from the Gemini email" warning at Step 3. Both changes target a specific failure mode: an agent reads the Gemini-notes email body (which is a summary), writes that to the local file, and never fetches the underlying Drive doc that contains the verbatim word-for-word transcript. The verification step uses the bundled `verify_transcripts.py` script (counts timestamp markers + speaker-attribution lines) to detect summary-only saves before they silently land.

## v0.2.0 — Workspace-Rooted Paths

In v0.2.0 (2026-04-22), meeting transcripts land in the workspace-private repo (`ai-knowledge-<workspace>-<person>-private/transcripts/meetings/`), matching synthesis-slack-sync v2.0.0. The config schema updates accordingly: `ai_knowledge_repo` → `transcripts_repo`, with the workspace no longer included in the path (it's implicit in the repo name).
