#!/usr/bin/env python3
"""Gated cross-client release for the synthesis-skills plugin.

A release is not finished when `main` is pushed. The plugin *is* the repository
— the marketplace manifests carry no version and point at `./` — so publishing
is a push. But every client keeps a version-pinned installation that does not
follow the remote on its own, so a pushed-but-uninstalled release leaves the
running clients silently behind their own source.

This script makes that state unreachable by sequencing the whole operation
behind one command that fails closed:

    preflight -> required checks -> publish -> install selected clients -> verify

Configured lifecycle selections define the native targets. Without a configured
profile, the publisher retains its explicit Claude, Codex, and Muse install flow
without inventing a lifecycle selection.

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
import contextlib
import fcntl
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "synthesis-agent-conformance" / "scripts"))
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "synthesis-onboarding" / "scripts"))

try:
    from client_binaries import resolve_client_binary
except ImportError:  # pragma: no cover - resolved at runtime in the repo
    def resolve_client_binary(name: str):  # type: ignore[misc]
        import shutil

        override = os.environ.get(
            {"claude": "SYNTHESIS_CLAUDE_BIN", "codex": "SYNTHESIS_CODEX_BIN", "muse": "SYNTHESIS_MUSE_BIN"}.get(name, "")
        )
        if override is not None and override != "":
            return override if Path(override).is_file() else None
        if override == "":
            return None
        return shutil.which(name)

from bootstrap import materialize_release
from cache_guardian import GuardianError as CacheGuardianError
from cache_guardian import _tree_digest as _guardian_tree_digest
from cache_guardian import RecoveryStore, persist_archive
from system_contract import (ContractError, SystemState, activate_cli, atomic_write_json,
                             canonical_tracked_tree_digest, canonical_tree_digest,
                             descriptor_fields, json_digest, validate_release_descriptor,
                             verify_materialized_release, verify_native_release_inventory)


PLUGIN_NAME = "synthesis-skills"
MARKETPLACE = "synthesis-engineering"
MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json")
ACCEPTANCE_MANIFEST = Path(
    "skills/synthesis-implementation-integrity/acceptance-suite.yaml"
)
ACCEPTANCE_RUNNER = Path(
    "skills/synthesis-implementation-integrity/scripts/acceptance_suite.py"
)
CACHE_GUARDIAN = Path(
    "skills/synthesis-skills-manager/scripts/cache_guardian.py"
)
GIT_HOOKS_INSTALLER = Path(
    "skills/synthesis-git-hooks/scripts/install.sh"
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
    ("pytest.checkpoint", ["python3", "-m", "pytest", "skills/synthesis-checkpoint/scripts/", "-q"]),
    ("pytest.autopilot", ["python3", "-m", "pytest", "skills/synthesis-autopilot/scripts/", "-q"]),
    ("pytest.promotion-gate", ["python3", "-m", "pytest", "skills/synthesis-promotion-gate/scripts/", "-q"]),
    ("pytest.context-lifecycle-integrity", ["python3", "-m", "pytest", "skills/synthesis-context-lifecycle/scripts/", "skills/synthesis-implementation-integrity/scripts/", "-q"]),
    ("pytest.onboarding", ["python3", "-m", "pytest", "skills/synthesis-onboarding/scripts/", "-q"]),
    ("onboarding.catalog-scaffolds", ["python3", "skills/synthesis-onboarding/scripts/check_scaffolds.py", "."]),
    ("onboarding.capabilities", ["python3", "skills/synthesis-onboarding/scripts/check_capabilities.py", "."]),
    ("pytest.release", ["python3", "-m", "pytest", "skills/synthesis-skills-manager/scripts/test_release.py", "-q"]),
    ("pytest.guardrails", ["python3", "-m", "pytest", "skills/synthesis-agent-guardrails/tests/", "-q"]),
    ("meeting-transcripts.completeness", ["python3", "skills/synthesis-meeting-transcripts/test_verify_transcripts.py"]),
    ("meeting-transcripts.primary", ["python3", "skills/synthesis-meeting-transcripts/test_transcript_primary.py"]),
    ("pytest.rituals-guard-hooks", ["python3", "-m", "pytest", "skills/synthesis-daily-rituals/scripts/", "skills/synthesis-bitbucket/scripts/", "skills/synthesis-message-guard/scripts/", "skills/synthesis-git-hooks/scripts/", "skills/synthesis-slack-sync/scripts/", "skills/synthesis-chief-of-staff/scripts/", "skills/synthesis-repo-guard/", "skills/synthesis-decision-packet/scripts/", "-q"]),
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
    verified_roots: dict[str, Path] = field(default_factory=dict)

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
    client_owned_version: str | None = None
    native_sources: dict[str, tuple[str, frozenset[str]]] = field(default_factory=dict)
    native_recoveries: dict[str, NativeCacheRecovery] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeCacheRecovery:
    """Exact retained native metadata, outside the client-owned cache tree."""

    source: Path
    tree: Path
    manifest: Path
    digest: str
    manifest_digest: str
    intent_digest: str
    commit: str
    source_identity: tuple[int, ...]
    bundle_identity: tuple[int, int]


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
    if branch == "main" and parents:
        fields = parents.split()
        if len(fields) == 2:
            return fields[1], "single-parent release commit; parent is the release boundary"
    return None, detail or branch_detail or (
        "set SYNTHESIS_ACCEPTANCE_CHANGE_BASE, use a feature branch with origin/main, "
        "or run from the release commit on main"
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
            "--no-renames",
            "--name-only",
            "-z",
            "--diff-filter=ACDMRTUXB",
            f"{base_sha}..{head_sha}",
            "--",
        ],
        cwd=repo,
    )
    if changed.returncode != 0:
        return None, changed.stderr.strip() or "git diff failed"
    changed_paths = sorted(
        {path for path in changed.stdout.split("\0") if path}
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


def _runner_failure_detail(output: str) -> str:
    """Name the failing cases from a runner receipt.

    The runner prints a JSON receipt whose last line is always `}`, so
    reporting the raw tail renders every runner failure as
    `FAIL checks.acceptance.r5: }`. Parse the receipt and name the
    unmatched cases plus the first error line instead.
    """
    try:
        receipt = json.loads(output)
    except (TypeError, ValueError):
        lines = (output or "").strip().splitlines()
        meaningful = [
            ln.strip()
            for ln in lines
            if ln.strip() and set(ln.strip()) - set("{}")
        ]
        return meaningful[-1] if meaningful else "acceptance runner failed"
    if not isinstance(receipt, dict):
        return "acceptance runner failed"
    bad = [
        case
        for case in receipt.get("cases", [])
        if isinstance(case, dict) and not case.get("matched", False)
    ]
    if bad:
        names = ", ".join(str(case.get("id", "?")) for case in bad)
        first = (bad[0].get("stderr") or bad[0].get("stdout") or "").strip().splitlines()
        err = first[-1].strip() if first else "no runner output"
        return f"{len(bad)} case(s) unmatched: {names}; first error: {err}"
    errors = receipt.get("errors")
    if errors:
        return "; ".join(str(error) for error in errors[:3])
    return "acceptance runner failed"


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
        result.add(
            "checks.acceptance.r5",
            False,
            _runner_failure_detail(completed.stdout or completed.stderr),
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
    if client == "muse":
        command = [binary, "plugins", "list", "--json"]
    else:
        command = [binary, "plugin", "list", "--json"]
    result = run(command, timeout=180)
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
    if client == "muse":
        record = _muse_record_from_list(data)
        if record is None or not record.get("enabled", True):
            return None, None
        return str(record.get("version") or "") or None, record.get("cache_path")
    installed = data.get("installed", []) if isinstance(data, dict) else []
    for item in installed:
        if not isinstance(item, dict):
            continue
        if item.get("name") == PLUGIN_NAME and item.get("enabled", True):
            source = item.get("source") or {}
            return str(item.get("version") or "") or None, source.get("path")
    return None, None


def _muse_install_record(binary: str) -> dict | None:
    """Return Muse's install record for this plugin, or None when absent.

    Muse refuses ``plugins install`` from a new path while a record exists
    ("already installed from a different source"), so refresh branches on
    record existence: a present record is synced in place and updated, a
    missing record is installed fresh. Existence — not enabled state —
    decides, because a disabled record still blocks a fresh install.
    """
    result = run([binary, "plugins", "list", "--json"], timeout=180)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(_first_json(result.stdout + "\n" + result.stderr))
    except (ValueError, TypeError):
        return None
    return _muse_record_from_list(data)


def _muse_record_from_list(data: object) -> dict | None:
    """Extract this plugin's install record from a parsed list document."""
    items = data.get("plugins", []) if isinstance(data, dict) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        record = item.get("record") or {}
        if isinstance(record, dict) and record.get("id") == PLUGIN_NAME:
            return record
    return None


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
    """The conventional pinned install root each client uses.

    Muse's installed bytes live under a content-addressed cache path that
    changes with every release, so its conventional root is the
    synthesis-owned bundle the install refreshes from — the load path the
    CLI reports covers the cache side.
    """
    if client == "muse":
        return muse_bundle_dir(version)
    base = Path.home() / (".claude" if client == "claude" else ".codex")
    return base / "plugins" / "cache" / MARKETPLACE / PLUGIN_NAME / version


def plugin_cache_parent(client: str) -> Path:
    """Return the directory containing this plugin's versioned cache roots."""
    return installed_root(client, "0.0.0").parent


MUSE_BUNDLE_ROOT = Path(
    os.environ.get(
        "SYNTHESIS_MUSE_BUNDLE_ROOT",
        str(Path.home() / ".cache" / "synthesis" / "muse-bundle"),
    )
)


