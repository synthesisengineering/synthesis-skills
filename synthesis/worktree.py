"""Worktrees (R2.7): create one under a board claim, retire it only when nothing
would be lost, and land merged work in the main checkout.

Every command takes its paths explicitly and never picks a repository from the
current directory. Nothing here forces: a worktree is removed only when clean,
a branch is deleted only at the commit that was verified, and a remote branch
only by a lease bound to that commit.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from synthesis import board, paths

TEMPORARY_ROOTS = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/")


class Refused(Exception):
    pass


def _git(repo: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    env = {**os.environ, "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env, timeout=timeout)


def _out(repo: str, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        raise Refused(f"git {' '.join(args)} failed in {repo}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def _real(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def _absolute(path: str) -> str:
    """Paths are given explicitly: a relative path would depend on the current directory."""
    if not os.path.isabs(os.path.expanduser(path)):
        raise Refused(f"give {path!r} as an absolute path")
    return os.path.expanduser(path)


def _toplevel(path: str) -> str:
    """The real top of the git worktree at `path`; `path` must be that top, not a folder inside it."""
    real = _real(path)
    if not os.path.isdir(real):
        raise Refused(f"no directory at {path}")
    top = _git(real, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or _real(top.stdout.strip()) != real:
        raise Refused(f"{path} is not the top of a git worktree")
    return real


def _worktrees(repo: str) -> list[dict]:
    """`git worktree list --porcelain` as dicts; the first entry is the main checkout."""
    entries, current = [], {}
    for line in _out(repo, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if current:
                current["path"] = _real(current["worktree"])
                entries.append(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return entries


def _remote_default(repo: str, *, fetch: bool) -> tuple[str, str, str]:
    """(remote, default branch, its commit), after a fresh fetch so "merged" means merged on the remote."""
    remotes = _out(repo, "remote").split()
    remote = "origin" if "origin" in remotes else (remotes[0] if len(remotes) == 1 else "")
    if not remote:
        raise Refused(f"{repo} has no origin remote" + (f" (remotes: {', '.join(remotes)})" if remotes else ""))
    if fetch:
        fetched = _git(repo, "fetch", "--quiet", "--prune", remote)
        if fetched.returncode != 0:
            raise Refused(f"fetch from {remote} failed, so nothing can be shown merged: {fetched.stderr.strip()}")
    def commit(name: str) -> str:
        oid = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{name}^{{commit}}")
        return oid.stdout.strip() if name and oid.returncode == 0 else ""

    symbolic = _git(repo, "symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD")
    name = symbolic.stdout.strip()[len(f"refs/remotes/{remote}/"):] if symbolic.returncode == 0 else ""
    if not commit(name):  # never set, or left dangling by a renamed default branch: ask the remote
        name = ""
        for line in _git(repo, "ls-remote", "--symref", remote, "HEAD").stdout.splitlines():
            if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
                name = line[len("ref: refs/heads/"):-len("\tHEAD")]
    for candidate in [name] if name else ["main", "master"]:
        if commit(candidate):
            return remote, candidate, commit(candidate)
    raise Refused(f"cannot find {remote}'s default branch" + (f" ({name} is not fetched)" if name else ""))


def _merged(repo: str, head: str, base: str) -> str:
    """How `head`'s content is known to be in `base`, or "" when it is not."""
    if _git(repo, "merge-base", "--is-ancestor", head, base).returncode == 0:
        return "merged"
    if _git(repo, "diff", "--quiet", head, base, "--").returncode == 0:
        return "identical tree (squash merge)"
    # A squash merge after the default branch moved on: merging head changes nothing in base.
    merge = _git(repo, "merge-tree", "--write-tree", base, head)
    if merge.returncode == 0 and merge.stdout.split()[:1] == [_out(repo, "rev-parse", f"{base}^{{tree}}")]:
        return "content already in the default branch (squash merge)"
    return ""


