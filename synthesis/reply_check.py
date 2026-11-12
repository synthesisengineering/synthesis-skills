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
# and passed 9 of 17 waits (review, 2026-11-12). THEIRS, the principal's own next move, exempts only the clause it
# stands in. Config `wait_phrases` adds plain phrases.
# "once" is a conjunction here, not a count: not "at once", "once more", "once on staging", "once a day".
_ONCE = r"(?<!\bat )once(?! (?:more|again|a|an|per|every|each|or|and|only|on|in|at|for|with|to|by|upon|daily|weekly)\b)"
_ME, _WHEN = r"\b(?:i|we)", r"\b(?:" + _ONCE + r"|when|after|until|as soon as|the moment)\b"
# Ordinary grammar between a subject and its verb (review round 2): any run of adverbs ("currently still", "then",
# "simply"; "not" and "no longer" are none), helping verbs ("continue to wait", "be able to resume", "go ahead and
# merge"), "going to" and "need to" for "will", and a subject left out ("Will report back", "I pushed it and will").
_SOON = (r"(?:(?:still|now|just|also|then|again|already|here|both|all|each|right now|at this point|stuck|blocked|idle"
         r"|(?!hardly|barely|rarely|scarcely)\w+ly),? ){0,3}")
_ASIDE = r"(?:, [^,;:]{1,40},|,)? "  # words between commas after the helping verb: "I will, for my part, continue"
_AM = r"(?:" + _ME + r"(?:['’]m| am|['’]re| are)|\b(?:and|but) am)" + _ASIDE + _SOON
_WILL = (r"(?:" + _ME + r"(?:['’]ll| will| shall|(?:['’]m| am|['’]re| are) going to)|^\W*will|" + _ME
         + r"\b[^:]{0,120}?\b(?:and|but|then) will)" + _ASIDE + _SOON)
_MUST = r"(?:" + _WILL + "|" + _ME + r" (?:(?:still|now|just|also|then|\w+ly) )?(?:(?:need|have|plan|intend|want) to|must) )"
_HELP = r"(?:(?:be|keep|keep on|go on|carry on|continue to|have to|need to|be able to|go ahead and) )*"
_GO = (r"(?:continue(?! to\b)|resume|proceed|pick (?:[\w'’-]+ ){1,4}?(?:back )?up|finish|merge|confirm|follow up|circle back"
       r"|(?:report|check|come|get) back|let you know|(?:update|notify|tell|ping|message) you)\b")
# The session itself ("I", not the "we" of advice) with any verb before an event that is still to come: "I'll send it as soon
# as the run finishes", "once their quote arrives, I'll update the sheet", "I'll check them when it's done".
_I = (r"(?:\bi(?:['’]ll| will| shall|(?:['’]m| am) going to)|\bwe(?:['’]ll| will)(?! (?:want|need|have|be|see|know|likely|probably)\b)"
      r"|^\W*will|\bi\b[^:]{0,120}?\b(?:and|but|then) will)" + _ASIDE + _SOON)
_THEN = r"(?:" + _ONCE + r"|as soon as(?! (?:possible|practical)\b)|the moment) (?!(?:i|we)\b)(?=\w)"
# After "when" or "after", an arrival is an event to come ("when the second pass comes back"); "when the network is down" is a case.
_COMES = (r"(?:when|after) (?!(?:i|we|a|an|any|each|every|some|no)\b)(?:[\w'’-]+ ){1,5}?(?:comes?|arrives?|lands?|shows? up|finish(?:es)?"
          r"|completes?|returns?|repl(?:y|ies)|responds?|answers?|confirms?|approves?|signs?|accepts?|ships?|delivers?|clears?|posts?"
          r"|settles?|pass(?:es)?|goes (?:green|through|live|out)|reopens?|lifts?|ends?|issues?|renews?|resets?|propagates?|exits?"
          r"|(?:is|are|has been|have been) (?:done|ready|back|in|out|through|over|up|live|green|available|here|\w+ed))\b")
