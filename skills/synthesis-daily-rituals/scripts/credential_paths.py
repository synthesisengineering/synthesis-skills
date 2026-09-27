"""Names-only tracked-path inventory owned by the daily ritual recorder.

Never open a tracked file or object blob. A finding is a name requiring review,
not an assertion that secret material exists. No rotation, deletion or network.
"""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import selectors
import signal
import stat
import time

from ritual_workers import (
    MAX_REGISTRY_BYTES,
    RitualWorkersError,
    read_regular,
    strict_yaml,
)

MAX_REPOS = 256
MAX_TRACKED_BYTES = 8 * 1024 * 1024
MAX_TOTAL_TRACKED_BYTES = 16 * 1024 * 1024
MAX_TOTAL_SECONDS = 45
PER_REPO_SECONDS = 5


def credential_looking(path: str) -> bool:
    """Conservative filename candidates, including sample names; no content inference."""
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1] if parts else ""
    return bool(
        name == ".env"
        or name.startswith(".env.")
        or re.search(
            r"(^|[-_.])(credentials?|secrets?|tokens?|service[-_]?account)([-_.]|$)",
            name,
        )
        or re.fullmatch(r"id_(rsa|dsa|ecdsa|ed25519)(\..*)?", name)
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
        or any(
            part in {".aws", ".ssh", "credentials", "secrets"} for part in parts[:-1]
        )
    )


def _git_names(repo: Path, remaining: float) -> bytes:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_OPTIONAL_LOCKS="0",
        LC_ALL="C",
    )
    command = [
        "git",
        "--no-replace-objects",
        "--literal-pathspecs",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.hooksPath=" + os.devnull,
        "-C",
        str(repo),
        "ls-files",
        "--cached",
        "--full-name",
        "-z",
    ]
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    deadline = time.monotonic() + min(PER_REPO_SECONDS, remaining)
    output = bytearray()
    error_bytes = 0
    succeeded = False
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map():
                left = deadline - time.monotonic()
                if left <= 0:
                    raise RitualWorkersError("tracked path inventory timed out")
                for key, _ in selector.select(left):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif key.fileobj is process.stdout:
                        output.extend(chunk)
                        if len(output) > MAX_TRACKED_BYTES:
                            raise RitualWorkersError(
                                "tracked path inventory exceeds byte bound"
                            )
                    else:
                        error_bytes += len(chunk)
                        if error_bytes > 65536:
                            raise RitualWorkersError(
                                "tracked path inventory diagnostics exceed byte bound"
                            )
        remaining_wait = deadline - time.monotonic()
        if remaining_wait <= 0 or process.wait(timeout=remaining_wait):
            raise RitualWorkersError(
                "tracked path inventory unavailable (git failed or deadline elapsed)"
            )
        succeeded = True
        return bytes(output)
    finally:
        if not succeeded or process.poll() is None:
            # Only the newly owned process group is terminated; no broad matching.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)
        process.stdout.close()
        process.stderr.close()


def _local_git_metadata(repo: Path, workspace: Path) -> tuple:
    """Refuse foreign Git indirection before asking Git for tracked names."""
    marker = repo / ".git"
    if marker.is_symlink():
        raise RitualWorkersError("Git metadata alias is not workspace-local authority")
    if marker.is_file():
        text = read_regular(marker, 8192).decode("utf-8")
        match = re.fullmatch(r"gitdir: ([^\r\n]+)\n?", text)
        if match is None:
            raise RitualWorkersError("invalid bounded Git directory declaration")
        directory = Path(match.group(1))
        directory = directory if directory.is_absolute() else repo / directory
        directory = Path(os.path.abspath(directory))
    elif marker.is_dir():
        directory = marker
    else:
        raise RitualWorkersError("Git metadata is unavailable")
    if (
        directory.resolve() != directory
        or not directory.is_dir()
        or not directory.is_relative_to(workspace)
    ):
        raise RitualWorkersError(
            "Git directory resolves outside the declared workspace"
        )
    common = directory / "commondir"
    backlink = directory / "gitdir"
    if marker.is_file():
        if not os.path.lexists(common) or not os.path.lexists(backlink):
            raise RitualWorkersError(
                "Git indirection requires reciprocal local worktree ownership"
            )
        text = read_regular(backlink, 8192).decode("utf-8")
        if "\n" in text.rstrip("\n") or "\r" in text:
            raise RitualWorkersError("invalid bounded Git worktree backlink")
        reverse = Path(text.rstrip("\n"))
        if not reverse.is_absolute() or reverse != marker:
            raise RitualWorkersError("Git worktree backlink names a different checkout")
    if os.path.lexists(common):
        text = read_regular(common, 8192).decode("utf-8")
        if not text.strip() or "\n" in text.rstrip("\n") or "\r" in text:
            raise RitualWorkersError("invalid bounded Git common directory declaration")
        target = Path(text.rstrip("\n"))
        target = target if target.is_absolute() else directory / target
        target = Path(os.path.abspath(target))
        if (
            target.resolve() != target
            or not target.is_dir()
            or not target.is_relative_to(workspace)
        ):
            raise RitualWorkersError(
                "Git common directory resolves outside the workspace"
            )
    index = directory / "index"
    if os.path.lexists(index):
        metadata = index.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
        ):
            raise RitualWorkersError("Git index must be an owned local regular file")
    # Recheck the exact index and indirection metadata after Git returns; a
    # changing source is UNKNOWN, never evidence attributed to the old checkout.
    fingerprint = []
    for item in (marker, directory, common, backlink, index):
        if os.path.lexists(item):
            info = item.lstat()
            fingerprint.append(
                (
                    str(item),
                    info.st_dev,
                    info.st_ino,
                    info.st_mode,
                    info.st_nlink,
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ctime_ns,
                )
            )
    return tuple(fingerprint)


