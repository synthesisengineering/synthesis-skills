# Preserved text: slack sync, retired in milestone M3

Read this only to review what was cut. The passages below are no longer
instructions; they are kept verbatim so the reasoning stays readable (ruling D8).
Each block names the file it came from and why it went.

Contents:
- Why the scripts were cut
- Replaced passages, file by file (verbatim)
- references/slack-token-guide.md at 4.0.0 (verbatim)

## Why the scripts were cut

Verdicts from the v5 code evaluation (tool scripts, slack sync):

- `scripts/acquire.py` (585 lines), `scripts/connector_replay.py` (698) and
  `thread_checker.acquire_channel` (about 250 lines): CUT. They existed so a
  Python reader could produce receipts the watermark would accept (the
  acquisition gate, 4.152.0, 2026-09-28). The gate harmed the work it was meant
  to protect: on 2026-10-01 it stopped Slack bookmarks for a workspace that
  reads through connectors although every sync ran in full (lesson
  2026-10-01, say it in plain English and escalate a degraded sync), and 4.154.0
  then added connector replay to parse transcripts so Python could accept what
  the agent had already read. The coverage rules the code encoded are kept as
  protocol text (sync-protocol.md, Step 1 read rules, Step 2 Source D, Step 4)
  and as scenarios E01 to E14.
- `scripts/slack_read.py` (280): CUT, never configured (every token in the
  registry was `PLACEHOLDER`); reads go through the Slack connector.
- `scripts/slack_workspaces.py` (427): SLIM to the workspace-to-domain map and
  the visibility rule, read from the synthesis config; the token machinery
  served `slack_read.py` only.
- `retrofit_permalinks.py` (294): CUT, job finished. None of the 22 September
  and October daily plans had a bare timestamp; the 8 April and May plans that
  do are history, and `thread_checker.py` still reads both forms.
- `thread_checker.py`: SLIM to its checklist half (the 2026-04-01 and
  2026-03-10 lessons), moved into `scripts/`.

## Replaced passages, file by file (verbatim)

### SKILL.md

Why: the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
6. **Save, then advance.** A watermark advances only after the write, with an acquisition-evidence receipt.
````

Why: two binding rules added in M3 for the read rules that left the cut acquisition code (scenarios E04, E05, E06, E13, E14); the old rule 12 line is unchanged.

````markdown
12. **Check the date** against two independent signals before naming a dated file.
````

Why: retrofit_permalinks.py was cut: its job is finished (no September or October daily plan has a bare timestamp).

````markdown
- [references/transcript-formats.md](references/transcript-formats.md): file shapes, permalinks, retrofit. Read it when creating a transcript file.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
- [references/cross-workspace-visibility.md](references/cross-workspace-visibility.md), [references/slack-token-guide.md](references/slack-token-guide.md): visibility modes; minting tokens. Read them when `slack_workspaces.py doctor` fails.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
Each step below is its command; the full step is in references/sync-protocol.md. Before any sync, `scripts/slack_workspaces.py doctor` names the readable workspaces (exit 1: a token is missing).
````

Why: Contents gained preserved.md, which every reference file must be listed in.

````markdown
- [references/coverage-map.md](references/coverage-map.md): where the 3.14.0 text lives.
````

Why: thread_checker.py moved from the skill root into scripts/ with the other scripts.

````markdown
`python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel>.md [action_plan_file]`, also for `_dms.md` and `_group-dms.md`; every thread it lists is re-read in Step 2.
````

Why: `synthesis exec-public` was the old receipt-owned launcher; v5 has no such command, so scripts run with `python3` from their skill folder; the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
`slack_read_channel(resolved_channel_id, oldest=WINDOW_OLDEST, limit=30, detail="detailed")`, with `WINDOW_OLDEST` printed by `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py window --workspace <W> --surface slack --target <resolved id>`. Acquire through `synthesis exec-public synthesis-slack-sync/scripts/acquire.py` with the declared Web API adapter.
````

