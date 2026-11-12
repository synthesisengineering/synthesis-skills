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
    "any message from you", "ping me when",  # an external wait handed back to the principal (2026-11-02)
]
# A wait the session itself announces with nothing armed (2026-11-11: "should be asking you soon", and the turn
# ended; a board message reaches a session only at its next prompt). Read clause by clause (EDGE), a clause is one
# when it has: (a) "I'm" or "we're" waiting or awaiting, unless its "for" or "on" has no object after it ("the terms
# we're waiting on from the vendor" names a thing); (b) "I'll" or "we'll" wait, or hold until something; (c) "I'll"
# or "we'll" with a verb of carrying on and once, when, after, until or as soon as, in either order, or straight
# after "when it finishes" or "should come shortly", which alone are an event or an explanation; (d) "Waiting for",
# "on" or "until", or "Awaiting", opening it or after a colon or dash, unless that is the sentence's subject
# ("waiting for a runner was the cause"). Phrases read anywhere in a reply sent back 15 of 34 that need no watcher
# and passed 9 of 17 waits (review, 2026-11-12). THEIRS, the principal's own next move ("you" as the one who acts,
# "your" before an act of theirs), exempts only the clause it stands in. Config `wait_phrases` adds plain phrases.
_ME, _SOON, _WHEN = r"\b(?:i|we)", r"(?:(?:still|now|just|currently) )?", r"\b(?:once|when|after|until|as soon as)\b"
_WILL = _ME + r"(?:['’]ll| will) " + _SOON
_GO = r"(?:continue(?! to\b)|resume|proceed|pick \w+(?: back)? up|finish|merge|follow up|(?:report|check|come|get) back|let you know)\b"
_SUBJECT = (r"(?!(?: (?!(?:that|which|who|when|it|they|we|i)\b)[\w'’-]+){1,6}? "
            r"(?:is|was|are|were|has|had|can|could|would|cause[sd]|took|takes|costs?)\b)")
WAITS = re.compile(
    "(?i)" + _ME + r"(?:['’]m| am|['’]re| are) " + _SOON + r"a?waiting\b(?! (?:for|on)(?: you\b| from\b|\W*$))"
    "|" + _WILL + r"(?:(?:be|keep|have to|need to) )?(?:wait(?:ing)?\b|hold(?:ing)?\b(?=.{0,160}?\b(?:until|till)\b))(?! (?:for|on) you\b)"
    "|" + _WILL + _GO + ".{0,160}?" + _WHEN + "|" + _WHEN + ".{0,160}?" + _WILL + _GO
    + r"|\b(?:(?:when|once) it (?:lands|finishes|returns|arrives)|should (?:come|arrive) shortly),?(?: and)?(?: then)? " + _WILL
    + r"|(?:^\W*|[:—–] ?| --? )" + _SOON + r"(?:waiting (?:(?:for|on)\b(?! you\b)" + _SUBJECT + r"|until\b)|awaiting\b" + _SUBJECT + ")")
THEIRS = re.compile(
    r"(?i)\b(?:from|until|till|once|when|after|as soon as) you\b|\bfor you to\b"
    r"|\byou (?:promised|owe|decide|choose|pick|prefer|want|approve|confirm|say)\b|\byour (?:next (?:message|prompt)"
    r"|(?:(?:next|final|explicit|written) )?(?:answers?|repl(?:y|ies)|response|go(?:-ahead)?|word|codes?|approval|decision"
    r"|confirmation|yes|ok(?:ay)?|input|review|call|choice|ruling|sign-off|permission|instructions?|direction|feedback|guidance"
    r"|clarification|consent|preference|selection|pick|verdict|signal|thoughts|nod|say-so|green light|thumbs-up))(?![\w-])")
MARKS = re.compile(r"^[ \t]*>.*|[*_#]+|^[ \t]*(?:[-+•]|\d+[.)])[ \t]+", re.M)  # a quoted line; emphasis, heading and list marks
EDGE = re.compile(r"(?<=[.!?])\s+|;|(?<![:\s])\s*\n\s*")  # a sentence's or a line's end, a semicolon; after a colon the line runs on
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


def unarmed_wait(reply: str, payload: dict, config: dict) -> list[str]:
    """The words with which a reply announces the session's own wait that nothing will end: no live `synthesis wait`
    of this session, no autopilot run it owns. A clause that awaits the principal's own next move is no such wait,
    and a reply that ends by asking them has none."""
    plain = MARKS.sub("", QUOTED.sub(" ", CODE.sub(" ", reply))).strip()
    forms = [WAITS] + [re.compile(rf"(?i)\b{re.escape(str(p))}\b") for p in config.get("wait_phrases") or [] if str(p).strip()]
    hits = {m.group(0).lower().strip(" :—–-") for clause in ([] if plain.endswith("?") else EDGE.split(plain))
            for text in [" ".join(clause.split())] for form in forms for m in form.finditer(text) if not THEIRS.search(text, m.start())}
    if not hits:
        return []
    from synthesis import autopilot, paths, wait
    session = paths.session_id(payload)
    return [] if session and (wait.live(session) or autopilot.brief(payload)) else sorted(hits)


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
    waits = unarmed_wait(reply, payload, config)
    if waits:
        problems.append("this reply announces a wait (" + ", ".join(f'"{w}"' for w in waits) + ") and nothing is armed to end "
                        "it: a board message or a finished job reaches this seat only at its next prompt. Arm the lightest "
                        "watcher that fits (`synthesis wait message`, `file` or `run`, as a background task where the "
                        "harness wakes on one; `synthesis wait note` for a timer the harness holds) and say what is armed, "
                        "for how long and what wakes the seat; or ask the principal, with a recommendation, where a "
                        "watcher's cost is in doubt; or say plainly that nothing wakes this seat until they prompt it.")
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
