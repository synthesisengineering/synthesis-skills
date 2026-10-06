# Slack sync: the full sync protocol

Steps 0 to 5 in full, the draft message format, and the rules that bind every transcript write. SKILL.md carries the step outline with each command; read this at the start of every sync.

Contents:
- Step 0: Run the thread checker (MANDATORY)
- Step 0: Preflight — resolve every read target (v3.7.0, REQUIRED)
- Step 1: Read channels for new top-level messages (windows, acquisition entries, acquisition evidence)
- Step 2: Re-read ALL active threads — today AND recent days (sources A, B, C; mechanical check)
- Step 3: Check DMs; Step 3b: Check Group DMs
- Step 4: Save to local transcripts (watermark advance and the end-of-sync gate)
- Step 5: Update action plan; Draft Message Format (MANDATORY)
- Transcript Files and Permalinks

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
slack_read_channel(resolved_channel_id, oldest=WINDOW_OLDEST, limit=30, detail="detailed")
```

- **`WINDOW_OLDEST` is the `oldest=` epoch printed by** `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py window --workspace <W> --surface slack --target <resolved id>` — never hand-computed, never copied from a transcript header, never midnight. Quote the human-readable bounds the command prints in the sync report, so the window is checkable by eye (v3.8.0; a hand-typed `oldest` of 07:50 *today* once reported five channels empty that were not).
- A **bootstrap window** (no watermark yet for that target or surface) reads to the workspace's backfill bound and states that bound in the report.
- **Every declared target is read every sync**, including targets read earlier the same day — the window simply starts where the last read stopped.
- Note the **reply count** on every message that has threads. These will be re-read in Step 2.

Use `synthesis exec-public synthesis-slack-sync/scripts/acquire.py` with the explicitly declared structured Web API adapter, following [declared acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md). Recorded connector calls remain source custody, but their rendered message strings cannot prove author or message boundaries. Connector replay therefore reports a blocking problem and refuses attributable archives or watermark advancement; repeating those same reads cannot repair that limitation. The owner consumes preflight and the current registry and never discovers targets or falls back to direct credentials. Keep unsupported connector coverage UNKNOWN.

Before advancing a Slack watermark, read the mandatory [acquisition evidence contract](../../synthesis-daily-rituals/references/acquisition-evidence.md). Use detailed channel/DM reads with complete pagination, independently search within the declared window for replies (including old parents), and follow the union of local known threads, history indicators, and search parents. `thread_checker.acquire_channel` provides this bounded read-only adapter flow. Retain actual in-window positive controls and raw call references; historical controls or empty/concise reads cannot establish absence. Save exact message IDs and bytes, then pass the complete receipt to `sync_watermark.py advance --acquisition-evidence`. If a connector lacks required detail or pagination, report unknown coverage and keep the watermark.

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
slack_read_channel(channel_id=RESOLVED_CONVERSATION_ID, oldest=WINDOW_OLDEST, limit=20, detail="detailed")
```

The resolved conversation id comes from preflight (Step 0), never from a config field chosen mid-sweep. Only check DMs the config marks active — preflight carries that scoping — and report any DM preflight marked unresolved instead of silently skipping it.

### Step 3b: Check Group DMs

For each group DM in the preflight's resolved-target list:

```
slack_read_channel(channel_id=RESOLVED_GROUP_DM_ID, oldest=WINDOW_OLDEST, limit=20, detail="detailed")
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
- **Record the read once it is saved (v3.8.0):** for each target whose window was read and whose messages (or confirmed absence) are now on disk, run `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <the window's latest> --acquisition-evidence <receipt.json>`. The watermark advances only after the write, so a read that failed to save cannot claim coverage — and the gate at the end of the sync (`sync_watermark.py status --workspace <W> --surface slack --since run --targets-from <declared.json>`, the declared set written by `preflight.py --json --out` this run and never a stored copy) lists exactly the targets this sync did not re-read.

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

The canonical structural format for a draft block lives in [`templates/draft-block.md`](../templates/draft-block.md). Read it as the literal template; this section gives the protocol-level rules for when and how to apply it.

The shape (v3.3.0+) is two-tier:

1. **Glanceable summary** — brief H3 title (≤60 char target), compressed `**Send to:**` line, optional one-line framing context, the message body itself.
2. **Click-to-expand detail** — Grounding wrapped in `<details>/<summary>` so verification metadata is one click away rather than crowding the glance surface.

**Protocol rules** (full field-by-field detail in `templates/draft-block.md`):

- **H3 title** is a scannable label. ≤60 char target, ≤80 hard cap. Format: `Draft N: <action> <recipient/topic>`. NEVER include channel IDs, user IDs, thread timestamps, commit hashes, PR numbers, status markers, or compound clauses in the title.
- **Send to** uses `#channel · <thread or new>` shape. Compressed metadata strip, not a verbose paragraph. If thread reply, include author name + human-readable time + `(TS=...)` on the same line.
- **Optional context paragraph** — single plain paragraph between Send-to and the body, used only when helpful framing is needed. Skip if the body speaks for itself.
- **Message body** — fenced code block, ready to paste into Slack. If the body itself contains triple-backtick fences, use 4-backtick OUTER fence per CommonMark (per synthesis-console v0.8.5 structural-axis rule).
- **Grounding** — wrapped in `<details>/<summary>`. Bullets must include what was verified, where (file path / commit / GH Actions run / thread TS), and any staleness or unverified caveats.

**When marking drafts as SENT** — see [`templates/sent-marker.md`](../templates/sent-marker.md) for the canonical form. Summary: wrap the H3 title in `~~...~~`, and append a `**Sent:** <human-time> — by <Name> in <target> · (TS=...) <permalink>` paragraph between the body and the Grounding `<details>` block.

**Backward compat** — the cockpit's parser (synthesis-console v0.8.6+) and `thread_checker.py` accept both the v3.3.0 two-tier form AND legacy pre-v3.3.0 forms (inline Grounding, H3-jammed SENT, etc.). Existing daily-plan files don't need retroactive rewriting; new drafts and rewrites should use the v3.3.0 form.

**Cross-reference** — synthesis-console `docs/cockpit-design.md` "Drafts" section. The template files in this skill and the cockpit's parser are the producer-consumer contract; they must change together.

---

## Transcript Files and Permalinks

The per-channel, `_dms.md`, and `_group-dms.md` file shapes, the permalink construction rule, the `Send to:` line form, and the retrofit script are in [references/transcript-formats.md](transcript-formats.md). The rules that bind every write:

- **Always record the TS** for every significant message — embedded in a Slack permalink (`https://{slack_workspace_domain}/archives/{channel_id}/p{ts_no_dot}`) whose visible text is the human-readable time. When `slack_workspace_domain` is absent, warn once per session and fall back to the legacy `(TS: 1234567890.123456)` text; never invent a domain.
- **Note reply counts** so the next sync can detect new replies; **separate sync sessions** with a horizontal rule and a timestamped `## … sync (~HH:MM TZ)` header; **each file is scoped to its subject** — mid-day syncs append to the same file and never fan out to new ones.
- `retrofit_permalinks.py <plan.md> --config <slack-sync.yaml>` converts a legacy bare-TS file to permalinks in one idempotent pass (`--dry-run` to preview); for multi-workspace plans run it once per workspace config.