Why: `synthesis exec-public` was the old receipt-owned launcher; v5 has no such command, so scripts run with `python3` from their skill folder; the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
Write, then `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <the window's latest> --acquisition-evidence <receipt.json>`. Gate: `sync_watermark.py status --workspace <W> --surface slack --since run --targets-from <declared.json>`.
````

Why: the declared set's consumer is named (the watermark status at Step 4), since the acquisition gate it also fed is gone.

````markdown
`python3 <synthesis-slack-sync-root>/scripts/preflight.py --config .agents/slack-sync.yaml` prints the resolved-target table and a **census** line (`census: 9 C / 4 D / 0 unresolved`); `--json --out <declared.json>` writes the declared set. Exit 1: a target is unresolved; exit 2: empty set or bad config.
````

### references/configuration.md

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
Read when setting up a project, or when a path, token or workspace is wrong.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
- Multi-workspace registry (v3.11.0), path resolution summary (v3.0.0), private-repo discovery (ADR-014)
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
## Multi-workspace registry (v3.11.0)

A principal with several Slack workspaces declares them once per machine in
`~/.synthesis/slack-workspaces.yaml` (seed with
`scripts/slack_workspaces.py init`; tokens are `PLACEHOLDER` until provided,
never literals). Before any sync, run
`scripts/slack_workspaces.py doctor` from inside the session workspace: exit 0
names the readable set, exit 1 names the workspace whose token is still
missing. Visibility doctrine — unified (default focus plus purpose-bound
cross-workspace reads) versus isolated (session workspace only, with
machine-level enforcement) — lives in
`references/cross-workspace-visibility.md`; token minting and installation in
`references/slack-token-guide.md`. Syncs read only the `readable` set the
registry reports for the session workspace.
````

### references/cross-workspace-visibility.md

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
The ecosystem supports two visibility postures, declared per machine in
the workspace registry (`scripts/slack_workspaces.py init` writes
`~/.synthesis/slack-workspaces.yaml`). The same two postures apply to
every message surface (Slack, email, calendars, chat): Slack is the
first surface with a registry; the others follow the same doctrine.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
- Only workspaces whose tokens resolve to `ready`/`external` are
  readable. Placeholders read as unconfigured, never as empty.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
forbidden — not discouraged, forbidden: the `readable` set is the
focus workspace alone even when other workspaces are configured and
their tokens are valid.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
- Soft: `mode: isolated` in the registry. The agent refuses
  cross-workspace reads as a policy violation.
- Hard (machine-level): the workspace is absent from that machine's
  registry and MCP configuration entirely. A workspace the machine
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
- A principal opts into `isolated` by setting `mode:` in the registry.
````

Why: slack_read.py and the registry's token machinery were cut (never configured: every token was PLACEHOLDER); the workspace map and the visibility rule moved to the synthesis config.

````markdown
- Moving a workspace to its own machine (the future separate-computer
  shape) is a registry operation, not a code change: the workspace
  exists only on its machine's registry, with its own tokens.
````

### references/provenance-and-errors.md

Why: the quote-provenance Stop hook was old machinery (a private per-turn hook); v5's turn-end reply check covers unsourced quotes in replies.

````markdown
A Stop hook at `~/.claude/hooks/quote-provenance-checker.py` (installed alongside `~/.claude/hooks/lazy-shortcut-detector.py` for the parallel discipline) scans the conversation transcript for Slack-TS-shaped values written into transcript / daily-plan / context files that did NOT appear elsewhere in the session — no MCP read, no Read tool result, no user message containing them, no other tool input. Candidates are logged to `~/.claude/quote-provenance-log.jsonl` with the file path, the fabricated TS values, and a stderr warning. The hook does NOT block writes; it makes violations visible after the fact for the user to review.
````

### references/sync-protocol.md

