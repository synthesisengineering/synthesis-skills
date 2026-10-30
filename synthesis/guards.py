"""Pre-tool guards (R3). Each returns None to allow, or a reason to block.

Guarded: sends (R3.1), the account a calendar or mail call acts as (R3.6),
deploys and their date rules (R3.2, R3.7), and destructive commands (R3.4).
These fail closed when their config can't be read or is malformed (R3.5).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import time

from synthesis import approvals, paths

DEFAULT_SEND_TOOLS = [
    "mcp__*slack*send_message*", "mcp__*slack*schedule_message*", "mcp__*gmail*send*",
    "mcp__*send_gmail_message*", "mcp__*draft_gmail_message*", "mcp__*create_draft*",
    "mcp__*send_email*", "mcp__*mail*send*", "mcp__*__reply", "mcp__*__forward",
    "mcp__*chat*send_message*", "mcp__*workspace*send_message*",
]
DEFAULT_DEPLOY_PATTERNS = [
    r"\bwrangler\s+(pages\s+)?deploy\b", r"\bvercel\b.*--prod\b", r"\bnetlify\s+deploy\b.*--prod\b",
    r"\bfirebase\s+deploy\b", r"\bnpm\s+publish\b", r"\btwine\s+upload\b", r"\bgh\s+release\s+create\b",
    r"\S*publish_sheet\.py\b",  # the action sheet's upload; free only to a host in sheet_hosts (_sheet_host)
]
SHEET_SCRIPT = os.path.join("skills", "synthesis-action-sheet", "scripts", "publish_sheet.py")
SEPARATORS = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}

# --- sends (R3.1) -------------------------------------------------------------------------------
# The approval binds the whole call (recipients, subject, thread headers, every body part and attachment) and is
# keyed by its digest, so sessions composing at once never share a slot (2026-09-02). Before an approval is asked
# for, the text must pass the register scan and the format rules: email is HTML with no break inside a paragraph
# and no markdown (2026-09-23), no text a person reads breaks a paragraph, a persona signature is a link
# (2026-08-30), threading headers carry literal Message-IDs (2026-08-20, 2026-08-28), and someone the call
# identifies who goes by another name is called by it, not by their official first name (2026-10-13).

EMAIL_TOOLS = frozenset({"send_gmail_message", "draft_gmail_message", "create_draft", "update_draft",
                         "send_email", "reply", "forward"})
HTML_FIELDS = frozenset({"htmlBody", "html_body", "bodyHtml", "body_html", "html"})
BODY_FIELDS = frozenset({"body", "message", "text", "content", "forwardText", "textBody", "text_body",
                         "bodyText", "plain_text", "plainText", "message_text"})
THREAD_HEADERS = ("in_reply_to", "references", "inReplyTo", "in_reply_to_id")
# Fields that never render a link: an RSVP's comment reaches the organizer as plain text, so a signature there
# names its domain in words (2026-10-22: a declined invitation could not carry its signed note).
PLAIN_FIELDS = frozenset({"rsvp_comment", "responseComment"})
HTML_TAGS = frozenset({"p", "div", "span", "a", "em", "strong", "b", "i", "u", "ul", "ol", "li", "blockquote",
                       "html", "body", "br"})
LOOKS_HTML = re.compile(r"</?(?:p|div|span|br|a|b|i|em|strong|u|ul|ol|li|blockquote|html|body|table|img|pre|h[1-6])"
                        r"(?:\s[^<>]*)?/?>", re.I)
MARKDOWN = re.compile(r"\]\(\s*(?:https?|mailto):|\*\*[^*\n]+\*\*|^#{1,6} \S", re.M)
LINKED = re.compile(r"href\s*=\s*(?:\"[^\"]*\"|'[^']*')|<(?:https?|mailto):[^>|\s]*(?:\|[^>]*)?>"
                    r"|\]\((?:https?|mailto):[^)]*\)")
BLOCK_START = re.compile(r"\s*(?:[-*•+]\s|\d+[.)]\s|>|\|)")


def is_send_tool(tool: str, config: dict) -> bool:
    patterns = DEFAULT_SEND_TOOLS + list(config.get("send_tools", []))
    return any(fnmatch.fnmatchcase(tool, p) for p in patterns)


def _strings(value, key: str = ""):
    """(field, text) for every populated string in a call, nested parts included. Attachment
    payloads are bound by the approval digest but are not prose to scan."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in ("attachments", "attachment"):
                yield from _strings(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v, key)
    elif isinstance(value, str) and value.strip():
        yield key, value


def _rendered(markup: str, breaks_ok: bool) -> tuple[str, str, list[str]]:
    """The text an HTML part shows (entities decoded, tags gone); that text followed by its link targets, which
    rules read, so a branding link counts as branding and no phrase is split (2026-10-13); and what in it email
    must not carry."""
    from html.parser import HTMLParser
    from urllib.parse import urlsplit
    text, links, problems, stack, blocks = [], [], [], [], ("p", "div", "li", "blockquote")

    def start(tag, attrs, closed=False):
        problems.extend([f"unsupported HTML element <{tag}>"] if tag not in HTML_TAGS else [])
        problems.extend(["a <br> breaks a paragraph; start a new <p> instead"] if tag == "br" and not breaks_ok else [])
        for name, value in attrs:
            if name not in ("href", "title", "lang", "dir"):
                problems.append(f"unsupported HTML attribute {name}")
            elif name == "href" and urlsplit((value or "").strip()).scheme.lower() not in ("https", "http", "mailto"):
                problems.append("an HTML link must be https, http or mailto")
        text.append("\n\n" if tag in blocks else "\n" if tag == "br" else "")
        stack.extend([tag] if tag != "br" and not closed else [])
        links.extend(v for n, v in attrs if n == "href" and v)

    def end(tag):
        if tag != "br":
            if stack and stack[-1] == tag:
                stack.pop()
            else:
                problems.append("unbalanced HTML")
            text.append("\n\n" if tag in blocks else "")

    reader = HTMLParser(convert_charrefs=True)
    reader.handle_starttag, reader.handle_endtag = start, end
    reader.handle_startendtag = lambda tag, attrs: start(tag, attrs, closed=True)
    reader.handle_data = lambda data: text.append(re.sub(r"\s+", " ", data))
    reader.handle_comment = lambda data: problems.append("HTML comments are not allowed in outgoing prose")
    reader.feed(markup)
    reader.close()
    shown = "".join(text).strip()
    return shown, "\n\n".join([shown] + links), problems + (["unclosed HTML element"] if stack else [])


def broken_paragraph(text: str) -> bool:
    """True when a line break falls inside a paragraph. Blank lines separate paragraphs; a list
    item, quote or table row starts its own line, and fenced code keeps its lines."""
    fenced, previous = False, False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip().startswith("```"):
            fenced, previous = not fenced, False
        elif fenced or not line.strip():
            previous = False
        elif previous and not BLOCK_START.match(line):
            return True
        else:
            previous = True
    return False


def _is_email(tool: str, tool_input: dict) -> bool:
    name = tool.rsplit("__", 1)[-1]
    return name in EMAIL_TOOLS or (name == "send_message" and any(
        k in tool_input for k in ("to", "cc", "bcc", "subject", "htmlBody", "body_format")))


def message_problems(tool: str, tool_input: dict, config: dict, chans: set | None = None) -> list[str]:
    """Why this outgoing message can't go as written, before anyone is asked to approve it. A register rule naming
    channels holds only there (2026-10-27: a line that fits scheduling went out on Jira answers)."""
    from synthesis import sends
    fmt, chans = config.get("message_format") or {}, chans or {sends.channel(tool, tool_input)}
    breaks_ok = bool(fmt.get("allow_line_breaks_in_paragraphs")) or any(  # a document's lines are its own
        fnmatch.fnmatchcase(tool, p) for p in sends.DOCUMENT_EDITS)
    strings, html_format = list(_strings(tool_input)), tool_input.get("body_format") == "html"
    texts, html_parts, problems = [], [], []
    for key, text in strings:
        texts.append(text)
        if key in HTML_FIELDS or (html_format and key in BODY_FIELDS) or LOOKS_HTML.search(text):
            shown, with_links, markup = _rendered(text, breaks_ok)
            texts.append(with_links)  # markup and entities must not hide a banned phrase (2026-07-29)
            html_parts.append((key, shown, markup))
    for rule in config.get("forbidden_phrases", []):
        # Case-insensitive unless the rule says otherwise: a rule against a miscased brand
        # must not block the correctly cased one (2026-08-03).
        flags = 0 if rule.get("case_sensitive") else re.IGNORECASE
        if rule.get("channels") and not chans & set(rule["channels"]):
            continue
        if any(re.search(rule["pattern"], t, flags) for t in texts):
            return [f"message breaks the rule '{rule.get('name', rule['pattern'])}': {rule.get('why', 'see your voice rules')}"]
    for key in THREAD_HEADERS:
        value = str(tool_input.get(key) or "").strip()
        if re.search(r"&(?:lt|gt|amp|#\d+);", value):
            problems.append(f"{key} is HTML-escaped ({value[:60]}); a Message-ID takes literal angle brackets, <id@host>")
        elif value.count("<") != value.count(">"):
            problems.append(f"{key} has an unbalanced angle bracket ({value[:60]})")
    html_keys = {k for k, _, _ in html_parts}
    if _is_email(tool, tool_input):
        bodies = [(k, t) for k, t in strings if k in BODY_FIELDS | HTML_FIELDS]
        plain_ok = fmt.get("default_email_format") == "plain" or any(
            fnmatch.fnmatchcase(tool, p) for p in fmt.get("plain_email_tools", []))
        if bodies and not (html_format or html_keys & HTML_FIELDS) and not plain_ok:
            problems.append("email goes out as HTML, never plain text (plain text is hard-wrapped on send): pass the "
                            "body as htmlBody, or body_format html, with each paragraph in <p>")
        if html_format and "body" in tool_input and "body" not in html_keys:
            problems.append("body_format is html but the body has no paragraph markup; wrap each paragraph in <p>")
        problems += [f"{key}: {m}" for key, _, markup in html_parts for m in markup]
        for key, text in bodies:
            shown = next((s for k, s, _ in html_parts if k == key), text)
            if MARKDOWN.search(shown):
                problems.append(f"{key}: markdown never renders in email; write links as <a href> and emphasis as <strong>")
            if key not in html_keys and not breaks_ok and broken_paragraph(text):
                problems.append(f"{key}: a line break falls inside a paragraph; join each paragraph onto one line")
    elif not breaks_ok:
        problems += [f"{k}: a line break falls inside a paragraph; join each paragraph onto one line, or separate "
                     "paragraphs with a blank line" for k, t in strings if k in BODY_FIELDS and k not in html_keys
                     and broken_paragraph(t)]
    signature, raw = config.get("signature") or {}, "\n".join(t for _, t in strings)
    rendered = "\n".join(t for k, t in strings if k not in PLAIN_FIELDS)
    if any(m and m in rendered for m in signature.get("markers", [])) and not any(  # iMessage and typed text carry no named link
            fnmatch.fnmatchcase(tool, p) for p in ["imessage_send", "messages_send", "desktop_type"]
            + signature.get("plain_url_tools", [])):
        shown = LINKED.sub(" ", rendered)
        exposed = [d for d in signature.get("domains", []) if d and d in shown]
        if exposed:
            problems.append(f"the signature shows {', '.join(exposed)} as text; on a channel that renders links the "
                            "persona name itself must be the link")
    for person in config.get("preferred_names", []):  # only in a call carrying one of their identifiers (2026-10-13)
        official, preferred = person.get("official", ""), person.get("preferred", "")
        if official and any(i and str(i).lower() in raw.lower() for i in person.get("identifiers", [])) and any(
                k not in ADDRESSED and re.search(rf"\b{re.escape(official)}\b", t) for k, t in strings):
            problems.append(f"this message involves someone who goes by {preferred}; write {preferred}, not {official}")
    return problems


