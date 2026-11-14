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
releases, so a harness deleting an old plugin folder never breaks a running
session. Whether an approval of the hooks lasts across upgrades depends on the
harness. Muse (`plugins approve`) has kept it across every release so far. Codex
(`/hooks`) does not: it stores, with each approval, a fingerprint of the
installed plugin, so every release that reinstalls the plugin leaves the
approval stale, and Codex runs none of synthesis's hooks until the person
approves them again (found 2026-11-05 on Codex 0.166 by running a real turn;
the doctor had read Codex's own record and reported the hooks trusted). The
doctor's `codex hook trust` check now computes that fingerprint itself, and the
release script names the approval as waiting on the person. The script runs
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
| UserPromptSubmit | `user-prompt-submit` | 5 s | every prompt; it also briefs a session whose project changed since its last brief, and after a pause of ten minutes or more says when the last turn ended |
| PreToolUse | `pre-tool-use` | 5 s | shell tools, and MCP tools whose names send, draft, reply, forward, schedule, change calendar events, set focus time or out-of-office, trash mail, or share files |
| Stop | `stop` | 5 s | every turn end, which it records for the next prompt |

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
| `prompt` (or `user_prompt`) | UserPromptSubmit | The text the person typed, scanned for `approve <code>`, with one or more codes after the word on its line. |
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
   runs the stable hook or `synthesis/hook.py` for any event, or that changes anything in
   the v5 state folder, its board (which only the `synthesis` CLI writes, so that Codex's
   sandbox may be granted it without reaching the state folder), a harness's transcript
   folder or the approved commit lines.
   - **How it reads a path.** Every write in the command is resolved and judged, whether or
     not the command spells a protected folder out: relative to the session's folder, to a
     `cd` (`cd -`, `pushd` and `popd` are followed), to where `env -C` or `sudo -D` sends
     the command, through a variable, through a link the same command makes (a relative link
     is read from the folder it is made in). A command is read once for each value it gives
     a variable (`D=…`, `D+=…`, after `export`, `readonly`, `declare` or `env`, in a `for …
     in` list, inside a quoted script), with the environment's value for one it does not
     set, the default a use carries (`${D:-…}`) and an end trimmed by `%` or `#`. The words
     after a shell's script (`sh -c 'script' name word`, `sh -s word` with the script on its
     input) are put where the script uses them (`$1`, `"$@"`), as the shell takes them and
     quoted for where they land (quoting starts over inside `$( )` and backticks); a
     script that gives them its own values (`set --`, `shift`, a function) is left as
     written. `$PWD` and `$OLDPWD` are the folder each command is in and the one it was in
     before, in its own words and targets; a script it hands a shell puts its own. `~` and
     `$HOME` are the home a command gives itself when it sets `HOME`. A word
     that starts with a substitution the guard can read is read with what that names put
     in: the folder of a path that is spelled out (`$(dirname <path>)`,
     `$(realpath <path>)`), a fresh temporary file or folder (`$(mktemp)`, `$(mktemp -d)`,
     made where its template says), the folder the command is in (`$(pwd)`), the top of
     the repository it is in (`$(git rev-parse --show-toplevel)`, asked of git as the
     command will ask). That holds for a `cd`, for a target and for a variable given one
     (`out=$(mktemp)`). After a `cd` it cannot read (any other substitution, a variable
     the command does not set), a bare file name is a write it cannot place: in a command
     that names a protected folder that write is refused, and so is a script run there
     that writes. `NAME=value` inside a program handed to another interpreter (a keyword
     argument, a statement of that program) is that program's text, not a variable the
     command sets.
     A path is compared the way a Mac's file system finds it, whatever its case.
     A target outside a protected folder may still change one, and is judged so: a folder
     changed throughout that holds it (`rm -r`, a move, a recursive copy or sync onto it,
     `chmod -R`, a `find` that deletes or runs a changing command), and a pattern that may
     name what lies in it (`*/*/*.jsonl` from the folder above; a part that starts with a
     pattern does not match a name that starts with a dot, as the shell reads one).
   - **What counts as a change.** A redirect; what a file utility changes (the destination
     of `cp`, `ln`, `install`, `rsync` and `ditto`, with `-t`; both ends of `mv`; `tee`,
     `touch`, `truncate`, `mkdir`, `rmdir`, `rm`, `unlink`, `shred`, `chmod`, `chown`,
     `chgrp`; `dd of=`; `sed` and `perl` editing in place; a compressor that replaces its
     file; what `sort -o`, `uniq` or an awk program writes (its redirects, and what a
     command it is given as a plain string writes); what `find` deletes or runs a changing
     command on (in the folders it searches: its operands, and BSD's `-f <folder>`), and
     what each command it runs writes besides, read in the folder of what it found when
     `-execdir` or `-okdir` runs it (the top of the search, and each protected folder under
     it); the files `xargs` hands such a command; a hex dump's second operand, which is its
     output, also when the first is `-`; what `trap` keeps to run when the shell ends, also after `--`); an interpreter script that writes there; and a path inside one of those
     folders handed to any program the guard does not know to only read it. An inline
     program for an interpreter the guard does not read (`php -r`, `lua -e`, `Rscript -e`
     and their like) is held for each path it names. What `printf` prints into a shell is
     its format with its words put in. A word handed to such a program may be a script it runs (`watch`, `ssh`,
     `osascript`), so in a command that names a protected folder each word with a space in
     it is read as a command line too. A line of it counts as a command where it starts
     with a program the guard has a rule for (a shell, an interpreter, a file utility,
     `awk`, `sed`, a hex dump, an interpreter it cannot read, or a reader such as `date`,
     `grep` or `git`, which may still redirect), and is held for what it writes, runs and
     starts; it is not held for a path it is merely handed. A shell's own words and words a
     sentence starts with (`select`, `for`, `case`, `read`, `which`) start no command there. Words for a
     reader are left alone: the value of a message option (`--body`, `-m`, `--title`,
     `--prompt` and their like), given apart or attached as `--body=…`, the words given to `codex`, `claude`, `muse` and `gh`,
     which run under their own guards, and a sentence that mentions a folder or shows a
     query (`select … where n > 5`).
   - **How it reads a Python program.** A program given to Python inline (`-c`, in each form
     Python takes it: `-Bc PROGRAM`, `-cPROGRAM`) or on its stdin is read by its syntax, and
     alone: another command's heredoc is not its text. A write is a file opened to write, a
     `pathlib` call that changes a file, a call into `os`, `shutil` or `subprocess`, a
     database opened, an archive unpacked, an in-place `fileinput`, the standard library's
     own writers (a log file `logging` is told to keep, `urlretrieve`, a temporary file
     made in a folder `dir=` names), a call named as a writer in any library, a module's
     own function that removes or moves, and a store or a file a library opens to be
     written (`shelve.open` and `dbm.open` unless told to read, `h5py.File(path, "w")`,
     `ExcelWriter(path)`, `np.memmap(path)`, a tree's `write(path)`), however the call was
     imported or renamed. A writer by its name is judged at the argument that writer
     takes as its path: the first for `to_csv` and its kin, `tofile`, `savefig`, `imsave`,
     `imwrite`, the `write_csv` family, a thing's own `save` and numpy's; the second for
     `dump` and for `save` in the libraries that take the thing first (`torch.save`,
     `joblib.dump`, `pd.to_pickle`); either, when it reads as a path, for a name the
     reader does not know (`to_<anything else>`, `write_<anything else>`, another
     module's `save(a, b)`). At the place a writer takes its path, a bare name is a
     file where the program stands and a path built from a protected one is that path,
     while an object, an open file or a buffer is no path; what is handed besides the
     path is content, whatever it spells. A function of the program's own named like a
     writer is read as it is written. An archive is judged
     where it lands: the archive unpacked and the folder packed are read. A link a program makes is judged at both ends, and none is made at
     a path that is the agent's own. A target the program spells out (a string, a name given
     one once, strings joined, a path built with `os.path.join` or `Path`) is judged where
     it leads. A name is read through every value the program gives it. Where it is read,
     that is the value its own body last gave it by a plain assignment, with whatever a
     branch, a loop or another function may have given it since; before any, it is what
     each caller handed the function. Each function is read by its own names, so two
     functions that both call what they are handed `path` are read apart, and a call of
     the program's own function is read by what that call hands it and what the function
     then hands back; a name the function itself gives another value, in a branch or a
     loop, is that value or the one it was handed, and a default of `None` is no value. One of two values (`a if c else b`, `a or b`), what a loop visits (a
     list the program spells out, its rows, `zip`, `enumerate`, a table's values), what a
     walk or a pattern finds (a path under the folder walked) and a template filled
     (`format`, `%`, a list joined) are read the same way. A member (`job.out`,
     `cfg["out"]`, `cfg.get("out", x)`, `rows[0]`, `os.environ["OUT"]`, `Path.home()`) is
     read by the thing that holds it. Each object, table and list the program makes is
     one thing, known by the place that makes it, however many names it is kept under
     and whatever it is handed to; what a function of the program's own hands back is
     read with what that call hands it, so a factory called for a transcript and for a
     file elsewhere makes two objects. It holds what it was made with: a table's entries (by
     a key, by a key held in a name, any of them when the key cannot be read; a table
     made from pairs, from another table or from a union holds what those hold, and one
     made from rows that cannot be read may hold anything), a list's places, what the `__init__` that runs gives each field from what that call hands it
     (a class without one of its own is built by the one it inherits, and a base's is
     followed through `super().__init__`), a data class's or a named tuple's field by
     place or by name, the class's constants and properties, a parser's defaults, and for
     a class that keeps its keywords as its fields (`self.__dict__.update(kw)` in its
     `__init__`) the keywords it is built with. And it
     holds whatever any statement gives it afterwards (`x.out = v`, `d["k"] = v`,
     `update`, `append`, `setattr`), through any name it is reached by, and a table
     filled from literal rows (`for key, value in rows: cfg[key] = value`) keeps each
     row's value under that row's key; what is given
     through a name that cannot be followed may be in any of them, and a thing whose
     maker cannot be read (`json.load(f)`) holds only what the program gives it. Along
     one path from one name, in statements that run once and in order, the last plain
     gift stands for those before it, so a table's entry read for a transcript and then
     given the file to write is that file; in a function, and through any other name,
     every gift counts. The environment is such a table: a variable holds what the
     command gave it until the program gives it another value, and `Path.home()` and
     `expanduser` use the home the program has where it asks. A table or a row spelled
     out once and only read, handed as `f(**table)` or `f(*row)`, is read as if written
     out. A target lands in a protected folder if any reading does. A value the reader cannot read makes the target one it cannot read, and
     that target is judged by what it is built from: a protected path in a string, or a
     name one reached through an assignment, a loop, a `with`, a default, a call to the
     program's own function or to one kept under a name, a list, an attribute, a class's
     fields, a parser's defaults or the environment the program sets itself. `~` is the
     home the program or its command gives itself, else the session's. Some of what is built from a path names no
     folder: its last part, one part counted from its end (`p.parts[-1]`,
     `path.split("/")[-2]`), a path taken relative to a folder that holds it (`relative_to`,
     `os.path.relpath` with its start), a path flattened into one name, a digest, a length.
     A fresh temporary folder (`tempfile.mkdtemp()`, `TemporaryDirectory()`) is a folder
     somewhere else. The words after the program are placed where it
     reads `sys.argv[n]`, and a variable of the environment where it reads it by name. Taken
     another way (a slice, an argument parser, the whole environment), one that names a
     protected path makes any write a refusal. What the program reads from a file is content
     and names no path (the `.name` of a file it opened is that file's path), and a copy out
     of a protected folder changes only the copy. The folder a call is made in is followed
     in the order the program's statements run: a folder change that is a statement of the
     program (`os.chdir`, `os.fchdir`) is sure, and a relative one is taken from wherever
     the program stood. The body of a `with`, of a `try`, of a branch, of a loop and of the
     program's main block is followed the same way, statement by statement: a branch may
     not be taken, a loop may run no times or leave at any point, a handler and a `finally`
     may start from any point of the `try`, and the body of `with contextlib.chdir(folder)`
     runs in that folder, after which the program is back where it was; a change inside
     `with contextlib.suppress(...)` may have failed and been passed over. A change inside a
     function may come at any time. A descriptor stands for the folder it was opened on,
     as that folder stood when it was opened (`fchdir`, `dir_fd=`), also one opened beside
     another; a number, and what `os.open` or `mkstemp` hands back, names no path. A command the program spells whole (`subprocess.run([...])`,
     `os.system("...")`, asyncio's and pty's ways to start one) is judged as the shell guard
     judges that command: in each folder the program may stand in or `cwd=` names, as the
     program `executable=` names, with the variables the program has put in `os.environ` or
     in the mapping it hands over as `env` (a dict, a copy of the environment, one kept
     under a name, under a second name, or added to later), with the words after a shell
     list's script, and with a script fed on its input or written down a pipe to it read as
     that command's script: a pipe belongs to the process it was opened for, under whatever
     name the program keeps that process, and what is written down it piece after piece is
     one script (a pipe the reader cannot tie to a process is read as every process's).
     What is written to `os.popen(command, "w")` is that command's input. In a list, a
     word built round a path the program found (`'echo x >> ' + str(p)`) keeps that path,
     and a script for a shell or an interpreter that cannot be read at all, built from a
     protected path, is refused.
     A relative path the program makes whole (`os.path.abspath`, `realpath`,
     `Path.resolve`, `os.getcwd()`, `Path.cwd()`) is whole from where the program stood at
     that call, wherever it stands when the path is used; `with_suffix`, `with_name` and
     `with_stem` spell the file they name.
     Handed anything else that is built from a protected path, or built from values the
     reader cannot read while it names one, it is held as a write; so is a command that
     leaves a variable to its environment while the program keeps a protected path in a
     mapping. A tree removed, moved or
     copied over whole (`rmtree`, `move`, `rename`, `copytree`) that holds a protected
     folder changes it (the folder of the approved lines too, when it is removed or moved
     away), and what a walk or a pattern over such a folder finds (`os.walk`, `glob`,
     `rglob`, from a relative folder or glob's `root_dir` as well, and through a link) may
     lie in it: of what a walk hands back, the folder is a path and the names in it are not.
     A program that runs code it builds (`exec`, `eval`, a module it names at run time)
     cannot be read: it is taken to write, and is refused while it names a protected path,
     is handed one or runs inside one. A program with a syntax error, and a script for
     another interpreter, is judged by its text: the words it is given, or the heredoc it
     reads on its stdin (the whole command when its text comes down a pipe).
   - **Standing in a protected folder.** A program can write where it stands without naming
     a file (an archive unpacked, a script file). Inside the state folder, the board or the
     sessions archive, where no session has reason to stand, only a command the guard can
     read runs: a reader, a file utility (judged by its targets), or a script given inline.
     Anything else is refused and told to run from another folder. Inside a harness's
     transcript folder, where sessions work on saved tool results, other programs run; a
     Python program given inline is read there too, and each of its writes must be led by a
     plain folder somewhere else (`/tmp/out/` followed by a name it computes passes; a bare
     name, or a folder that holds a protected one, does not). The same holds wherever the
     program may stand in a protected folder after a `chdir`; once a statement of the
     program has surely taken it elsewhere, its writes are judged there. (Applied to
     transcript folders as well, the standing rule refused 17 real commands in a 30-day
     replay, all needless.) A list of
     the programs that write never ends, so the guard keeps the other list: the usual
     readers (`cat`, `head`, `tail`, `grep`, `ls`, `jq`, `wc`, `diff` and their like) may
     be given such a path, an interpreter or a shell is judged by the script it is given,
     and `git` and the `synthesis` CLI pass, since they keep the approved lines and the
     board. Anything else is refused and told to read the file with `cat` and pipe it in,
     or to copy it out.
   - **A project's memory notes** (`*.md` under `<project>/memory/` in Claude Code's
     projects folder, under either spelling of the folder) are the agent's to write, move,
     remove and hand to any program, by shell, by file tool or by an inline program, and
     the folder may be made. A link made there is refused, and a path is judged where it
     really leads.
   - **A session's saved workflow scripts** (`*.js` directly in
     `<session>/workflows/scripts/`) are the agent's in the same way: the harness saves
     them there and has the agent edit them. The workflow's own record beside that folder
     stays protected.
   - **A saved tool result** (`<session>/tool-results/` beside a transcript: a fetched PDF,
     a screenshot, a long output) is material the agent is sent there to work on, so any
     program may be given it. Changing or removing it where it lies stays refused.
   - The hook is run when it is the script an interpreter or a shell runs: its first
     operand past its options, or the module after `-m`. A program handed the hook's file
     (a line counter, a compiler, another script) is not running it.
   Reading a transcript, and working on the hook's source, stay allowed. Before 5.7.0
   shipped, 30 days of shell commands recorded on one machine were run through the old
   guard and this one, and every command the new one refused was read.
3. **No hook text holds the phrase** (see What the hook returns).
4. **Random codes** mean a code cannot be planted before its request exists, and a
   later identical call never reuses the code an earlier approval answered.

### What remains open

No local file is secret from an agent running as the person's own OS user, so these
stay open, and no hook running as that same user can close them:

- An agent that deliberately forges its harness's transcript, writing a line shaped
  like the person's prompt, defeats the transcript check. The shell guard and the guard
  on the file tools (Write, Edit, `apply_patch` and their like) refuse the natural routes.
  A command that builds the path or the code at run time (an encoding, the output of a
  substitution, a glob in the folder's own name), a script file or a program run by its
  path, which the guard cannot read, a program that writes where it stands inside a
  transcript folder without naming a file (an archive unpacked there), a file-writing tool
  of another server that the guard does not know as a file tool, or a program the agent
  writes and runs gets through. So does a module run with `-m` (it is a script file:
  `python3 -m zipfile -e`), `git` told to put its own files in such a folder (a clone, an
  archive, a configuration file given with `-f`), a script that is the output of a process
  substitution (`bash <(…)`), and a command handed to a scheduler to run later (`crontab`,
  `at`). So does a write the Python reader does not follow: a writer of another library
  whose name says nothing of writing (a method named `write` on anything but a tree or a
  document writer, a store opened by a name the reader does not know), a path such a
  library's writer takes in a place the reader does not expect, a call reached through
  `getattr` or handed on with
  `functools.partial`, a path carried by an exception, a path built piece by piece so that
  no piece names the folder, a path the program reads out of a file or builds from a value
  the reader cannot read, a folder change or a mapping of variables
  made by code the reader cannot follow, a command an awk program builds in a variable and
  only reads from, and a program that runs what its configuration or a pipe hands it (a
  makefile on `make`'s input, a git alias given with `-c`, an editor named in a variable).
  A shell function's own `$1` is not followed either: a function handed a protected path
  is refused, also when it only reads it. The Python reader also refuses some programs
  that only write elsewhere, because it does not follow a test: a loop over a table's
  `items()` that writes only under one key (`if k == "out":`) is read as writing every
  value, what a method stores under a key it is handed (`cfg.set("out", path)`) is read
  as stored under any key, and a thing given a protected path through a name the reader
  cannot follow is taken to hold it wherever that thing is read. A program the guard does not know may be handed
  a folder that holds a protected one (an archive unpacked over it), and a program may
  list such a folder one level at a time and remove what it finds by a name it builds.
  A word handed to a program the guard does not know is read only where it starts as a
  command the guard knows: a script for that program's own language, or a line that
  starts with a program of the agent's, is not. A `cd` into a folder only a substitution
  or an unset variable names is refused for a bare write only in a command that names a
  protected folder; one that builds that folder's name at run time is the first case above.
- The shell guard reads the text of a command. It follows the ordinary ways a command names
  a file, runs in a folder and hands a file on, and each of those has a test. A spelling
  made to get past that reading may get through until it is added: ten review rounds by a
  second model each found more of them (a folder stack turned by number, a wrapper inside a
  wrapper, a file name split across two strings, a link made and then moved into place, two
  folder changes one after the other, a script written down a pipe, a path made whole
  before the program moved, a command run in the folder of what `find` found), and each
  was closed with a test. There is always another. What the guard is
  measured on is the other direction as well: 30 days of recorded commands, where it must
  not refuse ordinary work.
- A prompt another process injects into the session through the harness's own CLI
  (`claude -p --resume`, `codex queue`, `muse session-message`) is recorded as a typed
  prompt. The shell guard refuses such a command when it carries a pending code; one
  that builds the code at run time is not caught.
- A grant written by one of those routes can reuse a code the person typed for the
  identical call within the last 15 minutes: a second, identical send or deploy.
- The approved commit lines are a file the agent can change by one of those routes, or
  through git when the store lives in a synced repository (a pull, a checkout, a restore).
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

A session that comes back after a pause learns how old its picture is. The Stop hook
records when each turn ends, and a prompt that comes ten minutes or more later carries
one line: the time now, when the last turn ended and how long ago, and that what the
conversation says is in flight is as of then. Claude Code's idle compaction makes this
matter: it writes the summary about 54 minutes into a pause and applies it at the next
prompt, however much later, and the summary carries no time. SessionStart still restores
the project state from disk when the summary takes effect; the note covers what only
the conversation held.

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
  with the reason. When the hook itself cannot answer (it times out, crashes,
  prints output the harness cannot read, or cannot start because the stable hook
  is missing), Claude Code 2.1.295 or later blocks the call too, since the
  plugin's handler sets `"onFailure": "block"` (5.21.0); Claude Code names the
  hook and says `failed` or `timed out`, and an older one ignores the setting.
  Codex (0.167) and Muse (1.4.20) have no such setting: there a hook that times
  out or crashes lets the call through (Codex's runner marks it failed without
  blocking; Muse's `plugins hook test` gave `should_block: false` for a missing
  hook, an exit code of 1 and a timeout; probed 2026-11-14). Muse reads only its
  own manifest, which refuses the field, so it is set in `hooks/hooks.json`
  alone, where Codex reads it and hashes the hook without it. UserPromptSubmit and
  SessionStart keep the default: holding a person's prompt or a session's start
  on a hook failure costs more than it protects.
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
find hooks that are untrusted, modified or disabled. Codex 0.166 also stores a
fingerprint of the installed plugin's files with each approval and runs no hook
of a plugin whose files changed, which every release does. Doctor computes that
fingerprint the way Codex does (and the baseline Codex pins for approvals made
before it stored one), so a stale approval fails the check instead of passing
while Codex runs none of the hooks.

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
