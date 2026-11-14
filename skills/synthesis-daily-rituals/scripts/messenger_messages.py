#!/usr/bin/env python3
"""Read Messenger's chat list from what its extractor saved, and say how far back the read went.

Messenger runs inside facebook.com. Its chat list shows, without opening a chat: who, the age of the last message,
who spoke last (`You: `), the last message, an unread mark and Messenger's own `Follow up?` nudge on a chat that ends
with the principal. Opening a chat marks it read, so the read stays on the list. This prints a read-only extractor for
one inbox's grid, reads what it saved, lists the chats that end with someone else and prints one coverage line. It
opens nothing and writes nothing.

    messenger_messages.py plan --config .agents/messenger-sync.yaml [--today YYYY-MM-DD]
    messenger_messages.py extractor --inbox chats|requests|archived
    messenger_messages.py parse --text read.json --read-at 2026-11-14T09:45:00-05:00
        [--inbox NAME] [--since YYYY-MM-DD] [--opened N] [--empty] [--json]

`plan` reads the workspace's declaration (`workspace`, `inboxes` from chats, requests and archived; all three when
left out) and prints, per inbox, what to open and the day to scroll back to: the day the last read reached, or two
weeks back for a first read. Every inbox opens at the list's own address, beside "No chats selected"; Message
requests and Archived chats open from the menu over the list and have no address of their own.

`extractor` prints the script the browser tool runs on the page: it reads only the grid named for that inbox (a hidden
panel's rows have empty text) and returns each row's text lines, link and labels as JSON. Save what the tool returns.
A row shows an age, never a date, so `parse` dates it the latest its age allows (a `9w` row is at least nine weeks
old), and a row with no age moves nothing. Exit 0 for a complete read, 1 for one that stopped short of `--since` or
could not read a row, 2 for text that is not the extractor's, a read that holds no grid of that inbox, or a sign-in
page or security check. A chat open during the read was marked read: it is counted with `--opened` and named. An
empty list is a complete read only with `--empty`, and only where the grid is there or the page says it is empty. A
short list read to its end reaches every day only with `--end`, and only where the extractor saw it at its bottom.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root, which holds synthesis/

LIST = "https://www.facebook.com/messages/t/"
GRIDS = {"chats": "Chats", "requests": "Requests", "archived": "Archived chats"}
OPENS = {"chats": 'the chat list beside "No chats selected"; never a chat\'s own address, which opens the chat and marks it read',
         "requests": "then Settings, help and more > Message requests; read the grid named Requests, on the tab it opens on; "
                     "the panel has no address of its own",
         "archived": "then Settings, help and more > Archived chats; read the grid named Archived chats; the panel has no "
                     "address of its own"}
EMPTY = {"archived": "No archived chats"}  # what a panel says when it holds nothing, where a read has seen it
FIRST_READ_DAYS = 14
AGE = re.compile(r"^(\d{1,3})([mhdwy])$")
WORDS = re.compile(r"^(a|an|\d{1,3}) (minute|hour|day|week|year)s? ago$")
UNIT = {"m": timedelta(minutes=1), "h": timedelta(hours=1), "d": timedelta(days=1), "w": timedelta(weeks=1),
        "y": timedelta(days=365)}
JOINED = re.compile(r"^(.*\S)\s+·\s+(\d{1,3}[mhdwy]|Follow up\?)$")  # a preview and its age read as one line
CHAT = re.compile(r"/messages/(e2ee/)?t/([A-Za-z0-9._-]{1,128})/?$")
MEDIA = re.compile(r"^(?:You|\S+) sent (?:a|an|\d+) [^.]{1,40}\.$")
WALL = re.compile(r"log in|log into|sign in|security check|checkpoint|confirm (?:it'?s|that it'?s) you|captcha|unusual activity"
                  r"|verification code|two-factor|enter (?:your )?pin|restore your chat|temporarily blocked", re.I)
WALL_PATH = re.compile(r"^/(?:login|checkpoint|two_step_verification|recover)\b")
EXTRACTOR = r"""(() => {
  const name = __GRID__;
  const shown = (el) => el.getClientRects().length > 0;
  const grids = [...document.querySelectorAll('[role="grid"]')].filter((g) => g.getAttribute("aria-label") === name);
  const grid = grids.find(shown) || grids[0] || null;
  const out = {extractor: "messenger-list/1", url: location.href, title: document.title, grid: name, found: !!grid,
               rows: [], dialogs: [], page: ""};
  for (const box of document.querySelectorAll('[role="dialog"], [role="alertdialog"]')) {
    if (shown(box) && !(grid && box.contains(grid))) out.dialogs.push((box.innerText || "").slice(0, 300));
  }
  const rows = grid ? [...grid.querySelectorAll('[role="row"]')] : [];
  for (const row of rows) {
    const link = row.querySelector('a[href*="/t/"]');
    const more = row.querySelector('[aria-label^="More options for "]');
    out.rows.push({text: (row.innerText || "").split("\n"), href: link ? link.getAttribute("href") : null,
                   options: more ? more.getAttribute("aria-label") : null,
                   ages: [...row.querySelectorAll('[aria-label$=" ago"]')].map((e) => e.getAttribute("aria-label"))});
  }
  const scrollers = [];  // every scroll container from the first row up, in the grid or around it: --end holds only
  for (let box = rows[0] || null; box; box = box.parentElement) {  // when one is found and each is at its end
    if (/auto|scroll|overlay/.test(getComputedStyle(box).overflowY)) scrollers.push(box);
  }
  out.bottom = scrollers.length > 0 && scrollers.every((box) => box.scrollTop + box.clientHeight >= box.scrollHeight - 4);
  if (!out.rows.length) out.page = (document.body ? document.body.innerText : "").slice(0, 2000);
  return JSON.stringify(out);
})()"""


def stop(message: str):
    print(f"messenger_messages: {message}", file=sys.stderr)
    raise SystemExit(2)


def loaded(text: str) -> dict:
    """The extractor's saved value: its JSON, or the JSON string the browser tool returns it as."""
    try:
        data = json.loads(text)
        data = json.loads(data) if isinstance(data, str) else data
    except ValueError:
        data = None
    if not isinstance(data, dict) or data.get("extractor") != "messenger-list/1" or not isinstance(data.get("rows"), list):
        stop("this is not the extractor's saved output: save what the browser tool returned for `extractor --inbox <inbox>`")
    return data


