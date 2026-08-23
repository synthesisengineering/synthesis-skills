#!/usr/bin/env python3
"""
checkpoint_sync.py — Local handoff receipts and explicit remote publication.

The REMEDIATOR layer of synthesis-repo-guard (see SKILL.md for the full
three-layer design). Invoked at WORKFLOW EVENTS, never on a wall-clock timer:

  - AI-tool Stop records a LOCAL_READY receipt for one client session
  - synthesis-console records a producer path without committing or networking
  - day-end and synthesis-mac-sync publish pending context with
    ``--flush-pending``

Design rules (agreed 2026-07-08; companion lesson
2026-07-08-alert-channel-confidentiality-and-event-driven-checkpoints):

  1. NO background mutation. Stop and producer events write atomic local
     receipts only. Network publication is an explicit remote-handoff or
     day-end event.
  2. RUNTIME REMOTE GUARD: regardless of config, a context repo is published
     only if every push remote matches an allowed private namespace.
  3. Source-code paths are evidence, never auto-commit targets. Their owning
     workflow must commit and publish them before pending context manifests
     are retired.
  4. Safe publication: exact context paths only, then fetch, then a normal
     fast-forward push. Never rebase, force-push, or bypass hooks.
  5. Existing staged and dirty paths outside the manifest remain untouched.
  6. Alerts are GENERIC on audio/banner surfaces (no repo/client names —
     same rule as repo_sync_check.py); detail goes to the state file that
     synthesis-console renders.

Config: ~/.synthesis/checkpoint-sync.yaml (see checkpoint-sync.example.yaml).
State:  ~/.synthesis/repo-guard/checkpoint-state.json plus per-session pending manifests.

Exit codes: 0 = requested readiness reached; 1 = attention required; 2 = error.

Examples:
  ./checkpoint_sync.py --hook --quiet        # same-machine Stop receipt
  ./checkpoint_sync.py --repo ~/x/plan.md --now   # local producer receipt
  ./checkpoint_sync.py --flush-pending       # explicit remote handoff
  ./checkpoint_sync.py --flush-session ID    # exact-session remote handoff
  ./checkpoint_sync.py --dry-run             # preview remote handoff
"""

import argparse
import fcntl
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# SYNTHESIS_HOME overrides the state root (tests, sandboxes). Default ~/.synthesis
SYNTHESIS_HOME = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
CONFIG_PATH = SYNTHESIS_HOME / "checkpoint-sync.yaml"
STATE_DIR = SYNTHESIS_HOME / "repo-guard"
STATE_FILE = STATE_DIR / "checkpoint-state.json"
QUIET_AUDIO_FLAG = SYNTHESIS_HOME / "quiet-audio"
PENDING_DIR = STATE_DIR / "pending"
LOCAL_HANDOFF_DIR = STATE_DIR / "local-handoff"
REMOTE_HANDOFF_STATE = STATE_DIR / "remote-handoff-last.json"
RETIREMENT_DIR = STATE_DIR / "retired-worktrees"
LIFECYCLE_LOCK_FD_ENV = "SYNTHESIS_LIFECYCLE_LOCK_FD"
_LIFECYCLE_LOCK_STATE = threading.local()

DEFAULTS = {
    "repos": [],
    "repo_globs": [],
    "allowed_remote_prefixes": [],
    "commit_author_name": "Synthesis Checkpoint",
    "commit_author_email": "checkpoint@synthesisengineering.org",
}


# ---------------------------------------------------------------------------
# Config — PyYAML if present, else a minimal parser for the flat subset used
# ---------------------------------------------------------------------------

def _mini_yaml(text: str) -> dict:
    """Parse the restricted YAML subset this config uses: top-level
    `key: value` scalars and `key:` followed by `- item` lists. Comments and
    blank lines ignored. Sufficient and dependency-free."""
    data: dict = {}
    current_list = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_list is None:
                raise ValueError(f"list item outside a list key: {raw!r}")
            data[current_list].append(line.split("- ", 1)[1].strip().strip("'\""))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip().strip("'\"")
            if value == "":
                data[key] = []
                current_list = key
            else:
                data[key] = value
                current_list = None
    return data


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _mini_yaml(text)


def resolve_config(path: Path) -> dict:
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in load_config(path).items() if v is not None})
    return cfg


def configured_repos(cfg: dict) -> list[Path]:
    """Expand explicit paths + globs into existing repo paths (deduped)."""
    found: list[Path] = []
    seen = set()
    for entry in cfg.get("repos", []):
        p = Path(os.path.expanduser(str(entry)))
        if p.is_dir() and (p / ".git").exists() and str(p) not in seen:
            seen.add(str(p))
            found.append(p)
    for pattern in cfg.get("repo_globs", []):
        pattern = os.path.expanduser(str(pattern))
        # Glob over the filesystem: expand each path segment via Path.glob
        base = Path("/")
        try:
            import glob as _glob
            for hit in sorted(_glob.glob(pattern)):
                p = Path(hit)
                if p.is_dir() and (p / ".git").exists() and str(p) not in seen:
                    seen.add(str(p))
                    found.append(p)
        except Exception:
            continue
    return found


def pending_manifest_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return PENDING_DIR / f"{digest}.json"


