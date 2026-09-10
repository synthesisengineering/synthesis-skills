"""Shared conflict detection, deliberately separate from write authorization.

Physical claims conflict where their path patterns intersect. The projects/
metadata namespace also conflicts at the same relative target in registered
worktrees with one verified Git common directory. This never permits writing a
sibling checkout. Missing identity is an error, not evidence of foreign work.
"""
from __future__ import annotations

from functools import lru_cache
import fnmatch
import os
from pathlib import Path
import re
import stat
import subprocess


class ClaimIdentityError(ValueError):
    """A possible logical metadata conflict lacks unambiguous Git identity."""


class _NoVerifiedCheckout(ClaimIdentityError):
    """Git ran but could not identify a checkout at this path."""


def plain(value: str) -> str:
    return re.sub(r"`(.+?)`", r"\1", re.sub(r"\*\*(.+?)\*\*", r"\1", value)).strip()


def split_values(value: str) -> list[str]:
    clean = plain(value)
    if not clean or clean.lower().startswith("released"):
        return []
    return [part.strip() for part in re.split(r"[,;]|<br\s*/?>", clean) if part.strip()]


def workspace_parts(workspace: str) -> tuple[str, str]:
    return tuple(plain(part) for part in workspace.rsplit(" @ ", 1)) if " @ " in workspace else (plain(workspace), "unknown")


def _prefix(pattern: str) -> str:
    return re.split(r"[*?\[]", pattern, maxsplit=1)[0].rstrip("/")


def _tokens(segment: str) -> tuple[str, ...]:
    result = []
    offset = 0
    while offset < len(segment):
        end = offset + 1
        if segment[offset] == "[":
            if end < len(segment) and segment[end] == "!":
                end += 1
            if end < len(segment) and segment[end] == "]":
                end += 1
            end = segment.find("]", end)
            end = end + 1 if end >= 0 else offset + 1
        result.append(segment[offset:end])
        offset = end
    return tuple(result)


@lru_cache(maxsize=4096)
def _segments_intersect(left: str, right: str) -> bool:
    """Intersect glob NFAs using character-class boundary representatives."""
    if not any(c in left + right for c in "*?["):
        return left == right
    a, b = _tokens(left), _tokens(right)
    # Class predicates change only at literal/range boundaries. Adjacent code
    # points plus a generic character cover positive and negated Unicode ranges.
    points = {1, ord("_"), 0x10FFFF}
    for character in left + right:
        points.update(p for p in (ord(character) - 1, ord(character), ord(character) + 1) if 0 < p <= 0x10FFFF)
    alphabet = [chr(p) for p in points if chr(p) != "/"]
    pending = [(0, 0, False)]
    seen = set()
    while pending:
        i, j, consumed = pending.pop()
        if (i, j, consumed) in seen:
            continue
        seen.add((i, j, consumed))
        if i == len(a) and j == len(b) and consumed:
            return True
        if i < len(a) and a[i] == "*":
            pending.append((i + 1, j, consumed))
        if j < len(b) and b[j] == "*":
            pending.append((i, j + 1, consumed))
        if i < len(a) and j < len(b) and any(fnmatch.fnmatchcase(c, a[i]) and fnmatch.fnmatchcase(c, b[j]) for c in alphabet):
            pending.append((i if a[i] == "*" else i + 1, j if b[j] == "*" else j + 1, True))
    return False


def _parts(pattern: str) -> tuple[str, ...]:
    parts = tuple(part for part in pattern.strip("/").split("/") if part and part != ".")
    # Literal ancestor claims reserve their subtree; wildcard claims use exact
    # segment semantics, including explicit ** for recursive descent.
    return parts if any(c in pattern for c in "*?[") else (*parts, "**")