Why: the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
- Step 1: Read channels for new top-level messages (windows, acquisition entries, acquisition evidence)
````

Why: Step 2 gained Source D (replies to older threads found by search, scenario E02).

````markdown
- Step 2: Re-read ALL active threads — today AND recent days (sources A, B, C; mechanical check)
````

Why: thread_checker.py moved from the skill root into scripts/ with the other scripts.

````markdown
python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/<channel>.md [action_plan_file]
python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_dms.md [action_plan_file]
python3 <synthesis-slack-sync-root>/thread_checker.py {transcripts_repo}/{transcripts_path}/slack/YYYY-MM-DD/_group-dms.md [action_plan_file]
````

Why: names the consumer of the declared set, now that the acquisition gate is gone, and the standard-library config reader.

````markdown
Run `python3 <synthesis-slack-sync-root>/scripts/preflight.py --config .agents/slack-sync.yaml` (v3.10.0): it prints the resolved-target table for the sync report and a prefix **census** line (for example `census: 9 C / 4 D / 0 unresolved`), and `--json --out <declared.json>` writes the declared set the watermark gate consumes — derived from the config this run, never a stored copy.
````

Why: `synthesis exec-public` was the old receipt-owned launcher; v5 has no such command, so scripts run with `python3` from their skill folder.

````markdown
- **`WINDOW_OLDEST` is the `oldest=` epoch printed by** `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py window --workspace <W> --surface slack --target <resolved id>` — never hand-computed, never copied from a transcript header, never midnight. Quote the human-readable bounds the command prints in the sync report, so the window is checkable by eye (v3.8.0; a hand-typed `oldest` of 07:50 *today* once reported five channels empty that were not).
````

Why: the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
Use `synthesis exec-public synthesis-slack-sync/scripts/acquire.py` with the explicitly declared structured Web API adapter, following [declared acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md). Recorded connector calls remain source custody, but their rendered message strings cannot prove author or message boundaries. Connector replay therefore reports a blocking problem and refuses attributable archives or watermark advancement; repeating those same reads cannot repair that limitation. The owner consumes preflight and the current registry and never discovers targets or falls back to direct credentials. Keep unsupported connector coverage UNKNOWN.

Before advancing a Slack watermark, read the mandatory [acquisition evidence contract](../../synthesis-daily-rituals/references/acquisition-evidence.md). Use detailed channel/DM reads with complete pagination, independently search within the declared window for replies (including old parents), and follow the union of local known threads, history indicators, and search parents. `thread_checker.acquire_channel` provides this bounded read-only adapter flow. Retain actual in-window positive controls and raw call references; historical controls or empty/concise reads cannot establish absence. Save exact message IDs and bytes, then pass the complete receipt to `sync_watermark.py advance --acquisition-evidence`. If a connector lacks required detail or pagination, report unknown coverage and keep the watermark.
````

Why: `synthesis exec-public` was the old receipt-owned launcher; v5 has no such command, so scripts run with `python3` from their skill folder; the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
- **Record the read once it is saved (v3.8.0):** for each target whose window was read and whose messages (or confirmed absence) are now on disk, run `synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py advance --workspace <W> --surface slack --target <resolved id> --through <the window's latest> --acquisition-evidence <receipt.json>`. The watermark advances only after the write, so a read that failed to save cannot claim coverage — and the gate at the end of the sync (`sync_watermark.py status --workspace <W> --surface slack --since run --targets-from <declared.json>`, the declared set written by `preflight.py --json --out` this run and never a stored copy) lists exactly the targets this sync did not re-read.
````

Why: retrofit_permalinks.py was cut: its job is finished (no September or October daily plan has a bare timestamp).

````markdown
The per-channel, `_dms.md`, and `_group-dms.md` file shapes, the permalink construction rule, the `Send to:` line form, and the retrofit script are in [references/transcript-formats.md](transcript-formats.md). The rules that bind every write:
````

