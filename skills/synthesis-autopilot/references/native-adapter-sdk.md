# Additional native adapter qualification SDK

The additional adapters decode bounded observations for Cursor, GitHub Copilot, and OpenCode. They share the existing source reader and capability inventory. They do not authenticate a native producer, admit a run, grant a tool permission, or certify a task outcome. `assess()` keeps native and outcome cells `UNKNOWN`; a source file or a caller's `mode="native"` cannot change them.

## Implemented source contracts

| Client package | Input grammar | Useful observations | Qualification boundaries |
| --- | --- | --- | --- |
| `native_cursor` | Cursor documented hook inputs with `hook_event_name`; explicit capture route for IDE, CLI, or cloud | Session/generation IDs, tool-use IDs, structured tool results, interruption, compaction, subordinate child observations | No provider token schema. Child-stop without a child ID cannot cancel the root. Hook deployment and permissions require exact-surface native tests. |
| `native_copilot` | Documented camelCase and PascalCase hooks; SDK event schema from `@github/copilot-sdk` 1.0.14 | Session IDs, SDK tool-call IDs, API-call usage identity, root/child cancellation distinction, compaction and permission observations | CamelCase hook route must come from a retained capture envelope. Hooks lacking call IDs cannot be paired by adjacency. SDK previous-event links are retained but do not prove complete delivery. CLI, VS Code, and cloud are separate surfaces. |
| `native_opencode` | V2 event and SDK readback schemas from `@opencode/client` 2.0.16 | Session/parent IDs, durable sequence, tool-call IDs, direct-shell result and output range, response usage, compaction, interruption and permission observations | OpenCode V1 is a different protocol. A live subscription has no replay guarantee. Tool names on `session.tool.called` need their earlier identity event. A readback's session request needs owner-held transport custody. |

Copilot protection is **`FAIL_OPEN_PATHS`**. The official hook reference says command-hook timeouts and HTTP-hook failures can allow execution. A registered hook, a successful hook call, or this adapter's presence cannot justify a protected-client badge. Cursor's `failClosed` must be configured and tested on the selected surface; `preToolUse`'s `ask` result and `sessionStart`'s `continue=false` do not establish enforced approval. OpenCode permission replies are observed data; this package emits none.

## Python interfaces

Each package exports the same observation interface as the existing native dialects:

```python
qualify_source(header, *, expected_root_session_id,
               expected_thread_id=None, expected_parent_thread_id=None,
               expected_agent_id=None)
decode_record(row, producer, *, mode="synthetic", source_locator=None)
describe_contract()
is_ignored_projection(projected, producer)
record_sequences(row, producer)
```

`qualify_source` checks the declared native identity and lineage. Its returned producer always has `authentication="owner_admission_required"` and `root_authority=False`. Decode candidates carry typed facts, native IDs, source locators, and an explicit mode. Tool results always keep `outcome_pass=False`. User text never proves a human identity or grants authority.

The shared `native_observations` reader imports these packages through its fixed registry. It retains its bounded incremental reader, source generation and current-range verification. Capture order and OpenCode durable order are independent sequence lanes in the existing cursor. Repeated, reversed, or skipped sequence values refuse complete coverage. Suffix revalidation accepts `prior_sequences` only from the owner-verified cursor at its exact lower boundary; an arbitrary caller frontier is not evidence. Ingestion commits still belong to the existing admitted journal/CAS owner.

This package does not widen `observation_bridge` or PM root admission. An unsupported client cannot become a run owner merely by supplying a valid header. Existing owner commands reject a substituted additional-client transcript and preserve the journal. A future admitted native transport must join the actual surface, session, producer build, permission posture, and current source bytes through the current PM/native owner. It must not add a second journal or issue a reusable caller-controlled verification token.

The qualification SDK provides:

```python
capture_record(client, surface, event, payload, *, session_id,
               producer_version, capture_id, sequence)
inspect_source(path, *, client, session_id, mode="synthetic",
               max_pages=16, page_bytes=1024*1024)
assess(surface, *, required=(), source_report=None)
```

`capture_record` wraps a transport payload. The envelope is a provenance claim, not a signature. Retain the original native source and exact byte locators separately when transforming SSE, HTTP readbacks, or other wire formats into captured JSONL. Capture IDs, versions, sessions, and surface labels cannot change inside one source. The SDK refuses cached modules loaded from another source tree.

