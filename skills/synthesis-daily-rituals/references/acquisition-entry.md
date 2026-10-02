# Declared acquisition entries

These entries perform bounded reads, save exact source evidence, verify the saved
files, and call the existing watermark owner. They do not send messages, create
credentials, discover other accounts, or change a connector automatically.
Judgment, commitments and communication approvals retain their existing owners.

## Runtime and configuration

Use the installed release's verified entries:

```text
synthesis exec-public synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py --help
synthesis exec-public synthesis-slack-sync/scripts/acquire.py --help
```

The setup-selected Python must contain `httpx` and `PyYAML`. Authorized environment
setup may install them with that interpreter's `-m pip install httpx PyYAML`.
Acquisition never installs dependencies. On macOS the runtime selects the
prescribed python.org Python 3.12 interpreter; elsewhere its validated Python
3.12 policy applies. Missing dependencies refuse before credential resolution or
requests. An unrelated `uv` environment does not prove verified execution.

Outputs require physical absolute paths without symlink ancestors. Configuration
uses an absolute `transcripts_repo` and relative `transcripts_path`. Keep source
content and captures in the correct private repository/deletion unit. Do not put
token values in arguments or configuration.

## Google Drive and Docs

Extend the existing meeting-transcripts YAML:

```yaml
workspace: example
google_account: reader@example.invalid
transcripts_repo: /absolute/private-repository
transcripts_path: transcripts
transcript_tab_id: stable-verbatim-tab-id
acquisition_adapter:
  kind: google-rest-v1
  token: env:DECLARED_GOOGLE_READ_TOKEN
  folder_id: declared-folder-id
  positive_control_id: known-document-in-that-folder
  window_field: createdTime
```

`window_field` is explicitly `createdTime` or `modifiedTime`, not inferred meeting
time. Fresh `about.get` must match the declared account, and `files.get` must
identify the declared non-trashed Doc in that folder. `files.list` follows every
folder/window page without title filtering; `incompleteSearch` must be false.
`documents.get(includeTabsContent=true)` binds the document and stable tab IDs.

Declare exactly one transcript selector. `transcript_tab_id` fits a source whose
transcript tab keeps one ID across documents. Gemini notes do not: each
meeting's document gives its Transcript tab a new ID (six documents on
2026-10-01 carried six). For those, declare `transcript_tab_title: Transcript`
instead. The title selects only within a complete tab inventory and only when
exactly one tab carries it; that tab's own ID is then recorded in the archive
header and binds the read. No matching tab, or more than one, refuses.

### Through the local workspace-mcp server

A workspace that already runs workspace-mcp needs no Google token: the server
holds the account's grant, and the fetcher calls it directly over loopback.
Every response is retained in custody before it is read.

{F}yaml
google_account: reader@example.invalid
transcript_tab_title: Transcript
acquisition_adapter:
  kind: workspace-mcp-v1
  url: http://localhost:8765/mcp
  name_contains: Notes by Gemini
  positive_control_id: known-document-the-name-filter-matches
  window_field: createdTime
{F}

- Identity: `list_calendars` must name the declared account as the primary
  calendar's ID.
- Positive control: `get_drive_file_permissions` must show the declared
  control as a live Google Doc whose name contains the filter.
- Inventory: `search_drive_files` for Docs whose name contains the filter
  inside the window, in the user corpus without shared-drive items, following
  every `nextPageToken`. Each page must hold exactly the files it reports.
  Drive reports an incomplete search only across several corpora, which this
  query excludes; the tool does not echo that flag, so this remains a stated
  basis rather than an observed one.
- Content: `inspect_doc_structure` lists the tabs; the transcript tab is
  selected by title as above, and every tab is read by ID with
  `get_doc_as_markdown`. An empty transcript tab refuses for owner review.

The URL must be loopback `http`. A remote or unknown adapter refuses before any
call, and selecting this adapter never falls back to a direct token.

Select `--mode health`, `inventory`, or `fetch`. All take `--config`, `--through`,
`--backfill-from` and `--capture-dir`. Supply timezone-bearing ISO timestamps.
The existing watermark provides the start when present; backfill is the explicit
first-run bound. Fetch requires `--evidence`; only fetch accepts `--advance`.

```text
synthesis exec-public synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py --mode fetch --config /absolute/meeting-transcripts.yaml --through 2026-09-28T00:00:00Z --backfill-from 2026-09-27T00:00:00Z --capture-dir /absolute/private-capture/run-001 --evidence /absolute/private-capture/run-001-evidence.json --advance
```

Health separates dependency, transport and authenticated recorder observations;
it does not certify inventory. Inventory reports IDs and full paging without
archive writes or advance. Fetch saves `meetings/<source-id>.md`, labeling tool
notes as lossy and keeping the verbatim transcript separate. Missing, empty,
ambiguous or incomplete transcript tabs refuse; raw structured notes remain in
custody. Replacing a changed meeting file requires explicit `--force`, preserving
old bytes first.

