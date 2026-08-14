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

Nothing here uses unconditional force. Optional remote deletion uses only a
commit-bound --force-with-lease compare-and-delete operation, and nothing is
removed before its verification passes.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path


SYNTHESIS_HOME = Path(
    os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
)
PENDING_DIR = SYNTHESIS_HOME / "repo-guard" / "pending"
STATE_DIR = PENDING_DIR.parent
LIFECYCLE_LOCK = STATE_DIR / "lifecycle.lock"
RETIREMENT_RUNTIME_DIR = STATE_DIR / "retirement-runtime"
RETIREMENT_DIR = STATE_DIR / "retired-worktrees"
LIFECYCLE_LOCK_FD_ENV = "SYNTHESIS_LIFECYCLE_LOCK_FD"
CHECKPOINT_SYNC = (
    Path(__file__).resolve().parents[2]
    / "synthesis-repo-guard"
    / "checkpoint_sync.py"
)


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


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def validate_state_paths(*paths: Path) -> None:
    for value in paths:
        path = lexical_absolute(value)
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            if os.path.lexists(current) and current.is_symlink():
                raise ValueError(f"state path contains a symlink component: {current}")


@contextmanager
def lifecycle_lock():
    validate_state_paths(STATE_DIR, LIFECYCLE_LOCK, RETIREMENT_RUNTIME_DIR)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    validate_state_paths(STATE_DIR, LIFECYCLE_LOCK, RETIREMENT_RUNTIME_DIR)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(LIFECYCLE_LOCK, flags, 0o600)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"lifecycle lock is not a regular file: {LIFECYCLE_LOCK}")
    fcntl.flock(descriptor, fcntl.LOCK_EX)
    try:
        yield descriptor
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def stage_reconciler() -> Path:
    source = CHECKPOINT_SYNC
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"source-managed retirement reconciler is unavailable: {source}")
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    destination = RETIREMENT_RUNTIME_DIR / f"checkpoint-sync-{digest}.py"
    validate_state_paths(RETIREMENT_RUNTIME_DIR, destination)
    RETIREMENT_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    validate_state_paths(RETIREMENT_RUNTIME_DIR, destination)
    if destination.is_symlink():
        raise ValueError(f"staged retirement reconciler is a symlink: {destination}")
    if destination.is_file():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError(f"staged retirement reconciler hash mismatch: {destination}")
        return destination
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(RETIREMENT_RUNTIME_DIR)
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o700)
        os.replace(temporary_name, destination)
        directory_fd = os.open(
            RETIREMENT_RUNTIME_DIR,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return destination


def verify_reconciler_interface(checkpoint_sync: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(checkpoint_sync), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    required = {
        "--prepare-worktree-retirement",
        "--complete-worktree-retirement",
        "--retirement-remote",
    }
    if completed.returncode != 0 or not required.issubset(set(completed.stdout.split())):
        raise ValueError("staged retirement reconciler lacks the required interface")


def reconciler_digest(data: dict) -> str:
    digest = data.get("reconciler_sha256")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("retirement intent has no valid reconciler digest")
    return digest


def pinned_reconciler(data: dict) -> Path:
    digest = reconciler_digest(data)
    checkpoint_sync = RETIREMENT_RUNTIME_DIR / f"checkpoint-sync-{digest}.py"
    validate_state_paths(RETIREMENT_RUNTIME_DIR, checkpoint_sync)
    if checkpoint_sync.is_symlink() or not checkpoint_sync.is_file():
        raise ValueError(
            f"retirement intent's pinned reconciler is unavailable: {checkpoint_sync}"
        )
    if hashlib.sha256(checkpoint_sync.read_bytes()).hexdigest() != digest:
        raise ValueError(
            f"retirement intent's pinned reconciler hash does not match: {checkpoint_sync}"
        )
    verify_reconciler_interface(checkpoint_sync)
    return checkpoint_sync


def run_reconciler(
    checkpoint_sync: Path,
    arguments: list[str],
    lock_fd: int,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment[LIFECYCLE_LOCK_FD_ENV] = str(lock_fd)
    command = [
        sys.executable,
        str(checkpoint_sync),
        *arguments,
        "--json",
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=environment,
        pass_fds=(lock_fd,),
    )


def reconciler_detail(completed: subprocess.CompletedProcess[str]) -> Path:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        try:
            payload = json.loads(completed.stdout)
            detail = str(payload[0].get("alert") or detail)
        except (IndexError, TypeError, json.JSONDecodeError):
            pass
        raise ValueError(f"retirement preparation or completion failed: {detail}")
    try:
        payload = json.loads(completed.stdout)
        detail = payload[0]["detail"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("retirement reconciler returned invalid intent evidence") from exc
    return lexical_absolute(Path(str(detail)))


def matching_retirement_intent(
    repository: Path, worktree: Path
) -> tuple[Path, dict] | None:
    validate_state_paths(RETIREMENT_DIR)
    if not RETIREMENT_DIR.is_dir():
        return None
    matches: list[tuple[Path, dict]] = []
    for intent in sorted(RETIREMENT_DIR.glob("*.json")):
        validate_state_paths(intent)
        if intent.is_symlink():
            raise ValueError(f"retirement intent is a symlink: {intent}")
        data = json.loads(intent.read_text(encoding="utf-8"))
        if data.get("schema_version") != 2 or data.get("state") not in {
            "prepared",
            "completed",
        }:
            raise ValueError(f"retirement intent is invalid: {intent}")
        if (
            lexical_absolute(Path(str(data.get("repository") or "")))
            == lexical_absolute(repository)
            and lexical_absolute(Path(str(data.get("worktree") or "")))
            == lexical_absolute(worktree)
        ):
            matches.append((intent, data))
    if len(matches) > 1:
        raise ValueError("multiple retirement intents match the missing worktree")
    return matches[0] if matches else None


def cleanup_branch(
    repository: Path,
    branch: str,
    remote: str,
    expected_head: str,
    *,
    delete_remote: bool,
) -> int:
    branch_check = run(repository, "check-ref-format", "--branch", branch)
    if branch_check.returncode != 0:
        return fail(f"retirement intent branch is invalid: {branch}")
    head_check = run(repository, "rev-parse", "--verify", f"{expected_head}^{{commit}}")
    if head_check.returncode != 0 or head_check.stdout.strip() != expected_head:
        return fail("retirement intent head is not a canonical commit")

    local_ref = f"refs/heads/{branch}"
    local_exists = run(repository, "show-ref", "--verify", "--quiet", local_ref)
    if local_exists.returncode == 0:
        deleted = run(repository, "branch", "-d", branch)
        if deleted.returncode != 0:
            return fail(
                "local branch cleanup failed; remote branch was not touched: "
                + (deleted.stderr.strip() or f"could not delete {branch}")
            )
        print(f"Deleted local branch {branch}")
    elif local_exists.returncode == 1:
        print(f"Local branch {branch} already absent")
    else:
        return fail(local_exists.stderr.strip() or "could not inspect local branch")

    if delete_remote:
        remote_ref = f"refs/heads/{branch}"
        listed = run(repository, "ls-remote", "--heads", remote, remote_ref)
        if listed.returncode != 0:
            return fail(f"could not query {remote}: {listed.stderr.strip()}")
        if not listed.stdout.strip():
            print(f"Remote branch {remote}/{branch} already absent")
        else:
            lines = [line.split() for line in listed.stdout.splitlines() if line.strip()]
            if lines != [[expected_head, remote_ref]]:
                return fail(
                    f"remote branch {remote}/{branch} no longer equals the "
                    "verified retirement head; it was not deleted"
                )
            pushed = run(
                repository,
                "push",
                f"--force-with-lease={remote_ref}:{expected_head}",
                remote,
                f":{remote_ref}",
            )
            if pushed.returncode != 0:
                return fail(
                    "remote branch deletion lease failed; the branch may have "
                    f"advanced and was not deleted: {pushed.stderr.strip()}"
                )
            print(f"Deleted remote branch {remote}/{branch}")
    return 0


def resume_retirement(
    repository: Path,
    worktree: Path,
    expected_branch: str | None,
    remote: str,
    *,
    delete_remote: bool,
) -> int | None:
    match = matching_retirement_intent(repository, worktree)
    if match is None:
        return None
    intent, data = match
    recorded_branch = data.get("branch")
    recorded_remote = data.get("remote")
    recorded_head = data.get("head")
    if recorded_branch is not None and not isinstance(recorded_branch, str):
        return fail("retirement intent branch is invalid")
    if not isinstance(recorded_remote, str) or not recorded_remote:
        return fail("retirement intent remote is invalid")
    if remote != recorded_remote:
        return fail(
            f"retirement intent was verified against {recorded_remote}, not {remote}"
        )
    if not isinstance(recorded_head, str) or not recorded_head:
        return fail("retirement intent head is invalid")
    if expected_branch and recorded_branch and expected_branch != recorded_branch:
        return fail(
            f"retirement intent is for {recorded_branch}, not {expected_branch}"
        )
    try:
        with lifecycle_lock() as lock_fd:
            checkpoint_sync = pinned_reconciler(data)
            completed = run_reconciler(
                checkpoint_sync,
                ["--complete-worktree-retirement", str(intent)],
                lock_fd,
            )
            reconciler_detail(completed)
            print(f"Resumed retirement from {intent}")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return fail(str(exc))
    branch = expected_branch or recorded_branch
    if not branch:
        print("retire-worktree: no recorded branch; branch cleanup was not attempted")
        return 0
    return cleanup_branch(
        repository,
        branch,
        recorded_remote,
        recorded_head,
        delete_remote=delete_remote,
    )


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
        try:
            resumed = resume_retirement(
                repository,
                worktree,
                args.branch,
                args.remote,
                delete_remote=args.delete_remote,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return fail(str(exc))
        if resumed is not None:
            return resumed
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

    fetched = run(repository, "fetch", "--quiet", "--prune", args.remote)
    if fetched.returncode != 0:
        return fail(
            f"fetch from {args.remote} failed; remote ancestry cannot be proven: "
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
    symbolic_base = run(repository, "rev-parse", "--symbolic-full-name", base)
    remote_prefix = f"refs/remotes/{args.remote}/"
    if (
        symbolic_base.returncode != 0
        or not symbolic_base.stdout.strip().startswith(remote_prefix)
    ):
        return fail(
            f"verification base must be a freshly fetched {args.remote} "
            "remote-tracking ref"
        )
    base = symbolic_base.stdout.strip()
    base_check = run(repository, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_check.returncode != 0 or not base_check.stdout.strip():
        return fail(f"verification base does not resolve: {base}")
    base_oid = base_check.stdout.strip()

    ancestry = run(repository, "merge-base", "--is-ancestor", branch, base_oid)
    if ancestry.returncode != 0:
        return fail(
            f"branch {branch} is not fully contained in {base}; its commits "
            "have not been verified on the remote"
        )

    head_result = run(worktree, "rev-parse", "HEAD")
    if head_result.returncode != 0 or not head_result.stdout.strip():
        return fail(head_result.stderr.strip() or "worktree HEAD is unavailable")
    head = head_result.stdout.strip()

    try:
        with lifecycle_lock() as lock_fd:
            checkpoint_sync = stage_reconciler()
            verify_reconciler_interface(checkpoint_sync)
            prepared = run_reconciler(
                checkpoint_sync,
                [
                    "--prepare-worktree-retirement",
                    str(worktree),
                    "--retirement-repository",
                    str(repository),
                    "--retirement-head",
                    head,
                    "--retirement-remote",
                    args.remote,
                    "--retirement-base",
                    base,
                    "--retirement-branch",
                    branch,
                ],
                lock_fd,
            )
            intent = reconciler_detail(prepared)
            intent_data = json.loads(intent.read_text(encoding="utf-8"))
            checkpoint_sync = pinned_reconciler(intent_data)

            removed = run(repository, "worktree", "remove", str(worktree))
            if removed.returncode != 0:
                return fail(removed.stderr.strip() or "git worktree remove failed")
            print(f"Removed worktree {worktree}")

            completed = run_reconciler(
                checkpoint_sync,
                ["--complete-worktree-retirement", str(intent)],
                lock_fd,
            )
            reconciler_detail(completed)
            if completed.stdout.strip():
                print(completed.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return fail(str(exc))

    return cleanup_branch(
        repository,
        branch,
        args.remote,
        head,
        delete_remote=args.delete_remote,
    )


if __name__ == "__main__":
    sys.exit(main())