def check_send(tool: str, tool_input: dict, config: dict, session: dict | None = None) -> str | None:
    """session: the hook payload, whose transcript shows who typed an approval (a shell's script passes none)."""
    problems = message_problems(tool, tool_input, config)
    if problems:
        return "This message can't go out as written: " + "; ".join(problems[:6]) + "."
    from synthesis import sends
    subject, chan = {"tool": tool, "input": tool_input}, sends.channel(tool, tool_input)
    summary = f"{tool}: " + " ".join(t for _, t in _strings(tool_input))[:160]
    if sends.covered(chan, [t for _, t in _strings(tool_input)], _project(session), config):
        sends.log(chan, tool, summary, "window", session)
        sends.settle()
        return None
    if approvals.consume("send", subject, session):
        sends.log(chan, tool, summary, "approval", session)
        return None
    text = " ".join(t for _, t in _strings(tool_input))
    code = approvals.request("send", subject, f"{tool}: {text[:120]}")
    return ("Sending needs the principal's approval of this exact message. Show them the exact text and "
            f"recipient and ask them to type {approvals.how(code)}. Then make this identical call again."
            + (RESHAPE if _reshapes_calendar(tool, tool_input) else ""))


# 2026-10-27: a series moved to a new hour brought back an occurrence canceled at the old hour, double-booked.
RESHAPE = (" This deletes an event or sets its time or recurrence: in the same message, list its occurrences from today"
           " through the next three, canceled and moved ones included, each checked against accepted meetings (a series'"
           " cancellations stay keyed to the old start time, so moving the series brings them back); prefer changing this"
           " and following occurrences over the whole series; after the write, read back today and every date it touched.")


def _reshapes_calendar(tool: str, tool_input: dict) -> bool:
    deletes = tool.endswith("delete_event") or str(tool_input.get("action", "")).lower() == "delete"
    timed = {"start", "end", "start_time", "end_time", "startTime", "endTime", "recurrence", "rrule"} & set(tool_input)
    return bool(re.search(r"(?:create|update|manage|delete|move)_event$", tool)) and (deletes or bool(timed))


# --- account routing (R3.6) ---------------------------------------------------------------------
# Calendar, mail and sharing calls act as an account, and their recipients see which one: an
# invitation sent from the wrong account cannot be unsent (2026-09-11). Matched on the tool's own
# name after the last "__"; reads are never routed. `send_message` is Gmail on one connector, Google
# Chat on another and session-to-session messaging on a third, so it is routed only when it
# addresses a mailbox or a Chat space. Slack sends belong to the send guard alone.

ROUTED_TOOLS = frozenset({
    "create_event", "update_event", "delete_event", "manage_event", "respond_to_event",
    "manage_focus_time", "manage_out_of_office", "send_gmail_message", "draft_gmail_message",
    "create_draft", "update_draft", "send_email", "reply", "forward", "trash_message", "trash_thread",
    "share_file", "set_drive_file_permissions", "manage_drive_access"})
ADDRESSED = ("to", "cc", "bcc", "recipient", "recipients", "space_id", "space_name", "user_google_email")
# Parameters that name the account a call acts as, most specific first. Apple Calendar picks the
# account by calendar name, so `calendar` counts; a Google calendar id does not (the connector's
# own account is still the organizer).
ACCOUNT_KEYS = ("user_google_email", "from_account", "from_email", "account", "user_email", "sender", "calendar")


def routed(tool: str, tool_input: dict) -> bool:
    name = tool.rsplit("__", 1)[-1]
    return name in ROUTED_TOOLS or (name == "send_message" and any(k in tool_input for k in ADDRESSED))


def _address(value: str) -> str:
    found = re.search(r"<([^<>]+)>", value)
    return (found.group(1) if found else value).strip().lower()


def check_account(tool: str, tool_input: dict, config: dict, cwd: str) -> str | None:
    """Config: {"account_routing": {"default_account": "<who account-less connectors act as>",
    "workspaces": {"<root>": {"account": "<address>", "label": "<name>", "aliases": [...]}}}}."""
    routing = config.get("account_routing", {})
    workspaces = routing.get("workspaces", {}) if isinstance(routing, dict) else None
    if not isinstance(workspaces, dict):
        return "account_routing in the synthesis config needs a \"workspaces\" map; calendar and mail calls are blocked until it is fixed"
    best = _workspace_of(workspaces, cwd)
    if best is None:
        return None
    root, meta = best
    expected = str(meta.get("account") or "").strip()
    if not expected:
        return f"account_routing names no account for {root}; calendar and mail calls there are blocked until it does"
    allowed = {_address(expected)} | {_address(str(a)) for a in meta.get("aliases", [])}
    supplied = next((str(tool_input[k]) for k in ACCOUNT_KEYS if isinstance(tool_input.get(k), str) and tool_input[k].strip()), "")
    acting = supplied or str(routing.get("default_account") or "")
    if acting and _address(acting) in allowed:
        return None
    where = f"this session is in the {meta.get('label') or root} workspace, whose account is {expected}"
    if supplied:
        return f"{tool} would act as {supplied}, but {where}. Use {expected}, or do personal work from outside that workspace."
    return (f"{tool} names no account, so it acts as its connector's own account{f' ({acting})' if acting else ''}, "
            f"but {where}. Use a tool that takes the account and pass {expected} (for example as user_google_email). "
            "Check the organizer or sender afterwards: an invitation cannot be unsent.")


def _workspace_of(workspaces: dict, cwd: str) -> tuple[str, dict] | None:
    """(root, settings) of the deepest configured workspace root holding cwd; `~` and symlinks resolve."""
    here, best = os.path.realpath(cwd), None
    for root, meta in workspaces.items():
        real = os.path.realpath(os.path.expanduser(root))
        if paths.inside(here, real) and (best is None or len(real) > len(best[0])):
            best = (real, meta if isinstance(meta, dict) else {})
    return best


# --- browser profiles ---------------------------------------------------------------------------
# One Chrome extension serves every session on the Mac and acts in whichever browser was selected last
# (2026-10-21: a session worked 15 minutes in another workspace's profile, a public post included, after
# another session's selection). A browser call passes only when this session made the latest selection,
# to its workspace's browser, and its transcript shows that selection succeeded.
BROWSER = "mcp__claude-in-chrome__"
TRANSCRIPT_TAIL = 8 << 20


def _blocks(line: str) -> list:
    try:
        content = (json.loads(line).get("message") or {}).get("content")
    except (ValueError, AttributeError):
        return []
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


_TAILS: dict = {}


def _tail(transcript: str) -> list:
    """The lines of a Claude Code transcript's last 8 MB, read once per version of the file; [] if unreadable."""
    try:
        state = os.stat(transcript)
        key = (transcript, state.st_size, state.st_mtime_ns)
        if key not in _TAILS:
            with open(transcript, "rb") as handle:
                handle.seek(max(0, state.st_size - TRANSCRIPT_TAIL))
                lines = handle.read().decode("utf-8", "replace").splitlines()
            _TAILS.clear()
            _TAILS[key] = lines
    except OSError:
        return []
    return _TAILS[key]


def _last_selection(transcript: str) -> tuple[str, bool] | None:
    """(device, succeeded) for the newest select_browser call in a Claude Code transcript's last 8 MB; a call
    with no result yet has not succeeded. None when there is none there or the file cannot be read."""
    lines = _tail(transcript)
    for i in range(len(lines) - 1, -1, -1):
        if "select_browser" not in lines[i]:
            continue
        call = next((b for b in _blocks(lines[i]) if b.get("type") == "tool_use" and b.get("name") == BROWSER + "select_browser"), None)
        if call is None:
            continue
        device, ident = str((call.get("input") or {}).get("deviceId") or ""), str(call.get("id") or "-")
        for later in lines[i + 1:]:
            for result in (_blocks(later) if ident in later else []):
                if result.get("type") == "tool_result" and result.get("tool_use_id") == ident:
                    text = result.get("content")
                    text = " ".join(str(p.get("text", "")) for p in text if isinstance(p, dict)) if isinstance(text, list) else str(text or "")
                    return device, not result.get("is_error") and text.strip().startswith('Selected browser "')
        return device, False
    return None


