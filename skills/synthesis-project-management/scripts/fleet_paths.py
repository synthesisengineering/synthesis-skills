#!/usr/bin/env python3
"""Fleet ``~``-normalization: expand at load, fail closed in the doctor.

Design: 2026-09-19-fleet-architecture.md section 6. No persisted fleet-synced
config may contain a literal home path (``/Users/<name>/`` or any absolute
path under the current home). Consumers expand ``~``/``$HOME`` at load; the
doctor gate fails on any unexpanded absolute home path in a synced file,
naming file, line, and value.

This module holds the shared primitives. Each consumer wires them into its
own loader:

- git-hook-config ``coordination_board`` (synthesis-git-hooks ``_load_config``)
- ritual workers ``artifact_dir`` (synthesis-daily-rituals ``ritual_workers``)
- account-routing workspace keys (``route_account_workspace`` below)
- checkpoint ``recipient_index`` (synthesis-checkpoint ``refresh``)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Absolute home roots that must never appear literally in synced files: any
# macOS /Users/<name> or Linux /home/<name> prefix, plus the current home
# itself (which covers nonstandard locations on either platform).
HOME_ROOT_PREFIXES = ("/Users/", "/home/")


def expand_home(value: str) -> str:
    """Expand a ``~``- or ``$HOME``-rooted persisted path for this Mac."""
    return os.path.expandvars(os.path.expanduser(value))


def _home_prefixes() -> tuple[str, ...]:
    home = str(Path.home())
    return (home + os.sep, home) + HOME_ROOT_PREFIXES


def is_unexpanded_home_path(value: object) -> bool:
    """Whether a persisted value is a literal absolute home path.

    ``~``-prefixed and ``$HOME``-relative values pass; so does anything that
    is not an absolute path at all. A literal ``/Users/<name>/...``,
    ``/home/<name>/...``, or current-home-prefixed absolute path fails.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text.startswith("~") or text.startswith("$HOME") or text.startswith("${HOME}"):
        return False
    if not os.path.isabs(text):
        return False
    return text.startswith(_home_prefixes())


def route_account_workspace(
    workspaces: dict, candidate: str
) -> tuple[str, object] | None:
    """Route a workspace path through account-routing keys, expanded first.

    ``workspaces`` maps persisted workspace keys (``~``-rooted after
    normalization; absolute in legacy files) to route records. Both the keys
    and the candidate expand before compare, so an exact-match-on-unexpanded
    regression cannot silently stop routing. Returns the matched
    ``(key, record)`` pair for the longest-prefix match, or None.
    """
    if not isinstance(workspaces, dict) or not isinstance(candidate, str):
        return None
    expanded_candidate = os.path.normpath(expand_home(candidate.strip()))
    best: tuple[str, object] | None = None
    best_length = -1
    for key, record in workspaces.items():
        if not isinstance(key, str) or not key.strip():
            continue
        expanded_key = os.path.normpath(expand_home(key.strip()))
        if expanded_candidate != expanded_key and not expanded_candidate.startswith(
            expanded_key + os.sep
        ):
            continue
        if len(expanded_key) > best_length:
            best = (key, record)
            best_length = len(expanded_key)
    return best


@dataclass(frozen=True)
class UnexpandedPath:
    """One doctor-gate hit: file, line, and offending value."""

    path: str
    line: int
    value: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: unexpanded absolute home path: {self.value}"


def _home_path_tokens(line: str, home: str) -> list[str]:
    tokens = []
    for raw in line.replace(",", " ").replace(":", " ").split():
        token = raw.strip().strip("\"'")
        if is_unexpanded_home_path(token):
            tokens.append(token)
    # Absolute home paths containing spaces survive the split above only as
    # fragments; catch the full span with a prefix scan as well.
    for prefix in (home + os.sep, "/Users/", "/home/"):
        start = 0
        while True:
            index = line.find(prefix, start)
            if index < 0:
                break
            # A nested /home/ or /Users/ component is not a new absolute
            # path. Keep the full actual home token and refuse real roots.
            if index and line[index - 1] not in " \t\"':=([{,":
                start = index + len(prefix)
                continue
            end = index + len(prefix)
            while end < len(line) and line[end] not in "\"'\n":
                end += 1
            span = line[index:end].strip().rstrip(",")
            if span and span not in tokens and is_unexpanded_home_path(span):
                tokens.append(span)
            start = index + len(prefix)
    return tokens


