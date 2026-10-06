---
name: synthesis-slack-sync
description: "Sync Slack channels, DMs and threads to local transcripts via Slack MCP and update the daily action plan, with full thread re-reads and watermarked windows. Use when asked to: slack sync, sync from slack, check slack, read channels, sync messages, sync transcripts, what's new on slack."
license: "CC0-1.0"
depends_on: ["synthesis-project-management"]
metadata:
  author: "Rajiv Pant"
  version: "4.0.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
  format: v5
---

# Synthesis Slack Sync

A protocol for syncing Slack channels and threads to local transcript files using Slack MCP. Designed for AI-assisted workflows where an agent reads Slack on behalf of a user, saves transcripts locally, and updates a daily action plan.

## Binding rules

1. **Transcripts first.** Lookups and verification ("did X get sent?", "did anyone reply?") `Grep` local transcripts, never the Slack search API; the question shape is the trigger.
2. **A zero-result search is NEVER evidence of absence.** Prove absence with a bounded direct read and state its bounds; re-run a modifier query without the modifier before trusting a zero.
3. **Preflight decides the targets.** Steps 1, 3 and 3b read only its resolved-target list; taking an id such as `dm_id` from the config mid-sweep is banned.
4. **Windows are printed, never typed:** `WINDOW_OLDEST` comes from `sync_watermark.py window`. Every declared target is read every sync.
5. **Re-read every active thread** (today, yesterday, Step 1 indicators) in full; replies, the user's own included, never appear at channel level.
6. **Save, then advance.** A watermark advances only after the write, with an acquisition-evidence receipt.
7. **The user's own outbound discharges owed items.** An "unanswered" claim cites a read from this run (`status --since run` green).
8. **Every synced section is backed by a read in the same turn;** no quote without a tool call this session that surfaced it.
9. **Always record the TS** as a permalink; without `slack_workspace_domain`, warn once and use the bare-TS form, but never invent a domain.
10. **Drafts use the mandatory format** and are researched in primary sources; the action plan is append-only.
11. **Backfills are history.** Reconcile against newer local material before calling anything open.
12. **Check the date** against two independent signals before naming a dated file.

## Contents

- [references/sync-protocol.md](references/sync-protocol.md): Steps 0 to 5 in full, draft rules, transcript and permalink rules. Read it at the start of every sync.
- [references/lookups-and-absence.md](references/lookups-and-absence.md): the search-API rule, zero-result protocols, backfills, continuing conversations. Read it before any lookup, verification or backfill.
- [references/provenance-and-errors.md](references/provenance-and-errors.md): provenance in full, dates, errors. Read it before writing a sync section or quoting anyone, or when a call fails.
- [references/configuration.md](references/configuration.md): the config, multi-workspace registry, paths, prerequisites. Read it when setting up.
- [references/transcript-formats.md](references/transcript-formats.md): file shapes, permalinks, retrofit. Read it when creating a transcript file.
- [references/version-history.md](references/version-history.md): each release and its incident. Read it when a rule's reason matters.
- [references/cross-workspace-visibility.md](references/cross-workspace-visibility.md), [references/slack-token-guide.md](references/slack-token-guide.md): visibility modes; minting tokens. Read them when `slack_workspaces.py doctor` fails.
- [templates/draft-block.md](templates/draft-block.md), [templates/sent-marker.md](templates/sent-marker.md): the literal draft and SENT forms. Read them before writing or marking a draft.
- [references/coverage-map.md](references/coverage-map.md): where the 3.14.0 text lives.
- The search-API rule, the step outline with every command, Provenance Discipline, When This Skill Runs: below.

## ⛔ NEVER Use Slack Search API for Lookups

**When verifying whether a message was sent, or looking up past conversations, ALWAYS read local transcript files first.** Use `Grep` on transcript files in the transcripts directory. NEVER call `slack_search_public`, `slack_search_public_and_private`, or `slack_read_channel` for historical lookups.

**The only valid uses of the Slack MCP API are:**
1. Syncing NEW messages during this protocol (Steps 1-3)
2. Reading a specific thread by TS that was never synced locally

## Sync Protocol

Every sync — whether day-start, mid-day, or day-end — follows these steps. No shortcuts, no skipped steps.

Each step below is its command; the full step is in references/sync-protocol.md. Before any sync, `scripts/slack_workspaces.py doctor` names the readable workspaces (exit 1: a token is missing).

### Step 0: Run the thread checker (MANDATORY)

`python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel>.md [action_plan_file]`, also for `_dms.md` and `_group-dms.md`; every thread it lists is re-read in Step 2.

### Step 0: Preflight — resolve every read target (v3.7.0, REQUIRED)

`python3 <synthesis-slack-sync-root>/scripts/preflight.py --config .agents/slack-sync.yaml` prints the resolved-target table and a **census** line (`census: 9 C / 4 D / 0 unresolved`); `--json --out <declared.json>` writes the declared set. Exit 1: a target is unresolved; exit 2: empty set or bad config.

### Step 1: Read channels for new top-level messages

`slack_read_channel(resolved_channel_id, oldest=WINDOW_OLDEST, limit=30, detail="detailed")`, with `WINDOW_OLDEST` printed by `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py window --workspace <W> --surface slack --target <resolved id>`. Acquire through `synthesis exec-public synthesis-slack-sync/scripts/acquire.py` with the declared Web API adapter.

### Step 2: Re-read ALL active threads — today AND recent days

`slack_read_thread(channel_id, message_ts=PARENT_TS)`, never with `oldest`.

### Step 3: Check DMs

`slack_read_channel(channel_id=RESOLVED_CONVERSATION_ID, oldest=WINDOW_OLDEST, limit=20, detail="detailed")`.

### Step 3b: Check Group DMs

The same read with `channel_id=RESOLVED_GROUP_DM_ID`.

### Step 4: Save to local transcripts

Write, then `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <the window's latest> --acquisition-evidence <receipt.json>`. Gate: `sync_watermark.py status --workspace <W> --surface slack --since run --targets-from <declared.json>`.

### Step 5: Update action plan

Mark SENT; match the user's own outbound against every owed item.

#### Draft Message Format (MANDATORY)

Use templates/draft-block.md; mark sent per templates/sent-marker.md.

## Provenance Discipline

Every `## ... sync (~HH:MM TZ)` section is backed by a `slack_read_channel` or `slack_read_thread` call in the same turn and holds only what those calls returned. Full rules: references/provenance-and-errors.md.

## When This Skill Runs

This skill is invoked:
- **By the user** typing `/synthesis-slack-sync` or "sync from Slack" or similar
- **By `synthesis-daily-rituals`** during Day-Start (Step 3: Sync), Mid-Day Sync, and Day-End (Step 1: Transcript Sync)
- **Before drafting any Slack reply** — the daily-rituals skill requires re-reading the actual thread before drafting, to avoid stale-information replies
