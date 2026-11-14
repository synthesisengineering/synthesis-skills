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


def _cli_words(words: list, action: str) -> list | None:
    """The words after the synthesis CLI when they run `sends <action>`, however the CLI is spelled and wherever its
    options sit (`synthesis --session S sends open` opened one with no code on 2026-10-13); None for help or another command."""
    for i, w in enumerate(words):
        if os.path.basename(w) == "synthesis" or w in ("synthesis.cli", "synthesis/cli.py") or w.endswith("synthesis/cli.py"):
            rest = words[i + 1:]
            if "sends" in rest and action in rest[rest.index("sends") + 1:] and not {"-h", "--help"} & set(rest):
                return rest
    return None


def window_asked(words: list) -> dict | None:
    """The window `synthesis sends open` asks for; None for help or another command."""
    rest = _cli_words(words, "open")
    if rest is None:
        return None
    given = {}
    for j, token in enumerate(rest):
        key, eq, value = token.partition("=")
        if key in ("--hours", "--channels", "--project", "--sends"):
            given[key[2:]] = value if eq else (rest[j + 1] if j + 1 < len(rest) else "")
    return asked(given.get("hours", 0), given.get("channels", ""), given.get("project", ""), given.get("sends", 0))


VALUED = ("--hours", "--channels", "--project", "--sends", "--date", "--session")  # the options of `sends` that take a value


def batch_asked(words: list, cwd: str) -> str | None:
    """The file `synthesis sends batch <file>` opens a batch from, as a path from cwd ("" when it names none); None for
    `--show`, which only prints, for help and for another command."""
    rest = _cli_words(words, "batch")
    if rest is None or "--show" in rest:
        return None
    after = rest[rest.index("batch", rest.index("sends") + 1) + 1:]
    named = [w for i, w in enumerate(after) if not w.startswith("-") and (i == 0 or after[i - 1] not in VALUED)]
    return os.path.join(cwd, os.path.expanduser(named[0])) if named else ""


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
KINDS = ('none of the three kinds: a connector call {"tool", "input"}, a browser send {"channel", "to", "text"} or a '
         'messages send {"channel": "messages", "to", "text"}, each with nothing else')
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
        raise ValueError(f"{file} is no batch: {exc}") from None


def checked(batch) -> dict:
    """The batch itself when it has the one shape a batch takes; else ValueError, naming what is wrong."""
    if not isinstance(batch, dict) or set(batch) != {"batch", "project", "entries"}:
        raise ValueError('a batch is {"batch": <name>, "project": <project>, "entries": [...]}, with nothing else')
    if not all(isinstance(batch[k], str) and batch[k].strip() for k in ("batch", "project")):
        raise ValueError("a batch names itself and the project whose sessions send it")
    entries = batch["entries"]
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_SENDS:
        raise ValueError(f"a batch holds 1 to {MAX_SENDS} entries")
    for n, entry in enumerate(entries, 1):
        problem = _entry_problem(entry)
        if problem or entries.index(entry) < n - 1:
            raise ValueError(f"entry {n} {problem or f'repeats entry {entries.index(entry) + 1}'}")
    return batch


def _entry_problem(entry) -> str:
    keys = set(entry) if isinstance(entry, dict) else set()
    if keys == {"tool", "input"} and isinstance(entry["tool"], str) and entry["tool"] and isinstance(entry["input"], dict):
        from synthesis import guards
        tool = entry["tool"]
        return (f"names {tool}, whose sends a batch binds as a browser entry or not at all" if guards.desktop_tool(tool)
                or guards.shell_tool(tool) or tool in guards.FILE_TOOLS else "")
    if keys != {"channel", "to", "text"} or not all(isinstance(entry[k], str) and entry[k].strip() for k in keys):
        return f"is {KINDS}"
    if entry["channel"] == "messages":
        return "" if all(HANDLE.fullmatch(h.strip()) for h in entry["to"].split(",")) else (
            "names no handle messages_send.py takes: +<country code><number> or an address, or for --members several, "
            "comma-separated")
    found = conversation(entry["to"])
    return "" if found and found[0] == entry["channel"] else (
        "names no conversation the guard can place on its page, for its channel: a Messenger chat's address "
        "(facebook.com/messages/t/<id> or /messages/e2ee/t/<id>, messenger.com/t/<id> or /e2ee/t/<id>), channel messenger")


