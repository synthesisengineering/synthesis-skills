#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Save one Messenger chat's text from its page when an export lacks it, as the importer writes a transcript.

    python3 "$HOME/.synthesis/v5/current/skills/synthesis-message-exports/scripts/chat_page.py" extractor
    python3 "$HOME/.synthesis/v5/current/skills/synthesis-message-exports/scripts/chat_page.py" save READ [READ ...] --out FOLDER --since YYYY-MM-DD [--principal NAME] [--into FILE] [--dry-run]

`extractor` prints the script the browser tool runs on one open chat: it reads the chat's message log and returns each
message's labels (its time, sender and whole text), the page's clock and time zone and each dialog's heading as JSON,
and clicks, types and sends nothing. Save what the tool returns, one file per read; a log that drops what it scrolled
past is read as it scrolls, each read overlapping the next by two messages or more, and the reads saved together.
`save` writes their messages in the importer's transcript format and identity scheme, each keyed by the minute the page
shows and a digest of its text, its block marked as read from the page. A message pairs with an export's by sender,
minute and text alone, in either order, so nothing is written twice; one that pairs only in part (its minute with other
words or another sender), an item whose labels match no message and a possible twin where two reads meet are held for
a person, never written and never dropped. The messages go to the transcript holding this chat's earlier page reads;
else to one holding its messages that names the person or title the log names, every message of it inside the read's
span pairing; else to the one --into names, on the same evidence; else to a new one. A transcript passed over is
named. `You` is written as --principal, the principal's name as the export writes it. Text is fenced as untrusted data.
Standard library only; no network.

