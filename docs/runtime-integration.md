# Runtime contract

What a harness adapter must provide for the synthesis runtime to work in it.
Claude Code, Codex and Muse meet this contract today; an adapter for another
harness meets the same one. The code it describes is `hooks/hooks.json`,
`.muse-plugin/`, `synthesis/hook.py` and `synthesis/install.py`.

## Skills

The skills are the `skills/<name>/SKILL.md` trees, in the
[Agent Skills](https://agentskills.io) format. A harness either loads them
natively from the plugin or reads them through a documented Agent Skills
bridge. Harness-specific discovery metadata lives beside the skill (Codex's
is `agents/openai.yaml`) and never changes the shared text. The format rules,
including the 8,000-byte limit on `SKILL.md`, are in
[skill-format.md](skill-format.md).

## The stable hook path

Every hook runs one command:

```text
$HOME/.synthesis/v5/bin/synthesis-hook <event>
```

`synthesis install` writes that script, and its text never changes between
releases. A harness that asks the person to trust a hook's exact
definition (Codex's `/hooks`, Muse's `plugins approve`) therefore keeps that
trust across upgrades, and a harness deleting an old plugin folder never breaks
a running session. The script runs
`python3 -S ~/.synthesis/v5/current/synthesis/hook.py <event>`; `current` is a
symlink switched atomically, so a running hook sees the old release or the new
one, never neither.

The SessionStart registration also passes the plugin folder the harness loaded
(Claude Code's `${CLAUDE_PLUGIN_ROOT}`; Muse's `MUSE_PLUGIN_ROOT`, or the
script's own location). If the stable hook is missing it installs the runtime
from that folder first, and on every start it installs the folder's runtime if
it differs from the current one. A failed self-update never blocks the session;
`synthesis doctor` reports it.

## The four events

| Harness event | Argument | Timeout | Registered for |
|---|---|---|---|
| SessionStart | `session-start` | 10 s | every start, with no matcher, so it also fires after compaction where the harness supports that |
| UserPromptSubmit | `user-prompt-submit` | 5 s | every prompt |
| PreToolUse | `pre-tool-use` | 5 s | shell tools, and MCP tools whose names send, draft, reply, forward, schedule, change calendar events, set focus time or out-of-office, trash mail, or share files |
| Stop | `stop` | 5 s | every turn end |

The PreToolUse matcher is the regular expression in `hooks/hooks.json`;
`tests/test_hooks_registration.py` checks that every guarded tool reaches it and
that reads and edits never start it. A harness without matchers (Muse) runs the
hook for every tool, and the hook returns at once for tools it does not guard.
Register no other events: `tests/test_hooks_registration.py` fails if more than
these four appear.

## What the hook reads

Each event reads one JSON object on stdin. Missing fields are tolerated.

| Field | Events | Used for |
|---|---|---|
| `session_id` | all | The session's identity on the board. If absent, the hook reads `SYNTHESIS_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID` or `MUSE_SESSION_ID` from the environment. |
| `cwd` | SessionStart, PreToolUse | The session's working directory: the workspace for account routing, the directory a shell command starts in, and the ritual line's workspace. |
| `prompt` (or `user_prompt`) | UserPromptSubmit | The text the person typed, scanned for `approve <code>`. |
| `tool_name`, `tool_input` | PreToolUse | The call to check. A shell command is read from `tool_input.command` or `tool_input.cmd`, as a string or an argv list; `tool_input.workdir` is the fallback directory. |
| `last_assistant_message`, `transcript_path` | Stop | The reply to check, and the session record its quotes must appear in. |
| `stop_hook_active` | Stop | Whether this turn end follows a hook's earlier request to continue. |
| `background_tasks`, `session_crons` | Stop | Whether something already scheduled will wake an autopilot session. |

The harness is identified from the environment (`CLAUDECODE` or
`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`, `MUSE_SESSION_ID` or
`MUSE_PLUGIN_ROOT`). An adapter for a new harness adds its variables to
`synthesis/paths.py`.

## What the hook returns

The hook writes at most one JSON object to stdout, in Claude Code's hook output
schema, and decides through that output rather than its exit code. An adapter for a harness with another schema
translates these four shapes:

- SessionStart and UserPromptSubmit:
  `{"hookSpecificOutput": {"hookEventName": ..., "additionalContext": "<text>"}}`,
  text the harness adds to the model's context.
- PreToolUse, to block:
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "<why>"}}`.
  No output means allow.
- Stop, to send the reply back:
  `{"decision": "block", "reason": "<what to do>"}`. A note for the person
  without blocking: `{"systemMessage": "<text>"}`.

## Approvals

When a guard holds a send or a deploy, it files a request whose six-character
code comes from a SHA-256 digest of the exact call (for a send, the tool and its
whole input; for a deploy, the command and, inside a git checkout, the commit at
HEAD). The block message tells the agent to show the person the exact text or
command and ask them to reply `approve <code>`. The UserPromptSubmit hook finds the code in
the person's prompt and grants the request; the next identical call consumes the
grant once. Requests and grants expire after 15 minutes. `synthesis approvals`
lists what is waiting.

This works only because the agent cannot write the person's prompt. An adapter
must pass UserPromptSubmit the text the person typed, never text the agent or a
tool produced; a harness that cannot guarantee that cannot host the send or
deploy guards, and the adapter must say so.

## Compaction

The SessionStart output is the project brief: local time, the active project's
`PRIME-DIRECTIVE.md` and current-state block, the session's autopilot run, one
ritual line, and the unread-message count. Re-injecting it after compaction is
what lets a long session keep its directive. Claude Code and Codex rerun
SessionStart after compacting. An adapter for a harness that does not must say
so; a session there recovers with `synthesis brief`.

## Failure behavior

- **PreToolUse fails closed** for the calls it guards: an unreadable
  `~/.synthesis/v5/config.json` or an exception inside a guard blocks the call
  with the reason.
- **Stop fails open**, because a turn-end check that fails closed loops
  forever. The reply check sends a reply back at most once in a row, and an
  autopilot run is asked to continue at most `autopilot.max_continuations`
  times in a row (3 by default) before the session is allowed to stop.
- **SessionStart never blocks a session.** A failed self-update is skipped and
  `synthesis doctor` reports the stale runtime; a ritual line that cannot be
  computed is left out.

## Hook trust

When a harness asks the person to review or approve hooks, that decision stays
with the person. Setup never approves hooks; `synthesis doctor` names every
hook still waiting, and for Codex it reproduces the trust hash Codex stores to
find hooks that are untrusted, modified or disabled.

## Adding another harness

An adapter for another harness provides:

1. a native plugin install through the harness's own commands, added to the
   onboarding [setup.py](../skills/synthesis-onboarding/scripts/setup.py),
   with an uninstall path;
2. hook registration that calls the stable hook path for all four events, in
   the harness's own format;
3. the payload fields above, or a translation from the harness's own;
4. a session-id and harness variable in `synthesis/paths.py`;
5. a `synthesis doctor` check that reads the harness's installed plugin through
   its own read-only listing command and confirms the hooks are wired;
6. tests for each of these, and a stated list of what the harness cannot do.

A harness is supported once these are merged and a fresh session in it shows
the SessionStart brief. The
[conformance audit](../skills/synthesis-agent-conformance/references/audit.md)
describes the live checks.
