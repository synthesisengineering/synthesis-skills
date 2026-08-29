---
name: synthesis-meeting-transcripts
description: "Fetch AI-generated meeting notes and full transcripts into local markdown files, and verify that an artifact is primary before it supports attribution-bearing claims. Tool-agnostic: works with Gmail/Drive MCPs and local transcript exports. Use when asked to fetch, pull, sync, download, import, classify, or verify a meeting transcript."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "0.9.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

## v0.9.0 — The declared set gets an execution path

v0.9.0 (2026-08-29) closes the gap an external adversarial review found in
v0.8.0: the policy said "declared means fetched" while the operative protocol
only resolved one user-named meeting. Step 0 now defines the declared-window
sweep — enumerate the declared set for the window, fetch every member, and
account for every member in the report with unclosed gaps recorded
machine-readably. Frontmatter version also catches up; v0.8.0 shipped with
stale skill metadata.

## v0.8.0 — Declared means fetched: no judgment gate before fetching

v0.8.0 (2026-08-27) removes agent judgment from the decision of *which* declared
transcripts to fetch.

**The defect.** The sweep enumerated documents and recorded their ids, but
fetching was gated on the agent deciding what looked worth fetching. That
judgment deprioritised several meetings as routine standups. One held a live
action item for the principal; another carried a launch date contradicting the
one recorded everywhere else, so the corpus held two incompatible dates and
nothing surfaced the conflict.

**The rule.** If a transcript is declared in scope for the window, it is
fetched. The agent does not get a vote on which declared items are interesting.
Relevance is judged *after* fetching, when the content is visible — never
before, from a title.

**Why this shape is already settled here.** The workspace retired this exact
failure once before, when "sync when active" gating was removed from the repo
list after a repository drifted for six weeks behind a judgment that it looked
inactive. Titles and activity heuristics are not evidence about content. A
declared set exists precisely so that no per-item judgment stands between the
list and the fetch; re-introducing one at a lower level rebuilds the failure the
declared set was meant to prevent.

A run that cannot fetch a declared item records it as an unclosed gap rather
than silently omitting it.

## v0.7.0 — Source grade is now executable

The standing kernel rule already says that a verbatim transcript is the only
primary source for attribution-bearing meeting claims. v0.7.0 adds the missing
mechanical boundary: `transcript_primary.py` rejects a structured summary even
when its filename or heading says “primary transcript,” classifies artifacts
from complete raw provider-message records that pair an identifier with
bounded message content, and requires an exact record-bound message location
before issuing an attribution receipt. Loose or conflicting identifiers fail
closed.

Both executable components now report the same 0.7.0 version as this skill's
metadata. The acceptance suite executes that parity instead of leaving the
existing “must match” banner as an unchecked claim.

The motivating fixture preserves the structure, not the private content, of a
real 128-line summarizer that had been labelled a primary transcript. Its
summary bullets and inline times cannot establish raw-message provenance. The
positive fixture uses synthetic `message_ts`, `thread_ts`, and Slack permalink
records. Classification is explicitly diagnostic. Only
`authorize-attribution` is an enforced gate, and its receipt binds the input
hash and the exact permalink or `message_ts`; a thread id alone is not
quote-granular. Every result names the unverified remainder.

## v0.6.1 — The heartbeat distinguishes absence from invisibility

v0.6.1 makes the doctor classify restricted LaunchAgent visibility as
unverifiable, separates curl transport failure from HTTP status, and prevents a
double-`000` response from being accepted as health.

## v0.6.0 — The optional auto-start service gets a heartbeat

v0.6.0 (2026-08-12) adds `optional-workspace-mcp/doctor.sh`. The bundle shipped an
installer for a supervised background service and no way to ask whether that service
was still alive — the one fail-open control in a stack whose other guards all ship a
health check.

