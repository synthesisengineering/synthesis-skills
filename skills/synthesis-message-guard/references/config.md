# Send-guard configuration

The guard reads `~/.synthesis/v5/config.json`, the principal's private file. An
unreadable or malformed file blocks every send (R3.5); a missing file means the defaults
below. The public starting point is
[config.example.json](../config.example.json), which the tests load in CI, where there is
no `~/.synthesis`.

## Keys

| Key | Meaning |
|---|---|
| `send_tools` | Extra tool-name globs to guard, beside the built-in Slack, Gmail, email, chat and draft patterns (`mcp__*slack*send_message*`, `mcp__*send_gmail_message*`, `mcp__*create_draft*`, `mcp__*__reply`, ...). |
| `forbidden_phrases` | The register scan: `[{"name", "pattern", "why", "case_sensitive"}]`. Patterns are Python regexes, matched case-insensitively unless `case_sensitive` is true. |
| `message_format.allow_line_breaks_in_paragraphs` | Default false. True only for content whose line structure matters (an address block, poetry). Changes formatting only. |
| `message_format.default_email_format` | Default `html`. `plain` lets every transport send plain text (still with whole paragraphs). |
| `message_format.plain_email_tools` | Tool-name globs of transports that can only send plain text (for example `mcp__apple-mail__*`). |
| `signature.markers` | Strings that mark a persona signature (for example the persona's emoji). |
| `signature.domains` | Persona domains that must appear only inside a link on a link-capable channel. |
| `signature.plain_url_tools` | Tool globs whose channel cannot render links, where the visible domain is the right form. |
| `own_repos` | Repository globs (`owner/*`, `owner/name`) whose PRs, issues and comments are the principal's own work, not sends: GitHub connector tools naming that `owner`/`repo`, and `gh` commands whose `-R`, API path or `origin` remote names it. |
| `not_send_tools` | Tool globs never treated as sends, for a tool whose name reads like one but reaches no person. |
| `send_commands` | Extra `[channel, regex]` pairs for shell programs that post, matched from the start of a command's words (built in: `gh`, `bkt`, `glab`, `jira`/`acli`, `osascript` Messages or Mail, and `curl`, `wget`, HTTPie writes to another host). |
| `send_window_signatures` | Regexes; inside an open send window, a send goes without a per-message code only if one matches its text. List the signatures of the lanes the principal lets a window cover. Empty means a window covers nothing. |
| `preferred_names` | People who go by a name other than their official first name: `[{"official": "Robert", "preferred": "Bob", "identifiers": ["bob@example.test", "U0EXAMPLE"]}]`. Optional; absent means no name check. See below. |

None of these keys can grant a send: approval is always the principal's, and overrides
change formatting only. Grounding, register, recipient, branding, threading, approval and
disclosure requirements stay in force.

## Preferred names

A person is addressed by the name they go by, not by the official first name a
directory or an email header shows (`synthesis-agent-correspondence` binding rule 12;
on 2026-10-13 an agent message addressed someone by the official first name a
directory showed, not the name she goes by). Each `preferred_names` entry names one person:

- `official`: the official first name, matched as a whole word and case-sensitively,
  so "Robert's" is caught and a lowercase email local part is not.
- `preferred`: the name they go by, which the problem text tells the agent to write.
- `identifiers`: strings that identify that person on the channels the principal uses:
  email addresses, a Slack user ID (which also appears inside mention syntax such as
  `<@U0EXAMPLE>`), a Slack DM channel ID, a Jira account ID (as in `[~accountid:...]`).
  Matched without regard to case anywhere in the call: recipients, channel, subject or
  body.

The guard flags the official name only when one of that entry's identifiers appears in
the call, so a message to someone else who shares the first name is never blocked. It
reads every string in the call (body, HTML body, subject, event title) except the
address fields (`to`, `cc`, `bcc`, `recipient`, `recipients`, `space_id`, `space_name`,
`user_google_email`), where a display name such as `Robert Example <bob@example.test>`
is an address, not a greeting. Mention syntax stays whatever the platform requires;
only the words around it change. The problem text names the preferred name:

```text
this message involves someone who goes by Bob; write Bob, not Robert
```

A message that names the person without any identifier in the call (a group channel
where they are mentioned by name only) is not checked; the drafting rule still applies.
An entry that is not an object stops every guarded send, like any malformed config
(R3.5); `identifiers` is a list, never a single string.

## Every channel and send windows (2026-10-13)

The principal asked that approval cover "all communications sent for me / on my behalf, regardless of
communications channel", and for a proper setting that suspends per-message approval for a while.

**Recognition.** A connector tool is a send when its name has a saying verb (send, reply, forward, comment,
post, publish, share, invite, respond, mention, schedule, submit, draft, notify, remind), or a writing verb
(create, add, edit, update, manage, set) whose object is something people read (comment, message, issue,
page, post, reply, review, draft, event, invite, reaction, canvas, envelope, request, ticket, thread, access,
permission). A tool whose first verb reads (get, list, search...) is never a send; agent-to-agent tools are
exempt. In the shell, each command a line runs is checked against the posting programs. The register scan
reads the message the command sends: its text words and every body it reads from a file (`--body-file`,
`gh pr ... -F`, `--input`, `@file`, `$(cat file)`), never its options, URLs or file names; a body file the
guard cannot read, or one named through a variable, is refused. The approval binds the command, its message
and the directory each posting command runs in after its own `cd`, so the same command approved and run
again from another directory still goes (2026-10-13). Limits: a program that sends through its own code (a script calling an HTTP
library) is not recognized; the binding rule covers it.

**Windows.** Only the principal opens one. The command itself checks: run by an agent (a harness's
environment, or no terminal), `synthesis sends open` opens only on the principal's granted code for exactly
that window, read from the session's own transcript, and otherwise refuses with a code to show them; the guard
also asks for the code before the command runs, wherever its options sit, and `--help` never needs one. Run in
their own terminal, it opens directly (2026-10-13: a global option before `sends` slipped past the guard alone). A script that imports the approval or window code is
refused. A window names its hours (at most 12), its channels (or `all`) and optionally a project; it ends by
itself, and `synthesis sends close` ends it at once with no code. Every session sees it at each prompt. Each
send it covers still passes the register scan and format rules, must carry a `send_window_signatures`
signature, and is written to the day's ledger with the sends approved by code; `synthesis sends log
[--date]` prints it for the daily plan's "On your behalf". Exact-text sends (the principal's own words) are
outside every window: list only the signatures of lanes the principal allows.

## Calibration

The pattern set must PASS the principal's real sent messages and BLOCK the incident
drafts. Re-run calibration whenever patterns change; a guard that blocks the principal's
own voice is miscalibrated, not strict.

- A rule against a miscased brand is case-sensitive (`"case_sensitive": true`): on
  2026-08-03 a retired-branding pattern compiled to ignore case blocked every correctly
  signed send.
- The positive controls are tests, run in CI: a real signed agent message, in Slack
  wire form, reaches the approval step; a known-bad message (an apology for delay,
  self-abandonment) is blocked by name
  (`tests/test_send_guard.py::test_positive_controls_a_real_signed_message_passes_and_a_known_bad_one_blocks`,
  `tests/test_signed_message.py`). A principal's private config adds its own canonical
  messages as tests in the private layer, so a pattern change that blocks real traffic
  fails there before it reaches a session.

## Wiring and health

The plugin's hooks file registers the PreToolUse hook for every harness, matching shell
tools and every MCP tool whose name holds send, draft, reply, forward or schedule (plus
the calendar and sharing verbs the account guard needs), and `synthesis doctor` proves
each harness actually calls it. A tool added through `send_tools` must also match that
matcher, or it never reaches the guard. There is no per-client patterns file and no
enrollment step.

## From the 1.x patterns file

| 1.x `patterns.json` | v5 |
|---|---|
| `gated_tool_patterns` (regexes) | built-in globs plus `send_tools` |
| `exempt_tool_patterns` | not needed: session-to-session tools are never guarded |
| `block_patterns` `{name, regex}` | `forbidden_phrases` `{name, pattern, why, case_sensitive}` |
| `warn_patterns` | dropped: a warning the model never sees changes nothing |
| `ledger_max_age_minutes` | approvals expire after 15 minutes |
| `text_field_candidates` | every string in the call is scanned |
| `doctor_clean_controls` | tests (above) |
| `currency_claim_patterns`, `currency_claim_max_age_minutes` | binding rule 2: re-read within 30 minutes |
| `email_policy`, `paragraph_policy` | `message_format` |
| `signature_link_enforcement` | `signature`, plus the HTML email rule for every email |
| `peer_send_resolution` | board messages (`synthesis msg`) resolve their target |
