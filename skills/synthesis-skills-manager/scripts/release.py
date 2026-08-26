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
  --dry-run       print the plan and run read-only steps; mutate nothing

Exit codes: 0 released/verified, 1 a step failed, 2 preconditions unverifiable.
"""

from __future__ import annotations

import argparse
import json
import os
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

# The required checks, mirroring the repository's own verification contract.
# Kept as data so a reader can see exactly what a release runs.
REQUIRED_CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("conformance.source", ["python3", "skills/synthesis-agent-conformance/scripts/conformance.py", "source"]),
    ("conformance.instructions", ["python3", "skills/synthesis-agent-conformance/scripts/conformance.py", "instructions", "--repo-root", "."]),
    ("pytest.conformance", ["python3", "-m", "pytest", "skills/synthesis-agent-conformance/scripts/", "-q"]),
    ("pytest.coordination", ["python3", "-m", "pytest", "skills/synthesis-project-management/scripts/test_coordination.py", "-q"]),
    ("pytest.promotion-gate", ["python3", "-m", "pytest", "skills/synthesis-promotion-gate/scripts/", "-q"]),
    ("pytest.context-lifecycle-integrity", ["python3", "-m", "pytest", "skills/synthesis-context-lifecycle/scripts/", "skills/synthesis-implementation-integrity/scripts/", "-q"]),
    ("acceptance.r5", ["python3", "skills/synthesis-implementation-integrity/scripts/acceptance_suite.py", "run", "--manifest", "skills/synthesis-implementation-integrity/acceptance-suite.yaml", "--repo-root", "."]),
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


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout
    )


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


def deep_verify(client: str, expected: str, result: Result) -> bool:
    """Verify a client twice: its own report, and the manifest it loads.

    The second half exists because the first half can lie. A stale marketplace
    snapshot, a hand-made cache directory, or a partial install can all leave a
    client reporting a version whose files are not the ones on disk.
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
    return ok_reported and ok_disk


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


def publish(repo: Path, result: Result, dry_run: bool) -> bool:
    """Push main to every configured push remote."""
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo).stdout.strip()
    if not result.add("publish.on-main", branch == "main", f"branch={branch or 'unknown'}"):
        return False
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
        if dry_run:
            result.add(f"publish.push.{remote}", True, "dry-run")
            continue
        completed = run(["git", "push", remote, "main"], cwd=repo, timeout=600)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip().splitlines()
            return result.add(f"publish.push.{remote}", False, tail[-1] if tail else "push failed")
        result.add(f"publish.push.{remote}", True, "pushed")
    return True


def run_required_checks(repo: Path, result: Result, dry_run: bool) -> bool:
    ok = True
    for name, command in REQUIRED_CHECKS:
        if dry_run:
            result.add(f"checks.{name}", True, "dry-run")
            continue
        completed = run(command, cwd=repo)
        passed = completed.returncode == 0
        tail = (completed.stdout or completed.stderr).strip().splitlines()
        ok = result.add(f"checks.{name}", passed, "" if passed else (tail[-1] if tail else "failed")) and ok
        if not passed:
            break
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".", help="synthesis-skills checkout (default: cwd)")
    parser.add_argument("--install-only", action="store_true", help="refresh + verify clients only")
    parser.add_argument("--check-only", action="store_true", help="preflight + required checks only")
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

    if not args.install_only:
        if not run_required_checks(repo, result, args.dry_run):
            print("\nRELEASE ABORTED: required checks failed. Nothing was published.")
            return 1
        if args.check_only:
            print(f"\nCHECKS PASSED for {version}. Nothing published (--check-only).")
            return 0
        if not publish(repo, result, args.dry_run):
            print("\nRELEASE ABORTED: publish failed. Clients left untouched.")
            return 1

    for client in ("claude", "codex"):
        refresh_client(client, result, args.dry_run)

    if args.dry_run:
        print(f"\nDRY RUN complete for {version}. No state changed.")
        return 0

    verified = all(deep_verify(client, version, result) for client in ("claude", "codex"))
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