def muse_bundle_dir(version: str) -> Path:
    """The version-stamped local bundle Muse installs refresh from.

    Muse installs synthesis-skills from a local bundle rather than a git
    marketplace snapshot, so the release stages the versioned tree here and
    installs from it; ``muse plugins install`` over the existing record is
    idempotent and re-caches from the bundle path.
    """
    return MUSE_BUNDLE_ROOT / f"v{version}"


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
    and is repointed atomically only after all selected clients verified a version.
    """
    return STABLE_ROOT / PLUGIN_NAME / "current"


def refresh_stable_path(
    version: str, result: Result, dry_run: bool, *, target: Path | None = None,
    repo: Path | None = None,
) -> bool:
    link = stable_path()
    if target is None or repo is None:
        return result.add("install.stable-path", False, "an exact verified native root and release source are required")
    root = target
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
    ok, detail = content_digest_report(repo, root)
    if not ok:
        return result.add("install.stable-path", False, detail)
    identity = (root.stat().st_dev, root.stat().st_ino)
    if link.exists() and not link.is_symlink():
        return result.add("install.stable-path", False, "existing stable path is not a managed symbolic link")
    previous = os.readlink(link) if link.is_symlink() else None
    link.parent.mkdir(parents=True, exist_ok=True)
    staging = link.with_name("." + link.name + "." + secrets.token_hex(8))
    os.symlink(root, staging)
    os.replace(staging, link)
    # Client caches can change after verification. Recheck the actual consumer
    # after publication and restore the preceding pointer on observed drift.
    # Later cache changes remain the guardian's responsibility.
    try:
        resolved = Path(os.path.realpath(link))
        ok, detail = content_digest_report(repo, root)
        ok = ok and resolved == root and (root.stat().st_dev, root.stat().st_ino) == identity
    except OSError as exc:
        ok, detail = False, str(exc)
    if not ok:
        if link.is_symlink() and os.readlink(link) == str(root):
            if previous is None:
                link.unlink()
            else:
                os.symlink(previous, staging)
                os.replace(staging, link)
        return result.add("install.stable-path", False, "native root changed at stable publication; prior pointer preserved: " + detail)
    return result.add(
        "install.stable-path",
        True,
        f"{link} -> {root}",
    )


def _tree_digest(root: Path) -> str:
    """Use the guardian's one canonical historical-root integrity policy."""
    try:
        return _guardian_tree_digest(root)
    except CacheGuardianError as exc:
        raise OSError(str(exc)) from exc


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
    archive = codex_cache_archive()
    if not archive.is_absolute() or not archive.name:
        raise OSError(f"unsafe Codex recovery archive boundary: {archive}")
    _validate_native_recovery_store(archive.with_name(archive.name + "-native-retained"), plugin_cache_parent("codex"))
    lock_path = archive.parent / f".{PLUGIN_NAME}.release.lock"
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
    persist_archive(archive, {version: backup / version for version in versions}, budget=CODEX_CACHE_ARCHIVE_BUDGET_BYTES)