def atomic_json(path: Path, payload: dict) -> None:
    validate_state_paths(path.parent, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    validate_state_paths(path.parent, path)
    if path.is_symlink():
        raise ValueError(f"refusing to replace symlinked state path: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        directory_fd = os.open(
            path.parent,
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


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def validate_state_paths(*paths: Path) -> None:
    """Reject any existing symlink component in a state mutation path."""

    for value in paths:
        path = lexical_absolute(value)
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            if os.path.lexists(current) and current.is_symlink():
                raise ValueError(f"state path contains a symlink component: {current}")


def lifecycle_lock_path() -> Path:
    return PENDING_DIR.parent / "lifecycle.lock"


def open_lock_file(path: Path) -> int:
    validate_state_paths(path.parent, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    validate_state_paths(path.parent, path)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"state lock is not a regular file: {path}")
    return descriptor


def inherited_lifecycle_lock_fd(path: Path) -> int | None:
    raw = os.environ.get(LIFECYCLE_LOCK_FD_ENV)
    if raw is None:
        return None
    try:
        descriptor = int(raw)
        inherited = os.fstat(descriptor)
        expected = os.stat(path, follow_symlinks=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"inherited lifecycle lock is invalid: {exc}") from exc
    if (inherited.st_dev, inherited.st_ino) != (expected.st_dev, expected.st_ino):
        raise ValueError("inherited lifecycle lock does not match the state lock")
    if not stat.S_ISREG(inherited.st_mode):
        raise ValueError("inherited lifecycle lock is not a regular file")
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return descriptor


@contextmanager
def lifecycle_lock():
    """Serialize every pending-manifest, receipt, and retirement mutation."""

    depth = getattr(_LIFECYCLE_LOCK_STATE, "depth", 0)
    if depth:
        _LIFECYCLE_LOCK_STATE.depth = depth + 1
        try:
            yield
        finally:
            _LIFECYCLE_LOCK_STATE.depth -= 1
        return

    path = lifecycle_lock_path()
    validate_state_paths(
        path.parent, path, PENDING_DIR, LOCAL_HANDOFF_DIR, RETIREMENT_DIR
    )
    inherited = inherited_lifecycle_lock_fd(path)
    descriptor = inherited if inherited is not None else open_lock_file(path)
    if inherited is None:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    _LIFECYCLE_LOCK_STATE.depth = 1
    try:
        yield
    finally:
        _LIFECYCLE_LOCK_STATE.depth = 0
        if inherited is None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git(repo: Path, *args: str, timeout: int = 60, env: dict | None = None,
        strip: bool = True) -> tuple[int, str, str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        r = subprocess.run(
            ["git", "-C", str(repo)] + list(args),
            capture_output=True, text=True, timeout=timeout, env=merged_env,
        )
        out = r.stdout.strip() if strip else r.stdout
        return r.returncode, out, r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except FileNotFoundError:
        return -1, "", "git not found"


def remote_guard(repo: Path, allowed_prefixes: list[str]) -> tuple[bool, str]:
    """A repo may be auto-touched only if every push remote URL starts with an
    allowed prefix. Empty allowed list => guard fails (fail closed)."""
    if not allowed_prefixes:
        return False, "no allowed_remote_prefixes configured (fail closed)"
    rc, out, err = git(repo, "remote", "-v")
    if rc != 0:
        return False, f"git remote failed: {err or out}"
    push_urls = [
        line.split()[1]
        for line in out.splitlines()
        if line.strip().endswith("(push)") and len(line.split()) >= 2
    ]
    if not push_urls:
        return False, "no push remotes"
    for url in push_urls:
        if not any(url.startswith(p) for p in allowed_prefixes):
            return False, f"push remote outside allowed namespace: {url}"
    return True, "ok"


def dirty_paths(repo: Path) -> list[str]:
    # strip=False: porcelain lines for unstaged states begin with a SPACE
    # (" M path"). A global strip() eats that space on the FIRST line and the
    # fixed-width `line[3:]` slice then chops the path's first character.
    # (Found live 2026-07-08: producer mode saw "rojects/…" and matched nothing.)
    rc, out, _ = git(
        repo, "status", "--porcelain", "--untracked-files=all", strip=False
    )
    if rc != 0 or not out.strip():
        return []
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        # porcelain v1: two status chars, one space, then the path
        # (or `old -> new` for renames)
        p = line[3:]
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        p = p.strip().strip('"')
        if p:
            paths.append(p)
    return paths


def ahead_behind(repo: Path, branch: str) -> tuple[int, int]:
    rc, out, _ = git(repo, "rev-list", "--left-right", "--count", f"origin/{branch}...{branch}")
    if rc != 0:
        return (-1, -1)
    parts = out.split()
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])  # (behind, ahead)
    return (-1, -1)


def git_common_dir(repo: Path) -> Path | None:
    rc, output, _ = git(repo, "rev-parse", "--git-common-dir")
    if rc != 0 or not output:
        return None
    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve()


def git_path(repo: Path, name: str) -> Path | None:
    rc, output, _ = git(repo, "rev-parse", "--git-path", name)
    if rc != 0 or not output:
        return None
    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = repo / candidate
    return candidate.resolve(strict=False)


def configured_repo_identity(repo: Path, cfg: dict) -> tuple[bool, str]:
    """Accept configured checkouts and their isolated git worktrees.

    A feature worktree is a separate filesystem path but shares the configured
    checkout's git common directory. Comparing that identity keeps the
    auto-sync class narrow without excluding the worktrees synthesis uses for
    concurrent projects.
    """
    identity = git_common_dir(repo)
    if identity is None:
        return False, "git common directory is unavailable"
    configured = configured_repos(cfg)
    configured_identities = {
        candidate_identity
        for candidate in configured
        if (candidate_identity := git_common_dir(candidate)) is not None
    }
    if identity not in configured_identities:
        return False, "repository is outside the configured auto-sync class"
    return True, "ok"


def remote_branch_exists(repo: Path, branch: str) -> bool:
    rc, _, _ = git(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}")
    return rc == 0


def finish_sync(
    repo: Path,
    branch: str,
    rec: dict,
    *,
    committed: bool,
    dry_run: bool,
) -> dict:
    """Fetch and fast-forward-push one branch, including its first push."""
    rc, _, err = git(repo, "fetch", "origin", timeout=120)
    if rc != 0:
        rec.update(
            action="committed-no-push" if committed else "fetch-failed",
            alert=f"fetch failed (offline?): {err[:200]}",
        )
        return rec

    if not remote_branch_exists(repo, branch):
        if not committed:
            rec.update(action="unpublished-branch", alert=f"origin/{branch} does not exist")
            return rec
        if dry_run:
            rec.update(action="would-publish-branch")
            return rec
        rc, out, err = git(repo, "push", "--set-upstream", "origin", branch, timeout=180)
        if rc != 0:
            rec.update(action="committed-push-failed", alert=f"push failed: {(err or out)[:200]}")
            return rec
        rec.update(action="committed-pushed", ahead=1)
        return rec

    behind, ahead = ahead_behind(repo, branch)
    if behind < 0 or ahead < 0:
        rec.update(
            action="committed-unverifiable" if committed else "unverifiable",
            alert=f"could not compare the local branch with origin/{branch}",
        )
        return rec
    if ahead > 0:
        if behind > 0:
            rec.update(
                action="committed-diverged" if committed else "diverged",
                alert=(
                    f"diverged from origin/{branch} (ahead {ahead}, behind {behind}) "
                    "— resolve manually; commit is safe locally"
                ),
            )
            return rec
        if dry_run:
            rec.update(action="would-push", ahead=ahead)
            return rec
        rc, out, err = git(repo, "push", "origin", branch, timeout=180)
        if rc != 0:
            rec.update(
                action="committed-push-failed" if committed else "push-failed",
                alert=f"push failed: {(err or out)[:200]}",
            )
            return rec
        rec.update(action="committed-pushed" if committed else "pushed-stranded", ahead=ahead)
    elif behind > 0:
        rec.update(
            action="committed-diverged" if committed else "behind",
            alert=(
                f"local branch is behind origin/{branch} by {behind} commit(s); "
                "fast-forward before declaring remote readiness"
            ),
        )
    elif committed:
        rec.update(action="committed-pushed")
    else:
        rec.update(action="clean")
    return rec


# ---------------------------------------------------------------------------
# Checkpoint core
# ---------------------------------------------------------------------------

def summarize_paths(paths: list[str], limit: int = 3) -> str:
    shown = ", ".join(paths[:limit])
    extra = len(paths) - limit
    return shown + (f" +{extra} more" if extra > 0 else "")


def repo_root_for_path(path: Path) -> Path | None:
    probe = path if path.is_dir() else path.parent
    rc, output, _ = git(probe, "rev-parse", "--show-toplevel")
    return Path(output).resolve() if rc == 0 and output else None


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def listed_worktree_roots(repository: Path) -> tuple[list[Path], str | None]:
    rc, output, error = git(repository, "worktree", "list", "--porcelain")
    if rc != 0:
        return [], error or output or "git worktree list failed"
    roots = [
        Path(line.partition(" ")[2]).resolve(strict=False)
        for line in output.splitlines()
        if line.startswith("worktree ")
    ]
    return roots, None


def fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def retirement_result(repository: Path | str) -> dict:
    return {
        "repo": str(repository),
        "name": "retired-worktree",
        "action": "retirement-reconcile-failed",
        "alert": None,
    }


def validate_retirement_target(
    worktree: Path, repository: Path, *, expect_active: bool
) -> tuple[Path, Path]:
    repository_input = lexical_absolute(repository)
    worktree_input = lexical_absolute(worktree)
    if repository_input.is_symlink():
        raise ValueError("repository path is a symlink")
    if worktree_input.is_symlink():
        raise ValueError("retired worktree path is a symlink")
    try:
        repository = repository_input.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"repository is unavailable: {exc}") from exc
    worktree = worktree_input.resolve(strict=False)

    unsafe_roots = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if worktree in unsafe_roots:
        raise ValueError(f"unsafe retired-worktree root: {worktree}")
    if (
        worktree == repository
        or worktree in repository.parents
        or repository in worktree.parents
    ):
        raise ValueError("retired worktree overlaps the repository root")

    top_rc, top, top_error = git(repository, "rev-parse", "--show-toplevel")
    if top_rc != 0 or not top or Path(top).resolve() != repository:
        raise ValueError(top_error or "repository is not its git toplevel")

    worktrees, worktree_error = listed_worktree_roots(repository)
    if worktree_error:
        raise ValueError(worktree_error)
    target_is_active = worktree in worktrees
    if expect_active:
        if not target_is_active or not worktree.is_dir():
            raise ValueError("retirement preparation requires the exact active worktree")
    elif target_is_active or os.path.lexists(worktree):
        raise ValueError("retired worktree still exists or remains registered")
    return worktree, repository


