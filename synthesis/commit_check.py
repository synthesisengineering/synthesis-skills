"""Git commit check (R2.1, R3.3): secrets, unapproved disclosures, other sessions' claims.

Runs as the global pre-commit, pre-merge-commit and commit-msg hook (core.hooksPath; the
installed wrapper passes the hook's name in SYNTHESIS_GIT_HOOK). Credentials, private keys
(a key header followed by key body lines) and credential file names block in every
repository. The principal's commit policy, the YAML file named by `commit_policy` in
config.json, adds exposure patterns by repository class, read from the push remotes: strict
(a strict remote, no remote, or nothing matched), public-surface (every remote a published
surface: names in the disclosure ledger pass) or personal (every remote personal: credentials
only). Commit messages get the strict set in strict and public-surface repositories. A
disclosure line that already exists verbatim in HEAD is moved or copied text, not a new
disclosure; a credential blocks wherever it moves. Any other disclosure hit passes only once
the principal approves that exact line (ruling of 2026-10-06): no word list can tell a leak
from a legitimate mention, and rewording text to get past the check weakens both.
Anything it can't read or decide blocks the commit (R3.5); a machine with no board advises.
After its own checks it runs the repository's own hooks (E37): the `.githooks/<hook>`
delegate, then `.git/hooks/<hook>`, each once and never itself; a repository that declares
`.githooks/required` (on disk, or still in the index, E38) needs an executable delegate.
"""

from __future__ import annotations

import codecs
import json
import os
import re
import subprocess
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from synthesis import approvals, paths, yamlish  # noqa: E402

CREDENTIALS = {
    "AWS access key": r"\bAKIA[0-9A-Z]{16}\b",
    "GitHub token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b",
    "GitLab token": r"\bglpat-[A-Za-z0-9_-]{20,}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    "Anthropic key": r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",
    "OpenAI key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_-]{35}\b",
}
KEY_HEADER = re.compile(rb"BEGIN (?:(?:RSA|EC|DSA|OPENSSH|PGP|ENCRYPTED|SSH2) ){0,2}PRIVATE KEY", re.I)
KEY_INLINE = re.compile(rb"PRIVATE KEY(?: BLOCK)?-----(?:\\[nr]|\s)+[A-Za-z0-9+/]{40,}", re.I)
KEY_BODY = re.compile(rb"[\s\"'>#*;-]*[A-Za-z0-9+/]{40,}={0,2}(?:\\[nr])*[\s\"',;]*")
# Published example keys pass by exact value; no credential is approvable. AWS's: docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html
EXAMPLE_KEYS = re.compile(rb"(?<![A-Za-z0-9/+])(?:AKIAIOSFODNN7EXAMPLE|wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY)(?![A-Za-z0-9/+])")
SECRET_FILE = re.compile(r"(?:^|/)(?:\.env(?:\.(?!(?:example|sample|template|dist|defaults)$)[^/]+)?|id_(?:rsa|dsa|ecdsa|ed25519)"
                         r"|[^/]+\.(?:pem|p12|pfx|jks|keystore)|\.netrc|\.pgpass|\.aws/credentials)$", re.I)
# Files whose purpose is the pattern catalog itself; exposure patterns skip them, credentials never do.
CATALOG_PATHS = [r"(^|/)\.githooks/pre-commit$", r"(^|/)\.githooks/extra-patterns\.ya?ml$", r"^\.synthesis/git-hook-config\.ya?ml$",
                 r"(^|/)git-hook-config\.example\.ya?ml$", r"(^|/)anti-shortcut-catalog\.ya?ml$",
                 r"^skills/synthesis-disclosure-policy/", r"^skills/synthesis-git-hooks/"]
# The policy and ledger files config.json names are catalogs too, wherever the principal keeps them.
POSIX = {"alnum": "0-9A-Za-z", "alpha": "A-Za-z", "digit": "0-9", "space": r"\s", "blank": r" \t", "upper": "A-Z",
         "lower": "a-z", "xdigit": "0-9A-Fa-f", "punct": r"!-/:-@\[-`{-~"}
