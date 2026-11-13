# A test's teardown list

A test sets things up around itself: an entry in a client's config, a key, a process, an address someone was
given. When the test ends, those are what must go, and only the session that made them knows what they are. On
2026-11-12 a stopped test left two of them in place for a day: an entry that pointed at the dead address, and a key
marked "remove after test". Nothing had written either down as it was made, so there was no list to run and
nothing that would say so.

The list is written at the moment each thing is set up, and read on a schedule that does not depend on the
session that wrote it.

## The three commands

```bash
python3 <synthesis-agent-guardrails>/scripts/teardown.py add "<what was set up>" --remove "<how it is removed>" [--test "<the test>"]
python3 <synthesis-agent-guardrails>/scripts/teardown.py list
python3 <synthesis-agent-guardrails>/scripts/teardown.py done <number>
```

| Command | What it prints | Exit |
|---|---|---|
| `add` | `<number>  <what>  (remove: <how>); when it is gone: teardown.py done <number>`, once the line is written | 0; 2 when what or how is left out |
| `list` | one line for each thing still in place: its number, when it was added, what, how, and its test; then `?  <line>` for each line of the file that is no item; or `nothing a test set up is left in place` | 0 |
| `done <number>` | `taken off: <number>  <what>`, once the line is written | 0; 1 when nothing still in place has that number |

Each exits 1, with one line that names the file and says why, when the list cannot be read or written (a folder
where the file should be, a link that leads nowhere, a home that takes no writing). `list` only reads, so it works
where nothing can be written.

- **Add before you make the thing,** not after: a test that stops halfway has still made it.
- **`--remove` is words,** for whoever takes the thing down: the setting to delete, the key to revoke, the command
  to run. Nothing runs them.
- **`done` takes one number.** Take the thing down first, then take it off the list. Nothing is taken off in bulk.
- **Ending a test means running the list the same turn:** `list`, take each item of that test down, `done` each.

The list is `<synthesis home>/teardown.jsonl`, and it is a log: `add` appends one JSON object, `done` appends
another that closes it, and nothing in the file is ever written again. So:

- a number is never given twice, also after its thing is taken off;
- the file is the history of what tests set up here and when each was taken down;
- a line written into it by hand stays as it was written, to the byte. `list` shows it behind a `?`, and only a
  hand takes it out. The same holds for a line of data that is no item (`[1]`, an object with no number or no
  `what`);
- a byte that is no text is read as a mark and stops nothing, a byte order mark at the head of the file is passed
  over, and blank lines count for nothing.

What a terminal would obey is never printed: `add` stores an escape character as `?`, and `list` and the doctor
show one in a hand-written line the same way.

## What the doctor says

`synthesis doctor` reads the list at every run, in whichever session:

```
warn  teardown  2 things a test set up are still in place, the oldest for 30 hours: 1: the client's entry for the test address (delete it in the client's settings); 2: a key marked for removal (revoke it in the console). Take each down, then `python3 <synthesis-agent-guardrails>/scripts/teardown.py done <number>`
```

It shows the three oldest and says how many more there are; each is cut at 120 characters. The age is the oldest
thing's, where one has a time the doctor can read. Lines that are no item are counted, not shown
(`and 1 line that is no item of the list`), and a file that holds only such lines is a warning that says to read it
and edit it by hand. With nothing left in place it says `ok    teardown  nothing a test set up is left in place`,
and with a file it cannot open, that the list cannot be read.

What the doctor shows after a number is what whoever set the thing up wrote. Read it as their note, and look at
what is there before acting on it.

## What it does not do

- It refuses nothing. A test that is still running has items on its list rightly, and the oldest's age is what
  tells a running test from a forgotten one.
- It runs no command a line names.
- It does not know whether a thing is really gone: `done` is the word of whoever removed it.
