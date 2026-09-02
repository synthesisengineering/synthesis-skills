#!/usr/bin/env python3
"""Gated cross-client release for the synthesis-skills plugin.

A release is not finished when `main` is pushed. The plugin *is* the repository
— the marketplace manifests carry no version and point at `./` — so publishing
is a push. But every client keeps a version-pinned installation that does not
follow the remote on its own, so a pushed-but-uninstalled release leaves the
running clients silently behind their own source.

This script makes that state unreachable by sequencing the whole operation
behind one command that fails closed:

    preflight -> required checks -> publish -> install both clients -> verify

The verification step is deliberately paranoid, for a reason learned the hard
way: **a client's own version report is not sufficient evidence.** A client can
report the intended version while the tree it actually loads is stale. Every
client is therefore verified twice — once by asking the CLI, and once by
reading the plugin manifest at the path the CLI says it loads from. Agreement
between the two, and with the source manifests, is the only accepted pass.

Nothing here authors a release. Version bumps, CHANGELOG entries, and README
notes are human/agent work; this script verifies they are coherent and then
ships them. Refusing to invent release content is part of the contract.

Modes:
  (default)       full release from the current checkout
  --install-only  skip publishing; refresh and verify the clients only
                  (new machine, recovered drift, or a release pushed elsewhere)
  --check-only    preflight + required checks; no publish, no install
  --acceptance-only
                  consume a fresh acceptance result bound to this Git state;
                  no publish or install (repository CI boundary)
  --dry-run       print the plan and run read-only steps; mutate nothing

Exit codes: 0 released/verified, 1 a step failed, 2 preconditions unverifiable.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "synthesis-agent-conformance" / "scripts"))

try:
    from client_binaries import resolve_client_binary
except ImportError:  # pragma: no cover - resolved at runtime in the repo
    def resolve_client_binary(name: str):  # type: ignore[misc]
        import shutil

        override = os.environ.get(
            {"claude": "SYNTHESIS_CLAUDE_BIN", "codex": "SYNTHESIS_CODEX_BIN"}.get(name, "")
        )
        if override is not None and override != "":
            return override if Path(override).is_file() else None
        if override == "":
            return None
        return shutil.which(name)


PLUGIN_NAME = "synthesis-skills"
MARKETPLACE = "synthesis-engineering"
MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
ACCEPTANCE_MANIFEST = Path(
    "skills/synthesis-implementation-integrity/acceptance-suite.yaml"
)
ACCEPTANCE_RUNNER = Path(
    "skills/synthesis-implementation-integrity/scripts/acceptance_suite.py"
)
CACHE_GUARDIAN = Path(
    "skills/synthesis-skills-manager/scripts/cache_guardian.py"
)
ACCEPTANCE_CONSUMER_ID = (
    "synthesis-skills-manager.release.consume-acceptance.v1"
)
RELEASE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
# One release train per plugin: a virtual coordination-board resource whose
# claim overlap refusal is the mutual exclusion. On 2026-09-01 two agent
# sessions releasing this repository in parallel overtook each other five
# times and once collided on the announced version; message-based sequencing
# failed because an autonomous session mid-transaction does not re-read the
# board. Machines without a coordination board (outside contributors) are
# exempt; where a board exists, preflight refuses to proceed unless this
# process's session holds the train.
TRAIN_RESOURCE = f"release-train:{PLUGIN_NAME}"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
)
DEFAULT_ACTIVE_PROJECT_POINTER = Path.home() / ".synthesis" / "active-project.json"
HOOK_PLUGIN_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)")
RECOVERY_DIGEST_IGNORED_ROOTS = frozenset(
    {".git", ".in_use", ".codex-marketplace-install.json"}
)
CODEX_CACHE_ARCHIVE_BUDGET_BYTES = 512 * 1024 * 1024
CODEX_CACHE_QUIET_SECONDS = 10.0
CODEX_CACHE_SETTLE_TIMEOUT_SECONDS = 60.0
CODEX_CACHE_POLL_SECONDS = 0.1

# The required checks, mirroring the repository's own verification contract.
# Kept as data so a reader can see exactly what a release runs.
REQUIRED_CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("conformance.source", ["python3", "skills/synthesis-agent-conformance/scripts/conformance.py", "source"]),
    ("conformance.instructions", ["python3", "skills/synthesis-agent-conformance/scripts/conformance.py", "instructions", "--repo-root", "."]),
    ("pytest.conformance", ["python3", "-m", "pytest", "skills/synthesis-agent-conformance/scripts/", "-q"]),
    ("pytest.coordination", ["python3", "-m", "pytest", "skills/synthesis-project-management/scripts/", "-q"]),
    ("pytest.promotion-gate", ["python3", "-m", "pytest", "skills/synthesis-promotion-gate/scripts/", "-q"]),
    ("pytest.context-lifecycle-integrity", ["python3", "-m", "pytest", "skills/synthesis-context-lifecycle/scripts/", "skills/synthesis-implementation-integrity/scripts/", "-q"]),
    ("pytest.onboarding", ["python3", "-m", "pytest", "skills/synthesis-onboarding/scripts/test_onboard.py", "-q"]),
    ("onboarding.catalog-scaffolds", ["python3", "skills/synthesis-onboarding/scripts/check_scaffolds.py", "."]),
    ("pytest.release", ["python3", "-m", "pytest", "skills/synthesis-skills-manager/scripts/test_release.py", "-q"]),
    ("meeting-transcripts.completeness", ["python3", "skills/synthesis-meeting-transcripts/test_verify_transcripts.py"]),
    ("meeting-transcripts.primary", ["python3", "skills/synthesis-meeting-transcripts/test_transcript_primary.py"]),
    ("pytest.rituals-guard-hooks", ["python3", "-m", "pytest", "skills/synthesis-daily-rituals/scripts/", "skills/synthesis-message-guard/scripts/", "skills/synthesis-git-hooks/scripts/", "skills/synthesis-slack-sync/scripts/", "skills/synthesis-chief-of-staff/scripts/", "-q"]),
    ("pytest.kb-edit-okf", ["python3", "-m", "pytest", "skills/synthesis-kb-edit/scripts/", "skills/synthesis-okf/scripts/", "-q"]),
    ("compileall", ["python3", "-m", "compileall", "-q", "skills"]),
)


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Result:
    steps: list[Step] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.steps.append(Step(name, ok, detail))
        marker = "PASS" if ok else "FAIL"
        line = f"{marker} {name}"
        if detail:
            line += f": {detail}"
        print(line, flush=True)
        return ok

    @property
    def failed(self) -> list[Step]:
        return [s for s in self.steps if not s.ok]


@dataclass(frozen=True)
class AcceptanceAuthority:
    """The exact accepted state that must survive to the publish boundary."""

    change_base: str
    expected: dict[str, object]
    receipt: dict[str, object]


@dataclass(frozen=True)
class CodexCacheSnapshot:
    """Complete recovery trees retained across Codex's cache transition."""

    backup: Path
    versions: tuple[str, ...]
    archive: Path | None = None


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_value(repo: Path, arguments: list[str]) -> tuple[str | None, str]:
    completed = run(["git", *arguments], cwd=repo)
    value = completed.stdout.strip()
    if completed.returncode != 0 or not value:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        return None, detail
    return value, ""


