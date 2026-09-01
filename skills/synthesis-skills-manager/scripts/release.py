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
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
ACCEPTANCE_CONSUMER_ID = (
    "synthesis-skills-manager.release.consume-acceptance.v1"
)
RELEASE_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

# The required checks, mirroring the repository's own verification contract.
# Kept as data so a reader can see exactly what a release runs.
REQUIRED_CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("conformance.source", ["python3", "skills/synthesis-agent-conformance/scripts/conformance.py", "source"]),
    ("conformance.instructions", ["python3", "skills/synthesis-agent-conformance/scripts/conformance.py", "instructions", "--repo-root", "."]),
    ("pytest.conformance", ["python3", "-m", "pytest", "skills/synthesis-agent-conformance/scripts/", "-q"]),
    ("pytest.coordination", ["python3", "-m", "pytest", "skills/synthesis-project-management/scripts/test_coordination.py", "-q"]),
    ("pytest.promotion-gate", ["python3", "-m", "pytest", "skills/synthesis-promotion-gate/scripts/", "-q"]),
    ("pytest.context-lifecycle-integrity", ["python3", "-m", "pytest", "skills/synthesis-context-lifecycle/scripts/", "skills/synthesis-implementation-integrity/scripts/", "-q"]),
    ("pytest.release", ["python3", "-m", "pytest", "skills/synthesis-skills-manager/scripts/test_release.py", "-q"]),
    ("meeting-transcripts.completeness", ["python3", "skills/synthesis-meeting-transcripts/test_verify_transcripts.py"]),
    ("meeting-transcripts.primary", ["python3", "skills/synthesis-meeting-transcripts/test_transcript_primary.py"]),
    ("pytest.rituals-guard-hooks", ["python3", "-m", "pytest", "skills/synthesis-daily-rituals/scripts/", "skills/synthesis-message-guard/scripts/", "skills/synthesis-git-hooks/scripts/", "-q"]),
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


def refresh_client(client: str, result: Result, dry_run: bool) -> bool:
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
    for command in commands:
        label = f"install.{client}.{command[2] if len(command) > 2 else 'run'}"
        if dry_run:
            result.add(label, True, "dry-run: " + " ".join(command[1:]))
            continue
        completed = run(command, timeout=600)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip().splitlines()
            return result.add(label, False, tail[-1] if tail else "command failed")
        result.add(label, True, " ".join(command[1:]))
    return True


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
        refresh_client(client, result, args.dry_run)

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
    print(f"\nRELEASED {version}: published, installed, and verified on both clients.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
