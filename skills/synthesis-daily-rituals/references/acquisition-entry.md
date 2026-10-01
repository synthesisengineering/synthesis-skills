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

The MCP one-off title lookup is separate. The documented workspace-mcp
`get_doc_content` returns plain text, which cannot establish stable tab identity
or full tab inventory. That contract needs a supported structured adapter before
it can satisfy complete-window acquisition; selecting it never falls back to a
direct token. The bounded MCP capture hook preserves success/error bodies and
labels incomplete failure prefixes. HTTP health and credential presence are not
authenticated coverage.

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
`file:` references work; client-managed `mcp:` is explicitly unavailable to this
Python transport. No token discovery or login flow runs. The user token needs
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
visible. Documented channel/DM search syntax uses a wider day window followed by
exact local timestamp selection.

Slack search applies user filters and may suppress nearby matches. Evidence
describes the declared returned corpus, not content the API cannot expose. Empty
results without a genuine in-window positive control remain UNKNOWN. Missing
pagination, repeated cursors, foreign IDs, conflicting content, HTTP/auth/rate
limits and partial coverage prevent advance.

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