def check_browser(tool: str, tool_input: dict, config: dict, cwd: str, session: dict | None) -> str | None:
    """Config: {"browser_routing": {"workspaces": {"<root>": {"device": "<deviceId>", "label": "<name>"}}}}. The
    workspace is the one the session started in, so changing directory never changes its browser."""
    from synthesis import board
    routing = config.get("browser_routing")
    if routing is None:
        return None
    workspaces = routing.get("workspaces") if isinstance(routing, dict) else None
    if not isinstance(workspaces, dict):
        return "browser_routing in the synthesis config needs a \"workspaces\" map; browser calls are blocked until it is fixed"
    me = paths.session_id(session)
    record = board.load(me) if me else None
    found = _workspace_of(workspaces, (record.cwd if record and record.cwd else "") or cwd)
    if found is None:
        return None
    root, meta = found
    device, label, name = str(meta.get("device") or "").strip(), meta.get("label") or root, tool[len(BROWSER):]
    if not device:
        return f"browser_routing names no browser for {root}; browser calls there are blocked until it does"
    if name == "list_connected_browsers":
        return None
    if name == "switch_browser":
        return f"switch_browser lets any browser connect; this session's browser is {label}: select_browser with deviceId {device}."
    if name == "select_browser":
        wanted = str(tool_input.get("deviceId") or "")
        if wanted != device:
            return (f"This session's browser is {label} ({device}), set for the workspace it started in; selecting "
                    f"{wanted or 'nothing'} would act as another profile. Select {device} instead.")
        paths.write_json(paths.state() / "browser.json", {"device": device, "session": me, "at": time.time(), "confirmed": False})
        return None
    current = paths.read_json(paths.state() / "browser.json")
    if current.get("session") != me or current.get("device") != device or not me:
        since = (f"The latest browser selection was made by session {current.get('session')}, at "
                 f"{time.strftime('%H:%M', time.localtime(float(current.get('at') or 0)))}, not by this one"
                 if current.get("session") and current.get("session") != me else "No browser is selected for this session")
        return (f"{since}; the extension is shared, so its browser or tab group may have changed. Call "
                f"list_connected_browsers, then select_browser with deviceId {device} ({label}), before any other browser call.")
    if not current.get("confirmed"):
        if _last_selection(str((session or {}).get("transcript_path") or "")) != (device, True):
            return (f"This session's last select_browser for {device} has not reported success ('Selected browser ...'), "
                    "so actions could reach another profile. Call select_browser again and wait for its result.")
        paths.write_json(paths.state() / "browser.json", {**current, "confirmed": True})
    return None


# --- shell reading ------------------------------------------------------------------------------
# A small reader for the shell a guard must see through: quotes, operators, comments, heredocs,
# here-strings and command substitutions. It runs and expands nothing. Arguments and quoted text
# are data; a substitution, `bash -c`, `eval`, `env -S`, and a shell reading its stdin (heredoc,
# here-string or pipe) run code, so their text is read as commands too. Text it cannot read
# (unbalanced quotes, nesting past MAX_DEPTH) is judged on its raw words by the caller, and an
# unreadable command with no guarded word in it is never blocked for being unreadable.


class Unreadable(ValueError):
    pass


MAX_DEPTH = 6
OPERATORS = ("<<<", "<<-", "<<", "<&", "<", "&&", "&>", "&", "||", "|&", "|", ";;", ";", ">>", ">&", ">|", ">",
             "(", ")", "\n")
REDIRECTS = frozenset({"<<<", "<&", "<", "&>", ">>", ">&", ">|", ">"})
PLAIN = re.compile(r"[^\s'\"\\`$#;&|()<>]+")
SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
STDIN = frozenset({"/dev/stdin", "/dev/fd/0", "/proc/self/fd/0", "-"})
INTERPRETER = re.compile(r"(node|bun|deno|python(\d+(\.\d+)*)?)$")  # python3.12 runs scripts too
KEYWORDS = frozenset({"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until", "time", "fi", "done"})
# Commands that run the command after their own options; the set holds options that take a value.
WRAPPERS = {"env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, "command": set(), "exec": {"-a"},
            "nohup": set(), "time": set(), "nice": {"-n", "--adjustment"},
            "timeout": {"-s", "--signal", "-k", "--kill-after"}, "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-U"},
            "xargs": {"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a"}, "npx": {"-p", "--package"},
            "bunx": set(), "pnpx": set(), "caffeinate": set()}


def _close(s: str, i: int, opener: str) -> int:
    """Index just past the `)` or backtick that closes a substitution whose text starts at i."""
    depth, pending = 1, []
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
        elif opener == "`":
            if c == "`":
                return i + 1
            i += 1
        elif c == "'":
            end = s.find("'", i + 1)
            if end < 0:
                raise Unreadable("unbalanced quote")
            i = end + 1
        elif c == '"':
            i = _dquote(s, i + 1, [])[0]
        elif s.startswith("<<", i) and not s.startswith("<<<", i):
            i, delim, _ = _delimiter(s, i + (3 if s.startswith("<<-", i) else 2))
            pending.append(delim)
        elif c == "\n" and pending:  # a heredoc inside the substitution: skip its body
            for delim in pending:
                i = _body(s, i + 1, delim, True)[0] - 1
            pending, i = [], i + 1
        else:
            depth += (c == "(") - (c == ")")
            i += 1
            if not depth:
                return i
    raise Unreadable("unclosed substitution")


def _dquote(s: str, i: int, subs: list, closing: str = '"') -> tuple[int, str]:
    """Read double-quoted text (or an unquoted heredoc body, closing=""): (end, text), collecting
    the command substitutions inside it."""
    out = []
    while i < len(s):
        c = s[i]
        if closing and c == closing:
            return i + 1, "".join(out)
        if c == "\\" and i + 1 < len(s) and s[i + 1] in '$`"\\\n':
            out.append("" if s[i + 1] == "\n" else s[i + 1])
            i += 2
        elif c == "`" or s.startswith("$(", i):
            start = i + (1 if c == "`" else 2)
            end = _close(s, start, c if c == "`" else "(")
            subs.append(s[start:end - 1])
            out.append(s[i:end])
            i = end
        else:
            out.append(c)
            i += 1
    if closing:
        raise Unreadable("unbalanced quote")
    return i, "".join(out)


def _delimiter(s: str, i: int) -> tuple[int, str, bool]:
    """(end, word, quoted) for the delimiter after `<<`; a quoted delimiter means a literal body."""
    while i < len(s) and s[i] in " \t":
        i += 1
    j = i
    while j < len(s) and s[j] not in " \t\r\n;&|()<>":
        if s[j] in "'\"":
            end = s.find(s[j], j + 1)
            if end < 0:
                raise Unreadable("unbalanced quote")
            j = end + 1
        else:
            j += 2 if s[j] == "\\" else 1
    raw = s[i:j]
    if not raw:
        raise Unreadable("heredoc without a delimiter")
    return j, re.sub(r"['\"\\]", "", raw), bool(re.search(r"['\"\\]", raw))


def _lex(s: str) -> list:
    """Tokens: ("w", word), ("op", op), ("redir", op), ("in", stdin text, literal) and ("sub", script)."""
    tokens, word, started, heredocs, i = [], [], False, [], 0

    def end_word():
        nonlocal word, started
        if started:
            tokens.append(("w", "".join(word)))
        word, started = [], False

    while i < len(s):
        c = s[i]
        plain = PLAIN.match(s, i)
        if plain:
            word.append(plain.group())
            started, i = True, plain.end()
        elif c in " \t\r":
            end_word()
            i += 1
        elif c == "\\":
            if s[i + 1:i + 2] != "\n":
                word.append(s[i + 1:i + 2])
                started = True
            i += 2
        elif c == "'" or s.startswith("$'", i):  # single quotes, or ANSI-C quotes with their escapes decoded
            end, i = i + 1 + (c == "$"), i + 1 + (c == "$")
            while end < len(s) and s[end] != "'":
                end += 2 if s[end] == "\\" and c == "$" else 1
            if end >= len(s):
                raise Unreadable("unbalanced quote")
            text = s[i:end]
            if c == "$":  # $'g\x69t' is git: decode \xHH, octal and the letter escapes
                import codecs
                text = codecs.escape_decode(text.encode("utf-8", "surrogateescape"))[0].decode("utf-8", "replace")
            word.append(text)
            started, i = True, end + 1
        elif c == '"':
            subs = []
            i, text = _dquote(s, i + 1, subs)
            tokens += [("sub", x) for x in subs]
            word.append(text)
            started = True
        elif c == "`" or s.startswith("$(", i):
            start = i + (1 if c == "`" else 2)
            end = _close(s, start, c if c == "`" else "(")
            tokens.append(("sub", s[start:end - 1]))
            word.append(s[i:end])
            started, i = True, end
        elif c in "$#" and (started or c == "$"):
            word.append(c)
            started, i = True, i + 1
        elif c == "#":  # a comment runs to the end of its line
            end = s.find("\n", i)
            i = len(s) if end < 0 else end
        else:
            op = next(o for o in OPERATORS if s.startswith(o, i))
            if op in REDIRECTS and started and "".join(word).isdigit():
                word, started = [], False  # 2>file: the 2 names a file descriptor
            end_word()
            i += len(op)
            if op in ("<<", "<<-"):
                i, delim, literal = _delimiter(s, i)
                heredocs.append((delim, op == "<<-", len(tokens)))
                tokens.append(("in", "", literal))
            elif op in REDIRECTS:
                tokens.append(("redir", op))
            else:
                tokens.append(("op", op))
                if op == "\n" and heredocs:
                    i = _bodies(s, i, heredocs, tokens)
    end_word()
    _bodies(s, len(s), heredocs, tokens)
    return tokens


def _body(s: str, i: int, delim: str, dash: bool) -> tuple[int, str]:
    """(end, text) of a heredoc body starting at i; it runs to its delimiter line or the end."""
    lines = []
    while i < len(s):
        end = s.find("\n", i)
        end = len(s) if end < 0 else end
        line, i = s[i:end], end + 1
        if (line.lstrip("\t") if dash else line) == delim:
            break
        lines.append(line)
    return min(i, len(s)), "\n".join(lines)


def _bodies(s: str, i: int, pending: list, tokens: list) -> int:
    """Read the heredoc bodies that start at i into their placeholder tokens."""
    for delim, dash, at in pending:
        i, text = _body(s, i, delim, dash)
        tokens[at] = ("in", text, tokens[at][2])
    pending.clear()
    return i


