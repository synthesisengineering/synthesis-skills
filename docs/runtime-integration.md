# Runtime contract

What a harness adapter must provide for the synthesis runtime to work in it.
Claude Code and Codex meet this contract, and Muse meets it with the gaps stated
under [Muse](#muse); an adapter for another harness meets the same one. The M5
sandbox run of 2026-10-05 (Claude Code 2.1.288, Codex 0.160.0, Muse 1.4.3) is the
evidence for what this page says about each harness. The code it describes is `hooks/hooks.json`,
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
it is a newer release than the current one. A session still on an older plugin
never switches the runtime back; a rollback is an explicit `synthesis install`.
A failed self-update never blocks the session; `synthesis doctor` reports it.

## The four events

| Harness event | Argument | Timeout | Registered for |
|---|---|---|---|
| SessionStart | `session-start` | 10 s | every start, with no matcher, so it also fires after compaction where the harness supports that |
| UserPromptSubmit | `user-prompt-submit` | 5 s | every prompt; it also briefs a session whose project changed since its last brief |
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
| `session_id` | all | The session's identity on the board. If absent, the hook reads `SYNTHESIS_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID` or `MUSE_SESSION_ID` from the environment. Without `transcript_path`, it also finds the session's transcript (see [Approvals](#approvals)). |
| `transcript_path` | SessionStart, PreToolUse, Stop | Which harness is running (from where the file lives); the record an approval is checked against; the record a reply's quotes must appear in. |
| `cwd` | SessionStart, PreToolUse | The session's working directory: the workspace for account routing, the directory a shell command starts in, and the ritual line's workspace. |
| `prompt` (or `user_prompt`) | UserPromptSubmit | The text the person typed, scanned for `approve <code>`. |
| `tool_name`, `tool_input` | PreToolUse | The call to check. A shell command is read from `tool_input.command` or `tool_input.cmd`, as a string or an argv list; `tool_input.workdir` is the fallback directory. |
| `last_assistant_message` | Stop | The reply to check. |
| `stop_hook_active` | Stop | Whether this turn end follows a hook's earlier request to continue. |
| `background_tasks`, `session_crons` | Stop | Whether something already scheduled will wake an autopilot session. |

The harness is identified first from where its transcript lives: under
`~/.claude/projects` (or `$CLAUDE_CONFIG_DIR/projects`) it is Claude Code, under
`$CODEX_HOME/sessions` or in a file named `rollout-*` it is Codex, under
`$XDG_DATA_HOME/muse/sessions` (default `~/.local/share`) it is Muse. Without a
transcript path it comes from the environment (`CLAUDECODE` or
`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`, `MUSE_SESSION_ID` or
`MUSE_PLUGIN_ROOT`). Codex sets `CODEX_THREAD_ID` in its shell tool but not in hook
processes, which is why every Codex session once showed as `unknown` (M5 defect 2).
A session's recorded harness is never overwritten with `unknown`. An adapter for a
new harness adds its transcript folder and variables to `synthesis/paths.py`.

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

Claude Code 2.1.288 adds every Stop-hook block reason to its list of hook errors,
whether the hook blocks with `{"decision": "block"}` or with exit code 2, and shows
"Stop hook error occurred". The label comes from Claude Code, not from this output:
the documented block shape is the one used, the reply is sent back as intended, and
the label is harmless. Only a Stop `additionalContext` avoids it, and whether that
continues the turn depends on an internal Claude Code setting, so it is not used.

No hook text holds the approval phrase itself: every message rewrites "approve" followed
by a code in the shape the guards issue as "approve code <code>", so a harness that
records hook text as a prompt can never turn it into an approval. Ordinary words after
"approve" are left alone, because every issued code starts with a digit.

## Approvals

When a guard holds a send or a deploy, it files a request under a random
six-character code (a digit, then five hexadecimal characters), keyed to a SHA-256 digest of the exact call (for a send, the
tool and its whole input; for a deploy, the command and, inside a git checkout, the
commit at HEAD). A retry of the same call keeps its code; nobody can know a code
before its request exists. The block message tells the agent to show the person the
exact text or command and to ask them to type approve followed by the code; it never
prints the two together. The UserPromptSubmit hook finds the code in the person's
prompt and records a grant. The next identical call spends the grant once, and only if
the harness's own transcript of the session shows the person typing approve and that
code after the request was filed. Requests and grants expire after 15 minutes.
`synthesis approvals` lists what is waiting.

The commit check uses the same approvals for a disclosure hit: a line in a file or a
commit message that matches the principal's exposure patterns. No word list can tell a
leak from a legitimate mention, and agents that reworded, split or assembled a term at
run time to get past the check weakened the text and defeated the check, so the
principal ruled (2026-10-06) that a legitimate line is approved instead, and that a
flagged term is never reworded, split, encoded or built at run time to get past any
guard. The request is keyed to a SHA-256 of the repository (its normalized push
remotes), the path (or `commit message`) and the line's exact bytes. Once spent, the
approval is kept in the store `line_allowances` names (by default
`line-allowances.json` beside the commit policy) as that hash and a date, so the line
passes from then on; an edited line or a new place asks again. `git commit` from an
agent's shell has no hook payload, so the check finds the transcript by the session id
the shell carries: `CLAUDE_CODE_SESSION_ID` (seen in a live Claude Code shell),
`CODEX_THREAD_ID` (Codex sets it in its shell tool) or `MUSE_SESSION_ID`. Muse 1.4.3's
binary names `MUSE_SESSION_ID`, but the M5 run could not show that its shell tool sets
it (the offline provider calls no tools); until a live Muse session shows it, a Muse
agent sets `SYNTHESIS_SESSION` to its session id for the commit. Credentials are never
approvable; vendors' published example keys pass by exact value.

The person's prompt is the only source of an approval (R3.0). The agent runs as the
same OS user as the hooks, so a grant file proves nothing on its own: in the M5
sandbox an agent granted its own send by piping a made-up prompt into
`synthesis-hook user-prompt-submit`, and it could as well have written the grant file
(M5 defect 1). That is why a grant is checked against the harness's record when it is
spent.

### What counts as the person's prompt

| Harness | Record | Counts | Never counts |
|---|---|---|---|
| Claude Code | `transcript_path` (JSONL) | `user` entries, and `queued_command` prompt attachments (typed while the agent worked), whose `origin`, when present, is `human` | tool results; `isMeta` entries (Stop-hook feedback, messages from other sessions); `isSidechain` entries (subagents); compaction summaries; hook attachments; the agent's own text |
| Codex | `transcript_path` (the rollout JSONL) | `UserMessage` items, and `user_message` events in older rollouts | function-call output; command items; developer messages (hook context); `HookPrompt` items and `<hook_prompt>` messages (Stop send-backs) |
| Muse | `transcript_path`, else the session log found by its id under `$XDG_DATA_HOME/muse/sessions/` | `runtime.user_intent.accepted` chat intents on the main surface, from this session | runtime-hook context blocks; tool records; intents from another session |

Inside a counted prompt, text the harness wraps in a tag block (`<system-reminder>`,
`<task-notification>`, `<bash-stdout>`, pasted content) does not count. A script run
from a harness's shell (the iMessage sender) has no hook payload, so it finds the
session's transcript by the session id its shell carries. When there is no
transcript, when it cannot be read, or when it does not show the prompt, the grant is
spent unused, the call is blocked with that reason, and the request is filed again. A
harness that gives no transcript cannot carry approved sends or deploys until it does.

### The layers, and what each stops

1. **The transcript check where the grant is spent** stops a grant the agent made by
   feeding the prompt hook a made-up prompt or by writing the grant file, and stops
   tool output, hook text or another session's message that carries the code.
2. **The shell guard** refuses a command that carries a pending code (for example
   `codex queue <thread> "approve <code>"`, or `claude -p --resume <id>` with it), that
   runs the stable hook or `synthesis/hook.py` for any event, or that writes into the v5
   state folder, a harness's transcript folder or the approved commit lines (by path, or
   by the store's file name from inside its folder): redirects, the destination of `cp`,
   `mv`, `ln`, `install` and `rsync`, `tee`, `touch`, `truncate`, `mkdir`, `rm`,
   `unlink`, `chmod`, `sed -i` and `perl -i`, and interpreter scripts given inline or on
   stdin that write there.
   Reading a transcript, and working on the hook's source, stay allowed.
3. **No hook text holds the phrase** (see What the hook returns).
4. **Random codes** mean a code cannot be planted before its request exists, and a
   later identical call never reuses the code an earlier approval answered.

### What remains open

No local file is secret from an agent running as the person's own OS user, so these
stay open, and no hook running as that same user can close them:

- An agent that deliberately forges its harness's transcript, writing a line shaped
  like the person's prompt, defeats the transcript check. The shell guard refuses the
  natural routes; a command that builds the path or the code at run time (a variable,
  an encoding, a script file written first), a file-edit tool (edits are not guarded,
  for latency), or a program the agent writes and runs gets through.
- A prompt another process injects into the session through the harness's own CLI
  (`claude -p --resume`, `codex queue`, `muse session-message`) is recorded as a typed
  prompt. The shell guard refuses such a command when it carries a pending code; one
  that builds the code at run time is not caught.
- A grant written with a file-edit tool can reuse a code the person typed for the
  identical call within the last 15 minutes: a second, identical send or deploy.
- The approved commit lines are a file the agent can edit with a file-edit tool, or
  change through git when the store lives in a synced repository (a pull, a checkout).
  A fingerprint added that way passes its line without the person. It holds hashes, so
  the agent would have to compute the hash of the exact line, path and repository.
- The agent can rewrite the runtime under `~/.synthesis/v5` or its config.

Closing these needs isolation the hooks do not have: the agent under its own OS user
or sandbox, or approvals signed by something outside the agent's reach.

### When the harness then refuses the call

The grant is spent at PreToolUse, before the harness's own permission prompt or MCP
approval policy. If the harness or the person then declines the call, the approval is
gone, and the next identical call asks again (M5 finding 4: Codex with
`approval_policy = never`). Single use is kept because it fails safe.

## Compaction

The SessionStart output is the project brief: local time, the active project's
`PRIME-DIRECTIVE.md` and current-state block, the session's autopilot run, one
ritual line, and the unread-message count. Re-injecting it after compaction is
what lets a long session keep its directive. Claude Code and Codex rerun
SessionStart after compacting (M5: Claude Code's `/compact`, Codex's automatic
compaction). An adapter for a harness that does not must say so; a session there
recovers with `synthesis brief`.

A session that chooses its project after it started (`synthesis use`) gets the brief
at its next prompt, once, in every harness: UserPromptSubmit briefs a session whose
project differs from the one it was last briefed on. `synthesis resume` prints the
brief itself, so it counts as briefed.

## Muse

What the M5 sandbox showed for Muse 1.4.3, and what it could not test:

- **SessionStart runs only when a session is created**, not when `muse exec
  --session-id <id>` continues it: across seven continued turns in two sessions it
  ran once per new session. A new session has no project until `synthesis use` runs
  inside it, so the SessionStart brief carries none; the brief arrives at the next
  prompt instead (above). A continued session after a long gap gets no fresh local
  time or ritual line until the next session.
- **PreToolUse runs for every tool**, because Muse has no matcher; an unguarded call
  costs about 29 ms.
- **The approval check** reads Muse's session log. Whether Muse's hook payload names
  it in `transcript_path` was not observed; without it the hook finds the log by the
  session id. The guard ran through Muse's own hook runner, not from a model's tool
  call, because the offline provider cannot call tools.
- **Not tested:** Muse compaction (the offline provider cannot compact, so whether
  Muse reruns SessionStart after compacting is unknown), resume from Muse's TUI (it
  needs a terminal that answers cursor queries), and `muse session-message`.



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
3. the payload fields above, or a translation from the harness's own, including a
   transcript in which the person's own prompts can be told apart from tool output,
   hook text and other sessions' messages, read in `synthesis/approvals.py`; without
   it the harness cannot carry approved sends or deploys;
4. its transcript folder and a session-id and harness variable in `synthesis/paths.py`;
5. a `synthesis doctor` check that reads the harness's installed plugin through
   its own read-only listing command and confirms the hooks are wired;
6. tests for each of these, and a stated list of what the harness cannot do.

A harness is supported once these are merged and a fresh session in it shows
the SessionStart brief. The
[conformance audit](../skills/synthesis-agent-conformance/references/audit.md)
describes the live checks.
