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

**Fix:** Before asserting a fact about identity, ownership, billing, or account state, examine the primary source. For categorization that requires identity confidence, prefer fetching the body to inferring from headers.

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

## Subject rules support only positive `subject_contains`, not negation

**Incident:** During the first triage session, a single sender (`no-reply@zoom.us`) was found to carry both legitimate Zoom subscription / expiry notices AND third-party-webinar spam confirmations (Zoom's email-confirmation pipeline gets hijacked by spammers running webinars on the platform). The natural rule shape — "from this address AND subject does NOT contain 'subscription' or 'expired' or 'renew' → trash" — isn't expressible in the manifest engine, which supports only positive `subject_contains` matching, not negation.

**Why this matters:** Mixed-content senders aren't a Zoom-specific quirk. Any shared-infrastructure sender — webinar platforms, event-confirmation services, mailing-list relays, white-label notification systems — can carry both legit and unwanted content under one address.

**Workaround for one-off cases:** Add an explicit `disposition: keep` rule for the sender so legit mail stays in inbox, then run a one-shot script that trashes only the non-legit subjects. This is what was done for Zoom (three spam messages trashed via a hardcoded `/tmp` script that distinguished by the legit-keyword list).

**The signal to abstract:** when this pattern occurs a second time for a different sender, the engine should grow real support — either `subject_not_contains` in the existing `subject_rules` structure, or a separate `subject_exclude_rules` table. Until then, document each occurrence here so the eventual abstraction has multiple cases to design against. (Premature abstraction from one case commits to a wrong API.)

## DKIM / SPF / DMARC pass confirms identity, not intent — do not use authentication as evidence of legitimacy

**Incident:** A user flagged an inbox message as "almost certainly a scam or phishing email." The agent inspected the message, found that DKIM, SPF, and DMARC all passed cleanly, the sender was relayed via a known ESP, and the body contained no credential prompts or suspicious URLs. The agent presented this as evidence the message was likely legitimate (probably a real but unsolicited "order confirmation" from a brand-named domain). The user then clarified that they had not ordered the product and were not at any event where they would have signed up. The user was correct; the agent's analysis had over-weighted technical authentication signals against the user's stated context.

**Why this matters:** Domain authentication confirms that the sender controls the DNS and signing keys for the domain they claim. It does NOT confirm that the sender's intent is benign. A scammer who buys a lookalike domain — or a "support" / "info" TLD sibling of a known brand — and configures DKIM, SPF, and DMARC properly will pass all three checks. Spoofed-brand domains often pass authentication because they are real domains (just controlled by the scammer, not the brand). The harder the brand is to register, the more cheap-TLD imitators show up to pass auth on a different domain.

**The dispositive signal is user context, not technical signals.** When a user says "I didn't order this," "I have no account with this company," "I never signed up," or "I have no relationship with this sender," that signal is more reliable than any DKIM / SPF / DMARC pass. The user has knowledge the agent does not — what they bought, who they met, where they were. The agent can only see headers.

**Rule for LLM-agent inspection paths:** when presenting technical-signal analysis of a message a user has flagged as suspicious, frame authentication as evidence of *domain ownership* only — never as evidence of *benign intent*. If the user's stated context contradicts the technical signals, default to the user's context. The right phrasing is "this domain successfully authenticated as itself" — not "this is likely legitimate." A two-axis verdict is correct: authenticated-by-claimed-domain (yes/no, from headers) AND wanted-by-recipient (yes/no, from user context). Both are needed; either alone misleads.

**Routing implication:** when a user-flagged spoofed-brand domain is identified, add it to the manifest's sender rules as `cold_sales` (trash) — including the parent domain so future subdomains (`em<N>.brand.<tld>`, `mail.brand.<tld>`, etc.) auto-route without re-prompting.

## Subject rules required a `domain` clause and only matched substrings — calendar protocol responses had no clean rule shape

**Incident:** Meeting acceptance / decline / tentative / canceled-event responses from colleagues were piling up in inbox because the manifest engine couldn't express the natural rule shape: "any sender, subject starts with `Accepted:` (or `Declined:` etc.) → archive." Two specific gaps surfaced together:

1. `subject_rules` entries REQUIRED a `domain` clause, so a rule matching across all senders couldn't be written.
2. Only `subject_contains` (substring match) was supported, so prefix-anchored matches like "starts with `Accepted:`" had to use substring matching, which falsely matches replies like `Re: Accepted:` from humans discussing an acceptance.

The pattern is general: calendar-protocol mail (Google Calendar, Microsoft Outlook, Apple Calendar) uses standardized subject prefixes regardless of which colleague sent the response. Any subject-prefix-driven routing across heterogeneous senders has the same shape.

**Fix (shipped in v1.2.0):** Two engine extensions, both backward-compatible with the existing rules.yaml entries:

1. `subject_rules` entries may now omit the `domain` clause. Absent domain = any-sender rule.
2. New `subject_starts_with` operator alongside the existing `subject_contains`. Prefix-anchored match; safer than substring for canonical-prefix patterns.

Example — archive calendar-response noise regardless of sender:

```yaml
subject_rules:
  - {if: {subject_starts_with: "Accepted:"}, disposition: archive}
  - {if: {subject_starts_with: "Declined:"}, disposition: archive}
  - {if: {subject_starts_with: "Tentative:"}, disposition: archive}
  - {if: {subject_starts_with: "Canceled event:"}, disposition: archive}
  - {if: {subject_starts_with: "Cancelled event:"}, disposition: archive}
```

**What was deliberately NOT shipped:** `subject_not_contains` (the negation operator from the Zoom case above). That remains a separate gap because the negation use case is for sender-anchored mixed-content streams, not subject-anchored protocol patterns. The two shapes don't share an API. Documenting both occurrences here so the next abstraction (negation) has its own clean design.

---

## `imapsync` flag names must be verified against `--help` before destructive runs

**Incident:** During a Gmail-to-Gmail mailbox migration, an `imapsync` invocation was launched with the flag `--delete` intended to delete from source after confirmed transfer to destination. The actual flag is `--delete1` (with the trailing `1` indicating "host1 = source"). The wrong-named flag was interpreted as a supplementary argument; `imapsync` exited 64 immediately with the message *"Found 1 supplementary arguments: [--delete]. It usually means a quoting issue in the command line or some misspelled or unknown options."* The script wrapping the call captured this exit code, marked the run as failed, and returned — but the user wasn't watching the log in real time, so the failure went undetected for hours. The destructive operation simply never happened; the source mailbox stayed intact.

A separate flag error in the same migration session: `--maxerrors` (plural) was used; the real flag is `--maxerror` (singular). Same silent-exit-64 failure mode.

**Why it matters:** `imapsync` has a `--delete2` flag too. `--delete1` deletes from the source after successful transfer (this is "move" semantics, the usual goal). `--delete2` deletes from the *destination* messages that aren't on the source — destructive sync in the wrong direction, the opposite of what most users want. A typo that lands on `--delete2` instead of `--delete1` would silently destroy destination state. The pattern of "looks intuitive but is actually wrong" extends across the imapsync option list.

**The rule:** Before launching any imapsync run that triggers destructive behavior (any flag matching `--delete*`, `--expunge*`, `--regextrans*`, `--regexflag`, `--regexmess`), verify the exact flag name against the binary's `--help` output:

```bash
imapsync --help 2>&1 | grep -i -A1 -E "delete|expunge"
```

This is fast (under a second) and prevents an entire class of "I lost an hour because a flag I half-remembered doesn't exist" failures. The cost of the verification is trivial compared to the cost of re-running a multi-hour Gmail migration.

**Specific corrections from the canonical incident:**

| What you might remember | What actually works |
|---|---|
| `--delete` | `--delete1` (source) or `--delete2` (destination) |
| `--maxerrors` | `--maxerror` (singular) |
| `--expunge` | `--expunge1` or `--expunge2` |
| Standalone numeric flags | Most are paired with `1` or `2` to specify host1/host2 |

## Gmail IMAP throttle makes `imapsync` ETA throttle-bound, not bandwidth-bound

**Incident:** A Gmail-to-Gmail migration of ~1,000 unique messages (~300 MiB total) was estimated at 15–30 minutes based on Gmail's documented IMAP transfer ceiling of roughly 1.5 MiB/sec. Actual observed transfer rate: **0.10 messages/sec, ~14 KiB/sec** sustained. The full run took just under 3 hours of wall-clock for the copy phase alone, an order of magnitude longer than the byte-count estimate suggested.

**Why it happens:** Gmail's IMAP server enforces per-account throttling that prioritizes interactive use (Gmail web UI, mobile clients) over sustained automated transfers. The 1.5 MiB/sec figure represents an upper bound under non-throttling conditions; in practice, sustained transfer from a single account during normal Google business hours runs at 1–2 orders of magnitude slower. The throttle scales with the destination account's activity, source account's activity, time of day, and Google's current capacity headroom.

**The rule:** Do not predict Gmail migration ETA from byte totals or message counts in advance. Instead:

1. Launch the run with a low-bar early-progress estimate ("at least 10 minutes for the initial folder walk; will revise after 5 minutes of observation").
2. After 5 minutes of run time, sample the actual `msgs/sec` from the log tail.
3. Compute the projected wall-clock from `(total_unique_messages / observed_msgs_per_sec)`.
4. Report the revised ETA explicitly to the user. Do not let an early under-estimate stand.

For a fresh account-pair migration of ~1,000 unique messages, plan on 2–3 hours wall-clock as the baseline. Faster is a pleasant surprise; slower is normal under aggressive throttling.

**Implication for orchestration:** A multi-hour run cannot live inside a single conversation session's lifetime. Use a shell-level detachment pattern (`nohup` + stdio redirection + `disown`) so the imapsync process re-parents to `init` and survives any session reset, terminal disconnect, or harness lifecycle event. The harness's `background-task` mechanism is not equivalent — it tracks the task and can terminate it.

---

These pitfalls were collected from real incidents during the development of this skill. Each one cost time, money, or risk. Adding a new pitfall to this file is part of the cost of resolving any new bug in the engine — better to document it now than rediscover it later.