The failure it exists to catch: `install-autostart.sh` records an **absolute** path to
`start.sh` into the launchd/systemd unit at install time. Move the checkout, rename a
parent directory, or restructure the repo, and the unit still points at the old path.
launchd exits `78` (`EX_CONFIG`), `KeepAlive` retries every 30 seconds indefinitely, and
the log fills with thousands of identical lines. Nothing surfaces. The only symptom is
that the MCP tools are quietly absent — and since the natural reading of "my tools are
missing" is a client problem, the investigation starts in the wrong place. Restarting
the client cannot help: the client never owned the process.

Observed 2026-08-12 against a checkout that had gained a `skills/` directory level. The
unit had been failing for an unknown period.

`doctor.sh` checks the unit exists, that its recorded start-script path still exists and
is executable, that the supervisor has it loaded and with what exit status (`78` gets a
targeted hint), that the client secret is present, that the port is listening, and that
the endpoint answers. Exit codes follow the guard contract — `0` healthy, `1` defects,
`2` a check could not run, because a check that cannot run must never be reported as a
check that passed. It also flags the case where the unit runs a *different* checkout
than the one you are editing.

The remedy is always to re-run `install-autostart.sh`, never to hand-edit the unit: the
installer derives the path from its own location and is correct by construction. The
defect was never in the generator — only in the absence of anything that noticed the
generated artifact had gone stale.

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

# Synthesis Meeting Transcripts

A protocol for fetching AI-generated meeting transcripts from the user's Gmail and Google Drive into a local markdown archive. Designed for teams where Google Meet + Gemini (or equivalents) produce meeting notes + word-for-word transcripts that live in Google Docs, and the user wants them mirrored locally alongside their project context.

This skill provides the **protocol** — how to find a meeting's Gemini-generated doc, extract both the notes summary and the full transcript, and save them to the right local folder. A per-project **config file** provides the specifics: which Google account, which meeting patterns to recognize, where to save locally. Prefer `.agents/meeting-transcripts.yaml`; existing `.claude/meeting-transcripts.yaml` configs remain supported.

This skill is **tool-agnostic.** It works with:

- Anthropic's hosted Claude Connectors for Gmail + Drive (single-account, most common)
- Self-hosted multi-account servers like [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) (a bundled auto-start helper is in `optional-workspace-mcp/`)
- Any other MCP that provides equivalent Gmail search + Drive file read capabilities

The skill describes the *workflow*; it does not prescribe which tools must be used.

---

## Configuration

Create `.agents/meeting-transcripts.yaml` in each project that uses this skill. Existing `.claude/meeting-transcripts.yaml` configs are valid compatibility fallbacks.

```yaml
# .agents/meeting-transcripts.yaml — Meeting transcript sync configuration (v0.2.0 schema)

# REQUIRED
workspace: example-workspace
# Identifier for the workspace. Used in transcript headers.
# Must match the workspace-private repo name pattern: ai-knowledge-<workspace>-<person>-private.

google_account: user@example.com
# The Google account whose Gmail/Drive will be searched.
# With Anthropic hosted connectors: must match the account authenticated in Claude Connectors.
# With workspace-mcp: any authenticated account.

transcripts_repo: ~/workspaces/example-workspace/ai-knowledge-example-workspace-<person>-private
# Absolute path to the workspace-private repo where transcripts are stored (Type 3 content).

transcripts_path: transcripts
# Relative to transcripts_repo. Meetings land in {transcripts_repo}/{transcripts_path}/meetings/.

# OPTIONAL — Named meeting patterns
# Maps a short name the user types ("pull the standup") to a Drive search query.
# The query is a Drive API v3 search expression matched against doc names.
# Values with unspecified patterns fall back to the generic {{name}} pattern.
meeting_patterns:
  standup: 'name contains "Daily Standup" and name contains "Notes by Gemini"'
  retro: 'name contains "Retrospective" and name contains "Notes by Gemini"'
  # Add your team's common meetings here.

# OPTIONAL — Generic fallback pattern for meetings not in meeting_patterns.
# {{name}} is substituted with the user's natural-language meeting name.
generic_pattern: 'name contains "{{name}}" and name contains "Notes by Gemini"'

# OPTIONAL — Filename date format for saved transcripts. Default: YYYY-MM-DD
# Produces: {transcripts_repo}/{transcripts_path}/meetings/{meeting-name-slug}-{date}.md
filename_date_format: "YYYY-MM-DD"
```

