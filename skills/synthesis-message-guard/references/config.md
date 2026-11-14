# Send-guard configuration

The guard reads `~/.synthesis/v5/config.json`, the principal's private file. An
unreadable or malformed file blocks every send (R3.5); a missing file means the defaults
below. The public starting point is
[config.example.json](../config.example.json), which the tests load in CI, where there is
no `~/.synthesis`.

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
for a code to open a window the command would refuse. The command itself checks: run by an agent (a harness's
environment, or no terminal), `synthesis sends open` opens only on the principal's granted code for exactly
that window, read from the session's own transcript, and otherwise refuses with a code to show them; the guard
also asks for the code before the command runs, wherever its options sit, and `--help` never needs one. Run in
their own terminal, it opens directly (2026-10-13: a global option before `sends` slipped past the guard alone). A script that imports the approval or window code is
refused. A window names its hours (at most 12), its channels (or `all`) and optionally a project; it ends by
itself, and `synthesis sends close` ends it at once with no code. Every session sees it at each prompt. Each
send it covers still passes the register scan and format rules, must carry a `send_window_signatures`
signature, and is written to the day's ledger with the sends approved by code; `synthesis sends log
[--date]` prints it for the daily plan's "On your behalf". Exact-text sends (the principal's own words) are
outside every window: list only the signatures of lanes the principal allows.

## Computer use and the browser (2026-10-22)

On 2026-10-22 a photo with a caption went out on WhatsApp through `computer_batch`, a click on the app's Send
button, and no code was asked for: the guard recognized sends by tool name, and computer use has none. A scan of
45 days of transcripts then found 11 browser sends (LinkedIn messages, posts on X and LinkedIn, a support chat)
made through Claude in Chrome's `browser_batch`, none guarded either. Both now wait for the principal's code.

**Which tools.** The computer-use server's action tools under any server id (`computer_batch`, `app_batch`,
`app_click`, `app_key`, `app_type`, `app_menu`, `teach_step`, `teach_batch` and the single-action tools), a linked
device's `computer_*` tools, and a browser server's `computer` and `browser_batch` (Claude in Chrome, the built-in
browser). Screenshots, zooms, scrolls, waits, menu listings and every read pass at once.

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
  `mail.google.com`; `google chat`), Gmail (every other page of `mail.google.com`; `email` and `google chat`, since
  5.21.0: Chat runs in pop-ups on Gmail's own pages, and a page cannot show which box has the focus, so Return and a
  typed line break wait there as the send shortcut, cmd or ctrl with Return, did already), Slack (`slack.com`; `slack`), WhatsApp (`whatsapp.com`, `wa.me`; `whatsapp`),
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
  `outlook.cloud.microsoft`, its new address), under the email rules: Return writes a line, and cmd or ctrl with Return
  sends.

The page is the tab a step names, else the one the last browser call ran on, read from the tab list Claude in Chrome
prints after every call, or the page a `navigate` step earlier in the same batch opened. A `navigate` that names no
host (`back`, `forward`, a path, a script) leaves the page unknown, unless the tab was on a messaging site: the page it
opens may be that site's still, so it is judged as that site's. A page whose address the guard cannot read (a browser
that prints no tab list) is judged by the summary rule alone. On 2026-10-22 a session found that Return in a Google
Chat compose box went out with no code, because a browser page had counted as no app.

**A click on the control that publishes** (5.21.0). On a messaging site's page, a click waits for a code when its
summary names Send, Post, Comment, Reply, Repost, Share, Publish or Submit right after a click verb (clicks, presses,
taps, hits, chooses or selects, with or without `on` and `the`, the label in quotes or not): "Clicks the Post button",
"Taps on Share", "Clicks Comment". These sites label few controls Send: their Post, Comment and Reply post in the
principal's name, and one label can both open a box and post what is in it, so the label alone holds. It passes when
the summary says the click only opens something: the label followed by box, field, input, area, composer or editor
("Clicks the comment box"), or the words opens, opening, expands, focuses, shows, reveals or starts, or to open,
expand, focus, show, reveal or start ("Clicks Comment to open the comment box"). Best, write what the click does
("Opens the comment box"). Over the 30 days before 5.21.0, 1,506 recorded browser clicks and 37 computer-use clicks
held no summary of that form on any site, so the hold costs nothing measured.

**Words typed on these pages** (5.21.0). On the pages of facebook.com, instagram.com, linkedin.com and x.com outside
their messages a box may be a search, so a call that only types there (no click, no key, nothing it says sends) and
breaks a register or format rule is not refused outright: it waits for the principal's code, and the hold names the
rule, so they decide with the words in front of them. One code releases one identical call. A call that sends, or
does anything besides typing, is refused outright, as on a page of messages, where typing writes a message, and as
on every page of Gmail; an address that can change keeps its own code. Holding these words unscanned until a call
sends instead would let a comment typed in one call and posted by Return in the next reach people with no scan at all.

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
button") passes outside the Return and line-break rules, and so does a page script (`javascript_tool`) that
submits a form. Pasted text (cmd+v) is not scanned. These are why the binding rule still governs every send.

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