def fetched_remote_base(
    repository: Path, remote: str, base: str
) -> tuple[str, str]:
    if not remote or any(character.isspace() for character in remote):
        raise ValueError("retirement remote name is invalid")
    fetch_rc, _, fetch_error = git(repository, "fetch", "--quiet", "--prune", remote)
    if fetch_rc != 0:
        raise ValueError(f"retirement remote fetch failed: {fetch_error}")
    full_rc, full_ref, full_error = git(
        repository, "rev-parse", "--symbolic-full-name", base
    )
    prefix = f"refs/remotes/{remote}/"
    if full_rc != 0 or not full_ref.startswith(prefix):
        raise ValueError(
            full_error
            or f"retirement base must be a fetched {remote} remote-tracking ref"
        )
    base_rc, base_oid, base_error = git(
        repository, "rev-parse", "--verify", f"{full_ref}^{{commit}}"
    )
    if base_rc != 0 or not base_oid:
        raise ValueError(base_error or "retirement base does not resolve")
    return full_ref, base_oid


def canonical_retirement_commits(
    repository: Path, verified_head: str, base_oid: str
) -> tuple[str, str]:
    head_rc, canonical_head, head_error = git(
        repository, "rev-parse", "--verify", f"{verified_head}^{{commit}}"
    )
    base_rc, canonical_base, base_error = git(
        repository, "rev-parse", "--verify", f"{base_oid}^{{commit}}"
    )
    if head_rc != 0 or not canonical_head:
        raise ValueError(head_error or "verified retirement head does not resolve")
    if base_rc != 0 or not canonical_base:
        raise ValueError(base_error or "pinned retirement base does not resolve")
    ancestry_rc, _, ancestry_error = git(
        repository, "merge-base", "--is-ancestor", canonical_head, canonical_base
    )
    if ancestry_rc != 0:
        raise ValueError(
            ancestry_error or "retired head is not contained in the pinned remote base"
        )
    return canonical_head, canonical_base


def retirement_intent_path(worktree: Path, head: str, base_oid: str) -> Path:
    identity = hashlib.sha256(
        f"{worktree}\0{head}\0{base_oid}".encode("utf-8")
    ).hexdigest()
    return RETIREMENT_DIR / f"{identity}.json"


