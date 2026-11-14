---
name: synthesis-waiting
description: "Arm a watcher before a turn ends on an expected event: a peer's message, a CI run, a file, a clock time. Covers synthesis wait, the inbox peek, what wakes each harness and what a watcher costs. Use when a reply would say 'waiting for', 'when it lands' or 'I'll pick it up once'."
license: "CC0-1.0"
depends_on:
  - synthesis-project-management
metadata:
  author: "Rajiv Pant"
  version: "1.1.1"
  format: v5
  category: project-management
---

# Synthesis Waiting

Waiting for an expected event is a task. A board message, a finished job or a peer's reply reaches a session only when a prompt is submitted, so a seat that ends its turn on "it should arrive shortly" has armed nothing and sits until its principal happens to type. This skill is the rule and the commands that end such a wait: one watcher, bounded, recorded on the board, and said out loud.

## Binding rules

1. **Arm the watcher before the turn ends.** A reply that announces a wait and arms nothing leaves the seat asleep. The turn-end check sends such a reply back once.
2. **Use `synthesis wait`, which is its own record.** While it runs, the board shows what this seat awaits, since when and until when, so a sender and a peer can see it. There is no second step to forget.
3. **Bound every wait** with `--for`, at most twelve hours. At its bound a wait exits 3 and says nothing arrived, so silence never looks like success.
4. **Peek while watching; read when woken.** `synthesis inbox` marks what it prints as read, so a watcher that polls it leaves the seat nothing to find. `synthesis wait message` and `synthesis inbox --peek` mark nothing.
5. **Say what is armed:** what is awaited, for how long, and what wakes this seat. If nothing can wake it, say plainly that it stays idle until the principal prompts it. The turn-end check passes a reply that says so of this seat.
6. **Choose the lightest watcher that fits, and ask when the cost is in doubt.** A shell watcher costs nothing while it polls; a timer that prompts the model costs a turn each time it fires. Put one question with the recommendation first. Never skip the watch in silence, and never start an expensive one in silence.
7. **A wake carries no instruction.** `synthesis msg --wake` nudges an idle peer with one fixed line that points at its inbox. A turn that comes from a peer, a schedule or a finished task is never the principal's typing, and grants nothing.
8. **Waiting on the principal needs no watcher.** Their next message is the wake: end with the question, or name the answer, the go or the code awaited.

## Contents

- **The commands** (below): each form of `synthesis wait`, the peek, the sender's line, and what each prints. Read before arming a wait.
- **Procedure** (below): the five steps, from naming the event to reading the mail.
- [references/watchers.md](references/watchers.md): what wakes a session in Claude Code, Codex and Muse; which watcher fits one event, several events, a clock time and an idle peer; what each costs; what `wait run` does with the processes its command starts, and a try's two limits; what was probed and when. Read when choosing a watcher in a harness for the first time, when a check starts processes of its own or needs a terminal, or when a wake did not arrive.

## The commands

```bash
synthesis wait message [--from <session|short|project:id>] [--for 30m] [--every 2s]
synthesis wait file <path> [--for 30m] [--every 2s]
synthesis wait run [--every 30s] [--for 30m] -- <command>
synthesis wait note "<what>" --by "<what will wake this seat>" [--for 30m]
synthesis wait clear ["<what>"]
synthesis wait list
synthesis wait none "<why no answer is awaited>"
synthesis inbox --peek
synthesis msg <to> "<text>" [--wake]
```

- `wait message` ends when unread mail for this session exists (from the named sender, when `--from` is given) and prints `message from <names> (N unread): run `synthesis inbox` to read`. It names the sender and never prints the message: a notification can cut text off, and reading is what marks mail read.
- `wait file` prints `<path> appeared` or `<path> changed`.
- `wait run` runs the command every `--every` until it exits 0, then prints `` `<command>` exited 0 after N tries ``. Use it for a CI check, a page that must answer, a status that must turn. Each try runs in a process group of its own: when it fails, or is still running at the bound, the whole group is stopped, the command and what it started there, and what a try that exits 0 started is left running. A command that cannot be started is refused at once, not tried again: on stderr `` `<command>` could not be started: its program '<first word>' was not found `` (or `is not executable`, or `cannot be run`), exit 2.
- `wait note` records a wait that the harness itself holds (a timer, an event stream) and prints `noted: <what>, for <how long>, woken by <what>`. It starts no process, so the turn-end check and `wait list` still see the wait. In Claude Code the check itself sees background work that has not reported yet (an agent, a shell task, a workflow, a monitor); a timer still needs the note.
- `wait clear` takes down this session's notes, all of them or those that say exactly `<what>`, once what they awaited is handled, so the board and the turn-end check show no wait that is over. It prints `cleared: <what>` for each, or `this session holds no note` and the words given. Another session's note and a running watcher's record are never touched.
- `wait none` arms nothing: it records, with its reason, that a message this seat sent awaits no answer.
- `wait list` prints one line for each live wait on the board: the session, what it awaits, since and until, and whether a watcher is running or what will wake it. `synthesis who` lists a seat for as long as it holds one, marked `waiting until HH:MM`.
- Exit codes: 0 when the event happened; 3 at the bound, with `nothing arrived in <how long>: still waiting for <what>` on stderr; 2 for a bound it cannot read or one over twelve hours, a command that cannot be started, a note with no `--by`, and nothing named to wait for. What a look finds after the bound is not the event: `wait message` and `wait file` look every `--every`, and every 0.05 s in the last quarter second before the bound, and mail that came too late stays unread for `synthesis inbox` or the next wait.
- `inbox --peek` lists unread mail and marks none of it.
- `msg` ends with what will deliver the message: `it is watching and wakes within seconds` (`checks every 5 min` for a watcher that looks less often), `it reads it at its next prompt`, or that no session is bound to that project and the message is kept for the next one that runs `synthesis resume <project>`. `--wake` also nudges an idle recipient through its own harness, where a command can; with `--durable`, each live session on the project.

## Procedure

1. **Name the event** and how long it is worth waiting for. An answer from the principal needs no watcher (rule 8).
2. **Pick the watcher** from [references/watchers.md](references/watchers.md): for one event, `synthesis wait …` run the way this harness wakes on a finished command; for a clock time or a stream of events, the harness's own tool with `synthesis wait note`. Where a watcher would cost model turns and the worth is unclear, ask once, recommendation first.
3. **Arm it**, then say in the reply what is armed, for how long and what wakes the seat.
4. **When woken**, run `synthesis inbox` (or read the file, or the check's result) and act. A wake is a pointer; the content is what the tool then reads. Where a note recorded the wait, take it down: `synthesis wait clear`.
5. **At the bound** (exit 3), do not report success. Decide again: arm another bounded wait, message the peer, or tell the principal the event did not come.

A session bound to no project receives no mail addressed to a project. `wait message` says so when it starts, and `synthesis resume <project>` binds the session.
