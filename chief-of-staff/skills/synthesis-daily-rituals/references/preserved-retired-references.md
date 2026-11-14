# Preserved: four retired 2.45.1 reference files (verbatim)

These files described machinery v5 removes: the verified `synthesis exec-public` launcher, worker
artifact custody receipts, names-only credential-path inventories, and acquisition evidence
(direct Slack and Google API readers whose receipts gated every watermark). The code evaluation
decided it (`guards-rituals.md`, the synthesis-daily-rituals rows): the acquisition modules and
`archive_publish.py` are CUT, `credential_paths.py` is REPLACED by the commit check's filename
rule, and the artifact custody in `ritual_workers.py` and the evidence subcommands of
`ritual_state.py` went with their SLIM rewrites. The acquisition gate caused the 2026-10-01
regression: connector syncs ran in full, bookmarks stopped advancing, and the fix on offer was
handing over new read tokens. The files are kept word for word so their incident history and
reasoning stay readable. Nothing here is a live instruction.

Contents:
- ritual-evidence.md (2.45.1): verified execution, worker artifacts as evidence, record durability, migration markers, names-only credential-path review
- acquisition-evidence.md (2.45.1): readiness, meeting inventory, the receipt schema, Slack thread acquisition
- acquisition-entry.md (2.45.1): declared acquisition entries for Google Drive and Docs, Slack, connector replay, custody and retry
- mechanical-extraction.md (2.45.1): the mechanical owner map P1 to P5

---

# Ritual evidence and verified execution

This reference is mandatory before day-start and before recording a worker
completion. It supplements the worker contract without changing the desk's
nonblocking fold or granting cross-workspace authority.

## One verified execution owner

Use the installed `synthesis exec-public` owner for each ritual helper, followed
by that helper's existing arguments:

```text
synthesis exec-public synthesis-daily-rituals/scripts/portfolio_review.py
synthesis exec-public synthesis-daily-rituals/scripts/decay_sweep.py
synthesis exec-public synthesis-daily-rituals/scripts/pr_queue_scan.py
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py
synthesis exec-public synthesis-daily-rituals/scripts/gchat_preflight.py
synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py
```

The launcher verifies the selected release, interpreter, helper and registered
local dependencies. A missing registration or integrity refusal is a readiness
failure: retain the diagnostic and repair through the installed lifecycle owner.
Do not switch to direct Python execution, a source checkout or another client to
route around it. `--help` establishes parser availability only, never a successful
sync, account grant, network operation, artifact, or real lifecycle acceptance.

## Workspace worker artifact is completion evidence

The existing `~/.synthesis/ritual/workers.yaml` registry remains the owner. Each
registered worker declares `workspace_root` (an absolute or `~` path) and
`surfaces` (the full list of required coverage surfaces), in addition to its
existing workspace key, seat, status and artifact directory. The artifact directory
must be a real directory strictly inside that workspace root. Declare the actual
workspace's sources from its existing repo manifest, sync configuration and
practices; do not silently substitute an empty or reduced list. Missing declarations
are a readiness gap, not permission to alter the registry or disable evidence.
Use the owner's read-only `worker-readiness --workspace <id>` subcommand to expose
that gap before starting work. Configuration enrollment remains the registry owner's
authorized action; do not fabricate readiness by inferring it from a missing file.

Run the worker from within its registered workspace and retain its own claims.
Write the real artifact to its registered directory as
`YYYY-MM-DD-<run_type>.md` (day-start, midday, day-end or weekly-review). Keep the
existing frontmatter and fixed body sections. Additionally record `session` as
the actual current native/coordination identity and `outcome` as the exact outcome
passed to the recorder: clean/complete/completed/success, or
partial/failed/skipped/blocked/degraded. Unknown outcome labels refuse. `started` and `finished` are observed, timezone-aware wall
clock times; `date` is the logical workday, which can differ across midnight.
Include every declared surface exactly once with its real status and detail, and
explicit `gaps`. A clean result requires every surface synced and no gaps. An
unread or failed surface stays partial/failed and cannot become a clean result.