def inventory(workspace_root: Path) -> dict:
    root = Path(workspace_root).expanduser().absolute()
    report = {
        "schema": 1,
        "workspace_root": str(root),
        "names_only": True,
        "secret_contents_read": False,
        "complete": False,
        "repositories": [],
        "findings": [],
        "gaps": [],
    }
    start = time.monotonic()
    try:
        if root.resolve() != root or not root.is_dir():
            raise RitualWorkersError(
                "workspace root must be a real directory without links"
            )
        # The workspace manifest's conventional symlink into its own context repo
        # is supported, but it must resolve inside this exact workspace.
        manifest = root / ".agents/repos.yaml"
        resolved = manifest.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise RitualWorkersError(
                "repository manifest resolves outside the workspace"
            )
        document = strict_yaml(
            read_regular(resolved, MAX_REGISTRY_BYTES).decode("utf-8")
        )
        if not isinstance(document, dict) or "repos" not in document:
            raise RitualWorkersError("repository manifest must declare repos")
        entries = document["repos"]
        if isinstance(entries, dict):
            rows = []
            for key, value in entries.items():
                if (
                    not isinstance(key, str)
                    or not isinstance(value, dict)
                    or ("name" in value and value["name"] != key)
                ):
                    raise RitualWorkersError("invalid or ambiguous repository map")
                rows.append({"name": key, **value})
            entries = rows
        if not isinstance(entries, list) or not entries or len(entries) > MAX_REPOS:
            raise RitualWorkersError("repo inventory must be a nonempty bounded list")
        seen = set()
        total_bytes = 0
        for number, entry in enumerate(entries):
            label = entry.get("name") if isinstance(entry, dict) else None
            if not isinstance(label, str) or not label.strip() or label in seen:
                report["gaps"].append(
                    {
                        "entry": number,
                        "reason": "invalid or duplicate repository identity",
                    }
                )
                continue
            seen.add(label)
            row = {"repo": label, "status": "unscanned", "tracked_count": 0}
            report["repositories"].append(row)
            try:
                declared = entry.get("path", label)
                if not isinstance(declared, str) or not declared.strip():
                    raise RitualWorkersError("invalid repository path")
                path = Path(os.path.expanduser(declared))
                path = path if path.is_absolute() else root / path
                if (
                    ".." in path.parts
                    or path.resolve() != path
                    or not path.is_relative_to(root)
                    or path == root
                ):
                    raise RitualWorkersError("foreign or linked repository path")
                if not path.is_dir() or not (path / ".git").exists():
                    raise RitualWorkersError(
                        "declared repository is not a local checkout"
                    )
                metadata_before = _local_git_metadata(path, root)
                remaining = MAX_TOTAL_SECONDS - (time.monotonic() - start)
                if remaining <= 0:
                    raise RitualWorkersError("workspace inventory time bound reached")
                if total_bytes >= MAX_TOTAL_TRACKED_BYTES:
                    raise RitualWorkersError(
                        "workspace tracked path byte bound reached"
                    )
                raw = _git_names(path, remaining)
                if _local_git_metadata(path, root) != metadata_before:
                    raise RitualWorkersError(
                        "tracked path source changed during inventory"
                    )
                total_bytes += len(raw)
                if (
                    len(raw) > MAX_TRACKED_BYTES
                    or total_bytes > MAX_TOTAL_TRACKED_BYTES
                ):
                    raise RitualWorkersError(
                        "workspace tracked path byte bound exceeded"
                    )
                if raw and not raw.endswith(b"\0"):
                    raise RitualWorkersError("tracked path listing was truncated")
                names = raw[:-1].split(b"\0") if raw else []
                decoded = set()
                for name in names:
                    value = name.decode("utf-8", errors="strict")
                    parsed = PurePosixPath(value)
                    if not value or parsed.is_absolute() or ".." in parsed.parts:
                        raise RitualWorkersError("invalid tracked path in index")
                    decoded.add(value)
                row.update(status="scanned", tracked_count=len(decoded))
                for name in sorted(decoded):
                    if credential_looking(name):
                        report["findings"].append({"repo": label, "path": name})
            except (
                OSError,
                UnicodeError,
                RitualWorkersError,
                subprocess.SubprocessError,
            ) as exc:
                row["reason"] = str(exc)
                report["gaps"].append({"repo": label, "reason": str(exc)})
        report["complete"] = not report["gaps"]
    except (OSError, UnicodeError, RitualWorkersError, ValueError, TypeError) as exc:
        report["gaps"].append({"reason": str(exc)})
    return report


def command(workspace_root: Path) -> int:
    result = inventory(workspace_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["complete"] else 2
