---
name: synthesis-message-guard
description: Fail-closed pre-send enforcement for agent-drafted correspondence. A PreToolUse hook blocks every message-sending or draft-creating tool call unless the outgoing text passes a deterministic register scan AND a fresh, single-use grounding ledger — sha256-bound to the exact message — attests that the composing agent read the full thread, searched prior correspondence, and mapped every factual claim to a source. Use when setting up, debugging, or composing under the guard; when a send is blocked; or when asked about message grounding, voice enforcement, or pre-send gates.
license: "Apache-2.0"
depends_on: ["synthesis-agent-correspondence"]
metadata:
  author: "Rajiv Pant"
  version: "1.6.0"
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
   final text + attestations)             sha256 matches the exact text,
5. call the send/draft tool               attestations complete
                                       c. pass → log + consume ledger
                                          fail → exit 2, send blocked
```

- **Engine:** `scripts/message_guard.py`. Stdlib only — identical behavior
  under any python3 (lesson inherited from a PyYAML-dependent guard that
  failed open for weeks). Any internal error blocks the send.
- **Config:** `~/.synthesis/message-guard/patterns.json` — private, per-person.
  Block/warn regexes, gated tool patterns, exemptions, freshness window.
  The engine refuses to run without it. Start with `patterns.example.json` or run
  `synthesis-onboarding init`; both paths are validated before wiring the guard.
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
| `message_sha256` | must equal sha256 of the exact outgoing text (`--sha`) |
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
message_guard.py --sha   < draft   # sha256 for the ledger
message_guard.py --ledger-template # skeleton
message_guard.py --write-ledger    # stdin: ledger JSON -> files it at its own sha
message_guard.py --ledger-path < draft  # where this text's ledger belongs
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
- **Bash is not gated.** Sending mail via raw shell would bypass the hook.
  Doing so is prohibited by rule; the hook covers every legitimate send path
  (the MCP tools).
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
5. File the ledger: `--sha` for the hash, then pipe the JSON to
   `--write-ledger`. Call the tool. The gate verifies.

## Related

- `synthesis-git-hooks` — the same fail-closed philosophy at the commit
  boundary; this skill is its correspondence twin.
- The principal's private writing-voice skill — the source of truth the block
  patterns are derived from; patterns.json cites it.
- `synthesis-daily-rituals` — runs `--doctor` at day-start.