def acceptance_change_base(repo: Path) -> tuple[str | None, str]:
    """Resolve the base at the release boundary, never from manifest prose."""

    supplied = os.environ.get("SYNTHESIS_ACCEPTANCE_CHANGE_BASE", "").strip()
    if supplied:
        resolved, detail = _git_value(
            repo, ["rev-parse", "--verify", f"{supplied}^{{commit}}"]
        )
        return resolved, detail

    parents, detail = _git_value(repo, ["rev-list", "--parents", "-n", "1", "HEAD"])
    if parents:
        fields = parents.split()
        if len(fields) >= 3:
            return fields[1], "merge first parent"

    branch, branch_detail = _git_value(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch and branch != "main":
        base, merge_detail = _git_value(repo, ["merge-base", "HEAD", "origin/main"])
        if base:
            return base, "feature branch merge-base with origin/main"
        return None, merge_detail
    return None, detail or branch_detail or (
        "set SYNTHESIS_ACCEPTANCE_CHANGE_BASE, use a feature branch with origin/main, "
        "or run from the resulting merge commit"
    )


def acceptance_expectation(
    repo: Path, change_base: str, transaction_id: str
) -> tuple[dict[str, object] | None, str]:
    base_sha, detail = _git_value(
        repo, ["rev-parse", "--verify", f"{change_base}^{{commit}}"]
    )
    if not base_sha:
        return None, f"change-base: {detail}"
    head_sha, detail = _git_value(repo, ["rev-parse", "--verify", "HEAD^{commit}"])
    if not head_sha:
        return None, f"change-head: {detail}"
    ancestor = run(["git", "merge-base", "--is-ancestor", base_sha, head_sha], cwd=repo)
    if ancestor.returncode != 0:
        return None, "change-base is not an ancestor of HEAD"
    head_tree, detail = _git_value(
        repo, ["rev-parse", "--verify", f"{head_sha}^{{tree}}"]
    )
    if not head_tree:
        return None, f"head-tree: {detail}"
    changed = run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            f"{base_sha}..{head_sha}",
            "--",
        ],
        cwd=repo,
    )
    if changed.returncode != 0:
        return None, changed.stderr.strip() or "git diff failed"
    changed_paths = sorted(
        {line.strip() for line in changed.stdout.splitlines() if line.strip()}
    )
    manifest = repo / ACCEPTANCE_MANIFEST
    try:
        manifest_bytes = manifest.read_bytes()
    except OSError as exc:
        return None, f"acceptance manifest unreadable: {exc}"
    serialized_paths = ("\n".join(changed_paths) + "\n").encode("utf-8")
    return {
        "transaction_id": transaction_id,
        "change_base": base_sha,
        "change_head": head_sha,
        "head_tree": head_tree,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "changed_paths": changed_paths,
        "changed_paths_sha256": _sha256_bytes(serialized_paths),
    }, ""


def validate_acceptance_receipt(
    receipt: object, expected: dict[str, object]
) -> tuple[bool, str]:
    if not isinstance(receipt, dict):
        return False, "runner output is not a JSON object"
    for field, expected_value in expected.items():
        if receipt.get(field) != expected_value:
            return False, f"receipt {field} does not match the release transaction"
    fixed = {
        "receipt_schema": "acceptance-run-receipt-v1",
        "receipt_consumer": ACCEPTANCE_CONSUMER_ID,
        "metadata_class": "acceptance-test",
        "issues_authority_receipt": False,
        "ok": True,
    }
    for field, expected_value in fixed.items():
        if receipt.get(field) != expected_value:
            return False, f"receipt {field} is invalid"
    coverage = receipt.get("coverage")
    if not isinstance(coverage, dict):
        return False, "receipt coverage is missing"
    declared = coverage.get("declared")
    terminal = coverage.get("terminal")
    if (
        not isinstance(declared, int)
        or isinstance(declared, bool)
        or declared <= 0
        or terminal != declared
        or coverage.get("not_run") != 0
    ):
        return False, "receipt coverage is not closed and terminal"
    cases = receipt.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != declared
        or not all(isinstance(case, dict) and case.get("matched") is True for case in cases)
    ):
        return False, "receipt cases are incomplete or mismatched"
    return True, "fresh transaction-bound receipt consumed"