def _native_recovery_inventory(root: Path) -> dict[str, list]:
    """Hash every byte and mode, including Git and otherwise ignored metadata.

    This is deliberately separate from the historical release/archive policy.
    No links are traversed and unsupported types fail before a native command.
    """
    entries: dict[str, list] = {}
    pending = [root]
    while pending:
        path = pending.pop()
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        relative = str(path.relative_to(root))
        if stat.S_ISDIR(info.st_mode):
            entries[relative] = ["directory", mode]
            pending.extend(sorted(path.iterdir(), reverse=True))
        elif stat.S_ISLNK(info.st_mode):
            entries[relative] = ["link", mode, os.readlink(path)]
        elif stat.S_ISREG(info.st_mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                if (opened.st_dev, opened.st_ino, opened.st_mode) != (info.st_dev, info.st_ino, info.st_mode):
                    raise OSError(f"retained native file changed identity: {path}")
                digest = hashlib.sha256()
                size = 0
                while size < info.st_size and (chunk := handle.read(min(1024 * 1024, info.st_size - size))):
                    digest.update(chunk)
                    size += len(chunk)
                if handle.read(1):
                    raise OSError(f"retained native file grew during inspection: {path}")
                after = os.fstat(handle.fileno())
            if (size != info.st_size or (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                    != (info.st_size, info.st_mtime_ns, info.st_ctime_ns)):
                raise OSError(f"retained native file changed during inspection: {path}")
            entries[relative] = ["file", mode, size, digest.hexdigest()]
        else:
            raise OSError(f"unsupported retained native file type: {path}")
        if len(entries) + len(pending) > 200_000:
            raise OSError("retained native recovery exceeds the 200000-entry inspection bound")
    return entries


def _native_inventory_digest(entries: dict[str, list]) -> str:
    return _sha256_bytes(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode())


def _validate_native_recovery_store(store: Path, cache: Path) -> None:
    archive = codex_cache_archive()
    protected = {Path.home().resolve(), Path.cwd().resolve(), SCRIPT_DIR.parents[2]}
    if (store != archive.with_name(archive.name + "-native-retained")
            or not store.is_absolute() or store.resolve() != store
            or any(root == store or root.is_relative_to(store) for root in protected)
            or any(store == root or store.is_relative_to(root) or root.is_relative_to(store)
                   for root in (cache, archive))):
        raise OSError(f"unsafe retained native recovery store: {store}")
    for ancestor in (store, *store.parents):
        if (ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir())
                or (ancestor / ".git").exists() or (ancestor / ".git").is_symlink()
                or (ancestor / ".agents/repos.yaml").exists()):
            raise OSError(f"redirected retained native recovery store: {ancestor}")


def _write_native_recovery_record(path: Path, value: dict) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    identity = _cache_transition_parent_identity(path.parent)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = "." + path.name + "-" + secrets.token_hex(16) + ".tmp"
    try:
        opened = os.fstat(directory)
        if (opened.st_dev, opened.st_ino) != identity:
            raise OSError(f"native recovery record parent changed identity: {path.parent}")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        # Link publishes the fully synced seal atomically and cannot overwrite
        # an unexpected existing record. Failed attempts remain for inspection.
        os.link(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        os.unlink(temporary, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)
    return _sha256_bytes(raw)


def _read_native_recovery_record(path: Path) -> tuple[dict, str]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 64 * 1024 * 1024):
            raise OSError(f"unsafe native recovery record: {path}")
        raw = handle.read(info.st_size + 1)
        after = os.fstat(handle.fileno())
    if (len(raw) != info.st_size or (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            != (info.st_size, info.st_mtime_ns, info.st_ctime_ns)):
        raise OSError(f"native recovery record changed during inspection: {path}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate recovery record key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise OSError(f"unreadable native recovery record: {path}") from exc
    if not isinstance(value, dict):
        raise OSError(f"invalid native recovery record: {path}")
    return value, _sha256_bytes(raw)


def _native_recovery_catalog(store: Path) -> tuple[dict[str, dict], str | None]:
    """Durable plans distinguish interrupted publication from lost recovery."""
    path = store.with_name(store.name + ".json")
    if not store.exists() and not store.is_symlink() and not path.exists() and not path.is_symlink():
        return {}, None
    data, digest = _read_native_recovery_record(path)
    records = data.get("records")
    if (set(data) != {"schema_version", "records"} or data.get("schema_version") != 1
            or not isinstance(records, dict)):
        raise OSError(f"invalid native preservation catalog: {path}")
    for name, entry in records.items():
        if (not isinstance(name, str) or re.fullmatch(r"retained-[0-9a-f]{32}", name) is None
                or not isinstance(entry, dict) or set(entry) != {"state", "intent", "intent_digest", "manifest_digest"}
                or not isinstance(entry["state"], str) or entry["state"] not in {"PLANNED", "VERIFIED"}
                or not isinstance(entry["intent"], dict)
                or entry["intent_digest"] != _sha256_bytes((json.dumps(entry["intent"], indent=2, sort_keys=True) + "\n").encode())
                or (entry["state"] == "PLANNED" and entry["manifest_digest"] is not None)
                or (entry["state"] == "VERIFIED" and (not isinstance(entry["manifest_digest"], str)
                    or re.fullmatch(r"[0-9a-f]{64}", entry["manifest_digest"]) is None))):
            raise OSError(f"invalid native preservation plan: {path}")
    if store.is_symlink() or (store.exists() and not store.is_dir()):
        raise OSError(f"native preservation store is redirected: {store}")
    observed = {child.name for child in store.iterdir()} if store.exists() else set()
    if not observed <= set(records):
        raise OSError(f"native preservation bundle membership changed: {store}")
    for name, entry in records.items():
        bundle = store / name
        if name not in observed:
            if entry["state"] == "VERIFIED":
                raise OSError(f"verified native preservation bundle is missing: {bundle}")
            continue
        _cache_transition_parent_identity(bundle)
        intent = bundle / "intent.json"
        if intent.exists() or intent.is_symlink() or entry["state"] == "VERIFIED":
            if _read_native_recovery_record(intent)[1] != entry["intent_digest"]:
                raise OSError(f"native preservation intent changed: {bundle}")
        if entry["state"] == "VERIFIED":
            if _read_native_recovery_record(bundle / "manifest.json")[1] != entry["manifest_digest"]:
                raise OSError(f"native preservation seal changed: {bundle}")
    return records, digest


def _publish_native_recovery_catalog(store: Path, records: dict[str, dict], previous: str | None) -> None:
    path = store.with_name(store.name + ".json")
    candidate = path.with_name("." + path.name + "-" + secrets.token_hex(16))
    _write_native_recovery_record(candidate, {"schema_version": 1, "records": records})
    if previous is None:
        # No-overwrite publication of the initial catalog.
        os.link(candidate, path, follow_symlinks=False)
        candidate.unlink()
    else:
        if _read_native_recovery_record(path)[1] != previous:
            raise OSError(f"native preservation catalog changed during update: {path}")
        os.replace(candidate, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _native_recovery_version(name: str) -> str | None:
    if RELEASE_VERSION_RE.fullmatch(name):
        return name
    match = re.fullmatch(r"\.release-displaced-([0-9]+\.[0-9]+\.[0-9]+)-[0-9a-f]{32}", name)
    return match[1] if match else None


def _native_roots_to_preserve(parent: Path) -> list[Path]:
    roots = []
    if not parent.exists():
        return roots
    for child in sorted(parent.iterdir()):
        if child.name.startswith(".release-"):
            if (not child.name.startswith(".release-displaced-") or _native_recovery_version(child.name) is None
                    or child.is_symlink() or not child.is_dir()):
                raise OSError(f"unrecognized or interrupted native recovery path; review before refresh: {child}")
            roots.append(child)
        elif RELEASE_VERSION_RE.fullmatch(child.name) and ((child / ".git").exists() or (child / ".git").is_symlink()):
            roots.append(child)
    return roots


def _load_native_recoveries(repo: Path | None, current_version: str | None) -> dict[str, NativeCacheRecovery]:
    """Resume durable plans only from exact originals or complete sealed copies.

    A verified catalog entry never falls back to its original if preservation
    artifacts disappear. Incomplete attempts remain available for review.
    """
    parent, archive = plugin_cache_parent("codex"), codex_cache_archive()
    store = archive.with_name(archive.name + "-native-retained")
    _validate_native_recovery_store(store, parent)
    catalog, catalog_digest = _native_recovery_catalog(store)
    records: dict[str, NativeCacheRecovery] = {}
    pending = []
    expected_keys = {"schema_version", "source", "version", "commit", "tree", "digest", "disposition", "inventory", "state"}
    for name, entry in sorted(catalog.items()):
        bundle = store / name
        intent, intent_digest = entry["intent"], entry["intent_digest"]
        version, tree_name = intent.get("version"), intent.get("tree")
        if (set(intent) != expected_keys or intent.get("schema_version") != 1
                or intent.get("state") != "COPYING" or intent.get("disposition") != "RETAINED_FOR_SEPARATE_REVIEW"
                or not isinstance(version, str) or RELEASE_VERSION_RE.fullmatch(version) is None
                or not isinstance(tree_name, str) or _native_recovery_version(tree_name) != version
                or intent.get("source") != str(parent / tree_name) or not isinstance(intent.get("inventory"), dict)
                or _native_inventory_digest(intent["inventory"]) != intent.get("digest") or repo is None):
            raise OSError(f"unproven native recovery intent: {bundle}")
        reference = "HEAD" if version == current_version else f"v{version}"
        commit, _ = _git_value(repo, ["rev-parse", "--verify", reference + "^{commit}"])
        if commit is None or re.fullmatch(r"[0-9a-f]{40}", commit) is None or intent.get("commit") != commit:
            raise OSError(f"native recovery no longer binds an immutable release: {bundle}")
        manifest = bundle / "manifest.json"
        if not manifest.exists() and not manifest.is_symlink():
            pending.append((bundle, intent))
            continue
        ready, manifest_digest = _read_native_recovery_record(manifest)
        tree = bundle / tree_name
        if (ready != {**intent, "state": "VERIFIED"} or tree.is_symlink() or not tree.is_dir()
                or _native_recovery_inventory(tree) != intent["inventory"]
                or _read_native_recovery_record(bundle / "intent.json")[1] != intent_digest):
            raise OSError(f"native recovery seal differs from its complete copy: {bundle}")
        _codex_native_git_identity(tree, commit)
        if entry["state"] == "PLANNED":
            # A crash after the fsynced ready seal but before catalog advancement
            # is recoverable only by re-verifying the complete sealed tree.
            catalog[name] = {**entry, "state": "VERIFIED", "manifest_digest": manifest_digest}
            _publish_native_recovery_catalog(store, catalog, catalog_digest)
            _, catalog_digest = _native_recovery_catalog(store)
        record = NativeCacheRecovery(parent / tree_name, tree, manifest, intent["digest"],
                                     manifest_digest, intent_digest, commit, (), _cache_transition_parent_identity(bundle))
        _verify_native_recoveries(CodexCacheSnapshot(bundle, (), native_recoveries={str(manifest): record}))
        records[str(manifest)] = record
    for bundle, intent in pending:
        if any(record.source == Path(intent["source"]) and record.commit == intent["commit"]
               and record.digest == intent["digest"] for record in records.values()):
            continue
        source = Path(intent["source"])
        if (not source.is_dir() or source.is_symlink()
                or _native_recovery_inventory(source) != intent["inventory"]):
            raise OSError(f"interrupted native preservation has no exact original or complete recovery: {bundle}")
        _codex_native_git_identity(source, intent["commit"])
    return records


def _preserve_native_recovery(source: Path, commit: str) -> NativeCacheRecovery:
    """Copy a proven retained checkout before allowing native cache deletion.

    Incomplete attempts and completed bundles are never automatically removed.
    Only a verified bundle returned here can authorize the following refresh.
    """
    parent = plugin_cache_parent("codex")
    version = _native_recovery_version(source.name)
    if version is None or source.parent != parent or source.is_symlink() or not source.is_dir():
        raise OSError(f"unrecognized retained native recovery path: {source}")
    _validate_codex_cache_boundary(parent / version, parent, allow_retained=True)
    parent_identity = _cache_transition_parent_identity(parent)
    expected = _native_recovery_inventory(source)
    identity = _codex_native_git_identity(source, commit)
    archive = codex_cache_archive()
    store = archive.with_name(archive.name + "-native-retained")
    _validate_native_recovery_store(store, parent)
    catalog, previous_catalog = _native_recovery_catalog(store)
    bundle = store / ("retained-" + secrets.token_hex(16))
    tree = bundle / source.name
    digest = _native_inventory_digest(expected)
    payload = {"schema_version": 1, "source": str(source), "version": version,
               "commit": commit, "tree": tree.name, "digest": digest,
               "disposition": "RETAINED_FOR_SEPARATE_REVIEW", "inventory": expected}
    intent = {**payload, "state": "COPYING"}
    intent_digest = _sha256_bytes((json.dumps(intent, indent=2, sort_keys=True) + "\n").encode())
    entry = {"state": "PLANNED", "intent": intent, "intent_digest": intent_digest, "manifest_digest": None}
    store.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # The complete durable intent precedes both directories. A process can die
    # at any following boundary without creating an unregistered bundle.
    _publish_native_recovery_catalog(store, {**catalog, bundle.name: entry}, previous_catalog)
    catalog, previous_catalog = _native_recovery_catalog(store)
    try:
        store.mkdir(mode=0o700, exist_ok=True)
        store_identity = _cache_transition_parent_identity(store)
        bundle.mkdir(mode=0o700)
        _write_native_recovery_record(bundle / "intent.json", intent)
        shutil.copytree(source, tree, symlinks=True)
        if (_native_recovery_inventory(tree) != expected
                or _native_recovery_inventory(source) != expected
                or _codex_native_git_identity(source, commit) != identity):
            raise OSError("retained native checkout changed or copied bytes/modes differ")
        _codex_native_git_identity(tree, commit)
        _validate_native_recovery_store(store, parent)
        if (_cache_transition_parent_identity(parent) != parent_identity
                or _cache_transition_parent_identity(store) != store_identity):
            raise OSError("retained native preservation parent changed identity")
        # Commit file and directory contents before recording verified recovery.
        for path in [*tree.rglob("*"), tree]:
            if not path.is_symlink():
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    mode = os.fstat(descriptor).st_mode
                    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                        raise OSError(f"retained native copy changed file type: {path}")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        manifest = bundle / "manifest.json"
        manifest_digest = _write_native_recovery_record(manifest, {**payload, "state": "VERIFIED"})
        for path in (bundle, store):
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        _publish_native_recovery_catalog(store,
                                        {**catalog, bundle.name: {**entry, "state": "VERIFIED", "manifest_digest": manifest_digest}},
                                        previous_catalog)
    except BaseException:
        print(f"Native recovery preservation interrupted before refresh; source path {source}; recovery attempt path {bundle}", flush=True)
        raise
    info = bundle.stat()
    return NativeCacheRecovery(source, tree, manifest, digest, manifest_digest, intent_digest, commit,
                               identity, (info.st_dev, info.st_ino))


def _verify_native_recoveries(snapshot: CodexCacheSnapshot, *, sources: bool = False,
                              allow_missing_sources: bool = False) -> None:
    parent = plugin_cache_parent("codex")
    if sources:
        observed = set(_native_roots_to_preserve(parent))
        expected = {record.source for record in snapshot.native_recoveries.values() if record.source_identity}
        if observed - expected or (not allow_missing_sources and observed != expected):
            raise OSError("retained native recovery membership changed before refresh")
    for record in snapshot.native_recoveries.values():
        bundle, store = record.tree.parent, record.tree.parent.parent
        _validate_native_recovery_store(store, parent)
        catalog, _ = _native_recovery_catalog(store)
        if (re.fullmatch(r"retained-[0-9a-f]{32}", bundle.name) is None
                or catalog.get(bundle.name, {}).get("state") != "VERIFIED"
                or catalog[bundle.name]["intent_digest"] != record.intent_digest
                or catalog[bundle.name]["manifest_digest"] != record.manifest_digest
                or record.source.parent != parent or record.tree.name != record.source.name
                or _native_recovery_version(record.tree.name) is None
                or _cache_transition_parent_identity(bundle) != record.bundle_identity
                or record.manifest != bundle / "manifest.json" or record.manifest.is_symlink()
                or not record.manifest.is_file()
                or _read_native_recovery_record(record.manifest)[1] != record.manifest_digest
                or (bundle / "intent.json").is_symlink() or not (bundle / "intent.json").is_file()
                or _read_native_recovery_record(bundle / "intent.json")[1] != record.intent_digest
                or record.tree.is_symlink() or not record.tree.is_dir()
                or _native_inventory_digest(_native_recovery_inventory(record.tree)) != record.digest):
            raise OSError(f"retained native recovery is missing, changed or redirected: {bundle}")
        _codex_native_git_identity(record.tree, record.commit)
        source_present = record.source.exists() or record.source.is_symlink()
        if (sources and record.source_identity and (source_present or not allow_missing_sources)
                and (_codex_native_git_identity(record.source, record.commit) != record.source_identity
                     or _native_inventory_digest(_native_recovery_inventory(record.source)) != record.digest)):
            raise OSError(f"retained native source changed before refresh: {record.source}")


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
    native_sources: dict[str, tuple[str, frozenset[str]]] = {}
    native_recoveries: dict[str, NativeCacheRecovery] = {}
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
        if archive is not None:
            stored = RecoveryStore.read(archive)
            for version in stored.versions:
                restored_archive = backup / ".archive-input" / version
                stored.materialize(version, restored_archive)
                archive_roots[version] = restored_archive
        retained_roots = _native_roots_to_preserve(parent)
        retained_versions = {_native_recovery_version(root.name) for root in retained_roots}
        boundary_versions = set(cache_roots) | set(peer_roots) | set(archive_roots) | retained_versions
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
            reference = "HEAD" if version == current_version else f"v{version}"
            commit, detail = _git_value(repo, ["rev-parse", "--verify", reference + "^{commit}"])
            if commit is None or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
                raise OSError(f"cannot bind native recovery source for {version}: {detail}")
            native_sources[version] = (commit, frozenset(tracked))
            # Git records child modes but no mode for the release root itself.
            # Keep its prior archive identity; new tagged roots use one declared
            # mode rather than inheriting the publisher's changing umask.
            destination.chmod(stat.S_IMODE(archive_roots[version].stat().st_mode) if version in archive_roots else 0o755)
            if version in archive_roots:
                _copy_cache_extras(archive_roots[version], destination, tracked)
            if version in peer_roots:
                _copy_cache_extras(peer_roots[version], destination, tracked)
            if version in cache_roots:
                _copy_cache_extras(cache_roots[version], destination, tracked)

        if archive is not None:
            native_recoveries.update(_load_native_recoveries(repo, current_version))
        for root in retained_roots:
            version = _native_recovery_version(root.name)
            if version not in native_sources:
                raise OSError(f"retained native recovery has no immutable release binding: {root}")
            record = _preserve_native_recovery(root, native_sources[version][0])
            native_recoveries[str(record.manifest)] = record
        if native_recoveries:
            result.add("install.codex.cache-native-preservation", True,
                       "verified exact native recovery bundles outside client cache; retained for separate review: "
                       + ", ".join(str(record.manifest) for record in native_recoveries.values()))

        if archive is not None:
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
    except (CacheGuardianError, OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
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
    return CodexCacheSnapshot(backup=backup, versions=versions, archive=archive,
                              client_owned_version=current_version, native_sources=native_sources,
                              native_recoveries=native_recoveries)


def _remove_transition_backup(backup: Path) -> None:
    """Remove only a validated mkdtemp directory created by this module."""
    resolved = backup.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if (
        backup.is_symlink()
        or not backup.is_dir()
        or resolved in (Path.home().resolve(), Path.cwd().resolve())
        or (resolved / ".git").exists()
        or Path.cwd().resolve().is_relative_to(resolved)
        or
        resolved.parent != temporary_root
        or not resolved.name.startswith("synthesis-codex-cache-")
    ):
        raise OSError(f"refusing unsafe transition-backup cleanup target: {backup}")
    shutil.rmtree(resolved)


def _cache_transition_parent_identity(parent: Path) -> tuple[int, int]:
    """Reject ancestor redirects before a tree mutation or cleanup."""
    if not parent.is_absolute() or any(p.is_symlink() for p in (parent, *parent.parents)):
        raise OSError(f"unsafe cache-transition parent: {parent}")
    if not parent.is_dir() or parent.resolve() != parent:
        raise OSError(f"unsafe cache-transition parent: {parent}")
    info = parent.stat()
    return info.st_dev, info.st_ino


def _remove_cache_transition_tree(path: Path, parent: Path, prefix: str) -> None:
    parent_identity = _cache_transition_parent_identity(parent)
    if not path.exists() and not path.is_symlink():
        return
    protected = {Path.home().resolve(), Path.cwd().resolve(), SCRIPT_DIR.parents[2]}
    if (
        path.parent != parent or not prefix.startswith(".release-")
        or not path.name.startswith(prefix) or path.is_symlink() or not path.is_dir()
        or any(p == path or p.is_relative_to(path) for p in protected)
        or any(child.name == ".git" for child in path.rglob("*"))
    ):
        raise OSError(f"refusing unsafe cache-transition cleanup target: {path}")
    # Bind recursive removal to the verified parent, including if its pathname
    # is concurrently replaced. Python's fd-based rmtree never follows links.
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) != parent_identity:
            raise OSError(f"cache-transition parent changed before cleanup: {parent}")
        if not shutil.rmtree.avoids_symlink_attacks:
            raise OSError("safe descriptor-based tree cleanup is unavailable")
        shutil.rmtree(path.name, dir_fd=descriptor)
    finally:
        os.close(descriptor)


def _replace_cache_root(
    source: Path, destination: Path, parent: Path, *,
    retain_displaced: bool = False,
    validate_destination: Callable[[], None] | None = None,
) -> Path | None:
    """Stage and verify before swapping; retain Muse's old source for recovery.

    The optional boundary check runs again after copying, immediately before
    either rename. Recovery examines the filesystem, not flags set after a
    syscall: an interruption can arrive after rename succeeds but before its
    next Python statement executes.
    """
    if destination.parent != parent or parent.is_symlink():
        raise OSError(f"refusing unsafe cache-repair boundary: {destination}")
    parent_identity = _cache_transition_parent_identity(parent)
    staging_prefix = f".release-repair-{destination.name}-"
    displaced_prefix = f".release-displaced-{destination.name}-"
    nonce = secrets.token_hex(16)
    staging = parent / f"{staging_prefix}{nonce}"
    displaced = parent / f"{displaced_prefix}{nonce}"
    had_destination = destination.exists()
    move_attempted = False
    prior_identity: tuple[int, int] | None = None
    replacement_identity: tuple[int, int] | None = None

    def identity(path: Path) -> tuple[int, int]:
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise OSError(f"cache-transition tree is not a real directory: {path}")
        return info.st_dev, info.st_ino

    try:
        if displaced.exists() or displaced.is_symlink():
            raise OSError(f"cache-transition recovery path already exists: {displaced}")
        shutil.copytree(source, staging, symlinks=True)
        replacement_identity = identity(staging)
        if _tree_digest(source) != _tree_digest(staging):
            raise OSError(f"staged repair differs from snapshot: {source}")
        if _cache_transition_parent_identity(parent) != parent_identity:
            raise OSError(f"cache-transition parent changed before replacement: {parent}")
        if validate_destination is not None:
            validate_destination()
        if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
            raise OSError(f"version root has an unsafe type: {destination}")
        if destination.exists():
            prior_identity = identity(destination)
            move_attempted = True
            os.rename(destination, displaced)
        if _cache_transition_parent_identity(parent) != parent_identity:
            raise OSError(f"cache-transition parent changed before promotion: {parent}")
        if destination.exists() or destination.is_symlink():
            raise OSError(f"cache-transition destination appeared before promotion: {destination}")
        os.rename(staging, destination)
        if (_cache_transition_parent_identity(parent) != parent_identity
                or identity(destination) != replacement_identity):
            raise OSError(f"cache-transition identity changed after promotion: {destination}")
        if _tree_digest(source) != _tree_digest(destination):
            raise OSError(f"atomically repaired root differs from snapshot: {destination}")
    except BaseException as exc:
        rollback_error: OSError | None = None
        if move_attempted and displaced.exists() and not displaced.is_symlink():
            try:
                if _cache_transition_parent_identity(parent) != parent_identity:
                    raise OSError(f"cache-transition parent changed before rollback: {parent}")
                if identity(displaced) != prior_identity:
                    raise OSError(f"recovery tree changed identity: {displaced}")
                if destination.exists() or destination.is_symlink():
                    if staging.exists() or staging.is_symlink():
                        raise OSError("destination and staging both exist; refusing to overwrite either")
                    if identity(destination) != replacement_identity:
                        raise OSError(f"destination changed identity; retained without moving: {destination}")
                    os.rename(destination, staging)
                os.rename(displaced, destination)
            except OSError as rollback_exc:
                rollback_error = rollback_exc
        elif not had_destination and not staging.exists() and destination.exists():
            try:
                if _cache_transition_parent_identity(parent) != parent_identity:
                    raise OSError(f"cache-transition parent changed before rollback: {parent}")
                if identity(destination) != replacement_identity:
                    raise OSError(f"destination changed identity; retained without moving: {destination}")
                os.rename(destination, staging)
            except OSError as rollback_exc:
                rollback_error = rollback_exc
        if rollback_error is not None:
            raise OSError(
                f"cache-root repair failed ({exc}); rollback failed ({rollback_error}); "
                f"recovery trees retained at {displaced} and {staging}"
            ) from exc
        raise
    finally:
        # A failed Muse transition must never discard bytes that may be the
        # only remaining recovery evidence. Successful renames consume staging.
        if not retain_displaced:
            _remove_cache_transition_tree(staging, parent, staging_prefix)
    if retain_displaced:
        return displaced if displaced.exists() else None
    _remove_cache_transition_tree(displaced, parent, displaced_prefix)
    return None


def _validate_codex_cache_boundary(path: Path, parent: Path, *, allow_retained: bool = False) -> None:
    """A version label is not authority to move a repository or workspace."""
    protected = {Path.home().resolve(), Path.cwd().resolve(), SCRIPT_DIR.parents[2]}
    if (not parent.is_absolute() or path.parent != parent
            or RELEASE_VERSION_RE.fullmatch(path.name) is None
            or parent == Path(parent.anchor) or parent.resolve() != parent
            or any(p == parent or p == path or p.is_relative_to(path) for p in protected)):
        raise OSError(f"unsafe Codex cache boundary: {path}")
    for ancestor in (parent, *parent.parents):
        if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
            raise OSError(f"redirected Codex cache ancestor: {ancestor}")
        if ((ancestor / ".git").exists() or (ancestor / ".git").is_symlink()
                or (ancestor / ".agents/repos.yaml").exists()):
            raise OSError(f"Codex cache parent is inside a repository or workspace: {ancestor}")
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise OSError(f"version root has an unsafe type: {path}")
    if not path.exists():
        recoveries = sorted(parent.glob(f".release-displaced-{path.name}-*"))
        if recoveries and not allow_retained:
            raise OSError(f"cache root absent after an interrupted transition; retained recovery trees: {recoveries}")
        return
    for child in path.rglob("*"):
        if child.name == ".git" and child != path / ".git":
            raise OSError(f"nested repository inside Codex cache: {child}")


def _codex_native_git_identity(root: Path, expected_commit: str | None) -> tuple[int, ...]:
    """Admit only a standalone native checkout of the pinned published commit.

    Inspect copied refs with controlled Git metadata and local objects only.
    Never load the checkout's configuration during an object lookup: a normal
    rev-parse can otherwise execute a promisor remote helper. No admitted
    Git-backed tree is deleted.
    """
    metadata = root / ".git"
    if (expected_commit is None or not metadata.is_dir() or metadata.is_symlink()
            or root.is_symlink() or not root.is_dir()):
        raise OSError(f"unproven native Git cache ownership: {root}")
    for child in root.rglob("*"):
        if child.name == ".git" and child != metadata:
            raise OSError(f"redirect or nested repository in native Git cache: {child}")
        if child.is_symlink():
            try:
                target = child.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise OSError(f"unverifiable native cache link: {child}") from exc
            if (child.is_relative_to(metadata) or not target.is_relative_to(root)
                    or target.is_relative_to(metadata)):
                raise OSError(f"native Git metadata or payload redirects ownership: {child}")
    for relative in ("commondir", "gitdir", "worktrees", "modules", "config.worktree",
                     "objects/info/alternates", "objects/info/http-alternates"):
        if (metadata / relative).exists():
            raise OSError(f"native Git metadata redirects repository ownership: {metadata / relative}")
    if list((metadata / "objects/pack").glob("*.promisor")):
        raise OSError(f"native Git objects require a promisor remote: {root}")
    marker = root / ".codex-marketplace-install.json"
    if marker.exists():
        if not marker.is_file() or marker.is_symlink():
            raise OSError(f"native cache installation identity is not a regular file: {root}")
        try:
            installed = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OSError(f"invalid native installation identity: {root}") from exc
        if (not isinstance(installed, dict) or installed.get("source_type") != "git"
                or installed.get("source") != "https://github.com/synthesisengineering/synthesis-skills.git"
                or installed.get("revision") != expected_commit or installed.get("sparse_paths") != []):
            raise OSError(f"native Git cache does not identify the pinned release: {root}")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0",
                       GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="", GIT_PROTOCOL_FROM_USER="0",
                       GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")

    def git(*arguments: str, cwd: Path, data: str | None = None) -> str:
        try:
            proc = subprocess.run(["git", "--no-pager", "-c", "core.hooksPath=" + os.devnull,
                                   "-c", "core.fsmonitor=false", "-c", "protocol.allow=never", *arguments],
                                  cwd=cwd, env=environment, input=data,
                                  capture_output=True, text=True, timeout=30)
        except subprocess.SubprocessError as exc:
            raise OSError(f"native Git identity check failed: {root}") from exc
        if proc.returncode:
            raise OSError(f"native Git identity is unverifiable: {root}: {proc.stderr.strip()}")
        return proc.stdout.strip()

    # Parse captured bytes through Git's parser without repository discovery or
    # include expansion. Subsequent Git commands use only this controlled temp
    # repository, so even a concurrent edit to the real config cannot run code.
    inputs: dict[str, bytes] = {}
    for path in [metadata / "config", metadata / "HEAD", metadata / "packed-refs",
                 *((metadata / "refs").rglob("*") if (metadata / "refs").is_dir() else ())]:
        if path.exists() and not path.is_dir():
            if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
                raise OSError(f"unsafe native Git identity file: {path}")
            inputs[str(path.relative_to(metadata))] = path.read_bytes()
    if "config" not in inputs or "HEAD" not in inputs:
        raise OSError(f"native Git identity metadata is incomplete: {root}")
    with tempfile.TemporaryDirectory(prefix="synthesis-git-inspect-") as temporary:
        inspection = Path(temporary)
        environment["GIT_CEILING_DIRECTORIES"] = str(inspection.parent.resolve())
        # An explicit file and a non-repository cwd prevent unsafe includes from
        # being read even during the initial repository setup for git config.
        try:
            configuration = git("config", "--file", "-", "--no-includes", "--null", "--list",
                                cwd=inspection, data=inputs["config"].decode("utf-8"))
        except UnicodeError as exc:
            raise OSError(f"native Git configuration is unreadable: {root}") from exc
        for entry in configuration.split("\0"):
            key, _, value = entry.partition("\n")
            key = key.lower()
            if (key.startswith(("include.", "includeif."))
                    or key in {"core.worktree", "extensions.worktreeconfig", "extensions.partialclone"}
                    or (key.startswith("remote.") and key.endswith((".promisor", ".partialclonefilter")))
                    or (key == "core.bare" and value.lower() != "false")):
                raise OSError(f"native Git configuration redirects ownership or requires a remote: {root}")
        isolated = inspection / ".git"
        (isolated / "objects").mkdir(parents=True)
        (isolated / "refs").mkdir()
        (isolated / "config").write_text("[core]\nrepositoryformatversion = 0\nbare = false\n")
        for relative, contents in inputs.items():
            if relative == "config":
                continue
            target = isolated / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
        environment["GIT_OBJECT_DIRECTORY"] = str(metadata / "objects")
        if git("rev-parse", "--verify", "HEAD^{commit}", cwd=inspection) != expected_commit:
            raise OSError(f"foreign Git checkout at native cache location: {root}")
    if any((metadata / relative).is_symlink() or (metadata / relative).read_bytes() != contents
           for relative, contents in inputs.items()):
        raise OSError(f"native Git identity changed during inspection: {root}")
    info, git_info = root.stat(), metadata.stat()
    return info.st_dev, info.st_ino, git_info.st_dev, git_info.st_ino


def _restore_codex_caches_once(
    snapshot: CodexCacheSnapshot, retained: set[Path] | None = None,
) -> tuple[set[str], set[str]]:
    """Restore or repair one observed generation of the cache tree."""
    parent = plugin_cache_parent("codex")
    restored: set[str] = set()
    repaired: set[str] = set()
    if any(not isinstance(version, str) or RELEASE_VERSION_RE.fullmatch(version) is None
           for version in snapshot.versions):
        raise OSError("cache snapshot contains an unsafe version path")
    for version in sorted(snapshot.versions, key=_version_key, reverse=True):
        source = snapshot.backup / version
        destination = parent / version
        _validate_codex_cache_boundary(destination, parent)
        parent.mkdir(parents=True, exist_ok=True)
        native_source = snapshot.native_sources.get(version)
        commit = native_source[0] if native_source is not None else None
        native_identity = None
        if (destination / ".git").exists() or (destination / ".git").is_symlink():
            native_identity = _codex_native_git_identity(destination, commit)
        if version == snapshot.client_owned_version:
            # Git archive permissions are historical recovery metadata. A native
            # checkout owns its umask and Git state; verify its shipped inventory
            # and executable bits without chmod, displacement, or cleanup.
            if native_source is None:
                raise OSError(f"client-owned newest cache has no immutable source binding: {destination}")
            if not destination.is_dir():
                raise OSError(f"client-owned newest cache is absent: {destination}")
            current_identity = destination.stat().st_dev, destination.stat().st_ino
            files = set(native_source[1])
            try:
                canonical_source = source.resolve()
                digest = canonical_tracked_tree_digest(canonical_source, files)
                verify_native_release_inventory(destination, canonical_source, digest, source_files=files)
            except ContractError as exc:
                raise OSError(f"client-owned newest cache failed release verification: {exc}") from exc
            _validate_codex_cache_boundary(destination, parent)
            if (destination.stat().st_dev, destination.stat().st_ino) != current_identity:
                raise OSError(f"client-owned newest cache changed identity during verification: {destination}")
            if native_identity is not None:
                if _codex_native_git_identity(destination, commit) != native_identity:
                    raise OSError(f"client-owned newest Git metadata changed identity: {destination}")
            elif (destination / ".git").exists() or (destination / ".git").is_symlink():
                raise OSError(f"Git metadata appeared during newest cache verification: {destination}")
            continue

        def validate_destination() -> None:
            _validate_codex_cache_boundary(destination, parent)
            if native_identity is not None:
                if _codex_native_git_identity(destination, commit) != native_identity:
                    raise OSError(f"native cache identity changed before repair: {destination}")
            elif (destination / ".git").exists() or (destination / ".git").is_symlink():
                raise OSError(f"repository appeared before cache repair: {destination}")

        if not destination.exists():
            _replace_cache_root(source, destination, parent, validate_destination=validate_destination)
            restored.add(version)
        elif not destination.is_dir():
            raise OSError(f"version root is not a directory: {destination}")
        elif _tree_digest(source) != _tree_digest(destination):
            displaced = _replace_cache_root(source, destination, parent,
                                            retain_displaced=native_identity is not None,
                                            validate_destination=validate_destination)
            if displaced is not None and retained is not None:
                retained.add(displaced)
            repaired.add(version)
        if _tree_digest(source) != _tree_digest(destination):
            raise OSError(f"version root changed during refresh: {destination}")
        for recovery in parent.glob(f".release-displaced-{version}-*"):
            if re.fullmatch(rf"\.release-displaced-{re.escape(version)}-[0-9a-f]{{32}}", recovery.name) is None:
                raise OSError(f"unrecognized retained recovery path: {recovery}")
            _codex_native_git_identity(recovery, commit)
            if retained is not None:
                retained.add(recovery)
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
    retained: set[Path] = set()
    try:
        _verify_native_recoveries(snapshot)
        # Initial recovery is mandatory I/O, not evidence of continuing native
        # mutation. Start the existing bounded settling window only once every
        # preserved root has first been restored and verified.
        initial_restored, initial_repaired = _restore_codex_caches_once(snapshot, retained)
        restored.update(initial_restored)
        repaired.update(initial_repaired)
        started = quiet_since = clock()
        while True:
            new_restored, new_repaired = _restore_codex_caches_once(snapshot, retained)
            now = clock()
            if new_restored or new_repaired:
                restored.update(new_restored)
                repaired.update(new_repaired)
                quiet_since = now
            if now - quiet_since >= CODEX_CACHE_QUIET_SECONDS:
                _verify_native_recoveries(snapshot)
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
    if retained:
        result.add("install.codex.cache-recovery", True,
                   "verified displaced Git checkouts retained without automatic deletion; "
                   "recovery disposition requires separate review: " + ", ".join(str(path) for path in sorted(retained)))
    if snapshot.native_recoveries:
        result.add("install.codex.cache-native-recovery", True,
                   "exact native metadata remains preserved outside the client cache; no automatic cleanup or reinsertion; "
                   "recovery disposition requires separate review: "
                   + ", ".join(str(record.manifest) for record in snapshot.native_recoveries.values()))
    return result.add(
        "install.codex.cache-restore",
        True,
        f"verified {len(snapshot.versions)} complete root(s) after a "
        f"{CODEX_CACHE_QUIET_SECONDS:g}s quiet window; restored {len(restored)}, "
        f"repaired {len(repaired)}",
    )


def content_digest_report(source_repo: Path, installed: Path) -> tuple[bool, str]:
    """Compare the complete shipped inventory against the installed tree.

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
    try:
        toplevel, _detail = _git_value(source_repo, ["rev-parse", "--show-toplevel"])
        files = None
        if toplevel and Path(toplevel).resolve() == source_repo.resolve():
            tracked = run(["git", "ls-files", "-z"], cwd=source_repo)
            if tracked.returncode:
                raise ContractError("source Git inventory is unavailable")
            files = set(filter(None, tracked.stdout.split("\0")))
            digest = canonical_tracked_tree_digest(source_repo, files)
        else:
            digest = canonical_tree_digest(source_repo)
        verify_native_release_inventory(installed, source_repo, digest, source_files=files)
    except (ContractError, OSError) as exc:
        return False, str(exc)
    return True, "complete native inventory and bytes match the source release digest %s" % digest


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
    result.verified_roots.pop(client, None)
    reported, load_path = client_reported_version(client)
    ok_reported = result.add(
        f"verify.{client}.reported",
        reported == expected,
        f"cli reports {reported or 'nothing'} (expected {expected})",
    )

    if client == "muse":
        manifest_name = ".muse-plugin"
    elif client == "claude":
        manifest_name = ".claude-plugin"
    else:
        manifest_name = ".codex-plugin"
    # A healthy conventional cache or staged bundle cannot vouch for another
    # tree the client actually reports loading, on any supported harness.
    candidates = [Path(load_path)] if load_path else [installed_root(client, expected)]
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
    verified = ok_reported and ok_disk and ok_content
    if verified:
        result.verified_roots[client] = content_root
    return verified


def _muse_bundle_completeness(root: Path, version: str) -> tuple[bool, str]:
    """Validate a staged Muse bundle before installing from it.

    Mirrors the repository's own .muse-plugin contract: the manifest must
    report the release version, every declared skill path must resolve to a
    file, and every hook script must exist and be executable. Byte equality
    with the source tree is deep_verify's job; this gate only refuses to
    install a structurally incomplete bundle.
    """
    if not root.is_dir() or root.is_symlink():
        return False, "bundle is absent, not a directory, or a symlink"
    try:
        if not (root / ".muse-plugin" / "plugin.json").resolve().is_relative_to(root.resolve()):
            return False, "bundle manifest escapes its root"
        manifest = json.loads(
            (root / ".muse-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return False, f"bundle manifest unreadable: {exc}"
    if not isinstance(manifest, dict):
        return False, "bundle manifest is not an object"
    if manifest.get("version") != version:
        return False, f"bundle manifest reports {manifest.get('version')!r} (expected {version})"
    if manifest.get("name") != PLUGIN_NAME:
        return False, f"bundle manifest names {manifest.get('name')!r} (expected {PLUGIN_NAME})"
    capabilities = manifest.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return False, "bundle manifest capabilities is not an object"
    skills = capabilities.get("skills") or []
    if not isinstance(skills, list) or not skills:
        return False, "bundle manifest declares no skills"

    def owned_file(value: object) -> bool:
        if not isinstance(value, str) or not value:
            return False
        relative = PurePosixPath(value)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        candidate = root / value
        try:
            return candidate.is_file() and candidate.resolve().is_relative_to(root.resolve())
        except (OSError, RuntimeError):
            return False

    for entry in skills:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not owned_file(path):
            return False, f"bundle skill missing: {path!r}"
    hooks = capabilities.get("hooks") or []
    if not isinstance(hooks, list):
        return False, "bundle manifest hooks is not an array"
    for hook in hooks:
        if not isinstance(hook, dict):
            return False, "bundle hook entry is not an object"
        command = hook.get("command") or []
        if not isinstance(command, list) or len(command) < 2 or not owned_file(command[1]):
            return False, f"bundle hook script missing: {hook.get('id')}"
        script = root / command[1]
        if not os.access(script, os.X_OK):
            return False, f"bundle hook script not executable: {hook.get('id')}"
    return True, f"bundle stages {len(skills)} skills for {version}"


def _validate_muse_bundle_path(path: Path, *, repo: Path | None = None) -> None:
    """Authorize only direct owned version roots, never an arbitrary CLI path.

    An environment override selects the bundle parent, not permission to erase
    a checkout. Existing trees also need a Muse ownership manifest. Its version
    need not match the directory name: Muse pins the original install path.
    """
    parent = MUSE_BUNDLE_ROOT
    protected = {Path.home().resolve(), Path.cwd().resolve(), SCRIPT_DIR.parents[2]}
    if repo is not None:
        protected.add(repo.resolve())
    try:
        resolved_parent, resolved_path = parent.resolve(), path.resolve()
    except (OSError, RuntimeError) as exc:
        raise OSError(f"cannot resolve Muse bundle ownership boundary: {path}") from exc
    if (
        not parent.is_absolute() or not path.is_absolute()
        or ".." in parent.parts or ".." in path.parts
        or path.parent != parent
        or not path.name.startswith("v")
        or RELEASE_VERSION_RE.fullmatch(path.name[1:]) is None
        or parent == Path(parent.anchor)
        or resolved_parent != parent or resolved_path != path
        or any(p == parent or p == path or p.is_relative_to(path) for p in protected)
    ):
        raise OSError(f"refusing unowned or unsafe Muse bundle path: {path}")
    for ancestor in (parent, *parent.parents):
        if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()):
            raise OSError(f"unsafe Muse bundle ancestor: {ancestor}")
        if (ancestor / ".git").exists() or (ancestor / ".git").is_symlink():
            raise OSError(f"Muse bundle parent is inside a repository: {ancestor}")
        if (ancestor / ".agents" / "repos.yaml").exists():
            raise OSError(f"Muse bundle parent is inside a workspace: {ancestor}")
    if not path.exists():
        # A killed rename can leave the previous tree at a recovery path.
        # Never silently create a fresh source over that unresolved transition.
        recoveries = sorted(parent.glob(f".release-displaced-{path.name}-*"))
        if recoveries:
            raise OSError(f"Muse bundle is absent; retained recovery tree(s): {recoveries}")
        return
    if not path.is_dir() or path.is_symlink():
        raise OSError(f"Muse bundle root is not a real directory: {path}")
    for child in path.rglob("*"):
        if child.name == ".git":
            raise OSError(f"refusing to replace a repository inside a Muse bundle: {child}")
        if child.is_symlink():
            try:
                contained = child.resolve().is_relative_to(path)
            except (OSError, RuntimeError) as exc:
                raise OSError(f"Muse bundle symlink cannot be resolved: {child}") from exc
            if not contained:
                raise OSError(f"Muse bundle symlink escapes its owned tree: {child}")
    try:
        manifest = json.loads((path / ".muse-plugin" / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OSError(f"existing Muse bundle has no readable ownership manifest: {path}") from exc
    if (not isinstance(manifest, dict) or manifest.get("name") != PLUGIN_NAME
            or not isinstance(manifest.get("version"), str)
            or RELEASE_VERSION_RE.fullmatch(manifest["version"]) is None):
        raise OSError(f"existing tree is not an owned Muse bundle: {path}")


@contextlib.contextmanager
def _muse_bundle_lock(path: Path, *, repo: Path | None = None) -> Iterator[None]:
    """Serialize bundle swaps and reject redirected lock/parent paths."""
    _validate_muse_bundle_path(path, repo=repo)
    MUSE_BUNDLE_ROOT.mkdir(parents=True, exist_ok=True)
    lock_path = MUSE_BUNDLE_ROOT / ".release.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    with os.fdopen(descriptor, "a+") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError(f"Muse bundle lock is not a regular file: {lock_path}")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _validate_muse_bundle_path(path, repo=repo)
        yield


def _materialize_muse_bundle(
    repo: Path, version: str, result: Result, dry_run: bool
) -> Path | None:
    """Export the release tree to the version-stamped Muse bundle directory.

    Export and verify in a fresh sibling before replacing an owned bundle.
    Keep displaced bytes for recovery; they may include retained local work.
    """
    destination = muse_bundle_dir(version)
    try:
        _validate_muse_bundle_path(destination, repo=repo)
        if dry_run:
            result.add("install.muse.bundle", True, f"dry-run: stage bundle at {destination}")
            return destination
        with _muse_bundle_lock(destination, repo=repo):
            if destination.exists():
                ok, detail = _muse_bundle_completeness(destination, version)
                content_ok, content_detail = content_digest_report(repo, destination)
                if ok and content_ok:
                    result.add("install.muse.bundle", True, f"reusing complete bundle at {destination}")
                    return destination
                result.add("install.muse.bundle-replace", True,
                           f"staging replacement ({detail}; {content_detail})")
            staging_prefix = f".release-export-{destination.name}-"
            staging = MUSE_BUNDLE_ROOT / f"{staging_prefix}{secrets.token_hex(16)}"
            try:
                _export_release_tag(repo, version, staging, current_version=version)
                ok, detail = _muse_bundle_completeness(staging, version)
                if not ok:
                    raise OSError(f"exported bundle incomplete: {detail}")
                content_ok, content_detail = content_digest_report(repo, staging)
                if not content_ok:
                    raise OSError(f"exported bundle differs from source: {content_detail}")
                recovery = _replace_cache_root(
                    staging, destination, MUSE_BUNDLE_ROOT, retain_displaced=True,
                    validate_destination=lambda: _validate_muse_bundle_path(destination, repo=repo),
                )
            finally:
                _remove_cache_transition_tree(staging, MUSE_BUNDLE_ROOT, staging_prefix)
            if recovery is not None:
                detail += f"; previous bytes retained at {recovery}"
            result.add("install.muse.bundle", True, detail)
            return destination
    except (OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        result.add("install.muse.bundle", False, str(exc))
        return None


def _sync_muse_recorded_source(
    recorded: Path, staged: Path, version: str, result: Result, dry_run: bool,
    *, repo: Path | None = None,
) -> bool:
    """Copy the versioned export over the bundle path Muse's record points at.

    The record pins its source path, so a new versioned directory alone is
    not installable — the staged tree must be synced into place before
    ``plugins update`` re-caches from it. The versioned export is left
    untouched as the retry source if the copy is interrupted.
    """
    try:
        _validate_muse_bundle_path(recorded, repo=repo)
        _validate_muse_bundle_path(staged, repo=repo)
        if dry_run:
            return result.add("install.muse.sync", True, f"dry-run: sync {staged} into {recorded}")
        with _muse_bundle_lock(recorded, repo=repo):
            _validate_muse_bundle_path(staged, repo=repo)
            ok, detail = _muse_bundle_completeness(staged, version)
            if not ok:
                raise OSError(f"staged tree incomplete: {detail}")
            if recorded == staged:
                return result.add("install.muse.sync", True, "recorded source already stages this version")
            if recorded.exists() and _tree_digest(recorded) == _tree_digest(staged):
                return result.add("install.muse.sync", True, "recorded source already matches staged bytes")
            recovery = _replace_cache_root(
                staged, recorded, MUSE_BUNDLE_ROOT, retain_displaced=True,
                validate_destination=lambda: _validate_muse_bundle_path(recorded, repo=repo),
            )
            if recovery is not None:
                detail += f"; previous bytes retained at {recovery}"
    except OSError as exc:
        return result.add("install.muse.sync", False, str(exc))
    return result.add("install.muse.sync", True, detail)


def refresh_client(
    client: str, result: Result, dry_run: bool, repo: Path | None = None
) -> bool:
    """Refresh one client's marketplace snapshot and installed plugin."""
    binary = resolve_client_binary(client)
    if not binary:
        return result.add(f"install.{client}", False, "client binary not found")
    if client == "muse":
        if repo is None:
            return result.add("install.muse", False, "no source repo supplied to stage the bundle from")
        version, detail = source_version(repo)
        if version is None:
            return result.add("install.muse", False, f"source manifests disagree: {detail}")
        bundle = _materialize_muse_bundle(repo, version, result, dry_run)
        if bundle is None:
            return False
        try:
            record = _muse_install_record(binary)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return result.add("install.muse.record", False, f"could not read install record: {exc}")
        source_path = ((record.get("source") or {}) if record else {}).get("path")
        if record is None or not source_path:
            commands = [[binary, "plugins", "install", str(bundle), "--json"]]
        else:
            recorded = Path(str(source_path))
            if not recorded.is_absolute():
                return result.add("install.muse.record", False, f"recorded source is not absolute: {source_path}")
            if not _sync_muse_recorded_source(recorded, bundle, version, result, dry_run, repo=repo):
                return False
            commands = [[binary, "plugins", "update", PLUGIN_NAME, "--json"]]
    elif client == "claude":
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
            # Keep the watcher serialized behind this transition while its new
            # standalone consumer is installed, before retiring legacy roots.
            if repo is not None and not install_codex_cache_guardian(repo, result, False, prepare_only=True):
                return False
            cache_snapshot = snapshot_codex_caches(result, repo=repo)
            if cache_snapshot is None:
                return False

        commands_ok = True
        for index, command in enumerate(commands):
            label = f"install.{client}.{command[2] if len(command) > 2 else 'run'}"
            if dry_run:
                result.add(label, True, "dry-run: " + " ".join(command[1:]))
                continue
            if cache_snapshot is not None:
                try:
                    _verify_native_recoveries(cache_snapshot, sources=True, allow_missing_sources=index > 0)
                except OSError as exc:
                    return result.add("install.codex.cache-native-preservation", False,
                                      f"native refresh refused; recovery inputs retained at {cache_snapshot.backup}: {exc}")
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
    repo: Path, result: Result, dry_run: bool, *, prepare_only: bool = False
) -> bool:
    """Install the durable supervisor that repairs later Codex cache generations."""
    source = repo / CACHE_GUARDIAN
    if not source.is_file() or source.is_symlink():
        return result.add(
            "install.codex.cache-guardian",
            False,
            f"guardian source is unavailable or unsafe: {source}",
        )
    command = [sys.executable, str(source), "--prepare" if prepare_only else "--install"]
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


def sync_commit_gate(result: Result, dry_run: bool, *, source: Path | None = None) -> bool:
    """Re-sync the commit gate from the live release pointer.

    The gate (pre-commit + coordination engine under ~/.synthesis/git-hooks/)
    approves every commit on the machine, but releases never reinstalled it:
    it ran 4.124.0 while claims were written by 4.133.0, and its doctor
    compared against the pinned install-time clone, so the skew was
    invisible. Every install now re-runs the gate installer from the stable
    pointer — which main() repoints at the verified release just before —
    so gate and claim writer always agree. The installer ends with its own
    doctor and fails closed; a bad gate blocks the release loudly instead
    of commits silently.
    """
    root = source or stable_path()
    installer = root / GIT_HOOKS_INSTALLER
    if not installer.is_file() or installer.is_symlink():
        return result.add(
            "install.commit-gate",
            False,
            f"gate installer is unavailable or unsafe: {installer}",
        )
    command = ["bash", str(installer)]
    if dry_run:
        return result.add(
            "install.commit-gate",
            True,
            "dry-run: " + " ".join(command),
        )
    completed = run(command, timeout=300)
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip().splitlines()
    detail = output[-1] if output else "gate installer produced no receipt"
    return result.add(
        "install.commit-gate", completed.returncode == 0, detail
    )


def activate_published_cli(
    repo: Path, version: str, result: Result, dry_run: bool
) -> bool:
    """Materialize and activate the release through the public verifier."""
    home = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home())))
    cache_base = Path(os.environ.get("XDG_CACHE_HOME", str(home / ".cache")))
    state_base = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local" / "state")))
    releases = cache_base / "synthesis" / "releases"
    state = state_base / "synthesis"
    launcher = Path(os.environ.get("SYNTHESIS_INSTALL_BIN_DIR", str(home / ".local" / "bin"))) / "synthesis"
    active = state / "active-release.json"
    descriptor_path = state / "releases" / (version + ".json")
    if dry_run:
        return result.add(
            "install.synthesis-cli", True,
            "dry-run: verify v%s and activate a content-addressed generation" % version,
        )
    try:
        head = run(["git", "rev-parse", "HEAD^{commit}"], cwd=repo).stdout.strip()
        tag = run(["git", "rev-parse", "--verify", "refs/tags/v%s^{commit}" % version], cwd=repo)
        if tag.returncode:
            raise ContractError("published release tag v%s is unavailable locally" % version)
        if tag.stdout.strip() != head:
            raise ContractError("local release tag does not point at published HEAD")
        generation, descriptor = materialize_release(
            repo,
            releases,
            channel="pin",
            ref="v%s" % version,
            source_url="https://github.com/synthesisengineering/synthesis-skills.git",
        )
        activate_cli(generation, descriptor, launcher, active)
        atomic_write_json(descriptor_path, descriptor)
    except (ContractError, OSError) as exc:
        return result.add("install.synthesis-cli", False, str(exc))
    return result.add(
        "install.synthesis-cli",
        True,
        "activated %s at %s" % (version, generation),
    )