Add `lesson_candidates: []` to frontmatter when there are none. Otherwise use a
list of `{id: <candidate-id>, pointer: <absolute workspace-local file>}` entries.
Pointers must refer to real owned regular files within the worker's workspace.
Add the mandatory final `## Lesson candidates` body section after `## Backlog
deltas`; state `none` or name the local candidates and their pointers. The worker
keeps detailed source material in its workspace; the desk consumes the worker
artifact and routes candidate decisions without copying private source prose into
another workspace. Candidate existence is not acceptance as a durable lesson.
Keep/drop approval and the existing lessons/project record process remain intact.

Record only after the artifact is complete, using the existing recorder with
`--workspace`, `--direction`, explicit `--date`, `--outcome` and `--session`.
The recorder loads the registry itself, derives the exact artifact path and
verifies its contents. `--pointer` remains a narrative pointer, never substitute
evidence or an override to a foreign artifact. A worker record gets an artifact
SHA-256 receipt, byte count, seat and session. Missing, unreadable, linked,
foreign, changing, oversized or invalid artifacts refuse the append. A dormant
worker cannot record. The recorder does not create or backfill evidence, infer
coverage, prove native identity, send messages, or give the worker new claims.
The registry and native coordination layer retain their separate authority.

Without a registered worker the existing single-session ritual remains valid.
Explicit `--mode worker` with no registered workspace refuses, and a malformed
registry refuses rather than silently reverting to single-session behavior.
Historical artifactless records remain historical; never invent replacement
artifacts or rewrite old records to make coverage appear complete.

## Record durability and interrupted writes

The recorder serializes cooperating writers with a bounded exclusive file lock.
It completes short writes, fsyncs the file, checks exact readback and fsyncs the
parent before reporting success. Regular files do not inherit pipe atomicity
from `PIPE_BUF`. Zero-progress writes, failed fsync, changed files and interrupted
non-newline tails refuse. Retain ambiguous bytes for owner reconciliation;
repeating a refused operation is not evidence that its earlier effect was absent.
Linked files and aliased parent paths refuse. A process crash can leave an
interrupted tail, which is preserved rather than silently overwritten.

## Migration markers are not workdays

`mode=migration` identifies bookkeeping. Open-workday derivation excludes those
markers on both sides: a marker cannot create an open day or close real work.
Records, the unknown-workspace baseline and all historical timestamps stay intact.
No invented paired day-end, historical close or backfill is needed.

## Names-only credential-path review at day-start

After resolving this workspace and before reporting day-start coverage, run:

```text
synthesis exec-public synthesis-daily-rituals/scripts/ritual_state.py credential-paths --workspace-root <actual workspace root>
```

The owner reads the existing `.agents/repos.yaml` and each declared local Git
index's tracked **names**. It includes dormant repositories and repositories with
`ritual_sync: false`, because those flags do not eliminate tracked-file exposure.
It never reads tracked file contents or Git blobs, and does not contact a provider.
Git indirection must stay inside this exact workspace. Linked worktrees require
reciprocal checkout metadata; a pointer to another checkout's ordinary `.git`
directory refuses. The index and metadata identities are rechecked after Git
returns. Changed sources remain gaps, and their names are not attributed to the
previous checkout. Separate metadata directories without reciprocal worktree
ownership require explicit owner support and currently refuse.
Untracked files are outside this particular check and are never described as scanned.

Report candidate repository-relative paths privately, with the qualification
“credential-looking names; contents not inspected.” Sample/template names also
remain candidates: a filename alone cannot prove that a file is safe or secret.
The output's `complete` field describes inventory coverage, not absence of secrets.
Missing clones, malformed/foreign paths, unreadable indexes, limits or failed
commands remain explicit gaps and return a nonzero status. Partial coverage can
never support a “none found across the workspace” statement. Runaway bounds are
256 repositories, 8 MiB of path output per repo, 16 MiB across the workspace,
5 seconds per repo and 45 seconds
overall. Preserve the actual coverage and gaps in the worker artifact.

No rotation, key creation, purge, content scan, deletion or history rewrite is
part of this check. Those actions require their own authorization and provider
or repository owners. Do not place these paths in audible alerts or banners.

---

# Acquisition evidence before coverage claims

