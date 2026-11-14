"""Work in a shared checkout: uncommitted changes found, kept recoverable, and the project index edited safely.

2026-10-20: a session's script emptied a shared projects/index.yaml (it opened the file for writing before
reading it). Another session's uncommitted edit in that file, covered by no claim, was lost, and nothing
could restore it. A snapshot here is a commit of the uncommitted changes written through a temporary index, so
the files, the index and the stash list are untouched, kept reachable by a ref under refs/synthesis/journal/ for
KEEP_DAYS. Since 5.19.0 (the audit of 2026-11-11, §3.2) a claim's, a release's and a commit's snapshot keep
untracked files too, and none keeps a credential. The claims log records who claimed what, so a warning can name
the last claimant.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time

from synthesis import paths

KEEP_DAYS = 14
GLOB = set("*?[")
UNTRACKED_MAX = 2 * 1024 * 1024  # an untracked file larger than this is named in the journal, not kept;
UNTRACKED_ALL = 20 * 1024 * 1024  # so is one past this many bytes in all, or past this many files, so a build
UNTRACKED_FILES = 1000  # folder nobody ignored is never copied whole at every claim
LEFT_NAMED = 50  # the journal names this many of the other files it did not keep, every one under the claim, and counts them all
JUNK = re.compile(r"(?:^|/)(?:\.DS_Store|\._[^/]*|Icon\r)$")  # what Finder writes beside a record is not one


class Unreadable(ValueError):
    """git could not read a checkout's status: nothing about its work can be said, so nothing passes on it."""


