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
# when it has: "I'm" or "we're" waiting or awaiting, unless its "for" or "on" has no object after it ("the terms we're
# waiting on from the vendor" names a thing); "I'll" or "we'll" wait, or hold, pause or stand by until something; a
# future with a verb of carrying on (_GO) and once, when, after, until or as soon as, in either order; the session's
# own future with any verb and an event still to come (_THEN, _DONE, _COMES, _FIRST); "Waiting for", "on" or "until",
# "Awaiting", "Holding ... until" or "Resuming when" opening a sentence, unless that is the sentence's subject (SUBJECT,
# UNTIL). Phrases read anywhere in a reply sent back 15 of 34 that need no watcher and
# passed 9 of 17 waits (review round 1, 2026-11-12); round 2 found 6 of 32 and 5 of 20, each a class of grammar, and
# seven more fresh lists found the rest of what is read here. THEIRS, the principal's own next move, exempts the
# clause it stands in (_theirs says where in it). Config `wait_phrases` adds plain phrases.
# Thirty days of recorded turn-ending replies (4,842, on 2026-11-12) then showed what invented sentences had not: of 815
# replies read as a wait, 586 were turns the harness itself held (held_by_harness), and of the 202 others, read one by
# one, 96 were the session's own wait. The rest awaited the principal's own next step (STAGED, CODED, ASKED, "your"),
# were a list of open loops under a label, a heading, a table or a fragment (TABLED, LABEL, a sentence's first clause
# only), sat in a message drafted for someone else (STAGED), or stated a rule (RULE).
# "once" is a conjunction here, not a count: not "at once", "once more", "once on staging", "once a day".
_ONCE = r"(?<!\bat )once(?! (?:more|again|a|an|per|every|each|or|and|only|on|in|at|for|with|to|by|upon|daily|weekly)\b)"
# After the conjunction, "I" or "we" with a verb of the session's own is its next step and no event ("I will resume after I
# update the snapshots"). With a verb of receiving the thing still has to come ("once I have it", "when I hear back"), and
# "when I can" waits to be able (the one wait in thirty days of recorded replies that turns on this form is of that kind).
_GETS = (r"(?:(?: do| finally| actually| also| then)? (?:get(?! (?:to|back to|started|going|around|on with|into|through|done|a (?:chance|moment|minute))\b)"
         r"|receive|hear|see|know|learn|find out)|(?:['’]ve| have)(?: \w+ly| also)? (?:got|gotten|received|heard|seen|learned|learnt|found out)"
         r"| have (?!(?:time|a (?:chance|moment|minute))\b)(?:it|them|that|this|those|these|the|a|an|its|their|his|her|your|my|our|both|all|some|any|more|enough"
         r"|word|news|confirmation|access|approval|permission|feedback|results|what|everything|something|[\w-]+['’]s)"
         r"|(?:['’]m| am|['’]re| are) (?:told|notified|given|sent|informed|pinged|unblocked|able to)| can)\b")
_EVENT = r"(?! (?:i|we)\b(?!" + _GETS + "))"
_ME, _WHEN = r"\b(?:i|we)", r"\b(?:" + _ONCE + r"|when|after|until|as soon as|the (?:moment|minute|instant))\b" + _EVENT
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
_THEN = r"(?:" + _ONCE + r"|as soon as(?! (?:possible|practical)\b)|the (?:moment|minute|instant)) (?!(?:i|we)\b)(?=\w)"
# After "when" or "after", an arrival is an event to come ("when the second pass comes back"); "when the network is down" is a case.
_COMES = (r"(?:when|after|the (?:day|minute|instant)) (?!(?:i|we)\b)(?:[\w'’-]+ ){1,5}?(?:comes?|arrives?|lands?|shows? up"
          r"|opens?(?: up)?|frees? up|becomes? (?:available|free)|finish(?:es)?"
          r"|completes?|returns?|repl(?:y|ies)|responds?|answers?|confirms?|approves?|signs?|accepts?|ships?|delivers?|clears?|posts?"
          r"|settles?|pass(?:es)?|goes (?:green|through|live|out)|reopens?|lifts?|ends?|issues?|renews?|resets?|propagates?|exits?"
          r"|(?:is|are|has been|have been) (?:done|ready|back|in|out|through|over|up|live|green|available|here|\w+ed))\b")
