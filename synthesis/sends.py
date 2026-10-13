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
CHANNELS = [("slack", "slack"), ("jira", "jira"), ("confluence", "confluence"), ("github", "github"),
            ("bitbucket", "bitbucket"), ("notion", "notion"), ("gmail", "email"), ("mail", "email"),
            ("event", "calendar"), ("calendar", "calendar"), ("document_comment", "docs"),
            ("spreadsheet_comment", "docs"), ("presentation_comment", "docs"), ("drive", "docs")]
# (channel, pattern over the command's words) for programs that post; `curl` and its kin are judged by method and host
COMMANDS = [
    ("github", r"gh (?:pr|issue) (?:comment|create|edit|review)\b|gh (?:pr|issue) close\b.*(?:\s-c\b|\s--comment\b)"),
    ("bitbucket", r"bkt pr (?:comment|create|edit|approve|decline|reopen|request-changes)\b"),
    ("gitlab", r"glab (?:mr|issue) (?:note|comment|create|update)\b"),
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
    if head in WEB:
        return "web" if _web_write(words) else None
    if head in API and words[1:2] == ["api"]:
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


def opens_window(words: list) -> bool:
    """`synthesis sends open`, however the CLI is spelled (its stable path, `python3 -m synthesis.cli`, the file)."""
    for i, w in enumerate(words):
        if (os.path.basename(w) == "synthesis" or w in ("synthesis.cli", "synthesis/cli.py") or w.endswith("synthesis/cli.py")) \
                and words[i + 1:i + 3] == ["sends", "open"]:
            return True
    return False


def attached(words: list, cwd: str) -> tuple[str, str]:
    """(text, problem) of the files a posting command sends as its body (--body-file, gh's -F, --input, @file)."""
    flags = {"--body-file", "--input"} | ({"-F"} if os.path.basename(words[0]) == "gh" and words[1:2] in (["pr"], ["issue"]) else set())
    names = [words[i + 1] for i, w in enumerate(words[:-1]) if w in flags]
    names += [w.split("@", 1)[1] for w in words if re.match(r"(?:[\w.-]+=)?@[^@\s]+$", w)]
    texts = []
    for name in names:
        path = os.path.join(cwd, os.path.expanduser(name))
        if name == "-" or not os.path.isfile(path):
            return "", f"its body comes from {name}, which the guard cannot read to check"
        with open(path, encoding="utf-8", errors="replace") as handle:
            texts.append(handle.read(1_048_576))
    return "\n\n".join(texts), ""


# --- the window ---------------------------------------------------------------------------------


def _window_file():
    return paths.state() / "sends" / "window.json"


def window() -> dict:
    """The open window, or {}: one that has run out is closed."""
    data = paths.read_json(_window_file())
    return data if data and float(data.get("until", 0)) > time.time() else {}


def open_window(hours: float, channels: list, project: str = "") -> dict:
    if not 0 < hours <= MAX_HOURS:
        raise ValueError(f"a send window lasts more than 0 and at most {MAX_HOURS} hours")
    if not channels:
        raise ValueError("name the channels it covers (for example slack,jira,bitbucket), or all")
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
