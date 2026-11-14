#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Save one Messenger chat's text from its page when an export lacks it, as the importer writes a transcript.

    python3 chat_page.py extractor
    python3 chat_page.py save READ [READ ...] --out FOLDER --since YYYY-MM-DD [--principal NAME] [--into FILE] [--dry-run]

`extractor` prints the script the browser tool runs on one open chat: it reads the chat's message log and returns each
message's labels (its time, sender and whole text) as JSON, and clicks, types and sends nothing. Save what the tool
returns, one file per read; a log that drops what it scrolled past is read as it scrolls, and its reads saved together.
`save` writes their messages in the importer's transcript format and identity scheme, each keyed by the minute the page
shows and a digest of its text, its block marked as read from the page. A later import of the same chat pairs its
messages with those blocks by digest and minute and adds nothing the transcript holds, and this pairs with an export's
blocks the same way. The messages go to the transcript holding this chat's earlier page reads, else to one holding any
of them with the same people, else to the one --into names, else to a new one. `You` is written as --principal, the
principal's name as the export writes it. Text is fenced as untrusted data. Standard library only; no network.

Exit 0: saved, reaching the day asked for. 1: saved, short of that day or with messages it could not read. 2: refused,
nothing written. Reference: ../references/chat-page.md.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_messages as im  # noqa: E402  the transcript format, the identity scheme and the pairing rule

EXTRACTOR = r"""(() => {
  const shown = (el) => el.getClientRects().length > 0;
  const log = document.querySelector('[role="log"][aria-label^="Messages in conversation with "]');
  const out = {extractor: "messenger-chat/1", url: location.href, title: document.title,
               zone: Intl.DateTimeFormat().resolvedOptions().timeZone || null, log: log ? log.getAttribute("aria-label") : null,
               items: [], dialogs: [], page: ""};
  for (const box of document.querySelectorAll('[role="dialog"], [role="alertdialog"]')) {
    if (shown(box) && !(log && box.contains(log))) out.dialogs.push((box.innerText || "").slice(0, 300));
  }
  for (const item of log ? log.querySelectorAll('[role="article"]') : []) {
    const labels = [...item.querySelectorAll("[aria-label]")].filter((e) => e.closest('[role="article"]') === item)
      .map((e) => e.getAttribute("aria-label")).filter((label) => /^(Enter, Message sent |At [A-Z][a-z]+ \d)/.test(label));
    out.items.push(labels.length ? {labels} : {text: (item.innerText || "").slice(0, 300)});
  }
  if (!log) out.page = (document.body ? document.body.innerText : "").slice(0, 2000);
  return JSON.stringify(out);
})()"""
WHEN = (r"(?P<month>[A-Z][a-z]+) (?P<day>\d{1,2}), (?P<year>\d{4}), (?P<hour>\d{1,2}):(?P<minute>\d{2})"
        r"[   ](?P<half>[AP]M)")  # the page puts a narrow no-break space before AM or PM, or a space
LABELS = (re.compile(r"Enter, Message sent " + WHEN + r" by (?P<sender>[^:\n]{1,200}?): (?P<text>.*)", re.S),
          re.compile(r"At " + WHEN + r", (?P<sender>[^:\n]{1,200}?): (?P<text>.*)", re.S))
FIELDS = ("month", "day", "year", "hour", "minute", "half", "sender", "text")
CHAT = re.compile(r"https://(?:(?:www|web|m)\.)?facebook\.com/messages/(e2ee/)?t/([A-Za-z0-9._-]{1,128})/?(?:[?#].*)?"
                  r"|https://(?:www\.)?messenger\.com/(e2ee/)?t/([A-Za-z0-9._-]{1,128})/?(?:[?#].*)?", re.S)
TITLE = re.compile(r"Messages in conversation with (.+)", re.S)
WALL = re.compile(r"log in|log into|sign in|security check|checkpoint|confirm (?:it'?s|that it'?s) you|captcha|unusual activity"
                  r"|verification code|two-factor|enter (?:your )?pin|restore your chat|temporarily blocked", re.I)
WALL_PATH = re.compile(r"https://[^/]+/(?:login|checkpoint|two_step_verification|recover)\b")


class Refused(Exception):
    """Nothing is written."""


def loaded(path):
    """One read as saved: the extractor's JSON, or the JSON string the browser tool returns it as."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data = json.loads(data) if isinstance(data, str) else data
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict) or data.get("extractor") != "messenger-chat/1" or not isinstance(data.get("items"), list):
        raise Refused(f"{os.path.basename(path)} is not the extractor's saved output: save what the browser tool returned for "
                      "`chat_page.py extractor`")
    return data


def label_of(label):
    """(month, day, year, hour, minute, half, sender, text) from either of a message's labels, or None."""
    for shape in LABELS:
        found = shape.fullmatch(str(label))
        if found:
            return tuple(found.group(field) for field in FIELDS)
    return None


