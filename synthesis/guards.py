"""Pre-tool guards (R3). Each returns None to allow, or a reason to block.

Guarded: sends (R3.1), the account a calendar or mail call acts as (R3.6),
deploys and their date rules (R3.2, R3.7), and destructive commands (R3.4).
These fail closed when their config can't be read or is malformed (R3.5).
"""

from __future__ import annotations

import fnmatch
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
]
SEPARATORS = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}

# --- sends (R3.1) -------------------------------------------------------------------------------
# The approval binds the whole call (recipients, subject, thread headers, every body part and
# attachment) and is keyed by its digest, so sessions composing at once never share a slot
# (2026-09-02). Before an approval is asked for, the text must pass the register scan and the
# format rules: email is HTML with no break inside a paragraph and no markdown (2026-09-23), no
# text a person reads breaks a paragraph, a persona signature is a link (2026-08-30), and
# threading headers carry literal Message-IDs (2026-08-20, 2026-08-28).

EMAIL_TOOLS = frozenset({"send_gmail_message", "draft_gmail_message", "create_draft", "update_draft",
                         "send_email", "reply", "forward"})
HTML_FIELDS = frozenset({"htmlBody", "html_body", "bodyHtml", "body_html", "html"})
BODY_FIELDS = frozenset({"body", "message", "text", "content", "forwardText", "textBody", "text_body",
                         "bodyText", "plain_text", "plainText", "message_text"})
THREAD_HEADERS = ("in_reply_to", "references", "inReplyTo", "in_reply_to_id")
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


def _rendered(markup: str, breaks_ok: bool) -> tuple[str, list[str]]:
    """The text an HTML part shows (entities decoded, tags gone), and what in it email must not carry."""
    from html.parser import HTMLParser
    from urllib.parse import urlsplit
    text, problems, stack, blocks = [], [], [], ("p", "div", "li", "blockquote")

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
    return "".join(text).strip(), problems + (["unclosed HTML element"] if stack else [])


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


def message_problems(tool: str, tool_input: dict, config: dict) -> list[str]:
    """Why this outgoing message can't go as written, before anyone is asked to approve it."""
    fmt = config.get("message_format") or {}
    breaks_ok = bool(fmt.get("allow_line_breaks_in_paragraphs"))
    strings = list(_strings(tool_input))
    html_format = tool_input.get("body_format") == "html"
    texts, html_parts, problems = [], [], []
    for key, text in strings:
        texts.append(text)
        if key in HTML_FIELDS or (html_format and key in BODY_FIELDS) or LOOKS_HTML.search(text):
            shown, markup = _rendered(text, breaks_ok)
            texts.append(shown)  # markup and entities must not hide a banned phrase (2026-07-29)
            html_parts.append((key, shown, markup))
    for rule in config.get("forbidden_phrases", []):
        # Case-insensitive unless the rule says otherwise: a rule against a miscased brand
        # must not block the correctly cased one (2026-08-03).
        flags = 0 if rule.get("case_sensitive") else re.IGNORECASE
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
        for key, shown, markup in html_parts:
            problems += [f"{key}: {m}" for m in markup]
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
    signature = config.get("signature") or {}
    raw = "\n".join(t for _, t in strings)
    if any(m and m in raw for m in signature.get("markers", [])) and not any(
            fnmatch.fnmatchcase(tool, p) for p in signature.get("plain_url_tools", [])):
        shown = LINKED.sub(" ", raw)
        exposed = [d for d in signature.get("domains", []) if d and d in shown]
        if exposed:
            problems.append(f"the signature shows {', '.join(exposed)} as text; on a channel that renders links the "
                            "persona name itself must be the link")
    return problems


def check_send(tool: str, tool_input: dict, config: dict) -> str | None:
    problems = message_problems(tool, tool_input, config)
    if problems:
        return "This message can't go out as written: " + "; ".join(problems[:6]) + "."
    subject = {"tool": tool, "input": tool_input}
    if approvals.consume("send", subject):
        return None
    text = " ".join(t for _, t in _strings(tool_input))
    code = approvals.request("send", subject, f"{tool}: {text[:120]}")
    return ("Sending needs the principal's approval of this exact message. Show them the exact text and "
            f"recipient and ask them to reply \"approve {code}\". Then make this identical call again.")


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


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def check_account(tool: str, tool_input: dict, config: dict, cwd: str) -> str | None:
    """Config: {"account_routing": {"default_account": "<who account-less connectors act as>",
    "workspaces": {"<root>": {"account": "<address>", "label": "<name>", "aliases": [...]}}}}."""
    routing = config.get("account_routing", {})
    workspaces = routing.get("workspaces", {}) if isinstance(routing, dict) else None
    if not isinstance(workspaces, dict):
        return "account_routing in the synthesis config needs a \"workspaces\" map; calendar and mail calls are blocked until it is fixed"
    if not workspaces:
        return None
    here, best = os.path.realpath(cwd), None
    for root, meta in workspaces.items():
        real = os.path.realpath(os.path.expanduser(root))
        if _inside(here, real) and (best is None or len(real) > len(best[0])):
            best = (real, meta)
    if best is None:
        return None
    root, meta = best[0], best[1] if isinstance(best[1], dict) else {}
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
INTERPRETERS = frozenset({"node", "bun", "deno", "python", "python3"})
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
            depth += c == "("
            depth -= c == ")"
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
    items, words, stdin, scripts, skip, piped = [], [], [], [], "", False
    for kind, *rest in tokens:
        if kind == "w":
            if skip == "<<<":
                stdin.append((rest[0], True))
            elif not skip:
                words.append(rest[0])
            skip = ""
        elif kind == "in":
            stdin.append((rest[0], rest[1]))
        elif kind == "sub":
            scripts.append(rest[0])
        elif kind == "redir":
            skip = rest[0]
        else:
            if words or stdin or scripts:
                items.append((words, stdin, scripts, piped))
            words, stdin, scripts, skip = [], [], [], ""
            piped = rest[0] in ("|", "|&")
            if rest[0] in "()":
                items.append(rest[0])
    if words or stdin or scripts:
        items.append((words, stdin, scripts, piped))
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
    command, reads, i = False, True, 1
    while i < len(words):
        word = words[i]
        if word in ("-o", "+o", "-O", "+O"):
            i += 2
            continue
        if word == "--" or not word.startswith(("-", "+")):
            rest = words[i + (word == "--"):]
            if command:
                return (rest[0] if rest else None), False
            return None, (not rest or rest[0] in STDIN) and reads
        if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word):
            command = True
        i += 1
    return None, not command


