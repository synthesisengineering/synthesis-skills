# Unattended continuation

How a run keeps producing turns when nobody is typing, in Claude Code, Codex
and Muse, and how its backstop stays visible and stoppable (R6.2). The
per-harness facts come from the 2026-10-05 harness report (Claude Code 2.1.288,
Codex CLI 0.160.0 and desktop 26.930, Muse 1.4.3). Re-check them when a harness
updates: a capability is what a probe shows today, not what this page remembers.
`$AP` below is `$HOME/.synthesis/v5/current/synthesis/autopilot.py`, the helper
described in [turn-end-check.md](turn-end-check.md#helper-commands).

## Contents

- [The rule](#the-rule)
- [Mechanisms by what they survive](#mechanisms-by-what-they-survive)
- [Claude Code](#claude-code), [Codex](#codex), [Muse](#muse)
- [A launchd backstop for any harness](#a-launchd-backstop-for-any-harness)
- [The backstop is visible and stoppable](#the-backstop-is-visible-and-stoppable)
- [A continuation is observed, not assumed](#a-continuation-is-observed-not-assumed)
- [Re-entry protocol](#re-entry-protocol)
- [Budget and runaway control](#budget-and-runaway-control)
- [Capability probe, volatile state, compaction](#capability-probe-volatile-state-compaction)

## The rule

The costliest way this mode fails is silently, at a turn boundary. The real
incident that forced this section: a principal delegated an overnight run and
went to sleep; the agent engaged the mode correctly, wrote the plan file, ran
two phases, and then its turn ended. **Agent harnesses do not run between
turns.** The session sat idle all night — the machine rebooted mid-night
without interrupting anything, because nothing was executing — and the phase
that was the entire point never started. Every discipline in this file held;
the work still did not happen, because the contract said "complete the work
end to end" and nothing caused the next turn to exist.

**The rule: an engagement whose horizon extends beyond the current turn MUST
establish a verified continuation mechanism before its first turn ends — or
must say plainly, at engagement, that it cannot run unattended in this
environment and negotiate what happens instead.** Claiming overnight autonomy
without a continuation mechanism is a false capability claim, and the silence
it produces is indistinguishable from progress until the principal wakes up.

Current models make the same failure more often in small form: a long turn ends
with a progress summary that announces the next step instead of taking it.
Treat a text-only end of turn as a report, not as proof the task is done. The
turn-end check ([turn-end-check.md](turn-end-check.md)) turns such a stop into a
request for the next open item, at most three times in a row.

## Mechanisms by what they survive

**Continuation mechanisms, by what they survive.** Verify what the current
harness actually provides — do not assume from memory (see the capability
probe rule below). The common classes:

| Mechanism | Survives turn end | Survives session death | Survives reboot |
|---|---|---|---|
| In-flight background work whose completion re-invokes the session (dispatched agents, detached exec with a completion waiter, workflows) | yes | no | no |
| Self-scheduled wakeup / dynamic loop (the harness re-invokes the session with a prompt on a cadence it sets) | yes | no | no |
| Scheduled task / cron re-entry (a scheduler starts a fresh run that resumes from the plan file) | yes | yes | usually |
| Principal-side relaunch instruction (documented command the principal or their machine runs) | yes | yes | yes |

**Match the mechanism to the horizon, and layer for long ones.** A run
measured in hours inside one sitting can ride background work and wakeups. A
run measured across sleep, reboots, or days needs a scheduler-class re-entry
as the dead-man's switch underneath whatever finer mechanism drives the
inner loop — the plan file is the state that makes any fresh re-entry able
to resume. When no mechanism exists at all, the honest engagement response
is: "I can only make progress while turns are running; here is the relaunch
command / loop invocation that would change that."

In the plan: the finer mechanism goes on `Continuation:`, the scheduler-class
re-entry on `Backstop:` (with `stop: <how>`). `Horizon: overnight` or `days`
makes the backstop required.

## Claude Code

| Mechanism | Survives | Create; list; stop | Seen by the turn-end check |
|---|---|---|---|
| Background work: `Bash` with `run_in_background`, `Monitor`, sub-agents | Turn end; completion re-invokes the session. Unattended background Bash runs 30 minutes by default, 2 hours at most; Monitor watches 5 to 30 minutes | The tool call itself; the harness's task list; stop the task | Yes: `background_tasks` in the Stop payload lets the turn end |
| Self-paced wakeup (`/loop` without an interval; `ScheduleWakeup`) | Turn end only. Wakes between 1 minute and 1 hour; not restored by `--resume` | `/loop`; the session's own schedule; cancel the loop | Through `session_crons` when the loop is cron-backed |
| Session cron (`/loop <interval>`: `CronCreate`, `CronList`, `CronDelete`) | Turn end while the session stays open and idle. 1-minute minimum, 50 per session, recurring jobs expire after 7 days, missed fires are not caught up | `CronCreate`; `CronList`; `CronDelete`, then `CronList` to read the deletion back | Yes: `session_crons` |
| Desktop scheduled task (the desktop app; tools `create_scheduled_task`, `list_scheduled_tasks`, `list_task_runs`, `delete_scheduled_task` where the app exposes them) | Session death and app restart, while the app is open and the machine awake; one catch-up run on wake. Each run starts a **fresh session** | Create with the wake prompt; see it in the app's Scheduled list (stored as `~/.claude/scheduled-tasks/<task>/SKILL.md`); delete there or with the tool, then list to read back | No; record it on `Backstop:` |
| Headless resume from launchd: `claude -p --resume <session id> "<wake prompt>"` | Reboot, when run by a launch agent; same session id, so the same owner | See [launchd](#a-launchd-backstop-for-any-harness) | No; record it on `Backstop:` |

The desktop scheduled task is Claude Code's backstop for overnight and longer
runs. Because each run is a fresh session, set `Silent after:` to about twice its
interval so a run can [take over](plan-file.md#ownership-and-takeover) a plan
whose owner died, and record its first run with `list_task_runs`. Cloud routines
(`/schedule`) are not a backstop for local work: they start a fresh cloud session
without the local files, user skills or plugins, at a one-hour minimum. `/goal`
is the principal's own command (it keeps starting turns until a model judges the
goal met, with at most three idle check-ins between prompts); the agent cannot
type it, but may suggest it. Claude Code caps Stop-hook continuations at eight
in a row by itself (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`); the autopilot check stops
asking after three.

## Codex

| Mechanism | Survives | Create; list; stop | Seen by the turn-end check |
|---|---|---|---|
| Stop-hook continuation (the autopilot check) | Turn end in a running CLI or app session. Codex states no cap; the check's own limit of three applies | Automatic; `decision: block` turns the reason into a new user prompt | Itself |
| Desktop scheduled task (formerly automations; minute, daily, weekly or RRULE recurrence) | Session death; can target the existing thread, so the wake keeps the thread's context and session id. Needs the computer on and the app running | Create, pause and delete in the app's scheduled list (or the app's scheduling tool where the agent has one). Never edit `~/.codex/automations/*/automation.toml` by hand: the format is undocumented | No; record it on `Backstop:` (or `Continuation:` for an in-sitting cadence) |
| `/goal` (CLI, app, IDE) | Continues when the thread is idle; stops on errors, repeated empty output or usage limits | The principal sets it; `/goal` pause, resume, clear | No |
| Background terminals (`/ps`, `/stop`) | Turn end; `background_terminal_max_timeout` defaults to 5 minutes | `/ps`; `/stop` | No |
| Headless resume from launchd: `codex exec resume <session id> "<wake prompt>"` | Reboot, when run by a launch agent | See [launchd](#a-launchd-backstop-for-any-harness) | No |

The Codex CLI and IDE extension have no scheduler of their own; a CLI-only run
that must outlive the session uses the launchd backstop. The Stop payload has
`stop_hook_active` and `last_assistant_message` but no task or cron lists, so a
waiting Codex run records its continuation and first wake on the plan.

## Muse

| Mechanism | Survives | Create; list; stop | Seen by the turn-end check |
|---|---|---|---|
| `/loop` (`cron_create`, `cron_list`, `cron_delete`) | Turn end while Muse is running. A fire during an active run is skipped; jitter up to 30 minutes; at most one catch-up after resume. Expiry is unresolved (docs say 7 days; the 1.4 binary marks loop jobs permanent), so always delete at close | `cron_create`; `cron_list`; `cron_delete`, then `cron_list` to read back | No; record it on `Continuation:` |
| `/goal` (`create_goal`, `update_goal`, `report_progress`) | Queues follow-ups until the goal is met; Esc pauses | The goal tools; `/goal` | No |
| `monitor` tool | Wakes the session when a watched command prints a line (default wake delay 120 seconds) | The tool; `work_status`; `work_stop` | No |
| Stop-hook continuation (the autopilot check) | Turn end; Muse caps it at eight (`max_consecutive_stop_hook_continuations`) | Automatic | Itself |
| Headless continuation from launchd: `muse exec --session-id <id> --prompt-file <wake prompt file>` | Reboot, when run by a launch agent | See [launchd](#a-launchd-backstop-for-any-harness) | No |

No out-of-session scheduler is documented for Muse: every Muse schedule needs a
running Muse process. For an overnight or longer horizon, either add the launchd
backstop, or keep Muse open with `/loop` and the machine awake (`caffeinate`)
and say plainly at engagement that the run stops if Muse exits. Muse runs hooks
in a cleared environment with no session id in it, and whether its shells carry
`MUSE_SESSION_ID` is unconfirmed: if `engage` reports no session id, pass
`--session <id>` with the id of the session folder Muse shows for this session.

## A launchd backstop for any harness

A launch agent re-entering through the harness's headless resume survives app
exit, logout and reboot. It is a standing change to the principal's machine, so
it needs the principal's approval before it is created; a native scheduled task
inside the harness app is the default. The headless run uses the permission mode
the principal already approved for this work: never add a permission-bypass flag
the principal has not set.

- **Create:** a plist at `~/Library/LaunchAgents/org.synthesis.autopilot.<slug>.plist`
  with `Label` `org.synthesis.autopilot.<slug>`, `StartInterval` in seconds, and
  `ProgramArguments` running the harness's headless resume command (above) with
  the wake prompt; load it with `launchctl bootstrap gui/$(id -u) <plist>`.
- **See it:** `launchctl list | grep org.synthesis.autopilot`.
- **Stop it:** `launchctl bootout gui/$(id -u)/org.synthesis.autopilot.<slug>`, then
  delete the plist. Read the deletion back with
  `launchctl print gui/$(id -u)/org.synthesis.autopilot.<slug>`, which then reports
  that the service cannot be found.

## The backstop is visible and stoppable

**Long runs schedule a backstop cron.** Any engagement whose horizon
extends beyond the current sitting registers a scheduler-class
backstop at engagement — a cron or scheduled task that re-invokes the
run from the plan file if the inner continuation ever goes silent —
and deletes it at close. The backstop is the dead-man's switch under
whatever finer mechanism drives the loop; a run that ends with its
backstop still scheduled pages a principal who already got the report.

- **Visible.** The plan's `Backstop:` line names the job and says
  `stop: <how>`. `python3 -S "$AP" status --all` lists every engaged run on this
  Mac with its continuation, first wake and backstop lines, and its open
  blockers and questions.
- **Stoppable without touching a scheduler.** Setting the plan's status to
  `cancelled — <reason>` stops the run: every scheduled wake reads the plan first
  and does no work on a closed plan. The `stop:` instruction then removes the job.
- **Every wake uses the same prompt.** `python3 -S "$AP" wake-prompt --plan <path>`
  prints it. Give that exact text to every scheduler and loop.
- **Closing deletes every job and reads the deletion back.** A requested
  deletion is not a deletion: list the jobs again (`CronList`,
  `list_scheduled_tasks`, `cron_list`, the app's list, `launchctl print`) and
  write `deleted <time>` on the `Continuation:` and `Backstop:` lines. `close`
  refuses until both say so (or `none`). A wake that still fires late reads the
  closed plan, deletes its job and stops.

## A continuation is observed, not assumed

A saved run, recoverable context, a scheduled job and an observed wake establish
different facts. Native registration or listing proves a job exists, not that it
will execute; a file containing a job ID is insufficient. On the first wake a
job delivers, write `First wake: <time>` on the plan (for a Claude desktop task,
`list_task_runs` shows the run). Until then a scheduled continuation counts for
60 minutes after `Engaged:`; past that, a waiting plan whose continuation never
fired is treated as having none, and the check says so. A stopped worker cannot
independently notice its own silence, which is why the backstop sits outside
the session. Never invent another scheduler to bypass host limits.

In Claude Code the Stop payload's `session_crons` and `background_tasks` are the
harness's own evidence; the check accepts them for surviving turn end, and
still asks for a backstop when the horizon is overnight or longer.

## Re-entry protocol

**Re-entry protocol.** Every wake — wakeup, completion notification,
scheduled re-entry, or a fresh session resuming — starts the same way: read
the plan file first (it is the loop variable), read the coordination board,
verify the plan's claimed state against ground truth (git, artifacts on
disk — not memory), then continue the next unmet goal. Record every wake in
the plan's cycle ledger.

In v5 terms: read the plan; if it is closed, delete this job and stop; run
`synthesis inbox` and `synthesis who`; if another session owns the plan, take it
over only past its `Silent after:` limit, otherwise message the owner and stop;
check git and the files the plan cites; `cycle --advanced` or `--waiting-on`;
then the next open item.

## Budget and runaway control

**Budget and runaway control.** The twin fear of the silent stop is the
loop that burns the principal's usage limits without value. The plan file
declares the budget up front: horizon, maximum cycles or wall-clock, and
the per-cycle value test. Each cycle records what it advanced; a cycle that
advanced nothing must name the external event it is waiting on, and waits
use coarse cadences (do not poll for what a completion notification will
deliver). Stop conditions are exactly: goals met · blocker recorded and
principal alerted · budget exhausted and principal alerted. "Still running"
is never itself evidence of value.

`cycle --plan <path> --advanced "<what>"` or `--waiting-on "<event>"` appends the
ledger line; with neither it refuses, so a bare spin cannot be logged. The
turn-end check adds its own bound: it asks at most three times in a row while
the plan does not change.

## Capability probe, volatile state, compaction

**Capability probe before asserting absence.** An agent that wrongly
believes it is blocked stops. In the motivating incident's aftermath, a
session confidently reported that the counterpart CLI could not be reached
unattended — stale knowledge stated as fact; the CLI had a working headless
mode the same session had already used. Before any blocker or plan step
claims a capability is absent ("X cannot run autonomously", "no way to
reach Y"), run the probe — locate the binary, invoke the minimal command,
read the tool schema — and record the probe's evidence with the claim.
Zero results from memory are not evidence of absence.

**Volatile state dies at reboots.** Scratchpad and temp directories are
cleared by reboots and session ends — and long-horizon runs are exactly the
runs that meet reboots. Anything a later phase, another agent, or a durable
record depends on moves into the project (resources/) **at every phase
boundary**, not only at close. Losing derived findings to a reboot mid-run
means regenerating them on the next wake — paid for twice.

**Compaction.** When context runs low with items left, keep working: the plan
file and the session-start re-injection exist so a run continues through
compaction. Stopping to suggest a fresh session is the context-budget excuse.
Keep CONTEXT.md's current-state block naming the plan and its next item, and
re-read the plan first after any compaction.