def instant(said, zone):
    """(UTC milliseconds of the minute shown, minutes a second reading lies later, local day, local HH:MM), or None for
    a time the zone never shows. In the hour the clocks went back each time happens twice and the page cannot say which:
    the first is kept, and the block says the second may be meant."""
    month, day, year, hour, minute, half = said[:6]
    try:
        if not 1 <= int(hour) <= 12:
            raise ValueError(hour)
        wall = datetime.datetime(int(year), im.MONTHS.index(month) + 1, int(day), int(hour) % 12 + 12 * (half == "PM"),
                                 int(minute))
    except ValueError:
        return None
    first, second = (wall.replace(tzinfo=zone, fold=fold).astimezone(datetime.timezone.utc) for fold in (0, 1))
    if first.astimezone(zone).replace(tzinfo=None) != wall:
        return None  # skipped when the clocks went forward
    return int(first.timestamp()) * 1000, int((second - first).total_seconds()) // 60, wall.date().isoformat(), f"{wall:%H:%M}"


def read_chat(reads, principal):
    """The chat these reads show: its address, its name, its messages as the importer's message records (each read's
    repeats kept, a message in two reads once), the oldest local time, and what was not written."""
    chat, pages, counts, oldest = None, [], dict.fromkeys(("notices", "textless", "unreadable"), 0), None
    for data in reads:
        url = str(data.get("url") or "")
        seen = [str(d) for d in data.get("dialogs") or []] + ([] if data.get("log") else [str(data.get("page") or "")])
        if WALL_PATH.match(url) or any(WALL.search(text) for text in seen):
            raise Refused("the page shows a sign-in page or a security check; stop and tell the principal")
        named = TITLE.fullmatch(str(data.get("log") or ""))
        if not named:
            raise Refused("no chat log in this read: open the chat, let its messages load, and read again")
        found = CHAT.fullmatch(url)
        if not found:
            raise Refused("the page is not a Messenger chat's own address on facebook.com or messenger.com")
        e2ee, ident = (found[1], found[2]) if found[2] else (found[3], found[4])
        address = f"https://www.facebook.com/messages/{'e2ee/' if e2ee else ''}t/{ident}/"
        if chat not in (None, address):
            raise Refused("these reads are of two chats: save each chat's reads on its own")
        chat, title = address, " ".join(named[1].split())
        try:
            zone = ZoneInfo(str(data.get("zone") or ""))
        except (ValueError, KeyError, OSError):
            raise Refused(f"the read names no time zone this Python knows ({str(data.get('zone'))[:40]!r}); the page's times "
                          "are in the browser's own, which the extractor records")
        page = []
        for entry in data["items"]:
            labels = entry.get("labels") if isinstance(entry, dict) else None
            if not labels:
                counts["notices"] += 1  # the encryption notice and the like: no message label
                continue
            said = {label_of(label) for label in labels}
            when = instant(next(iter(said)), zone) if len(said) == 1 and None not in said else None
            if when is None:
                counts["unreadable"] += 1  # a label in no known shape, labels that disagree, or a time never shown
                continue
            sender, text = next(iter(said))[6:]
            if not text.strip():
                counts["textless"] += 1
                continue
            if sender == "You" and not principal:
                raise Refused("the read holds the principal's own messages (`You`): pass --principal with the principal's "
                              "name as the export writes it")
            page.append({"ts": when[0], "sender": principal if sender == "You" else sender, "text": text, "attachments": [],
                         "share": None, "reactions": [], "unsent": False, "call": None, "page": (address, when[1])})
            oldest = min(oldest or (when[0], when[2], when[3], zone.key), (when[0], when[2], when[3], zone.key))
        pages.append(page)
    conversation = {"pages": pages}
    im.keyed(conversation)
    if not conversation["messages"]:
        raise Refused("the reads hold no message with text: scroll the log until messages show, and read again")
    return chat, title, conversation["messages"], oldest, counts


def people(path, cid):
    """The names a transcript gives its people, as written: its participants and every sender of its blocks."""
    blocks, recorded = im.read_transcript(path, cid)
    return set((recorded or "Participants: ")[len("Participants: "):].split(", ")) | {im.sender_of(b[2][0]) for b in blocks}


