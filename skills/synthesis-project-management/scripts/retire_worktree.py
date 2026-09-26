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
- the checked-out HEAD must be an ancestor of the verification base
  (default: the remote's fetched main) — by default after a fresh fetch, so
  "merged" means merged on the REMOTE, not in a stale local ref; a
  squash-merge has no shared commits, so an identical tree is accepted as
  the secondary proof, named loudly in the output;
- the main worktree is fast-forwarded to the verified base when it tracks
  the base branch (defect 3: "landed" must mean the operator's checkout
  too, not just origin) — retirement refuses when the advance is unsafe
  (dirty, diverged, or ahead checkout) and leaves a checkout on another
  branch alone with a loud note;
- local branch deletion checks the recorded head and delegates checked-out and
  ancestry protection to native Git, using a pinned remote base as its upstream;
- the remote branch is deleted only when --delete-remote is passed.

Verified detached worktrees use the same clean-state, ancestry and manifest
checks. They retire without deleting any local or remote branch.

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
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import uuid
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
        env={**os.environ, "LC_ALL": "C"},
    )


def fail(message: str) -> int:
    print(f"retire-worktree refused: {message}", file=sys.stderr)
    return 2


def _under_retired(cell: str, retired: str) -> bool:
    """Whether a held claim cell names the retired tree or something under it.

    Only absolute cells can be attributed lexically; relative areas resolve
    against row workspaces and are left for their owner. Covering cells
    (parents of the retired tree) are NOT matched — they still name live
    paths and must stay held.
    """
    base = cell.split(" @ ", 1)[0].removesuffix("/**").removesuffix("/")
    if not os.path.isabs(base):
        return False
    real = os.path.realpath(base)
    return real == retired or real.startswith(retired + os.sep)


def _narrow_retired_claims(worktree: Path, board: Path | None, *, diagnose_only: bool = False) -> bool:
    """Release the caller's claimed areas under the removed worktree.

    Retirement without narrowing leaves the seat's row naming a removed
    checkout, which fails every pairwise board check involving the seat
    and blocks its next claim on its own stale areas (intake 33). Only
    the CALLER's row is touched — narrow enforces ownership — and only
    cells under the retired tree; covering areas stay held. A failed owned
    cleanup refuses successful completion while retaining the durable intent
    for an authenticated retry. Missing session identity is reported without
    inventing an owner. Runs after verified retirement completion on both the fresh
    and resumed paths; retries use the same native ownership checks and
    never acquire or release a foreign row.
    """
    if worktree.exists() or worktree.is_symlink():
        print(f"retire-worktree WARNING: removed-worktree path has been recreated: {worktree}; no claims changed", file=sys.stderr)
        return False
    coordination = Path(__file__).resolve().parent / "coordination.py"
    retired = os.path.realpath(worktree)
    session_id = os.environ.get("SYNTHESIS_COORDINATION_SESSION", "").strip()
    base_cmd = [sys.executable, str(coordination)]
    if board is not None:
        base_cmd += ["--board", str(board)]
    if not session_id:
        print(
            "retire-worktree: no SYNTHESIS_COORDINATION_SESSION exported; "
            f"release areas under {worktree} by hand: coordination.py narrow "
            f"--session <id> --release {shlex.quote(str(worktree))}",
        )
        return True
    try:
        completed = subprocess.run(
            base_cmd + ["status", "--json"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "LC_ALL": "C"},
        )
        if completed.returncode != 0:
            raise ValueError(completed.stderr.strip() or "coordination status failed")
        sessions = json.loads(completed.stdout)["sessions"]
        if not isinstance(sessions, list):
            raise ValueError("coordination status lacks a sessions list")
    except Exception as exc:
        print(
            f"retire-worktree WARNING: cannot read board for claim narrowing: {exc}",
            file=sys.stderr,
        )
        return False
    row = next(
        (candidate for candidate in sessions
         if session_id in (
             candidate.get("session_uuid"),
             candidate.get("compact_id"),
             candidate.get("speakable_id"),
         )),
        None,
    )
    if row is None:
        print(f"retire-worktree: no board row for session {session_id}; nothing narrowed")
        return True
    areas = [cell for cell in row.get("claims", []) if _under_retired(cell, retired)]
    workspaces = [cell for cell in row.get("workspaces", []) if _under_retired(cell, retired)]
    if not areas and not workspaces:
        print(f"retire-worktree: no claimed areas under {worktree}; nothing narrowed")
        return True
    narrow_cmd = base_cmd + ["narrow", "--session", session_id]
    for cell in areas:
        narrow_cmd += ["--release", cell]
    for cell in workspaces:
        narrow_cmd += ["--release-workspace", cell]
    if diagnose_only:
        remedy = " ".join(shlex.quote(part) for part in narrow_cmd[2:])
        print(f"retire-worktree: no verified intent; no claims changed. "
              f"Session {session_id} retains cells under {worktree}. "
              f"Owner recovery: coordination.py {remedy}", file=sys.stderr)
        return False
    try:
        narrowed = subprocess.run(
            narrow_cmd, capture_output=True, text=True, timeout=60,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"retire-worktree WARNING: claim narrowing did not finish: {exc}; retry verified retirement", file=sys.stderr)
        return False
    if narrowed.returncode != 0:
        detail = narrowed.stderr.strip() or narrowed.stdout.strip()
        manual = " ".join(shlex.quote(part) for part in narrow_cmd[2:])
        print(
            f"retire-worktree WARNING: claim narrowing failed: {detail}. "
            f"Release by hand: coordination.py {manual}",
            file=sys.stderr,
        )
        return False
    print(
        f"retire-worktree: narrowed {len(areas)} area(s), "
        f"{len(workspaces)} workspace(s) under {worktree}"
    )

    return True


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


