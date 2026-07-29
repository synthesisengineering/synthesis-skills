---
name: synthesis-message-guard
description: Fail-closed pre-send enforcement for agent-drafted correspondence. A PreToolUse hook blocks every message-sending or draft-creating tool call unless the outgoing text passes a deterministic register scan AND a fresh, single-use grounding ledger — sha256-bound to the exact message — attests that the composing agent read the full thread, searched prior correspondence, and mapped every factual claim to a source. Use when setting up, debugging, or composing under the guard; when a send is blocked; or when asked about message grounding, voice enforcement, or pre-send gates.
---

# Message Guard

**Version 1.0.0** (2026-07-29)

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
  The engine refuses to run without it.
- **Ledger:** `~/.synthesis/message-guard/ledger.json` — written per message,
  consumed on use (single-shot; no reuse across messages). Passed sends are
  appended to `log.jsonl` with the full ledger for audit.
- **Wiring:** a `PreToolUse` entry in `~/.claude/settings.json` matching the
  send/draft tool family across all MCP servers by name pattern.

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
message_guard.py --doctor          # config, controls, wiring, state dir
message_guard.py --test            # behavioral suite (12 cases)
```

## Guarantees and their proofs

1. **Fail closed.** No ledger, stale ledger, sha mismatch, unknown tool shape,
   unreadable config, or ANY internal exception → the send is blocked with
   remediation on stderr. Proven by `--test` cases including a
   missing-config invocation.
2. **Positive controls.** `--doctor` requires a known-bad text to trip the
   scanner and a known-clean text to pass — a scanner that stops matching is
   detected, not trusted.
3. **Calibration.** The pattern set must PASS the principal's real sent
   messages and BLOCK the incident drafts. Re-run calibration whenever
   patterns change; a guard that blocks the principal's own voice is
   miscalibrated, not strict.
4. **Monitored.** The doctor runs in the day-start ritual (synthesis-daily-
   rituals Step 1) alongside the commit-hook doctor. A guard nobody monitors
   is already broken.

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
5. Write the ledger (`--sha` for the hash). Call the tool. The gate verifies.

## Related

- `synthesis-git-hooks` — the same fail-closed philosophy at the commit
  boundary; this skill is its correspondence twin.
- The principal's private writing-voice skill — the source of truth the block
  patterns are derived from; patterns.json cites it.
- `synthesis-daily-rituals` — runs `--doctor` at day-start.
