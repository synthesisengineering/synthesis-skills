# Mailbox manifest (`.agents/mailboxes.yaml`)

Every workspace that sweeps email declares its accounts here — same idea
as `repos.yaml`: the declared list is the complete decision, and the
ritual sweeps exactly it. Until this manifest existed, "email" meant
Gmail in practice while the personal-life iCloud mailbox rotted unread
(§5a: seven Smurl emails over four weeks in a mailbox no ritual read).

## Schema

```yaml
workspace: rajiv
accounts:
  - address: rajiv.pant@gmail.com
    transport: gmail            # gmail | apple-mail | m365 | forwards-to
    role: primary-personal
    sweep: every-ritual         # every-ritual | weekly | on-request
  - address: rajiv.pant@mac.com
    transport: apple-mail
    mailboxes: [INBOX]          # default when omitted: [INBOX]
    role: personal-life
    sweep: every-ritual
  - address: rajiv@rajiv.com
    transport: forwards-to      # not a mailbox; a domain alias
    delivers_to: rajiv.pant@mac.com
```

Rules, all enforced by `scripts/mailboxes.py`:

- Exactly one workspace declares each account. A seat sweeps its own
  manifest's accounts and no others; mail it needs from another
  workspace's account goes through that seat.
- `forwards-to` entries need `delivers_to` and take no `role`/`sweep` —
  they document where mail lands so nobody sweeps an alias as a mailbox.
- `mailboxes` bounds the sweep (INBOX, not Archive/Newsletters with
  thousands of unread). Omit it only when INBOX-only is correct.

## Sweep states

The email surface reports per account, never as one blended "email
done":

- **SWEPT** — advanced this run with a `through` moment.
- **BLIND** — due and neither swept nor deferred with a reason. Fails
  the ritual: sweep it now or defer it with an explicit reason.
- **UNREACHABLE** — attempted, transport failed. Defer with a reason
  starting `unreachable:` (e.g. `unreachable: apple-mail auth
  expired`). Passes loud — the report names it — because an attempted
  failure is information, while silence is a lie.
- **DEFERRED** — skipped deliberately with a dated reason (travel,
  outage window). Passes with the reason on record; a deferral older
  than a day stops counting and the account is BLIND again.
- Not due (weekly inside its window, on-request unasked) is not a gap
  and needs no record — but anything swept shows up regardless, so the
  report's denominator is every account touched plus every account due.

A coverage claim names its denominator: "2 of 3 swept (mac.com
UNREACHABLE: auth expired)" carries information; "email done" does not.
