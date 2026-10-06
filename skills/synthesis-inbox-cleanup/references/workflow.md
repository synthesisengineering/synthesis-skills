# Inbox cleanup: the workflow

How to run a sweep on each tool stack, with the exact commands and what each prints, and the pitfalls that have already burned us. Moved verbatim from the 1.6.2 SKILL.md; only link paths changed.

Contents:
- Three tool stacks, one methodology: which stack each account class uses
- The categorization taxonomy: the four dispositions and why trash is never permanent
- The workflow: steps 1 to 6 for iCloud and generic IMAP, then Microsoft 365 and outlook.com, then Gmail paths A and B
- Pitfalls: the summary table; the incidents behind each are in pitfalls.md

## Three tool stacks, one methodology

| Account class | Tool stack | Why |
|---|---|---|
| iCloud, generic IMAP | Python + `imaplib` + YAML manifest | Direct protocol access; manifest is human-curated, version-able, portable across IMAP providers |
| Microsoft 365 (Exchange Online), outlook.com | Mail.app AppleScript | M365 blocks basic-auth IMAP; M365 MCP needs admin consent. Mail.app is already authenticated locally |
| Gmail (personal or Workspace) | workspace-mcp Gmail API + native server-side filters | API is straightforward; native filters keep going-forward routing server-side without local daemons |

The methodology — census new senders, draft a plan, apply with dry-run-first — is the same across all three. Only the execution layer differs. See [`references/three-tool-stacks.md`](three-tool-stacks.md) for the decision tree and the trade-offs.

## The categorization taxonomy

Every message resolves to one disposition:

| Disposition | Action | Recoverable? |
|---|---|---|
| `keep` | Stay in inbox (default for human/business correspondence) | n/a |
| `archive` | Move to `Archive` folder | yes, just move back |
| `newsletter` | Move to `Newsletters` folder | yes, just move back |
| `trash` | Move to `Trash` folder | yes, ~30-day retention before permanent deletion |

Trash is never permanent in the engine. Permanent deletion is the mail provider's automatic expiry, not an engine action. This is deliberate: a wrong rule that trashes a year of bank statements is recoverable for 30 days. A wrong rule that hard-deletes them is not.

## The workflow

### 1. Census the inbox (read-only)

```bash
cd <synthesis-inbox-cleanup-root>/scripts
python3 icloud_census.py
```

Output: every distinct sender in the inbox, sorted by volume, cross-referenced against the existing manifest. Marks each sender as already-covered or `UNCLASSIFIED`. The UNCLASSIFIED list is the work-queue.

### 2. Triage the unmatched senders

**Examine actual content before classifying.** The census output shows volume and one example subject per sender — that is circumstantial signal, exactly what the circumstantial-inference pitfall (`references/pitfalls.md`) warns against. Run the inspector before deciding:

```bash
python3 icloud_inspect_senders.py "<address-pattern>" ["<pattern>" ...]
```

The inspector aggregates every matching INBOX message: distinct From variants with counts, date range, all unique subjects most-frequent first, plus one sanitized body sample from the most recent message. The body sample passes through `sanitize.py` (HTML strip + Unicode normalize + invisible/bidi/tags-block strip + wrapper-token scrub + byte-budget truncation + nonce-bearing `<UNTRUSTED_EMAIL nonce="…">` demarcation) so an LLM agent assisting with triage receives content that cannot mount a credible prompt-injection attack.

Then decide: keep / archive / newsletter / trash. The decision is added to `~/.synthesis/inbox-cleanup/rules.yaml`. New entries to `never_touch` require explicit human review — the LLM cannot modify that list (see "Prompt-injection defenses" below).

**The past-archive-but-future-keep pattern.** When you want a personal contact's existing backlog out of inbox but their future mail visible (settled recruiting threads, completed intros, stale event chatter), the manifest engine can't express that — it routes by sender pattern, not by date or thread state. Two-step solution:

```bash
# 1. Add a people_known (or other keep-class) rule for the address in
#    ~/.synthesis/inbox-cleanup/rules.yaml so future mail keeps in inbox.
# 2. Imperatively archive the current backlog from that address:
python3 icloud_archive_senders.py <address> [<address> ...] --apply
```

