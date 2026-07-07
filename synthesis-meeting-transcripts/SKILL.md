---
name: synthesis-meeting-transcripts
description: "Fetch AI-generated meeting notes and full transcripts (e.g., Google Meet + Gemini) from the user's Gmail/Drive into local markdown files. Tool-agnostic: works with any Gmail + Drive MCP (Anthropic hosted connectors, self-hosted workspace-mcp, or others). Replaces the manual email → Google Doc → export-markdown → Downloads → move workflow. Use when asked to: fetch meeting transcript, pull standup, grab meeting notes, sync meetings, download transcript, get Gemini notes, import meeting."
license: "Apache-2.0"
metadata:
  depends_on: "synthesis-daily-rituals (optional integration)"
  author: "Rajiv Pant"
  version: "0.4.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

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
python3 ~/.claude/skills/synthesis-meeting-transcripts/verify_transcripts.py \
    {transcripts_repo}/{transcripts_path}/meetings/ \
    --only-incomplete
```

The script counts timestamp markers (`00:01:31`-style) in each meeting file. A real Gemini transcript has ~5–50 timestamps; a summary-only save has 0–2. If the just-saved file shows `INCOMPLETE`, re-fetch the Drive doc and re-save — your earlier extraction missed the Transcript tab.

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