If the config file is missing, the skill should warn and ask the user to create one. A minimal working config has `workspace`, `google_account`, `transcripts_repo`, `transcripts_path`.

---

## Prerequisites

- A Gmail MCP and a Drive MCP must both be connected and authenticated for `google_account`. This skill doesn't care which specific MCPs — it will use whatever Gmail/Drive tools are available in the session.
- Local transcript directory must exist or be creatable at `{transcripts_repo}/{transcripts_path}/meetings/`.

---

## Protocol

### Step 0: Declared-window sweep (v0.9.0 — how "declared means fetched" executes)

The single-meeting path below serves an explicit user request. A ritual sync
(Day-Start 3c, Day-End Step 1) runs this sweep instead, because the policy
above has to have an execution path or it is prose:

1. **Enumerate the declared set** for the window from
   `.agents/meeting-transcripts.yaml`: every declared meeting pattern crossed
   with every occurrence that ended inside the window. The enumeration is the
   complete decision — no per-item judgment about which meetings look
   interesting stands between the list and the fetch.
2. **Run Steps 2–5 for every member.** Relevance is judged after fetching,
   from content.
3. **Account for every member.** The sync report carries one line per
   declared member: fetched (with path), or an **unclosed gap** naming the
   member, the window, and the failure ("no doc found", "fetch failed",
   "verbatim half missing"). A member missing from the report is the defect
   this step exists to prevent; a gap is closed this run or carried as a
   blocking item, never dropped.

### Step 1: Resolve the meeting

Accept a natural-language meeting reference from the user (e.g., "today's standup", "Monday's PDE sync", "the 2 pm design review"). Extract:

- **Meeting name** — lookup in `meeting_patterns` first; fall back to `generic_pattern` with the meeting name substituted.
- **Date** — parse relative dates ("today", "yesterday", "Monday") against the system date. Verify with `date` before using.
- **Account** — usually `google_account` from config, but user may override ("from my work account" or "from my personal account" when multiple are configured).

### Step 2: Find the Gemini meeting doc

Use the available Drive search tool to find docs matching the resolved pattern with a `modifiedTime` filter bracketing the target date. Typical query:

```
name contains "Daily Standup" and name contains "Notes by Gemini" and modifiedTime > "2026-04-21T00:00:00" and modifiedTime < "2026-04-22T00:00:00"
```

If no docs match:
- Retry with a broader window (±1 day) in case of timezone drift.
- If still no match, search Gmail for the corresponding Gemini notes email (`from:gemini-notes@google.com` with subject containing the meeting name on the target date) — the email usually links to the doc.
- If still no match, report to user and stop. Do not guess or fabricate.

If multiple match:
- Prefer the doc whose name exactly contains the date.
- If ambiguity remains, list candidates and ask the user to pick.

### Step 3: Fetch the doc content

Use the available Drive file-read tool to fetch the full content. Gemini notes docs typically have **two tabs**:

1. **Notes** — summary, next steps, paraphrased details with timestamps
2. **Transcript** — word-for-word transcription with speaker attribution