def _commands(command: str, cwd: str, depth: int = 0) -> list[tuple[list[str], str]]:
    """Each simple command a shell line runs, with the directory it runs in. Follows `cd`,
    subshells, substitutions, `bash -c`, eval, and scripts a shell reads from its stdin."""
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
        words, stdin, scripts, piped = item
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
            found += _commands(script, cwd, depth + 1)
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
    if forms[0][0] in INTERPRETERS:
        rest = words[1:]
        while rest and rest[0].startswith("-") and rest[0] != "-m":
            rest = rest[1:]
        forms.append(rest[1:] if rest[:1] == ["-m"] else rest)
    return any(form and re.match(p, " ".join(form)) for form in forms for p in patterns)


def _targets(command: str, config: dict, cwd: str) -> list[tuple[str, str | None]]:
    """(directory, rev) for each deploy in the command. A push deploys HEAD; a build deploys the tree."""
    patterns = DEFAULT_DEPLOY_PATTERNS + list(config.get("deploy_patterns", []))
    commands, readable = _parse(command, cwd)
    targets: list[tuple[str, str | None]] = [(d, None) for words, d in commands if _deploys(words, patterns)]
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
        if any(_inside(p, r) for r in repos for p in (real, main) if p):
            targets.append((real, "HEAD"))
    return targets


def _last_deploy(identity: str):
    import hashlib
    return paths.state() / "deploys" / (hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16] + ".json")


def check_deploy(command: str, config: dict, cwd: str | None = None) -> str | None:
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
    for directory, rev in targets:
        root, main = (None, None) if re.search(r"[$`]", directory) else _checkout(directory)
        identities.append(main or directory)
        if root:
            reason = check_dates(root, rev, config)
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
    if approvals.consume(kind, subject) or (kind == "deploy" and approvals.consume("deploy-rapid", subject)):
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
                f"and ask them to reply \"approve {code}\" for this rapid redeploy. Then run the identical command again.")
    code = approvals.request(kind, subject, f"deploy: {command[:160]}")
    unknown = [d for d, _ in targets if re.search(r"[$`]", d)]
    why = (f"This push names its repository through a variable ({unknown[0]}), so it may publish a site that "
           "deploys on push." if unknown else "This publishes to production.")
    return (f"{why} Show the principal this exact command and ask them to reply \"approve {code}\". "
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
        sub, _ = _git(words, directory)
        if sub == "push":
            rest = words[words.index("push") + 1:]
            forced = any(w in ("-f", "--force") for w in rest)
            for ref in (w for w in rest if not w.startswith("-")):
                if (forced or ref.startswith("+")) and ref.split(":")[-1].lstrip("+") in ("main", "master"):
                    return "refusing a force push to a default branch"
    return None


# --- dispatch -----------------------------------------------------------------------------------

SHELL_TOOLS = {"Bash", "bash", "exec_command", "exec", "shell", "local_shell", "run_shell_command"}  # "bash": Muse


def shell_command(tool_input: dict) -> str:
    """The command text, whichever harness spelled it: a string or an argv list."""
    value = tool_input.get("command", tool_input.get("cmd", ""))
    return shlex.join(value) if isinstance(value, list) else str(value)


def _sends(tool: str, tool_input: dict, config: dict) -> bool:
    """A send tool by name, or any server's `send_message` that addresses a mailbox or Chat space
    (the Gmail connector's server name is an id that no name pattern can anticipate)."""
    return is_send_tool(tool, config) or (tool.rsplit("__", 1)[-1] == "send_message" and routed(tool, tool_input))


def guarded(tool: str, tool_input: dict | None = None) -> bool:
    """Calls whose guard must fail closed when the config can't be read (R3.5)."""
    return tool in SHELL_TOOLS or _sends(tool, tool_input or {}, {}) or routed(tool, tool_input or {})


def check(tool: str, tool_input: dict, config: dict, cwd: str | None = None) -> str | None:
    """cwd is the session's working directory (the hook payload's `cwd`); defaults to this process's."""
    if not cwd:
        try:
            cwd = str(tool_input.get("workdir") or "") or os.getcwd()
        except OSError:
            cwd = os.path.expanduser("~")
    if tool in SHELL_TOOLS:
        command = shell_command(tool_input)
        return check_destructive(command, config, cwd) or check_deploy(command, config, cwd)
    if routed(tool, tool_input):
        reason = check_account(tool, tool_input, config, cwd)
        if reason:
            return reason  # before the send approval, so no approval is spent on the wrong account
    if _sends(tool, tool_input, config):
        return check_send(tool, tool_input, config)
    return None