# Not "I'll note that once ..." (how something behaves), and not "I will not ...".
_SAYS = r"(?!(?:not|never|no longer)\b)(?:(?!\b(?:that|because|since|which|if|whether|what|how|why|where)\b)[^;:]){1,100}?"
_DONE = (r"(?:when|once|after|as soon as|the (?:day|moment|minute|instant)) (?:it|they|that|this|everything)(?:(?:['’]s|['’]re"
         r"| is| are| has| have)(?: been)? (?:done|ready|finished|completed?|through|over|back|in|up|live|green|available|out|here"
         r"|merged|published|released)\b| (?:lands?|finish(?:es)?|completes?|ends?|returns?|arrives?|pass(?:es)?|comes?)\b"
         r"| (?:does|do|has|have|is|are)\b(?=\W*$|,))")
# The event in front, after "when" or "after", with any verb: "when the bank confirms, I will record it". An event named with
# "a" or "any" is a rule ("when a build fails, I'll read the first error"), and "after that" is the session's own next step.
_FIRST = (r"^\W*(?:after|when) (?!(?:i|we|a|an|any|each|every|some|no|in|that|this|needed|necessary|possible|asked|prompted)\b)"
          r"[^,;:]{2,100}?,? (?:and )?(?:then )?")
_GOING = (r"(?:resuming|continuing(?! to\b)|proceeding|merging|finishing|following up|circling back|(?:reporting|checking|coming"
          r"|getting) back|picking (?:[\w'’-]+ ){1,4}?(?:back )?up)\b")
_HELD = r"\b(?=.{0,160}?\b(?:until|till)\b" + _EVENT + ")"  # a hold is a wait when it runs until something
# "Waiting for X" is the subject of its sentence, an explanation, when a verb follows X: a helping verb, a verb of effect
# ("blocks", "adds", "takes"), or any verb in -s before its object or "out", "up", "down", "off". The words between may
# hold an infinitive ("the import to release its lock") but nothing that opens another clause (_STOP), so "waiting for
# the reviewer to confirm the fix is right" stays an announcement (review round 2).
_STOP = (r"that|which|who|whom|whose|what|where|why|how|whether|wh\w+ever|when|it|they|we|i|you|he|she|and|but|or|then|so"
         r"|before|after|while|until|till|because|if|as|since|once|though")
_SAID = (r"sure|word|news|notice|proof|signs?|signal|confirm\w*|(?:say|report|check|tell|decide|see|know|find|show|ensure|learn"
         r"|hear)s?|verif(?:y|ies)")  # what may open a clause of its own: "to confirm the fix is right"
_WORD, _ANY = r"(?: (?!(?:" + _STOP + "|" + _SAID + r")\b)[\w'’/.-]+)", r"(?: (?!(?:" + _STOP + r")\b)[\w'’/.-]+)"
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
          + "|" + _SAID + r")\b)(?:is|are|was|were|has|have|had|[a-z]+(?:s|ed))\b" + _WORD + r"{0,6}? " + _OFTEN
          + r"(?:is|was|can|could|has|does)(?:n['’]t| not)?\b|" + _ANY + r"{1,14}? " + _OFTEN + r"(?:took\b|cost\b|" + _EFFECT + "))")
SUBJECT = re.compile("(?i)(?:" + _WORD + r"{1,12}? " + _PRED + "|" + _WORD + r"{0,8}? (?:before|after|while|until|till|when|once)"
                     + _LATER + ")")
