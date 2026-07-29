# Sent Marker Template — schema v1 (synthesis-slack-sync v3.2.0+)

The canonical form for marking a draft as sent. Goes in the draft section
between the message body and the `<details>` Grounding block.

---

## Schema

```markdown
### ~~Draft N: <title>~~

**Send to:** #channel · <routing>

` ` `
[Message text]
` ` `

**Sent:** <human-readable date+time> — by <Name> in #channel · (TS=<unix-ts>) <permalink>

<details><summary>Grounding (N facts verified)</summary>
...
</details>
```

Two structural moves vs an active draft:

1. **Wrap the H3 title in `~~...~~`.** Title only — keep it short. NEVER
   pack SENT metadata into the heading text itself (pre-v3.2.0 form was
   `### ~~Draft N: title~~ ✅ SENT by ... at ... in ...`; that form
   renders as four lines of giant strikethrough at typical H3 typography
   and breaks the cockpit's sent-state detection).

2. **Append a `**Sent:**` paragraph** between the message body and the
   `<details>` Grounding block.

---

## Sent paragraph fields

```
**Sent:** <human-readable> — by <Name> in <channel-or-DM> · (TS=<unix-ts>) <permalink>
```

| Field | Why |
|-------|-----|
| Human-readable date+time first | The user reads this. Include timezone abbreviation. |
| `by <Name>` | Identifies who sent the message. Useful in shared workspaces or when the sender is not the daily-plan owner. |
| Channel or DM target | Where it landed. Use `#channel-name` or `@person`. |
| `(TS=<unix-ts>)` | Agent uses this to re-read the message and any thread replies. |
| Permalink | When `slack_workspace_domain` is configured, include the Slack permalink — the cockpit renders this as the "Open in Slack" / "View in Slack" link in the sent badge. |

---

## Examples

```markdown
**Sent:** Thu Apr 2 6:16 PM EDT — by Rajiv in #eng-team · (TS=1775141956.643419) https://acme.slack.com/archives/C0XXXXXX/p1775141956643419
```

```markdown
**Sent:** Wed Apr 29 1:32 PM EDT — by Rajiv in DM with @teammate · (TS=1777483930.607659) https://acme.slack.com/archives/D0YYYYYY/p1777483930607659
```

```markdown
**Sent:** Wed Apr 29 8:14 AM EDT — by Rajiv in #standup · (TS=1777455250.040000)
```

(The third example omits the permalink — acceptable when
`slack_workspace_domain` isn't configured. The cockpit's "View in Slack"
link will fall back to a constructed URL from the channel ID + TS.)

---

## Backward compatibility

The skill's `thread_checker.py` and synthesis-console v0.8.6+'s parser
both accept the legacy form (`### ~~Draft N: title~~ ✅ SENT by ... at ...
in ...`) as well as the canonical form above. Existing daily-plan files
don't need retroactive rewriting — but new SENT markers should use the
canonical form, and any time the agent rewrites a sent draft for any
reason, it should bring it to the canonical form.

---

## Cross-references

- `templates/draft-block.md` — the active draft template this transitions
  from.
- `SKILL.md` — protocol prose.
- synthesis-console `docs/cockpit-design.md` "Drafts" section — the
  consumer-side parser. Same-commit-together rule with this template.