_UNREAD_SELECTION = object()


def lifecycle_release_clients(version: str, result: Result, *, desired=_UNREAD_SELECTION) -> tuple[str, ...] | None:
    """A publisher cannot broaden an explicit local installation selection."""
    try:
        if desired is _UNREAD_SELECTION:
            desired = SystemState().read_desired()
        if desired is None:
            detail = "no lifecycle profile is configured; release will not infer one"
            clients = ("claude", "codex", "muse")
        else:
            if not desired.get("enabled", True):
                raise ContractError("the desired installation is disabled; preserved")
            if desired["profile"] == "modular":
                raise ContractError("the desired installation is modular; release cannot activate full native plugins")
            pin = desired["release"].get("version_pin")
            if pin and pin != version:
                raise ContractError("release %s conflicts with the selected exact pin %s; preserved" % (version, pin))
            detail = "%s profile and its saved policy will be preserved" % desired["profile"]
            clients = tuple(desired["clients"])
    except (ContractError, OSError, ValueError) as exc:
        result.add("preflight.lifecycle-selection", False, str(exc))
        return None
    result.add("preflight.lifecycle-selection", True, detail + "; native targets: " + ", ".join(clients))
    return clients


def lifecycle_release_selection(version: str, result: Result) -> bool:
    return lifecycle_release_clients(version, result) is not None