def _status(path: str) -> list[str]:
    """Every entry removal would lose: modified, untracked and ignored, except ignored `__pycache__`."""
    status = _git(path, "status", "--porcelain", "-z", "--ignored=matching", "--untracked-files=all")
    if status.returncode != 0:
        raise Refused(f"git status failed in {path}: {status.stderr.strip()}")
    lost, skip = [], False
    for entry in status.stdout.split("\0"):
        if skip or not entry:
            skip = False
            continue
        skip = "R" in entry[:2] or "C" in entry[:2]  # a rename or copy is followed by its source path
        if entry.startswith("!! ") and "__pycache__" in entry[3:].rstrip("/").split("/"):
            continue
        lost.append(entry)
    return lost


def create(repo: str, path: str, branch: str, ref: str | None = None, *, session_id: str, take: bool = False) -> str:
    """Claim `path` for this session, then add a worktree there on `branch`.

    A new branch starts at `ref` (default: the repository's HEAD). An existing
    branch is checked out as it is, so `ref` must not be given for one.
    """
    if not session_id:
        raise Refused("no session id: pass --session or run inside a harness session")
    repo = _toplevel(_absolute(repo))
    target = _real(_absolute(path))
    if os.path.lexists(target) and not (os.path.isdir(target) and not os.listdir(target)):
        raise Refused(f"{target} already exists and is not an empty directory")
    if branch.startswith("-") or _git(repo, "check-ref-format", "--branch", branch).returncode != 0:
        raise Refused(f"{branch!r} is not a valid branch name")
    exists = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    if exists and ref:
        raise Refused(f"branch {branch} already exists; omit --from to check it out, or choose a new branch name")
    start = ref or "HEAD"
    if not exists and (start.startswith("-") or _git(repo, "rev-parse", "--verify", "--quiet", f"{start}^{{commit}}").returncode):
        raise Refused(f"{start!r} is not a commit in {repo}")

    claim = target + "/**"
    before = board.load(session_id)
    already_held = before is not None and claim in before.claims
    try:
        board.claim(session_id, [claim], take_stale=take, harness=paths.harness())
    except board.ClaimConflict as exc:
        raise Refused(f"{exc}; no worktree was created") from None
    add = ["worktree", "add", target, branch] if exists else ["worktree", "add", "-b", branch, target, start]
    added = _git(repo, *add)
    if added.returncode != 0:
        if not already_held:
            board.release(session_id, [claim])
        raise Refused(f"git worktree add failed, and the claim was released: {added.stderr.strip()}")
    head = _out(target, "rev-parse", "--short", "HEAD")
    lines = [f"Created worktree {target} on {'existing ' if exists else 'new '}branch {branch} at {head}"
             + ("" if exists else f" (from {start})"), f"Claimed {claim} for session {session_id}"]
    if target.startswith(TEMPORARY_ROOTS):
        lines.append("Warning: this is under a temporary directory, which the system may clear; "
                     "keep long-lived work somewhere durable.")
    return "\n".join(lines)


