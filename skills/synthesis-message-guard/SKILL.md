---
name: synthesis-message-guard
description: Fail-closed pre-send enforcement for agent-drafted correspondence. A PreToolUse hook blocks every message-sending or draft-creating tool call unless the outgoing text passes a deterministic register scan AND a fresh, single-use grounding ledger — sha256-bound to the entire tool input — attests that the composing agent read the full thread, searched prior correspondence, and mapped every factual claim to a source. Use when setting up, debugging, or composing under the guard; when a send is blocked; or when asked about message grounding, voice enforcement, or pre-send gates.
license: "Apache-2.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "1.7.0"
  source_repo: "github.com/synthesisengineering/synthesis-skills"
  source_type: "public"
---

# Message Guard

**Version 1.3.0** (2026-09-01) adds `patterns.example.json`, the public,
validator-backed starting point used by `synthesis-onboarding init`. The
scaffolder preserves the user's local copy and can add interview-supplied wording
boundaries without putting personal policy in this repository. A fail-closed
message gate now ships the route to a valid config instead of requiring adopters
to reconstruct one from prose.

**Version 1.2.0** (2026-08-28) — adds `check_header_hygiene`: the gate now inspects the
RFC threading headers (`in_reply_to`, `references`) in the tool input, not only the message
text, and blocks a send whose Message-ID has been HTML-escaped (`&lt;id@host&gt;`) or left
with an unbalanced angle bracket. Such a header matches no message, so the reply orphans in
any strict RFC client — but Gmail's own `thread_id` threading masks it whenever the caller
passes both, which is why the error survived review and recurred (2026-08-20, 2026-08-28).
A malformed header is now structurally undeliverable rather than silently wrong.

**Version 1.1.0** (2026-07-29)

Prose rules do not survive contact with a model under load. This skill is the
enforcement layer for correspondence the way commit hooks are the enforcement
layer for repositories: the rules live in code, run outside the model, and fail
closed.

## Why it exists

Two same-night incidents (2026-07-29), both by an agent that had the relevant
rules loaded in context:

1. **A reply composed without reading the thread it was replying into.** The
   thread's own quoted history contained the principal's earlier message taking
   the opposite strategic position, with a better argument. The reply was sent.
   Correcting it cost a follow-up email and real trust.