def _run(repo: str, *args: str, env: dict | None = None, data: bytes | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=30, input=data,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", **(env or {})})
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(args, 1, b"", str(exc).encode())


def _git(repo: str, *args: str, env: dict | None = None, text_in: str | None = None) -> tuple[int, str]:
    """git's status and output, decoded with no newline translation, so a name holding a carriage return survives."""
    done = _run(repo, *args, env=env, data=None if text_in is None else text_in.encode("utf-8", "surrogateescape"))
    return done.returncode, done.stdout.decode("utf-8", "surrogateescape")


def repo_of(path: str) -> str:
    """The working tree holding path, or "" when it is in none."""
    d = path if os.path.isdir(path) else os.path.dirname(path) or "."
    while d and not os.path.isdir(d):
        d = os.path.dirname(d)
    code, out = _git(d or ".", "rev-parse", "--show-toplevel")
    return out.strip() if code == 0 else ""


def _literal(claim: str) -> str:
    """The part of a claim before any glob segment: the folder or file git can be asked about."""
    parts = claim[:-3].split(os.sep) if claim.endswith("/**") else claim.split(os.sep)
    keep = []
    for part in parts:
        if GLOB & set(part):
            break
        keep.append(part)
    return os.sep.join(keep) or os.sep


def _changes(repo: str, untracked: bool, *spec: str) -> list[str] | None:
    """`git status` rows ("XY path"), or None when git cannot read the checkout. Untracked files .gitignore does not
    exclude are among them when asked, never what Finder writes; a folder git lists as untracked ends in "/": a
    repository inside this one, whose own status holds its work."""
    code, out = _git(repo, "status", "--porcelain=v1", "-z", f"--untracked-files={'all' if untracked else 'no'}",
                     "--no-renames", *spec)
    return None if code else [r for r in out.split("\0") if len(r) > 3 and not (r.startswith("??") and JUNK.search(r[3:]))]


def dirty_under(claims: list[str]) -> list[str]:
    """Files with uncommitted changes that fall under any of these claims: untracked files among them, and the work of
    a repository inside a claimed folder. Raises Unreadable when git cannot read a checkout, so nothing passes on it."""
    from synthesis import board
    found = []
    for claim in claims:
        base = _literal(board.normalize(claim))
        repo = repo_of(base)
        rows = _changes(repo, True, "--", os.path.relpath(base, repo)) if repo else []
        if rows is None:
            raise Unreadable(f"git could not read the status of {repo}")
        for full in (os.path.join(repo, r[3:]) for r in rows):
            if full.rstrip("/") == base or board.overlaps(claim, full.rstrip("/")):
                found += dirty_under([full.rstrip("/") + "/**"]) if full.endswith("/") else [full]
    return sorted(set(found))


def _stamp() -> dict:
    """A snapshot is no one's commit, made now: a fixed identity, as `git stash create` falls back to, so it never needs
    one set, and the present time whatever the environment says."""
    when = f"@{int(time.time())} +0000"
    return {"GIT_AUTHOR_NAME": "synthesis journal", "GIT_AUTHOR_EMAIL": "journal@synthesis", "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_NAME": "synthesis journal", "GIT_COMMITTER_EMAIL": "journal@synthesis", "GIT_COMMITTER_DATE": when}


def _commit(repo: str, tree: str, parents: list, reason: str) -> str:
    code, sha = _git(repo, "commit-tree", "--no-gpg-sign", tree, *[a for p in parents for a in ("-p", p)], "-m",
                     f"synthesis journal: {reason}", env=_stamp())
    return sha.strip() if code == 0 else ""


def _staged_commit(repo: str, index: str, head: str, folder: str) -> str:
    """What the index holds, as a commit on HEAD, read from a copy so the index itself is never written: the state
    `git stash create` kept as its second parent. "" when nothing can be written: a merge in progress, or a staged
    change holding a credential (the commit check's built-in patterns), which a snapshot never keeps."""
    from synthesis import credentials
    copy = os.path.join(folder, "staged")
    try:
        shutil.copyfile(index, copy)
    except OSError:
        return ""
    diff = _run(repo, "diff", "--cached", "--no-color", "--no-ext-diff", "--no-textconv", "-U0", env={"GIT_INDEX_FILE": copy})
    if diff.returncode or any(credentials.held("", line[1:]) for line in diff.stdout.splitlines() if line.startswith(b"+")):
        return ""
    code, tree = _git(repo, "write-tree", env={"GIT_INDEX_FILE": copy})
    return _commit(repo, tree.strip(), [head] if head else [], "the index") if code == 0 and tree.strip() else ""


def _tree_commit(repo: str, files: list[str], reason: str, staged: bool, left: list) -> str:
    """A commit of HEAD with these files as the working tree holds them, written through a temporary index, with the
    index's own state as its last parent when something is staged. A file git refuses to read is moved to `left`
    and the rest kept."""
    code, out = _git(repo, "rev-parse", "--git-path", "index", "HEAD")
    index, _, head = out.partition("\n")
    head = head.strip() if code == 0 else ""  # a checkout with no commit yet gets a snapshot with no parent
    with tempfile.TemporaryDirectory() as folder:
        env, extra = {"GIT_INDEX_FILE": os.path.join(folder, "index")}, []
        if staged:
            extra = [s for s in [_staged_commit(repo, os.path.join(repo, index.strip()), head, folder)] if s]
        if _git(repo, "read-tree", head or "--empty", env=env)[0]:
            return ""
        for _ in range(len(files) + 1):
            done = _run(repo, "update-index", "--add", "--remove", "-z", "--stdin", env=env,
                        data="".join(f + "\0" for f in files).encode("utf-8", "surrogateescape"))
            if done.returncode == 0:
                break
            said = done.stderr.decode("utf-8", "surrogateescape")  # git names the file it could not read: leave it out
            refused = [f for f in files if f"fatal: {f}:" in said or f"path {f}" in said or f"open(\"{f}\")" in said]
            if not refused:
                return ""
            files = [f for f in files if f not in refused]
            left += refused
        code, tree = _git(repo, "write-tree", env=env)
    return _commit(repo, tree.strip(), ([head] if head else []) + extra, reason) if code == 0 and tree.strip() else ""


def _holds(repo: str, rel: str) -> bool:
    """Whether a file holds a credential by the commit check's built-in patterns, read up to UNTRACKED_MAX bytes;
    a name alone where there is nothing to read."""
    from synthesis import credentials
    full = os.path.join(repo, rel)
    try:
        data = b"" if os.path.islink(full) or not os.path.isfile(full) else open(full, "rb").read(UNTRACKED_MAX)
    except OSError:
        data = b""
    return bool(credentials.held(rel, data))


def snapshot(repo: str, reason: str, session: str = "", untracked: bool = True, first: tuple = ()) -> str:
    """Keep the checkout's uncommitted changes recoverable; returns the snapshot's commit, or "".

    The snapshot is a commit of the working tree, written through a temporary index: the tracked changes and, with
    untracked (a claim, a release, a commit), the untracked files .gitignore does not exclude, within the limits
    above. Those under the claims in `first` are kept before any other, and every one of them not kept is named. A
    file past a limit, one git cannot read and one holding a credential are named in the journal and not kept (a
    tracked one is kept as HEAD has it). When something is staged, the index's own state is the snapshot's last
    parent. The session start, inside the hook's budget, keeps tracked changes alone, and its journal line says so.
    The real index, the working tree and the stash list are untouched."""
    from synthesis import board
    rows = _changes(repo, untracked) if repo else None
    if not rows:
        return ""
    files = list(dict.fromkeys(r[3:] for r in rows if not r.startswith("??")))

    def claimed(rel: str) -> bool:
        return any(board.overlaps(c, os.path.join(repo, rel.rstrip("/"))) for c in first)
    kept, left, size = [], [], 0
    for rel in sorted((r[3:] for r in rows if r.startswith("??") and r[3:] not in files), key=lambda r: (not claimed(r), r)):
        full = os.path.join(repo, rel)
        try:
            info = os.lstat(full)
        except OSError:
            continue  # gone since git listed it
        readable = stat.S_ISLNK(info.st_mode) or (stat.S_ISREG(info.st_mode) and os.access(full, os.R_OK))
        if (readable and info.st_size <= UNTRACKED_MAX and size + info.st_size <= UNTRACKED_ALL and len(kept) < UNTRACKED_FILES
                and not _holds(repo, rel)):
            kept.append(rel)
            size += info.st_size
        else:  # a repository inside this one ("dir/") lands here too: named, its own snapshots keep its work
            left.append(rel)
    for rel in [f for f in files if _holds(repo, f)]:
        files.remove(rel)
        left.append(rel)
    sha = _tree_commit(repo, files + kept, reason, any(r[0] not in " ?" for r in rows), left) if files or kept else ""
    if not sha:  # git wrote nothing: every file it would have kept is named
        left += [f for f in files + kept if f not in left]
    named = [f for f in left if claimed(f)] + [f for f in left if not claimed(f)][:LEFT_NAMED]
    entry = {"repo": repo, "reason": reason, "session": session, **({} if untracked else {"tracked_only": True}),
             **({"left": named, "left_count": len(left)} if left else {})}
    if not sha:
        if left:  # nothing could be kept, and the journal says what was not
            _append("journal.jsonl", {**entry, "sha": "", "files": []})
        return ""
    _git(repo, "update-ref", f"refs/synthesis/journal/{time.strftime('%Y%m%dT%H%M%S')}-{sha[:10]}", sha)
    _append("journal.jsonl", {**entry, "sha": sha, "files": [f for f in files + kept if f not in left]})
    code, refs = _git(repo, "for-each-ref", "--format=%(refname)", "refs/synthesis/journal/")
    for name in refs.splitlines():  # older snapshots go, by the time their name gives: a commit's own date can be set
        try:
            made = time.mktime(time.strptime(name.rsplit("/", 1)[-1].split("-")[0], "%Y%m%dT%H%M%S"))
        except ValueError:
            continue
        if made < time.time() - KEEP_DAYS * 86400:
            _git(repo, "update-ref", "-d", name)
    return sha


def snapshot_paths(targets: list[str], reason: str, session: str = "") -> list[str]:
    """A snapshot of each checkout these claims fall in, their own files kept first."""
    from synthesis import board
    first = tuple(board.as_claim(t) for t in targets)  # a folder named bare covers what is under it
    return [s for s in (snapshot(r, reason, session, first=first) for r in sorted({repo_of(t) for t in targets} - {""})) if s]


def _append(name: str, entry: dict) -> None:
    """One line, under a lock; the journal drops the lines of snapshots older than KEEP_DAYS, whose refs are gone."""
    log = paths.board() / name
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        if name == "journal.jsonl" and json.loads(handle.readline() or "{}").get("at", time.time()) < time.time() - KEEP_DAYS * 86400:
            handle.seek(0)
            recent = [line for line in handle.readlines() if json.loads(line).get("at", 0) >= time.time() - KEEP_DAYS * 86400]
            handle.seek(0)
            handle.truncate()
            handle.writelines(recent)
        handle.write(json.dumps({"at": time.time(), **entry}) + "\n")


def _read(name: str) -> list[dict]:
    log = paths.board() / name
    rows = []
    for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def journal(path: str = "") -> list[dict]:
    """Snapshots, newest first; with a path, only those that hold a change to it or name it as not kept."""
    real = os.path.realpath(path) if path else ""
    rows = [r for r in _read("journal.jsonl") if not real or any(
        os.path.realpath(os.path.join(r["repo"], f)) == real for f in r.get("files", []) + r.get("left", []))]
    return sorted(rows, key=lambda r: -r.get("at", 0))


def show(sha: str, path: str) -> bytes:
    """The file as a snapshot kept it, byte for byte: a binary file, or one with CRLF line ends, comes back as kept."""
    repo = repo_of(path)
    done = _run(repo, "show", f"{sha}:{os.path.relpath(os.path.realpath(path), repo)}") if repo else None
    if done is None or done.returncode:
        raise ValueError(f"no snapshot {sha} of {path}")
    return done.stdout


def log_claims(session: str, project: str, action: str, claims: list[str]) -> None:
    _append("claims.jsonl", {"session": session, "project": project, "action": action, "claims": claims})


def last_claimant(path: str, exclude: str = "") -> dict:
    """The session that last claimed something covering path, from the claims log: {session, project, at}."""
    from synthesis import board
    for row in reversed(_read("claims.jsonl")):
        if row.get("action") == "claim" and row.get("session") != exclude and any(
                board.overlaps(c, path) for c in row.get("claims", [])):
            return row
    return {}


# --- the project index ---------------------------------------------------------------------------------------

EDITABLE = {"status", "last_session", "bounded", "wake_when", "blocked_by", "completed_date", "superseded_by",
            "started_date", "initiative", "name"}
STATUSES = {"active", "paused", "completed", "archived"}


def _edit(text: str, project: str, field: str, value: str) -> str:
    """The index with one scalar field of one project set; refuses a project or field it cannot find safely."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.rstrip() == f"- id: {project}"), None)
    if start is None:
        raise ValueError(f"no project {project!r} in the index")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("- ") or re.match(r"\S", lines[i])), len(lines))
    shown = value if re.fullmatch(r"[a-z][a-z-]*|true|false", value) else json.dumps(value)
    for i in range(start + 1, end):
        if lines[i].startswith(f"  {field}:"):
            if lines[i].rstrip().endswith((">", "|", ">-", "|-")):
                raise ValueError(f"{field} is a multi-line field; edit it by hand under a claim")
            lines[i] = f"  {field}: {shown}"
            return "\n".join(lines)
    after = next((i for i in range(start + 1, end) if lines[i].startswith("  status:")), start)
    lines.insert(after + 1, f"  {field}: {shown}")
    return "\n".join(lines)


def index_set(project: str, field: str, value: str, session: str = "") -> str:
    """Set one field of one project in the shared index: atomic in the working tree, committed alone, so other
    sessions' uncommitted edits in the file are kept and never committed under this change."""
    from synthesis import board, project as projects
    if field not in EDITABLE:
        raise ValueError(f"{field!r} is not a field this command sets; it sets {', '.join(sorted(EDITABLE))}")
    if field == "status" and value not in STATUSES:
        raise ValueError(f"status is one of {', '.join(sorted(STATUSES))}")
    index = next((r / "projects" / "index.yaml" for r in projects.roots() if (r / "projects" / "index.yaml").is_file()
                  and f"- id: {project}\n" in (r / "projects" / "index.yaml").read_text(encoding="utf-8")), None)
    if index is None:
        raise ValueError(f"no index in the knowledge roots lists {project!r}")
    held = board.holders(str(index), exclude=session)
    if held:
        raise ValueError(f"{index} is claimed by {held[0].session} (project {held[0].project or '-'}); ask them first")
    repo = repo_of(str(index))
    rel = os.path.relpath(os.path.realpath(index), repo)
    snapshot(repo, f"index set {project} {field}", session)
    before = index.read_text(encoding="utf-8")
    after = _edit(before, project, field, value)
    code, head = _git(repo, "show", f"HEAD:{rel}")
    committed = ""
    if code == 0 and f"- id: {project}\n" in head:  # commit this change alone, against HEAD, through the commit hooks
        new_head = _edit(head, project, field, value)
        _, blob = _git(repo, "hash-object", "-w", "--stdin", text_in=new_head)
        _, old_blob = _git(repo, "rev-parse", f"HEAD:{rel}")
        _, staged = _git(repo, "ls-files", "-s", "--", rel)
        with tempfile.TemporaryDirectory() as folder:
            env = {"GIT_INDEX_FILE": os.path.join(folder, "index")}
            _git(repo, "read-tree", "HEAD", env=env)
            _git(repo, "update-index", "--cacheinfo", f"100644,{blob.strip()},{rel}", env=env)
            # a commit message names neither the project nor the field: the principal's commit-message rule (2026-10-27)
            done = subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "Update docs"],
                                  capture_output=True, text=True, env={**os.environ, **env})
        if done.returncode:
            raise ValueError("the commit was refused: " + (done.stderr or done.stdout).strip()[-400:])
        if old_blob.strip() and old_blob.strip() in staged:  # the real index held HEAD's version: move it along
            _git(repo, "update-index", "--cacheinfo", f"100644,{blob.strip()},{rel}")
        committed = _git(repo, "rev-parse", "--short", "HEAD")[1].strip()
    if index.read_text(encoding="utf-8") != before:
        raise ValueError(f"{index} changed while this command ran; nothing in the working tree was written")
    handle, temp = tempfile.mkstemp(dir=str(index.parent), prefix=".index.", suffix=".yaml")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(after)
    os.replace(temp, index)
    return f"set {project} {field} in {index}" + (f"; committed {committed}" if committed else "; not in HEAD yet, so not committed")