def retire(path: str, *, session_id: str = "", delete_remote: bool = False) -> str:
    """Remove a worktree whose work is safely on the remote default branch, then its branches."""
    given = os.path.normpath(_absolute(path))
    if os.path.islink(given):
        raise Refused(f"{path} is a symbolic link; give the worktree's real path")
    target = _toplevel(given)
    entries = _worktrees(target)
    main = entries[0]
    if main["path"] == target:
        raise Refused(f"{target} is the repository's main checkout; only linked worktrees are retired")
    entry = next((e for e in entries if e["path"] == target), None)
    if entry is None:
        raise Refused(f"{target} is not a registered worktree of {main['path']}")
    if "locked" in entry:
        raise Refused(f"{target} is locked ({entry['locked'] or 'no reason given'}); unlock it first")
    try:
        cwd = _real(os.getcwd())
    except FileNotFoundError:
        cwd = ""
    if cwd and paths.inside(cwd, target):
        raise Refused(f"the current directory {cwd} is inside {target}; leave it first")
    holders = board.holders(target + "/**", exclude=session_id)
    if holders:
        h = holders[0]
        raise Refused(f"{target} is inside a claim held by {h.session} ({h.project or '-'}: {h.goal or 'no goal'})")
    lost = _status(target)
    if lost:
        raise Refused(f"{target} is not clean; removal would lose these (commit, move or delete them first):\n  "
                      + "\n  ".join(lost))

    head = entry["HEAD"]
    branch = entry.get("branch", "")[len("refs/heads/"):] if entry.get("branch", "").startswith("refs/heads/") else ""
    remote, default, base = _remote_default(target, fetch=True)
    how = _merged(target, head, base)
    if not how:
        raise Refused(f"{target} HEAD {head[:12]} is not merged into {remote}/{default} ({base[:12]}) "
                      "and its content differs; push it and merge it first")
    # The remote branch to delete: the upstream when it is on this remote, else the same name there.
    remote_ref = f"refs/heads/{branch}"
    if branch and _git(target, "config", f"branch.{branch}.remote").stdout.strip() == remote:
        remote_ref = _git(target, "config", f"branch.{branch}.merge").stdout.strip() or remote_ref

    removed = _git(main["path"], "worktree", "remove", target)
    if removed.returncode != 0:
        raise Refused(f"git worktree remove failed: {removed.stderr.strip()}")
    lines = [f"Verified {head[:12]} against {remote}/{default} at {base[:12]}: {how}", f"Removed worktree {target}"]

    if not branch:
        lines.append("Detached HEAD: no branch to delete")
    elif branch == default:
        lines.append(f"Kept local branch {branch}: it is the default branch")
    else:
        current = _git(main["path"], "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").stdout.strip()
        if current != head:
            lines.append(f"Kept local branch {branch}: it moved to {current[:12] or 'nothing'} after verification")
        else:
            deleted = _git(main["path"], "branch", "-D", "--", branch)
            lines.append(f"Deleted local branch {branch}" if deleted.returncode == 0
                         else f"Kept local branch {branch}: {deleted.stderr.strip()}")
    if delete_remote and branch:
        lines.append(_delete_remote_branch(main["path"], remote, remote_ref, default, head))

    # Claims under a removed tree name nothing; drop this session's and any stale holder's (R2.4: told).
    for holder in board.sessions():
        if holder.session != session_id and not holder.stale:
            continue  # a live holder overlapping the tree was refused above
        under = [c for c in holder.claims if paths.inside(_real(c[:-3] if c.endswith("/**") else c), target)]
        if not under:
            continue
        board.release(holder.session, under)
        if holder.session == session_id:
            lines.append(f"Released this session's claims under it: {', '.join(under)}")
        else:
            board.notify(holder.session, session_id or "synthesis worktree retire",
                         f"Retired worktree {target}; its work is on {remote}/{default}. "
                         f"Released your stale claims under it: {', '.join(under)}")
            lines.append(f"Released stale claims of {holder.session} under it and told that session")
    if "bare" not in main:
        try:
            lines.append(land(main["path"], fetch=False)[1])
        except Refused as exc:
            lines.append(f"Not landed: {exc}")
    return "\n".join(lines)


def _delete_remote_branch(repo: str, remote: str, ref: str, default: str, head: str) -> str:
    """Delete `ref` on `remote` only while it still points at the verified `head`."""
    if ref == f"refs/heads/{default}" or not ref.startswith("refs/heads/"):
        return f"Kept {remote} {ref}: it is the default branch or not a branch"
    listed = _git(repo, "ls-remote", remote, ref)
    if listed.returncode != 0:
        return f"Kept the remote branch: cannot read {remote} ({listed.stderr.strip()})"
    oids = [line.split("\t")[0] for line in listed.stdout.splitlines() if line.endswith("\t" + ref)]
    if not oids:
        return f"Remote branch {remote} {ref} is already gone"
    if oids != [head]:
        return f"Kept remote branch {remote} {ref}: it is at {oids[0][:12]}, not the verified {head[:12]}"
    pushed = _git(repo, "push", "--quiet", f"--force-with-lease={ref}:{head}", remote, f":{ref}")
    if pushed.returncode != 0:
        return f"Kept remote branch {remote} {ref}: the lease on {head[:12]} failed ({pushed.stderr.strip()})"
    return f"Deleted remote branch {remote} {ref} at {head[:12]}"


