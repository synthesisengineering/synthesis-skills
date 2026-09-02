---
name: synthesis-slack-sync
description: "Slack channel sync protocol for AI-assisted workflows. Reads channels and threads via Slack MCP, saves to local transcript files in workspace-scoped repos, and updates person-scoped daily action plans. Handles mid-day re-syncs with thread staleness detection. Use when asked to: slack sync, sync from slack, check slack, read channels, sync messages, sync transcripts, what's new on slack."
license: "CC0-1.0"
depends_on: ["synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "3.10.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Synthesis Slack Sync

A protocol for syncing Slack channels and threads to local transcript files using Slack MCP. Designed for AI-assisted workflows where an agent reads Slack on behalf of a user, saves transcripts locally, and updates a daily action plan.

This skill provides the **protocol** — the sync methodology, thread re-reading discipline, transcript format, and action plan update rules. A per-project **config file** provides the specifics: which channels, which paths, which DMs. Prefer `.agents/slack-sync.yaml`; existing `.claude/slack-sync.yaml` configs remain supported.

Version history and the incidents behind each rule: [references/version-history.md](references/version-history.md). Transcript and permalink formats: [references/transcript-formats.md](references/transcript-formats.md). Draft templates: [templates/draft-block.md](templates/draft-block.md) and [templates/sent-marker.md](templates/sent-marker.md).

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
- Meeting transcripts (written by synthesis-meeting-transcripts): `{transcripts_repo}/{transcripts_path}/meetings/YYYY-MM-DD-<slug>.md`
- Google Chat transcripts (if any): `{transcripts_repo}/{transcripts_path}/gchat/YYYY-MM-DD.md`
- Email threads (if any): `{transcripts_repo}/{transcripts_path}/email/<thread-id>.md`
- Attachments: `{transcripts_repo}/{transcripts_path}/attachments/`
- Daily action plan: `{action_plan_repo}/{action_plan_path}/YYYY-MM-DD.md`

The workspace identifier no longer appears in transcript paths — it's implicit in `transcripts_repo` (the workspace-private repo is named after its workspace). The `<channel-name>` in the per-channel filename is the Slack channel name WITHOUT the leading `#`.

Repos matching `ai-knowledge-*-private` are excluded from auto-discovery by default (ADR-014); this skill writes to one deliberately — the config names it — and a `.ai-knowledge-private-owner` sentinel at the repo root confirms ownership. Other tools must not include these repos in discovery scans unless running in explicit owner context.

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

### The question-shape trigger

**This rule covers VERIFICATION, not just "lookups."** "Did X get sent?", "did anyone reply?", "is this claim true?", "did that actually happen?" are all historical lookups wearing a different hat. The trigger is the QUESTION SHAPE — anything answered by finding-or-not-finding a past message — never whether the task felt like a lookup when it started.

The distinction was paid for: the rule once failed to fire precisely because the work was framed as "verifying a suspicious claim" rather than "looking something up." The agent ran four workspace searches, got four zeros, and reported two true events as fabricated. One of them sat in the exact channel it had searched for, posted shortly before the search — hidden behind a silently-failing query modifier and an oversized result file that was never opened before concluding. Transcripts-first would have found it in one `Grep`.

### A zero-result search is NEVER evidence of absence

Not weak evidence — none. The search index lags, misses thread replies, and fails silently on malformed modifiers: a `from:@Display Name` modifier with a space in it returns zero instead of erroring. Two protocols follow:

- **To establish that something did not happen,** use a bounded direct read: `slack_read_channel` with an explicit `oldest`/`latest` window on the specific channel, or `slack_read_thread` on the known parent. State the bounds in the finding — "not present in #channel between t1 and t2" — never the unbounded "didn't happen."
- **Before trusting any null result from a modifier-bearing query** (`from:`, `in:`, `to:`), re-run it without the modifier. If the unmodified query finds results the modified one missed, the modifier was broken, and every zero it produced is uninterpretable.

Absence claims are a grounding problem: a negative result is only evidence if the instrument could have produced a positive one. The general discipline — positive controls, scoped negative findings, truncated-output rules — lives in [synthesis-grounding-discipline](../synthesis-grounding-discipline/SKILL.md); this section is its Slack instance.

### Backfills and archive imports

A backfill — reading a conversation to its first message rather than to a window — is a different operation from a sync, and it fails differently.

**Retrieval.** Page until the source says there are no more messages; a page limit or a date bound is not the beginning. Report the **earliest message's actual date** per conversation, so the reader can tell you reached the start rather than that a cursor quit early. Expand every thread: replies do not appear in channel history, and skipping them is the standard way a backfill silently loses half a conversation. Preserve raw user IDs beside resolved names.

**Naming and framing.** A backfill file states the span it covers and the date it was captured. When a conversation is *partly* captured already, name the new file by its date range rather than "full history" — that name claims a completeness it does not have.

**The analysis rule, which matters more than the retrieval.** Everything in a backfill is history, and it all reads present-tense. **Do not report anything from it as currently open without reconciling against newer material already held locally.** A conversation that stops is not a question that stayed unanswered — the thread often continued somewhere else. Scope every finding to where you looked ("unanswered in this conversation through <date>"), and title the output by what it establishes: a list of where conversations stopped, not a list of open loops. The general discipline, with the incident that produced it, is entry 12 of [synthesis-grounding-discipline](../synthesis-grounding-discipline/SKILL.md).

Candidate open items surfaced this way are exactly what [synthesis-catchup-ledger](../synthesis-catchup-ledger/SKILL.md) exists to classify — route them through its still-relevant / obsolete / ambiguous triage rather than reporting them raw.

---

## Sync Protocol

Every sync — whether day-start, mid-day, or day-end — follows these steps. No shortcuts, no skipped steps.

### Step 0: Run the thread checker (MANDATORY)

Before doing anything else, run the thread checker script on each transcript file that exists for today:

```bash
python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel>.md [action_plan_file]
python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_dms.md [action_plan_file]
python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_group-dms.md [action_plan_file]
```

Skip any file that does not yet exist (e.g., no DMs synced today). Combine the output from all runs into a single checklist. You MUST re-read every thread listed during Step 2. The script exists because manually deciding which threads to re-read has repeatedly failed — threads get skipped and messages get missed.

### Step 0: Preflight — resolve every read target (v3.7.0, REQUIRED)

Before any read, build the resolved-target list for this sweep. For every surface the config declares — channels, 1:1 DMs, group DMs — record the one id a conversation-read call accepts: the channel id for channels and group DMs, the **conversation id (`D…`), never the user id (`U…`)**, for DMs. A surface whose read id cannot be established is recorded as **unresolved** and reported that way — never as unreadable, never as a config defect, because the sweep has evidence for neither. An empty resolved-target list refuses the sweep rather than reporting a quiet day.

Run `python3 <synthesis-slack-sync-root>/scripts/preflight.py --config .agents/slack-sync.yaml` (v3.10.0): it prints the resolved-target table for the sync report and a prefix **census** line (for example `census: 9 C / 4 D / 0 unresolved`), and `--json --out <declared.json>` writes the declared set the watermark gate consumes — derived from the config this run, never a stored copy. It validates the id prefix per class (`C`/`G` for channels and group DMs, `D` for DMs; a `U`-prefixed id is never a read target), exits 1 when any declared target is unresolved so the report must name it, and exits 2 on an empty resolved set or a malformed config. Steps 1, 3, and 3b iterate ONLY its resolved-target list. Reaching back into the config for an id mid-sweep is the banned move from v3.6.0: where an entry carries two id-like fields, the wrong one usually resolves, so the bug hides until the person behind it leaves — and on 2026-09-01 a careful reader with the config open, warned minutes earlier, still derived every DM target as a user id; the census makes that a visibly wrong shape instead of quiet empties.

### Step 1: Read channels for new top-level messages

For each channel in the preflight's resolved-target list:

```
slack_read_channel(resolved_channel_id, oldest=WINDOW_OLDEST, limit=30)
```

- **`WINDOW_OLDEST` is the `oldest=` epoch printed by** `python3 <synthesis-daily-rituals-root>/scripts/sync_watermark.py window --workspace <W> --surface slack --target <resolved id>` — never hand-computed, never copied from a transcript header, never midnight. Quote the human-readable bounds the command prints in the sync report, so the window is checkable by eye (v3.8.0; a hand-typed `oldest` of 07:50 *today* once reported five channels empty that were not).
- A **bootstrap window** (no watermark yet for that target or surface) reads to the workspace's backfill bound and states that bound in the report.
- **Every declared target is read every sync**, including targets read earlier the same day — the window simply starts where the last read stopped.
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

For each 1:1 DM in the preflight's resolved-target list:

```
slack_read_channel(channel_id=RESOLVED_CONVERSATION_ID, oldest=WINDOW_OLDEST, limit=20)
```

The resolved conversation id comes from preflight (Step 0), never from a config field chosen mid-sweep. Only check DMs the config marks active — preflight carries that scoping — and report any DM preflight marked unresolved instead of silently skipping it.

### Step 3b: Check Group DMs

For each group DM in the preflight's resolved-target list:

```
slack_read_channel(channel_id=RESOLVED_GROUP_DM_ID, oldest=WINDOW_OLDEST, limit=20)
```

Group DMs (multi-party IMs) are separate from 1:1 DMs. They use channel IDs, not user IDs. Only check group DMs the preflight resolved from the config's declared list.

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
- **Record the read once it is saved (v3.8.0):** for each target whose window was read and whose messages (or confirmed absence) are now on disk, run `python3 <synthesis-daily-rituals-root>/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <the window's latest>`. The watermark advances only after the write, so a read that failed to save cannot claim coverage — and the gate at the end of the sync (`sync_watermark.py status --workspace <W> --surface slack --since run --targets-from <declared.json>`, the declared set written by `preflight.py --json --out` this run and never a stored copy) lists exactly the targets this sync did not re-read.

Meeting transcripts are NOT part of Slack sync — they are handled by the daily-rituals skill and placed in `{transcripts_repo}/{transcripts_path}/meetings/YYYY-MM-DD-<slug>.md`.

### Step 5: Update action plan

- **Mark sent messages as SENT** with timestamps. Cross-reference messages the user sent against draft messages in the action plan.
- **The user's own outbound is first-class sweep state (v3.8.0).** Every message the user sent that Steps 1-3b returned — in channels, threads, DMs, group DMs — is cross-referenced against every owed item, draft, and waiting-on entry, and each item it discharged is marked with the message time. A claim that something is unanswered or unsent must cite the read that established it, and that read must belong to this run: `status --since run` green for that target, or the claim is not made. Origin (2026-09-01): a question answered by the user at 09:27 was reported unanswered at 17:51, citing a 09:15 read.
- **Update waiting-on-others** table with any new information from thread replies.
- **Note new action items** or signals worth responding to in the "Things to Know" section.
- **Draft replies with grounding research.** When a Slack message requires a response (technical question, status request, bug report), research the answer in primary sources (source code, config files, PRs, deploy scripts, running systems) BEFORE drafting. Never draft a reply based solely on transcripts or conversation memory. The user's credibility depends on accuracy.
- **Use the mandatory draft format below** for every draft message. No exceptions.
- **Do NOT remove content** from the action plan — it is append-only (mark done, don't delete).

#### Draft Message Format (MANDATORY)

The canonical structural format for a draft block lives in [`templates/draft-block.md`](templates/draft-block.md). Read it as the literal template; this section gives the protocol-level rules for when and how to apply it.

The shape (v3.3.0+) is two-tier:

1. **Glanceable summary** — brief H3 title (≤60 char target), compressed `**Send to:**` line, optional one-line framing context, the message body itself.
2. **Click-to-expand detail** — Grounding wrapped in `<details>/<summary>` so verification metadata is one click away rather than crowding the glance surface.

**Protocol rules** (full field-by-field detail in `templates/draft-block.md`):

- **H3 title** is a scannable label. ≤60 char target, ≤80 hard cap. Format: `Draft N: <action> <recipient/topic>`. NEVER include channel IDs, user IDs, thread timestamps, commit hashes, PR numbers, status markers, or compound clauses in the title.
- **Send to** uses `#channel · <thread or new>` shape. Compressed metadata strip, not a verbose paragraph. If thread reply, include author name + human-readable time + `(TS=...)` on the same line.
- **Optional context paragraph** — single plain paragraph between Send-to and the body, used only when helpful framing is needed. Skip if the body speaks for itself.
- **Message body** — fenced code block, ready to paste into Slack. If the body itself contains triple-backtick fences, use 4-backtick OUTER fence per CommonMark (per synthesis-console v0.8.5 structural-axis rule).
- **Grounding** — wrapped in `<details>/<summary>`. Bullets must include what was verified, where (file path / commit / GH Actions run / thread TS), and any staleness or unverified caveats.

**When marking drafts as SENT** — see [`templates/sent-marker.md`](templates/sent-marker.md) for the canonical form. Summary: wrap the H3 title in `~~...~~`, and append a `**Sent:** <human-time> — by <Name> in <target> · (TS=...) <permalink>` paragraph between the body and the Grounding `<details>` block.

**Backward compat** — the cockpit's parser (synthesis-console v0.8.6+) and `thread_checker.py` accept both the v3.3.0 two-tier form AND legacy pre-v3.3.0 forms (inline Grounding, H3-jammed SENT, etc.). Existing daily-plan files don't need retroactive rewriting; new drafts and rewrites should use the v3.3.0 form.

**Cross-reference** — synthesis-console `docs/cockpit-design.md` "Drafts" section. The template files in this skill and the cockpit's parser are the producer-consumer contract; they must change together.

---

## Transcript Files and Permalinks

The per-channel, `_dms.md`, and `_group-dms.md` file shapes, the permalink construction rule, the `Send to:` line form, and the retrofit script are in [references/transcript-formats.md](references/transcript-formats.md). The rules that bind every write:

- **Always record the TS** for every significant message — embedded in a Slack permalink (`https://{slack_workspace_domain}/archives/{channel_id}/p{ts_no_dot}`) whose visible text is the human-readable time. When `slack_workspace_domain` is absent, warn once per session and fall back to the legacy `(TS: 1234567890.123456)` text; never invent a domain.
- **Note reply counts** so the next sync can detect new replies; **separate sync sessions** with a horizontal rule and a timestamped `## … sync (~HH:MM TZ)` header; **each file is scoped to its subject** — mid-day syncs append to the same file and never fan out to new ones.
- `retrofit_permalinks.py <plan.md> --config <slack-sync.yaml>` converts a legacy bare-TS file to permalinks in one idempotent pass (`--dry-run` to preview); for multi-workspace plans run it once per workspace config.

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
- **By `synthesis-daily-rituals`** during Day-Start (Step 3: Sync), Mid-Day Sync, and Day-End (Step 1: Transcript Sync)
- **Before drafting any Slack reply** — the daily-rituals skill requires re-reading the actual thread before drafting, to avoid stale-information replies