`inspect_source` invokes the actual bounded reader, reducer, and current-positive-range revalidator. It reports diagnostics, gaps, pending bytes, coverage and observations. Its source status `CURRENT` means those selected bytes decoded and revalidated within the reported scope. It does not mean complete native delivery, authenticated origin, historical absence, or current task acceptance. Positive event memory is capped at 512; use the admitted journal reader for longer runs. The JSON parser caps input at 1 MiB, depth at 32, nodes at 16,384, and arrays/objects at 1,024 entries. OpenCode assistant readbacks are capped at 64 content parts; larger material remains a reference/gap requiring bounded reconciliation.

`assess` obtains surfaces from the canonical capability registry and returns separate `documented`, `implemented`, `installed`, `native`, and `outcome` cells for ten capabilities. Required capabilities stay unresolved until their actual native/outcome owners supply qualifying evidence. JSON assertions such as `verified=true` and `native_provenance="VERIFIED"` cannot satisfy a requirement. Source availability does not change the existing surface levels: Cursor/Copilot remain skill-only, and OpenCode is observation-only.

## Strict JSON command interface

The SDK script accepts one JSON object on stdin and emits one bounded JSON result. It supports only `describe` and `inspect`; it has no action callback, native executor, installer, permission response, Goal, scheduler, or settings operation.

```json
{"operation":"describe","surface":"copilot-cli"}
```

```json
{"operation":"inspect","path":"/absolute/public-fixture.jsonl","client":"opencode","session_id":"session-public","mode":"synthetic"}
```

Unknown fields, duplicate fields, scalar requests, malformed JSON and nonfinite numbers return `UNRESOLVED` with a nonzero exit. The output cap is 4 MiB. Large transcripts use paginated native ingestion rather than an unbounded qualification response.

## Qualification procedure

1. Pin and verify the official client and schema artifacts before execution. Record the exact version, binary/package digest, surface, account boundary, permission configuration, source paths and bounded trial procedure. Installed discovery and `--help` output prove neither tool execution nor permissions.
2. Start with a public synthetic fixture. Through the real client, produce a harmless tool result with a unique native call ID and independently read the current result bytes. Retain failed/refused attempts. A direct API shell call proves only that local native consumer; it does not prove provider-driven tool use or approval enforcement.
3. Attempt a denied effect within the delegated test scope and observe the actual refusal. Test crash/timeout behavior separately where the official surface can fail open. Never bypass the native permission decision to make the test pass.
4. Observe an active cancellation and terminal readback with exact session/turn/child IDs. An idle `interrupted=false`, a request acknowledgement, a killed probe process, or a child-stop alone is not root cancellation acceptance. Keep all unresolved child and background work visible.
5. Test same-size tampering, truncation, replacement, missed notifications, partial and oversized records, duplicate response IDs, unknown grammar, sequence holes, provisional counters and root/child identity substitution. Revalidate current positive ranges at consumption. Keep cumulative/aggregate counters separate from per-response settlement; billing and full-tree scope remain unknown without independent proof.
6. For recovery and continuation, name the actual tested horizon and reconstruct the existing journal and source custody. Live event streams, retained state, manual resume, and scheduled delivery are different claims. No Goal, schedule, plugin registration, permission observation, or native success message can complete the portable task.

If authentication, a license, workspace trust, UI presence, or a user-owned permission choice is required, record the exact surface and missing action. The decoder and synthetic controls remain usable while those native gates remain unresolved. Do not replace a required capability with a simulated success.

## Primary specifications

The source contracts were checked against these primary interfaces on 2026-09-25:

- [Cursor hooks](https://cursor.com/docs/hooks) and [CLI output formats](https://cursor.com/docs/cli/reference/output-format). CLI print streams are not claimed by the hook decoder.
- [GitHub Copilot hook reference](https://docs.github.com/en/copilot/reference/hooks-reference), [CLI quickstart](https://docs.github.com/en/copilot/get-started/cli-quickstart), and [official Copilot SDK](https://github.com/github/copilot-sdk).
- [OpenCode V2 client](https://opencode.ai/v2/docs/build/client), [SDK](https://opencode.ai/v2/docs/build/sdk), [API](https://opencode.ai/v2/docs/api), and [OpenAPI schema](https://opencode.ai/v2/openapi.json). The experimental session log and live subscription have different retention contracts; a `log.synced` frontier alone does not supply historical records.

### Native call identity

Tool pairing requires a native call ID and the same source generation, producer,
mode and native call scope. Copilot SDK scope retains the actual `agentId`
(including the root's null value); Cursor scope retains `conversation_id` and
`generation_id`. Those raw scope fields participate in semantic identity and
current-byte rederivation. A root call cannot consume a child result, and a
Cursor result cannot reuse a call from another generation. Hook records lacking
a native call ID remain separate `missing_identity` observations even when their
names, arguments or positions match. Source currentness alone is not a paired
process result or outcome authority.
