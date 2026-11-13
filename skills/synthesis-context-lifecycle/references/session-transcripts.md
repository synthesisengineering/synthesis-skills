# Agent session transcripts

The project records (CONTEXT.md, REFERENCE.md, session logs) are the curated memory: small enough to load, written
by an agent at the moments it chooses. Underneath them is the full conversation, which each harness keeps in its own
folder and format. Claude Code deletes its copies 30 days after a session's last use unless `cleanupPeriodDays` is
set, Codex is moving its rollouts into a database, and Muse keeps an event log. The transcript archive keeps every
session in one form that outlives each of them.

## What is kept

`synthesis sessions export` reads each harness's native transcript past the point it already exported and writes:

```
<synthesis home>/sessions/<workspace>/<YYYY-MM>/<harness>-<session>/
    meta.json              harness, session, native file, workspace folder, projects, models, first and last
                           record times, what was skipped and how often
    transcript-0001.jsonl  one record per event, numbered by `seq`; a new segment starts past 8 MB
    media/<sha256>.png     each image or document once, named by its hash
<synthesis home>/sessions/<workspace>/blobs/ab/<sha256>.txt
                           a long tool input or output, or long injected text, once for the whole workspace
```

Record kinds: `session`, `user` (the principal's own prompt, and nothing else), `brief` (a prompt one agent wrote
for another: a sub-agent's task, a spawned thread's instructions, a message from another session), `assistant` (a
reply, with its model), `reasoning`
(the model's visible reasoning; encrypted reasoning is counted, not kept), `tool_call`, `tool_result`, `system`
(hook output and injected context, each distinct text once), `compaction` (the harness's summary when it compacted),
`meta` (titles, links, modes, cost totals). A tool input or output, or injected text, longer than 2,000 characters
keeps its first 1,000 in the record and the whole text in a blob (`text_blob`, `text_chars`); `--whole` reads it back.

What is left out: copies the harness keeps of the same content (Claude Code's request blobs and `toolUseResult`,
Codex's UI events and the history replayed into each compaction), the copy of the whole conversation Codex hands its
approval reviewer (the reviewer's verdicts are kept; `meta.json` names its `role` and `parent`), Claude Code workflow
run journals, file backups, and sync markers. `meta.json` counts each. Text automations, the harness or the interface
put in the prompt slot (heartbeats, scheduled-task prompts, recommended plugins, UI actions) is `system`, not `user`.

A sub-agent belongs to the workspace its parent session started in, even when it worked in another folder; `cwd` in
`meta.json` keeps where it actually ran. After an adapter changes, `synthesis sessions export --rebuild` moves the
archive aside (to `<synthesis home>/archive/sessions-<time>/`, never deleted) and exports everything again.

## Secrets and privacy

- Every string is masked with the commit check's credential patterns, plus private key blocks and bearer tokens:
  `[redacted <kind> <sha256 prefix>]`, so two copies of one secret still match without either being readable.
- The workspace comes from the session's working folder (config `workspace_roots`, default `~/workspaces/*`), so a
  client workspace's sessions stay with that workspace and leave with it. A session outside every workspace goes to
  `other`.
- The archive is local. What leaves the Mac is chosen per workspace (below); a session outside every workspace never
  leaves (R10.4).
- Only the exporter writes the archive: the guard refuses file tools and shell writes there, so it stays a faithful
  copy of what each harness recorded.

## When it runs

Never in a hook: R8.3 bars a hook from writing per-call state that grows, and nothing needs a copy per turn, because
each harness writes its own transcript to disk as the session runs. The copy is made where it is read:

- `synthesis resume <project>` exports the last two days, then shows the project's latest prompts and replies from
  every harness. That is how work moved from one harness to another carries the conversation, not only the records.
- `synthesis handoff` and the day-end ritual run `synthesis sessions sync`, which exports first; the conversations
  leave the Mac at the same moments as the records, so the two never disagree about where the work stood.
- Anyone may run `synthesis sessions export` (add `--all` for everything on the Mac) before reading or citing.
- On a Mac where the onboarding setup scheduled it (`setup.py plugin --sessions-export`), a LaunchAgent runs
  `synthesis sessions export --all --scheduled` and `synthesis sessions sync` every hour and at login, so a
  transcript is copied whether or not any session remembers to. `--scheduled` marks a run as the schedule's
  own; it is the job's flag and no one else's. `synthesis doctor` fails when that schedule is not loaded,
  when it runs another command than this install's (one label holds one schedule, so another install's setup
  replaces it; the doctor names what it runs), when no export has finished in a day, or when none of the
  schedule's own has: an export a session ran says nothing of whether the job still runs (2026-11-11: until
  then the archive had no trigger of its own, and a transcript that no session exported within two days was
  skipped).
- An export that could not copy a transcript (it could not be read, or held a row its adapter does not expect)
  goes on to the others, says so in its report and names it in the stamp it leaves, with why and when it last
  tried, and so does the export a sync runs first. On any Mac `synthesis doctor` then fails,
  with how many and the first reason, until a run copies each one: `synthesis sessions export --all` tries them
  all, and an export of the last two days or of one session clears only what it copied.
- A folder the search for transcripts cannot list is named in the stamp the same way, as `<harness> <folder>`
  with why: a harness's transcript folder, a project's, a day's, or the folder above them, closed to the process
  that runs the export. It may hold a transcript of any workspace written on any day, so the doctor fails, the
  listing of every day stops, and no transcript of that harness is called gone while it stands. It clears when a
  run of everything lists the folder or finds it removed. A transcript the search can name and not look at is
  named as one not copied (2026-11-12: the search passed over a folder closed to it, the run found nothing there
  to copy and stamped complete).
- A transcript the harness removed before any run copied it can no longer be copied. A run of everything says
  so, the stamp keeps its name with when its copy last failed and when it was found gone, and the doctor keeps
  failing. What it held is not in the archive, and only the principal can accept that:
  `synthesis sessions export --lost <session>` clears it. Run by an agent, it asks for the principal's approval
  code first; typed by the principal in a terminal of their own, it needs none. It refuses a transcript that is
  still there, that the harness only moved, or whose harness has a folder that cannot be listed, and it appends
  each loss it clears to `<synthesis home>/sessions/.state/lost.jsonl`. `--rebuild` carries the stamp and that
  file into the new archive.
- `synthesis sessions export` says in its exit status whether everything it was asked for was copied:

  | Status | What happened |
  |---|---|
  | 0 | Everything asked for was copied, also when nothing was new. An export of two days or of one session exits 0 when what it was asked for was copied, whatever an earlier run left in the stamp. |
  | 1 | Something was not copied: a transcript this run could not copy, a folder it could not list, a transcript a run of everything found gone and not yet cleared, or an archive that could not be written. The stamp is left first; then one line on stderr says how many are not copied and points to `synthesis doctor` and the stamp. An archive that cannot be written leaves no stamp, and the line says why instead. |
  | 2 | `--lost` only: it needs the principal's code, or one is on record that the session's transcript does not show the principal typing. Nothing is cleared. |

  `--lost` exits 0 when it clears a loss, and 1 for a transcript the stamp does not name or one not known to be
  gone. The scheduled job runs `sessions sync` after the export whatever the export's status.

## Copying each workspace's conversation off the Mac

Config `sessions_repos` maps each workspace to the checkout of its own private sessions repo:

```json
"sessions_repos": {"personal": "<checkout of ai-sessions-personal>",
                   "client-a": "<checkout of ai-sessions-client-a-private>"}
```

`synthesis sessions sync` writes each session's `session`, `meta`, `user`, `brief`, `assistant`, `reasoning`,
`compaction` and `tool_call` records into `<repo>/<YYYY-MM>/<harness>-<session>/` (same `seq` numbers, so a citation
reads the same on every Mac), masked again, with a `meta.json` that drops local paths. Tool output, long text and
images stay in the local archive. Each month touched is one commit; then it pulls with rebase and pushes. The
commit check scans every commit, and a refusal stops that workspace's sync with the reason (`FAILED <workspace>:
...`), recording nothing as synced. The files are rewritten whole from the archive each time a session changes, so
the same records always give the same bytes: closed segments never change, and a rebuilt archive simply corrects
them.

Another Mac that has cloned a sessions repo reads its sessions with the same commands (`list`, `recent`, `show`,
`search`); a session this Mac also has is read from the local archive. `synthesis doctor` reports each repo: cloned,
synced within two days, and a warning at 3 GB, before GitHub's 5 GB advice.

A sessions repo belongs to its workspace's deletion unit: deleting the workspace's data deletes the repo and
`<synthesis home>/sessions/<workspace>/` (see [deletion-units.md](deletion-units.md)).

## Reading and citing

```bash
synthesis sessions list --project <id>            # sessions, newest first, with their projects
synthesis sessions recent --project <id>          # the latest prompts and replies, any harness
synthesis sessions show <session> --kinds user,assistant
synthesis sessions show <session> --whole         # tool output and injected text in full
synthesis sessions search "<pattern>" --project <id>
```

Cite the record behind a decision or quote as `<harness> <session> #<seq>` (for example `codex 01a1b2c3 #4120`) in a
session log or lesson, and open it with `synthesis sessions show <session> --seq <n>`, which prints that record
whole and three either side, each cut at `--width` characters. Write as much of the session's id as the commands
print for it (`prompts`, `recent`, `search` and `resume`): eight characters, or more where two sessions begin
alike. Characters that two sessions share name neither: such a citation does not count, and `show` asks for more
of the id. What is printed for a main session never names the sub-agents it started, whose ids begin with its
whole id and are printed whole; `meta.json` gives a sub-agent `role: subagent` and its `parent`. A quote or
attribution read from the archive in the current session has a tool output behind it, as quote provenance requires. One entry that covers a stretch of a session cites it as a range:
`claude-code d20ab7c4 #1500-1560`. `--json` prints one object per line for tools such as the Console. Keep the conversation out
of CONTEXT.md and project folders: it would break their size budgets (R1.5) and flood every search of the project.

## What the principal asked

Every prompt the principal typed is in the archive as a `user` record. A record accounts for one by citing it,
alone or inside a range. What no record cites is a request, a decision or a correction that reached no record:

```bash
synthesis sessions prompts --workspace <W> [--date YYYY-MM-DD]                    # each prompt of that day
synthesis sessions prompts --workspace <W> --records <folder of records> [--json]  # only those no record cites
```

The listing first copies every transcript written since that day began. While one that may hold that day's
prompts in that workspace is not copied, it lists nothing and exits 2, since an archive that is not current cannot
say what was typed: one this run could not copy, one an earlier run could not and none has since, or one that is
gone and the principal has not cleared (`synthesis doctor` says how each is cleared). A transcript filed under
another workspace, or last written before that day began, does not stop it, and neither does a sub-agent's or a
reviewer's, which holds an agent's briefs and no word of the principal's. While another export holds the
archive it waits for it, and it lists nothing when the archive cannot be written. `--date` takes a date, and
anything else lists nothing.

Each line names a prompt by what opens it:
`<harness> <session> --seq <n>  HH:MM  <the prompt's first words>`, with as much of the session's id as tells it
from the archive's other sessions (eight characters, or more where two begin alike). What follows the harness is
what `synthesis sessions show` takes. Then one line counts, and says where it looked:
`2 of 31 prompts on <day> in <W> are cited by no record under <folders>` (exit 1), or
`all 31 prompts ... are cited by a record under <folders>` (exit 0).

**That name is not a citation.** The listing, its JSON answer and the list the day-end record prints when it
refuses all name a prompt with `--seq`, and a record cites one with `#`: `<harness> <session> #<n>`. So a copy of
what they print accounts for nothing, however it is kept: pasted, quoted, made into a checklist or a table, or
saved as data. Two things keep the listing's line from holding a citation by another road. In a prompt's own
words, which the line prints, every number is set apart from its `#` (`PR # 291`, `c1 # 12`), whatever session
or day it names. And every line `show`, `recent` and `search` print begins with `[<harness> <session>]`, so a
`#<n>` never stands at the head of a line, where a session's id at the end of the line above would make a
citation of it. `show` prints the prompt itself as typed.

The citation is written by whoever writes the record, and it counts where it stands: in a sentence however it
wraps, on a line of its own, in a heading, a cell of a table, a footnote or a field of a JSON or YAML record. (Until
2026-11-13 the listing printed citations, and rules tried to know its saved output by its shape. Four reviews each
found ordinary shapes those rules did not know, where a list of what was open closed the day.)

A citation claims that its record accounts for the prompt, and nothing can check that it does. Write one only
where the record says what became of the prompt. To note that prompts are open, give their number or their names
as the listing prints them.

A citation names one session: its id in full, or eight or more of its first characters that no other session
listed shares. Its number has at most nine digits. A range (`#12-40`, `#12–40`, `#12 to #40`, `#12 through #40`)
has its dash on the line of its first number and ends in a number of its own, which carries its `#` unless the
dash is tight: a list item on the next line, a date or a time after a dash, and a number after a dash set off by
spaces or after a word (`#12 — 2027 planning`, `#5 to 30 people`) end no range. A string that carries an escape
is read as the text it holds, so a dash an encoder escaped still joins its range.

`--records` reads the files under that folder that end in `.md`, `.markdown`, `.txt`, `.json`, `.jsonl`, `.yaml`
or `.yml`, whatever the case of the ending, and changed since the day began; repeat it for more. On a day with no
prompt it reads none. It reads every folder under the one named, except:

- a folder whose name begins with a dot, and `node_modules`;
- a folder reached through a link (name such a folder itself);
- a sessions repo, and this Mac's archive: they hold the conversations, and so every citation an agent wrote,
  tried to write or talked about.

A folder that is not there or may not be listed, a record that may not be read, and a folder that is a sessions
repo or lies in one are each named, and nothing is listed (exit 2): read as empty, a folder would leave every
prompt open with no word of why. A file that is no regular file, a link that leads nowhere or back to itself, and
a folder removed while the records are read are passed over.

`--json` prints
`{"workspace", "date", "prompts", "open": [...], "records": [...]}`; the day-end record runs it itself. `open`
holds the names as the listing prints them. Without `--records` nothing was held against any record, and the
answer has `listed` in place of `open`. `records` names each folder as the listing read it, by its real path:
`~` expanded, links followed, and `..` taken from where a link leads, never as written. The record reads the
folders its config names the same way before it compares, and refuses one the config writes from no fixed place
(`kb/records`, `./records`): it would be read from wherever the day-end runs. An empty `--records ""` names no
folder: like one that is not there, it is said and nothing is listed.

For each prompt left: open it (`synthesis sessions show <session> --seq <n>`), and where its substance is
already in a record, cite it there; where it is not, write the record first, then cite. A prompt that needs no
record (a greeting, a go already recorded with its question) is cited in the session-log entry for that stretch,
which says so. The citation is the agent's statement that the record covers the prompt, and the principal can
open either. Each session does this for its own prompts when it writes its session log, so the day-end finds
few left. A workspace turns the day-end check on in the ritual config (see the daily rituals' day-end).
