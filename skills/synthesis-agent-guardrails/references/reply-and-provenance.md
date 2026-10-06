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
- quotes someone (said, wrote, replied, ...: "twelve or more characters") with words that
  appear nowhere in this session's transcript: quote only what a tool surfaced;
- names a file without a clickable absolute-path link, when `reply_file_links` is true.

It never sends a reply back twice in a row and lets the reply through on any internal
error: a turn-end check that fails closed loops forever. When a reply is sent back, revise
exactly what it names.

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

- Records: each path given that is a file, and the files under each folder, that sit in
  `transcripts/`, `daily-plans/` or `projects/<id>/sessions/`, or are a project's
  `CONTEXT.md` or `REFERENCE.md`, and changed since the date.
- What is checked: what a record gained since its last commit before the date: every
  Slack timestamp (`1234567890.123456` or the `p1234567890123456` permalink form) and every
  attributed quote of twelve or more characters.
- Sources: harness session logs changed since the date (`~/.claude/projects` and
  `~/.codex/sessions`, or each `--sources DIR`). Only what a tool returned or a person
  typed counts. The agent's own words, its write calls and a write's echoed result never
  source themselves. Each log is searched as raw bytes first, and only the lines holding a
  candidate are parsed, so a day of logs reads in seconds.
- Exit 0 when everything is sourced, 1 when something is not, 2 when no session log
  folder exists. It reads only.
- An unsourced line is a lead, not a verdict: open the source (the synced transcript, the
  channel) and either cite it or correct the record. Never "fix" it by finding a similar
  message.

Tests: `skills/synthesis-agent-guardrails/tests/test_provenance_scan.py`.