Exit 0: saved, reaching the day asked for (a message from before it was read) with nothing held. 1: saved, short of
that day, or with messages it could not read or held for a person. 2: refused, nothing written. Reference:
../references/chat-page.md.
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
  const out = {extractor: "messenger-chat/1", url: location.href, title: document.title, at: Date.now(),
               zone: Intl.DateTimeFormat().resolvedOptions().timeZone || null, log: log ? log.getAttribute("aria-label") : null,
               items: [], dialogs: [], page: ""};
  for (const box of document.querySelectorAll('[role="dialog"], [role="alertdialog"]')) {
    if (!shown(box) || (log && box.contains(log))) continue;
    const heading = box.querySelector('h1, h2, h3, [role="heading"]') || {innerText: (box.innerText || "").trim().split("\n")[0]};
    out.dialogs.push((box.getAttribute("aria-label") || heading.innerText || "").slice(0, 120));  // its heading, never its text
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
LABELS = (re.compile(r"Enter, Message sent " + WHEN + r" by (?P<rest>.+)", re.S), re.compile(r"At " + WHEN + r", (?P<rest>.+)", re.S))
CHAT = re.compile(r"https://(?:(?:www|web|m)\.)?facebook\.com/messages/(e2ee/)?t/([A-Za-z0-9._-]{1,128})/?(?:[?#].*)?"
                  r"|https://(?:www\.)?messenger\.com/(e2ee/)?t/([A-Za-z0-9._-]{1,128})/?(?:[?#].*)?", re.S)
TITLE = re.compile(r"Messages in conversation with (.+)", re.S)
WALL = re.compile(r"log in|log into|sign in|security check|checkpoint|confirm (?:it'?s|that it'?s) you|captcha|unusual activity"
                  r"|verification code|two-factor|enter (?:your )?pin|restore your chat|temporarily blocked", re.I)
WALL_PATH = re.compile(r"https://[^/]+/(?:login|checkpoint|two_step_verification|recover)\b")
EARLIEST = "2004-02-04"  # Facebook began: a label dated before it carries no date
HELD = (("early", f"dated before {EARLIEST}, so with no date"), ("unlabeled", "item whose labels match no message"),
        ("twins", "possible twin where two reads meet"), ("doubtful", "like one in the transcript in its minute, with other "
                                                                       "words or another sender"))


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


def label_of(label, title):
    """(month, day, year, hour, minute, half, sender, text) from either of a message's labels, or None. The sender is
    the name the log gives or `You` where the label carries it, else what stands before the first `: `."""
    for shape in LABELS:
        found = shape.fullmatch(str(label))
        if found:
            when, rest = tuple(found.group(f) for f in ("month", "day", "year", "hour", "minute", "half")), found["rest"]
            for name in (title, "You"):
                if name and rest.startswith(name + ": "):
                    return (*when, name, rest[len(name) + 2:])
            sender, colon, text = rest.partition(": ")
            return (*when, sender, text) if colon and sender and len(sender) <= 200 and "\n" not in sender else None
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
    """The chat these reads show: its address, its name, its messages as the importer's message records, the oldest
    local time the reads cover without a gap from the newest one, and the counts of what was not written. Two reads are
    one only where they share two messages or more; a message they share alone may be a twin, kept once and held."""
    chat, runs = None, []
    counts = dict.fromkeys(("notices", "textless", "unreadable", "early", "unlabeled", "twins", "gaps", "doubtful"), 0)
    for data in reads:
        url = str(data.get("url") or "")
        heads = [str(d).split("\n", 1)[0] for d in data.get("dialogs") or []]  # a dialog by its heading, never message text
        seen = heads + ([] if data.get("log") else [str(data.get("page") or "")])
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
        run = []
        for entry in data["items"]:
            labels = entry.get("labels") if isinstance(entry, dict) else None
            if not labels:
                counts["unlabeled"] += 1  # an article whose labels match no message may still hold one
                continue
            said = {label_of(label, title) for label in labels}
            sender, text = next(iter(said))[6:] if len(said) == 1 and None not in said else (None, "")
            if sender == "a participant" and "end-to-end encryption" in text.lower():
                counts["notices"] += 1  # where the chat became encrypted, labeled as sent at time zero: no message, no day
                continue
            when = instant(next(iter(said)), zone) if sender is not None else None
            if when is None:
                counts["unreadable"] += 1  # a label in no known shape, labels that disagree, or a time never shown
                continue
            if when[2] < EARLIEST:
                counts["early"] += 1
                continue
            if not text.strip():
                counts["textless"] += 1
                continue
            if sender == "You" and not principal:
                raise Refused("the read holds the principal's own messages (`You`): pass --principal with the principal's "
                              "name as the export writes it")
            run.append({"ts": when[0], "sender": principal if sender == "You" else sender, "text": text, "attachments": [],
                        "share": None, "reactions": [], "unsent": False, "call": None, "page": (address, when[1]),
                        "local": (when[2], when[3], zone.key)})
        if run:
            im.keyed({"pages": [run]})  # each read's repeats keep their own ids
            runs.append(run)
    if not runs:
        raise Refused("the reads hold no message with text: scroll the log until messages show, and read again")
    merged, chain = {}, []
    for run in sorted(runs, key=lambda run: -max(m["ts"] for m in run)):  # the newest read first: coverage runs back from it
        shared = {m["key"] for m in run} & set(merged)
        if merged and len(shared) < 2:
            counts["gaps"], counts["twins"] = counts["gaps"] + 1, counts["twins"] + len(shared)
        if not counts["gaps"]:
            chain += run
        for message in run:
            merged.setdefault(message["key"], message)
    first = min(chain, key=lambda m: m["ts"])
    return chat, title, sorted(merged.values(), key=lambda m: m["ts"]), (first["ts"], *first["local"]), counts


def paged(messages):
    """Messages read from the page, as the importer's pairs() reads them: (sender as written, minutes, text digest)."""
    return [(im.inline(m["sender"]), {m["ts"], m["ts"] + m["page"][1] * im.MINUTE_MS}, im.text_digest(m["text"])) for m in messages]


def place(out, chat, title, messages, into):
    """(path, its id, its blocks, its header kept or None, transcripts passed over with why): where this chat's messages
    go. The transcript holding its earlier page reads; else one holding any of its messages, on evidence about the chat
    itself; else the one --into names, on the same evidence; else a new one, named as the importer names a secure-storage
    conversation, or `page-` for a chat no download covers."""
    held, unread = im.holders(out)
    keys, read, cid = {m["key"] for m in messages}, paged(messages), lambda where: os.path.basename(where)[len("messenger-"):-3]
    low, high = min(m["ts"] for m in messages), max(m["ts"] for m in messages) + im.MINUTE_MS

    def doubt(where):
        """Why a transcript is not this chat's, or None: it names the person or title the log names, and every message of
        it inside the read's span pairs with one read."""
        if im.inline(title) not in held[where][4]:
            return f"it does not name {title}, who this chat is with"
        inside = [block for block in im.exact_blocks(held[where][0]) if low <= block[2] < high]
        left = len(inside) - len(im.pairs(inside, read))
        return f"{left} of its messages inside the read's span pair with none read" if left else None

    mine, passed = sorted(where for where, entry in held.items() if any(page[3] == chat for page in entry[2])), []
    for where in [] if mine else sorted(held):
        if held[where][1] & keys or im.pairs(im.exact_blocks(held[where][0]), read):
            why = doubt(where)
            (passed.append((os.path.basename(where), why)) if why else mine.append(where))
    if len(mine) > 1:
        raise Refused("more than one transcript holds this chat: " + ", ".join(map(os.path.basename, mine)))
    if into:
        target = os.path.join(out, os.path.basename(into))
        if mine and mine[0] != target:
            raise Refused(f"{os.path.basename(into)} is not the transcript that holds this chat, {os.path.basename(mine[0])}")
        if target not in held:
            raise Refused(f"{os.path.basename(into)} is no transcript in --out that reads back"
                          + (f" ({unread[target]})" if target in unread else ""))
        why = doubt(target)
        if why:
            raise Refused(f"{os.path.basename(into)}: {why}: it is another conversation's")
        mine = [target]
    if mine:
        return mine[0], cid(mine[0]), held[mine[0]][0], held[mine[0]][5], passed
    first = hashlib.sha256(messages[0]["key"].encode("utf-8")).hexdigest()[:8]
    name = f"{'e2ee' if '/e2ee/' in chat else 'page'}-{im.slug(title, 60)}-{first}"
    path = os.path.join(out, f"messenger-{name}.md")
    if os.path.lexists(path):
        raise Refused(f"messenger-{name}.md is there and holds another conversation")
    return path, name, [], None, passed


def save(args):
    try:
        since = datetime.date.fromisoformat(args.since).isoformat() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since) else ""
    except ValueError:
        since = ""
    if not since:
        raise Refused(f"--since is the day asked for, a real day as YYYY-MM-DD, got {args.since!r}")
    reads = [loaded(path) for path in args.reads]
    chat, title, messages, oldest, counts = read_chat(reads, args.principal)
    out = os.path.realpath(args.out)
    if os.path.lexists(out) and not os.path.isdir(out):
        raise Refused("--out names something that is not a folder")
    if not os.path.isdir(os.path.dirname(out)):
        raise Refused("the folder that would hold --out does not exist")
    path, cid, old, kept, passed = place(out, chat, title, messages, args.into)
    have = {key for key, _, _ in old}
    fresh = [message for message in messages if message["key"] not in have]
    exact, fresh_paged = im.exact_blocks(old), paged(fresh)
    found = im.pairs(exact, fresh_paged)
    doubtful = im.loose(exact, fresh_paged, found)[1]
    new = [message for n, message in enumerate(fresh) if n not in set(found.values()) and n not in doubtful]
    counts["doubtful"] = len(doubtful)
    if new and not args.dry_run:
        if not os.path.isdir(out):
            os.mkdir(out, 0o700)
        conversation = {"title": title, "names": sorted({m["sender"] for m in messages}), "from": [chat], "where": "page read"}
        im.write(out, path, im.render(conversation, old, new, cid, kept if old else None))
    reached, held = oldest[1] < since, sum(counts[key] for key, _ in HELD)
    left = [f"{n} {what}" for what, n in (("notice" + "s" * (counts["notices"] != 1), counts["notices"]),
                                          ("without text", counts["textless"])) if n]
    print(f"page read: {len(messages)} message{'s' * (len(messages) != 1)} from {len(reads)} read{'s' * (len(reads) != 1)}, "
          f"back to {oldest[1]} {oldest[2]} {oldest[3]}; "
          + (f"it reaches {since}, the day asked for" if reached else
             f"it stops short of {since}, the day asked for: scroll the log further up and read again")
          + (f"; the reads do not overlap by two messages at {counts['gaps']} point{'s' * (counts['gaps'] != 1)}, so the "
             "coverage stops where they meet: read again with more overlap" if counts["gaps"] else "")
          + (f"; {counts['unreadable']} could not be read" if counts["unreadable"] else "")
          + (f"; {held} held for a person ({', '.join(f'{counts[key]} {why}' for key, why in HELD if counts[key])})" if held else "")
          + (f"; {' and '.join(left)} not written" if left else ""))
    for name, why in passed:
        print(f"not joined: {name}: {why}")
    state = "new" if not old else "extended" if new else "unchanged"
    print(f"transcript: {os.path.basename(path)} ({state}): {len(new)} new, {len(messages) - len(new) - len(doubtful)} already "
          f"in it" + (f", {len(doubtful)} held" if doubtful else ""))
    if args.dry_run:
        print("dry run: nothing written")
    return 0 if reached and not counts["unreadable"] and not held else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="chat_page.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extractor", help="print the read-only script the browser tool runs on the open chat")
    keep = sub.add_parser("save", help="write the saved reads' messages into the transcripts")
    keep.add_argument("reads", nargs="+", help="each read as saved: what the browser tool returned for the extractor")
    keep.add_argument("--out", required=True, help="the private folder of the transcripts, the one the importer writes")
    keep.add_argument("--since", required=True, help="the day asked for, YYYY-MM-DD: reached once a message from before it is read")
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
