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
| `add` | `<number>  <what>  (remove: <how>); when it is gone: teardown.py done <number>` | 0; 2 when what or how is left out |
| `list` | one line for each item: its number, when it was added, what, how, and its test; or `nothing a test set up is left in place` | 0 |
| `done <number>` | `taken off: <number>  <what>` | 0; 1 when no item has that number |

- **Add before you make the thing,** not after: a test that stops halfway has still made it.
- **`--remove` is words,** for whoever takes the thing down: the setting to delete, the key to revoke, the command
  to run. Nothing runs them.
- **`done` takes one number.** Take the thing down first, then take it off the list. Nothing is taken off in bulk.
- **Ending a test means running the list the same turn:** `list`, take each item of that test down, `done` each.

The list is `<synthesis home>/teardown.jsonl`, one JSON object a line. A line written into it by hand is kept and
shown as it is.

## What the doctor says

`synthesis doctor` reads the list at every run, in whichever session:

```
warn  teardown  2 things a test set up are still in place, the oldest for 30 hours: 1: the client's entry for the test address (delete it in the client's settings); 2: a key marked for removal (revoke it in the console). Take each down, then `python3 <synthesis-agent-guardrails>/scripts/teardown.py done <number>`
```

It shows the three oldest and says how many more there are. With an empty list it says
`ok    teardown  nothing a test set up is left in place`.

## What it does not do

- It refuses nothing. A test that is still running has items on its list rightly, and the oldest's age is what
  tells a running test from a forgotten one.
- It runs no command a line names.
- It does not know whether a thing is really gone: `done` is the word of whoever removed it.
