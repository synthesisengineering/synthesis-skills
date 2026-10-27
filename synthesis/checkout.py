"""Work in a shared checkout: uncommitted changes found, kept recoverable, and the project index edited safely.

2026-10-20: a session's script emptied a shared projects/index.yaml (it opened the file for writing before
reading it). Another session's uncommitted edit in that file, covered by no claim, was lost, and nothing
could restore it. A snapshot here is `git stash create`: a commit of the tracked changes that leaves the files,
the index and the stash list untouched, kept reachable by a ref under refs/synthesis/journal/ for KEEP_DAYS.
Untracked files are not kept. The claims log records who claimed what, so a warning can name the last claimant.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time

from synthesis import paths

KEEP_DAYS = 14
GLOB = set("*?[")


def _git(repo: str, *args: str, env: dict | None = None, text_in: str | None = None) -> tuple[int, str]:
    try:
        done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=30, input=text_in,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", **(env or {})})
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return done.returncode, done.stdout


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


def dirty_under(claims: list[str]) -> list[str]:
    """Tracked files with uncommitted changes that fall under any of these claims."""
    from synthesis import board
    found = []
    for claim in claims:
        base = _literal(board.normalize(claim))
        repo = repo_of(base)
        if not repo:
            continue
        code, out = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=no", "--no-renames", "--",
                         os.path.relpath(base, repo))
        files = [os.path.join(repo, r[3:]) for r in out.split("\0") if len(r) > 3] if code == 0 else []
        found += [f for f in files if f == base or board.overlaps(claim, f)]
    return sorted(set(found))


def snapshot(repo: str, reason: str, session: str = "") -> str:
    """Keep the checkout's uncommitted tracked changes recoverable; returns the snapshot's commit, or ""."""
    code, out = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=no", "--no-renames")
    files = [r[3:] for r in out.split("\0") if len(r) > 3] if code == 0 else []
    if not files:
        return ""
    code, sha = _git(repo, "stash", "create", f"synthesis journal: {reason}")
    sha = sha.strip()
    if code or not sha:
        return ""
    _git(repo, "update-ref", f"refs/synthesis/journal/{time.strftime('%Y%m%dT%H%M%S')}-{sha[:10]}", sha)
    _append("journal.jsonl", {"repo": repo, "sha": sha, "reason": reason, "session": session, "files": files})
    code, refs = _git(repo, "for-each-ref", "--format=%(refname) %(creatordate:unix)", "refs/synthesis/journal/")
    for line in refs.splitlines():  # older snapshots go; a session's edit is restored within days or not at all
        name, _, when = line.rpartition(" ")
        if when.isdigit() and int(when) < time.time() - KEEP_DAYS * 86400:
            _git(repo, "update-ref", "-d", name)
    return sha


def snapshot_paths(targets: list[str], reason: str, session: str = "") -> list[str]:
    return [s for s in (snapshot(r, reason, session) for r in sorted({repo_of(t) for t in targets} - {""})) if s]


def _append(name: str, entry: dict) -> None:
    log = paths.state() / name
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": time.time(), **entry}) + "\n")


def _read(name: str) -> list[dict]:
    log = paths.state() / name
    rows = []
    for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def journal(path: str = "") -> list[dict]:
    """Snapshots, newest first; with a path, only those that hold a change to it."""
    real = os.path.realpath(path) if path else ""
    rows = [r for r in _read("journal.jsonl") if not real
            or any(os.path.realpath(os.path.join(r["repo"], f)) == real for f in r.get("files", []))]
    return sorted(rows, key=lambda r: -r.get("at", 0))


def show(sha: str, path: str) -> str:
    """The file as a snapshot kept it."""
    repo = repo_of(path)
    code, out = _git(repo, "show", f"{sha}:{os.path.relpath(os.path.realpath(path), repo)}") if repo else (1, "")
    if code:
        raise ValueError(f"no snapshot {sha} of {path}")
    return out


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