def delete_local_branch(
    repository: Path, branch: str, expected_head: str, *,
    base_ref: str, base_oid: str, force: bool = False,
) -> None:
    """Use native safe deletion against an immutable, command-selected upstream.

    Git owns checked-out-branch refusal and config cleanup. The preflight checks
    are observations, not global serialization of arbitrary concurrent Git.
    The lifecycle lock serializes this helper only; it cannot lock git switch.
    Callers pass force only after content_verdict proved an identical tree on
    the remote; a squash-merge has no shared commits, so native -d would refuse
    content that is already verified present.
    """
    local_ref = f"refs/heads/{branch}"
    config_result = run(repository, "rev-parse", "--path-format=absolute", "--git-path", "config")
    if config_result.returncode != 0 or not Path(config_result.stdout.strip()).is_absolute():
        raise ValueError("Git configuration path cannot be verified")
    config = Path(config_result.stdout.strip())
    validate_state_paths(config)
    if not stat.S_ISREG(config.stat().st_mode):
        raise ValueError("Git configuration is not a regular file")
    if os.path.lexists(config.with_name(config.name + ".lock")):
        raise ValueError("Git configuration is locked; branch and config retained")
    exists = run(repository, "show-ref", "--verify", "--quiet", local_ref)
    if exists.returncode == 1:
        remaining = run(repository, "config", "--local", "--get-regexp",
                        r"^branch\." + re.escape(branch) + r"\.")
        if remaining.returncode != 1:
            raise ValueError("local branch is absent but its configuration remains or cannot be verified; inspect it before retirement")
        return
    if exists.returncode != 0:
        raise ValueError("local branch cannot be inspected before cleanup")
    if run(repository, "symbolic-ref", "--quiet", local_ref).returncode != 1:
        raise ValueError("local branch is symbolic or cannot be verified as a direct ref")
    if any(entry.get("branch") == local_ref for entry in worktree_entries(repository)):
        raise ValueError("local branch is checked out; branch and config retained")
    current = run(repository, "rev-parse", "--verify", local_ref)
    if current.returncode != 0 or current.stdout.strip() != expected_head:
        raise ValueError(f"local branch no longer equals verified retirement head {expected_head}")

    merge = run(repository, "config", "--get-all", f"branch.{branch}.merge")
    if merge.returncode not in {0, 1}:
        raise ValueError("branch upstream configuration cannot be read")
    merge_refs = list(dict.fromkeys(merge.stdout.splitlines())) if merge.returncode == 0 else [local_ref]
    if not merge_refs or any(run(repository, "check-ref-format", ref).returncode != 0 for ref in merge_refs):
        raise ValueError("branch upstream merge configuration is not a set of valid refs")
    identifier = uuid.uuid4().hex
    remote_name = "synthesis-retirement-" + identifier
    collision = run(repository, "config", "--get-regexp", r"^remote\." + remote_name + r"\.")
    if collision.returncode != 1:
        raise ValueError("temporary retirement remote name is configured or cannot be verified absent")
    pinned_ref = "refs/synthesis-retirement/" + identifier
    created = run(repository, "update-ref", pinned_ref, base_oid, "0" * len(base_oid))
    if created.returncode != 0:
        raise ValueError("cannot pin verified retirement base: " + created.stderr.strip())
    try:
        options = ["-c", f"branch.{branch}.remote={remote_name}",
                   "-c", f"remote.{remote_name}.url=."]
        # branch.merge is multivalued: another -c merge=... does not replace
        # its first value. Map every existing merge source through a unique
        # command-only remote, to a real ref (a raw OID silently falls back to HEAD).
        for ref in merge_refs:
            options.extend(["-c", f"remote.{remote_name}.fetch={ref}:{pinned_ref}"])
        if merge.returncode == 1:
            options.extend(["-c", f"branch.{branch}.merge={local_ref}"])
        upstream = run(repository, *options, "for-each-ref", "--format=%(upstream)", local_ref)
        pinned = run(repository, "rev-parse", "--verify", pinned_ref)
        if (upstream.returncode != 0 or upstream.stdout.strip() != pinned_ref
                or pinned.returncode != 0 or pinned.stdout.strip() != base_oid):
            raise ValueError("native branch deletion does not resolve to the pinned verification base")
        verb = "-D" if force else "-d"
        deleted = run(repository, *options, "branch", verb, "--", branch)
        if deleted.returncode != 0:
            raise ValueError(f"native branch deletion against {base_ref} at {base_oid} refused: " + deleted.stderr.strip())
        if force:
            print(f"Deleted squash-merged branch {branch} by verified identical tree against {base_ref}")
        remaining = run(repository, "config", "--local", "--get-regexp",
                        r"^branch\." + re.escape(branch) + r"\.")
        if remaining.returncode != 1:
            raise ValueError("native branch deletion left branch configuration or its cleanup cannot be verified")
    finally:
        removed = run(repository, "update-ref", "-d", pinned_ref, base_oid)
        if removed.returncode != 0:
            raise ValueError("temporary retirement base cleanup refused; ref may have changed: " + pinned_ref)


