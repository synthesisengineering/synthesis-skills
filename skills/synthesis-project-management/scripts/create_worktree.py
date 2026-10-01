#!/usr/bin/env python3
"""Authenticated creation-only reservations for absent linked worktrees.

A reservation intersects physical claims but never grants file-edit authority.
The existing coordination owner publishes it before any target/Git mutation.
Failure retains the reservation and every partial worktree for exact recovery.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import coordination as C
from run_admission import bounded_lock
from coordination_process import run as run_effect

from fleet_paths import require_work_placement

PREFIX = "create:"


def fail(message):
    raise ValueError(message)


@contextmanager
def ancestry(path: Path):
    """Open every directory from / without symlinks; revalidate before effects."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or str(path) == "/":
        fail("creation path must be an absolute non-root path without traversal")
    held = []
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    held.append((None, "/", fd, os.fstat(fd)))
    try:
        for part in path.parts[1:]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            held.append((fd, part, child, os.fstat(child)))
            fd = child

        def verify():
            for parent, name, descriptor, before in held:
                now = os.stat(name, dir_fd=parent, follow_symlinks=False)

                def identity(value):
                    return value.st_dev, value.st_ino, value.st_mode

                if identity(now) != identity(before) or identity(
                    os.fstat(descriptor)
                ) != identity(before):
                    fail("creation ancestry changed")
            return fd

        verify()
        yield verify
        verify()
    finally:
        for _, _, descriptor, _ in reversed(held):
            os.close(descriptor)


def _git(repository, *args):
    return run_effect(["git", "-C", str(repository), *args], cwd=repository, timeout=60)


def _repository(repository):
    # Native discovery binds the actual registered checkout and common dir.
    scopes = C.claim_scope.ClaimScopeResolver()
    common, root = scopes._identity(str(repository))
    if root != str(repository):
        fail("repository must be the exact registered checkout root")
    return common


def _owner(board, sessions, selector):
    owner = C.find_session(sessions, selector)
    caller = C.detect_self()
    # Strong selectors still name a row; only the native handle authenticates it.
    if (
        owner is None
        or not C.active(owner)
        or not caller.harness_session_id
        or not caller.client
        or not C._caller_owns_session(board, owner, caller=caller)
    ):
        fail(
            "creation requires an active exact native owner; aliases are not authority"
        )
    return owner


