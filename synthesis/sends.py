"""Outgoing messages in every channel (Rajiv, 2026-10-13): "Shouldn't it apply to all communications sent
for me / on my behalf, regardless of communications channel?" A call is a send by what it does, not by a
list of tool names: a connector tool whose name delivers words, or a shell command that posts. The send
window lets signed Ragbot sends go without a per-message code for a while, and the ledger lists the day's
sends for the daily plan's "On your behalf"."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.parse

from synthesis import paths

MAX_HOURS = 12  # Rajiv's ruling, 2026-10-13
# A window holds its planned sends and closes after the last (2026-10-27: one ran on for hours past them).
MAX_SENDS = 50
READS = {"get", "list", "read", "search", "fetch", "query", "find", "lookup", "inspect", "describe", "view", "show",
         "download", "export", "check", "count", "preview", "resolve", "debug"}
SAYS = {"send", "reply", "forward", "comment", "post", "publish", "share", "invite", "respond", "mention", "schedule",
        "submit", "draft", "announce", "notify", "remind"}
WRITES = {"create", "add", "edit", "update", "manage", "set", "put", "patch", "upsert", "write"}
SAID = {"comment", "message", "issue", "page", "post", "reply", "review", "draft", "event", "invite", "email", "mail",
        "reaction", "canvas", "envelope", "request", "ticket", "thread", "announcement", "story", "access", "permission"}
PREPOSITIONS = {"to", "on", "in", "for", "from", "with", "by", "of", "into", "as", "at"}
NOT_PEOPLE = ["mcp__ccd_*", "mcp__*__*session*"]  # agents talking to agents
ALSO_SENDS = ["mcp__*execute_zapier_write_action*", "mcp__*manage_out_of_office*",
              "mcp__*move[_-]event*"]  # moving a meeting notifies its guests; "move" is no saying verb (2026-11-11)
# An edit to a document, sheet or deck others read is published in the principal's name: on 2026-10-27 an agent
# added a line to an agenda seven colleagues read, with no code (the principal had approved it in chat).
DOCUMENT_EDITS = ["mcp__*__modify_doc_text", "mcp__*__batch_update_doc", "mcp__*__insert_doc_elements",
                  "mcp__*__insert_doc_image", "mcp__*__find_and_replace_doc", "mcp__*__update_doc_headers_footers",
                  "mcp__*__update_paragraph_style", "mcp__*__create_table_with_data", "mcp__*__manage_doc_tab",
                  "mcp__*__modify_sheet_values", "mcp__*__append_table_rows", "mcp__*__format_sheet_range",
                  "mcp__*__manage_sheet_tab", "mcp__*__batch_update_presentation", "mcp__*__update_drive_file"]
CHANNELS = [("imessage", "messages"), ("messages_send", "messages"), ("slack", "slack"), ("jira", "jira"), ("confluence", "confluence"), ("github", "github"),
            ("bitbucket", "bitbucket"), ("notion", "notion"), ("gmail", "email"), ("mail", "email"),
            ("event", "calendar"), ("calendar", "calendar"), ("document_comment", "docs"),
            ("spreadsheet_comment", "docs"), ("presentation_comment", "docs"), ("drive", "docs"), ("_doc", "docs"),
            ("paragraph", "docs"), ("table", "docs"), ("sheet", "docs"), ("presentation", "docs")]
# (channel, pattern over the command's words) for programs that post; `curl` and its kin are judged by method and host
# Global options may sit between a program and its subcommand: `bkt -c work pr edit` posted unseen (2026-10-14).
OPTS = r"(?:\s+-\S+(?:\s+(?!-)\S+)?)*"
COMMANDS = [
    ("github", rf"gh{OPTS}\s+(?:pr|issue)\s+(?:comment|create|edit|review)\b|gh{OPTS}\s+(?:pr|issue)\s+close\b.*(?:\s-c\b|\s--comment\b)"),
    ("bitbucket", rf"bkt{OPTS}\s+pr\s+(?:comment|create|edit|approve|decline|reopen|request-changes)\b"),
    ("gitlab", rf"glab{OPTS}\s+(?:mr|issue)\s+(?:note|comment|create|update)\b"),
    ("jira", r"(?:jira|acli)\b.*\b(?:comment|create|edit)\b"),
    ("messages", r"osascript\b.*\b(?:Messages|Mail)\b.*\bsend\b"),
]
API = {"gh": "github", "bkt": "bitbucket", "glab": "gitlab"}
WEB = {"curl", "wget", "http", "https", "xh"}
LOCAL = re.compile(r"(?:localhost|127\.0\.0\.1|\[?::1\]?|[\w.-]+\.localhost|[\w.-]+\.test)$")


def _words(name: str) -> list:
    return [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", name)]


def says(tool: str, config: dict) -> bool:
    """True when a connector tool delivers words to people: a saying verb (send, comment, post...), or a
    writing verb whose object is something people read (create an issue, update a page)."""
    if any(fnmatch.fnmatchcase(tool, p) for p in NOT_PEOPLE + list(config.get("not_send_tools", []))):
        return False
    if any(fnmatch.fnmatchcase(tool, p) for p in ALSO_SENDS + DOCUMENT_EDITS):
        return True
    words = _words(tool.rsplit("__", 1)[-1])
    verbs = [i for i, w in enumerate(words) if w in READS | SAYS | WRITES]
    if not verbs or words[verbs[0]] in READS:
        return False
    if any(w in SAYS for w in words[verbs[0]:]):
        return True
    thing = []
    for w in words[verbs[0] + 1:]:
        if w in PREPOSITIONS:
            break
        thing.append(w)
    head = thing[-1] if thing else ""
    return words[verbs[0]] in WRITES and (head in SAID or (head.endswith("s") and head[:-1] in SAID))


def channel(tool: str, tool_input: dict) -> str:
    name = tool.lower()
    found = next((c for key, c in CHANNELS if key in name), "")
    if not found and any(k in tool_input for k in ("to", "cc", "bcc")):
        found = "email"
    return found or ("chat" if name.endswith("send_message") else "other")


def own_repo(repo: str, config: dict) -> bool:
    return bool(repo) and any(fnmatch.fnmatchcase(repo.lower(), p.lower()) for p in config.get("own_repos", []))


def tool_repo(tool_input: dict) -> str:
    owner, repo = tool_input.get("owner"), tool_input.get("repo")
    return f"{owner}/{repo}" if isinstance(owner, str) and isinstance(repo, str) else ""


def _origin(cwd: str) -> str:
    """owner/repo of the GitHub remote a `gh` command in cwd acts on."""
    import subprocess
    try:
        url = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True, text=True,
                             timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    found = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$", url)
    return found.group(1) if found else ""


def _web_write(words: list) -> bool:
    """A curl, wget or HTTPie call that writes to a host other than this machine."""
    hosts = [urllib.parse.urlsplit(w).hostname or "" for w in words if re.match(r"https?://", w)]
    if not hosts or all(LOCAL.match(h) for h in hosts):
        return False
    rest = " " + " ".join(words[1:])
    if os.path.basename(words[0]) in ("http", "https", "xh"):
        return bool(re.search(r"\s(?:POST|PUT|PATCH|DELETE)\s|\s[\w.-]+:?=", rest))
    return bool(re.search(r"\s(?:-X|--request|--method)[=\s]*(?:POST|PUT|PATCH|DELETE)\b|\s(?:-d|-F|-T|--data[\w-]*|--form"
                          r"|--json|--upload-file|--post-data|--post-file|--body-data|--body-file)\b", rest))


def command_send(words: list, cwd: str, config: dict) -> str | None:
    """The channel a shell command posts to, or None. Own repositories (`own_repos`) are not sends."""
    head = os.path.basename(words[0])
    line = " ".join([head] + words[1:])
    if {"-h", "--help"} & set(words[1:]):
        return None  # help prints and posts nothing (2026-10-13: `bkt pr edit --help` asked for a code)
    if head in WEB:
        return "web" if _web_write(words) else None
    if head in API and re.match(rf"{head}{OPTS}\s+api\b", line):
        if not re.search(r"\s(?:-X|--method)[=\s]*(?:POST|PUT|PATCH|DELETE)\b|\s(?:-f|-F|--field|--raw-field|--input)\b",
                         " " + line) or ("graphql" in words and "mutation" not in line):
            return None
        path = next((w for w in words[2:] if re.match(r"/?repos/", w)), "")
        repo = "/".join(path.lstrip("/").split("/")[1:3])
        return None if head == "gh" and own_repo(repo, config) else API[head]
    found = next((c for c, p in COMMANDS + [(c, p) for c, p in config.get("send_commands", [])] if re.match(p, line)), None)
    if found == "github":
        flag = next((words[i + 1] for i, w in enumerate(words[:-1]) if w in ("-R", "--repo")), "")
        if own_repo(flag or _origin(cwd), config):
            return None
    return found


def cli_calls(words: list) -> list:
    """(its arguments, or None where they cannot be read as the CLI reads them; its words) for each `synthesis sends` a
    command's words run, read with the CLI's own parser (cli.parsed), so the guard and the CLI never read one command two
    ways (the review of 5.23.0). Every CLI word counts, wherever it stands (`synthesis --session S sends open` opened a
    window with no code on 2026-10-13; `synthesis wait -- synthesis sends ...` runs one later). Help does nothing."""
    found = []
    for i, w in enumerate(words):
        argv = words[i + 1:]
        if "sends" not in argv or not (os.path.basename(w) == "synthesis" or w in ("synthesis.cli", "synthesis/cli.py")
                                       or w.endswith("synthesis/cli.py")):
            continue
        import contextlib  # only for a line that runs the CLI: every other command pays nothing for its parser
        import io
        from synthesis import cli
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                args = cli.parsed(argv)
        except SystemExit as done:
            if done.code in (0, None):  # help, which prints and does nothing
                continue
            args = "unread"
        if args is not None and (args == "unread" or args.command == "sends"):
            readable = args != "unread" and not any(re.search(r"[$`*?]", a) for a in argv)  # a word the shell changes first
            found.append((args if readable else None, argv))
    return found


def window_refusal(window: dict) -> str:
    from synthesis import approvals
    scope = f"{window['sends']} sends in {window['hours']:g} h, {', '.join(window['channels']) or 'no channels'}" + (
        f", project {window['project']}" if window["project"] else "")
    code = approvals.request("send-window", window, f"open a send window: {scope}")
    return (f"Opening a send window ({scope}) lets signed Ragbot sends go without a per-message code until it ends. "
            f"Show the principal that scope and ask them to type {approvals.how(code)}. Then run the identical command again.")


def asked(hours, channels: str, project: str, count=0) -> dict:
    """A window request in one form, so the guard and the command bind the same approval."""
    try:
        hours = float(hours)
    except ValueError:
        hours = 0.0
    count = int(count) if str(count).isdigit() else 0
    return {"hours": hours, "channels": sorted({c.strip() for c in str(channels).split(",") if c.strip()}),
            "project": str(project), "sends": count}


CAT = re.compile(r"\s*cat\s+(['\"]?)([^'\"\s]+)\1\s*")


def _substitutions(word: str) -> tuple[list, str]:
    """The commands substituted into a word ($(...) and backticks), and the word without them."""
    from synthesis.guards import _close
    inner, rest, i = [], [], 0
    while i < len(word):
        if word.startswith("$(", i) or word[i] == "`":
            start = i + (2 if word[i] == "$" else 1)
            end = _close(word, start, "(" if word[i] == "$" else "`")
            inner.append(word[start:end - 1])
            i = end
        else:
            rest.append(word[i])
            i += 1
    return inner, "".join(rest)


def _strings(value) -> list:
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    return [s for v in value for s in _strings(v)] if isinstance(value, list) else [value] if isinstance(value, str) else []


def _readable(text: str) -> str:
    """JSON is read as the strings it carries, so an escaped emoji is the emoji and its layout is not prose."""
    if text.strip()[:1] in ("{", "["):
        try:
            return "\n\n".join(_strings(json.loads(text)))
        except ValueError:
            pass
    return text


def message_text(words: list, cwd: str, written: set = frozenset()) -> tuple[str, str]:
    """(text, problem): the message a posting command sends, which the register scan reads: its text words, every
    body it reads from a file (--body-file, gh's -F, --input, @file, $(cat file)) and every heredoc a substituted
    command reads. Options, URLs, file names and the code around a heredoc are not the message (2026-10-13)."""
    from synthesis import guards
    flags = {"--body-file", "--input"} | ({"-F"} if os.path.basename(words[0]) == "gh" and words[1:2] in (["pr"], ["issue"]) else set())
    names, parts, takes = [], [], False
    for word in words[1:]:
        if takes:  # the file a body flag names
            names.append(word)
            takes = False
            continue
        if word in flags:
            takes = True
            continue
        at = re.match(r"(?:[\w.-]+=)?@([^@\s]+)$", word)
        if at:
            names.append(at.group(1))
            continue
        try:
            commands, word = _substitutions(word)
            for inner in commands:
                cat, heredocs = CAT.fullmatch(inner), [t[1] for t in guards._lex(inner) if t[0] == "in"]
                if not (cat or heredocs):
                    return "", (f"its body comes from a command ({inner.strip()[:60]}) whose output the guard cannot "
                                "read; put the text inline, in a heredoc, or in a file")
                names, parts = names + ([cat.group(2)] if cat else []), parts + heredocs
        except guards.Unreadable as exc:
            return "", f"its text cannot be read ({exc})"
        word = word.partition("=")[2] if word.startswith("-") else word  # --body=text keeps its text
        if word and (any(c.isspace() for c in word) or not ("/" in word or os.path.exists(os.path.join(cwd, word)))):
            parts.append(word)
    texts = []
    for name in names:
        path = os.path.join(cwd, os.path.expanduser(name))
        if name == "-" or "$" in name or not os.path.isfile(path):
            return "", f"its body comes from {name}, which the guard cannot read to check"
        if os.path.realpath(path) in written:
            return "", (f"it writes {name} and posts it in one command, so the guard would check the old contents; "
                        "write the file in one command and post it in the next")
        with open(path, encoding="utf-8", errors="replace") as handle:
            texts.append(handle.read(1_048_576))
    return "\n\n".join(_readable(t) for t in parts + texts), ""


# --- the window ---------------------------------------------------------------------------------


def _window_file():
    return paths.state() / "sends" / "window.json"


def window() -> dict:
    """The open window, or {}: one that has run out is closed."""
    data = paths.read_json(_window_file())
    return data if data and float(data.get("until", 0)) > time.time() else {}


def check_window(hours: float, channels: list, count: int) -> None:
    if not 0 < hours <= MAX_HOURS:
        raise ValueError(f"a send window lasts more than 0 and at most {MAX_HOURS} hours")
    if not 0 < count <= MAX_SENDS:
        raise ValueError(f"name the sends it is for (--sends, 1 to {MAX_SENDS}): it closes after the last")
    if not channels:
        raise ValueError("name the channels it covers (for example slack,jira,bitbucket), or all")


def open_window(hours: float, channels: list, project: str = "", count: int = 0) -> dict:
    check_window(hours, channels, count)
    data = {"opened": time.time(), "until": time.time() + hours * 3600, "channels": sorted(set(channels)),
            "project": project, "sends": count}
    paths.write_json(_window_file(), data)
    return data


def close_window() -> bool:
    try:
        _window_file().unlink()
        return True
    except FileNotFoundError:
        return False


def spent(w: dict) -> int:
    """Sends the window has let through since it opened (it may span midnight)."""
    days = {time.strftime("%Y-%m-%d", time.localtime(w["opened"])), time.strftime("%Y-%m-%d")}
    return sum(1 for d in days for e in ledger(d) if e.get("how") == "window" and e.get("at", 0) >= w["opened"])


def settle() -> None:
    """After a send the window let through: its last planned send closes it."""
    w = window()
    if w and spent(w) >= w.get("sends", 0):
        close_window()


def covered(chan: str, texts: list, project: str, config: dict) -> str:
    """Why the open window covers this send, or "" when it does not (a window with no planned sends covers none)."""
    w = window()
    w = w if w and spent(w) < w.get("sends", 0) else {}
    marks = [m for m in config.get("send_window_signatures", []) if any(re.search(m, t) for t in texts)]
    if w and ("all" in w["channels"] or chan in w["channels"]) and (not w.get("project") or w["project"] == project) and marks:
        return f"the send window open until {time.strftime('%H:%M', time.localtime(w['until']))}"
    return ""


def describe(w: dict) -> str:
    scope = ", ".join(w["channels"]) + (f"; project {w['project']}" if w.get("project") else "")
    left = max(w.get("sends", 0) - spent(w), 0)
    return (f"Send window open until {time.strftime('%H:%M', time.localtime(w['until']))} ({scope}), {left} of "
            f"{w.get('sends', 0)} sends left: signed Ragbot sends go without a per-message code and are logged; the "
            "last planned send closes it, and `synthesis sends close` ends it sooner.")


# --- batches ------------------------------------------------------------------------------------
# 2026-11-14: drafts in the principal's own words, read and approved in one sitting. One code for a batch's digest lets
# each entry go once, exactly as written, within 12 hours, from a session on its project. Binding each text and
# recipient is stronger than a window, so a batch may carry what a window must not: the principal's own words.

# A page whose address names one conversation: (site, and every host under it; the path that names it; channel, as the
# guard names the site's pages). An encrypted chat's path and a plain one's are two conversations (2026-11-14: every
# chat facebook.com lists links to /messages/e2ee/t/<id>/), and so are the two sites'.
CONVERSATIONS = (("facebook.com", r"/messages/(?:e2ee/)?t/[\w.-]+", "messenger"),
                 ("messenger.com", r"/(?:e2ee/)?t/[\w.-]+", "messenger"))
HANDLE = re.compile(r"\+[1-9][0-9]{6,14}|[^\s@,]+@[^\s@,]+\.[^\s@,]+")  # what messages_send.py takes: +<country code><number>, or an address
KINDS = ('none of the four kinds: a connector call {"tool", "input"}, a browser send {"channel", "to", "text"}, and a '
         'messages send by --to {"channel": "messages", "to", "text"} or by --members {"channel": "messages", "members", '
         '"service", "chat", "text"}, each with nothing else')
# What a Messenger entry's send reads of the page, shared by the read-only check (`synthesis sends composer-check`) and
# the send script, so a live read shows exactly what a send reads. The box is the one contenteditable textbox labelled
# `Write to ...` or for a message, with the placeholder `Aa`, or a Lexical editor (the coordinator's live read of
# 2026-11-14: `Write to <Name>`, `Aa`, Lexical, in no form); the composer around it is its nearest ancestor that holds
# a control labelled for sending or for a file or attachment. Outside the box, in the composer or in any other child of
# its parent (in plain mode the composer is that parent's only child, live 2026-11-15), staged counts media, an svg
# outside a control (a file's icon) and a control labelled to remove, close, cancel, delete or discard (the third
# round, #6); marks count text that opens with `Replying to`, `Edit`, `Editing`, `Cancel reply` or `Cancel edit`, a
# control labelled for a reply or an edit, a quotation, and a heading outside the composer (inside it only by those
# words: it always holds a hidden `Compose` heading). Inline counts images in the box.
_READ = ("const boxes = [...document.querySelectorAll('[contenteditable=\"true\"][role=\"textbox\"]')]; "
         "const fits = b => /^write to|message/i.test(b.getAttribute('aria-label') || '') || "
         "b.getAttribute('aria-placeholder') === 'Aa' || b.hasAttribute('data-lexical-editor'); "
         "const found = boxes.filter(fits); const box = found.length === 1 ? found[0] : null; let area = box && "
         "box.parentElement; while (area && ![...area.querySelectorAll('[aria-label*=\"send\" i], [aria-label*=\"file\" i], "
         "[aria-label*=\"attach\" i]')].some(e => !box.contains(e))) area = area.parentElement; "
         "const label = e => e.getAttribute('aria-label') || ''; const near = area ? [...(area.parentElement || area)"
         ".querySelectorAll('*')].filter(e => !box.contains(e) && !e.contains(box)) : null; "
         "const staged = near && near.filter(e => /^(img|video|audio|canvas|object|embed|iframe|picture)$/i.test(e.tagName) || "
         "/^svg$/i.test(e.tagName) && !e.closest('[role=\"button\"], [role=\"link\"], button, a') || "
         "/remove|close|cancel|delete|discard/i.test(label(e))).length; "
         "const marks = near && near.filter(e => /^\\s*(replying to|edit(ing)?|cancel (reply|edit))\\b/i.test(e.innerText || '') || "
         "/reply|edit/i.test(label(e)) || e.tagName === 'BLOCKQUOTE' || !area.contains(e) && (e.getAttribute('role') === "
         "'heading' || /^H[1-6]$/.test(e.tagName))).length; "
         "const inline = box && box.querySelectorAll('img, svg, picture, canvas, video, [role=\"img\"]').length; ")
COMPOSER_MARK = "synthesis-composer-6"
COMPOSER_CHECK = ("(() => { " + _READ + "return JSON.stringify({check: '" + COMPOSER_MARK + "', url: location.href, box: "
                  "found.length > 1 ? 'ambiguous' : box ? 'found' : 'none', text: box ? box.innerText : null, focused: !!box && "
                  "box.contains(document.activeElement), staged: !box ? null : area ? staged : 'unknown', marks: !box ? null : "
                  "area ? marks : 'unknown', inline: box ? inline : null, boxes: boxes.length}); })()")
# SHA-256 of a text's UTF-8, synchronous (crypto.subtle answers later, and the send must be one run).
_SHA = ("const sha = s => { const K = [], H = [], b = [...new TextEncoder().encode(s)], n = b.length * 8; "
        "for (let p = 2, c = 0; c < 64; p++) { let prime = true; for (let d = 2; d * d <= p; d++) if (p % d === 0) { prime = false; "
        "break; } if (prime) { if (c < 8) H[c] = Math.pow(p, 1 / 2) * 2 ** 32 | 0; K[c++] = Math.pow(p, 1 / 3) * 2 ** 32 | 0; } } "
        "b.push(128); while (b.length % 64 !== 56) b.push(0); for (let i = 7; i >= 0; i--) b.push(i > 3 ? 0 : n >>> i * 8 & 255); "
        "const r = (x, k) => x >>> k | x << 32 - k; for (let o = 0; o < b.length; o += 64) { const w = [], v = H.slice(); "
        "for (let i = 0; i < 64; i++) { w[i] = i < 16 ? b[o + 4 * i] << 24 | b[o + 4 * i + 1] << 16 | b[o + 4 * i + 2] << 8 | "
        "b[o + 4 * i + 3] : (r(w[i - 2], 17) ^ r(w[i - 2], 19) ^ w[i - 2] >>> 10) + w[i - 7] + (r(w[i - 15], 7) ^ "
        "r(w[i - 15], 18) ^ w[i - 15] >>> 3) + w[i - 16] | 0; const t = v[7] + (r(v[4], 6) ^ r(v[4], 11) ^ r(v[4], 25)) + "
        "(v[4] & v[5] ^ ~v[4] & v[6]) + K[i] + w[i] | 0, u = (r(v[0], 2) ^ r(v[0], 13) ^ r(v[0], 22)) + (v[0] & v[1] ^ "
        "v[0] & v[2] ^ v[1] & v[2]) | 0; v.pop(); v.unshift(t + u | 0); v[4] = v[4] + t | 0; } "
        "for (let i = 0; i < 8; i++) H[i] = H[i] + v[i] | 0; } return H.map(x => (x >>> 0).toString(16).padStart(8, '0')).join(''); }; ")
# A Messenger entry's send (the third round of 5.24.0's review, #1, #2, #3 and #6): one synchronous run that reads the
# composer, compares its words to the entry's by digest, and clicks the one control labelled `Press enter to send` or
# `Send` only when the page is the entry's conversation, its words are the entry's and nothing is staged or marked, so no
# typist, other session or later script acts between the read and the send. It runs last in the send step.
SEND_MARK = "synthesis-send-1"
SEND_SCRIPT = ("(() => { const want = __WANT__; " + _READ + _SHA + "const host = location.hostname.replace(/\\.$/, ''); "
               "const site = " + json.dumps([site for site, _, _ in CONVERSATIONS]) + ".find(s => host === s || host.endsWith('.' + s)); "
               "const here = site ? site + location.pathname.replace(/\\/+$/, '') : ''; const words = box ? box.innerText.replace("
               "/\\n$/, '') : null; const same = words !== null && sha(words) === want.digest; const controls = area ? "
               "[...area.querySelectorAll('[aria-label]')].filter(e => !box.contains(e) && /^(press enter to send|send)$/i.test("
               "label(e).trim())) : []; const sent = here === want.to && same && staged === 0 && marks === 0 && inline === 0 && "
               "controls.length === 1; if (sent) controls[0].click(); return JSON.stringify({send: '" + SEND_MARK + "', url: "
               "location.href, conversation: here === want.to, box: found.length > 1 ? 'ambiguous' : box ? 'found' : 'none', "
               "words: same, staged, marks, inline, controls: controls.length, sent, after: box ? box.innerText : null}); })()")
ADDRESS_KEYS = ("to", "cc", "bcc", "channel", "channel_id", "chat_id", "space_id", "space_name", "thread_id", "thread_ts",
                "user_id", "recipient", "recipients", "issueIdOrKey", "owner", "repo", "pull_number", "issue_number")


def conversation(address: str) -> tuple | None:
    """(channel, site and path) of an address that names one conversation, its trailing slash, query and fragment left
    off; None for any other."""
    try:
        url = urllib.parse.urlsplit(address.strip() if "://" in address else "//" + address.strip())
        host, path = (url.hostname or "").rstrip("."), url.path.rstrip("/")
    except ValueError:
        return None
    return next(((chan, site + path) for site, pattern, chan in CONVERSATIONS
                 if (host == site or host.endswith("." + site)) and re.fullmatch(pattern, path, re.ASCII)), None)


def _unique(pairs: list) -> dict:
    keys = [k for k, _ in pairs]
    twice = next((k for k in keys if keys.count(k) > 1), None)
    if twice is not None:
        raise ValueError(f"the key {twice!r} is given twice")
    return dict(pairs)


def _no_number(name: str):
    raise ValueError(f"{name} is no number JSON has")


def read_batch(file: str) -> dict:
    """The batch a file holds, after every check a batch passes; ValueError says what is wrong. A key given twice and a
    number JSON does not have are refused: what the principal reads must be what the digest binds."""
    with open(file, encoding="utf-8") as handle:
        text = handle.read(1_048_577)
    try:
        if len(text) > 1_048_576:
            raise ValueError("it is larger than 1 MB")
        return checked(json.loads(text, object_pairs_hook=_unique, parse_constant=_no_number))
    except ValueError as exc:
        raise ValueError(f"{_shown(file)} is no batch: {exc}") from None


def checked(batch) -> dict:
    """The batch itself when it has the one shape a batch takes; else ValueError, naming what is wrong."""
    if not isinstance(batch, dict) or set(batch) != {"batch", "project", "entries"}:
        raise ValueError('a batch is {"batch": <name>, "project": <project>, "entries": [...]}, with nothing else')
    if not all(isinstance(batch[k], str) and batch[k].strip() for k in ("batch", "project")):
        raise ValueError("a batch names itself and the project whose sessions send it")
    entries = batch["entries"]
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_SENDS:
        raise ValueError(f"a batch holds 1 to {MAX_SENDS} entries")
    hidden = _controls(batch)  # the review of 5.23.0: an escape code hid words in the listing, a carriage return overprinted
    if hidden:
        raise ValueError(f"it holds a control character other than a newline, or half of a surrogate pair ({_shown(hidden)[:80]}), "
                         "which no listing shows")
    seen = {}
    for n, entry in enumerate(entries, 1):
        problem = _entry_problem(entry)
        if problem or entries.index(entry) < n - 1:
            raise ValueError(f"entry {n} {problem or f'repeats entry {entries.index(entry) + 1}'}")
        where = _conversation_of(entry)
        if where in seen:  # four entries that read as four people were one conversation (the same review)
            raise ValueError(f"entry {n} goes to the conversation of entry {seen[where]}: one entry for each conversation")
        seen.update({where: n} if where else {})
    return batch


def _conversation_of(entry: dict):
    """The conversation an entry goes to, one entry each: a Messenger address, a handle or a chat; for a connector call,
    its tool's channel and the recipient fields it names (the review of 5.24.0), or None where it names none."""
    if "tool" not in entry:
        return entry["channel"], entry.get("chat") or entry.get("to")
    named = {k: entry["input"][k] for k in ADDRESS_KEYS if k in entry["input"]}
    return (channel(entry["tool"], entry["input"]), json.dumps(named, sort_keys=True)) if named else None


def _controls(value) -> str:
    """The first string of a JSON value, a key included, that holds a control character other than a newline or half of
    a surrogate pair (a JSON escape can hold one); else ""."""
    if isinstance(value, dict):
        return next((s for k, v in value.items() for s in (_controls(k), _controls(v)) if s), "")
    if isinstance(value, list):
        return next((s for v in value for s in [_controls(v)] if s), "")
    return value if isinstance(value, str) and any(unicodedata.category(c) in ("Cc", "Cs") and c != "\n" for c in value) else ""


# Characters of a kind that draws (letters, marks, symbols) that render as nothing or as a plain space: fillers, blanks,
# joiners and selectors (the review of 5.24.0: variation selectors, U+034F, U+115F and U+3164 printed as is; its third
# round: U+1D159 and U+16FE4).
INVISIBLE = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F), (0x2800, 0x2800), (0x3164, 0x3164),
             (0xFE00, 0xFE0F), (0xFFA0, 0xFFA0), (0x16FE4, 0x16FE4), (0x1D159, 0x1D159), (0xE0100, 0xE01EF))


