# Slack sync: lookups, absence claims and backfills

Read before any historical lookup or verification question ("did X get sent?", "did anyone reply?"), before claiming something did not happen, before a backfill, or when a message continues an earlier discussion.

Contents:
- NEVER Use Slack Search API for Lookups: the only valid uses of the MCP API
- The question-shape trigger
- A zero-result search is NEVER evidence of absence
- Backfills and archive imports
- Following Continuing Conversations

## ⛔ NEVER Use Slack Search API for Lookups

**When verifying whether a message was sent, or looking up past conversations, ALWAYS read local transcript files first.** Use `Grep` on transcript files in the transcripts directory. NEVER call `slack_search_public`, `slack_search_public_and_private`, or `slack_read_channel` for historical lookups.

The Slack search API has indexing delays (recent messages don't appear), misses thread replies entirely, and is slower and more expensive than local file reads. On 2026-04-01, four Slack search API calls returned "no results" for messages that existed in threads — nearly causing duplicate messages to be sent.

**The only valid uses of the Slack MCP API are:**
1. Syncing NEW messages during this protocol (Steps 1-3)
2. Reading a specific thread by TS that was never synced locally

### The question-shape trigger

**This rule covers VERIFICATION, not just "lookups."** "Did X get sent?", "did anyone reply?", "is this claim true?", "did that actually happen?" are all historical lookups wearing a different hat. The trigger is the QUESTION SHAPE — anything answered by finding-or-not-finding a past message — never whether the task felt like a lookup when it started.

The distinction was paid for: the rule once failed to fire precisely because the work was framed as "verifying a suspicious claim" rather than "looking something up." The agent ran four workspace searches, got four zeros, and reported two true events as fabricated. One of them sat in the exact channel it had searched for, posted shortly before the search — hidden behind a silently-failing query modifier and an oversized result file that was never opened before concluding. Transcripts-first would have found it in one `Grep`.

### A zero-result search is NEVER evidence of absence

Not weak evidence — none. The search index lags, misses thread replies, and fails silently on malformed modifiers: a `from:@Display Name` modifier with a space in it returns zero instead of erroring. Two protocols follow:

- **To establish that something did not happen,** use a bounded direct read: `slack_read_channel` with an explicit `oldest`/`latest` window on the specific channel, or `slack_read_thread` on the known parent. State the bounds in the finding — "not present in #channel between t1 and t2" — never the unbounded "didn't happen."
- **Before trusting any null result from a modifier-bearing query** (`from:`, `in:`, `to:`), re-run it without the modifier. If the unmodified query finds results the modified one missed, the modifier was broken, and every zero it produced is uninterpretable.

Absence claims are a grounding problem: a negative result is only evidence if the instrument could have produced a positive one. The general discipline — positive controls, scoped negative findings, truncated-output rules — lives in [synthesis-grounding-discipline](../../synthesis-grounding-discipline/SKILL.md); this section is its Slack instance.

### Backfills and archive imports

A backfill — reading a conversation to its first message rather than to a window — is a different operation from a sync, and it fails differently.

**Retrieval.** Page until the source says there are no more messages; a page limit or a date bound is not the beginning. Report the **earliest message's actual date** per conversation, so the reader can tell you reached the start rather than that a cursor quit early. Expand every thread: replies do not appear in channel history, and skipping them is the standard way a backfill silently loses half a conversation. Preserve raw user IDs beside resolved names.

**Naming and framing.** A backfill file states the span it covers and the date it was captured. When a conversation is *partly* captured already, name the new file by its date range rather than "full history" — that name claims a completeness it does not have.

**The analysis rule, which matters more than the retrieval.** Everything in a backfill is history, and it all reads present-tense. **Do not report anything from it as currently open without reconciling against newer material already held locally.** A conversation that stops is not a question that stayed unanswered — the thread often continued somewhere else. Scope every finding to where you looked ("unanswered in this conversation through <date>"), and title the output by what it establishes: a list of where conversations stopped, not a list of open loops. The general discipline, with the incident that produced it, is entry 12 of [synthesis-grounding-discipline](../../synthesis-grounding-discipline/SKILL.md).

Candidate open items surfaced this way are exactly what [synthesis-catchup-ledger](../../synthesis-catchup-ledger/SKILL.md) exists to classify — route them through its still-relevant / obsolete / ambiguous triage rather than reporting them raw.

---

## Following Continuing Conversations

When a channel message references or continues an earlier discussion (broadcast replies, "also sent to channel," or topic continuations):

1. Grep local transcripts for the topic/keywords to find the parent message and its TS.
2. Read the parent thread via MCP using that TS — this surfaces all new replies.
3. Update the local transcript with any new thread replies.

**Do NOT search Slack MCP repeatedly.** Local transcripts are the source of truth for historical context. The point of syncing is to avoid depending on the MCP API for lookups.
