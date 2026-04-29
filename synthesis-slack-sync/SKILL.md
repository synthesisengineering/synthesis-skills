---
name: synthesis-slack-sync
description: "Slack channel sync protocol for AI-assisted workflows. Reads channels and threads via Slack MCP, saves to local transcript files in workspace-scoped repos, and updates person-scoped daily action plans. Handles mid-day re-syncs with thread staleness detection. Use when asked to: slack sync, sync from slack, check slack, read channels, sync messages, sync transcripts, what's new on slack."
license: "CC0-1.0"
metadata:
  depends_on: "synthesis-daily-rituals, synthesis-project-management"
  author: "Rajiv Pant"
  version: "3.2.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Slack Sync

A protocol for syncing Slack channels and threads to local transcript files using Slack MCP. Designed for AI-assisted workflows where an agent reads Slack on behalf of a user, saves transcripts locally, and updates a daily action plan.

This skill provides the **protocol** — the sync methodology, thread re-reading discipline, transcript format, and action plan update rules. A per-project **config file** provides the specifics: which channels, which paths, which DMs. Prefer `.agents/slack-sync.yaml`; existing `.claude/slack-sync.yaml` configs remain supported.

## v3.2.0 — Canonical Sent-State Marker Location

In v3.2.0 (2026-04-29), the prescribed format for marking a draft as SENT changes from H3-jammed metadata to a separate `**Sent:**` paragraph below the draft body.

The pre-v3.2.0 form jammed the entire SENT metadata into the H3 heading text:

```markdown
### ~~Draft N: title~~ ✅ SENT by Rajiv at Thu Apr 2 6:16 PM EDT in #channel-name
```

That format renders as four lines of giant strikethrough in synthesis-console (H3 typography is ~1.75rem; long heading text wraps painfully). It also breaks the cockpit's sent-state detection — synthesis-console's parser looks for `**Sent:**` paragraphs to recognize sent drafts and replace the action bar with a "Sent" badge + "Open in Slack" link. With SENT in the H3, the parser doesn't notice, and the user sees Copy/Edit/Send buttons on a draft that already shipped.

The v3.2.0 canonical form keeps the H3 short and puts the metadata in its own paragraph:

```markdown
### ~~Draft N: title~~

**Send to:** ...

` ` `
[Message text]
` ` `

**Sent:** Thu Apr 2 6:16 PM EDT — by Rajiv in #channel-name (TS=1775141956.643419) https://acme.slack.com/archives/C0XXXXXX/p1775141956643419

**Grounding:**
- ...
```

**Backward compatibility.** The skill's `thread_checker.py` and synthesis-console v0.8.6+'s parser both accept the legacy H3-jammed form as well as the new canonical form. Existing daily-plan files don't need to be rewritten retroactively — but new SENT markers should use the canonical form, and any time the agent rewrites a sent draft for any reason, it should bring it to the canonical form.

This release follows the same producer-consumer-contract pattern as recent updates to other skills: when the consumer is the synthesis-console cockpit and the producer is a generative agent, the format and the parser must change together. Cross-reference: synthesis-console's `docs/cockpit-design.md` "Drafts" section.

## v3.1.0 — Workspace Domain, Permalinks, and Provenance Discipline

In v3.1.0 (2026-04-29), the skill gains three changes that work together:

1. **A new optional `slack_workspace_domain` config field.** Each project's `slack-sync.yaml` declares the Slack workspace's URL host (e.g., `acme.slack.com`). The skill stays generic — workspace-specific values live in per-project config, never hardcoded.

2. **Clickable permalinks replace bare Unix timestamps in transcript and draft formats.** Previous format wrote `(TS: 1234567890.123456)` as visible text. The new format hides the TS inside a Slack permalink URL — the visible text is the human-readable date/time, the link target is `https://{slack_workspace_domain}/archives/{channel_id}/p{ts_no_dot}`. The TS is still machine-readable (extractable from the URL); it's just not cluttering the rendered view in synthesis-console or any other Markdown viewer. Both formats are accepted by `thread_checker.py` during the transition; new sync output should use the permalink form when `slack_workspace_domain` is configured.

