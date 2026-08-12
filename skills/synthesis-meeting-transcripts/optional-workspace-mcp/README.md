# Optional — workspace-mcp integration bundle

The scripts in this directory are **optional helpers** for users who run [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp) locally to access multiple Google accounts simultaneously (Anthropic's hosted Gmail + Drive connectors currently support only one Google account at a time).

If you use Anthropic's hosted Gmail + Drive connectors and a single Google account is sufficient, you **do not need these scripts**. The parent `synthesis-meeting-transcripts` skill works directly with the hosted connectors.

## What's here

| File | Purpose |
|------|---------|
| `start.sh` | Launches the workspace-mcp server in the background (macOS/Linux) |
| `stop.sh` | Stops the running workspace-mcp server |
| `fetch-meeting.py` | Cross-platform script that fetches a meeting transcript deterministically — bypasses the LLM. Use from a shell, cron, or a skill that wants speed over flexibility |
| `install-autostart.sh` | Installs a launchd user LaunchAgent (macOS) or systemd user unit (Linux) so workspace-mcp auto-starts on login |
| `doctor.sh` | Health check for the auto-start service — verifies the unit exists, points at a start script that still exists, is loaded, and is actually serving |
| `uninstall-autostart.sh` | Removes the auto-start configuration |
| `mcp_client.py` | Small JSON-RPC client used by `fetch-meeting.sh` to call MCP tools over HTTP |

## Quick start

```bash
# One-time install (after you've set up workspace-mcp per its README):
./install-autostart.sh

# Start the server manually if you skipped auto-start:
./start.sh

# Pull today's standup for the default account configured in .agents/meeting-transcripts.yaml:
uv run --with httpx --with pyyaml python fetch-meeting.py standup

# Or a specific date:
uv run --with httpx --with pyyaml python fetch-meeting.py standup --date 2026-04-21

# Any other meeting name (uses generic_pattern from config):
uv run --with httpx --with pyyaml python fetch-meeting.py "PDE Leadership sync"

# Override the Google account for one fetch:
uv run --with httpx --with pyyaml python fetch-meeting.py standup --account me@work.example.com
```

## When the MCP tools go missing

An auto-start service that dies stays dead quietly. Run the doctor first:

```bash
./doctor.sh          # full report
./doctor.sh --quiet  # exit code + one summary line, for hooks and rituals
```

Exit codes follow the synthesis guard contract: `0` healthy, `1` defects found,
`2` a check could not run (health unknown, not confirmed).

**The most common failure is a stale unit path.** `install-autostart.sh` records an
absolute path to `start.sh` at install time. Move the checkout, rename a parent
directory, or restructure the repo, and the unit still points at the old location:
the supervisor exits `78` (`EX_CONFIG`), `KeepAlive` retries on a 30-second throttle
forever, the log fills with identical failures, and the only visible symptom is that
your MCP tools are absent. The doctor names the missing path and the current one.

The fix is always to **re-run the installer**, never to hand-edit the unit —
`install-autostart.sh` derives the path from its own location, so it is correct by
construction:

```bash
./install-autostart.sh
```

Consider wiring `./doctor.sh --quiet` into a daily ritual or login check. A guard with
no heartbeat is indistinguishable from a guard that is working.

## Prerequisites

- [workspace-mcp](https://github.com/taylorwilsdon/google_workspace_mcp) installed and authenticated to your Google accounts
- `uv` (runs the Python deps `httpx` and `pyyaml` on demand — no global pip install needed)
- Your `.agents/meeting-transcripts.yaml` filled in (see parent skill's SKILL.md). Existing `.claude/meeting-transcripts.yaml` configs are supported.

## Shell alias for convenience

Add to your `.zshrc` / `.bashrc`:
```bash
alias fetch-meeting='uv run --with httpx --with pyyaml python ~/path/to/fetch-meeting.py'
```
Then just `fetch-meeting standup` from any project that has `.agents/meeting-transcripts.yaml` or a compatible `.claude/meeting-transcripts.yaml`.

## Why separate from the skill core

The parent skill deliberately stays tool-agnostic so it works for the majority of users on Anthropic's hosted connectors. These scripts are for the minority who need multi-account parallelism. Keeping them in a subdirectory documents that separation and keeps the skill's core free of self-hosted-specific assumptions.