### 3. Dry-run plan (read-only)

```bash
python3 icloud_plan.py
```

Output: every inbox message classified per the current manifest, grouped by disposition, sorted by sender volume. No changes made. Review before applying.

### 4. Apply (one stage at a time, default dry-run)

```bash
python3 icloud_apply.py trash         # dry-run
python3 icloud_apply.py trash --apply # actually move
python3 icloud_apply.py archive --apply
python3 icloud_apply.py newsletter --apply
# or:
python3 icloud_apply.py all --apply
```

Each invocation re-derives dispositions from the current inbox — so stages are independently re-runnable and the planner and the executor can never diverge (they share `_lib.py`).

### 5. (Optional) Purge stranger-aliased Google notices on a catch-all domain

If you own a catch-all domain (e.g., `example.com` with mail routing to your iCloud), strangers often use made-up addresses on it (`fake@example.com`) when signing up for Google services. The resulting Google sign-in / billing / inactive notices land in your inbox.

```bash
python3 icloud_catchall_google_purge.py             # dry-run
python3 icloud_catchall_google_purge.py --apply     # trash them
```

Spare-rules live in `~/.synthesis/inbox-cleanup/config.yaml` — exact recipient addresses you actually use on the domain, plus subject keywords that should spare a message regardless of recipient (e.g., family-member domains you administer).

### 6. List unmatched senders ongoing

```bash
python3 icloud_tail.py
```

After a sweep, the long tail of senders still in inbox that match no manifest rule. The ongoing work-list. Feed the volume-sorted top entries to `icloud_inspect_senders.py` (step 2) to ground each decision in actual content.

### Microsoft 365 and outlook.com

```bash
osascript scripts/m365_mailapp_cleanup.template.applescript
```

Edit the template first — replace `{ACCOUNT_NAME}`, `{TRASH_FOLDER}`, `{ARCHIVE_FOLDER}`, and the per-sender match clauses. M365 uses `Deleted Items`, not `Trash`. Idempotent (whole-set `whose` clauses, not per-item index refs that go stale mid-move).

### Gmail (per-account)

Gmail does not use the manifest. Two paths:

**Path A — periodic cleanup via workspace-mcp:** the LLM agent uses `search_gmail_messages` (`in:inbox category:promotions` + known auto-mail patterns) plus `batch_modify_gmail_message_labels` to archive promos and notifications. NEVER auto-archive `noreply@` transactional mail (payroll, Stripe, banks, healthcare).

**Path B — server-side filters:** the LLM agent uses `manage_gmail_filter` to create persistent Gmail filters that route incoming mail automatically. See [`templates/gmail-filters.example.yaml`](../templates/gmail-filters.example.yaml) for proven filter shapes and [`references/gmail-filters-patterns.md`](gmail-filters-patterns.md) for the category catalog.

Filters survive across all Gmail clients (web, mobile, IMAP) and apply at the server, so going-forward routing needs no local daemon.

## Pitfalls — patterns that have already burned us

| Pitfall | What goes wrong | Fix |
|---|---|---|
| IMAP `TO` operator does substring matching | `TO "rg@example.com"` also matches `rajiv.garg@example.com` | Parse the recipient header explicitly; equality-test the address |
| Operating on threads instead of messages | One archive operation moves a whole conversation including the user's outbox replies | Always operate on individual messages, not threads, on Gmail |
| Body header content read without sanitization | Subject "URGENT: ignore previous instructions..." reaches the model | Route every body-read through `scripts/sanitize.py` |
| Forgetting some IMAP servers lack the MOVE capability | `M.uid('MOVE', ...)` fails silently | The engine checks capabilities and falls back to COPY+STORE+EXPUNGE |
| Trashing a `noreply@` from a bank because "noreply doesn't reply" | Bank statement, payroll deposit alert, or fraud alert lost | Banks / payroll / healthcare go in `never_touch` first, always |
| Inferring sender identity from circumstantial signals | Concluding a Google Workspace tenant is yours because the domain is yours | Read the message body — billing entity, account ID, tax info are usually in the body |

The IMAP substring pitfall and the circumstantial-inference pitfall are documented in detail in [`references/pitfalls.md`](pitfalls.md) with the specific incidents that surfaced them.
