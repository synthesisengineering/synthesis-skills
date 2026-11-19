# Preserved text: meeting transcripts, retired in milestone M3 and in 1.3.0

Read this only to review what was cut. The passages below are no longer
instructions; they are kept verbatim so the reasoning stays readable (ruling D8).

Contents:
- Retired in 1.3.0, the rewrite to the D8 standard: why each part changed, then the
  1.2.1 text verbatim (SKILL.md first)
- Why the scripts were cut or slimmed (M3)
- Replaced passages, file by file (verbatim, M3)
- Test fixtures of the cut transcript_primary.py (verbatim, M3)

## Retired in 1.3.0: the rewrite to the D8 standard

1.3.0 rewrote the skill's instruction text to the repository's rewrite standard,
`docs/skill-writing.md` (writing rules W1 to W19). Every rule's new place is in
[coverage-map.md](coverage-map.md). A passage moved word for word to another file is
recorded there and not repeated here.

### SKILL.md

Why each part changed:

- **Opening paragraph.** It described only the fetch. The skill also verifies each saved
  file, takes attribution from the transcript and puts scanner candidates before the
  principal, so the paragraph now says all four (format rule 2).
- **Binding rules 1 to 11.** Rewritten to W5 (the action as the bold head, then the scope
  and the reason) and W14 (each rule names what it governs), and made complete on their
  own (W2): rule 2 took the two-hour bound and rule 3 the "read every page" step from
  Step 0, rule 4 the length point from the v0.5.0 fetch-time rule, rule 5 the recorded
  tab ID and rule 7 the failed-fetch case from Step 3, and rule 8 "asked" and "promised"
  from the v0.4.0 note and "say the actor is unknown" from Step 4.6. Rules 9 and 8 carry
  the fix for the defect the skill's evaluation found: with the skill loaded, a model
  asked the user to confirm a commitment it had read directly from transcript lines the
  user pasted, which it did not do without the skill. Rule 9's "A scanned commitment"
  meant scanner output but read as any commitment; it now names the commitment scanner
  and says it covers scanner output only, and rule 8 says to attribute directly when a
  transcript line names the actor. "Unclosed gap" became "open gap" and "no-source
  attestation" the no-source marker, one name for each (format rule 11).
- **The line above rule 1.** New: it says the rules hold against a contrary request and
  how to answer one (W8, format rule 11).
- **Contents.** Lists the new Step 0 reference, describes the evidence reference by what
  it now holds, and says when to read the coverage map and this file.
- **Protocol, Step 0.** Moved to references/declared-window-sweep.md and rewritten (W18:
  a procedure for one kind of request lives in its own reference, and SKILL.md routes to
  it). Its steps now run in the order the work does: inventory, enumerate, fetch, account,
  and only then advance the watermark, which the old text placed before the steps. The
  heading's version tag went to the release notes, and "does not get a vote" became the
  plain rule it stood for. It had stayed in SKILL.md because a daily-rituals test read
  its phrases there; that test stopped reading them on 2026-10-05.
- **The closing pointer to Steps 1 to 6.** Replaced by "Which path", which routes each
  kind of request to its procedure (W18).

The 1.2.1 SKILL.md, verbatim:

````markdown
---
name: synthesis-meeting-transcripts
description: "Fetch AI-generated meeting notes and full transcripts into local markdown, and verify an artifact is primary before it supports attribution. Tool-agnostic: Gmail/Drive MCPs or local exports. Use to fetch, pull, sync, download, import, classify or verify a meeting transcript."
license: "Apache-2.0"
depends_on: []
metadata:
  author: "Rajiv Pant"
  version: "1.2.1"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
  category: chief-of-staff
---

# Synthesis Meeting Transcripts

A protocol for fetching AI-generated meeting transcripts from the user's Gmail and Google Drive into a local markdown archive. Designed for teams where Google Meet + Gemini (or equivalents) produce meeting notes + word-for-word transcripts that live in Google Docs, and the user wants them mirrored locally alongside their project context.

## Binding rules