def content_verdict(
    repository: Path, head: str, base_oid: str
) -> tuple[bool, str]:
    """Return (verified, method) for retirement content.

    Ancestry is the primary proof that the content reached the remote. A
    squash-merge lands identical content under a new commit, so an identical
    tree is the secondary proof. Anything else is unverified. Callers print
    the method so the record names which proof authorized the retirement.
    """
    ancestry = run(repository, "merge-base", "--is-ancestor", head, base_oid)
    if ancestry.returncode == 0:
        return True, "ancestry"
    identical = run(repository, "diff", "--quiet", head, base_oid, "--")
    if identical.returncode == 0:
        return True, "identical-tree"
    return False, ""


def cleanup_branch(
    repository: Path,
    branch: str,
    remote: str,
    expected_head: str,
    *,
    base_ref: str,
    base_oid: str,
    delete_remote: bool,
) -> int:
    branch_check = run(repository, "check-ref-format", "--branch", branch)
    if branch_check.returncode != 0:
        return fail(f"retirement intent branch is invalid: {branch}")
    head_check = run(repository, "rev-parse", "--verify", f"{expected_head}^{{commit}}")
    if head_check.returncode != 0 or head_check.stdout.strip() != expected_head:
        return fail("retirement intent head is not a canonical commit")
    if (
        not isinstance(base_ref, str)
        or not base_ref.startswith(f"refs/remotes/{remote}/")
        or run(repository, "check-ref-format", base_ref).returncode != 0
    ):
        return fail("retirement intent base is not a remote-tracking ref for " + remote)
    if not isinstance(base_oid, str) or not base_oid:
        return fail("retirement intent base commit is invalid")
    base_check = run(repository, "rev-parse", "--verify", f"{base_oid}^{{commit}}")
    if base_check.returncode != 0 or base_check.stdout.strip() != base_oid:
        return fail(f"retirement intent base {base_ref} has no canonical commit")
    verified, method = content_verdict(repository, expected_head, base_oid)
    if not verified:
        return fail(
            f"verified retirement head {expected_head} is not contained in "
            f"pinned base {base_ref} at {base_oid}, and its tree differs; "
            "no branch was deleted"
        )
    print(f"Verified branch content by {method} against {base_ref} at {base_oid[:12]}")

    try:
        with lifecycle_lock():
            delete_local_branch(repository, branch, expected_head,
                base_ref=base_ref, base_oid=base_oid,
                force=(method == "identical-tree"))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return fail(f"local branch cleanup failed; remote branch was not touched: {exc}")
    print(f"Retired local branch {branch} and its config against {base_ref} at {base_oid}")

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
    board: Path | None = None,
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
    if expected_branch and expected_branch != recorded_branch:
        return fail(
            f"retirement intent is for {recorded_branch or 'detached HEAD'}, not {expected_branch}"
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
    if not _narrow_retired_claims(worktree, board):
        return fail("retirement is retained; caller claim cleanup requires an authenticated retry")
    branch = recorded_branch
    if not branch:
        print("retire-worktree: no recorded branch; branch cleanup was not attempted")
        return 0
    return cleanup_branch(
        repository,
        branch,
        recorded_remote,
        recorded_head,
        base_ref=data.get("base_ref"),
        base_oid=data.get("base_oid"),
        delete_remote=delete_remote,
    )


def fast_forward_main_worktree(
    repository: Path,
    entries: list[dict[str, str]],
    main_worktree: Path,
    remote: str,
    base: str,
    base_oid: str,
) -> str | None:
    """Fast-forward the main worktree to the verified base, or refuse.

    Defect 3 ("landed" means origin, not the operator's checkout): a branch
    verified on the remote while the operator's main checkout sits behind
    leaves the next session reading stale files — 23 commits behind in the
    motivating incident, after an explicit warning. Retirement is the
    landing path, so it advances the main checkout itself: purely
    fast-forward to the already-verified base commit, never touching a
    dirty tree, and never moving a checkout that is not on the base
    branch. Returns None when the main worktree is current (or was
    advanced, or legitimately tracks another branch), else a refusal
    message. Nothing is removed before this passes.
    """
    main_entry = next(
        (
            entry
            for entry in entries
            if Path(entry["worktree"]).resolve() == main_worktree
        ),
        None,
    )
    if main_entry is None:
        return f"main worktree {main_worktree} is not listed; cannot verify it is current"
    current = run(main_worktree, "rev-parse", "HEAD")
    if current.returncode != 0 or not current.stdout.strip():
        return f"main worktree HEAD is unavailable: {main_worktree}"
    if current.stdout.strip() == base_oid:
        print(f"Main worktree {main_worktree} is already at {base} ({base_oid[:12]})")
        return None
    remote_prefix = f"refs/remotes/{remote}/"
    expected_branch = f"refs/heads/{base[len(remote_prefix):]}" if base.startswith(remote_prefix) else ""
    if not expected_branch or main_entry.get("branch", "") != expected_branch:
        print(
            f"Main worktree {main_worktree} is on "
            f"{main_entry.get('branch') or 'detached HEAD'}, not {expected_branch or base}; "
            "leaving it alone — advance it yourself"
        )
        return None
    status = run(main_worktree, "status", "--porcelain")
    if status.returncode != 0:
        return f"status failed in the main worktree: {main_worktree}"
    if status.stdout.strip():
        return (
            f"main worktree {main_worktree} has uncommitted changes; commit, "
            "stash, or inspect before retiring:"
            f"\n{status.stdout.strip()}"
        )
    merged = run(main_worktree, "merge", "--ff-only", base_oid)
    landed = run(main_worktree, "rev-parse", "HEAD")
    if merged.returncode == 0 and landed.returncode == 0 and landed.stdout.strip() == base_oid:
        print(f"Advanced main worktree {main_worktree} to {base} ({base_oid[:12]})")
        return None
    ahead = run(repository, "merge-base", "--is-ancestor", base_oid, current.stdout.strip())
    if ahead.returncode == 0:
        return (
            f"main worktree {main_worktree} is ahead of {base} at {base_oid[:12]}; "
            "push its commits or inspect before retiring"
        )
    detail = merged.stderr.strip().splitlines()
    return (
        f"main worktree {main_worktree} cannot fast-forward to {base} at "
        f"{base_oid[:12]}; rebase, reset, or inspect before retiring"
        + (f": {detail[-1]}" if detail else "")
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
        help="Verification base ref; must be a <remote> remote-tracking ref such "
        "as <remote>/main (default: <remote>/HEAD, falling back to <remote>/main).",
    )
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--board",
        default=None,
        type=Path,
        help="Coordination board for claim narrowing after removal "
        "(default: the board coordination.py uses).",
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
        try:
            resumed = resume_retirement(
                repository,
                worktree,
                args.branch,
                args.remote,
                delete_remote=args.delete_remote,
                board=args.board,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return fail(str(exc))
        if resumed is not None:
            return resumed
        _narrow_retired_claims(worktree, args.board, diagnose_only=True)
        return fail(f"{worktree} is not a worktree of {repository}")
    if Path(match["worktree"]).resolve() == main_worktree:
        return fail("refusing to retire the repository's main worktree")

    cwd = Path.cwd().resolve()
    if cwd == worktree.resolve() or worktree.resolve() in cwd.parents:
        return fail(
            "the current directory is inside the target worktree; leave it "
            "first"
        )

    # --ignored: every check retirement runs sees only tracked files, so a
    # worktree holding nothing but ignored content used to read clean and
    # take its ignored files with it on removal (intake 56: a 26 MB
    # gitignored data dump destroyed with no log line). Every non-clean
    # line — modified, untracked, or ignored — refuses with its disposition
    # recorded in the refusal.
    status = run(worktree, "status", "--ignored", "--porcelain")
    if status.returncode != 0:
        return fail(status.stderr.strip() or "status failed in the worktree")
    lines = [line for line in status.stdout.splitlines() if line.strip()]
    tracked = [line for line in lines if not line.startswith("!!")]
    ignored = [line for line in lines if line.startswith("!!")]
    if tracked:
        return fail(
            "worktree is not clean; commit, stash, or inspect before retiring:"
            f"\n{chr(10).join(tracked)}"
        )
    if ignored:
        return fail(
            "worktree holds ignored files that removal would destroy; extract "
            "what matters (or git clean what is truly regenerable) before "
            "retiring:"
            f"\n{chr(10).join(ignored)}"
        )

    branch_ref = match.get("branch", "")
    if branch_ref.startswith("refs/heads/"):
        branch = branch_ref[len("refs/heads/") :]
    elif not branch_ref and "detached" in match:
        branch = None
    else:
        return fail(f"worktree branch state cannot be verified: {branch_ref or 'missing'}")
    if args.branch and args.branch != branch:
        return fail(f"worktree is on {branch or 'detached HEAD'}, not the expected {args.branch}")

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
    resolved_name = symbolic_base.stdout.strip()
    if symbolic_base.returncode != 0 or not resolved_name.startswith(remote_prefix):
        if symbolic_base.returncode != 0:
            resolution = "does not resolve to any ref"
        elif resolved_name:
            resolution = f"resolves to {resolved_name}"
        else:
            # rev-parse exited 0 but printed no name: a revision expression
            # such as HEAD~0, or a short name that a local branch or tag
            # shadows (git reports that ambiguity only on stderr), so carry
            # git's own diagnosis rather than guessing the cause.
            resolution = "resolves to a commit but not to a single ref name"
            diagnosis = symbolic_base.stderr.strip().splitlines()
            if diagnosis:
                resolution += f" ({diagnosis[-1]})"
        return fail(
            f"verification base must be a freshly fetched {args.remote} "
            f"remote-tracking ref under {remote_prefix} (for example "
            f"{remote_prefix}main); received {base!r}, which {resolution}"
        )
    base = resolved_name
    base_check = run(repository, "rev-parse", "--verify", f"{base}^{{commit}}")
    if base_check.returncode != 0 or not base_check.stdout.strip():
        return fail(f"verification base does not resolve: {base}")
    base_oid = base_check.stdout.strip()

    head_result = run(worktree, "rev-parse", "HEAD")
    if head_result.returncode != 0 or not head_result.stdout.strip():
        return fail(head_result.stderr.strip() or "worktree HEAD is unavailable")
    head = head_result.stdout.strip()
    verified, method = content_verdict(repository, head, base_oid)
    if not verified:
        return fail(
            f"worktree HEAD {head} is not fully contained in {base}, and its "
            "tree differs from the base; its commits have not been verified "
            "on the remote"
        )
    print(f"Verified retirement content by {method}: {head[:12]} against {base} at {base_oid[:12]}")

    refusal = fast_forward_main_worktree(
        repository, entries, main_worktree, args.remote, base, base_oid
    )
    if refusal is not None:
        return fail(refusal)

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
                ] + (["--retirement-branch", branch] if branch else []),
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

    # Removal succeeded: the caller's cells under the retired tree are now
    # stale. Narrow them in the same step so the row never names a removed
    # checkout (intake 33). An incomplete cleanup remains an authenticated retry.
    if not _narrow_retired_claims(worktree, args.board):
        return fail("retirement is retained; caller claim cleanup requires an authenticated retry")

    if branch is None:
        print("Retired verified detached worktree; no branch cleanup was attempted")
        return 0
    return cleanup_branch(
        repository,
        branch,
        args.remote,
        head,
        base_ref=intent_data.get("base_ref"),
        base_oid=intent_data.get("base_oid"),
        delete_remote=args.delete_remote,
    )


if __name__ == "__main__":
    sys.exit(main())
