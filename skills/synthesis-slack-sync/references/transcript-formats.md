# Transcript files and permalinks — formats

Contents:
- Transcript File Format: channel file, DMs aggregator file, group DMs aggregator file
- Slack Permalink Construction: visible text, the draft "Send to:" line, fallback without `slack_workspace_domain`, older daily plans

The file shapes every sync writes and the permalink form every recorded
message takes. The binding rules are summarized in [sync-protocol.md](sync-protocol.md)
("Transcript Files and Permalinks") and SKILL.md binding rule 9; this file is the literal format.

## Transcript File Format

Each file under `{transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/` follows one of three shapes: per-channel, `_dms.md` aggregator, or `_group-dms.md` aggregator.

### Channel file (`slack/YYYY-MM-DD/<channel>.md`)

One file per channel per day. The filename is the channel name without the leading `#` (e.g., `team-general.md`).

```markdown
# Slack #[channel-name] — [Day], [Month] [Date], [Year]
# Workspace: [workspace]

Last synced: ~HH:MM TZ

---

### [Author Name] — [HH:MM TZ]({permalink})
**Message ID:** [CONVERSATION_ID]:[MESSAGE_TS]
[Message content]
**Thread ([N] replies):**
- [Reply Author] [HH:MM]({reply_permalink}): "[reply text]"
  **Message ID:** [CONVERSATION_ID]:[REPLY_TS]
- [Reply Author] [HH:MM]({reply_permalink}): "[reply text]"
  **Message ID:** [CONVERSATION_ID]:[REPLY_TS]
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
**Message ID:** [CONVERSATION_ID]:[MESSAGE_TS]
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
**Message ID:** [CONVERSATION_ID]:[MESSAGE_TS]
[Message content]

---
```

Key rules:
- **Always record the TS** for every significant message. In v3.1.0+ the TS is embedded in the Slack permalink URL (`/pNNNNNNNNNNNNNNNN`); in pre-v3.1.0 files it appears as `(TS: 1234567890.123456)` text. Both forms are valid; `thread_checker.py` accepts both.
- **Note reply counts** so the next sync can detect new replies.
- **Separate sync sessions** with a horizontal rule and a timestamp header.
- **Each file is scoped to its subject.** A per-channel file contains only that channel's messages. `_dms.md` contains only 1:1 DMs. `_group-dms.md` contains only group DMs. Mid-day syncs append to the same file; they don't fan out to new files.
- **Directory listing tells the story.** `ls slack/YYYY-MM-DD/` shows which channels were active that day. File sizes show where activity concentrated.

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

### Older daily plans

Files written before v3.1.0 keep the bare `(TS: 1234567890.123456)` form. They stay as they are: `thread_checker.py` reads both forms. The one-time retrofit script that linkified them was retired in v4.0.0 once no current plan used the old form; its text is in [preserved.md](preserved.md).
