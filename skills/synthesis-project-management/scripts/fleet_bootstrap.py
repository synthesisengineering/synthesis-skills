#!/usr/bin/env python3
"""Idempotent bootstrap for a new fleet Mac.

Provisioning order (architecture §9, clean-install path only — never copy a
Mac): mint identity, clone subscribed repos, install the hooks runtime plus
the skill set, enroll the machine, verify the doctor. Every step writes a
receipt under ``<home>/.synthesis/fleet/receipts/``; a safe rerun re-verifies
current state and reports ``noop`` instead of redoing work.

Usage::

    python3 fleet_bootstrap.py --home /Users/example --source-root ~/workspaces/example/synthesis-skills \\
        --label my-mac --role secondary --repos-manifest fleet-repos.json \\
        --fleet-registry ~/workspaces/personal/fleet/machines.json

``--repos-manifest`` is JSON: ``{"schema_version": 1, "repos":
[{"remote": "<url>", "path": "~/workspaces/<name>", "branch": "main"}]}``.
``branch`` is optional. Paths may be ``~``-rooted (expanded against
``--home``, never the invoking process's home) or absolute.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import fleet_doctor as _doctor
import fleet_identity as _identity

REPOS_SCHEMA_VERSION = 1
RECEIPTS_DIRNAME = "receipts"

STEP_IDENTITY = "mint-identity"
STEP_REPOS = "clone-repos"
STEP_INSTALL = "install-runtime"
STEP_ENROLL = "enroll-machine"
STEP_DOCTOR = "verify-doctor"

STATUS_DONE = "done"
STATUS_NOOP = "noop"
STATUS_FAIL = "fail"

GIT_TIMEOUT_SECONDS = 120


class FleetBootstrapError(ValueError):
    """A bootstrap step that cannot proceed."""


@dataclass
class StepResult:
    step: str
    status: str
    detail: str
    receipt: str = ""


def _run_git(args: list[str], cwd: Path | None = None):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )


def _default_install_runner(script: Path, home: Path):
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=env,
    )


def fleet_dir_for(home: Path) -> Path:
    return Path(home).expanduser() / ".synthesis" / "fleet"


def receipts_dir_for(home: Path) -> Path:
    return fleet_dir_for(home) / RECEIPTS_DIRNAME


def expand_for_home(value: str, home: Path) -> Path:
    """Expand ``~``/``$HOME`` against the bootstrapped home, not ours."""
    text = value.strip()
    if text == "~":
        return Path(home)
    if text.startswith("~/"):
        return Path(home) / text[2:]
    if text.startswith("$HOME/"):
        return Path(home) / text[len("$HOME/"):]
    if text.startswith("${HOME}/"):
        return Path(home) / text[len("${HOME}/"):]
    return Path(os.path.expandvars(text)).expanduser()


def parse_repos_manifest(path: Path | None, home: Path) -> list[dict]:
    """Validate the repos manifest; [] when no manifest is configured."""
    if path is None:
        return []
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FleetBootstrapError(f"repos manifest not found: {path}")
    except (OSError, ValueError) as exc:
        raise FleetBootstrapError(f"repos manifest unreadable: {path}: {exc}")
    if not isinstance(document, dict):
        raise FleetBootstrapError("repos manifest must be a JSON object")
    if document.get("schema_version") != REPOS_SCHEMA_VERSION:
        raise FleetBootstrapError(
            f"repos manifest schema_version must be {REPOS_SCHEMA_VERSION}"
        )
    repos = document.get("repos")
    if not isinstance(repos, list):
        raise FleetBootstrapError("repos manifest repos must be a list")
    parsed = []
    for position, entry in enumerate(repos):
        if not isinstance(entry, dict):
            raise FleetBootstrapError(f"repos[{position}] must be an object")
        remote = entry.get("remote")
        target = entry.get("path")
        branch = entry.get("branch", "")
        if not isinstance(remote, str) or not remote.strip():
            raise FleetBootstrapError(f"repos[{position}] needs a remote URL")
        if not isinstance(target, str) or not target.strip():
            raise FleetBootstrapError(f"repos[{position}] needs a path")
        if branch is not None and not isinstance(branch, str):
            raise FleetBootstrapError(f"repos[{position}] branch must be a string")
        parsed.append(
            {
                "remote": remote.strip(),
                "path": str(expand_for_home(target, home)),
                "branch": (branch or "").strip(),
            }
        )
    return parsed


def write_receipt(home: Path, result: StepResult, machine_id: str) -> Path:
    directory = receipts_dir_for(home)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"bootstrap-{result.step}.json"
    payload = {
        **asdict(result),
        "receipt": str(path),
        "machine_id": machine_id,
        "at": _identity.utcnow_iso(),
    }
    staging = path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(staging, path)
    result.receipt = str(path)
    return path


def step_identity(home: Path) -> StepResult:
    """Mint this Mac's stable machine-id exactly once."""
    directory = fleet_dir_for(home)
    try:
        existing = _identity.read_machine_id(directory)
    except _identity.FleetIdentityError as exc:
        return StepResult(STEP_IDENTITY, STATUS_FAIL, str(exc))
    if existing is not None:
        return StepResult(
            STEP_IDENTITY, STATUS_NOOP, f"machine-id already minted: {existing}"
        )
    try:
        minted = _identity.mint_machine_id(directory)
    except _identity.FleetIdentityError as exc:
        return StepResult(STEP_IDENTITY, STATUS_FAIL, str(exc))
    return StepResult(
        STEP_IDENTITY, STATUS_DONE, f"minted machine-id: {minted}"
    )