The existing sync watermark remains the state owner. Meeting and Slack acquisition adds a validation prerequisite; it does not create a separate scheduler, transaction engine, authorization source, or historical completion claim. Unknown provider coverage stays unknown. All examples and shipped tests are synthetic.

## Readiness and the exact declared window

Resolve the workspace's existing recorder and conversation configurations. Declare every source/account and every resolved channel/DM target before reading. Use the watermark's window; for a first capture, explicitly declare the owner's bootstrap bound. Record the exact source timestamp semantics (meeting time or source modification time), never infer them from a title. Do not expand to another workspace or account to fill a gap.

At day-start, invoke the recorder connector's owner-declared read-only identity probe. Service health and tool availability do not prove account sign-in. The optional meeting fetcher supports `--readiness-only` and `recorder_readiness`: configuration must supply `recorder_probe.tool`, `arguments`, and `semantics: authentication-read-only`; the adapter returns an actual `authenticated` boolean, account identity, and preserved `tool_call_id`. A missing adapter, expired sign-in, an account mismatch, unparseable text, or unavailable tool is a readiness gap. Human login remains a human action. Never infer read-only semantics from a tool's name.

The public adapter seams are implementations with injected, owner-selected read transports, not proof that a particular connector supports them. Bind and test a real connector's parameter and response schema before enabling it. Preserve raw tool outputs and their call references in the workspace's existing evidence locations. No credentials belong in receipts.

## Meeting source inventory and archive binding

`fetch-meeting.py` owns `inventory_documents`: bounded pages and total records, loop/cursor refusal, explicit source/account/window arguments, no relevance filter. The list adapter returns `ok`, `documents` (`source_id`, `occurred_at`), `next_cursor`, `complete`, and `tool_call_id`. Record a successful same-source positive-control document with its exact source/account identity, current observation time and call ID separately. A foreign or stale control refuses coverage. A limited search page without an exhaustion proof remains incomplete.

Every saved meeting header carries exactly one `**Source ID:** provider:document-id`. Keep the provider tab ID as well. Unwrap tool-result envelopes before interpreting text. Tab titles and tab positions are not identities. A declared title may select one tab only within a complete inventory where exactly one tab carries it; the selected tab's ID is what the archive records and binds. `document_tabs.select_tabs` reads provider `tabProperties.tabId` and `documentTab.body`; adapters must retain the full document's tab inventory and explicit `tabsComplete`. A missing requested tab is not absent unless enumeration is complete; even then its absence cannot prove the document has no transcript under another ID. The fetch owner refuses publication for a missing declared ID and requests owner rebinding. An explicitly returned empty transcript tab can preserve notes with a labeled no-source explanation. Empty returned transcript, absent declared tab, unavailable tab content, missing inventory, and incomplete inventory have distinct reasons. Never stamp `no-source-transcript` from an error or a tool summary.

Exact saved-file verification uses repeatable `verify_transcripts.py --file` or `--saved-manifest` (a JSON list of absolute `path` and `sha256`). It refuses missing, unreadable, aliased, changed, or duplicate paths; it audits explicitly named prefix files too. The optional fetch owner preserves replaced bytes, atomically publishes, and verifies the newly saved file digest. Its completeness detector is diagnostic: it cannot establish provider authenticity, truthful no-source explanations, or attribution. The primary-source attribution gate remains mandatory.

## Receipt schema and validation owner

A JSON evidence file has `schema: 1`, `workspace`, `surface: meetings|slack`, offset-bearing `from` and `through`, an absolute `archive_root`, and `archives: [{path, sha256}]` with root-relative paths. Every archive byte is reread through the existing ritual evidence owner's no-follow, ownership, permissions, and identity checks. Individual files are bounded to 8 MiB; aggregate input to 128 MiB; each inventory list to 10,000 members. A bounded read refusal preserves the original file and reports unknown coverage.

For meetings, add `declared_sources` (unique source IDs), `sources` and optional `gap_decisions`. Each source contains `id`, `account`, `readiness: {status: authenticated, account, observed_at, tool_call_id}` and `inventory: {from, through, observed_at, tool_call_id, complete: true, next_cursor: null, positive_control: {observed: true, source, account, source_id, observed_at, tool_call_id}, documents: [{source_id, occurred_at}]}`. Inventory observation must cover the full requested window; sign-in must belong to that run/window and be at most 24 hours old. The archive/source-ID sets are compared exactly. Each archived meeting also passes the existing transcript diagnostic. Duplicate IDs, foreign headers, and missing files refuse coverage.