The MCP one-off title lookup is separate. Its `get_doc_content` plain text
cannot establish tab identity or a complete tab inventory, so it never
satisfies complete-window acquisition; the `workspace-mcp-v1` adapter above
does, through the structure and per-tab reads. The bounded MCP capture hook
preserves success/error bodies and labels incomplete failure prefixes. HTTP
health and credential presence are not authenticated coverage.

## Slack

Use the existing sync configuration and workspace registry:

```yaml
workspace: example
transcripts_repo: /absolute/private-repository
transcripts_path: transcripts
channels:
  - id: C123
    name: channel
acquisition_adapter:
  kind: slack-web-api-v1
  team_id: T123
  user_id: U123
known_archives:
  - slack/2026-09-27/channel.md
```

```yaml
# Existing slack-workspaces registry
mode: isolated
workspaces:
  - name: example
    domain: example.slack.com
    token: env:DECLARED_SLACK_READ_TOKEN
```

Only that workspace's credential reference is resolved. `env:` and absolute
`file:` references work for this direct adapter; a client-managed `mcp:`
reference is unavailable to its Python transport and selects nothing on its
own (see connector replay below). No token discovery or login flow runs. The user token needs
provider permissions for the declared conversation, history, replies and search,
including `search:read`. Bot identity is refused. `auth.test` must match the exact
team, user and domain; authentication alone does not prove every read capability.

```text
synthesis exec-public synthesis-slack-sync/scripts/acquire.py --mode fetch --config /absolute/slack-sync.yaml --registry /absolute/slack-workspaces.yaml --through 2026-09-28T00:00:00Z --backfill-from 2026-09-27T00:00:00Z --capture-dir /absolute/private-capture/run-002 --evidence /absolute/private-capture/run-002-evidence.json --advance
```

Health checks identity without acquisition or advance. Fetch uses only the
existing preflight's resolved C/G/D targets. Unsafe or colliding filenames,
duplicate IDs and unresolved DMs refuse before requests. The thread owner follows
detailed history, independent search and the union of known/history/search
parents. Replies never use `oldest`; an older parent with a new reply stays
visible. Search `after:`/`before:` days are exclusive and read in the
searcher's time zone, anywhere from UTC-12 to UTC+14, so the direct adapter
widens each side by two UTC days and then selects the exact window locally.

Slack search applies user filters and may suppress nearby matches. Evidence
describes the declared returned corpus, not content the API cannot expose. Empty
results without a genuine in-window positive control remain UNKNOWN, with one
bounded exception. A channel whose history and window search both return
nothing in the window passes only when two reads of its own, each bounded at the
window's end and observed after it, return a real message that predates the
window: the newest history message and the newest search-indexed message. The
same capture must also hold another channel's genuine in-window search control,
so the search demonstrably covered the window. Otherwise that channel, and the
run, stay UNKNOWN. Missing pagination, repeated cursors, foreign IDs,
conflicting content, HTTP/auth/rate limits and partial coverage prevent advance.

### Connector replay (Claude Code)

A workspace the agent already reads through a client-managed Slack connector
can advance without any token. The agent makes ordinary connector reads; Claude
Code records each call's exact input, raw result and completion time in its
session transcript. `acquire.py` then serves the thread owner only from those
recorded calls, so every observation cites a real `tool_use` id rather than
agent-written custody.

```yaml
acquisition_adapter:
  kind: claude-code-connector-replay-v1
  user_id: U123
```

```yaml
# Registry entry: <server> is the segment in the connector's mcp__<server>__slack_* tool names
  - name: example
    domain: example.slack.com
    token: mcp:<server>
```

Run `--mode plan` first with every transcript that may hold the reads: the
session file and each `subagents/agent-*.jsonl` that made calls, one
`--transcript` per file. The plan lists every missing call with its exact
input. Make those calls, then plan again: threads a search finds and the
quiet-channel probes surface on the second pass. When the plan reports
`ready`, run `--mode fetch` with the same transcripts and `--advance`.
`problems` names conversations whose coverage cannot be proven, such as a DM
with no message at all. Fetch reports each one under `unacquired_targets` with
its reason and leaves its watermark unchanged, while every proven conversation
advances. A run that proves no conversation refuses outright. This applies to
the direct adapter too.

```text
synthesis exec-public synthesis-slack-sync/scripts/acquire.py --mode plan --config /absolute/slack-sync.yaml --registry /absolute/slack-workspaces.yaml --through 2026-09-28T00:00:00Z --backfill-from 2026-09-27T00:00:00Z --capture-dir /absolute/private-capture/run-003 --evidence /absolute/private-capture/run-003-evidence.json --transcript /absolute/.claude/projects/<project>/<session>.jsonl --transcript /absolute/.claude/projects/<project>/<session>/subagents/agent-1.jsonl
```

What counts as a recorded read:

- Only calls to the registry's server whose result arrived at or after the
  window end. Failed calls, other servers and other tools never count.
- History: a detailed `slack_read_channel` whose `oldest` and `latest`
  strictly enclose the window, because the provider's boundary inclusivity is
  not observable. Cursor pages follow through recorded calls with the same
  input.
