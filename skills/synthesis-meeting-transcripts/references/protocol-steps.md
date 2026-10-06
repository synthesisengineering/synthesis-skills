# Protocol steps 1 to 6

The single-meeting path, as written in 0.14.0. An explicit user request runs these steps directly; a ritual sync runs Step 0 in SKILL.md, which runs Steps 2 to 5 for every declared member. Date verification and the daily-rituals integration follow the steps.

Contents:
- Step 1: Resolve the meeting
- Step 2: Find the Gemini meeting doc
- Step 3: Fetch the doc content (stable tab IDs, envelopes, coverage reasons)
- Do not extract content from the Gemini email summary
- Step 4: Save to local transcript archive (the header block)
- Step 4.5: Mandatory verification with `verify_transcripts.py`, the no-source marker, file-name exclusions
- Step 4.6: Verify source grade with `transcript_primary.py` before attribution
- Step 4.7: Extract candidate commitments with `extract_commitments.py`
- Step 4.8: Stamp confirmed commitments with their owner
- Step 5: Update indices; Step 6: Cleanup and commit
- Date Verification
- Integration With synthesis-daily-rituals

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

Unwrap every JSON-RPC/MCP tool-result envelope with the optional client's `call_tool_text` before reading text. An outer or nested tool error is unknown coverage. Select the transcript by the provider's stable tab ID through `document_tabs.select_tabs`, never by title, order, or a regular expression over flattened text. Missing tab inventory, incomplete tab inventory, missing content, absent declared tab, and empty returned tab have distinct reasons. Only a complete tab inventory establishes `transcript-tab-absent`; neither an error nor a flattened summary authorizes a no-source marker. Preserve every returned notes/transcript byte and the provider's tab IDs. Connector adapters must actually expose these capabilities; capability absence is a surfaced readiness gap.

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
**Source ID:** {provider}:{source document ID}
**Transcript tab ID:** {stable provider tab ID, when present}
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
    --file {exact-newly-saved-file} --json
```

Pass every newly saved file with repeatable `--file`, or use `--saved-manifest` containing the exact absolute paths and SHA-256 digests produced by this save. A directory scan is a separate corpus diagnostic and cannot substitute for exact-set verification. Missing, changed, aliased, unreadable, or duplicate paths refuse verification. The script counts timestamp markers (`00:01:31`-style) in each meeting file. A real Gemini transcript has ~5–50 timestamps; a summary-only save has 0–2. If the just-saved file shows `INCOMPLETE`, re-fetch the Drive doc and re-save — your earlier extraction missed the Transcript tab.

**Reading the summary line.** `--only-incomplete` narrows the listed rows, never the counts: the `Total:` line always describes the whole audited corpus and appends `(listing filtered to incomplete only)`. So a clean run reports the real corpus size with `0 incomplete` — an empty listing under a real total is the all-clear, not a failed invocation. A wrong path is a distinct outcome: `ERROR: not a directory` (or `no .md files found`) on stderr, exit code 2. In `--json`, `total_files` is the corpus and `listed_count` is the rows.

**Failure modes this catches:**
- Saved the Gemini email body instead of the Drive doc
- Read only the first tab of a multi-tab doc
- Wrote a curated summary on top of the email and forgot the verbatim half
- Drive file-read tool returned an abbreviated form

**This step is not optional.** Saving a meeting transcript without the verbatim section is the failure mode that prompted this verification step — a class of error where an agent silently substitutes a summary for the actual substance the protocol requires.

If the verifier is missing or unrunnable, report verification unavailable and preserve the saved bytes and gap. A grep threshold cannot establish an exact saved-file receipt or authorize the watermark.

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

### Step 4.7: Extract candidate commitments (v0.10.0)

Verification proves the transcript is faithful; nothing yet asks whether
anything in it is owed. Run the scanner over the saved file:

```bash
python3 <synthesis-meeting-transcripts-root>/extract_commitments.py \
    {saved-file} [--speaker "{principal}"]
```

A Gemini timestamp carries across its entire dialogue block until the next timestamp or section boundary; missing times remain null. It flags first-person commitment shapes (`I'll`, `I will`, `of course`,
`let me`, `send me`, `I promise`, `by <date>`) with timestamps and
speakers. Present every candidate for the principal to confirm **in the
same turn as the filing** — timestamp, speaker, quote. The scanner never
creates tasks, files, or calendar entries, and neither do you on its
output alone: an unconfirmed candidate is not an obligation.

### Step 4.8: Stamp confirmed commitments with their owner (v0.11.0)

A confirmed commitment belongs to exactly one workspace (§3). Route it
by the daily-rituals ownership rules — manifest owner, deletion-unit
test, movable-item seat — and record the stamp with the item:

```bash
python3 <synthesis-meeting-transcripts-root>/extract_commitments.py \
    --stamp --owner "{workspace}" --owner-rule "{1|2|3|candidate-confirmed}"
```

`candidate-confirmed` covers the commitment no rule claimed that the
principal placed by hand in the confirmation turn. Other seats record
nothing for this commitment — not even a pointer. The stamp refuses a
blank owner or an unknown rule rather than guessing either.

### Step 5: Update indices (optional)

If the project uses a daily action plan or CONTEXT.md that tracks meeting transcripts:
- Add a reference to the saved transcript.
- Note any decisions / action items surfaced in the Notes section.

### Step 6: Cleanup and commit

- Never leave downloaded transcripts in `~/Downloads/`. The whole point of this skill is to bypass that path.
- Commit the new transcript file to the transcripts_repo with a descriptive message.
- Push if the repo is normally push-on-save.

## Date Verification

Before writing any dated file, cross-check the target date against at least two independent signals:

1. The system date (`date`)
2. The Google Doc's `modifiedTime` from Drive search results
3. The user's stated meeting date if explicit

Same discipline as the sibling Slack sync skill in this repo. The `currentDate` system value is captured at session start — if a session crosses midnight, that cached value goes stale and subsequent dates will be wrong.

## Integration With synthesis-daily-rituals

This skill can be invoked from the daily rituals' Day-Start Step 2b ("Meeting Transcripts") as an automated alternative to the manual Downloads-folder-scanning path. The rituals skill calls this one with the day's scheduled meetings (from the calendar MCP, if configured), fetching transcripts for any that have already completed.

See the daily rituals skill for the integration contract.