1. **Declared means fetched.** A ritual sync runs Step 0 below: enumerate the declared set, fetch every member, and account for each as fetched or as an unclosed gap. Relevance is judged after fetching, never before.
2. **Unknown coverage is a visible gap.** Unknown authentication, tab enumeration or archive coverage never becomes a no-source attestation, and the meetings watermark never moves past an unsaved doc or a meeting that may still be under way.
3. **A Drive search listing cannot prove a window complete,** because it omits the provider completeness flag. A full page, a next-page token, an incompleteSearch warning or a failed search leaves the window open; say so in the report.
4. **The verbatim transcript is the only primary source.** Fetch it in full whenever the source has one. The Gemini email is for discovery only, never for content.
5. **Select the transcript by the document's stable tab ID,** never by order or a regular expression; a title only when exactly one tab in a complete tab list carries it. Only a complete tab list establishes `transcript-tab-absent`.
6. **Verify both halves landed** with `verify_transcripts.py --file <exact saved file> --json` before calling a meeting fetched. A directory scan does not substitute.
7. **Use the `<!-- VERIFIER: no-source-transcript -->` marker only when the source truly has no transcript,** with a one-line reason beside it.
8. **Never derive attribution from a tool summary.** Who warned, decided, approved or owns comes from the verbatim transcript; if it does not say, keep the passive form.
9. **A scanned commitment is a candidate until the principal confirms it** in the same turn. Stamp each confirmed one with exactly one owner; nothing is created from scanner output alone.
10. **Cross-check every date against at least two independent signals** before writing a dated file.
11. **Never leave transcripts in `~/Downloads/`.** Commit them to `transcripts_repo`, whose pre-commit gate refuses a summary saved as a transcript.

## Contents

- [references/protocol-steps.md](references/protocol-steps.md): Steps 1 to 6 with every command (`verify_transcripts.py`, `extract_commitments.py`), the email warning, the no-source marker, the attribution rule, date verification and the daily-rituals integration. Read it before fetching a meeting, and for each member of a Step 0 sweep.
- [references/transcript-primary-and-commit-gate.md](references/transcript-primary-and-commit-gate.md): the v0.4.0 hierarchy of evidence and the v0.5.0 pre-commit gate. Read it before citing anything from a meeting record, and when setting up a transcripts repo.
- [references/setup.md](references/setup.md): the `.agents/meeting-transcripts.yaml` schema (required: `workspace`, `google_account`, `transcripts_repo`, `transcripts_path`), prerequisites, multi-account options and what `start.sh` sets for the server. Read it when a project has no config, a config is refused, or an account is unreachable.
- [references/release-notes.md](references/release-notes.md) and [references/earlier-version-history.md](references/earlier-version-history.md): release notes from v0.2.0 to 1.2.1. Read them when a result differs from what an earlier version did.
- [optional-workspace-mcp/README.md](optional-workspace-mcp/README.md): the optional self-hosted multi-account server helper: `fetch-meeting.py` (one meeting, or `--window FROM THROUGH` for saved and unsaved docs), `mcp_client.py`, the service scripts and `doctor.sh`.
- [references/coverage-map.md](references/coverage-map.md): where each part of the earlier 0.14.0 text now lives, and the M3 script changes.
- [references/preserved.md](references/preserved.md): the retired acquisition and attribution-receipt text, verbatim. Read it only to review the cut.
- Protocol, Step 0: below.

## Protocol

### Step 0: Declared-window sweep (v0.9.0 — how "declared means fetched" executes)

The agent does not get a vote on which declared items are interesting. Relevance is judged after fetching, never before. Every declared item is fetched or retained as an unclosed gap.

Inventory the window first: with the optional workspace-mcp helper, `python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py" --window FROM THROUGH` lists every doc the declared patterns find, each marked saved or unsaved, and the moment the watermark may advance to; its `scope` names the only patterns searched, and `undeclared` lists Gemini notes docs no declared pattern finds (declare a recurring one to cover it). With hosted connectors, run the same Drive search per declared pattern with the window's `modifiedTime` bounds, follow every page, and compare each doc ID with the IDs the saved files name: a `**Source ID:**` header, a Google Doc link, or the first backticked ID on a `> Source:` line (`` > Source: Gemini doc `<id>` ``), the three forms `--window` reads.