- Search: `slack_search_public_and_private` with exactly `in:<#ID>`, no
  keywords or semantic query, `include_bots: true`, and bounds enclosing the
  window: the connector's `after`/`before` Unix-timestamp parameters strictly
  (verified exact on 2026-10-01), or `after:`/`before:` day filters with two
  UTC days of margin. Search rows are discovery-only and never archived,
  because the search renders text differently from history and threads.
- Threads: a detailed `slack_read_thread` without `oldest`, `latest` or
  cursor that holds the parent and every reply it reports. A paginated thread
  read refuses; read it again with `limit: 1000`.
- Identity: `slack_read_user_profile` without `user_id`, so it names the
  connector's own user, matching the declared `user_id` and not a bot.

Archived text drops what varies between reads of one message: the `Thread:`
and `Reactions:` metadata lines, and mention display names (`<@U123|Name>`
becomes Slack's own `<@U123>`). The full rendering stays in each row's
`rendered` field inside the raw footer. A spilled result resolves only from the
same session's `tool-results` directory and must match its recorded size.

Custody is `connector-calls.json` in the capture directory: each used call's
id, tool, input, observation time, transcript and result digest, plus the byte
count and sha256 of every transcript prefix read, which can be re-checked while
the transcript only grows. The evidence's provider limitations state what
replay cannot prove: it is as authentic as the client's own transcript, and the
connector's rendered text stands in for Slack's raw message bodies.


## Saved bytes, custody and retry

Slack retains daily paths `slack/YYYY-MM-DD/<channel>.md`, `_dms.md` and
`_group-dms.md`. Messages and replies carry `Message ID: channel:ts`, raw
user/parent IDs, exact text, permalinks and a reversible raw-metadata footer.
No model supplies speaker names or rewrites content. Repeated identical reads
are idempotent; additive merges preserve old bytes and recheck the reviewed
digest under the publication lock. Conflicts or an unrecognized historical
format require source reconciliation, never silent overwrite. Legacy archives
can still supply known-parent discovery through explicit channel and parent headers.
Quoted or fenced bodies are ignored; ambiguous channel names, missing identities,
unclosed fences and timestamp-bearing prose cannot certify an empty thread set.
Owned archives use their validated final raw-codec footer, including every
conversation/timestamp and explicit parent relationship. Raw body headings and
quoted codec text never create target scope.

Slack page-number search requires complete count/total/page metadata. When both
`paging` and `pagination` are returned, every declaration must agree. Per-page
range and match counts, aggregate unique message identities and cross-page
totals must remain consistent before a terminal cursor is produced. A changing
provider result set refuses advancement; there is no automatic retry or claim
of a provider-wide transactional snapshot.

Both MCP callers share one bounded initializer. Before initialized notification
or any tool request, it requires a unique successful reply to initialize ID 1,
protocol `2025-03-26`, a declared tools capability, server implementation metadata
and a bounded visible-ASCII session ID. Subsequent calls carry that exact
session and protocol. A session header or later tool success cannot repair a
failed handshake. An unsupported protocol or missing tools capability refuses.

The direct transport permits 1,000 requests, 120 seconds, 4 MiB per response,
128 MiB raw aggregate and 256 MiB serialized custody. HTTP I/O has a 15-second
timeout; existing finite inventory/collection page bounds also apply. There is
no automatic retry, redirect following, proxy-environment routing or compressed
response expansion. Excess means incomplete custody, never an empty source. If
a provider echoes the credential, its body is withheld and only the hash/error
retained. Status output has metadata and receipt paths, not raw payloads/tokens.

The common publisher retains no-follow directory access, bounded locking,
staging, fsync, old-byte backup and exact readback. Separate file replacements
are not one atomic transaction. A late failure preserves prior effects and
staging while leaving the overall watermark unchanged. Evidence publishes only
after exact archive validation. After a crash following evidence publication,
the existing `sync_watermark.py advance --acquisition-evidence` can consume that
unchanged file. Changed archives or absent Message IDs refuse. Each new
acquisition uses a new capture/evidence destination rather than rewriting a
previous receipt.

## Provider contracts

- [Drive about.get](https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get)
- [Drive files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list)
- [Docs documents.get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get)
- [workspace-mcp Docs tools](https://github.com/taylorwilsdon/google_workspace_mcp/blob/main/skills/managing-google-workspace/references/docs.md)
- [Slack auth.test](https://docs.slack.dev/reference/methods/auth.test/)
- [Slack history](https://docs.slack.dev/reference/methods/conversations.history/)
- [Slack retrieving messages](https://docs.slack.dev/messaging/retrieving-messages/)
- [Slack search.messages](https://docs.slack.dev/reference/methods/search.messages/)
- [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle)
- [MCP tools capability](https://modelcontextprotocol.io/specification/2025-03-26/server/tools)
- [Slack pagination](https://docs.slack.dev/apis/web-api/pagination/)

Synthetic tests do not prove current account access, installed-client loading,
provider completeness beyond these contracts, or actual token savings.