def address(href) -> str | None:
    """A chat's address, the same from any page that links it; None for anything else (the list's own address)."""
    found = CHAT.search(re.split(r"[?#]", str(href or ""))[0])
    return f"https://www.facebook.com/messages/{found[1] or ''}t/{found[2]}/" if found else None


def entry(raw: dict, read: datetime):
    """One conversation from a row the extractor saved, or None when it cannot be read. Its lines: an optional
    `Active now`, the name, an optional `Unread message:`, the preview (on one line or several), a lone `·`, then the
    age or Messenger's `Follow up?`."""
    lines = [str(line).strip() for line in raw.get("text") or [] if str(line).strip()]
    joined = JOINED.match(lines[-1]) if lines else None
    if joined:
        lines[-1:] = [joined[1], "·", joined[2]]
    found = {"who": None, "chat": address(raw.get("href")), "age": None, "last": None, "from_me": False, "kind": "message",
             "unread": False, "nudge": False, "active": lines[:1] == ["Active now"], "open": False, "preview": ""}
    lines = lines[found["active"]:]
    if len(lines) < 3 or lines[-2] != "·":
        return None
    found["who"], tail, words = lines[0], lines[-1], lines[1:-2]
    named = str(raw.get("options") or "")
    if named.startswith("More options for ") and named[len("More options for "):] != found["who"]:
        return None  # the first line is not the name its options button gives: the row is not as this reads it
    if words[:1] == ["Unread message:"]:
        found["unread"], words = True, words[1:]
    age, said = AGE.match(tail), [WORDS.match(str(w)) for w in raw.get("ages") or []]
    if tail == "Follow up?":
        found["nudge"] = True
    elif not age or any(w and (1 if w[1] in ("a", "an") else int(w[1]), w[2][0]) != (int(age[1]), age[2]) for w in said):
        return None
    else:
        found["age"], found["last"] = tail, (read - int(age[1]) * UNIT[age[2]]).date().isoformat()
    found["preview"] = preview = " ".join(words)
    found["from_me"] = found["nudge"] or preview.startswith(("You: ", "You sent "))
    found["kind"] = "media" if MEDIA.match(preview) else "message"
    return found