def land(path: str, *, fetch: bool = True) -> tuple[bool, str]:
    """Fast-forward the main checkout's default branch to the remote's, when it has no
    uncommitted changes to tracked files and is behind.

    Returns (landed or already current, what happened and why).
    """
    entries = _worktrees(_toplevel(_absolute(path)))
    main = entries[0]
    if "bare" in main:
        return False, f"{main['path']} is a bare repository; there is no main checkout to land"
    where = main["path"]
    remote, default, base = _remote_default(where, fetch=fetch)
    if main.get("branch") != f"refs/heads/{default}":
        on = main.get("branch", "")[len("refs/heads/"):] or "a detached HEAD"
        return False, f"Not landed: main checkout {where} is on {on}, not {default}; left as it is"
    local = main["HEAD"]
    if local == base:
        return True, f"Main checkout {where} is already at {remote}/{default} ({base[:12]})"
    if _git(where, "merge-base", "--is-ancestor", local, base).returncode != 0:
        ahead = _git(where, "merge-base", "--is-ancestor", base, local).returncode == 0
        return False, (f"Not landed: main checkout {where} is " + (f"ahead of {remote}/{default}; push it first" if ahead
                       else f"diverged from {remote}/{default}; rebase or inspect it"))
    # Untracked files never block: a fast-forward leaves them alone, and git refuses one that would overwrite them.
    dirty = _git(where, "status", "--porcelain", "--untracked-files=no").stdout.rstrip().splitlines()
    if dirty:
        return False, f"Not landed: main checkout {where} has uncommitted changes:\n  " + "\n  ".join(dirty[:20])
    merged = _git(where, "merge", "--ff-only", "--quiet", base)
    if merged.returncode != 0:
        return False, f"Not landed: fast-forward of {where} failed: {merged.stderr.strip()}"
    return True, f"Landed: main checkout {where} fast-forwarded {local[:12]}..{base[:12]} to {remote}/{default}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synthesis worktree", description=__doc__.split("\n\n")[0])
    parser.add_argument("--session", default="", help="session id (default: the harness's own)")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("create", help="claim a path for this session, then add a worktree there")
    p.add_argument("repo", help="the repository (any of its checkouts), given explicitly")
    p.add_argument("path", help="absolute path of the new worktree")
    p.add_argument("branch", help="new branch, or an existing one to check out")
    p.add_argument("--from", dest="ref", default=None, help="start point for a new branch (default: HEAD)")
    p.add_argument("--take", action="store_true", help="take over an overlapping stale claim")
    p = sub.add_parser("retire", help="remove a merged, clean worktree and its branch")
    p.add_argument("path")
    p.add_argument("--delete-remote", action="store_true", help="also delete the remote branch, by lease")
    p = sub.add_parser("land", help="fast-forward the main checkout's default branch to the remote's")
    p.add_argument("path", help="any checkout of the repository")
    args = parser.parse_args(argv)
    session_id = args.session or paths.session_id()
    try:
        if args.action == "create":
            print(create(args.repo, args.path, args.branch, args.ref, session_id=session_id, take=args.take))
            return 0
        if args.action == "retire":
            print(retire(args.path, session_id=session_id, delete_remote=args.delete_remote))
            return 0
        landed, note = land(args.path)
        print(note)
        return 0 if landed else 1
    except (Refused, subprocess.TimeoutExpired) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
