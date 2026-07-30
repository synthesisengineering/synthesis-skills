#!/usr/bin/env python3
"""Retire a merged feature worktree and its branches, fail-closed.

Parallel sessions create isolated worktrees constantly, and retiring them by
hand repeats the same risky sequence: verify the work reached the remote,
remove the worktree, delete the local branch, delete the remote branch. Done
manually it depends on the shell's current directory being the right
repository — the exact dependency behind repeated wrong-repo worktree
mistakes — and nothing stops removal of a dirty tree or an unmerged branch.

This helper takes the repository EXPLICITLY, never trusts the working
directory, and refuses every unsafe state:

- the repository path must be a git worktree's real toplevel, not a symlink;
- the target must be a linked worktree of that repository, never its main
  worktree, and never a directory containing the current working directory;
- the worktree must be completely clean (tracked and untracked);
- the checked-out branch must be an ancestor of the verification base
  (default: the remote's fetched main) — by default after a fresh fetch, so
  "merged" means merged on the REMOTE, not in a stale local ref;
- the local branch is deleted with git's safe delete only, and the remote
  branch only when --delete-remote is passed.

Nothing here ever uses --force variants, and nothing is removed before its
verification passes.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run(
    repository: Path, *arguments: str, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def fail(message: str) -> int:
    print(f"retire-worktree refused: {message}", file=sys.stderr)
    return 2


def worktree_entries(repository: Path) -> list[dict[str, str]]:
    listing = run(repository, "worktree", "list", "--porcelain")
    if listing.returncode != 0:
        raise RuntimeError(listing.stderr.strip() or "git worktree list failed")
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in listing.stdout.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        required=True,
        type=Path,
        help="The repository the worktree belongs to (explicit — the current "
        "directory is never used to pick a repository).",
    )
    parser.add_argument("--worktree", required=True, type=Path)
    parser.add_argument(
        "--branch",
        help="Expected branch; must match the worktree's checkout when given.",
    )
    parser.add_argument(
        "--base",
        default=None,
        help="Verification base ref (default: <remote>/HEAD, falling back to "
        "<remote>/main).",
    )
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip the pre-verification fetch (verification then runs against "
        "the last-fetched state).",
    )
    parser.add_argument(
        "--delete-remote",
        action="store_true",
        help="Also delete the branch on the remote after ancestry passes.",
    )
    args = parser.parse_args()

    repository = args.repository.expanduser()
    if repository.is_symlink():
        return fail(f"repository path is a symlink: {repository}")
    repository = repository.absolute()
    toplevel = run(repository, "rev-parse", "--show-toplevel")
    if toplevel.returncode != 0:
        return fail(f"not a git repository: {repository}")
    if Path(toplevel.stdout.strip()).resolve() != repository.resolve():
        return fail(
            f"repository must be the worktree toplevel, got {repository} "
            f"inside {toplevel.stdout.strip()}"
        )

    worktree = args.worktree.expanduser().absolute()
    try:
        entries = worktree_entries(repository)
    except RuntimeError as exc:
        return fail(str(exc))
    if not entries:
        return fail("git reported no worktrees")
    main_worktree = Path(entries[0]["worktree"]).resolve()
    match = next(
        (
            entry
            for entry in entries
            if Path(entry["worktree"]).resolve() == worktree.resolve()
        ),
        None,
    )
    if match is None:
        return fail(f"{worktree} is not a worktree of {repository}")
    if Path(match["worktree"]).resolve() == main_worktree:
        return fail("refusing to retire the repository's main worktree")

    cwd = Path.cwd().resolve()
    if cwd == worktree.resolve() or worktree.resolve() in cwd.parents:
        return fail(
            "the current directory is inside the target worktree; leave it "
            "first"
        )

    status = run(worktree, "status", "--porcelain")
    if status.returncode != 0:
        return fail(status.stderr.strip() or "status failed in the worktree")
    if status.stdout.strip():
        return fail(
            "worktree is not clean; commit, stash, or inspect before retiring:"
            f"\n{status.stdout.strip()}"
        )

    branch_ref = match.get("branch", "")
    if not branch_ref.startswith("refs/heads/"):
        return fail(f"worktree is not on a local branch: {branch_ref or 'detached'}")
    branch = branch_ref[len("refs/heads/") :]
    if args.branch and args.branch != branch:
        return fail(f"worktree is on {branch}, not the expected {args.branch}")

    if not args.no_fetch:
        fetched = run(repository, "fetch", "--quiet", "--prune", args.remote)
        if fetched.returncode != 0:
            return fail(
                f"fetch from {args.remote} failed (pass --no-fetch only to "
                "verify against last-fetched state): "
                + fetched.stderr.strip()
            )

    base = args.base
    if base is None:
        for candidate in (f"{args.remote}/HEAD", f"{args.remote}/main"):
            resolved = run(repository, "rev-parse", "--verify", "--quiet", candidate)
            if resolved.returncode == 0:
                base = candidate
                break
    if base is None:
        return fail(
            f"could not resolve a verification base under {args.remote}; "
            "pass --base explicitly"
        )
    base_check = run(repository, "rev-parse", "--verify", "--quiet", base)
    if base_check.returncode != 0:
        return fail(f"verification base does not resolve: {base}")

    ancestry = run(repository, "merge-base", "--is-ancestor", branch, base)
    if ancestry.returncode != 0:
        return fail(
            f"branch {branch} is not fully contained in {base}; its commits "
            "have not been verified on the remote"
        )

    removed = run(repository, "worktree", "remove", str(worktree))
    if removed.returncode != 0:
        return fail(removed.stderr.strip() or "git worktree remove failed")
    print(f"Removed worktree {worktree}")

    deleted = run(repository, "branch", "-d", branch)
    if deleted.returncode != 0:
        print(
            f"retire-worktree: local branch kept: "
            + (deleted.stderr.strip() or f"could not delete {branch}"),
            file=sys.stderr,
        )
    else:
        print(f"Deleted local branch {branch}")

    if args.delete_remote:
        listed = run(repository, "ls-remote", "--heads", args.remote, branch)
        if listed.returncode != 0:
            return fail(f"could not query {args.remote}: {listed.stderr.strip()}")
        if not listed.stdout.strip():
            print(f"Remote branch {args.remote}/{branch} already absent")
        else:
            pushed = run(repository, "push", args.remote, "--delete", branch)
            if pushed.returncode != 0:
                return fail(
                    f"remote branch deletion failed: {pushed.stderr.strip()}"
                )
            print(f"Deleted remote branch {args.remote}/{branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