def consume_acceptance(
    repo: Path, result: Result, dry_run: bool
) -> AcceptanceAuthority | None:
    # PRINCIPAL RULE (controlling plan D4): even a dry run reconstructs the
    # receipt. Skipping it would make the dry-run publish path unable to prove
    # that authority remains current at the boundary it models.
    change_base, detail = acceptance_change_base(repo)
    if not change_base:
        result.add(
            "checks.acceptance.r5",
            False,
            f"authoritative change-base unavailable: {detail}",
        )
        return None
    transaction_id = secrets.token_hex(16)
    expected, detail = acceptance_expectation(repo, change_base, transaction_id)
    if expected is None:
        result.add("checks.acceptance.r5", False, detail)
        return None
    command = [
        "python3",
        str(ACCEPTANCE_RUNNER),
        "run",
        "--manifest",
        str(ACCEPTANCE_MANIFEST),
        "--repo-root",
        ".",
        "--change-base",
        change_base,
        "--transaction-id",
        transaction_id,
        "--json",
    ]
    completed = run(command, cwd=repo)
    if completed.returncode != 0:
        tail = (completed.stdout or completed.stderr).strip().splitlines()
        result.add(
            "checks.acceptance.r5",
            False,
            tail[-1] if tail else "acceptance runner failed",
        )
        return None
    try:
        receipt = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        result.add(
            "checks.acceptance.r5", False, f"runner receipt is not valid JSON: {exc}"
        )
        return None
    refreshed, detail = acceptance_expectation(repo, change_base, transaction_id)
    if refreshed is None or refreshed != expected:
        result.add(
            "checks.acceptance.r5",
            False,
            detail or "source state changed while acceptance executed",
        )
        return None
    status = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo)
    if status.returncode != 0 or status.stdout.strip():
        result.add(
            "checks.acceptance.r5",
            False,
            "source worktree changed while acceptance executed",
        )
        return None
    valid, detail = validate_acceptance_receipt(receipt, expected)
    result.add("checks.acceptance.r5", valid, detail)
    if not valid:
        return None
    return AcceptanceAuthority(
        change_base=change_base,
        expected=expected,
        receipt=receipt,
    )


def revalidate_acceptance_authority(
    repo: Path, authority: AcceptanceAuthority
) -> tuple[bool, str]:
    """Expire authority unless every accepted source binding still matches."""

    transaction_id = authority.expected.get("transaction_id")
    if not isinstance(transaction_id, str) or not transaction_id:
        return False, "accepted transaction id is unavailable"
    refreshed, detail = acceptance_expectation(
        repo, authority.change_base, transaction_id
    )
    if refreshed is None:
        return False, detail
    if refreshed != authority.expected:
        return False, "accepted source state changed before publication"
    status = run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo
    )
    if status.returncode != 0:
        return False, "source worktree state could not be established"
    if status.stdout.strip():
        return False, "source worktree changed before publication"
    return validate_acceptance_receipt(authority.receipt, authority.expected)


def read_manifest_version(path: Path) -> str | None:
    """Return the version in a plugin.json, or None if unreadable."""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("version") or "") or None
    except (OSError, ValueError):
        return None


def source_version(repo: Path) -> tuple[str | None, str]:
    """Return the single agreed source version, or None when manifests disagree."""
    found = {m: read_manifest_version(repo / m) for m in MANIFESTS}
    distinct = {v for v in found.values() if v}
    detail = ", ".join(f"{k}={v}" for k, v in found.items())
    if len(distinct) != 1 or any(v is None for v in found.values()):
        return None, detail
    return distinct.pop(), detail


def changelog_top_version(repo: Path) -> str | None:
    """Return the version of the newest CHANGELOG entry."""
    try:
        for line in (repo / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                token = stripped[3:].strip().lstrip("[").split("]")[0].split()[0]
                return token or None
    except (OSError, IndexError):
        return None
    return None


def client_reported_version(client: str) -> tuple[str | None, str | None]:
    """Ask the client CLI for its enabled plugin version and load path.

    Returns (version, load_path). Either may be None when the client cannot be
    reached or reports nothing — both are treated as failures by the caller,
    never as an implicit pass.
    """
    binary = resolve_client_binary(client)
    if not binary:
        return None, None
    result = run([binary, "plugin", "list", "--json"], timeout=180)
    if result.returncode != 0:
        return None, None
    try:
        data = json.loads(_first_json(result.stdout + "\n" + result.stderr))
    except (ValueError, TypeError):
        return None, None
    if client == "claude":
        items = data if isinstance(data, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("id", "")).startswith(f"{PLUGIN_NAME}@") and item.get("enabled", True):
                return str(item.get("version") or "") or None, item.get("installPath")
        return None, None
    installed = data.get("installed", []) if isinstance(data, dict) else []
    for item in installed:
        if not isinstance(item, dict):
            continue
        if item.get("name") == PLUGIN_NAME and item.get("enabled", True):
            source = item.get("source") or {}
            return str(item.get("version") or "") or None, source.get("path")
    return None, None


def _first_json(text: str) -> str:
    """Extract the first JSON document from mixed CLI output.

    The opener that appears EARLIEST wins. Trying '[' before '{' regardless of
    position looks equivalent and is not: an object whose body contains an
    array (``{"installed": [...]}`` — Codex's exact shape) would yield the
    inner array and silently lose every field around it.
    """
    candidates = [(text.find(opener), opener, closer) for opener, closer in (("[", "]"), ("{", "}"))]
    candidates = sorted((start, opener, closer) for start, opener, closer in candidates if start != -1)
    for start, opener, closer in candidates:
        depth = 0
        for index in range(start, len(text)):
            if text[index] == opener:
                depth += 1
            elif text[index] == closer:
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return ""


def installed_root(client: str, version: str) -> Path:
    """The conventional pinned install root both clients use."""
    base = Path.home() / (".claude" if client == "claude" else ".codex")
    return base / "plugins" / "cache" / MARKETPLACE / PLUGIN_NAME / version


def plugin_cache_parent(client: str) -> Path:
    """Return the directory containing this plugin's versioned cache roots."""
    return installed_root(client, "0.0.0").parent


STABLE_ROOT = Path(
    os.environ.get("SYNTHESIS_STABLE_PLUGIN_ROOT", str(Path.home() / ".synthesis" / "plugins"))
)


def stable_path() -> Path:
    """The version-independent path instruction files and sessions may pin.

    Versioned cache paths go stale on the next release — a session on a
    months-old engine read the shared board as corrupt on 2026-09-01, and the
    personal workspace's own day-start commands pinned a release twenty
    versions behind. The stable path is synthesis-owned, outside the
    client-owned caches (which the clients replace on their own schedule),
    and is repointed atomically only after both clients verified a version.
    """
    return STABLE_ROOT / PLUGIN_NAME / "current"


def refresh_stable_path(
    version: str, result: Result, dry_run: bool, *, target: Path | None = None
) -> bool:
    link = stable_path()
    root = target or installed_root("claude", version)
    if dry_run:
        return result.add("install.stable-path", True, f"would point {link} -> {root}")
    manifest = root / ".claude-plugin" / "plugin.json"
    try:
        installed = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError) as exc:
        return result.add(
            "install.stable-path", False, f"{root} is not a verified install root: {exc}"
        )
    if installed != version:
        return result.add(
            "install.stable-path", False, f"{root} carries {installed}, expected {version}"
        )
    link.parent.mkdir(parents=True, exist_ok=True)
    staging = link.with_name(link.name + ".tmp")
    if staging.is_symlink() or staging.exists():
        staging.unlink()
    os.symlink(root, staging)
    os.replace(staging, link)
    resolved = Path(os.path.realpath(link))
    return result.add(
        "install.stable-path",
        resolved == Path(os.path.realpath(root)),
        f"{link} -> {root}",
    )


