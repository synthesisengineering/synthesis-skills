# Preserved text: meeting transcripts, retired in milestone M3

Read this only to review what was cut. The passages below are no longer
instructions; they are kept verbatim so the reasoning stays readable (ruling D8).

Contents:
- Why the scripts were cut or slimmed
- Replaced passages, file by file (verbatim)
- Test fixtures of the cut transcript_primary.py (verbatim)

## Why the scripts were cut or slimmed

Verdicts from the v5 code evaluation (tool scripts, meeting transcripts):

- `transcript_primary.py` (461 lines): CUT. It classified a file as raw provider
  records or a derived summary and issued a hash-bound receipt authorizing one
  attribution. The need it served is real (lesson 2026-07-07, passive AI-note
  attribution drift: "He was warned" became a warning from the meeting
  counterpart); it is a reading rule, kept as binding rule 8, Step 4.6 and
  transcript-primary-and-commit-gate.md. Telling a transcript from a summary is
  `verify_transcripts.py`'s job, and only the old release wiring consumed the
  receipt. Its acceptance manifest (`acceptance-suite.yaml`) and fixtures went with it.
- `optional-workspace-mcp/google_read.py` (174) and `workspace_mcp_read.py` (241):
  CUT. Adapters for the acquisition gate; no meeting-transcripts config on this
  machine ever declared one. What workspace_mcp_read.py learned about the server
  is kept in fetch-meeting.py: tabs come from `inspect_doc_structure` and each
  tab's text from `get_doc_as_markdown`, and a Drive search listing carries no
  completeness flag.
