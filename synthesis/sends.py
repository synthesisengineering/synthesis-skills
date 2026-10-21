"""Outgoing messages in every channel (Rajiv, 2026-10-13): "Shouldn't it apply to all communications sent
for me / on my behalf, regardless of communications channel?" A call is a send by what it does, not by a
list of tool names: a connector tool whose name delivers words, or a shell command that posts. The send
window lets signed Ragbot sends go without a per-message code for a while, and the ledger lists the day's
sends for the daily plan's "On your behalf"."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import time
import urllib.parse

from synthesis import paths

MAX_HOURS = 12  # Rajiv's ruling, 2026-10-13
READS = {"get", "list", "read", "search", "fetch", "query", "find", "lookup", "inspect", "describe", "view", "show",
         "download", "export", "check", "count", "preview", "resolve", "debug"}
SAYS = {"send", "reply", "forward", "comment", "post", "publish", "share", "invite", "respond", "mention", "schedule",
        "submit", "draft", "announce", "notify", "remind"}
WRITES = {"create", "add", "edit", "update", "manage", "set", "put", "patch", "upsert", "write"}
SAID = {"comment", "message", "issue", "page", "post", "reply", "review", "draft", "event", "invite", "email", "mail",
        "reaction", "canvas", "envelope", "request", "ticket", "thread", "announcement", "story", "access", "permission"}
PREPOSITIONS = {"to", "on", "in", "for", "from", "with", "by", "of", "into", "as", "at"}
NOT_PEOPLE = ["mcp__ccd_*", "mcp__*__*session*"]  # agents talking to agents
ALSO_SENDS = ["mcp__*execute_zapier_write_action*", "mcp__*manage_out_of_office*"]
CHANNELS = [("imessage", "messages"), ("messages_send", "messages"), ("slack", "slack"), ("jira", "jira"), ("confluence", "confluence"), ("github", "github"),
            ("bitbucket", "bitbucket"), ("notion", "notion"), ("gmail", "email"), ("mail", "email"),
            ("event", "calendar"), ("calendar", "calendar"), ("document_comment", "docs"),
            ("spreadsheet_comment", "docs"), ("presentation_comment", "docs"), ("drive", "docs")]
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
    if any(fnmatch.fnmatchcase(tool, p) for p in ALSO_SENDS):
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


def window_asked(words: list) -> dict | None:
    """The window `synthesis sends open` asks for, however the CLI is spelled and wherever its options sit
    (`synthesis --session S sends open` opened one with no code on 2026-10-13); None for help or another command."""
    for i, w in enumerate(words):
        if os.path.basename(w) == "synthesis" or w in ("synthesis.cli", "synthesis/cli.py") or w.endswith("synthesis/cli.py"):
            rest = words[i + 1:]
            if "sends" in rest and "open" in rest[rest.index("sends") + 1:] and not {"-h", "--help"} & set(rest):
                given = {}
                for j, token in enumerate(rest):
                    key, eq, value = token.partition("=")
                    if key in ("--hours", "--channels", "--project"):
                        given[key[2:]] = value if eq else (rest[j + 1] if j + 1 < len(rest) else "")
                return asked(given.get("hours", 0), given.get("channels", ""), given.get("project", ""))
    return None


def window_refusal(window: dict) -> str:
    from synthesis import approvals
    scope = f"{window['hours']:g} h, {', '.join(window['channels']) or 'no channels'}" + (
        f", project {window['project']}" if window["project"] else "")
    code = approvals.request("send-window", window, f"open a send window: {scope}")
    return (f"Opening a send window ({scope}) lets signed Ragbot sends go without a per-message code until it ends. "
            f"Show the principal that scope and ask them to type {approvals.how(code)}. Then run the identical command again.")


def asked(hours, channels: str, project: str) -> dict:
    """A window request in one form, so the guard and the command bind the same approval."""
    try:
        hours = float(hours)
    except ValueError:
        hours = 0.0
    return {"hours": hours, "channels": sorted({c.strip() for c in str(channels).split(",") if c.strip()}),
            "project": str(project)}


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


def check_window(hours: float, channels: list) -> None:
    if not 0 < hours <= MAX_HOURS:
        raise ValueError(f"a send window lasts more than 0 and at most {MAX_HOURS} hours")
    if not channels:
        raise ValueError("name the channels it covers (for example slack,jira,bitbucket), or all")


def open_window(hours: float, channels: list, project: str = "") -> dict:
    check_window(hours, channels)
    data = {"opened": time.time(), "until": time.time() + hours * 3600, "channels": sorted(set(channels)),
            "project": project}
    paths.write_json(_window_file(), data)
    return data


def close_window() -> bool:
    try:
        _window_file().unlink()
        return True
    except FileNotFoundError:
        return False


def covered(chan: str, texts: list, project: str, config: dict) -> str:
    """Why the open window covers this send, or "" when it does not."""
    w = window()
    marks = [m for m in config.get("send_window_signatures", []) if any(re.search(m, t) for t in texts)]
    if w and ("all" in w["channels"] or chan in w["channels"]) and (not w.get("project") or w["project"] == project) and marks:
        return f"the send window open until {time.strftime('%H:%M', time.localtime(w['until']))}"
    return ""


def describe(w: dict) -> str:
    scope = ", ".join(w["channels"]) + (f"; project {w['project']}" if w.get("project") else "")
    return (f"Send window open until {time.strftime('%H:%M', time.localtime(w['until']))} ({scope}): signed Ragbot sends "
            "go without a per-message code and are logged. `synthesis sends close` ends it.")


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