def _escaped(text: str) -> str:
    """A text as a listing prints it: a character that draws a glyph (a letter, mark, digit, punctuation or symbol, none
    of the blanks above), a plain space or a line break as it is; every other one as its code (the third round)."""
    return "".join(c if c in " \n" or unicodedata.category(c)[0] in "LMNPS" and not any(low <= ord(c) <= high for low, high in INVISIBLE)
                   else f"\\u{ord(c):04x}" if ord(c) <= 0xFFFF else f"\\U{ord(c):08x}" for c in text)


def _shown(text: str) -> str:
    """A text as a listing shows it: quoted as JSON, each control, format (zero-width, direction) or line-separator
    character written as its code, so nothing in it hides or moves what is around it."""
    return _escaped(json.dumps(text, ensure_ascii=False))


def _entry_problem(entry) -> str:
    keys = set(entry) if isinstance(entry, dict) else set()
    if keys == {"tool", "input"} and isinstance(entry["tool"], str) and entry["tool"] and isinstance(entry["input"], dict):
        from synthesis import guards
        tool = entry["tool"]
        return ("names a tool whose name holds more than letters, digits and _ . : - (the listing prints a name as it is)"
                if not re.fullmatch(r"[A-Za-z0-9_.:-]+", tool, re.ASCII) else
                f"names {tool}, whose sends a batch binds as a browser entry or not at all" if guards.desktop_tool(tool)
                or guards.shell_tool(tool) or tool in guards.FILE_TOOLS else
                f"names {tool}, the messages sender's: its sends take the messages kinds, which no photo goes with"
                if tool in ("imessage_send", "messages_send") else "")
    if keys not in ({"channel", "to", "text"}, {"channel", "members", "service", "chat", "text"}) or not (
            isinstance(entry["text"], str) and entry["text"].strip() and isinstance(entry["channel"], str)):
        return f"is {KINDS}"
    if "members" in keys:  # the chat messages_send.py reaches by --members, as its own approval names it
        members = entry["members"]
        return "" if (entry["channel"] == "messages" and isinstance(members, list) and members
                      and all(isinstance(m, str) and HANDLE.fullmatch(m) for m in members) and len(set(members)) == len(members)
                      and entry["service"] in ("iMessage", "SMS") and isinstance(entry["chat"], str) and entry["chat"].strip()) else (
            "names a chat by --members: each member's handle once, its service (iMessage or SMS) and its chat id")
    if entry["channel"] == "messages":
        return "" if isinstance(entry["to"], str) and HANDLE.fullmatch(entry["to"]) else (
            "names no handle --to takes: +<country code><number> or an address")
    return "" if isinstance(entry["to"], str) and conversation(entry["to"]) == (entry["channel"], entry["to"]) else (
        "names no conversation in the one form the guard compares, for its channel: facebook.com/messages/t/<id>, "
        "facebook.com/messages/e2ee/t/<id>, messenger.com/t/<id> or messenger.com/e2ee/t/<id>, channel messenger")