def manifest_reconciliation_plans(
    worktree: Path,
) -> tuple[list[tuple[Path, dict, list[str], list[str], list[str]]], list[object]]:
    validate_state_paths(PENDING_DIR, LOCAL_HANDOFF_DIR, RETIREMENT_DIR)
    manifests = sorted(PENDING_DIR.glob("*.json")) if PENDING_DIR.is_dir() else []
    plans: list[tuple[Path, dict, list[str], list[str], list[str]]] = []
    locks: list[object] = []
    try:
        for manifest in manifests:
            lock_path = manifest.with_suffix(".lock")
            descriptor = open_lock_file(lock_path)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            lock = os.fdopen(descriptor, "a+", encoding="utf-8")
            locks.append(lock)
            if manifest.is_symlink():
                raise ValueError(f"pending manifest is a symlink: {manifest}")
            if not manifest.exists():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            session_id = data.get("session_id")
            if (
                not isinstance(session_id, str)
                or pending_manifest_path(session_id) != manifest
            ):
                raise ValueError(f"pending manifest filename or session mismatch: {manifest}")
            paths = data.get("paths")
            remote_paths = data.get("remote_paths", paths)
            if not isinstance(paths, list) or not isinstance(remote_paths, list):
                raise ValueError(f"pending manifest path arrays are invalid: {manifest}")
            if any(
                not isinstance(value, str) or not Path(value).expanduser().is_absolute()
                for value in [*paths, *remote_paths]
            ):
                raise ValueError(
                    f"pending manifest paths must be absolute strings: {manifest}"
                )
            if not set(remote_paths).issubset(set(paths)):
                raise ValueError(f"pending remote_paths are not a subset of paths: {manifest}")
            history = data.get("retired_worktrees", [])
            if not isinstance(history, list):
                raise ValueError(f"retired_worktrees history is invalid: {manifest}")

            removed = [
                value
                for value in paths
                if path_is_within(Path(value).expanduser(), worktree)
            ]
            if not removed:
                continue
            remaining = [value for value in paths if value not in set(removed)]
            remaining_remote = [
                value for value in remote_paths if value not in set(removed)
            ]
            receipt = LOCAL_HANDOFF_DIR / manifest.name
            validate_state_paths(receipt)
            if receipt.is_symlink():
                raise ValueError(f"local handoff receipt is a symlink: {receipt}")
            plans.append((manifest, data, removed, remaining, remaining_remote))
        return plans, locks
    except Exception:
        for lock in reversed(locks):
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()
        raise


def release_manifest_locks(locks: list[object]) -> None:
    for lock in reversed(locks):
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def prepare_retirement_intent(
    worktree: Path,
    repository: Path,
    verified_head: str,
    remote: str,
    base: str,
    *,
    branch: str | None = None,
    expect_active: bool,
    dry_run: bool,
) -> tuple[dict, Path | None, list[Path]]:
    worktree, repository = validate_retirement_target(
        worktree, repository, expect_active=expect_active
    )
    base_ref, fetched_base_oid = fetched_remote_base(repository, remote, base)
    canonical_head, canonical_base = canonical_retirement_commits(
        repository, verified_head, fetched_base_oid
    )
    plans, locks = manifest_reconciliation_plans(worktree)
    try:
        touched = [plan[0] for plan in plans]
        intent = retirement_intent_path(worktree, canonical_head, canonical_base)
        result = retirement_result(repository)
        result.update(
            action="retirement-prepared" if not dry_run else "retirement-prepare-ready",
            manifests=len(plans),
            files=sum(len(plan[2]) for plan in plans),
            detail=str(intent),
        )
        if dry_run:
            return result, None, touched
        prepared_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        reconciler_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        atomic_json(
            intent,
            {
                "schema_version": 2,
                "state": "prepared",
                "mode": "normal" if expect_active else "recovery",
                "worktree": str(worktree),
                "repository": str(repository),
                "head": canonical_head,
                "remote": remote,
                "base_ref": base_ref,
                "base_oid": canonical_base,
                "branch": branch,
                "prepared_at": prepared_at,
                "reconciler_sha256": reconciler_hash,
                "manifests_preflight": [str(path) for path in touched],
                "paths_preflight": sum(len(plan[2]) for plan in plans),
            },
        )
        return result, intent, touched
    finally:
        release_manifest_locks(locks)