A well-behaved Drive file-read tool returns both tabs in a single fetch (verified: workspace-mcp's `get_drive_file_content` does this). If the tool only returns the first tab, note the limitation and fetch the second tab explicitly via the Docs API tabs feature if available.

### ⚠️ DO NOT extract content from the Gemini email summary

Gemini sends an email when meeting notes are generated. **That email is a summary of the summary** — it contains the high-level recap + next steps but NOT the verbatim transcript with speaker dialogue and timestamps. Reading the email and saving its content is the #1 way agents accidentally lose 90% of the meeting record. The verbatim transcript ONLY lives in the Drive doc, never in the email.

**Rule:** Locate the Drive doc ID (from the email's "Open meeting notes" button, or via the Drive search in Step 2) and fetch the FULL Drive doc via the file-read tool. The email is for discovery only — never for content extraction.

The Step 4.5 verification below catches this failure mode mechanically — by counting timestamps and speaker-attribution lines in the saved file rather than trusting the agent's belief that "this looks complete."

### Step 4: Save to local transcript archive

Write to `{transcripts_repo}/{transcripts_path}/meetings/{meeting-slug}-{date}.md` with this header:

```markdown
# {Meeting Title} — {Weekday}, {Month} {Day}, {Year}

**Source:** Gemini meeting notes + full transcript
**Google Doc:** {doc URL}
**Fetched via:** {tool used} ({google_account}) — {fetch date}
**Meeting start:** {time if known} | **Duration:** {duration if known}

---

{full doc content — both tabs}
```

If a file already exists at that path:
- Check if it's identical to what was just fetched. If yes, report "already synced" and skip.
- If different (Gemini sometimes regenerates), prefer the newly-fetched version but preserve the old one as `{path}.old-{timestamp}.md` so nothing is lost.

### Step 4.5: 🚨 MANDATORY VERIFICATION — confirm both halves landed

Before declaring the meeting fetched, **verify the saved file contains BOTH the notes summary AND the verbatim transcript.** A summary-only save is a silent failure that costs hours later when someone needs the actual dialogue and finds only paraphrase.

**Run the verifier:**

```bash
python3 <synthesis-meeting-transcripts-root>/verify_transcripts.py \
    {transcripts_repo}/{transcripts_path}/meetings/ \
    --only-incomplete
```

The script counts timestamp markers (`00:01:31`-style) in each meeting file. A real Gemini transcript has ~5–50 timestamps; a summary-only save has 0–2. If the just-saved file shows `INCOMPLETE`, re-fetch the Drive doc and re-save — your earlier extraction missed the Transcript tab.

**Reading the summary line.** `--only-incomplete` narrows the listed rows, never the counts: the `Total:` line always describes the whole audited corpus and appends `(listing filtered to incomplete only)`. So a clean run reports the real corpus size with `0 incomplete` — an empty listing under a real total is the all-clear, not a failed invocation. A wrong path is a distinct outcome: `ERROR: not a directory` (or `no .md files found`) on stderr, exit code 2. In `--json`, `total_files` is the corpus and `listed_count` is the rows.

**Failure modes this catches:**
- Saved the Gemini email body instead of the Drive doc
- Read only the first tab of a multi-tab doc
- Wrote a curated summary on top of the email and forgot the verbatim half
- Drive file-read tool returned an abbreviated form

**This step is not optional.** Saving a meeting transcript without the verbatim section is the failure mode that prompted this verification step — a class of error where an agent silently substitutes a summary for the actual substance the protocol requires.

If the verifier is missing or unrunnable in the current environment, you MUST manually grep the saved file for ≥5 timestamp markers before declaring done:

```bash
grep -cE '^\*?\*?[0-9]+:[0-9]+(:[0-9]+)?\*?\*?' <saved-file>
```

If count < 5, you have not saved the full transcript. Re-fetch the Drive doc.

**When the source Doc legitimately has no transcript section** (Google Meet was recorded but transcription was not enabled — common for casual 1:1s, training sessions, and meetings hosted by people who don't run Gemini): add the literal marker `<!-- VERIFIER: no-source-transcript -->` somewhere in the local file. The verifier will accept it as `OK (no-source-transcript)` rather than `INCOMPLETE`. Include a one-line human explanation alongside the marker so future readers know why the file has no transcript section.

**File-name exclusions** the verifier silently skips (it doesn't audit them):
- `_*.md` — meta/TODO/index files (e.g., `_BACKFILL_TODO.md`)
- `gdoc-*.md` — Google Doc imports (not meetings)
- `email-*.md` — synced email threads (not meetings)

If you want to keep one of these in the meetings directory but still audit it, rename it without the excluded prefix.

### Step 4.6: Verify source grade before attribution

Before a quote, approval, warning, decision, action owner, or close paraphrase
cites an artifact as primary, classify the artifact and then bind the claim to
one raw message location:

```bash
python3 <synthesis-meeting-transcripts-root>/transcript_primary.py \
    classify <artifact> --json

python3 <synthesis-meeting-transcripts-root>/transcript_primary.py \
    authorize-attribution <artifact> \
    --location 'permalink:https://example.slack.com/archives/C123/p1700000000000001' \
    --json
```

`classify` is a diagnostic and never issues authority. A derived artifact exits
1 even when it calls itself a transcript. `authorize-attribution` also exits 1
unless the file has dense, complete raw provider-message records and the
supplied `permalink:` or `message_ts:` belongs to one of those records in the
same input bytes. A
`thread_ts:` identifies a conversation, not the exact message supporting a
claim, so it is not sufficient for attribution authority.

The receipt expires when the file's bytes change. It does not verify semantic
fidelity, speaker identity beyond the stored labels, capture completeness
outside the artifact, or whether a later consumer cites the verified message
honestly; those limits remain in every result.

### Step 5: Update indices (optional)

If the project uses a daily action plan or CONTEXT.md that tracks meeting transcripts:
- Add a reference to the saved transcript.
- Note any decisions / action items surfaced in the Notes section.

### Step 6: Cleanup and commit

- Never leave downloaded transcripts in `~/Downloads/`. The whole point of this skill is to bypass that path.
- Commit the new transcript file to the transcripts_repo with a descriptive message.
- Push if the repo is normally push-on-save.

---

## When Multi-Account Matters

Anthropic's hosted Gmail and Drive connectors support **one Google account each** (as of early 2026). If the user routinely needs transcripts from a work account different from their personal account, they'll hit this limit.

**Workarounds:**

1. **Switch the connector account.** Works if the user primarily uses one account. Tedious if they switch often.
2. **Use a self-hosted multi-account MCP server.** Recommended: [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp). A bundled setup helper is in this skill's `optional-workspace-mcp/` directory — it provides `start.sh`, `stop.sh`, `install-autostart.sh` (macOS + Linux), and a cross-platform `fetch-meeting.sh` that shells out to the MCP server directly for deterministic pulls.
3. **Use one Claude account per Google account.** Claude Desktop can run two separate instances (macOS: `open -n -a "Claude" --args --user-data-dir=...`), each signed into a different Claude account with different connectors. Heaviest setup.

The skill's Step 2 and Step 3 work identically across all three paths. Config only needs to specify `google_account`; how authentication is wired up is the user's problem to solve once.

---

## Date Verification

Before writing any dated file, cross-check the target date against at least two independent signals:

1. The system date (`date`)
2. The Google Doc's `modifiedTime` from Drive search results
3. The user's stated meeting date if explicit

Same discipline as the sibling Slack sync skill in this repo. The `currentDate` system value is captured at session start — if a session crosses midnight, that cached value goes stale and subsequent dates will be wrong.

---

## Integration With synthesis-daily-rituals

This skill can be invoked from the daily rituals' Day-Start Step 2b ("Meeting Transcripts") as an automated alternative to the manual Downloads-folder-scanning path. The rituals skill calls this one with the day's scheduled meetings (from the calendar MCP, if configured), fetching transcripts for any that have already completed.

See the daily rituals skill for the integration contract.

---

## Why Tool-Agnostic Matters

Most teams use Anthropic's hosted Gmail + Drive connectors — that's the default and it works. This skill is intentionally built so that the common path "just works" with the default connectors. The multi-account self-hosted route exists for users like the author whose work life spans multiple Google Workspace domains, but it's deliberately optional and lives in a subdirectory so it doesn't clutter the core workflow for users who don't need it.

If a future MCP ecosystem produces a multi-account Gmail/Drive connector with Anthropic-hosted convenience, this skill should work against that too with zero changes. The workflow stays; the tool bindings update.