3. **Provenance discipline becomes explicit.** Every `## ... sync (~HH:MM TZ)` section header added to a transcript file MUST be backed by a `slack_read_channel` or `slack_read_thread` call in the same turn. Section bodies may ONLY contain messages those MCP calls returned. If MCP returned no new messages, the section says "No new messages since last sync" and stops — no quotes, no TSes, no claims about specific people having sent specific things. See the dedicated "Provenance Discipline" section below for the full rule and the rationale (2026-04-29 fabrication incident).

### Why these three changes are coupled

Permalinks make TSes machine-traceable in the file (every linked time is a TS visible in the URL), which makes provenance violations grep-able. The Stop-hook backstop at `~/.claude/hooks/quote-provenance-checker.py` looks for TSes that appear in transcript writes but nowhere else in the session — and it parses TSes from BOTH the legacy `(TS: ...)` text and the new `/pNNNNNNNNNNNNNNNN` URL form. The format change and the discipline change reinforce each other.

## v3.0.0 — Per-Channel-Per-Day Layout

In v3.0.0 (2026-04-22 afternoon), the transcript layout changed again within the same day as v2.0.0 was released. The refinement:

**Transcripts now live one-file-per-channel-per-day** inside a dated directory:

```
{transcripts_repo}/{transcripts_path}/slack/
├── YYYY-MM-DD/
│   ├── <channel-name>.md       (one file per channel)
│   ├── _dms.md                  (all 1:1 DMs for the day, aggregated)
│   ├── _group-dms.md            (all group DMs for the day, aggregated)
│   └── _misc.md                 (cross-channel sync notes, if any)
└── _historical-pre-v3/          (legacy pre-v3 content if any)
```

### Why v3.0.0

v2.0.0 used one-file-per-day-per-type (`channels/YYYY-MM-DD.md`, `dms/YYYY-MM-DD.md`, `group-dms/YYYY-MM-DD.md`). That worked but had two weaknesses:

1. **Heavy days produced large channel files.** A busy day with 50+ active channels would pack everything into one file.
2. **Type-based directories made new primitives awkward.** Adding Slack huddles or canvases would mean new top-level folders.

Per-channel-per-day solves both: each file is scoped to one channel's activity on one day (naturally smaller), and new primitives within Slack are new file patterns within the same dated dir, not new folders.

### Aggregation conventions

- **Channels get one file each per day.** `mmc-product-growth-squad.md`, `tech-csa-pull-requests.md`, etc.
- **DMs are aggregated** into `_dms.md` per day. DMs are typically lower-volume; daily context across all people is more useful than per-person files.
- **Group DMs are aggregated** into `_group-dms.md` per day. Same rationale.
- **The `_`-prefix** on `_dms.md` and `_group-dms.md` sorts them to the top of the directory listing, visually signaling they are aggregators rather than channel files.

### `-private` Discovery Protocol (ADR-014)

Any repo matching `ai-knowledge-*-private` is filtered from auto-discovery by default. This skill writes to a `-private` repo intentionally — the config file points at it explicitly. Other tools (ragbot auto-discovery, etc.) must NOT include these repos in their discovery scans unless running in explicit owner context. A sentinel file `.ai-knowledge-private-owner` at the repo root confirms ownership.

## Configuration

Create `.agents/slack-sync.yaml` in each project that uses this skill. Existing `.claude/slack-sync.yaml` configs are valid compatibility fallbacks.