def batch_digest(batch: dict) -> str:
    """SHA-256 of the batch's canonical JSON: every field, in a form its layout in the file does not change."""
    return hashlib.sha256(json.dumps(batch, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def batch_refusal(batch: dict, file: str) -> str:
    from synthesis import approvals
    digest, count = batch_digest(batch), len(batch["entries"])
    code = approvals.request("send-batch", digest, f"open batch {_shown(batch['batch'])}: {count} sends, digest {digest[:12]}, "
                             f"project {_shown(batch['project'])}")
    _requests_file().parent.mkdir(parents=True, exist_ok=True)
    with _requests_file().open("a", encoding="utf-8") as handle:  # what ties this code to this digest at each spend
        handle.write(json.dumps({"digest": digest, "code": code, "at": time.time()}) + "\n")
    return (f"Opening batch {digest[:12]} ({count} send{'s' if count != 1 else ''} from {_shown(file)}) lets each entry below go once, "
            f"exactly as written, within {MAX_HOURS} hours, from this session alone. Show the principal this whole list as it "
            f"stands (each text quoted, every hidden character as its code) and ask them to type {approvals.how(code)} to open "
            f"exactly it. Then run the identical command again." + (
                " Each Messenger entry then goes as one browser_batch on a tab that already shows its conversation: a navigate "
                "to the conversation's address on that tab, its words typed there (shift+Return for a line break), and last the "
                "page script `synthesis sends script --entry <digest prefix>:<its number>` prints, which sends only those words; "
                "a Return or a click there waits for its own code."
                if any(e.get("channel") == "messenger" for e in batch["entries"]) else "") + f"\n{batch_listing(batch, show=True)}")


def batch_listing(batch: dict, show: bool = False) -> str:
    """What the principal approves: the digest, the count and each entry's channel and recipient; with `show` (and in
    the hold), each entry's text in full, quoted with every hidden character as its code (a connector call's whole input)."""
    lines = [f"Batch {_shown(batch['batch'])} for project {_shown(batch['project'])}: {len(batch['entries'])} sends, digest "
             f"{batch_digest(batch)}"]
    for n, e in enumerate(batch["entries"], 1):
        if "tool" in e:
            to = ", ".join(f"{k} {_shown(e['input'][k])}" for k in ADDRESS_KEYS if k in e["input"]) or "recipients in its input"
            lines += [f"{n:>3}. {channel(e['tool'], e['input'])} by {e['tool']}: {to}"]
        else:
            lines += [f"{n:>3}. {e['channel']} " + (f"by {e['service']} to chat {_shown(e['chat'])}, members "
                                                    f"{', '.join(map(_shown, e['members']))}" if "members" in e else f"to {_shown(e['to'])}")]
        shown = _escaped(json.dumps(e["input"], ensure_ascii=False, indent=2, sort_keys=True)) if "tool" in e else _shown(e["text"])
        lines += ["\n".join("       " + line for line in shown.split("\n"))] if show else []
    return "\n".join(lines)


def _batch_file(digest: str):
    return paths.state() / "sends" / "batches" / f"{digest}.json"


def _whole(data: dict, file) -> bool:
    """Batch state as its grant wrote it: its digest is its file's name and the hash of the batch it holds, its spent
    marks name its own entries, and it lasts at most 12 hours from its grant. Anything else (edited, extended, another
    shape, unreadable) is no batch, and its sends fall back to the code per call."""
    try:
        batch = checked({k: data[k] for k in ("batch", "project", "entries")})
        return (batch_digest(batch) == data["digest"] == file.stem and isinstance(data["spent"], dict)
                and set(data["spent"]) <= {str(i) for i in range(len(batch["entries"]))}
                and all(isinstance(data[k], str) and data[k] for k in ("session", "code"))
                and float(data["asked"]) <= float(data["granted"]) and 0 <= float(data["until"]) - float(data["granted"]) <= MAX_HOURS * 3600)
    except (KeyError, TypeError, ValueError):
        return False


def batches() -> list:
    """The open batches: whole, granted, and neither past their 12 hours nor closed."""
    found = []
    for file in sorted(_batch_file("").parent.glob("*.json")):
        data = paths.read_json(file)
        if _whole(data, file) and float(data["granted"]) <= time.time() < float(data["until"]):
            found.append(data)
    return found


def open_batch(batch: dict, grant: dict, session_id: str) -> dict:
    """Copy a batch the principal granted into the synthesis state, so its file no longer matters: its entries, digest
    and project, the grant's time, the session that ran the granted command and the code the principal typed in it
    (each spend finds them in that session's record again), and each entry's spent mark. A batch granted again keeps
    what it already sent; one whose earlier state cannot be read is refused, since which of its entries went cannot be told."""
    from synthesis import approvals
    digest, now = batch_digest(checked(batch)), time.time()
    file = _batch_file(digest)
    with approvals.alone():
        earlier = paths.read_json(file) if file.exists() else {"spent": {}}
        if file.exists() and not _whole(earlier, file):
            raise ValueError(f"an earlier grant of batch {digest[:12]} left state that cannot be read ({file}), so which of "
                             "its entries went cannot be told: it is not opened again")
        data = {**batch, "digest": digest, "granted": now, "until": now + MAX_HOURS * 3600, "spent": earlier["spent"],
                "session": session_id, "code": str(grant.get("code") or ""), "asked": float(grant.get("asked") or now)}
        paths.write_json(file, data)
        for old in file.parent.glob("*.json"):  # bounded: a batch's record outlives its 12 hours by a month
            if old != file and now - old.stat().st_mtime > 30 * 86400:
                old.unlink()
    return data


def close_batches() -> int:
    """End every open batch now: the principal's stop. What each sent stays recorded, for a grant of it again."""
    from synthesis import approvals
    with approvals.alone():
        ended = batches()
        for data in ended:
            paths.write_json(_batch_file(data["digest"]), {**data, "until": time.time()})
    return len(ended)


def describe_batch(data: dict) -> str:
    done = {int(i) for i in data["spent"]} | {i for d, i in _spends() if d == data["digest"]}  # the ledger's spends count too
    return (f"Batch {data['digest'][:12]} ({_shown(data['batch'])}, project {_shown(data['project'])}) open until "
            f"{time.strftime('%H:%M', time.localtime(data['until']))}: {len(data['entries']) - len(done)} of "
            f"{len(data['entries'])} entries left, each sent once as written; `synthesis sends close` ends it sooner.")


def batch_spend(match, session: dict | None = None, spend: bool = True) -> str:
    """The first unspent entry `match` accepts, of an open batch this session's granted command opened, as the ledger
    names it (batch:<digest prefix>:<index>), marked spent unless `spend` is false; "" for none. Each time, the session's
    own record must show the principal typing the batch's code (state alone is never a grant), and an entry the spends
    ledger holds is spent whatever its state says (the review of 5.23.0). The caller holds approvals.alone()."""
    me, ledger = str((session or {}).get("session_id") or ""), None  # the session the guard is told, never the environment's
    for data in batches() if me else []:
        for i, entry in enumerate(data["entries"] if data["session"] == me else []):
            if str(i) in data["spent"] or not match(entry):
                continue
            ledger = _spends() if ledger is None else ledger
            if (data["digest"], i) in ledger or not _backed(data, session):
                continue
            if spend:
                with _spends_file().open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"digest": data["digest"], "entry": i, "at": time.time(), "session": me}) + "\n")
                data["spent"][str(i)] = {"at": time.time(), "session": me}
                paths.write_json(_batch_file(data["digest"]), data)
            return f"batch:{data['digest'][:12]}:{i}"
    return ""


