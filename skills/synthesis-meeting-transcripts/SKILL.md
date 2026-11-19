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

Keeps meeting records usable as evidence. It fetches a meeting's AI notes and its verbatim transcript (Google Meet with Gemini notes in Google Docs, through whatever Gmail and Drive tools the session has, or another recorder's export) into the project's transcripts repository, verifies each saved file, takes who said, decided or owns what from the transcript's speaker lines, and puts the commitments its scanner flags before the principal.

## Binding rules

These rules keep the record honest, so they hold when a request asks otherwise: say which rule applies and why, then do what it allows.

1. **Fetch every declared meeting in a ritual sync.** In a day-start, mid-day or day-end sync, run Step 0: fetch each member of the declared set, report each as fetched or as an open gap, and judge relevance only after fetching, from content, since a title is no evidence of what a meeting held. A meeting the user names is fetched alone (Steps 1 to 6).
2. **Report unknown coverage as an open gap.** When sign-in, the tab list or archive coverage is unknown, the meeting stays an open gap (never a no-source marker) and the meetings watermark stays before it. The watermark also stays before any unsaved doc and any meeting that may still be under way, so never later than two hours before the check.
3. **Leave the window open when a Drive listing is bounded.** A Drive search returns no completeness flag, so a full page, a next-page token, an `incompleteSearch` warning or a failed search means more docs may exist: read every page, and report the window as unproven until then.
4. **Save the verbatim transcript in full whenever the source has one.** It is the only primary source; its length is no reason to abridge it. Use the Gemini email only to find the doc, never as content: it is a summary of the summary.
5. **Select the transcript by the document's stable tab ID** from a complete tab list, and record that ID; position or a regular expression only guesses, so neither selects. A title selects only when exactly one tab in a complete list carries it. Only a complete tab list establishes `transcript-tab-absent`.
6. **Verify the exact saved file before calling a meeting fetched:** `verify_transcripts.py --file <saved file> --json` must show both halves landed. A directory scan reports on the corpus, not on this file.
7. **Add the `<!-- VERIFIER: no-source-transcript -->` marker only when the source has no transcript,** as a complete tab list or the doc itself shows, with a one-line reason beside it. A failed or partial fetch is an open gap (rule 2), not a missing transcript.
8. **Take who acted from the verbatim transcript.** Who decided, warned, approved, asked, promised or owns an action comes from the transcript's speaker lines, whether fetched or pasted by the user; when a line names the actor, attribute directly. A tool summary, decisions section or action-item list says what happened, never who did or owns it, because the summarizer drops the actor: if the transcript is silent, keep the passive form or say the actor is unknown.
9. **Confirm scanner candidates with the principal.** Lines the commitment scanner (`extract_commitments.py`) flags are candidates, since it matches phrasing, not obligations: show each (timestamp, speaker, quote) for the principal to confirm in the same turn, create nothing from scanner output alone, and stamp each confirmed one with exactly one owner. This rule covers scanner output only; a commitment read from transcript lines to say who owns what is attribution (rule 8) and needs no confirmation.
10. **Cross-check every date against at least two independent signals** before writing a dated file, such as the system `date`, the doc's `modifiedTime` (in UTC) and a date the user or the doc's name states; a session's cached date goes stale across midnight.
11. **Commit transcripts to `transcripts_repo`, never leave them in `~/Downloads/`;** its pre-commit gate refuses a summary saved as a transcript.

## Contents

- Which path: below. Read it first.
- [references/declared-window-sweep.md](references/declared-window-sweep.md): Step 0, the ritual sync: inventory the window (`fetch-meeting.py --window`), fetch and account for every declared member, advance the meetings watermark (`sync_watermark.py advance`). Read it at the start of every ritual sync.
- [references/protocol-steps.md](references/protocol-steps.md): Steps 1 to 6 for one meeting with every command (`verify_transcripts.py`, `extract_commitments.py`): find, fetch by tab ID, save, verify, attribute, commitments, commit; date checks; the daily-rituals hand-off. Read it before fetching or filing a meeting, and for each member of a sweep.
- [references/transcript-primary-and-commit-gate.md](references/transcript-primary-and-commit-gate.md): what counts as primary evidence, how summaries are kept, and the transcripts repository's pre-commit gate. Read it before citing a meeting record, and when setting up a transcripts repo.
- [references/setup.md](references/setup.md): the `.agents/meeting-transcripts.yaml` schema (required: `workspace`, `google_account`, `transcripts_repo`, `transcripts_path`), prerequisites, multi-account options and what `start.sh` sets for the server. Read it when a project has no config, a config is refused, or an account is unreachable.
- [references/release-notes.md](references/release-notes.md) and [references/earlier-version-history.md](references/earlier-version-history.md): release notes from v0.2.0 to 1.2.1. Read them when a result differs from what an earlier version did.
- [optional-workspace-mcp/README.md](optional-workspace-mcp/README.md): the optional self-hosted multi-account server: `fetch-meeting.py`, `mcp_client.py`, the service scripts and `doctor.sh`. Read it when the project uses that server.
- [references/coverage-map.md](references/coverage-map.md): where each rule of 1.2.1, and of 0.14.0, lives now. Read it to check a rewrite.
- [references/preserved.md](references/preserved.md): text retired in 1.3.0 and in M3, word for word, with reasons. Read it only to review a rewrite.

## Which path

- **The user names one meeting** ("pull today's design review"): Steps 1 to 6 in [references/protocol-steps.md](references/protocol-steps.md), for that meeting only.
- **A ritual sync** (day-start 3c, the mid-day sync, day-end step 1): Step 0 in [references/declared-window-sweep.md](references/declared-window-sweep.md), which runs Steps 2 to 5 for every declared member.
- **The user brings a record** (pasted lines, a saved file, a download): answer from it by rules 4 and 8; to file a download, save, verify and commit it by Steps 4 to 6.
- **No config, a refused config, an unreachable account:** [references/setup.md](references/setup.md).
