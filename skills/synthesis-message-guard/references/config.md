# Send-guard configuration

The guard reads `~/.synthesis/v5/config.json`, the principal's private file. An
unreadable or malformed file blocks every send (R3.5); a missing file means the defaults
below. The public starting point is
[config.example.json](../config.example.json), which the tests load in CI, where there is
no `~/.synthesis`.

**When the guard cannot answer** (5.21.0). In Claude Code the plugin's PreToolUse hook sets
`"onFailure": "block"`, so from Claude Code 2.1.295 a send is held when the guard times out (its
limit is 5 seconds), crashes, prints output Claude Code cannot read, or cannot start because the
stable hook is missing; Claude Code names the hook and says `failed` or `timed out`. An older
Claude Code ignores the setting and lets the send through, and `synthesis doctor` warns. Codex
(0.167) and Muse (1.4.20) have no such setting, but block on exit 2 with a reason, so the guard's
own command turns a stable hook that cannot start or crashes into exit 2 with one line of reason,
and a send is held there too (Muse's hook test, run on 2026-11-14). The guard keeps a deadline of
its own, 4 seconds from when the hook starts judging the send (5.21.1): past it the send is held,
and any process the guard started is stopped, so a slow guard answers closed in every harness
inside its 5-second limit. What still lets a send through in Codex and Muse is a hook that uses up
their 5 seconds before its deadline is set: Python itself slow to start by more than about a second.
An unreadable config and an error inside a guard still block in all three, since the guard catches
those itself.

## Keys

| Key | Meaning |
|---|---|
| `send_tools` | Extra tool-name globs to guard, beside the built-in Slack, Gmail, email, chat and draft patterns (`mcp__*slack*send_message*`, `mcp__*send_gmail_message*`, `mcp__*create_draft*`, `mcp__*__reply`, ...). A calendar create, update or delete listed here that names no attendees and sets notifications to `none` emails no one and goes without a code; every RSVP waits, whatever its notifications (2026-10-23). |
| `forbidden_phrases` | The register scan: `[{"name", "pattern", "why", "case_sensitive"}]`. Patterns are Python regexes, matched case-insensitively unless `case_sensitive` is true. |
| `message_format.allow_line_breaks_in_paragraphs` | Default false. True only for content whose line structure matters (an address block, poetry). Changes formatting only. |
| `message_format.default_email_format` | Default `html`. `plain` lets every transport send plain text (still with whole paragraphs). |
| `message_format.plain_email_tools` | Tool-name globs of transports that can only send plain text (for example `mcp__apple-mail__*`). |
| `signature.markers` | Strings that mark a persona signature (for example the persona's emoji). |
| `signature.domains` | Persona domains that must appear only inside a link on a link-capable channel. |
| `signature.plain_url_tools` | Tool globs whose channel cannot render links, where the visible domain is the right form. Fields that never render a link are left out of the check in any tool: an RSVP's comment (`rsvp_comment`, `responseComment`), which reaches the organizer as plain text (2026-10-22). |
| `own_repos` | Repository globs (`owner/*`, `owner/name`) whose PRs, issues and comments are the principal's own work, not sends: GitHub connector tools naming that `owner`/`repo`, and `gh` commands whose `-R`, API path or `origin` remote names it. |
| `not_send_tools` | Tool globs never treated as sends, for a tool whose name reads like one but reaches no person. |
| `send_commands` | Extra `[channel, regex]` pairs for shell programs that post, matched from the start of a command's words (built in: `gh`, `bkt`, `glab`, `jira`/`acli`, `osascript` Messages or Mail, and `curl`, `wget`, HTTPie writes to another host). |
| `send_window_signatures` | Regexes; inside an open send window, a send goes without a per-message code only if one matches its text. List the signatures of the lanes the principal lets a window cover. Empty means a window covers nothing. |
| `forbidden_phrases[].channels` | Optional on a register rule: the channels (`jira`, `bitbucket`, `slack`, `docs`...) where it holds; elsewhere the rule is skipped. For a line that fits some channels only: on 2026-10-27 a line saying the principal had not reviewed the details, which fits scheduling, went out on Jira answers. |
| `messaging_apps` | Extra bundle ids of chat apps where computer use counts as messaging (Return sends, shift with Return writes a line), beside the built-in list below. A value that is not a list of strings stops every computer-use action. |
| `same_day_meetings` | `{"exempt": ["<address or pattern>"], "own": ["<address or pattern>"]}` (`own` optional: the principal's addresses beyond those `account_routing` names). With this key present, a calendar create, update or move that starts today and invites anyone but the principal waits for an approval of its own that names it same-day. A meeting with an exempt attendee keeps the ordinary approval. Absent means no rule; a value that is not this shape blocks calendar writes. See below. |
| `fresh_calendar` | `{"minutes": 10, "reads": ["<the end of a tool's name>", ...]}` (both optional; `{}` turns the rule on with ten minutes). With this key present, a message to a person (a call whose name says it sends, replies, forwards or drafts a message, on mail, Slack, chat or texts or by a connector the guard has no name for; a text or a mail from the shell) whose words name a clock time is held unless this session read a calendar, and the read succeeded, in those minutes before the call. `reads` names tools that read a calendar beside the ones the guard knows, each by its whole name, a pattern over it, or its end. Any other shape blocks messages until it is fixed, `null` included; leaving the key out, or `false`, turns the rule off. See below. |
| `in_person_travel` | `{"preferences": "<the chief-of-staff preferences file>"}`. With this key present, a calendar write that creates an event at a place, or gives one a place, is refused unless the call carries the event's travel line (`Travel: ...` in its description). What a place is comes from that file's `travel_policy` and the chief of staff's `travel_check.py`. No approval is asked. Without the key nothing changes; a policy that cannot be read refuses the write |
| `temporary_addresses` | `{"hosts": ["<more host names>"], "local": true}` (both optional; `{}` turns the rule on). With this key present, a send, a draft, a shell post or typed words that hold an address that can change, or that only this machine or its network answers, are refused before any approval is asked, and starting a quick tunnel waits for a code of its own. Absent means no rule; a value that is not this shape, `null` included, blocks sends. See below. |
| `preferred_names` | People who go by a name other than their official first name: `[{"official": "Robert", "preferred": "Bob", "identifiers": ["bob@example.test", "U0EXAMPLE"]}]`. Optional; absent means no name check. See below. |

None of these keys can grant a send: approval is always the principal's, and overrides
change formatting only. Grounding, register, recipient, branding, threading, approval and
disclosure requirements stay in force.

## Preferred names

A person is addressed by the name they go by, not by the official first name a
directory or an email header shows (`synthesis-agent-correspondence` binding rule 12;
on 2026-10-13 an agent message addressed someone by the official first name a
directory showed, not the name she goes by). Each `preferred_names` entry names one person:

- `official`: the official first name, matched as a whole word and case-sensitively,
  so "Robert's" is caught and a lowercase email local part is not.
- `preferred`: the name they go by, which the problem text tells the agent to write.
- `identifiers`: strings that identify that person on the channels the principal uses:
  email addresses, a Slack user ID (which also appears inside mention syntax such as
  `<@U0EXAMPLE>`), a Slack DM channel ID, a Jira account ID (as in `[~accountid:...]`).
  Matched without regard to case anywhere in the call: recipients, channel, subject or
  body.

The guard flags the official name only when one of that entry's identifiers appears in
the call, so a message to someone else who shares the first name is never blocked. It
reads every string in the call (body, HTML body, subject, event title) except the
address fields (`to`, `cc`, `bcc`, `recipient`, `recipients`, `space_id`, `space_name`,
`user_google_email`), where a display name such as `Robert Example <bob@example.test>`
is an address, not a greeting. Mention syntax stays whatever the platform requires;
only the words around it change. The problem text names the preferred name:

```text
this message involves someone who goes by Bob; write Bob, not Robert
```

A message that names the person without any identifier in the call (a group channel
where they are mentioned by name only) is not checked; the drafting rule still applies.
An entry that is not an object stops every guarded send, like any malformed config
(R3.5); `identifiers` is a list, never a single string.

## Same-day meetings (2026-11-09)

A yes to a meeting is not a yes to the earliest free slot. On 2026-11-09 an agent staged a
meeting into the first open slot of the same day, three days running, because the requester
had suggested "tomorrow or Monday". The principal approved each invitation, and nothing in
that approval said the meeting was today. With `same_day_meetings` in the config:

- **What it holds:** a calendar write (`create_event`, `update_event`, `manage_event`,
  `move_event`, with `_` or `-` in the name, singular or plural) whose start falls on today
  and that invites at least one address other than the principal's own, or that moves an
  existing event to today (an update names the event, not its guests, so only a write that
  emails no one is left alone). The start is read from `start`, `start_time`, `startTime`,
  `start_datetime`, `startDateTime`, `start_date` or `startDate`, flat or nested
  (`{"dateTime": ...}`, `{"date": ...}`), in the call or in a list of events at any depth
  inside it. A start is today when its date as written is today (ISO, or a written date such
  as `9 November 2026 at 3:00 PM`), when the same moment is today on this machine's clock,
  or, for a time with no offset, when it is today in a time zone that event names. Attendees are read from any field
  whose name contains attend, guest, invite or particip, in whatever shape the connector
  takes; people a call removes and booked rooms are not counted.
- **What it says:** `This puts a meeting on today's date and invites N other(s)` (or `This
  moves a meeting to today's date`) `... propose
  another day unless the principal asked for today ... type approve followed by the code
  <code> for this same-day meeting.` The ordinary invitation approval does not cover it, and
  neither does a send window.
- **A move with notifications off is still a move.** Turning notifications off makes a calendar
  write the quiet kind that needs no approval, except when it moves an existing event to
  today: its guests' calendars change all the same. The one exception is an event the
  chief-of-staff skill's holds ledger has as a hold the agent placed that is in force today
  (not released, not past its expiry, its instance for today not released), which has no
  guests by construction. The guard asks the ledger's own reader, `holds_state.py`, which
  every install keeps in the runtime; a ledger or a reader it cannot read exempts nothing.
- **What it leaves alone:** a meeting on any other day; a write with no attendees (a hold,
  a focus block), including an update that sets an empty guest list; a meeting whose guests
  include an `exempt` address or pattern (`chief@example.test`, `*@board.example.test`),
  which keeps the ordinary approval because that person's timing binds; and the principal's
  own addresses, taken from `account_routing` (`default_account`, each workspace's `account`
  and `aliases`) and from the rule's `own` list. A guest is exempt by their address field, never by a display name, and in
  a call that writes several events each event is judged by itself, with its own time zone,
  wherever the list of events sits in the call.
- **A zone it cannot read is sent back, not guessed:** when a start has no offset, names a
  time zone this machine does not know (a Windows name such as `Tokyo Standard Time`) and
  its written date is within a day of today, the call is refused with a request for a UTC
  offset or an IANA zone name; nothing is approved or held.
- **Also since 2.6.0:** a tool named `move_event` is a send like the other calendar writes
  (moving a meeting notifies its guests), and a calendar write with guests anywhere in the
  call, not only at its top level, is never the quiet kind that needs no approval.
- **What it cannot see:** an update that sets no start (adding a guest to a meeting already
  on today), an RSVP, a start written in a form this cannot read (it reads ISO and day, month and year in words), and a
  meeting placed through a browser or computer use. The
  chief-of-staff skill's slot check covers the decision before any call is made.

## A time in the words (2026-11-12)

A calendar read at the draft is not a calendar read at the send. On 2026-11-12 a meeting request offered a time
that a new invitation, arrived half an hour earlier, overlapped: the calendar had been read when the message was
drafted, and the draft then waited for its approval. Every send waits for one, so every offer of a time has that
window. The guard cannot know that a message proposes a meeting. It knows that the words name a clock time, and
when this session last read a calendar. With `fresh_calendar` in the config:

- **What it holds:** a message to a person whose words name a clock time, anywhere in the call's text, while this
  session's record shows no calendar read that succeeded in the last ten minutes (`minutes` sets another number,
  1 to 60).
- **A message to a person** is a call the guard takes for a send whose own name says it sends, replies, forwards
  or drafts a message (`send_gmail_message`, `reply`, `forward`, `slack_send_message_draft`, `imessage_send`), on a
  channel of messages (mail, Slack, chat, texts) or on one the guard has no name for, as a mail connector whose
  server is named by an id is. A draft is one, since it is written to be sent. From the shell it is `osascript` to
  Messages or Mail, a command `send_commands` names for `messages`, `email`, `slack` or `chat`, and the
  local-messaging skill's sender, which asks the guard itself. Not one: a calendar write, whatever its server is
  called (an event states its own time, and the calendar rules judge it, the same-day rule among them); a
  harness's own tool (a note to an agent, a file for the principal); a ticket, a comment, a reaction, a share, an
  out-of-office note, a canvas, a document, a page. Each of those still waits for its ordinary approval where the
  guard takes it for a send. So does a message typed into a web page or an app by computer use: this rule reads
  connectors' calls and shell commands, and no screen.
- **A clock time** is `3:30`, `15:30`, `3 pm`, `11am`, `3:30 p.m.`, `7.30 pm`, `3:30p`, `14:00h`, `15h30`, and
  the hour that closes a range (`2-3pm`, `10-11am`). Not one: a duration (`1:23:45`), a time inside a web address
  or after its `#`, an offset alone (`-05:00`), a full stamp with its offset
  (`2026-11-13T10:20:00-05:00`), and a time in words or with a dot and no `am` or `pm` (`noon`, `Thursday
  afternoon`, `19.30`), which is not held. A time in a quoted thread is held like any other; in thirty days of
  recorded messages that name a clock time (164), none quoted one. A number that only looks like a time (`John 3:16`, `line 12:30`) is
  held like one.
- **When it asks:** at the first call, before any approval code is asked, so the principal is not shown a text
  the check may still change; and again at the approved call, since the approval may have taken longer than the
  read stays fresh. That second question is the moment the incident missed. An approval already typed stands: the
  hold spends nothing, and the same call goes once the calendar is read.
- **What it says:** `This message names a time (<the times, as written>), and this session last read a calendar
  N minutes ago` (or `has not read a calendar`) `: one is read in the 10 minutes before such a message goes. Read
  the calendar for the day it names, check each time against what is there, and make this identical call again
  ... If its time is no calendar's, or this session has no calendar to read, show the principal the exact text
  and ask them to type approve followed by the code <code> to send it as it is.`
- **The code of its own:** a status note that says when something happened names a time and offers none, and a
  session may have no calendar to read. The principal releases such a message by the code the hold gives, whose
  request says what it waives. It stands in place of the ordinary code, for that exact message, once, whatever
  the read is by then. The ordinary approval does not waive the read, and neither does a send window: a message a
  window covers is still held until the calendar is read. A message that goes on one code spends the other, a
  request still waiting included, so a second copy is shown again. Sends are judged one at a time, so two
  identical calls made at the same moment cannot each go on one of the two codes.
- **What counts as a read:** a call whose result came back and was no error, to a tool whose name ends in
  `get_event`, `get_events`, `list_events`, `search_events` or `list_all_events` (with `_` or `-`) and says it is
  a calendar's (`calendar`, `gcal` or `caldav` anywhere in the tool's whole name, or a server named `workspace`,
  `workspace-mcp` or `google_workspace`), or to one named `query_freebusy` or `suggest_time`. An error tracker's
  `search_events`, a repository's `list_events` and a server that only has `workspace` in a longer name are none.
  `reads` adds tools: each entry is a tool's whole name, a pattern over it (`mcp__0a1b*__list_events`, or a whole
  server, `mcp__acme-cal__*`) or its end after the last `__`. A calendar connector whose server is named by an id
  needs an entry. A read that failed, one with no result yet, a calendar write (whatever names its server), and a
  result dated more than a minute ahead of the clock are none. The time is the one on the result.