def _tree_digest(root: Path) -> str:
    """Hash recovery-owned paths and bytes, excluding client-managed metadata."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: str(item.relative_to(root))):
        relative_path = path.relative_to(root)
        if (
            relative_path.parts
            and relative_path.parts[0] in RECOVERY_DIGEST_IGNORED_ROOTS
        ):
            continue
        relative = str(relative_path).encode("utf-8")
        if path.is_symlink():
            digest.update(b"L\0" + relative + b"\0" + os.readlink(path).encode("utf-8"))
        elif path.is_dir():
            digest.update(b"D\0" + relative)
        elif path.is_file():
            digest.update(b"F\0" + relative + b"\0" + path.read_bytes())
    return digest.hexdigest()


def codex_cache_archive() -> Path:
    """Durable recovery source for cache roots retained by running tasks."""
    return (
        Path.home()
        / ".synthesis"
        / "plugin-cache-recovery"
        / MARKETPLACE
        / PLUGIN_NAME
    )


def _acquire_codex_cache_lock():
    """Acquire the single-writer lock for the Codex cache transition."""
    lock_path = codex_cache_archive().parent / f".{PLUGIN_NAME}.release.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    handle = os.fdopen(descriptor, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        handle.close()
        raise OSError(
            "another release process owns the Codex cache transition lock"
        ) from None
    return handle


def _release_codex_cache_lock(handle) -> None:
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    handle.close()


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]


def _real_version_roots(parent: Path) -> dict[str, Path]:
    if not parent.is_dir():
        return {}
    return {
        source.name: source
        for source in sorted(parent.iterdir(), key=lambda path: path.name)
        if not source.is_symlink()
        and source.is_dir()
        and RELEASE_VERSION_RE.fullmatch(source.name) is not None
    }


def _release_tags(repo: Path) -> list[str]:
    completed = run(["git", "tag", "--list", "v*"], cwd=repo)
    if completed.returncode != 0:
        raise OSError(completed.stderr.strip() or "could not list release tags")
    return sorted(
        {
            tag[1:]
            for tag in completed.stdout.splitlines()
            if tag.startswith("v") and RELEASE_VERSION_RE.fullmatch(tag[1:])
        },
        key=_version_key,
    )


def _export_release_tag(
    repo: Path,
    version: str,
    destination: Path,
    *,
    current_version: str,
) -> set[str]:
    """Export one immutable release tree without trusting tar member paths."""
    reference = "HEAD" if version == current_version else f"v{version}"
    completed = subprocess.run(
        ["git", "archive", "--format=tar", reference],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise OSError(detail or f"could not export v{version}")
    tracked: set[str] = set()
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise OSError(f"unsafe path in v{version}: {member.name}")
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(member.mode & 0o777)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isfile():
                source = archive.extractfile(member)
                if source is None:
                    raise OSError(f"unreadable file in v{version}: {member.name}")
                target.write_bytes(source.read())
                target.chmod(member.mode & 0o777)
            elif member.issym():
                link = PurePosixPath(member.linkname)
                if link.is_absolute() or ".." in link.parts:
                    raise OSError(
                        f"unsafe symlink in v{version}: {member.name} -> {member.linkname}"
                    )
                target.symlink_to(member.linkname)
            else:
                raise OSError(f"unsupported archive entry in v{version}: {member.name}")
            tracked.add(relative.as_posix())
    return tracked


def _copy_cache_extras(source: Path, destination: Path, tracked: set[str]) -> None:
    """Retain known client metadata while immutable tag bytes win collisions."""
    if not source.is_dir() or source.is_symlink():
        return
    for path in sorted(source.rglob("*"), key=lambda item: str(item.relative_to(source))):
        relative = path.relative_to(source)
        relative_text = relative.as_posix()
        target = destination / relative
        if not relative.parts or relative.parts[0] != ".codex-marketplace-install.json":
            continue
        if relative_text in tracked:
            continue
        if path.is_symlink():
            link = PurePosixPath(os.readlink(path))
            if link.is_absolute() or ".." in link.parts:
                raise OSError(f"unsafe cache symlink: {path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(os.readlink(path))
        elif path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _cache_root_completeness(root: Path, version: str) -> tuple[bool, str]:
    """Validate an untagged peer/archive root before trusting it as recovery source."""
    if not root.is_dir() or root.is_symlink():
        return False, "root is absent, not a directory, or a symlink"
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        link = PurePosixPath(os.readlink(path))
        if link.is_absolute() or ".." in link.parts:
            return False, f"unsafe symlink is present: {path.relative_to(root)}"
    manifest_versions = {
        read_manifest_version(root / manifest)
        for manifest in MANIFESTS
        if (root / manifest).is_file()
    }
    if version not in manifest_versions:
        return False, f"no plugin manifest reports {version}"
    hooks = root / "hooks" / "hooks.json"
    if not hooks.is_file():
        return False, "hooks/hooks.json is missing"
    try:
        hook_text = hooks.read_text(encoding="utf-8")
        json.loads(hook_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, f"hooks/hooks.json is unreadable: {exc}"
    hook_targets = sorted(set(HOOK_PLUGIN_PATH_RE.findall(hook_text)))
    if not hook_targets:
        return False, "hooks/hooks.json declares no plugin-root command target"
    missing_targets = [target for target in hook_targets if not (root / target).is_file()]
    if missing_targets:
        return False, f"missing hook target(s): {', '.join(missing_targets[:3])}"
    if not any(root.glob("skills/*/SKILL.md")):
        return False, "no skill entry point is present"
    return True, f"{len(hook_targets)} hook target(s) and skill tree present"


def _copy_legacy_cache_root(source: Path, destination: Path) -> None:
    """Copy a complete pre-tag cache tree without client liveness markers."""
    shutil.copytree(
        source,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".in_use"),
    )


def _tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _persist_codex_archive(
    backup: Path, versions: list[str], archive: Path
) -> None:
    archive.mkdir(parents=True, exist_ok=True)
    for version in versions:
        source = backup / version
        destination = archive / version
        if destination.is_symlink():
            raise OSError(f"recovery archive root is a symlink: {destination}")
        shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
        if _tree_digest(source) != _tree_digest(destination):
            raise OSError(f"recovery archive differs after write: {destination}")


def snapshot_codex_caches(
    result: Result, repo: Path | None = None
) -> CodexCacheSnapshot | None:
    """Build complete tag-backed snapshots before Codex's destructive refresh.

    Existing cache roots alone are not proof of completeness: a prior refresh
    can leave only the one file a stranded Stop hook needed. When a source
    checkout is supplied, immutable release tags provide every tracked byte;
    cache-only metadata is layered on top. A durable, budgeted archive lets a
    later release recover roots that a previous client transition removed.
    """
    parent = plugin_cache_parent("codex")
    archive = codex_cache_archive() if repo is not None else None
    backup = Path(tempfile.mkdtemp(prefix="synthesis-codex-cache-"))
    try:
        peers = {
            "Codex cache": parent,
            "Claude cache": plugin_cache_parent("claude"),
        }
        if archive is not None:
            peers["recovery archive"] = archive
        for label, root in peers.items():
            if root.is_symlink():
                raise OSError(f"{label} root is a symlink: {root}")
        cache_roots = _real_version_roots(parent)
        peer_roots = _real_version_roots(peers["Claude cache"])
        archive_roots = _real_version_roots(archive) if archive is not None else {}
        boundary_versions = set(cache_roots) | set(peer_roots) | set(archive_roots)
        preserved_versions = set(boundary_versions)
        seed_versions = set(boundary_versions)
        tags: list[str] = []
        current_version: str | None = None
        if repo is not None:
            tags = _release_tags(repo)
            current_version, detail = source_version(repo)
            if current_version is None:
                raise OSError(detail)
            if current_version not in tags:
                tags.append(current_version)
                tags.sort(key=_version_key)
            if boundary_versions:
                low = min(boundary_versions, key=_version_key)
                high = max(boundary_versions, key=_version_key)
                preserved_versions.update(
                    version
                    for version in tags
                    if _version_key(low) <= _version_key(version) <= _version_key(high)
                )
            seed_versions.update(preserved_versions)
            seed_versions.add(current_version)

        for version in sorted(seed_versions, key=_version_key):
            destination = backup / version
            if repo is None:
                source = cache_roots.get(version) or archive_roots.get(version)
                if source is None:
                    raise OSError(f"no recovery source for cache version {version}")
                shutil.copytree(source, destination, symlinks=True)
                continue
            if version not in tags:
                candidates = [
                    ("recovery archive", archive_roots.get(version)),
                    ("Claude cache", peer_roots.get(version)),
                    ("Codex cache", cache_roots.get(version)),
                ]
                rejected: list[str] = []
                for label, source in candidates:
                    if source is None:
                        continue
                    complete, completeness_detail = _cache_root_completeness(
                        source, version
                    )
                    if complete:
                        _copy_legacy_cache_root(source, destination)
                        break
                    rejected.append(f"{label}: {completeness_detail}")
                else:
                    detail = "; ".join(rejected) or "no peer or archive root exists"
                    raise OSError(
                        f"immutable tag v{version} is unavailable and no complete "
                        f"legacy recovery root was found ({detail})"
                    )
                continue
            tracked = _export_release_tag(
                repo,
                version,
                destination,
                current_version=current_version or "",
            )
            if version in archive_roots:
                _copy_cache_extras(archive_roots[version], destination, tracked)
            if version in peer_roots:
                _copy_cache_extras(peer_roots[version], destination, tracked)
            if version in cache_roots:
                _copy_cache_extras(cache_roots[version], destination, tracked)

        if archive is not None:
            projected_bytes = _tree_bytes(backup)
            if projected_bytes > CODEX_CACHE_ARCHIVE_BUDGET_BYTES:
                raise OSError(
                    "recovery archive would exceed the 512 MiB hard budget; "
                    "no historical root was deleted automatically"
                )
            _persist_codex_archive(
                backup, sorted(seed_versions, key=_version_key), archive
            )
            if _tree_bytes(archive) > CODEX_CACHE_ARCHIVE_BUDGET_BYTES:
                raise OSError("recovery archive exceeds the 512 MiB hard budget")
            result.add(
                "install.codex.cache-archive",
                True,
                f"verified {len(seed_versions)} complete recovery root(s)",
            )
    except (OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        result.add(
            "install.codex.cache-snapshot",
            False,
            f"could not preserve complete active-session cache roots; recovery copy kept at {backup}: {exc}",
        )
        return None
    versions = tuple(sorted(preserved_versions, key=_version_key))
    result.add(
        "install.codex.cache-snapshot",
        True,
        f"preserved {len(versions)} complete version root(s) before refresh",
    )
    return CodexCacheSnapshot(backup=backup, versions=versions, archive=archive)


def _remove_transition_backup(backup: Path) -> None:
    """Remove only a validated mkdtemp directory created by this module."""
    resolved = backup.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if (
        resolved.parent != temporary_root
        or not resolved.name.startswith("synthesis-codex-cache-")
        or resolved.is_symlink()
    ):
        raise OSError(f"refusing unsafe transition-backup cleanup target: {backup}")
    shutil.rmtree(resolved)


def _restore_codex_caches_once(
    snapshot: CodexCacheSnapshot,
) -> tuple[set[str], set[str]]:
    """Restore or repair one observed generation of the cache tree."""
    parent = plugin_cache_parent("codex")
    restored: set[str] = set()
    repaired: set[str] = set()
    parent.mkdir(parents=True, exist_ok=True)
    for version in snapshot.versions:
        source = snapshot.backup / version
        destination = parent / version
        if destination.is_symlink():
            raise OSError(f"version root became a symlink: {destination}")
        if not destination.exists():
            shutil.copytree(source, destination, symlinks=True)
            restored.add(version)
        elif not destination.is_dir():
            raise OSError(f"version root is not a directory: {destination}")
        elif _tree_digest(source) != _tree_digest(destination):
            shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
            repaired.add(version)
        if _tree_digest(source) != _tree_digest(destination):
            raise OSError(f"version root changed during refresh: {destination}")
    return restored, repaired


def restore_codex_caches(
    snapshot: CodexCacheSnapshot,
    result: Result,
    *,
    clock=time.monotonic,
    sleeper=time.sleep,
) -> bool:
    """Restore complete roots and require a quiet post-command cache window."""
    restored: set[str] = set()
    repaired: set[str] = set()
    started = clock()
    quiet_since = started
    try:
        while True:
            new_restored, new_repaired = _restore_codex_caches_once(snapshot)
            now = clock()
            if new_restored or new_repaired:
                restored.update(new_restored)
                repaired.update(new_repaired)
                quiet_since = now
            if now - quiet_since >= CODEX_CACHE_QUIET_SECONDS:
                _remove_transition_backup(snapshot.backup)
                break
            if now - started >= CODEX_CACHE_SETTLE_TIMEOUT_SECONDS:
                raise OSError(
                    "Codex cache did not remain unchanged for the required quiet window"
                )
            sleeper(CODEX_CACHE_POLL_SECONDS)
    except OSError as exc:
        return result.add(
            "install.codex.cache-restore",
            False,
            f"active-session cache preservation failed; recovery copy kept at {snapshot.backup}: {exc}",
        )
    return result.add(
        "install.codex.cache-restore",
        True,
        f"verified {len(snapshot.versions)} complete root(s) after a "
        f"{CODEX_CACHE_QUIET_SECONDS:g}s quiet window; restored {len(restored)}, "
        f"repaired {len(repaired)}",
    )


def content_digest_report(source_repo: Path, installed: Path) -> tuple[bool, str]:
    """Compare every source skills/ file against the installed tree by bytes.

    Version equality is a claim about a label; this is the check on the
    content behind it. The motivating false-green (2026-08-24): a skill was
    edited without a version bump, ``plugin update`` no-opped on the
    unchanged version, and both clients reported current while one loaded
    stale files. A release is not verified until the installed bytes equal
    the source bytes, whatever the version strings say.
    """
    skills_root = source_repo / "skills"
    if not skills_root.is_dir():
        return False, f"source skills/ missing at {skills_root}"
    mismatched: list[str] = []
    missing: list[str] = []
    compared = 0
    for path in sorted(skills_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_repo)
        if "__pycache__" in rel.parts or rel.suffix == ".pyc":
            continue
        counterpart = installed / rel
        if not counterpart.is_file():
            missing.append(str(rel))
            continue
        compared += 1
        if _sha256_bytes(path.read_bytes()) != _sha256_bytes(counterpart.read_bytes()):
            mismatched.append(str(rel))
    if compared == 0 and not missing:
        return False, "no source files compared — refusing an empty verification"
    if missing or mismatched:
        sample = (missing + mismatched)[:3]
        return False, (
            f"{len(missing)} missing, {len(mismatched)} differing of "
            f"{compared + len(missing)} source files (e.g. {', '.join(sample)})"
        )
    return True, f"{compared} files byte-equal to source"


def deep_verify(client: str, expected: str, result: Result,
                repo: Path | None = None) -> bool:
    """Verify a client three ways: its report, the manifest it loads, and
    the installed bytes against the source tree.

    The later halves exist because the first can lie. A stale marketplace
    snapshot, a hand-made cache directory, or a partial install can all leave a
    client reporting a version whose files are not the ones on disk — and an
    unbumped version can leave on-disk version equality vouching for stale
    content.
    """
    reported, load_path = client_reported_version(client)
    ok_reported = result.add(
        f"verify.{client}.reported",
        reported == expected,
        f"cli reports {reported or 'nothing'} (expected {expected})",
    )

    manifest_name = ".claude-plugin" if client == "claude" else ".codex-plugin"
    candidates = [installed_root(client, expected)]
    if load_path:
        candidates.append(Path(load_path))
    seen: list[str] = []
    ok_disk = False
    for candidate in candidates:
        manifest = candidate / manifest_name / "plugin.json"
        on_disk = read_manifest_version(manifest)
        if on_disk:
            seen.append(f"{candidate}={on_disk}")
        if on_disk == expected:
            ok_disk = True
    result.add(
        f"verify.{client}.on-disk",
        ok_disk,
        "; ".join(seen) if seen else "no readable plugin manifest at any reported root",
    )
    ok_content = False
    if repo is not None:
        content_root = next(
            (c for c in candidates
             if read_manifest_version(c / manifest_name / "plugin.json") == expected),
            candidates[0],
        )
        ok_content, detail = content_digest_report(repo, content_root)
        result.add(f"verify.{client}.content", ok_content, detail)
    else:
        result.add(f"verify.{client}.content", False,
                   "no source repo supplied for content comparison")
    return ok_reported and ok_disk and ok_content


def refresh_client(
    client: str, result: Result, dry_run: bool, repo: Path | None = None
) -> bool:
    """Refresh one client's marketplace snapshot and installed plugin."""
    binary = resolve_client_binary(client)
    if not binary:
        return result.add(f"install.{client}", False, "client binary not found")
    if client == "claude":
        commands = [
            [binary, "plugin", "marketplace", "update", MARKETPLACE],
            [binary, "plugin", "update", f"{PLUGIN_NAME}@{MARKETPLACE}"],
        ]
    else:
        # Codex refreshes the git marketplace snapshot, then installs FROM it.
        # Skipping the upgrade leaves the snapshot stale even when the install
        # appears to succeed — the exact failure this script exists to prevent.
        commands = [
            [binary, "plugin", "marketplace", "upgrade", MARKETPLACE],
            [binary, "plugin", "add", f"{PLUGIN_NAME}@{MARKETPLACE}"],
        ]
    cache_lock = None
    if client == "codex" and not dry_run and repo is not None:
        try:
            cache_lock = _acquire_codex_cache_lock()
        except OSError as exc:
            return result.add("install.codex.cache-lock", False, str(exc))
        result.add("install.codex.cache-lock", True, "single writer acquired")
    try:
        cache_snapshot = None
        if client == "codex" and not dry_run:
            cache_snapshot = snapshot_codex_caches(result, repo=repo)
            if cache_snapshot is None:
                return False

        commands_ok = True
        for command in commands:
            label = f"install.{client}.{command[2] if len(command) > 2 else 'run'}"
            if dry_run:
                result.add(label, True, "dry-run: " + " ".join(command[1:]))
                continue
            completed = run(command, timeout=600)
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout).strip().splitlines()
                result.add(label, False, tail[-1] if tail else "command failed")
                commands_ok = False
                break
            result.add(label, True, " ".join(command[1:]))
        caches_ok = True
        if cache_snapshot is not None:
            caches_ok = restore_codex_caches(cache_snapshot, result)
        return commands_ok and caches_ok
    finally:
        if cache_lock is not None:
            _release_codex_cache_lock(cache_lock)


