# Three tool stacks: when to use which

Email cleanup looks the same conceptually across providers — categorize senders, move messages, set up going-forward routing — but the execution layer is different per account class. This file documents which tool stack to reach for and why.

## Decision tree

```
Is the account…

├── iCloud or a generic IMAP provider (no admin OAuth requirement)?
│     → Python + imaplib + the manifest engine in scripts/
│
├── Microsoft 365 (Exchange Online) or outlook.com?
│     → Mail.app AppleScript template (M365 blocks basic-auth IMAP)
│
└── Gmail (personal or Google Workspace)?
      → workspace-mcp Gmail API + native server-side filters
```

## Stack 1 — iCloud / generic IMAP (Python + imaplib)

**Why this stack:** Most IMAP providers (iCloud, Fastmail, generic hosted IMAP) allow direct app-specific-password auth without OAuth or admin consent. The Python `imaplib` module in the standard library is sufficient. The manifest YAML is human-curated, version-able, and portable across providers.

**Auth:** App-specific password stored in macOS Keychain (service `inbox-cleanup-imap` by default). Each provider has its own way to generate the password:

- iCloud: appleid.apple.com → Sign-In and Security → App-Specific Passwords
- Fastmail: Settings → Privacy & Security → App Passwords
- Generic: provider's account settings

**Hosts:**

| Provider | IMAP host |
|---|---|
| iCloud | `imap.mail.me.com` |
| Fastmail | `imap.fastmail.com` |
| Yahoo | `imap.mail.yahoo.com` |

Edit `~/.synthesis/inbox-cleanup/config.yaml` to set the host and the user candidate list.

**Scripts:**

- `icloud_census.py` — read-only sender survey
- `icloud_plan.py` — read-only dry-run categorization
- `icloud_apply.py` — executor with `--apply` gate
- `icloud_tail.py` — list unmatched senders (work-queue)
- `icloud_catchall_google_purge.py` — special-case for catch-all domains

The script names prefix `icloud_` because that's the original target, but they work against any IMAP provider that allows direct password auth. Don't let the prefix mislead you.

**Pitfalls:** see `pitfalls.md`. Headline ones: IMAP `TO` substring matching, MOVE capability not universally supported (the engine falls back to COPY + STORE + EXPUNGE).

## Stack 2 — Microsoft 365 / outlook.com (Mail.app AppleScript)

**Why this stack:** M365 blocks basic-auth IMAP on most tenants. Modern auth (OAuth2) requires admin consent for IMAP. The M365 MCP connector also requires admin consent. Mail.app on macOS already has the account authenticated through the system's mail account flow, so AppleScript reaches the inbox with no extra credentials and no admin wall.

**Auth:** None at the script level. The Mail.app account is already authenticated through System Settings → Internet Accounts (or Mail.app's own Add Account flow).

**Template:** `scripts/m365_mailapp_cleanup.template.applescript`. Copy per account, edit the placeholders (`{ACCOUNT_NAME}`, `{TRASH_FOLDER}`, `{ARCHIVE_FOLDER}`), populate the match clauses with your sender patterns.

**Why whole-set `whose` clauses, not per-item loops:** AppleScript's per-item index references go stale mid-move (`whose` returns a frozen result list; once the move begins, the underlying indexes shift and you get error -1728 partway through). Whole-set `whose` moves are atomic per clause and self-correcting on re-run.

**M365 vs. iCloud folder name conventions:**

| Action | iCloud | M365 / Outlook |
|---|---|---|
| Trash | `Trash` | `Deleted Items` |
| Archive | `Archive` | `Archive` |

Set the placeholders accordingly.

**Idempotent and re-runnable:** Each clause only matches messages currently in the inbox matching the criterion. A re-run only moves whatever's currently new in inbox. Safe to schedule via launchd or run on demand.

**What stays in the AppleScript and what goes in YAML:** Nothing in the M365 stack uses the YAML manifest. The rule set is encoded inline in the AppleScript. This is intentional — AppleScript is the tool, the rule set is small (a few dozen lines per account), and there's no value in adding a YAML→AppleScript code generator for v1. If you have more than three M365 accounts, that calculus might change.

## Stack 3 — Gmail (workspace-mcp + native server-side filters)

**Why this stack:** Gmail offers two distinct mechanisms that complement each other.

- **API-driven cleanup** via `workspace-mcp` Gmail tools — handles the existing backlog. The agent searches for known patterns (`in:inbox category:promotions`, known auto-mail senders) and applies labels / archives in bulk.
- **Server-side filters** via the `manage_gmail_filter` tool — handles future incoming mail. Filters run at Gmail's server, apply across all clients (web, mobile, IMAP), and need no local daemon.

**Auth:** workspace-mcp's standard Google OAuth setup. The skill assumes workspace-mcp is already running and authenticated on the user's Mac.

**Backlog cleanup (Path A):**

The agent uses these MCP tools:

- `search_gmail_messages` with queries like `in:inbox category:promotions older_than:30d`
- `get_gmail_messages_content_batch` to fetch a sample for sanity-check
- `batch_modify_gmail_message_labels` to archive (remove `INBOX` label) or label (add custom label)

The agent operates on **individual messages, not threads.** This is critical: thread-level operations move conversations including the user's own outbox replies. Always pass `addLabelIds` / `removeLabelIds` to message IDs, not thread IDs.

**Going-forward routing (Path B):**

The agent uses `manage_gmail_filter` to create persistent filters. Each filter has a `criteria` (from / to / subject / has-the-words) and an `action` (apply label / archive / mark read / etc.). See `gmail-filters-patterns.md` for the proven category catalog and `templates/gmail-filters.example.yaml` for the structural shape.

Server-side filters are the recommended going-forward routing for Gmail because:

- They apply at the server, so mobile / web / IMAP all see the result
- They run on every incoming message automatically, no local cron
- They're visible in Gmail Settings → Filters and Blocked Addresses, so the user can audit them in the native UI

**Transactional safety on Gmail:** NEVER auto-archive `noreply@` mail without explicit per-sender rules. `noreply@chase.com` is a bank statement; `noreply@stripe.com` is a charge confirmation; `noreply@kaiser.org` is a healthcare update. Gmail's own "Promotions" tab is mostly safe to archive, but transactional `noreply@` is not.

## What does NOT fit any of these stacks

- **iCloud labels** — iCloud's mail uses folders, not Gmail-style labels. The skill uses folders (`Newsletters`, `Archive`, `Trash`) on iCloud because that's the available primitive.
- **Web-only providers without IMAP** (e.g., some webmail services) — out of scope. The skill assumes IMAP, Mail.app, or Gmail API access.
- **Encrypted mail (PGP / S/MIME)** — the engine reads headers only, so encrypted bodies are not a problem for categorization. But any future body-reading path would need explicit handling.

## Cross-stack: the manifest is per-account-class, not per-account

`~/.synthesis/inbox-cleanup/rules.yaml` covers the IMAP accounts the manifest engine touches. M365 rules live in per-account AppleScript files. Gmail rules live in Gmail's native filter UI.

This is intentional — three different tools, three different rule stores. Trying to unify them would mean writing a YAML→AppleScript and YAML→Gmail-filter code generator, which is more complexity than the proven workflow needs. v1 keeps them separate.

A future v2 could unify them. Not yet.