- **Whose record:** the guard reads the last 8 MB of a Claude Code transcript. A sender that asks from a script,
  as the local-messaging skill's does, passes no record, and the guard finds the session's by its id. In Codex and
  Muse it does not see a calendar read, and the hold says so: there, reading the calendar cannot clear it, and the
  code of its own is the release, after the agent says when it read. The same holds for a sub-agent, whose calls
  and results are kept apart from its session's: its hold says its own reads are not seen. A session whose record
  cannot be read has read no calendar. A sub-agent's read in the main record is not this session's.
- **What it cannot see:** whether the read covered the day the message names, and whether the agent compared: the
  read puts the calendar in front of the agent at the moment of sending, and the hold's words say what to check.
  A draft the principal sends himself is fresh when it is made, not when it leaves.

Replayed with the rule's own code over recorded messages (2026-11-13, as it stands after a second review): of 451
distinct messages sent to people on 76 days, 143 named a clock time, and 89 of those would have been held at their
last call. Read by eye on
a small sample, about six in ten of the messages that name a clock time are about when people meet; the other holds
cost one calendar read each and reach no one (`tests/test_fresh_calendar.py`).

## An address that can change

What another person is given must stand on an address that stays. On 2026-11-12 a connector tested
on a laptop behind a quick tunnel was handed to two colleagues in direct messages that carried the
tunnel's address. One of them relied on it for real work; when the laptop's app restarted, the
address was gone for good. With `temporary_addresses` in the config:

- **What it refuses:** a message whose words hold a quick tunnel's host (a subdomain of
  `trycloudflare.com`, `ngrok.io`, `ngrok.app`, `ngrok.dev`, `ngrok.pizza`, `ngrok-free.app`,
  `ngrok-free.dev`, `ngrok-free.pizza`, `loca.lt`, `localtunnel.me`, `serveo.net`,
  `serveousercontent.com`, `localhost.run`, `lhr.life`, `lhr.rocks`, `pinggy.io`, `pinggy.link`,
  `pinggy-free.link`, `devtunnels.ms`, `app.github.dev`, `ts.net`, `tunnelmole.net`, `bore.pub` or
  `loophole.site`, the services the knowledge-base
  connector refuses to start on, or a host the config's `hosts` names and its subdomains), a tunnel
  service's own host with a port, with or without a scheme, since bore hands out `bore.pub:<port>`
  (`bore.pub:41234`, `http://bore.pub:41234`), and, unless `local` is
  false: `localhost`, a `.local` or `.localhost` name or a private-range address written with a
  scheme or a port (`http://localhost:8787`, `my-laptop.local:3000`, `http://192.168.1.20:8000`),
  and a loopback or any-interface address however written (`127.0.0.1`, `0.0.0.0`). A port is one
  to five digits (`localhost:9`, `laptop.local:9`), and a host is read whole, to where its name
  ends. The scheme may be any but `file://`, whose host names this disk
  (`file://localhost/tmp/plan.pdf` is a file, as a connector takes one), and a user and password
  before the host are read past and never shown (`ssh://10.1.2.3`, `ftp://192.168.1.2/data`,
  `postgres://app:secret@10.1.2.3:5432/app`);
  a quick tunnel's host is read past them too. A link-local address counts with the private ranges
  (`http://169.254.169.254`, `169.254.10.1:8080`), and so does the shared range `100.64.0.0/10`,
  which a carrier's network and a tailnet's addresses use and the knowledge-base connector refuses
  (`http://100.64.0.1`, `100.100.100.100:3000`; `http://100.128.0.1` is outside it). A
  wildcard-DNS name is the address it carries, as `nip.io` and `sslip.io` read one: four numbers
  joined by dots or by dashes, or eight hex digits, after the start, a dot or a dash, or an IPv6
  address with dashes for its colons as a label of its own. When that address is loopback,
  private, shared or link-local the name is refused however written (`192.168.1.20.nip.io`,
  `https://app.192.168.1.20.nip.io/x`, `http://10-0-0-5.sslip.io:8080`, `app-127-0-0-1.nip.io`,
  `7f000001.nip.io`, `--1.sslip.io`). A bracketed IPv6 address that is loopback,
  any-interface, unique-local or link-local is refused however written (`http://[fd12::42]:8080`,
  `http://[fe80::12]:9090`, `[::1]`). It reads every
  path a message takes: a connector's send or draft, a shell command that posts, and words typed
  into a messaging app or a browser page.
- **What releases it:** the principal's approval of the address itself. The refusal carries a code
  for exactly the addresses it found; once they type it, a message that holds those addresses goes
  on to the ordinary approval of the message, for fifteen minutes. The approval of a message never
  releases an address, and an approval of one address covers no other.
- **What passes:** the word `localhost` in a sentence, a file named `.env.local`, a version number
  that looks like an address (`10.2.3.4`), a tunnel service's own site (its bare name in prose,
  `bore.pub`, and a documentation link, `https://ngrok.io/docs`), a look-alike host
  (`notbore.pub:41234`, `bore.pub.example.com:41234`), and an address at a host no rule names. A public name that only begins like a local one is that public
  name (`https://localhost.example.org`, `https://10.2.3.4.example.org`,
  `https://example.localhost.org`), and so is a name that a wildcard-DNS service points at a
  public address (`https://app.203.0.113.9.nip.io`, `https://8.8.8.8.sslip.io`): put the service
  in `hosts` (`nip.io`) to have all its names refused. A file's name with its line number is no address: a dotfile
  (`.env.local:12`), a name that goes on past `.local` (`settings.local.json:3`), and a name ending
  in `.local` with no scheme before it that is a configuration file's (`config.local:7`: the word
  before `.local` is `config`, `conf`, `cfg`, `cnf`, `ini`, `env`, `rc`, `settings`, `properties`,
  `json`, `yaml`, `yml`, `toml`, `makefile` or `dockerfile`), that follows a path
  (`src/app.local:42`, `/etc/rc.local:14`) or that has a column after its line
  (`notes.local:17:3`). Any other name ending in `.local` with a port is an address
  (`app.local:7`), and so is every one after a scheme (`http://config.local:7`). An address
  outside those ranges passes after any scheme (`ssh://build.example.com`, `http://172.32.0.1`,
  `http://[2001:db8::1]:8080`), and so does a bracket that follows a word (`rows[::1]`). An IP
  address with a prefix length after it and no scheme, `//` or port before it names a range and
  passes (`0.0.0.0/0`, `10.0.0.0/8`, `127.0.0.0/8`, `[fd00::]/8`): the length is `/0` to `/32`,
  and to `/128` for a bracketed IPv6 address. After a scheme what follows the host is a path, and
  the address counts (`http://10.0.0.5/8`), as it does past a length no range has
  (`127.0.0.1/33`, `127.0.0.1/8080`).
- **Starting a tunnel:** `cloudflared tunnel --url ...`, `ngrok http`, `tcp`, `tls` or `start`,
  `devtunnel host`, `localtunnel` or `lt` with a port (also through `npx`, `bunx`, `pnpm` or `yarn`), and a reverse
  `ssh -R` to `serveo.net`, `localhost.run` or `pinggy.io` wait for the principal's code. `autossh`
  is read as `ssh` is, and its own `-M <port>` takes a value
  (`autossh -M 0 -R 80:localhost:8080 serveo.net`; `autossh -M 20000 -R 9000:localhost:9000
  build.example.com` starts nothing). `devtunnel host` is read past `devtunnel`'s own options
  (`devtunnel --verbose host -p 8080`; `devtunnel --verbose list` starts nothing). The hold
  says what a quick tunnel is for: their own test, with an address that is never given to anyone. A
  named tunnel (`cloudflared tunnel run <name>`) is a deployment and is not held here. `cloudflared
  tunnel` is a quick tunnel with `--url` and no subcommand, or with `--hello-world`
  (`cloudflared tunnel --no-autoupdate --url http://localhost:8080`, `cloudflared tunnel
  --hello-world`); followed by any of its subcommands (`login`, `create`, `route`, `vnet`, `run`,
  `list`, `ready`, `info`, `ingress`, `delete`, `cleanup`, `token`, `diag`, `proxy-dns`, `help`)
  it is a named tunnel's command, whatever options it carries
  (`cloudflared tunnel run --url http://localhost:8080 production`,
  `cloudflared tunnel --config config.yml run`). The `ssh`
  destination is read as a host, in any case, with or without a user, an `ssh://` scheme or a
  port: a reverse forward is a tunnel when that host is the service's name or a subdomain of it
  (`serveo.net`, `qr@a.pinggy.io`). A host that only ends with a service's letters is someone
  else's (`notserveo.net`, `team-pinggy.io`), and a jump host, a key file's name or a word of the
  remote command that carries a service's name makes no tunnel.
- **The services added last, in their own forms:** `bore local <port> --to bore.pub` (or `-t`,
  or `--to=`; the server read as a host, in any case and with or without a closing dot,
  `--to BORE.PUB.`), `tmole <port>` and `tunnelmole <port>` (`tmole 8080 as demo.tunnelmole.net`
  too), `loophole http <port>`, `loophole path <folder>` and `loophole webdav <folder>`, and
  `tailscale funnel <port or target>` (`tailscale funnel --bg 3000`,
  `tailscale funnel --https=8443 localhost:3000`) wait for the code. Their lookups start
  nothing: `bore --version`, `bore server`, `tmole --help`, `loophole account login`,
  `loophole version`, `tailscale funnel status`, `tailscale funnel reset`, a funnel turned
  `off`, and `tailscale serve ...`, which a tailnet's own members reach and the public does not.
  Nor does `bore local` to a server of one's own (`--to tunnel.example.com`) or to a name that
  only starts with the service's (`--to bore.pub.example.com`).