```yaml
# .agents/slack-sync.yaml — Slack sync configuration (v3.1.0 schema)
#
# workspace: (REQUIRED) Workspace identifier. Used in transcript headers; must match
#   the workspace-private repo name pattern ai-knowledge-<workspace>-<person>-private.
# slack_workspace_domain: (OPTIONAL but strongly recommended, v3.1.0+) The Slack
#   workspace's URL host, e.g. "acme.slack.com". Used to construct clickable
#   message permalinks in transcripts and draft messages. If absent, the skill
#   falls back to the legacy bare-TS format and warns once per session.
# transcripts_repo: Absolute path to the workspace-private repo (Type 3). Transcripts
#   are written at {transcripts_repo}/{transcripts_path}/{channels,dms,group-dms,meetings}/.
# transcripts_path: Relative subpath within transcripts_repo. Conventionally "transcripts".
# action_plan_repo: Absolute path to the person's personal ai-knowledge repo where daily
#   action plans live. Daily plans are person-scoped (one per day, shared across all
#   workspaces the person touches that day), so this does NOT point at the workspace-
#   private repo.
# action_plan_path: Relative subpath within action_plan_repo. Conventionally "daily-plans".
# channels / dm_channels / group_dm_channels: as before.

workspace: example-workspace
slack_workspace_domain: example-workspace.slack.com

transcripts_repo: ~/workspaces/example-workspace/ai-knowledge-example-workspace-<person>-private
transcripts_path: transcripts

action_plan_repo: ~/workspaces/<person>/ai-knowledge-<person>
action_plan_path: daily-plans

channels:
  - id: C0EXAMPLE01
    name: team-general
    type: public_channel
  - id: C0EXAMPLE02
    name: eng-pull-requests
    type: private_channel
  # Add more channels as needed

dm_channels: []
  # - id: U0EXAMPLE01
  #   name: Jane Doe
  #   dm_id: D0EXAMPLE01

group_dm_channels: []
  # - id: C0EXAMPLE03
  #   name: "Project Alpha team"
```

If the config file is missing, the skill should warn and ask the user to create one.

**Path resolution summary (v3.0.0):**
- Channel transcripts: `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel-name>.md`
- DM transcripts (aggregated per day): `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_dms.md`
- Group DM transcripts (aggregated per day): `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_group-dms.md`
- Cross-channel sync notes (if any): `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_misc.md`
- Meeting transcripts (written by synthesis-meeting-transcripts): `{transcripts_repo}/{transcripts_path}/meetings/YYYY-MM-DD-<slug>.mdYYYY-MM-DD-<slug>.md`
- Google Chat transcripts (if any): `{transcripts_repo}/{transcripts_path}/gchat/YYYY-MM-DD.md`
- Email threads (if any): `{transcripts_repo}/{transcripts_path}/email/<thread-id>.md`
- Attachments: `{transcripts_repo}/{transcripts_path}/attachments/`
- Daily action plan: `{action_plan_repo}/{action_plan_path}/YYYY-MM-DD.md`

The workspace identifier no longer appears in transcript paths — it's implicit in `transcripts_repo` (the workspace-private repo is named after its workspace). The `<channel-name>` in the per-channel filename is the Slack channel name WITHOUT the leading `#`.

---

## Prerequisites

- **Slack connector or MCP must be connected and authenticated.** If any Slack tool call fails with an auth error, stop and instruct the user to re-authenticate using the current tool's Slack auth flow (Claude Code example: `claude mcp auth slack`), then restart the IDE/CLI if required.
- **Local transcript files must exist or be created.** The skill creates today's per-channel files and the `_dms.md` / `_group-dms.md` aggregators under `slack/YYYY-MM-DD/` as needed.

---

## ⛔ NEVER Use Slack Search API for Lookups

**When verifying whether a message was sent, or looking up past conversations, ALWAYS read local transcript files first.** Use `Grep` on transcript files in the transcripts directory. NEVER call `slack_search_public`, `slack_search_public_and_private`, or `slack_read_channel` for historical lookups.