def reserve(board, selector, target, repository, *, fixture_deadline=None):
    target, repository = Path(target), Path(repository)
    if target.name in {"", ".", ".."} or any(c in str(target) for c in "*?[,;\n\r|"):
        fail("creation target must be an exact path")
    placement = require_work_placement(target, fixture_deadline=fixture_deadline)
    token = PREFIX + str(target)
    # The board is Markdown: its parser/serializer is the exact authority format.
    # Refuse spellings it would normalize or split before publishing any claim.
    if C.split_values(C.sanitize(token)) != [token]:
        fail("creation target cannot be represented exactly on the coordination board")
    with ancestry(target.parent) as verify_parent, ancestry(repository) as verify_repo:
        common = _repository(repository)
        source_placement = require_work_placement(Path(common), fixture_deadline=fixture_deadline)

        def operation(text):
            require_work_placement(target, fixture_deadline=fixture_deadline)
            require_work_placement(Path(common), fixture_deadline=fixture_deadline)
            verify_parent()
            verify_repo()
            try:
                os.stat(target.name, dir_fd=verify_parent(), follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                fail("creation target already exists; no reservation granted")
            sessions = C.rows(text, strict=True)
            own = _owner(board, sessions, selector)
            changed = replace(own, claims=list(dict.fromkeys([*own.claims, token])))
            prospective = [
                changed if s.session_uuid == own.session_uuid else s for s in sessions
            ]
            problems = C.validate_sessions(prospective)
            if problems:
                fail("creation claim refused: " + "; ".join(problems))
            return C.replace_table(text, prospective)

        C.locked_update(board, operation, require_fence=True, lock_timeout=5)
        return {
            "reservation": token,
            "target": str(target),
            "repository": str(repository),
            "common": common,
            "placement": placement,
            "source_placement": source_placement,
        }


def create(board, selector, target, repository, branch, ref="HEAD", *, fixture_deadline=None):
    """Reserve, create, verify, then release only this creation reservation.

    There is no retry after native Git begins. A failed/partial creation is
    retained and reports refusal; no deletion, reset, force or peer release.
    """
    target, repository, board = Path(target), Path(repository), Path(board)
    if not isinstance(branch, str) or not branch or branch.startswith("-"):
        fail("an explicit new branch is required")
    if not isinstance(ref, str) or not ref or ref.startswith("-"):
        fail("an explicit commit-ish is required")
    require_work_placement(target, fixture_deadline=fixture_deadline)
    with (
        ancestry(board.parent),
        bounded_lock(board.parent / ".worktree-create.lock", timeout=5),
    ):
        receipt = reserve(board, selector, target, repository, fixture_deadline=fixture_deadline)
        # Keep local board ownership serialized through creation. Remote lease
        # admission is fenced before the effect, never executed in a CAS callback.
        with bounded_lock(board.parent / ".active-sessions.lock", timeout=5):
            config = C.lease_configuration(board)
            if config is not None:
                C.lease_update(board, config, lambda text: text, require_fence=True)
            text = board.read_text(encoding="utf-8")
            if config is None and C.declared_lease(text):
                fail("declared coordination lease has no local configuration")
            own = _owner(board, C.rows(text, strict=True), selector)
            if receipt["reservation"] not in own.claims:
                fail("creation reservation was removed before execution")
            with (
                ancestry(target.parent) as verify_parent,
                ancestry(repository) as verify_repo,
            ):
                verify_repo()
                parent_fd = verify_parent()
                if _repository(repository) != receipt["common"]:
                    fail("repository identity changed after admission")
                try:
                    os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    fail(
                        "target appeared after admission; retained without modification"
                    )
                # mkdirat pins the write to the admitted parent. Git receives
                # an empty owned directory; revalidation detects path replacement.
                require_work_placement(target, fixture_deadline=fixture_deadline)
                os.mkdir(target.name, 0o700, dir_fd=parent_fd)
                created = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
                verify_parent()
                verify_repo()
                require_work_placement(target, fixture_deadline=fixture_deadline)
                require_work_placement(Path(receipt["common"]), fixture_deadline=fixture_deadline)
                result = _git(
                    repository, "worktree", "add", "-b", branch, str(target), ref
                )
                if result.returncode:
                    fail(
                        "native creation failed; reservation and partial work retained: "
                        + (result.stderr or result.stdout).strip()
                    )
                verify_parent()
                verify_repo()
                current = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
                if (current.st_dev, current.st_ino) != (created.st_dev, created.st_ino):
                    fail("created target identity changed; reservation retained")
                if C.claim_scope.ClaimScopeResolver()._identity(str(target)) != (
                    receipt["common"],
                    str(target),
                ):
                    fail("created checkout does not bind the reserved repository")

        def finish(text):
            sessions = C.rows(text, strict=True)
            own = _owner(board, sessions, selector)
            if receipt["reservation"] not in own.claims:
                fail("creation reservation changed before conversion")
            # Workspace membership is part of staged-edit authority: adding a
            # checkout would expand existing relative claims into that tree.
            # Only a later explicit authenticated claim may change either set.
            changed = replace(
                own, claims=[c for c in own.claims if c != receipt["reservation"]]
            )
            prospective = [
                changed if s.session_uuid == own.session_uuid else s for s in sessions
            ]
            problems = C.validate_sessions(prospective)
            if problems:
                fail(
                    "created worktree retained; claim conversion refused: "
                    + "; ".join(problems)
                )
            return C.replace_table(text, prospective)

        C.locked_update(board, finish, require_fence=True, lock_timeout=5)
        return {
            **receipt,
            "status": "created-awaiting-workspace-and-edit-claim",
            "branch": branch,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--fixture-deadline", type=float, help="Explicit epoch deadline, at most 900 seconds away, for an ephemeral test fixture; never durable custody")
    args = parser.parse_args(argv)
    try:
        result = create(
            args.board,
            args.session,
            args.target,
            args.repository,
            args.branch,
            args.ref,
            fixture_deadline=args.fixture_deadline,
        )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("worktree creation REFUSED: " + str(exc), file=sys.stderr)
        return 10
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