def _simple(tokens: list) -> list:
    """Simple commands: "(" and ")" for subshells, else (words, stdin texts, scripts, piped in)."""
    items, words, stdin, scripts, skip, piped, writes = [], [], [], [], "", False, []
    for kind, *rest in tokens + [("op", ";")]:  # a closing ";" flushes the last command
        if kind == "w":
            if skip == "<<<":
                stdin.append((rest[0], True))
            elif not skip:
                words.append(rest[0])
            elif skip in (">", ">>", ">|", "&>") or (skip == ">&" and not rest[0].isdigit()):
                writes.append(rest[0])  # a file this command writes (2026-10-13: a `>` inside quotes is not one)
            skip = ""
        elif kind == "in":
            stdin.append((rest[0], rest[1]))
        elif kind == "sub":
            scripts.append(rest[0])
        elif kind == "redir":
            skip = rest[0]
        else:
            if words or stdin or scripts or writes:
                items.append((words, stdin, scripts, piped, writes))
            words, stdin, scripts, skip, writes = [], [], [], "", []
            piped = rest[0] in ("|", "|&")
            if rest[0] in "()":
                items.append(rest[0])
    return items


def _bare(words: list[str]) -> tuple[list[str], list[str]]:
    """The command a line runs, past assignments, keywords and wrappers like env or timeout, plus
    any script a wrapper takes as text (eval, env -S)."""
    scripts: list[str] = []
    while words:
        head = os.path.basename(words[0])
        if words[0] in KEYWORDS or re.match(r"[A-Za-z_]\w*=", words[0]):
            words = words[1:]
            continue
        if head == "eval":
            return [], scripts + [" ".join(words[1:])]
        if head == "command" and words[1:2] in (["-v"], ["-V"]):
            return [], scripts  # a lookup, not a run
        if head not in WRAPPERS:
            break
        takes, i = WRAPPERS[head], 1
        while i < len(words) and ((words[i].startswith("-") and words[i] != "-")
                                  or (head == "env" and re.match(r"[A-Za-z_]\w*=", words[i]))):
            if words[i] in ("-S", "--split-string") and i + 1 < len(words):
                scripts.append(words[i + 1])
            elif words[i].startswith("--split-string="):
                scripts.append(words[i].split("=", 1)[1])
            i += 2 if words[i] in takes else 1
        words = words[i + (head == "timeout"):]  # timeout's first operand is its duration
    return words, scripts


def _shell_input(words: list[str]) -> tuple[str | None, bool]:
    """(script given with -c, reads its script from stdin) for a shell or `source` command."""
    head = os.path.basename(words[0])
    if head in ("source", "."):
        args = [w for w in words[1:] if w != "--"]
        return None, bool(args) and args[0] in STDIN
    if head not in SHELLS:
        return None, False
    command, i = False, 1
    while i < len(words):
        word = words[i]
        if word in ("-o", "+o", "-O", "+O"):
            i += 2
            continue
        if word == "--" or not word.startswith(("-", "+")):
            rest = words[i + (word == "--"):]
            if command:
                return (rest[0] if rest else None), False
            return None, not rest or rest[0] in STDIN
        if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word):
            command = True
        i += 1
    return None, not command


def _commands(command: str, cwd: str, depth: int = 0, writes: list | None = None) -> list[tuple[list[str], str]]:
    """Each simple command a shell line runs, with the directory it runs in. Follows `cd`,
    subshells, substitutions, `bash -c`, eval, and scripts a shell reads from its stdin. `writes`
    collects (file, directory) for every redirect that writes a file."""
    if depth > MAX_DEPTH:
        raise Unreadable("nested too deeply")
    found, outer, upstream = [], [], ""
    for item in _simple(_lex(command)):
        if item in ("(", ")"):
            if item == "(":
                outer.append(cwd)
            elif outer:
                cwd = outer.pop()  # a subshell's cd ends with it
            continue
        words, stdin, scripts, piped, targets = item
        if writes is not None:
            writes += [(t, cwd) for t in targets]
        for text, literal in stdin:
            if not literal:  # an unquoted heredoc expands its substitutions
                _dquote(text, 0, scripts, "")
        words, inner = _bare(words)
        scripts = scripts + inner
        if words:
            found.append((words, cwd))
            if words[0] in ("cd", "pushd") and (len(words) == 1 or words[1] != "-"):
                target = os.path.expanduser(os.path.expandvars(words[1] if len(words) > 1 else "~"))
                cwd = os.path.normpath(os.path.join(cwd, target))
            script, reads = _shell_input(words)
            if script is not None:
                scripts.append(script)
            elif reads:  # the shell runs whatever reaches its stdin
                scripts += [text for text, _ in stdin] + ([upstream] if piped else [])
        upstream = "\n".join([t for t, _ in stdin] + words[1:]).replace("\\n", "\n")
        for script in scripts:
            found += _commands(script, cwd, depth + 1, writes)
    return found


def _parse(command: str, cwd: str) -> tuple[list[tuple[list[str], str]], bool]:
    """(commands, readable). Unreadable text falls back to a plain split on its separators."""
    try:
        return _commands(command, cwd), True
    except (Unreadable, StopIteration, IndexError):
        found = [(_bare(part.split())[0], cwd) for part in SEPARATORS.split(command)]
        return [(words, where) for words, where in found if words], False


def _git(words: list[str], cwd: str) -> tuple[str | None, str]:
    """(subcommand, directory it acts on) for a git command line; (None, cwd) for anything else."""
    if os.path.basename(words[0]) != "git":
        return None, cwd
    i = 1
    while i < len(words) and words[i].startswith("-"):
        if words[i] == "-C" and i + 1 < len(words):
            cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(words[i + 1])))
        i += 2 if words[i] in GIT_VALUE_OPTIONS else 1
    return (words[i] if i < len(words) else None), cwd


def _checkout(path: str) -> tuple[str | None, str | None]:
    """(worktree root, main checkout root) of the git checkout holding path. A linked worktree
    shares its main checkout's identity, so it is gated and rate-limited like the main one."""
    here = os.path.realpath(path)
    while True:
        dotgit = os.path.join(here, ".git")
        if os.path.isdir(dotgit):
            return here, here
        if os.path.isfile(dotgit):
            try:
                with open(dotgit, encoding="utf-8") as f:
                    gitdir = os.path.join(here, f.read().split("gitdir:", 1)[1].strip())
                with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as f:
                    common = os.path.realpath(os.path.join(gitdir, f.read().strip()))
                return here, os.path.dirname(common) if os.path.basename(common) == ".git" else common
            except (OSError, IndexError):
                return here, here  # a submodule or an unusual layout: its own identity
        parent = os.path.dirname(here)
        if parent == here:
            return None, None
        here = parent


# --- deploys (R3.2) and their date rules (R3.7) -------------------------------------------------

REDEPLOY_WINDOW = 45 * 60  # a second deploy of one site this soon is the rushed follow-up fix (2026-08-29)
FUTURE_SKEW = 15 * 60  # a date this far ahead is a clock artifact, not a post published early
DEFAULT_CONTENT = ["content/posts/**/index.md", "**/src/content/articles/*.md"]  # nested-date and flat layouts
DATE_LINE = r"^(date|pubDate|publishDate)[[:space:]]*[:=]"
DATE_VALUE = re.compile(r"[:=]\s*[\"']?(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?)?")


def _run_git(root: str, *args: str) -> tuple[int, str]:
    import subprocess
    try:
        out = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""
    return out.returncode, out.stdout


def _moment(line: str) -> float | None:
    """The moment a front-matter date line names; local time when it carries no zone."""
    found = DATE_VALUE.search(line)
    if not found:
        return None
    from datetime import datetime, timedelta, timezone
    day, hour, minute, second, zone = found.groups()
    try:
        when = datetime.strptime(f"{day} {hour or '00'}:{minute or '00'}:{second or '00'}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    if zone is None:
        return time.mktime(when.timetuple())
    offset = 0 if zone == "Z" else (1 if zone[0] == "+" else -1) * (int(zone[1:3]) * 60 + int(zone[-2:]))
    return when.replace(tzinfo=timezone(timedelta(minutes=offset))).timestamp()


def _dates(root: str, rev: str | None, globs: list[str]) -> dict[str, float] | None:
    """{path: moment} from each content file's first date line, at rev or in the working tree."""
    code, out = _run_git(root, "grep", "-z", "-n", "-I", "-E", "-e", DATE_LINE,
                         *([rev] if rev else ["--untracked"]), "--", *[f":(glob){g}" for g in globs])
    if code not in (0, 1):
        return None
    found: dict[str, float | None] = {}
    for record in out.split("\n"):
        fields = record.split("\0")
        if len(fields) >= 3:
            path = fields[0][len(rev) + 1:] if rev else fields[0]
            found.setdefault(path, _moment(fields[2]))
    return {p: t for p, t in found.items() if t is not None}


def _show(moment: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(moment))


def _listing(items: list[str]) -> str:
    return "; ".join(items[:5]) + (f"; and {len(items) - 5} more" if len(items) > 5 else "")


def check_dates(root: str, rev: str | None, config: dict) -> str | None:
    """Refuse a deploy that puts a page live before its stated date or re-dates a live page.
    These hold even for an approved deploy: an approval covers a publish, not a break in the
    site's own timeline (2026-08-29; the flat layout escaped the old scan until 2026-08-31)."""
    globs = config.get("deploy_content", DEFAULT_CONTENT)
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        return "deploy_content in the synthesis config must be a list of path globs; deploy blocked until it is fixed"
    live = _dates(root, rev, globs)
    if live is None:
        return f"could not read the content dates in {root}; deploy blocked until `git grep` works there"
    early = sorted(p for p, t in live.items() if t > time.time() + FUTURE_SKEW)
    if early:
        return ("A page must never go live before its stated date, even with approval: "
                + _listing([f"{p} is dated {_show(live[p])}" for p in early])
                + ". Hold this deploy until then, or have the principal correct the date.")
    if not live:
        return None
    code, out = _run_git(root, "for-each-ref", "--format=%(objectname)",
                         "refs/remotes/origin/HEAD", "refs/remotes/origin/main", "refs/remotes/origin/master")
    base = out.split("\n", 1)[0].strip() if code == 0 else ""
    if not base:
        if not _run_git(root, "remote")[1].strip():
            return None  # never pushed anywhere: no live dates to protect
        return ("Could not find the published branch (origin's main) to check that no live page's date changes. "
                f"Run `git -C {root} fetch origin`, then retry.")
    published = _dates(root, base, globs)
    if published is None:
        return f"could not read the published content dates in {root}; deploy blocked"
    moved = sorted(p for p in live if p in published and live[p] != published[p])
    if moved:
        return ("Published dates never change, even with approval. This deploy re-dates live pages: "
                + _listing([f"{p} {_show(published[p])} -> {_show(live[p])}" for p in moved])
                + ". Restore the published date. If the principal wants the page at a new date, take it down "
                "in one deploy and republish it at that date in another.")
    return None


def _deploys(words: list[str], patterns: list[str]) -> bool:
    """A deploy pattern matches from the start of the command, or of the script an interpreter runs
    (`python3 -m twine upload`, `node release.mjs deploy`). Words passed as arguments never match."""
    forms = [[os.path.basename(words[0])] + words[1:]]
    if INTERPRETER.match(forms[0][0]):
        rest = words[1:]
        while rest and rest[0].startswith("-") and rest[0] != "-m":
            rest = rest[1:]
        forms.append(rest[1:] if rest[:1] == ["-m"] else rest)
    return any(form and re.match(p, " ".join(form)) for form in forms for p in patterns)


def _sheet_host(words: list[str], cwd: str, config: dict) -> bool:
    """An action sheet's upload, by the plugin's own script, to a Pages project the principal listed in
    sheet_hosts. The script uploads only the generator's page, and only while the host and a fresh
    subdomain ask for a sign-in; any other upload to that project still waits for approval (2026-10-22)."""
    hosts = config.get("sheet_hosts")
    rest = words[1:] if INTERPRETER.match(os.path.basename(words[0])) else words
    while rest and rest[0].startswith("-") and rest[0] != "-m":
        rest = rest[1:]
    if not isinstance(hosts, list) or not rest or rest[0] == "-m":
        return False
    script = os.path.realpath(os.path.join(cwd, os.path.expanduser(rest[0])))
    projects = [b for a, b in zip(rest[1:], rest[2:]) if a == "--project"]
    projects += [a.split("=", 1)[1] for a in rest[1:] if a.startswith("--project=")]
    return script.endswith(os.sep + SHEET_SCRIPT) and len(projects) == 1 and projects[0] in hosts


def _targets(command: str, config: dict, cwd: str) -> list[tuple[str, str | None]]:
    """(directory, rev) for each deploy in the command. A push deploys HEAD; a build deploys the tree."""
    patterns = DEFAULT_DEPLOY_PATTERNS + list(config.get("deploy_patterns", []))
    commands, readable = _parse(command, cwd)
    targets: list[tuple[str, str | None]] = [(d, None) for words, d in commands
                                             if _deploys(words, patterns) and not _sheet_host(words, d, config)]
    if not readable and not targets and any(re.search(p, command) for p in patterns):
        targets = [(cwd, None)]  # unreadable text with a deploy word in it: judged on the raw words
    repos = None
    for words, directory in commands:
        sub, where = _git(words, directory)
        if sub != "push":
            continue
        if repos is None:
            repos = [os.path.realpath(os.path.expanduser(r)) for r in config.get("push_deploys", [])]
        if repos and re.search(r"[$`]", where):
            targets.append((where, "HEAD"))  # a variable names the repository: it may be a site
            continue
        real, main = os.path.realpath(where), _checkout(where)[1]
        if any(paths.inside(p, r) for r in repos for p in (real, main) if p):
            targets.append((real, "HEAD"))
    return targets


def _last_deploy(identity: str):
    import hashlib
    return paths.state() / "deploys" / (hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16] + ".json")


