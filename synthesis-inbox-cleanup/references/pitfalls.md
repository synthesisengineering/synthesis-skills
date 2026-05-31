# Pitfalls: patterns that have already burned us

Real incidents that motivated specific design decisions in this skill. Read this before extending the engine.

## IMAP `TO` operator does substring matching, not equality

**Incident:** A search for `TO "rg@example.com"` returned 19 Hyatt loyalty messages whose recipient was actually `rajiv.garg@example.com`. The IMAP `TO` predicate matches any substring of the recipient's address. The Hyatt account had nothing to do with the user — a stranger named Rajiv Garg had used the catch-all domain as a fake email when signing up.

**Why it's dangerous:** A categorization pass that "filters messages to address X" can sweep in messages to *every address containing X as a substring*. If `X = "rg"`, that matches `rg@`, `rajiv.garg@`, `rgrant@`, `rg-noreply@`, and dozens of others.

**Fix:** Parse the recipient headers explicitly with `email.utils.getaddresses()` and equality-test against a normalized lowercase address. Never rely on IMAP search for recipient equality. The catch-all Google purge script does this.

**Bug-level signature:** if your IMAP search is returning more results than you expect, the first thing to check is whether the search operator does substring or exact matching. RFC 3501 says `TO` is a substring operator; many engineers assume it's exact.

## Circumstantial inference vs. primary evidence (sender identity)

**Incident:** Asked whether a short-alias address on a catch-all domain (e.g., `xy@<user's-domain>`) was the user's. The first response argued yes from circumstantial signals: the user owns the domain, so a Google Workspace at the domain must be theirs, so the admin alias must be theirs. The conclusion was stated confidently from header metadata alone. Two rounds of pushback later, reading the actual message bodies revealed Google's billing entity was a regional subsidiary that bills only customers in a tax jurisdiction the user does not live in. Conclusion flipped: the Workspace belonged to an unknown delegate (someone with current or historical DNS access), not the domain owner.

**Why it matters for this skill:** The engine routinely needs to decide "is this sender legit," "is this account mine," "should this address be in `never_touch`." Circumstantial inference from address patterns and domain ownership is not evidence. The primary data — message body content, billing entity, account ID, tax info — is one fetch call away.

**Fix:** Before asserting a fact about identity, ownership, billing, or account state, examine the primary source. For categorization that requires identity confidence, prefer fetching the body to inferring from headers. The discipline applies whenever a chain of reasoning runs `[domain ownership] → [a tenant exists at that domain] → [therefore the domain owner owns the tenant]` — the chain is broken at the second arrow, because anyone with current or historical DNS access could have set up the tenant.

**Anti-pattern signature:** any reasoning chain that goes `[domain ownership] → [a tenant exists at that domain] → [therefore the domain owner owns the tenant]` is broken at the second arrow. Anyone with current or historical DNS access could have set up the tenant.

## Threads vs. messages on Gmail

**Incident:** A "archive all marketing from sender X" pass was implemented via `batch_modify_gmail_thread_labels` instead of `batch_modify_gmail_message_labels`. The marketing sender had been in long-running threads — including threads where the user had replied. The thread-level operation moved the user's own outbox messages out of the inbox along with the marketing.

**Why it's dangerous:** A thread is a conversation; a message is a single send. Categorization decisions ("move marketing to trash") apply to messages, not conversations. Operating on threads sweeps in any reply chain attached to the matched parent.

**Fix:** On Gmail, always operate on `messageId`, not `threadId`. The workspace-mcp tool has both `batch_modify_gmail_message_labels` and `batch_modify_gmail_thread_labels`; use the message-level variant.

## IMAP MOVE capability is not universal

**Incident:** Some IMAP servers don't support the `MOVE` extension (RFC 6851). A `M.uid('MOVE', ...)` call fails silently or returns an error that the calling code might not check.

**Fix:** Check `M.capabilities` for `MOVE`. If absent, fall back to `COPY` + `STORE +FLAGS \Deleted` + `EXPUNGE`. The engine does this:

```python
caps = [(c.decode() if isinstance(c, bytes) else c).upper() for c in M.capabilities]
has_move = "MOVE" in caps
if has_move:
    M.uid('MOVE', csv, target)
else:
    M.uid('COPY', csv, target)
    M.uid('STORE', csv, '+FLAGS', r'(\Deleted)')
    M.uid('EXPUNGE', csv)
```

iCloud supports MOVE. Some self-hosted IMAP servers and older Exchange-via-IMAP gateways do not.

## Per-item AppleScript index references go stale mid-move

**Incident:** An early AppleScript implementation used `repeat with i from 1 to count of messages` and indexed into the inbox per iteration. Partway through, indexes shifted (because messages were moving out), and the loop hit error `-1728` ("Can't get item N of...") with a partial move complete.

**Fix:** Use whole-set `whose` clauses instead. `move (every message of ibox whose <criterion>) to trashBox` is atomic per clause. Each clause moves all currently-matching messages in one operation; no index drift.

The template uses this pattern throughout.

## Silent body-fetch failures

**Incident:** A function intended to fetch and display message bodies returned silently when the IMAP response parsing failed. The user thought no matching messages existed; in reality, the parsing had errored and no bodies were ever displayed.

**Fix:** Every IMAP fetch path must raise on parse failure (or at minimum log the parse error with the message UID). Silent returns are debugging hostile.

## CWD lost after `osascript` calls

**Incident:** After running `osascript path/to/cleanup.applescript` in an agent loop, the agent's current working directory had drifted (likely a quirk of how the AppleScript host was invoked). The next `git` commands operated against the wrong repository.

**Fix:** Use absolute paths in every shell invocation. Don't depend on CWD remaining stable across non-shell tool calls. The pattern `cd /full/path/to/repo && git ...` is the safe default.

## Concurrent-window git index race

**Incident:** Two Claude Code windows working in the same repository. Window A staged a few files with `git add foo.py`. Window B ran a sub-agent that staged its own work with `git mv`. Window A then ran `git commit -m "..."` expecting to commit only `foo.py` — but the commit swept up the sub-agent's in-progress moves too. The combined commit went to a public remote and could not be retroactively split.

**Fix:** Always use `git commit -o <paths>` (the `-o` / `--only` flag) with explicit pathspecs when there is any chance another window or sub-agent has staged work. Or use `git restore --staged <other-files>` before committing.

This is not specific to inbox-cleanup, but it bit this project hard during multi-window development.

## Hardcoded user-specific values leaking into a public skill

**Incident:** An early version of the catch-all Google purge script had the maintainer's actual catch-all domain hardcoded in the source, plus a family-domain spare-set as Python constants. These would have leaked private information about the maintainer (and their family members' domains) if the script had been published as-is.

**Fix:** Move all user-specific values to `~/.synthesis/inbox-cleanup/config.yaml`. The public skill's script reads from config and has no hardcoded user data. This is now a hard requirement for any script in this skill.

**Bug-level signature:** if a Python constant in a public-bound file contains a real name, a real domain, an email address, or anything that identifies the user — that's a leak. Hoist it to config before publication.

## Treating the IMAP search response as a list when it's actually a single space-joined byte string

**Incident:** `M.search(None, "ALL")[1]` returns `[b'1 2 3 4 ...']` — a list containing ONE byte string of space-joined UIDs, not a list of UIDs. New IMAP users iterate over the outer list and operate on the full UID string as if it were a single UID.

**Fix:** `M.search(None, "ALL")[1][0].split()` — split the inner byte string. The engine does this consistently.

## Subject-keyword spares need substring matching, not equality

**Incident:** When adding family-member domain support to the catch-all purge, an initial implementation checked `if subject == family_domain`. That never matched because the family domain appears as a substring in a longer subject ("Reminder: subscription on family-domain.com expires…").

**Fix:** Use substring matching for subject keywords. The current implementation does this with `if any(kw in subject_lower for kw in SPARE_SUBJECT_KEYWORDS)`.

---

These pitfalls were collected from real incidents during the development of this skill. Each one cost time, money, or risk. Adding a new pitfall to this file is part of the cost of resolving any new bug in the engine — better to document it now than rediscover it later.