- **The forms a start takes:** each of those is read however the command spells it.
  - The program named through a variable the command sets:
    `tunnel_program=cloudflared; $tunnel_program tunnel --url ...`.
  - A package or an image without its version or tag: `npx --yes localtunnel@2.0.2 --port 7777`,
    `cloudflare/cloudflared:latest`.
  - The words of `pnpm`, `yarn`, `npm`, `bun`, `docker`, `podman` and `nerdctl`, read from each
    one on as the command it runs: `pnpm dlx localtunnel@2.0.2 --port 7777`,
    `npm exec --yes localtunnel@2 -- --port 3000`,
    `docker run --rm cloudflare/cloudflared tunnel --url ...`,
    `docker run ngrok/ngrok:latest http 8080` and
    `docker run pinggy/pinggy -p 443 -R0:localhost:8000 a.pinggy.io` (`pinggy` takes the words
    `ssh` does).
  - `ngrok`'s subcommand after its own options and their values: `ngrok --log=stdout http 7777`,
    `ngrok --config ngrok.yml start web`. It is the first word that names one of its subcommands;
    `http`, `tcp`, `tls`, `start` and `start-all` start a tunnel.
  - `-R` alone, in a cluster or with its value joined on, before the destination or after it:
    `ssh -NR 80:localhost:7777 nokey@localhost.run`, `ssh -NR80:localhost:3000 serveo.net`.
  - What starts nothing still passes: a variable that only names the program
    (`echo "$tunnel_program"`), a named tunnel in a container
    (`docker run cloudflare/cloudflared tunnel run <name>`), `docker pull` of an image,
    `ngrok help http`, `ngrok --log=stdout config check`, a package that is installed or looked
    up (`npm install localtunnel@2.0.2`), another package with a port
    (`npx --yes cowsay@1.6.0 --port 7777`), a forward the other way (`ssh -NT -L ...`), and `-R`
    among the words of a remote command (`ssh nokey@localhost.run ls -R /tmp`).
- **The doctor** proves the rule reads a quick tunnel's address under the installed config
  (`temporary addresses`), and fails when the setting cannot be read.
- **A setting that cannot be read:** anything but an object of that shape, a key that is present
  and `null` included. Sends stop with a message that names the setting, starting a quick tunnel
  is still held for its code, and the doctor fails its line. Only an absent key means no rule.

What a handoff to another person needs instead is in synthesis-implementation-integrity,
`references/handoff-gate.md`.

## A meeting at a place

An in-person commitment is not on the calendar until its travel is. On 2026-11-11 an evening event 28
miles from a principal's home had sat on his calendar for six days with no travel time, route or
fare; he owns no car, and the event was personal, so one could not be expensed. The agent that wrote
the event was never asked how he would get there. With `in_person_travel` in the config:

- **What it refuses:** a calendar write (the same tool names as above) whose event is at a place
  (`location`, `locations`, `where`, `place` or `venue`, written out or as a structure) and whose
  description (`description`, `notes`, `body` or `details`, plain or HTML) carries no `Travel:` line. The refusal says what to do: work the trip out as the chief-of-staff skill's
  `references/in-person-travel.md` sets out, put a travel block on each side, write the line, and
  make the call again. It asks for no approval, so an agent clears it by doing the work.
- **What passes:** no location; a link, a phone number or one of the policy's `online` words, unless
  the location also holds a street address (a venue called Zoom Hall is a place); the principal's
  home or a named place of the policy; an event whose title starts with the policy's
  `block_title` (a travel block is not itself a commitment); an update that sets no location. A
  line that is a placeholder ("TBD") is no line. Each event of a call that writes several is
  judged by itself.
- **Whose rules:** what a place is and what a travel line is are read from the chief of staff's own
  `travel_check.py` and the `travel_policy` in the preferences file the key names. The guard holds
  no copy of either. When that file or its policy cannot be read, a write that names a place is
  refused with the reason; a write that names none (a hold, a rename) is not judged, since there is
  nothing for the policy to say.
- **What it cannot see:** an event the principal accepts or adds themselves, an invitation that
  arrives, an update that moves an event without naming its place, and a write through a browser
  or computer use. The daily rituals' travel check reads the calendar itself and covers those.
  Whether the line is true is not something a guard can know; the travel check then looks for the
  blocks the line promises.

## Every channel and send windows (2026-10-13)

The principal asked that approval cover "all communications sent for me / on my behalf, regardless of
communications channel", and for a proper setting that suspends per-message approval for a while.

**Recognition.** A connector tool is a send when its name has a saying verb (send, reply, forward, comment,
post, publish, share, invite, respond, mention, schedule, submit, draft, notify, remind), or a writing verb
(create, add, edit, update, manage, set) whose object is something people read (comment, message, issue,
page, post, reply, review, draft, event, invite, reaction, canvas, envelope, request, ticket, thread, access,
permission). A tool whose first verb reads (get, list, search...) is never a send; agent-to-agent tools are
exempt. In the shell, each command a line runs is checked against the posting programs. The register scan
reads the message the command sends: its text words and every body it reads from a file (`--body-file`,
`gh pr ... -F`, `--input`, `@file`, `$(cat file)`), never its options, URLs or file names; a body file the
guard cannot read, or one named through a variable, is refused. The approval binds the command, its message
and the directory each posting command runs in after its own `cd`, so the same command approved and run
again from another directory still goes (2026-10-13). Global options before a subcommand (`bkt -c work pr
edit`, `gh -R team/app pr comment`) do not hide it, and `--help` or `-h` never counts as a post. A substituted
command's output is read only when it is `cat <file>` or a heredoc it reads (the code around the heredoc is not
message); any other substitution is refused, since the guard cannot know what it prints. JSON is read as the
strings it carries, so an escaped emoji is the emoji. A command that writes its body file and posts it in one
line is refused, since the guard would read the old contents (2026-10-14).