HTTP health alone is not sign-in: a read as the declared account shows which account answers. Never filter by meeting title or perceived relevance. Then advance with `python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-daily-rituals/scripts/sync_watermark.py" advance --workspace <W> --surface meetings --through <T>`, where T, written with its offset, is the earliest of the window's end (Drive reads its days as UTC), two hours before the check ran (a meeting under way may have no doc yet) and one second before each unsaved doc was created. A failed search, a full page, a next-page token, Drive's incompleteSearch warning or an unknown tab list keeps the watermark where it is.

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

Steps 1 to 6, the single-meeting path whose Steps 2 to 5 the sweep runs for every member, are in [references/protocol-steps.md](references/protocol-steps.md).
````

### references/protocol-steps.md

Why each part changed:

- **Title and opening paragraph.** The file states the steps as they stand rather than "as written in 0.14.0",
  and points to the new Step 0 reference.
- **Contents.** Entries renamed with their steps.
- **Step 1.** Reworded; the example "Monday's PDE sync" became a generic "Monday's design sync".
- **Step 2.** The fallbacks are numbered in the order they run (format rule 13), and "Do not guess or fabricate"
  became the positive "A guessed or reconstructed doc is never saved" (W12).
- **Step 3.** Reworded, the behavior first (W12), with pointers to binding rules 5 and 7; "a no-source marker"
  became "the no-source marker", the one name the skill uses (format rule 11).
- **The email warning.** The heading's alarm emoji and capitals came out (W9), "#1 way agents accidentally lose 90%
  of the meeting record" became the plain claim it made, and the "Rule:" label went, since binding rule 4 holds the
  rule.
- **Step 4.** The header is marked as the exact template it is (W17); the existing-file cases reworded.
- **Step 4.5.** The heading's emoji and "MANDATORY" came out (W9; binding rule 6 holds the invariant), what the
  verifier prints and its exit codes were added (format rule 7), and "This step is not optional" became the reason it
  runs on every save.
- **Step 4.6.** The heading is kept, since a test reads it. Added "the saved file, or transcript lines the user
  supplies" and "When that line names the actor, the attribution is settled; write it" (W15, W16), for the defect
  the skill's evaluation found; "attribution vacuums" became "have lost their actor"; the incident pointer goes to
  the v0.4.0 note, back in release-notes.md.
- **Step 4.7.** The heading's version tag went to the release notes; what the scanner prints and its JSON were added
  (format rule 7); a last sentence says the step governs the scanner's output and that a question about who
  committed to what in transcript lines is answered by Step 4.6, for the same defect.
- **Step 4.8.** The heading's version tag went to the release notes; what the stamp prints and its exit code were
  added.
- **Step 5.** Decisions and action items are noted with their actor and owner taken from the transcript, so the
  step agrees with binding rule 8 (format rule 11: a conflict left open makes a model stop to ask).
- **Step 6.** The behavior first, with pointers to binding rule 11 and the commit gate.
- **Date Verification.** Adds the UTC conversion and the date in the doc's name, matching binding rule 10.
- **Integration With synthesis-daily-rituals.** The old step number (Day-Start Step 2b) and the calendar input had
  gone stale: the rituals run Step 0 over the declared patterns in the day-start (3c), mid-day and day-end (step 1)
  syncs.

The 1.2.1 references/protocol-steps.md, verbatim:

````markdown
# Protocol steps 1 to 6

The single-meeting path, as written in 0.14.0. An explicit user request runs these steps directly; a ritual sync runs Step 0 in SKILL.md, which runs Steps 2 to 5 for every declared member. Date verification and the daily-rituals integration follow the steps.

Contents:
- Step 1: Resolve the meeting
- Step 2: Find the Gemini meeting doc
- Step 3: Fetch the doc content (stable tab IDs, envelopes, coverage reasons)
- Do not extract content from the Gemini email summary
- Step 4: Save to local transcript archive (the header block)
- Step 4.5: Mandatory verification with `verify_transcripts.py`, the no-source marker, file-name exclusions
- Step 4.6: Resolve attribution from the verbatim transcript
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

