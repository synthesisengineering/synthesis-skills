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
- [Browser profiles](#browser-profiles)

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

## Browser profiles

`guards.check_browser`, for every `mcp__claude-in-chrome__*` call (2026-10-21; the principal's workspace rule had
been on disk since 2026-10-01).

THE INCIDENT. One Chrome extension serves every session on the Mac, and it acts in whichever browser any session
selected last. The extension reconnected with a new tab group on the profile another workspace's session had
picked, and a session kept working there for about 15 minutes, a public post included. The rule naming each
workspace's profile was already written; as with the calendar incident, a rule on disk was not read at the
moment of acting.

What it does, when `browser_routing.workspaces` maps the workspace the session started in to a device:

- `list_connected_browsers` always passes: it only lists.
- `select_browser` passes only for that workspace's device, and records the session and device as the
  extension's latest selection. Any other device, and `switch_browser` (which lets whatever browser the
  principal clicks connect), are refused.
- Every other browser call passes only when this session made the latest selection, to its device, and its
  transcript shows that call returned `Selected browser "..."` without an error. A selection by any other
  session, to any device, re-arms the check, because the shared extension's browser or tab group may have
  changed. The transcript is read once per selection, from its last 8 MB.

The workspace is the one recorded when the session started, so a session that changes directory keeps its
browser. Outside every mapped root, and with no `browser_routing`, nothing is checked. A malformed map or a
mapped root without a device blocks; so does an unreadable config.

What it cannot see: a change made in Chrome itself (the principal switching the extension's browser by hand),
and browsers driven by other harnesses' own browser tools. The selection is read from Claude Code's transcript;
elsewhere it never confirms, so the calls stay blocked.

Tests: `tests/test_browser_guard.py`.
