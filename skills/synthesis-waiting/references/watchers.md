# Watchers, harness by harness

What can wake a session differs by harness, and a watcher that cannot wake the seat is no watcher. Each line below
says how it was learned and when. Where a capability was not shown, the table says "not shown" with the probe, never
"missing": probe again before relying on either answer.

## What wakes a session

| Harness | What wakes an idle session | How it was learned |
|---|---|---|
| Claude Code | A background shell task that exits wakes the session once. | Used through a day of reviews, test runs and replays, 2026-11-11. |
| Claude Code | An event stream the harness holds (its monitor tool) for a bounded time, re-armed after that. | The tool's own description, 2026-11-11. |
| Claude Code | A scheduled prompt (a timer or a cron job of the harness). Each firing is a model turn. | Read in a session's transcript: the turn is recorded as scheduled, not typed. |
| Claude Code desktop | A turn delivered by another session of the same app. | The tool's own description, 2026-11-11. |
| Codex | `codex queue --thread <id> --message <text>` stores a message for an existing session. An ended non-interactive session did not take it, and resuming one from the queue needs a local daemon. A live desktop thread: not shown. | Run against a throwaway session, codex-cli 0.167.0-alpha.4.1, 2026-11-11. |
| Codex | Its own finished background command: not shown. | Not probed. |
| Muse | `muse session-message` sends to a live session; `muse sessions` lists them. With no live session there was nothing to send to. | `muse sessions` printed an empty list, 2026-11-11. |

A turn that arrives by any of these routes is recorded as what it is. None counts as the principal's typed prompt,
so none can grant an approval: the approval check reads only prompts the person typed.

In Claude Code the turn-end check reads the first two rows from the session's own transcript: a background agent,
shell task, workflow or monitor the session started, with no task notification for it yet, is a wait the harness
holds, and a reply that announces a wait beside it passes without a `synthesis wait`. In thirty days of recorded
turn ends, five of every six replies that announced a wait were of this kind (the agent-guardrails reference has the
count). A timer and a turn from another session are not read: record those with `synthesis wait note`.

## Which watcher

| Awaited | Claude Code | Codex | Muse |
|---|---|---|---|
| One event: a message, a file, a check | `synthesis wait …` as a background shell task. It costs nothing while it polls and wakes the session when it exits. | `synthesis wait …` in the foreground, up to the tool's time limit, and say that the seat is held for that long; for longer, a wait the person or a peer ends with `synthesis msg --wake`. | The same as Codex until a wake of its own is shown. |
| Several events, their number unknown | The harness's event stream over `synthesis wait run`, bounded and re-armed, with `synthesis wait note` so the board shows it. | Not shown. | Not shown. |
| A clock time | The harness's timer, with `synthesis wait note`. Each firing is a model turn: say so, and prefer one long timer to many short ones. | Not shown. | Its scheduling tools; not probed. |
| Waking an idle peer | The app's own session-to-session message. `synthesis msg --wake` has no command for it and says so. | `synthesis msg --wake`, which runs `codex queue`. | `synthesis msg --wake`, which runs `muse session-message`. |

## What a watcher costs

- A shell command that polls (`synthesis wait message`, `file`, `run`) uses no model turn until it ends. Its cost is
  the process, and the one turn that reads what it found.
- A timer that prompts the model costs a full turn each time it fires, with the session's whole context. Sixty
  one-minute checks cost sixty turns; one `synthesis wait run --every 60s --for 1h` costs one.
- An event stream costs a turn for each event it delivers. Filter at the source so it delivers the event awaited
  and nothing else.
- `--wake` spends a turn of another session. Use it for something that needs action now.

Where a shell watcher fits, use it without asking. Where only a model-driven watcher fits and the wait is long or
its worth unclear, ask the principal once, with the recommendation first and the cost in turns.

## What `wait run` does with the command's processes

Each try of `synthesis wait run` runs in a process group of its own, with no controlling terminal: a command that
would ask for a password there fails instead of asking.

- A try that exits 0 in time ends the wait. What it started is left running.
- When a try fails, or is still running at the bound, its whole group is stopped, the command and every process
  it started there: each is asked to end (SIGTERM), and what is still there two seconds later is killed. So a
  wait may return up to two seconds after its bound, and a helper that later tries need is started before the
  wait, not inside the check.
- A process that moved itself to another process group or session, as a daemon does, has left the try and is not
  stopped.
- A wait that is told to end (SIGTERM, a closed terminal, Ctrl-C) stops the try it is running first. One that is
  killed outright (SIGKILL) cannot: its try runs on until the command ends.

## When a wake did not arrive

1. `synthesis wait list`: is the wait still on the board? A wait whose process died or whose bound passed is gone.
2. `synthesis inbox --peek`: did the mail arrive unseen? A session bound to no project receives nothing addressed
   to a project; `synthesis who` shows the binding, and `synthesis resume <project>` restores it. A seat that holds
   a live wait is listed there for the wait's whole bound, marked `waiting until HH:MM`. Once it has been quiet
   for eight hours its row also says `STALE`: its claims go stale as any seat's do, while mail still reaches it.
3. Was the message sent to this session? The sender's `synthesis msg` ended with what would deliver it.
4. Did the watcher end at its bound (exit 3)? Then nothing arrived in time, and the next step is a decision, not a
   longer silence. What came after the bound is still there to find: mail stays unread until `synthesis inbox`
   reads it, and a file that turned up late is in place, so a new `wait file` waits for its next change.