A gap decision names `source`, `source_id`, a nonempty `reason`, `evidence_ref`, and one of `retry`, `authentication-required`, `source-unavailable`, or `operator-review`. Decisions explain missing documents; they do not advance through them. Preserve the complete gap list in the worker artifact and decision packet. No historical backfill or user decision is invented.

For Slack, add exact `declared_targets` and `channels`. The declared targets are the conversations this receipt proves; the acquisition owner lists any other configured conversation under `unacquired_targets` with its reason, and that conversation's watermark stays unchanged. Each channel carries `id`, local `known_thread_ids`, `history`, `reply_search`, and `threads`. History records `detail: detailed`, the exact window, all messages and pagination completion. Search records the same bounds plus actual returned `positive_control_ids` within that window. A channel without one may instead carry `quiet_control: {history, search}`, each `{newest_ts, tool_call_id, observed_at}` with `newest_ts` before the window and `observed_at` at or after its end. It is accepted only when that channel returned nothing in the window and another channel in the same receipt has a genuine in-window control; the result names it in `quiet_channels`. Every observation carries `tool_call_id` and offset-bearing `observed_at` at or after the requested end. Each thread carries `parent_ts`, complete messages, and pagination proof, with no `oldest`. Saved records carry `**Message ID:** channel-id:message-ts`; all observed in-window messages must be in the saved archives. This proves recorded ID coverage, not semantic fidelity.

Use the installed verified owner:

```text
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py acquisition-check --workspace W --surface meetings --through END --acquisition-evidence capture.json --json
synthesis exec-public synthesis-daily-rituals/scripts/sync_watermark.py advance --workspace W --surface meetings --through END --acquisition-evidence capture.json
```

For Slack repeat `--target CHANNEL` for the exact receipt targets. `acquisition-check` is read-only. `advance` revalidates before changing a slot; refusal leaves stored bytes unchanged. `--surface-level` cannot bypass evidence. Other surfaces keep their existing owners and requirements. Retain source receipts with the ritual artifact, not only the concise watermark result.

## Detailed Slack and thread acquisition

Use `thread_checker.acquire_channel` with owner-selected `read_channel`, `read_thread`, and `search_replies` adapters. Every call requests detailed results. Follow all cursors; refuse repeated or malformed cursors, missing terminal pagination evidence, explicit incomplete/truncated results, foreign-channel messages, transport errors, and bounds exhaustion. Calls have a 120-second aggregate check and at most 100 pages per stage; each adapter must independently enforce a finite request timeout. A synchronous call cannot be preempted by the caller's elapsed-time check.

Read full threads without `oldest`, including parents outside the window. The required parent set is the union of local known threads, history reply indicators, and independently discovered in-window replies. Confirm that the thread pass contains the search reply. A positive control must be an actual returned in-window message. If no such control is available, report unknown coverage instead of asserting an empty channel, unless the caller supplies both quiet-channel probes (`probe_newest` for history, `probe_search_newest` for the search index), each bounded at the window's end, and both return a message that predates the window. Source receipts cannot authorize sends, account access, or broader searches.

## Managed records and installation boundary

If the capture updates a managed project's existing index or context, invoke the context-lifecycle `context_edit.apply_transaction` owner with fresh admission and exact claims; do not replace it with a second journal or lock engine. Transcript archive publication remains the acquisition owner's single-file operation, outside managed record editing. Installed verified execution must include the acquisition helper, ritual reader, and transcript verifier in its dependency receipt. Native connector authentication, real-source coverage, and selected-client loading require separate observed acceptance. Synthetic test success does not supply those facts.

---

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

```yaml
google_account: reader@example.invalid
transcript_tab_title: Transcript
acquisition_adapter:
  kind: workspace-mcp-v1
  url: http://localhost:8765/mcp
  name_contains: Notes by Gemini
  positive_control_id: known-document-the-name-filter-matches
  window_field: createdTime
```

