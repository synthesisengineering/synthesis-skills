"""Pre-tool guards (R3). Each returns None to allow, or a reason to block.

Guarded: sends (R3.1), the account a calendar or mail call acts as (R3.6),
deploys and their date rules (R3.2, R3.7), and destructive commands (R3.4).
These fail closed when their config can't be read or is malformed (R3.5).
"""

from __future__ import annotations

import fnmatch
import itertools
import json
import math
import os
import re
import shlex
import time
from datetime import date, datetime

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
    r"\S*publish_drive\.py\b",  # the knowledge base's Drive copy: a script's own upload is not in the command's text
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
# The workspace connector's mail tools read an attachment given as a path from the connector's own disk, and only
# from its attachment folder and the folders ALLOWED_FILE_DIRS names, where its start script names the outbox. A
# file elsewhere was refused after the send was approved; beside one it could read, the mail went without it (2026-11-12).
# The guard counts the outbox and the connector's default attachment folder and nothing its own process has in
# ALLOWED_FILE_DIRS: that is the session's setting, and a connector a supervisor started carries its own.
# What counts as attached is what its source (2.1.0) reads: the entry's `url`, else the file at its `path`, else base64
# `content` with a `filename`, an entry it cannot read that way being left out (gmail_tools._prepare_gmail_message);
# and from no folder a file whose name or folder marks secrets (core.utils.validate_file_path, copied here).
# Five Drive tools read a local file under the same rule: `file_path`, a path or a file:// URL, for update_drive_file
# and the three imports (drive_helpers._resolve_import_media); `fileUrl`, when it is a file:// URL, for
# create_drive_file. Their `file_url`, and any other `fileUrl`, is fetched over http or https and is no file here.
FILE_MAIL_TOOLS = frozenset({"send_gmail_message", "draft_gmail_message"})
FILE_DRIVE_TOOLS = {"update_drive_file": "file_path", "import_to_google_doc": "file_path", "import_to_google_sheets": "file_path",
                    "import_to_google_slides": "file_path", "create_drive_file": "fileUrl"}
ENTRY_KEYS = ("url", "path", "content", "filename", "mime_type", "content_id")  # the first three are where it reads from
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")  # it takes line breaks and NULs out of a filename and fails on others
CONTENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+\-@]*")  # gmail_tools.CONTENT_ID_SAFE_RE, the `content_id` it takes
SECRET_NAMES = frozenset({".credentials", ".credentials.json", "credentials.json", "client_secret.json", "client_secrets.json",
                          "service_account.json", "service-account.json", ".npmrc", ".pypirc", ".netrc", ".git-credentials"})
SECRET_FOLDERS = ("/proc", "/sys", "/dev", "/etc/shadow", "/etc/passwd", "/private/etc/shadow", "/private/etc/passwd",
                  "~/.kube", "~/.gnupg", "~/.config/gcloud")
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


# 2026-11-12: a connector tested on a laptop behind a quick tunnel was handed to two colleagues in direct messages that
# carried the tunnel's address. One relied on it, and a restart of the laptop's app took the address away for good.
TUNNELS = (".trycloudflare.com", ".ngrok.io", ".ngrok.app", ".ngrok.dev", ".ngrok.pizza", ".ngrok-free.app", ".ngrok-free.dev",
           ".ngrok-free.pizza", ".loca.lt", ".localtunnel.me", ".serveo.net", ".serveousercontent.com", ".localhost.run",
           ".lhr.life", ".lhr.rocks", ".pinggy.io", ".pinggy.link", ".pinggy-free.link", ".devtunnels.ms", ".app.github.dev",
           ".ts.net", ".tunnelmole.net", ".bore.pub", ".loophole.site")
# The knowledge-base connector refuses to start on the same services (its TEMPORARY_HOSTS); a test holds the two equal.
HOSTNAME = re.compile(r"(?<![\w.@-])(?:[a-z0-9-]+\.)+[a-z][a-z0-9-]*(?![\w-])")
NAMED = re.compile(rf"({HOSTNAME.pattern})(?::(\d{{1,5}})(?!\w))?")  # a name and its port, if it has one
_HOST = r"(localhost|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.local(?:host)?|\d{1,3}(?:\.\d{1,3}){3}|\[[0-9a-f:.]+(?:%[\w.-]+)?\])"
# A host is read whole: after any scheme or where a bare one starts, to where its name ends, then its port. A public
# name that only begins like a local one (localhost.example.org, 10.2.3.4.example.org) is no match (2026-11-12). The
# host of a file:// URL names this disk, as a connector takes a local file: file://localhost/<path> is no address.
LOCAL = re.compile(rf"(?:(?<!file)(://)|(?<![\w.@-])){_HOST}(?![\w-]|\.[\w-])\.?(?::(\d+)(?!\w))?")
NEAR = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")  # the private ranges, and IPv6's unique-local one
FILED = re.compile(r"(?:^|\.)(?:config|conf|cfg|cnf|ini|env|rc|settings|properties|json|ya?ml|toml|makefile|dockerfile)\.local$")


def _only_here(m, low: str) -> str:
    """The address one match of LOCAL spells, host and port, when only this machine or its network answers it: a local
    name or a private or link-local address written as an address (after any scheme but file://, or with a port of one
    to five digits), a loopback or any-interface address however written, and a bracketed IPv6 one that is any of
    these or unique-local, however written. "" for any other, and for a file's name with its line number: a name ending
    in .local with no scheme before it that is a configuration file's (config.local:7), follows a path
    (src/app.local:42) or has a column after its line (notes.local:17:3). A dotfile (.env.local:12) and a name that
    goes on (settings.local.json:3) are no match at all. An IP address with no scheme, no `//` and no port before a
    prefix length (/0 to /32, to /128 for a bracketed IPv6 one) names a range (10.0.0.0/8, [fd00::]/8): ""."""
    import ipaddress
    (scheme, host, port), at = m.groups(), m.start(2)
    shown, told = host + (":" + port if port else ""), bool(scheme) or bool(port) and len(port) < 6
    if host[-1].isalpha():
        filed = host.endswith(".local") and not scheme and bool(
            FILED.search(host) or low[at - 1:at] in ("/", "\\") and low[max(at - 2, 0):at] != "//"
            or re.match(r":\d", low[m.end():m.end() + 2]))
        return shown if told and not filed else ""
    ranged = re.match(r"/(\d{1,3})(?![\w/]|\.\w)", low[m.end():])  # past it, only what ends a word
    if ranged and not (scheme or port or low[max(at - 2, 0):at] == "//") and int(ranged[1]) <= (128 if host[0] == "[" else 32):
        return ""
    try:
        ip = ipaddress.ip_address(host.strip("[]").split("%")[0])  # past a zone: fe80::12%en0
    except ValueError:
        return ""
    ip = getattr(ip, "ipv4_mapped", None) or ip  # ::ffff:10.0.0.1 is 10.0.0.1
    near = ip.is_link_local or any(ip in ipaddress.ip_network(net) for net in NEAR)
    return shown if ip.is_loopback or ip.is_unspecified or near and (told or host[0] == "[") else ""


def temporary_addresses(texts: list, config: dict):
    """The addresses in these words that can change, or that only this machine or its network answers: a quick tunnel's
    host (a subdomain of a tunnel service, or a host the config names and its subdomains), a tunnel service's own host
    with a port (bore.pub:41234, as bore hands one out; its bare name and its documentation are none) and, unless `local` is false,
    a local name or a private address written with a scheme or a port, and a loopback address however written
    (`_only_here`). A user and password before a host are read past and never shown. A string when the setting
    cannot be read. {"temporary_addresses": {"hosts": ["<more>"], "local": true}}; no key, no rule, and a key that is
    there and null is a setting that cannot be read."""
    if "temporary_addresses" not in config:
        return []
    rule = config["temporary_addresses"]
    more, local = (rule.get("hosts", []), rule.get("local", True)) if isinstance(rule, dict) else (None, None)
    if not isinstance(more, list) or not all(isinstance(h, str) and h.strip() for h in more) or not isinstance(local, bool):
        return ('temporary_addresses in the synthesis config needs an object, {} or one with "hosts" as a list of host names '
                'and "local" as true or false (either may be absent); sends are blocked until it is fixed')
    exact, own = {h.strip().lower().lstrip(".") for h in more}, {h.lstrip(".") for h in TUNNELS}
    ends, found = TUNNELS + tuple("." + h for h in exact), set()
    for low in (re.sub(r"://[^\s/?#]*@", "://", str(text).lower()) for text in texts):  # to the last @: a password may hold one
        for h, port in NAMED.findall(low):
            found |= {h} if h in exact or h.endswith(ends) else {f"{h}:{port}"} if port and h in own else set()
        found |= {_only_here(m, low) for m in LOCAL.finditer(low)} - {""} if local else set()
    return sorted(found)


def message_problems(tool: str, tool_input: dict, config: dict, chans: set | None = None, session: dict | None = None) -> list[str]:
    """Why this outgoing message can't go as written, before anyone is asked to approve it. A register rule naming
    channels holds only there (2026-10-27: a line that fits scheduling went out on Jira answers). An address that can
    change is released only by the principal's approval of the address itself, which the message's own never is."""
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
    held = temporary_addresses(texts, config)
    if isinstance(held, str):
        return [held]
    if held and not approvals.backed("temporary-address", held, session):
        code = approvals.request("temporary-address", held, "an address that can change, in a message: " + ", ".join(held)[:140])
        return [f"it holds an address that can change or that only this machine answers ({', '.join(held)}). Such an address "
                "is never given to anyone: what another person uses runs at a permanent address, on infrastructure that outlives "
                f"this machine. If the principal means to send exactly this (their own test), they type {approvals.how(code)} "
                "for the address itself; the message then still waits for its own approval"]
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
    return problems + _unread_files(tool, tool_input)


def _unread_files(tool: str, tool_input: dict, bound: dict | None = None, whole: bool = True) -> list[str]:
    """Why a workspace-connector call would not attach or upload what it names, judged as the connector reads it. A
    file is judged as it reads one: the path whole (it resolves a relative one in its own folder and expands no
    `~`), links followed, letters as written, the file inside the outbox or the connector's default attachment
    folder, and not one it reads from nowhere. A Drive call gives the file's content once. Given `bound`, each file
    it would read goes into it under its real path with the hash of its bytes (of its first byte alone when not
    `whole`, which shows it can be read), and one that cannot be read is a problem."""
    name = tool.rsplit("__", 1)[-1]
    key, given = FILE_DRIVE_TOOLS.get(name), tool_input.get("attachments") if name in FILE_MAIL_TOOLS else None
    if not key and given is None:
        return []
    try:  # some clients send the list as its JSON text, which the connector reads too: a list's text and no other
        parsed = json.loads(given) if isinstance(given, str) else None
        given = parsed if isinstance(parsed, list) else given
    except ValueError:
        pass
    outbox, problems, until = paths.outbox(), [], time.monotonic() + HASH_SECONDS
    roots = tuple(os.path.realpath(os.path.expanduser(r)).rstrip(os.sep) + os.sep for r in (str(outbox), "~/.workspace-mcp/attachments"))
    rule = (": the mail connector takes an attachment only from its `url`, the file at its `path` or standard base64 "
            "`content` with a `filename`, so this one would not go as given. Give one of the three (a file by its full "
            f"path, staged in {outbox}) and file this send again")
    stage = f"copy the file into {outbox} (make the folder if it is missing), give that copy's full path "

    def fetched(url: str) -> str:
        """Why the mail connector would not attach a `url` as given (2.1.0: _resolve_url_attachments). Its own download
        link it reads from its disk, with no host or on one its settings name, which the guard cannot see; any other
        `url` it fetches over http or https from a named host, and in no other way."""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            parts, web = parsed.path.strip("/").split("/"), parsed.scheme in ("http", "https") and bool(parsed.hostname)
        except ValueError:
            parts, web = [], False
        if len(parts) == 2 and parts[0] == "attachments":
            return (f"gives the `url` {url}, which the mail connector reads as its own download link (`/attachments/<id>`, "
                    "on any host it may serve) from a file it saved on this disk, bytes an approval cannot bind: "
                    f"{stage}as the attachment's `path`, and file this send again")
        return "" if web else (f"gives the `url` {url}, and the mail connector fetches a `url` only over http or https "
                               f"from a named host, so it would attach nothing: for a file on this disk, {stage}as the "
                               "attachment's `path`, and file this send again")

    def unread(file: str, what: str = "the attachment", who: str = "the mail connector",
               give: str = "as the attachment's `path`, and file this send again") -> str:
        if "\0" in file:  # it names no file, and a newer Python raises where such a path is resolved
            return f"{what} {file!r} holds a NUL character, which names no file: {stage}{give}"
        real = os.path.realpath(file)
        names = real.lower().split(os.sep)
        why = ("is not a full path" if not os.path.isabs(file) else "does not exist" if not os.path.exists(real)
               else "is not a file" if not os.path.isfile(real) else "")
        if not why and (names[-1] in SECRET_NAMES or any(n in (".env", ".ssh", ".aws") or n.startswith(".env.") for n in names)
                        or any((real + os.sep).startswith(os.path.expanduser(f) + os.sep) for f in SECRET_FOLDERS)):
            return (f"{what} {file} is one {who} never reads, whatever folder holds it, since its name "
                    "or a folder above it marks secrets (a .env, key or credentials file): leave it out and tell the principal")
        why = why or ("" if real.startswith(roots) else f"is outside the folders {who} reads")
        try:
            if not why and bound is not None:
                bound[real] = _sha256(real, until, whole)
        except (OSError, ValueError) as exc:
            return f"{what} {file} cannot be read ({exc.strerror or exc})"
        return why and f"{what} {file} {why}: {stage}{give}"

    named, remote = tool_input.get(key) if key else None, tool_input.get("file_url") if key == "file_path" else None
    twice = [k for k in ("content", "file_path", "file_url", "base64_content") if tool_input.get(k) is not None] if key == "file_path" else []
    if len(twice) > 1:
        problems.append(f"this call gives {' and '.join(f'`{k}`' for k in twice)}, and the connector takes exactly one source "
                        "for a file's content: give one and make this call again")
    if isinstance(named, str):
        from urllib.parse import unquote, urlparse
        give = f"as `{key}`" + (", after `file://`," if key == "fileUrl" else "") + " and make this call again"
        try:
            url = urlparse(named)  # a file:// URL is the path in it, percent-decoded, led by any host but localhost
        except ValueError as exc:  # the connector parses it the same way first, and fails the call
            problems.append(f"`{key}` {named} cannot be parsed as a path or a URL ({exc}), so the connector would refuse "
                            f"the call: give the staged file's full path {give}")
            url = None
        if url and url.scheme == "file":
            named = unquote(("//" + url.netloc if url.netloc.lower() not in ("", "localhost") else "") + url.path)
        if url and (url.scheme == "file" or key == "file_path"):
            problems.append(unread(named, "the file", "the connector", give))
    if isinstance(remote, str) and (remote.lower().startswith("file:") or os.path.isabs(remote)):
        problems.append(f"`file_url` is fetched over http or https, and {remote} is a file on this disk: copy the file into "
                        f"{outbox} (make the folder if it is missing), give that copy's full path as `file_path` and make "
                        "this call again")
    if given is not None and not isinstance(given, list):
        problems.append("`attachments` is neither a list of entries nor the JSON text of one, and the mail connector "
                        "refuses any other shape: give a list with one entry for each file and file this send again")
    for place, entry in enumerate(given if isinstance(given, list) else [], 1):
        if not isinstance(entry, dict):
            problems.append(f"attachment {place} is not an object{rule}")
            continue
        sources = [k for k in ENTRY_KEYS[:3] if (k in entry if k == "url" else entry.get(k))]  # a `url` key leads, even empty
        shown, cid = entry.get("filename"), entry.get("content_id")
        which = f"attachment {place}" + (f" ({shown})" if isinstance(shown, str) and shown and not CONTROL.search(shown) else "")
        unknown, url = ", ".join(f"`{k}`" for k in entry if k not in ENTRY_KEYS), entry.get("url")
        set_here = [f"`{k}`" for k in ("error", "_resolved_bytes") if k in entry]
        if set_here:
            problems.append(f"attachment {place} carries {' and '.join(set_here)}, which the mail connector sets on an entry "
                            "itself: it leaves out an entry that carries `error`, and takes `_resolved_bytes` before the "
                            "entry's own source. Remove it and file this send again")
        texts = [f"`{k}` {entry[k]!r}" for k in ("filename", "mime_type")
                 if entry.get(k) and not (isinstance(entry[k], str) and not CONTROL.search(entry[k]))]
        if texts:
            problems.append(f"attachment {place} gives {' and '.join(texts)} with a control character, or not as text: the "
                            "mail connector takes line breaks and NULs out of a filename, so it goes under another name than "
                            "the one shown, and leaves out an entry whose name or type is not text. Give each as plain text "
                            "and file this send again")
        if cid and (re.search(r"[\x00-\x1f\x7f]", str(cid)) or not CONTENT_ID.fullmatch(str(cid).strip().strip("<>").strip())):
            problems.append(f"attachment {place} gives the `content_id` {cid!r}, which the mail connector refuses, leaving the "
                            "entry out: it takes letters, digits, '.', '_', '+', '-' and '@', led by a letter or a digit, in "
                            "angle brackets or not. Give one such and file this send again")
        if sources == ["path"]:
            problems.append(unread(str(entry["path"])))
        elif sources == ["url"] and isinstance(url, str) and url.strip():
            fault = fetched(url)
            problems.append(fault and f"{which} {fault}")
        elif len(sources) > 1:
            problems.append(f"{which} gives {' and '.join(f'`{s}`' for s in sources)}: the mail connector reads only the "
                            f"`{sources[0]}` of such an entry, empty or not, and never the rest; give one of them and file "
                            "this send again")
        else:
            fault = ("has none of `path`, `content` and `url`" + (f" ({unknown}: not read)" if unknown else "") if not sources
                     else "has an empty `url`" if sources == ["url"]
                     else "gives `content` with no `filename`" if not entry.get("filename")
                     else "" if _standard_base64(entry["content"]) else "gives `content` that is not standard base64")
            problems.append(fault and f"{which} {fault}{rule}")
    return [p for p in problems if p]


def _standard_base64(text) -> bool:
    """Whether the connector's decoder gives back the bytes this encodes. It skips every letter outside the standard
    alphabet, so URL-safe text or a `data:` prefix decodes to other bytes, or to nothing it can attach."""
    import base64
    try:
        return isinstance(text, str) and base64.b64decode("".join(text.split()), validate=True) is not None
    except ValueError:
        return False


HASH_SECONDS = 2.0  # of the 5 a pre-tool-use hook is given: a harness passes over a hook that runs past its time


def _sha256(file: str, until: float, whole: bool = True) -> str:
    """The hash of a file's bytes (of its first byte alone when not `whole`), read before `until`: a file that takes
    longer is one the guard cannot bind. A read on a stalled disk or mount blocks inside one call, past any check made
    between chunks, so the read runs in a daemon thread the guard stops waiting for at `until`, and the thread checks
    the limit again on its way out, an empty file's included. A read that never returns is left behind: the hook's
    process answers and exits without waiting for it."""
    import hashlib
    import threading
    late = TimeoutError(f"not within the {HASH_SECONDS:g} s the guard may spend reading the files a call names")
    done, out = threading.Event(), []

    def read() -> None:
        try:
            digest = hashlib.sha256()
            with open(file, "rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b"") if whole else [handle.read(1)]:
                    digest.update(chunk)
                    if time.monotonic() >= until:
                        break
            out.append(late if time.monotonic() >= until else digest.hexdigest())
        except Exception as exc:  # handed to the guard's thread, which says why the file cannot be read
            out.append(exc)
        finally:
            done.set()

    threading.Thread(target=read, name="synthesis-file-hash", daemon=True).start()
    if not done.wait(max(0.0, until - time.monotonic())):
        raise late
    if isinstance(out[0], Exception):
        raise out[0]
    return out[0]


def check_upload(tool: str, tool_input: dict) -> str | None:
    """A Drive upload that asks for no code still names a file the connector must read: one it would not read is
    refused here, as a send's is before its code, and so is one it cannot read: its first byte is read, since no
    approval binds its bytes."""
    unread = _unread_files(tool, tool_input, {}, whole=False)
    return "This call can't go as written: " + "; ".join(unread) + "." if unread else None


def check_send(tool: str, tool_input: dict, config: dict, session: dict | None = None) -> str | None:
    """session: the hook payload, whose transcript shows who typed an approval (a shell's script passes none)."""
    files: dict = {}  # each file the connector will read, with the hash of its bytes: an approval of a path alone let
    # a copy replaced in the outbox after the principal's code go out in its place (as the iMessage sender binds a photo)
    problems = message_problems(tool, tool_input, config, session=session) or _unread_files(tool, tool_input, files)
    if problems:
        return "This message can't go out as written: " + "; ".join(problems[:6]) + "."
    from synthesis import sends
    subject, chan = {"tool": tool, "input": tool_input, **({"files": files} if files else {})}, sends.channel(tool, tool_input)
    summary = f"{tool}: " + " ".join(t for _, t in _strings(tool_input))[:160]
    others = _invited_today(tool, tool_input, config)  # a meeting on today has an approval of its own; no window covers it
    if isinstance(others, str):
        return others
    kind = "send-same-day" if others else "send"
    if not others and sends.covered(chan, [t for _, t in _strings(tool_input)], _project(session), config):
        sends.log(chan, tool, summary, "window", session)
        sends.settle()
        return None
    if approvals.consume(kind, subject, session):
        sends.log(chan, tool, summary, "approval", session)
        return None
    text = " ".join(t for _, t in _strings(tool_input))
    code = approvals.request(kind, subject, f"{'SAME-DAY meeting' if others else tool}: {text[:120]}")
    reshape = RESHAPE if _reshapes_calendar(tool, tool_input) else ""
    if others:
        what = (f"puts a meeting on today's date and invites {others} other{'' if others == 1 else 's'}" if others > 0
                else "moves a meeting to today's date (its guests are on the event, not in this call)")
        return (f"This {what}. A meeting is "
                "not added to today by an agent's choice, and a requester's timing is their preference: propose another day "
                "unless the principal asked for today. If they did, show them the exact event and ask them to type "
                f"{approvals.how(code)} for this same-day meeting. Then make this identical call again." + reshape)
    return ("Sending needs the principal's approval of this exact message. Show them the exact text and "
            f"recipient and ask them to type {approvals.how(code)}. Then make this identical call again." + reshape
            + (" The approval covers each file the call has the connector read as it is now, so name those files to the "
               "principal too: one changed before the call needs a new code." if files else ""))


# 2026-10-27: a series moved to a new hour brought back an occurrence canceled at the old hour, double-booked.
RESHAPE = (" This deletes an event or sets its time or recurrence: in the same message, list its occurrences from today"
           " through the next three, canceled and moved ones included, each checked against accepted meetings (a series'"
           " cancellations stay keyed to the old start time, so moving the series brings them back); prefer changing this"
           " and following occurrences over the whole series; after the write, read back today and every date it touched.")


def _reshapes_calendar(tool: str, tool_input: dict) -> bool:
    deletes = tool.endswith("delete_event") or str(tool_input.get("action", "")).lower() == "delete"
    timed = {"start", "end", "start_time", "end_time", "startTime", "endTime", "recurrence", "rrule"} & set(tool_input)
    return bool(re.search(r"(?:create|update|manage|delete|move)_event$", tool)) and (deletes or bool(timed))


# --- same-day meetings (R3.1, R5) ---------------------------------------------------------------
# 2026-11-09: an agent staged a meeting into the first open slot of the same day, three days running, because the
# requester had said "tomorrow or Monday". The principal approved every invitation, and no approval said it was today.

START_KEYS = frozenset({"start", "start_time", "startTime", "start_datetime", "startDateTime", "start_date", "startDate"})
ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
WRITTEN = re.compile(r"\b(?:(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?|([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?)\s+(\d{4})\b")  # 9 November 2026; Nov 9, 2026


def _today() -> date:
    return date.today()


def _starts(value):
    """Every start a calendar call names: flat, nested ({"dateTime": ...}) and inside a list of events."""
    for key, item in value.items() if isinstance(value, dict) else ():
        if key in START_KEYS:
            yield from (str(v) for v in (item.values() if isinstance(item, dict) else [item]) if isinstance(v, str))
        else:
            yield from _starts(item)
    for item in value if isinstance(value, list) else ():
        yield from _starts(item)


GUESTS = re.compile(r"attend|guest|invite|particip", re.I)
ADDRESS_KEYS = ("email", "address", "emailAddress", "mail")  # an entry's own address; a display name can look like one
CALENDAR_WRITE = re.compile(r"(?:create|update|manage|move)[_-]events?$")


def _invitees(value, inside: bool = False):
    """Addresses of the people a calendar call invites: anywhere under an attendee, guest, invitee or participant
    field, whatever shape each entry takes. People a call removes are not invited, and a booked room is not a person."""
    if isinstance(value, dict):
        own = inside and any(k in value for k in ADDRESS_KEYS)
        for key, item in value.items():
            if not re.search(r"remov", key, re.I) and (not own or key in ADDRESS_KEYS):
                yield from _invitees(item, inside or bool(GUESTS.search(key)))
    elif isinstance(value, list):
        for item in value:
            yield from _invitees(item, inside)
    elif inside and isinstance(value, str):
        yield from (a for a in ADDRESS.findall(value.lower()) if not a.endswith("@resource.calendar.google.com"))


def _keys(value):
    for key, item in value.items() if isinstance(value, dict) else ():
        yield key
        yield from _keys(item)
    for item in value if isinstance(value, list) else ():
        yield from _keys(item)


def _events(value):
    """Each event a call writes: the entries of any list of events inside it, however deep the list sits."""
    for item in value.values() if isinstance(value, dict) else value if isinstance(value, list) else ():
        if isinstance(value, list) and isinstance(item, dict) and any(_starts(item)):
            yield item
        else:
            yield from _events(item)


HOLDS_READER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills", "synthesis-chief-of-staff",
                            "scripts", "holds_state.py")


def _own_hold(event: dict) -> bool:
    """Whether the event a call names is a hold the agent placed that is in force today. The chief of staff's
    holds ledger is the one record of which calendar entries are the agent's own, and its own reader is asked
    (a copy of its rules here once missed expiry and a day's release). A reader or a ledger that cannot be read
    proves nothing, so the move is approved like any other."""
    named = {text for key, text in _strings(event) if re.fullmatch(r"(?:event_?)?id", key, re.I)}
    try:
        ledger = type(os)("holds_state")
        with open(HOLDS_READER, encoding="utf-8") as source:
            exec(compile(source.read(), HOLDS_READER, "exec"), ledger.__dict__)  # no import: nothing is written beside it
        return bool(named) and any(hold.get("id") in named for hold in ledger.current(ledger.load_events(), _today()))
    except Exception:  # noqa: BLE001
        return False


TRAVEL_READER = os.path.join(os.path.dirname(HOLDS_READER), "travel_check.py")
PLACE_KEYS = frozenset({"location", "locations", "where", "place", "venue"})


def _place(value, under: bool = False):
    """Each text a call gives for where an event is: what a location field holds, written out or as a structure."""
    for key, item in value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else ():
        yield from _place(item, under or str(key).lower() in PLACE_KEYS)
    if under and isinstance(value, str) and value.strip():
        yield value.strip()


def check_travel(tool: str, tool_input: dict, config: dict) -> str | None:
    """A calendar write that puts the principal at a place carries the event's travel line, or is refused with the
    way to earn one (2026-11-11: an evening 28 miles from home sat on a calendar for six days with no way to get
    there, and the agent that wrote it was never asked). What a place is and what a travel line is are asked of
    the chief of staff's own travel check and the principal's travel policy; no copy of either lives here. It
    reads the call alone and asks for no approval. {"in_person_travel": {"preferences": "<the preferences file>"}};
    no key, no change; a policy that cannot be read refuses a write that names a place, and only that one: what a
    place is is the policy's to say, and a call that names none needs none (2026-11-11: with no preferences file
    every calendar write was refused, a hold with no location among them)."""
    rule = config.get("in_person_travel")
    if rule is None or not CALENDAR_WRITE.search(tool):
        return None
    try:
        events = [*_events(tool_input)] or [tool_input]
        if not any(next(_place(event), "") for event in events):
            return None
        with open(os.path.expanduser(str(rule["preferences"])), encoding="utf-8") as source:
            policy = json.load(source)["travel_policy"]
        reader = type(os)("travel_check")
        reader.__file__ = TRAVEL_READER
        with open(TRAVEL_READER, encoding="utf-8") as source:
            exec(compile(source.read(), TRAVEL_READER, "exec"), reader.__dict__)  # no import: nothing is written beside it
        title = str(policy.get("block_title") or "Travel").lower()
        for event in events:
            said = {key.lower(): text for key, text in _strings(event)}
            name = next((said[k] for k in ("summary", "title", "subject", "name") if said.get(k)), "an event")
            notes = "\n".join(said.get(k, "") for k in ("description", "notes", "body", "details"))
            spot = ", ".join(_place(event))
            block = reader.is_block(name, reader.lines(notes), title)  # a block as the travel check knows one: by its title's form or its lines
            if reader.place(spot, policy) == "away" and not block and not reader.form(reader.lines(notes).get("travel")):
                return (f"Refused: this writes \"{name}\" at a place ({spot}) and says nothing about how the "
                        "principal gets there. Work the trip out first (synthesis-chief-of-staff, references/in-person-travel.md): "
                        "who pays, the exact address, the trip door to door from a live source, a travel block on each side. "
                        "Then put the event's travel line in its description (`Travel: blocks before and after`, or `Travel: "
                        "local, N min walk`, or `Travel: none, <why>`) and make the call again. This needs no approval.")
    except Exception as exc:  # noqa: BLE001
        return (f"Refused: in_person_travel is set, and the travel policy cannot be read ({exc!r}). It is the travel_policy "
                "section of the preferences file that key names; a calendar write is not judged without it.")
    return None