UNTIL = re.compile("(?i)" + _LATER)
WAITS = re.compile(  # a clause that opens with the wait is tested as a subject afterwards: group "on" by SUBJECT, "till" by UNTIL
    "(?i)" + _AM + r"(?:a?waiting\b(?! (?:for|on)(?: you\b| from\b|\W*$))|(?:holding|standing by|paus(?:ing|ed))" + _HELD + ")"
    "|" + _MUST + _HELP + r"(?:wait(?:ing)?\b|(?:hold(?:ing)?|stand(?:ing)? by|paus(?:e|ing))" + _HELD + r")(?! (?:for|on) you\b)"
    "|" + _WILL + _HELP + _GO + ".{0,160}?" + _WHEN + "|" + _WHEN + ".{0,160}?" + _WILL + _HELP + _GO
    + r"|\b(?:until|till)\b" + _EVENT + ".{0,160}?(?:" + _MUST + _HELP + r"(?:hold|pause)\b|" + _AM + r"(?:holding|pausing)\b)"
    + "|" + _I + _SAYS + r"\b(?:" + _THEN + "|" + _DONE + "|" + _COMES + r")|\b" + _THEN + r"[^,;:]{0,100},? (?:and )?(?:then )?" + _I
    + r"|\b(?:" + _DONE + r"|should (?:come|arrive) shortly),?(?: and)?(?: then)? " + _WILL + "|" + _FIRST + _I
    + r"|^\W*" + _COMES + r"[^,;:]{0,80}?,? (?:and )?(?:then )?" + _I + "|" + _ME + r"(?:['’]ve| have) (?:paused|held)" + _HELD
    + r"|^\W*" + _SOON + r"(?:(?P<on>waiting (?:for|on|to (?:hear|see|get|learn|find out))\b(?! you\b)|awaiting\b)"
    r"|(?P<till>waiting until\b|(?:holding|standing by|pausing)\b.{0,160}?\b(?:until|till)\b" + _EVENT + "|" + _GOING
    + r"[^;:]{0,100}?\b(?:when|after|as soon as|" + _ONCE + r")\b" + _EVENT + "))")
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
         r"|that|whether|if|when|once|while|because|between|among|around|concerning|within|is|are|was|will|would|comes?|arrives?"
         r"|lands?|reaches|gets|here|there|first|now|today|tonight|tomorrow|soon|too|either|again|instead|please|yet|still|also"
         r"|back|i|we|it|you|not|to{})\b)")
_SOFT = (r"bot|tests?|suite|build|pipeline|ci|job|branch|pr|pull request|deploy\w*|server|service|script|container|cluster|repo\w*"
         r"|runner|workflow|linter|checks?|app|site|machine|database|queue|cache|index|import|export|sync|upload|download|migration"
         r"|run|process|program|agent|session|code to")
# Straight after the wait's own word, "your" and a thing named in a few words is theirs to give ("your sign-in retry", "your
# two answers before I write"), unless software or someone else acts on it ("your tests", "your registrar to release",
# "your lawyer's comments") or it sits further on ("the hold on your card").
YOURS = re.compile(r"(?i)(?: (?:for|on)(?= )|(?<= for)|(?<= on)) (?:(?:only|just|both|either|also|still|now) )?your (?!(?:[\w-]+ ){0,3}?(?:" + _SOFT + r")\b)"
                   r"(?:(?!to\b)[\w-]+ ){0,3}?(?!to\b)[\w-]+(?=\W*$|[,.;:!?)]| (?:of|on|about|for|before|in|at|by|from|with|regarding|as|after|until|since|and"
                   r"|or|but|so|then|that|whether|if|when|once|while|because|is|are|was|here|first|now|today|tonight|tomorrow|soon|yet|still)\b)")
