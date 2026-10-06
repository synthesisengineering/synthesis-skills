# Slack sync: configuration, paths and prerequisites

Read when setting up a project, or when a path or workspace is wrong.

Contents:
- Protocol and config: what the skill provides and what the per-project config provides
- Configuration: `.agents/slack-sync.yaml` with schema comments
- Multi-workspace map (v3.11.0; in the synthesis config since v4.0.0), path resolution summary (v3.0.0), private-repo discovery (ADR-014)
- Prerequisites

## Protocol and config

This skill provides the **protocol** — the sync methodology, thread re-reading discipline, transcript format, and action plan update rules. A per-project **config file** provides the specifics: which channels, which paths, which DMs. Prefer `.agents/slack-sync.yaml`; existing `.claude/slack-sync.yaml` configs remain supported.

Version history and the incidents behind each rule: [references/version-history.md](version-history.md). Transcript and permalink formats: [references/transcript-formats.md](transcript-formats.md). Draft templates: [templates/draft-block.md](../templates/draft-block.md) and [templates/sent-marker.md](../templates/sent-marker.md).

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

## Multi-workspace map (v3.11.0; in the synthesis config since v4.0.0)

A principal with several Slack workspaces declares them once per machine in the
synthesis config (`~/.synthesis/v5/config.json`, or `$SYNTHESIS_HOME/config.json`):

```json
"slack_workspaces": {
  "mode": "unified",
  "workspaces": {
    "example-workspace": {"domain": "example-workspace.slack.com"},
    "personal": {"domain": "example-personal.slack.com"}
  }
}
```

The keys are the session-workspace names (the `~/workspaces/<name>` folders).
Before any sync, run `python3 <synthesis-slack-sync-root>/scripts/slack_workspaces.py`
from inside the session workspace (or with `--session-workspace <name>`): it prints
the mode, each workspace's domain and the readable set; exit 2 means the map is
missing or malformed or the session workspace is not in it. Visibility doctrine —
unified (default focus plus purpose-bound cross-workspace reads) versus isolated
(session workspace only, with machine-level enforcement) — lives in
`references/cross-workspace-visibility.md`. Syncs read only the readable set it
reports, each through the Slack connector the session has for that workspace. No
token is stored or needed: reads go through the harness's Slack connector.

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