2. **A drafted message containing register patterns the principal's written
   voice rules explicitly ban** (self-flagellation about a delayed reply;
   expressing trust in a colleague via the author's own limitation). The
   principal had warned about exactly this class before.

Both failures were rule-knowledge failures at compose time, not knowledge gaps.
The fix is structural: make the send mechanically impossible until the work is
attested and the text passes a deterministic scan.

## Architecture

```
composing agent                      engine (stdlib python, fail closed)
--------------                       ----------------------------------
1. research: full thread read,       PreToolUse hook on every send/draft
   history search, claims→sources    tool call:
2. compose                             a. register scan of outgoing text
3. self-scan:   --scan < draft            (block patterns from config)
4. write ledger (sha256 of exact       b. ledger present, fresh (<45 min),
   tool input + attestations)             sha256 matches every input field,
5. call the send/draft tool               attestations complete
                                       c. pass → log + consume ledger
                                          fail → exit 2, send blocked
```

- **Engine:** `scripts/message_guard.py`. Stdlib only — identical behavior
  under any python3 (lesson inherited from a PyYAML-dependent guard that
  failed open for weeks). Any internal error blocks the send.
- **Config:** `~/.synthesis/message-guard/patterns.json` — private, per-person.
  Block/warn regexes, gated tool patterns, exemptions, freshness window.
  The engine refuses to run without it. `patterns.example.json` supplies policy defaults, not transport readiness. Follow the [onboarding owner workflow](../synthesis-onboarding/references/message-guard-onboarding.md), supply reviewed capabilities and validate the exact configuration before wiring. Copying the template alone is not a ready installation.
- **Ledger:** `~/.synthesis/message-guard/ledger/<message-sha256>.json` — one
  per message, consumed on use (single-shot; no reuse across messages). File it
  with `--write-ledger`, which derives the path from the ledger's own
  `message_sha256`: you never type a path, so you cannot misfile one. Keying by
  sha is what lets several seats compose at once. A single shared slot could
  not: the second seat's write replaced the first's, and the first seat's send
  was then refused for a sha mismatch — reported as "you edited the text after
  grounding," which was false and pointed at the wrong repair. Passed sends are
  appended to `log.jsonl` with the full ledger for audit.
- **Wiring:** equivalent `PreToolUse` entries in Claude Code's
  `~/.claude/settings.json` and Codex's `~/.codex/hooks.json`, each matching
  the send/draft tool family across all MCP servers by name pattern. The doctor
  requires every installed client to carry the guard.

## Peer-session sends (config-adopted)

Agent-to-agent session messaging has a different failure mode from
correspondence: not register drift but **misdelivery** — a target chat
session chosen by guessing a title or display label. Adopting
`peer_send_resolution` in `patterns.json` gives those tools their own lane,
which runs before the exempt list and replaces the ledger lane for matching
calls:

```json
"peer_send_resolution": {
  "tool_pattern": "ccd_session_mgmt__send_message$",
  "target_field": "session_id",
  "board": "~/.synthesis/coordination/active-sessions.md"
}
```

The target session id must appear as an **active client session ref** on the
coordination board (schema v4, registered at claim time) — otherwise the send
blocks with instructions to run `coordination.py resolve` or use the board
message bus. An unreadable board blocks (fail closed). Unadopted instances
keep the old posture — inter-session tools stay in `exempt_tool_patterns` —
and the doctor says which posture is live. Requires the tool's PreToolUse
wiring to route these calls to the guard; the doctor checks that too.

## Currency claims carry read freshness (config-adopted, v1.5.0)

A claim such as "still unanswered", "unsent", or "no reply yet" is a
statement about NOW that rests on a read taken at some moment. The ledger
recorded WHERE such a claim came from but not WHEN the source was read, so
on 2026-09-01 a "still unanswered by the principal" claim resting on a read
eight hours old passed as verified while the answer had gone out that
morning — a false receipt in the layer built to stop exactly that.

Adopt the lane by adding to the config:

```json
"currency_claim_patterns": ["\\b(unanswered|unsent|not (yet )?(replied|responded|answered|sent)|no (reply|response|answer)( yet)?|still (open|waiting|pending|unanswered)|has(n't| not) (replied|responded|answered|sent))\\b"],
"currency_claim_max_age_minutes": 30
```

With it adopted, every `claims[]` entry whose text matches a pattern must
carry `read_at` (ISO-8601, the moment the source was read THIS run), and
the send is blocked when `read_at` is missing or older than the maximum —
the remedy is to re-read the source and refresh it. Stable facts ("PR 96
merged") need no `read_at`. Without the keys the lane is off and the doctor
says so. `--ledger-template` shows the field.

## The ledger contract

`--ledger-template` prints the skeleton. Fields the engine enforces:

| Field | Rule |
|---|---|
| `created_at` | ISO-8601; older than the freshness window → block |
| `message_sha256` | must equal the canonical digest of the complete `tool_name` and `tool_input` JSON (`--message-sha`) |
| `is_reply` | required boolean |
| `thread_fully_read.source_ids` | non-empty when `is_reply` — the message IDs / ts values actually fetched this session |
| `history_searched[]` | non-empty when `is_reply` — each entry: query, where, results |
| `claims[]` | every factual claim → source; or `no_factual_claims: true` |
| `voice_rules_pass` | explicit `true` after loading the voice skill |
| `invented_precision_scan` | explicit `true` — every number in the text has a source |
| `recipient_address_check` | explicit `true` — right person, right address |
| `ragbot_branding_check` | required `true` for direct sends as the agent |

The ledger cannot make a model honest, but it converts skipping the research
from an invisible omission into a deliberate written lie — auditable in
`log.jsonl` — and the deterministic scan layer is model-independent entirely.

## Modes

```bash
message_guard.py --gate            # hook mode (stdin: tool-call JSON)
message_guard.py --scan  < draft   # pre-check wording; exit 2 on block hits
message_guard.py --message-sha < tool-call.json # all fields bound to the ledger
message_guard.py --ledger-template # skeleton
message_guard.py --write-ledger    # stdin: ledger JSON -> files it at its own sha
message_guard.py --message-ledger-path < tool-call.json # exact ledger path
message_guard.py --doctor          # config, controls, all client wiring, state dir
message_guard.py --test            # behavioral suite (31 cases)
```

## Guarantees and their proofs

1. **Fail closed.** No ledger, stale ledger, sha mismatch, unknown tool shape,
   unreadable config, or ANY internal exception → the send is blocked with
   remediation on stderr. Proven by `--test` cases including a
   missing-config invocation.
2. **Positive controls.** `--doctor` requires a known-bad text to trip the
   scanner and a known-clean text to pass — a scanner that stops matching is
   detected, not trusted. Since 1.6.0 the known-clean text is a canonical
   SIGNED agent message (the Ragbot signature line in Slack wire form): on
   2026-08-03 a generic clean control passed while a retired-branding pattern
   compiled under IGNORECASE blocked every real signed send. Add your own
   canonical messages with `doctor_clean_controls` so a pattern change that
   blocks real traffic fails the doctor.
3. **Calibration.** The pattern set must PASS the principal's real sent
   messages and BLOCK the incident drafts. Re-run calibration whenever
   patterns change; a guard that blocks the principal's own voice is
   miscalibrated, not strict.
4. **Monitored across clients.** The doctor runs in the day-start ritual
   (synthesis-daily-rituals Step 1) alongside the commit-hook doctor. It checks
   Claude Code and Codex independently whenever each client is installed; one
   healthy client cannot hide an unwired peer.

## Known limits — stated, not hidden

- **Judgment failures pass the scan.** A condescending-but-pattern-free
  sentence, a strategically wrong recommendation, or a subtly mis-scoped legal
  claim will not trip a regex. Those are caught by the ledger's forced research
  step and, for high-stakes messages, by adversarial multi-agent review. The
  scan removes the *enumerable* failure modes; the ledger makes the research
  auditable; neither replaces review.
- **Execution tools can invoke other transports.** Capability enrollment does not parse arbitrary shell programs or prove absence of network effects. Sending through an unapproved transport is prohibited; retain native sandbox/network controls and explicit communication authorization. Never classify a general execution tool as read-only from its name.
- **Hook config loads at session start.** A newly wired hook protects new
  sessions; the wiring session itself must self-enforce.

## Composing under the guard (the honest workflow)

1. Read the FULL thread you are replying into — including quoted history.
   The thread's own tail is a primary source; a reply that contradicts it is
   the canonical incident.
2. Search prior correspondence for the recipient AND topic — every mailbox the
   principal uses, plus local transcripts. Record the queries.
3. Compose. Run `--scan`. Fix hits by rewriting the thought, not by
   thesaurus-dodging the regex.
4. Map every factual claim to its source. A claim you cannot source becomes a
   question to the recipient or gets cut.
5. Freeze the complete tool call, including recipients, subject, alternate parts and threading fields. File the ledger: `--message-sha` for the hash, then pipe the ledger JSON to
   `--write-ledger`. Call the tool. The gate verifies.

## Multipart integrity and email defaults

The engine recursively scans every populated string in a recognized message
object, including every HTML and plain-text part. It scans rendered HTML as well
as source so entities and inline elements cannot conceal banned wording. The
canonical `synthesis-message-v2` digest binds **the entire tool input** and the
tool name, including recipients, subject, thread headers and attachment
references. Object-key ordering does not change it; array ordering and any field
change do. A text-only ledger cannot authorize the new gate. Re-ground and bind
pending messages to the complete frozen call; do not reinterpret old ledgers.
`--sha` and `--ledger-path` remain raw-text utilities, never send-ledger commands.

Email defaults to HTML with paragraph markup and no rendered breaks inside a
paragraph. Nested literal MIME-style text parts are checked by their declared
content types, not only their field names. Encoded/opaque nested text requires a
verified transport adapter; a payload digest does not inspect its rendered words. HTML source newlines that render as spaces are allowed. The local
constructor takes `paragraphs` plus explicit `to`, `cc`, `bcc`, and `subject`
fields, escapes literal prose, and joins wrapped source lines. Rich link and
persona signature markup may be composed explicitly and checked by the same
gate. It must follow the correspondence and private disclosure skills.

The owner may deliberately set `email_policy.default_format` to `plain`, or
`email_policy.allow_intra_paragraph_breaks` to `true`. These are independent
configuration choices, useful for a transport requiring plain text or content
whose line structure matters. A payload's `override` flag has no authority.
Overrides change formatting only: grounding, register, recipient, branding,
threading, human approval and disclosure requirements remain in force. The
constructor and MIME helper never send or file drafts.

```json
"email_policy": {
  "default_format": "html",
  "allow_intra_paragraph_breaks": false
}
```

## Owner-managed capability enrollment

A transport whose native schema has no format selector declares `fixed_format: plain` or `fixed_format: html` in its owner capability, together with its actual
`body_field`. This is mutually exclusive with `format_field`, `html_value`, and
`plain_value`; callers cannot change the fixed format through payload fields.
The HTML default still refuses a fixed-plain transport. Only an explicit owner
plain-text policy override permits it, with the same paragraph checks and exact
whole-call approval. Native schema evidence must establish the fixed format.


Use the actual selected client's complete tool catalog, including descriptors
and input schemas. Export or collect the native catalog through its owner; do
not ask the operator to type tool names or invent missing descriptors. Normalize
it to `{ "client": "codex", "source": "evidence reference", "complete": true,
"total_tools": N, "next_cursor": null, "tools": [...] }`, where `N` is the exact
length of `tools` and each tool has `name`, `input_schema`, and any captured
annotations. Preserve the collector's original pagination and origin evidence
separately. Missing completeness, an outstanding cursor, mismatched totals, or
unknown envelope fields refuse enrollment. These assertions are required inputs,
not proof that the collector actually saw every native tool. The
supported client labels are `claude`, `codex` and `muse`.

1. Run `--capability-plan` with the catalog JSON. Existing owner declarations
   become proposals. Unrecognized tools require semantic review of their real
   schema and behavior. A name, description, or `readOnlyHint` is not permission.
2. Submit `--capability-enroll` an object containing `inventory`, `owner_review`
   (`inventory_digest` and a real authorization/evidence `source`), and one
   `decisions` entry per descriptor. Each decision binds `name`,
   `descriptor_sha256`, and a `capability`: `email`, `human-text`, or exact
   `non-correspondence`. Email declarations also specify `body_field` and
   `format_field`, with optional `html_value` and `plain_value`; nested fields use
   JSON Pointer. Review code/schema rather than guessing from names. Peer-session
   routing still belongs to its existing board-resolved lane.
3. Preserve the proposed registry through the configuration owner. Run
   `--capability-readiness --capabilities-file <registry>` on a freshly captured
   catalog before activating broad hooks. Added, removed, changed, ambiguous or
   unclassified descriptors block readiness with a concrete drift report.
4. Have the configuration owner apply the reviewed hook diff and verify real
   invocation in each selected client. `--dispatch` recognizes exact enrolled
   non-correspondence tools without requiring a message ledger and gates
   correspondence through the same engine. Dispatch refuses absent, partial, or
   inconsistent enrollment before applying any exemption. Unknown tools fail closed. Do not
   install a catch-all hook until the complete inventory is ready.

Enrollment prints a proposal; it does not activate hooks, claim that a human
approved it, or prove the supplied inventory came from the running client.
Registries are private, owner-managed policy. Reconcile catalog drift at startup
and whenever tools change. The per-call event does not include the full catalog;
readiness of a stale supplied inventory cannot prove native catalog freshness.

**Engine migration is an owner-managed release gate.** Existing `--gate` hooks
resolve the public engine immediately; installing new bytes changes their digest
and format contract even without activating `--dispatch`. Before installation,
the configuration owner must inventory existing transports and pending messages,
prepare exact body/format mappings and deliberate formatting overrides, re-ground
pending full tool calls, and qualify the candidate's legitimate and forbidden
controls against that prepared configuration. Do not translate old text-only
ledgers into approvals, discard them, infer approval from a migration script, or
publish a healthy-install claim from matcher-only doctor checks. Preserve the old
ledger evidence and record its owner disposition. If real catalogs, transport
mapping or pending-message custody are unavailable, publish source separately
and retain the selected-client installation gate until this transition is ready.
Then activate the reviewed configuration and engine together through their owners,
followed by native invocation/readback acceptance. Broad-hook proposals remain
unactivated until the complete catalog and classification review are available.

The existing engine owns a read-only `--migration-plan` and
`--migration-preflight`. An existing installation must explicitly declare its
transport mappings and email policy. Missing mappings refuse. A fixed transport
that cannot satisfy the selected policy remains unavailable and requires an
explicit retained disposition in the owner record; supported transports remain
usable. The preflight never changes policy.
The plan returns the exact `required_record` for the owner to review. Preserve
its fields and add `owner_review` with an attributed `source` and timezone-aware
`reviewed_at`, then save it at the returned `record_path` through the owner.
This record binds the candidate engine, exact configuration bytes and every
retained local pending-ledger file. Each pending disposition remains
`retain-for-regrounding`; the record neither translates approvals nor permits a
send. Changed evidence requires a new owner review. Aliases, special files,
ambiguous JSON and custody limits refuse. The engine reads at most 1 MiB per
file, 4,096 pending files and 8 MiB of pending evidence.

The combined release preflight and the central CLI activation owner enforce this
check before changing the selected generation, with a recheck under the
activation lock. `NOT_CONFIGURED` identifies absence of a local message-guard
configuration; it is not a healthy installed guard. `READY_FOR_OWNER_ACTIVATION`
qualifies the exact local migration inputs only. Provider drafts remain
`NOT_INSPECTED`, native catalog coverage remains `NOT_ESTABLISHED`, and broad
dispatch still needs its separate complete-catalog enrollment and native tests.

Do not auto-pass new tools to keep an unattended run moving. Preserve other
protective hooks and legitimate non-email workflows during the owner merge.

## Readback and ritual monitoring

Use `--build-email` for local paragraph construction and `--build-mime` for a
synthetic MIME representation. `--verify-readback` accepts `expected` (the
constructed message object) and `raw_mime` (the full fetched MIME string). It
decodes transfer encoding, inspects every text part, and compares the complete
expected part list, MIME topology and To/Cc/Bcc/Subject/Reply-To/In-Reply-To/
References headers, plus From and Message-ID when supplied. The expected MIME
object accepts `body`, `body_format`, `to`, `cc`, `bcc`, `subject`, `reply_to`,
`in_reply_to`, `references`, `from`, and `message_id`; only address fields accept
lists. Unknown expected fields, including provider-only `thread_id` and attachment
references, refuse verification instead of receiving a misleading whole-input
receipt. Use a reviewed transport adapter that binds those fields to actual
provider readback when needed. Text attachments, disposition/filename changes,
duplicate control headers, malformed transfer encodings, excessive depth, rewritten
links, changed or extra parts and lost HTML refuse verification. Attachments or
other MIME parts need a separately reviewed transport adapter; they are not silently
skipped. Native transport normalization must be established from an actual raw
readback before a new adapter can declare it acceptable.

After an authorized draft/send, fetch the exact draft/message through the
transport's read operation; retain the message ID, tool result, requested fields,
raw readback and verifier output in private evidence. A synthetic constructor
roundtrip proves the local contract only. `VERIFIED_SUPPLIED_READBACK` explicitly
does not attest that a transport was contacted or a message was delivered.

`--monitor-email` consumes a bounded list of records with `message_id`,
`raw_mime`, and optional `expected`. It checks every supplied record and returns
counts plus per-ID violations; no sends or mailbox changes occur. The ritual
owner must record the selected accounts, time window, pagination/completeness
and unreadable IDs alongside the result. An empty or partial export cannot
establish absence of defects. Failures get a private actionable report; never
silently re-send or modify old messages. The guard can verify syntax and evidence
consistency, but does not manufacture transport, authorization or live-hook proof.

Bounds are 8 MiB for a tool payload or monitoring batch, 4096 JSON values,
32 levels of nesting, 128 MIME parts, and 1000 supplied monitoring records.
Whichever bound is reached first refuses the operation. Split monitoring into
recorded batches with complete window coverage. Source controls also apply to
the setup-owned standalone script; no extra runtime module is required.

## Related

- `synthesis-git-hooks` — the same fail-closed philosophy at the commit
  boundary; this skill is its correspondence twin.
- The principal's private writing-voice skill — the source of truth the block
  patterns are derived from; patterns.json cites it.
- `synthesis-daily-rituals` — runs `--doctor` at day-start.


## Other human-readable correspondence

Declared `human-text` capabilities use the same default against unintended
intra-paragraph breaks. `--build-text` accepts a `paragraphs` list and returns a
literal `message` with source wrapping normalized. Use
`paragraph_policy.allow_intra_paragraph_breaks: true` only as an explicit
owner-controlled override for intentional line structure such as code, poetry
or an address block. This policy is separate from email's format selection.
It changes no disclosure, send approval or grounding requirement. Never run a
prose normalizer over content whose literal whitespace carries meaning.

`--verify-text-readback` compares supplied `expected` and `observed` strings
exactly and checks the selected paragraph policy. Preserve actual post IDs and
fetch evidence when invoking it after an authorized write. Native link/markup
normalization requires empirical adapter qualification; an exact mismatch is
not silently rewritten into success. Include human-text posts in the ritual's
account/window coverage, using this verifier for each fetched record. Missing
or unreadable posts stay explicit in the coverage report.

Fresh setup uses the read-only `--configuration-preflight` owner mode to validate declared transport mappings and return a canonical configuration digest. `--policy-preflight` validates stored policy, including existing owner pattern declarations, without consulting capability overrides or claiming native loading. The doctor refuses missing capabilities, checks every exact declared correspondence name against hook coverage, and refuses broad dispatch without a valid stored capability registry. Stored registry validity does not prove a fresh native catalog.