_SAYS = r"(?:(?!\b(?:that|because|since|which|if|whether|what|how|why|where)\b)[^;:]){1,100}?"  # not "I'll note that once ..."
_DONE = (r"(?:when|once|after) (?:it|they|that|this|everything)(?:(?:['’]s|['’]re| is| are| has| have)(?: been)? (?:done|ready"
         r"|finished|completed?|through|over|back|in|up|live|green|available|out|here|merged|published|released)\b| (?:lands?"
         r"|finish(?:es)?|completes?|ends?|returns?|arrives?|pass(?:es)?|comes?)\b| (?:does|do|has|have|is|are)\b(?=\W*$|,))")
# The event in front, after "when" or "after", with any verb: "when the bank confirms, I will record it". An event named with
# "a" or "any" is a rule ("when a build fails, I'll read the first error"), and "after that" is the session's own next step.
_FIRST = (r"^\W*(?:after|when) (?!(?:i|we|a|an|any|each|every|some|no|in|that|this|needed|necessary|possible|asked|prompted)\b)"
          r"[^,;:]{2,100}?,? (?:and )?(?:then )?")
_GOING = (r"(?:resuming|continuing(?! to\b)|proceeding|merging|finishing|following up|circling back|(?:reporting|checking|coming"
          r"|getting) back|picking (?:[\w'’-]+ ){1,4}?(?:back )?up)\b")
_HELD = r"\b(?=.{0,160}?\b(?:until|till)\b)"  # a hold is a wait when it runs until something
# "Waiting for X" is the subject of its sentence, an explanation, when a verb follows X: a helping verb, a verb of effect
# ("blocks", "adds", "takes"), or any verb in -s before its object or "out", "up", "down", "off". The words between may
# hold an infinitive ("the import to release its lock") but nothing that opens another clause (_STOP), so "waiting for
# the reviewer to confirm the fix is right" stays an announcement (review round 2).
_STOP = (r"that|which|who|whom|whose|what|where|why|how|whether|wh\w+ever|when|it|they|we|i|you|he|she|and|but|or|then|so"
         r"|before|after|while|until|till|because|if|as|since|once|though|sure|word|news|notice|proof|signs?|signal"
         r"|confirm\w*"
         r"|(?:say|report|check|tell|decide|see|know|find|show|ensure|learn|hear)s?|verif(?:y|ies)")
_WORD = r"(?: (?!(?:" + _STOP + r")\b)[\w'’/.-]+)"
_EFFECT = (r"(?:take|cost|add|waste|delay|slow|mean|make|block|stall|hurt|help|risk|keep|hold|tie|burn|defeat|prevent|guarantee"
           r"|avoid|hide|explain|account|produce|create|trigger|introduce|require|force|starve|mask|dominate|double)s\b")
_OFTEN = r"(?:(?:never|always|often|usually|only|just|also|still|\w+ly) )?"
_PRED = (_OFTEN + r"(?:(?:is|was|are|were|has|had|can|could|would|will|should|may|might|must|does|did)(?:n['’]t)?\b|cause[sd]\b"
         r"|(?:took|cost|made|meant|(?:stall|block|delay|slow|wast|add)ed)\b|" + _EFFECT + r"|[a-z]+s (?:(?:out|up|down|off|why|how"
         r"|what)\b|(?:a|an|the|its|their|our|every|each|last|next|most|much|many|some|no) [\w'’/.-]+"
         r"(?: (?![\w-]*(?:s|ed)(?=\W*$|[ ,]))[\w'’/.-]+){0,3}?(?=\W*$|,| (?:to|in|on|at|for|by|of|from|with|and|but|so|which|when"
         r"|while|during|than|as|into|across|because|if|until)\b)))")