def check_deploy(command: str, config: dict, cwd: str | None = None, session: dict | None = None) -> str | None:
    cwd = cwd or os.getcwd()
    found = _targets(command, config, cwd)
    pushes = [_checkout(d)[1] or d for d, rev in found if rev and not re.search(r"[$`]", d)]
    twice = sorted({os.path.basename(p) for p in pushes if pushes.count(p) > 1})
    if twice:  # one approval covers one publish; a second is a rapid redeploy of its own
        return (f"This command deploys {', '.join(twice)} more than once. Deploy once; a second deploy "
                "right after it is a rapid redeploy that needs its own decision.")
    targets = list(dict.fromkeys(found))
    if not targets:
        return None
    heads, identities, recent = {}, [], []
    # A site whose build renders other repositories' working trees publishes their dates too.
    renders = {os.path.realpath(os.path.expanduser(k)): v for k, v in (config.get("deploy_also_renders") or {}).items()}
    for directory, rev in targets:
        root, main = (None, None) if re.search(r"[$`]", directory) else _checkout(directory)
        identities.append(main or directory)
        if root:
            reason = check_dates(root, rev, config)
            for extra in renders.get(os.path.realpath(main or root), []) if not reason else []:
                reason = reason or check_dates(os.path.realpath(os.path.expanduser(extra)), None, config)
            if reason:
                return reason
            heads[main] = _run_git(root, "rev-parse", "HEAD")[1].strip()  # approval binds to what HEAD is now
        try:
            last = float(_last_deploy(main or directory).read_text(encoding="utf-8").split("\n")[1])
        except (OSError, ValueError, IndexError):
            continue  # no record of a recent deploy: the brake cannot invent one
        if 0 <= time.time() - last < REDEPLOY_WINDOW:
            recent.append((os.path.basename(main or directory), last))
    kind = "deploy-rapid" if recent else "deploy"
    subject = {"command": command, "heads": heads} if heads else command
    # A rapid-redeploy approval is the stronger one, so it still counts if the window has just closed.
    if approvals.consume(kind, subject, session) or (kind == "deploy" and approvals.consume("deploy-rapid", subject, session)):
        for identity in identities:
            record = _last_deploy(identity)
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(f"{identity}\n{time.time()}\n", encoding="utf-8")
        return None
    if recent:
        name, last = recent[0]
        code = approvals.request(kind, subject, f"RAPID redeploy (last {time.strftime('%H:%M', time.localtime(last))}): {command[:140]}")
        return (f"This is a second deploy of {name} within {REDEPLOY_WINDOW // 60} minutes of the last one "
                f"({time.strftime('%H:%M', time.localtime(last))}). A rushed follow-up fix is the riskiest publish: "
                "put the options to the principal first. Only if they want it now, show them this exact command "
                f"and ask them to type {approvals.how(code)} for this rapid redeploy. Then run the identical command again.")
    code = approvals.request(kind, subject, f"deploy: {command[:160]}")
    unknown = [d for d, _ in targets if re.search(r"[$`]", d)]
    why = (f"This push names its repository through a variable ({unknown[0]}), so it may publish a site that "
           "deploys on push." if unknown else "This publishes to production.")
    return (f"{why} Show the principal this exact command and ask them to type {approvals.how(code)}. "
            "Then run the identical command again.")


# --- destruction (R3.4) -------------------------------------------------------------------------


def _protected(config: dict) -> list[str]:
    home = os.path.expanduser("~")
    workspaces = os.path.join(home, "workspaces")
    roots = ["/", home, workspaces] + [os.path.expanduser(p) for p in config.get("protected_roots", [])]
    if os.path.isdir(workspaces):
        roots += [e.path for e in os.scandir(workspaces) if e.is_dir()]
    return [os.path.realpath(r) for r in roots]


def check_destructive(command: str, config: dict, cwd: str | None = None) -> str | None:
    protected = None
    for words, directory in _parse(command, cwd or os.getcwd())[0]:
        if os.path.basename(words[0]) == "rm" and any(w.startswith("-") and "r" in w.lstrip("-").lower() for w in words[1:]):
            protected = protected if protected is not None else _protected(config)
            for target in (w for w in words[1:] if not w.startswith("-")):
                real = os.path.realpath(os.path.join(directory, os.path.expanduser(os.path.expandvars(target))))
                if real in protected or os.path.exists(os.path.join(real, ".git")):
                    return f"refusing a recursive delete of {real}: it is a protected root or a repository"
        if _git(words, directory)[0] == "push":
            rest = words[words.index("push") + 1:]
            forced = any(w in ("-f", "--force") for w in rest)
            for ref in (w for w in rest if not w.startswith("-")):
                if (forced or ref.startswith("+")) and ref.split(":")[-1].lstrip("+") in ("main", "master"):
                    return "refusing a force push to a default branch"
    return None


# --- approvals come only from the principal's own prompt (R3.0) ------------------------------------
# The agent runs as the hooks' own OS user. In the M5 sandbox (2026-10-05) it granted its own send by
# piping a made-up prompt into the hook; it could as well write a grant or a transcript line. A grant
# is checked against the harness's transcript when it is spent (approvals.py); this refuses the shell
# routes to forging one, and to writing the approved commit lines. A route assembled at run time is beyond a
# text check: docs/runtime-integration.md.

COPIERS = frozenset({"cp", "mv", "ln", "install", "rsync"})  # these write only their last argument
WRITERS = COPIERS | {"tee", "touch", "truncate", "mkdir", "rm", "unlink", "chmod"}
SCRIPT = re.compile(r"(?:python[\d.]*|node|bun|deno|perl|ruby)$")
# What makes a script able to write, not words a reader also uses (json.dumps, str.replace, d["x"] refused a
# read on 2026-10-08): a file opened to write, a mutating file call, or anything that can run other programs.
SCRIPTED_WRITE = re.compile(
    r"\bopen\([^)]*(?:,\s*|mode\s*=\s*)['\"][rbtU]*[wax+]|\.open\(\s*['\"][rbtU]*[wax+]"
    r"|\.(?:write_text|write_bytes|writelines|touch|mkdir|rmdir|unlink|symlink_to|hardlink_to|chmod|truncate)\("
    r"|\.(?:rename|replace)\(\s*[^,()]+\)"  # Path.rename/replace(target); str.replace takes two arguments
    r"|\bos\.(?:remove|unlink|rmdir|removedirs|renames?|replace|makedirs|mkdir|symlink|link|truncate|chmod|chown|utime"
    r"|open|write|system|popen|exec\w*|spawn\w*)\b|\bshutil\.|\bsubprocess\b|\bsqlite3\b"
    r"|\bfs\.\w*(?:[Ww]rite|[Aa]ppend|rename|unlink|rm|mkdir|copy|symlink|truncate|chmod)|createWriteStream"
    r"|\bFile\.(?:write|rename|delete|unlink)|\bFileUtils\b|\bunlink\b|\brename\s*\(|open\s*\(\s*\w+\s*,\s*['\"]\+?[>|]")