def place(out, chat, title, messages, into):
    """(path, its id, its blocks, the header kept or None): where this chat's messages go. The transcript holding its
    earlier page reads; else the one holding any of its messages with the same people; else the one --into names;
    else a new one, named as the importer names a secure-storage conversation, or `page-` for a chat no download covers."""
    held, unread = im.holders(out)
    senders = {im.inline(message["sender"]) for message in messages}
    keys = {message["key"] for message in messages}
    paged = [(message["key"].split("-")[1], {message["ts"], message["ts"] + message["page"][1] * im.MINUTE_MS})
             for message in messages]
    cid = lambda where: os.path.basename(where)[len("messenger-"):-len(".md")]  # noqa: E731
    mine = sorted(where for where, (_, _, pages) in held.items() if any(page[3] == chat for page in pages))
    if not mine:
        exact = lambda blocks: [(key, ts) for key, ts, lines in blocks if not im.page_blocks([(key, ts, lines)])]  # noqa: E731
        mine = sorted(where for where, (blocks, have, _) in held.items()
                      if (have & keys or im.pairs(exact(blocks), paged)) and senders <= people(where, cid(where)))
    if len(mine) > 1:
        raise Refused("more than one transcript holds this chat: " + ", ".join(map(os.path.basename, mine)))
    if into:
        target = os.path.join(out, os.path.basename(into))
        if mine and mine[0] != target:
            raise Refused(f"{os.path.basename(into)} is not the transcript that holds this chat, {os.path.basename(mine[0])}")
        if target not in held:
            raise Refused(f"{os.path.basename(into)} is no transcript in --out that reads back"
                          + (f" ({unread[target]})" if target in unread else ""))
        missing = senders - people(target, cid(target))
        if missing:
            raise Refused(f"{os.path.basename(into)} does not name {', '.join(sorted(missing))}, who wrote in this chat: it "
                          "is another conversation's")
        mine = [target]
    if mine:
        lines = Path(mine[0]).read_text(encoding="utf-8").split("\n")
        if not (lines[4].startswith("From: ") and lines[5].startswith("Participants: ")):
            raise Refused(f"{os.path.basename(mine[0])} has no header this importer wrote")
        return mine[0], cid(mine[0]), held[mine[0]][0], lines[1:6]
    first = hashlib.sha256(messages[0]["key"].encode("utf-8")).hexdigest()[:8]
    name = f"{'e2ee' if '/e2ee/' in chat else 'page'}-{im.slug(title, 60)}-{first}"
    path = os.path.join(out, f"messenger-{name}.md")
    if os.path.lexists(path):
        raise Refused(f"messenger-{name}.md is there and holds another conversation")
    return path, name, [], None


def save(args):
    reads = [loaded(path) for path in args.reads]
    chat, title, messages, oldest, counts = read_chat(reads, args.principal)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        raise Refused("--since is the day asked for, YYYY-MM-DD")
    out = os.path.realpath(args.out)
    if os.path.lexists(out) and not os.path.isdir(out):
        raise Refused("--out names something that is not a folder")
    if not os.path.isdir(os.path.dirname(out)):
        raise Refused("the folder that would hold --out does not exist")
    path, cid, old, kept = place(out, chat, title, messages, args.into)
    have = {key for key, _, _ in old}
    fresh = [message for message in messages if message["key"] not in have]
    exact = [(key, ts) for key, ts, lines in old if not im.page_blocks([(key, ts, lines)])]
    paired = set(im.pairs(exact, [(m["key"].split("-")[1], {m["ts"], m["ts"] + m["page"][1] * im.MINUTE_MS}) for m in fresh]).values())
    new = [message for n, message in enumerate(fresh) if n not in paired]
    if new and not args.dry_run:
        if not os.path.isdir(out):
            os.mkdir(out, 0o700)
        conversation = {"title": title, "names": sorted({m["sender"] for m in messages}), "from": [chat], "where": "page read"}
        im.write(out, path, im.render(conversation, old, new, cid, kept))
    reached, left = oldest[1] <= args.since, [f"{n} {what}" for what, n in (("notice" + "s" * (counts["notices"] != 1),
                                                                          counts["notices"]), ("without text", counts["textless"])) if n]
    print(f"page read: {len(messages)} message{'s' * (len(messages) != 1)} from {len(reads)} read{'s' * (len(reads) != 1)}, "
          f"back to {oldest[1]} {oldest[2]} {oldest[3]}; "
          + (f"it reaches {args.since}, the day asked for" if reached else
             f"it stops short of {args.since}, the day asked for: scroll the log further up and read again")
          + (f"; {counts['unreadable']} could not be read" if counts["unreadable"] else "")
          + (f"; {' and '.join(left)} not written" if left else ""))
    state = "new" if kept is None and not old else "extended" if new else "unchanged"
    print(f"transcript: {os.path.basename(path)} ({state}): {len(new)} new, {len(messages) - len(new)} already in it")
    if args.dry_run:
        print("dry run: nothing written")
    return 0 if reached and not counts["unreadable"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="chat_page.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extractor", help="print the read-only script the browser tool runs on the open chat")
    keep = sub.add_parser("save", help="write the saved reads' messages into the transcripts")
    keep.add_argument("reads", nargs="+", help="each read as saved: what the browser tool returned for the extractor")
    keep.add_argument("--out", required=True, help="the private folder of the transcripts, the one the importer writes")
    keep.add_argument("--since", required=True, help="the day asked for, YYYY-MM-DD: the coverage says whether the read reached it")
    keep.add_argument("--principal", default="", help="the principal's name as the export writes it, for the page's `You`")
    keep.add_argument("--into", default="", help="the transcript in --out to extend when no transcript holds this chat yet")
    keep.add_argument("--dry-run", action="store_true", help="read and count; write nothing")
    args = parser.parse_args(argv)
    if args.command == "extractor":
        print(EXTRACTOR)
        return 0
    try:
        return save(args)
    except Refused as refusal:
        print(f"refused: {refusal}; nothing written")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