# After "until", "when", "after" or "before" the words may hold a verb of their own, so "is" makes a subject only before a
# judgment ("waiting until Friday is risky", "resuming after a crash is handled by the checkpoint file"; "waiting until CI is
# green" announces), "can" or "has" only after that verb, "would" or a verb of effect always.
_VALUE = (r"(?:the|a|an|what|why|how|risky|safer?|slow(?:er)?|fast(?:er)?|fine|ok(?:ay)?|expected|standard|normal|common|typical|usual"
          r"|rare|wasteful|pointless|harmless|better|worse|best|wrong|right|correct|costly|expensive|cheaper?|unnecessary|necessary"
          r"|required|recommended|optional|allowed|forbidden|possible|impossible|easy|hard|tricky|trivial|automatic|idempotent"
          r"|handled|managed|covered|supported|controlled|governed|performed|implemented|meant|supposed|intended)\b")
_TAIL = r"(?:" + _WORD + r"| (?:before|after|during|in|on|at))"
_LATER = (_WORD + r"{1,10}?(?:" + _TAIL + r"{0,8}? " + _OFTEN + r"(?:(?:is|was)(?:n['’]t| not)? " + _VALUE
          + r"|(?:would|will|should|may|might|must)(?:n['’]t)?\b|took\b|cost\b|" + _EFFECT + r")| (?!(?:" + _STOP
          + r")\b)(?:is|are|was|were|has|have|had|[a-z]+(?:s|ed))\b" + _WORD + r"{0,6}? " + _OFTEN + r"(?:is|was|can|could|has|does)(?:n['’]t| not)?\b)")
SUBJECT = re.compile("(?i)(?:" + _WORD + r"{1,12}? " + _PRED + "|" + _WORD + r"{0,8}? (?:before|after|while|until|till|when|once)" + _LATER + ")")
UNTIL = re.compile("(?i)" + _LATER)
WAITS = re.compile(  # a clause that opens with the wait is tested as a subject afterwards: group "on" by SUBJECT, "till" by UNTIL
    "(?i)" + _AM + r"(?:a?waiting\b(?! (?:for|on)(?: you\b| from\b|\W*$))|(?:holding|standing by|paus(?:ing|ed))" + _HELD + ")"
    "|" + _MUST + _HELP + r"(?:wait(?:ing)?\b|(?:hold(?:ing)?|stand(?:ing)? by|paus(?:e|ing))" + _HELD + r")(?! (?:for|on) you\b)"
    "|" + _WILL + _HELP + _GO + ".{0,160}?" + _WHEN + "|" + _WHEN + ".{0,160}?" + _WILL + _HELP + _GO
    + r"|\b(?:until|till)\b.{0,160}?(?:" + _MUST + _HELP + r"(?:hold|pause)\b|" + _AM + r"(?:holding|pausing)\b)"
    + "|" + _I + _SAYS + r"\b(?:" + _THEN + "|" + _DONE + "|" + _COMES + r")|\b" + _THEN + r"[^,;:]{0,100},? (?:and )?(?:then )?" + _I
    + r"|\b(?:" + _DONE + r"|should (?:come|arrive) shortly),?(?: and)?(?: then)? " + _WILL + "|" + _FIRST + _I
    + r"|(?:^\W*|[:—–] ?| --? )" + _SOON + r"(?:(?P<on>waiting (?:for|on|to (?:hear|see|get|learn|find out))\b(?! you\b)|awaiting\b)"
    r"|(?P<till>waiting until\b|(?:holding|standing by|pausing)\b.{0,160}?\b(?:until|till)\b|" + _GOING
    + r"[^;:]{0,100}?\b(?:when|after|as soon as|" + _ONCE + r")\b))")