def parse(data: dict, read: datetime, since: str = "", opened: int = 0, inbox: str = "", empty: bool = False,
          end: bool = False) -> dict:
    grid, rows = GRIDS.get(inbox) or data.get("grid"), data["rows"]
    if end and data.get("bottom") is not True:
        stop("--end says the list ends here, but the read was not at the bottom of the list: scroll to its end, wait for "
             "anything more to load, and read again")
    path = re.sub(r"^[a-z]+://[^/]+", "", str(data.get("url") or ""))
    seen = [str(d) for d in data.get("dialogs") or []] + ([] if data.get("found") else [str(data.get("page") or "")])
    if WALL_PATH.match(path) or any(WALL.search(text) for text in seen):
        stop("the page shows a sign-in page or a security check; stop and tell the principal")
    if inbox and data.get("grid") != grid:
        stop(f"this read is of the list named {data.get('grid')}, not {grid}: run the extractor for {inbox} and read again")
    if not data.get("found") or not rows:
        says = EMPTY.get(inbox, "")
        told = bool(says) and says in str(data.get("page") or "")
        if not data.get("found") and not told:
            stop(f"no list named {grid} in this read: open the {inbox or 'inbox'} list and read again")
        if not empty:
            stop("no conversations in the list" + (f" (the page says {says})" if told else "") + ": pass --empty when the page "
                 "itself says the inbox holds none, or read again once the list has loaded")
    elif empty:
        stop(f"--empty says the inbox holds nothing, but this read holds {len(rows)} rows: read it without the flag")
    threads, unreadable, blank = [], 0, 0
    for raw in rows:
        raw = raw if isinstance(raw, dict) else {}
        found = entry(raw, read)
        unreadable += found is None
        blank += found is None and not any(str(line).strip() for line in raw.get("text") or [])
        threads += [found] if found else []
    here = address(path)  # the page itself was a chat: it was open during the read, so it is read now
    for thread in threads:
        thread["open"] = bool(here) and thread["chat"] == here
    opened = max(opened, int(bool(here)))
    oldest = min((t["last"] for t in threads if t["last"]), default=None)  # a row with no age moves nothing
    short = bool(since and threads and not end and (oldest is None or oldest > since))  # the whole list read reaches any day
    complete = (bool(threads) or empty) and not unreadable and not short
    owed, nudged = [t for t in threads if not t["from_me"]], [t for t in threads if t["nudge"]]
    unread, count = sum(t["unread"] for t in threads), len(threads)
    line = (f"Messenger{', ' + inbox if inbox else ''}: "
            + (f"{count} conversation{'s' * (count != 1)} read from the list, back to {oldest or 'no day shown'}"
               f"{' (the end of the list)' if end else ''}; "
               f"{len(owed)} end{'s' * (len(owed) == 1)} with someone else ({unread} unread); Messenger suggests a follow-up "
               f"on {len(nudged)}; " if threads else "no conversations in the list; ")
            + f"{opened or 'none'} opened"
            + (f"; {unreadable} could not be read" if unreadable else "")
            + (f" ({blank} with no text: a hidden panel's rows read empty, so read only the grid of the inbox on screen)"
               if blank else "")
            + ("" if not short else f"; the read stops short of {since}: scroll the list further and read again" if oldest
               else f"; no row read shows its age, so nothing shows the read reached {since}: scroll the list further and "
                    "read again"))
    return {"read_at": read.isoformat(), "inbox": inbox or None, "threads": threads, "owed": owed, "nudged": nudged,
            "coverage": {"threads": count, "oldest": oldest, "unreadable": unreadable, "since": since or None, "opened": opened,
                         "complete": complete, "through": read.isoformat() if complete else None},
            "line": line}