def reconcile_published_lifecycle(
    repo: Path, version: str, result: Result, dry_run: bool, *, expected_desired_digest: str | None = None,
) -> bool:
    """Finish a configured installation with a real, exact-release transaction.

    CLI activation and native plugin updates do not advance lifecycle state.
    Repair replays the saved organization commit and profile, verifies owned
    output provenance, and records a new generation without accepting stale
    SessionStart evidence or altering previous installation history.
    """
    state = SystemState()
    try:
        desired = state.read_desired()
        if expected_desired_digest is not None and json_digest(desired) != expected_desired_digest:
            raise ContractError("saved desired selection changed after publisher admission; reconciliation refused")
        if desired is None:
            return result.add("install.lifecycle", True,
                "not configured; no desired profile or accepted generation was invented")
        if not lifecycle_release_selection(version, result):
            return False
        if dry_run:
            return result.add("install.lifecycle", True,
                "dry-run: repair the saved selection, bind release %s, and verify its committed generation" % version)
        before = state.read_observation()
        pointer = state.state_dir / "active-release.json"
        if pointer.is_symlink() or not pointer.is_file():
            raise ContractError("activated release descriptor is unavailable or unsafe")
        active = json.loads(pointer.read_text(encoding="utf-8"))
        descriptor = validate_release_descriptor(descriptor_fields(active))
        head, detail = _git_value(repo, ["rev-parse", "HEAD^{commit}"])
        if head is None or descriptor["version"] != version or descriptor["commit"] != head:
            raise ContractError("activated release does not match the published source: %s" % detail)
        verify_materialized_release(Path(active["release_root"]), descriptor)
        command = [str(state.launcher_path), "repair", "--expected-release-digest",
                   descriptor["content_digest"], "--expected-desired-digest",
                   expected_desired_digest or json_digest(desired), "--json"]
        completed = run(command, timeout=900)
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            raise ContractError("lifecycle repair failed: %s" % (detail[-1] if detail else "exit %s" % completed.returncode))
        receipt = json.loads(_first_json(completed.stdout))
        after = state.read_observation()
        if state.read_desired() != desired:
            raise ContractError("desired selection changed during lifecycle repair; preserved for inspection")
        if after["transactions"][:len(before["transactions"])] != before["transactions"]:
            raise ContractError("prior lifecycle transaction history changed during repair; preserved for inspection")
        latest = after["transactions"][-1] if after["transactions"] else {}
        if (not isinstance(receipt, dict) or latest.get("transaction_id") != receipt.get("transaction_id")
                or latest.get("state") != "committed" or latest.get("command") != "repair"
                or after["generation"] != latest.get("generation")
                or after["generation"] <= before["generation"]
                or latest.get("committed_desired_digest") != json_digest(desired)):
            raise ContractError("repair did not produce a new committed generation for the saved selection")
        recorded = latest.get("release") or {}
        if any(recorded.get(key) != descriptor[key] for key in ("version", "commit", "tree", "content_digest")):
            raise ContractError("committed lifecycle generation belongs to another release")
        source = latest.get("source-provenance") or {}
        installed = latest.get("installed") or {}
        if (source.get("status") != "verified" or source.get("content_digest") != descriptor["content_digest"]
                or installed.get("status") != "verified"
                or not isinstance((latest.get("details") or {}).get("engine", {}).get("post_repair_doctor"), dict)):
            raise ContractError("committed generation lacks verified source or post-repair doctor evidence")
        natives = installed.get("native_plugins") or {}
        if any(not isinstance(natives.get(client), dict)
               or natives[client].get("content_digest") != descriptor["content_digest"]
               for client in desired["clients"]):
            raise ContractError("committed generation lacks exact native plugin content evidence")
    except (ContractError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        return result.add("install.lifecycle", False, str(exc))
    return result.add("install.lifecycle", True,
        "generation %s committed for %s with desired state and prior history preserved; native live-loading requires its own receipt"
        % (latest["generation"], version))


def fetch_published_tag(repo: Path, version: str, result: Result, dry_run: bool) -> bool:
    """Fetch and verify the remote-published immutable tag without authoring it."""
    if dry_run:
        return result.add(
            "publish.fetch-tag", True, "dry-run: fetch and verify v%s" % version
        )
    fetched = run(["git", "fetch", "--all", "--tags"], cwd=repo, timeout=600)
    if fetched.returncode:
        detail = (fetched.stderr or fetched.stdout).strip().splitlines()
        return result.add(
            "publish.fetch-tag", False, detail[-1] if detail else "tag fetch failed"
        )
    head = run(["git", "rev-parse", "HEAD^{commit}"], cwd=repo)
    tag = run(
        ["git", "rev-parse", "--verify", "refs/tags/v%s^{commit}" % version],
        cwd=repo,
    )
    matches = not head.returncode and not tag.returncode and tag.stdout.strip() == head.stdout.strip()
    return result.add(
        "publish.fetch-tag",
        matches,
        "v%s matches published HEAD" % version
        if matches
        else "fetched v%s does not match published HEAD" % version,
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
    status = run(["git", "status", "--porcelain"], cwd=repo)
    dirty = [ln for ln in status.stdout.splitlines() if ln.strip()]
    result.add(
        "preflight.tree-clean",
        status.returncode == 0 and not dirty,
        (
            f"{len(dirty)} uncommitted path(s)"
            if dirty
            else "clean"
            if status.returncode == 0
            else "git status failed"
        ),
    )
    if install_only:
        head = run(["git", "rev-parse", "HEAD^{commit}"], cwd=repo)
        tag = run(
            ["git", "rev-parse", "--verify", "refs/tags/v%s^{commit}" % version],
            cwd=repo,
        )
        matches = (
            head.returncode == 0
            and tag.returncode == 0
            and head.stdout.strip() == tag.stdout.strip()
        )
        result.add(
            "preflight.release-tag",
            matches,
            "v%s matches HEAD" % version
            if matches
            else "v%s is missing or does not match HEAD" % version,
        )
    if not install_only:
        top = changelog_top_version(repo)
        result.add(
            "preflight.changelog-matches",
            top == version,
            f"CHANGELOG newest={top}, manifests={version}",
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

    clients = ("claude", "codex", "muse")
    state = SystemState()
    expected_selection = None
    if not args.check_only and not args.acceptance_only:
        try:
            desired = state.read_desired()
        except (ContractError, OSError, ValueError) as exc:
            result.add("preflight.lifecycle-selection", False, str(exc))
            return 1
        expected_selection = json_digest(desired)
        clients = lifecycle_release_clients(version, result, desired=desired)
        if clients is None:
            print("\nRELEASE ABORTED: local lifecycle selection was preserved. Nothing published or installed.")
            return 1

    def selection_check() -> bool:
        if json_digest(state.read_desired()) != expected_selection:
            return result.add("install.lifecycle-selection", False,
                              "saved desired selection changed after publisher admission; further effects refused")
        return True

    def selected_effect(operation) -> bool:
        # The native effect and its selection check share the lifecycle lock.
        # Bootstrap activation and the child lifecycle transaction acquire
        # their own resources; each handoff is checked independently below.
        try:
            with contextlib.nullcontext() if args.dry_run else state.locked():
                return selection_check() and operation()
        except (ContractError, OSError, ValueError) as exc:
            return result.add("install.lifecycle-selection", False, str(exc))

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
        if not fetch_published_tag(repo, version, result, args.dry_run):
            print("\nRELEASE ABORTED: published tag could not be verified locally. Clients left untouched.")
            return 1

    # New plugin hooks call exec-public, so establish their verified execution
    # prerequisite before any client can load the new hook definitions.
    if (not selected_effect(lambda: True)
            or not activate_published_cli(repo, version, result, args.dry_run)):
        print(
            f"\nRELEASE INCOMPLETE for {version}: the public synthesis CLI "
            "could not be activated through the release verifier. Clients left untouched."
        )
        return 1

    for client in clients:
        if not selected_effect(lambda: refresh_client(client, result, args.dry_run, repo=repo)):
            print(f"\nRELEASE INCOMPLETE for {version}: native refresh refused or failed.")
            return 1

    if "codex" in clients:
        if not selected_effect(lambda: install_codex_cache_guardian(repo, result, args.dry_run)):
            print(f"\nRELEASE INCOMPLETE for {version}: native guardian installation refused or failed.")
            return 1

    if args.dry_run:
        print(f"\nDRY RUN complete for {version}. No state changed.")
        return 0

    verified = all(deep_verify(client, version, result, repo=repo)
                   for client in clients)
    if not verified or result.failed:
        print(
            f"\nRELEASE INCOMPLETE for {version}: "
            f"{len(result.failed)} step(s) failed. The clients are NOT confirmed current — "
            "re-run with --install-only after fixing."
        )
        return 1
    if not selected_effect(lambda: refresh_stable_path(version, result, args.dry_run,
            target=result.verified_roots.get(clients[0]), repo=repo)):
        print(
            f"\nRELEASE INCOMPLETE for {version}: the stable path could not be "
            "repointed at the verified install — re-run with --install-only."
        )
        return 1
    if not selected_effect(lambda: sync_commit_gate(result, args.dry_run)):
        print(
            f"\nRELEASE INCOMPLETE for {version}: the commit gate could not be "
            "re-synced from the verified install — re-run with --install-only."
        )
        return 1
    if not reconcile_published_lifecycle(repo, version, result, args.dry_run,
            expected_desired_digest=expected_selection):
        print(
            f"\nRELEASE INCOMPLETE for {version}: client installation succeeded, "
            "but its selected lifecycle generation could not be reconciled. "
            "Saved state and failed transaction evidence were retained."
        )
        return 1
    print(f"\nRELEASED {version}: published, installed, and verified on {', '.join(clients)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
