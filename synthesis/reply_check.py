"""Turn-end check of the agent's final reply (ruling S15, R4).

Blocks a reply once when it uses lazy-shortcut phrasing or quotes someone with
words that appear nowhere in this session's record, and, when the config sets
`reply_file_links`, when it names a file without a clickable absolute-path
markdown link (a bare name or a relative path does not resolve for the reader).
Phrases inside quotation marks or code are exempt, so naming a rule doesn't trip it. Never blocks twice
in a row and lets the reply through on any internal error: a turn-end check
that fails closed loops forever.
"""

from __future__ import annotations

import json
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


FILE = re.compile(r"(?<![\w/.@~-])(?:~?/|\.{1,2}/)?(?:[\w.-]+/)*[\w-][\w.-]*\.(?:md|py|js|ts|tsx|jsx|mjs|json|ya?ml"
                  r"|toml|sh|bash|zsh|html|css|astro|txt|csv|sql|rb|go|rs|java)(?::\d+)?(?![\w/-])(?!\.\w)")
LINK = re.compile(r"\[[^\]\n]*\]\(\s*<?([^()<>\s]*)>?(?:\s+\"[^\"]*\")?\s*\)")
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+|\bmailto:\S+", re.I)
FRAMEWORK = re.compile(r"[A-Z]\w*\.js")  # Node.js, Next.js: names, not files


def unlinked_files(reply: str) -> list[str]:
    """File names in a reply that are not a markdown link to an absolute path. Code spans,
    fenced blocks and URLs are not references; a link whose target is relative fails."""
    text = CODE.sub(" ", reply)
    bad = [t for t in LINK.findall(text) if t and not re.match(r"[a-z][a-z0-9+.-]*:|[/#]", t, re.I)]
    text = URL.sub(" ", LINK.sub(" ", text))
    bad += [m.group(0) for m in FILE.finditer(text) if not FRAMEWORK.fullmatch(m.group(0))]
    return list(dict.fromkeys(bad))


def shortcut_hits(reply: str, extra: list[str]) -> list[str]:
    plain = QUOTED.sub(" ", CODE.sub(" ", reply)).lower()
    return sorted({p for p in DEFAULT_PHRASES + [e.lower() for e in extra] if re.search(rf"\b{re.escape(p)}\b", plain)})


def _probe(quote: str) -> bytes:
    """A distinctive plain-ASCII run of the quote, which survives JSON escaping in a transcript."""
    return " ".join(re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", quote)[:6]).encode("ascii", "ignore")


def unsourced_quotes(reply: str, transcript_path: str | None) -> list[str]:
    quotes = [a or b for a, b in ATTRIBUTED.findall(CODE.sub(" ", reply))]
    if not quotes or not transcript_path:
        return []
    with open(transcript_path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as record:
        probes = [(quote, _probe(quote)) for quote in quotes]
        return [quote[:80] for quote, probe in probes if len(probe) >= 12 and record.find(probe) == -1]


CALENDAR_WRITE = re.compile(r"(?:create|update|manage|delete|move|respond_to)_event$")
CALENDAR_READ = re.compile(r"(?:get|list|search|list_all)_events?$|query_freebusy$")


def unread_calendar_writes(transcript_path: str | None, tail: int = 2_000_000) -> list[str]:
    """Calendar writes this turn that no calendar read followed (2026-10-27: moving a series revived a meeting
    canceled at its old hour, and nobody looked). Reads the tail of a Claude Code transcript; other shapes find none."""
    if not transcript_path:
        return []
    with open(transcript_path, "rb") as handle:
        handle.seek(max(0, handle.seek(0, 2) - tail))
        chunk = handle.read()
    if b"_event" not in chunk:
        return []
    calls, failed = [], set()
    for line in chunk.splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("message"), dict):
            continue
        content = entry["message"].get("content")
        parts = [p for p in content if isinstance(p, dict)] if isinstance(content, list) else []
        if entry.get("type") == "user" and (isinstance(content, str) or any(p.get("type") == "text" for p in parts)):
            calls, failed = [], set()  # the principal's prompt starts a new turn
        calls += [(p.get("id"), str(p.get("name", ""))) for p in parts if p.get("type") == "tool_use"]
        failed |= {p.get("tool_use_id") for p in parts if p.get("type") == "tool_result" and p.get("is_error")}
    pending = []
    for ident, name in calls:
        pending = [] if CALENDAR_READ.search(name) else pending + (
            [name.rsplit("__", 1)[-1]] if CALENDAR_WRITE.search(name) and ident not in failed else [])
    return pending


def check(payload: dict, config: dict) -> str | None:
    reply = str(payload.get("last_assistant_message") or "")
    if payload.get("stop_hook_active") or not reply:
        return None
    problems = []
    hits = shortcut_hits(reply, list(config.get("shortcut_phrases", [])))
    if hits:
        problems.append("lazy-shortcut phrasing: " + ", ".join(f'"{h}"' for h in hits)
                        + ". Do the work or name the real blocker instead of deferring it.")
    files = unlinked_files(reply) if config.get("reply_file_links") else []
    if files:
        problems.append("files named without a clickable link: " + ", ".join(files[:6])
                        + ". Write each as [name](/absolute/path/to/file); a bare name or relative path does not open.")
    writes = unread_calendar_writes(payload.get("transcript_path"))
    if writes:
        problems.append(f"the calendar changed this turn ({', '.join(sorted(set(writes)))}) and nothing read it back. "
                        "Read the principal's calendar for today and every date the change touched before reporting.")
    missing = unsourced_quotes(reply, payload.get("transcript_path"))
    if missing:
        problems.append("quotes not found in this session's record: " + "; ".join(f'"{q}"' for q in missing)
                        + ". Quote only what a tool surfaced this session, or remove the quote.")
    return "Before this reply goes out, revise it: " + " ".join(problems) if problems else None
