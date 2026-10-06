# Setup: configuration, prerequisites and accounts

What the skill needs before its first fetch, as written in 0.14.0: the per-project config, prerequisites, the multi-account options, and why the skill is tool-agnostic.

Contents:
- Protocol and config, and the tools the skill works with
- Configuration: `.agents/meeting-transcripts.yaml`
- Prerequisites
- When Multi-Account Matters
- Why Tool-Agnostic Matters

## Protocol and config

This skill provides the **protocol** — how to find a meeting's Gemini-generated doc, extract both the notes summary and the full transcript, and save them to the right local folder. A per-project **config file** provides the specifics: which Google account, which meeting patterns to recognize, where to save locally. Prefer `.agents/meeting-transcripts.yaml`; existing `.claude/meeting-transcripts.yaml` configs remain supported.

This skill is **tool-agnostic.** It works with:

- Anthropic's hosted Claude Connectors for Gmail + Drive (single-account, most common)
- Self-hosted multi-account servers like [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) (a bundled auto-start helper is in `optional-workspace-mcp/`)
- Any other MCP that provides equivalent Gmail search + Drive file read capabilities

The skill describes the *workflow*; it does not prescribe which tools must be used.

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

## Prerequisites

- A Gmail MCP and a Drive MCP must both be connected and authenticated for `google_account`. This skill doesn't care which specific MCPs — it will use whatever Gmail/Drive tools are available in the session.
- Local transcript directory must exist or be creatable at `{transcripts_repo}/{transcripts_path}/meetings/`.

## When Multi-Account Matters

Anthropic's hosted Gmail and Drive connectors support **one Google account each** (as of early 2026). If the user routinely needs transcripts from a work account different from their personal account, they'll hit this limit.

**Workarounds:**

1. **Switch the connector account.** Works if the user primarily uses one account. Tedious if they switch often.
2. **Use a self-hosted multi-account MCP server.** Recommended: [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp). A bundled setup helper is in this skill's `optional-workspace-mcp/` directory — it provides `start.sh`, `stop.sh`, `install-autostart.sh` (macOS + Linux), and a cross-platform `fetch-meeting.py` that shells out to the MCP server directly for deterministic pulls.
3. **Use one Claude account per Google account.** Claude Desktop can run two separate instances (macOS: `open -n -a "Claude" --args --user-data-dir=...`), each signed into a different Claude account with different connectors. Heaviest setup.

The skill's Step 2 and Step 3 work identically across all three paths. Config only needs to specify `google_account`; how authentication is wired up is the user's problem to solve once.

## Why Tool-Agnostic Matters

Most teams use Anthropic's hosted Gmail + Drive connectors — that's the default and it works. This skill is intentionally built so that the common path "just works" with the default connectors. The multi-account self-hosted route exists for users like the author whose work life spans multiple Google Workspace domains, but it's deliberately optional and lives in a subdirectory so it doesn't clutter the core workflow for users who don't need it.

If a future MCP ecosystem produces a multi-account Gmail/Drive connector with Anthropic-hosted convenience, this skill should work against that too with zero changes. The workflow stays; the tool bindings update.