def _falls(text: str, zones: list, unread: bool) -> str:
    """"today" when the date as written is today (ISO, or a written date such as "9 November 2026 at 3:00 PM"), the
    same moment is today on this machine's clock, or (for a time with no offset) it is today in a zone the event
    names; "unknown" when it names a zone this machine cannot read and the date as written is within a day of
    today, so it could be; "" otherwise."""
    today, text = _today(), text.strip()
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00").replace(" ", "T", 1))
        local = [m.astimezone().date() for m in ([moment] if moment.tzinfo else [moment.replace(tzinfo=z) for z in zones])]
    except (ValueError, OverflowError, OSError):  # not an ISO time, or one no calendar holds: only its written date can count
        found = WRITTEN.search(text)
        day, month, year = (found.group(1) or found.group(4), (found.group(2) or found.group(3)).lower(), found.group(5)) if found else ("", "", "")
        written = month in MONTHS and (int(year), MONTHS.index(month) + 1, int(day)) == (today.year, today.month, today.day)
        return "today" if written or text.startswith(today.isoformat()) else ""
    if moment.date() == today or today in local:
        return "today"
    return "unknown" if unread and not moment.tzinfo and abs((moment.date() - today).days) <= 1 else ""


def _invited_today(tool: str, tool_input: dict, config: dict) -> int | str:
    """How many other people a calendar write invites to a meeting that starts today; -1 when it moves an existing
    event to today and names no guest list (the guests are on the event, not in the call); 0 when the rule does
    not apply; a refusal when its setting, or a time zone that decides the day, cannot be read. Config:
    {"same_day_meetings": {"exempt": ["<address or pattern>"], "own": ["<address or pattern>"]}}: a meeting with an
    exempt guest keeps the ordinary approval, and `own` lists the principal's addresses beyond those account
    routing names. Each event in a call that writes several is judged by itself. No key, no rule."""
    rule = config.get("same_day_meetings")
    if rule is None or not CALENDAR_WRITE.search(tool):
        return 0
    exempt, mine = (rule.get("exempt", []), rule.get("own", [])) if isinstance(rule, dict) else (None, None)
    if not all(isinstance(names, list) and all(isinstance(e, str) for e in names) for names in (exempt, mine)):
        return ("same_day_meetings in the synthesis config needs \"exempt\" and \"own\" as lists of addresses or patterns "
                "(either may be empty or absent); calendar writes are blocked until it is fixed")
    routing = config.get("account_routing") if isinstance(config.get("account_routing"), dict) else {}
    own = {_address(str(a)) for meta in [routing, *(routing.get("workspaces") or {}).values()] if isinstance(meta, dict)
           for a in [meta.get("default_account"), meta.get("account"), *(meta.get("aliases") or [])] if a}
    moves = bool(re.search(r"(?:update|move)[_-]events?$", tool)) or str(tool_input.get("action", "")).lower() == "update"
    shared = {k: v for k, v in tool_input.items() if isinstance(v, str)}  # a zone named once for the whole call
    count = 0
    for event in list(_events(tool_input)) or [tool_input]:
        zones, unread = [], []
        for key, text in [*_strings(event), *shared.items()]:  # an event's own zone, never another event's
            if re.search(r"time_?zone", key, re.I):
                try:
                    from zoneinfo import ZoneInfo
                    zones.append(ZoneInfo(text))
                except (KeyError, ValueError, OSError):  # a name this machine does not know, such as a Windows one
                    unread.append(text)
        when = {_falls(start, zones, bool(unread)) for start in _starts(event)}
        invited = {a for a in set(_invitees(event)) - own if not any(fnmatch.fnmatchcase(a, m.lower()) for m in mine)}
        listed = any(re.fullmatch(r"attendees|guests|invitees|participants", key, re.I) for key in _keys(event))
        others = len(invited) or (-1 if moves and not listed and not _own_hold(event) else 0)
        if not others or not when & {"today", "unknown"} or any(fnmatch.fnmatchcase(a, e.lower()) for a in invited for e in exempt):
            continue
        if "today" not in when:
            return (f"This event's start names a time zone this machine cannot read ({unread[0]}), so it cannot tell "
                    "whether the meeting falls on today. Give the start with a UTC offset, or name the zone the IANA way "
                    "(for example Asia/Tokyo), and make the call again.")
        count = others if others < 0 and not count else max(count, 0) + max(others, 0)
    return count


# --- account routing (R3.6) ---------------------------------------------------------------------
# Calendar, mail and sharing calls act as an account, and their recipients see which one: an
# invitation sent from the wrong account cannot be unsent (2026-09-11). Matched on the tool's own
# name after the last "__"; reads are never routed. `send_message` is Gmail on one connector, Google
# Chat on another and session-to-session messaging on a third, so it is routed only when it
# addresses a mailbox or a Chat space. Slack sends belong to the send guard alone.

