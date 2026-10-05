"""Turn-end check of the agent's final reply (ruling S15, R4).

Blocks a reply once when it uses lazy-shortcut phrasing or quotes someone with
words that appear nowhere in this session's record. Phrases inside quotation
marks or code are exempt, so naming a rule doesn't trip it. Never blocks twice
in a row and lets the reply through on any internal error: a turn-end check
that fails closed loops forever.
"""

from __future__ import annotations

import mmap
import re

DEFAULT_PHRASES = [
    "for now", "as a first pass", "can revisit later", "revisit later", "future fix needed",
    "that's a larger task", "not a pain point today", "doesn't bite hard", "not a real concern at current volume",
    "the only real con is", "won't matter until", "that's a theoretical concern", "in the interim",
    "document-and-defer", "execute or defer", "defer this", "deferred to", "out of scope for now",
]
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
QUOTED = re.compile(r"\"[^\"\n]{1,400}\"|“[^”\n]{1,400}”")
ATTRIBUTED = re.compile(
    r"\b(?:said|says|wrote|writes|replied|asked|told \w+|warned|noted|added)\s*[:,]?\s*(?:\"([^\"\n]{12,400})\"|“([^”\n]{12,400})”)",
    re.I)


def shortcut_hits(reply: str, extra: list[str]) -> list[str]:
    plain = QUOTED.sub(" ", CODE.sub(" ", reply)).lower()
    return sorted({p for p in DEFAULT_PHRASES + [e.lower() for e in extra] if re.search(rf"\b{re.escape(p)}\b", plain)})


def _probe(quote: str) -> bytes:
    """A distinctive plain-ASCII run of the quote, which survives JSON escaping in a transcript."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", quote)
    run = " ".join(words[:6])
    return run.encode("ascii", "ignore")


def unsourced_quotes(reply: str, transcript_path: str | None) -> list[str]:
    quotes = [a or b for a, b in ATTRIBUTED.findall(CODE.sub(" ", reply))]
    if not quotes or not transcript_path:
        return []
    missing = []
    with open(transcript_path, "rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as record:
            for quote in quotes:
                probe = _probe(quote)
                if len(probe) >= 12 and record.find(probe) == -1:
                    missing.append(quote[:80])
    return missing


def check(payload: dict, config: dict) -> str | None:
    if payload.get("stop_hook_active"):
        return None
    reply = str(payload.get("last_assistant_message") or "")
    if not reply:
        return None
    problems = []
    hits = shortcut_hits(reply, list(config.get("shortcut_phrases", [])))
    if hits:
        problems.append("lazy-shortcut phrasing: " + ", ".join(f'"{h}"' for h in hits)
                        + ". Do the work or name the real blocker instead of deferring it.")
    missing = unsourced_quotes(reply, payload.get("transcript_path"))
    if missing:
        problems.append("quotes not found in this session's record: " + "; ".join(f'"{q}"' for q in missing)
                        + ". Quote only what a tool surfaced this session, or remove the quote.")
    if not problems:
        return None
    return "Before this reply goes out, revise it: " + " ".join(problems)
