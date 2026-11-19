# Protocol steps 1 to 6: one meeting

The single-meeting path. A request that names one meeting runs these steps for that meeting; a ritual sync runs
Steps 2 to 5 for every declared member from Step 0 ([declared-window-sweep.md](declared-window-sweep.md)). Date
verification and the daily-rituals hand-off follow the steps.

Contents:
- Step 1: Resolve the meeting
- Step 2: Find the Gemini meeting doc
- Step 3: Fetch the doc content (stable tab IDs, envelopes, coverage reasons)
- The Gemini email is for discovery only
- Step 4: Save to the local transcript archive (the header block)
- Step 4.5: Verify that both halves landed (`verify_transcripts.py`, the no-source marker, skipped file names)
- Step 4.6: Resolve attribution from the verbatim transcript
- Step 4.7: Extract candidate commitments (`extract_commitments.py`)
- Step 4.8: Stamp confirmed commitments with their owner
- Step 5: Update indices; Step 6: Cleanup and commit
- Date Verification
- Integration With synthesis-daily-rituals

### Step 1: Resolve the meeting

From the meeting the user names ("today's standup", "Monday's design sync", "the 2 pm design review"), resolve:

- **Meeting name:** look it up in `meeting_patterns`; otherwise use `generic_pattern` with the name substituted.
- **Date:** parse a relative date ("today", "yesterday", "Monday") against the system date, checked with `date`.
- **Account:** `google_account` from the config, unless the user names another configured account ("from my work
  account", "from my personal account").

### Step 2: Find the Gemini meeting doc

Search Drive with the session's Drive search tool for docs matching the resolved pattern, with a `modifiedTime`
filter that brackets the target date. A typical query:

```
name contains "Daily Standup" and name contains "Notes by Gemini" and modifiedTime > "2026-04-21T00:00:00" and modifiedTime < "2026-04-22T00:00:00"
```

When no doc matches, widen the search in this order:

1. Search again a day wider on each side, since time zones shift `modifiedTime`.
2. Search Gmail for the Gemini notes email (`from:gemini-notes@google.com`, the meeting name in the subject, on the
   target date); it usually links to the doc.
3. Report to the user that no doc was found, and stop. A guessed or reconstructed doc is never saved.

When several docs match, take the one whose name contains the date exactly; if more than one remains, list them
and ask the user to pick.

### Step 3: Fetch the doc content

Fetch the whole doc with the session's Drive file-read tool. A Gemini notes doc usually has two tabs:

1. **Notes:** the summary, next steps and paraphrased details with timestamps.
2. **Transcript:** the word-for-word transcription with speaker attribution.

Unwrap every JSON-RPC or MCP tool-result envelope before reading the text (the optional client's
`mcp_client.call_tool_text` does this). An outer or nested tool error means coverage is unknown.

Select the transcript by the document's stable tab ID (binding rule 5); position, or a regular expression over the
flattened text, never selects it. A tab title selects only when exactly one tab in a complete tab list carries it;
record the chosen tab's ID either way. With workspace-mcp, `fetch-meeting.py` lists the tabs
(`inspect_doc_structure`) and reads each one (`get_doc_as_markdown`).

Each failure keeps its own reason: an unreadable tab list, an incomplete tab list, a title two tabs share, an absent
declared tab, an empty returned tab and a tool error. Only a complete tab list establishes `transcript-tab-absent`;
an error or a flattened summary never justifies the no-source marker (binding rule 7). Keep every returned notes
and transcript byte, and the provider's tab IDs. A connector that cannot list tabs leaves the choice to you: read
the document and say which part you saved.

### The Gemini email is for discovery only

Gemini sends an email when meeting notes are generated. The email is a summary of the summary: the high-level recap
and the next steps, without the transcript's speaker dialogue and timestamps. Saving the email in place of the doc
is the most common way a fetch loses most of the meeting record, because the verbatim transcript lives only in the
Drive doc.

Find the Drive doc ID (from the email's "Open meeting notes" button, or with the Step 2 search) and fetch the full
doc with the file-read tool. The email is for finding the doc, never for content. Step 4.5's verifier catches an
email saved as a transcript mechanically, by counting timestamps and speaker lines in the saved file rather than
trusting a sense that the file looks complete.

### Step 4: Save to the local transcript archive

Write to `{transcripts_repo}/{transcripts_path}/meetings/{meeting-slug}-{date}.md` with exactly this header:

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

When a file already exists at that path:

- If it is identical to what was just fetched, report "already synced" and skip it.
- If it differs (Gemini sometimes regenerates its notes), save the newly fetched version and keep the old one as
  `{path}.old-{timestamp}.md`, so nothing is lost.

### Step 4.5: Verify that both halves landed

A meeting counts as fetched only when the saved file holds both the notes summary and the verbatim transcript
(binding rule 6). A summary-only save fails silently and costs hours later, when someone needs the actual dialogue
and finds only paraphrase. Run the verifier on the exact file just saved:

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/verify_transcripts.py" \
    --file {exact-newly-saved-file} --json
```

It prints a row per file with its status (`OK`, `INCOMPLETE` or `OK (no-source-transcript)`) and its timestamp and
speaker counts, then a `Total:` line, and exits 0 when every file is complete, 1 when one is incomplete and 2 on a
bad path. Pass every newly saved file with a repeated `--file`, or give `--saved-manifest` a JSON list of the exact
absolute paths and SHA-256 digests this save produced. A missing, changed, aliased, unreadable or duplicate path
refuses verification. A directory scan is a separate diagnostic of the whole corpus and never stands in for
verifying the exact set.

The verifier counts timestamp markers (`00:01:31`-style) and speaker lines in each file. A real Gemini transcript has
about 5 to 50 timestamps; a summary-only save has 0 to 2. When the file just saved shows `INCOMPLETE`, fetch the
Drive doc again and re-save it: the earlier extraction missed the Transcript tab.

**Reading the summary line.** `--only-incomplete` narrows the listed rows, never the counts: the `Total:` line
always describes the whole audited corpus and adds `(listing filtered to incomplete only)`. A clean run reports the
real corpus size with `0 incomplete`, so an empty listing under a real total is the all-clear, not a failed run. A
wrong path is a different outcome: `ERROR: not a directory` (or `no .md files found`) on stderr, exit code 2. In
`--json`, `total_files` is the corpus and `listed_count` is the rows.

What the verifier catches:

- the Gemini email body saved instead of the Drive doc;
- only the first tab of a multi-tab doc read;
- a curated summary written over the email, with the verbatim half missing;
- an abbreviated form returned by the Drive file-read tool.

The step exists because agents have saved a summary where the protocol requires the verbatim transcript, silently
putting paraphrase in place of the substance, so it runs on every save.

When the verifier is missing or will not run, report verification as unavailable and keep the saved bytes and the
gap. A grep threshold cannot stand in for an exact saved-file receipt, and it does not move the watermark.

When the source doc has no transcript (Google Meet recorded without transcription, which is common for casual 1:1s,
training sessions and meetings hosted by people who don't run Gemini), add the literal marker
`<!-- VERIFIER: no-source-transcript -->` to the local file, with a one-line explanation beside it so later readers
know why there is no transcript section. The verifier then reports `OK (no-source-transcript)` instead of
`INCOMPLETE`.

File names the verifier skips without auditing:

- `_*.md`: meta, TODO and index files (for example `_BACKFILL_TODO.md`);
- `gdoc-*.md`: Google Doc imports, not meetings;
- `email-*.md`: synced email threads, not meetings.

To keep one of these in the meetings folder and still audit it, rename it without the skipped prefix.

### Step 4.6: Resolve attribution from the verbatim transcript

Before a quote, approval, warning, decision, action owner or close paraphrase cites a meeting record, find the moment
in the verbatim transcript (the saved file, or transcript lines the user supplies) and take the actor from the
speaker line there. When that line names the actor, the attribution is settled; write it. A tool summary, a
"Decisions" section or an action-item list is a lossy derivative: it can say what happened, never who did it.
Passive constructions in AI notes ("he was warned", "it was decided") have lost their actor. When the transcript
does not settle who acted, keep the passive form or say the actor is unknown; never fill the slot with the most
salient person. The hierarchy of evidence is in
[transcript-primary-and-commit-gate.md](transcript-primary-and-commit-gate.md), and the incident that taught it in
the v0.4.0 release note ([release-notes.md](release-notes.md)). `verify_transcripts.py` (Step 4.5) is what tells a
transcript from a summary; a file it calls `INCOMPLETE` cannot support attribution.

### Step 4.7: Extract candidate commitments

After Step 4.5 verifies a newly saved transcript, scan it for anything owed. Verification proves the transcript is
faithful; this step asks whether anything in it is owed.

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/extract_commitments.py" \
    {saved-file} [--speaker "{principal}"]
```

It prints `extract-commitments <version>: <n> dialogue lines`, then one line per candidate,
`[timestamp] Speaker (shape): quote`. It flags first-person commitment shapes (`I'll`, `I will`, `of course`,
`let me`, `send me`, `I promise`, `by <date>`) with their timestamps and speakers. A Gemini timestamp carries across
its whole dialogue block until the next timestamp or section boundary; a missing time stays null. `--speaker` limits
it to one speaker, and `--json` prints the candidates as JSON (`candidates`, each with `timestamp`, `speaker`,
`shape` and `quote`).

Present every candidate for the principal to confirm in the same turn as the filing: timestamp, speaker, quote
(binding rule 9). The scanner never creates tasks, files or calendar entries, and neither do you on its output
alone: an unconfirmed candidate is not an obligation. This step governs the scanner's output; a request about who
committed to what in transcript lines is answered from those lines by Step 4.6, with no confirmation step.

### Step 4.8: Stamp confirmed commitments with their owner

A confirmed commitment belongs to exactly one workspace (§3). Route it by the daily-rituals ownership rules
(manifest owner, deletion-unit test, movable-item seat) and record the stamp with the item:

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/extract_commitments.py" \
    --stamp --owner "{workspace}" --owner-rule "{1|2|3|candidate-confirmed}"
```

It prints `owner: <workspace>` and `owner_rule: <rule>`. `candidate-confirmed` covers a commitment no rule claimed
that the principal placed by hand in the confirmation turn. Other seats record nothing for this commitment, not even
a pointer. The stamp refuses (exit 2) a blank owner or an unknown rule rather than guessing either.

### Step 5: Update indices (optional)

When the project's daily action plan or CONTEXT.md tracks meeting transcripts:

- add a reference to the saved transcript;
- note the decisions and action items the Notes section surfaced, with each actor and owner taken from the
  transcript (Step 4.6).

### Step 6: Cleanup and commit

- Leave nothing in `~/Downloads/`: this skill exists to replace that path (binding rule 11).
- Commit the new transcript file to the transcripts_repo with a descriptive message; its pre-commit gate checks it
  ([transcript-primary-and-commit-gate.md](transcript-primary-and-commit-gate.md)).
- Push when the repository is normally pushed on save.

## Date Verification

Before writing a dated file, cross-check the target date against at least two independent signals (binding rule
10):

1. the system date (`date`);
2. the Google Doc's `modifiedTime` from the Drive search results, which is in UTC, converted to the meeting's time
   zone;
3. the user's stated meeting date, when given;
4. the date in the doc's name, which Step 2 matches.

The sibling Slack sync skill in this repository applies the same check. The session's `currentDate` is captured at
session start; when a session crosses midnight it goes stale, and dates taken from it are wrong.

## Integration With synthesis-daily-rituals

The daily rituals run this skill in each sync: the day-start sync (3c), the mid-day sync and the day-end sync (step
1) run Step 0 for the window ([declared-window-sweep.md](declared-window-sweep.md)), the automated alternative to
scanning the Downloads folder by hand, and record the window with the meetings watermark. The rituals skill holds
the integration contract.
