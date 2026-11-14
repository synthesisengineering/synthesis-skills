# SPDX-License-Identifier: Apache-2.0
"""Invented exports for the importer's tests: made-up people and made-up words, never real data.

Meta's regular export writes text as UTF-8 bytes escaped one by one as if each were a Latin-1 character;
`meta_text` makes text that way, and json.dumps with its default ASCII escapes then writes it as Meta's files
show it (\\u00c3\\u00a9 for é). The secure-storage download is written both ways in the tests, since whether it
carries the same quirk is not established.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

ALEX, BLAIR, CASEY = "Alex Sample", "Blair Example", "Casey Fixture"
T0 = 1709647320000  # 2024-03-05T14:02:00Z, a Tuesday
DAY = 86_400_000
SECTIONS = ("inbox", "archived_threads", "filtered_threads", "message_requests", "e2ee_cutover")


def meta_text(text: str) -> str:
    """Text as the regular export writes it: each UTF-8 byte as one Latin-1 character."""
    return text.encode("utf-8").decode("latin-1")


def dyi_message(sender: str, ts: int, content: str | None = None, **fields) -> dict:
    message = {"sender_name": meta_text(sender), "timestamp_ms": ts}
    if content is not None:
        message["content"] = meta_text(content)
    message.update(fields)
    return message


def dyi_thread(title: str, participants: list, messages: list, thread_type: str = "Regular") -> dict:
    return {"participants": [{"name": meta_text(name)} for name in participants], "messages": messages,
            "title": meta_text(title), "is_still_participant": True, "thread_type": thread_type,
            "thread_path": "inbox/placeholder", "magic_words": []}


def write_dyi(root: Path, folder: str, files: list, section: str = "inbox",
              parent: str | None = "your_facebook_activity") -> Path:
    """One conversation of the regular export: files[0] is message_1.json, files[1] message_2.json, and so on."""
    base = Path(root) / (parent or "") / "messages" / section / folder
    base.mkdir(parents=True, exist_ok=True)
    for number, data in enumerate(files, 1):
        (base / f"message_{number}.json").write_text(json.dumps(data, indent=2), encoding="ascii")
    return base


def secure_message(sender: str, ts: int, text: str = "", **fields) -> dict:
    """One message of the secure-storage download, every key it is reported to carry."""
    message = {"isUnsent": False, "media": [], "reactions": [], "senderName": sender, "text": text,
               "timestamp": ts, "type": "Generic"}
    message.update(fields)
    return message


def write_secure(root: Path, stem: str, participants: list, messages: list, thread_name: str | None = None,
                 meta_escaped: bool = False) -> Path:
    """One conversation of the secure-storage download: `<display name>_<n>.json` at the download's top level."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    data = {"participants": participants, "threadName": stem.rsplit("_", 1)[0] if thread_name is None else thread_name,
            "messages": messages}
    if meta_escaped:  # every string written the regular export's way
        data = _every_string(data, meta_text)
    path = root / f"{stem}.json"
    path.write_text(json.dumps(data, ensure_ascii=meta_escaped), encoding="utf-8")
    return path


def _every_string(value, change):
    if isinstance(value, str):
        return change(value)
    if isinstance(value, list):
        return [_every_string(item, change) for item in value]
    if isinstance(value, dict):
        return {key: _every_string(item, change) for key, item in value.items()}
    return value


def zip_tree(folder: Path, target: Path, extra: dict | None = None) -> Path:
    """The folder as a ZIP, entry names relative to it; `extra` adds entries by name, written as given."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(Path(folder).rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(folder).as_posix())
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return target


def split_fences(text: str) -> tuple:
    """(lines outside the untrusted fences, the text of each fence), read as CommonMark reads a fenced block: it
    opens at three or more backticks with the info string `untrusted`, and closes only at a line of backticks at
    least as long."""
    outside, inside, tick = [], [], None
    for line in text.split("\n"):
        if tick is None:
            opened = re.fullmatch(r"(`{3,})untrusted", line)
            if opened:
                tick = opened.group(1)
                inside.append([])
            else:
                outside.append(line)
        elif len(line) >= len(tick) and set(line) == {"`"}:
            tick = None
        else:
            inside[-1].append(line)
    assert tick is None, "a fence was left open"
    return outside, ["\n".join(block) for block in inside]


def tree(root: Path) -> dict:
    """Every file under root with its size and modification time, to show what a run left alone."""
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(Path(root).rglob("*")) if p.is_file() and not p.is_symlink()}
