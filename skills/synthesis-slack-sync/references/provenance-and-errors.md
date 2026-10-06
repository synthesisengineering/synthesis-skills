# Slack sync: provenance, dates and errors

Read before writing a sync section, attributing or quoting a message, or propagating a Slack citation into another file; before naming a dated file; and when a Slack call fails.

Contents:
- Provenance Discipline: MCP-read requirement, quote attribution, cross-file propagation, automated backstop, what the rule is not
- Date Verification
- Error Handling

## Provenance Discipline

The 2026-04-29 fabrication incident — an agent invented a Slack message attributed to a teammate, complete with a plausibly-tweaked TS, then drafted a reply to the imaginary message — motivated this section. The format-level fixes above (permalinks, embedded TSes) make provenance violations grep-able; the rules below define what's actually a violation.

### MCP-read requirement for sync sections

Every `## ... sync (~HH:MM TZ)` section header added to a transcript file (`transcripts/slack/YYYY-MM-DD/*.md`) MUST be backed by a `slack_read_channel` or `slack_read_thread` MCP call IN THE SAME TURN.

- The body of that section may ONLY contain messages those MCP calls returned. Verbatim quotes, TS values, reactions, thread reply counts — all must come from the MCP output, not from the agent's expectations.
- If the MCP call returned no new messages: the section says "No new messages since last sync" and stops. **It MUST NOT contain message quotes, TS values, or claims about specific people having sent specific things.**
- Commentary about previously-synced messages (e.g., "this thread is now in good shape") is allowed, but must reference messages that ARE in the file from a prior sync — not introduce new ones.

### Quote-attribution requirement everywhere

Anywhere a quote is attributed to another person — transcripts, daily plans, project CONTEXT.md, session logs, draft "Send to" thread descriptors, anywhere — the agent must be able to cite the specific tool_use call in the current session that surfaced the quote. There is no "I remember it from earlier in the conversation." There is no "this is what they would say." Either there's a tool call to cite, or there's no quote.

### Cross-file propagation rule

When CONTEXT.md / daily plan / sessions logs cite a Slack message ("X said Y at HH:MM EDT"), the citation chain must trace `MCP call → transcript file → derivative file`. If a derivative file makes a claim that the transcript file doesn't support, the derivative is wrong. Re-verify against the actual Slack thread (or its synced transcript) before propagating.

### Automated backstop

A Stop hook at `~/.claude/hooks/quote-provenance-checker.py` (installed alongside `~/.claude/hooks/lazy-shortcut-detector.py` for the parallel discipline) scans the conversation transcript for Slack-TS-shaped values written into transcript / daily-plan / context files that did NOT appear elsewhere in the session — no MCP read, no Read tool result, no user message containing them, no other tool input. Candidates are logged to `~/.claude/quote-provenance-log.jsonl` with the file path, the fabricated TS values, and a stderr warning. The hook does NOT block writes; it makes violations visible after the fact for the user to review.

### What this rule is NOT

- It is not a rule against describing what's happening in a thread you've actually read. Summaries grounded in real synced content are fine.
- It is not a rule against drafting messages. Draft message bodies are agent-authored prose; only their attribution metadata (TS, parent author quote, channel, thread context) needs provenance.
- It is not a rule against speculating in your own analysis text ("Stephen will probably ask about X next"). Speculation is fine; recording the speculation as if it were a real message is not.

---

## Date Verification

Before writing or naming any dated file, cross-check the date against at least two independent signals:

1. Slack Unix timestamps (convert with `date -r TS`)
2. Day-of-week clues in message content
3. User statements about the current day

The `currentDate` system value is a snapshot from session start. If a session crosses midnight, all subsequent dates will be wrong.

---

## Error Handling

- **Slack connector auth failure:** Stop immediately. Instruct the user to re-authenticate using the current tool's Slack auth flow, then restart the IDE/CLI if required.
- **Channel not found:** The channel ID may have changed or the bot may have been removed. Warn and skip.
- **Rate limiting:** If Slack returns rate limit errors, wait and retry. Do not skip channels.
- **Empty channel:** Record "No new messages" in the transcript. Do not silently skip.