def _spends_file():
    return paths.state() / "sends" / "batch-spends.jsonl"


def _spends() -> set:
    """(digest, entry) of every batch send there has been: the append-only ledger each state's spent marks yield to."""
    found = set()
    for line in _spends_file().read_text(encoding="utf-8").splitlines() if _spends_file().is_file() else []:
        try:
            row = json.loads(line)
            found.add((str(row["digest"]), int(row["entry"])))
        except (ValueError, KeyError, TypeError):
            continue
    return found


def _requests_file():
    return paths.state() / "sends" / "batch-requests.jsonl"


# The messages sender's session (the third round, #5): it named its own (`--session`), and a link or runpy kept another
# session's name. Now a command the guard lets run `messages_send.py` files a ticket for the session its hook names, and
# the sender's own guard call takes the one ticket filed in the last minute; a run the guard did not see finds none.
TICKET_SECONDS = 60


def _ticket_file(session_id: str):
    return paths.state() / "sends" / "sender" / f"{session_id}.json"


def sender_ticket(session_id: str) -> None:
    if re.fullmatch(r"[\w.-]+", session_id or ""):
        paths.write_json(_ticket_file(session_id), {"at": time.time()})


def ticket() -> dict | None:
    """The session of the one ticket filed in the last minute, taken; None for none, or for more than one. The caller
    holds approvals.alone(); stale tickets go as they are passed."""
    fresh = []
    for file in _ticket_file("x").parent.glob("*.json"):
        if time.time() - float(paths.read_json(file).get("at") or 0) <= TICKET_SECONDS:
            fresh.append(file)
        else:
            file.unlink(missing_ok=True)
    if len(fresh) != 1:
        return None
    fresh[0].unlink(missing_ok=True)
    return {"session_id": fresh[0].stem}