# A script that opens a send window, grants or spends an approval, or writes into synthesis state. Reading the
# window, the ledger or the board stays allowed (a read-only check was refused on 2026-10-13).
SELF_GRANT_CALLS = re.compile(r"\b(?:open_window|grant_from_prompt|consume|_window_file)\b|\bpaths\.state\b[\s\S]*\b(?:"
                              r"write_json|write_text|touch|unlink)\b|\b(?:write_json|write_text|touch|unlink)\b[\s\S]*\bpaths\.state\b")
HOOK_RUN = re.compile(r"(?:^|/)(?:synthesis-hook|synthesis/hook\.py)$|^synthesis\.hook$")


PATCH_PATHS = re.compile(r"(?m)^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$")
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "write_file", "edit_file", "apply_patch"}


def _protected_roots(config: dict | None) -> list[str]:
    """Where only the guard, the harness and the synthesis CLI write: synthesis state, the board, harness
    transcripts, approved commit lines."""
    store = paths.line_allowances(config or {})
    return [str(r) for r in [paths.state(), paths.board(), *paths.transcript_roots().values(), *([store] if store else [])]]


# The board grants nothing, but a session file edited by hand can drop another session's claims (5.1.18).
BOARD_WAY = ("Claims and messages go through `synthesis claim`, `synthesis release` and `synthesis msg`, "
             "which keep the board consistent for every session.")


def _file_targets(tool: str, tool_input: dict) -> list[str]:
    text = str(tool_input.get("input") or tool_input.get("patch") or "") if tool == "apply_patch" else ""
    return [a or b for a, b in PATCH_PATHS.findall(text)] or [str(tool_input.get(k)) for k in (
        "file_path", "path", "notebook_path") if tool_input.get(k)]


def _shell_writes(command: str, cwd: str) -> list[str]:
    """The files a shell line writes or removes: redirects, copiers and writers, `sed -i`, `apply_patch`."""
    writes = []
    try:
        found = _commands(command, cwd, writes=writes)
    except (Unreadable, StopIteration, IndexError):
        return []
    targets = [os.path.join(w, t) for t, w in writes]
    for words, where in found:
        head, rest = os.path.basename(words[0]), [w for w in words[1:] if not w.startswith("-")]
        if head in WRITERS or (head in ("sed", "perl") and "-i" in words):
            targets += [os.path.join(where, w) for w in (rest[-1:] if head in COPIERS else rest)]
        if head == "apply_patch":
            targets += [os.path.join(where, a or b) for a, b in PATCH_PATHS.findall(command)]
    return targets


def check_claimed(targets: list[str], cwd: str, session: dict | None) -> str | None:
    """A write into a path another live session has claimed is refused when it is written, not first at commit
    (2026-10-20: a claimed file was emptied, and claims were checked only at commit)."""
    from synthesis import board
    me = paths.session_id(session)
    for target in targets:
        real = os.path.realpath(os.path.join(cwd, os.path.expanduser(os.path.expandvars(target))))
        held = board.holders(real, exclude=me)
        if held:
            return (f"Refused: {real} is claimed by session {held[0].session} (project {held[0].project or '-'}: "
                    f"{held[0].goal or 'no goal'}). Ask it on the board (`synthesis msg`) or wait for its release.")
    return None


def check_file_write(tool: str, tool_input: dict, cwd: str, config: dict) -> str | None:
    """An agent's own file tools (Write, Edit, apply_patch) may not write where approvals and send windows live
    (2026-10-14: those tools never reached the guard, so a window could be written by hand)."""
    targets = _file_targets(tool, tool_input)
    roots = [os.path.realpath(r) for r in _protected_roots(config)]
    real = {t: os.path.realpath(os.path.join(cwd, os.path.expanduser(t))) for t in targets}
    hits = [t for t in targets if any(paths.inside(real[t], r) for r in roots)]
    if hits and paths.inside(real[hits[0]], os.path.realpath(paths.board())):
        return f"Refused: {tool} would write {hits[0]}, inside the synthesis board. {BOARD_WAY}"
    return (f"Refused: {tool} would write {hits[0]}, inside the synthesis state folder, a harness's session "
            "transcripts or the approved commit lines. Approvals and send windows come only from the principal; "
            "show them what needs approving.") if hits else None


def _python_source(words: list, text: str) -> str:
    """The Python a command runs: its -c program, or the heredoc it reads on stdin; "" for a script file."""
    if "-c" in words[:-1]:
        return words[words.index("-c") + 1]
    if words[1:2] in ([], ["-"]):
        try:
            return "\n".join(t[1] for t in _lex(text) if t[0] == "in")
        except (Unreadable, StopIteration, IndexError):
            return ""
    return ""


def _python_writes(source: str, names: list) -> bool | None:
    """Whether a Python program writes into a protected path: True, False, or None when it cannot be told
    (no source, a syntax error, exec or eval). Only a write's target counts, never the content it writes, so a
    project record that cites a transcript path is not a write into transcripts (2026-10-14)."""
    import ast
    try:
        tree = ast.parse(source) if source.strip() else None
    except SyntaxError:
        tree = None
    if tree is None or any(isinstance(n, ast.Name) and n.id in ("exec", "eval", "compile", "__import__") for n in ast.walk(tree)):
        return None
    tainted, grew = set(), True

    def named(node) -> bool:  # built from a protected path, directly or through an assigned name
        return any((isinstance(n, ast.Constant) and isinstance(n.value, str) and any(m in n.value for m in names))
                   or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(node))
    while grew:
        grew = False
        for n in ast.walk(tree):
            value = getattr(n, "value", None) if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) else None
            if value is not None and named(value):
                for target in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    new = {x.id for x in ast.walk(target) if isinstance(x, ast.Name)} - tainted
                    tainted, grew = tainted | new, grew or bool(new)
    for n in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        func, args = n.func, n.args
        attr = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        base = func.value if isinstance(func, ast.Attribute) else None
        given = args[0:1] if base is not None else args[1:2]  # Path(p).open("w") takes its mode first; open(p, "w") second
        mode = next(iter(given), next((k.value for k in n.keywords if k.arg == "mode"), None))
        writes_mode = mode is not None and not (isinstance(mode, ast.Constant) and not re.search(r"[wax+]", str(mode.value)))
        targets = ([args[0]] if attr == "open" and base is None and args and writes_mode else
                   [base] + args[:1] if base is not None and attr in ("rename", "replace") else  # both ends change
                   [base] if base is not None and (attr in ("write_text", "write_bytes", "touch", "mkdir", "rmdir", "unlink",
                                                            "symlink_to", "hardlink_to", "chmod", "truncate")
                                                   or (attr == "open" and writes_mode)) else [])
        if isinstance(base, ast.Name) and base.id in ("os", "shutil", "subprocess"):
            targets = list(args)  # every argument of a filesystem or process call can name what it changes
        if any(named(t) for t in targets):
            return True
    return False


def check_self_grant(command: str, cwd: str, config: dict | None = None) -> str | None:
    codes, home, store = approvals.pending(), os.path.expanduser("~"), paths.line_allowances(config or {})
    text = command.replace("${HOME}", home).replace("$HOME", home)
    raw = _protected_roots(config)
    mine = store and store.name in text  # the store's own name: a write from inside its folder
    names = [n for r in raw for n in (r, "~" + r[len(home):]) if n in text] + ([store.name] if mine else [])
    redirects, readable = [], True
    try:  # the files the parsed command writes; a `>` inside a quoted string is not one (2026-10-13)
        _commands(text, cwd, writes=redirects) if names else None
    except (Unreadable, StopIteration, IndexError):
        readable = False
    targets = [os.path.join(w, os.path.expanduser(os.path.expandvars(t))) for t, w in redirects]
    targets += [t.strip("'\"") for t in re.findall(r">{1,2}\|?\s*([^\s;&|<>()]+)", text)] if names and not readable else []
    why, wheres = "", {cwd}
    if codes and re.search(r"(?i)\b(?:%s)\b" % "|".join(map(re.escape, codes)), command):
        why = "carries a pending approval code (to see pending requests, run `synthesis approvals`)"
    for words, where in _parse(command, cwd)[0]:
        head, own = os.path.basename(words[0]), " ".join(words[1:])
        wheres.add(where)  # a redirect after `cd <root>` writes relative to that root
        if HOOK_RUN.search(words[0]) or ((SCRIPT.match(head) or head in SHELLS) and any(HOOK_RUN.search(w) for w in words[1:])):
            why = why or "runs the synthesis hook, which only the harness may run"
        if names and (head in WRITERS or (head in ("sed", "perl") and "-i" in own)):
            targets += [os.path.join(where, os.path.expanduser(os.path.expandvars(w)))
                        for w in (words[-1:] if head in COPIERS else words[1:])]
        script = text if words[1:2] in ([], ["-"]) else own  # a program read from stdin is the heredoc's text
        if SCRIPT.match(head) and re.search(r"\bsynthesis\b", script) and SELF_GRANT_CALLS.search(script):
            why = why or "runs synthesis's approval or send-window code, which only the guard and the principal's prompt use"
        source = _python_source(words, text) if head.startswith("python") else ""
        # The code decides only when every mention of a protected path is inside it; one named elsewhere on the line
        # could reach the script through a variable (2026-10-06), so that stays judged by the whole command.
        judged = _python_writes(source, names) if source and not any(n in text.replace(source, "") for n in names) else None
        if names and SCRIPT.match(head) and any(n in script for n in names) and re.search(SCRIPTED_WRITE, script) \
                and judged is not False:
            why = why or "runs a script that writes where the synthesis state, its board or a harness's transcripts live (a script on stdin is judged by the whole command: if only another part names that path, run the script alone)"
        if head == "apply_patch":  # Codex's file editor, run as a command: the patch names every file it writes
            targets += [os.path.join(where, a or b) for a, b in PATCH_PATHS.findall(text)]
    real = [os.path.realpath(os.path.join(w, os.path.expanduser(t))) for t in targets for w in wheres]
    real += [os.path.join(t, store.name) for t in real] if mine else []  # a copy into its folder
    if not why and any(paths.inside(t, os.path.realpath(paths.board())) for t in real):
        return f"Refused: this command writes into the synthesis board. {BOARD_WAY}"
    if not why and any(paths.inside(t, os.path.realpath(r)) for t in real for r in raw):
        why = "writes into the synthesis state folder, a harness's session transcripts or the approved commit lines"
    return (f"Refused: this command {why}. Approvals come only from the principal's own prompt; show them "
            "what needs approving and ask them to answer in their own message.") if why else None