ROUTED_TOOLS = frozenset({
    "create_event", "update_event", "delete_event", "manage_event", "move_event", "respond_to_event",
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
HANDED = "$(xargs)"  # stands for the files xargs hands a command; the lexer never yields this as a word
STDIN = frozenset({"/dev/stdin", "/dev/fd/0", "/proc/self/fd/0", "-"})
INTERPRETER = re.compile(r"(node|bun|deno|python(\d+(\.\d+)*)?)$")  # python3.12 runs scripts too
KEYWORDS = frozenset({"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until", "time", "fi", "done"})
# Commands that run the command after their own options; the set holds options that take a value.
WRAPPERS = {"env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, "command": set(), "exec": {"-a"},
            "nohup": set(), "time": set(), "nice": {"-n", "--adjustment"},
            "timeout": {"-s", "--signal", "-k", "--kill-after"}, "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "--chdir", "-U"},
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
    """Simple commands: "(" and ")" for subshells, else (words, stdin texts, scripts, piped in, files written,
    link). The link is "&&" when only `&&` stands between a command and the one before it, so it runs only if that
    one succeeded; "||" when it runs only if that one failed; "" otherwise."""
    items, words, stdin, scripts, skip, piped, writes, before = [], [], [], [], "", False, [], []
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
                link = before[0] if before[:1] in (["&&"], ["||"]) and set(before[1:]) <= {"\n"} else ""  # `&&` may end a line
                items.append((words, stdin, scripts, piped, writes, link))
                before = []
            before.append(rest[0])
            words, stdin, scripts, skip, writes = [], [], [], "", []
            piped = rest[0] in ("|", "|&")
            if rest[0] in "()":
                items.append(rest[0])
    return items


def _bare(words: list[str], moved: list | None = None) -> tuple[list[str], list[str]]:
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
        if head == "trap":  # what it keeps to run when the shell ends or a signal comes: the word before its signals, past `--`
            rest = list(itertools.dropwhile(lambda w: w in ("--", "-l", "-p"), words[1:]))
            scripts += [w for w in rest[:1] if len(rest) > 1 and w != "-"]
        if head not in WRAPPERS:
            break
        takes, i = WRAPPERS[head], 1
        while i < len(words) and ((words[i].startswith("-") and words[i] != "-")
                                  or (head == "env" and re.match(r"[A-Za-z_]\w*=", words[i]))):
            sent = (words[i + 1:i + 2] if words[i] in (("-C", "--chdir") if head == "env" else ("-D", "--chdir"))
                    else [words[i].split("=", 1)[1]] if words[i].startswith("--chdir=") else [])
            if moved is not None and head in ("env", "sudo") and sent:
                moved.append(sent[0])  # `env -C <folder> <command>`, `sudo -D <folder> <command>`: the command runs there
            if words[i] in ("-S", "--split-string") and i + 1 < len(words):
                scripts.append(words[i + 1])
            elif words[i].startswith("--split-string="):
                scripts.append(words[i].split("=", 1)[1])
            i += 2 if words[i] in takes else 1
        if head == "xargs" and words[i:]:  # the files it hands a command arrive on its input: HANDED stands where they go
            mark = next((w[2:] or "".join(words[k + 1:k + 2]) for k, w in enumerate(words[1:i], 1) if w[:2] in ("-I", "-J")), "")
            words[i:] = [w.replace(mark, HANDED) for w in words[i:]] if mark else words[i:] + [HANDED]
        words = words[i + (head == "timeout"):]  # timeout's first operand is its duration
    return words, scripts


POSITIONAL = re.compile(r"\$(?:\{(\d+|[@*])\}|([\d@*]))")
REBOUND = re.compile(r"\bset\s+--|\bshift\b|\(\)\s*[{(]|\bfunction\s")  # the script gives $1 another value: a function's own, `set --`


def _placed(script: str, given: list[str]) -> str:
    """A shell's script with the words that follow it put where it uses them: $0, $1, ${10}, "$@", $*. Each is put
    as the shell takes it: nothing inside single quotes, whole inside double quotes, split at its spaces outside
    them. A script that gives them other values is left as written (2026-11-11, the seventh review: a list handed
    to the shell lost the words after its script, and `sh -s <state folder>` read its script with no $1)."""
    out, i, single, double, outer = [], 0, False, False, []  # outer: for each open substitution, how it opened and the quoting around it
    while i < len(script) and not REBOUND.search(script):
        use = POSITIONAL.match(script, i) if script[i] == "$" and not single else None
        if use or (script[i] == "\\" and not single):
            key = (use[1] or use[2]) if use else ""
            took = given[1:] if key in ("@", "*") else given[int(key):int(key) + 1] if use else []
            out.append(script[i:i + 2] if not use else ('" "' if key == "@" else " ").join(re.sub(r'(["\\$`])', r"\\\1", w) for w in took)
                       if double else " ".join(shlex.quote(part) for w in took for part in w.split()))
            i = use.end() if use else i + 2
            continue
        if not single and (script[i:i + 2] == "$(" or script[i] == "`" and "`" not in outer[-1:]):
            outer, double = outer + [script[i], double], False  # inside a substitution quoting starts over
        elif not single and not double and outer and script[i] in ("`" if outer[-2] == "`" else ")"):
            double = outer.pop()
            outer.pop()
        single, double = single if double else (script[i] == "'") != single, double if single else (script[i] == '"') != double
        out.append(script[i])
        i += 1
    return "".join(out) + script[i:]


def _shell_input(words: list[str]) -> tuple[str | None, bool, list[str]]:
    """(script given with -c, reads its script from stdin, the words it takes as $0, $1 ...) for a shell or `source`
    command. After -s the words are the script's own, and the script comes on stdin."""
    head = os.path.basename(words[0])
    if head in ("source", "."):
        args = [w for w in words[1:] if w != "--"]
        return None, bool(args) and args[0] in STDIN, args
    if head not in SHELLS:
        return None, False, []
    command, fed, i = False, False, 1
    while i < len(words):
        word = words[i]
        if word in ("-o", "+o", "-O", "+O"):
            i += 2
            continue
        if word == "--" or not word.startswith(("-", "+")):
            rest = words[i + (word == "--"):]
            if command:
                return (rest[0] if rest else None), False, rest[1:] or words[:1]
            return None, fed or not rest or rest[0] in STDIN, words[:1] + rest if fed else rest or words[:1]
        command, fed = command or bool(re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word)), fed or bool(re.fullmatch(r"-[A-Za-z]*s[A-Za-z]*", word))
        i += 1
    return None, not command, words[:1]


def _led(word: str, cwd: str) -> str:
    """A word that starts with a substitution this can read, with what that names put in: the folder of a path that
    is spelled out, a fresh temporary file or folder (made where its template says, else somewhere of its own), the
    folder the command is in, the top of the repository it is in (asked of git, as the command will ask). Any other
    substitution, or a variable the command does not set, stays as written: a bare name written after a `cd` into
    it is a write the guard cannot place (2026-11-11: `cd "$(dirname <transcript>)" && touch forged.json` was a
    write beside where the session stood; a temporary file kept in a variable was refused as unreadable)."""
    found = re.match(r"\$\(\s*(dirname|realpath|mktemp|pwd|git rev-parse --show-toplevel)\b\s*(.*?)\s*\)", word)
    try:
        words = shlex.split(found[2]) if found else []
    except ValueError:
        return word
    if not found or any(re.search(r"[$`*?]", w) for w in words):
        return word
    kind, rest = found[1], word[found.end():]
    if kind == "mktemp":
        return next((w.split("=", 1)[-1] for w in words if "/" in w), os.path.join("/tmp", "tmp.made")) + rest
    if kind in ("dirname", "realpath") and len(words) == 1:
        return (os.path.dirname(words[0]) if kind == "dirname" else words[0]) + rest
    if words or kind in ("dirname", "realpath"):
        return word
    return ((_run_git(cwd, "rev-parse", "--show-toplevel")[1].strip() if kind != "pwd" else "") or cwd) + rest


class Quoted(str):
    """The folder of a command read out of a word that was handed to a program the guard does not know (`watch`,
    `ssh`, `osascript`), which may run it. Such a command is judged for what it writes, runs and starts; it is not
    held for a path it is merely handed, since the word may be a message that mentions one."""


PLACE = re.compile(r"\$(?:(OLD)?PWD\b|\{(OLD)?PWD\})")  # the folder a command is in, and the one it was in before
DEEP = "/**"  # after a folder a command runs in: that folder or any under it (`find -execdir` runs in the folder of what it found)
OPAQUE = frozenset({"php", "lua", "luajit", "Rscript", "julia", "swift", "tclsh", "groovy", "scala", "elixir", "pwsh", "jshell"})
MESSAGE = re.compile(r"--?(?:m|msg|message|body|title|subtitle|subject|description|notes?|comment|text|caption|summary|prompt)")  # its value is words for a reader
PROMPTED = frozenset({"codex", "claude", "muse", "gh"})  # their words are prompts and messages: each runs under its own guards
STARTERS = frozenset({"echo", "printf", "cat", "cd", "pushd", "find", "sed", "perl", "tee", "touch", "truncate", "mkdir", "rmdir", "rm",
                      "unlink", "shred", "chmod", "chown", "chgrp", "dd", "cp", "mv", "ln", "install", "rsync", "ditto", "gzip", "gunzip"})


def _commands(command: str, cwd: str, depth: int = 0, writes: list | None = None, runs: list | None = None,
              feeds: list | None = None, prose: bool = False) -> list[tuple[list[str], str]]:
    """Each simple command a shell line runs, with the directory it runs in. Follows `cd`,
    subshells, substitutions, `bash -c`, eval, and scripts a shell reads from its stdin. `writes`
    collects (file, directory) for every redirect that writes a file. `runs` collects, for each
    command found and in the same order, (the `&&` chain it stands in, whether a later command of
    that chain runs only if this one ran and succeeded). `feeds` collects, the same way, the text each
    command reads on its own stdin (its heredocs and here-strings)."""
    if depth > MAX_DEPTH:
        raise Unreadable("nested too deeply")
    found, outer, upstream, chain, back, stack = [], [], "", object(), cwd, []
    for item in _simple(_lex(command)):
        if item in ("(", ")"):
            if item == "(":
                outer.append((cwd, back, list(stack)))
            elif outer:
                cwd, back, stack = outer.pop()  # a subshell's cd ends with it
            continue
        words, stdin, scripts, piped, targets, link = item
        chain = chain if link == "&&" else object()
        opening = words[:next((i for i, w in enumerate(words) if w not in KEYWORDS), len(words))]
        needed = link != "||" and "!" not in opening  # after `||` it may be skipped; under `!` its failure is what counts
        stdin = [(text if literal else PLACE.sub(lambda m: back if m[1] or m[2] else cwd, text), literal) for text, literal in stdin]
        for text, literal in stdin:
            if not literal:  # an unquoted heredoc expands its substitutions
                _dquote(text, 0, scripts, "")
        moved: list = []
        words, inner = _bare(words, moved)
        scripts = scripts + inner
        here = cwd
        for folder in moved:  # `env -C a env -C b`: b is read from a
            here = os.path.normpath(os.path.join(here, os.path.expanduser(folder)))
        head, script = os.path.basename(words[0]) if words else "", words
        # $PWD and $OLDPWD in a command's own words and targets are the folder it is in and the one before. A script it
        # hands a shell is left as written: that script puts its own, where it runs.
        words, targets = [[PLACE.sub(lambda m: back if m[1] or m[2] else cwd, w) for w in each] for each in (words, targets)]
        words = script if words and _shell_input(script)[0] is not None else words
        # Read out of a word that may be a message, a line counts as a command only when it starts as one the guard
        # knows (a shell, an interpreter, a file utility): `select ... where n > 5` and `Example: echo x > file` are words.
        taken = not prose or head in STARTERS or head in SHELLS or bool(SCRIPT.match(head)) or head in WRITERS or head in OWN_RULES or (
            head in OPAQUE or head in READERS - WORDS)  # a reader may still redirect: `date >> file`
        if writes is not None and taken:
            writes += [(t, cwd) for t in targets]
        if words and (not taken or (_named(words) and head not in PROMPTED)):  # a word it is handed may be a script it runs: read as one
            for at, word in enumerate(words[1:], 1):
                held = ([], [], [])
                try:
                    said = MESSAGE.fullmatch(words[at - 1]) or (word.startswith("-") and MESSAGE.fullmatch(word.split("=", 1)[0]))
                    inner = _commands(word, here, depth + 1, *held, prose=True) if " " in word and not said else []  # --body TEXT, --body=TEXT
                except (Unreadable, StopIteration, IndexError, RecursionError):
                    continue
                found += [(w, Quoted(h)) for w, h in inner]
                for mine, more in zip((writes, runs, feeds), held):
                    if mine is not None:
                        mine += more
        if not taken:
            continue
        if words:
            found.append((words, here))
            if runs is not None:
                runs.append((chain, needed))
            if feeds is not None:
                feeds.append("\n".join(text for text, _ in stdin))
            if words[0] in ("cd", "pushd", "popd"):  # where the next command runs: `cd -` goes back, `popd` to the folder pushd left
                to = next((w for w in words[1:] if w == "-" or not re.match(r"[-+]", w)), None)
                turn = next((w for w in words[1:] if re.fullmatch(r"[-+]\d+", w)), "")  # +N from this folder, -N from the oldest
                dirs = [cwd] + stack[::-1]  # the stack as the shell shows it: this folder first
                at = (int(turn[1:]) if turn[:1] == "+" else len(dirs) - 1 - int(turn[1:])) % len(dirs) if turn else 0
                aim = _led(os.path.expanduser(os.path.expandvars(to or "~")), cwd)
                went = back if to == "-" else aim if aim[:1] in ("$", "`") else os.path.normpath(os.path.join(cwd, aim))
                if words[0] == "cd":
                    dirs[0] = went if to is not None or not turn else dirs[at]
                elif words[0] == "popd":
                    dirs = (dirs[:at] + dirs[at + 1:]) if len(dirs) > 1 else dirs
                else:  # pushd: a folder goes on top; a number turns the stack; alone, the top two change places
                    dirs = [went] + dirs if to is not None else dirs[at:] + dirs[:at] if turn else dirs[1:2] + dirs[:1] + dirs[2:]
                cwd, back, stack = dirs[0], cwd, dirs[1:][::-1]
            if os.path.basename(words[0]) == "find":  # what it runs with -exec is a command of its own, `{}` a file under each folder it
                roots, ran = _find(words)[0], _find(script)[1]  # searches; with -execdir it runs in the folder of what it found
                scripts += [f"cd {shlex.quote(root.rstrip('/') + DEEP)} && " + shlex.join(w.replace("{}", "./{}") for w in run) if there
                            else shlex.join(w.replace("{}", os.path.join(root, "{}")) for w in run) for run, there in ran if run for root in roots]
            script, reads, given = _shell_input(words)
            if script is not None:
                scripts.append(_placed(script, given))
            elif reads:  # the shell runs whatever reaches its stdin
                scripts += [_placed(text, given) for text in [text for text, _ in stdin] + ([upstream] if piped else [])]
        said, fill = words[1:], iter(words[2:])
        if head == "printf":  # what it prints: its format with its words put in
            said = [re.sub(r"%[-0-9.]*[sbqd]", lambda m: next(fill, ""), w) for w in said[:1]]
        upstream = "\n".join([t for t, _ in stdin] + said).replace("\\n", "\n")
        for script in scripts:
            found += _commands(script, here, depth + 1, writes, runs, feeds)
    return found


def _parse(command: str, cwd: str, runs: list | None = None, feeds: list | None = None) -> tuple[list[tuple[list[str], str]], bool]:
    """(commands, readable). Unreadable text falls back to a plain split on its separators, where no
    command can be shown to depend on another."""
    try:
        return _commands(command, cwd, runs=runs, feeds=feeds), True
    except (Unreadable, StopIteration, IndexError):
        found = [(_bare(part.split())[0], cwd) for part in SEPARATORS.split(command)]
        found = [(words, where) for words, where in found if words]
        if runs is not None:
            runs[:] = [(None, False)] * len(found)
        if feeds is not None:
            feeds[:] = [""] * len(found)
        return found, False


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
    (`python3 -m twine upload`, `node release.mjs deploy`). Words passed as arguments never match, and a
    `--dry-run` (a site's build checks its deploy that way) or `--help` publishes nothing; `-h` can mean
    something else, such as rsync's human-readable sizes."""
    if "--dry-run" in words or "--help" in words:
        return False
    forms = [[os.path.basename(words[0])] + words[1:]]
    if INTERPRETER.match(forms[0][0]):  # the script it runs, or the module after -m, past its options and their values
        kind, at, name = _program(words)
        forms.append([name] + words[at + 1 + (words[at:at + 2] == [words[at], name] and words[at] != name):] if kind == "file" else [])
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


SCRIPT_LIMIT = 256 * 1024
SHEBANG = re.compile(rb"#![^\n]*\b(?:ba|z|da|k)?sh\b")


def _script_file(words: list[str], cwd: str) -> str | None:
    """The text of the shell script a command runs from a file (`bash publish.sh`, `./publish.sh`), or None."""
    head, path = os.path.basename(words[0]), None
    if head in SHELLS:
        i = 1
        while i < len(words) and words[i].startswith(("-", "+")):
            if re.fullmatch(r"[-+][A-Za-z]*c[A-Za-z]*", words[i]):
                return None  # -c: the script is on the command line, which the parser already reads
            i += 2 if words[i] in ("-o", "+o", "-O", "+O") else 1
        path = words[i] if i < len(words) else None
    elif "/" in words[0]:
        path = words[0]
    if not path:
        return None
    try:
        with open(os.path.join(cwd, os.path.expanduser(path)), "rb") as handle:
            if head not in SHELLS and handle.read(2) != b"#!":
                return None  # a program, not a script: never read past its first bytes
            handle.seek(0)
            text = handle.read(SCRIPT_LIMIT + 1)
    except OSError:
        return None
    if len(text) > SCRIPT_LIMIT or (head not in SHELLS and not SHEBANG.match(text)):
        return None
    return text.decode("utf-8", "replace")


def _script_deploys(words: list[str], cwd: str, patterns: list[str], config: dict, depth: int = 0) -> bool:
    """Whether a shell script this command runs deploys, three scripts deep. A deploy inside a script was
    invisible here (2026-10-30: `bash scripts/publish-site.sh` published a site with no approval)."""
    text = _script_file(words, cwd) if depth < 3 else None
    if text is None:
        return False
    commands, readable = _parse(text, cwd)
    if not readable and any(re.search(p, text) for p in patterns):
        return True
    return any((_deploys(w, patterns) and not _sheet_host(w, d, config)) or _script_deploys(w, d, patterns, config, depth + 1)
               for w, d in commands)


def _publishes_to(directory: str, remotes: list[str]) -> bool:
    """Whether the checkout at directory has a remote on a repository the principal listed in deploy_remotes."""
    code, out = _run_git(directory, "remote", "-v")
    found = {m.group(1).lower() for m in re.finditer(r"[/:]([\w.-]+/[\w.-]+?)(?:\.git)?\s", out)}
    return code == 0 and bool(found & {r.lower().removesuffix(".git") for r in remotes})


NPM_VALUE_OPTIONS = {"--access", "--tag", "--otp", "--registry", "--workspace", "-w", "--auth-type"}


def _publish_target(words: list[str], cwd: str) -> str:
    """What a build deploy publishes: `gh release create -R owner/repo` names its repository, `npm publish
    <path>` its package; anything else publishes the folder it runs in. Until 2026-10-30 every one was the
    folder, so a release of one repository run from another checkout counted as that checkout's deploy, bound
    its HEAD and set off its rapid-redeploy brake."""
    head = [os.path.basename(words[0])] + words[1:3]
    named = [b for a, b in zip(words, words[1:]) if a in ("-R", "--repo")] + [
        w.split("=", 1)[1] for w in words if w.startswith("--repo=")]
    if head == ["gh", "release", "create"] and named:
        return "github:" + named[0].lower()
    if head[:2] == ["npm", "publish"]:
        rest, path = words[2:], None
        while rest and path is None:
            word, rest = rest[0], rest[1:]
            if word in NPM_VALUE_OPTIONS:
                rest = rest[1:]
            elif not word.startswith("-"):
                path = word
        if path:
            return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))
    return cwd


def _targets(command: str, config: dict, cwd: str) -> list[tuple[str, str | None]]:
    """(directory, rev) for each deploy in the command. A push deploys HEAD; a build deploys the tree."""
    patterns = DEFAULT_DEPLOY_PATTERNS + list(config.get("deploy_patterns", []))
    commands, readable = _parse(command, cwd)
    targets: list[tuple[str, str | None]] = [(_publish_target(words, d), None) for words, d in commands
                                             if (_deploys(words, patterns) and not _sheet_host(words, d, config))
                                             or _script_deploys(words, d, patterns, config)]
    remotes = [str(r) for r in config.get("deploy_remotes") or []]
    for words, directory in commands if remotes else []:
        if [os.path.basename(words[0])] + words[1:3] == ["gh", "pr", "merge"]:  # a merge to a repository that publishes
            named = [b for a, b in zip(words, words[1:]) if a in ("-R", "--repo")] + [
                w.split("=", 1)[1] for w in words if w.startswith("--repo=")]
            if (named and named[0].lower() in {r.lower() for r in remotes}) or (not named and _publishes_to(directory, remotes)):
                targets.append((directory, None))
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
        if any(paths.inside(p, r) for r in repos for p in (real, main) if p) or (remotes and _publishes_to(where, remotes)):
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
        root, main = (None, None) if re.search(r"[$`]", directory) or directory.startswith("github:") else _checkout(directory)
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


TUNNEL_SSH = ("serveo.net", "localhost.run", "pinggy.io")
CARRIERS = ("pnpm", "yarn", "npm", "bun", "docker", "podman", "nerdctl")  # run the package, the program or the image their words name
NGROK = ("http", "tcp", "tls", "start", "start-all", "config", "version", "update", "diagnose", "api", "service", "credits",
         "completion", "help", "authtoken")  # its subcommands: the first five start a tunnel
LOOPHOLE = ("http", "path", "webdav", "account", "completion", "help", "version")  # its subcommands: the first three start one
SSH_VALUED = "BbcDEeFIiJLlmOoPpQRSWw"  # ssh's options that take a value: joined on, or the next word
CLOUDFLARED = ("login", "create", "route", "vnet", "run", "list", "ready", "info", "ingress", "delete", "cleanup", "token",
               "diag", "proxy-dns", "help", "h")  # `cloudflared tunnel`'s subcommands: each one a named tunnel's


def _reverse_host(rest: list[str]) -> str:
    """The host an ssh command opens a reverse forward on, "" when it opens none: its destination (the first word that
    is no option and no option's value, without the user, a scheme or a port) when -R is among its options, before the
    destination or after it: alone, in a cluster (-NR) or with its value joined on. A jump host, a key file's name and
    the words of the remote command are none of it (2026-11-12: a forward to a host that ends with a service's
    letters, and one that only named a service, were held; -NR was not)."""
    reverse, host, i = False, None, 0
    while i < len(rest) and (host is None or rest[i].startswith("-")):  # the next plain word after the destination starts the remote command
        word, i = rest[i], i + 1
        if not word.startswith("-"):
            host = re.match(r"(?:ssh://)?(?:[^@/]*@)?([^:/]*)", word.lower())[1].rstrip(".")
            continue
        at = next((j for j, c in enumerate(word) if c in SSH_VALUED), 0)  # the first letter that takes a value
        reverse, i = reverse or word[at] == "R", i + (0 < at == len(word) - 1)  # nothing joined on: its value is the next word
    return host or "" if reverse else ""


def _tunnels(words: list[str]) -> bool:
    """Does this command start a quick tunnel: an address handed out for as long as the command runs? A program is read
    without a version or a tag (localtunnel@2.0.2, cloudflare/cloudflared:latest), and the words of a package runner or
    a container from each one on, as the command it runs (2026-11-12: `docker run cloudflare/cloudflared tunnel --url`,
    `ngrok --log=stdout http` and `npx --yes localtunnel@2.0.2 --port` started unheld). `cloudflared tunnel` is quick
    with --url or --hello-world and no subcommand; with one (`tunnel run --url ... <name>`) it is a named tunnel's.
    `bore local` to bore.pub, `tmole <port>`, `loophole http`, `path` or `webdav` and `tailscale funnel <target>` start one;
    their lookups (`tailscale funnel status`) and a bore server of one's own do not."""
    def named(word: str) -> str:
        return re.split("[:@]", os.path.basename(word))[0]

    def starts(name: str, rest: list) -> bool:
        def flag(*names):
            return any(w in names or w.startswith(tuple(n + "=" for n in names)) for w in rest)

        def value(*names) -> str:  # what an option is given: joined on after "=", or the next word
            return next((w.split("=", 1)[1] if "=" in w else after for w, after in zip(rest, rest[1:] + [""])
                         if w in names or w.startswith(tuple(n + "=" for n in names))), "")
        plain = [w for w in rest if not w.startswith("-")]
        return bool(name == "cloudflared" and "tunnel" in rest and flag("--url", "--hello-world")
                    and not any(w in CLOUDFLARED for w in rest[rest.index("tunnel") + 1:])
                    or name == "ngrok" and next((w for w in rest if w in NGROK), "") in NGROK[:5]  # past its own options and their values
                    or name == "devtunnel" and rest[:1] == ["host"]
                    or name in ("lt", "localtunnel") and flag("--port", "-p")
                    or name == "bore" and rest[:1] == ["local"] and ("." + value("--to", "-t").lower()).endswith(".bore.pub")
                    or name in ("tmole", "tunnelmole") and plain[:1] and plain[0].isdigit()
                    or name == "loophole" and next((w for w in rest if w in LOOPHOLE), "") in LOOPHOLE[:3]
                    or name == "tailscale" and plain[:1] == ["funnel"] and plain[1:2] and "off" not in plain
                    and plain[1] not in ("status", "reset", "help")  # a funnel is public; `tailscale serve` is the tailnet's own
                    or name in ("ssh", "pinggy")  # to the service's own name, or a subdomain of it
                    and ("." + _reverse_host(rest)).endswith(tuple("." + s for s in TUNNEL_SSH)))
    spots = [i for i, w in enumerate(words) if i and not w.startswith("-")] if named(words[0]) in CARRIERS else [0]
    return any(starts(named(words[i]), words[i + 1:]) for i in spots)


def check_tunnel(command: str, config: dict, cwd: str, session: dict | None = None) -> str | None:
    """Starting a quick tunnel waits for the principal's code, where the config has `temporary_addresses` (the key,
    whatever it holds): its address is gone when the command stops, so it serves their own test and nothing another
    person is given."""
    if "temporary_addresses" not in config or not any(  # in each reading of it: `T=cloudflared; $T tunnel --url ...`
            _tunnels(words) for text in _resolved(command) for words, _ in _parse(text, cwd)[0] if words):
        return None
    if approvals.consume("tunnel", command, session):
        return None
    code = approvals.request("tunnel", command, f"a temporary tunnel: {command[:150]}")
    return ("This starts a temporary tunnel: its address is gone for good when the command stops. It serves the principal's "
            "own test and is never given to anyone; what another person uses is deployed at a permanent address first. Show "
            f"them this exact command and ask them to type {approvals.how(code)}. Then run the identical command again.")


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
    found = [item for text in _resolved(command) for item in _parse(text, cwd or os.getcwd())[0]]  # each reading of it
    for words, directory in found:
        if os.path.basename(words[0]) == "rm" and any(w.startswith("-") and "r" in w.lstrip("-").lower() for w in words[1:]):
            protected = protected if protected is not None else {paths.spelled(p) for p in _protected(config)}
            for target in (w for w in words[1:] if not w.startswith("-")):
                real = os.path.realpath(os.path.join(directory, os.path.expanduser(os.path.expandvars(target))))
                if paths.spelled(real) in protected or os.path.exists(os.path.join(real, ".git")):
                    return f"refusing a recursive delete of {real}: it is a protected root or a repository"
        if _git(words, directory)[0] == "push":
            rest = words[words.index("push") + 1:]
            forced = any(w in ("-f", "--force") for w in rest)
            for ref in (w for w in rest if not w.startswith("-")):
                if (forced or ref.startswith("+")) and ref.split(":")[-1].lstrip("+") in ("main", "master"):
                    return "refusing a force push to a default branch"
    return None


# --- pull-request gate (R3, R7) ------------------------------------------------------------------
# 2026-11-09: a repository whose rule was "changes land through a pull request" had taken 61 commits pushed
# straight to main in six weeks; its instructions said "push every remote", and nothing refused the push.

def _repo_names(text: str) -> set:
    return {m.group(1).lower() for m in re.finditer(r"[/:]([\w.-]+/[\w.-]+?)(?:\.git)?(?=\s|$)", text)}


ROUTING = ("remote.", "push.", "alias.", "branch.", "url.")  # config on the command line that can send a push elsewhere
GIT_COMMANDS = frozenset(  # never an alias, so no lookup is made for them
    "add am apply bisect blame branch cat-file checkout cherry-pick clean clone commit config describe diff fetch "
    "for-each-ref gc grep init lfs log ls-files ls-remote merge mv notes pull rebase reflog remote reset restore revert "
    "rev-list rev-parse rm show stash status submodule switch symbolic-ref tag update-ref version worktree".split())
REBASE_VALUES = frozenset({"--onto", "-s", "--strategy", "-X", "--strategy-option", "-x", "--exec"})  # their value is the next word
UNREAD_BRANCH = ("its default branch (where the push goes could not be read from the command, so no branch can be ruled out; "
                 "a push that names its branch outright, run by itself from the checkout, can be read)")
UNKNOWN_DEFAULT = ("what may be its default branch (this checkout does not record which branch that is: name it as \"branch\" in "
                   "the repository's pr_gated rule, or run `git remote set-head {remote} --auto` there, and push again)")


def _push(words: list[str], where: str, depth: int = 0) -> tuple[list[str], bool] | None:
    """(the words of the `git push` this command runs, whether where it goes can be read): a push named outright
    or through an alias, which may name another alias or put git options first. Config given on the command line
    that can send a push elsewhere, a shell alias that pushes, and an alias defined on the line make it unreadable."""
    i = 1
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in GIT_VALUE_OPTIONS else 1
    if os.path.basename(words[0]) != "git" or i >= len(words):
        return None
    sub, given = words[i], [b.lower() for a, b in zip(words[1:i], words[2:i + 1]) if a == "-c"]
    plain = not any(key.startswith(ROUTING) for key in given) and not any(w.startswith("--config-env") for w in words[1:i])
    if sub == "push":
        return words, plain
    if sub in GIT_COMMANDS:
        return None
    here = any(key.startswith(f"alias.{sub.lower()}=") for key in given)
    code, alias = _run_git(where, "config", "--get", f"alias.{sub}")
    alias = alias.strip() if code == 0 else ""
    try:
        expansion = [] if here or alias.startswith("!") else shlex.split(alias)
    except ValueError:
        expansion = []
    if expansion and depth < 5:
        found = _push(words[:i] + expansion + words[i + 1:], where, depth + 1)
        return (found[0], found[1] and plain) if found else None
    return (words[:i] + ["push"], False) if here or "push" in alias else None


def _switched_to(words: list[str], where: str):
    """The branch a `git checkout` or `git switch` leaves current: its name, "" when that cannot be read, or None
    when the command changes no branch (a path, a commit)."""
    rest = words[words.index("checkout" if "checkout" in words else "switch") + 1:]
    for flag, name in zip(rest, rest[1:] + [""]):
        if flag in ("-b", "-B", "-c", "-C", "--orphan"):
            return "" if not name or re.search(r"[$`]", name) else name
    names = [w for w in rest[:rest.index("--")] if not w.startswith("-")] if "--" in rest else [w for w in rest if not w.startswith("-")]
    if not names or re.search(r"[$`]", names[0]) or names[0] == "-":
        return "" if names or "-" in rest else None
    return names[0] if _run_git(where, "show-ref", "--verify", "--quiet", f"refs/heads/{names[0]}")[0] == 0 else None


PUSH_OPTIONS = ("all", "atomic", "branches", "delete", "dry-run", "exec", "follow-tags", "force", "force-if-includes",
                "force-with-lease", "ipv4", "ipv6", "mirror", "porcelain", "progress", "prune", "push-option", "quiet",
                "receive-pack", "recurse-submodules", "repo", "set-upstream", "signed", "tags", "thin", "verbose", "verify")
PUSH_SHORT = {"n": "dry-run", "d": "delete", "f": "force", "u": "set-upstream", "q": "quiet", "v": "verbose", "4": "ipv4",
              "6": "ipv6", "o": "push-option"}


def _push_options(rest: list[str]):
    """(options by their full name, the other words) as git reads a push's arguments: any unambiguous start of a
    long option, `--no-` to turn one off, the last of a pair winning, short options run together. None for the
    options when one of them cannot be read."""
    options, args, i = {}, [], 0
    while i < len(rest):
        word, i = rest[i], i + 1
        if word == "--":
            return options, args + rest[i:]
        if word.startswith("--"):
            name, given, value = word[2:].partition("=")
            off = name.startswith("no-")
            base = name[3:] if off else name
            full = [o for o in PUSH_OPTIONS if o == base] or [o for o in PUSH_OPTIONS if o.startswith(base)]
            if len(full) != 1:
                return None, args
            if full[0] in ("push-option", "repo", "receive-pack", "exec") and not given and not off:
                value, i = "".join(rest[i:i + 1]), i + 1
            options[full[0]] = False if off else value or True
        elif word.startswith("-") and len(word) > 1:
            for at, letter in enumerate(word[1:], 2):
                if letter not in PUSH_SHORT:
                    return None, args
                if letter == "o":  # the rest of the word, or the next word, is its value
                    i += not word[at:]
                    break
                options[PUSH_SHORT[letter]] = True
        else:
            args.append(word)
    return options, args


def _gated_push(words: list[str], where: str, rules: dict, readable: bool, branches, line: str, places: set) -> tuple[str, str] | None:
    """(repository, branch) unless this `git push` provably leaves the default branch of every gated repository
    alone. Nothing is worked out about what the push would change: one that names the default branch, or whose
    destination cannot be read, is held, even with nothing ahead (three reviews showed that predicting git is
    where the holes were). `branches` is what earlier commands on the line may have left current: None when none
    switched, else a set of names, with "" for one that cannot be read and None for the branch before the line.
    `line` is the whole command and `places` every folder it runs git in, for a push whose own folder cannot be read."""
    options, args = _push_options(words[words.index("push") + 1:])
    if options and options.get("dry-run"):
        return None
    inside = _run_git(where, "rev-parse", "--git-dir")[0] == 0  # a clone or a worktree made earlier on the line is not there yet
    readable, options = readable and inside and options is not None, options or {}
    destination, refspecs = (args[0] if args else str(options.get("repo") or "")), args[1:]  # `--repo` when none is named
    named = "" if re.search(r"[$`]", destination) else destination  # a remote named through a variable is any remote
    known, urls = _run_git(where, "remote", "get-url", "--push", "--all", named) if named else (1, "")
    remote = named if known == 0 else "origin"
    # Where it can go: every URL the named remote pushes to, or a URL given outright. When the line names none, or
    # its routing cannot be read, that is every remote here and any repository the command's own words name.
    reach = (urls if known == 0 else named) if named and readable else " ".join(
        [line] + [_run_git(place, "remote", "-v")[1] for place in ([where] if inside else sorted(places))])
    found = _repo_names(reach) & set(rules)
    if not found:
        return None
    repo = sorted(found)[0]
    # Config that sends branches somewhere their names do not say: a refspec or a mirror on a remote, or a
    # push.default other than git's own.
    config = _run_git(where, "config", "--get-regexp", r"^remote\..*\.(push|mirror)$")[1]
    mapped = bool(re.search(r"\.push\s", config)) or _run_git(where, "config", "--get", "push.default")[1].strip() not in ("", "simple", "current")
    mirror = any(value.strip().lower() not in ("false", "no", "off", "0")  # a boolean as git reads one; no value is true
                 for key, _, value in (entry.partition(" ") for entry in config.splitlines()) if key.endswith(".mirror"))
    every = (any(options.get(o) for o in ("all", "mirror", "branches")) or mirror
             or any("*" in s or s.lstrip("+") == ":" for s in refspecs))
    if not readable or every or any(re.search(r"[$`]", spec) for spec in refspecs):
        return repo, UNREAD_BRANCH
    code, head = _run_git(where, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD")
    stated = rules[repo].get("branch") if isinstance(rules[repo], dict) else None
    defaults = {str(stated)} if stated else {head.strip().split("/", 1)[1]} if code == 0 and "/" in head else set()
    now = _run_git(where, "symbolic-ref", "--short", "HEAD")[1].strip()
    current = {now} if branches is None else {now if b is None else b for b in branches}

    def lands(target: str):
        """The default branch a push to `target` reaches, or why that cannot be ruled out (the default branch is
        not recorded, or HEAD cannot be known), else None."""
        if not defaults:
            return UNKNOWN_DEFAULT.format(remote=remote)
        if target not in ("HEAD", "@"):
            return target if target in defaults else None
        return UNREAD_BRANCH if "" in current else next(iter(sorted(current & defaults)), None)

    if not refspecs:  # git consults its config; `--tags` alone pushes tags and no branch
        hit = None if options.get("tags") else UNREAD_BRANCH if mapped else lands("HEAD")
        return (repo, hit) if hit else None
    at = 0
    while at < len(refspecs):
        spec, at = refspecs[at], at + 1
        if spec == "tag" and at < len(refspecs):  # `tag <name>` pushes that tag
            at += 1
            continue
        source, colon, target = spec.lstrip("+").partition(":")
        target = target or source
        if target.startswith("refs/tags/"):  # a tag is what gets updated, whatever is pushed onto it
            continue
        hit = UNREAD_BRANCH if not colon and mapped else lands(target.replace("refs/heads/", "", 1))
        if hit:
            return repo, hit
    return None


def check_pr_gate(command: str, config: dict, cwd: str, session: dict | None = None) -> str | None:
    """Config: {"pr_gated": {"<owner>/<repo>": {"since": "YYYY-MM-DD", "direct_ok": ["<commit>"]}}}. A push that
    would move such a repository's default branch waits for the principal's code for that one push."""
    gated = config.get("pr_gated")
    if gated is None:
        return None
    runs: list = []
    commands, readable = _parse(command, cwd, runs)
    # Git reads its config and its repository from the environment too; a line that sets either is not what it looks.
    readable = readable and not re.search(r"\bGIT_(?:CONFIG\w*|DIR|WORK_TREE|COMMON_DIR|NAMESPACE)=", command)
    pushes, rerouted, moved, places = [], set(), {}, {cwd}
    for (words, directory), (chain, needed) in zip(commands, runs):
        sub, where = _git(words, directory)
        found, said = _push(words, where), set(words)
        rest = words[words.index(sub, 1) + 1:] if sub else []
        named = [w for at, w in enumerate(rest)  # the words that name something; a rebase option's own value names no branch
                 if not w.startswith("-") and not (sub == "rebase" and at and rest[at - 1] in REBASE_VALUES)]
        places |= {where} if sub else set()
        if found:
            # What earlier commands may have left current. A switch settles it only when this push stands in its
            # `&&` chain and so runs only if the switch did; any other leaves the branch before the line in play.
            level = None
            for link, firm, there in moved.get(where, []):
                level = {there} if there and firm and link is chain else (level or {None}) | {there}
            pushes.append((found[0], where, readable and found[1] and where not in rerouted, level))
        elif ((sub == "config" and not said & {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l", "get", "list"})
              or (sub == "remote" and said & {"add", "set-url", "rename", "remove", "rm", "set-branches"})):
            rerouted.add(where)  # written earlier on the line, these change where a later push goes
        elif sub in ("checkout", "switch"):
            there = _switched_to(words, where)
            if there is not None:
                moved.setdefault(where, []).append((chain, needed, there))
        elif sub == "rebase":  # `git rebase <upstream> <branch>` checks <branch> out first; with --root every name is one
            moved.setdefault(where, []).extend((chain, False, name) for name in (named if "--root" in said else named[1:]))
        elif (sub == "bisect" or (sub == "symbolic-ref" and (len(named) > 1 or said & {"-d", "--delete"}))
              or (sub == "branch" and said & {"-m", "-M", "--move"}) or (sub == "stash" and named[:1] == ["branch"])):
            moved.setdefault(where, []).append((chain, False, ""))
    if not pushes:
        return None
    if not isinstance(gated, dict) or not all(isinstance(k, str) and "/" in k for k in gated):
        return ("pr_gated in the synthesis config needs a map of \"owner/repo\" names to their settings; pushes are "
                "blocked until it is fixed")
    names = {k.lower(): rule for k, rule in gated.items()}
    hits = [hit for words, where, clear, level in pushes
            for hit in [_gated_push(words, where, names, clear, level, command, places)] if hit]
    if not hits:
        return None
    subject = {"command": command, "runs_in": sorted({where for _, where, _, _ in pushes})}
    if approvals.consume("push-direct", subject, session):
        return None
    repo, branch = hits[0]
    code = approvals.request("push-direct", subject, f"DIRECT push to {repo} {branch}: {command[:140]}")
    return (f"This pushes straight to {branch} of {repo}, which takes changes only through a pull request: push a "
            "branch, open the pull request, let its checks pass, merge it, then install from the merged branch. If the "
            f"principal wants this one push to go direct, show them the exact command and ask them to type {approvals.how(code)}. "
            "Then run the identical command again.")


# --- approvals come only from the principal's own prompt (R3.0) ------------------------------------
# The agent runs as the hooks' own OS user. In the M5 sandbox (2026-10-05) it granted its own send by
# piping a made-up prompt into the hook; it could as well write a grant or a transcript line. A grant
# is checked against the harness's transcript when it is spent (approvals.py); this refuses the shell
# routes to forging one, and to writing the approved commit lines. A route assembled at run time is beyond a
# text check: docs/runtime-integration.md.

COPIERS = frozenset({"cp", "mv", "ln", "install", "rsync", "ditto"})  # these write only where the copy lands
PACKERS = frozenset({"gzip", "gunzip", "bzip2", "bunzip2", "xz", "unxz", "zstd", "compress", "uncompress"})  # replace their files
VALUED = {"touch": ("-r", "--reference", "-t", "-d", "--date"), "truncate": ("-r", "--reference", "-s", "--size"),
          "mkdir": ("-m", "--mode"), "install": ("-m", "--mode", "-o", "--owner", "-g", "--group"),
          "xxd": ("-c", "-cols", "-g", "-groupsize", "-l", "-len", "-s", "-seek", "-o", "-n", "-name")}  # options whose next word is no file
WRITERS = COPIERS | PACKERS | {"tee", "touch", "truncate", "mkdir", "rmdir", "rm", "unlink", "shred", "chmod", "chown", "chgrp", "dd"}
IN_PLACE = re.compile(r"-\w*i(?:\W.*)?|--in-place(?:=.*)?")  # sed -i, sed -Ei.bak, perl -pi
INTO = re.compile(r"--target-directory(?:=(.*))?|-[A-Za-su-z]*t(.*)")  # cp -t DIR, mv -ft DIR, --target-directory=DIR
# Programs that only read the files they are given. A path inside a protected folder may be handed to one of these,
# to an interpreter or a shell (judged by what it runs), and to git and synthesis's own CLI, which keep the approved
# lines and the board. Any other program may change what it is given, so the guard does not pass it one (2026-11-11:
# a gate passes what it can prove; a list of the utilities that write never ends).
GONE = "/**"  # after a target: the command removes or moves away everything under that folder (rm -r, a move's source)
OVER = "/**/*"  # after a target: the command changes or searches throughout it (a recursive copy onto it, chmod -R, find)
READERS = frozenset(("cat head tail grep egrep fgrep rg ls stat wc file du diff cmp comm md5 md5sum shasum sha256sum "
                     "basename dirname realpath readlink test [ [[ echo printf cd pushd popd true false : export readonly "
                     "local declare typeset unset zcat gzcat strings od hexdump nl cut tr tac column jq date which "
                     "for case select read fold fmt expand paste join rev sort uniq less more sleep kill wait exit return "
                     "break continue shift trap seq expr bc ps pgrep uname hostname whoami id git synthesis").split())
WORDS = frozenset("for case select read test [ [[ : true false export readonly local declare typeset unset less more sleep kill wait exit "
                  "return break continue shift trap which file id synthesis".split())  # a shell's own words, and words a sentence starts with
AWKS = ("awk", "gawk", "mawk", "nawk")
AWK_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|/(?:[^/\\\n]|\\.)+/|>>?|\|\||\||[;{}\n]|\bprintf?\b|\bsystem\s*\(|\S')
OWN_RULES = ("sed", "perl", "find", "xxd", "source", ".", "eval", "apply_patch", *AWKS)  # each is read where it is handled
GIT_READS = frozenset({"status", "log", "diff", "show", "ls-files", "rev-parse", "blame", "grep", "describe", "cat-file", "shortlog"})
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
    r"|\.(?:write|append)File\w*\(|\.(?:rm|unlink|rename|mkdir|copyFile|truncate|chmod|symlink)Sync\("
    r"|\bFile\.(?:write|rename|delete|unlink)|\bFileUtils\b|\bunlink\b|\brename\s*\("
    r"|open\s*\(?\s*(?:my\s+)?[$\w]+\s*,\s*['\"]\s*\+?[>|]")
# A script that opens a send window, grants or spends an approval, or writes into synthesis state. Reading the
# window, the ledger or the board stays allowed (a read-only check was refused on 2026-10-13).
SELF_GRANT_CALLS = re.compile(r"\b(?:open_window|grant_from_prompt|consume|_window_file)\b|\bpaths\.state\b[\s\S]*\b(?:"
                              r"write_json|write_text|touch|unlink)\b|\b(?:write_json|write_text|touch|unlink)\b[\s\S]*\bpaths\.state\b")
HOOK_RUN = re.compile(r"(?:^|/)(?:synthesis-hook|synthesis/hook\.py)$|^synthesis\.hook$")
ASSIGNED = re.compile(r"(?:^|(?<=[\s;&|({'\"]))([A-Za-z_]\w*)(\+?)=(\"[^\"\n]*\"|'[^'\n]*'|\$\([^()\n]*\)[^\s;&|()<>\"']*|[^\s;&|()<>\"']*)")
LOOPED = re.compile(r"\bfor\s+([A-Za-z_]\w*)\s+in\s+([^;\n]*)")
USED = re.compile(r"\$\{([A-Za-z_]\w*)(?:(%%?|##?|:?[-=?+])([^{}$`'\"]*))?\}|\$([A-Za-z_]\w*)")
READINGS = 32  # past this many, a variable the command gives several values stays as written


def _put(use, values: dict) -> str:
    """What the shell puts for one use of a variable: its value from the command or the environment, the default
    the use carries, or the value with an end trimmed. The use as written when that cannot be told."""
    name, op, word = use[1] or use[4], use[2] or "", use[3] or ""
    if name in ("PWD", "OLDPWD") and name not in values:
        return use[0]  # the folder each command is in: the parser puts it, not the guard's own environment
    value = values.get(name, os.environ.get(name))
    if name in values and value is None:
        return use[0]
    if op[-1:] in ("-", "=", "?", "+"):
        return (word if value else "") if op[-1] == "+" else value or (word if op[-1] in "-=" else use[0])
    if value is None or not op:
        return use[0] if value is None else value
    hits = [i for i in range(len(value) + 1) if fnmatch.fnmatchcase(value[i:] if op[0] == "%" else value[:i], word)]
    cut = (min if op in ("%%", "#") else max)(hits, default=None)
    return value if cut is None else value[:cut] if op[0] == "%" else value[cut:]


def _program(words: list[str]) -> tuple[str, int, str]:
    """How an interpreter or a shell is given its code: ("file", i, name) for a script, or the module after -m, at
    words[i]; ("inline", i, text) for a program in its own words (-c, an interpreter's -e), its arguments starting at
    i; ("stdin", i, "") when it reads its input, its arguments starting at i (at `-`, or past the last word). Python
    reads a word of options letter by letter, so -Bc PROGRAM, -cPROGRAM and -Wignore are read that way, and a -c
    after `-` or after -W is an argument (2026-11-11: each of those hid the program)."""
    head, i, fed = os.path.basename(words[0]), 1, False
    takes = ({"--check-hash-based-pycs"} if head.startswith("python") else {"-o", "+o", "-O", "+O"} if head in SHELLS  # options that take the next word
             else {"-r", "--require", "--loader", "--import"} if head in ("node", "bun", "deno") else {"-I", "-r"})
    while i < len(words):
        word = words[i]
        at = next((j for j, c in enumerate(word) if j and c in "cmWX"), 0) if head.startswith("python") and re.match(r"-[A-Za-z]", word) else 0
        if word == "-":
            break
        if at and word[at] in "cm":
            given = word[at + 1:] or "".join(words[i + 1:i + 2])
            return ("inline", i + 1 + (not word[at + 1:]), given) if word[at] == "c" else ("file", i, given)
        if word == "-c" or (word == "-e" and head not in SHELLS):
            return "inline", i + 2, "".join(words[i + 1:i + 2])
        if word == "-m" or not word.startswith(("-", "+")):
            return ("stdin", i, "") if fed else ("file", i, "".join(words[i + (word == "-m"):i + 1 + (word == "-m")]))
        fed = fed or (head in SHELLS and bool(re.fullmatch(r"-[A-Za-z]*s[A-Za-z]*", word)))  # sh -s: the script is on stdin, the words are its own
        i += 1 + (word in takes or bool(at and not word[at + 1:]))
    return "stdin", i, ""


def _ran(words: list[str]) -> str:
    """The file of code an interpreter or a shell runs: its first operand, past its options and their values, or the
    module after -m; nothing when the program is given inline or read from its input. The words after it are handed
    to it, not run (2026-11-11: a line counter handed hook.py was refused as running it)."""
    kind, _, name = _program(words)
    return name if kind == "file" else ""


def _own_text(text: str) -> str:
    """A command with each program it hands another interpreter, inline or on that command's own stdin, blanked out.
    `NAME=value` in one is that program's text, a keyword argument or a statement, not a variable the command sets
    (2026-11-11: `env=dict(os.environ, OUT=target)` was read as the shell's `OUT=target`, and `$OUT` in the command
    the program started was filled in with the argument's name)."""
    if not (ASSIGNED.search(text) and re.search(r"python|node|bun|deno|perl|ruby", text)):
        return text
    feeds: list = []
    found = _parse(text, "/", feeds=feeds)[0]
    for (words, _), fed in zip(found, feeds + [""] * len(found)):
        kind, _, given = _program(words) if SCRIPT.match(os.path.basename(words[0])) else ("", 0, "")
        body = fed if kind == "stdin" else given if kind == "inline" else ""
        spot = re.search("".join("\\\\?" + re.escape(c) for c in body), text) if ASSIGNED.search(body) and len(body) < 20000 else None
        text = text[:spot.start()] + " " * (spot.end() - spot.start()) + text[spot.end():] if spot else text  # in double quotes it is spelled with backslashes
    return text


def _resolved(text: str) -> list[str]:
    """Every reading of a command with its variables put where they are used: a value the command gives one (`D=…`,
    after `export`, `readonly` or `env`, in a `for … in` list, inside a quoted script), else the environment's
    (2026-11-11: `D=<state folder>; echo x > "$D/a"` passed, a target being expanded from the environment only).
    A variable given several values gives a reading for each, since which one a command gets depends on the order
    things run in. A variable neither sets stays as written."""
    found: dict = {}
    for m in ASSIGNED.finditer(_own_text(text)):
        for before in (list(found.get(m[1], {})) or [os.environ.get(m[1], "")]) if m[2] else [""]:  # `D+=…` adds to each value D had
            found.setdefault(m[1], {})[before + m[3].strip("'\"")] = None
    for m in LOOPED.finditer(text):  # a list a command prints cannot be read: `$` stands for it
        listed = ["$"] if re.search(r"\$\(|`", m[2]) else [word.strip("'\"") for word in m[2].split()]
        found.setdefault(m[1], {}).update(dict.fromkeys(listed))
    used = {m[1] or m[4] for m in USED.finditer(text)}
    found = {name: list(values) for name, values in found.items() if name in used}
    if math.prod(map(len, found.values())) > READINGS:
        found = {name: values if len(values) == 1 else [None] for name, values in found.items()}
    readings = {}
    for choice in itertools.product(*found.values()):
        values, put = dict(zip(found, choice)), text
        for _ in range(4):  # a variable built from another
            put, before = USED.sub(lambda use: _put(use, values), put), put
            if put == before:
                break
        readings[put] = None
    return list(readings)


def _landing(words: list[str]) -> list[str]:
    """The words of a command that name what it changes: each operand of a file utility, or of `sed` or `perl`
    editing in place; `dd`'s `of=`; what `sort -o`, `uniq` or an awk program writes; for a copier where the copy
    lands, which is its last operand or the folder `-t` gives, and each source's name inside it in case that is a
    folder (2026-11-11: `cp -t <folder>`, `dd of=` and `perl -pi` wrote where no check was looking)."""
    head = os.path.basename(words[0])
    refs = {i + 1 for i, w in enumerate(words) if w in VALUED.get(head, ())}  # a reference file is only read; a size or a date is no file
    rest = [w for i, w in enumerate(words) if i and i not in refs and not w.startswith("-")]
    whole = head in ("ditto", "mv", "find") or any(re.fullmatch(r"-[A-Za-z]*[rRa][A-Za-z]*|--recursive|--archive", w) for w in words[1:])

    def all_of(folders: list, how: str = GONE) -> list:  # a folder changed throughout, marked: one that holds a protected folder changes it
        return [w.rstrip("/") + how for w in folders] if whole else []
    if head in ("chmod", "chown", "chgrp") and not any(w.startswith("--reference") for w in words):
        rest = rest[1:]  # the mode or the owner comes first
    if head == "dd":
        return [w[3:] for w in rest if w.startswith("of=")]
    if head == "sort":  # a reader, unless told where to write
        return [m[1] or m[2] or "".join(words[i + 1:i + 2]) for i, w in enumerate(words)
                for m in [re.fullmatch(r"-o(.*)|--output(?:=(.*))?", w)] if m]
    ops = [w for i, w in enumerate(words) if i and i not in refs and (w == "-" or not w.startswith("-"))]  # `-` is an operand: the input
    if head == "xxd":  # a hex dump reads its first file; a second names its output
        return [w for w in ops[1:2] if w != "-"]
    if head == "uniq":  # its second operand is its output; the value of -f, -s or -w is no operand
        return [w for i, w in enumerate(words) if i and (w == "-" or not w.startswith("-")) and not re.fullmatch(
            r"-[fsw]|--(?:skip-fields|skip-chars|check-chars)", words[i - 1])][1:2]
    if head in AWKS:  # a reader, unless its program redirects or runs a command, or it edits in place
        return [out for w in rest for out in _awk_writes(w)] + (rest if "inplace" in words else [])  # `-F|` is an option, not a pipe
    if head in PACKERS:  # to its output, or only listed or tested, a file is read
        return [] if any(re.fullmatch(r"-\w*[clt]\w*|--(?:stdout|to-stdout|list|test)", w) for w in words[1:]) else rest + all_of(rest, OVER)
    if head in ("sed", "perl"):  # its files, not its script: the word after -e or -f, or attached to one, else the first operand
        if not any(IN_PLACE.fullmatch(w) for w in words[1:]):
            return []
        scripts = [words[i + 1] for i, w in enumerate(words[:-1]) if re.fullmatch(r"-\w*[ef]|--expression|--file", w)]
        files = [w for w in rest if w and w not in scripts]
        return files if scripts or any(re.match(r"-\w*[ef].|--(?:expression|file)=", w) for w in words[1:]) else files[1:]
    if head == "find":  # it changes what it finds when told to delete, to write a list, or to run a command that does
        roots, runs = _find(words)
        lists = [words[i + 1] for i, w in enumerate(words[:-1]) if w.startswith(("-fprint", "-fls"))]  # the list it writes is that file
        return lists + (roots + all_of(roots, OVER) if "-delete" in words or any(_changes(run) for run, _ in runs) else [])
    if head not in COPIERS or (head == "install" and any(re.fullmatch(r"-\w*d\w*|--directory", w) for w in words)):
        return rest + all_of(rest, GONE if head == "rm" else OVER) * (head in ("rm", "chmod", "chown", "chgrp")) if head in WRITERS else []
    given = [(INTO.fullmatch(w), i) for i, w in enumerate(words)] if head != "rsync" else []
    into = [m[1] or m[2] or "".join(words[i + 1:i + 2]) for m, i in given if m] or rest[-1:]
    lands = into + [os.path.join(d, os.path.basename(s.rstrip("/"))) for d in into for s in rest if s not in into]
    if head == "mv" or "--remove-source-files" in words:  # these also take their sources away
        return rest + lands + all_of([s for s in rest if s not in into])
    return lands + all_of(into, OVER) * (head in ("cp", "rsync", "ditto"))  # a tree copied over a folder lands in the folders it holds


def _find(words: list[str]) -> tuple[list[str], list[tuple[list[str], bool]]]:
    """(the folders a `find` searches: its operands before the expression, and BSD's `-f <folder>`; each command it
    runs with -exec or -ok, and whether it runs it in the folder of what it found, as -execdir and -okdir do)."""
    runs = [(list(itertools.takewhile(lambda w: w not in (";", "+"), words[i + 1:])), w.endswith("dir"))
            for i, w in enumerate(words) if w.startswith(("-exec", "-ok"))]
    at, roots = 1, []
    while at < len(words) and (re.fullmatch(r"-[HLPEXdsx]+|-f", words[at]) or not words[at].startswith(("-", "(", "!"))):
        roots += [words[at]] * (not words[at].startswith("-"))
        at += 1
    return roots or ["."], runs


def _awk_writes(program: str) -> list[str]:
    """What an awk program writes: the file after `print … >`, what a command it is given as a plain string writes
    (`print | "cmd"`, `"cmd" | getline`, `system("cmd")`), and `$` (a place no check can read) where the file or the
    command printed to is not a plain string. Strings and patterns are read whole, a `/` after a value divides, and
    a `>` inside parentheses compares (the third review: `print 2 / 1 > "file"` hid its redirect in a pattern, and
    `print ($1 > 2)` was refused). A command awk builds in a variable and only reads from is not read."""
    outs, printing, redirect, depth, last, i, tokens = [], False, False, 0, "", 0, []
    while i < len(program):
        m = AWK_TOKEN.match(program, i)
        if not m:
            i += 1
            continue
        token = m[0]
        if token[:1] == "/" and len(token) > 1 and re.fullmatch(r"[\w.)\]$\"+-]", last[-1:]) and last not in ("print", "printf"):
            token = "/"  # after a value it divides
        tokens.append(token)
        last, i = token, m.start() + len(token)
    for at, token in enumerate(tokens):
        before, after = "".join(tokens[at - 1:at]), "".join(tokens[at + 1:at + 2])
        one = token[:1] == '"' and after in ("", ";", "}", "\n", ")")  # a name in two strings, or built from a field, cannot be read
        outs += [token[1:-1] if one else "$"] if redirect else []
        depth += (token == "(") - (token == ")")
        redirect = printing and depth <= 0 and token in (">", ">>")
        printing = token in ("print", "printf") or (printing and token not in (";", "{", "}", "\n"))
        runs = token == "|" or token.startswith("system")
        whole = ([after] if after[:1] == '"' and "".join(tokens[at + 2:at + 3]) in ((")",) if token != "|" else ("", ";", "}", "\n", ")")) else
                 [before] if token == "|" and before[:1] == '"' and "".join(tokens[max(at - 2, 0):at - 1]) in ("", "{", ";", "\n", "(") else [])
        if runs and whole:  # a command given whole, as one plain string: what it writes is read as a command's is
            outs += _string_writes(whole[0][1:-1])
        elif token.startswith("system") or (token == "|" and printing):  # built from pieces, or printed to: no check can read it
            outs += ["$"]
    return outs


def _string_writes(command: str) -> list[str]:
    """The files a command given as a plain string writes: its redirects and what its utilities change, each from
    the folder the string's own `cd` leaves it in, and what it hands a program not known to only read it."""
    writes: list = []
    try:
        found = _commands(command.replace('\\"', '"'), "", writes=writes)
    except (Unreadable, StopIteration, IndexError, RecursionError):
        return ["$"]
    return [os.path.join(w, t) for t, w in writes] + [os.path.join(here, w) for words, here in found for w in _landing(words) + _named(words)]


def _named(words: list[str]) -> list[str]:
    """Every path a command hands a program the guard does not know: not a reader, not a file utility whose writes
    `_landing` reads, not an interpreter or a shell. A word is taken whole, after its `=`, and for an option from
    its first `/` or `~`, so `-C <folder>`, `--output=<file>` and `-o<file>` are all seen. The caller keeps the
    ones that are paths."""
    head = os.path.basename(words[0])
    if "/" in words[0] or head in READERS or head in WRITERS or head in OWN_RULES or head in SHELLS or SCRIPT.match(head):
        return []  # a program run by its path is a script the guard cannot read, like one run by its shell
    inner = [path for w in words[1:] for path in re.findall(r"[~/][\w./~+@%-]*", w)] if head in OPAQUE else []  # each path its program names
    told = [w for at, w in enumerate(words) if at and not (w.startswith("-") and MESSAGE.fullmatch(w.split("=", 1)[0]))
            and not MESSAGE.fullmatch(words[at - 1])]  # --body=TEXT and --body TEXT are words for a reader
    return [part for w in told for part in {w, w.split("=", 1)[-1], "".join(re.findall(r"^-[^~/]*([~/].*)", w)) or w}] + inner


def _changes(run: list[str]) -> bool:
    """Whether a command `find -exec` runs may change the files it is handed, where `{}` stands: a file utility or an
    unknown program given them, a shell or a script file (which cannot be read), or an inline program that writes."""
    head = os.path.basename(run[0]) if run else "echo"
    script, _, given = _shell_input(run) if run else (None, False, [])
    if script is not None:  # a shell's own script, `{}` put where it uses the word: what it writes there, or hands a program that may
        return any(w.startswith(("{}", "$")) for w in _string_writes(_placed(script, given)))
    if SCRIPT.match(head) or head in SHELLS:
        flag = "-c" if head.startswith("python") else "-e"
        inline = run[run.index(flag) + 1] if head not in SHELLS and flag in run[:-1] else None
        return inline is None or bool(SCRIPTED_WRITE.search(inline))
    return any(w.startswith("{}") for w in _landing(run) + _named(run))


PATCH_PATHS = re.compile(r"(?m)^\*\*\* (?:Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$")
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "write_file", "edit_file", "apply_patch"}


def _reaches(target: str, root: str, whole: bool = False, hidden: bool = False) -> bool:
    """Whether a target that does not lie in a protected folder may still change it: a folder changed throughout
    (`whole`) that holds it, or a pattern (`*`, `?`, `[`, `**`) that may name it or something in it. Each part of
    the folder's path is matched against the target's; a part that starts with a pattern does not match a name
    that starts with a dot, as the shell reads one, unless `hidden` (pathlib's patterns do) (2026-11-11: `rm -rf` of
    the folder above the transcripts, and `rm` of `*/*/*.jsonl` under it, were no write)."""
    have, want = ([part for part in paths.spelled(path).split("/") if part] for path in (target, root))
    cut = have.index("**") if "**" in have else len(have)
    met = all(fnmatch.fnmatchcase(w, h) and (hidden or h[:1] not in "*?[" or w[:1] != ".") for h, w in zip(have[:cut], want))
    return met and (cut < len(have) or whole or len(have) >= len(want))


def _protected_roots(config: dict | None) -> list[str]:
    """Where only the guard, the harness and the synthesis CLI write: synthesis state, the board, the transcript
    archive, harness transcripts, approved commit lines."""
    store = paths.line_allowances(config or {})
    return [str(r) for r in [paths.state(), paths.board(), paths.sessions(), *paths.transcript_roots().values(),
                             *([store] if store else [])]]


# The board grants nothing, but a session file edited by hand can drop another session's claims (5.1.18); the
# transcript archive is evidence of what was asked and done, so nothing but its exporter may change it (5.2.0).
BOARD_WAY = ("Claims and messages go through `synthesis claim`, `synthesis release` and `synthesis msg`, "
             "which keep the board consistent for every session.")
SESSIONS_WAY = "Only `synthesis sessions export` writes it, so it stays a faithful copy of what each harness recorded."


def _cli_owned(real: str) -> str:
    """Where a write lands when it is in a folder only the synthesis CLI writes, with the way to change it; else ''."""
    for root, what, way in ((paths.board(), "the synthesis board", BOARD_WAY),
                            (paths.sessions(), "the session transcript archive", SESSIONS_WAY)):
        if paths.inside(real, os.path.realpath(root)):
            return f"inside {what}. {way}"
    return ""


def _own(real: str, folder: bool = False) -> bool:
    """A file beside a project's session transcripts that is the agent's own: a Markdown file in the project's memory
    folder (with `folder`, that folder or one inside it, which `mkdir` makes), or a script in a session's
    `workflows/scripts` folder. Claude Code keeps both there and has the agent write them; neither holds a
    transcript or an approval. The file tools, the shell and an inline program may write, move and remove one (ten
    days of transcripts held ten such shell writes; thirty held six such programs, all refused). A path is judged
    where it really leads, so a link there opens nothing, and a command that makes a link there is refused."""
    root = os.path.realpath(paths.transcript_roots()["claude-code"])
    parts = os.path.relpath(paths.spelled(real), paths.spelled(root)).split(os.sep) if paths.inside(real, root) else []
    return (parts[1:2] == ["memory"] and (folder or (len(parts) >= 3 and parts[-1].endswith(".md")))) or (
        not folder and len(parts) == 5 and parts[2:4] == ["workflows", "scripts"] and parts[-1].endswith(".js"))


def _material(real: str) -> bool:
    """A tool result Claude Code saved beside a session's transcript (a fetched PDF, a screenshot, a long output):
    material the agent is sent there to work on, so any program may be given it. Changing it in place stays
    refused (30 days of transcripts: three of six new refusals were a converter reading one)."""
    root = os.path.realpath(paths.transcript_roots()["claude-code"])
    return paths.inside(real, root) and os.path.relpath(paths.spelled(real), paths.spelled(root)).split(os.sep)[2:3] == ["tool-results"]


def _file_targets(tool: str, tool_input: dict) -> list[str]:
    text = str(tool_input.get("input") or tool_input.get("patch") or "") if tool == "apply_patch" else ""
    return [a or b for a, b in PATCH_PATHS.findall(text)] or [str(tool_input.get(k)) for k in (
        "file_path", "path", "notebook_path") if tool_input.get(k)]


def _shell_writes(command: str, cwd: str) -> list[str]:
    """The files a shell line writes or removes: redirects, what its utilities change (`_landing`), `apply_patch`;
    in every reading of the line (`_resolved`)."""
    targets = []
    for text in _resolved(command):
        writes = []
        try:
            found = _commands(text, cwd, writes=writes)
        except (Unreadable, StopIteration, IndexError):
            continue
        targets += [os.path.join(w, t) for t, w in writes]
        for words, where in found:
            targets += [os.path.join(where, w) for w in _landing(words)]
            if os.path.basename(words[0]) == "apply_patch":
                targets += [os.path.join(where, a or b) for a, b in PATCH_PATHS.findall(text)]
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
    hits = [t for t in targets if any(paths.inside(real[t], r) for r in roots) and not _own(real[t])]
    if hits and _cli_owned(real[hits[0]]):
        return f"Refused: {tool} would write {hits[0]}, {_cli_owned(real[hits[0]])}"
    return (f"Refused: {tool} would write {hits[0]}, inside the synthesis state folder, a harness's session "
            "transcripts or the approved commit lines. Approvals and send windows come only from the principal; "
            "show them what needs approving.") if hits else None


def _python_source(words: list, fed: str) -> tuple[str, list]:
    """(the Python a command runs, the words it is handed from its own name on): its -c program, or what it reads on
    its own stdin; ("", []) for a script file. Read together with every other heredoc of the line, two programs were
    judged as one (2026-11-11)."""
    kind, i, text = _program(words)
    return ("", []) if kind == "file" else (text, ["-c"] + words[i:]) if kind == "inline" else (fed, words[i:] or [""])


OS_WRITES = re.compile(r"remove|unlink|rmdir|removedirs|renames?|replace|makedirs|mkdir|symlink|link|truncate|chmod|chown|utime|open"
                       r"|write|system|popen|exec\w*|(?:posix_)?spawn\w*")
OPENERS = ("builtins", "io", "codecs", "gzip", "bz2", "lzma", "tarfile", "zipfile")  # their open (or ZipFile) takes the file, then the mode
COPIES = ("copy", "copy2", "copyfile", "copytree", "copymode", "copystat", "copyfileobj")  # shutil's: only the second place changes
PATH_WRITES = ("write_text", "write_bytes", "touch", "mkdir", "rmdir", "unlink", "chmod", "lchmod", "truncate")
LINKS = ("symlink_to", "hardlink_to", "link_to", "symlink", "link")  # pathlib's and os's: a link made at a path that is the agent's own is still a link
MUTATORS = ("append", "extend", "insert", "add", "update", "setdefault", "appendleft", "extendleft", "put", "put_nowait", "add_argument", "set_defaults")
CONTENT = ("open", "read", "readline", "readlines", "read_text", "read_bytes")  # hand back what a file holds, not where it is
ARG_READERS = {"argparse", "optparse", "getopt", "fileinput", "click", "typer", "fire", "docopt"}  # take the arguments unseen
WALKS = ("walk", "fwalk", "glob", "iglob", "rglob")  # hand back what lies under a folder, or what a pattern names
LIBRARY_WRITES = ("basicConfig", "FileHandler", "RotatingFileHandler", "TimedRotatingFileHandler", "WatchedFileHandler", "urlretrieve",
                  "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile", "TemporaryDirectory", "mkstemp", "mkdtemp")
# A writer by its name, in any library, and where it takes its path: first (`df.to_csv`, `arr.tofile`, `savefig`,
# a thing's own `save`, numpy's), second (`dump`, and `save` in the libraries that take the thing first), either
# when the reader cannot tell (`to_<anything else>`, `write_<anything else>`, another module's `save(a, b)`); and,
# as a module's own function only, a deletion or a move (`send2trash`), since a list has a `remove` of its own.
# PATH_KEYS: the keywords such writers take a path under.
BY_NAME = re.compile(r"(to_(?:csv|json|excel|parquet|pickle|feather|hdf|stata|html|latex|xml|markdown|orc|string|file|netcdf|zarr|disk)|tofile|writeto|savefig|imsave|imwrite"
                     r"|mimsave|mimwrite|dump_stats|write_(?:csv|json|parquet|excel|ipc|ndjson|avro|image|html|videofile|audiofile|gif|png|pdf|svg))"
                     r"|(to_[a-z_]+|write_\w+)|(save\w*)|(dump)|((?:remove|delete|unlink|trash|send2trash|rmtree|move|rename|extract|unpack|truncate)\w*)")
OBJECT_FIRST = {"torch", "joblib", "pickle", "dill", "cloudpickle", "nibabel", "torchvision", "tensorflow", "keras", "pandas", "pyarrow", "networkx"}  # save(what, where)
PATH_FIRST = {"numpy", "cv2", "imageio", "scipy", "skimage", "matplotlib", "tifffile", "PIL"}  # save(where, what)
OPENED = re.compile(r"\w*(?:File|Store|Writer)|Dataset|open_\w+|memmap|get_writer")  # a library's own way to open a file: h5py.File(path, "w"), ExcelWriter(path)
STRINGS = ("join", "joinpath", "Path", "PurePath", "PosixPath", "str", "fspath", "expanduser", "expandvars", "abspath", "realpath", "normpath", "resolve", "absolute",
           "with_suffix", "with_name", "with_stem", "format", "replace", "dirname", "basename", "getcwd", "cwd", "home", "mkdtemp", "mktemp", "gettempdir", "strip",
           "rstrip", "lstrip", "lower", "upper", "removesuffix", "removeprefix", "relative_to", "relpath", "getenv")  # hand back a string or a path
FOREIGN = ("open", "Path", "str", "StringIO", "BytesIO", "ZipFile", "TarFile", "NamedTemporaryFile", "TemporaryFile", "Popen", "popen", "connect", "cursor",
           "getLogger", "ArgumentParser", "writer", "reader", "DictWriter", "DictReader", "fdopen", "urlopen", "GzipFile", "TextIOWrapper", "compile")  # make no object of the program's own
PATH_KEYS = ("path", "filepath", "file_path", "filename", "file", "fname", "fp", "f", "where", "dest", "dst", "target", "output", "out", "out_file",
             "outfile", "path_or_buf", "buf", "excel_writer", "uri", "save_path", "output_path")
STARTS = ("system", "popen", "create_subprocess_exec", "create_subprocess_shell", "spawn")  # os's, asyncio's and pty's ways to start a command
PLACED = ("args", "shell", "cwd", "env", "input", "executable", "stdin", "stdout", "stderr")  # what a started command is given that the reader places or judges


def _python_writes(source: str, names: list, roots: list | tuple = (), where: str = "", argv: list | tuple = (),
                   env: dict | None = None, config: dict | None = None) -> tuple:
    """(whether a Python program writes into a protected path, whether it writes at all; the first is the refusal's own
    text when it is a command the program starts that is refused); (None, None) when it cannot
    be told (no source, a syntax error), and (None, True) for a program that runs code it builds (exec, eval,
    importlib): it cannot be read and is taken to write. Only a write's target counts, never the content it writes, so
    a project record that cites a transcript path is not a write into transcripts (2026-10-14). The program is read
    by its syntax, since a pattern over its text stops at the first closing parenthesis (2026-11-11). A target the
    program spells out is judged where it leads, so what is the agent's own there is its own for a program too. Any
    other target is judged by what it is built from: a protected path in a string or an argument, or a name one
    reached through an assignment, a loop, a `with`, a default, a call to the program's own function, a list or an
    attribute. What the program reads from a file is content, and names no path (30 days: six programs that read
    a transcript and numbered their output files by its lines were refused).
    `argv` is what the shell hands the program, from its own name on, and `env` the variables it runs with;
    `where` is the folder it runs in, and inside a protected folder, or after a chdir into one, every write must
    be led by a plain folder elsewhere."""
    import ast
    import copy
    import warnings
    try:
        with warnings.catch_warnings():  # what Python thinks of the program's escapes is not the hook's to print
            warnings.simplefilter("ignore")
            tree = ast.parse(source) if source.strip() else None
    except (SyntaxError, ValueError, RecursionError):
        tree = None
    if tree is None:
        return None, None

    def nodes_of(body):  # the nodes of some statements, down to each function written in them: its defaults and decorators are read where it is written
        todo = list(body)
        while todo:
            n = todo.pop()
            yield n
            todo += (getattr(n, "decorator_list", []) + n.args.defaults + [d for d in n.args.kw_defaults if d is not None]
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) else ast.iter_child_nodes(n))

    def scope(body: list, outer: dict, func=None) -> None:
        """Each function's own names get a name no other function shares (`path@…`), so two functions that both
        call what they are handed `path` are read apart; a name it only reads is the enclosing function's or the
        program's, as Python reads it."""
        own = list(nodes_of(body))
        params = [a for a in func.args.posonlyargs + func.args.args + func.args.kwonlyargs + [func.args.vararg, func.args.kwarg] if a] if func else []
        mine = ({a.arg for a in params} | {n.id for n in own if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}) - {"self", "cls"} - {
            x for n in own if isinstance(n, (ast.Global, ast.Nonlocal)) for x in n.names} if func else set()
        names = {**outer, **{x: x for n in own if isinstance(n, ast.Global) for x in n.names}, **{name: f"{name}@{id(func)}" for name in mine}}
        for n in params + own:
            if isinstance(n, ast.arg):
                n.arg = names.get(n.arg, n.arg)
            elif isinstance(n, ast.Name):
                n.id = names.get(n.id, n.id)
        for f in [n for n in own if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))]:
            scope(f.body if isinstance(f.body, list) else [f.body], names, f)
    whole_tree, count = list(ast.walk(tree)), {}
    for n in whole_tree:
        name = n.id if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load) else getattr(n, "arg", None) if isinstance(n, ast.arg) else None
        count[name] = count.get(name, 0) + 1
    only_read = {id(x.value) for c in whole_tree if isinstance(c, ast.Call) for x in c.keywords + c.args if getattr(x, "arg", 0) is None or isinstance(x, ast.Starred)} | {
        id(n.value) for n in whole_tree if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)}
    spelt_once = {s.targets[0].id: s.value for s in whole_tree if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
             and count.get(s.targets[0].id) == 1 and (all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in s.value.keys) if isinstance(s.value, ast.Dict)
                                                      else isinstance(s.value, (ast.List, ast.Tuple)) and not any(isinstance(e, ast.Starred) for e in s.value.elts))}
    spelt_once = {name: v for name, v in spelt_once.items() if all(id(n) in only_read for n in whole_tree if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load))}

    def one(name, key):  # one entry of a table or a row the program spells out once and only reads
        return ast.Subscript(value=ast.Name(id=name, ctx=ast.Load()), slice=ast.Constant(value=key), ctx=ast.Load())
    for c in [c for c in whole_tree if isinstance(c, ast.Call)]:  # f(**table) and f(*row) of such a one: as if each entry were written out
        c.keywords = [x for k in c.keywords for x in ([ast.keyword(arg=key.value, value=one(k.value.id, key.value)) for key in spelt_once[k.value.id].keys]
                                                     if k.arg is None and isinstance(spelt_once.get(getattr(k.value, "id", None)), ast.Dict) else [k])]
        c.args = [x for a in c.args for x in ([one(a.value.id, i) for i in range(len(spelt_once[a.value.id].elts))]
                                             if isinstance(a, ast.Starred) and isinstance(spelt_once.get(getattr(a.value, "id", None)), (ast.List, ast.Tuple)) else [a])]
    scope(tree.body, {})
    nodes = list(ast.walk(tree))

    def said(node):  # the text of a string, None for anything else
        value = node.value if isinstance(node, ast.Constant) else None
        return value.decode("utf-8", "replace") if isinstance(value, bytes) else value if isinstance(value, str) else None

    def imported(node):  # the module a call imports by a name it spells out: __import__("os"), import_module("os")
        call = isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in ("__import__", "import_module")
        return said(node.args[0]) if call and node.args else None
    modules, direct, stars, local, pairs, loops, tainted, bound, files, ranges, sent_to = {}, {}, [], {}, [], [], set(), {}, {}, {}, {}
    for n in nodes:  # what each name is: a module, a name taken from one, the program's own function, an assignment
        if isinstance(n, ast.Import):
            modules.update({(a.asname or a.name).split(".")[0]: a.name if a.asname else a.name.split(".")[0] for a in n.names})
        elif isinstance(n, ast.ImportFrom):
            stars += [n.module or ""] * any(a.name == "*" for a in n.names)
            direct.update({a.asname or a.name: (n.module or "", a.name) for a in n.names})
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local.setdefault(n.name, []).append(n.args)
        elif isinstance(n, ast.ClassDef):  # a call of the class reaches its methods
            local.setdefault(n.name, []).extend(f.args for f in ast.walk(n) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)))
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and n.value is not None:
            for target in n.targets if isinstance(n, ast.Assign) else [n.target]:
                apart = (isinstance(target, (ast.Tuple, ast.List)) and isinstance(n.value, (ast.Tuple, ast.List))
                         and len(target.elts) == len(n.value.elts) and not any(isinstance(e, ast.Starred) for e in target.elts + n.value.elts))
                pairs += zip(target.elts, n.value.elts) if apart else [(target, n.value)]  # a, b = x, y is two assignments
                if isinstance(target, ast.Name) and isinstance(n.value, ast.Lambda):
                    local.setdefault(target.id, []).append(n.value.args)
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            loops.append(n)
    spelt = {id(n.func) for n in nodes if imported(n)}
    if any((isinstance(n, ast.Name) and n.id in ("exec", "eval", "compile")) or getattr(n, "id", getattr(n, "attr", "")) in ("run_path", "run_module")
           or (getattr(n, "id", getattr(n, "attr", "")) in ("__import__", "import_module") and id(n) not in spelt) for n in nodes):
        return None, True  # it runs code it builds, or imports a module it names at run time
    for target, value in pairs:  # a function kept under another name is still that function
        if isinstance(target, ast.Name) and isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and value.value.id in modules:
            direct[target.id] = (modules[value.value.id], value.attr)
        elif isinstance(target, ast.Name) and isinstance(value, ast.Name) and (value.id in direct or value.id == "open"):
            direct[target.id] = direct.get(value.id, ("builtins", "open"))
        elif isinstance(target, ast.Name) and imported(value):
            modules[target.id] = imported(value)
    stored = [n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)] + [n.arg for n in nodes if isinstance(n, ast.arg)]
    total = {name: len(list(same)) for name, same in itertools.groupby(sorted(stored))}
    once = {name for name, count in total.items() if count == 1}  # names given a value exactly once
    calls = [n for n in nodes if isinstance(n, ast.Call)]
    given_once = {t.id: v for t, v in pairs if isinstance(t, ast.Name) and t.id in once}  # what a name given one value once was given
    # The words after the program are its arguments, and `sys.argv[2]` is the second of them. Taken another way (a
    # slice, a loop, an argument parser), or after a word the shell fills in, they cannot be placed, and then any
    # write is refused while one of them names a protected path (30 days: four programs that read their first
    # argument and wrote their second were refused).
    index = {id(n.value): n for n in nodes if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and type(n.slice.value) is int}
    uses = [n for n in nodes if getattr(n, "attr", getattr(n, "id", "")) in ("argv", "orig_argv")]
    placed = (all(id(n) in index and isinstance(n, ast.Attribute) and n.attr == "argv" and isinstance(n.value, ast.Name)
                  and modules.get(n.value.id) == "sys" for n in uses)
              and not ARG_READERS & {m.split(".")[0] for m in [*modules.values(), *(m for m, _ in direct.values())]}
              and not any(re.search(r"[*?\[{$`]", w) for w in argv[1:]))
    given = {id(index[id(n)]): argv[index[id(n)].slice.value] for n in uses if placed and 0 <= index[id(n)].slice.value < len(argv)}
    loose = not placed and any(m in w for w in argv[1:] for m in names)

    # The environment is placed the same way: a variable the program reads by name (os.environ["X"], .get("X"),
    # os.getenv("X")) has the value the command gives it, when that value is plain. Read any other way, a variable
    # that carries a protected path makes any write a refusal (30 days: a program that read the time from one
    # variable was refused for a transcript's path in another).
    env, keyed, env_given = env or {}, set(), {}

    def home(path: str) -> str:  # `~` as the program's own HOME gives it, else the command's, else the hook's
        mine = ([spelled(v) for k, v in mapped.get("environ", ()) if k == "HOME"] or [env.get("HOME", "")])[-1]
        return mine + path[1:] if mine and not re.search(r"[$`]", mine) and (path == "~" or path[:2] == "~/") else os.path.expanduser(path)
    for n in nodes:
        holder = n.value if isinstance(n, ast.Subscript) else n.func.value if isinstance(n, ast.Call) and getattr(n.func, "attr", "") in ("get", "setdefault", "pop") else None
        key = said(n.slice) if isinstance(n, ast.Subscript) else said(n.args[0]) if isinstance(n, ast.Call) and n.args else None
        if key is not None and (getattr(holder, "attr", getattr(holder, "id", "")) == "environ" or (
                holder is None and isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) == "getenv")):
            keyed.add(id(holder if holder is not None else n.func))
            if key in env and not re.search(r"[$`]", env[key]):
                env_given[id(n)] = env[key]  # what the command gave it; the program may give it another value before it reads it
    keyed |= {id(x) for n in nodes if isinstance(n, ast.Call) for x in n.args[:getattr(n.func, "id", "") == "dict"] + [k.value for k in n.keywords if k.arg == "env"] + [
        getattr(n.func, "value", None)] * (getattr(n.func, "attr", "") == "copy")} | {id(v) for n in nodes if isinstance(n, ast.Dict) for k, v in zip(n.keys, n.values) if k is None}
    keyed |= {id(n.func.value) for n in nodes if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "update"} | {id(v) for t, v in pairs if isinstance(t, ast.Name) and getattr(v, "attr", getattr(v, "id", "")) == "environ"} | {
        id(c) for n in nodes if isinstance(n, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops) for c in n.comparators}  # given a value, kept under a name, asked for a name: each read as the table it is
    wild = any(getattr(n, "attr", getattr(n, "id", "")) in ("environ", "environb", "getenv", "putenv") and id(n) not in keyed for n in nodes)  # copied whole for a child, it is read through the copy
    loose = loose or (wild and (any(m in v for v in env.values() for m in names) or any(
        v[:1] == "/" and paths.inside(v, r) for v in env.values() for r in roots)))

    def source(node):  # what an open call opens: its first argument, or the path whose own open() it is; None for any other node
        if not (isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "open"):
            return None
        whole = isinstance(node.func, ast.Name) or (isinstance(node.func.value, ast.Name) and node.func.value.id in modules)
        return (node.args[:1] or [None])[0] if whole else node.func.value

    def opened(node) -> bool:  # a file opened from a protected path: what it holds is content, but its .name is that path
        return isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "open" and any(
            map(named, [*node.args, *(k.value for k in node.keywords), *([node.func.value] if isinstance(node.func, ast.Attribute) else [])]))

    store = paths.line_allowances(config or {})
    folders_held = [r for r in roots if not store or r != os.path.realpath(str(store))]  # the approved lines are one file: nothing holds a folder of them

    def over(n) -> bool:  # a walk or a pattern that may find what lies in a protected folder, from a folder that holds it
        label = getattr(n.func, "attr", getattr(n.func, "id", ""))
        method = isinstance(n.func, ast.Attribute) and not (isinstance(n.func.value, ast.Name) and n.func.value.id in modules)
        top = spelled(n.func.value) if method else spelled((n.args[:1] or [n])[0])
        top = os.path.join(top, said(n.args[0]) or "\0") if method and label == "glob" and n.args else top
        top = os.path.join(*[spelled(k.value) for k in n.keywords if k.arg == "root_dir"], top)  # glob's root_dir leads its pattern
        top = home(top[top.rfind("\1") + 1:]).replace("\0", "*")
        return any(_reaches(os.path.realpath(os.path.join(spot, top)), r, label in ("walk", "fwalk", "rglob"), method)
                   for spot in ([""] if os.path.isabs(top) else places) if "\0" not in spot for r in folders_held)

    def rooted(n) -> bool:  # what names no folder: a path taken relative to one that holds it, one part of a path, a path flattened, a digest
        label = getattr(getattr(n, "func", None), "attr", getattr(getattr(n, "func", None), "id", ""))

        def slashed(call) -> bool:  # its first argument is the slash
            return isinstance(call, ast.Call) and bool(call.args) and (said(call.args[0]) == "/" or getattr(call.args[0], "attr", "") == "sep")
        if isinstance(n, ast.Subscript):  # one part of a path, counted from its end: p.parts[-1], path.split("/")[-2]
            parts = getattr(n.value, "attr", "") == "parts" or (getattr(getattr(n.value, "func", None), "attr", "") in ("split", "rsplit") and slashed(n.value))
            return parts and isinstance(n.slice, ast.UnaryOp) and isinstance(n.slice.op, ast.USub) and isinstance(getattr(n.slice.operand, "value", None), int)
        if label in ("hexdigest", "len", "hash") or (label == "replace" and slashed(n) and len(n.args) == 2 and "/" not in (said(n.args[1]) or "/")):
            return True
        given = n.args + [k.value for k in n.keywords if k.arg == "start"] if isinstance(n, ast.Call) else []
        if label not in ("relative_to", "relpath") or len(given) != 1 + (label == "relpath") or len(given) - len(n.args) != len(n.keywords):
            return False
        if label == "relative_to":
            return True  # it raises unless the path lies under that folder
        path, start = (home(spelled(a)) for a in given)
        if re.search("[\0\1]", start) or not os.path.isabs(start) or "\1" in path:
            return False
        if "\0" not in path:  # spelled out: it must not climb
            return os.path.isabs(path) and ".." not in os.path.relpath(path, start).split(os.sep)
        return any(paths.inside(os.path.realpath(start), r) or paths.inside(r, os.path.realpath(start)) for r in roots)

    def named(node, apart=()) -> bool:  # built from a protected path: in a string, in an argument, or through a name or an attribute
        todo, met = [node], set()
        while todo:
            n = todo.pop()
            if isinstance(n, ast.Name) and n.id in apart:
                continue  # what a walk found from where the program stands: after a folder elsewhere it only goes further in
            held_ = members(n) if is_member(n) else [(None, ())]
            if all(v is not None for v, _ in held_):  # a member of something the program makes: built from what that member holds, not from all the thing holds
                if any(isinstance(v, str) and any(m in v for m in names) for v, _ in held_):
                    return True
                todo += [v for v, _ in held_ if isinstance(v, ast.AST)] if id(n) not in met else []  # once: a member may hold what is built from itself
                met.add(id(n))
                continue
            if isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) in WALKS and over(n):
                return True  # what it finds under a folder that holds a protected one may lie in that one
            if isinstance(n, ast.Attribute) and n.attr == "name" and (opened(n.value) or "name of " + getattr(n.value, "id", "") in tainted):
                return True
            field = (isinstance(n, ast.Attribute) and not (isinstance(n.value, ast.Name) and n.value.id in modules) and (
                "." + n.attr in tainted or (n.attr in tainted and n.attr in classed))) or (".environ" in tainted and (
                getattr(n, "attr", "") == "environ" or getattr(getattr(n, "func", None), "attr", getattr(getattr(n, "func", None), "id", "")) == "getenv"))
            if field or (isinstance(n, ast.Name) and n.id in tainted) or any(m in (said(n) or given.get(id(n)) or env_given.get(id(n), "")) for m in names):
                return True
            own_ = asked(n)[1] if isinstance(n, ast.Call) and (key_of(n) or "")[:3] == "()@" else None
            if own_ is not None and id(own_) in bodies:  # the program's own function: built from what it hands back, not from what it is handed or all its object holds
                if bodies[id(own_)].name in tainted:
                    return True
                continue
            if isinstance(n, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                todo += [n.key, n.value] if isinstance(n, ast.DictComp) else [n.elt]  # what a comprehension makes: built from what it makes each one of
                continue
            leaf = (isinstance(n, ast.Attribute) and n.attr in ("name", "stem", "suffix")) or (
                isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) == "basename") or rooted(n)
            if not leaf and not (isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) in CONTENT):
                todo += ast.iter_child_nodes(n)  # what a file holds is not where it is, and the last part of a path names no folder
        return False

    def spelled(node) -> str:  # the path a node spells out, "\0" standing for each part that cannot be read
        label = getattr(getattr(node, "func", None), "attr", getattr(getattr(node, "func", None), "id", ""))
        if id(node) in given or said(node) is not None:
            return given.get(id(node), said(node))
        if id(node) in picked:
            return picked[id(node)]  # one side of `a if c else b` or `a or b`, what this call of the program's own function hands back, one value a member holds
        if is_member(node):
            found = read_as(node)
            return found[0] if len(found) == 1 else "\0"
        key = key_of(node)
        if key is not None and (key in picked or len(ranges.get(key, ())) == 1):
            return picked[key] if key in picked else ranges[key][0]  # the one value it holds, or the one this reading takes
        if isinstance(node, ast.Name):
            return bound.get(node.id, "\0")
        if isinstance(node, ast.Attribute) and node.attr == "path" and getattr(node.value, "id", None) in finds:
            return spelled(node.value)  # what os.scandir found: its path
        if label == "home" and isinstance(node, ast.Call) and not node.args:
            return "~"  # Path.home()
        if isinstance(node, ast.Attribute) and node.attr == "name" and getattr(node.value, "id", "") in files:
            return files[node.value.id]  # the name of a file it opened is the path it opened
        if (isinstance(node, ast.Attribute) and node.attr == "parent") or (label == "dirname" and len(node.args) == 1 and not node.keywords):
            whole = spelled(node.value if isinstance(node, ast.Attribute) else node.args[0])  # the folder of a path it spells
            return whole if "\0" in whole else os.path.dirname(whole) or whole[:whole.rfind("\1") + 1] + "."
        if isinstance(node, ast.Attribute) and node.attr == "executable" and modules.get(getattr(node.value, "id", "")) == "sys":
            return "python3"  # sys.executable: the interpreter the program itself runs under
        if isinstance(node, ast.JoinedStr):
            return "".join(spelled(v.value if isinstance(v, ast.FormattedValue) else v) for v in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
            return spelled(node.left) + "/" * isinstance(node.op, ast.Div) + spelled(node.right)
        shape = node.left if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) else node.func.value if label == "format" and isinstance(node.func, ast.Attribute) else None
        shape = None if shape is None else said(shape) if said(shape) is not None else spelled(shape)  # the template itself, or the one a name holds
        if isinstance(node, ast.BinOp) and shape is not None and not re.search("[\0\1\2]", shape):  # "%s/line-%d.txt" % (folder, i): each filled in its turn
            filled = iter(node.right.elts if isinstance(node.right, ast.Tuple) else [node.right])
            return re.sub(r"%(?:\(\w*\))?[-#0 +]*\d*(?:\.\d+)?[a-zA-Z%]", lambda m: "%" if m[0] == "%%" else (
                lambda a: spelled(a) if a is not None and m[0] == "%s" else "\0")(next(filled, None)), shape)
        if label == "format" and shape is not None and not re.search("[\0\1\2]", shape):  # "{}/line-{:03d}.txt".format(folder, i)
            filled, worded = iter(node.args), {k.arg: k.value for k in node.keywords}

            def fill(m):
                name = re.split(r"[!:.\[]", m[1], 1)[0]
                a = next(filled, None) if not name else node.args[int(name)] if name.isdigit() and int(name) < len(node.args) else worded.get(name)
                return spelled(a) if a is not None and not isinstance(a, ast.Starred) else "\0"
            return re.sub(r"\{([^{}]*)\}", fill, shape.replace("{{", "\3").replace("}}", "\4")).replace("\3", "{").replace("\4", "}")
        if label == "join" and isinstance(node.func, ast.Attribute) and len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple)) and (
                said(node.func.value) is not None or getattr(node.func.value, "attr", "") == "sep"):  # "/".join([folder, name])
            return (said(node.func.value) if said(node.func.value) is not None else "/").join(spelled(e) for e in node.args[0].elts)
        if label in ("mkdtemp", "TemporaryDirectory", "gettempdir") and len(node.args) < 3 and "dir" not in [k.arg for k in node.keywords]:
            return os.path.join("/tmp", "tmp.made")  # a fresh folder of its own, or the folder they are made in: somewhere else
        if isinstance(node, ast.Call) and not node.keywords:
            parts = [spelled(a) for a in node.args]
            if label in ("join", "joinpath", "Path", "PurePath", "PosixPath") and parts:
                return os.path.join(*([spelled(node.func.value)] if label == "joinpath" else []), *parts)
            if label in ("str", "fspath", "expanduser", "abspath", "realpath", "normpath", "resolve", "absolute", "encode") and len(parts) <= 1:
                whole = parts[0] if parts else spelled(node.func.value) if isinstance(node.func, ast.Attribute) else "\0"
                if label == "expanduser" and whole[:1] == "~" and id(node) in homes:
                    whole = spelled(homes[id(node)]) + whole[1:]  # the home it has where it asks
                made = label in ("abspath", "realpath", "resolve", "absolute") and whole[:1] not in ("/", "~", "\0", "\1")
                return f"\1{id(node)}\1" * made + whole  # a relative path made whole is whole from where the program stood at this call
            if label in ("getcwd", "cwd") and not parts:
                return f"\1{id(node)}\1."
            if label in ("relative_to", "relpath") and rooted(node):  # spelled out at both ends, it is that relative path
                ends = [home(x) for x in ([spelled(node.func.value)] if label == "relative_to" else parts[:1]) + parts[-1:]]
                if all(os.path.isabs(x) and not re.search("[\0\1]", x) for x in ends):
                    return os.path.relpath(*ends)
            if label in ("with_suffix", "with_name", "with_stem") and isinstance(node.func, ast.Attribute) and len(parts) == 1:
                folder, name = os.path.split(spelled(node.func.value))
                stem, suffix = os.path.splitext(name)
                return os.path.join(folder, parts[0] if label == "with_name" else stem + parts[0] if label == "with_suffix" else parts[0] + suffix)
        return "\0"

    def taint(found) -> bool:
        new = set(found) - tainted
        tainted.update(new)
        return bool(new)

    def held(target) -> set:  # what a binding gives a value to: a name, an attribute (as ".attr"), the holder of a key
        return ({target.id} if isinstance(target, ast.Name)
                else {"." + target.attr} | (held(target.value) if target.attr == "__dict__" else set()) if isinstance(target, ast.Attribute)
                else held(target.value) if isinstance(target, (ast.Subscript, ast.Starred))
                else {x for e in getattr(target, "elts", getattr(target, "args", [])) for x in held(e)})  # obj.__dict__["k"] and vars(obj)["k"] give to obj
    classes = {c.name: c for c in nodes if isinstance(c, ast.ClassDef)}
    classed = {x for c in classes.values() for b in c.body for t in getattr(b, "targets", [getattr(b, "target", None)])
               if t is not None for x in held(t)} | {b.name for c in classes.values() for b in c.body if isinstance(
                   b, (ast.FunctionDef, ast.AsyncFunctionDef))}  # a name given in a class body is read as an attribute, a property too

    def lineage(name, seen: tuple = ()) -> list:  # a class of the program's own, then each it inherits from, nearest first
        return [name] + [x for b in classes[name].bases for x in lineage(getattr(b, "id", ""), seen + (name,))] if name in classes and name not in seen else []
    inits = {name: next((f.args for k in lineage(name) for f in classes[k].body if isinstance(f, ast.FunctionDef) and f.name == "__init__"), None)
             for name in classes}  # the __init__ that builds each: its own, or the one it inherits
    defs = [f for f in nodes if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))]
    bodies, inside = {id(f.args): f for f in defs}, {id(n): f for f in defs for n in nodes_of(f.body)}  # each function by its arguments; the function each node is written in
    of_class = {id(f): c.name for c in classes.values() for f in c.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
    kin = {name: {name} for name in classes}  # the classes one inherits from or is inherited by: an object of one may be handled as any
    for name in classes:
        group = set().union(*(kin[k] for k in lineage(name)))
        kin.update(dict.fromkeys(group, group))
    grown = {id(n.value): n.op for n in nodes if isinstance(n, ast.AugAssign)}  # `out += x` gives out + x
    withs = [(w.optional_vars, w.context_expr) for w in nodes if isinstance(w, ast.withitem) and w.optional_vars is not None]
    once_value = {**given_once, **{t.id: v for t, v in withs if isinstance(t, ast.Name) and t.id in once}}
    methods = {id(b.args) for c in classes.values() for b in c.body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))}
    mutated = {getattr(kept, "id", "") for kept in [n.func.value for n in calls if getattr(n.func, "attr", "") in MUTATORS] + [
        getattr(t, "value", None) for t, _ in pairs]}  # a list that gains a row later is not the list as written
    rows = {t.id: v.elts for t, v in pairs if isinstance(t, ast.Name) and t.id in once - mutated and isinstance(v, (ast.List, ast.Tuple))}
    def asked(c) -> tuple:  # (the name, the arguments) of the program's own function a call reaches: f(...), obj.method(...), a class of its own
        method = isinstance(c.func, ast.Attribute) and not (isinstance(c.func.value, ast.Name) and c.func.value.id in modules)
        name = c.func.id if isinstance(c.func, ast.Name) else c.func.attr if method else None
        home, on = of_class.get(id(inside.get(id(c)))), once_value.get(getattr(getattr(c.func, "value", None), "id", ""), getattr(c.func, "value", None))
        if home and (name == "cls" or (name == "__init__" and getattr(getattr(on, "func", None), "id", "") == "super")):
            name = home if name == "cls" else (lineage(home)[1:] or [None])[0]  # cls(...) builds the class it is written in; super().__init__(...) runs its base's
        elif method and (isinstance(on, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.List, ast.Tuple, ast.Dict, ast.Set)) or (
                isinstance(on, ast.Attribute) and getattr(on.value, "id", "") in modules) or getattr(getattr(on, "func", None), "attr", getattr(
                    getattr(on, "func", None), "id", "")) in FOREIGN):
            return None, None  # called on a file it opened, a string, a list, sys.stdout: no object of the program's own
        own = inits[name] if name in classes else local[name][0] if name and len(local.get(name, ())) == 1 else None
        if method and own is None and name not in classes and len(local.get(name, ())) > 1:  # two classes with a method of that name: the one of what it is called on
            k = home if getattr(on, "id", "") == "self" else getattr(getattr(on, "func", None), "id", "")
            own = next((f.args for x in lineage(k or "") for f in classes[x].body if getattr(f, "name", "") == name), None)
        return (name, own) if own is None or name in classes or method == (id(own) in methods) else (None, None)  # f.write(...) is no call of the program's own write()
    plainly = [n for n in calls if asked(n)[1] is not None
               and not any(isinstance(a, ast.Starred) for a in n.args) and None not in [k.arg for k in n.keywords]]
    mapcalls = [c for c in calls if getattr(c.func, "id", "") == "map" and len(c.args) == 2 and not c.keywords and isinstance(c.args[0], ast.Name)
                and c.args[0].id not in classes and len(local.get(c.args[0].id, ())) == 1]  # map(f, values): each is handed to f's first name
    called = {id(c.func) for c in calls} | {id(c.args[0]) for c in mapcalls}  # a function also handed on, kept under another name or called another way has other callers
    based_on = {id(b) for c in classes.values() for b in c.bases}  # a class named as another's base is not handed on
    loose_names = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in called | based_on} | {
        asked(c)[0] for c in calls if asked(c)[0] and c not in plainly} | {n.attr for n in nodes if isinstance(n, ast.Attribute) and id(n) not in called} | {
        c.func.attr for c in calls if isinstance(c.func, ast.Attribute) and len(local.get(c.func.attr, ())) > 1 and asked(c)[1] is None}
    loose_owns = {id(inits[n]) if n in classes else id(local[n][0]) for n in loose_names if (n in classes and inits[n]) or len(local.get(n, ())) == 1}
    fixed = {id(f.args) for f in nodes if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name not in total and not any(
        isinstance(t, ast.Attribute) and t.attr == f.name for t, _ in pairs) and all(
        getattr(d, "id", getattr(d, "attr", "")) in ("staticmethod", "classmethod", "lru_cache", "cache", "cached_property", "property") for d in f.decorator_list)} | {
        id(v.args) for t, v in pairs if isinstance(t, ast.Name) and isinstance(v, ast.Lambda) and total.get(t.id) == 1}  # still itself: not wrapped, not given another value
    callers = {}  # each function of the program's own whose every caller is seen: (its arguments, those calls, whether it is a class's __init__)
    for name, own, call in [(*asked(c), c) for c in plainly] + [(c.args[0].id, local[c.args[0].id][0], None) for c in mapcalls]:
        if name not in loose_names and id(own) in fixed and id(own) not in loose_owns:  # a base's __init__ is reached under each class's name
            callers.setdefault(id(own), (own, [], name in classes))[1].extend([call] if call is not None else [])

    def hands(own, calls_of, init: bool = False, kept={}) -> dict:  # what each caller hands each of a function's own names; a default stands where a caller gives none
        if (id(own), len(calls_of), id(calls_of[0]) if calls_of else 0) in kept:
            return kept[id(own), len(calls_of), id(calls_of[0]) if calls_of else 0]  # asked again for each settling
        takers = [a.arg for a in own.posonlyargs + own.args]
        takers = takers[takers[:1] in (["self"], ["cls"]) and (init or all(isinstance(c.func, ast.Attribute) for c in calls_of)):]  # a method's own first
        given_by = dict(zip(takers[len(takers) - len(own.defaults):], own.defaults))
        given_by.update({a.arg: d for a, d in zip(own.kwonlyargs, own.kw_defaults) if d is not None})
        return kept.setdefault((id(own), len(calls_of), id(calls_of[0]) if calls_of else 0), {
            taker: [c.args[at] if at < min(len(c.args), len(takers)) else next((k.value for k in c.keywords if k.arg == taker.split("@")[0]), given_by.get(taker))
                    for c in calls_of] for at, taker in enumerate(takers + [a.arg for a in own.kwonlyargs])})
    # What a command the program starts is given besides its words: the variables the program has put in
    # os.environ or in the mapping it hands over as `env`, however it keeps that mapping (the seventh review: a
    # mapping kept under a name, a copy of the environment, `os.environ.update`), and a script written down a pipe.
    whole, mapped = object(), {}  # mapped: what each mapping is given after it is made, by its name ("environ" for os.environ)

    aliases = {t.id for t, v in pairs if isinstance(t, ast.Name) and getattr(v, "attr", "") == "environ"}  # e = os.environ

    def holder(node):
        name = getattr(node, "attr", getattr(node, "id", None))
        return "environ" if name == "environ" or (isinstance(node, ast.Name) and name in aliases) else getattr(node, "id", None)
    for target, value in pairs:
        if isinstance(target, ast.Subscript) and holder(target.value):
            mapped.setdefault(holder(target.value), []).append((said(target.slice), value))
    for n in calls:
        label = getattr(n.func, "attr", getattr(n.func, "id", ""))
        if label == "putenv" and len(n.args) == 2:
            mapped.setdefault("environ", []).append((said(n.args[0]), n.args[1]))
        elif label in ("update", "setdefault") and isinstance(n.func, ast.Attribute) and holder(n.func.value):
            mapped.setdefault(holder(n.func.value), []).extend(
                [(said(n.args[0]), n.args[1])] if label == "setdefault" and len(n.args) == 2
                else [(whole, a) for a in n.args] + [(k.arg, k.value) for k in n.keywords])

    def handed(node, seen: tuple = ()) -> list:  # the variables a mapping holds, as (name, value); a name of None for what cannot be read
        label = getattr(getattr(node, "func", None), "attr", getattr(getattr(node, "func", None), "id", ""))
        if isinstance(node, ast.Dict):
            return [x for k, v in zip(node.keys, node.values) for x in (handed(v, seen) if k is None else [(said(k), v)])]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return handed(node.left, seen) + handed(node.right, seen)
        if isinstance(node, ast.Call) and label in ("dict", "copy"):
            return [x for a in node.args + ([node.func.value] if label == "copy" else []) for x in handed(a, seen)] + [(k.arg, k.value) for k in node.keywords]
        name = holder(node)
        found = [x for k, v in mapped.get(name, ()) for x in (handed(v, seen + (name,)) if k is whole else [(k, v)])] + [
            x for v in [v for t, v in pairs if not isinstance(t, ast.Subscript) and holder(t) == name and holder(v) != name] + sent_to.get(name, [])
            for x in handed(v, seen + (name,))] if name and name not in seen else []  # what it was given, or what its one caller hands it
        return found if found or name == "environ" else [(None, node)]

    # A name may be given more than one value: a second assignment, one of two, a value in each of two functions,
    # what each of two callers hands it, what a loop visits. A target is read once for each value its names may hold,
    # and lands in a protected folder if any reading does. `stores` holds, under each name, the values the program
    # gives it (None for one that cannot be read, a string for one already spelled); a field of the program's own
    # object stands under ".field" and an entry of its own table under "[table]key". "\2" is no value at all: None
    # (this project's probe after the tenth review: thirty everyday programs were refused from inside a transcript
    # folder because a name was read only when it was given one value, once).
    picked, stores, sites, turns, finds, deep = {}, {}, {}, {}, set(), []

    def given_to(key, values, site: int = 0) -> None:
        stores.setdefault(key, []).extend(values)
        sites[key] = sites.get(key, 0) + site
    rets = {id(f.args): [None] if any(isinstance(r, (ast.Yield, ast.YieldFrom)) for r in nodes_of(f.body)) else [
        r.value for r in nodes_of(f.body) if isinstance(r, ast.Return) and r.value is not None] for f in defs if id(f.args) in fixed}
    rets.update({id(v.args): [v.body] for _, v in pairs if isinstance(v, ast.Lambda) and id(v.args) in fixed})  # what each function of its own hands back

    def gives(n, kept={}) -> list:  # (name, values) for each name an assignment gives a value: plainly, side by side, or unpacked from a pair it can read
        found = kept.setdefault(id(n), [])  # read once: a value it makes up for a name is the same value wherever it is asked for
        for target in (n.targets if isinstance(n, ast.Assign) else [n.target]) if not found else []:
            value, wide = ast.BinOp(left=target, op=n.op, right=n.value) if isinstance(n, ast.AugAssign) else n.value, getattr(target, "elts", None)
            if wide is None:
                found += [(target, [value])] * isinstance(target, ast.Name)
                continue
            label, kw = getattr(getattr(value, "func", None), "attr", getattr(getattr(value, "func", None), "id", "")), {k.arg: k.value for k in getattr(value, "keywords", [])}
            back = rets.get(id(asked(value)[1]), []) if isinstance(value, ast.Call) and asked(value)[0] not in classes else []
            sides = ([[e] for e in value.elts] if isinstance(value, (ast.Tuple, ast.List)) else [[e] for e in rows[value.id]] if getattr(value, "id", None) in rows
                     else [[ast.Constant(value="\2")], [ast.BinOp(left=kw["dir"], op=ast.Add(), right=ast.Constant(value="/\0")) if "dir" in kw else ast.Constant(value="/tmp/tmp.made")]]
                     if label == "mkstemp" else [[r.elts[at] for r in back] for at in range(len(wide))]
                     if back and all(isinstance(r, ast.Tuple) and len(r.elts) == len(wide) for r in back)
                     else [[ast.Subscript(value=value, slice=ast.Constant(value=at), ctx=ast.Load())] for at in range(len(wide))]
                     if isinstance(value, (ast.Call, ast.Name, ast.Subscript, ast.Attribute)) else [])  # a pair, a row, mkstemp's, its own function's, else each by its place
            if len(sides) == len(wide) and not any(isinstance(e, ast.Starred) for e in wide + [x for side in sides for x in side if x is not None]):
                found += [(t, side) for t, side in zip(wide, sides) if isinstance(t, ast.Name)]
        return found
    for n in nodes:
        for t, values in gives(n) if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and n.value is not None else []:
            given_to(t.id, values, 1)
    for target, value in pairs + withs:
        if isinstance(target, ast.Name) and any(target is t for t, _ in withs):
            given_to(target.id, [value], 1)
    # Where a name is read, the value it holds is the one its own body last gave it by a plain assignment, with
    # whatever a branch, a loop or another function may have given it since; before any, what the function was
    # handed (a name read for a transcript and then given the file to write was held to the transcript). A member
    # (`job.out`, `cfg["out"]`, `os.environ["OUT"]`) is read the same way along the path it is reached by.
    reach, plain_stores, reach_m, tags, live, this, selfish, walked, kn, primed = {}, set(), {}, {}, {}, {}, {}, {}, {}, []
    pair_of, ENV = {id(t): v for t, v in pairs}, ast.Name(id="environ", ctx=ast.Load())  # what each target is given; the environment, as a table of its own
    homes = {id(n): ast.Call(func=ast.Attribute(value=ast.Name(id="Path", ctx=ast.Load()), attr="home", ctx=ast.Load()), args=[], keywords=[])
             for n in calls if getattr(n.func, "attr", getattr(n.func, "id", "")) == "expanduser"}  # the home each expanduser() asks for, where it asks
    kept_kw = {id(n.func.value): inside[id(n)] for n in calls if getattr(n.func, "attr", "") == "update" and getattr(n.func.value, "attr", "") == "__dict__"
               and getattr(n.func.value.value, "id", "") == "self" and len(n.args) == 1 and not n.keywords and id(n) in inside and inside[id(n)].name == "__init__"
               and getattr(inside[id(n)].args.kwarg, "arg", None) == getattr(n.args[0], "id", "")}  # `self.__dict__.update(kw)` in an __init__: its keywords are its fields
    loose_fields = any(getattr(n, "attr", getattr(n, "id", getattr(n, "name", ""))) in ("__dict__", "vars", "__setattr__", "__getattr__", "__getattribute__")
                       and id(n) not in kept_kw for n in nodes)  # fields given some other way: none of them is read
    hidden = any(getattr(n, "id", "") in ("globals", "locals") for n in nodes)
    tainted.update(total if hidden and any(m in (said(n) or "") for n in nodes for m in names) else ())  # any name may be given what the program names
    shapes = {t.id: (said(v.args[1]) or "").replace(",", " ").split() or [said(e) or "" for e in getattr(v.args[1], "elts", [])] for t, v in pairs
              if isinstance(t, ast.Name) and isinstance(v, ast.Call) and getattr(v.func, "attr", getattr(v.func, "id", "")) == "namedtuple" and len(v.args) > 1}
    fields_of = {**{c.name: [b.target.id for k in reversed(lineage(c.name)) for b in classes[k].body if isinstance(b, ast.AnnAssign) and isinstance(b.target, ast.Name)]
                    for c in classes.values() if inits[c.name] is None}, **shapes}  # a class with fields and no __init__ of its own, a named tuple
    parsed = {}  # an argument parser's defaults, under the name it gives each argument; a word of the command line may replace one
    for n in calls:
        label, kw = getattr(n.func, "attr", getattr(n.func, "id", "")), {k.arg: k.value for k in n.keywords}
        if label in ("SimpleNamespace", "Namespace", "set_defaults", "replace", "_replace"):
            loose_fields = loose_fields or None in kw
            for k, v in kw.items() if label == "set_defaults" else []:
                parsed.setdefault(str(k), []).append(v)
        elif label == "add_argument":
            flags = [said(a) or "" for a in n.args]
            dest = said(kw["dest"]) if "dest" in kw else next((f for f in flags if f.startswith("--")), "".join(flags[:1]))
            parsed.setdefault(str(dest).lstrip("-").replace("-", "_"), []).extend([kw.get("default")] + [None] * (len(argv) > 1))
        elif label == "setattr" and len(n.args) == 3:
            loose_fields = loose_fields or said(n.args[1]) is None
            given_to(str(said(n.args[1])), [n.args[2]])  # on the program's own module it is a name

    def key_at(n):  # the key a read or a store spells: a string, a place, or what the name it is kept under was last plainly given; None for any other
        n = reach[id(n)] if isinstance(n, ast.Name) and isinstance(reach.get(id(n)), ast.Constant) else n
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and type(getattr(n.operand, "value", None)) is int:
            return -n.operand.value
        return n.value if isinstance(n, ast.Constant) and type(n.value) in (str, int) else None

    def sel_of(n):  # (what it is a member of, which member, a default) for x.a, x["k"], x[0], x.get("k", d), getattr(x, "a", d), os.getenv("K", d), Path.home()
        label = getattr(getattr(n, "func", None), "attr", getattr(getattr(n, "func", None), "id", ""))
        if isinstance(n, ast.Attribute):
            lone = isinstance(n.value, ast.Name) and n.value.id in modules
            return None if lone or loose_fields or id(n) in called or holder(n) == "environ" else (n.value, ("a", n.attr), None)
        if isinstance(n, ast.Subscript):
            return None if isinstance(n.slice, ast.Slice) else (n.value, ("k", key_at(n.slice)), None)
        if not isinstance(n, ast.Call) or n.keywords or any(isinstance(a, ast.Starred) for a in n.args) or asked(n)[1] is not None:
            return None
        if label == "home" and not n.args:
            return ENV, ("k", "HOME"), ast.Constant(value="~")
        if label == "getenv" and 1 <= len(n.args) <= 2:
            return ENV, ("k", key_at(n.args[0])), (n.args[1:] or [None])[0]
        if label == "getattr" and isinstance(n.func, ast.Name) and 2 <= len(n.args) <= 3 and not loose_fields:
            return n.args[0], ("a", key_at(n.args[1])), (n.args[2:] or [None])[0]
        if label in ("get", "setdefault", "pop") and isinstance(n.func, ast.Attribute) and (label == "pop") <= len(n.args) + (label == "pop") <= 2 + (label == "pop") and len(
                n.args) <= 2 and not (isinstance(n.func.value, ast.Name) and n.func.value.id in modules):
            return n.func.value, ("k", key_at(n.args[0]) if n.args else None), (n.args[1:] or [None])[0]
        return None

    def path_of(n):  # a member as (the name it is reached from, the way from it, that name's node): ("cfg", "k'paths'k'out'", cfg); None when it has no such spelling
        m = sel_of(n)
        if not m or m[1][1] is None:
            return None
        lead = ("environ", "", None) if holder(m[0]) == "environ" else (m[0].id, "", m[0]) if isinstance(m[0], ast.Name) else path_of(m[0])
        return (lead[0], f"{lead[1]}{m[1][0]}{m[1][1]!r}", lead[2]) if lead else None

    def flat(body) -> list:  # a program's statements with its `if __name__ == "__main__":` block in line: it runs once, in order
        return [x for s in body for x in (flat(s.body) if isinstance(s, ast.If) and not s.orelse and getattr(getattr(s.test, "left", None), "id", "") == "__name__" else [s])]

    def order(body, mine, top: bool = False) -> None:
        last, lasts = {}, {}
        for at, stmt in enumerate(body):
            seen = list(nodes_of([stmt]))
            reach.update((id(n), last.get(n.id)) for n in seen if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and mine(n.id))
            for n in [m for n in seen for m in (n, homes.get(id(n))) if m is not None]:  # a member read: what its own path was last plainly given here
                p = path_of(n) if isinstance(n, ast.Call) or isinstance(getattr(n, "ctx", None), ast.Load) else None
                if p and mine(p[0]):
                    reach_m[id(n)] = (p[:2], id(body), lasts.get(p[:2], (None, -1)), top)
            plain = isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None
            for t, values in gives(stmt) if plain else []:
                last[t.id] = values[0] if len(values) == 1 and isinstance(values[0], ast.AST) and mine(t.id) else None
                plain_stores.update([id(last[t.id])] * (last[t.id] is not None))
                for p in [p for p in lasts if p[0] == t.id]:
                    del lasts[p]  # a name given a new thing: what the old one's members were given is not this one's
            for t in [n for n in seen if isinstance(n, (ast.Attribute, ast.Subscript)) and isinstance(n.ctx, ast.Store) and id(n) in pair_of] if plain else []:
                p = path_of(t)
                if p and mine(p[0]) and id(pair_of[id(t)]) not in grown:
                    for q in [q for q in lasts if q[0] == p[0] and q[1].startswith(p[1])]:
                        del lasts[q]  # and what lay under a member is gone with it
                    lasts[p[:2]], tags[id(pair_of[id(t)])] = (pair_of[id(t)], at), (p[:2], id(body), at)
    order(flat(tree.body), lambda name: "@" not in name, True)
    for f in defs:
        order(f.body, lambda name, mark=f"@{id(f)}": name.endswith(mark))
    for n in nodes:  # a store whose values are read elsewhere, or that gives none: a function's own name, a loop's, a name only annotated
        for t in [n] if isinstance(n, ast.arg) else getattr(n.target, "elts", [n.target]) if isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)) else [
                n.target] if isinstance(n, ast.AnnAssign) and n.value is None else []:
            if isinstance(t, (ast.arg, ast.Name)):  # a loop over `x.y` or `x[0]` gives no name a value
                given_to(getattr(t, "arg", getattr(t, "id", "")), [], 1)

    def key_of(n):  # the name a value is read under: a name where it is read, or its own function's answer
        if isinstance(n, ast.Name):
            return n.id if id(n) not in reach else f"{n.id}~{id(reach[id(n)]) if reach[id(n)] is not None else ''}"
        name, own = asked(n) if isinstance(n, ast.Call) else (None, None)
        if own is not None and name not in classes and id(own) in rets and isinstance(n.func, ast.Attribute) == (id(own) in methods):
            return f"()@{id(own)}"  # what the program's own function hands back
        return None

    # A member is read by the thing that holds it. Each table, list or object the program makes is one thing, known by
    # the place that makes it, however many names it is kept under and whatever it is handed to; a thing holds what
    # it was made with (a table's entries, what an object's __init__ gives its fields from what that call hands it,
    # its class's constants and properties) and whatever any statement gives it afterwards. Along one path from one
    # name, in statements that run once and in order, the last plain gift replaces what came before it. A thing whose
    # maker cannot be read (`json.load(f)`) holds only what the program gives it, and what is given through a name
    # that cannot be followed may be in any of them (the eleventh review, and this project's probe after it: one set
    # of values stood for a field or a key whatever carried it, so two objects of a class, a table whose entry is
    # replaced, a key kept in a name and a class that inherits its __init__ were all read wrongly).
    given_m, loose_m, removed, born, slots, memo, copies = {}, {}, set(), {}, {}, {}, {}  # what each thing is given, by its maker's id, then kind and key; memo: readings kept between settlings

    def gifts(store, kind, key) -> list:  # what one such store holds for a member: its own key's, any key's, and all of them when the key cannot be read
        by = store.get(kind, {})
        return [x for values in by.values() for x in values] if key is None else by.get(key, []) + by.get(None, [])
    fields_given = {t.attr for t in nodes if isinstance(t, ast.Attribute) and isinstance(t.ctx, ast.Store)}
    LISTS = (ast.List, ast.Tuple, ast.Set, ast.ListComp, ast.SetComp, ast.GeneratorExp)
    tops = {id(v) for f in defs for s in f.body if isinstance(s, (ast.Assign, ast.AnnAssign)) and s.value is not None
            for v in [s.value] + list(getattr(s.value, "elts", []))}
    for t in [t for t in nodes if isinstance(t, ast.Attribute) and isinstance(t.ctx, ast.Store) and getattr(t.value, "id", "") == "self"]:
        f = inside.get(id(t))  # what an __init__ gives each field of the object it builds, and whether by a statement of its own body
        if f is not None and f.name in ("__init__", "__post_init__") and id(f) in of_class:
            v = None if id(pair_of.get(id(t))) in grown else pair_of.get(id(t))
            born.setdefault((id(f), t.attr), []).append((v, id(v) in tops))

    def builds(c) -> bool:  # a call that makes an object of a class of the program's own
        return isinstance(c, ast.Call) and asked(c)[0] in classes and getattr(c.func, "attr", "") != "__init__"

    def selves(f, seen: tuple = ()) -> list:  # the objects `self` may be in a function: those it is called on, or every one the program makes of that class and its kin
        name, every = of_class.get(id(f)), []
        if name is None or id(f) in seen:
            return []
        if f.name not in ("__init__", "__post_init__") and id(f.args) in callers:
            every = [x for c in callers[id(f.args)][1] for x in resolve(c.func.value, seen + (id(f),))]
        return [x for x in every if x is not None] + [c for c in calls if builds(c) and asked(c)[0] in kin[name]] * (None in every or not every)

    def inlined(r, call, sent: dict):  # what a function hands back, written with what this call hands it, so each call's object is its own
        def written(n):
            if isinstance(n, ast.Name) and n.id in sent and isinstance(n.ctx, ast.Load):
                return sent[n.id]  # a name the function is handed and never gives another value
            if not isinstance(n, ast.AST):
                return n
            new = copy.copy(n)
            for field, value in ast.iter_fields(n):
                setattr(new, field, [written(v) for v in value] if isinstance(value, list) else written(value))
            inside.update({id(new): inside[id(n)]} if id(n) in inside else {})
            return new
        return r if r is None or not sent else copies.setdefault((id(r), id(call)), written(r))

    cuts = [0, 0]  # how often a reading was cut short (a thing reached through itself, too deep, too much), and the steps of the reading in hand

    def resolve(node, seen: tuple = ()) -> list:  # each thing an expression may be, as the node that makes it; None for one that cannot be told
        plain, cuts[1] = not any(this.values()), cuts[1] + 1 if seen else 0
        if plain and ("r", id(node)) in memo:
            return memo["r", id(node)]
        if node is None or len(seen) > 60 or cuts[1] > 4000:  # too deep or too much to follow: it cannot be told
            cuts[0] += node is not None
            return [None]
        before, found = cuts[0], list(dict.fromkeys(follow(node, seen)))
        memo.update({("r", id(node)): found} if plain and cuts[0] == before else {})  # kept when nothing under it was cut short
        return found

    def follow(node, seen: tuple) -> list:
        if holder(node) == "environ":
            return [ENV]
        if isinstance(node, ast.Name) and node.id in ("self", "cls") and id(node) in inside and id(inside[id(node)]) in of_class:
            f = inside[id(node)]
            now = [x for o in this.get(id(f.args)) or [None] for x in ([o] if o is not None else selves(f, seen))]
            return [classes[of_class[id(f)]]] if node.id == "cls" else now or [None]
        if isinstance(node, ast.Name):
            key = key_of(node)
            if node.id in classes and node.id not in total:
                return [classes[node.id]]
            cuts[0] += key in seen
            return [] if key in seen else [c for name, c in classes.items() if name == node.id] + [  # a class's name given a value besides: either
                x for v in live.get(key, [None]) + [None] * (total.get(node.id, 0) > sites.get(node.id, 0))
                for x in ([None] if v is None or isinstance(v, str) else resolve(v, seen + (key,)))]
        if isinstance(node, (ast.IfExp, ast.BoolOp, ast.NamedExpr)):
            return [x for v in ([node.body, node.orelse] if isinstance(node, ast.IfExp) else getattr(node, "values", [getattr(node, "value", None)]))
                    for x in resolve(v, seen)]
        label = getattr(getattr(node, "func", None), "attr", getattr(getattr(node, "func", None), "id", ""))
        name, own = asked(node) if isinstance(node, ast.Call) else (None, None)
        if own is not None and name not in classes and id(own) in rets:  # what the program's own function hands back
            was, this[id(own)] = this.get(id(own)), resolve(node.func.value, seen) if isinstance(node.func, ast.Attribute) else None
            sent = {t: a[0] for t, a in hands(own, [node], False).items() if a[0] is not None and total.get(t) == 1} if any(node is c for c in plainly) else {}
            found = [x for r in rets[id(own)] for x in resolve(inlined(r, node, sent), seen + (id(own),))] if id(own) not in seen else []
            this[id(own)], cuts[0] = was, cuts[0] + (id(own) in seen)
            return found
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return resolve(node.left, seen) + resolve(node.right, seen)  # a | b holds what either holds
        if isinstance(node, ast.Call) and label in ("copy", "deepcopy", "list", "tuple", "sorted", "reversed") and len(node.args) + isinstance(node.func, ast.Attribute) >= 1:
            return resolve(node.args[0] if node.args else node.func.value, seen)  # a copy holds what the thing it copies holds
        cuts[0] += id(node) in seen
        if id(node) not in seen and isinstance(getattr(node, "ctx", None) or ast.Load(), ast.Load) and sel_of(node):
            return [x for v, _ in members(node, seen + (id(node),)) for x in ([None] if v is None or isinstance(v, str) else resolve(v, seen + (id(node),)))]
        return [node]

    def built(c, a, seen: tuple = ()) -> list:  # what a field holds as an object is made: (the value, the calls it is read under)
        name, obj = (c.name, None) if isinstance(c, ast.ClassDef) else (asked(c)[0], [c])

        def by(f, under_) -> list:  # what one __init__ gives the field: the last its own statements give it, with each a branch of it may; else its base's, as it calls it
            got = born.get((id(f), a), []) if f is not None and id(f) not in [id(x[0]) for x in under_[:-1]] else []
            plain = [v for v, top in got if top]
            return [(v, under_) for v, top in got if not top] + [(v, under_) for v in plain[-1:]] or [
                x for s in calls if f is not None and inside.get(id(s)) is f and getattr(s.func, "attr", "") == "__init__" and asked(s)[0] in classes
                for x in by(bodies.get(id(asked(s)[1])), under_ + ((asked(s)[1], s, obj),))]
        init = bodies.get(id(inits.get(name)))
        post = next((f for k in lineage(name) for f in classes[k].body if getattr(f, "name", "") == "__post_init__"), None)
        found = (by(init, ((init.args, c, obj),)) if init is not None and obj else []) + (by(post, ((post.args, None, obj),)) if post is not None and obj else [])
        if not found and obj and a in fields_of.get(name, ()):  # a class with fields and no __init__ of its own: handed by place or by name
            found = handed_field(c, name, a)
        if not found and obj and init in kept_kw.values():  # a class that keeps its keywords as its fields
            found = [(None, ())] if None in [k.arg for k in c.keywords] else [(k.value, ()) for k in c.keywords if k.arg == a]
        for b in [b for k in lineage(name) for b in classes[k].body] if not found else []:  # else what the class body gives: a constant, a field's default, a property's answer
            mine_ = isinstance(b, (ast.Assign, ast.AnnAssign)) and b.value is not None and any(
                getattr(t, "id", None) == a for t in getattr(b, "targets", [getattr(b, "target", None)]))
            made = getattr(getattr(b, "value", None), "func", None)
            if mine_ and getattr(made, "attr", getattr(made, "id", "")) == "field":  # dataclasses.field(default=...)
                found += [(k.value.body if k.arg == "default_factory" else k.value, ()) for k in b.value.keywords if k.arg == "default" or (
                    k.arg == "default_factory" and isinstance(k.value, ast.Lambda))] or [(None, ())]
            elif mine_:
                found.append((b.value, ()))
            elif getattr(b, "name", None) == a and any(getattr(d, "id", getattr(d, "attr", "")) in ("property", "cached_property") for d in b.decorator_list):
                found += [(r, ((b.args, None, obj),)) for r in rets.get(id(b.args), [None])]
        return found

    def handed_field(c, name, a) -> list:  # a field handed by place or by name: a named tuple's, a class with fields and no __init__ of its own
        unread = any(isinstance(x, ast.Starred) for x in c.args) or None in [k.arg for k in c.keywords]
        at = fields_of[name].index(a)
        return [(None, ())] if unread else [(v, ()) for v in c.args[at:at + 1] + [k.value for k in c.keywords if k.arg == a]]

    def part(c, sel, n=None, seen: tuple = ()) -> list:  # (a value, the calls it is read under) for each thing one member of one thing may hold
        (kind, key), label = sel, getattr(getattr(c, "func", None), "attr", getattr(getattr(c, "func", None), "id", ""))
        kw = {k.arg: k.value for k in getattr(c, "keywords", [])}
        if c is None or id(c) in seen:
            return [(None, ())] * (c is None)  # a thing that holds itself (`cfg = {**cfg, ...}`) is read once
        seen += (id(c),)
        if c is ENV:
            made = [(env[key], ())] if key in env and not re.search(r"[$`]", env[key]) else [] if key is not None else [(None, ())] + [
                (v, ()) for v in env.values() if any(m in v for m in names) or (v[:1] == "/" and any(paths.inside(v, r) for r in roots))]  # any of them: one may name a protected path
        elif isinstance(c, ast.Dict):
            made = [x for k, v in zip(c.keys, c.values) for x in (
                [y for o in resolve(v, seen) or [None] for y in part(o, sel, None, seen)] if k is None else [(v, ())] * (key is None or key_at(k) in (key, None)))]
        elif isinstance(c, (ast.List, ast.Tuple, ast.Set)):
            whole = not any(isinstance(e, ast.Starred) for e in c.elts)
            made = [(c.elts[key], ())] if whole and type(key) is int and -len(c.elts) <= key < len(c.elts) else [
                (e, ()) for e in c.elts] * (key is None or not whole) + [(None, ())] * (not whole)
        elif isinstance(c, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            made = [(getattr(c, "value", getattr(c, "elt", None)), ())]
        elif isinstance(c, ast.ClassDef) or builds(c):
            made = built(c, key, seen) if kind == "a" and key is not None else [(None, ())]
        elif label in shapes and kind == "a" and key in shapes[label]:
            made = handed_field(c, label, key)
        elif isinstance(c, ast.Call) and label in ("SimpleNamespace", "Namespace", "dict"):
            made = [(v, ()) for k, v in kw.items() if k is not None and (key is None or k == key)]
            for o in [o for a in c.args + [k.value for k in c.keywords if k.arg is None] for o in resolve(a, seen) or [None]]:
                rows_ = [v for v, _ in part(o, ("k", None), None, seen)] if isinstance(o, (ast.List, ast.Tuple)) else [None]  # the rows it was made with and given since
                pairs_ = all(isinstance(r, (ast.Tuple, ast.List)) and len(r.elts) == 2 for r in rows_)
                made += ([(r.elts[1], ()) for r in rows_ if key is None or key_at(r.elts[0]) in (key, None)] if pairs_  # dict([("k", v)]): each row's second, by its first
                         else [(None, ())] if isinstance(o, LISTS) else part(o, sel, None, seen))  # what another table holds; rows it cannot read may hold anything
        elif isinstance(c, ast.Call) and label in ("replace", "_replace"):
            made = [(kw[key], ())] if key in kw else [x for o in resolve(c.args[0] if c.args else c.func.value, seen) or [None] for x in part(o, sel, None, seen)]
        elif isinstance(c, ast.Call) and label == "parse_args":
            made = [(v, ()) for v in parsed.get(key, [None])]
        elif isinstance(c, ast.Call) and label == "defaultdict" and getattr((c.args[:1] or [None])[0], "id", "") in ("list", "set", "dict") and kind == "k":
            fresh = (lambda: ast.Dict(keys=[], values=[])) if c.args[0].id == "dict" else (lambda: ast.List(elts=[], ctx=ast.Load()))
            made = [(slots.setdefault((id(c), key), fresh()), ())] if key is not None else [(v, ()) for (owner, _), v in slots.items() if owner == id(c)]  # the list it makes for each key
        else:
            made = [(None, ())]  # what something else made: all it holds is what the program gives it
        shared = [given_m.get(id(classes[k]), {}) for k in lineage(asked(c)[0])] if builds(c) else []  # an object also holds what its class is given later
        given = [x for store in (given_m.get(id(c), {}), *shared, loose_m) for x in gifts(store, kind, key)]
        if n is not None and id(n) in reach_m:  # along its own path: the last plain gift before it stands for all before, and in a program's own statements none comes after
            way, body, (lastv, lastat), top = reach_m[id(n)]
            given = [(v, t) for v, t in given if not (t and t[:2] == (way, body) and (top or t[2] <= lastat))]
            made = [(lastv, ())] if lastv is not None else made
        found = made + [(v, ()) for v, _ in given]
        return found or [(None, ())] * (kind == "a" and not isinstance(c, ast.Call) or builds(c))

    def members(n, seen: tuple = ()) -> list:  # (a value, the calls it is read under) for each thing a member read may give; a value of None cannot be told, "\2" is none at all
        plain = not seen and not any(this.values())  # read with no call in hand: the same at every asking until the names are read again
        if plain and id(n) in memo:
            return memo[id(n)]
        base, sel, default = sel_of(n)
        things = resolve(base, seen) or [None]
        found = [x for c in things for x in part(c, sel, n if len(things) == 1 else None, seen)]
        spare = default is not None and bool(not found or loose_m or any(v is None for v, _ in found) or any(id(c) in removed for c in things))
        found = found + [(default, ())] * spare or [("\2", ())]
        memo.update({id(n): found} if plain else {})
        return found

    def under(calls_):  # each reading of the calls a value is read under: a function's own names as that call hands them, `self` as the object it is called on
        if not calls_:
            yield
            return
        own, c, obj = calls_[0]
        sent = {t: a[0] for t, a in hands(own, [c], asked(c)[0] in classes).items() if a[0] is not None} if c is not None else {}
        options = [list(dict.fromkeys((["\2"] if isinstance(a, ast.Constant) and a.value is None else spellings(a)) + [  # what it is handed, or what the function gives the name itself
            x for v in stores.get(t, []) for x in (["\0"] if v is None else [v] if isinstance(v, str) else spellings(v))])) for t, a in sent.items()]
        if any(d is own for d in deep) or len(deep) > 3 or math.prod(map(len, options)) > 8:
            sent, options = {}, []  # a function that calls itself, or too many readings: whatever any call may hand it
        deep.append(own)
        was, this[id(own)] = this.get(id(own)), obj or this.get(id(own))
        for combo in itertools.product(*options):
            picked.update(x for t, v in zip(sent, combo) for x in ((t, v), (t + "~", v)))
            yield from under(calls_[1:])
        for t in sent:
            picked.pop(t, None), picked.pop(t + "~", None)
        deep.pop()
        this[id(own)] = was

    def read_as(n) -> list:  # every spelling a member read may have
        found = []
        for v, calls_ in members(n):
            for _ in under(calls_) if isinstance(v, ast.AST) else [0]:
                found += ["\0"] if v is None else [v] if isinstance(v, str) else ["\2"] if isinstance(v, ast.Constant) and v.value is None else spellings(v)
        found = list(dict.fromkeys(found))
        return ["\0"] if len(found) > 12 else found

    def is_member(n) -> bool:  # a member read of something the program makes: read by what that thing holds
        if not primed or not isinstance(n, (ast.Attribute, ast.Subscript, ast.Call)) or not isinstance(getattr(n, "ctx", None) or ast.Load(), ast.Load):
            return False
        if id(n) not in kn:
            kn[id(n)] = sel_of(n) is not None and any(v is not None for v, _ in members(n))
        return kn[id(n)]

    def stringy(a, depth: int = 0) -> bool:  # reads as a path or a string the program builds, through each name it is kept under: no object, no open file
        label = getattr(getattr(a, "func", None), "attr", getattr(getattr(a, "func", None), "id", ""))
        if isinstance(a, (ast.JoinedStr, ast.BinOp)) or said(a) is not None or (isinstance(a, ast.Call) and label in STRINGS):
            return True
        if depth > 4 or not isinstance(a, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
            return False
        own = asked(a)[1] if isinstance(a, ast.Call) else None
        values = rets.get(id(own), [None]) if own is not None else [v for v, _ in members(a)] if is_member(a) else live.get(key_of(a), [None]) if isinstance(a, ast.Name) else [None]
        return bool(values) and all(isinstance(v, str) or (v is not None and stringy(v, depth + 1)) for v in values)

    def elements(node, seen: tuple = ()):  # what a loop over it visits, as values or as the spelled folder a walk's finds lie under; None when it cannot be read
        if isinstance(node, ast.Name) and (node.id in rows or (node.id in once_value and node.id not in seen and node.id not in mutated
                                                              and isinstance(once_value[node.id], ast.Call))):
            return rows[node.id] if node.id in rows else elements(once_value[node.id], seen + (node.id,))
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return list(node.elts)
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            return elements(node.value, seen)  # some of them
        label, method = getattr(getattr(node, "func", None), "attr", getattr(getattr(node, "func", None), "id", "")), isinstance(
            getattr(node, "func", None), ast.Attribute) and not (isinstance(node.func.value, ast.Name) and node.func.value.id in modules)
        if isinstance(node, ast.Call) and label in ("sorted", "list", "reversed", "tuple", "set", "iter", "islice", "tqdm", "filter") and node.args:
            return elements(node.args[label == "filter" and len(node.args) > 1], seen)  # the same things, in another order or fewer
        if isinstance(node, ast.Call) and label == "values" and method:
            return [v for c in resolve(node.func.value) or [None] for v, _ in part(c, ("k", None))] if primed else None
        if isinstance(node, ast.Call) and label in ("glob", "iglob") and not method and node.args:  # what a pattern finds lies under the folder before its first wildcard
            top = os.path.join(*[spelled(k.value) for k in node.keywords if k.arg == "root_dir"], spelled(node.args[0]))
            cut = re.split(r"[*?\[]", top, 1)
            lead = os.path.dirname(cut[0])
            return [top] if len(cut) == 1 else None if ".." in cut[1].split("/") else [lead + "/\0" if lead else "\0"]  # a pattern that climbs finds what lies elsewhere
        if isinstance(node, ast.Call) and method and label in ("glob", "rglob") and (
                not node.args or said(node.args[0]) is None or said(node.args[0])[:1] == "/" or ".." in said(node.args[0]).split("/")):
            return None
        if isinstance(node, ast.Call) and ((method and label in ("glob", "rglob", "iterdir")) or (not method and label in ("scandir", "walk", "fwalk"))):
            return [spelled(node.func.value if method else (node.args[:1] or [ast.Constant(value=".")])[0]) + "/\0"]
        things = resolve(node) if primed and not isinstance(node, ast.Call) else [None]  # a list the program makes, however it is reached: what it was made with and given since
        return [v for c in things for v, _ in part(c, ("k", None))] if things and all(isinstance(c, LISTS) for c in things) else None

    def columns(n) -> dict:  # what each name of a loop's target is given: values, or None for what cannot be read
        it, names_ = n.iter, getattr(n.target, "elts", None)
        label = getattr(getattr(it, "func", None), "attr", getattr(getattr(it, "func", None), "id", ""))
        if names_ is None:
            return {n.target.id: elements(it)} if isinstance(n.target, ast.Name) else {}
        each, wide = elements(it), len(names_)
        if label == "zip" and len(it.args) == wide:
            sides = [elements(a) for a in it.args]
        elif label in ("items", "enumerate") and wide == 2:
            sides = [None, elements(ast.Call(func=ast.Attribute(value=it.func.value, attr="values"), args=[], keywords=[])) if label == "items" and isinstance(
                it.func, ast.Attribute) else elements(it.args[0]) if label == "enumerate" and it.args else None]
        elif label in ("walk", "fwalk"):
            sides = [each] + [None] * (wide - 1)
        elif each and all(isinstance(r, (ast.Tuple, ast.List)) and len(r.elts) == wide and not any(isinstance(e, ast.Starred) for e in r.elts) for r in each):
            sides = [[r.elts[at] for r in each] for at in range(wide)]
        else:
            sides = [None] * wide
        return {t.id: side for t, side in zip(names_, sides) if isinstance(t, ast.Name)}

    def gather() -> dict:  # every value each name is given, as the program now reads
        live, handed_in, visited = {key: list(values) for key, values in stores.items()}, {}, {}
        finds.clear()
        for own in [f.args for f in nodes if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))]:  # what each function's own names are handed
            _, calls_of, init = callers.get(id(own), (own, None, False))
            got = hands(own, calls_of, init) if calls_of is not None else {}
            for a in own.posonlyargs + own.args + own.kwonlyargs + [x for x in (own.vararg, own.kwarg) if x]:
                via = [e for c in mapcalls if local[c.args[0].id][0] is own and a.arg == next(iter(got), None) for e in (elements(c.args[1]) or [None])]
                handed_in.setdefault(a.arg, []).extend([v for v in got[a.arg] if getattr(v, "id", None) != a.arg] + via if a.arg in got
                                                       else [] if a.arg in ("self", "cls") else [None])
        for n in loops:
            for name, values in columns(n).items():
                visited.setdefault(name, []).extend([None] if values is None else values)
                finds.update([name] * bool(values and all(isinstance(v, str) for v in values)))
        for name in [k for k in {*stores, *handed_in, *visited} if k[:1] not in (".", "[")]:
            plain = [v for v in stores.get(name, []) if isinstance(v, ast.AST) and id(v) in plain_stores]
            rest = [v for v in stores.get(name, []) if not any(v is x for x in plain)] + visited.get(name, [])
            live[name] = plain + handed_in.get(name, []) + rest  # read where the order is not known: any of them
            live[name + "~"] = handed_in.get(name, []) + rest  # read before its body's first plain assignment
            live.update((f"{name}~{id(v)}", [v] + rest) for v in plain)  # read after one of them
        live.update((f"()@{key}", back or [ast.Constant(value=None)]) for key, back in rets.items())
        return live

    def outer(node):  # a value's nodes down to each `a if c else b` and `a or b`, read by its sides, each call of the program's own function, read by what it hands back, and each member read
        yield node
        if id(node) in homes:
            yield homes[id(node)]
        if not (isinstance(node, ast.IfExp) or (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)) or (key_of(node) or "")[:3] == "()@" or is_member(node)):
            for child in ast.iter_child_nodes(node):
                yield from outer(child)

    def answers(c) -> list:  # what one call of the program's own function hands back, read with what this call hands it and the object it is called on
        own = asked(c)[1]
        if any(d is own for d in deep) or len(deep) > 2:
            return ranges.get(key_of(c)) or ["\0"]  # a function that calls itself, or too deep: whatever any call may hand back
        obj = resolve(c.func.value) if isinstance(c.func, ast.Attribute) else None
        found = [x for _ in under(((own, c, obj),)) for r in rets[id(own)] for x in (spellings(r) if r is not None else ["\0"])]
        return list(dict.fromkeys(found)) or ["\2"]

    def spellings(node) -> list:  # each path a node may spell, one for every value its names may hold; as `spelled` reads it when they are too many
        if walked.get(id(node), (None,))[0] is not node:  # walked once: a value is read again at each settling
            seen = list(outer(node))
            walked[id(node)] = (node, [c for c in seen if isinstance(c, ast.IfExp) or (isinstance(c, ast.BoolOp) and isinstance(c.op, ast.Or))
                                       or (key_of(c) or "")[:3] == "()@" or is_member(c)], list(dict.fromkeys(k for k in map(key_of, seen) if k is not None and k[:3] != "()@")))
        sides = [c for c in walked[id(node)][1] if id(c) not in picked]
        free = [k for k in walked[id(node)][2] if k not in picked and len(ranges.get(k, ())) > 1]
        options = [ranges[k] for k in free] + [read_as(c) if is_member(c) else answers(c) if isinstance(c, ast.Call) else [
            x for alt in ([c.body, c.orelse] if isinstance(c, ast.IfExp) else c.values) for x in spellings(alt) if x != "\2"] or ["\2"] for c in sides]
        if not options or math.prod(map(len, options)) > 32:
            return [spelled(node)]
        found, keys = [], free + [id(c) for c in sides]
        for combo in itertools.product(*options):
            picked.update(zip(keys, combo))
            found.append(spelled(node))
        for key in keys:
            picked.pop(key, None)
        return list(dict.fromkeys(x for x in found if "\2" not in x or x == "\2"))

    def values_of(key, values) -> list:  # every spelling the values given under one name may have
        own_ = [v for v in values if isinstance(v, ast.AST) and (
            selfish[key, id(v)] if (key, id(v)) in selfish else selfish.setdefault((key, id(v)), key in map(key_of, ast.walk(v))))]  # built from the name's own: `out += x`
        base = [x for v in values if not any(v is o for o in own_) for x in (
            ["\0"] if v is None else [v] if isinstance(v, str) else ["\2"] if isinstance(v, ast.Constant) and v.value is None else spellings(v))]
        for _ in own_[:3]:  # from each value it may have had, once for each such statement
            more = []
            for had in dict.fromkeys(base):
                picked[key] = had
                more += [x for v in own_ for x in spellings(v)]
                del picked[key]
            base += more
        found = list(dict.fromkeys(base))
        return ["\0"] if len(found) > 12 else found

    places = [where]  # each folder the program may stand in at some time, whatever the order: filled in below

    def elsewhere(raw: str) -> bool:  # a plain folder elsewhere leads this spelling, whatever its end
        lead = os.path.dirname(home(raw).split("\0")[0]) if "\1" not in raw else ""
        return os.path.isabs(lead) and not any(paths.inside(os.path.realpath(lead), r) or paths.inside(r, os.path.realpath(lead)) for r in roots)

    def inward(raw: str) -> set:  # the names that hold what a walk found from where the program stands: under such a folder they only go further in
        return {k for k in finds if all(v[:1] not in ("/", "~", "\0", "\1") and ".." not in v.split("/") for v in ranges.get(k + "~", ["/"]))} if elsewhere(raw) else set()

    def settle() -> None:  # what each name is built from and spells, to a fixed point
        grew = True
        while grew:
            grew = False
            live.update(gather())
            memo.clear()
            for key, values in list(live.items()):  # each name is every value it is given: a second assignment, two callers, what a loop visits
                name = key.split("~")[0]
                found = values_of(key, values) + ["\0"] * (total.get(name, 0) > sites.get(name, 0))
                found = ["\0"] if hidden and name in total else found  # given through globals() or locals(): no name is read
                if found != ranges.get(key, []) and turns.get(key, 0) < 8:  # names built from each other in a ring are not read
                    turns[key] = turns.get(key, 0) + 1
                    ranges[key], grew = found if turns[key] < 8 else ["\0"], True
            for target, value in pairs + [(n.optional_vars, n.context_expr) for n in nodes if isinstance(n, ast.withitem) and n.optional_vars is not None]:
                same = opened(value) or "name of " + getattr(value, "id", "") in tainted  # the file itself, or another name for it
                grew |= isinstance(target, ast.Name) and same and taint(["name of " + target.id])
                was = files.get(getattr(value, "id", "")) if isinstance(value, ast.Name) else spelled(source(value)) if source(value) is not None else None
                if isinstance(target, ast.Name) and target.id in once and target.id not in files and was and was[:1] != "\0":
                    files[target.id], grew = was, True
            for target, value in pairs:
                grew |= named(value, inward(spelled(value))) and taint(held(target))
                if isinstance(target, ast.Name) and target.id in once and target.id not in bound and spelled(value)[:1] != "\0":
                    bound[target.id], grew = spelled(value), True  # a name given one value once spells what that value spells
            for own, calls_of, init in callers.values():  # a helper called in one place spells what that caller hands it
                for taker, sent in hands(own, calls_of, init).items():
                    sent_as = {spelled(a) if a is not None else "\0" for a in sent if getattr(a, "id", None) != taker}  # its call of itself hands the same on
                    sent_to[taker] = [a for a in sent if a is not None and getattr(a, "id", None) != taker] if taker in once else []
                    if taker in once and taker not in bound and len(sent_as) == 1 and min(sent_as)[:1] != "\0":
                        bound[taker], grew = min(sent_as), True
            for n in loops:  # over rows the program spells out, each name takes its own column; over anything else, all of it
                each = n.iter.elts if isinstance(n.iter, (ast.List, ast.Tuple)) else rows.get(getattr(n.iter, "id", ""))
                width = len(getattr(n.target, "elts", []))
                if each is not None and width and all(isinstance(r, (ast.Tuple, ast.List)) and len(r.elts) == width and not any(
                        isinstance(e, ast.Starred) for e in r.elts + n.target.elts) for r in each):
                    grew |= taint(x for r in each for t, v in zip(n.target.elts, r.elts) if named(v) for x in held(t))
                else:  # of what a walk hands back, the folder is a path; the names in it are not
                    walked = isinstance(n.target, ast.Tuple) and getattr(getattr(n.iter, "func", None), "attr", "") in ("walk", "fwalk")
                    counted = isinstance(n.target, ast.Tuple) and len(n.target.elts) == 2 and getattr(getattr(n.iter, "func", None), "id", "") == "enumerate"
                    cols = {name: vs for name, vs in columns(n).items() if vs and all(isinstance(v, ast.AST) for v in vs)}  # a name whose every visit can be read
                    grew |= taint(name for name, vs in cols.items() if any(map(named, vs)))
                    grew |= named(n.iter) and taint(held(n.target.elts[0] if walked else n.target.elts[1] if counted else n.target) - set(cols))  # a count is no path
            for n in nodes:
                if isinstance(n, ast.withitem) and n.optional_vars is not None:
                    grew |= named(n.context_expr) and taint(held(n.optional_vars))
                    if getattr(n.optional_vars, "id", None) in once - set(bound) and spelled(n.context_expr)[:1] != "\0":
                        bound[n.optional_vars.id], grew = spelled(n.context_expr), True  # `with TemporaryDirectory() as d`
                elif isinstance(n, ast.arguments):  # a default
                    takers, values = n.posonlyargs + n.args + n.kwonlyargs, [None] * (len(n.posonlyargs + n.args) - len(n.defaults)) + n.defaults + n.kw_defaults
                    grew |= taint(a.arg for a, v in zip(takers, values) if v is not None and named(v))
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):  # what the program's own function hands back
                    grew |= any(isinstance(r, (ast.Return, ast.Yield, ast.YieldFrom)) and r.value is not None and named(r.value)
                                for r in ast.walk(n)) and taint([n.name])
                elif isinstance(n, ast.Call) and any(named(a) for a in n.args + [k.value for k in n.keywords]):
                    label, root = getattr(n.func, "attr", getattr(n.func, "id", "")), getattr(n.func, "value", None)
                    while isinstance(root, (ast.Attribute, ast.Subscript)):
                        root = root.value
                    if label in MUTATORS and isinstance(root, ast.Name):  # kept in a list, a set, a dict, a parser's defaults, the environment
                        grew |= taint([root.id] if root.id not in modules else [".environ"] * (getattr(n.func.value, "attr", "") == "environ"))
                    if label in fields_of:  # a class with fields and no __init__ of its own keeps what it is handed in them
                        grew |= taint("." + f for f in fields_of[label])
                    if not local.get(label) and (not isinstance(n.func, (ast.Name, ast.Attribute)) or label in stores or label in fields_given
                                                 or any(isinstance(a, ast.Lambda) for a in n.args)):
                        grew |= taint(a.arg for a in nodes if isinstance(a, ast.arg))  # handed to a function kept under a name, or to one written in place: any may take it
                    if label == "setattr" and len(n.args) == 3 and named(n.args[2]):
                        grew |= taint(held(n.args[0]) | {"." + (said(n.args[1]) or "")})
                    for name in [label] + [a.id for a in n.args if isinstance(a, ast.Name)]:  # handed to the program's own function
                        for own in [*local.get(name, ()), *filter(None, [inits.get(name)])]:  # a class is built by the __init__ it inherits
                            takers = [a.arg for a in own.posonlyargs + own.args]
                            takers = takers[takers[:1] in (["self"], ["cls"]):]
                            if name != label or any(isinstance(a, ast.Starred) for a in n.args) or None in [k.arg for k in n.keywords]:
                                grew |= taint(a.arg for a in ast.walk(own) if isinstance(a, ast.arg))  # through map or *args: any of them
                                continue
                            spare, extra = [own.vararg.arg] if own.vararg else [], [own.kwarg.arg] if own.kwarg else []
                            worded = {t.split("@")[0]: t for t in takers + [a.arg for a in own.kwonlyargs]}  # a keyword names it as it was written
                            grew |= taint([x for i, a in enumerate(n.args) if named(a) for x in takers[i:i + 1] or spare] + [
                                x for k in n.keywords if named(k.value) for x in ([worded[k.arg]] if k.arg in worded else extra)])
    def rowed(key, value) -> list:  # (key, value) for each row, when both are the names of one loop over rows the program spells out and neither is given anything else
        names_ = [getattr(key, "id", None), getattr(value, "id", "")]
        for n in [n for n in loops if [getattr(e, "id", 0) for e in getattr(n.target, "elts", [])] == names_ and all(total.get(x) == 1 for x in names_)]:
            cols, table_ = columns(n), resolve(n.iter.func.value) if getattr(getattr(n.iter, "func", None), "attr", "") == "items" else []
            if all(cols.get(x) and all(isinstance(v, ast.AST) for v in cols[x]) for x in names_):
                return list(zip(cols[names_[0]], cols[names_[1]]))
            if len(table_) == 1 and isinstance(table_[0], ast.Dict) and None not in table_[0].keys and not given_m.get(id(table_[0])):
                return list(zip(table_[0].keys, table_[0].values))
        return []

    def census() -> tuple:  # what each thing is given after it is made, and what is taken from it: read with what the pass before found
        given_, loose_, gone = {}, {}, set()

        def keep(of, sel, value) -> None:  # one thing given to a member: to each thing its holder may be, or to any when that cannot be told
            for c in resolve(of) or [None]:
                (given_.setdefault(id(c), {}) if c is not None else loose_).setdefault(sel[0], {}).setdefault(sel[1], []).append((value, tags.get(id(value))))
        for t in [n for n in nodes if isinstance(n, (ast.Attribute, ast.Subscript)) and isinstance(n.ctx, (ast.Store, ast.Del))]:
            m, f = sel_of(t), inside.get(id(t))
            if isinstance(t.ctx, ast.Del) or m is None:
                gone.update(id(c) for c in resolve(t.value)) if isinstance(t.ctx, ast.Del) else keep(t.value, ("k", None), None) if isinstance(t, ast.Subscript) else None
            elif m[1][1] is None and isinstance(t, ast.Subscript) and rowed(t.slice, pair_of.get(id(t))):
                for k, v in rowed(t.slice, pair_of[id(t)]):  # `for key, value in rows: cfg[key] = value`: each row's value under that row's key
                    keep(m[0], ("k", key_at(k)), v)
            elif not (m[1][0] == "a" and getattr(m[0], "id", "") == "self" and f is not None and f.name in ("__init__", "__post_init__") and id(f) in of_class):
                keep(m[0], m[1], None if id(pair_of.get(id(t))) in grown else pair_of.get(id(t)))  # what an __init__ gives self is read as the object is built
        for n in calls:
            label, base, kw = getattr(n.func, "attr", getattr(n.func, "id", "")), getattr(n.func, "value", None), {k.arg: k.value for k in n.keywords}
            if label == "putenv" and len(n.args) == 2:
                keep(ENV, ("k", key_at(n.args[0])), n.args[1])
            elif label == "setattr" and len(n.args) == 3:
                keep(n.args[0], ("a", key_at(n.args[1])), n.args[2])
            elif base is not None and label in ("setdefault", "__setitem__") and len(n.args) == 2:
                keep(base, ("k", key_at(n.args[0])), n.args[1])
            elif base is not None and label == "update":
                for k, v in [(k, v) for k, v in kw.items()] + [(None, None)] * (None in kw):
                    keep(base, ("k", k), v if k is not None else None)
                for o in [o for a in n.args for o in resolve(a) or [None]]:
                    spelt_out = isinstance(o, ast.Dict) and None not in o.keys
                    for k, v in zip(o.keys, o.values) if spelt_out else [(None, None)]:
                        keep(base, ("k", key_at(k) if spelt_out else None), v)
            elif base is not None and label in ("append", "add", "insert", "extend", "appendleft", "extendleft"):
                for a in n.args[label == "insert":]:
                    for v in (elements(a) or [None]) if "extend" in label else [a]:
                        keep(base, ("k", None), v)
            elif base is not None and label in ("pop", "popitem", "clear", "remove", "discard"):
                gone.update(id(c) for c in resolve(base))
        return given_, loose_, gone
    for _ in range(2):  # twice: what a loop visits depends on what its names are, and those on what loops visit
        live.update(gather())
        primed.append(1)
    for _ in range(4):  # until it settles: what a thing is given may be reached through what another was given (rows added to a list, then copied into a table)
        found = census()
        if found == (given_m, loose_m, removed):
            break
        given_m.clear(), loose_m.clear(), removed.clear(), memo.clear(), kn.clear()
        given_m.update(found[0]), loose_m.update(found[1]), removed.update(found[2])
        live.update(gather())
    kn.clear(), walked.clear(), memo.clear()
    settle()
    stand_in = os.path.expanduser(next((m for m in names if m[:1] in ("/", "~")), "".join(names[:1])))  # a protected folder, for one built from it that cannot be spelled

    def within(spot: str) -> bool:  # a folder the program may stand in lies in a protected one; an end that cannot be read lies under the part that can
        lead = spot if "\0" not in spot else os.path.dirname(spot.split("\0")[0])
        return os.path.isabs(lead) and any(paths.inside(os.path.realpath(lead), r) for r in roots)

    def lands(node, folder: bool = False, link: bool = False, at=(where,), reach=()) -> bool:  # whether a write's target is, or may be, in a protected folder
        return any(leads(path, node, folder, link, at, reach) for path in spellings(node) if "\2" not in path)  # no value at all writes nothing

    def leads(raw: str, node, folder: bool, link: bool, at, reach) -> bool:  # one spelling of a target, from each folder the call may be made in
        made = re.search("\1(\\d+)\1[^\1]*$", raw)  # made whole at an earlier call: from where the program stood then
        raw, at = (raw[raw.rfind("\1") + 1:], stood.get(int(made[1]), [where]) if made else places) if "\1" in raw else (raw, at)
        path = home(raw)
        froms = [""] if os.path.isabs(path) else at
        # A plain path is judged where it leads (one that names a protected folder and climbs away from it is not
        # plain). Any other target is judged by what it is built from, and inside by the folder that leads it.
        if "\0" not in path:
            reals = [os.path.realpath(os.path.join(s, path)) for s in froms if "\0" not in s]
            inside = [real for real in reals if any(paths.inside(real, r) for r in roots)]
            if any(_reaches(real, r, True) for real in reals if real not in inside for r in reach):
                return True  # a folder removed, moved or copied over whole changes the protected folder it holds
            unread = any("\0" in s and within(s) for s in froms)  # from a folder it cannot read, under a protected one
            if inside or unread or not any(m in raw for m in names):
                return unread or any(link or not _own(real, folder) for real in inside)  # no link is made there
        return named(node, inward(path)) or (any(map(within, at)) and not elsewhere(path))

    # Where the program stands when it makes each call. A folder change that is a statement of the program's own
    # body is sure: after it the program stands there, taken from wherever it stood. A change inside a loop, a
    # branch or a `with` may not have happened, so from its statement on the program may stand in either place, and
    # one inside a function may come at any time. A descriptor stands for the folder it was opened on (the seventh
    # review: of two changes one after the other only the first was followed, `fchdir` not at all, and a program
    # that had left a transcript folder for good was still held to it).
    def opened_on(node, seen: tuple = ()) -> list:  # what a descriptor stands for: the path each `open` that made it was given, and that call
        made = [v for t, v in pairs if isinstance(t, ast.Name) and t.id == getattr(node, "id", None) and t.id not in seen] or [node]
        return [x for v in made for x in (
            [((v.args[:1] or [k.value for k in v.keywords if k.arg in ("path", "file")] or [v])[0], v)]
            if isinstance(v, ast.Call) and getattr(v.func, "attr", direct.get(getattr(v.func, "id", ""), ("", getattr(v.func, "id", "")))[1]) == "open"
            else opened_on(v, seen + (node.id,)) if isinstance(v, ast.Name) and v is not node else [(v, None)])]  # kept under another name

    def folders(given, descriptor: bool = False, depth: int = 0) -> list:  # each folder those arguments may name, "\0" for a part that cannot be read
        found = []
        for a, call in [pair for arg in given for pair in (opened_on(arg) if descriptor else [(arg, None)])]:
            beside = [k.value for k in getattr(call, "keywords", ()) if k.arg == "dir_fd"] if depth < 4 else []
            for v in map(home, [x for x in spellings(a) if "\2" not in x]):
                if v[:1] == "\0":
                    found.append(stand_in if names and named(a) else v)
                elif beside and not os.path.isabs(v):  # opened beside another descriptor: under that one's folder
                    found += [os.path.join(base, v) for base in folders(beside, True, depth + 1)]
                else:
                    found.append((f"\1{id(call)}\1" if call is not None else "\1") * (descriptor and v[:1] not in ("/", "\1")) + v)
        return found

    def based(v: str, spots) -> list:  # the folders a path is read from: where the program stood at the call that opened it or made it whole
        made = re.search("\1(\\d+)\1", v)
        return (stood.get(int(made[1]), places) if made else places) if "\1" in v else spots

    def shift(spots, changes) -> list:  # where it may stand after each of those changes, from each folder it may stand in
        return [os.path.join(s, v[v.rfind("\1") + 1:]) for c in changes for v in change[id(c)] for s in based(v, spots)]

    def changer(n) -> str:  # "chdir" or "fchdir" for a name of either, under any name it was imported by
        found = direct.get(getattr(n, "id", ""), ("", getattr(n, "attr", getattr(n, "id", ""))))[1]
        return found if found in ("chdir", "fchdir") else ""
    handed_on = any(isinstance(n, (ast.Attribute, ast.Name)) and id(n) not in called and changer(n) for n in nodes)  # map(os.chdir, ...)
    stood, anywhere, functions = {}, [where], [f for f in nodes if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))]
    for _ in range(2):  # twice: what a walk finds depends on where the program may stand, and where it may stand on what its names spell
        change = {id(n): folders([*n.args, *(k.value for k in n.keywords)], changer(n.func) == "fchdir") for n in calls if changer(n.func)}
        places[:] = [where] + [stand_in] * bool(handed_on and names)  # a change handed on cannot be followed: it may stand in a folder the command names
        for _ in [v for values in change.values() for v in values]:
            places += [f for f in dict.fromkeys(shift(places, [n for n in calls if id(n) in change])) if f not in places][:64 - len(places)]
        settle()
    if change or handed_on:
        deferred = [c for f in functions for c in ast.walk(f) if id(c) in change]

        def walk(body: list, at: list) -> list:  # each statement in the order it runs, from the folders the program may stand in before it
            for stmt in body:
                if isinstance(stmt, (ast.With, ast.AsyncWith)):  # its body runs once and in order: a change in it is as sure as one outside
                    heads, back = [item.context_expr for item in stmt.items], at
                    at = walk([ast.Expr(value=h) for h in heads if id(h) not in change], at)
                    for h in [h for h in heads if id(h) in change]:  # `with contextlib.chdir(folder):` the body runs there
                        stood[id(h)], at = at, list(dict.fromkeys(shift(at, [h])))
                    passed = any(getattr(getattr(h, "func", None), "attr", getattr(getattr(h, "func", None), "id", "")) == "suppress" for h in heads)
                    at = walk(stmt.body, at) + back * passed  # under `suppress` a change may have failed and been passed over
                    at = back if any(id(h) in change for h in heads) else list(dict.fromkeys(at))  # and after `with chdir` it is back
                    continue
                if isinstance(stmt, ast.If):  # each branch in order; its main block always runs, any other may not
                    at = walk([ast.Expr(value=stmt.test)], at)
                    main = getattr(getattr(stmt.test, "left", None), "id", "") == "__name__" and not stmt.orelse
                    at = list(dict.fromkeys(walk(stmt.body, at) + (walk(stmt.orelse, at) if stmt.orelse or not main else [])))
                    continue
                if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):  # its body in order, each time from wherever a round may have left it
                    at = walk([ast.Expr(value=getattr(stmt, "iter", getattr(stmt, "test", None)))], at)
                    for _ in range(2):
                        now, mids = at, list(at)
                        for part in stmt.body:
                            now = walk([part], now)
                            mids += now
                        at = list(dict.fromkeys(mids))  # it may run no times, or leave at any point
                    at = walk(stmt.orelse, at)
                    continue
                if isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):  # in order until something fails: a handler and the
                    now, mids = at, list(at)                                      # finally may start from any point of the body
                    for part in stmt.body:
                        now = walk([part], now)
                        mids += now
                    done, mids = walk(stmt.orelse, now), list(dict.fromkeys(mids))
                    at = walk(stmt.finalbody, list(dict.fromkeys(done + [f for h in stmt.handlers for f in walk(h.body, mids)] + mids)))
                    continue
                inner = [c for c in ast.walk(stmt) if id(c) in change]
                mine = isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and (
                    modules.get(getattr(getattr(stmt.value.func, "value", None), "id", "")) == "os" or direct.get(getattr(stmt.value.func, "id", ""), ("",))[0] == "os")
                sure = mine and inner == [stmt.value]  # os's own change, not another object's method of that name
                stood.update((id(c), at) for c in ast.walk(stmt) if sure and isinstance(c, ast.Call))  # what it is handed was made before it
                before, at, maybe = at, list(dict.fromkeys(shift(at, inner))) if sure else at, deferred + inner * (not sure)
                for _ in [v for c in maybe for v in change[id(c)]]:  # a change that may come, and come again after another
                    at = at + [f for f in dict.fromkeys(shift(at, maybe)) if f not in at][:64 - len(at)]
                stood.update((id(c), before if sure else at) for c in ast.walk(stmt) if isinstance(c, ast.Call))
                anywhere.extend(f for f in at if f not in anywhere)
            return at
        walk(tree.body, [where] + [stand_in] * bool(handed_on and names))
        for f, spots in [(f, list(anywhere)) for f in functions]:  # a function runs wherever it is called: its own statements in order from there
            walk(f.body if isinstance(f.body, list) else [ast.Expr(value=f.body)], spots)

    stored = any(named(v) for entries in mapped.values() for _, v in entries)  # a protected path kept in some mapping, under any name

    same = {t.id: v.id for t, v in pairs if isinstance(t, ast.Name) and isinstance(v, ast.Name) and t.id in once}  # alias = process

    def owner(node):  # whose pipe: the name the process is kept under, the call that started it, None when it cannot be told
        node = node.value if getattr(node, "attr", "") == "stdin" else node
        name = getattr(node, "id", None)
        for _ in range(8):  # a second name for it is the same process
            name = same.get(name, name)
        return name if isinstance(node, ast.Name) else node if isinstance(node, ast.Call) else None
    begun = [c for c in calls if getattr(c.func, "attr", getattr(c.func, "id", "")) in ("Popen", "popen", "create_subprocess_exec", "create_subprocess_shell")]
    tied = begun + [t.id for t, v in pairs + withs if isinstance(t, ast.Name) and any(v is c for c in begun)]  # each process, and the names it is kept under
    fed_by = [c for c in begun if getattr(c.func, "attr", getattr(c.func, "id", "")) == "popen"]  # os.popen(command, "w"): what is written to it is the command's input
    fed_by += [t.id for t, v in pairs + withs if isinstance(t, ast.Name) and any(v is c for c in fed_by)]
    piped = [(owner(c.func.value), a) for c in calls if isinstance(c.func, ast.Attribute) and (c.func.attr == "communicate" or (
        c.func.attr in ("write", "writelines") and (getattr(c.func.value, "attr", "") == "stdin" or any(
            c.func.value is f or getattr(c.func.value, "id", None) == f for f in fed_by))))
        for a in c.args[:1] + [k.value for k in c.keywords if k.arg == "input"]] + [
        (owner(k.value), a) for c in calls for k in c.keywords if k.arg == "file" and getattr(k.value, "attr", "") == "stdin"
        for a in c.args[:1]]  # what the program writes down a pipe, and to which process: communicate, stdin.write, print(file=p.stdin)
    def descriptor(given) -> bool:  # a number, or a name given nothing but numbers and what os.open or mkstemp hands back
        made = [(given or [None])[0]] if isinstance((given or [None])[0], ast.Constant) else stores.get(getattr((given or [None])[0], "id", ""), [])
        return bool(made) and all((isinstance(v, ast.Constant) and (type(v.value) is int or v.value == "\2")) or (isinstance(v, ast.Call) and source(v) is not None and (
            modules.get(getattr(getattr(v.func, "value", None), "id", "")) == "os" or direct.get(getattr(v.func, "id", ""), ("",))[0] == "os")) for v in made)
    hit = wrote = False
    for n in calls:
        base = n.func.value if isinstance(n.func, ast.Attribute) else None
        label, kw = n.func.attr if base is not None else getattr(n.func, "id", ""), {k.arg: k.value for k in n.keywords}
        fds = [kw[k] for k in ("dir_fd", "src_dir_fd", "dst_dir_fd") if k in kw]  # a name given beside a descriptor is read from its folder
        at = stood.get(id(n), [where])
        at = [os.path.join(s, v[v.rfind("\1") + 1:]) for v in folders(fds, True) for s in based(v, [""])] + at * ("dir_fd" not in kw) if fds else at
        plain = base is None and label not in direct and label not in local  # a builtin, or a name a star import brought
        owners = ([modules.get(base.id, base.id)] if isinstance(base, ast.Name) else [imported(base).split(".")[0]] if imported(base)
                  else [direct[label][0]] if base is None and label in direct else stars if plain else [])
        label = direct[label][1] if base is None and label in direct else label
        every = [a for a in n.args + list(kw.values()) if said(a) is not None or not isinstance(a, ast.Constant)]  # a number names no file
        opener = label in ("open", "ZipFile", "TarFile", "FileIO") and (plain or any(m in OPENERS for m in owners))
        starred = any(isinstance(a, ast.Starred) for a in n.args) or None in kw  # open(*pair): the mode cannot be read
        method = base is not None and not imported(base) and not (isinstance(base, ast.Name) and base.id in modules)  # p.write_text(), not os.remove()
        mode = ((n.args[1:2] if opener else n.args[:1]) or [kw.get("mode")])[0]  # Path(p).open("w") takes its mode first
        def says(node, pattern) -> bool:  # a mode or a flag opens to write: as each value it may hold reads, and one that cannot be read may
            return any("\0" in text or "\1" in text or bool(re.search(pattern, text)) for text in ([said(node)] if said(node) is not None else spellings(node)))
        writes = mode is not None and says(mode, r"^[rbtU]*[wax+][\w+:|]*$")
        how = (n.args[1:2] or [kw.get("flags")])[0]
        how = given_once.get(getattr(how, "id", ""), how)  # flags kept under a name given them once
        flags = {x.attr if isinstance(x, ast.Attribute) else direct.get(x.id, ("", x.id))[1] for x in (ast.walk(how) if how is not None else ())
                 if isinstance(x, (ast.Attribute, ast.Name))} - set(modules)  # by the name each flag has in os
        reads_only = (isinstance(how, ast.Constant) and how.value == 0) or (bool(flags) and flags <= {
            "O_RDONLY", "O_CLOEXEC", "O_NONBLOCK", "O_NOFOLLOW", "O_DIRECTORY", "O_NOCTTY", "O_BINARY"})
        starts = "subprocess" in owners or (label in STARTS and bool({"os", "asyncio", "pty"} & {m.split(".")[0] for m in owners}))
        if starts:
            first = ast.List(elts=n.args) if label == "create_subprocess_exec" else (n.args[:1] or [kw.get("args")])[0]
            first = given_once.get(getattr(first, "id", ""), first)  # a command kept under a name given it once
            parts = [spelled(e) for e in first.elts] if isinstance(first, (ast.List, ast.Tuple)) else None
            if parts:  # one word of a list is one file: what it found in a protected folder stands for a file there, any other unread part for a name
                reads = os.path.basename(parts[0]) in SHELLS or bool(SCRIPT.match(os.path.basename(parts[0])))
                kind, code, _ = _program([w.replace("\0", "x") for w in parts]) if reads else ("", 0, "")
                code = 0 if "shell" in kw and getattr(kw["shell"], "value", True) else code - 1 if kind == "inline" else len(parts)
                hit = hit or (code < len(parts) and parts[code][:1] == "\0" and named(first.elts[code]))  # a script it cannot read, built from a protected path
                parts = [w.replace("\0", stand_in + "/x" if names and named(e) else "x") if w[:1] != "\0" else stand_in + "/x" if names and named(e) else w
                         for w, e in zip(parts, first.elts)]
                parts[:1] = [spelled(kw["executable"])] if "executable" in kw else parts[:1]  # the program it really runs
            ran = shlex.join(parts) if parts else spelled(first) if first is not None and parts is None else "\0"
            fed_code = any(os.path.basename(w) in SHELLS or SCRIPT.match(os.path.basename(w)) for w in (parts[:1] if parts else ran.split())) and (
                not parts or _program(parts)[0] == "stdin")  # a shell or an interpreter with no script of its own runs what it is fed
            if parts and "shell" in kw and getattr(kw["shell"], "value", True):
                ran = shlex.join(["sh", "-c", *parts])  # a list handed to the shell: its first word is the script, the rest that script's $0, $1 ...
            unplaced = any(map(named, n.args[1:] * (label != "create_subprocess_exec") + [v for k, v in kw.items() if k not in PLACED]))
            for key, value in handed(ast.Name(id="environ")) + (handed(kw["env"]) if "env" in kw else []):  # the variables the program hands it
                put = spelled(value) if "\0" not in spelled(value) else stand_in if names and named(value) else None
                if put is not None and re.fullmatch(r"[A-Za-z_]\w*", key or ""):
                    ran = f"{key}={shlex.quote(put)}; {ran}"
                else:
                    hit = hit or named(value)  # a protected path under a name it cannot tell: any command it starts may use it
            mine = {t.id for t, v in pairs + withs if v is n and isinstance(t, ast.Name)}  # the names this process is kept under
            feeds = [kw["input"]] if "input" in kw else [a for who, a in piped if who is n or who in mine or who not in tied] if label == "popen" or getattr(
                kw.get("stdin"), "attr", getattr(kw.get("stdin"), "id", "")) == "PIPE" else []  # its own pipe, and any that is no one's
            texts = ["".join(spelled(a) for a in feeds)] * bool(feeds)  # what it is fed, piece after piece, is that command's script
            dark = fed_code and "\0" in "".join(texts) and feeds  # one it cannot read is a script only for a shell or an interpreter
            was = [f for call in re.findall("\1(\\d+)\1", ran + "".join(texts)) for f in stood.get(int(call), [where])]
            at = (was or places) if "\1" in ran + "".join(texts) else at  # a word made whole earlier: from where the program stood then
            ran, texts = re.sub("\1(?:\\d+\1)?", "", ran), [re.sub("\1(?:\\d+\1)?", "", text) for text in texts]
            spots = [os.path.join(spot, v[v.rfind("\1") + 1:]) for spot in at for v in folders([kw["cwd"]])] if "cwd" in kw else at
            known = [os.path.realpath(f) if os.path.isabs(f) else f  # a folder it cannot read whole is judged from the part it can
                     for f in (spot if "\0" not in spot else os.path.dirname(spot.split("\0")[0]) for spot in spots)]
            if "\0" not in ran:  # a command it spells whole is judged as the shell guard judges one, wherever it may run
                for text in [t for t in texts if "\0" not in t] or [""]:
                    line = f"{ran} <<'INPUT_OF_THE_COMMAND'\n{text}\nINPUT_OF_THE_COMMAND" if text else ran
                    hit = hit or next(filter(None, (check_self_grant(line, f, config) for f in known)), False)  # the refusal itself
                hit = hit or (bool(dark) and any(map(named, dark))) or (stored and any(USED.search(text) for text in _resolved(ran)))
                if not dark and not unplaced:  # everything it is given was placed: nothing is left for the older rule,
                    continue                   # which holds a command handed anything built from a protected path
            hit = hit or any(map(named, feeds))  # a command it cannot read, fed what is built from a protected path
        told = kw.get("inplace", n.args[1] if len(n.args) > 1 else None)  # fileinput edits its files only when told to
        edits = told is not None and not (isinstance(told, ast.Constant) and not told.value)
        kept = [k for k, plain in (("follow_symlinks", True), ("symlinks", False)) if k in kw and getattr(kw[k], "value", None) is not plain]
        targets = [t for m in owners for t in (  # what a call into the standard library changes: a copy, only where it lands
            [] if m == "shutil" and label in ("which", "disk_usage", "get_terminal_size")
            else [] if (m, label) == ("shutil", "copyfileobj")  # two files already open: each open is judged where it is made
            else n.args[1:2] + [kw[k] for k in ("extract_dir",) if k in kw] or [ast.Constant(value=".")] if (m, label) == ("shutil", "unpack_archive")
            else n.args[:1] + [kw[k] for k in ("base_name",) if k in kw] if (m, label) == ("shutil", "make_archive")  # the folder it packs is read
            else n.args[1:2] + [kw[k] for k in ("dst", "fdst") if k in kw] or every if m == "shutil" and label in COPIES
            else [] if (m, label) == ("os", "open") and reads_only
            else n.args[:1] or [kw[k] for k in ("path",) if k in kw] if (m, label) == ("os", "open")  # its flags and its mode are no file
            else [] if (m, label) == ("os", "write") and descriptor(n.args[:1])  # to a descriptor os.open made: its open is judged where it is made
            else every if m == "shutil" or starts or (label == "connect" and m in ("sqlite3", "duckdb", "apsw")) or (m == "os" and OS_WRITES.fullmatch(label))
            or (m == "fileinput" and edits)
            else [])]
        if opener and (writes or starred):  # open(path, "w") or open(file=path, mode="w"); a descriptor os.open made was judged there
            targets += [a for a in n.args[:1] or [kw[k] for k in ("file", "name", "filename") if k in kw] if not descriptor([a])]
        elif method and label in ("extractall", "extract"):  # an archive unpacked: where it is told, else where the program stands
            targets += n.args[label == "extract":][:1] or [kw[k] for k in ("path",) if k in kw] or [ast.Constant(value=".")]
        elif method and label in LINKS:  # the link and what it points at: written through, it writes there
            targets += [base] + every
        elif method and (label in PATH_WRITES or (label == "open" and writes)):
            targets.append(base)
        elif method and label in ("rename", "replace") and len(n.args) + len(kw) == 1 and (n.args or "target" in kw):
            targets += [base] + every  # both ends change; str.replace takes two
        flag = (n.args[1:2] or [kw.get("mode", kw.get("flag"))])[0]
        aims = flag is not None and says(flag, r"[wax+cn]")  # opened to be written
        writer = BY_NAME.fullmatch(label) if not targets and not opener and asked(n)[1] is None else None  # the program's own save() is read as it is written
        lib = set() if method else {m.split(".")[0] for m in owners}
        made_by = [v for v in ([base] if isinstance(base, ast.Call) else live.get(key_of(base), []) if isinstance(base, ast.Name) else []) if isinstance(v, ast.Call)]
        sure, maybe = [], []  # what it takes as its path, and what may be its path
        if label == "open" and owners and not method and not opener and "os" not in owners:  # another library's store: shelve and dbm make one unless told to read
            sure = (n.args[:1] or [kw[k] for k in PATH_KEYS if k in kw]) * (aims or (flag is None and bool({"shelve", "dbm"} & set(owners))))
        elif writer is None and not targets and not opener and asked(n)[1] is None and OPENED.fullmatch(label) and (
                label.endswith(("Writer", "Store", "_writer")) or label == "memmap" if flag is None or label.endswith("Writer") else aims):
            sure = n.args[:1] or [kw[k] for k in PATH_KEYS if k in kw]  # h5py.File(path, "w"), ExcelWriter(path), np.memmap(path)
        elif method and label == "write" and any(re.fullmatch(r"ElementTree|parse|\w*(?:Writer|Merger)", getattr(v.func, "attr", getattr(v.func, "id", ""))) for v in made_by):
            sure = n.args[:1]  # a tree's or a document's own write(path); a file's write(text) is content
        elif writer and writer[4]:  # dump(what, where); a thing's own dump(where)
            sure, maybe = n.args[1:2], n.args[:1] * (method and len(n.args) == 1)
        elif writer and lib & OBJECT_FIRST and not writer[5]:  # torch.save(what, where), pd.to_pickle(what, where)
            sure = n.args[1:2]
        elif writer and (writer[1] or (writer[3] and (method or lib & PATH_FIRST or len(n.args) == 1))):
            sure, maybe = n.args[:1], n.args[1:2] * bool(method and writer[3])
        elif writer:  # to_<anything else>, write_<anything else>, another module's save(a, b): either may be the path; a deletion, as a module's own function
            maybe = (n.args if owners and not method else []) if writer[5] else n.args[:1 + (not method)]
        sure += [kw[k] for k in PATH_KEYS if k in kw] if writer else []
        led = {id(a): [s for s in spellings(a) if s[:1] not in ("\0", "\2")] for a in sure + maybe}  # each reading with a lead that can be read
        targets += [a for a in sure if led[id(a)] or stringy(a)] + [
            a for a in maybe if led[id(a)] and (named(a) or any(re.search(r"/|^~|\.\w{1,6}$", s) for s in led[id(a)]))]
        if label in LIBRARY_WRITES:  # the standard library's own writers: a log file, a download, a temporary file made where it is told
            targets += [kw[k] for k in ("filename", "dir") if k in kw] + (
                n.args[1:2] if label == "urlretrieve" else n.args[:1] if "Handler" in label else n.args[2:3] if label.startswith(("mk", "TemporaryD")) else [])
        wrote = wrote or bool(targets)
        gone = ([base] if method and label in ("rename", "replace") else (n.args[:1] or [kw[k] for k in ("src", "path") if k in kw])
                if label in ("rmtree", "move", "rename", "renames", "replace") else [])  # a tree removed or moved away whole takes all it holds
        over_it = n.args[1:2] + [kw[k] for k in ("dst",) if k in kw] if label == "copytree" else []  # one copied over a folder lands in what it holds
        hit = hit or any(lands(t, label in ("mkdir", "makedirs"), label in LINKS or bool(kept), at,
                               roots if any(t is x for x in gone) else folders_held if any(t is x for x in over_it) else ())
                         for t in targets)  # a copy that keeps links may make one
    return hit or (wrote and loose), wrote


