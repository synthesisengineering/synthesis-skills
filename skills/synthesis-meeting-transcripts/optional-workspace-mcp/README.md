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
| `mcp_client.py` | Small JSON-RPC client used by `fetch-meeting.py` to call MCP tools over HTTP |

## Verified acquisition and one-off lookup

For complete declared account/folder/window acquisition, use the verified
Python health/inventory/fetch route in [declared acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md).
It explicitly selects the Google REST adapter; no service or token fallback
occurs. The documented workspace-mcp plain-text response does not supply stable
tab identity. A title lookup therefore cannot certify full-window coverage.

The separate one-off lookup still uses the local MCP server:

```text
synthesis exec-public synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py standup --date 2026-04-21
```

This mode requires source-native structured tab evidence before a verified save.
Service setup remains in the existing start/install owners and requires the
owner's authorization; acquisition does not install a service.

## When the MCP tools go missing

An auto-start service that dies stays dead quietly. Run the doctor first:

```bash
./doctor.sh          # full report
./doctor.sh --quiet  # exit code + service/recorder summary, for hooks and rituals
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

- The verified runtime's selected interpreter contains httpx and PyYAML. Follow
  the dependency setup in the acquisition reference; a temporary uv interpreter
  is not the installed verified runtime.
- The existing meeting-transcripts YAML has the exact account/archive settings.
- MCP lookup additionally needs the declared local server and actual account
  authentication. The direct adapter instead consumes one explicitly referenced
  read token and the declared folder/tab contract; it never acquires a token.

The service doctor reports supervisor/HTTP liveness and retains its 0/1/2 exit
semantics. Its RECORDER UNKNOWN line is intentional. Actual declared account
authentication is observed only by the Python health route, and neither health
plane establishes complete source coverage.

## Why separate from the skill core

The parent skill deliberately stays tool-agnostic so it works for the majority of users on Anthropic's hosted connectors. These scripts are for the minority who need multi-account parallelism. Keeping them in a subdirectory documents that separation and keeps the skill's core free of self-hosted-specific assumptions.