# --- sends by computer use (R3.1) ---------------------------------------------------------------
# Computer use sends with no send-named tool: a click on Send, Return in a compose field, a typed line break or the
# app's Send menu item (2026-10-22: an approved WhatsApp photo went out through computer_batch and no code was asked
# for). In a messaging app those wait for the principal's code, a click must say what it does, and words typed there
# pass the register scan as they are typed. In any app, and in a browser page, an action whose summary says it sends
# waits too (45 days of transcripts held 11 such browser sends to LinkedIn, X and a support chat, none guarded).
# computer_batch and the teach tools name no app, so they count as acting in every messaging app the session asked to
# control, and in all of them while its grants are unseen (asked for before this guard ran, or no session id).

# bundle id: (channel, the modifier that makes Return a line break; "" for email, where Return writes a line and
# cmd or ctrl with Return sends, as does Mail's cmd+shift+d)
MESSAGING_APPS = {
    "net.whatsapp.WhatsApp": ("whatsapp", "shift"), "desktop.WhatsApp": ("whatsapp", "shift"),
    "com.apple.MobileSMS": ("messages", "option"), "com.tinyspeck.slackmacgap": ("slack", "shift"),
    "org.whispersystems.signal-desktop": ("signal", "shift"), "ru.keepcoder.Telegram": ("telegram", "shift"),
    "org.telegram.desktop": ("telegram", "shift"), "com.microsoft.teams2": ("teams", "shift"),
    "com.microsoft.teams": ("teams", "shift"), "com.hnc.Discord": ("discord", "shift"), "us.zoom.xos": ("zoom", "shift"),
    "com.apple.mail": ("email", ""), "com.microsoft.Outlook": ("email", ""),
}
APP_NAMES = {"whatsapp": "net.whatsapp.WhatsApp", "messages": "com.apple.MobileSMS", "slack": "com.tinyspeck.slackmacgap",
             "signal": "org.whispersystems.signal-desktop", "telegram": "ru.keepcoder.Telegram",
             "microsoft teams": "com.microsoft.teams2", "teams": "com.microsoft.teams2", "discord": "com.hnc.Discord",
             "zoom.us": "us.zoom.xos", "zoom": "us.zoom.xos", "mail": "com.apple.mail",
             "microsoft outlook": "com.microsoft.Outlook", "outlook": "com.microsoft.Outlook"}
CLICKS = {"click", "left_click", "double_click", "triple_click", "right_click", "middle_click", "left_mouse_down", "left_mouse_up"}
DESKTOP_TOOLS = CLICKS | {"batch", "teach_step", "teach_batch", "app_batch", "app_click", "app_key", "app_type", "app_menu",
                          "key", "hold_key", "type", "request_access", "request_teach_access"}
RETURNS = {"return", "enter", "kp_enter", "kp_return"}
MODIFIERS = {"alt": "option", "opt": "option", "command": "cmd", "meta": "cmd", "super": "cmd", "control": "ctrl"}
SAYS_SENT = re.compile(r"^\W*(?:(?:send|repl(?:y|ie)|forward|post|publish|share|invite|respond|comment|mention|announce"
                       r"|notif(?:y|ie)|remind|schedule|deliver|email|text)(?:s|es|d|ed|ing)?\b"
                       r"|(?:click|press|tap|hit|choose|select)(?:s|es)?\s+(?:the\s+)?send\b)|\bto send\b", re.I)


def desktop_tool(tool: str) -> str:
    """The computer-use action a tool performs ("batch", "app_click"...), or "" for any other tool: the desktop
    app's computer-use server by any id, a linked device's computer_* tools, or a browser's computer and
    browser_batch tools ("browser", "browser_batch")."""
    server, _, name = tool.rpartition("__")
    if tool.startswith("mcp__") and name in ("computer", "browser_batch") and re.search(r"browser|chrome", server, re.I):
        return "browser" if name == "computer" else name
    bare = name[len("computer_"):] if name.startswith("computer_") else name
    linked = "computer" in server.lower() or name.startswith("computer_")
    return bare if tool.startswith("mcp__") and linked and bare in DESKTOP_TOOLS else ""


def _desktop_actions(name: str, tool_input: dict) -> list:
    """(kind, value, summary) for each click, key chord, typed text or menu path a computer-use call performs.
    Screenshots, scrolls, waits and menu listings do nothing to anyone and are left out."""
    if name == "teach_batch":
        items = [a for s in tool_input.get("steps") or [] if isinstance(s, dict) for a in s.get("actions") or []]
    elif name in ("batch", "app_batch", "teach_step"):
        items = list(tool_input.get("actions") or [])
    elif name == "browser_batch":  # {name, input} steps; a form_input value is text typed into the page
        steps = [(str(s.get("name", "")), s.get("input") if isinstance(s.get("input"), dict) else {})
                 if isinstance(s, dict) else ("", s) for s in tool_input.get("actions") or []]
        items = [{**i, "action": "type", "text": str(i.get("value", ""))} if n.endswith("form_input") and isinstance(i, dict)
                 else i for n, i in steps]
    elif name == "browser":
        items = [tool_input]
    else:
        items = [{**tool_input, "action": name[4:] if name.startswith("app_") else name}]
    found = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"a computer-use action is not an object ({str(item)[:40]})")
        act = str(item.get("action") or "")
        kind = "click" if act in CLICKS else "key" if act in ("key", "hold_key") else act if act in ("type", "menu") else ""
        value = (" > ".join(str(p) for p in item.get("path") or []) if kind == "menu" else
                 str(item.get("combo") or item.get("text") or "") if kind in ("key", "type") else "")
        if kind and (value or kind == "click"):
            found.append((kind, value, str(item.get("action_summary") or "")))
    return found


def _messaging(config: dict) -> dict:
    """bundle id: (channel, line-break modifier) for every messaging app, with the config's `messaging_apps` (chat
    apps where shift with Return writes a line)."""
    extra = config.get("messaging_apps", [])
    if not isinstance(extra, list) or not all(isinstance(b, str) and b for b in extra):
        raise ValueError("messaging_apps in the synthesis config must be a list of bundle ids")
    return {**MESSAGING_APPS, **{b: (b.rsplit(".", 1)[-1].lower(), "shift") for b in extra}}


# A browser page on a messaging site counts as that messaging app (2026-10-22: Return in a Google Chat compose box
# went out with no code, since a page was no app). Its address comes from the tab list Claude in Chrome prints after
# each call, or from a navigate step earlier in the same batch; a page whose address is unknown is judged as before.
WEB_MESSAGING = (  # (host, or .suffix for every host under it; path prefix; channel; line-break modifier, as above)
    ("mail.google.com", "/chat", "google chat", "shift"), ("chat.google.com", "", "google chat", "shift"),
    ("mail.google.com", "", "email", ""), ("outlook.office.com", "", "email", ""),
    ("outlook.office365.com", "", "email", ""), ("outlook.live.com", "", "email", ""), (".slack.com", "", "slack", "shift"),
    ("web.whatsapp.com", "", "whatsapp", "shift"), ("www.linkedin.com", "/messaging", "linkedin", "shift"),
    ("teams.microsoft.com", "", "teams", "shift"), ("teams.live.com", "", "teams", "shift"),
    ("discord.com", "", "discord", "shift"), ("web.telegram.org", "", "telegram", "shift"),
    ("www.messenger.com", "", "messenger", "shift"), ("x.com", "/messages", "x", "shift"),
)
TAB_LINE = re.compile(r'tabId (\d+): .*\("([^"\s]+)"\)\s*$', re.M)


def _web_app(url: str):
    """(page, (channel, line-break modifier)) when url is a messaging site's page, else None."""
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(url if "://" in url else "https://" + url)
    except ValueError:
        return None
    host, path = (parts.hostname or "").lower(), parts.path or "/"
    for site, prefix, chan, brk in WEB_MESSAGING:
        if (host == site or site[0] == "." and host.endswith(site)) and path.startswith(prefix):
            return host + prefix, (chan, brk)
    return None


def _browser_call(lines: list, i: int, ident: str) -> bool:
    """Whether the call whose result is on line i went to a browser server (a shell printing a tab list did not)."""
    for line in reversed(lines[max(0, i - 200):i] if ident else []):
        for call in (_blocks(line) if ident in line else []):
            if call.get("type") == "tool_use" and call.get("id") == ident:
                return bool(re.search(r"browser|chrome", str(call.get("name", "")).rpartition("__")[0], re.I))
    return False


def _tabs(transcript: str) -> tuple:
    """({tab id: address}, the tab the newest call ran on), from the newest browser result's tab list."""
    lines = _tail(transcript)
    for i in range(len(lines) - 1, -1, -1):
        for block in reversed(_blocks(lines[i]) if "Tab Context" in lines[i] else []):
            content = block.get("content") if block.get("type") == "tool_result" else ""
            text = ("\n".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
                    if isinstance(content, list) else str(content or ""))
            if "Tab Context" in text and _browser_call(lines, i, str(block.get("tool_use_id") or "")):
                context = text[text.rindex("Tab Context"):]
                front = re.search(r"Executed on tabId: (\d+)", context)
                return dict(TAB_LINE.findall(context)), front.group(1) if front else ""
    return {}, ""


def _pages(name: str, tool_input: dict, session: dict | None) -> dict:
    """page: (channel, line-break modifier) for each messaging site this browser call acts on."""
    tabs, front = _tabs(str((session or {}).get("transcript_path") or ""))
    steps = [("computer", tool_input)] if name == "browser" else [
        (str(s.get("name", "")), s["input"]) for s in tool_input.get("actions") or []
        if isinstance(s, dict) and isinstance(s.get("input"), dict)]
    reached = {}
    for step, given in steps:
        tab = str(given.get("tabId") or front)
        if step.endswith("navigate"):  # the steps after it act on the new page
            tabs[tab] = str(given.get("url") or "")
        page = _web_app(tabs.get(tab, ""))
        if page:
            reached[page[0]] = page[1]
    return reached


def _bundle(app, apps: dict) -> str:
    text = str(app or "").strip().lower()
    return APP_NAMES.get(text) or next((b for b in apps if b.lower() == text), "")


def _grants(session: dict | None):
    me = "".join(c if c.isalnum() or c in "-_." else "_" for c in paths.session_id(session))
    return paths.state() / "desktop" / f"{me}.json" if me else None