def batch_digest(batch: dict) -> str:
    """SHA-256 of the batch's canonical JSON: every field, in a form its layout in the file does not change."""
    return hashlib.sha256(json.dumps(batch, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def batch_refusal(batch: dict, file: str) -> str:
    from synthesis import approvals
    digest, count = batch_digest(batch), len(batch["entries"])
    code = approvals.request("send-batch", digest, f"open batch {batch['batch']}: {count} sends, digest {digest[:12]}, "
                             f"project {batch['project']}")
    return (f"Opening batch {digest[:12]} ({count} send{'s' if count != 1 else ''} from {file}, project {batch['project']}) "
            f"lets each entry go once, exactly as written, within {MAX_HOURS} hours. Show the principal every entry in full "
            f"(`synthesis sends batch {file} --show`, or the packet built from the same file, with digest {digest[:12]}) and "
            f"ask them to type {approvals.how(code)}. Then run the identical command again.")


def batch_listing(batch: dict, show: bool = False) -> str:
    """What the principal approves: the digest, the count and each entry's channel and recipient; with `show`, each
    entry's text in full (a connector call's whole input), to read before the code is typed."""
    lines = [f"Batch {batch['batch']} for project {batch['project']}: {len(batch['entries'])} sends, digest {batch_digest(batch)}"]
    for n, e in enumerate(batch["entries"], 1):
        if "tool" in e:
            to = ", ".join(f"{k} {e['input'][k]}" for k in ADDRESS_KEYS if k in e["input"]) or "recipients in its input"
            lines += [f"{n:>3}. {channel(e['tool'], e['input'])} by {e['tool']}: {to}"]
        else:
            lines += [f"{n:>3}. {e['channel']} to {e['to']}"]
        shown = json.dumps(e["input"], ensure_ascii=False, indent=2) if "tool" in e else e["text"]
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
                and 0 <= float(data["until"]) - float(data["granted"]) <= MAX_HOURS * 3600)
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


def open_batch(batch: dict) -> dict:
    """Copy a granted batch into the synthesis state with its digest, project, the grant's time and each entry's spent
    mark, so its file no longer matters. A batch granted again keeps what it already sent; one whose earlier state
    cannot be read is refused, since which of its entries went can no longer be told."""
    from synthesis import approvals
    digest, now = batch_digest(checked(batch)), time.time()
    file = _batch_file(digest)
    with approvals.alone():
        earlier = paths.read_json(file) if file.exists() else {"spent": {}}
        if file.exists() and not _whole(earlier, file):
            raise ValueError(f"an earlier grant of batch {digest[:12]} left state that cannot be read ({file}), so which of "
                             "its entries went cannot be told: it is not opened again")
        data = {**batch, "digest": digest, "granted": now, "until": now + MAX_HOURS * 3600, "spent": earlier["spent"]}
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
    return (f"Batch {data['digest'][:12]} ({data['batch']}, project {data['project']}) open until "
            f"{time.strftime('%H:%M', time.localtime(data['until']))}: {len(data['entries']) - len(data['spent'])} of "
            f"{len(data['entries'])} entries left, each sent once as written; `synthesis sends close` ends it sooner.")


def batch_spend(match, project: str, session: dict | None = None, spend: bool = True) -> str:
    """The first unspent entry `match` accepts in an open batch of this project, as the ledger names it
    (batch:<digest prefix>:<index>), marked spent unless `spend` is false; "" for none. The caller holds
    approvals.alone(), so two sessions never spend one entry."""
    for data in batches() if project else []:
        for i, entry in enumerate(data["entries"] if data["project"] == project else []):
            if str(i) not in data["spent"] and match(entry):
                if spend:
                    data["spent"][str(i)] = {"at": time.time(), "session": paths.session_id(session)}
                    paths.write_json(_batch_file(data["digest"]), data)
                return f"batch:{data['digest'][:12]}:{i}"
    return ""


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
    (messages_send.py asks the guard itself) by the handle `--to` names (imessage_send) or the members `--members` names
    (messages_send), and its text, with no photo."""
    if "tool" in entry:
        return entry["tool"] == tool and _same(entry["input"], tool_input)
    named = [h.strip() for h in entry["to"].split(",")]
    to = named[0] if tool == "imessage_send" and len(named) == 1 else sorted(set(named)) if len(named) > 1 else None
    shape = {"imessage_send": {"to", "text"}, "messages_send": {"to", "service", "text", "chat"}}.get(tool)
    return (entry["channel"] == "messages" and set(tool_input) == shape and to is not None and _same(tool_input["to"], to)
            and _same(tool_input["text"], entry["text"]))


def browser_entry(entry: dict, chan: str, where: str, text: str) -> bool:
    """Whether a browser call that types `text` and sends it on the page of conversation (chan, where) is this entry."""
    return "to" in entry and conversation(entry["to"]) == (chan, where) and _plain(entry["text"]) == text


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
