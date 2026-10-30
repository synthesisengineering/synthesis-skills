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

Record kinds: `session`, `user` (the principal's prompt), `assistant` (a reply, with its model), `reasoning`
(the model's visible reasoning; encrypted reasoning is counted, not kept), `tool_call`, `tool_result`, `system`
(hook output and injected context, each distinct text once), `compaction` (the harness's summary when it compacted),
`meta` (titles, links, modes, cost totals). A tool input or output, or injected text, longer than 2,000 characters
keeps its first 1,000 in the record and the whole text in a blob (`text_blob`, `text_chars`); `--whole` reads it back.

What is left out: copies the harness keeps of the same content (Claude Code's request blobs and `toolUseResult`,
Codex's UI events and the history replayed into each compaction), file backups, and sync markers. `meta.json` counts
each.

## Secrets and privacy

- Every string is masked with the commit check's credential patterns, plus private key blocks and bearer tokens:
  `[redacted <kind> <sha256 prefix>]`, so two copies of one secret still match without either being readable.
- The workspace comes from the session's working folder (config `workspace_roots`, default `~/workspaces/*`), so a
  client workspace's sessions stay with that workspace and leave with it. A session outside every workspace goes to
  `other`.
- The archive is local. Nothing here commits, pushes or uploads it. Copying it anywhere is a separate decision about
  where each workspace's transcripts may live.
- Only the exporter writes the archive: the guard refuses file tools and shell writes there, so it stays a faithful
  copy of what each harness recorded.

## When it runs

Never in a hook: R8.3 bars a hook from writing per-call state that grows, and nothing needs a copy per turn, because
each harness writes its own transcript to disk as the session runs. The copy is made where it is read:

- `synthesis resume <project>` exports the last two days, then shows the project's latest prompts and replies from
  every harness. That is how work moved from one harness to another carries the conversation, not only the records.
- The day-end ritual runs `synthesis sessions export --days 2`.
- Anyone may run `synthesis sessions export` (add `--all` for everything on the Mac) before reading or citing.

## Reading and citing

```bash
synthesis sessions list --project <id>            # sessions, newest first, with their projects
synthesis sessions recent --project <id>          # the latest prompts and replies, any harness
synthesis sessions show <session> --kinds user,assistant
synthesis sessions show <session> --whole         # tool output and injected text in full
synthesis sessions search "<pattern>" --project <id>
```

Cite a transcript as `<harness> <session> #<seq>` in a session log or lesson. A quote or attribution read from the
archive in the current session has a tool output behind it, as quote provenance requires. Keep the conversation out
of CONTEXT.md and project folders: it would break their size budgets (R1.5) and flood every search of the project.