- `optional-workspace-mcp/fetch-meeting.py` (678 to 351), `mcp_client.py` (329 to
  181), `document_tabs.py` (207, folded in): SLIM. Kept: the fetch, tab-ID
  selection with distinct reasons, "an error is not absence", and a saved/unsaved
  list for a window (IR-55, IR-57). Dropped: readiness receipts, raw-response
  custody, the source-inventory seam and the archive publisher. httpx and PyYAML
  were replaced by the standard library (v5 rule: Apple's Python 3.9 must run it).
- `verify_transcripts.py`: KEEP. Its exact-file reader came from the cut
  acquisition module, so it now reads exact bytes itself; it gained
  `from __future__ import annotations` so Apple's Python 3.9 runs it.
- `extract_commitments.py`: KEEP; its docstring no longer names a private person.
- The service scripts: KEEP, with the generic launchd label
  `com.synthesis.workspace-mcp` (requirement R7.4).

## Replaced passages, file by file (verbatim)

### SKILL.md

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
The earlier release notes and rationale are retained in [references/earlier-version-history.md](references/earlier-version-history.md). Before a declared-window sweep, read the mandatory [acquisition evidence contract](../synthesis-daily-rituals/references/acquisition-evidence.md). Unknown authentication, tab enumeration, or archive coverage is a visible gap, never a no-source attestation.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
2. **Unknown coverage is a visible gap.** Unknown authentication, tab enumeration or archive coverage never becomes a no-source attestation; only verified acquisition evidence advances the watermark.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
3. **A rendered Drive inventory cannot authorize interval completion or watermark advancement,** because it omits the provider completeness flag. Use an explicitly configured structured reader; credentials and adapters are never selected automatically.
````

Why: document_tabs.py was folded into fetch-meeting.py (verdict SLIM).

````markdown
5. **Select the transcript by the provider's stable tab ID** through `document_tabs.select_tabs`, never by title, order or a regular expression. Only a complete tab inventory establishes `transcript-tab-absent`.
````

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
8. **Never derive attribution from a tool summary.** Before a quote, approval, decision or owner cites an artifact, run `transcript_primary.py classify` and then `authorize-attribution` on one raw message location.
````

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
- [references/protocol-steps.md](references/protocol-steps.md): Steps 1 to 6 with every command (`verify_transcripts.py`, `transcript_primary.py`, `extract_commitments.py`), the email warning, the no-source marker, date verification and the daily-rituals integration. Read it before fetching a meeting, and for each member of a Step 0 sweep.
````

Why: Contents updated for the scripts that remain and for preserved.md.

````markdown
- [references/release-notes.md](references/release-notes.md) and [references/earlier-version-history.md](references/earlier-version-history.md): release notes from v0.2.0 to 0.14.0. Read them when a result differs from what an earlier version did.
````

Why: Contents updated for the scripts that remain and for preserved.md.

````markdown
- [optional-workspace-mcp/README.md](optional-workspace-mcp/README.md): the optional self-hosted multi-account server helper.
````

Why: Contents updated for the scripts that remain and for preserved.md.

````markdown
- [references/coverage-map.md](references/coverage-map.md): where each part of the earlier 0.14.0 text now lives.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
Use the verified Python acquisition modes documented in [declared acquisition entries](../synthesis-daily-rituals/references/acquisition-entry.md) for supported complete-window reads. They compose the current inventory, stable-tab, publication and watermark owners.
````

Why: the acquisition gate (declared acquisition entries, acquisition evidence, recorder readiness receipts, the Google REST and workspace-mcp custody adapters) was cut (verdict CUT); its read rules are protocol text now.

````markdown
Probe recorder identity at day-start using the owner's declared read-only adapter; HTTP health alone is not sign-in. Inventory every declared recorder source and account for the exact window, following all pages and retaining raw tool-call references and a same-source positive control. `inventory_documents` in the optional fetch owner provides a bounded adapter seam; never filter by meeting title or perceived relevance. Compare provider/source IDs against exact saved archive headers with `sync_watermark.py acquisition-check`; retain per-source gap decisions. Advance only with the verified acquisition evidence file; unknown enumeration or a missing archive keeps the watermark unchanged.
````

### optional-workspace-mcp/README.md

Why: the acquisition gate (declared acquisition entries, the Google REST and workspace-mcp custody adapters, recorder readiness receipts, the receipt-owned launcher) was cut (verdict CUT); fetch-meeting.py is plain standard-library Python again.

````markdown
## Verified acquisition and one-off lookup

For complete declared account/folder/window acquisition, use the verified
Python health/inventory/fetch route in [declared acquisition entries](../../synthesis-daily-rituals/references/acquisition-entry.md).
It explicitly selects the Google REST adapter; no service or token fallback
occurs. The documented workspace-mcp plain-text response does not supply stable
tab identity. A title lookup therefore cannot certify full-window coverage.

The separate one-off lookup still uses the local MCP server:

```text
synthesis exec-public synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py standup --date 2026-04-21
```

This mode requires source-native structured tab evidence before a verified save.
Service setup remains in the existing start/install owners and requires the
owner's authorization; acquisition does not install a service.
````

Why: the acquisition gate (declared acquisition entries, the Google REST and workspace-mcp custody adapters, recorder readiness receipts, the receipt-owned launcher) was cut (verdict CUT); fetch-meeting.py is plain standard-library Python again.

````markdown
## Prerequisites

- The verified runtime's selected interpreter contains httpx and PyYAML. Follow
  the dependency setup in the acquisition reference; a temporary uv interpreter
  is not the installed verified runtime.
- The existing meeting-transcripts YAML has the exact account/archive settings.
- MCP lookup additionally needs the declared local server and actual account
  authentication. The direct adapter instead consumes one explicitly referenced
  read token and the declared folder/tab contract; it never acquires a token.

The service doctor reports supervisor/HTTP liveness and retains its 0/1/2 exit
semantics. Its RECORDER UNKNOWN line is intentional. Actual declared account
authentication is observed only by the Python health route, and neither health
plane establishes complete source coverage.
````

### references/protocol-steps.md

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
- Step 4.6: Verify source grade with `transcript_primary.py` before attribution
````

Why: document_tabs.py was folded into fetch-meeting.py (verdict SLIM); the selection rules are unchanged.

````markdown
Unwrap every JSON-RPC/MCP tool-result envelope with the optional client's `call_tool_text` before reading text. An outer or nested tool error is unknown coverage. Select the transcript by the provider's stable tab ID through `document_tabs.select_tabs`, never by title, order, or a regular expression over flattened text. Missing tab inventory, incomplete tab inventory, missing content, absent declared tab, and empty returned tab have distinct reasons. Only a complete tab inventory establishes `transcript-tab-absent`; neither an error nor a flattened summary authorizes a no-source marker. Preserve every returned notes/transcript byte and the provider's tab IDs. Connector adapters must actually expose these capabilities; capability absence is a surfaced readiness gap.
````

Why: transcript_primary.py was cut (verdict CUT): the need is a reading rule, kept as binding rule 8 and in transcript-primary-and-commit-gate.md (v0.4.0, item 3); summary-versus-transcript is verify_transcripts.py's job, and only release wiring consumed its receipt.

````markdown
### Step 4.6: Verify source grade before attribution

Before a quote, approval, warning, decision, action owner, or close paraphrase
cites an artifact as primary, classify the artifact and then bind the claim to
one raw message location:

```bash
python3 <synthesis-meeting-transcripts-root>/transcript_primary.py \
    classify <artifact> --json

python3 <synthesis-meeting-transcripts-root>/transcript_primary.py \
    authorize-attribution <artifact> \
    --location 'permalink:https://example.slack.com/archives/C123/p1700000000000001' \
    --json
```

`classify` is a diagnostic and never issues authority. A derived artifact exits
1 even when it calls itself a transcript. `authorize-attribution` also exits 1
unless the file has dense, complete raw provider-message records and the
supplied `permalink:` or `message_ts:` belongs to one of those records in the
same input bytes. A
`thread_ts:` identifies a conversation, not the exact message supporting a
claim, so it is not sufficient for attribution authority.

The receipt expires when the file's bytes change. It does not verify semantic
fidelity, speaker identity beyond the stored labels, capture completeness
outside the artifact, or whether a later consumer cites the verified message
honestly; those limits remain in every result.
````

### references/release-notes.md

Why: the title gained 1.0.0.

````markdown
# Release notes: 0.14.0, 0.13.0, and v0.2.0 to v0.5.3
````

## Test fixtures of the cut transcript_primary.py (verbatim)

Synthetic, public test data for the cut classifier: a raw provider-message export it accepted and the 128-line structured summary (the engagement-motivating shape) it refused. Kept so the summary shape that once cleared a primary-transcript gate stays on record.

### fixtures/raw-message-transcript.md

````markdown
# Synthetic raw-message transcript

**Artifact type:** provider message export
**Capture bounds:** ten consecutive messages from one synthetic thread
**Content:** public test data only

## Messages

### Participant A — [9:00 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000000000001)
message_ts: `1700000000.000001`
thread_ts: `1700000000.000001`
The first message states the proposed direction.

### Participant B — [9:01 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000001000002)
message_ts: `1700000001.000002`
thread_ts: `1700000000.000001`
The second message asks how the result will be verified.

### Participant A — [9:02 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000002000003)
message_ts: `1700000002.000003`
thread_ts: `1700000000.000001`
The third message names the acceptance boundary.

### Participant C — [9:03 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000003000004)
message_ts: `1700000003.000004`
thread_ts: `1700000000.000001`
The fourth message identifies an unresolved question.

### Participant B — [9:04 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000004000005)
message_ts: `1700000004.000005`
thread_ts: `1700000000.000001`
The fifth message proposes a concrete check.

### Participant A — [9:05 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000005000006)
message_ts: `1700000005.000006`
thread_ts: `1700000000.000001`
The sixth message accepts that check.

### Participant C — [9:06 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000006000007)
message_ts: `1700000006.000007`
thread_ts: `1700000000.000001`
The seventh message records a source limitation.

### Participant B — [9:07 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000007000008)
message_ts: `1700000007.000008`
thread_ts: `1700000000.000001`
The eighth message distinguishes notes from the source.

### Participant A — [9:08 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000008000009)
message_ts: `1700000008.000009`
thread_ts: `1700000000.000001`
The ninth message assigns the final verification.

### Participant C — [9:09 AM](https://example-workspace.slack.com/archives/C0123456789/p1700000009000010)
message_ts: `1700000009.000010`
thread_ts: `1700000000.000001`
The tenth message closes the synthetic thread.
<!-- End of synthetic raw-message fixture. -->
````

### fixtures/structured-summary-128-lines.md

````markdown
# Primary Transcript Review Packet

- This file summarizes a longer source artifact.
- The source artifact is not embedded in this file.
- The prose groups themes instead of preserving message order.
- Names and details are synthetic for this public fixture.
- The heading deliberately overstates the file's evidence grade.

## Executive summary

- The discussion covered delivery, ownership, and sequencing.
- Participants appeared aligned on the immediate objective.
- Several tradeoffs were summarized without exact wording.
- The notes describe outcomes rather than individual messages.
- No raw provider identifiers accompany these statements.

## Themes

- One theme concerned how work should be staged.
- Another concerned who would verify the result.
- A third concerned how the outcome would be communicated.
- The order here was chosen by a summarizer.
- It does not preserve the source conversation's order.

## Decisions

- The group decided to continue with the proposed direction.
- A later validation step was described as required.
- An owner was inferred from the surrounding discussion.
- The exact speaker and wording are not preserved.
- These bullets are derived notes, not raw messages.

## Action items

- Participant A will inspect the generated artifact.
- Participant B will prepare a follow-up checklist.
- The team will compare the result with the stated goal.
- Timing is summarized without a source-message locator.
- Ownership is summarized without a source-message locator.

## Risks

- A missing dependency could delay the next step.
- A stale artifact could create contradictory evidence.
- A summary could flatten disagreement into consensus.
- A passive sentence could erase the responsible actor.
- None of these bullets identifies a raw message record.

## Delivery notes

- The first deliverable should be independently checked.
- The second deliverable depends on the first result.
- The notes collapse several exchanges into one statement.
- They do not preserve edits or reply relationships.
- They do not expose provider message identifiers.

## Timeline

- The opening topic was discussed around 09:10.
- A decision was reportedly reached around 09:25.
- The next topic began around 09:40.
- These inline times are part of summary prose.
- They are not raw-message timestamps or permalinks.

## Open questions

- Which artifact is the canonical source?
- Which participant made the final recommendation?
- Was the decision explicit or inferred by the summarizer?
- Which exact message supports the attributed statement?
- The summary cannot answer those questions by itself.

## Recommendations

- Preserve the original source alongside derived notes.
- Resolve attribution against the source before citation.
- Keep summary language explicitly marked as derived.
- Require a location for every attribution-bearing claim.
- Refuse a primary-source label when raw evidence is absent.

## Supporting observations

- The document is intentionally polished and concise.
- Its confident register does not establish provenance.
- Its internal consistency does not establish source grade.
- A filename or heading cannot upgrade the evidence.
- The source boundary must be checked mechanically.

## Review synthesis

- Reviewers found the summary useful for navigation.
- They did not treat it as a word-for-word record.
- Several clauses would require direct source confirmation.
- A source locator was requested but is unavailable here.
- The classification therefore remains derived.

## Quotation candidates

- A concise phrase was reconstructed from the notes.
- Another phrase was converted into reported speech.
- Removing quotation marks reduced asserted precision.
- It did not create firsthand evidence.
- Neither phrase has a raw-message location in this file.

## Attribution candidates

- Participant A was described as approving the direction.
- Participant B was described as warning about timing.
- The summary does not show who used either formulation.
- It cannot establish approval, warning, or ownership.
- Attribution-bearing use must fail closed.

## Completeness bounds

- The summarizer selected what appeared important.
- Omitted exchanges cannot be inferred from this artifact.
- Reply context and message edits are not represented.
- Reactions and deletions are not represented.
- These bounds make the artifact useful but derivative.

## Source notes

- The named upstream source is intentionally unavailable.
- No provider export is embedded or linked here.
- No message identifier can be resolved from this file.
- No permalink density can establish raw-message structure.
- This final block completes the 128-line fixture shape.
<!-- End of synthetic structured-summary fixture. -->
````
