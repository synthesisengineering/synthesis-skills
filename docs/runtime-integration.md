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
`~/.synthesis/v5/current/synthesis/hook.py <event>` with the interpreter pinned
at install, by its real path, owned by root with every folder above it and
writable by neither this user nor its groups, with `-I -S` under `env -i` and
only the variables the runtime reads, its own synthesis home, and the real git's
folder and then the system's first on PATH (5.24.0; the CLI, the git hooks and
the release launcher run the same way). Every session start rewrites a launcher
that differs from what the running runtime writes. `current` is a symlink
switched atomically, so a running hook sees the old release or the new one,
never neither.

The SessionStart registration also passes the plugin folder the harness loaded
(Claude Code's `${CLAUDE_PLUGIN_ROOT}`; Muse's `MUSE_PLUGIN_ROOT`, or the
script's own location). That folder is the harness's own plugin cache, which the
guard does not protect, so since 5.24.0 a session start installs from it only into
a synthesis home that no runtime has been in: the first install. The bootstrap that
runs while the stable hook is missing (`install.py`, which passes `synthesis install
--first`) and the session start itself install nothing where the home holds any of
`releases`, `current`, `bin`, `git-hooks`, `state`, `board` or `sessions`: a runtime
that is there is never replaced from that folder, at any version, and one that was
removed, by uninstall or by any other route, is never installed again from it
(review round 2 of 5.23.1, N6). The bootstrap says why on stderr, and every guarded
call is then held until a runtime is installed again. A newer release reaches the
runtime through the release launcher (`~/.synthesis/v5/bin/synthesis-release
--install-only --tag v<version>`), from a clone of GitHub it verified, a tag on
`main` no older than the runtime or GitHub's highest version tag, with no code; or
through setup or `synthesis install <folder>`, each of which waits for the
principal's code in a session (see [The runtime
itself](#the-layers-and-what-each-stops)). When the folder carries a newer release,
the session start says so once, naming both versions and the launcher's line, and
`synthesis doctor` warns while the two differ.

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
| `tool_name`, `tool_input` | PreToolUse | The call to check. A shell command is read from `tool_input.command` or `tool_input.cmd`, as a string or an argv list; `tool_input.workdir` is the fallback directory. A Codex code-mode script (`exec`) is passed on purpose: see [Codex code mode](#codex-code-mode). |
| `tool_use_id` | PreToolUse | The call's own id: for a script sent under `command`, whether Codex's record shows this very call as its code-mode tool ([Codex code mode](#codex-code-mode)). |
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

### The sealed folders (the guard's sandbox, 2026-11-15)

Every record an approval rests on lives in `~/.synthesis/v5/approvals/`, which only the
hook writes, and what only the installer writes in `~/.synthesis/v5/install/`; each
harness's operating-system sandbox keeps every shell out of both (the policy files and the
doctor's seal check are their own part). `approvals/` holds `grants/` (one file per live
grant), `requests/` (those the hook files), `effects/` (grants the hook applies itself),
`granted.jsonl` (each typed code the hook spent: the code, what it granted, when the
principal typed it, and the record and line that showed it), `records/` (each session's
record, as the prompt hook names it), `sends/` (the window, the day's ledger, batches,
their spends and code records, the sender's tickets), `deploys/`, `desktop/`, `typed/`,
`imessage-sends/`, `stop/`, `release-grants/`, `browser.json`, `browser-accounts.json`,
`lock` and `line-allowances.json`. `install/` holds `codex-user-hooks.json`. What a shell
may write stays in `state/`: the requests it files (`state/requests/`, named as a shell's
when granted, and never granted under a code the hook filed), the close mark of
`synthesis sends close`, the doctor's notes and the autopilot's pointers.

- **A shell asks; the hook applies.** `synthesis sends open` and `sends batch` file the
  request (the batch carried in it) and open nothing; the commit check files the line's
  request and never writes the store. Once the session's record shows the principal
  typing the code, the hook applies it at that prompt, the turn's next tool call or its
  end: it opens the window or the batch, or keeps the line. `synthesis sends close`
  writes a close mark beside the state, which ends what opened before it and never
  extends anything. The lost-session and gap-review commands read a live, typed grant
  and spend nothing.
- **A process that cannot write the sealed folder spends nothing**: `consume`, `void`,
  `alone` and `answered` raise `approvals.Sealed`, naming the folder.
- **A command outside the sandbox** (Claude Code's `dangerouslyDisableSandbox`, Codex's
  `sandbox_permissions: "require_escalated"` or `with_escalated_permissions`, the desktop
  app's terminal panel) waits for the principal's code of exactly that command, where it
  runs; the release launcher's own line leaves the sandbox with no code.
- **The guard's own settings** change through `synthesis config apply <file>`, run outside the
  sandbox: it shows the change key by key and waits for the principal's code of exactly that
  file's content, and the runtime's own launcher running that line outside the sandbox needs
  no second code. A file tool's write of `config.json`, a harness's hook or sandbox settings
  or a launch agent waits for the code of that call.
- **An MCP tool that writes a file** is judged by its path arguments, as the file tools are:
  an MCP server runs outside every sandbox, so one that writes into a sealed or protected
  folder is refused.
- **The installer** refuses, naming the folder, where it cannot write the sealed runtime,
  rather than install half of it.
- **A Muse session gets no approval** until Muse's sandbox is shown to seal the folders:
  its prompt hook grants nothing, a grant made elsewhere lets nothing through there, and a
  held call says to make it in a Claude Code or Codex session.
- **The move.** The first install or hook that finds `approvals/` not there moves the old
  records out of `state/` (and merges a line store the config once placed elsewhere),
  once; after that a file in an old place is a shell's and stays where it is.
- **Residual.** A shell-filed request can misdescribe what its code approves (it deceives
  the principal; it forges nothing). A Codex `write_stdin` into a session an escalated
  command started types into that unsandboxed shell under the one code. The plugin caches
  are sealed by the sandbox alone: the skills' scripts run from there, so the guard does
  not hold a program that reads them.

The commit check uses the same approvals for a disclosure hit: a line in a file or a
commit message that matches the principal's exposure patterns. No word list can tell a
leak from a legitimate mention, and agents that reworded, split or assembled a term at
run time to get past the check weakened the text and defeated the check, so the
principal ruled (2026-10-06) that a legitimate line is approved instead, and that a
flagged term is never reworded, split, encoded or built at run time to get past any
guard. The request is keyed to a SHA-256 of the repository (its normalized push
remotes), the path (or `commit message`) and the line's exact bytes. The check runs in
the agent's shell, so it only files the request (in `state/requests`); once the session's
record shows the principal typing its code, the hook keeps the line in the sealed store,
`~/.synthesis/v5/approvals/line-allowances.json`, as that hash and a date, so the line
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
session's transcript by the session id its shell carries, at the path the prompt hook
recorded. That path counts only inside the folders each harness keeps its records in as
the prompt hook's environment named them, recorded beside it: the environment of the
command running the script, which the agent sets, never names them. When there is no
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
     not the command spells a protected folder out: relative to the session's folder (or the
     folder a Codex or Muse shell call names as its own, its `workdir`), to a
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
     `$HOME` are the home a command gives itself when it sets `HOME`; a line that gives
     `HOME` a value the guard does not read (`read`, `printf -v`, a loop over it, a
     parameter that assigns) and then uses it waits, but text it only prints or hands a
     program as input (`echo "HOME: $HOME"`, a heredoc fed to anything but a shell) gives
     `HOME` no value (5.24.0). A process substitution (`diff <(…) file`) is a file's name
     to its command and its own command is read; a `case` statement's patterns run
     nothing; and an alias is one a command on the line defines, never a word in a
     message, a note or a heredoc's body. A word
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
     is handed one or runs inside one; so is one that reaches a call by a name it builds
     (`getattr` with a built name or on a module, `vars()`, a module's `__dict__`,
     `functools.partial`, `operator.methodcaller`, `ctypes`). A program with a syntax error
     is judged as below.
   - **A program the guard does not know to only read** (5.22.1). A list of the ways to write
     never ends (a one-line copy in a language the guard does not read wrote a transcript and
     a grant, and so did a launcher in front of one, git with an option that writes, a hard
     link and an archive whose members carry their own paths), so the guard keeps the other
     list. A command any of whose words, options or program text names a protected folder or
     a folder above one passes only when its program is a known reader: a program on the
     readers' list with none of its own options that write or run (`less -o`, `rg --pre`,
     `sort -o`), git with a read subcommand and none of its options that write or run
     (`--output`, `--work-tree`, `-c`, `--config-env`, a pager, `--ext-diff`, `--textconv`),
     `find` and `eval` (what each runs is judged as a command of its own), a hex dump with one
     file, an awk program read with certainty that has no output redirect, pipe or `system`, a
     sed program read with certainty (bracket expressions as BSD sed reads them) with no `w`,
     `W` or `e`, a shell whose script is on the line, on its input or in a file `cat` pipes to
     it (each of its commands is judged; a script on its input that cannot be read waits),
     Python its reader proves, and the plugin's own scripts: inside the release the guard runs
     from (`releases/<hash>/` under the synthesis home), or byte for byte that release's copy at
     the same relative path, with the modules beside it that it imports (a skill's script in a
     harness's plugin cache). The installed runtime (`releases`, `current` and `bin` under the
     synthesis home) is a protected folder, so no command plants or changes a file there. A
     script, a module or Python on the line that uses synthesis's own code from outside the
     release waits only when it names one of synthesis's functions that write (its state,
     approvals, send windows and batches, board or archive: the list a test keeps to what the
     source shows, under any name it is imported by, called or not), reaches that code in a
     way its reader cannot follow (`getattr`, `vars()` or `__dict__` on it, a module handed
     on, a name its module only imports, a name or code it builds, `import *`), or writes
     where synthesis's own paths lead (`paths.state()` and the like, spelled out as the
     folders they return where they can be); using it by name to read passes (`guards.check`,
     `paths.home()`, `yamlish`, the board's readers), as does a function the source shows
     never writes, handed on.
     Python on the line (`-c`, or a program on its input) is proved only where none of the
     agent's modules can stand in: run with `-I` (or `-P` with `-E`), or with no file or
     package where it runs named like a module it imports, none the line writes there, and no
     `PYTHONSTARTUP`, `PYTHONHOME`, `PYTHONUSERBASE` or `PYTHONSAFEPATH` set on the line, nor a
     `PYTHONPATH` unless each folder it names is there when judged, holds no module the
     program imports, no `sitecustomize` or `usercustomize`, and nothing that hides a module
     of Python's own installation (its standard library and site-packages, not the folders
     the guard's process was started from; a folder with no `__init__.py` hides nothing) but
     a `synthesis` package byte for byte the guard's own, and is neither written into by the
     line nor beside another program on it that may fill it unseen (review round 3 of
     22.21). A
     script file, or a module run with `-m` from the folder that holds it, is judged by what
     its text shows (after the 30-day replay: proving every expression held about 3,700
     commands a month): read whole up to 4 MB, with each module of its own it imports (a file
     or package beside it named like no module found elsewhere, or one its package names
     relative to itself, and theirs in turn), it waits only when the command or that text
     names a protected folder and the text holds a write or a run the reader recognizes that
     it cannot place outside them; a module of its own waits on any such write, since what
     its functions are handed comes from another file. A file beside it named like a module
     found elsewhere stands in, and waits; a module run with `-m` found anywhere else waits
     whenever the command names a protected folder, since its first file is not the program
     it runs (pip's and pytest's hand everything on) and need not be this Python's. A file
     argparse opens to write is a write. A hold for want of only isolation says that `-I`, or
     a folder or line without the module or variable, needs no code; a git read it spells whole (a list that starts with `git`, a read
     subcommand, no option that writes or runs, no shell) is a read wherever it points. Anything
     else waits for the principal's code for exactly that command, the folder it runs in and
     the size, time and digest of every script it runs, so a script rewritten after the
     approval is a new command; the hold names the program that runs and says to read with
     `cat`, `head`, `tail`, `grep` or `jq` (or a redirect of `cat` for a copy), or with Python
     the guard can read, for no code. Words are judged wherever the program sits, so a launcher
     (`script`, `arch`, `time -p`, `xcrun`) hides nothing, and after the shell's own expansions:
     brace lists (`{a,b}`, `{1..3}`, nested) and every redirect bash and zsh accept (`>|`,
     `>!`, `>>!`, `&>!`, `>&!`, `&>>`, `<>`). A name hides nothing either (22.32): a command
     word the guard judges by name (a shell, an interpreter, a reader, a file utility, a wrapper
     and their like) that leads to a script rather than a compiled program, by its own path or
     found on PATH as the shell looks it up (also when a wrapper or `find -exec` starts it, or
     the line gives PATH itself), is judged as that script too: the command its `#!` line
     starts, or a shell for a file with none, beside its judgment by name. A builtin the shell
     runs itself is not looked up, and the commands that really are scripts pass where their
     installer puts them (the guardrails' config reference, "Commands judged by name"). A
     folder is named by its path in any case; on the
     command line, each word only by its own path (after `~`, variables, `..` and links), so
     parts in two words never join (2026-11-15: a skill script's path in the harness's plugin
     cache and a project page's path were read together as naming the transcripts); in a
     program's text, by the parts of its path below the home folder within one statement,
     however they are joined (`Path.home() / ".claude" / "projects"`, `$ENV{HOME} . "/" .
     ".claude"`), but never from two paths written whole, and a path written whole only where
     they stand one after another;
     by a variable that holds it, a folder above it or a place inside it, with the rest of the
     path anywhere after it; by a path that leads into it through `..`, a link made beforehand
     or one the line makes; by a folder between it and the home folder or such a variable,
     handed as a word; by standing in the state folder, its board or the session archive (in a
     transcript folder, by the bare name of a file that is there); and by the files `xargs`
     hands a program on a line that names one. A project's memory notes, a session's saved
     workflow scripts and saved tool results name no folder. Values of message options and the
     words given to `codex`, `claude`, `muse` and `gh` are left alone. An archive tool that
     unpacks where it stands in a folder that holds or lies in a protected one, or where its
     members say (`-P`, `--absolute-names`, `--insecure`, `pax -r`), waits too; a copy into
     such a folder stays refused. A script file outside the runtime release that names one of
     synthesis's writers waits (the release script and onboarding's setup, run from a
     checkout, are such files); Python on the line that reaches synthesis's code in a way its
     reader cannot follow is refused. The guard reads only regular files a command runs as scripts, bounded in
     size and opened without waiting, reads each script and its own modules once a call (at
     most eight scripts, 64 modules a script), stops reading a program at the call's
     deadline, and a command it cannot finish judging within 3 seconds waits for the
     principal's code.
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
   - **The runtime itself** (5.24.0; review round 2 of 5.23.1, N5 and N6; review round 1 of
     22.18, H1 and H2; review round 4 of 5.23.1, Q4). Replacing or removing an installed runtime waits
     for the principal's code for exactly that change, and `install.install` and
     `install.uninstall` themselves spend it, so every route that starts the CLI, setup.py or
     the release script as a process of its own ends at that check. The release launcher's
     install needs no code because the hook grants it: when the guard lets the launcher's
     line through, it writes one grant, an install of `v<version>` (the tag the line names,
     or the version its checkout's manifests carry) into this home. The line counts as the
     launcher's only as written, or handed to the system's own shell (`<shell> -c '<line>'`,
     the shell a file owned by root with every folder above it and writable by no user, as
     named and as resolved, so no link of a user's is on the way; named bare, the first of
     its name on the harness's PATH: combined review round 1 of 22.8 with 22.18, C2; one put
     ahead of it after the line has passed is open, below). `install.install` spends the grant
     once, and only for the release tool's fresh clone in the protected releases folder
     whose HEAD is the commit GitHub's tag names (`git ls-remote`, asked from a folder
     outside the clone so no config of the clone's sends it elsewhere: round 2, R2-1), its
     tracked tree clean, and whose staged copy holds exactly that commit's files (C8: the
     harness commands a release runs are found where this user writes; the release also
     holds its clone to the verified commit after each of them). It trusts no main
     program, interpreter flag or
     module's `__file__`, so a program that poses as the release tool (a forged `__main__`
     under `-I -S`) is asked for the code like any other (review round 2 of 22.18, K1). A
     release older than the running one is a subject of its own (`rollback`), named to the
     principal as a downgrade with both versions, and needs his code on every route, the
     launcher's too. Install calls the check it bound when it loaded, so a program in the
     installer's own process that puts its own function in `install.approval`, by name or by
     a name built at run time, changes nothing. Not every name built at run time fails
     closed: a program that replaces those bound names (`install._approve`,
     `install._released`), or the runtime's files themselves, is held only by the guard's
     reading of it, which holds it where it spells synthesis's installer and passes it where
     it builds the names at run time (C1, open: below). Run from a checkout, the release
     script's install stage waits for the code.
     `synthesis install` (with or without
     a folder, and `--git-hooks`, which also points git's global hooks at the commit check)
     and `synthesis uninstall` refuse wherever the home shows a runtime (`install.traces`)
     unless a live grant the principal's prompt backs names that change; otherwise they file
     the request and say what the hook says. So the spelling does not matter: a script run
     by `sh`, by its path or sourced, Python's `subprocess`, perl, awk, a git alias, a make
     recipe, a wrapper of another name and a scheduled job all end at that refusal. The code
     binds the change, the home, whether git's hooks follow, and the sha256 of every file the
     install copies (the whole `synthesis/` package with the folders in it, the stable skill
     scripts and the CHANGELOG): the install copies those files into a staging folder inside
     the protected releases folder, hashes that copy, checks it against the grant and
     installs from it, so a file changed or added after the code is never installed on it.
     The hook asks for the same subject wherever it reads the CLI as the command (`synthesis`
     on PATH, its stable path, `~/.local/bin/synthesis` or any link to it, `python -m
     synthesis.cli`, `-m synthesis` and `-m synthesis.install`, the CLI's module or any
     `synthesis/install.py` run by path, the CLI's script read by a shell, behind `env`,
     `nohup`, `timeout`, `xargs`, `find -exec` or a runner such as `uv run`, in any shell a
     harness has) and only checks it, so the principal approves before the run; a bare
     `synthesis` that PATH resolves to anything but the stable launcher is judged as the
     program it is, never as the CLI. The CLI's own parser reads the words, so its help, a
     dry run (`uninstall --dry-run`) and words it refuses need no code, and neither does a
     first install into a home no runtime has been in; a word the guard cannot read (a
     substitution, a variable it cannot be sure of, a glob) makes the command wait. Where no
     runtime runs the prompt hook to record a grant (after an uninstall), the CLI reads the
     session's own record for the code instead (`--session` names a session the hook
     recorded before). A Python program that
     calls the installer (`install.install`, `install.uninstall`, the CLI's install or
     uninstall) waits as any program that names one of synthesis's writers does, and its
     import is read wherever a statement may start (after `;` or `:`, in a list of
     imports); one that loads synthesis's code by a name or a file it hands a loader is
     refused. `synthesis doctor`, `synthesis who`, `synthesis version` and every other
     command pass as before.
   - **What Codex types into a session.** Codex starts a long-running process with
     `exec_command` (on a terminal with `tty: true`) and types into it with `write_stdin`,
     which reaches the hook through its matcher. A typed line is judged in the folder that
     session's `exec_command` named, found by the session's number in the harness's record
     (an `exec_command` whose output gave it, or a code-mode script that started one command
     and whose output gave it): as a command line, by every shell guard, and for a program
     that is no shell also as what it is fed; typed into an interpreter started with no script
     (`python3`, `node`), with everything typed into it as its program; typed into ssh to
     another machine, by every shell guard where it stands, since its own folder is elsewhere.
     The line is the text typed before it and not yet submitted, then its own
     characters, so a line split across calls is judged whole. A poll (nothing typed) and
     keys that start nothing new (Ctrl-C, Ctrl-D, Ctrl-Z, Enter) pass; text carrying keys
     or history that edit, complete or recall a line (backspace, Tab, an arrow, `!!`,
     `^a^b`, `fc -s`) waits, since what the terminal runs is not the text. Where the record shows
     no start, where a typed line changed a shell's folder or variables (`cd`, `pushd`,
     `export`, an assignment, `alias`, `source`, a bare folder name, which zsh takes as `cd`),
     and in a shell in a container or one ssh opens on this machine (it starts in the home
     folder), only a line whose every command just reads goes without a code: what it writes
     cannot be placed, and a read writes nothing.
   Reading a transcript, and working on the hook's source, stay allowed. Before 5.7.0
   shipped, 30 days of shell commands recorded on one machine were run through the old
   guard and this one, and every command the new one refused was read.
3. **The guard's own settings take the person's code; the global commit check's entry
   points take none.** `config.json` in the synthesis home holds what every approval
   means: the commit lines the person approved, their own repositories, the hosts their
   action sheets upload to, the signatures a send window lets through, the forbidden
   phrases, the account each workspace acts as and the turn-end judge's program and host.
   `git-hooks` beside it holds what git runs before every commit, merge and commit message
   in every repository: it is one of the runtime's own protected folders (above), which
   only its installer writes, so a write there is refused outright. The person changes the
   settings, so a write to them is not refused: it waits for their code for exactly that
   call. A file tool (Write, Edit, MultiEdit, NotebookEdit,
   Codex's `apply_patch`, Muse's `write_file` and `edit_file`) is bound to the tool, the
   file and everything it writes; a shell command to the command, the folder it runs in,
   each script it runs and each file it names, as each stands then, so a file changed after
   the approval makes it a new command. A shell command is read as for the protected
   folders above, with the settings among them: a redirect, what a file utility changes, a
   pattern that may name them, a folder changed throughout that holds them, a program that
   writes there or starts a command that does, and synthesis's own `paths.config_file()`
   read as the config's path; a program the guard cannot prove only reads that names them
   waits. A command that also reaches one of the protected folders above is refused, as
   before. The copy that installs the person's settings from a private repository waits like
   any other write. A path is judged where it really leads and in any case, so a link made
   beforehand, `..`, `~`, `$HOME` or capitals change nothing. Reading needs no code (`cat`,
   `head`, `grep`, `jq`, `diff`, git's reads, Python the guard proves only reads, and a
   redirect of `cat` for a copy); `cp` and `ln` of them wait, as for every protected file,
   since they can link as well as copy. The installer's own route (`synthesis install`,
   `synthesis update`, the release script's install stage) writes the hooks from the runtime
   it installs, which the guard trusts as it trusts itself.
4. **A shell's startup files, Claude Code's shell snapshots and the harness programs take
   the person's code the same way.** Claude Code runs every command through zsh, which
   reads `~/.zshenv` and sources a snapshot of the shell from `shell-snapshots` in Claude
   Code's configuration folder; Codex runs `bash -lc`, which reads `~/.bash_profile`,
   `~/.bash_login` or `~/.profile`; bash reads the file `BASH_ENV` names. Code there runs
   before every command, where no guard sees it. The harnesses, `synthesis doctor` and the
   release tool run `claude`, `codex`, `muse` and `gh` wherever each resolves. So a write
   to any of these waits for the person's code, bound and read as for the settings above:
   `~/.zshenv`, `~/.zprofile`, `~/.zshrc`, `~/.zlogin` and `~/.zlogout`, and the same names
   in `ZDOTDIR` (from the environment, or where `~/.zshenv` sets it); `~/.bash_profile`,
   `~/.bash_login`, `~/.profile`, `~/.bashrc`; the files `BASH_ENV` and `ENV` name; the
   snapshots folder; and each harness program at every folder on PATH and in the vendors'
   known places (`~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, the Codex and
   ChatGPT apps), whether or not a file is there yet, since one put there runs instead;
   each link on the way, to the file it ends at; the folder its installer keeps it in
   (Claude Code's versions under `~/.local/share/claude`, the desktop app's `claude-code`
   folder, Codex's app-server CLI under `~/.codex/plugins/.plugin-appserver`, a Homebrew keg
   or cask, an npm package, the Codex CLI folder inside the ChatGPT or Codex app); and the
   files muse's launcher keeps beside it (`muse-bin-<version>`, `.muse-version`). A folder
   this user cannot write, the system's own, is left out. An installer told to change one of these programs waits too, since it
   writes where the guard does not see: Homebrew or a Node package manager installing,
   upgrading, removing or linking `gh`, `codex`, `claude-code` or its npm package, a bare
   `brew upgrade` or `npm update -g` while one of them is installed that way, and
   `claude update` or `claude install`. Reading them needs no code, nor does sourcing a
   startup file or a snapshot (`source ~/.zshrc` runs what a shell's start runs anyway),
   running a harness program, by name or by its path (a launcher's text may name where its
   program is kept), or installing other tools (`brew install`, `pip install --user`,
   `npm install -g`). A harness's own variables that name its program or a startup file
   (Claude Code's `CLAUDE_CODE_EXECPATH`, `BASH_ENV`) do not count as a protected path the
   environment hands a program, so a program that reads its environment is not held for
   them.
5. **No hook text holds the phrase** (see What the hook returns).
6. **Random codes** mean a code cannot be planted before its request exists, and a
   later identical call never reuses the code an earlier approval answered.

### What remains open

- **A page script's call whose name says nothing of what it does** (5.24.0). On a messaging site's page the guard
  reads a script's code: a call by a name built as it runs is refused and one that acts waits, but a library's own
  event call (jQuery's `.trigger('click')`) or an app's own function under a name that does not say it sends passes as
  a read, since nothing in the script shows its effect. Tests: `test_open_a_call_whose_name_says_nothing_of_what_it_does`,
  marked to fail until it is closed.
- **Spellings made to beat that reader** (review round 1 of 5.23.1, #13), each a case of
  `test_open_a_spelling_made_to_beat_the_reader` or `test_open_a_blob_document_made_on_the_sites_own_origin`, expected to
  fail until closed: a member named by an escaped string (`el['\u0063lick']()`, `el['\x63lick']()`); a method called in
  parentheses (`(el.click)()`); a plain name as a template tag (`` el.click`` ``); an alias of a built name; a call by
  `forEach(Function.prototype.call, ...)`; a getter; an indirect `eval` (`(0, eval)(...)`); a timer given a string in a
  variable; `open` through a window alias (`const w = window; w.open(...)`); HTML decoded at run time
  (`insertAdjacentHTML(..., atob(...))`); a `blob:` document made on the site's own origin and then navigated to; an
  HTML-like comment (`<!-- '`), whose quote the reader takes for a string; and an object divided (`{} / x / 1`), whose
  `/` the reader takes for a pattern. A batch whose `javascript:` navigate moves the tab was closed by reading the page
  after it as unknown.
- **Two more spellings** (review round 2 of 5.23.1, #5 and #6), cases of
  `test_open_a_fetch_or_a_method_reached_under_another_name`, expected to fail until closed: `fetch` reached under
  another name with its method quoted (`const {fetch: f} = window` or `const f = window.fetch`, then
  `f(url, {"method": "POST", ...})`), and a method that names what it does read as a value and called under another
  name (`const o = {c: HTMLElement.prototype.click}; o.c.call(el)`; `el.go = HTMLElement.prototype.click; el.go()`).
  A third came with closing #3: the reader keeps no scopes, so a page's own send called by a bare name the script also
  defines elsewhere, as a function or a parameter (`[0].map(sendMessage => sendMessage); sendMessage(...)`), passes (a
  case of the same test). A fourth came with review round 3's T1: an init the reader cannot follow is read by the
  script's own words, so one that a page's own function returns (`fetch(url, options())`) passes when the script names
  no method and no body, a case of the first item above (a call whose name says nothing of what it does) and of the
  same test.
- **Moves made to beat the batch's moved rule** (review round 5 of 5.24.0, #1), cases of
  `test_open_a_move_the_page_script_reader_does_not_see`, expected to fail until closed: a page script moves the tab by
  a member of `location` it names as it runs (`location[['hr', 'ef'].join('')] = ...`), or by writing a refresh into the
  page (`document.body.innerHTML = '<meta http-equiv="refresh" ...>'`). Each is no move to the reader, so a script after
  it in the same call is judged on the page the list showed before. Review round 6 adds two, cases of
  `test_open_a_page_that_moves_the_tab_by_itself`: a page that redirects itself after the last list of tabs showed it,
  and, as ruled, a local app's page that sends the tab on (a navigate or a click on a local app moves nothing, so a
  script after it runs there). A move by an address off a local app, a link, a click, a key, a form value or an upload
  on another page, or a script that can navigate (a location change by name, alias or `Object.assign`, `open`, a
  history or navigation step, and off a local app a click, a submit or a dispatched event) is one.
- **Two more from review round 4 of 5.23.1** (C1 and C2), cases of
  `test_open_an_init_from_a_string_or_a_pages_send_under_the_scripts_own_name`, expected to fail until closed: an init
  parsed from a string (`fetch(url, JSON.parse('{"method":"POST",...}'))`), whose method and body the reader sees only
  as a string; and a page's send under a method name the script defines, by `this` at the script's top level (where it
  is the page's window) or by a receiver the script sets to the page's object (`let o = {sendMessage() {}}; o =
  window.app; o.sendMessage(...)`), the member-call form of the item above on scopes. Review round 5 adds W5, a case of
  `test_open_an_iife_that_writes_a_decoy_object_and_returns_the_pages`: an IIFE that writes any object literal (a
  `=> ({i})` callback inside it) and returns the page's object counts as the script's own, so a page's send through it,
  under a method name the script defines elsewhere, passes.
- **Three more from review round 7 of 5.23.1** (Y4), cases of `test_open_a_method_set_another_way`, expected to fail
  until closed: a method set by `Object.defineProperty`, by `Object.fromEntries`, or as a class field after another
  field (`class O { credentials = 'include'; method = 'POST' }`, with `new O()` as the init). The cost on the other side
  (Y5): a read whose own result mapping has a `method` key (`d.items.map(p => ({id: p.id, method: p.paymentMethod}))`)
  waits for a code, since the reader counts that key wherever it is written. It is rare, and it fails closed
  (`test_a_read_whose_own_result_maps_a_method_key_waits`).

No local file is secret from an agent running as the person's own OS user, so these
stay open, and no hook running as that same user can close them:

- An agent that deliberately forges its harness's transcript, writing a line shaped
  like the person's prompt, defeats the transcript check. The shell guard and the guard
  on the file tools (Write, Edit, `apply_patch` and their like) refuse the natural routes.
  A command that builds the path or the code at run time (an encoding, the output of a
  substitution, a glob in the folder's own name, a name assembled from pieces none of which
  spells the folder), a script file, a module or a program run by its path that names no
  protected folder in a spelling the guard reads (it reads a script's first 4 MB, a longer
  Python script waits, and it reads an editor's file as text it edits, not a script), a Python
  script whose own text and own modules show no write the reader recognizes while a module
  it imports from anywhere else, or compiled code beside it, does the writing, a program other than an archive tool that
  writes where it stands inside a transcript folder without naming a file, a file-writing
  tool of another server that the guard does not know as a file tool, or a program the agent
  writes and runs that names no such folder gets through. The installed plugin and runtime
  are trusted as the guard itself is (an agent that rewrites them can rewrite the guard), and
  a script file run without `-I` loads what the shell's own `PYTHONPATH`, which the guard does
  not see, puts first. So does `git`
  told to put its own files in such a folder (a clone, an
  archive, a configuration file given with `-f`), a script that is the output of a process
  substitution (`bash <(…)`), and a command handed to a scheduler to run later (`crontab`,
  `at`). So does a write the Python reader does not follow: a writer of another library
  whose name says nothing of writing (a method named `write` on anything but a tree or a
  document writer, a store opened by a name the reader does not know), a path such a
  library's writer takes in a place the reader does not expect, a path carried by an
  exception, a path built piece by piece so that
  no piece names the folder, a path the program reads out of a file or builds from a value
  the reader cannot read, a folder change or a mapping of variables
  made by code the reader cannot follow, and a program that runs what its configuration or a pipe hands it (a
  makefile on `make`'s input, a git alias given with `-c`, an editor named in a variable).
  A shell function's own `$1` is not followed either: a function handed a protected path
  is refused, also when it only reads it. The Python reader also refuses some programs
  that only write elsewhere, because it does not follow a test: a loop over a table's
  `items()` that writes only under one key (`if k == "out":`) is read as writing every
  value, what a method stores under a key it is handed (`cfg.set("out", path)`) is read
  as stored under any key, and a thing given a protected path through a name the reader
  cannot follow is taken to hold it wherever that thing is read. A program may list a folder
  that holds a protected one, one level at a time, and remove what it finds by a name it builds.
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
- A program the guard does not know that runs git itself in a folder it is handed runs whatever that repository's
  configuration names; every carried script that does so is read as a scanner (the context doctor, with the knowledge
  roots its setting names when it is given no folder; `repo_state.py`, `stray_lessons.py`, `pr_queue_scan.py`,
  `portfolio_review.py` and `sharing_scan.py`); this is crafted, as it needs a program of the agent's own.
- A raw socket client (`nc`, `socat`) that writes a local MCP server's JSON-RPC itself, a Python program's asyncio
  stream, and a request library the guard does not know whose post names no write method and no body keyword (pycurl's
  `POSTFIELDS` alone) reach the server's tools unread; this is crafted, and 60 days of records hold none.
- A program that takes its target from the environment and builds its body while it runs, with the JSON-RPC method
  split across literals (`'tools/' + 'call'`), reaches the server's tools unread: the guard reads such a body as a request
  the program builds, and finds a tool call only where the program's text spells the method whole, so it reads a body
  that is no tool call. The strict expected failure `test_a_tool_call_whose_method_is_split_across_literals_waits`
  names it (review round 4 of 22.17; crafted).
- Crafted: outside the release, a program named like a Python interpreter and given by its
  path is taken to be Python, so a shell script named `python3` runs under the proof the
  guard made for the reader script it is handed.
- Crafted: for a script outside the release, nothing on the line that makes the word
  `python3` run something else (a function, an alias, `hash`, `autoload`, a value given by
  any builtin, `PATH` or zsh's `path`) is looked for, so the proof made from its text holds
  while something else runs; in front of a script of the release, each of them, and a HOME
  given a value the guard does not read, makes it wait or be judged like any other.
- Crafted: a script outside the release, or any Python run without `-s`, `-S` or `-I`, is
  proven by its own text and modules alone, so a module named like a standard one planted
  beside it (one the standard library imports, as `argparse` imports `gettext`), compiled
  code made for one of its own modules, or a `usercustomize.py` or `.pth` file in the user's
  own site folder runs unseen; a run of the release passes `-s`, which leaves out the user's
  own site folder.
- Crafted: a file planted in the interpreter's own site-packages (a `.pth` file, a site
  customization) or in a standard library the user can write (a Homebrew Python's) runs
  inside a trusted run of the release; it closes when trusted runs use the sealed
  interpreter the guard's sandbox plans (plan item 22.14).
- Crafted: an inline Python program that writes through a hard link the agent made earlier
  to a release file (`open(<link>, 'w')`) is not seen as a write to that file: the shell
  and the file tools ask whether a file they write shares its inode with a protected one,
  and the Python reader does not.
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
- The routes above that the guard cannot read reach the runtime under `~/.synthesis/v5`,
  its config and its git hooks as they reach the protected folders, and so does a write
  through a hard link to one of them made by such a route. Git can also be told to skip
  the commit check without touching its entry points (`git commit --no-verify`, `git -c
  core.hooksPath=…`, or the global `core.hooksPath` changed with `git config --global`);
  the guard holds none of these.
- A compiled look-alike: a compiled program under the name of a command the guard judges by
  name (`bash`, `python3`, `ls`, `cat` and their like), one the agent built, copied or linked
  to, is judged by that name, since the guard reads only that it is compiled (crafted; 22.32
  reads a script under such a name as what it is). So is a look-alike the line makes by a
  route the guard does not read as a write before it runs it (a download, an archive, a
  recursive copy, a program's own write), an installed script of one of the commands that
  really are scripts rewritten where its installer put it in a folder the user writes (npm's
  global folder, a version manager's shims, Homebrew's Cellar), and a look-alike set there,
  or in a copy of npm's or a version manager's layout, under a name that installer provides.
  The guard looks a command up on PATH as its own process has it and as the line sets it
  (with `$(pwd)` put in): a folder another substitution builds into PATH, a name bound to a
  file with `hash -p` or looked up with BSD `env -P`, and a harness's shell that reads a
  startup file, a snapshot, a function or an alias first may run something else under the
  name.
- The first install comes from the harness's plugin folder, and that folder is the agent's to write. Where the
  synthesis home holds no trace of a runtime, the bootstrap in `hooks.json` (and Muse's `session-start.sh`) runs
  `python3 -B -S <plugin>/synthesis/install.py` from PATH while the stable hook is missing, and installs the runtime
  from the folder the harness passes. Once a runtime has been installed, the CLI's install and uninstall refuse
  without the principal's code however they are started, and the guard refuses the plain routes to its folders (`rm`,
  `mv`, `ln`, `chmod` and their like). A program of the agent's own that writes those folders itself (its own copy of
  the installer, with that check taken out) and runs where the guard cannot read it is the first case above: the
  CLI's check binds the runtime's own CLI, not code the agent wrote,
  and even a runtime removed by some other route leaves the state and board its sessions wrote, which keep any session
  start from installing again. But the bootstrap
  runs the plugin folder's own code, and the registration itself (`hooks.json`) is in that folder: an agent that
  rewrites the harness's plugin cache changes what the next session start runs, with or without a runtime, which no
  check in the runtime can stop. A harness still on a plugin from before 5.24.0 runs that release's bootstrap, which
  installs whatever its folder holds whenever the stable hook is missing. Sealing the plugin caches is part of the
  sandbox the principal ruled for on 2026-11-15.
- The guard refuses the shell's and the file tools' ways of removing or changing
  the runtime's own files (`releases`, `current`, `bin`, `git-hooks`) that it can place: it places a command in a
  Codex workdir or a terminal tab's folder by its real path, and judges each command a shell line runs in every
  folder the line may leave it in: each `cd`, `pushd` and `popd` by its text and by its real path (`cd -P`, `set -P`,
  zsh's chase options, review round 3 of 5.23.1, M1), under each CDPATH or cdpath entry the line or the environment
  sets, at OLDPWD, a cdable_vars value or an auto_cd folder, where zsh's `cd old new` leads, and where the shell stays
  when a `cd` may fail: no folder there when the guard looks, or a command before it that may make, remove or move one
  (round 4, Q1). A line whose folder it cannot tell waits for the principal's code (a CDPATH it cannot read, a
  redefined `cd`, a `cd` inside eval, a sourced file or a trap, a function whose body changes folder called anywhere
  but in a command substitution, an alias a command on a line that changes folder defines or one whose value does,
  BASH_ENV or ZDOTDIR). A `cd` outside every function's body is the line's own, which it follows (5.24.0). What it
  cannot see stays open: a function called by a name a variable holds (`f=q; $f`, crafted); a folder another process
  removes or makes between the guard's look and the `cd`; a CDPATH,
  cdable_vars or auto_cd set in the user's shell profile without being exported; and a shell startup file (the
  harness's shell snapshot, `~/.zshenv`) that changes folder before a command runs. The agent can start such a process
  with no code, and a startup file or snapshot written before the guard held them (22.26), or by a route above, still
  runs, so a later command's relative path can land in a protected folder the guard did not place it in.
- The guard holds writes to the startup files and the harness programs, not runs of them. A
  harness program written where the guard never saw it (before the guard held these, by one
  of the routes above, or by the person) runs when a harness, `synthesis doctor` or the release tool
  starts it. Nor are these held: a file a startup file sources (`. ~/.cargo/env`, a plugin
  manager's scripts), a `ZDOTDIR` set other than in the environment or `~/.zshenv`, a
  package of another name that installs a `claude`, `codex` or `gh` command (`npm install
  -g`, `pip install --user`), which writes it unseen, and a folder on the PATH an agent's
  shell builds from its startup files that is neither on the PATH the hook runs with nor
  one of the known places.
- A code for a shell command binds the scripts it runs, not the files named inside them: a
  script that copies a settings file it names only in its own text (`bash install.sh`
  running `cp v5-config.json …`) still runs on its code after that file changes. It closes
  once the reading of the scripts a command runs takes in the files they name.
- What Codex types into a session is judged from the record's last 32 MB: a session started
  further back is judged as one the record does not show, and an interpreter keeps a name
  typed further back that the guard no longer sees. A code-mode script that types into a
  session it names by a variable is not tied to that session. A shell's own state that no
  typed line shows (its startup files, `PROMPT_COMMAND`, a trap set before) is not read.
- An interpreter or a shell that Codex starts on a terminal with no command is not held at its
  start: what is typed into it later is judged line by line, an interpreter's lines with all it
  was typed as its program, so holding every bare start would add a code for little gain (60
  days of records held 17 such starts, all interpreters, all on one day).
- A program of the agent's that loads synthesis by a name no piece of which says synthesis
  as code does (`'synth' + 'esis'`, character codes, a decoded or capitalized string, a
  name read from a file, its environment or its input), through a way of loading the guard
  does not list (a pickle, a mock's patch), as one of the package's modules under its bare
  name from the package's own folder, from a copy of the package under another name, by
  running a file of its own through a path the reader cannot put together, or, on the line
  or its input, through a module of its own that reaches synthesis in a way the reader cannot
  follow without naming one of its writers (a script file's such module waits), is read as
  reaching none of synthesis's writers: it can forge the send ledger's lines, open a send
  window, delete pending grants and requests or plant a deploy record. To grant itself what
  a check a script or the CLI enters itself releases (a send a script makes, a line
  approval, the CLI's send window), it must also record the session's transcript path under
  an environment of its own making, since the recorder takes the harness folders it writes
  beside the path from its own environment, or write a record into a harness's own folders
  (review rounds 4 and 5 of 5.23.1's approval fix; crafted). A shell script built at run
  time (`bash -c "$(…)"`, a script assembled from pieces in a variable) or fetched over the
  network and piped or substituted into a shell (`curl … | sh`, `bash <(curl …)`) is not
  read (nor is a script or module the line writes, below), nor a test placed under a conftest that
  isolates the synthesis home and then undoes it (deleting or re-pointing `SYNTHESIS_HOME`,
  overriding the `tmp_path` fixture), or
  that reaches a writer outside its tests by a name it builds at run time (`getattr` with a name
  joined from pieces, a call through a name it assigns), or through a plugin installed rather
  than its own (plan item 22.21 and its review rounds 1 to 3; crafted). Test runners other than pytest (`unittest` discovery, `tox`,
  `nox`) are ordinary and their tests are not yet read. One that loads synthesis
  through `importlib`, `__import__`, `exec`, `eval`, `compile` or `runpy` by a name or a
  text that says synthesis waits for the principal's code, or is refused on the line.
- The same kind of program, loading the installer by a name the item above leaves unread
  (one built from a piece held in a name), can replace what the installer bound when it
  loaded (`install._approve`, `install._released`) by names it builds at run time, then call
  `install.install` on a folder of its own: the guard passes it, and the runtime becomes
  the agent's (combined review round 1 of 22.8 with 22.18, C1; crafted). One that hands the
  loader a name its literals spell is refused since 22.21. A test holds the open case as an
  expected failure (`tests/test_combined_review_1.py`), so it is seen when it closes.
- A script or module a line writes and then runs is not read. A Python script the line
  writes from a heredoc with any writer but `cat` (`tee s.py <<'EOF'`) and then runs, and a
  module the line writes that a program on it imports (read as it stood before the line, if
  at all), run with no code even when they name synthesis's writers. A shell script the line
  writes from a heredoc is read as that heredoc's text (22.21), a script `cat` writes from one
  as its body (22.22), and a script the line writes with no heredoc (`printf` or `echo` into
  a file) waits as one the guard cannot read. Review round 4 of 22.21 and round 2 of 22.22
  ruled that what a line writes would be read whatever the writer; the merges that brought
  them into 5.24.0 read only `cat`'s heredocs, which narrows those rulings to the planted
  file `tee`, `printf`, `dd` or a written module leaves unread. Reading what each writer puts
  in a file is parked for the sandbox (the run's decision of 2026-11-16 13:57 under rule 8:
  both items shipped as net improvements; the same on main).
- The holds of the rituals' `decay_sweep.py` and `ritual_state.py` run from a plugin cache
  rather than the runtime say the script is more than the guard could read in its time, and
  never point at the runtime's own copy, which 5.24.0's skill text runs and which passes
  (22.15). Only a session on an older skill's text meets them (the integration review of
  5.24.0).
- Three holds of `eslint` and `tsc` in one scratch project on 2026-11-06 did not repeat in a
  bare folder; why they waited there is not known (the integration review of 5.24.0's
  replay; one day, one project).
- A launcher line handed to a bare shell (`bash -lc '<line>'`, as Codex's shell tool hands
  it) passes when the first shell of that name on the harness's PATH is the system's. A
  shell of the agent's put in a folder this user writes, ahead of the system's, after the
  guard passed the line and before the harness looks the shell up, runs in its place,
  unjudged: the guard judges the line, not the harness's later search of PATH (combined
  review round 1 of 22.8 with 22.18, C2's remainder; crafted, a race). Refusing every PATH
  with such a folder ahead of the system's shell would refuse the release from Codex on
  the principal's Mac and on CI's runners. A test holds this as an expected failure.
- A program planted ahead of the real one runs in its place. Every hook that starts a program
  by its name starts whatever the hook's PATH finds first. The launchers put the real git's
  folder and then the system's first on that PATH, so git and the system's own tools cannot be
  planted ahead, but any other program is found further along it, where a folder the agent can
  write may come first. The plan's judge (21.3) is part of this class: it
  runs `claude` or `codex` as the hook's PATH resolves it, and accepts a `command` setting only
  where it resolves to that file or to one in the harness's known install locations
  (`~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`, and the apps' own folders). A program
  planted in an install location the person can write, or in a folder earlier on PATH, counts as
  the harness's own and runs (review round 2 of 21.3; crafted: it needs a program planted in a
  writable folder, and a written setting or a PATH ordered ahead of the real program; a strict
  expected-failure test holds it). Trusting only folders the person cannot write would refuse
  the ordinary install, which lives in `~/.local/bin` or `/opt/homebrew/bin`, and a vendor's
  signature does not fit a program installed as a script.
- A persona footer written as an object nested under a key the signature check skips as
  addressing (a `reply_to` given as an object with a note in it, a calendar guest's
  `comment`) is skipped with that key, so its domain shown in words is not seen. No
  connector puts a message's text there; the strict expected failure
  `test_a_footer_nested_under_an_addressing_key_is_refused` names it (review round 1 of
  22.31; crafted).
- The autopilot count reads only the plan file, which the run writes itself. A run that
  means to slip the count can mark an item of its own `origin: principal`, stamp a
  principal item's close again at a later time, or split one of the principal's items
  into several so that each close counts. A time stamped in an extreme year, such as the
  year 9999, cannot be converted: the count rejects it and names the item, and the check
  stays on (before this, such a stamp ended `cycle` with a traceback and switched the
  turn-end check off). Review round 1 of 22.37; crafted.
- During a stop, the turn-end check names work only when its item is stamped: an item
  added or checked after the count blocker's alert without its time goes unseen. A
  principal request recorded during a stop counts as work after the alert, like any
  other item. The count names an item by its leading number, so dotted numbers collapse:
  it names items 1.1 and 1.2 both as 1. On a plan adopting origins, old checked items
  with no close time are named among those the count could not read, though they closed
  long before. An answer dated up to five minutes ahead of a later alert releases the
  run, inside the tolerance the clock is given (crafted). Review round 2 of 22.37.
- A deploy CLI copied or linked under another name is not read as that CLI. The guard knows
  a CLI's own entry script, run by an interpreter, by the package it sits in under
  `node_modules` (`node_modules/wrangler/bin/wrangler.js`), a `.bin` shim's name and the
  script's own basename, so wrangler's script copied to `w.js` and run as
  `node w.js pages deploy` goes unheld (crafted; the ordinary path to the same script ran a
  production deploy unheld on 2026-11-16, and is held since).

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

## Codex code mode

In code mode Codex runs nearly every call as one `exec` script: JavaScript evaluated in a
V8 isolate with no file system, network or process of its own. Each tool the script calls
on its global `tools` object (`tools.exec_command`, `tools.apply_patch`, an MCP tool)
reaches the PreToolUse hook as a call of its own, under that tool's own name, and is judged
as one; Codex's records show hooks refusing such nested calls inside the scripts' results.

- **The script passes on purpose** and is never read as a shell line. A bare string, or a
  script under `input` or `code`, is known by its signs: the grammar's first-line
  `// @exec:` pragma, a call on the global `tools`, or one of the script's global helpers
  such as `text(` (never a member of another object, such as `process.exit(`). Each helper
  counted works inside Codex, by the tool's own description: on the script's result
  (`text`, `image`, `audio`, `generatedImage`, `notify`, `yield_control`; Codex refuses a
  remote media URL), its session's store (`store`, `load`) or its run (`exit`). No
  shell tool sends those shapes. Under `command`, where a shell's command line also
  arrives, the text is a script only when Codex's own record of this very call (the
  payload's `tool_use_id`, in the rollout `transcript_path` names, inside Codex's sessions
  folder) shows its `exec` tool with this text: a command line can be written to look like
  a script, so how the text looks never decides there. Everything else under the name
  `exec` is judged as a command line: `cmd`, an argv list, or text with no script signs.
- **The browser page tracker reads the calls a script makes.** Codex records them only as
  `item_completed` events (`McpToolCall`: server, tool, arguments, result). The guard
  reads them under the name Codex's hook gives the tool (`workspace-mcp` and
  `github.fetch` make `mcp__workspace_mcp__github__fetch`), and a direct call's event,
  which carries the call's own id, is counted once.
- **The doctor proves that Codex still runs hooks on nested calls.** Its `codex nested hooks`
  line reads Codex's newest rollouts for a hook's refusal in a script's result, which only
  a hook run on a nested call makes, and names the Codex version and the date it proves:
  that this version hooks such calls, not that every one is hooked or whose hook refused.
  It warns, never fails, when it finds none, or only one from an older Codex than the
  newest to run a script.

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
  with the reason. A file tool is judged without the config it cannot read, since
  the folders and settings it guards need none: an ordinary write goes, a write into
  the state folder is refused and the config's own repair waits for the person's
  code. When the hook itself cannot answer (it times out, crashes,
  prints output the harness cannot read, or cannot start because the stable hook
  is missing), Claude Code 2.1.295 or later blocks the call too, since the
  plugin's handler sets `"onFailure": "block"` (5.21.0); Claude Code names the
  hook and says `failed` or `timed out`, and an older one ignores the setting.
  Codex (0.167) and Muse (1.4.20) have no such setting and let a call through
  when a hook exits with an error (Codex's runner marks it failed without
  blocking, in its source at 0.167.2), but block on exit 2 with a reason, so the
  guard's own command, in `hooks/hooks.json`, Muse's `pre-tool-use.sh` and the
  user-level declaration, turns a stable hook that cannot start or crashes into
  exit 2 with one line of reason; a deny exits 0 with its own. Muse's `plugins
  hook test` then gave `should_block: true` for a missing hook and an exit code
  of 1 (2026-11-14). The guard keeps a deadline of its own, `GUARD_SECONDS` (4)
  from when `pre_tool_use` starts, before it loads the guards (5.21.1): a timer
  raises past every handler in the guard's work, `subprocess.run` kills the git
  or other child it waits on, and the call is held with the reason, printed once
  the timer is cancelled. So a slow repository read or a lock answers closed in
  every harness inside its 5-second limit. What still lets a call through in
  Codex and Muse is a hook that uses up their 5 seconds before the timer is set:
  Python slow to start by more than about a second, under heavy load or on a
  stalled disk. Muse reads only its
  own manifest, which refuses the field, so it is set in `hooks/hooks.json`
  alone, where Codex reads it and hashes the hook without it. UserPromptSubmit and
  SessionStart keep the default: holding a person's prompt or a session's start
  on a hook failure costs more than it protects.
- **Stop fails open**, because a turn-end check that fails closed loops
  forever. The reply check sends a reply back at most once in a row, and an
  autopilot run is asked to continue at most `autopilot.max_continuations`
  times in a row (3 by default) before the session is allowed to stop.
- **SessionStart never blocks a session.** It installs only a first runtime, and a
  refused bootstrap says why on stderr; a runtime older than the plugin the harness
  loaded is named once and reported by the doctor, never replaced there; a ritual
  line that cannot be computed is left out.

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