PATTERN_KEYS = ("tier_0_always", "tier_1_strict_only", "personal_remote_patterns", "strict_repo_patterns",
                "public_surface_patterns", "allowlist_lines", "diff_exclude_paths")
HUNK = re.compile(rb"@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
SECONDS, MAX_DIFF, MAX_MESSAGE, MAX_CONTEXT = 60, 256 << 20, 1 << 20, 32 << 20
HOOK = os.environ.get("SYNTHESIS_GIT_HOOK", "pre-commit")  # pre-merge-commit and commit-msg set this
# Holds the git directory whose commit was already checked, so a repository hook that calls the
# synthesis check again returns at once, while a commit in another repository is still checked.
CHAINED = "SYNTHESIS_COMMIT_CHECKED"
NEVER_REWORD = ("Remove a line that leaks. For a legitimate line, show the principal the line, get their approval and commit "
                "again; never reword, split, encode or build the text at run time to get past this check.")


class Refused(ValueError):
    """The check can't establish a clean commit: the reason blocks it."""


# --- the policy file and the ledger: the shared YAML reader in its strict subset -------------
# Comments, nested mappings by indentation, lists of scalars, `key: []` and one-line scalars, with
# double-quoted text kept literal (decoding escapes would turn a regex \b into a backspace).
# Anything else (tabs, flow collections, anchors, block scalars) is an error that blocks the
# commit, never a guess: one interpreter lacking PyYAML once let commits pass unscanned (2026-07-28).


def parse_yaml(text: str) -> dict:
    try:
        return yamlish.load_mapping(text, strict=True)
    except ValueError as exc:
        raise Refused(str(exc)) from None


def leaves(node) -> list:
    """Every string in a policy node, in order."""
    if isinstance(node, str):
        return [node]
    values = node.values() if isinstance(node, dict) else node if isinstance(node, list) else []
    return [s for v in values for s in leaves(v)]


def regex(pattern: str, flags: int = re.IGNORECASE):
    """The policy's grep -E pattern as a Python regex (POSIX classes such as [:space:] translated)."""
    return re.compile(re.sub(r"\[:(\w+):\]", lambda m: POSIX.get(m.group(1), m.group(0)), pattern), flags)


def _read_yaml(path: str, what: str) -> dict:
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as handle:
            return parse_yaml(handle.read())
    except (OSError, UnicodeDecodeError) as exc:
        raise Refused(f"cannot read the {what} {path} ({exc})")
    except Refused as exc:
        raise Refused(f"cannot parse the {what} {path}: {exc}")


def load_policy(config: dict) -> dict | None:
    """The commit policy config.json names, validated; None when it names none."""
    path = config.get("commit_policy")
    if not path:
        return None
    policy = _read_yaml(str(path), "commit policy")
    if not isinstance(policy.get("config_version"), int) or policy["config_version"] < 2:
        raise Refused(f"the commit policy {path} must declare config_version 2 or later")
    if not leaves(policy.get("tier_0_always")):
        raise Refused(f"the commit policy {path} defines no tier_0_always credential patterns")
    for key in PATTERN_KEYS:
        for pattern in leaves(policy.get(key)):
            try:
                if not pattern or any(ord(c) < 32 for c in pattern):
                    raise re.error("empty, or holds a control character")
                regex(pattern)
            except re.error as exc:
                raise Refused(f"the commit policy's {key} has an invalid pattern {pattern!r} ({exc})")
    policy["disclosure_ledger"] = config.get("disclosure_ledger") or policy.get("disclosure_ledger")
    return policy


def classify(policy: dict | None, urls: list[str]) -> str:
    """strict, public-surface or personal, from the push remotes. Mixed remotes take the stricter class."""
    def matches(key, url):
        return any(regex(p).search(url) for p in leaves(policy.get(key)))
    if not policy or not urls or any(matches("strict_repo_patterns", u) for u in urls):
        return "strict"
    if leaves(policy.get("public_surface_patterns")):
        if all(matches("public_surface_patterns", u) for u in urls):
            return "public-surface"
        if any(matches("public_surface_patterns", u) for u in urls):
            return "strict"  # escalation, never demotion through a broad personal pattern
    personal = leaves(policy.get("personal_remote_patterns"))
    return "personal" if personal and all(matches("personal_remote_patterns", u) for u in urls) else "strict"


def allowances(policy: dict) -> set:
    """Identity patterns the disclosure ledger records as published precedent. A configured ledger
    that is missing or malformed blocks public-surface commits; an entry needs evidence and an
    approved register, and may only subtract a pattern from an identity group."""
    path = policy.get("disclosure_ledger")
    if not path:
        return set()
    entities = _read_yaml(str(path), "disclosure ledger").get("entities")
    if not isinstance(entities, dict) or not entities:
        raise Refused(f"the disclosure ledger {path} has no entities")
    groups = leaves(policy.get("ledger_allowance_groups")) or ["confidential_names"]
    tier1 = policy.get("tier_1_strict_only") if isinstance(policy.get("tier_1_strict_only"), dict) else {}
    eligible = {p for g in groups for p in leaves(tier1.get(g))}
    registers = set(leaves(policy.get("ledger_registers")) or ["biography"])
    found = set()
    for name, entry in entities.items():
        if not isinstance(entry, dict) or not leaves(entry.get("evidence")):
            raise Refused(f"ledger entity {name} has no evidence; precedent without evidence is not precedent")
        declared = set(leaves(entry.get("registers")))
        if not declared or declared - registers:
            raise Refused(f"ledger entity {name} needs registers from: {', '.join(sorted(registers))}")
        for pattern in leaves(entry.get("hook_patterns")):
            if pattern not in eligible:
                raise Refused(f"ledger entity {name} claims {pattern!r}, outside the identity groups {', '.join(groups)}")
            found.add(pattern)
    return found


def exposure(policy: dict | None, cls: str) -> list[str]:
    """The tier-1 patterns that apply in a repository of this class."""
    tier1 = (policy or {}).get("tier_1_strict_only")
    tier1 = tier1 if isinstance(tier1, dict) else {}
    if not policy or cls == "personal":
        return []
    if cls == "public-surface":
        groups = leaves(policy.get("public_surface_groups"))
        allowed = allowances(policy)
        selected = {g: tier1[g] for g in groups if g in tier1} if groups else tier1
        return [p for p in dict.fromkeys(leaves(selected)) if p not in allowed]
    return list(dict.fromkeys(leaves(tier1)))


# --- reading the commit, byte for byte --------------------------------------------------------


def git_bytes(args: list, deadline: float, limit: int = MAX_DIFF, ok: tuple = (0,)) -> bytes:
    """git's output as bytes, bounded in time and size. A failure or a bound reached refuses."""
    import selectors
    import tempfile
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(["git", *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err)
        out, selector = bytearray(), selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        try:
            while True:
                left = deadline - time.monotonic()
                if left <= 0 or not selector.select(left):
                    raise Refused(f"git {args[0]} took longer than {SECONDS} seconds")
                chunk = os.read(proc.stdout.fileno(), 1 << 16)
                if not chunk:
                    break
                out += chunk
                if len(out) > limit:
                    raise Refused(f"git {args[0]} returned more than {limit >> 20} MiB")
            if proc.wait(timeout=max(0.1, deadline - time.monotonic())) not in ok:
                err.seek(0)
                raise Refused(f"git {args[0]} failed: {err.read(400).decode('utf-8', 'replace').strip()}")
        finally:
            selector.close()
            proc.stdout.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return bytes(out)


def _path(raw: bytes) -> bytes:
    """A diff's destination path as bytes; git quotes and escapes unusual names."""
    raw = raw[:-1] if raw.endswith(b"\t") else raw
    if raw.startswith(b'"'):
        if len(raw) < 2 or not raw.endswith(b'"'):
            raise Refused("unterminated quoted path in the staged diff")
        raw = codecs.escape_decode(raw[1:-1])[0]
    if not raw.startswith(b"b/"):
        raise Refused("unrecognized path in the staged diff")
    return raw[2:]


def added(diff: bytes) -> list:
    """(path, new line number, bytes) for every added line. Hunk counts are followed, so an
    added line that looks like a diff header stays content."""
    found, path, old, new, number = [], None, 0, 0, 0
    for line in diff.split(b"\n"):
        if old > 0 or new > 0:
            if line.startswith(b"\\"):
                continue
            tag = line[:1]
            if tag not in (b"+", b"-", b" ") or (tag == b"-" and old < 1) or (tag != b"-" and new < 1):
                raise Refused("the staged diff is malformed (a hunk's lengths do not match)")
            old, new = old - (tag != b"+"), new - (tag != b"-")
            if tag == b"+":
                found.append((path, number, line[1:]))
            number += tag != b"-"
        elif line.startswith(b"diff --git "):
            path = None
        elif line.startswith(b"+++ "):
            path = _path(line[4:])
        elif line.startswith(b"@@ "):
            hunk = HUNK.match(line)
            if path is None or not hunk:
                raise Refused("the staged diff has a hunk with no file")
            old, number = int(hunk.group(1) or 1), int(hunk.group(2))
            new = int(hunk.group(3) or 1)
        elif line.startswith(b"+"):
            raise Refused("the staged diff has an added line outside a hunk")
    if old > 0 or new > 0:
        raise Refused("the staged diff ends inside a hunk")
    return found


def key_lines(lines: list) -> set:
    """Line numbers that belong to a private key: a key header followed by key body lines. A
    header with no body (a detection rule, a doc example) is not a key."""
    hits = set()
    for i, line in enumerate(lines):
        if KEY_INLINE.search(line):
            hits.add(i + 1)
        if not KEY_HEADER.search(line):
            continue
        j = i + 1
        while j < min(len(lines), i + 5) and (not lines[j].strip() or re.match(rb"\s*[A-Za-z-]+: ", lines[j])):
            j += 1
        if j < len(lines) and KEY_BODY.fullmatch(lines[j]):
            end = next((k for k in range(j, min(len(lines), j + 400)) if not KEY_BODY.fullmatch(lines[k])), len(lines))
            hits.update(range(i + 1, min(len(lines), end + 2) + 1))  # through the short last line and the footer
    return hits


def message_lines(path: str) -> list:
    """The commit message's lines, without git's comment lines. It must be a small regular file."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        import stat
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise Refused("the commit message is not a regular file")
        raw = handle.read(MAX_MESSAGE + 1)
    if len(raw) > MAX_MESSAGE:
        raise Refused("the commit message is over 1 MiB")
    return [(b"commit message", n, b"" if line.startswith(b"#") else line) for n, line in enumerate(raw.split(b"\n"), 1)]


def _show(path: bytes, number: int, line: bytes) -> str:
    text = line.decode("utf-8", "backslashreplace")[:160]
    return f"{path.decode('utf-8', 'backslashreplace')}:{number}: " + "".join(c if c >= " " else "?" for c in text)


def scan(lines: list, policy: dict | None, patterns: list[str], deadline: float, approve, staged: bool = True) -> list[str]:
    """Credentials and keys in every line; exposure patterns outside catalog files and allowlisted lines, each
    hit then put to `approve`. Lines with invalid UTF-8 are matched through a replacement view and never exempted.
    A key header is left to the key rule (header plus body), whichever tier-0 pattern names it."""
    policy, found, by_path, skip, hits = policy or {}, [], {}, {}, []
    tier0 = [(n, re.compile(p)) for n, p in CREDENTIALS.items()] + [("credential pattern", regex(p)) for p in leaves(policy.get("tier_0_always"))]
    exposed = [regex(p) for p in patterns]
    allow = [regex(p) for p in leaves(policy.get("allowlist_lines"))]
    excluded = [re.compile(p) for p in CATALOG_PATHS + leaves(policy.get("diff_exclude_paths"))]
    for path, number, line in lines:
        text = line.decode("utf-8", "replace")
        valid = text.encode("utf-8") == line
        probe = EXAMPLE_KEYS.sub(b" ", KEY_HEADER.sub(b" ", line)).decode("utf-8", "replace")
        name = next((n for n, rx in tier0 if rx.search(probe)), None)
        if name:
            found.append(f"{_show(path, number, line)}  <- looks like a {name}; remove it, and rotate it if it was real")
        if KEY_HEADER.search(line) or KEY_INLINE.search(line) or KEY_BODY.fullmatch(line):
            by_path.setdefault(path, set()).add(number)
        if path not in skip:  # a path with invalid UTF-8 or a newline earns no exclusion
            shown = path.decode("utf-8", "replace")
            skip[path] = shown.encode("utf-8") == path and "\n" not in shown and any(rx.search(shown) for rx in excluded)
        if exposed and not skip[path] and any(rx.search(text) for rx in exposed):
            if not (valid and any(rx.search("+" + text) for rx in allow)):
                hits.append((path, number, line))
    for path, numbers in by_path.items():
        content = git_bytes(["cat-file", "blob", b":" + path], deadline, MAX_CONTEXT).split(b"\n") if staged else [x[2] for x in lines]
        keys = key_lines(content) & numbers
        found += [f"{_show(path, n, content[n - 1])}  <- private key material; never commit a key" for n in sorted(keys)]
    moved = _in_head({h[2] for h in hits}, deadline) if hits and staged else set()
    return found + approve([h for h in hits if h[2] not in moved])


def read_allowances(store) -> dict:
    """The approved lines: {"lines": {fingerprint: date approved}}. No file yet is none; one that can't be read blocks."""
    try:
        with open(store, encoding="utf-8") as handle:
            return {**json.load(handle)["lines"]}  # anything but an object of lines raises
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, LookupError, TypeError) as exc:
        raise Refused(f"cannot read the approved lines in {store} ({exc}); repair it, never delete it to get past this")


def unapproved(hits: list, repo: str, store, approved: dict) -> list[str]:
    """Disclosure hits the principal has not approved for this repository, file (or commit message) and exact line.
    A grant counts once the harness's transcript shows the principal typing its code; it is then kept in the store
    as a hash and a date, so that line passes from then on, while an edit or a new place asks again."""
    found, granted = [], {}
    for path, number, line in hits:
        key = approvals.digest("disclosure-line", [repo, *(b.decode("utf-8", "surrogateescape") for b in (path, line))])
        if key in approved or key in granted:
            continue
        try:
            if approvals.consume("disclosure-line", {"fp": key}):
                granted[key] = time.strftime("%Y-%m-%d")
                continue
            code = approvals.request("disclosure-line", {"fp": key}, f"line {number} of {os.fsdecode(path)} in {repo}")
            why = f"unapproved disclosure for this repository's audience; if it belongs, ask the principal to type {approvals.how(code)}"
        except approvals.Unverified as exc:
            why = str(exc)
        found.append(f"{_show(path, number, line)}  <- {why}")
    if granted:
        paths.write_json(store, {"lines": {**approved, **granted}})
    return found


def identity(remotes: list[str]) -> str:
    """The repository an approval binds, alike in every clone on every Mac: its push remotes without scheme, user, `.git`
    or case; with none, its git folder (shared by its worktrees) under the home directory."""
    if remotes:
        return " ".join(sorted({re.sub(r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^/:]+)[:/]+(.*?)(?:\.git)?/*$", r"\1/\2", u.lower())
                                for u in remotes}))
    found, home = os.path.realpath(_git("rev-parse", "--git-common-dir").stdout.strip()), os.path.expanduser("~")
    return "~" + found[len(home):] if paths.inside(found, home) else found


def _in_head(lines: set, deadline: float) -> set:
    """The given lines that already exist, whole, in HEAD: moved text is not a new disclosure."""
    import tempfile
    wanted = {line for line in lines if line.strip() and b"\0" not in line}
    if not wanted or git_bytes(["rev-parse", "-q", "--verify", "HEAD"], deadline, ok=(0, 1)).strip() == b"":
        return set()
    with tempfile.NamedTemporaryFile() as patterns:
        patterns.write(b"\n".join(wanted) + b"\n")
        patterns.flush()
        out = git_bytes(["grep", "-h", "-I", "-F", "--no-color", "-f", patterns.name, "HEAD", "--"], deadline, ok=(0, 1))
    return wanted & set(out.split(b"\n"))


def changed_paths(deadline: float) -> list[str]:
    """Every staged path, both sides of a rename: a claim covers what leaves it as well as what arrives."""
    fields = git_bytes(["diff", "--cached", "--name-status", "-z", "-M", "--no-color"], deadline).split(b"\0")
    found, i = [], 0
    while i < len(fields) and fields[i]:
        count = 2 if fields[i][:1] in (b"R", b"C") else 1
        found += [os.fsdecode(p) for p in fields[i + 1:i + 1 + count]]
        i += 1 + count
    return found


def claims(repo_root: str, session_id: str, staged: list[str]) -> tuple[list[str], str]:
    """(problems, note): staged paths inside another live session's claim. No board advises;
    a board that exists but can't be read blocks (R2.6)."""
    from synthesis import board
    directory = paths.state() / "sessions"
    if not directory.is_dir():
        return [], "no coordination board on this machine, so claims were not checked"
    try:
        for entry in directory.glob("*.json"):
            json.loads(entry.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"the coordination board can't be read ({exc}); repair or remove that entry, then commit"], ""
    found = []
    for rel in staged:
        holders = board.holders(os.path.join(repo_root, rel), exclude=session_id)
        if holders:
            h = holders[0]
            found.append(f"{rel}: inside a claim held by {h.session} ({h.project or '-'}: {h.goal or 'no goal'})"
                         + ("" if session_id else "; if the claim is yours, commit with SYNTHESIS_SESSION=<your session id>"))
    return found, ""


def push_remotes() -> list[str]:
    out = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True).stdout
    return [p[1] for p in (line.split() for line in out.splitlines()) if len(p) >= 3 and p[2] == "(push)"]


def problems(config: dict, session_id: str, repo_root: str, message: str | None = None) -> tuple[list[str], list[str], str]:
    """(problems, notes, repository class) for the commit being made, or for its message."""
    deadline, policy, store = time.monotonic() + SECONDS, load_policy(config), paths.line_allowances(config)
    if policy:  # the configured policy, ledger and approved lines, when they live in this repository, are catalogs
        own = []
        for path in (config.get("commit_policy"), policy.get("disclosure_ledger"), store):
            real = os.path.realpath(os.path.expanduser(str(path))) if path else ""
            if real and real.startswith(os.path.realpath(repo_root) + os.sep):
                own.append("^" + re.escape(os.path.relpath(real, os.path.realpath(repo_root))) + "$")
        policy = {**policy, "diff_exclude_paths": leaves(policy.get("diff_exclude_paths")) + own}
    remotes = push_remotes()
    cls = classify(policy, remotes)
    wanted = cls != "personal" and (policy or {}).get("check_commit_message", True) is not False
    patterns = exposure(policy, cls) if message is None else exposure(policy, "strict") if wanted else []
    approved = read_allowances(store) if patterns else {}  # read whenever it could decide a line, so damage shows at once
    approve = lambda hits: unapproved(hits, identity(remotes), store, approved) if hits else []  # noqa: E731
    if message is not None:  # commit messages stay generic wherever outsiders read the log (2025-12-21)
        return scan(message_lines(message), policy, patterns, deadline, approve, False), [], cls
    diff = git_bytes(["diff", "--cached", "--no-ext-diff", "--no-textconv", "--text", "--no-color", "--src-prefix=a/",
                      "--dst-prefix=b/", "--no-renames", "--diff-filter=AM", "-U0"], deadline)
    found = scan(added(diff), policy, patterns, deadline, approve)
    names = git_bytes(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACR"], deadline).split(b"\0")
    found += [f"{os.fsdecode(n)}: a credential file name; keep secrets out of git (a public certificate can be .crt)"
              for n in names if n and SECRET_FILE.search(os.fsdecode(n))]
    held, note = claims(repo_root, session_id, changed_paths(deadline))
    return found + held, [note] if note else [], cls


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _same(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def repository_hooks(repo_root, common_dir, running):
    """(hooks to run, problem): the repository's own hooks for this event, minus the one running now."""
    # A clean automatic merge goes through the same delegate as any commit, as in 2.x.
    delegate = os.path.join(repo_root, ".githooks", "pre-commit" if HOOK == "pre-merge-commit" else HOOK)
    declared = HOOK != "commit-msg" and (os.path.lexists(os.path.join(repo_root, ".githooks", "required")) or _git(
        "-C", repo_root, "ls-files", "--error-unmatch", "--", ".githooks/required").returncode == 0)
    if declared:  # an unstaged rm leaves the declaration in the index; a staged `git rm` withdraws it
        if not os.path.lexists(delegate):
            return [], ".githooks/required is declared but .githooks/pre-commit is missing: create it as an executable file and commit it beside the marker"
        if not os.path.isfile(delegate):
            return [], ".githooks/required is declared but .githooks/pre-commit is not a regular file: replace it with an executable file"
        if not os.access(delegate, os.X_OK):
            return [], ".githooks/required is declared but .githooks/pre-commit is not executable: run chmod +x .githooks/pre-commit"
    chain = []
    for hook in (delegate, os.path.join(common_dir, "hooks", HOOK)):
        if not os.path.isfile(hook) or any(_same(hook, h) for h in [running] + chain):
            continue
        if os.access(hook, os.X_OK):
            chain.append(hook)
        else:
            print(f"synthesis commit check: skipped {hook}: not executable"
                  + (" (add .githooks/required to make this an error)" if hook == delegate else ""), file=sys.stderr)
    return chain, None


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--classify"]:  # which class this repository is, and why a commit would be checked so
        try:
            policy = load_policy(paths.config())
            cls = classify(policy, push_remotes())
            ledger = policy.get("disclosure_ledger") if policy else None  # read and checked whatever the class
            print(cls + (f" ({len(allowances(policy))} ledger allowances read cleanly)" if ledger else ""))
        except (OSError, ValueError) as exc:
            print(f"synthesis commit check: {exc}", file=sys.stderr)
            return 1
        return 0
    where = _git("rev-parse", "--show-toplevel", "--absolute-git-dir", "--git-common-dir", "--git-path", f"hooks/{HOOK}")
    lines = where.stdout.splitlines()
    if where.returncode != 0 or len(lines) != 4:
        print(f"synthesis commit check: cannot locate the repository ({where.stderr.strip()}); commit blocked", file=sys.stderr)
        return 1
    repo_root, git_dir, common_dir, running = lines[0], lines[1], os.path.abspath(lines[2]), os.path.abspath(lines[3])
    if os.environ.get(CHAINED) == git_dir + HOOK:  # a repository hook called the check again: already done
        return 0
    try:
        message = (args[0] if args else "") if HOOK == "commit-msg" else None
        found, notes, cls = problems(paths.config(), paths.session_id(), repo_root, message)
    except (OSError, ValueError) as exc:  # Refused is a ValueError
        print(f"synthesis commit check: {exc}; commit blocked", file=sys.stderr)
        return 1
    chain, problem = repository_hooks(repo_root, common_dir, running)
    found += [problem] if problem else []
    for note in notes:
        print(f"synthesis commit check: {note}", file=sys.stderr)
    if found:
        print(f"synthesis commit check refused this {'message' if message is not None else 'commit'} "
              f"({cls} repository):\n  " + "\n  ".join(found[:20])
              + (f"\n  ... and {len(found) - 20} more" if len(found) > 20 else "")
              + (f"\n{NEVER_REWORD}" if any(approvals.how("") in f for f in found) else ""), file=sys.stderr)
        return 1
    for hook in chain:
        env = {**os.environ, CHAINED: git_dir + HOOK, "SYNTHESIS_REPO_CLASS": cls}
        code = subprocess.run([hook, *args], env=env).returncode
        if code != 0:
            print(f"synthesis commit check: the repository's own hook {hook} refused this commit (exit {code})", file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