def load_retirement_intent(intent: Path) -> dict:
    intent = lexical_absolute(intent)
    expected_root = lexical_absolute(RETIREMENT_DIR)
    try:
        intent.relative_to(expected_root)
    except ValueError as exc:
        raise ValueError("retirement intent is outside the retirement state directory") from exc
    validate_state_paths(expected_root, intent)
    if intent.is_symlink() or not intent.is_file():
        raise ValueError(f"retirement intent is unavailable or unsafe: {intent}")
    data = json.loads(intent.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2 or data.get("state") not in {
        "prepared",
        "completed",
    }:
        raise ValueError("retirement intent schema or state is invalid")
    return data


def complete_retirement_intent(intent: Path) -> tuple[dict, list[Path]]:
    intent = lexical_absolute(intent)
    data = load_retirement_intent(intent)
    repository = Path(str(data.get("repository") or ""))
    result = retirement_result(repository)
    worktree, repository = validate_retirement_target(
        Path(str(data.get("worktree") or "")), repository, expect_active=False
    )
    remote = data.get("remote")
    base_ref = data.get("base_ref")
    if (
        not isinstance(remote, str)
        or not isinstance(base_ref, str)
        or not base_ref.startswith(f"refs/remotes/{remote}/")
    ):
        raise ValueError("retirement intent has no valid remote-tracking authority")
    canonical_head, canonical_base = canonical_retirement_commits(
        repository,
        str(data.get("head") or ""),
        str(data.get("base_oid") or ""),
    )
    if intent != retirement_intent_path(worktree, canonical_head, canonical_base):
        raise ValueError("retirement intent filename does not match its identity")
    reconciler_hash = data.get("reconciler_sha256")
    current_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if (
        not isinstance(reconciler_hash, str)
        or len(reconciler_hash) != 64
        or any(character not in "0123456789abcdef" for character in reconciler_hash)
        or reconciler_hash != current_hash
    ):
        raise ValueError("retirement intent is not running under its pinned reconciler")
    if data["state"] == "completed":
        result.update(
            action="retired-worktree-reconciled",
            manifests=len(data.get("manifests", [])),
            files=int(data.get("paths_removed", 0)),
            detail=str(intent),
        )
        return result, [Path(value) for value in data.get("manifests", [])]
    plans, locks = manifest_reconciliation_plans(worktree)
    try:
        reconciled_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        touched: list[Path] = []
        removed_count = 0
        for manifest, manifest_data, removed, remaining, remaining_remote in plans:
            receipt = LOCAL_HANDOFF_DIR / manifest.name
            if os.path.lexists(receipt):
                receipt.unlink()
                fsync_directory(receipt.parent)
            removed_count += len(removed)
            touched.append(manifest)
            if not remaining:
                manifest.unlink(missing_ok=True)
                fsync_directory(manifest.parent)
                continue
            history = manifest_data.get("retired_worktrees", [])
            history.append(
                {
                    "intent": str(intent),
                    "worktree": str(worktree),
                    "repository": str(repository),
                    "head": canonical_head,
                    "base_ref": data.get("base_ref"),
                    "base_oid": canonical_base,
                    "reconciled_at": reconciled_at,
                    "paths_removed": len(removed),
                }
            )
            manifest_data.update(
                updated_at=reconciled_at,
                paths=remaining,
                remote_paths=remaining_remote,
                retired_worktrees=history,
            )
            atomic_json(manifest, manifest_data)

        data.update(
            state="completed",
            completed_at=reconciled_at,
            manifests=[str(path) for path in touched],
            paths_removed=removed_count,
        )
        atomic_json(intent, data)
        result.update(
            action="retired-worktree-reconciled",
            manifests=len(touched),
            files=removed_count,
            detail=str(intent),
        )
        return result, touched
    finally:
        release_manifest_locks(locks)


def reconcile_retired_worktree(
    worktree: Path,
    repository: Path,
    verified_head: str,
    base: str,
    *,
    remote: str = "origin",
    dry_run: bool,
) -> tuple[list[dict], list[Path]]:
    """Recover a retirement that predates durable prepared-intent records."""

    result = retirement_result(repository)
    try:
        with lifecycle_lock():
            prepared, intent, touched = prepare_retirement_intent(
                worktree,
                repository,
                verified_head,
                remote,
                base,
                expect_active=False,
                dry_run=dry_run,
            )
            if dry_run:
                return [prepared], touched
            assert intent is not None
            completed, reconciled = complete_retirement_intent(intent)
            return [completed], reconciled
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result["alert"] = str(exc)
        return [result], []


def checkpoint_explicit_paths(repo: Path, paths: list[Path], cfg: dict, *, dry_run: bool) -> dict:
    """Checkpoint only files attributed to one client session."""
    rec: dict = {"repo": str(repo), "name": repo.name, "action": "none", "alert": None}
    configured, reason = configured_repo_identity(repo, cfg)
    if not configured:
        rec.update(action="guard-rejected", alert=reason)
        return rec
    ok, reason = remote_guard(repo, cfg["allowed_remote_prefixes"])
    if not ok:
        rec.update(action="guard-rejected", alert=f"remote guard: {reason}")
        return rec
    lock = git_path(repo, "index.lock")
    if lock is not None and lock.exists():
        rec.update(action="skipped-lock-active", alert="git index.lock is present")
        return rec

    rc, branch, _ = git(repo, "branch", "--show-current")
    if rc != 0 or not branch:
        rec.update(action="skipped", alert="detached HEAD or no branch")
        return rec

    relative: list[str] = []
    for path in paths:
        try:
            rel = str(path.resolve(strict=False).relative_to(repo.resolve()))
        except ValueError:
            rec.update(action="guard-rejected", alert=f"pending path is outside repository: {path}")
            return rec
        relative.append(rel)
    relative = sorted(set(relative))

    dirty = set(dirty_paths(repo))
    changed = [path for path in relative if path in dirty]
    committed = False
    if changed:
        if dry_run:
            rec.update(action="would-commit", files=len(changed), detail=summarize_paths(changed))
            return rec
        intent_paths: list[str] = []
        for path in changed:
            tracked_rc, _, _ = git(repo, "ls-files", "--error-unmatch", "--", path)
            if tracked_rc == 0:
                continue
            add_rc, _, add_error = git(repo, "add", "--intent-to-add", "--", path)
            if add_rc != 0:
                rec.update(
                    action="failed",
                    alert=f"could not prepare untracked context path: {add_error}",
                )
                return rec
            intent_paths.append(path)
        author_env = {
            "GIT_AUTHOR_NAME": cfg["commit_author_name"],
            "GIT_AUTHOR_EMAIL": cfg["commit_author_email"],
            "GIT_COMMITTER_NAME": cfg["commit_author_name"],
            "GIT_COMMITTER_EMAIL": cfg["commit_author_email"],
        }
        rc, out, err = git(
            repo,
            "commit",
            "-m",
            "Update project context",
            "--only",
            "--",
            *changed,
            env=author_env,
            timeout=120,
        )
        if rc != 0:
            if intent_paths:
                git(repo, "reset", "--", *intent_paths)
            rec.update(action="hook-blocked", alert=f"commit blocked: {(err or out)[:300]}")
            return rec
        committed = True
        rec.update(files=len(changed), detail=summarize_paths(changed))

    return finish_sync(repo, branch, rec, committed=committed, dry_run=dry_run)


def load_pending_manifest(session_id: str) -> tuple[Path, list[Path]]:
    manifest = pending_manifest_path(session_id)
    if manifest.is_symlink():
        raise ValueError(f"pending manifest is a symlink: {manifest}")
    if not manifest.is_file():
        return manifest, []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("session_id") != session_id or not isinstance(data.get("paths"), list):
        raise ValueError("session or paths mismatch")
    return manifest, [Path(str(value)).expanduser() for value in data["paths"]]


def file_evidence(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "state": "deleted-or-missing"}
    if path.is_symlink() or not path.is_file():
        return {"path": str(path), "state": "unsafe-non-file"}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path),
        "state": "present",
        "size": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def _local_handoff_checkpoint_unlocked(
    payload: dict, cfg: dict
) -> tuple[list[dict], Path | None]:
    """Record LOCAL_READY evidence without committing or using the network."""
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return [], None
    try:
        manifest, paths = load_pending_manifest(session_id)
    except (OSError, ValueError, TypeError) as exc:
        return [{"repo": "unknown", "name": "pending-session", "action": "failed", "alert": f"invalid pending manifest: {exc}"}], None
    if not paths:
        return [], manifest

    grouped: dict[Path, list[Path]] = {}
    for path in paths:
        root = repo_root_for_path(path)
        if root is None:
            return [{"repo": str(path), "name": "pending-session", "action": "failed", "alert": "pending path is not inside an available git worktree"}], manifest
        grouped.setdefault(root, []).append(path)

    results: list[dict] = []
    for repo, repo_paths in sorted(grouped.items(), key=lambda item: str(item[0])):
        branch_rc, branch, _ = git(repo, "branch", "--show-current")
        head_rc, head, _ = git(repo, "rev-parse", "HEAD")
        if branch_rc != 0 or not branch or head_rc != 0:
            results.append({"repo": str(repo), "name": repo.name, "action": "failed", "alert": "checkout identity is unavailable"})
            continue
        evidence = [file_evidence(path) for path in sorted(set(repo_paths))]
        unsafe = [item for item in evidence if item["state"] == "unsafe-non-file"]
        if unsafe:
            results.append({"repo": str(repo), "name": repo.name, "action": "guard-rejected", "alert": "pending path is a symlink or non-file"})
            continue
        results.append(
            {
                "repo": str(repo),
                "name": repo.name,
                "action": "local-ready",
                "branch": branch,
                "head": head,
                "files": len(evidence),
                "file_evidence": evidence,
                "alert": None,
            }
        )

    receipt = LOCAL_HANDOFF_DIR / f"{hashlib.sha256(session_id.encode('utf-8')).hexdigest()}.json"
    atomic_json(
        receipt,
        {
            "schema_version": 1,
            "readiness": "LOCAL_READY" if results and not any(item.get("alert") for item in results) else "BLOCKED",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session_id": session_id,
            "cwd": payload.get("cwd"),
            "results": results,
            "pending_manifest": str(manifest),
        },
    )
    return results, manifest


