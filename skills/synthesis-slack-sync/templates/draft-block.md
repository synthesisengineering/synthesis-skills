# Draft Block Template — schema v1 (synthesis-slack-sync v3.3.0+)

The canonical structure for a single draft message in a daily plan. Used by
the agent when drafting a Slack message into the action plan.

The format is two-tier: a glanceable summary at the top (title, routing) and
collapsed verification detail at the bottom (Grounding). The user reads the
summary every glance, the detail only when verifying before sending.

---

## Schema

```markdown
### Draft N: <action> <recipient/topic>

**Send to:** #channel · <thread or new>

[Optional one-line context paragraph if helpful framing.]

` ` `
[Message text — ready to copy and paste exactly as-is]
` ` `

<details><summary>Grounding (N facts verified)</summary>

- [Verified fact 1 — what source confirmed it]
- [Verified fact 2 — what source confirmed it]
- [Any staleness risk — e.g., "No new replies in thread since 11:23 AM"]

</details>
```

After sending (per `templates/sent-marker.md`), append a `**Sent:**`
paragraph between the body and the `<details>` block, and wrap the H3 title
in `~~...~~`.

---

## Field rules

### H3 title — keep brief

The title is a scannable label, NOT a summary. ≤60 character target, ≤80
hard cap. Format: `Draft N: <action> <recipient/topic>`.

NEVER in the title:

- Channel IDs, user IDs, thread timestamps (those go in **Send to:**)
- Commit hashes, PR numbers (those go in Grounding)
- Status markers, emoji prefixes, dates (those go in **Send to:** or for
  sent drafts in **Sent:**)
- Compound clauses joined by `+` or `;`
- Parentheticals with multiple comma-separated metadata items

If a title naturally needs more context, that context goes in the optional
one-line paragraph below **Send to:**, not in the title itself. Examples:

| Bad | Good |
|-----|------|
| `Draft G: Reply to the engineer about the routing question + concrete next steps for their open ticket` | `Draft G: Reply to engineer on routing question` |
| `Draft I: Skills repo split announcement (new prefix + new home + verified across mirrors)` | `Draft I: Skills repo split announcement` |
| `Draft K: Reply to colleague about staging deploy (PR #186 lands today, dual-PRIMARY routing verified)` | `Draft K: Reply to colleague on staging deploy` |

### Send-to — compressed

`#channel · <thread or new>`. Use middle-dot `·` separators between the
channel and routing context. The full thread metadata (parent author,
parent message timestamp, parent TS, optional permalink) lives ON the same
line but compressed:

```markdown
**Send to:** #eng-team · reply to @author at Wed Apr 2 10:59 AM EDT (TS=1775141956.643419)
**Send to:** #eng-team · new top-level message
**Send to:** @recipient · DM
**Send to:** @recipient · DM reply at Wed Apr 2 11:14 AM EDT (TS=1775142890.123456)
```

The TS and permalink are required for thread replies (the agent uses them
for thread re-reading) but rendered compactly so the line scans in one
glance.

### Optional context paragraph

A single plain paragraph between **Send to:** and the message body, used
ONLY when the draft needs framing context that isn't already obvious from
the title and Send-to. Skip it if the body speaks for itself. Examples of
when it helps: "Following up on yesterday's thread about caching." /
"Recipient asked twice; this is the third nudge." Keep it to one line.

### Message body

The fenced code block. Plain text, ready to copy and paste into Slack.
Slack mrkdwn syntax (single-asterisk `*bold*`, single-underscore `_italic_`,
backtick code, triple-backtick code blocks) is preserved verbatim. If the
body itself contains triple-backtick code blocks, use a 4-backtick OUTER
fence (` ```` `) so the inner ones render correctly per CommonMark — this
is the structural-axis rule from synthesis-console v0.8.5. The cockpit
also handles multi-segment bodies (intro prose + ` ```code``` ` + middle
prose + ...) without an outer fence, but a single fence is the default.

### Grounding inside `<details>`

The verification trail goes in a `<details>` block with a `<summary>`
that names the section and ideally a count. Markdown-it (and any
CommonMark-compliant renderer) renders `<details>/<summary>` as a native
HTML collapsible — closed by default, click to expand. This keeps the
glanceable surface clean while keeping the verification trail one click
away.

Each bullet must include:

- What was verified (the claim)
- The source (file path, commit hash, GH Actions run ID, thread TS, etc.)
- Any staleness check or unverified caveat

If a fact could not be verified, surface it explicitly inside the
collapsed Grounding rather than omitting it: `_Unable to verify: [what]
because [why]._`

---

## Why this shape

The daily plan serves at least four purposes (see `lessons/document-as-
contract-with-llm-producers.md` if accessible):

1. Human glance — "what's next?"
2. Human read — "verify before I send"
3. Agent maintain — read state, append updates
4. Agent context — cross-session continuity

Earlier templates put all metadata at uniform visual weight in the rendered
output, making purpose 1 (the most frequent) hostile because the metadata
crowded the substance. v3.3.0 separates the tiers: title + Send-to + body
are always visible (purpose 1, 2 partially); Grounding is collapsed
(purpose 2, on demand); machine-readable detail (TSes, permalinks) lives
on a single line within Send-to or Sent (purposes 3, 4).

---

## Cross-references

- `templates/sent-marker.md` — canonical `**Sent:**` paragraph form (v3.2.0+)
- `SKILL.md` — protocol prose, when to use this template
- synthesis-console `docs/cockpit-design.md` "Drafts" section — the consumer-
  side parser and rendering rules. Same-commit-together rule with this
  template.