**Which calls reach the guard.** The hook's matcher sends every shell command, every connector tool
(`mcp__*`) and every file-edit tool (Write, Edit, MultiEdit, NotebookEdit, `apply_patch`) to the guard; the
guard decides. Until 2026-10-14 the matcher listed send-shaped names, so a connector tool recognized by what it
does (`createJiraIssue`) never reached the guard. File-edit tools may not write into the synthesis state, a
harness's transcripts or the approved commit lines, where approvals and send windows live. A project's memory
notes (`*.md` under `<project>/memory/` in Claude Code's projects folder) are the exception: they sit beside the
transcripts and hold none, so the file tools and the shell may write them (5.7.0).

**Calendar changes that reshape a series (2026-10-27).** A call that deletes an event or sets its time or
recurrence asks, in its approval text, for the occurrences from today through the next three, canceled and
moved ones included, each checked against accepted meetings, and for a read-back afterward: a series moved
to a new hour had brought back a meeting canceled at the old hour (synthesis-chief-of-staff rule 10).

**Documents others read (2026-10-27).** An edit to a Google Doc, Sheet or Slides deck, or to a Drive file's
contents, is published in the principal's name, so it waits for their code like a send (channel `docs`): an
agent had added a line to an agenda seven colleagues read with no code, though the principal had approved it
in chat. The tools are listed in `sends.DOCUMENT_EDITS`; creating a new document is not an edit others read.
The paragraph rule does not apply to a document's own line breaks, and a window never covers an edit, since
an edit carries no signature.

Limits: a program that sends through its own code (a script calling an HTTP library) is not recognized; the
binding rule covers it. Computer use and browser actions are covered below.

**Windows.** Only the principal opens one, for a planned number of sends (`--sends`, 1 to 50) within at most 12
hours: the last planned send closes it (2026-10-27: a window stayed open for hours after its planned sends, and
later sends went out under it). A window without a planned count covers nothing, and the guard refuses to ask
for a code to open a window the command would refuse. The command itself checks: whoever runs it, from any
terminal, `synthesis sends open` opens only on the principal's granted code for exactly that window, read from the
session's own transcript (`--session <id>` names it from a terminal of the principal's own), and otherwise refuses
with a code to show them (2026-10-13: a global option before `sends` slipped past the guard alone; 5.22.1: a
harness-free environment and a terminal on the command's input, which it once took for the principal's own
terminal, are both an agent's to fake). The guard also asks for the code before the command
runs, wherever its options sit, for every window request in a command line, each with its own code, and `--help`
never needs one. A script that imports the approval or window code to open a window or make a grant is refused. A window names its hours (at most 12), its channels (or `all`) and optionally a project; it ends by
itself, and `synthesis sends close` ends it at once with no code. Every session sees it at each prompt. Each
send it covers still passes the register scan and format rules, must carry a `send_window_signatures`
signature, and is written to the day's ledger with the sends approved by code; `synthesis sends log
[--date]` prints it for the daily plan's "On your behalf". Exact-text sends (the principal's own words) are
outside every window: list only the signatures of lanes the principal allows.

## Batches (2026-11-14)

A seat that drafts replies in the principal's own words sends them in batches of about twenty: the principal reads
every text and recipient in one sitting and types one code, and fifty replies no longer need fifty codes. Over the 26
days to 2026-11-14 the guard let through 442 sends, 358 on a code per call, as many as 16 of those within one hour.
A batch binds each exact text and recipient, so it is stronger than a window and may carry what a window must not.

**The file,** written by the seat that drafted it, in its own project, with 1 to 50 entries of four kinds, each
with nothing else:

```json
{"batch": "replies-2026-11-14", "project": "inbox-backlog", "entries": [
  {"tool": "mcp__slack__slack_send_message", "input": {"channel_id": "D0123", "message": "Thanks, Tuesday works."}},
  {"channel": "messenger", "to": "facebook.com/messages/e2ee/t/1000000001", "text": "Thanks, Tuesday works."},
  {"channel": "messages", "to": "+15550100", "text": "On my way."},
  {"channel": "messages", "members": ["+15550101", "+15550102"], "service": "SMS", "chat": "chat-9", "text": "Landed."}]}
```

A connector call is the tool's exact name and its exact input. A browser send on Messenger is the conversation's
address in its one canonical form (`facebook.com/messages/t/<id>`, `facebook.com/messages/e2ee/t/<id>`,
`messenger.com/t/<id>` or `messenger.com/e2ee/t/<id>`, with nothing before or after it) and the exact text. A send by
the local messages sender (`messages_send.py`) is the handle `--to` takes and the text, or for `--members` each
member's handle once, the chat's service and its chat id, as the sender's own approval names them, and the text; a
connector entry never names the sender's own tools (`imessage_send`, `messages_send`), which would carry its photo. One
entry goes to each conversation (an address, a handle, a chat, or for a connector call the recipient fields its input
names: `to`, `channel_id`, a thread and their kin). Anything else is refused with what is wrong, and so
are a control character other than a newline, or half of a surrogate pair, anywhere in the file (the review of 5.23.0:
an escape code hid words in a listing, and a carriage return printed one line over another), a connector entry's tool
name holding more than letters, digits and `_ . : -` (its third round: the listing prints a name as it is, and a line
separator in one drew a line of the agent's own), a key given twice, a number JSON does not have, a repeated entry and
a file over 1 MB.

**Asking.** `synthesis sends batch <file>` prints the digest (SHA-256 of the batch's canonical JSON: sorted keys, no
spaces, UTF-8), the count and each entry's channel and recipient; `--show` also prints every text in full and opens
nothing, so it needs no code. Every listing quotes each text as JSON and prints as it is a letter, mark, digit,
punctuation or symbol, a plain space and a line break; every other character (a control, format, separator, private
or unassigned one, every other space) is written as its code, and so is any character of those kinds that is one of
the listed fillers, blanks and variation selectors (U+1D159 and U+16FE4 among them, the third round) or whose name says
it is a blank, filler, joiner, subjoiner, conjoiner or selector (U+13441, U+2D7F, U+1107F, U+11A47 and U+1BC9D among
them, review round 4, #8). The
file's path, the batch's name and its project are shown the same way (the review of 5.24.0), and a connector call's
input prints one field to a line. The command opens a batch only on the principal's code for exactly that
digest, typed in the session that runs it, from any terminal: an agent could fake a terminal of the principal's own, so
there is no such shortcut. It spends the code itself, so a file changed after the hold has another digest and gets
nothing. The guard holds the command with the code and the whole listing, texts included, so the principal reads in the
hold exactly what the code grants; a packet built from the same file is a convenience, never the record. The guard
reads every `synthesis sends` in a command line with the CLI's own parser; one it cannot read as the CLI would (a word
the shell changes first, or one the CLI refuses) waits for a code of its own, and a file goes only with `sends batch`.
At the grant the entries are copied into the synthesis state with the digest, the project, the grant's time, the
session that ran the command and the code the principal typed in it, so editing the file afterwards changes nothing.

**What an entry covers.** Exactly that entry, compared after each string's line endings are written as `\n`, and
nothing else is overlooked: a trailing space, a lookalike letter, another case or one more character is another
send. A connector entry binds the whole call, every field of its input, compared as JSON (`true` is not `1`); a call
whose input names anything its connector fetches, reads or carries when it runs (a key naming a url, a uri, a link, a
path, a file, an attachment, an upload, a download, media, an image, a photo, a picture, video, audio, a voice clip, a
blob, a sticker, a thumbnail or an avatar) is never covered, since a batch binds words, not what a url, a path or a
file holds when the call runs. A messages entry binds what the sender's own approval binds; a photo beside it
is outside every batch. A Messenger entry is sent in one step, a single `browser_batch` (the review's third round: a
check read in one call and a Return pressed in another left room between them for a page script that rewrote what the
check reported, a typist the guard could not see, and another session):

1. **A navigate** on a tab it names, which this session made with the browser's own `tabs_create` (the guard reads the
   new tab's id from that call's result in this session's record) and which this session's newest list of tabs already
   shows on the entry's conversation, to that conversation's https address with no query or fragment (`https://www.<its
   address>/`). A page gets a handle to another window only by opening it, so no page holds one to a tab the browser tool
   made (the review's third round: a script on a page the guard read as the agent's own `data:` page, after that page
   had moved itself to facebook.com, opened the chat and patched it through every load; the coordinator's ruling of
   2026-11-15). Since the tab was made, any action on it in another session's record, or one there that names no tab,
   and any page script but the shipped ones run on it in this session's record or its sub-agents' (a window a script
   opens keeps a handle to the tab) void it; a tab the guard did not see this session make is refused with that word:
   open a fresh tab with `tabs_create` and navigate it to the conversation. The navigate loads the page again, so
   whatever an earlier script did to it goes with it; since the tab already showed that conversation, no session's guard
   reads another address for it while the step runs.
2. **The words typed** on that tab, and nothing else: typing with no line break, shift+Return for each line break,
   select-all with Delete or Backspace to clear, and waits. No click and no other key: Return sends the box as it stands,
   and the composer's neighbours are send controls themselves (`Send a like` sends a thumbs-up; the coordinator's live
   read of 2026-11-14).
3. **Last, the send script**, exactly as `synthesis sends script --entry <digest prefix>:<its number>` prints it for
   the entry, run with the JavaScript tool on that tab. It holds the conversation and the SHA-256 of the entry's words,
   and in one synchronous run, so nothing can act between the read and the send, it:
   - finds **the box**: the one contenteditable textbox whose `aria-label` starts with `Write to` or names a message,
     whose `aria-placeholder` is `Aa`, or that is a Lexical editor (`data-lexical-editor`); two such boxes, or none,
     send nothing;
   - reads **its words**, its `innerText` with the one line break Lexical ends it with left off (an empty box is a
     single line break; a shift+Enter break is one line break inside), and compares their SHA-256 with the entry's,
     each line ending written as `\n`: past that one break the comparison is exact;
   - reads **the composer**, the box's nearest ancestor that also holds a control whose `aria-label` names sending
     (`Press enter to send`, `Send`) or a file or attachment (`Attach a file`), and outside the box, in it or in any other
     child of its parent (in plain mode the composer is its parent's only child, live 2026-11-15): **what is staged**
     (images, video, audio, canvases, objects, frames, pictures, an svg outside a control such as a file's icon, and a
     control labelled to remove, close, cancel, delete or discard), and **its mode** (text that opens with `Replying
     to`, `Edit`, `Editing`, `Cancel reply` or `Cancel edit`, a control labelled for a reply or an edit, a quotation, and
     a heading, `role="heading"` or `h1` to `h6`, outside the composer whatever it reads; inside it a heading counts
     only by those words, since Messenger's composer always holds a visually hidden `Compose` heading), with the images
     inside the box, which `innerText` leaves out. Reply mode was read live on 2026-11-15; edit mode and a staged file
     have not been;
   - checks that **the page** is the entry's conversation, by its site and path;
   - and only when all of that holds, clicks the one control in the composer labelled exactly `Press enter to send` or
     `Send`. It returns one JSON report: the address, whether the conversation and the words matched, the counts, the
     controls it found, whether it sent, and the box's text right after (empty when Messenger took the words at once).

`synthesis sends composer-check` prints the same reading as a script that sends nothing, for a look at the page. On a
Messenger site's tab (a page of facebook.com or messenger.com or a host under them, which share the chat's origin, or
of a host the guard counts as Messenger's, where the browser lands on a chat: m.me, fb.com, fb.me and Business Suite's
inbox), by this call's own navigates, this session's newest list of tabs, or another active session's list when that
is the newest of all that name the tab, no page script runs but the shipped read-only ones (the composer check, and the
extractors `messenger_messages.py` and `chat_page.py` print) and the send script as the last step of its send step; any
other, whichever browser tool runs it (Claude in Chrome's, the built-in pane's, and a driven browser's
`browser_evaluate` and `browser_run_code_unsafe`), and a navigate to a `javascript:` address too, read as a URL parser
reads it, from any of them, alone or in a batch, is refused at its own call, since it can change what the send reads or
what a click sends, then or later. A page no list of tabs names (a tab not listed yet, one a navigate sent where no host
is named, or a page a driven browser's record does not show) takes none either, since it may be a Messenger site's (the
third round's opener ran on such a tab), and nor does a tab a step earlier in the same call may have moved (a navigate
other than to a local app, a click, a key, typed words with a line break; review round 4, #2: a short link or a followed
link landed on a chat), until a list of tabs shows where it landed. Each browser keeps its own tab ids and lists. Over
the 60 days to 2026-11-15, 142 scripts ran in a batch after such a step, 58 of them on a messaging site's page, which is
refused anyway; the other 84 now run in a call of their own, with no code.
The guard spends the entry when it lets the step through, so a step whose script then finds the page wrong sends
nothing, and that entry needs a new code: the principal's code per call (the Return after the words) or a new batch. A
conversation is a page's site and path, its trailing slash and query left off: the
four forms above are four distinct conversations (every chat facebook.com lists links to `/messages/e2ee/t/<id>/`), and
a send on one never spends an entry for another. Each entry sends once, decided under the send guard's lock; only within
12 hours of the principal typing the batch's code (what `synthesis sends status` names as its end); and only from the
session that ran the granted command, as the guard is told it (a hook's payload). The messages sender names no session
(its third round: a link or runpy kept a `--session` naming another): for each run of the sender a command the guard
lets through makes, its program resolved as the write rules resolve one (an interpreter's file or module, a script run
by its path, each through its links), the guard files a one-use ticket for the session its hook names, bound to that
run (the sender's real file, its arguments and its real folder); the sender hands its guard call its own run, which
takes only a ticket of the same run filed in the last minute (review round 4, #6, #11 and #12: a `cat` or a `grep` of
the sender's file filed one, any run took it, and a line of two sends had one). A command that only names the file
files none; a run the guard did not see as the sender's (a copy under another name, runpy) finds none and waits for the
code per call, and so do identical runs of two sessions in one folder within the same minute. That session's own record must show, each time an
entry is spent, the principal typing the batch's
code after the guard first filed that code for that digest. The guard records each request it files for a batch, its
digest and code, in a ledger only it writes (`sends._requests_file`); no line of the session's record stands in for
it, since the agent writes those (the review's third round: its own sentence naming a digest and a code tied them, and
repeating both after the principal typed the code held a granted batch). A code typed for anything else backs
nothing, so batch state alone is never a grant. Each send is
written to an append-only spends ledger and to the day's ledger as `batch:<digest prefix>:<index>`, so `synthesis
sends log` shows it for "On your behalf". A Messenger send step's line is read with its send script's own report from
the session's record: `synthesis sends log` names one whose script declined as not sent, and one with no report yet as
unconfirmed (review round 4's notes: the line named a message the script then declined to send). Another session's
call voids a send step only when it went to the same browser, names the step's tab or none, can change the page (not
a screenshot, a scroll, a wait or a hover) and no hook refused it, and a tab is this session's only by the extension's
own `Created new tab. Tab ID: N` (the words every one of 89 such results in 60 days of records used, each naming in
`Executed on tabId` the tab it made).

**Every other check runs first.** The register scan, the format rules, an address that can change
(`temporary_addresses`) and a time in the words (`fresh_calendar`) hold an entry as they hold any message, a Messenger
entry's words included: an entry that names a clock time still needs a fresh calendar read when it goes, or the
hold's own code, which spends the entry with the send. For a Messenger entry that code binds the exact send step: its
conversation's address, and its script, which holds the words' digest. A meeting placed on today is never covered
(`same_day_meetings`). No shell post is a batch's entry: the messages sender asks the guard itself.

**The window and the batch never combine.** The batch is looked at after every check and before the window; a send
it covers is not counted against a window's planned sends, and a call is covered whole or not at all.

**What tampering with the state does.** The file tools and the shell writes the guard reads cannot write the state,
and a script that names a batch's opening or spending code is refused as the window's is; 5.22.1 closes the
interpreter writes the review of 5.23.0 found, and the guard reads `sends._batch_file`, `sends._spends_file`,
`sends._requests_file` and `sends._window_file` as leading into the state, so a program that names one is judged as
one that names the state folder. A path a program builds at run time is still unseen (the review of 5.24.0, #6, a sandbox's to close, not this
batch's). Behind that: state that cannot be read, whose entries no longer hash to
its digest and its file's name, that marks entries it does not have as spent, or whose life runs past 12 hours from
its grant is no batch, and its sends fall back to the code per call; the same batch granted again is then refused
rather than guessing which entries went. A spent mark taken out of the state reopens nothing, since the spends ledger
keeps every spend. A grant time moved later keeps nothing open past 12 hours from the principal's own prompt, which each
spend reads in the session's record, and another session's name put in the state spends nothing, since that session's
record holds no code for it. These fields are not signed: what holds the line is that only the guard and the CLI write
the state, and that the principal's typed code is read from the harness's record at every spend. A batch granted again
with readable state keeps the spent marks of its earlier grant.

**Ending.** `synthesis sends close` ends the window and every open batch at once, with no code, and `synthesis sends
status` shows each open batch with its entries left and when it ends.

## Computer use and the browser (2026-10-22)

On 2026-10-22 a photo with a caption went out on WhatsApp through `computer_batch`, a click on the app's Send
button, and no code was asked for: the guard recognized sends by tool name, and computer use has none. A scan of
45 days of transcripts then found 11 browser sends (LinkedIn messages, posts on X and LinkedIn, a support chat)
made through Claude in Chrome's `browser_batch`, none guarded either. Both now wait for the principal's code.

**Which tools.** The computer-use server's action tools under any server id (`computer_batch`, `app_batch`,
`app_click`, `app_key`, `app_type`, `app_menu`, `teach_step`, `teach_batch` and the single-action tools), a linked
device's `computer_*` tools, and a browser server's `computer`, `browser_batch`, `form_input`, `javascript_tool` and,
since 5.23.1, `navigate` (Claude in Chrome, the built-in browser). Screenshots, zooms, scrolls, waits, menu listings
and every read pass at once. Since 5.23.0 a browser tool
from any other server whose name says it drives a browser (Playwright, Chrome DevTools, Puppeteer) is read too, as the
steps it performs (typing, a key, a click, a form, a page script), on the page that server's own results last showed;
a click is read by the control the page's snapshot names, not only by the words the agent gives it; and a step that
may send on a page those results do not show waits for the code.

**Messaging apps.** Built in: WhatsApp (`net.whatsapp.WhatsApp`, `desktop.WhatsApp`), Messages
(`com.apple.MobileSMS`), Slack (`com.tinyspeck.slackmacgap`), Signal (`org.whispersystems.signal-desktop`),
Telegram (`ru.keepcoder.Telegram`, `org.telegram.desktop`), Teams (`com.microsoft.teams2`, `com.microsoft.teams`),
Discord (`com.hnc.Discord`), Zoom (`us.zoom.xos`), Mail (`com.apple.mail`) and Outlook (`com.microsoft.Outlook`);
`messaging_apps` adds more. In a messaging app these wait for the code:

- a click with no `action_summary` (the tools require one that states the effect; without it the guard cannot
  tell Send from navigation);
- Return or Enter, unless held with the app's line-break modifier alone: shift in chat apps, option in Messages.
  In Mail and Outlook, Return writes a line, and cmd or ctrl with Return, or Mail's cmd+shift+d, sends;
- typed text holding a line break, where a bare Return sends;
- a menu item that starts with Send (Mail's Message > Send).

**Messaging sites in the browser** (5.1.9). A browser page on a messaging site counts as that app, under the same
rules. A site is its host and every host under it, as the browser lands on them: since 5.21.0, after a batch that
opened `linkedin.com/...`, `uk.linkedin.com` or `m.me/...` pressed Return with no code while the browser landed on
`www.linkedin.com` or `www.messenger.com`. Each site's channel is the name a register rule's `channels` uses.

- **Return sends and shift with Return writes a line:** Google Chat (`chat.google.com`, and `/chat` on
  `mail.google.com`; `google chat`), Gmail (every other page of `mail.google.com`, and `gmail.com` and `/gmail` on
  `google.com`, the hosts a person types; `email` and `google chat`, since 5.21.0: Chat runs in pop-ups on Gmail's own
  pages, and a page cannot show which box has the focus, so Return and a typed line break wait there as the send
  shortcut, cmd or ctrl with Return, did already), Google Voice's texts (`voice.google.com`; `google voice`, since
  5.21.1), Slack (`slack.com`; `slack`), WhatsApp (`whatsapp.com`, `wa.me`; `whatsapp`),
  Teams (`teams.microsoft.com`, `teams.live.com`, and `teams.cloud.microsoft`, where its web app moved in 2026;
  `teams`), Discord (`discord.com`, `discordapp.com`, `discord.gg`; `discord`), Telegram (`telegram.org`, `t.me`;
  `telegram`), Messenger (`messenger.com`, `m.me`, and `/messages` on `facebook.com` and `fb.com`; `messenger`),
  Instagram's messages (`/direct` on `instagram.com`, and `ig.me`; `instagram`), LinkedIn's (`/messaging` on
  `linkedin.com`; `linkedin`), X's (`chat.x.com`, and `/messages` and `/i/chat` on `x.com` and `twitter.com`; `x`),
  and Business Suite's inbox (`/latest/inbox` on `business.facebook.com`; `facebook`, `messenger` and `instagram`).
- **Every other page of facebook.com** (with `fb.com` and `fb.me`; `facebook` and `messenger`), **instagram.com**
  (with `instagr.am`; `instagram`), **linkedin.com** (`linkedin`) **and x.com** (with `twitter.com`; `x`) counts too,
  since 5.21.0: Messenger runs in chat pop-ups on every page of facebook.com, LinkedIn's messages open in an overlay
  on every page and X's can open in a drawer beside its other pages, and Return in a comment box posts in the
  principal's name. A page cannot show which box has the focus, so on any of these pages Return waits for a code, a
  search box's included, and so does a click with no summary. A page of facebook.com outside `/messages` is both
  `facebook` and `messenger`, since a pop-up may hold the focus: a rule that names either holds there.
- **Email:** Outlook on the web (`outlook.office.com`, `outlook.office365.com`, `outlook.live.com`, and
  `outlook.cloud.microsoft`, its new address; since 5.21.1 also `outlook.com`, `hotmail.com` and `/mail` on `live.com`,
  the hosts a person types), under the email rules: Return writes a line, and cmd or ctrl with Return sends.

The page is the tab a step names, else the one the last browser call ran on, read from the tab list Claude in Chrome
prints after every call, or the page a `navigate` step earlier in the same batch opened. Each browser keeps its own tab
ids, so a call is read by its own browser's newest list: since 5.23.1 the built-in pane's lists (its tab ids are
`tab-N`), its own `tabs_context` (each tab's origin, the active one in front) and its navigate's result (`navigated to`
or `opened` and the address) are read too. A `navigate` that names no
host (`back`, `forward`, a path, a script) leaves the page unknown, unless the tab was on a messaging site: the page it
opens may be that site's still, so it is judged as that site's. A page whose address the guard cannot read (a browser
that prints no tab list) is judged by the summary rule alone. On 2026-10-22 a session found that Return in a Google
Chat compose box went out with no code, because a browser page had counted as no app.

**A click whose summary says it publishes** (5.21.0 on messaging sites; 5.21.1 in every app and on every page). On
2026-11-13 a public review went out with no code on a site that is no messaging site, through two clicks on a control
labeled Submit rating, each summarized as the tools ask, effect first: "Submits the five-star public review of" a
person. A click waits for a code when its summary

- starts with a verb that posts, in any tense: submits, reposts, retweets, quotes or rates ("Submits the rating"); or
- names Send, Post, Comment, Reply, Repost, Share, Publish, Submit, Tweet or Done after a click verb in any form
  (click, clicks, clicked, clicking; press, tap, hit, choose, select), with or without `on`, `the` and up to three
  words before the label, in quotes or not ("Clicks the blue Post button", "Clicking Submit rating").

One label can both open a box and post what is in it, so the label alone holds. It passes when what follows the label says the click only opens or closes something, and nothing
there says to post, publish, send or submit: the label followed by box, field, input, area, composer or editor
("Clicks the comment box"), or opens, expands, focuses, shows, reveals or closes, or to open, expand, focus, show,
reveal or close, with a box, field, menu, dialog, options, panel, sheet, form, window, list, modal, pop-up or drawer
within three words ("Clicks Comment to open the comment box", "Clicks Done to close the dialog"). It passes too when
the summary signs in, logs in, searches, queries, filters or looks something up and names no message, reply, comment,
review, rating, post, tweet, feedback or answer ("Clicks the Submit button to sign in", "Clicks Submit to run the
search"), and on the principal's own app on a local host (`localhost`, `127.0.0.1`, `[::1]`, a `.localhost` or
`.test` name), where every step of the call acts. A bare "Clicks the Share button" still waits: say what it opens.

Measured with the rule's own code over the 30 days to 2026-11-14: of 1,506 browser clicks and 37 computer-use clicks,
it holds 12 that no rule held before, in 3 transcripts, among them the incident's two clicks on Submit rating and its
four on the stars. 5.21.1 as first written held none of the twelve: its note that no click named one of these controls
counted only summaries of the click-verb form, which the incident's were not.

**Keys and page scripts that submit, on any page** (5.21.1). On a page that is no messaging site, a call that types
words and then presses Return or Enter (without shift), Space or Return after Tab, or types a line break waits for a
code when its summaries name a message, comment, review, post, reply or tweet: most forms submit on Return, and those
are the ones that post. A call that names none passes, as before 5.21.1 (the principal's ruling of 2026-11-14, "Skip
typed text that names no post"), and so does every call on a local app. A page script (`javascript_tool`, alone or as a batch step) reaches the guard: on a messaging
site's page it is refused unless it is one the plugin ships to read (below, since 5.23.1; on a Messenger site's tab a batch's send script runs too, in its send step,
"Batches"); elsewhere one that submits
a form, sends a key or an event, writes by fetch (a POST, PUT, PATCH or DELETE, or `sendBeacon`), or clicks with a word
that publishes in it (submit, post, send, publish, reply, comment, share, review, rating, tweet, done) waits, unless it
names a search, a sign-in, a password or a query as a whole word; on a local app none waits.
A form fill alone (`form_input`) is typed text, scanned as a batch's is. Measured the same way: the key rule holds 16
calls in 3 transcripts and passes 30 (23 that name no post, 6 that sign in or search, 1 on a local app; held as
unsure, the 23 would have been held too); the script rule holds 5 of 118 scripts on messaging sites, in 2
transcripts, and 24 of 459 elsewhere, in 5.

**On a messaging site's page only the plugin's own read-only scripts run** (5.23.1). Review round 4 of the batch
approval found a script that clicks Send by a name it builds as it runs (`el['cli' + 'ck']()`) passing on Slack,
WhatsApp, LinkedIn, Gmail and X: the rule above read a script's text for a click, a submit or a key, and no reading of
its text shows such a call. On a messaging site's page (every site and page the list above names), and on a page a
driven browser's record does not show, every page script is now refused but the extractors the plugin ships
(`messenger_messages.py extractor` and `chat_page.py extractor`, exactly as their commands print them). Refused, not
held for a code: the 60 days of Claude Code and Codex records to 2026-11-15 held 183 page scripts on those pages, 5 of
them a later release's own composer check and 178 others, all in 4 sessions (96 on LinkedIn, 56 on facebook.com, 12 on
Slack, 7 on X, 6 on Google Chat, 1 on Gmail), and the rule above held 5 of the 178, so a code for each would have asked
the principal 173 times about scripts no one can read for what they do. The browser's own read tools (`get_page_text`,
`read_page`, `find`) read a page with no code, and a click goes through the `computer` tool with a summary that says
what it does. No script in those records called a member named as it ran, so none sent that way. In the runtime the
hook runs from, an extractor counts only when its skill's scripts are among those the installer copies there.

**A navigate is read as a URL parser reads it** (5.23.1). The `navigate` tool called alone was never judged, and a
`navigate` step was read as written, while a browser strips control characters and spaces at an address's ends and
drops every tab and line break in it, so `java\tscript:` and `\x01javascript:` are `javascript:` addresses. Every
navigate from any browser tool (Claude in Chrome's and the built-in pane's, alone or in a batch, and a driven browser's)
is now read that way, and one to a `javascript:` address is the page script it runs, percent-decoded as the browser
decodes it, on the page the tab is on: refused on a messaging site's page, judged by the rule above elsewhere. What
its code leaves the page on is not known. No navigate to a `javascript:` address appears in the 60 days of records,
read raw or as a parser reads it, among 704 navigates.

**A register hit where the guard is unsure the words are a message** (5.21.1). On a page that is no messaging site,
and in an app that is none, a call that sends with words that break a register rule is not refused outright: a review
is a message and a search is not, and the guard cannot tell them apart. The send's own hold names the rule, and its
code waives it for that exact call; a send window never covers it. On a messaging site or in a messaging app the hit
is refused outright, as before.

**What the records keep** (5.21.1). The text a call types, and the values it fills in, never go into a stored request
or the send log, which keep only how many characters were typed: a test form's password, typed by an agent, had
landed there in plain text. The hold asks for a screenshot of the compose area instead. An action's own summary is
kept as the agent wrote it, so a summary does not quote what it types.

**Words typed on these pages** (5.21.0). On the pages of facebook.com, instagram.com, linkedin.com and x.com outside
their messages a box may be a search, so a call that only types there (no click, no key, nothing it says sends) and
breaks a register or format rule is not refused outright: it waits for the principal's code, and the hold names the
rule, so they decide with the words in front of them. One code releases one identical call. A call that sends, or
does anything besides typing, is refused outright, as on a page of messages, where typing writes a message, and as
on every page of Gmail; an address that can change keeps its own code. Holding these words unscanned until a call
sends instead would let a comment typed in one call and posted by Return in the next reach people with no scan at all.
Since 5.21.1 the words a code released are kept, with the rules they broke, for 15 minutes: a send from the same page
in that time shows them and the rules in its hold, and its approval binds them (the second review found that a Return
after them waited on a code that named neither). Gmail stays outside this release on purpose: a search there for words
a rule names is refused outright, as email's rules were before 5.21.0, since agents send email through the connectors,
which the guard reads, and the browser path to Gmail was made only stricter (a ruling of 2026-11-14).

In any app or browser page, an action whose summary starts with a sending verb (sends, replies, forwards, posts,
publishes, shares, invites, responds, comments, mentions, announces, notifies, reminds, schedules, delivers,
emails, texts), clicks or presses (on) Send, or does something "to send" waits too. On the 45 days of summaries this
held all 13 real sends and nothing else. Words typed in a messaging app or site, or in a call that sends, pass
the register scan as they are typed (on the four sites' other pages, a hit in a call that only types waits for a
code, as above); typed text cannot carry a named link, so the signature-link rule does not apply to it.

**Which app.** An `app_*` call names its app. `computer_batch` and the teach tools act on whatever is in front, so
the guard counts them as acting in every messaging app the session asked to control: it records the apps each
`request_access` or `request_teach_access` call names, per session, in the synthesis state. A session whose grants
it never saw (asked for before 5.1.5, or with no session id) is treated as controlling every messaging app until
it calls `request_access` again.

**Binding.** The approval binds the exact call, every action and summary in it, and any words it types. Text
typed in an earlier call was scanned then but is not bound, so type the words and send in one call where you can,
and show the principal a screenshot of the compose area with the code. A Return or click that does not send (a
file picker, a search field) is still held in a messaging app: click the control it confirms instead, with a
summary that says what it does. A send window covers a computer-use send in its channel (`whatsapp`, `slack`,
`email`, `browser`...) only when the call itself types the signed words.

**Limits.** The click rule reads the summary the agent wrote: a summary that hides a send ("Clicks the green
button") passes outside the Return and line-break rules, and so does a page script that hides one (one that calls a
site's own send function, or clicks with no word that publishes in it, off a messaging site). Pasted text (cmd+v) is
not scanned, and Playwright's browser tools reach no send rule (over the same 30 days they were used 31 times, none to
click, type or press a key). These are why the binding rule still governs every send.

## Keys, clicks and other apps from the shell (5.23.0)

Round 3 of the batch approval's review (2026-11-15) typed words into a Messenger box with the browser tool, which
sends nothing, then pressed Return through `osascript` (System Events `key code 36`), and the message went out with
no code: the shell guard read no key events. A shell command now waits for the principal's code for that exact
command, as a send does, when it

- presses keys or clicks in whatever app is in front: `osascript` or JavaScript for Automation with keystroke, key
  code or key down or up, or with System Events' UI verbs (click, perform, set value, focus or selection, select,
  confirm) where System Events is named; SystemUIServer or BetterTouchTool; `cliclick` and `xdotool` with an action,
  `ydotool`, `wtype`, `dotool`, `sendkeys`, `skhd -k` or `-t`, `shortcuts run`, `automator`; Hammerspoon's `hs` with Lua
  that presses, clicks, runs a task or loads code (`hs -c 'hs.reload()'` passes, and so does the HubSpot CLI, also
  `hs`); an input library a program uses (pyautogui, pynput, Quartz's CGEvent, AXUIElement, NSAppleScript,
  ScriptingBridge, appscript, robotjs, `@jxa/run`, the `osascript` and `applescript` modules);
- types into another terminal: `tmux send-keys`, `screen -X stuff`, `kitty @ send-text`, `wezterm cli send-text`;
- opens a terminal or an automation link: `open -a Terminal` (or iTerm, Warp, kitty, Alacritty, WezTerm, Ghostty), a
  `.command` or `.tool` file, a `shortcuts://`, `kmtrigger://`, `alfred://`, `hammerspoon://` or `raycast://` link;
- sends through a scriptable app: a `send` in Messages, Mail or Outlook, read across all of a script's lines;
- runs code in another app: Terminal's `do script`, iTerm's `write text` or `command`, a browser's `execute ...
  javascript` or `do JavaScript`, Keyboard Maestro, Alfred's `run trigger`, Hammerspoon, Shortcuts, Automator, an
  automation link or a `.command` file opened by a script;
- or runs a script the guard cannot read: a compiled script, one on an input another program writes, words the shell
  fills in (`-e "$S"`, `$(cat …)`, xargs's input), `do shell script`, `run script` or a script library, a raw `«event»`
  code, `use framework`, a bridge to the system's classes (`$.system`, `NSTask`, `NSAppleEventDescriptor`, an
  `ObjC.import` beyond Foundation, AppKit, Cocoa and stdlib), `eval`, an app or member a JavaScript script names only
  when it runs, or a string, comment or pattern it never closes.

The command is read wherever it runs: its `-e` lines, the file it names (`$HOME` and `~` filled in), a heredoc or pipe,
`bash -c`, `watch`, `script`, `launchctl asuser`, `arch`, a shell file, a `make` target's recipe, an npm, pnpm, yarn or
bun package script, every reading of the variables the line gives (`O=osascript; $O -e …`), and the commands a program
starts, from its calls, its command spans and its strings (an argument list, a string handed to a shell, an AppleScript
kept in a variable of a program that runs osascript), in Python with the modules of its own it imports and a module run
with `-m`, and in Perl, Ruby, Tcl, expect, Node, Deno, PHP and Swift. A file the same line writes is read as the line's
own heredocs. A command a program builds while it runs, or code it builds and runs, is not read: a sandbox around the
shell, not a reading of text, closes that. A program that starts nothing is only read, so an analysis, a comment or a help text that
names osascript or a library passes; a line the parser cannot read that names one of these programs waits. Words a
command types or sends pass the register scan first. System Events alone, asked which apps run, passes, and so do
Terminal and iTerm asked a window's name, Finder's select and a spreadsheet's set value. Over the 276,500 shell
commands recorded in the 60 days before 5.23.0, this reading holds 39 the old guard passed, none a message sent or a
key pressed: osascript whose script comes from another program's output or from words the shell fills in, and programs
whose strings run such a script. It takes 0.17 ms on a typical command and 307 ms at worst.

A browser tool from any other server is read by what it does (5.23.0, the same review), on the page that server's own
results show (Playwright's `- Page URL:` and tab list, Chrome DevTools' selected page, Puppeteer's `Navigated to`) or its
own newest navigate, in a Claude Code record or a Codex rollout. A click is read by the control the current page's
newest snapshot names for its `target` or `ref` together with the agent's words; on a messaging site a control the
snapshot does not name waits. `browser_type` with `submit`, `browser_press_key` Enter or a typed line break, a form or
dropped text holding one, an accepted dialog, and an evaluate or a script that acts are read as Claude in Chrome's are.
`browser_run_code_unsafe` waits when it loads its code from a file or its code starts a command that acts. A tool the
guard does not know, on a server that drives a browser, is a step that may send, and so is any step where nothing shows
the page. The code binds the call itself, so it is not spent on another control or box.

## Calibration

The pattern set must PASS the principal's real sent messages and BLOCK the incident
drafts. Re-run calibration whenever patterns change; a guard that blocks the principal's
own voice is miscalibrated, not strict.

- A rule against a miscased brand is case-sensitive (`"case_sensitive": true`): on
  2026-08-03 a retired-branding pattern compiled to ignore case blocked every correctly
  signed send.
- The positive controls are tests, run in CI: a real signed agent message, in Slack
  wire form, reaches the approval step; a known-bad message (an apology for delay,
  self-abandonment) is blocked by name
  (`tests/test_send_guard.py::test_positive_controls_a_real_signed_message_passes_and_a_known_bad_one_blocks`,
  `tests/test_signed_message.py`). A principal's private config adds its own canonical
  messages as tests in the private layer, so a pattern change that blocks real traffic
  fails there before it reaches a session.

## Wiring and health

The plugin's hooks file registers the PreToolUse hook for every harness, matching shell
tools and every MCP tool whose name holds send, draft, reply, forward or schedule (plus
the calendar and sharing verbs the account guard needs), and `synthesis doctor` proves
each harness actually calls it. A tool added through `send_tools` must also match that
matcher, or it never reaches the guard. There is no per-client patterns file and no
enrollment step.

## From the 1.x patterns file

| 1.x `patterns.json` | v5 |
|---|---|
| `gated_tool_patterns` (regexes) | built-in globs plus `send_tools` |
| `exempt_tool_patterns` | not needed: session-to-session tools are never guarded |
| `block_patterns` `{name, regex}` | `forbidden_phrases` `{name, pattern, why, case_sensitive}` |
| `warn_patterns` | dropped: a warning the model never sees changes nothing |
| `ledger_max_age_minutes` | approvals expire after 15 minutes |
| `text_field_candidates` | every string in the call is scanned |
| `doctor_clean_controls` | tests (above) |
| `currency_claim_patterns`, `currency_claim_max_age_minutes` | binding rule 2: re-read within 30 minutes |
| `email_policy`, `paragraph_policy` | `message_format` |
| `signature_link_enforcement` | `signature`, plus the HTML email rule for every email |
| `peer_send_resolution` | board messages (`synthesis msg`) resolve their target |