def install_codex_cache_guardian(
    repo: Path, result: Result, dry_run: bool
) -> bool:
    """Install the durable supervisor that repairs later Codex cache generations."""
    source = repo / CACHE_GUARDIAN
    if not source.is_file() or source.is_symlink():
        return result.add(
            "install.codex.cache-guardian",
            False,
            f"guardian source is unavailable or unsafe: {source}",
        )
    command = [sys.executable, str(source), "--install"]
    if dry_run:
        return result.add(
            "install.codex.cache-guardian",
            True,
            "dry-run: " + " ".join(command[1:]),
        )
    completed = run(command, cwd=repo, timeout=120)
    output = (completed.stdout or completed.stderr).strip().splitlines()
    detail = output[-1] if output else "guardian command produced no receipt"
    return result.add(
        "install.codex.cache-guardian", completed.returncode == 0, detail
    )


def _coordination_board_path() -> Path:
    override = os.environ.get("SYNTHESIS_COORDINATION_BOARD", "").strip()
    return Path(override).expanduser() if override else DEFAULT_COORDINATION_BOARD


def _train_session_selector() -> tuple[str | None, str]:
    """This process's coordination identity: env first, then the pointer."""
    explicit = os.environ.get("SYNTHESIS_COORDINATION_SESSION", "").strip()
    if explicit:
        return explicit, "environment"
    override = os.environ.get("SYNTHESIS_ACTIVE_PROJECT_FILE", "").strip()
    pointer = (
        Path(override).expanduser() if override else DEFAULT_ACTIVE_PROJECT_POINTER
    )
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "unavailable"
    owner = str(payload.get("owner_session") or "").strip()
    return (owner, "active-project pointer") if owner else (None, "unavailable")