def local_handoff_checkpoint(payload: dict, cfg: dict) -> tuple[list[dict], Path | None]:
    with lifecycle_lock():
        return _local_handoff_checkpoint_unlocked(payload, cfg)


def _flush_pending_manifests_unlocked(
    cfg: dict, manifests: list[Path], *, dry_run: bool
) -> tuple[list[dict], list[Path]]:
    """Publish and retire exactly the supplied pending manifests."""
    all_paths: list[Path] = []
    source_paths: list[Path] = []
    valid_manifests: list[Path] = []
    errors: list[dict] = []
    locks = []
    try:
        for manifest in manifests:
            lock_path = manifest.with_suffix(".lock")
            try:
                descriptor = open_lock_file(lock_path)
            except (OSError, ValueError) as exc:
                errors.append({"repo": str(lock_path), "name": "pending-session", "action": "failed", "alert": str(exc)})
                continue
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            lock = os.fdopen(descriptor, "a+", encoding="utf-8")
            locks.append(lock)
            if manifest.is_symlink():
                errors.append({"repo": str(manifest), "name": "pending-session", "action": "failed", "alert": "pending manifest is a symlink"})
                continue
            if not manifest.exists():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                session_id = data.get("session_id")
                if not isinstance(session_id, str) or pending_manifest_path(session_id) != manifest:
                    raise ValueError("manifest filename or session mismatch")
                remote_paths = data.get("remote_paths", data.get("paths"))
                if not isinstance(remote_paths, list):
                    raise ValueError("remote_paths must be a list")
                all_values = data.get("paths")
                if not isinstance(all_values, list):
                    raise ValueError("paths must be a list")
                remote_set = {
                    Path(str(value)).expanduser().resolve(strict=False)
                    for value in remote_paths
                }
                all_set = {
                    Path(str(value)).expanduser().resolve(strict=False)
                    for value in all_values
                }
                all_paths.extend(remote_set)
                source_paths.extend(all_set - remote_set)
                valid_manifests.append(manifest)
            except (OSError, ValueError, TypeError) as exc:
                errors.append({"repo": str(manifest), "name": "pending-session", "action": "failed", "alert": f"invalid pending manifest: {exc}"})

        grouped: dict[Path, list[Path]] = {}
        for path in sorted(set(all_paths)):
            root = repo_root_for_path(path)
            if root is None:
                errors.append({"repo": str(path), "name": "pending-session", "action": "failed", "alert": "pending path is not inside an available git worktree"})
                continue
            grouped.setdefault(root, []).append(path)
        results = errors + source_paths_remote_ready(source_paths) + [
            checkpoint_explicit_paths(repo, paths, cfg, dry_run=dry_run)
            for repo, paths in sorted(grouped.items(), key=lambda item: str(item[0]))
        ]
        if not dry_run and valid_manifests and not any(result.get("alert") for result in results):
            for manifest in valid_manifests:
                manifest.unlink(missing_ok=True)
            fsync_directory(PENDING_DIR)
        return results, valid_manifests
    finally:
        for lock in reversed(locks):
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()


def _flush_all_pending_unlocked(
    cfg: dict, *, dry_run: bool
) -> tuple[list[dict], list[Path]]:
    """Batch every pending session into one exact-path commit per repository."""
    manifests = sorted(PENDING_DIR.glob("*.json")) if PENDING_DIR.is_dir() else []
    return _flush_pending_manifests_unlocked(cfg, manifests, dry_run=dry_run)


def flush_all_pending(cfg: dict, *, dry_run: bool) -> tuple[list[dict], list[Path]]:
    with lifecycle_lock():
        return _flush_all_pending_unlocked(cfg, dry_run=dry_run)


def flush_pending_session(
    cfg: dict, session_id: str, *, dry_run: bool
) -> tuple[list[dict], list[Path]]:
    """Publish and retire one exact session without inspecting unrelated manifests."""
    if not isinstance(session_id, str) or not session_id.strip():
        return [
            {
                "repo": "unknown",
                "name": "pending-session",
                "action": "failed",
                "alert": "session id must be a non-empty string",
            }
        ], []
    if len(session_id.encode("utf-8")) > 512 or any(
        ord(character) < 32 for character in session_id
    ):
        return [
            {
                "repo": "unknown",
                "name": "pending-session",
                "action": "failed",
                "alert": "session id contains unsafe characters or exceeds 512 bytes",
            }
        ], []
    manifest = pending_manifest_path(session_id)
    with lifecycle_lock():
        validate_state_paths(PENDING_DIR, manifest)
        if manifest.is_symlink():
            return [
                {
                    "repo": str(manifest),
                    "name": "pending-session",
                    "action": "failed",
                    "alert": "pending manifest is a symlink",
                }
            ], [manifest]
        if not manifest.exists():
            return [
                {
                    "repo": str(manifest),
                    "name": "pending-session",
                    "action": "session-clean",
                    "alert": None,
                }
            ], []
        return _flush_pending_manifests_unlocked(cfg, [manifest], dry_run=dry_run)


