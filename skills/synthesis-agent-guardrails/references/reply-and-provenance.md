# The reply check and the provenance scan

## Contents

- [Why advice goes back to the model, not to stderr](#why-advice-goes-back-to-the-model-not-to-stderr)
- [The reply check](#the-reply-check)
- [The file-link rule](#the-file-link-rule)
- [The provenance scan](#the-provenance-scan)

## Why advice goes back to the model, not to stderr

The 1.x detectors (lazy shortcuts, bare file names, quote provenance, long sessions, date
reminders) ran as hooks that exited 0 and wrote to stderr or a log file. That output most
likely never reached the model, and nothing read the logs (449 rows of shortcut
detections, 110 of bare file names). v5 keeps the checks that matter where the model
reads them: the Stop hook returns a revise-once decision the harness hands back to the
model, and the provenance scan runs at day-end where the agent reads its output. The
date reminders (after four hours, and before writing a dated record) are replaced by
requirement R1.2: the brief re-injected at session start and after compaction is to carry
today's verified date. That line is not yet in `synthesis/hook.py`; until it is, re-anchor
the date with synthesis-checkpoint before writing a dated record in a long session.

## The reply check

`synthesis/reply_check.py`, run by the Stop hook on the final reply of a turn. It sends
the reply back once with `Before this reply goes out, revise it: ...` when the reply:

- uses lazy-shortcut phrasing (the built-in list, plus `shortcut_phrases` from config):
  do the work or name the real blocker. A phrase inside quotation marks or code is exempt,
  so naming a rule does not trip it;
- announces a wait of the session's own that nothing is armed to end, read clause by clause
  (a clause ends at a sentence's end, a semicolon or a line's end; [what it reads as a
  wait](#what-the-reply-check-reads-as-a-wait) has the forms and what passes). `wait_phrases`
  in the config adds phrases (synthesis-waiting has the rule and the commands);
- quotes someone (said, wrote, replied, ...: "twelve or more characters") with words that
  appear nowhere in this session's transcript: quote only what a tool surfaced;
- names a file without a clickable absolute-path link, when `reply_file_links` is true;
- follows a calendar write this turn (create, update, manage, move or delete an event, or an RSVP) that no
  calendar read came after: read back the principal's calendar for today and every date the change touched
  before reporting. A write the guard refused does not count. On 2026-10-27 a series moved to a new hour
  brought back a meeting canceled at the old hour, and only the principal looked. It reads the tail of a Claude
  Code transcript; other harnesses' records are not read for it.

It never sends a reply back twice in a row and lets the reply through on any internal
error: a turn-end check that fails closed loops forever. When a reply is sent back, revise
exactly what it names.

### What the reply check reads as a wait

Sent back when nothing is armed:

- `I'm` or `we're waiting` or `awaiting`, through adverbs and words between commas
  (`currently still`, `I am, however, still waiting`), and `and am waiting` after `I`;
- `I'll`, `I'm going to`, `I need to` or `I have to wait`, through helping verbs (`continue
  to wait`, `keep waiting`); `hold`, `pause` or `stand by` with `until`, in either order;
- a future with a verb of carrying on (continue, resume, proceed, pick up, finish, merge,
  confirm, follow up, report back, get back, let you know, update you) and `once`, `when`,
  `after`, `until`, `as soon as` or `the moment`, in either order;
- the session's own future with any verb before an event still to come: `once` or `as soon
  as` and something other than `I` or `we` (`I'll send it as soon as the run finishes`),
  `when` or `after` and an arrival (`when the second pass comes back`), `when it's done`;
  and the same with the event stated first (`when the bank confirms, I'll record it`);
- a subject left out: `Will merge once the checks pass`, `I pushed it and will merge once`;
- a sentence that opens with `Waiting for`, `Waiting on`, `Waiting until`, `Waiting to
  hear`, `Awaiting`, `Holding ... until` or `Resuming when`.

Passes:

- an explanation, where the phrase is the subject of its sentence: `Waiting for a lock
  blocks a thread`, `Waiting until Friday is risky`; software's own behavior (`the worker
  resumes once the queue has items`); a rule (`when a build fails, I'll read the first
  error`); advice (`we'll want to rotate the key once the audit ends`); a wait refused, in
  the past, or as a count (`once a day`, `as soon as possible`);
- carrying on, or a hold, that runs to the session's own next step: `I will resume after I
  update the snapshots`, `I'll hold the merge until I've rerun the suite`. After the
  conjunction, `I` or `we` with a verb of receiving, or with `can`, is still an event to
  come (`once I have it`, `when I hear back`, `when I can reach it again`);
- text in quotation marks (double, single or curly), in inline code, in a fence of
  backticks or of tildes, and on a quoted line. A name set aside this way still counts as
  the thing awaited: `still waiting on` and a job's name in code is a wait;
- a clause that awaits the principal's own move, wherever in the clause it stands: `you` as
  the one who acts and not in the past (`until you choose, I'll wait`), an act of theirs or
  a thing only they supply as the thing awaited (`your approval`, `your code`, `your dates`,
  `your answer is the only thing I'm awaiting`), the turn handed over (`it is your move`), a
  question they answer (`waiting to hear which date works for you`);
- a short wait that points back (`I'll wait`, `I'm waiting on that`, `until I have it`)
  when the clause before it names their move, asks them for something or ends in a
  question mark;
- `your` and a thing named in a few words straight after the wait's own word (`waiting on
  your sign-in retry`, `waiting on your two answers before I write the log`);
- a reply that hands them the turn, whatever else it waits for: it ends by asking them; it
  offers an approval code to type (`approve 3b90b7`, `Code: 2f9a01`, a code as a label
  before a colon); it asks them to act in so many words (`Say go and it's out`, `Tell me
  when it's done and I'll confirm`, `only you can`, `one step from you`). A request is one
  put to them: after `and`, `then` or a comma, one more verb of somebody else's asks them
  nothing (`The worker will restart and send me its result`, `She'll review it and let me
  know`, `I asked the vendor to check and tell me`). A code named as used, spent or
  replaced offers nothing, and the words straight after it or straight before it are what
  is read: `code 1abcde was consumed earlier`, `(3e7b10) has expired`, `you typed approve
  4a0c2d at noon`, `don't use the old codes`. A spent code beside one that is offered
  leaves the offer standing;
- the text between a `BEGIN` line and an `END` line, which is set aside as quoted text is,
  whether it is a message staged for their go or a record. The block excuses nothing
  outside it: `I'm waiting for the bank to respond` after one is sent back. Beside a
  block, a wait for it to be sent or to go out (`Once it's sent, I'll log it`, `when it
  goes out`) awaits their go and passes;
- a reply that says, in one sentence of its own, that nothing wakes this seat until the
  principal prompts it. That is the last resort the check's own message names, so a reply
  that has said it is not sent back to say it: `Nothing wakes this seat until you prompt
  it`, `This seat stays idle until your next message`, `I won't see it land until you prompt
  me`, `Nothing happens here until you prompt me`. It has to be this seat, in the present,
  and their prompt: `nothing wakes her session`, `nothing woke this seat` and `nothing wakes
  this seat until the build finishes` excuse nothing;
- a list of open loops, which names what is outstanding and announces nothing: a label
  with no subject before a colon (`Waiting on others: ...`); such a label in a heading or
  a table cell (`## Awaiting the vendor's go`, a cell that reads `awaiting re-auth`); a
  wait with no subject after a label, a dash or a semicolon inside a sentence (`- The venue
  — sent; awaiting their pick`); and `we` with a count or a pointer before the colon, where
  what is awaited is listed after it (`We're waiting on two answers: ...`, `What we're
  waiting on others for: ...`). A wait in the first person is read wherever it stands, in a
  heading, in a table row and before a colon: `## I'm waiting on CI`, `| State | I'm
  waiting on CI |`, `Will merge once it is green` in a cell and `We are waiting for the
  required pipeline: no further work is possible` are sent back;
- a rule for next time (`from now on`, `going forward`, `next time`, `whenever`, `every
  time`), where the phrase governs the wait's own clause: it opens the sentence or a clause
  of it, and no new clause of the session's stands between it and the wait (`From now on,
  when a send fails, I'll finish it through the browser`). The phrase somewhere else
  explains nothing: `The proposed change going forward is documented, and I am waiting on
  the external review` is a wait;
- an armed wait: a live `synthesis wait` of the session; an autopilot run it owns; in
  Claude Code, background work the session started that has not reported yet (an agent, a
  shell command, a workflow, a monitor), since the harness wakes the session when it
  does. That is read from the last four megabytes of the transcript. Work is started by
  the harness's own tool-result entry: a `user` entry, a result that opens with the launch
  line, a call id that is a string. It is ended by the harness's own notification naming
  that call: a `user` entry that is a task notification by its origin or opens with the
  notification tag, a queued command or a queue operation that opens with it. A copy of a
  launch in any other kind of entry starts nothing; the tag in the assistant's words, in a
  tool's output or quoted inside other text ends nothing; a malformed record or a path that
  cannot be read holds nothing, and the reader does not raise. Work launched before those
  four megabytes is not seen, and a wait beside it is sent back once: say then what is
  out.

A thing that belongs to the principal is not their move. `your review bot`, `your code to
compile`, `your registrar to release the domain`, `your lawyer's comments`, `the service to
answer your review request`, `the hold on your card` and `per your instructions` leave a
wait on software or on someone else as the session's own. What they already did exempts nothing (`your review
is filed and I'm waiting on the pipeline`, `after you approved`).

The check reads patterns, not meaning. Each fresh list written against it has found forms
it did not know, most of them waits said with a verb or a conjunction outside these lists;
`Standing by for` is one that is left to `wait_phrases`. A reply that passes is no proof
that nothing is awaited: the rule in synthesis-waiting binds whether or not the check fires.

What it is measured against is recorded replies, not invented ones. Run over thirty days
of turn-ending replies on one machine (4,443 delivered, November 2026), the forms above
read 537 as a wait; in 450 the harness held background work, and 87 were sent back, about
three a day. Of those, read one by one, three in four were the session's own wait with
nothing to end it. Most of the rest awaited a step of the principal's said in words the
check does not read (`once it's sent, I'll read it back`, after a send they have yet to
approve). What it lets pass on purpose: a wait in a reply that also asks the principal
for something, and a wait with no subject written after a label, a dash or a semicolon.

## The file-link rule

The principal's rule: every file referenced in a reply is a markdown link with the full
absolute path, `[name](/absolute/path/to/name.md)`. A bare name or a relative path cannot
be clicked, and it was broken repeatedly while it was only a written rule.

- Flagged: a name with a file extension (md, py, js, ts, tsx, jsx, mjs, json, yaml, yml,
  toml, sh, bash, zsh, html, css, astro, txt, csv, sql, rb, go, rs, java), with or without
  folders or a `:line` suffix, including one that ends a sentence; and a markdown link
  whose target is relative (`docs/plan.md`, `~/notes/a.md`).
- Not flagged: anything inside inline code or a fenced block (quoting shell or source is
  not a reference), URLs, links to absolute paths, `#anchors` and web or mail links, and
  framework names such as Node.js.
- The 1.x detector also skipped names the user had just typed and looked up
  hyphenated slugs on disk. v5 drops both: the Stop payload carries only the reply, and a
  disk search does not belong in a per-turn hook.

## The provenance scan

The origin: an agent made up a chat message by changing the last digits of a real
message's timestamp, and the fake landed in transcripts and project context as if it had
been read. The scan finds that shape after the fact, over what the day wrote.

```text
$ python3 <synthesis-agent-guardrails>/scripts/provenance_scan.py --since 2026-10-05 ~/workspaces/<w>/ai-knowledge-<w>
~/workspaces/<w>/ai-knowledge-<w>/projects/demo/CONTEXT.md: timestamp 1759700000.123457
provenance scan since 2026-10-05: 1 unsourced; read 6 records and 261 session logs
```

- Records: each path given that is a file, whatever its name or suffix (a YAML plan
  named outright is read); the `.md`, `.txt`, `.jsonl` and `.json` files under each folder
  given that sit in `transcripts/`, `daily-plans/`, `ritual-workers/`, `drafts/` or
  `projects/<id>/sessions/`, or are a project's `CONTEXT.md` or `REFERENCE.md`, with hidden
  folders and `node_modules` not entered; and every regular file under each
  `--records <folder>`, at any depth and in hidden folders too, with only `.git` left out,
  for a plan folder a workspace keeps under another name. A link to a folder is not
  followed. Each must have changed since the date. The last line says how many records
  were read: a count that leaves out the day's plan means the plan's folder was not given.
- A record that cannot be opened, and a folder that cannot be listed, is printed as
  `<path>: unreadable (<why>)` and counted in the last line (`1 unsourced, 2 unreadable; read 6
  records ...`). A file that is not text (bytes that are not UTF-8, or a NUL byte: an image, a
  database, the folder file a Mac keeps) holds nothing an agent wrote as text; the last line
  counts it (`...; 3 files that are not text were not read`) and it fails nothing. An unreadable
  record was not checked: read it another way.
- What is checked: what a record gained since its last commit before the date: every
  Slack timestamp (`1234567890.123456` or the `p1234567890123456` permalink form) and every
  attributed quote of twelve or more characters.
- Sources: harness session logs changed since the date (`~/.claude/projects` and
  `~/.codex/sessions`, or each `--sources DIR`). Only what a tool returned or a person
  typed counts. The agent's own words, its write calls and a write's echoed result never
  source themselves. Each log is searched as raw bytes first, and only the lines holding a
  candidate are parsed, so a day of logs reads in seconds.
- Exit 0 when every record was read and everything is sourced, 1 when something is
  unsourced or unreadable, 2 when no session log folder exists or a path given does not
  exist. It reads only.
- An unsourced line is a lead, not a verdict: open the source (the synced transcript, the
  channel) and either cite it or correct the record. Never "fix" it by finding a similar
  message.

Tests: `skills/synthesis-agent-guardrails/tests/test_provenance_scan.py`.