def train_check(result: Result) -> bool:
    """Fail closed unless this session holds the release train on the board.

    A machine without a coordination board has not adopted train
    serialization (public contributors); the check passes with a notice.
    Where a board exists, an unheld or peer-held train refuses — waiting is
    the point. A crashed holder is released by the user via the stale-claim
    review, never by another agent on its own initiative.
    """
    board = _coordination_board_path()
    if not board.is_file():
        return result.add(
            "preflight.release-train",
            True,
            f"no coordination board at {board}; train serialization not "
            "adopted on this machine",
        )
    coordination_scripts = (
        SCRIPT_DIR.parents[1] / "synthesis-project-management" / "scripts"
    )
    if str(coordination_scripts) not in sys.path:
        sys.path.insert(0, str(coordination_scripts))
    try:
        import coordination
    except Exception as exc:  # board present but engine missing: unverifiable
        return result.add(
            "preflight.release-train",
            False,
            f"board exists but the coordination engine is unavailable ({exc}); "
            "the release train cannot be verified",
        )
    refresh = coordination.lease_refresh(board)
    if refresh.get("error"):
        return result.add(
            "preflight.release-train",
            False,
            f"board lease refresh failed; the local mirror may be stale: "
            f"{refresh['error']}",
        )
    try:
        sessions = coordination.rows(board.read_text(encoding="utf-8"))
    except Exception as exc:
        return result.add(
            "preflight.release-train", False, f"board unreadable: {exc}"
        )
    holders = [
        session
        for session in sessions
        if coordination.active(session)
        and any(claim.strip() == TRAIN_RESOURCE for claim in session.claims)
    ]
    if not holders:
        return result.add(
            "preflight.release-train",
            False,
            f"nobody holds {TRAIN_RESOURCE}; claim it before authoring or "
            "publishing a release: coordination.py claim ... --area "
            f"{TRAIN_RESOURCE}",
        )
    selector, source = _train_session_selector()
    if selector is None:
        return result.add(
            "preflight.release-train",
            False,
            f"{TRAIN_RESOURCE} is held by {holders[0].label} and this process "
            "has no session identity; set SYNTHESIS_COORDINATION_SESSION or "
            "run with an owned active-project pointer",
        )
    mine = [
        session
        for session in holders
        if coordination.selector_matches(session.identity, selector)
    ]
    if mine:
        return result.add(
            "preflight.release-train",
            True,
            f"held by this session ({mine[0].label}, selector via {source})",
        )
    return result.add(
        "preflight.release-train",
        False,
        f"{TRAIN_RESOURCE} is held by {holders[0].label}, not this session; "
        "wait for its release, coordinate on the board message bus, or — for "
        "a genuinely dead holder — ask the user to run the stale-claim "
        "review (coordination.py stale)",
    )


