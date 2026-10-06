"""R4: one public shortcut-phrase catalog.

The Stop hook (synthesis/reply_check.py) keeps a short built-in list so it
stays fast; the anti-shortcuts skill's costume-catalog.json is the one public
catalog. Every built-in phrase must be caught by a catalog entry, so the two
cannot drift apart.
"""

import json
import re
from pathlib import Path

from synthesis import reply_check

CATALOG = Path(__file__).resolve().parents[1] / "skills" / "synthesis-anti-shortcuts" / "costume-catalog.json"


def _patterns():
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))["phrases"]
    return {e["id"]: re.compile(e["phrase"] if e.get("match") == "regex" else re.escape(e["phrase"]), re.I)
            for e in entries}


def test_every_built_in_reply_phrase_is_in_the_catalog():
    patterns = _patterns()
    missing = [p for p in reply_check.DEFAULT_PHRASES if not any(rx.search(p) for rx in patterns.values())]
    assert missing == [], f"add these to {CATALOG.name}: {missing}"


def test_the_check_catches_a_phrase_missing_from_the_catalog():
    patterns = _patterns()
    assert not any(rx.search("a phrase no catalog has") for rx in patterns.values())
