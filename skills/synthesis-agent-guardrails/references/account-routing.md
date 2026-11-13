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
- [The account a site shows](#the-account-a-site-shows)

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

## The account a site shows

`guards._account_hold`, which `check_browser` asks once the profile is the right one (2026-11-13).

THE INCIDENT (2026-11-12). A work browser profile was signed in, on a site where an AI assistant is used, to the
principal's personal account. The agent found it and reported that the work could not be tested from there. It
was no limit on the work: it was a misconfiguration to bring to the principal, and nothing brought it. The right
profile can show the wrong account, and what is typed or uploaded there then goes into an account the workspace
does not own.

What it does, when the workspace's entry under `browser_routing.workspaces` has `accounts`:

- `accounts` maps a site to the workspace's address there: `{"assistant.example": "me@clientco.example"}`. A site
  covers the hosts under it, so one entry is all a site takes. A key may name the page of the site that shows
  the signed-in account (`"assistant.example/settings"`, or with the page's query or fragment where that is how
  the site names it); then only a read of an address that begins with the key counts.
- **A call that puts something into a page of a named site waits:** `computer` with `type` or `key`,
  `form_input`, `file_upload`, `upload_image` and `javascript_tool`, alone or as a step of `browser_batch`, which
  waits whole. The page a step acts on is its tab's address in the newest list of tabs in the session's record,
  or the address a `navigate` step earlier in the same batch went to.
- **Going to the site, reading it and clicking on it never wait.** The account often shows only after a menu is
  opened, so a rule that held clicks could not always be satisfied.
- **What lets the call through:** the newest read that settles the question shows the workspace's address. A read
  settles it when it is the result of a browser call that ran on a tab of the site, is no error, and holds,
  before its list of tabs and apart from any address the call itself named, either the workspace's address and
  none of the principal's others, or one of the others without it. A page that shows both, as an account
  switcher does, settles nothing. Neither does a batch whose steps ran on two tabs or went somewhere after its
  first step: its result names one tab, the one it ended on, and its reads may be of another page. The
  principal's addresses are those the config names: `account_routing`'s, the same-day rule's `own`, and every
  workspace's `accounts`.
- **Another of the principal's addresses is called what it is.** The hold says that the profile is signed in to
  the site as that account, that this is a misconfiguration to tell the principal about now, with the profile
  and the site named, and that it is not a limit on the work and no reason to do the work somewhere else.
- **The doctor remembers it.** What each settling read showed is written to `state/browser-accounts.json`, by
  profile and site. `synthesis doctor` warns (`browser accounts`) while the newest one for a named site is not
  the account the config names now. The line clears when a session next reads the site and it shows that account.
- **The end of the turn asks too.** The reply check reads the turn's own lines the same way, and a turn that read
  another of the principal's accounts on a named site has its reply sent back once with the same words, whether
  or not a call was held ([reply-and-provenance.md](reply-and-provenance.md#a-site-signed-in-to-another-account)).
  In the incident no call was held: the agent read the page and stopped.

A map of another shape (a value that is no address, a key that is no host name, two keys for one site or for a
site and a host under it) blocks the workspace's browser calls until it is fixed.

What it cannot see: a browser. It knows only what a read brought into the record. So a page that shows the
workspace's address for another reason (a conversation that mentions it) counts as showing the account, unless
the key names the account's page. An account shown only in a picture is not read. An address the config does not
name settles nothing. A tab that moved since its last result is judged by where that result left it. A call
through computer use on the desktop is not a browser call. The record is read from its last 8 MB, so a long
session may be asked to read the account again.

Replayed over thirty days of recorded browser calls (2026-11-13), with the sites where an AI assistant is used
named for two workspaces: of 3,130 browser calls, 349 had a step on a named site. None of the 250 that only read,
pointed or went there was held. Of the 99 that put something into a page there, 26 came after a read that had
shown the workspace's account, and 73 came before any such read, in four sessions.

Tests: `tests/test_browser_accounts.py`.