def preflight(repo: Path, result: Result, install_only: bool) -> str | None:
    """Validate the release is coherent before anything is published."""
    version, detail = source_version(repo)
    if not result.add("preflight.manifests-agree", version is not None, detail):
        return None
    if not install_only:
        top = changelog_top_version(repo)
        result.add(
            "preflight.changelog-matches",
            top == version,
            f"CHANGELOG newest={top}, manifests={version}",
        )
        status = run(["git", "status", "--porcelain"], cwd=repo)
        dirty = [ln for ln in status.stdout.splitlines() if ln.strip()]
        result.add(
            "preflight.tree-clean",
            not dirty,
            f"{len(dirty)} uncommitted path(s)" if dirty else "clean",
        )
        train_check(result)
    return version


def publish(
    repo: Path,
    result: Result,
    dry_run: bool,
    authority: AcceptanceAuthority,
    version: str,
) -> bool:
    """Atomically publish edge, stable, and immutable pin refs per remote."""
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()
    if not result.add("publish.on-main", branch == "main", f"branch={branch or 'unknown'}"):
        return False
    valid, detail = revalidate_acceptance_authority(repo, authority)
    if not result.add("publish.acceptance", valid, detail):
        return False
    accepted_head = authority.expected.get("change_head")
    if not isinstance(accepted_head, str) or not accepted_head:
        return result.add(
            "publish.accepted-head", False, "receipt-bound head is unavailable"
        )
    if not RELEASE_VERSION_RE.fullmatch(version):
        return result.add(
            "publish.version-tag", False, f"invalid release version: {version}"
        )
    refspecs = [
        f"{accepted_head}:refs/heads/main",
        f"{accepted_head}:refs/heads/stable",
        f"{accepted_head}:refs/tags/v{version}",
    ]
    remotes = sorted(
        {
            line.split()[0]
            for line in run(["git", "remote", "-v"], cwd=repo).stdout.splitlines()
            if line.strip().endswith("(push)")
        }
    )
    if not result.add("publish.remotes", bool(remotes), ", ".join(remotes) or "none configured"):
        return False
    for remote in remotes:
        valid, detail = revalidate_acceptance_authority(repo, authority)
        if not result.add(f"publish.acceptance.{remote}", valid, detail):
            return False
        if dry_run:
            result.add(
                f"publish.push.{remote}", True, "dry-run atomic: " + " ".join(refspecs)
            )
            continue
        # PRINCIPAL RULE (controlling plan D4): the pushed object is immutable.
        # A concurrent branch movement cannot substitute a different commit
        # after the final authority check.
        completed = run(
            ["git", "push", "--atomic", remote] + refspecs,
            cwd=repo,
            timeout=600,
        )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip().splitlines()
            return result.add(f"publish.push.{remote}", False, tail[-1] if tail else "push failed")
        result.add(
            f"publish.push.{remote}", True, "atomically pushed " + " ".join(refspecs)
        )
    return True