# The principal's own next move is what is awaited: "you" as the one who acts and not in the past ("once you approve";
# "after you approved" and "as you want" are context), or an act of theirs. An act counts where it is the thing
# awaited: after the wait's own word ("for", "on", "until", "once I have"), a colon, a dash or the clause's start, and
# as the head of its phrase. "your review bot", "your code to compile" and "the service to answer your review" name a
# thing of theirs that software acts on (review round 2).
_ACT = (r"answers?|repl(?:y|ies)|response|go(?:-ahead)?|word|approval|decision|confirmation|yes|ok(?:ay)?|input|review|call"
        r"|choice|ruling|sign-off|permission|instructions?|direction|feedback|guidance|clarification|consent|preferences?"
        r"|selection|pick|verdict|signal|thoughts|nod|say-so|green light|thumbs-up|signature|vote|edits|corrections|comments"
        r"|notes|authori[sz]ation|rsvp")
# What only they can supply. With "to" and a verb after it, software is acting on it ("your code to compile").
_THING = r"codes?|headcount|numbers?|figures|dates?|availability|address|details|list|budget|requirements|priorities"
_HEAD = (r"(?=\W*$|[^\w\s-]| (?:of|on|about|for|before|in|at|by|from|with|regarding|as|after|until|since|over|and|or|but|so|then"
         r"|that|whether|if|when|once|while|because|is|are|was|will|would|comes?|arrives?|lands?|reaches|gets|here|there|first"
         r"|now|today|tonight|tomorrow|soon|too|either|again|instead|please|yet|still|also|back|i|we|it|you|not|to{})\b)")
THEIRS = re.compile(
    r"(?i)\b(?:from|by|until|till|once|when(?:ever)?|after|as soon as) you\b"
    r"(?! (?:\w+[^e\W]ed|sent|gave|said|told|chose|wrote|made|did|were|had|got|agreed)\b)|\bfor you to\b"
    r"|(?<!\bas )(?<!\blike )\byou (?:promised|owe|decide|choose|pick|prefer|want|approve|confirm|say)\b"
    r"|\b(?:hear|know|learn|see|find out) (?:back )?(?:which|what|whether|how|when|where|who|if)\b[^,;:]*?(?<!\bto )(?<!\bwith )"
    r"(?<!\babout )\byou\b"  # a question the principal answers: "to hear which date works for you"
    r"|\b(?:your (?:move|turn)\b|(?:up|over) to you\b|in your court\b|(?:is|are) yours\b)"  # the turn handed over in so many words
    r"|^\W*(?:please )?(?:(?:send|tell|give|show) me\b|let me know\b|(?:paste|type|reply|forward|share|confirm)\b(?![\w-]))"  # or asked for
    r"|(?:\b(?:for|on|until|till|once|when|after|as soon as|await(?:ing)?|needs?|is|are|was) |['’]s |(?:[:—–]| -) |^\W*"
    r"|\b(?:until|till|once|when|after|as soon as) (?:i|we)(?:['’]ve| have)? (?:have|get|got|receive[sd]?|see|hear|read|know|learn) "
    r"|\bto (?:have|get|receive|see|hear|read|know|learn) )(?:(?:only|just|both|either|also|still|now) )?"
    r"your (?:next (?:message|prompt)\b|(?:(?:next|final|explicit|written|own|" + _ACT + "|" + _THING + r") )*(?:(?:" + _ACT + ")"
    + _HEAD.format("") + "|(?:" + _THING + ")" + _HEAD.format(" (?:proceed|continue|go ahead|move forward|start|begin)") + "))")
FRONT = ("until", "till", "once", "when", "after", "as soon as", "your move", "your turn", "up to you", "over to you", "in your court",
         "is your", "'s your", "’s your", "are yours")  # how a move of theirs opens when it stands in front of the wait and counts
OPEN = re.compile(r"(?i)(?:(?<=awaiting)|(?<=await)) (?:on|in|at|from|with|about|regarding|before|by)\b.*$"  # nothing is named after
                  r"|(?: (?:for|on))?(?: (?:right now|now|here|today|still|at this point))?\W*$")           # the wait