def check_self_grant(command: str, cwd: str, config: dict | None = None) -> str | None:
    home = os.path.expanduser("~")
    if re.search(r"(?:^|[\s;&|(])(?:export\s+)?HOME=", command):  # a command that gives HOME its own value: `~` is that value too
        readings = _resolved(re.sub(r"(?<![\w$~./-])~(?=/|\s|$)", "$HOME", command))
    else:
        readings = _resolved(command.replace("${HOME}", home).replace("$HOME", home))
    return next(filter(None, (_self_grant(command, text, cwd, config) for text in readings)), None)


def _self_grant(command: str, text: str, cwd: str, config: dict | None) -> str | None:
    """One reading of a command: the reason it is refused, or None."""
    codes, home, store = approvals.pending(), os.path.expanduser("~"), paths.line_allowances(config or {})
    raw = _protected_roots(config)

    def spelled(name: str) -> set:  # as the command spells it: a Mac's file system ignores case
        return {m[0] for m in re.finditer(re.escape(name), text, re.I)}
    mine = spelled(store.name) if store else set()  # the store's own name: a write from inside its folder
    names = sorted({s for r in raw for n in (r, "~" + r[len(home):]) for s in spelled(n)} | mine)
    redirects, readable = [], True
    try:  # the files the parsed command writes, named in full or not (2026-11-11: a path relative to the session's
        _commands(text, cwd, writes=redirects)  # folder or to a `cd` was never looked at); a `>` inside quotes is not one
    except (Unreadable, StopIteration, IndexError):
        readable = False
    held = [os.path.realpath(r) for r in raw if not store or r != str(store)]

    def spots(where: str) -> list:  # where a command runs; for one `find -execdir` runs, the top of its search and each protected folder under it
        top = where[:-len(DEEP)]
        return [top] + [r for r in held if paths.inside(r, os.path.realpath(top))] if where.endswith(DEEP) else [where]
    asked = [(_led(os.path.expanduser(os.path.expandvars(t)), spot), spot) for t, w in redirects for spot in spots(w)]  # each write's target, and where it runs
    asked += [(t.strip("'\""), cwd) for t in re.findall(r">{1,2}\|?\s*([^\s;&|<>()]+)", text)] if names and not readable else []
    why, wheres, handed, links, made, linked = "", {cwd}, [], [], [], []
    if codes and re.search(r"(?i)\b(?:%s)\b" % "|".join(map(re.escape, codes)), command):
        why = "carries a pending approval code (to see pending requests, run `synthesis approvals`)"
    feeds, env = [], dict(os.environ)
    found = _parse(text, cwd, feeds=feeds)[0]
    for m in ASSIGNED.finditer(_own_text(text)):  # the value the command gives a variable; given two, the one that names a protected path
        if not m[2] and (env.get(m[1]) is None or m[1] in os.environ or any(n in m[3] for n in names)):
            env[m[1]] = m[3].strip("'\"")
    for (words, where), fed in [((words, spot), fed) for (words, where), fed in zip(found, feeds + [""] * len(found))
                                for spot in spots(where)]:  # each command, where it runs, with what it reads on its own stdin
        head, own = os.path.basename(words[0]), " ".join(words[1:])
        wheres.add(where)  # a redirect after `cd <root>` writes relative to that root
        if HOOK_RUN.search(words[0]) or ((SCRIPT.match(head) or head in SHELLS) and HOOK_RUN.search(_ran(words))):
            why = why or "runs the synthesis hook, which only the harness may run"
        landed = _landing(words)  # a copy onto a note or a script that is the agent's own lands on it, not inside it
        firm = {w for w in landed if _own(os.path.realpath(os.path.join(where, os.path.expanduser(w))))}
        roomy = {w for w in landed if head in COPIERS and _own(os.path.realpath(os.path.join(where, os.path.expanduser(w))), True)
                 and w not in firm and any(os.path.dirname(x.rstrip("/")) == w.rstrip("/") for x in landed if x != w)}
        landed = [w for w in landed if os.path.dirname(w) not in firm and w not in roomy]  # into its memory folder: the note it makes there
        asked += [(_led(os.path.expanduser(os.path.expandvars(w)), where), where) for w in landed]
        led = [os.path.realpath(os.path.join(where, os.path.expanduser(w))) for w in landed] if head in ("ln", "mkdir") else []
        links, made = links + led * (head == "ln"), made + led * (head == "mkdir")
        aimed = [w for w in words[1:] if not w.startswith("-")][:1] if head == "ln" else []  # what a link made here points at
        soft = any(re.fullmatch(r"-[A-Za-z]*s[A-Za-z]*|--symbolic", w) for w in words[1:])  # its target is read from the link's own folder
        linked += [(link, os.path.realpath(os.path.join(os.path.dirname(link) if soft else where, os.path.expanduser(aimed[0]))))
                   for link in led if aimed]
        moves = [os.path.realpath(os.path.join(where, os.path.expanduser(w))) for w in words[1:] if not w.startswith("-")] if head == "mv" else []
        for link, aim in [pair for pair in linked if pair[0] in moves[:-1]]:  # a link made here and then moved is that link at its new place
            for spot in (moves[-1], os.path.join(moves[-1], os.path.basename(link))):
                links, linked = links + [spot], linked + [(spot, aim)]
        within = any(paths.inside(os.path.realpath(where), os.path.realpath(r)) for r in raw)
        quoted = isinstance(where, Quoted)  # read out of a word handed to another program: judged for what it writes, runs and starts
        for word in _named(words) if readable and (not quoted or head in OPAQUE) else ():  # words the parser could not read name no program
            led = os.path.realpath(os.path.join(where, _led(os.path.expanduser(os.path.expandvars(word)), where)))
            if not within or word[:1] in ("~", "/") or word == HANDED or os.path.lexists(led):  # inside the folder, a file that is there
                handed.append((head, word, led))
        script = (fed or text) if _program(words)[0] == "stdin" else own  # read from stdin: its own heredoc, else whatever the line pipes in
        if SCRIPT.match(head) and re.search(r"\bsynthesis\b", script) and SELF_GRANT_CALLS.search(script):
            why = why or "runs synthesis's approval or send-window code, which only the guard and the principal's prompt use"
        source, argv = _python_source(words, fed) if head.startswith("python") else ("", [])
        # A Python program given inline or on stdin is judged by its own text: what its code writes. A protected
        # path named elsewhere on the line reaches it only through its arguments, its environment or the folder it
        # runs in (2026-10-06: through a variable). Its arguments are put where it reads them; through the
        # environment, or through arguments it takes unseen, any write it makes is refused. Another script is
        # judged by the words it is given, or, read from stdin, by the whole command.
        try:
            hit, wrote = _python_writes(source, names, [os.path.realpath(r) for r in raw], where, argv, dict(env, PWD=where), config) if source else (None, None)
        except RecursionError:  # nested too deeply to follow: judged by its text
            hit, wrote = None, None
        wrote = bool(re.search(SCRIPTED_WRITE, source or script)) if wrote is None else wrote  # by its syntax, else by its text
        carried = re.search(r"\b(?:environ|getenv|ENV)\b|\.env\b", script) and (any(n in m[3] for m in ASSIGNED.finditer(text) for n in names) or any(
            v[:1] == "/" and paths.inside(v, os.path.realpath(r)) for v in os.environ.values() for r in raw))
        reaches = hit is None and (carried or any(n in w for w in words[1:] if w != source for n in names))  # read by its syntax, both are placed
        lost = where[:1] in ("$", "`") and bool(names)  # it runs in a folder the guard cannot read, in a command that names a protected one
        if SCRIPT.match(head) and (hit or (wrote and (reaches or lost or (hit is None and (within or any(n in script for n in names)))))):
            inner = re.search(r"this command (.*?)\. Approvals come", hit) if isinstance(hit, str) else None
            why = why or (f"runs a program that starts a command this guard refuses: it {inner[1]}" if inner else
                          "runs a script that writes where the synthesis state, its board or a harness's transcripts live, or that "
                          "writes while such a path reaches it through an argument, the environment or the folder it runs in "
                          "(spell each file's path inside the program, or run the script alone)")
        sub, acts = _git(words, where)  # git acts where -C sends it; sent somewhere this cannot read, it is not shown to act here
        reads = sub is None or sub in GIT_READS or (sub == "remote" and words[words.index(sub) + 1:words.index(sub) + 2] in (
            [], ["-v"], ["get-url"], ["show"])) or any(w.startswith(("$", "`")) for w in words[1:words.index(sub)])
        stood = any(paths.inside(os.path.realpath(acts), os.path.realpath(str(r))) for r in (paths.state(), paths.board(), paths.sessions()))
        if stood and readable and not quoted and not ((head in READERS and reads) or head in WRITERS or head in OWN_RULES or (
                (SCRIPT.match(head) or head in SHELLS) and (source or not _ran(words)))):  # it names nothing, yet may write where it stands
            why = why or (f"runs `{head}` inside the synthesis state folder, its board or the session archive, where a "
                          "program this guard cannot read may write without naming a file (run it from another folder)")
        if head == "apply_patch":  # Codex's file editor, run as a command: the patch names every file it writes
            asked += [(a or b, where) for a, b in PATCH_PATHS.findall(text)]
    unread = ("$", "`")  # a target, or for a relative one the folder it is written in, that the command does not spell
    if not why and names and any(t.startswith(unread) or (not os.path.isabs(t) and str(w).startswith(unread)) for t, w in asked):
        why = ("writes to a place this guard cannot read (the target starts with a variable or a substitution the command "
               "does not set) while it names the synthesis state folder, its board or a harness's transcripts")
    targets = [os.path.join(w, t) for t, w in asked]
    real = [os.path.realpath(os.path.join(w, os.path.expanduser(t))) for t in targets for w in wheres]
    real += [aim + t[len(link):] for t in real for link, aim in linked if t not in links and paths.inside(t, link)]  # through a link made here
    real += [os.path.join(t, store.name) for t in real] if mine else []  # a copy into its folder
    owned = next((o for o in map(_cli_owned, real) if o), "") if not why else ""
    if owned:
        return f"Refused: this command writes {owned}"
    if not why and any(paths.inside(t, os.path.realpath(r)) for t in real for r in raw
                       if t in links or not (_own(t) or (t in made and _own(t, True)))):
        why = "writes into the synthesis state folder, a harness's session transcripts or the approved commit lines"
    # A target outside every protected folder may still change one. The approved lines are one file in a working
    # repository: removing or moving its folder removes it, while a search or a copy across that folder is judged by
    # what it names.
    apart = [t for t in real if not any(paths.inside(t, os.path.realpath(r)) for r in raw)]
    if not why and any(_reaches(t[:-len(end)] if end else t, os.path.realpath(r), bool(end)) for t in apart for r in raw
                       for end in [next((e for e in (OVER, GONE) if t.endswith(e)), "")]
                       if (end == GONE or (end and (not store or r != str(store)))) or (not end and re.search(r"[*?\[]", t))):
        why = ("changes a whole folder that holds the synthesis state folder, its board, the session archive or a harness's "
               "session transcripts, or names by a pattern what may lie in one (name what is to change, beside those folders)")
    given = "" if why else next((head for head, word, path in handed if (word == HANDED and names) or (not _material(path) and not _own(path) and any(
        paths.inside(path, os.path.realpath(r)) for r in raw))), "")  # HANDED: files from xargs, which cannot be read here
    if given:
        why = (f"gives `{given}` a file in the synthesis state folder, its board, a harness's session transcripts or the "
               f"approved commit lines, or files it takes from there through xargs, and `{given}` is not a program this "
               "guard knows to only read what it is given (read the file with cat, head, tail, grep or jq and pipe that in, or "
               "copy it out with cp and work on the copy)")
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
                                {c for c, _ in reached.values()}, session) if typed and (reached or sending) else []
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