The Slack search API has indexing delays (recent messages don't appear), misses thread replies entirely, and is slower and more expensive than local file reads. On 2026-04-01, four Slack search API calls returned "no results" for messages that existed in threads — nearly causing duplicate messages to be sent.

**The only valid uses of the Slack MCP API are:**
1. Syncing NEW messages during this protocol (Steps 1-3)
2. Reading a specific thread by TS that was never synced locally

---

## Sync Protocol

Every sync — whether day-start, mid-day, or day-end — follows these steps. No shortcuts, no skipped steps.

### Step 0: Run the thread checker (MANDATORY)

Before doing anything else, run the thread checker script on each transcript file that exists for today:

```bash
python3 ~/.agents/skills/synthesis-slack-sync/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel>.md [action_plan_file]
python3 ~/.agents/skills/synthesis-slack-sync/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_dms.md [action_plan_file]
python3 ~/.agents/skills/synthesis-slack-sync/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_group-dms.md [action_plan_file]
```

Skip any file that does not yet exist (e.g., no DMs synced today). Combine the output from all runs into a single checklist. You MUST re-read every thread listed during Step 2. The script exists because manually deciding which threads to re-read has repeatedly failed — threads get skipped and messages get missed.

### Step 1: Read channels for new top-level messages

For each channel in the config:

```
slack_read_channel(channel_id, oldest=LAST_SYNC_TIMESTAMP, limit=30)
```

- On **first sync of the day** (no channels transcript file exists yet): omit `oldest` or use midnight timestamp.
- On **subsequent syncs**: use the timestamp of the last sync recorded in the channels transcript file.
- Note the **reply count** on every message that has threads. These will be re-read in Step 2.

### Step 2: Re-read ALL active threads — today AND recent days

**This is the most important step. It is the step that gets skipped and causes missed messages.**

Thread replies do NOT appear as channel-level messages. The only way to detect them — including the user's own replies — is to re-read threads. This step must cover three sources of active threads:

**Source A: Threads in today's transcripts.** For every message in today's channels, DMs, and group-DMs transcript files that shows a thread (reply count > 0), re-read the full thread.

**Source B: Threads from yesterday's transcripts that may have new replies.** Open yesterday's dated directory `slack/YESTERDAY-YYYY-MM-DD/` and read every per-channel file, the `_dms.md`, and the `_group-dms.md`. For every thread that was active (had replies), re-read it. This catches: overnight replies, the user's own replies to threads from yesterday, and continuing conversations that span days.

**Source C: Threads surfaced by Step 1.** Any message returned by Step 1 that shows "Thread: N replies" must be re-read, even if the parent message is from a previous day. Channel reads return messages in reverse chronological order — a thread from 3 days ago can appear in the channel read if it had recent activity.

```
slack_read_thread(channel_id, message_ts=PARENT_TS)
```

Rules:
- **Never use the `oldest` parameter on thread reads.** It causes missed replies. Read the full thread every time.
- **Compare the reply count and latest reply timestamp** against what's in the local transcript.
- **If new replies exist**, append them to the appropriate transcript file for today (channels, DMs, or group-DMs), even if the parent message is from a previous day.
- **If the user sent a message** in a thread, it does NOT appear as a new channel-level message. The only way to detect it is to re-read the thread. If this step is skipped, the action plan shows drafts as "unsent" when the user already sent them.

**Mechanical check:** Before reporting "no new messages" for any sync, verify that:
1. Every thread TS in today's transcripts was re-read and reply counts match.
2. Every active thread from yesterday's transcripts was re-read for new replies.
3. Every thread indicator from Step 1 channel reads was followed.

**Why Source B matters:** On 2026-03-31, the user replied to an engineer's thread from the previous night. The reply didn't appear as a channel-level message. Because the thread was from the previous day and not in today's transcript, the sync missed it entirely — the daily plan showed the draft as unsent when the user had already sent it.

### Step 3: Check DMs

For each DM channel in the config:

```
slack_read_channel(channel_id=DM_CHANNEL_ID, oldest=LAST_SYNC_TIMESTAMP, limit=20)
```

Only check DMs that have active conversations. Don't read every DM — the config file specifies which ones are active.

### Step 3b: Check Group DMs

For each group DM channel in the config:

```
slack_read_channel(channel_id=GROUP_DM_ID, oldest=LAST_SYNC_TIMESTAMP, limit=20)
```

Group DMs (multi-party IMs) are separate from 1:1 DMs. They use channel IDs, not user IDs. Only check group DMs listed in the config.

### Step 4: Save to local transcripts

**This step is not optional. Never skip it, even if "nothing changed."**

Write each message type to its own transcript file under the workspace directory:

- **Channels:** `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel>.md` — channel messages and thread replies from Steps 1-2.
- **DMs:** `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_dms.md` — 1:1 DM messages from Step 3.
- **Group DMs:** `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_group-dms.md` — group DM messages from Step 3b.

For each file:
- Record the sync time (e.g., `## Mid-day sync (~14:30 EDT)`).
- If the file doesn't exist, create it with the standard header and create directories as needed.
- If no messages of that type were found, skip that file (do not create empty files).

Meeting transcripts are NOT part of Slack sync — they are handled by the daily-rituals skill and placed in `{transcripts_repo}/{transcripts_path}/meetings/YYYY-MM-DD-<slug>.md`.

### Step 5: Update action plan

- **Mark sent messages as SENT** with timestamps. Cross-reference messages the user sent against draft messages in the action plan.
- **Update waiting-on-others** table with any new information from thread replies.
- **Note new action items** or signals worth responding to in the "Things to Know" section.
- **Draft replies with grounding research.** When a Slack message requires a response (technical question, status request, bug report), research the answer in primary sources (source code, config files, PRs, deploy scripts, running systems) BEFORE drafting. Never draft a reply based solely on transcripts or conversation memory. The user's credibility depends on accuracy.
- **Use the mandatory draft format below** for every draft message. No exceptions.
- **Do NOT remove content** from the action plan — it is append-only (mark done, don't delete).

#### Draft Message Format (MANDATORY)

Every draft must use this exact structure. The user's workflow is: glance at where to send, copy-paste the message, then verify grounding. Format accordingly.

```markdown
### Draft N: [short description]
**Send to:** #channel-name — reply to @Author Name's message at Wed Apr 2, 10:59 AM EDT (TS: 1775141956.643419)
— OR for new messages —
**Send to:** #channel-name — new message (not a thread reply)

` ` `
[Message text — ready to copy and paste exactly as-is]
` ` `

**Grounding:**
- [Verified fact 1 — what source confirmed it]
- [Verified fact 2 — what source confirmed it]
- [Any staleness risk — e.g., "No new replies in thread since 11:23 AM"]
```

**Field rules:**

1. **Send to** comes first. Must include:
   - Channel name (e.g., `#le-csa-feedback`)
   - Thread reply vs. new message
   - If thread reply: the **author's name** and **human-readable date+time** of the parent message (e.g., "Thu Apr 2, 10:59 AM EDT")
   - Unix TS in parentheses after the human time — the user doesn't need it but the agent uses it for re-reading threads

2. **Message text** comes second, in a fenced code block. This is what the user copies and pastes. Nothing else should be between "Send to" and the code block.

3. **Grounding** comes third. Bullet list of facts verified against primary sources (code, git, deploy logs, Slack threads). Must include:
   - What was verified and where (file path, commit hash, GH Actions run ID, thread TS)
   - Staleness check — whether anything has happened since the draft was written that could make it wrong
   - Any facts the agent could NOT verify (flag explicitly so the user knows)

**When marking drafts as SENT (canonical, v3.2.0+):**

Two changes to the draft section:

1. **Wrap the H3 title in `~~...~~`** so the title shows struck through. Keep the H3 short — title only. NEVER pack SENT metadata into the heading text.
2. **Append a `**Sent:**` paragraph** immediately after the draft body, BEFORE the `**Grounding:**` paragraph if present.

```markdown
### ~~Draft N: [description]~~

**Send to:** #channel-name — reply to @Author Name's message at Wed Apr 2, 10:59 AM EDT (TS: 1775141956.643419)

` ` `
[Message text]
` ` `

**Sent:** Thu Apr 2 6:16 PM EDT — by Rajiv in #channel-name (TS=1775141956.643419) https://acme.slack.com/archives/C0XXXXXX/p1775141956643419

**Grounding:**
- ...
```

**Sent paragraph fields:**
- Human-readable date+time first (the user reads this).
- "by [Name]" identifies who sent the message (useful in shared workspaces or when the sender is not the daily-plan owner).
- Channel or DM target.
- `TS=<unix-ts>` — agent uses this to re-read the message and any thread replies.
- Permalink (when `slack_workspace_domain` is configured) — synthesis-console renders this as the "Open in Slack" / "View in Slack" link in the sent badge.

**Backward compat:** the legacy H3-jammed form is still recognized by `thread_checker.py` and by synthesis-console v0.8.6+, so existing files continue to work. New SENT markers should use the canonical form above.

Cross-reference: synthesis-console's [docs/cockpit-design.md](https://github.com/synthesisengineering/synthesis-console/blob/main/docs/cockpit-design.md) "Drafts" section. The format and the cockpit's parser are the producer-consumer contract — they must change together.

---

## Transcript File Format

Each file under `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/` follows one of three shapes: per-channel, `_dms.md` aggregator, or `_group-dms.md` aggregator.

### Channel file (`slack/YYYY-MM-DD/<channel>.md`)

One file per channel per day. The filename is the channel name without the leading `#` (e.g., `mmc-product-growth-squad.md`).

```markdown
# Slack #[channel-name] — [Day], [Month] [Date], [Year]
# Workspace: [workspace]

Last synced: ~HH:MM TZ

---

### [Author Name] — [HH:MM TZ]({permalink})
[Message content]
**Thread ([N] replies):**
- [Reply Author] [HH:MM]({reply_permalink}): "[reply text]"
- [Reply Author] [HH:MM]({reply_permalink}): "[reply text]"
**Reactions:** [emoji_name] ([count])

---

## Mid-day sync (~HH:MM TZ)

### [Author Name] — [HH:MM TZ]({permalink})
[New message]

#### Thread update — [N] replies — [HH:MM]({thread_permalink})
- [New reply details]

---
```

Within a single channel file, the channel name appears in the `# Slack #<channel>` top-level header only; messages below don't need `## #channel` subheaders (the entire file is about that channel).

`{permalink}` is constructed per "Slack Permalink Construction" below: the visible text is the human-readable time, the link target carries the TS (`/pNNNNNNNNNNNNNNNN`). Files written before v3.1.0 may carry the legacy `(TS: 1234567890.123456)` format; both are accepted by `thread_checker.py` during the transition.

### DMs aggregator file (`slack/YYYY-MM-DD/_dms.md`)

```markdown
# Slack DMs — [Day], [Month] [Date], [Year]
# Workspace: [workspace]

Last synced: ~HH:MM TZ

---

## DM with [Person Name] (DM_CHANNEL_ID)

### [Author Name] — [HH:MM TZ]({permalink})
[Message content]

---
```

### Group DMs aggregator file (`slack/YYYY-MM-DD/_group-dms.md`)

```markdown
# Slack Group DMs — [Day], [Month] [Date], [Year]
# Workspace: [workspace]

Last synced: ~HH:MM TZ

---

## Group DM: [Group Name or Members] (GROUP_DM_ID)

### [Author Name] — [HH:MM TZ]({permalink})
[Message content]

---
```

Key rules:
- **Always record the TS** for every significant message. In v3.1.0+ the TS is embedded in the Slack permalink URL (`/pNNNNNNNNNNNNNNNN`); in pre-v3.1.0 files it appears as `(TS: 1234567890.123456)` text. Both forms are valid; `thread_checker.py` accepts both.
- **Note reply counts** so the next sync can detect new replies.
- **Separate sync sessions** with a horizontal rule and a timestamp header.
- **Each file is scoped to its subject.** A per-channel file contains only that channel's messages. `_dms.md` contains only 1:1 DMs. `_group-dms.md` contains only group DMs. Mid-day syncs append to the same file; they don't fan out to new files.
- **Directory listing tells the story.** `ls slack/YYYY-MM-DD/` shows which channels were active that day. File sizes show where activity concentrated.

---

## Slack Permalink Construction

Every Slack message recorded in a transcript or quoted in a draft message MUST be presented as a clickable permalink (when `slack_workspace_domain` is configured). The permalink format:

```
https://{slack_workspace_domain}/archives/{channel_id}/p{ts_no_dot}
```

Where:
- `{slack_workspace_domain}` is read from `.agents/slack-sync.yaml` (e.g., `acme.slack.com`).
- `{channel_id}` is the channel ID (e.g., `C0EXAMPLE01`) — comes from the same config or from the MCP read result.
- `{ts_no_dot}` is the message TS with the `.` removed. Example: TS `1234567890.123456` becomes `1234567890123456`.

For thread replies, the same simple form navigates to the reply within its thread — Slack's permalink resolver handles thread context automatically. (Slack's "Copy link to message" UI emits a richer form with `?thread_ts=...&cid=...` query parameters; the simple `/pNNNNNNNNNNNNNNNN` form is sufficient for navigation and is what we generate.)

### Visible text is human-readable; TS hides in the URL

Instead of:

```markdown
### Author Name — HH:MM TZ (TS: 1234567890.123456)
```

Use:

```markdown
### Author Name — [HH:MM TZ](https://acme.slack.com/archives/C0XXXX/p1234567890123456)
```

The link target carries the TS for machine extraction (regex: `/p(\d{10})(\d{6})\b`). The visible time renders as a clickable link in synthesis-console, GitHub, VSCode preview, and any other Markdown viewer. No `(TS: ...)` clutter in the rendered view.

### Draft message "Send to:" line

Replies:

```markdown
**Send to:** #channel-name — reply to **Author's** message at [Wed, Apr 29, 4:09 PM EDT](https://acme.slack.com/archives/C0XXXX/p1777493393596089)
```

New top-level messages don't need a permalink — there's no parent to link to.

### Fallback when `slack_workspace_domain` is absent

If the per-project config does not set `slack_workspace_domain`, the skill MUST emit a one-time warning ("permalinks disabled — set `slack_workspace_domain` to enable clickable links in transcripts and drafts") and fall back to the legacy `(TS: 1234567890.123456)` text format. The skill does not invent a domain.

### Retrofitting older daily plans

`retrofit_permalinks.py` (shipped alongside `thread_checker.py` in this skill directory) converts a legacy daily plan or transcript file from the bare-TS format to the clickable-permalink format in one pass. It reads the workspace domain and channel-name → channel-ID map from a `slack-sync.yaml` config — generic-skill, no hardcoded workspace.

```bash
python3 retrofit_permalinks.py <plan.md> --config <slack-sync.yaml>
python3 retrofit_permalinks.py <plan.md> --config <slack-sync.yaml> --dry-run
```

Skip rules: lines containing only "parent thread TS" references are left as-is (the visible time on those lines refers to the reply, not the parent — linking it to the parent's TS would be wrong); lines with no resolvable channel hint are left unchanged (the script needs at least one `#channel-name` or `D0…`/`C0…` ID inline to construct a permalink). The script is idempotent — running it on an already-retrofitted file is a no-op.

For multi-workspace daily plans (a single plan referencing messages from more than one Slack workspace), run the script once per workspace's `slack-sync.yaml`. Each pass linkifies only the TSes whose channel resolves via the config it was given; other lines fall through to the next pass.

---

## Provenance Discipline

The 2026-04-29 fabrication incident — an agent invented a Slack message attributed to a teammate, complete with a plausibly-tweaked TS, then drafted a reply to the imaginary message — motivated this section. The format-level fixes above (permalinks, embedded TSes) make provenance violations grep-able; the rules below define what's actually a violation.

### MCP-read requirement for sync sections

Every `## ... sync (~HH:MM TZ)` section header added to a transcript file (`transcripts/slack/YYYY-MM-DD/*.md`) MUST be backed by a `slack_read_channel` or `slack_read_thread` MCP call IN THE SAME TURN.

- The body of that section may ONLY contain messages those MCP calls returned. Verbatim quotes, TS values, reactions, thread reply counts — all must come from the MCP output, not from the agent's expectations.
- If the MCP call returned no new messages: the section says "No new messages since last sync" and stops. **It MUST NOT contain message quotes, TS values, or claims about specific people having sent specific things.**
- Commentary about previously-synced messages (e.g., "this thread is now in good shape") is allowed, but must reference messages that ARE in the file from a prior sync — not introduce new ones.

### Quote-attribution requirement everywhere

Anywhere a quote is attributed to another person — transcripts, daily plans, project CONTEXT.md, session logs, draft "Send to" thread descriptors, anywhere — the agent must be able to cite the specific tool_use call in the current session that surfaced the quote. There is no "I remember it from earlier in the conversation." There is no "this is what they would say." Either there's a tool call to cite, or there's no quote.

### Cross-file propagation rule

When CONTEXT.md / daily plan / sessions logs cite a Slack message ("X said Y at HH:MM EDT"), the citation chain must trace `MCP call → transcript file → derivative file`. If a derivative file makes a claim that the transcript file doesn't support, the derivative is wrong. Re-verify against the actual Slack thread (or its synced transcript) before propagating.

### Automated backstop

A Stop hook at `~/.claude/hooks/quote-provenance-checker.py` (installed alongside `~/.claude/hooks/lazy-shortcut-detector.py` for the parallel discipline) scans the conversation transcript for Slack-TS-shaped values written into transcript / daily-plan / context files that did NOT appear elsewhere in the session — no MCP read, no Read tool result, no user message containing them, no other tool input. Candidates are logged to `~/.claude/quote-provenance-log.jsonl` with the file path, the fabricated TS values, and a stderr warning. The hook does NOT block writes; it makes violations visible after the fact for the user to review.

### What this rule is NOT

- It is not a rule against describing what's happening in a thread you've actually read. Summaries grounded in real synced content are fine.
- It is not a rule against drafting messages. Draft message bodies are agent-authored prose; only their attribution metadata (TS, parent author quote, channel, thread context) needs provenance.
- It is not a rule against speculating in your own analysis text ("Stephen will probably ask about X next"). Speculation is fine; recording the speculation as if it were a real message is not.

---

## Date Verification

Before writing or naming any dated file, cross-check the date against at least two independent signals:

1. Slack Unix timestamps (convert with `date -r TS`)
2. Day-of-week clues in message content
3. User statements about the current day

The `currentDate` system value is a snapshot from session start. If a session crosses midnight, all subsequent dates will be wrong.

---

## Following Continuing Conversations

When a channel message references or continues an earlier discussion (broadcast replies, "also sent to channel," or topic continuations):

1. Grep local transcripts for the topic/keywords to find the parent message and its TS.
2. Read the parent thread via MCP using that TS — this surfaces all new replies.
3. Update the local transcript with any new thread replies.

**Do NOT search Slack MCP repeatedly.** Local transcripts are the source of truth for historical context. The point of syncing is to avoid depending on the MCP API for lookups.

---

## Error Handling

- **Slack connector auth failure:** Stop immediately. Instruct the user to re-authenticate using the current tool's Slack auth flow, then restart the IDE/CLI if required.
- **Channel not found:** The channel ID may have changed or the bot may have been removed. Warn and skip.
- **Rate limiting:** If Slack returns rate limit errors, wait and retry. Do not skip channels.
- **Empty channel:** Record "No new messages" in the transcript. Do not silently skip.

---

## When This Skill Runs

This skill is invoked:
- **By the user** typing `/synthesis-slack-sync` or "sync from Slack" or similar
- **By `synthesis-daily-rituals`** during Day-Start (Step 2: Sync), Mid-Day Sync, and Day-End (Step 1: Transcript Sync)
- **Before drafting any Slack reply** — the daily-rituals skill requires re-reading the actual thread before drafting, to avoid stale-information replies

---

## Why Each Step Matters

These steps were developed through real incidents, not theory:

- **Step 2 (thread re-reading):** On 2026-03-24, a mid-day sync skipped thread re-reads. The action plan showed a draft as "unsent" when the user had already sent it hours earlier. The agent proposed sending it again, which would have been a duplicate message.
- **Step 4 (save to local):** Transcripts are the persistence layer. Without them, every sync starts from scratch, re-reading entire channels. With them, syncs are incremental and fast.
- **Step 5 (action plan update):** The action plan is the user's dashboard. If it shows stale information (unsent drafts that were sent, unresolved items that were resolved), the user makes wrong decisions.
