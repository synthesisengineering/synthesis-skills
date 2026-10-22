# SPDX-License-Identifier: Apache-2.0
"""Open an existing one-to-one WhatsApp chat with the principal's exact text in its composer. Nothing is sent.

Run: python3 whatsapp_prefill.py --to +15551234567 --text-file FILE [--photo PATH] [--store FOLDER]

WhatsApp's Mac app has no scripting interface, so the principal presses Send (the principal's ruling,
2026-10-22). This opens whatsapp://send with the number and text once; with --photo it also shows the photo in
Finder, to drag into the chat. It refuses a number with no one-to-one chat in WhatsApp's database, found by
number or by the linked id WhatsApp keeps for it (it never starts a chat), and text over 4,096 characters. A Send
pressed by computer use afterwards is held by the send guard: the principal sends.

Reads chat sessions and linked ids only, never messages. Prints one JSON object. Exit 0 prefilled; 2 refused.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import urllib.parse
sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle

NUMBER = re.compile(r"^\+[1-9][0-9]{6,14}$")
STORE = Path.home() / "Library" / "Group Containers" / "group.net.whatsapp.WhatsApp.shared"
TEXT_MAX = 4096


class Refused(Exception):
    """Nothing was opened."""


def opener(args: list) -> None:
    subprocess.run(["/usr/bin/open", *args], check=True, capture_output=True, timeout=15)


def _rows(database: Path, query: str, values: tuple) -> list:
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=0.5)
    try:
        return db.execute(query, values).fetchall()
    finally:
        db.close()


def existing_chat(number: str, store: Path) -> bool:
    """A one-to-one chat (session type 0) under the number's own id, or under a linked id WhatsApp pairs with it."""
    digits = number[1:]
    try:
        ids = [f"{digits}@s.whatsapp.net"]
        if (store / "LID.sqlite").is_file():
            ids += [r[0] for r in _rows(store / "LID.sqlite", "select ZIDENTIFIER from ZWAZACCOUNT where ZPHONENUMBER = ? "
                                        "and ZIDENTIFIER like '%@lid'", (digits,))]
        marks = ",".join("?" * len(ids))
        found = _rows(store / "ChatStorage.sqlite", "select count(*) from ZWACHATSESSION where ZSESSIONTYPE = 0 "
                      f"and ZCONTACTJID in ({marks})", tuple(ids))
    except sqlite3.Error as exc:
        raise Refused(f"cannot read WhatsApp's chats to confirm an existing chat ({exc}); nothing was opened") from exc
    return bool(found and found[0][0])


def prefill(number: str, text: str, photo: str | None = None, store: Path = STORE) -> dict:
    if not NUMBER.match(number):
        raise Refused("the recipient must be +<country code><number>; a WhatsApp link cannot name a group")
    if not text.strip() or len(text) > TEXT_MAX or "\0" in text:
        raise Refused(f"the text must be non-empty, at most {TEXT_MAX:,} characters, with no NUL")
    shown = Path(photo).expanduser().resolve() if photo else None
    if shown is not None and not shown.is_file():
        raise Refused(f"the photo is not a file: {shown}")
    if not existing_chat(number, store):
        raise Refused(f"no one-to-one WhatsApp chat with {number}; start it in WhatsApp first (this never starts one)")
    link = "whatsapp://send?" + urllib.parse.urlencode({"phone": number[1:], "text": text}, quote_via=urllib.parse.quote)
    try:
        opener([link])
        if shown is not None:
            opener(["-R", str(shown)])
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused(f"could not open WhatsApp: {exc}") from exc
    return {"status": "prefilled", "to": number, "photo": str(shown) if shown else None,
            "next": "The principal checks the chat and the text, attaches the photo if any, and presses Send. "
                    "Nothing was sent."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--to", required=True, help="the recipient's number: +<country code><number>")
    parser.add_argument("--text-file", required=True, help="UTF-8 file holding the exact approved text")
    parser.add_argument("--photo", help="a photo to show in Finder, for the principal to drag into the chat")
    parser.add_argument("--store", type=Path, default=STORE, help="WhatsApp's shared folder: ChatStorage.sqlite, LID.sqlite")
    args = parser.parse_args(argv)
    try:
        result = prefill(args.to, Path(args.text_file).read_text(encoding="utf-8"), args.photo, args.store)
    except (Refused, OSError, ValueError) as exc:
        result = {"status": "refused", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "prefilled" else 2


if __name__ == "__main__":
    sys.exit(main())
