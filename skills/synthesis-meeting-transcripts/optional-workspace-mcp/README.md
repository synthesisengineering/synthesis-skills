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

## Fetching one meeting, and checking a window

`fetch-meeting.py` uses only the Python standard library, so any `python3` runs it
(Apple's `/usr/bin/python3` included). From a project with
`.agents/meeting-transcripts.yaml`:

```bash
python3 <synthesis-meeting-transcripts-root>/optional-workspace-mcp/fetch-meeting.py standup --date 2026-04-21
python3 <synthesis-meeting-transcripts-root>/optional-workspace-mcp/fetch-meeting.py --window 2026-10-01 2026-10-05
```

The first finds the one doc matching the meeting's pattern on that date, lists its
tabs, picks the transcript by tab ID (or by a title exactly one tab carries), saves
notes and verbatim transcript with the `**Source ID:**` and `**Transcript tab ID:**`
headers, and runs `verify_transcripts.py` on the saved file; it prints the path and
the verdict. A tool error, an unreadable or incomplete tab list, or two matching docs
saves nothing and exits 1. A complete tab list with no transcript tab saves the notes
with the no-source marker.

The second lists every doc the declared patterns find in the window, saved or
unsaved, and `advance_through`: the moment the meetings watermark may move to (the
window end, or just before the first unsaved doc). A doc counts as saved when the
first 4,000 characters of a file in the archive's `meetings/` folder name its ID in
one of three forms: the `**Source ID:** google-drive:<id>` header this script
writes, a Google Doc link (`/document/d/<id>`), or a blockquote provenance line
whose first backticked ID is the doc's (`` > Source: Gemini doc `<id>` — ... ``).
Drive's listing carries no
completeness flag, so a full page leaves `advance_through` empty, and the listing is
what Drive returned, not proof that nothing else exists.

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

- `python3` (3.9 or later); no third-party packages.
- The meeting-transcripts YAML has the account and archive settings
  (references/setup.md).
- The local workspace-mcp server is running and signed in to that account. The
  service doctor reports supervisor and HTTP liveness with its 0/1/2 exit codes;
  its `ACCOUNT: not checked` line is deliberate: a read as the declared account
  (for example `python3 mcp_client.py list_calendars '{"user_google_email": "<account>"}'`)
  shows which account answers.

The service is installed under the launchd label `com.synthesis.workspace-mcp`
(systemd: `workspace-mcp.service`). An install from an earlier release may carry a
personal label; run `uninstall-autostart.sh` from that release, or `launchctl bootout`
the old label and remove its plist, then run `./install-autostart.sh`.

## Why separate from the skill core

The parent skill deliberately stays tool-agnostic so it works for the majority of users on Anthropic's hosted connectors. These scripts are for the minority who need multi-account parallelism. Keeping them in a subdirectory documents that separation and keeps the skill's core free of self-hosted-specific assumptions.