def run_required_checks(
    repo: Path, result: Result, dry_run: bool
) -> AcceptanceAuthority | None:
    for name, command in REQUIRED_CHECKS:
        if dry_run:
            result.add(f"checks.{name}", True, "dry-run")
            continue
        completed = run(command, cwd=repo)
        passed = completed.returncode == 0
        tail = (completed.stdout or completed.stderr).strip().splitlines()
        result.add(
            f"checks.{name}",
            passed,
            "" if passed else (tail[-1] if tail else "failed"),
        )
        if not passed:
            return None
    return consume_acceptance(repo, result, dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".", help="synthesis-skills checkout (default: cwd)")
    parser.add_argument("--install-only", action="store_true", help="refresh + verify clients only")
    parser.add_argument("--check-only", action="store_true", help="preflight + required checks only")
    parser.add_argument(
        "--acceptance-only",
        action="store_true",
        help="consume the transaction-bound acceptance receipt only",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan; mutate nothing")
    args = parser.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    if "plugins" in repo.parts and "cache" in repo.parts:
        print(f"FAIL preflight.repo-root: {repo} is an installed cache, not the source checkout")
        return 2
    if not (repo / ".claude-plugin" / "plugin.json").is_file():
        print(f"FAIL preflight.repo-root: {repo} is not a synthesis-skills checkout")
        return 2

    result = Result()
    version = preflight(repo, result, args.install_only)
    if version is None or result.failed:
        print("\nRELEASE ABORTED: preflight failed. Nothing was published or installed.")
        return 2 if version is None else 1

    if args.acceptance_only:
        if args.install_only or args.check_only:
            print("\nRELEASE ABORTED: --acceptance-only cannot be combined with other modes.")
            return 2
        if consume_acceptance(repo, result, args.dry_run) is None:
            print("\nACCEPTANCE REFUSED: no release authority was issued.")
            return 1
        print(f"\nACCEPTANCE CONSUMED for {version}. Nothing published or installed.")
        return 0

    if not args.install_only:
        authority = run_required_checks(repo, result, args.dry_run)
        if authority is None:
            print("\nRELEASE ABORTED: required checks failed. Nothing was published.")
            return 1
        if args.check_only:
            print(f"\nCHECKS PASSED for {version}. Nothing published (--check-only).")
            return 0
        if not publish(repo, result, args.dry_run, authority, version):
            print("\nRELEASE ABORTED: publish failed. Clients left untouched.")
            return 1

    for client in ("claude", "codex"):
        refresh_client(client, result, args.dry_run, repo=repo)

    install_codex_cache_guardian(repo, result, args.dry_run)

    if args.dry_run:
        print(f"\nDRY RUN complete for {version}. No state changed.")
        return 0

    verified = all(deep_verify(client, version, result, repo=repo)
                   for client in ("claude", "codex"))
    if not verified or result.failed:
        print(
            f"\nRELEASE INCOMPLETE for {version}: "
            f"{len(result.failed)} step(s) failed. The clients are NOT confirmed current — "
            "re-run with --install-only after fixing."
        )
        return 1
    if not refresh_stable_path(version, result, args.dry_run):
        print(
            f"\nRELEASE INCOMPLETE for {version}: the stable path could not be "
            "repointed at the verified install — re-run with --install-only."
        )
        return 1
    print(f"\nRELEASED {version}: published, installed, and verified on both clients.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
