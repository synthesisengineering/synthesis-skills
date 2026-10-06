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
WRAPPERS = {"env", "command", "exec", "time", "nohup", "sudo", "nice", "{", "!"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}

# --- sends (R3.1) -------------------------------------------------------------------------------


def is_send_tool(tool: str, config: dict) -> bool:
    patterns = DEFAULT_SEND_TOOLS + list(config.get("send_tools", []))
    return any(fnmatch.fnmatchcase(tool, p) for p in patterns)


def check_send(tool: str, tool_input: dict, config: dict) -> str | None:
    text = " ".join(str(v) for v in tool_input.values() if isinstance(v, str))
    for rule in config.get("forbidden_phrases", []):
        # Case-insensitive unless the rule says otherwise: a rule against a miscased brand
        # must not block the correctly cased one (2026-08-03).
        if re.search(rule["pattern"], text, 0 if rule.get("case_sensitive") else re.IGNORECASE):
            return f"message breaks the rule '{rule.get('name', rule['pattern'])}': {rule.get('why', 'see your voice rules')}"
    subject = {"tool": tool, "input": tool_input}
    if approvals.consume("send", subject):
        return None
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


# --- shell parsing ------------------------------------------------------------------------------


def _bare(words: list[str]) -> list[str]:
    """The command itself, without subshell parentheses, variable assignments or wrappers like env."""
    if words and words[0].startswith("("):
        words = [words[0].lstrip("(")] + words[1:]
    while words and (words[0] in WRAPPERS or not words[0] or re.match(r"[A-Za-z_]\w*=", words[0])):
        words = words[1:]
    if words and words[-1].endswith(")"):
        words = words[:-1] + [words[-1].rstrip(")")]
    return [w for w in words if w]


HEREDOC = re.compile(r"(?<!<)<<-?[ \t]*(['\"]?)([A-Za-z_][\w.-]*)\1([^\n]*)\n.*?(?:\n[ \t]*\2[ \t]*(?=\n|$)|$)", re.S)
SHELLS = ("sh", "bash", "zsh")


def _without_heredocs(command: str) -> str:
    """The command with heredoc bodies removed: a file being written is not a command being run.
    A heredoc fed to a shell is kept, because the shell runs it."""
    def drop(m):
        line = command[command.rfind("\n", 0, m.start()) + 1:m.start()] + " " + m.group(3)
        runs = any(os.path.basename(w) in SHELLS for w in re.split(r"[\s|;&()]+", line))
        return m.group(0) if runs else f"<<{m.group(2)}{m.group(3)}"
    return HEREDOC.sub(drop, command) if "<<" in command else command


def _segments(command: str) -> list:
    """Simple commands as word lists, with "(" and ")" marking subshells. Quotes are respected,
    so `bash -c 'cd x && y'` keeps its script whole; redirections and their targets are dropped."""
    command = _without_heredocs(command)
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
        lex.whitespace, lex.whitespace_split, lex.commenters = " \t\r", True, ""
        tokens = list(lex)
    except ValueError:  # unbalanced quotes: fall back to a plain split, which still sees every command
        return [part.split() for part in SEPARATORS.split(command)]
    segments, words, skip = [], [], False
    for token in tokens:
        if skip:
            skip = False
        elif token and set(token) <= set("<>&|") and set(token) & set("<>"):
            skip = True  # a redirection: the next token is its file
        elif token and set(token) <= set(";&|()\n"):
            segments.append(words)
            segments += [c for c in token if c in "()"]
            words = []
        else:
            words.append(token)
    return segments + [words]


def _commands(command: str, cwd: str) -> list[tuple[list[str], str]]:
    """Each simple command with the directory it runs in, following `cd`, subshells and wrapper shells."""
    found, outer = [], []
    for item in _segments(command):
        if item in ("(", ")"):
            if item == "(":
                outer.append(cwd)
            elif outer:
                cwd = outer.pop()  # a subshell's cd ends with it
            continue
        words = _bare(item)
        if not words:
            continue
        found.append((words, cwd))
        if words[0] in ("cd", "pushd") and (len(words) == 1 or words[1] != "-"):
            cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(os.path.expandvars(words[1] if len(words) > 1 else "~"))))
        if os.path.basename(words[0]) in SHELLS and len(words) > 2:
            flag = next((i for i, w in enumerate(words[1:], 1) if w.startswith("-") and "c" in w), None)
            if flag is not None and flag + 1 < len(words):
                found += _commands(words[flag + 1], cwd)  # the script a wrapper shell runs
    return found


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


def _targets(command: str, config: dict, cwd: str) -> list[tuple[str, str | None]]:
    """(directory, rev) for each deploy in the command. A push deploys HEAD; a build deploys the tree."""
    patterns = DEFAULT_DEPLOY_PATTERNS + list(config.get("deploy_patterns", []))
    commands = _commands(command, cwd)
    targets: list[tuple[str, str | None]] = []
    if any(re.search(p, _without_heredocs(command)) for p in patterns):
        targets = [(d, None) for words, d in commands if os.path.basename(words[0]) not in SHELLS
                   and any(re.search(p, " ".join(words)) for p in patterns)]
        targets = targets or [(cwd, None)]
    repos = None
    for words, directory in commands:
        sub, where = _git(words, directory)
        if sub != "push":
            continue
        if repos is None:
            repos = [os.path.realpath(os.path.expanduser(r)) for r in config.get("push_deploys", [])]
        real, main = os.path.realpath(where), _checkout(where)[1]
        if any(_inside(p, r) for r in repos for p in (real, main) if p):
            targets.append((real, "HEAD"))
    return list(dict.fromkeys(targets))


def _last_deploy(identity: str):
    import hashlib
    return paths.state() / "deploys" / (hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16] + ".json")


def check_deploy(command: str, config: dict, cwd: str | None = None) -> str | None:
    cwd = cwd or os.getcwd()
    targets = _targets(command, config, cwd)
    if not targets:
        return None
    heads, identities, recent = {}, [], []
    for directory, rev in targets:
        root, main = _checkout(directory)
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
    return ("This publishes to production. Show the principal this exact command and ask them to reply "
            f"\"approve {code}\". Then run the identical command again.")


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
    for words, directory in _commands(command, cwd or os.getcwd()):
        if words[0] == "rm" and any(w.startswith("-") and "r" in w.lstrip("-").lower() for w in words[1:]):
            protected = protected if protected is not None else _protected(config)
            for target in (w for w in words[1:] if not w.startswith("-")):
                real = os.path.realpath(os.path.join(directory, os.path.expanduser(os.path.expandvars(target))))
                if real in protected or os.path.exists(os.path.join(real, ".git")):
                    return f"refusing a recursive delete of {real}: it is a protected root or a repository"
        sub, _ = _git(words, directory)
        if sub == "push" and any(w in ("-f", "--force") for w in words):
            if any(w.split(":")[-1] in ("main", "master") for w in words[words.index("push") + 1:]):
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
