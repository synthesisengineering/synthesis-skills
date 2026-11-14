# Gmail filter patterns

Proven server-side filter shapes for Gmail (personal or Google Workspace). The agent uses `workspace-mcp`'s `manage_gmail_filter` tool to create these.

## Why server-side filters

Gmail's native filters run at the server. They apply to every incoming message automatically, work across all clients (web, mobile, IMAP), and need no local cron or daemon. Once created, going-forward routing is handled for free.

The trade-off: filters are per-account, edited via Gmail's own UI (Settings → Filters and Blocked Addresses). They are not portable to other providers. So filters complement, not replace, the manifest engine — filters handle Gmail's automatic routing, the manifest engine handles iCloud's batch sweeps.

## The five proven categories

These five filter shapes cover the bulk of typical Gmail inbox noise. Each filter has a `criteria` block (what to match) and an `action` block (what to do).

### 1. Newsletter routing (label + skip inbox)

For newsletters you subscribe to deliberately but want out of inbox. The label preserves them as searchable content; archiving keeps the inbox clean.

```yaml
criteria:
  from: "newsletter1@example.com OR newsletter2@example.com"
action:
  addLabelIds: ["Label_NEWSLETTERS"]   # custom label, create first
  removeLabelIds: ["INBOX"]            # skip inbox
```

Tip: use Gmail's `OR` operator in the `from` field to batch multiple newsletter senders into one filter. The OR list can be long.

### 2. Promotional / marketing trash

For senders that are pure promotional noise — never worth reading, never worth keeping. Send straight to trash.

```yaml
criteria:
  from: "deals@store.example OR marketing@brand.example"
action:
  addLabelIds: ["TRASH"]
  removeLabelIds: ["INBOX"]
```

The `TRASH` label is Gmail's built-in trash. Messages get 30-day retention before permanent deletion. Recoverable until then.

### 3. Notification routing (label + skip inbox)

For low-value but worth-keeping notifications (calendar invites you've already added, social activity, etc.).

```yaml
criteria:
  from: "noreply@calendar-service.example OR notifications@social-site.example"
action:
  addLabelIds: ["Label_NOTIFICATIONS"]
  removeLabelIds: ["INBOX"]
```

### 4. Important sender protection (mark + never spam)

Belt-and-braces for high-priority senders (bank, employer, healthcare, family). Adds a star or important label, prevents spam mis-classification.

```yaml
criteria:
  from: "bank@example.com OR employer@example.com"
action:
  addLabelIds: ["IMPORTANT", "STARRED"]
  removeLabelIds: ["SPAM"]
```

Note: `SPAM` is a built-in label. Removing it ensures the filter overrides Gmail's spam classifier for these senders.

### 5. Self-CC routing

When you BCC yourself on outbound mail for archival, route those copies to a `Sent-Archive` label rather than the inbox.

```yaml
criteria:
  from: "your.address@example.com"
action:
  addLabelIds: ["Label_SENT_ARCHIVE"]
  removeLabelIds: ["INBOX"]
```

## Filter creation order

When creating multiple filters via `manage_gmail_filter`:

1. **Create custom labels first.** A filter's `addLabelIds` array references labels by their internal ID (`Label_5`, `Label_12`). Get those IDs from `list_gmail_labels` (or from the `manage_gmail_label` response when creating). The MCP tool will fail if it tries to add a label that doesn't exist.

2. **Run the filters retroactively.** Gmail filters created via API don't automatically apply to existing messages — only to new incoming mail. To clean up the backlog, run the equivalent `search_gmail_messages` query and apply the same labels with `batch_modify_gmail_message_labels`.

3. **Audit in the UI.** After creation, the user can view all filters in Gmail Settings → Filters and Blocked Addresses. Each filter is editable / deletable from there. This is the recommended audit surface — the API is for creation; the UI is for ongoing inspection.

## What NOT to filter

| Sender pattern | Why not |
|---|---|
| `noreply@<bank>` | Bank statements, fraud alerts |
| `noreply@<payroll>` | Pay stubs, deposit confirmations |
| `noreply@<healthcare>` | Appointment confirmations, test results |
| `noreply@<auth-provider>` | Sign-in codes (you NEED these in inbox) |
| Anyone you might reply to | Auto-archiving humans is rude |
| Calendar invites | Some need response; archiving silently loses them |

The general rule: if a sender ever produces a message you'd want surfaced in the next 24 hours, don't filter them. Filters are for senders whose output is 100% predictably auto-archivable / trashable.

## The template

See `templates/gmail-filters.example.yaml` for a starting YAML structure. The agent can use it as a working format for proposing filters before calling `manage_gmail_filter`, and the user can review the YAML before approving.

## Synchronizing across multiple Gmail accounts

Server-side filters do not sync between accounts. Each Gmail account needs its filters created separately. A useful pattern:

1. Maintain a shared YAML (e.g., `gmail-filters-shared.yaml`) of category patterns
2. Per-account, run a script that reads the YAML and calls `manage_gmail_filter` for each entry
3. Audit per account in the Gmail UI

The skill does not ship a multi-account filter sync script in v1. The proven workflow has been per-account, agent-driven creation. If multi-account syncing becomes the regular need, that's a v2 feature.