Why: retrofit_permalinks.py was cut: its job is finished (no September or October daily plan has a bare timestamp).

````markdown
- `retrofit_permalinks.py <plan.md> --config <slack-sync.yaml>` converts a legacy bare-TS file to permalinks in one idempotent pass (`--dry-run` to preview); for multi-workspace plans run it once per workspace config.
````

### references/transcript-formats.md

Why: the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
- Deterministic acquisition output
````

Why: the acquisition gate (acquire.py, connector replay, acquisition-evidence receipts) was cut (verdict CUT); its read rules are now protocol text in sync-protocol.md, Step 1 read rules and Step 2 Source D.

````markdown
## Deterministic acquisition output

The verified acquisition entry retains these same daily paths and uses a
source-owned reversible raw codec. See [acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md).
Each message and reply has an explicit marker:

```markdown
**Message ID:** C123:1790560000.000000
**User ID:** U123
**Parent ID:** C123:1790560000.000000
```

DM/group-DM markers use their actual D/G conversation IDs. Exact text stays in a
length-delimited Markdown fence; full source variants, reactions and attachments
remain in the raw-metadata footer and original response custody. The renderer
does not resolve names or invent speaker attribution. It may use a channel-ID
subheading in a single-channel file so the existing known-thread parser has
unambiguous identity.

The illustrative hand-maintained shapes below are not proof of acquisition.
They require the same Message ID markers before the evidence gate can use them.
Existing non-codec archives remain readable for known-parent discovery; the
automated publisher refuses to overwrite/merge them until an explicit source
reconciliation establishes the new exact representation.
````

Why: retrofit_permalinks.py was cut: its job is finished (no September or October daily plan has a bare timestamp).

````markdown
- Slack Permalink Construction: visible text, the draft "Send to:" line, fallback without `slack_workspace_domain`, retrofitting older daily plans
````

Why: retrofit_permalinks.py was cut: its job is finished (no September or October daily plan has a bare timestamp).

````markdown
### Retrofitting older daily plans

`retrofit_permalinks.py` (shipped alongside `thread_checker.py` in this skill directory) converts a legacy daily plan or transcript file from the bare-TS format to the clickable-permalink format in one pass. It reads the workspace domain and channel-name → channel-ID map from a `slack-sync.yaml` config — generic-skill, no hardcoded workspace.

```bash
python3 retrofit_permalinks.py <plan.md> --config <slack-sync.yaml>
python3 retrofit_permalinks.py <plan.md> --config <slack-sync.yaml> --dry-run
```