@lru_cache(maxsize=4096)
def _patterns_intersect(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    pending = [(0, 0)]
    seen = set()
    while pending:
        i, j = pending.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        if i == len(left) and j == len(right):
            return True
        if i < len(left) and left[i] == "**":
            pending.append((i + 1, j))
        if j < len(right) and right[j] == "**":
            pending.append((i, j + 1))
        if i < len(left) and j < len(right) and _segments_intersect("*" if left[i] == "**" else left[i], "*" if right[j] == "**" else right[j]):
            pending.append((i if left[i] == "**" else i + 1, j if right[j] == "**" else j + 1))
    return False


def _metadata_suffixes(parts: tuple[str, ...]) -> list[tuple[str, ...]]:
    suffixes = []
    for i, part in enumerate(parts):
        if part == "**":
            suffixes.append(parts[i:])
        elif fnmatch.fnmatchcase("projects", part):
            suffixes.append(parts[i + 1:])
        if part != "**":
            break
    return suffixes


def _hint(pattern: str) -> tuple[str, ...] | None:
    parts = _parts(pattern)
    indices = [i for i, part in enumerate(parts) if part == "projects"]
    return parts[indices[-1] + 1:] if indices else None


def _mixed_paths_intersect(absolute: tuple[str, ...], relative: tuple[str, ...]) -> bool:
    # Without a checkout context, align only against known directory names.
    # A trailing ** cannot invent a new repository root for a relative claim.
    for i, segment in enumerate(absolute):
        if any(token in segment for token in "*?["):
            break
        if _patterns_intersect(absolute[i:], relative):
            return True
    return False


def _ordinary_nonrepo_scope(pattern: str) -> bool:
    """Prove a literal existing ordinary scope has no Git administrative ancestor.

    Its descendants are checked separately against the other claim's verified
    registered worktrees; absence of a local .git does not prove containment safe.
    """
    if pattern.endswith("/**"):
        pattern = pattern[:-3]  # the same subtree reserved by a literal directory
    if _hint(pattern) is not None or any(token in pattern for token in "*?["):
        return False
    path = Path(pattern)
    try:
        mode = path.stat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            return False
        directory = path if stat.S_ISDIR(mode) else path.parent
        for parent in (directory, *directory.parents):
            try:
                (parent / ".git").lstat()
            except FileNotFoundError:
                pass
            else:
                return False
            if (parent / "HEAD").is_file() and (parent / "objects").is_dir():
                return False  # a bare repository is not an ordinary directory
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ClaimIdentityError("ordinary claim filesystem identity is unavailable") from exc
    return True


class ClaimScopeResolver:
    """One-operation identity cache; never retained across board transactions."""
    def __init__(self):
        self.identities = {}
        self.registered = {}

    def _physical(self, claim: str, workspaces) -> str:
        raw = os.path.expanduser(plain(claim))
        if not raw or "\x00" in raw:
            raise ClaimIdentityError("claim path is empty or invalid")
        if Path(raw).is_absolute():
            return os.path.realpath(raw)
        candidates = set()
        for workspace in workspaces:
            path, _ = workspace_parts(workspace)
            base = Path(os.path.expanduser(path))
            if not base.is_absolute():
                continue
            if Path(raw).parts and Path(raw).parts[0] == base.name:
                base = base.parent
            candidates.add(os.path.realpath(base / raw))
        if len(candidates) != 1:
            if _hint(raw) is not None:
                raise ClaimIdentityError("relative metadata claim requires one exact checkout context")
            return raw  # historical relative source claims retain lexical scope
        return candidates.pop()

    def _identity(self, pattern: str) -> tuple[str, str]:
        prefix = Path(_prefix(pattern) or "/")
        while not prefix.is_dir() and prefix != prefix.parent:
            prefix = prefix.parent
        key = str(prefix)
        if key in self.identities:
            return self.identities[key]
        env = os.environ.copy()
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
            env.pop(name, None)
        def git(*args):
            try:
                done = subprocess.run(["git", "--no-optional-locks", "-C", key, *args], env=env, capture_output=True, text=True, timeout=10)
            except (OSError, subprocess.SubprocessError) as exc:
                raise ClaimIdentityError("metadata claim Git identity is unavailable") from exc
            if done.returncode:
                raise _NoVerifiedCheckout("metadata claim has no verified Git checkout")
            return done.stdout
        lines = git("rev-parse", "--path-format=absolute", "--git-common-dir", "--show-toplevel").splitlines()
        if len(lines) != 2 or not all(Path(line).is_absolute() and Path(line).is_dir() for line in lines):
            raise ClaimIdentityError("metadata claim Git identity is ambiguous")
        common, root = (str(Path(line).resolve()) for line in lines)
        registered = [str(Path(item[len("worktree "):]).resolve()) for item in git("worktree", "list", "--porcelain", "-z").split("\0") if item.startswith("worktree ")]
        if registered.count(root) != 1:
            raise ClaimIdentityError("metadata claim checkout is not uniquely registered")
        self.registered[common] = tuple(registered)
        result = (common, root)
        self.identities[key] = result
        return result

    def _scope_identity(self, pattern: str):
        try:
            return self._identity(pattern)
        except _NoVerifiedCheckout:
            if _ordinary_nonrepo_scope(pattern):
                return None
            raise

    def conflicts(self, left: str, right: str, *, left_workspaces=(), right_workspaces=()) -> bool:
        raw_left, raw_right = plain(left), plain(right)
        virtual_left = re.match(r"^[A-Za-z][A-Za-z0-9_-]*:", raw_left) is not None
        virtual_right = re.match(r"^[A-Za-z][A-Za-z0-9_-]*:", raw_right) is not None
        if virtual_left or virtual_right:
            return virtual_left and virtual_right and _segments_intersect(raw_left, raw_right)
        a, b = self._physical(left, left_workspaces), self._physical(right, right_workspaces)
        if Path(a).is_absolute() == Path(b).is_absolute() and _patterns_intersect(_parts(a), _parts(b)):
            return True
        if not Path(a).is_absolute() or not Path(b).is_absolute():
            # No absolute context was supplied for these ordinary source
            # paths. The invoking process's checkout is not their identity.
            if Path(a).is_absolute() == Path(b).is_absolute():
                return False
            absolute, relative = (_parts(a), _parts(b)) if Path(a).is_absolute() else (_parts(b), _parts(a))
            return _mixed_paths_intersect(absolute, relative)
        left_hint, right_hint = _hint(a), _hint(b)
        try:
            left_identity = self._scope_identity(a)
            right_identity = self._scope_identity(b)
        except ClaimIdentityError:
            # Synthetic, non-Git paths in one physical projects directory can
            # still prove disjointness. Never use an ancestor's directory name
            # to decide the logical namespace of a verified Git checkout.
            if (left_hint is not None and right_hint is not None
                    and a.rsplit("/projects/", 1)[0] == b.rsplit("/projects/", 1)[0]
                    and not _patterns_intersect(left_hint, right_hint)):
                return False
            if left_hint is not None or right_hint is not None:
                raise
            # No project metadata is implicated and no repository identity is
            # available. Preserve physical/lexical source-path behavior only.
            raw_a, raw_b = _parts(plain(left)), _parts(plain(right))
            if Path(plain(left)).is_absolute() == Path(plain(right)).is_absolute():
                return _patterns_intersect(raw_a, raw_b)
            absolute, relative = (raw_a, raw_b) if Path(plain(left)).is_absolute() else (raw_b, raw_a)
            return _mixed_paths_intersect(absolute, relative)
        if left_identity is None or right_identity is None:
            if left_identity is None and right_identity is None:
                return False
            ordinary, metadata, identity = (a, b, right_identity) if left_identity is None else (b, a, left_identity)
            common, root = identity
            relative = Path(metadata).relative_to(root).as_posix()
            if not _metadata_suffixes(_parts(relative)):
                return False
            return any(Path(checkout).is_relative_to(_prefix(ordinary)) for checkout in self.registered[common])
        left_common, left_root = left_identity
        right_common, right_root = right_identity
        if left_common != right_common:
            return False
        try:
            relative_a = Path(a).relative_to(left_root).as_posix()
            relative_b = Path(b).relative_to(right_root).as_posix()
        except ValueError as exc:
            raise ClaimIdentityError("metadata claim escapes its verified checkout") from exc
        return any(_patterns_intersect(x, y) for x in _metadata_suffixes(_parts(relative_a)) for y in _metadata_suffixes(_parts(relative_b)))


def claim_conflicts(left: str, right: str, *, left_workspaces=(), right_workspaces=()) -> bool:
    return ClaimScopeResolver().conflicts(left, right, left_workspaces=left_workspaces, right_workspaces=right_workspaces)


def project_claim_overlap(project: Path, claim: str, workspaces=()) -> bool:
    """Broad possible-repair scope, not an assertion that exact edits conflict.

    Any project resource or its registry could need repair. Two disjoint exact
    resource claims can therefore both intersect this broad target while they
    remain independent under claim_conflicts. Native ownership is separate.
    """
    project = Path(project).expanduser()
    if not project.is_absolute():
        raise ClaimIdentityError("project repair scope requires an absolute path")
    resolver = ClaimScopeResolver()
    targets = [str(project / "**")]
    if project.parent.name == "projects":
        targets.append(str(project.parent / "index.yaml"))
    return any(resolver.conflicts(target, claim, right_workspaces=workspaces) for target in targets)