def source_paths_remote_ready(paths: list[Path]) -> list[dict]:
    """Verify source edits were published by their policy-owning workflow."""
    grouped: dict[Path, list[Path]] = {}
    results: list[dict] = []
    for path in sorted(set(paths)):
        root = repo_root_for_path(path)
        if root is None:
            results.append(
                {
                    "repo": str(path),
                    "name": "source-path",
                    "action": "source-unavailable",
                    "alert": "edited source path is not inside an available git worktree",
                }
            )
            continue
        grouped.setdefault(root, []).append(path)

    for repo, repo_paths in sorted(grouped.items(), key=lambda item: str(item[0])):
        relative = [str(path.resolve(strict=False).relative_to(repo.resolve())) for path in repo_paths]
        status_rc, status, status_error = git(
            repo, "status", "--porcelain", "--", *relative, strip=False
        )
        if status_rc != 0:
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-unverifiable",
                    "alert": f"source status failed: {status_error}",
                }
            )
            continue
        if status.strip():
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-local-only",
                    "alert": "edited source paths remain uncommitted",
                }
            )
            continue
        upstream_rc, upstream, _ = git(
            repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
        if upstream_rc != 0 or not upstream:
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-local-only",
                    "alert": "source branch has no upstream",
                }
            )
            continue
        branch_rc, branch, _ = git(repo, "branch", "--show-current")
        remote_rc, remote, _ = git(
            repo, "config", "--get", f"branch.{branch}.remote"
        )
        if branch_rc != 0 or not branch or remote_rc != 0 or not remote or remote == ".":
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-local-only",
                    "alert": "source branch has no fetchable remote",
                }
            )
            continue
        fetch_rc, _, fetch_error = git(repo, "fetch", remote, timeout=120)
        if fetch_rc != 0:
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-unverifiable",
                    "alert": f"source fetch failed: {fetch_error}",
                }
            )
            continue
        counts_rc, counts, counts_error = git(
            repo, "rev-list", "--left-right", "--count", f"{upstream}...HEAD"
        )
        if counts_rc != 0 or len(counts.split()) != 2:
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-unverifiable",
                    "alert": f"source upstream comparison failed: {counts_error}",
                }
            )
            continue
        behind, ahead = (int(value) for value in counts.split())
        if behind or ahead:
            results.append(
                {
                    "repo": str(repo),
                    "name": repo.name,
                    "action": "source-not-remote-ready",
                    "alert": f"source branch is ahead {ahead}, behind {behind}",
                }
            )
            continue
        results.append(
            {
                "repo": str(repo),
                "name": repo.name,
                "action": "source-remote-ready",
                "files": len(relative),
                "alert": None,
            }
        )
    return results


def record_producer_path(path: Path, cfg: dict) -> tuple[list[dict], Path | None]:
    """Record a console or other non-agent producer write as local state."""
    with lifecycle_lock():
        target = path.expanduser().resolve(strict=False)
        root = repo_root_for_path(target)
        if root is None:
            return [
                {
                    "repo": str(target),
                    "name": "producer",
                    "action": "failed",
                    "alert": "producer path is not inside an available git worktree",
                }
            ], None
        configured, reason = configured_repo_identity(root, cfg)
        if not configured:
            return [
                {
                    "repo": str(root),
                    "name": root.name,
                    "action": "guard-rejected",
                    "alert": reason,
                }
            ], None
        ok, reason = remote_guard(root, cfg["allowed_remote_prefixes"])
        if not ok:
            return [
                {
                    "repo": str(root),
                    "name": root.name,
                    "action": "guard-rejected",
                    "alert": f"remote guard: {reason}",
                }
            ], None
        session_id = f"producer:{os.getpid()}:{time.time_ns()}"
        manifest = pending_manifest_path(session_id)
        atomic_json(
            manifest,
            {
                "schema_version": 2,
                "session_id": session_id,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "paths": [str(target)],
                "remote_paths": [str(target)],
                "producer": True,
            },
        )
        return _local_handoff_checkpoint_unlocked(
            {"session_id": session_id, "cwd": str(root)}, cfg
        )


# ---------------------------------------------------------------------------
# Generic attention ping (same confidentiality rule as repo_sync_check)
# ---------------------------------------------------------------------------

def audio_muted() -> bool:
    return QUIET_AUDIO_FLAG.exists()