BACK = re.compile(r"(?i)(?: (?:for|on))?(?: (?:that|this|it|them|those|both|here|now))?"            # or only a word that points back
                  r"(?:,? (?:before|so|then|and nothing else|only|alone)\b.*)?\W*$|.{0,80}?\b(?:until|till|once|when|after|as soon as) "
                  r"(?:(?:i|we)(?:['’]ve)? (?:have|get|got|receive|hear|see|know) )?(?:it|that|them|those|then)\W*$")
LEAD = re.compile(r"(?i)(?:(?:and|so|but|now|then|until then|till then|meanwhile),? )?")           # before a wait that opens its clause
MARKS = re.compile(r"^[ \t]*>.*|[*_#]+|^[ \t]*(?:[-+•]|\d+[.)])[ \t]+", re.M)  # a quoted line; emphasis, heading and list marks
EDGE = re.compile(r"(?<=[.!?])\s+|;|(?<![:\s])\s*\n\s*")  # a sentence's or a line's end, a semicolon; after a colon the line runs on
# Code and quoted text are not the reply's own words: a fence of three or more backticks, or of tildes at a line's start,
# up to the same fence; inline code; double quotes; single quotes, which open after a space or a bracket and close
# before one, so the apostrophe in "the caterer's estimate" ends nothing (review round 2).
CODE = re.compile(r"(?:(`{3,})|^[ \t]*(~{3,})).*?(?:\1|\2)|``[^\n]*?``|`[^`\n]*`", re.S | re.M)
QUOTED = re.compile(r"\"[^\"\n]{1,400}\"|“[^”\n]{1,400}”|(?<![\w'’])['‘](?=[^\s\d])[^\n]{0,400}?(?<=\S)['’](?![\w'’])")
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


def _explains(text: str, m: re.Match) -> bool:
    """Is the wait that opens this clause the subject of its sentence ("waiting for a lock blocks a thread")?"""
    opened = m.groupdict()
    return bool(opened.get("on") and SUBJECT.match(text, m.end()) or opened.get("till") and UNTIL.match(text, m.end()))


def _theirs(text: str, m: re.Match, before: str) -> bool:
    """Is the principal's own next move what this wait awaits? It is when it stands from the wait's words onward; in
    front of them as a condition ("until you choose, I'll wait", "once you sign, I'll wait for the bank"); or anywhere
    in front when nothing is named after the wait ("your answer is the only thing I'm awaiting"). What stands in front
    otherwise is context ("your review is filed and I'm waiting on CI"). A wait that opens its clause and names nothing,
    or only "that" or "it", awaits what the clause before it names: their move ("your approval is all that is left; I'm
    waiting on that"), a request to them, or a question."""
    if THEIRS.search(text, m.start()) or (before and LEAD.fullmatch(text, 0, m.start()) and BACK.match(text, m.end())
                                          and (before.endswith("?") or THEIRS.search(before))):
        return True
    bare = m.group(0).lower().endswith(("wait", "waiting")) and OPEN.match(text, m.end())
    return any(bare or t.group(0).lower().startswith(FRONT) for t in THEIRS.finditer(text, 0, m.start()))


def unarmed_wait(reply: str, payload: dict, config: dict) -> list[str]:
    """The words with which a reply announces the session's own wait that nothing will end: no live `synthesis wait`
    of this session, no autopilot run it owns. A clause that awaits the principal's own next move is no such wait,
    and a reply that ends by asking them has none."""
    plain = MARKS.sub("", QUOTED.sub(" something ", CODE.sub(" something ", reply))).strip()  # a name set aside is still a thing awaited
    forms = [WAITS] + [re.compile(rf"(?i)\b{re.escape(str(p))}\b") for p in config.get("wait_phrases") or [] if str(p).strip()]
    clauses = [] if plain.endswith("?") else [c for c in (" ".join(part.split()) for part in EDGE.split(plain)) if c]
    hits = {m.group(0).lower().strip(" :—–-") for at, text in enumerate(clauses) for form in forms for m in form.finditer(text)
            if not _explains(text, m) and not _theirs(text, m, clauses[at - 1] if at else "")}
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