Unwrap every JSON-RPC/MCP tool-result envelope (the optional client's `mcp_client.call_tool_text` does this) before reading text. An outer or nested tool error is unknown coverage. Select the transcript by the document's stable tab ID, never by order or a regular expression over flattened text; a tab title selects only when exactly one tab in a complete tab list carries it, and the chosen tab's ID is then recorded. With workspace-mcp, `fetch-meeting.py` lists the tabs (`inspect_doc_structure`) and reads each one (`get_doc_as_markdown`). An unreadable tab list, an incomplete tab list, a title two tabs share, an absent declared tab, an empty returned tab and a tool error have distinct reasons. Only a complete tab list establishes `transcript-tab-absent`; neither an error nor a flattened summary authorizes a no-source marker. Preserve every returned notes/transcript byte and the provider's tab IDs. A connector that cannot list tabs leaves the choice to you: read the document and say which part you saved.

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
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/verify_transcripts.py" \
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

### Step 4.6: Resolve attribution from the verbatim transcript

Before a quote, approval, warning, decision, action owner, or close paraphrase
cites a meeting record, find the moment in the verbatim transcript and take the
actor from the speaker line there. A tool summary, a "Decisions" section or an
action-item list is a lossy derivative: it can say what happened, never who did
it. Passive constructions in AI notes ("he was warned", "it was decided") are
attribution vacuums. When the transcript does not settle who acted, keep the
passive form or say the actor is unknown; never fill the slot with the most
salient person. The canonical incident (2026-07-07) and the hierarchy of evidence
are in [transcript-primary-and-commit-gate.md](transcript-primary-and-commit-gate.md).
`verify_transcripts.py` (Step 4.5) is what tells a transcript from a summary; a
file it calls `INCOMPLETE` cannot support attribution.

### Step 4.7: Extract candidate commitments (v0.10.0)

Verification proves the transcript is faithful; nothing yet asks whether
anything in it is owed. Run the scanner over the saved file:

```bash
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/extract_commitments.py" \
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
python3 -s "$HOME/.synthesis/v5/current/skills/synthesis-meeting-transcripts/extract_commitments.py" \
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
````

### references/transcript-primary-and-commit-gate.md

Why: the file now states the rules as they stand, in the present tense (format rule 12), and its title, opening and
contents say so. The v0.4.0 and v0.5.0 notes it held moved word for word back to release-notes.md, into their
places in the 0.14.0 order, where the rest of the release history is; the coverage map records the move.

The 1.2.1 opening, verbatim:

````markdown
# Transcript-primary sourcing and the commit gate

The v0.4.0 hierarchy of evidence for every fetched meeting record, and the v0.5.0 fail-closed commit gate that keeps a summary from being committed in place of a transcript, both as written.

Contents:
- v0.4.0: the verbatim transcript is the only primary source; summaries are lossy derivatives; no attribution from a summary; summary-only warnings; agent-authored headers
- v0.5.0: the transcripts-repo pre-commit hook, the fetch-time rule, the hardened verifier
````

### references/release-notes.md

Why: the v0.4.0 and v0.5.0 notes are back in this file, so its opening no longer sends the reader elsewhere for them.

````markdown
The notes for 1.0.0 and later, newest first, then the release notes that opened the 0.14.0 SKILL.md, in their original order. The v0.4.0 and v0.5.0 notes carry live rules, so they are in [transcript-primary-and-commit-gate.md](transcript-primary-and-commit-gate.md); v0.6.0 to v0.11.0 are in [earlier-version-history.md](earlier-version-history.md).
````

## Why the scripts were cut or slimmed

Verdicts from the v5 code evaluation (tool scripts, meeting transcripts):

- `transcript_primary.py` (461 lines): CUT. It classified a file as raw provider
  records or a derived summary and issued a hash-bound receipt authorizing one
  attribution. The need it served is real (lesson 2026-07-07, passive AI-note
  attribution drift: "He was warned" became a warning from the meeting
  counterpart); it is a reading rule, kept as binding rule 8, Step 4.6 and
  transcript-primary-and-commit-gate.md. Telling a transcript from a summary is
  `verify_transcripts.py`'s job, and only the old release wiring consumed the
  receipt. Its acceptance manifest (`acceptance-suite.yaml`) and fixtures went with it.
- `optional-workspace-mcp/google_read.py` (174) and `workspace_mcp_read.py` (241):
  CUT. Adapters for the acquisition gate; no meeting-transcripts config on this
  machine ever declared one. What workspace_mcp_read.py learned about the server
  is kept in fetch-meeting.py: tabs come from `inspect_doc_structure` and each
  tab's text from `get_doc_as_markdown`, and a Drive search listing carries no
  completeness flag.
- `optional-workspace-mcp/fetch-meeting.py` (678 to 351), `mcp_client.py` (329 to
  181), `document_tabs.py` (207, folded in): SLIM. Kept: the fetch, tab-ID
  selection with distinct reasons, "an error is not absence", and a saved/unsaved
  list for a window (IR-55, IR-57). Dropped: readiness receipts, raw-response
  custody, the source-inventory seam and the archive publisher. httpx and PyYAML
  were replaced by the standard library (v5 rule: Apple's Python 3.9 must run it).
- `verify_transcripts.py`: KEEP. Its exact-file reader came from the cut
  acquisition module, so it now reads exact bytes itself; it gained
  `from __future__ import annotations` so Apple's Python 3.9 runs it.
- `extract_commitments.py`: KEEP; its docstring no longer names a private person.
- The service scripts: KEEP, with the generic launchd label
  `com.synthesis.workspace-mcp` (requirement R7.4).

## Replaced passages, file by file (verbatim)

### SKILL.md

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
The earlier release notes and rationale are retained in [references/earlier-version-history.md](references/earlier-version-history.md). Before a declared-window sweep, read the mandatory [acquisition evidence contract](../synthesis-daily-rituals/references/acquisition-evidence.md). Unknown authentication, tab enumeration, or archive coverage is a visible gap, never a no-source attestation.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
2. **Unknown coverage is a visible gap.** Unknown authentication, tab enumeration or archive coverage never becomes a no-source attestation; only verified acquisition evidence advances the watermark.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
3. **A rendered Drive inventory cannot authorize interval completion or watermark advancement,** because it omits the provider completeness flag. Use an explicitly configured structured reader; credentials and adapters are never selected automatically.
````

Why: document_tabs.py was folded into fetch-meeting.py (verdict SLIM).

````markdown
5. **Select the transcript by the provider's stable tab ID** through `document_tabs.select_tabs`, never by title, order or a regular expression. Only a complete tab inventory establishes `transcript-tab-absent`.
````

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
8. **Never derive attribution from a tool summary.** Before a quote, approval, decision or owner cites an artifact, run `transcript_primary.py classify` and then `authorize-attribution` on one raw message location.
````

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
- [references/protocol-steps.md](references/protocol-steps.md): Steps 1 to 6 with every command (`verify_transcripts.py`, `transcript_primary.py`, `extract_commitments.py`), the email warning, the no-source marker, date verification and the daily-rituals integration. Read it before fetching a meeting, and for each member of a Step 0 sweep.
````

Why: Contents updated for the scripts that remain and for preserved.md.

````markdown
- [references/release-notes.md](references/release-notes.md) and [references/earlier-version-history.md](references/earlier-version-history.md): release notes from v0.2.0 to 0.14.0. Read them when a result differs from what an earlier version did.
````

Why: Contents updated for the scripts that remain and for preserved.md.

````markdown
- [optional-workspace-mcp/README.md](optional-workspace-mcp/README.md): the optional self-hosted multi-account server helper.
````

Why: Contents updated for the scripts that remain and for preserved.md.

````markdown
- [references/coverage-map.md](references/coverage-map.md): where each part of the earlier 0.14.0 text now lives.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
Use the verified Python acquisition modes documented in [declared acquisition entries](../synthesis-daily-rituals/references/acquisition-entry.md) for supported complete-window reads. They compose the current inventory, stable-tab, publication and watermark owners.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
Probe recorder identity at day-start using the owner's declared read-only adapter; HTTP health alone is not sign-in. Inventory every declared recorder source and account for the exact window, following all pages and retaining raw tool-call references and a same-source positive control. `inventory_documents` in the optional fetch owner provides a bounded adapter seam; never filter by meeting title or perceived relevance. Compare provider/source IDs against exact saved archive headers with `sync_watermark.py acquisition-check`; retain per-source gap decisions. Advance only with the verified acquisition evidence file; unknown enumeration or a missing archive keeps the watermark unchanged.
````

### optional-workspace-mcp/README.md

Why: the acquisition gate (declared acquisition entries, the Google REST and workspace-mcp custody adapters, recorder readiness receipts, the receipt-owned launcher) was cut (verdict CUT); fetch-meeting.py is plain standard-library Python again.

````markdown
## Verified acquisition and one-off lookup

For complete declared account/folder/window acquisition, use the verified
Python health/inventory/fetch route in [declared acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md).
It explicitly selects the Google REST adapter; no service or token fallback
occurs. The documented workspace-mcp plain-text response does not supply stable
tab identity. A title lookup therefore cannot certify full-window coverage.

The separate one-off lookup still uses the local MCP server:

```text
synthesis exec-public synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py standup --date 2026-04-21
```

This mode requires source-native structured tab evidence before a verified save.
Service setup remains in the existing start/install owners and requires the
owner's authorization; acquisition does not install a service.
````

Why: the acquisition gate (declared acquisition entries, the Google REST and workspace-mcp custody adapters, recorder readiness receipts, the receipt-owned launcher) was cut (verdict CUT); fetch-meeting.py is plain standard-library Python again.

````markdown
## Prerequisites

- The verified runtime's selected interpreter contains httpx and PyYAML. Follow
  the dependency setup in the acquisition reference; a temporary uv interpreter
  is not the installed verified runtime.
- The existing meeting-transcripts YAML has the exact account/archive settings.
- MCP lookup additionally needs the declared local server and actual account
  authentication. The direct adapter instead consumes one explicitly referenced
  read token and the declared folder/tab contract; it never acquires a token.

The service doctor reports supervisor/HTTP liveness and retains its 0/1/2 exit
semantics. Its RECORDER UNKNOWN line is intentional. Actual declared account
authentication is observed only by the Python health route, and neither health
plane establishes complete source coverage.
````

### references/protocol-steps.md

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
- Step 4.6: Verify source grade with `transcript_primary.py` before attribution
````

Why: document_tabs.py was folded into fetch-meeting.py (verdict SLIM); the selection rules are unchanged.

````markdown
Unwrap every JSON-RPC/MCP tool-result envelope with the optional client's `call_tool_text` before reading text. An outer or nested tool error is unknown coverage. Select the transcript by the provider's stable tab ID through `document_tabs.select_tabs`, never by title, order, or a regular expression over flattened text. Missing tab inventory, incomplete tab inventory, missing content, absent declared tab, and empty returned tab have distinct reasons. Only a complete tab inventory establishes `transcript-tab-absent`; neither an error nor a flattened summary authorizes a no-source marker. Preserve every returned notes/transcript byte and the provider's tab IDs. Connector adapters must actually expose these capabilities; capability absence is a surfaced readiness gap.
````

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
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
````

### references/release-notes.md

Why: the title gained 1.0.0.

````markdown
# Release notes: 0.14.0, 0.13.0, and v0.2.0 to v0.5.3
````

## Test fixtures of the cut transcript_primary.py (verbatim)

Synthetic, public test data for the cut classifier: a raw provider-message export it accepted and the 128-line structured summary (the engagement-motivating shape) it refused. Kept so the summary shape that once cleared a primary-transcript gate stays on record.

### fixtures/raw-message-transcript.md

````markdown
# Synthetic raw-message transcript

**Artifact type:** provider message export
**Capture bounds:** ten consecutive messages from one synthetic thread
**Content:** public test data only

## Messages

### Participant A — [9:00 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000000000001)
message_ts: `1700000000.000001`
thread_ts: `1700000000.000001`
The first message states the proposed direction.

### Participant B — [9:01 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000001000002)
message_ts: `1700000001.000002`
thread_ts: `1700000000.000001`
The second message asks how the result will be verified.

### Participant A — [9:02 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000002000003)
message_ts: `1700000002.000003`
thread_ts: `1700000000.000001`
The third message names the acceptance boundary.

### Participant C — [9:03 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000003000004)
message_ts: `1700000003.000004`
thread_ts: `1700000000.000001`
The fourth message identifies an unresolved question.

### Participant B — [9:04 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000004000005)
message_ts: `1700000004.000005`
thread_ts: `1700000000.000001`
The fifth message proposes a concrete check.

### Participant A — [9:05 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000005000006)
message_ts: `1700000005.000006`
thread_ts: `1700000000.000001`
The sixth message accepts that check.

### Participant C — [9:06 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000006000007)
message_ts: `1700000006.000007`
thread_ts: `1700000000.000001`
The seventh message records a source limitation.

### Participant B — [9:07 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000007000008)
message_ts: `1700000007.000008`
thread_ts: `1700000000.000001`
The eighth message distinguishes notes from the source.

### Participant A — [9:08 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000008000009)
message_ts: `1700000008.000009`
thread_ts: `1700000000.000001`
The ninth message assigns the final verification.

### Participant C — [9:09 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000009000010)
message_ts: `1700000009.000010`
thread_ts: `1700000000.000001`
The tenth message closes the synthetic thread.
<!-- End of synthetic raw-message fixture. -->
````

### fixtures/structured-summary-128-lines.md

````markdown
# Primary Transcript Review Packet

- This file summarizes a longer source artifact.
- The source artifact is not embedded in this file.
- The prose groups themes instead of preserving message order.
- Names and details are synthetic for this public fixture.
- The heading deliberately overstates the file's evidence grade.

## Executive summary

- The discussion covered delivery, ownership, and sequencing.
- Participants appeared aligned on the immediate objective.
- Several tradeoffs were summarized without exact wording.
- The notes describe outcomes rather than individual messages.
- No raw provider identifiers accompany these statements.

## Themes

- One theme concerned how work should be staged.
- Another concerned who would verify the result.
- A third concerned how the outcome would be communicated.
- The order here was chosen by a summarizer.
- It does not preserve the source conversation's order.

## Decisions

- The group decided to continue with the proposed direction.
- A later validation step was described as required.
- An owner was inferred from the surrounding discussion.
- The exact speaker and wording are not preserved.
- These bullets are derived notes, not raw messages.

## Action items

- Participant A will inspect the generated artifact.
- Participant B will prepare a follow-up checklist.
- The team will compare the result with the stated goal.
- Timing is summarized without a source-message locator.
- Ownership is summarized without a source-message locator.

## Risks

- A missing dependency could delay the next step.
- A stale artifact could create contradictory evidence.
- A summary could flatten disagreement into consensus.
- A passive sentence could erase the responsible actor.
- None of these bullets identifies a raw message record.

## Delivery notes

- The first deliverable should be independently checked.
- The second deliverable depends on the first result.
- The notes collapse several exchanges into one statement.
- They do not preserve edits or reply relationships.
- They do not expose provider message identifiers.

## Timeline

- The opening topic was discussed around 09:10.
- A decision was reportedly reached around 09:25.
- The next topic began around 09:40.
- These inline times are part of summary prose.
- They are not raw-message timestamps or permalinks.

## Open questions

- Which artifact is the canonical source?
- Which participant made the final recommendation?
- Was the decision explicit or inferred by the summarizer?
- Which exact message supports the attributed statement?
- The summary cannot answer those questions by itself.

## Recommendations

- Preserve the original source alongside derived notes.
- Resolve attribution against the source before citation.
- Keep summary language explicitly marked as derived.
- Require a location for every attribution-bearing claim.
- Refuse a primary-source label when raw evidence is absent.

## Supporting observations

- The document is intentionally polished and concise.
- Its confident register does not establish provenance.
- Its internal consistency does not establish source grade.
- A filename or heading cannot upgrade the evidence.
- The source boundary must be checked mechanically.

## Review synthesis

- Reviewers found the summary useful for navigation.
- They did not treat it as a word-for-word record.
- Several clauses would require direct source confirmation.
- A source locator was requested but is unavailable here.
- The classification therefore remains derived.

## Quotation candidates

- A concise phrase was reconstructed from the notes.
- Another phrase was converted into reported speech.
- Removing quotation marks reduced asserted precision.
- It did not create firsthand evidence.
- Neither phrase has a raw-message location in this file.

## Attribution candidates

- Participant A was described as approving the direction.
- Participant B was described as warning about timing.
- The summary does not show who used either formulation.
- It cannot establish approval, warning, or ownership.
- Attribution-bearing use must fail closed.

## Completeness bounds

- The summarizer selected what appeared important.
- Omitted exchanges cannot be inferred from this artifact.
- Reply context and message edits are not represented.
- Reactions and deletions are not represented.
- These bounds make the artifact useful but derivative.

## Source notes

- The named upstream source is intentionally unavailable.
- No provider export is embedded or linked here.
- No message identifier can be resolved from this file.
- No permalink density can establish raw-message structure.
- This final block completes the 128-line fixture shape.
<!-- End of synthetic structured-summary fixture. -->
````