THEIRS = re.compile(
    r"(?i)\b(?:from|by|until|till|once|when(?:ever)?|after|as soon as) you\b"
    r"(?! (?:\w+[^e\W]ed|sent|gave|said|told|chose|wrote|made|did|were|had|got|agreed)\b)|\bfor you to\b"
    r"|(?<!\bas )(?<!\blike )\byou (?:promised|owe|decide|choose|pick|prefer|want|approve|confirm|say)\b"
    r"|\b(?:hear|know|learn|see|find out) (?:back )?(?:which|what|whether|how|when|where|who|if)\b[^,;:]*?(?<!\bto )(?<!\bwith )"
    r"(?<!\babout )\byou\b"  # a question the principal answers: "to hear which date works for you"
    r"|\b(?:your (?:move|turn)\b|(?:up|over) to you\b|in your court\b|(?:is|are) yours\b)"  # the turn handed over in so many words
    r"|(?:^\W*|\b(?:and|then) )(?:please )?(?:(?:send|tell|give|show) me\b|let me know\b)"  # or asked for: a request put to them
    r"|^\W*(?:please )?(?:(?:paste|type|reply|forward|share|confirm)\b(?![\w-])|(?:read|review|check|choose|pick|decide|approve|sign"
    r"|answer|select) (?:the|this|that|these|those|it|them|which|whether|one|both|my|our|your)\b)"
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
EDGE = re.compile(r"(?<=[.!?])\s+|(?<![:\s])\s*\n\s*")  # a sentence's or a line's end; after a colon the line runs on
# A reply that hands the turn to the principal awaits their answer, whatever else it waits for: it offers an approval code
# to type, or asks them to act in so many words. A code named as used, spent or replaced offers nothing: SPENT reads the
# words straight after it ("code 1abcde was consumed earlier", "(3e7b10) has expired"), USED those straight before it ("you
# typed approve 4a0c2d", "don't use the old codes ..."). The text between a BEGIN line and an END line is set aside as
# quoted text is, a message staged for their go or a record; beside one, a wait for it to be sent (SENT) awaits their go.
STAGED = re.compile(r"(?m)^[ \t>*_-]*BEGIN[ \t*_-]*$[\s\S]*?^[ \t>*_-]*END[ \t*_-]*$")
_CODE = r"([0-9][0-9a-f]{5})"
CODED = re.compile(r"(?i)\bapprove\W{1,3}" + _CODE + r"\b|\bcodes?\b[^.\n]{0,60}?\b" + _CODE + r"\b|(?:\*\*|`)" + _CODE + r"(?:\*\*|`)?:")
SPENT = re.compile(r"(?i)[)`*:\]]*,? (?:(?:which|that) )?(?:(?:has|had|have|was|were|is|are|got) )?(?:(?:already|since|now|just|then|also) )?(?:been )?"
                   r"(?:expired|lapsed|consumed|used|spent|redeemed|typed|entered|taken|applied|replaced|superseded|voided|cancell?ed|withdrawn|revoked"
                   r"|no longer|ran out|timed out|went (?:out|through)|void|invalid|stale|gone|dead)\b")
USED = re.compile(r"(?i)(?:\b(?:earlier|old|older|previous|prior|former|expired|spent|used|dead|stale|first) (?:approval )?codes?"
                  r"(?:[\s`*(),:–—-]|\band\b|\bor\b|\b[0-9][0-9a-f]{5}\b)*|\b(?:typed|entered|used|ran|gave|sent)\b[^.;:,\n]{0,20})$")
SENT = re.compile(r"(?i)\b(?:once|when|after|as soon as|until) (?:it|that|this|they|both|each|the (?:message|note|email|reply|draft|post|send)s?)"
                  r"(?:['’]s|['’]re| is| are| has been| have been| goes| go| gets?) (?:sent|out|approved|posted|delivered|through)\b")
ASKED = re.compile(r"(?i)(?:^\W*|, |\b(?:and|then|so|or|otherwise) )(?:please |just )?(?:say (?:go|yes|the word|so|when)\b"
                   r"|(?:tell|ping|text|message|send|give|show|point) me\b|let me know\b|press (?:enter|return)\b|sign in\b)"
                   r"|\bonly you can\b|\bone (?:step|thing|click|answer|word) from you\b")
# The last resort the check's own message names, said in one sentence of the reply's own: nothing wakes this seat, or it
# sleeps or stays idle, or it will not wake, see or move, until the principal prompts it. Not another's seat ("her
# session"), not the past ("nothing woke"), not an event ("until the build finishes").
_SEAT = r"this (?:seat|session|agent|chat|thread|conversation)"
WOKEN = re.compile(
    r"(?is)(?:\b(?:nothing|no ?one|nobody|no (?:watcher|timer|monitor|alarm|hook|trigger|task|job))\b.{0,50}?\b(?:wakes?|wake up) (?:up )?(?:" + _SEAT + r"|me|us|myself)\b"
    r"|\b(?:" + _SEAT + r"|i)\b(?:['’]\w+)?(?: [\w'’]+){0,3}? (?:asleep|idle|parked|dormant|sleeps?|(?:won['’]t|will not|cannot|can['’]t|do(?:es)? not|do(?:es)?n['’]t|only)"
    r"(?: be)? (?:wakes?|woken|resumes?|moves?|acts?|continues?|sees?|knows?|notices?|hears?|looks?))\b"
    r"|\bnothing(?: else| more| further)?(?: here)? (?:happens|moves|resumes|continues|proceeds|runs)\b)"
    r".{0,120}?\b(?:until|till|unless|before|without|at|on|with|when|once|after) (?:you (?:next )?(?:prompt|message|nudge|ping|wake|write|return|come back|are back)\b"
    r"|your (?:next |own )?(?:prompt|message|nudge|ping|turn|word)\b|a (?:prompt|message|nudge|word) from you\b|the next (?:prompt|message)\b)")
TABLED = re.compile(r"(?m)^[ \t]*#{1,6}[ \t].*$|^[ \t]*\|.*\|[ \t]*$")  # a heading or a table row names things; it announces nothing
LABEL = re.compile(r"[^.;!?:]{0,60}:(?:\s|$)")  # "Waiting on others: ..." is a label over a list of open loops
RULE = re.compile(r"(?i)\b(?:from now on|going forward|in future|next time|whenever|every time|each time|as a rule)\b")
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


def _explains(text: str, m: re.Match, opens: bool = True) -> bool:
    """Is this wait no announcement: the subject of its sentence ("waiting for a lock blocks a thread"), a fragment
    inside one ("...; waiting on the scope language; then ..."), a label over a list of open loops, or a rule?"""
    opened = m.groupdict()
    if (opened.get("on") or opened.get("till")) and not opens or RULE.search(text, 0, m.end()):
        return True
    if (opened.get("on") or opened.get("till") or m.group(0)[:2].lower() == "we") and LABEL.match(text, m.end()):
        return True
    return bool(opened.get("on") and SUBJECT.match(text, m.end()) or opened.get("till") and UNTIL.match(text, m.end()))


STARTED = ("Async agent launched", "Command running in background", "Workflow launched in background", "Monitor started")
_STARTS = tuple(start.encode() for start in STARTED) + (b"moved to the background", b"resumedAgentId")
REPORTED = re.compile(r"<tool-use-id>\s*([\w-]+)\s*</tool-use-id>")


def held_by_harness(transcript_path: str | None, tail: int = 4_000_000) -> bool:
    """Has this session started background work that has not reported: an agent, a shell command, a workflow, a monitor,
    an agent resumed? The harness wakes the session when it does, so a wait beside it is armed. Reads the tail of a
    Claude Code transcript: a tool's result that opens with the harness's own launch line starts it, and a task
    notification the harness wrote (a prompt, a queued one, one that has arrived) naming that call ends it. Other
    shapes, a record that cannot be read, and work started before the tail hold nothing."""
    try:
        with open(transcript_path or "", "rb") as handle:
            handle.seek(max(0, handle.seek(0, 2) - tail))
            chunk = handle.read()
    except OSError:
        return False
    out = set()
    for line in chunk.splitlines():
        if b"<task-notification>" not in line and not (b'"tool_result"' in line and any(start in line for start in _STARTS)):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        content = entry["message"].get("content") if isinstance(entry.get("message"), dict) else None
        if isinstance(content, list):  # a tool's result; a notification it only prints ends nothing
            for part in content:
                body = part.get("content") if isinstance(part, dict) and part.get("type") == "tool_result" and not part.get("is_error") else None
                text = (body if isinstance(body, str) else " ".join(str(x.get("text", "")) for x in body if isinstance(x, dict))
                        if isinstance(body, list) else "").lstrip()
                if text.startswith(STARTED) or "moved to the background (ID:" in text[:300] or text.startswith("{") and '"resumedAgentId"' in text[:600]:
                    out.add(part.get("tool_use_id"))
            continue
        attachment = entry.get("attachment") if isinstance(entry.get("attachment"), dict) else {}
        said = next((s for s in (content, attachment.get("prompt"), entry.get("content")) if isinstance(s, str)), "")
        if "<task-notification>" in said:
            out -= set(REPORTED.findall(said))
    return bool(out)


def _theirs(text: str, m: re.Match, before: str) -> bool:
    """Is the principal's own next move what this wait awaits? It is when it stands from the wait's words onward; in
    front of them as a condition ("until you choose, I'll wait", "once you sign, I'll wait for the bank"); or anywhere
    in front when nothing is named after the wait ("your answer is the only thing I'm awaiting"). What stands in front
    otherwise is context ("your review is filed and I'm waiting on CI"). A wait that opens its clause and names nothing,
    or only "that" or "it", awaits what the clause before it names: their move ("your approval is all that is left; I'm
    waiting on that"), a request to them, or a question."""
    if THEIRS.search(text, m.start()) or YOURS.match(text, m.end()) or (before and LEAD.fullmatch(text, 0, m.start()) and BACK.match(text, m.end())
                                          and (before.endswith("?") or THEIRS.search(before))):
        return True
    bare = m.group(0).lower().endswith(("wait", "waiting")) and OPEN.match(text, m.end())
    return any(bare or t.group(0).lower().startswith(FRONT) for t in THEIRS.finditer(text, 0, m.start()))


def _offered(body: str) -> bool:
    """Does the reply offer the principal an approval code to type? One named as used or spent offers nothing."""
    return any(not SPENT.match(body, m.end(m.lastindex)) and not USED.search(body, max(0, m.start(m.lastindex) - 120), m.start(m.lastindex))
               for m in CODED.finditer(body))


def unarmed_wait(reply: str, payload: dict, config: dict) -> list[str]:
    """The words with which a reply announces the session's own wait that nothing will end: no live `synthesis wait`
    of this session, no autopilot run it owns, no background work the harness holds for it. A clause that awaits the
    principal's own next move is no such wait, and a reply that hands them the turn, or says in so many words that
    nothing wakes this seat until they prompt it, has none."""
    body = STAGED.sub(" something ", reply)
    if _offered(body):
        return []
    plain = MARKS.sub("", QUOTED.sub(" something ", CODE.sub(" something ", TABLED.sub("", body)))).strip()  # a name set aside is still a thing awaited
    forms = [WAITS] + [re.compile(rf"(?i)\b{re.escape(str(p))}\b") for p in config.get("wait_phrases") or [] if str(p).strip()]
    sentences = [] if plain.endswith("?") else EDGE.split(plain)
    clauses = [(text, at == 0) for sentence in sentences  # each clause, and whether it opens its sentence
               for at, text in enumerate(c for c in (" ".join(part.split()) for part in sentence.split(";")) if c)]
    if any(ASKED.search(text) for text, _ in clauses) or any(WOKEN.search(sentence) for sentence in sentences):
        return []
    hits = {m.group(0).lower().strip(" :—–-") for at, (text, opens) in enumerate(clauses) for form in forms for m in form.finditer(text)
            if not _explains(text, m, opens) and not _theirs(text, m, clauses[at - 1][0] if at else "") and not (body != reply and SENT.search(text))}
    if not hits:
        return []
    from synthesis import autopilot, paths, wait
    session = paths.session_id(payload)
    armed = session and (wait.live(session) or autopilot.brief(payload))
    return [] if armed or held_by_harness(payload.get("transcript_path")) else sorted(hits)


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
