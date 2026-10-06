# Account routing

`guards.check_account`, run by the PreToolUse hook before the send guard, so no approval
is ever spent on a call from the wrong account.

## Contents

- [The incident](#the-incident)
- [Why a gate and not a rule](#why-a-gate-and-not-a-rule)
- [What it does](#what-it-does)
- [Why the boundary is narrow](#why-the-boundary-is-narrow)
- [Design](#design)
- [Tests](#tests)

## The incident

THE INCIDENT (2026-09-11). A short calendar invitation to two client colleagues was
created through the personal-account calendar connector. It dispatched with a personal
address as organizer. Deleting the event does not unsend an invitation, and
suppressing the cancellation leaves a stale invite with no explanation. The cost is
reputational, it lands on the principal rather than the agent, and it cannot be
undone after the fact. Earlier, a brief had resolved to the wrong Gmail account
(2026-08-09): name the connector and the account explicitly.

## Why a gate and not a rule

The routing rule was written into the workspace instructions the same day. That is
necessary and demonstrably insufficient: three separate violations that week were of
rules already sitting on disk, unread at the moment of acting. The message guard exists
for the same reason on the send boundary. This is that boundary for calendar and mail
artifacts, one account layer up.

## What it does

When the session's working directory is inside a configured workspace, a call that
creates or changes an outward-facing artifact must act as that workspace's account (or one
of its aliases). Routed tools, matched on the tool's own name after the last `__`:
`create_event`, `update_event`, `delete_event`, `manage_event`, `respond_to_event`,
`manage_focus_time`, `manage_out_of_office`, `send_gmail_message`, `draft_gmail_message`,
`create_draft`, `update_draft`, `send_email`, `reply`, `forward`, `trash_message`,
`trash_thread`, `share_file`, `set_drive_file_permissions`, `manage_drive_access`, and
`send_message` when it addresses a mailbox or Chat space.

The account a call acts as is the first of `user_google_email`, `from_account`,
`from_email`, `account`, `user_email`, `sender` or `calendar` it carries (Apple Calendar
chooses the account by calendar name). A call with none acts as its connector's own
account, which is `account_routing.default_account` when configured; inside a workspace
bound to another account it is refused, naming the right account and the parameter to
pass. Reads are never routed, and outside every configured workspace nothing is.

## Why the boundary is narrow

This gate is about GOOGLE ACCOUNT IDENTITY. Every widening of it past that has been a
false positive, twice within an hour of being written:

  1. The first draft matched tool-name SUFFIXES, so `slack_send_message` matched `send_message`
     and every Slack send from a client workspace would have been blocked — the sanctioned
     agent-send lane included, which carries no Google account parameter and never will.
  2. The second draft matched terminal names exactly but kept a bare `send_message`, so
     one agent-messaging server's send_message — one agent session messaging another,
     nothing outward, no account at all — was blocked on its first live call.

A guard that blocks approved paths trains its own bypass, and that is a worse outcome than
the incident it was built for. So: names that are distinctively Google are gated
unconditionally; `send_message`, which three different servers use for three different
things, is gated only when its payload carries an addressee (the Gmail and Chat shapes).
Slack's boundary is synthesis-message-guard. Session-to-session messaging has no account
boundary to cross.

## Design

1. FAIL CLOSED on its own errors. An unreadable config blocks routed calls; it does not
   wave them through. A workspace with no account blocks routed calls there.
2. ZERO DEPENDENCIES. Stdlib only.
3. READ-ONLY CALLS ARE NEVER BLOCKED. Reading the personal calendar from a client
   workspace is legitimate and common (conflict checks). Only mutation is gated.
4. EMPTY AUTHORITY UNTIL CONFIGURED. With no workspaces configured the gate allows: it
   must not brick routine tool use.

## Tests

`tests/test_account_routing.py`: the incident shape, account-less calls, aliases and
display addresses, Apple Calendar by calendar name, the deepest workspace winning, `~`
and symlinked roots, reads, Slack and session messages left alone, an addressed
`send_message` on any server, a wrong-account send refused before any approval is filed,
and malformed or unreadable config failing closed.