def scan_file(path: Path) -> list[UnexpandedPath]:
    """Scan one synced file for literal absolute home paths, line by line."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise FleetPathsError(f"fleet doctor cannot read {path}: {exc}")
    home = str(Path.home())
    hits: list[UnexpandedPath] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for token in _home_path_tokens(line, home):
            hits.append(UnexpandedPath(str(path), number, token))
    return hits


class FleetPathsError(ValueError):
    """A fleet path gate failure (unreadable file or unexpanded path)."""


SYNCED_PATH_FILES = (
    "git-hook-config.yaml",
    "ritual/workers.yaml",
    "account-routing/workspaces.json",
    "checkpoint/active-campaign.json",
)


def check_synced_root(root: Path) -> list[UnexpandedPath]:
    """Run the doctor gate over the fleet-synced path-bearing files.

    Missing files are skipped (nothing persisted, nothing to fail); every
    present file must be free of literal absolute home paths.
    """
    hits: list[UnexpandedPath] = []
    for name in SYNCED_PATH_FILES:
        hits.extend(scan_file(Path(root) / name))
    return hits


def format_gate_report(hits: list[UnexpandedPath]) -> str:
    if not hits:
        return "PASS fleet-paths: no unexpanded absolute home paths in synced files"
    lines = ["FAIL fleet-paths: unexpanded absolute home paths in synced files:"]
    lines.extend(f"  {hit}" for hit in hits)
    return "\n".join(lines)


# Known temporary roots describe exposure, never a retention guarantee. The
# environment can add a root, but cannot remove the operating system defaults.
MAX_FIXTURE_SECONDS = 900
MAX_INVENTORY_REPOS = 64
MAX_REGISTERED_WORKTREES = 512
MAX_DELETED_PATHS = 100000
# Large indexes fail explicitly rather than consuming unbounded doctor resources.
MAX_INDEX_BYTES = 64 * 1024 * 1024


def temporary_roots() -> list[Path]:

    values = ["/tmp", "/var/tmp", "/private/tmp", "/private/var/tmp"]
    values.extend(os.environ.get(key, "") for key in ("TMPDIR", "TMP", "TEMP"))
    if os.name == "nt":
        values.extend([os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
                       os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Temp")])
    return list(dict.fromkeys(Path(value) for value in values if value and Path(value).is_absolute()))


def _temporary_storage_root(canonical: Path) -> str | None:
    """Return the known temporary root for an already canonical path."""
    roots = [root.resolve(strict=False) for root in temporary_roots()]
    # Other user-specific Darwin temporary/cache directories are not
    # necessarily represented by this process's TMPDIR.
    parts = canonical.parts
    darwin_temp = len(parts) >= 7 and parts[:4] == ("/", "private", "var", "folders") and parts[6] in {"T", "C"}
    found = next((str(root) for root in roots if canonical == root or root in canonical.parents), None)
    return found or (str(Path(*parts[:7])) if darwin_temp else None)


def classify_storage(path: Path) -> dict:
    """Classify one declared path, including aliases; never scan for work."""
    raw = Path(path).expanduser()
    result = {"path": str(raw), "canonical": None, "status": "unknown",
              "retention_deadline": None, "reason": "path could not be verified"}
    try:
        if not raw.is_absolute() or ".." in raw.parts:
            raise ValueError("absolute path without traversal required")
        canonical = raw.resolve(strict=False)
        result["canonical"] = str(canonical)
        temporary_root = _temporary_storage_root(canonical)
        if temporary_root:
            result.update(status="temporary", reason="temporary storage has no durable retention contract", temporary_root=temporary_root)
        else:
            result.update(status="durable-candidate", reason="outside known temporary roots; backup and custody still required")
    except (OSError, RuntimeError, ValueError) as exc:
        result["reason"] = str(exc)
    return result


def require_work_placement(path: Path, *, fixture_deadline: float | None = None) -> dict:
    """Durable by default; explicit finite fixtures retain every ordinary gate."""
    import math
    import time

    result = classify_storage(path)
    if result["status"] == "unknown":
        raise FleetPathsError("work placement UNKNOWN: " + result["reason"])
    if fixture_deadline is not None:
        if isinstance(fixture_deadline, bool) or not isinstance(fixture_deadline, (int, float)) or not math.isfinite(fixture_deadline):
            raise FleetPathsError("fixture deadline must be finite")
        remaining = fixture_deadline - time.time()
        if not 0 < remaining <= MAX_FIXTURE_SECONDS:
            raise FleetPathsError("fixture deadline expired or exceeds the 900-second fixture bound")
        result.update(purpose="ephemeral-test-fixture", fixture_deadline=fixture_deadline,
                      recovery="retain fixture evidence before closure; no automatic deletion")
    elif result["status"] == "temporary":
        raise FleetPathsError("temporary storage refused for durable work; choose a durable workspace; intentional tests require an explicit bounded fixture deadline")
    else:
        result["purpose"] = "durable-work"
    return result


def observe_declared_storage(path: Path) -> dict:
    """Observe one explicitly named root, without reading its contents."""
    import stat
    import time

    placement = classify_storage(path)
    result = {**placement, "sampled_at_unix_ns": time.time_ns(),
              "root_metadata": None, "content_age": "UNKNOWN"}
    try:
        root = Path(path).expanduser()
        before = root.lstat()
        if not stat.S_ISDIR(before.st_mode) or root.resolve() != root.absolute():
            raise ValueError("declared storage root is aliased or not an ordinary directory")
        after = root.lstat()
        def fields(value):
            return (value.st_dev, value.st_ino, value.st_mode, value.st_mtime_ns, value.st_ctime_ns)
        if fields(before) != fields(after):
            raise ValueError("declared root changed during observation")
        result["root_metadata"] = {"mtime_ns": before.st_mtime_ns, "ctime_ns": before.st_ctime_ns,
                                   "device": before.st_dev, "inode": before.st_ino}
        result["observation"] = "ordinary-root; timestamps describe this directory only"
    except (OSError, ValueError, RuntimeError) as exc:
        result["observation"] = "UNKNOWN: " + str(exc)
    return result


def missing_worktree_detail(path: Path, entry: dict, reason: str) -> str:
    return (f"{path}: unexplained disappearance or invalid worktree ({reason}); "
            f"registered repository={entry.get('repository', 'UNKNOWN')} common={entry.get('common', 'UNKNOWN')} HEAD={entry.get('HEAD', 'UNKNOWN')} branch={entry.get('branch', 'detached/UNKNOWN')}; "
            "preserve common Git metadata, refs, surviving files and claims; inspect and recover exact evidence before repair; do not prune or retire from absence")


def _storage_git(repository: Path, arguments: list[str], *, timeout: float):
    # These fixed metadata reads do not execute filters, hooks or fsmonitor.
    # Reuse native_git's bounded byte-capture owner; no shell or network query.
    import native_git

    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    result = native_git._spawn(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repository), *arguments],
                              env=env, timeout=timeout, max_output_bytes=4 * 1024 * 1024)
    if result.returncode:
        raise FleetPathsError("registered worktree inventory UNKNOWN: " + result.stderr.decode("utf-8", "replace")[:1000])
    return result.stdout.decode("utf-8", "strict")


def _index_signature(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _open_index(path: Path):
    """Open every component without following links; retain ancestry descriptors."""
    import stat

    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Git index path is ambiguous; completeness UNKNOWN")
    descriptors = []
    parents = []
    try:
        parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(parent)
        for name in path.parts[1:-1]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            descriptors.append(child)
            info = os.fstat(child)
            parents.append((parent, name, child, (info.st_dev, info.st_ino, info.st_mode)))
            parent = child
        before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Git index is not an ordinary file; completeness UNKNOWN")
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        descriptors.append(fd)
        if _index_signature(before) != _index_signature(os.fstat(fd)):
            raise ValueError("Git index changed before read; completeness UNKNOWN")
        return fd, before, parents, descriptors
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _index_fence(path, fd, before, parents):
    for parent, name, child, signature in parents:
        observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
        current = os.fstat(child)
        if signature != (observed.st_dev, observed.st_ino, observed.st_mode) or signature != (current.st_dev, current.st_ino, current.st_mode):
            raise ValueError("Git index ancestry changed; completeness UNKNOWN")
    if _index_signature(before) != _index_signature(os.fstat(fd)) or _index_signature(before) != _index_signature(path.lstat()):
        raise ValueError("Git index changed during inspection; completeness UNKNOWN")


def _index_link(body: bytes, width: int) -> str | None:
    """Locate only the shared dependency before Git could open it unsafely.

    Git still parses entries and extensions. This bounded locator merely skips
    the documented v2/v3/v4 encodings and refuses any ambiguity or truncation.
    """
    version = int.from_bytes(body[4:8], "big")
    count = int.from_bytes(body[8:12], "big")
    if count > MAX_DELETED_PATHS:
        raise ValueError("Git index entry count exceeds bound; completeness UNKNOWN")
    position = 12
    for _ in range(count):
        start = position
        position += 40 + width + 2
        if position > len(body):
            raise ValueError("Git index entry truncated; completeness UNKNOWN")
        flags = int.from_bytes(body[position - 2:position], "big")
        if flags & 0x4000:
            if version == 2:
                raise ValueError("unsupported Git index flags; completeness UNKNOWN")
            position += 2
        if version == 4:
            for _ in range(10):
                if position >= len(body):
                    raise ValueError("Git index compressed path truncated; completeness UNKNOWN")
                byte = body[position]
                position += 1
                if not byte & 0x80:
                    break
            else:
                raise ValueError("Git index compressed path exceeds bound; completeness UNKNOWN")
        end = body.find(b"\0", position)
        if end == -1:
            raise ValueError("Git index path truncated; completeness UNKNOWN")
        position = end + 1
        if version != 4:
            position = start + ((position - start + 7) // 8) * 8
        if position > len(body):
            raise ValueError("Git index padding truncated; completeness UNKNOWN")
    link = None
    while position < len(body):
        if len(body) - position < 8:
            raise ValueError("Git index extension truncated; completeness UNKNOWN")
        name = body[position:position + 4]
        size = int.from_bytes(body[position + 4:position + 8], "big")
        position += 8
        if size > len(body) - position:
            raise ValueError("Git index extension size invalid; completeness UNKNOWN")
        if name == b"link":
            if link is not None or size < width:
                raise ValueError("Git shared index reference ambiguous; completeness UNKNOWN")
            digest = body[position:position + width]
            if digest == bytes(width):
                raise ValueError("Git shared index reference unavailable; completeness UNKNOWN")
            link = digest.hex()
        position += size
    return link


def _index_witness(path: Path, algorithm: str, deadline: float) -> dict:
    """Check the bounded checksum; Git remains the index/extension parser."""
    import hashlib
    import time

    if algorithm not in {"sha1", "sha256"}:
        raise ValueError("unsupported Git object format; index integrity UNKNOWN")
    digest = hashlib.new(algorithm)
    limit = min(deadline, time.monotonic() + 5)
    def timely():
        if time.monotonic() >= limit:
            raise ValueError("Git index read deadline exceeded; completeness UNKNOWN")
    timely()
    fd, before, parents, descriptors = _open_index(path)
    try:
        if before.st_size > MAX_INDEX_BYTES or before.st_size < 12 + digest.digest_size:
            raise ValueError("Git index size outside integrity bound; completeness UNKNOWN")
        remaining = before.st_size - digest.digest_size
        header = b""
        chunks = []
        while remaining:
            timely()
            data = os.read(fd, min(65536, remaining))
            if not data:
                raise ValueError("Git index truncated during read; completeness UNKNOWN")
            header = (header + data)[:12] if len(header) < 12 else header
            digest.update(data)
            chunks.append(data)
            remaining -= len(data)
        trailer = b""
        while len(trailer) < digest.digest_size:
            timely()
            data = os.read(fd, digest.digest_size - len(trailer))
            if not data:
                raise ValueError("Git index checksum truncated; completeness UNKNOWN")
            trailer += data
        if os.read(fd, 1):
            raise ValueError("Git index grew during read; completeness UNKNOWN")
        _index_fence(path, fd, before, parents)
        timely()
        if header[:4] != b"DIRC" or int.from_bytes(header[4:8], "big") not in {2, 3, 4}:
            raise ValueError("unsupported Git index header/version; completeness UNKNOWN")
        if trailer == bytes(digest.digest_size):
            raise ValueError("Git index checksum unavailable (disabled integrity); completeness UNKNOWN")
        if trailer != digest.digest():
            raise ValueError("Git index checksum mismatch; completeness UNKNOWN")
        link = _index_link(b"".join(chunks), digest.digest_size)
        timely()
        return {"path": path, "signature": _index_signature(before), "link": link, "digest": digest.hexdigest(),
                "parents": [(name, signature) for _, name, _, signature in parents]}
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _verify_index_witness(witness):
    path = witness["path"]
    fd, info, parents, descriptors = _open_index(path)
    try:
        if witness["signature"] != _index_signature(info) or witness["parents"] != [(name, signature) for _, name, _, signature in parents]:
            raise ValueError("Git index or ancestry changed; completeness UNKNOWN")
        _index_fence(path, fd, info, parents)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def inspect_worktrees(repositories: list[Path]) -> list[dict]:
    """Inspect only explicitly selected repositories and their Git registry."""
    import stat
    import time

    if len(repositories) > MAX_INVENTORY_REPOS:
        raise FleetPathsError("registered repository inventory exceeds 64 inputs")
    deadline = time.monotonic() + 30
    results = []
    seen = set()

    def query(repository, arguments):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FleetPathsError("registered worktree inspection exceeded 30 seconds")
        return _storage_git(repository, arguments, timeout=min(5, remaining))

    for repository in repositories:
        identity = query(Path(repository), ["rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel"]).splitlines()
        if len(identity) != 2 or not Path(identity[0]).is_absolute() or Path(identity[1]).resolve() != Path(repository).resolve():
            raise FleetPathsError("declared repository is not its exact Git checkout root")
        common = Path(identity[0]).resolve()
        common_info = common.lstat()
        if not stat.S_ISDIR(common_info.st_mode):
            raise FleetPathsError("actual common Git directory is not ordinary")
        common_placement = classify_storage(common)
        raw = query(Path(repository), ["worktree", "list", "--porcelain", "-z"])
        entries = []
        entry = {}
        for item in raw.split("\0"):
            if item:
                key, _, value = item.partition(" ")
                if key in entry:
                    raise FleetPathsError("ambiguous registered worktree record")
                entry[key] = value
            elif entry:
                entries.append(entry)
                entry = {}
        if entry:
            raise FleetPathsError("unterminated registered worktree record")
        if not entries:
            raise FleetPathsError("registered worktree inventory is empty")
        if len(entries) > MAX_REGISTERED_WORKTREES:
            raise FleetPathsError("registered worktree inventory exceeds 512 entries")
        for entry in entries:
            entry = {**entry, "repository": str(repository), "common": str(common)}
            if time.monotonic() >= deadline:
                raise FleetPathsError("registered worktree inspection exceeded 30 seconds")
            path = Path(entry.get("worktree", ""))
            if not path.is_absolute():
                raise FleetPathsError("registered worktree path is not absolute")
            if str(path) in seen:
                continue
            seen.add(str(path))
            if len(seen) > MAX_REGISTERED_WORKTREES:
                raise FleetPathsError("aggregate registered worktree inventory exceeds 512 entries")
            row = {"path": str(path), "HEAD": entry.get("HEAD"), "branch": entry.get("branch"),
                   "placement": classify_storage(path), "common": str(common),
                   "common_placement": common_placement, "status": "OK", "issues": []}
            if common_placement["status"] != "durable-candidate":
                row["issues"].append(f"common Git directory {common}: {common_placement['reason']}; preserve refs and metadata before any relocation")
            if row["placement"]["status"] != "durable-candidate":
                row["issues"].append(row["placement"]["reason"])
            try:
                info = path.lstat()
                if not stat.S_ISDIR(info.st_mode):
                    raise ValueError("checkout root is not an ordinary directory")
                marker = path / ".git"
                marker_info = marker.lstat()
                if not (stat.S_ISREG(marker_info.st_mode) or stat.S_ISDIR(marker_info.st_mode)):
                    raise ValueError("linked metadata is not a regular file/directory")
                observed = query(path, ["rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel"]).splitlines()
                if len(observed) != 2 or Path(observed[1]).resolve() != path.resolve() or Path(observed[0]).resolve() != common:
                    raise ValueError("Git resolves to a different checkout or common directory")
                index_value = query(path, ["rev-parse", "--git-path", "index"]).rstrip("\n")
                index = Path(index_value)
                if not index.is_absolute():
                    index = path / index
                if not index.is_absolute() or "\n" in index_value or ".." in index.parts:
                    raise ValueError("actual Git index path is ambiguous")
                algorithm = query(path, ["rev-parse", "--show-object-format"]).strip()
                try:
                    witnesses = [_index_witness(index, algorithm, deadline)]
                except FileNotFoundError as exc:
                    raise ValueError("Git index is missing; tracked-file completeness is UNKNOWN; preserve HEAD and surviving metadata before repair") from exc
                link = witnesses[0]["link"]
                shared_value = str(index.parent / ("sharedindex." + link)) if link else ""
                if shared_value:
                    try:
                        witnesses.append(_index_witness(Path(shared_value), algorithm, deadline))
                    except FileNotFoundError as exc:
                        raise ValueError("shared Git index is missing; completeness UNKNOWN") from exc
                    if witnesses[1]["link"] is not None:
                        raise ValueError("nested shared Git index reference unsupported; completeness UNKNOWN")
                observed_shared = query(path, ["rev-parse", "--path-format=absolute", "--shared-index-path"]).rstrip("\n")
                if observed_shared != shared_value:
                    raise ValueError("Git shared index interpretation disagrees; completeness UNKNOWN")
                deleted = query(path, ["ls-files", "--deleted", "-z"]).split("\0")
                if deleted[-1] != "":
                    raise ValueError("unterminated tracked-file inventory")
                deleted.pop()
                after_root, after_marker = path.lstat(), marker.lstat()
                def signature(value):
                    return value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns
                if query(path, ["rev-parse", "--path-format=absolute", "--shared-index-path"]).rstrip("\n") != shared_value:
                    raise ValueError("shared Git index dependency changed; completeness UNKNOWN")
                _verify_index_witness(witnesses[0])
                if len(witnesses) == 2:
                    # Git itself refreshes shared-index timestamps on reads.
                    # Re-read bytes rather than treating that timestamp as proof
                    # either of corruption or of unchanged content.
                    before_shared = witnesses[1]
                    after_shared = _index_witness(before_shared["path"], algorithm, deadline)
                    keys = ("path", "parents", "digest", "link")
                    if any(before_shared[key] != after_shared[key] for key in keys) or before_shared["signature"][:4] != after_shared["signature"][:4]:
                        raise ValueError("shared Git index changed during inspection; completeness UNKNOWN")
                    if before_shared["signature"] != after_shared["signature"]:
                        row["shared_index_timestamp_refresh_observed"] = True
                if signature(marker_info) != signature(after_marker) or (info.st_dev, info.st_ino, info.st_mode) != (after_root.st_dev, after_root.st_ino, after_root.st_mode):
                    raise ValueError("checkout metadata changed during inspection")
                if len(deleted) > MAX_DELETED_PATHS:
                    raise ValueError("tracked-file inventory exceeds bound")
                if deleted:
                    row["missing_tracked_count"] = len(deleted)
                    row["missing_tracked_sample"] = deleted[:20]
                    row["issues"].append(missing_worktree_detail(path, entry, f"{len(deleted)} vanished tracked path(s); intentional deletion versus loss is UNKNOWN"))
            except FileNotFoundError:
                row["issues"].append(missing_worktree_detail(path, entry, "missing linked metadata or checkout root"))
            except (OSError, RuntimeError, ValueError) as exc:
                row["issues"].append(missing_worktree_detail(path, entry, str(exc)))
            if "prunable" in entry:
                row["issues"].append(missing_worktree_detail(path, entry, "Git marks the registration prunable: " + entry["prunable"]))
            if row["issues"]:
                row["status"] = "REPAIR-REQUIRED"
            results.append(row)
        after_common = common.lstat()
        if (common_info.st_dev, common_info.st_ino, common_info.st_mode) != (after_common.st_dev, after_common.st_ino, after_common.st_mode):
            raise FleetPathsError("common Git directory identity changed during inspection")
        if query(Path(repository), ["worktree", "list", "--porcelain", "-z"]) != raw:
            raise FleetPathsError("registered worktree membership changed during inspection")
    return results