Skip rules: lines containing only "parent thread TS" references are left as-is (the visible time on those lines refers to the reply, not the parent — linking it to the parent's TS would be wrong); lines with no resolvable channel hint are left unchanged (the script needs at least one `#channel-name` or `D0…`/`C0…` ID inline to construct a permalink). The script is idempotent — running it on an already-retrofitted file is a no-op.

For multi-workspace daily plans (a single plan referencing messages from more than one Slack workspace), run the script once per workspace's `slack-sync.yaml`. Each pass linkifies only the TSes whose channel resolves via the config it was given; other lines fall through to the next pass.
````

### references/sync-protocol.md, the whole Step 0 preflight paragraph

Why: its first sentence was restated in M3 (the block under references/sync-protocol.md above); the paragraph as it stood before:

````markdown
Run `python3 <synthesis-slack-sync-root>/scripts/preflight.py --config .agents/slack-sync.yaml` (v3.10.0): it prints the resolved-target table for the sync report and a prefix **census** line (for example `census: 9 C / 4 D / 0 unresolved`), and `--json --out <declared.json>` writes the declared set the watermark gate consumes — derived from the config this run, never a stored copy. It validates the id prefix per class (`C`/`G` for channels and group DMs, `D` for DMs; a `U`-prefixed id is never a read target), exits 1 when any declared target is unresolved so the report must name it, and exits 2 on an empty resolved set or a malformed config. Steps 1, 3, and 3b iterate ONLY its resolved-target list. Reaching back into the config for an id mid-sweep is the banned move from v3.6.0: where an entry carries two id-like fields, the wrong one usually resolves, so the bug hides until the person behind it leaves — and on 2026-09-01 a careful reader with the config open, warned minutes earlier, still derived every DM target as a user id; the census makes that a visibly wrong shape instead of quiet empties.
````

## references/slack-token-guide.md at 4.0.0 (verbatim)

Retired whole: it described minting and installing the user tokens `slack_read.py` needed. Reads go through the harness's Slack connector, which needs no token in the synthesis config.

````markdown
# Slack token guide: finding and installing workspace tokens

Each Slack workspace needs its own token. The registry
(`~/.synthesis/slack-workspaces.yaml`) names where each token lives;
this guide covers minting one and pointing the registry at it.
`slack_workspaces.py init` seeds generic `personal`/`work` entries —
rename them to match the session-workspace keys (the
`~/workspaces/<name>` directory names) and add further workspaces as
needed before installing tokens.

## Minting a token (per workspace)

1. Open [api.slack.com/apps](https://api.slack.com/apps) in a browser
   signed into the workspace.
2. Create a new app (From scratch), name it after the reader
   (e.g. `synthesis-reader`), pick the workspace.
3. Under OAuth & Permissions, add these **User Token Scopes** (not
   Bot Token Scopes): `channels:history`, `groups:history`,
   `im:history`, `mpim:history`, `channels:read`, `groups:read`,
   `im:read`, `mpim:read`, `search:read`, `users:read`. (No write
   scopes: the reader never posts. If the workspace admin must
   approve the app, this read-only list is the approval case.)
4. Install the app to the workspace and copy the User OAuth Token
   (`xoxp-...`).

The acquisition adapter reads as a person, so it needs a user token:
Slack's `search.messages` accepts only user tokens, and the
adapter's `auth.test` check refuses a bot identity outright. A bot
token (`xoxb-...`) cannot advance a Slack watermark.

A workspace that the agent already reads through a client-managed
Slack connector needs no token at all: set the registry's `token:` to
`mcp:<server>` and use the connector-replay adapter described in
[declared acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md).

If the workspace already has a reader app (a previous install), reuse
it: open the app, OAuth & Permissions, copy the token. Nothing
requires one app per machine.

## Installing the token (per machine)

Pick one form per workspace and set the registry's `token:` field:

- `env:SLACK_TOKEN_<WORKSPACE>` — export the variable in the shell
  profile (e.g. `export SLACK_TOKEN_WORK='xoxp-...'` in
  `~/.zshrc`). Best for CLI clients that inherit the shell.
- `file:/abs/path/to/token` — first line is the token. Best when env
  vars are awkward; keep the file `chmod 600`.
- `mcp:server-name` — the client manages the credential (OAuth or its
  own secret store) and exposes the workspace through an MCP server
  with this name. Readiness is proven by the first MCP call. For
  Claude Code, the name is the server segment of the connector's
  tool names (`mcp__<server>__slack_read_channel`).

Never paste a literal token value into the registry: `doctor`
rejects it. The registry is a synced dotfile; secrets don't live in
synced dotfiles.

## Verifying

```
python3 <synthesis-slack-sync-root>/scripts/slack_workspaces.py doctor
```

Run from inside `~/workspaces/<name>` so the session workspace
resolves. Exit 0 with `readable from here:` listing the workspaces
means the sync may read them. Exit 1 names the workspace whose token
is still a placeholder, missing, or rejected.

## Sending tokens to the agent later

When the principal provides tokens after the registry was seeded with
placeholders, the agent installs each token in the agreed form (env
var or file — never the registry, never chat logs beyond the paste),
re-runs `doctor`, and reports the readable set. The placeholder entries
exist so this step is installation, not redesign.
````