- Identity: `list_calendars` must name the declared account as the primary
  calendar's ID.
- Positive control: `get_drive_file_permissions` must show the declared
  control as a live Google Doc whose name contains the filter.
- Inventory: `search_drive_files` returns rendered rows without Drive's
  `incompleteSearch` result. A user-corpus query, an empty listing, or exhausted
  pagination cannot substitute for that missing evidence. The adapter retains
  the response and refuses inventory completion, fetch and watermark advance.
  An explicitly configured `google-rest-v1` reader validates the actual flag;
  acquisition never switches credentials or adapters automatically.
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
satisfies complete-window acquisition. The `workspace-mcp-v1` tab reader can
retain individual document content, but its rendered search inventory also
cannot establish complete-window acquisition. The bounded MCP capture hook
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

Claude Code records connector calls and raw responses in its native transcript.
`claude-code-connector-replay-v1` can inspect that custody and identify missing
calls. The current connector renders multiple source messages into one string
without unambiguous boundaries. A message quoting another message's header can
produce the same bytes as two separate messages. Raw-response hashes preserve
that text but cannot establish per-message authorship.

Channel, thread and search renderings therefore refuse reconstruction, including
apparently empty pages. A plan with only such targets is not ready, and fetch
cannot create attributed archives or advance their watermarks. No additional
read of the same representation resolves this limitation. Preserve the native
transcript and report the source boundary that remains unavailable.

Complete acquisition uses the explicitly declared `slack-web-api-v1` structured
reader above, with already authorized credentials. No credential discovery,
automatic adapter fallback, or new authentication is part of connector replay.
A future connector may support acquisition only after its actual producer
preserves lossless records and its consumer is verified against that contract.


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

---

# Mechanical ritual owners

Run these through the verified public runtime. They report evidence in their
own bounded domains; interpretation and effect approvals remain with the agent
and existing state owners. Do not copy native credentials into prompts.

| Package | Current owner | Required result |
|---|---|---|
| P1 meeting transcript acquisition | synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py health/inventory/fetch; document tabs and commitment extraction | Declared source IDs, exact full saved transcript/header/body, explicit missing-half and unavailable-source reasons; verbatim primary evidence remains separate from summaries. |
| P2 channel acquisition | synthesis-slack-sync/scripts/acquire.py, using preflight, registry and thread_checker | Current declared IDs, in-window roots and replies, exact saved files and coverage gaps; no automatic expansion into private conversations. |
| P3 sync arithmetic | synthesis-daily-rituals sync_watermark | Existing begin/window/advance/status owner, exact declared universe, evidence-bound advance, clock zone explicit and unknown coverage blocking. |
| P4 repository status | synthesis-daily-rituals repo_state.py | All declared repositories and branches, cached versus freshly fetched status, ahead/behind counts, BLIND/UNREACHABLE/DECISION/EXCLUDED with a denominator. |
| P5 grounding envelope | synthesis-message-guard message_guard.py --build-ledger | Canonical complete tool-input digest and truthful supplied attestations, checked by the existing single-use write/consume owner. |

For P1/P2, follow [declared acquisition entries](acquisition-entry.md): explicit supported adapter selection, exact account/source/target configuration, private raw custody and evidence-bound archive/advance. Unsupported MCP source identity remains UNKNOWN; service liveness is separate from recorder authentication.

For P4, use `synthesis exec-public synthesis-daily-rituals/scripts/repo_state.py
--workspace <absolute-root> --fetch` when this ritual is authorized to fetch.
Without --fetch the result is cached and cannot prove current remote state.
The helper performs no merge, rebase or fast-forward. The existing branch owner
handles a permitted fast-forward after rechecking claims and current state.
Do not overwrite an active seat's checkout. Every fetch is bounded; source and
branch identities are rechecked. An upstream-less branch stays BLIND.

Interpret raw reports without inflating their evidence plane. Test the chosen
package with causal negatives and a legitimate positive case before release,
verify its installed dependencies in each selected client, and retain actual
elapsed/resource measurements. Unknown model-token or energy costs remain
unknown. Script extraction does not prove that a model read every source or
that all future prompts will follow the protocol.
