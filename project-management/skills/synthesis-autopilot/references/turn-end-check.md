# The turn-end check and the helper commands

The plugin's Stop hook runs `synthesis/autopilot.py` at every turn end (R6.4).
It acts only for the session that owns a running plan, and asks for one of
three things: continue the next open checklist item, record a blocker and alert
the principal, or close honestly. This page says exactly when it asks, what
bounds it, and how to run each helper.

## Contents

- [When it asks](#when-it-asks): the decision for each `Status:`
- [What bounds it](#what-bounds-it): three in a row, fail open, under 50 ms
- [Per-harness Stop facts](#per-harness-stop-facts)
- [Helper commands](#helper-commands): engage, status, cycle, close, alert, wake-prompt, takeover
- [How it differs from the 2.4.0 gate](#how-it-differs-from-the-240-gate)

## When it asks

The check reads one small pointer file the `engage` helper wrote for this session
(`~/.synthesis/v5/state/autopilot/<session>.json`), then that plan. It does
nothing when there is no pointer, when the plan's `Owner session:` is another
session, or when it cannot read either.

| Plan status | The turn may end when | Otherwise the check asks |
|---|---|---|
| `running` | A background task the harness reports (`background_tasks`) will wake the session | "Continue with the next one now: <first open item> (N more open after it)", with how to block or wait honestly. If every item is checked: verify and close. On an overnight or longer horizon it also names a missing continuation or backstop |
| `waiting` | `Waiting on:` names the event, and a continuation will wake the session: `session_crons` or `background_tasks` in the payload, or a `Continuation:` with an observed `First wake:` or still inside 60 minutes of `Engaged:`; plus a backstop with `stop:` for overnight or longer | Names what is missing, or says to set `Status: running` and do the work that does not depend on the wait |
| `blocked` | Every open blocker carries `alerted`, and any blocker claiming a missing capability carries `probe:` | Names each blocker with no alert or no probe |
| `paused` | Always (the principal asked to pause) | Nothing |
| `done`, `incomplete`, `cancelled` | The close is honest (see [plan-file.md](plan-file.md#status-values)) | Lists what stands between the plan and that close, or says to close as incomplete with the reason |

The request is written as a short user message naming the open work, because a
model that ends a turn with a summary responds best to being told exactly what
remains and that a real blocker is an acceptable answer.

## What bounds it

- **At most three continuations in a row per plan.** A stop that arrives with
  the harness's repeat flag (`stop_hook_active`), or with the plan byte-for-byte
  unchanged since the last request, counts as a repeat. After three, the check
  lets the session stop and offers a one-time note for the person ("Autopilot
  asked this session to continue <plan> 3 times in a row, so it is letting the
  session stop. Review the plan: <path>"); `evaluate()` returns that note so the
  hook can show it as a
  user-visible message. A stop with no repeat flag and a changed plan starts the
  count again. The limit is `autopilot.max_continuations` in the v5 config.
- **Fails open.** Any error, unreadable pointer or plan, or unknown client ends
  the turn with no request. A turn-end check that fails closed asks for another
  turn forever; that is how the Stop loops of 2026-09-17 and 2026-09-23 happened.
- **Fast and local.** One pointer read and one plan read; no network, no
  transcript parsing, no scan of other sessions or old engagement records. The
  tests hold it under 50 ms in process and inside the hook budget as a cold
  process. The only state it writes is its own fixed-size pointer file.
- **Never a grant.** Nothing in a plan file grants permission. Sends and deploys
  still need the principal's typed approval (R3.0 to R3.2).

## Per-harness Stop facts

- All three harnesses continue a turn when a Stop hook prints
  `{"decision": "block", "reason": ...}`; Codex turns the reason into a new user
  prompt. All three send `stop_hook_active` and `last_assistant_message`.
- Claude Code also sends `background_tasks` and `session_crons`, and caps
  Stop-hook continuations at eight on its own (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`).
  Muse caps them at eight (`max_consecutive_stop_hook_continuations`). Codex
  states no cap. The check's limit of three sits under all of them.
- `systemMessage` in a hook's JSON reaches the person, not the model, in all
  three (Muse limits it to 1,000 characters): the place for the cap note.
- Muse may send `transcript_path` as null and runs hooks with no session id in
  the environment; the check uses the payload's `session_id`.

## Helper commands

`AP="$HOME/.synthesis/v5/current/skills/synthesis-autopilot/scripts/autopilot_cli.py"`
(this skill's `scripts/autopilot_cli.py` as the install copies it into the runtime;
the turn-end check stays in the core, `synthesis/autopilot.py`). Each helper takes
`--session <id>` before the command name when the shell does not carry the
harness's id (Claude Code shells carry
`$CLAUDE_CODE_SESSION_ID`, Codex `$CODEX_THREAD_ID`). Output below is real,
with the plan path shortened to `<plan>` and the close refusal's list cut after
its first standing item.

**Engage** a plan (writes Owner session, Status, Engaged and missing standing
items; claims the plan on the board; turns the check on for this session):

```text
$ python3 -S "$AP" engage --plan <plan>
engaged: <plan>
owner session: demo-1  status: running  horizon: sitting
next item: 1. Migrate /orders and its tests
```

On an overnight or longer horizon it adds a `before this turn ends: ...` line for
each missing continuation or backstop. A refusal exits 1 and lists every problem.

**Status** of this session's run, or of every engaged run on this Mac with
`--all` (the view to use when a harness pane is blank):

```text
$ python3 -S "$AP" status
<plan>
  status: running  owner: demo-1 (this session)  plan edited 0 min ago
  next: 1. Migrate /orders and its tests  (2 of 2 items open)
  continuation: none: this sitting only
  first wake: not yet
  backstop: none (horizon is this sitting)
```

Open blockers print as `blocker: ...` and open questions for the principal as
`question: ...`. `status --json` prints the same runs as a JSON list (plan, status,
owner, this_session, edited_min, next, open, total, waiting_on, continuation,
first_wake, backstop, blockers, questions) for tools such as the Console.

**Cycle**, once per wake; a bare spin is refused:

```text
$ python3 -S "$AP" cycle --plan <plan> --advanced "migrated /orders; 12 tests pass"
cycle recorded (1 in the ledger)
$ python3 -S "$AP" cycle --plan <plan>
refused: a cycle that advanced nothing must name the external wait it is on (--waiting-on). There is no way to record a bare spin: if nothing advanced and nothing external is awaited, the run is spinning, so record a blocker and alert, or close.
```

**Close** with `--done`, `--incomplete "<reason>"` or `--cancelled "<reason>"`.
It refuses (exit 1, plan unchanged) with every problem listed, then on success
writes the status, releases the plan's claim and turns the check off:

```text
$ python3 -S "$AP" close --plan <plan> --done
refused: <plan> cannot close as done:
- criterion not met: Endpoint tests pass
- 2 checklist item(s) still open, first: 1. Migrate /orders and its tests
- standing item end-to-end has no disposition (evidence, or WAIVED: reason)
Closing as incomplete with the reason stays available.
$ python3 -S "$AP" close --plan <plan> --incomplete "v1 route still has callers"
closed as incomplete: <plan>
next: send the completion alert and the completion report
```

**Alert** the principal with `--kind blocked|done|budget` and `--count N`. The
banner and spoken text carry only the count and a pointer ("Autopilot run is
blocked: 2 question(s) need you. Run autopilot status for details."). The audio
is suppressed while the mute flag exists (`~/.synthesis/quiet-audio`, or
`autopilot.mute_flag` in config). It prints one outcome per channel and the note
to copy onto the blocker; it exits 1 when nothing was posted or played:

```text
$ python3 -S "$AP" alert --kind blocked --count 2
banner: posted
audio: suppressed (mute flag)
record on the blocker or close line: alerted 2026-10-05T22:12-04:00 (banner posted; audio suppressed (mute flag))
```

A posted banner is not proof the person saw it, and a suppressed alert is not a
delivered one; the written report in the plan is always required.

**Wake prompt**, the one text every scheduler and loop uses:

```text
$ python3 -S "$AP" wake-prompt --plan <plan>
Autopilot wake for the plan at <plan>. Read that plan before anything else. If its Status is done, incomplete or cancelled, do no work: delete this scheduled job, read the deletion back, and stop. If another session owns it, run `autopilot_cli.py status --all`; take it over only when the plan has been silent longer than its Silent after: line allows, otherwise message the owner and stop. Otherwise verify the plan's state against git and the files on disk, record this wake in the cycle ledger, and continue the next open checklist item.
```

**Takeover** of a plan whose owner has gone silent past `Silent after:`:

```text
$ python3 -S "$AP" takeover --plan <plan>
refused: owner demo-1 was active 0 min ago (limit 480 min); message it with `synthesis msg demo-1 ...` instead
```

On success it prints `took over: <plan>` and the next item, and the old owner
finds a board notice at its next prompt.

**For the hook author:** `check(payload, config) -> str | None` has the same
contract as `reply_check.check`; `evaluate(payload, config)` returns
`(reason, note)` so the hook can also print the cap note as `systemMessage`; and
`brief(payload) -> str` is a one-paragraph reminder of the owned run for the
session-start hook, including after compaction.

## How it differs from the 2.4.0 gate

The 2.4.0 gate (`autopilot_gate.py`) did the same job from a registry of
engagement records outside the project. v5 keeps its rules and moves its state
into the plan file:

- The record is the plan file in the project; the pointer only says which plan
  a session engaged, and deleting it only turns the check off.
- An unreadable record now fails open instead of closed: 2.4.0 blocked every
  Stop on an unreadable record, which is the shape of the later Stop loops.
- Another session's plan never blocks this one, and nothing scans other
  sessions' records (F8).
- A blocker is a way to stop only while `Status: blocked`; recording progress
  does not clear it, and a done close refuses while it is open (F2).
- Close reads the plan's current standing checklist, so an item added mid-run
  needs a disposition (F1); a missing plan or one with no completion criteria
  cannot close as done (F5); only the `Required evidence` section creates
  citation obligations, and a scratch path there refuses a done close (F7).
- One plan has one owner holding the board claim; a second writer is refused at
  engage, at cycle and close, and by the commit check (F3, F4).