def generic_alert_ping(alert_count: int, speak: bool, notify: bool) -> None:
    if sys.platform != "darwin" or audio_muted():
        return
    noun = "item needs" if alert_count == 1 else "items need"
    msg = f"Repo checkpoint: {alert_count} {noun} your attention. Details are in your synthesis console."
    if notify:
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "Repo checkpoint"'],
            capture_output=True,
        )
    if speak:
        subprocess.run(["say", msg], capture_output=True)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def write_state(mode: str, results: list[dict], running: bool) -> None:
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": socket.gethostname(),
        "mode": mode,
        "running": running,
        "results": results,
        "alerts": [r for r in results if r.get("alert")],
    }
    atomic_json(STATE_FILE, payload)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG_PATH, help=f"Config path (default {CONFIG_PATH})")
    ap.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Record one non-agent producer path as local handoff state",
    )
    ap.add_argument(
        "--hook",
        action="store_true",
        help="Record same-machine handoff evidence from a client Stop payload",
    )
    ap.add_argument(
        "--flush-pending",
        action="store_true",
        help="Commit and push all session-attributed context paths for remote handoff",
    )
    ap.add_argument(
        "--flush-session",
        default=None,
        metavar="SESSION_ID",
        help="Commit, push, and retire one exact session manifest without inspecting other sessions",
    )
    ap.add_argument(
        "--reconcile-retired-worktree",
        type=Path,
        default=None,
        help="Remove paths beneath one verified retired worktree from pending manifests",
    )
    ap.add_argument(
        "--prepare-worktree-retirement",
        type=Path,
        default=None,
        help="Write a durable retirement intent before removing an active worktree",
    )
    ap.add_argument(
        "--complete-worktree-retirement",
        type=Path,
        default=None,
        help="Complete or resume reconciliation from a durable retirement intent",
    )
    ap.add_argument(
        "--retirement-repository",
        type=Path,
        default=None,
        help="Main repository that owned the retired worktree",
    )
    ap.add_argument(
        "--retirement-head",
        default=None,
        help="Exact commit that the retirement helper verified on the remote base",
    )
    ap.add_argument(
        "--retirement-base",
        default=None,
        help="Fetched remote-tracking ref that contains the retired head",
    )
    ap.add_argument(
        "--retirement-remote",
        default="origin",
        help="Remote whose freshly fetched tracking ref is the ancestry authority",
    )
    ap.add_argument(
        "--retirement-branch",
        default=None,
        help="Branch checked out by the prepared worktree",
    )
    ap.add_argument(
        "--now",
        action="store_true",
        help="Compatibility flag for local post-write producer mode",
    )
    ap.add_argument(
        "--no-throttle",
        action="store_true",
        help="Compatibility alias for an explicit remote handoff",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Preview remote publication"
    )
    ap.add_argument("--quiet", "-q", action="store_true", help="No stdout (state file still written)")
    ap.add_argument("--json", "-j", action="store_true", help="Print outcomes as JSON")
    ap.add_argument("--speak", action="store_true", help="Generic spoken ping if alerts (mute-aware)")
    ap.add_argument("--notify", action="store_true", help="Generic banner if alerts (mute-aware)")
    args = ap.parse_args()

    cfg = resolve_config(args.config.expanduser())

    retirement_modes = [
        args.reconcile_retired_worktree is not None,
        args.prepare_worktree_retirement is not None,
        args.complete_worktree_retirement is not None,
    ]
    if sum(retirement_modes) > 1:
        if not args.quiet:
            print("checkpoint_sync: choose exactly one retirement mode", file=sys.stderr)
        return 2

    if args.flush_session is not None and (
        args.hook
        or args.repo is not None
        or args.flush_pending
        or args.no_throttle
        or any(retirement_modes)
    ):
        if not args.quiet:
            print(
                "checkpoint_sync: --flush-session cannot be combined with another lifecycle mode",
                file=sys.stderr,
            )
        return 2

    if args.complete_worktree_retirement is not None:
        try:
            with lifecycle_lock():
                result, _manifests = complete_retirement_intent(
                    args.complete_worktree_retirement
                )
            results = [result]
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failed = retirement_result(args.retirement_repository or "unknown")
            failed["alert"] = str(exc)
            results = [failed]
    elif args.prepare_worktree_retirement is not None:
        if not (
            args.retirement_repository
            and args.retirement_head
            and args.retirement_base
        ):
            if not args.quiet:
                print(
                    "checkpoint_sync: retirement preparation requires "
                    "--retirement-repository, --retirement-head, and --retirement-base",
                    file=sys.stderr,
                )
            return 2
        try:
            with lifecycle_lock():
                result, _intent, _manifests = prepare_retirement_intent(
                    args.prepare_worktree_retirement,
                    args.retirement_repository,
                    args.retirement_head,
                    args.retirement_remote,
                    args.retirement_base,
                    branch=args.retirement_branch,
                    expect_active=True,
                    dry_run=args.dry_run,
                )
            results = [result]
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failed = retirement_result(args.retirement_repository)
            failed["alert"] = str(exc)
            results = [failed]
    elif args.reconcile_retired_worktree is not None:
        if not (
            args.retirement_repository
            and args.retirement_head
            and args.retirement_base
        ):
            if not args.quiet:
                print(
                    "checkpoint_sync: retired-worktree recovery requires "
                    "--retirement-repository, --retirement-head, and --retirement-base",
                    file=sys.stderr,
                )
            return 2
        results, _manifests = reconcile_retired_worktree(
            args.reconcile_retired_worktree,
            args.retirement_repository,
            args.retirement_head,
            args.retirement_base,
            remote=args.retirement_remote,
            dry_run=args.dry_run,
        )

    if any(retirement_modes):
        alerts = [result for result in results if result.get("alert")]
        if not args.quiet:
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                for result in results:
                    line = f"{result['name']}: {result['action']}"
                    if result.get("files") is not None:
                        line += f" ({result['files']} path(s))"
                    if result.get("alert"):
                        line += f"  ⚠ {result['alert']}"
                    print(line)
        return 1 if alerts else 0

    if args.flush_session is not None:
        results, manifests = flush_pending_session(
            cfg, args.flush_session, dry_run=args.dry_run
        )
        alerts = [result for result in results if result.get("alert")]
        readiness = (
            "BLOCKED"
            if alerts
            else ("REMOTE_READY" if manifests else "CLEAN")
        )
        if not args.dry_run:
            atomic_json(
                REMOTE_HANDOFF_STATE,
                {
                    "schema_version": 1,
                    "readiness": readiness,
                    "scope": "session",
                    "session_id": args.flush_session,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "manifests": [str(path) for path in manifests],
                    "results": results,
                },
            )
        if alerts:
            generic_alert_ping(len(alerts), speak=args.speak, notify=args.notify)
        if not args.quiet:
            if args.json:
                print(json.dumps({"readiness": readiness, "results": results}, indent=2))
            else:
                print(f"session remote handoff: {readiness}")
                for result in results:
                    line = f"{result['name']}: {result['action']}"
                    if result.get("alert"):
                        line += f"  ⚠ {result['alert']}"
                    print(line)
        return 1 if alerts else 0

    if args.hook:
        try:
            raw_payload = sys.stdin.read()
            hook_payload = json.loads(raw_payload) if raw_payload.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            if not args.quiet:
                print(f"checkpoint_sync: invalid hook payload: {exc}", file=sys.stderr)
            return 2
        results, manifest = local_handoff_checkpoint(hook_payload, cfg)
        if not args.dry_run:
            write_state("hook", results, running=False)
        alerts = [result for result in results if result.get("alert")]
        if alerts:
            generic_alert_ping(len(alerts), speak=args.speak, notify=args.notify)
        if not args.quiet:
            if args.json:
                print(json.dumps(results, indent=2))
            elif not results:
                state = f" ({manifest})" if manifest is not None else ""
                print(f"checkpoint_sync: no session-attributed context changes{state}")
            else:
                for result in results:
                    line = f"{result['name']}: {result['action']}"
                    if result.get("detail"):
                        line += f" ({result['detail']})"
                    if result.get("alert"):
                        line += f"  ⚠ {result['alert']}"
                    print(line)
        return 1 if alerts else 0

    if args.repo:
        results, manifest = record_producer_path(args.repo, cfg)
        if not args.dry_run:
            write_state("producer-local", results, running=False)
        alerts = [result for result in results if result.get("alert")]
        if alerts:
            generic_alert_ping(len(alerts), speak=args.speak, notify=args.notify)
        if not args.quiet:
            if args.json:
                print(json.dumps(results, indent=2))
            else:
                for result in results:
                    line = f"{result['name']}: {result['action']}"
                    if result.get("alert"):
                        line += f"  ⚠ {result['alert']}"
                    print(line)
        return 1 if alerts else 0

    if args.flush_pending or args.no_throttle or not args.hook:
        results, manifests = flush_all_pending(cfg, dry_run=args.dry_run)
        alerts = [result for result in results if result.get("alert")]
        readiness = (
            "BLOCKED"
            if alerts
            else ("REMOTE_READY" if manifests else "CLEAN")
        )
        if not args.dry_run:
            atomic_json(
                REMOTE_HANDOFF_STATE,
                {
                    "schema_version": 1,
                    "readiness": readiness,
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "manifests": [str(path) for path in manifests],
                    "results": results,
                },
            )
        if alerts:
            generic_alert_ping(len(alerts), speak=args.speak, notify=args.notify)
        if not args.quiet:
            if args.json:
                print(json.dumps({"readiness": readiness, "results": results}, indent=2))
            else:
                print(f"remote handoff: {readiness}")
                for result in results:
                    line = f"{result['name']}: {result['action']}"
                    if result.get("alert"):
                        line += f"  ⚠ {result['alert']}"
                    print(line)
        return 1 if alerts else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