def shell_tool(tool: str) -> bool:
    """A tool that runs a command line: the harnesses' shells and the Claude desktop app's terminal tab, whose
    commands passed every shell guard until 2026-10-30."""
    return tool in SHELL_TOOLS or tool.endswith("__run_in_terminal")


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
    return (bool(CALENDAR_WRITE.search(tool)) and notify == "none"
            and not tool_input.get("attendees") and not any(_invitees(tool_input)) and not rsvp)  # guests at any depth


def _sends(tool: str, tool_input: dict, config: dict) -> bool:
    """A tool that delivers words to people, by name or by what its name says it does (every channel, Rajiv,
    2026-10-13), or any server's `send_message` that addresses a mailbox or Chat space (the Gmail connector's
    server name is an id no name pattern can anticipate). Work in the principal's own repositories is not a send."""
    from synthesis import sends
    if sends.own_repo(sends.tool_repo(tool_input), config):
        return False
    # A write that emails no one is quiet, unless it moves a meeting to today: its guests' calendars still change.
    quiet = _quiet_calendar_write(tool, tool_input) and _invited_today(tool, tool_input, config) == 0
    return (((is_send_tool(tool, config) or sends.says(tool, config)) and not quiet)
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
    problems = message_problems("Bash", {"message_text": text}, config, set(chans), session)
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
    return (shell_tool(tool) or tool.startswith(BROWSER) or bool(desktop_tool(tool)) or _sends(tool, tool_input or {}, {})
            or routed(tool, tool_input or {}))


def check(tool: str, tool_input: dict, config: dict, cwd: str | None = None, session: dict | None = None) -> str | None:
    """cwd is the session's working directory (the hook payload's `cwd`); defaults to this process's.
    session is the hook payload, which names the transcript an approval is checked against."""
    if not cwd:
        try:
            cwd = str(tool_input.get("workdir") or "") or os.getcwd()
        except OSError:
            cwd = os.path.expanduser("~")
    if tool.endswith("__run_in_terminal") and tool_input.get("cwd"):  # the tab starts its shell there
        cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(str(tool_input["cwd"]))))
    if shell_tool(tool):
        command = shell_command(tool_input)
        return (check_destructive(command, config, cwd) or check_self_grant(command, cwd, config)  # a recursive delete is named as one
                or check_pr_gate(command, config, cwd, session)
                or check_deploy(command, config, cwd, session) or check_tunnel(command, config, cwd, session)
                or check_outgoing(command, config, cwd, session)
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
    return reason or check_travel(tool, tool_input, config) or (
        check_send(tool, tool_input, config, session) if _sends(tool, tool_input, config) else check_upload(tool, tool_input))