def plan(config: Path, today: date) -> list:
    """What a read opens and the day it scrolls back to, from the workspace's declaration."""
    import sync_watermark as watermarks
    from synthesis.yamlish import load
    try:
        declared = load(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stop(f"cannot read the declaration {config} ({exc})")
    declared = declared if isinstance(declared, dict) else {}
    workspace, inboxes = declared.get("workspace"), declared.get("inboxes", list(GRIDS))
    if not isinstance(workspace, str) or not workspace.strip():
        stop(f"{config} names no workspace")
    if not isinstance(inboxes, list) or not inboxes or not all(isinstance(i, str) and i.strip() for i in inboxes):
        stop(f"{config}: inboxes is a list of the inboxes to read, for example [chats, requests, archived]")
    if set(inboxes) - set(GRIDS):
        stop(f"{config}: inboxes names {', '.join(sorted(set(inboxes) - set(GRIDS)))}; this reads {', '.join(GRIDS)}")
    lines = []
    for inbox in inboxes:
        last = watermarks.window(workspace, "messenger", inbox)["from"]
        day = last[:10] if last else (today - timedelta(days=FIRST_READ_DAYS)).isoformat()
        lines += [f"open  {LIST}  ({inbox}: {OPENS[inbox]})",
                  f"read  {inbox}: " + (f"read through {day}; scroll back to that day" if last else f"never read; scroll back to {day}")
                  + f", stop there, and pass --inbox {inbox} --since {day}"]
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    ahead = sub.add_parser("plan", help="what to open and how far back to read")
    ahead.add_argument("--config", required=True, type=Path)
    ahead.add_argument("--today", type=date.fromisoformat, default=None, help="today, YYYY-MM-DD (default: the clock)")
    script = sub.add_parser("extractor", help="the read-only script the browser tool runs on the list")
    script.add_argument("--inbox", required=True, choices=list(GRIDS))
    read = sub.add_parser("parse", help="read what the extractor saved")
    read.add_argument("--text", required=True, type=Path, help="the extractor's value as the browser tool returned it")
    read.add_argument("--read-at", required=True, help="when the list was read, ISO-8601 with its offset")
    read.add_argument("--inbox", default="", choices=list(GRIDS), help="the inbox read; it is named in the coverage line")
    read.add_argument("--since", default="", help="the day the last read reached, YYYY-MM-DD")
    read.add_argument("--empty", action="store_true", help="the page itself says this inbox holds no conversations")
    read.add_argument("--end", action="store_true", help="the list was read to its bottom and scrolling loaded nothing more")
    read.add_argument("--opened", type=int, default=0, help="how many chats this read opened (each marks one read)")
    read.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "plan":
        print("\n".join(plan(args.config, args.today or date.today())))
        return 0
    if args.command == "extractor":
        print(EXTRACTOR.replace("__GRID__", json.dumps(GRIDS[args.inbox])))
        return 0
    try:
        moment = datetime.fromisoformat(args.read_at.replace("Z", "+00:00"))
        text = args.text.read_text(encoding="utf-8")
    except (ValueError, OSError) as exc:
        stop(f"cannot read --read-at or --text ({exc})")
    if args.since and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        stop("--since is a day, YYYY-MM-DD")
    result = parse(loaded(text), moment, args.since, args.opened, args.inbox, args.empty, args.end)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["line"])
        for t in result["threads"]:
            if t["open"]:
                print(f"  open during the read: {t['who']} (opening a chat marks it read; name it in the plan)")
        for t in result["owed"]:
            marks = [m for m in ("unread" if t["unread"] else "", "active now" if t["active"] else "") if m]
            print(f"  {t['last'] or 'no age'}{' (' + t['age'] + ')' if t['age'] else ''} {t['who']}: {t['preview'][:200]}"
                  + (f"  [{', '.join(marks)}]" if marks else ""))
        for t in result["nudged"]:
            print(f"  follow up? {t['who']}: {t['preview'][:200]}  [Messenger suggests a follow-up]")
    return 0 if result["coverage"]["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