def _backed(data: dict, session: dict | None) -> bool:
    """Whether the principal typed this batch's code in the granting session's own record, after the guard first filed
    that code for this batch's digest (the request it recorded), within its last 12 hours. A code typed for anything else
    backs nothing (the review of 5.24.0), and no line of the record stands in for the request: the agent writes those
    (its third round: its own sentence naming the digest and a code tied them; repeating both held a granted batch)."""
    from synthesis import approvals
    filed = []
    for line in _requests_file().read_text(encoding="utf-8").splitlines() if _requests_file().is_file() else []:
        try:
            row = json.loads(line)
            filed += [float(row["at"])] if (row["digest"], row["code"]) == (data["digest"], data["code"]) else []
        except (ValueError, KeyError, TypeError):
            continue
    try:
        record = approvals.transcript(session)
        return bool(filed and record) and approvals.typed(record, data["code"], max(min(filed), float(data["asked"]),
                                                                                    time.time() - MAX_HOURS * 3600), data["session"])
    except OSError:
        return False


def _plain(value):
    """A value with each string's line endings written one way: the one difference an entry overlooks."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value.replace("\r\n", "\n").replace("\r", "\n") if isinstance(value, str) else value


def _same(one, other) -> bool:
    """Equal as JSON after _plain: true is not 1, and 1 is not 1.0."""
    return json.dumps(_plain(one), sort_keys=True, ensure_ascii=False) == json.dumps(_plain(other), sort_keys=True, ensure_ascii=False)


def call_entry(entry: dict, tool: str, tool_input: dict) -> bool:
    """Whether a call is exactly this entry: a connector call by its tool and whole input; the messages sender's
    (messages_send.py asks the guard itself) as its own approval names it, `--to` (imessage_send) by the handle and text,
    `--members` (messages_send) by the sorted members, service, text and chat; a photo beside them is no entry's."""
    if "tool" in entry:
        return entry["tool"] == tool and _same(entry["input"], tool_input)
    wanted = ({"to": entry["to"], "text": entry["text"]} if "to" in entry else
              {"to": sorted(entry["members"]), "service": entry["service"], "text": entry["text"], "chat": entry["chat"]})
    return entry["channel"] == "messages" and tool == ("imessage_send" if "to" in entry else "messages_send") and _same(wanted, tool_input)


def send_script(entry: dict) -> str:
    """The page script that sends a Messenger entry: the shipped send script, holding the entry's conversation and the
    SHA-256 of its words (each line ending written as \\n), as `synthesis sends script` prints it and the guard compares it."""
    digest = hashlib.sha256(_plain(entry["text"]).encode("utf-8")).hexdigest()
    return SEND_SCRIPT.replace("__WANT__", json.dumps({"to": entry["to"], "digest": digest}))


# --- the ledger ---------------------------------------------------------------------------------


def log(chan: str, tool: str, summary: str, how: str, session: dict | None = None) -> None:
    """One line per send the guard let through, for the daily plan's "On your behalf"."""
    entry = {"at": time.time(), "channel": chan, "tool": tool, "summary": summary[:200], "how": how,
             "session": paths.session_id(session) if session else os.environ.get("SYNTHESIS_SESSION", "")}
    target = paths.state() / "sends" / f"{time.strftime('%Y-%m-%d')}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def ledger(day: str) -> list:
    target = paths.state() / "sends" / f"{day}.jsonl"
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line] if target.is_file() else []