def _sends_key(chords: str, apps: dict) -> bool:
    """A Return or Enter that sends in one of these apps (or Mail's cmd+shift+d in an email app)."""
    for chord in chords.split():
        *mods, key = chord.lower().split("+")
        held = {MODIFIERS.get(m, m) for m in mods}
        for _, brk in apps.values():
            if key in RETURNS and (held != {brk} if brk else bool(held & {"cmd", "ctrl"})) or (
                    not brk and key == "d" and held == {"cmd", "shift"}):
                return True
    return False


def check_desktop(name: str, tool: str, tool_input: dict, config: dict, session: dict | None = None) -> str | None:
    from synthesis import sends
    apps, record = _messaging(config), _grants(session)
    if name.startswith("request_"):  # every grant starts here, so the session's messaging apps are known
        if record and isinstance(tool_input.get("apps"), list):  # one the server would refuse leaves it unseen
            asked = {_bundle(a, apps) for a in tool_input["apps"]} - {""}
            paths.write_json(record, {"apps": sorted(set(paths.read_json(record).get("apps", [])) | asked), "at": time.time()})
        return None
    actions = _desktop_actions(name, tool_input)
    if not actions:
        return None
    seen = paths.read_json(record) if record else {}
    unseen = not name.startswith(("app_", "browser")) and "apps" not in seen  # a browser page is no messaging app
    reached = ({b: apps[b] for b in [_bundle(tool_input.get("app"), apps)] if b in apps} if name.startswith("app_")
               else _pages(name, tool_input, session) if name.startswith("browser")
               else apps if unseen else {b: apps[b] for b in seen["apps"] if b in apps})
    typed = [v for kind, v, _ in actions if kind == "type" and v.strip()]
    sending = [s or f"{kind} {v}".strip() for kind, v, s in actions if SAYS_SENT.search(s) or reached and (
        kind == "click" and not s.strip() or kind == "menu" and re.search(r"(?:^|> )send\b", v, re.I)
        or kind == "key" and _sends_key(v, reached) or kind == "type" and re.search(r"[\r\n]", v) and _sends_key("return", reached))]
    problems = message_problems("desktop_type", {"message_text": "\n\n".join(typed)}, config,
                                {c for c, _ in reached.values()}) if typed and (reached or sending) else []
    if problems:
        return "These words can't go out as written: " + "; ".join(problems[:6]) + "."
    if not sending:
        return None
    chans = sorted({c for c, _ in reached.values()})
    chan = "browser" if name.startswith("browser") else chans[0] if len(chans) == 1 else "desktop"
    where = ((f"the browser ({', '.join(sorted(reached))})" if reached else "the browser") if name.startswith("browser")
             else "any messaging app" if unseen else ", ".join(sorted(reached)) or "an app")
    what, subject = "; ".join(sending)[:200], {"tool": tool, "input": tool_input}
    summary = f"{tool} in {where}: {what}" + (f"; words: {' / '.join(typed)}" if typed else "")
    if sends.covered(chan, typed, _project(session), config):
        sends.log(chan, tool, summary, "window", session)
        sends.settle()
        return None
    if approvals.consume("send", subject, session):
        sends.log(chan, tool, summary, "approval", session)
        return None
    code = approvals.request("send", subject, summary[:300])
    return (f"This call sends in {where} ({what}). Sending needs the principal's approval of this exact call: show them "
            "the exact words and recipient as they will go out (a screenshot of the compose area) and ask them to type "
            f"{approvals.how(code)}. Then make this identical call again. Typing the words and sending in one call binds "
            "both to the approval. A Return or click here that does not send (a file picker, a search field): click the "
            "control it confirms instead, with a summary that says what it does."
            + (" This session's computer-use grants were asked for before the guard could see them; request_access "
               "naming the apps again tells it which apps this session controls." if unseen else ""))


# --- dispatch -----------------------------------------------------------------------------------

SHELL_TOOLS = {"Bash", "bash", "exec_command", "exec", "shell", "local_shell", "run_shell_command"}  # "bash": Muse


def shell_command(tool_input: dict) -> str:
    """The command text, whichever harness spelled it: a string or an argv list."""
    value = tool_input.get("command", tool_input.get("cmd", ""))
    return shlex.join(value) if isinstance(value, list) else str(value)


def _quiet_calendar_write(tool: str, tool_input: dict) -> bool:
    """A calendar write that names no attendees and turns notifications off emails no one, so it needs no
    approval (Rajiv's ruling, 2026-10-06: the gate exists because invitations email people in his name). An RSVP
    always waits: the organizer sees the answer (2026-10-23, an accepted RSVP with notifications off went unasked)."""
    notify = str(tool_input.get("send_updates", tool_input.get("sendUpdates", ""))).strip().lower()
    rsvp = str(tool_input.get("action", "")).strip().lower() == "rsvp" or bool(tool_input.get("response"))
    return (bool(re.search(r"(?:create|update|manage)_event$", tool)) and notify == "none"
            and not tool_input.get("attendees") and not rsvp)


def _sends(tool: str, tool_input: dict, config: dict) -> bool:
    """A tool that delivers words to people, by name or by what its name says it does (every channel, Rajiv,
    2026-10-13), or any server's `send_message` that addresses a mailbox or Chat space (the Gmail connector's
    server name is an id no name pattern can anticipate). Work in the principal's own repositories is not a send."""
    from synthesis import sends
    if sends.own_repo(sends.tool_repo(tool_input), config):
        return False
    return (((is_send_tool(tool, config) or sends.says(tool, config)) and not _quiet_calendar_write(tool, tool_input))
            or (tool.rsplit("__", 1)[-1] == "send_message" and routed(tool, tool_input)))


def _project(session: dict | None) -> str:
    from synthesis import board
    me = board.load(paths.session_id(session)) if paths.session_id(session) else None
    return me.project if me else ""


def check_outgoing(command: str, config: dict, cwd: str, session: dict | None = None) -> str | None:
    """A shell command that posts words to people waits for the principal's code, as a connector send does, and
    opening a send window needs it too. The register scan reads the message the command sends (its text words and
    any body file), not file names or URLs (2026-10-13: a scratch file's name tripped a rule)."""
    import hashlib
    from synthesis import sends
    posts, window, writes = [], None, []
    try:  # files this command writes, so a body file it rewrites before posting is not read stale (2026-10-13)
        _commands(command, cwd, writes=writes)
    except (Unreadable, StopIteration, IndexError):
        pass
    commands = _parse(command, cwd)[0]
    written = {os.path.realpath(os.path.join(w, os.path.expanduser(t))) for t, w in writes} | {
        os.path.realpath(os.path.join(where, t)) for words, where in commands if os.path.basename(words[0]) in COPIERS | {"tee"}
        for t in (words[-1:] if os.path.basename(words[0]) in COPIERS else words[1:])}
    for words, where in commands:
        window = window or sends.window_asked(words)
        chan = sends.command_send(words, where, config)
        if chan:
            text, problem = sends.message_text(words, where, written)
            if problem:
                return f"This command posts to {chan}, but {problem}. Put the text in the command or a readable file."
            posts.append((chan, text, where))
    if window:  # the command spends the grant itself (`synthesis sends open` refuses without one)
        try:  # never ask the principal to approve a window the command would refuse
            sends.check_window(window["hours"], window["channels"], window["sends"])
        except ValueError as exc:
            return f"This send window can't open: {exc}."
        return None if approvals.held("send-window", window) else sends.window_refusal(window)
    if not posts:
        return None
    text, chans = "\n\n".join(t for _, t, _ in posts), sorted({c for c, _, _ in posts})
    problems = message_problems("Bash", {"message_text": text}, config, set(chans))
    if problems:
        return "This command posts a message that can't go out as written: " + "; ".join(problems[:6]) + "."
    dirs = sorted({w for _, _, w in posts})  # where it runs, after its own cd: a re-run elsewhere is the same send
    summary = f"{', '.join(chans)} (runs in {', '.join(dirs)}): {command[:160]}"
    if all(sends.covered(c, [text], _project(session), config) for c in chans):
        for c in chans:
            sends.log(c, "shell", summary, "window", session)
        sends.settle()
        return None
    subject = {"command": command, "runs_in": dirs, "message": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    if approvals.consume("send", subject, session):
        for c in chans:
            sends.log(c, "shell", summary, "approval", session)
        return None
    code = approvals.request("send", subject, summary)
    return (f"This command posts to {', '.join(chans)} on the principal's behalf; it runs in {', '.join(dirs)}. Show "
            f"them the exact command and its message and ask them to type {approvals.how(code)}. Then run the identical "
            "command again from any directory: the approval binds where it runs, not where the shell started.")


def guarded(tool: str, tool_input: dict | None = None) -> bool:
    """Calls whose guard must fail closed when the config can't be read (R3.5)."""
    return (tool in SHELL_TOOLS or tool.startswith(BROWSER) or bool(desktop_tool(tool)) or _sends(tool, tool_input or {}, {})
            or routed(tool, tool_input or {}))


def check(tool: str, tool_input: dict, config: dict, cwd: str | None = None, session: dict | None = None) -> str | None:
    """cwd is the session's working directory (the hook payload's `cwd`); defaults to this process's.
    session is the hook payload, which names the transcript an approval is checked against."""
    if not cwd:
        try:
            cwd = str(tool_input.get("workdir") or "") or os.getcwd()
        except OSError:
            cwd = os.path.expanduser("~")
    if tool in SHELL_TOOLS:
        command = shell_command(tool_input)
        return (check_self_grant(command, cwd, config) or check_destructive(command, config, cwd)
                or check_deploy(command, config, cwd, session) or check_outgoing(command, config, cwd, session)
                or check_claimed(_shell_writes(command, cwd), cwd, session))
    if tool in FILE_TOOLS:
        return check_file_write(tool, tool_input, cwd, config) or check_claimed(_file_targets(tool, tool_input), cwd, session)
    if tool.startswith(BROWSER):
        return check_browser(tool, tool_input, config, cwd, session) or (
            check_desktop(desktop_tool(tool), tool, tool_input, config, session) if desktop_tool(tool) else None)
    if desktop_tool(tool):
        return check_desktop(desktop_tool(tool), tool, tool_input, config, session)
    # The account is checked before the send approval, so no approval is spent on the wrong account.
    reason = routed(tool, tool_input) and check_account(tool, tool_input, config, cwd)
    return reason or (check_send(tool, tool_input, config, session) if _sends(tool, tool_input, config) else None)