def step_repos(home: Path, repos: list[dict], *, git_runner=None) -> StepResult:
    """Clone subscribed repos; existing checkouts verify, never clobber."""
    runner = git_runner or _run_git
    if not repos:
        return StepResult(
            STEP_REPOS, STATUS_NOOP, "no repos manifest; nothing to clone"
        )
    cloned: list[str] = []
    verified: list[str] = []
    for entry in repos:
        target = Path(entry["path"])
        if target.exists() and not target.is_dir():
            return StepResult(
                STEP_REPOS,
                STATUS_FAIL,
                f"{target}: exists and is not a directory; refusing to clobber",
            )
        if target.is_dir() and (target / ".git").exists():
            try:
                origin = runner(["config", "--get", "remote.origin.url"], target)
            except (OSError, subprocess.SubprocessError) as exc:
                return StepResult(
                    STEP_REPOS, STATUS_FAIL, f"{target}: git failed: {exc}"
                )
            if origin.returncode != 0:
                return StepResult(
                    STEP_REPOS,
                    STATUS_FAIL,
                    f"{target}: existing checkout has no origin remote",
                )
            if origin.stdout.strip().rstrip("/") != entry["remote"].rstrip("/"):
                return StepResult(
                    STEP_REPOS,
                    STATUS_FAIL,
                    f"{target}: origin {origin.stdout.strip()} does not match "
                    f"subscribed {entry['remote']}; refusing to clobber",
                )
            verified.append(str(target))
            continue
        if target.exists():
            return StepResult(
                STEP_REPOS,
                STATUS_FAIL,
                f"{target}: exists but is not a git checkout; refusing to clobber",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        clone_args = ["clone", "--quiet", entry["remote"], str(target)]
        if entry["branch"]:
            clone_args = [
                "clone", "--quiet", "--branch", entry["branch"],
                entry["remote"], str(target),
            ]
        try:
            completed = runner(clone_args, None)
        except (OSError, subprocess.SubprocessError) as exc:
            return StepResult(
                STEP_REPOS, STATUS_FAIL, f"{target}: clone failed: {exc}"
            )
        if completed.returncode != 0:
            return StepResult(
                STEP_REPOS,
                STATUS_FAIL,
                f"{target}: clone failed: {completed.stderr.strip()}",
            )
        cloned.append(str(target))
    detail = (
        f"cloned {len(cloned)}: {', '.join(cloned)}"
        if cloned
        else f"verified {len(verified)} existing checkout(s)"
    )
    if verified and cloned:
        detail += f"; verified {len(verified)} existing"
    status = STATUS_DONE if cloned else STATUS_NOOP
    return StepResult(STEP_REPOS, status, detail)


def step_install(
    home: Path, source_root: Path, *, install_runner=None
) -> StepResult:
    """Verify the skill source, then install the hooks runtime once."""
    runner = install_runner or _default_install_runner
    root = Path(source_root).expanduser()
    components = (
        root / "skills/synthesis-onboarding/references/components.json"
    )
    machine_sync = root / "skills/synthesis-machine-sync/SKILL.md"
    installer = root / "skills/synthesis-git-hooks/scripts/install.sh"
    for required in (components, machine_sync, installer):
        if not required.is_file():
            return StepResult(
                STEP_INSTALL,
                STATUS_FAIL,
                f"skill source is missing {required.relative_to(root) if root in required.parents else required}",
            )
    try:
        skills = json.loads(components.read_text(encoding="utf-8"))["skills"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return StepResult(
            STEP_INSTALL, STATUS_FAIL, f"components catalog unreadable: {exc}"
        )
    if "synthesis-machine-sync" not in skills:
        return StepResult(
            STEP_INSTALL,
            STATUS_FAIL,
            "components catalog does not list synthesis-machine-sync",
        )
    hooks_dir = Path(home) / ".synthesis" / "git-hooks"
    source_pointer = hooks_dir / "source-path"
    expected_pointer = str(root / "skills/synthesis-git-hooks/scripts") + "\n"
    if (
        source_pointer.is_file()
        and (hooks_dir / "coordination.py").is_file()
        and source_pointer.read_text(encoding="utf-8") == expected_pointer
    ):
        return StepResult(
            STEP_INSTALL,
            STATUS_NOOP,
            f"hooks runtime already installed from {root}",
        )
    try:
        completed = runner(installer, Path(home))
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(STEP_INSTALL, STATUS_FAIL, f"installer failed: {exc}")
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return StepResult(
            STEP_INSTALL,
            STATUS_FAIL,
            "installer exited %s: %s"
            % (completed.returncode, tail[-1] if tail else "no output"),
        )
    return StepResult(
        STEP_INSTALL, STATUS_DONE, f"installed hooks runtime from {root}"
    )


def step_enroll(
    home: Path,
    *,
    label: str,
    role: str,
    fleet_registry: Path | None = None,
) -> StepResult:
    """Enroll this Mac's minted identity in the fleet registry.

    A primary founds the registry; a secondary installs the synced copy
    (``--fleet-registry``, from the just-cloned personal KB) before
    enrolling. A secondary with no synced copy fails closed instead of
    founding a second, conflicting fleet.
    """
    directory = fleet_dir_for(home)
    try:
        machine_id = _identity.read_machine_id(directory)
    except _identity.FleetIdentityError as exc:
        return StepResult(STEP_ENROLL, STATUS_FAIL, str(exc))
    if machine_id is None:
        return StepResult(
            STEP_ENROLL, STATUS_FAIL, "no machine-id minted; identity step first"
        )
    registry_path = _identity.registry_path(directory)
    if not registry_path.is_file() and fleet_registry is not None:
        try:
            document = json.loads(
                Path(fleet_registry).read_text(encoding="utf-8")
            )
            _identity.write_registry(document, directory)
        except (OSError, ValueError) as exc:
            return StepResult(
                STEP_ENROLL,
                STATUS_FAIL,
                f"synced fleet registry unusable: {exc}",
            )
    if not registry_path.is_file() and role != "primary":
        return StepResult(
            STEP_ENROLL,
            STATUS_FAIL,
            "secondary enrollment needs the synced fleet registry "
            "(--fleet-registry from the personal KB); refusing to found a "
            "second fleet",
        )
    try:
        registry = _identity.read_registry(directory)
    except _identity.FleetIdentityError as exc:
        return StepResult(STEP_ENROLL, STATUS_FAIL, str(exc))
    entry = registry["machines"].get(machine_id)
    if (
        isinstance(entry, dict)
        and entry.get("retired_at") is None
        and entry.get("label") == label.strip()
        and entry.get("role") == role
    ):
        return StepResult(
            STEP_ENROLL,
            STATUS_NOOP,
            f"machine {label} ({machine_id}) already enrolled as {role}",
        )
    try:
        _identity.enroll_self(
            label=label, role=role, directory=directory
        )
    except _identity.FleetIdentityError as exc:
        return StepResult(STEP_ENROLL, STATUS_FAIL, str(exc))
    return StepResult(
        STEP_ENROLL,
        STATUS_DONE,
        f"enrolled machine {label} ({machine_id}) as {role}",
    )


def step_doctor(home: Path, machine_id: str, *, doctor_runner=None) -> StepResult:
    """Verify the new Mac with the fleet doctor; fail on any finding."""
    board = Path(home) / ".synthesis" / "coordination" / "active-sessions.md"
    artifacts = fleet_dir_for(home) / "handoffs"
    try:
        if doctor_runner is not None:
            checks = doctor_runner(board=board)
        else:
            checks = _doctor.run_all(
                board=board, artifacts_dir=artifacts, machine_id=machine_id
            )
    except (OSError, ValueError, RuntimeError) as exc:
        return StepResult(STEP_DOCTOR, STATUS_FAIL, f"doctor failed: {exc}")
    failures = [check for check in checks if not check.ok]
    if failures:
        return StepResult(
            STEP_DOCTOR,
            STATUS_FAIL,
            "doctor findings: "
            + "; ".join(f"{check.id}: {check.detail}" for check in failures),
        )
    if (receipts_dir_for(home) / f"bootstrap-{STEP_DOCTOR}.json").is_file():
        return StepResult(
            STEP_DOCTOR,
            STATUS_NOOP,
            "doctor still passes: " + ", ".join(check.id for check in checks),
        )
    return StepResult(
        STEP_DOCTOR,
        STATUS_DONE,
        "doctor passes: " + ", ".join(check.id for check in checks),
    )


def bootstrap(
    *,
    home: Path,
    source_root: Path,
    label: str,
    role: str,
    repos: list[dict] | None = None,
    fleet_registry: Path | None = None,
    git_runner=None,
    install_runner=None,
    doctor_runner=None,
) -> dict:
    """Run every bootstrap step in order; stop at the first failure."""
    home = Path(home).expanduser()
    results: list[StepResult] = []
    machine_id = ""
    try:
        machine_id = _identity.read_machine_id(fleet_dir_for(home)) or ""
    except _identity.FleetIdentityError:
        machine_id = ""

    results.append(step_identity(home))
    if results[-1].status == STATUS_FAIL:
        return _finish(home, machine_id, results)
    try:
        machine_id = _identity.read_machine_id(fleet_dir_for(home)) or machine_id
    except _identity.FleetIdentityError:
        pass

    results.append(step_repos(home, repos or [], git_runner=git_runner))
    if results[-1].status == STATUS_FAIL:
        return _finish(home, machine_id, results)

    results.append(
        step_install(home, Path(source_root), install_runner=install_runner)
    )
    if results[-1].status == STATUS_FAIL:
        return _finish(home, machine_id, results)

    results.append(
        step_enroll(home, label=label, role=role, fleet_registry=fleet_registry)
    )
    if results[-1].status == STATUS_FAIL:
        return _finish(home, machine_id, results)

    results.append(
        step_doctor(home, machine_id, doctor_runner=doctor_runner)
    )
    return _finish(home, machine_id, results)


def _finish(home: Path, machine_id: str, results: list[StepResult]) -> dict:
    for result in results:
        try:
            write_receipt(home, result, machine_id)
        except OSError as exc:
            results.append(
                StepResult("write-receipt", STATUS_FAIL, f"receipt failed: {exc}")
            )
            break
    report = {
        "machine_id": machine_id,
        "steps": [asdict(result) for result in results],
        "ok": all(result.status != STATUS_FAIL for result in results),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--role", choices=("primary", "secondary"),
                        required=True)
    parser.add_argument("--repos-manifest", type=Path, default=None)
    parser.add_argument(
        "--fleet-registry",
        type=Path,
        default=None,
        help="Synced machines.json from the personal KB (required for secondary).",
    )
    args = parser.parse_args(argv)
    try:
        repos = parse_repos_manifest(args.repos_manifest, args.home)
    except FleetBootstrapError as exc:
        print(f"FAIL bootstrap: {exc}", file=sys.stderr)
        return 1
    report = bootstrap(
        home=args.home,
        source_root=args.source_root,
        label=args.label,
        role=args.role,
        repos=repos,
        fleet_registry=args.fleet_registry,
    )
    for step in report["steps"]:
        print(f"{step['status'].upper()} bootstrap-{step['step']}: {step['detail']}")
        if step["receipt"]:
            print(f"  receipt: {step['receipt']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
