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

Cite the record behind a decision or quote as `<harness> <session8> #<seq>` (for example `codex 01a1b2c3 #4120`) in a
session log or lesson, and open it with `synthesis sessions show <session8> --seq <n>`, which prints the record and
three either side. A quote or attribution read from the archive in the current session has a tool output behind it,
as quote provenance requires. `--json` prints one object per line for tools such as the Console. Keep the conversation out
of CONTEXT.md and project folders: it would break their size budgets (R1.5) and flood every search of the project.
