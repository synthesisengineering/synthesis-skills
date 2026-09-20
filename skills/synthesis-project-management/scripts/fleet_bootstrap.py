#!/usr/bin/env python3
"""Idempotent bootstrap for a new fleet Mac.

Provisioning order (architecture §9, clean-install path only — never copy a
Mac): mint identity, clone subscribed repos, install the hooks runtime plus
the skill set, enroll the machine, verify the doctor. Every step writes a
receipt under ``<home>/.synthesis/fleet/receipts/``; a safe rerun re-verifies
current state and reports ``noop`` instead of redoing work.

Humans should not invoke this script directly. The supported path is the
one-command wrapper, which discovers or asks for what it needs::

    synthesis fleet join

Direct usage (agents and tests only)::

    python3 fleet_bootstrap.py --home /Users/example --source-root ~/workspaces/example/synthesis-skills \\
        --label my-mac --role secondary --repos-manifest fleet-repos.json \\
        --fleet-registry ~/workspaces/personal/fleet/machines.json \\
        --kb-repo ~/workspaces/personal

``--repos-manifest`` is JSON: ``{"schema_version": 1, "repos":
[{"remote": "<url>", "path": "~/workspaces/<name>", "branch": "main"}]}``.
``branch`` is optional. Paths may be ``~``-rooted (expanded against
``--home``, never the invoking process's home) or absolute.
``--kb-repo`` is the knowledge working copy that carries the shared
``fleet/machines.json``; the final step publishes this Mac's enrollment
there so the rest of the fleet converges. Without it the enrollment
stays on this Mac and the run warns.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
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
STEP_PUBLISH = "publish-registry"

STATUS_DONE = "done"
STATUS_NOOP = "noop"
STATUS_FAIL = "fail"

GIT_TIMEOUT_SECONDS = 120
EXIT_INTERRUPTED = 130


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
    seen_paths: set[str] = set()
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
        resolved = str(expand_for_home(target, home))
        if resolved in seen_paths:
            raise FleetBootstrapError(
                f"repos[{position}] lists {resolved} twice; one entry per path"
            )
        seen_paths.add(resolved)
        parsed.append(
            {
                "remote": remote.strip(),
                "path": resolved,
                "branch": (branch or "").strip(),
            }
        )
    return parsed


def preflight(
    home: Path,
    role: str,
    fleet_registry: Path | None,
) -> list[str]:
    """Fail fast before any cloning: return every blocking problem found."""
    problems: list[str] = []
    if shutil.which("git") is None:
        problems.append(
            "git is not on PATH; install the Xcode Command Line Tools "
            "(xcode-select --install), then rerun the same command"
        )
    if not Path(home).expanduser().is_dir():
        problems.append(f"home {home} does not exist or is not a directory")
    if role == "secondary":
        if fleet_registry is None:
            problems.append(
                "secondary enrollment needs the synced fleet registry "
                "(--fleet-registry from the personal KB); refusing to found "
                "a second fleet"
            )
        elif not Path(fleet_registry).is_file():
            problems.append(f"synced fleet registry not found: {fleet_registry}")
        else:
            try:
                document = json.loads(
                    Path(fleet_registry).read_text(encoding="utf-8")
                )
            except (OSError, ValueError) as exc:
                problems.append(
                    f"synced fleet registry unusable: {exc}"
                )
            else:
                for issue in _identity.validate_registry(document):
                    problems.append(f"synced fleet registry invalid: {issue}")
    return problems


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
    except _identity.FleetIdentityError:
        # A concurrent run won the mint; adopt the winner's id so the
        # rerun (and this run) converge instead of failing.
        try:
            minted = _identity.read_machine_id(directory)
        except _identity.FleetIdentityError as exc:
            return StepResult(STEP_IDENTITY, STATUS_FAIL, str(exc))
        if minted is None:
            return StepResult(
                STEP_IDENTITY, STATUS_FAIL,
                "fleet machine-id mint lost a race and no id exists; "
                "rerun the same command",
            )
        return StepResult(
            STEP_IDENTITY, STATUS_NOOP, f"machine-id already minted: {minted}"
        )
    return StepResult(
        STEP_IDENTITY, STATUS_DONE, f"minted machine-id: {minted}"
    )


def step_repos(
    home: Path,
    repos: list[dict],
    *,
    git_runner=None,
    progress: Callable[[str], None] | None = None,
) -> StepResult:
    """Clone subscribed repos; existing checkouts verify, never clobber.

    ``progress`` receives one narrating line per repo as work lands, so a
    long clone stretch never looks hung.
    """
    runner = git_runner or _run_git
    if not repos:
        return StepResult(
            STEP_REPOS, STATUS_NOOP, "no repos manifest; nothing to clone"
        )
    cloned: list[str] = []
    verified: list[str] = []
    total = len(repos)
    for position, entry in enumerate(repos, start=1):
        target = Path(entry["path"])
        tag = f"[{position}/{total}]"
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
                    f"subscribed {entry['remote']}; refusing to clobber — "
                    "move it aside or fix its origin, then rerun the same "
                    "command",
                )
            verified.append(str(target))
            if progress is not None:
                progress(f"{tag} verified {target} (already cloned)")
            continue
        if target.exists():
            return StepResult(
                STEP_REPOS,
                STATUS_FAIL,
                f"{target}: exists but is not a git checkout; refusing to clobber",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        if progress is not None:
            progress(f"{tag} cloning {entry['remote']} -> {target}")
        # Clone beside the target and rename on success: an interrupted
        # clone leaves no half-checkout behind to block the rerun.
        staging = target.parent / f"{target.name}.partial-{os.getpid()}"
        for leftover in target.parent.glob(f"{target.name}.partial-*"):
            if leftover != staging:
                shutil.rmtree(leftover, ignore_errors=True)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        clone_args = ["clone", "--quiet", entry["remote"], str(staging)]
        if entry["branch"]:
            clone_args = [
                "clone", "--quiet", "--branch", entry["branch"],
                entry["remote"], str(staging),
            ]
        try:
            completed = runner(clone_args, None)
        except (OSError, subprocess.SubprocessError) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            return StepResult(
                STEP_REPOS, STATUS_FAIL, f"{target}: clone failed: {exc}"
            )
        if completed.returncode != 0:
            shutil.rmtree(staging, ignore_errors=True)
            return StepResult(
                STEP_REPOS,
                STATUS_FAIL,
                f"{target}: clone failed: {completed.stderr.strip()}",
            )
        try:
            os.rename(staging, target)
        except OSError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            return StepResult(
                STEP_REPOS, STATUS_FAIL,
                f"{target}: clone landed but rename failed: {exc}; "
                "rerun the same command",
            )
        cloned.append(str(target))
        if progress is not None:
            progress(f"{tag} cloned {target}")
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
    hostname: str | None = None,
    label_source: str | None = None,
) -> StepResult:
    """Enroll this Mac's minted identity in the fleet registry.

    A primary founds the registry; a secondary installs the synced copy
    (``--fleet-registry``, from the just-cloned personal KB) before
    enrolling. A secondary with no synced copy fails closed instead of
    founding a second, conflicting fleet. A label already held by a
    live other machine fails closed (relabel and rerun); so does a
    role that contradicts this Mac's own live enrollment.
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
    if (
        not registry_path.is_file()
        and fleet_registry is not None
        and Path(fleet_registry).is_file()
    ):
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
    if (
        isinstance(entry, dict)
        and entry.get("retired_at") is None
        and entry.get("role") != role
    ):
        return StepResult(
            STEP_ENROLL,
            STATUS_FAIL,
            f"machine {label} ({machine_id}) is already enrolled as "
            f"{entry.get('role')}; role changes are refused here — "
            "retire this entry before re-enrolling under another role",
        )
    rivals = [
        other_id
        for other_id, other in registry["machines"].items()
        if isinstance(other, dict)
        and other.get("retired_at") is None
        and other.get("label") == label.strip()
        and other_id != machine_id
    ]
    if rivals:
        rival = registry["machines"][rivals[0]]
        return StepResult(
            STEP_ENROLL,
            STATUS_FAIL,
            f"label {label.strip()} is already held by live machine "
            f"{rival.get('label')} ({rivals[0]}); rerun with a "
            "distinct --label so the fleet can tell its Macs apart",
        )
    if role == "primary":
        holders = [
            other_id
            for other_id, other in registry["machines"].items()
            if isinstance(other, dict)
            and other.get("retired_at") is None
            and other.get("role") == "primary"
            and other_id != machine_id
        ]
        if holders:
            holder = registry["machines"][holders[0]]
            return StepResult(
                STEP_ENROLL,
                STATUS_FAIL,
                f"fleet already has primary {holder.get('label')} "
                f"({holders[0]}); join as --role secondary instead of "
                "founding a second fleet",
            )
    try:
        _identity.enroll_self(
            label=label, role=role, directory=directory,
            hostname=hostname, label_source=label_source,
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


def _git_tail(completed) -> str:
    text = (completed.stderr or completed.stdout or "").strip().splitlines()
    return text[-1] if text else "no output"


def _diverged(repo: Path, pull_tail: str) -> StepResult:
    return StepResult(
        STEP_PUBLISH,
        STATUS_FAIL,
        f"{repo}: could not fast-forward onto the shared KB ({pull_tail}); "
        f"fetch the latest KB (git -C {repo} pull --rebase), resolve any "
        "conflicts, then rerun the same command",
    )


def _recover_concurrent_publish(
    runner, repo: Path, *, label: str, role: str, pull_tail: str,
    progress=None,
) -> StepResult | None:
    """Recover a failed fast-forward when safe; None means proceed.

    When the only unpushed commit is this Mac's own enroll commit, the
    recovery is mechanical: fetch, soften the commit back into the
    index, restore the remote's registry file, and let the normal
    union/commit/push path re-apply this Mac's entry on top. Anything
    else (other unpushed work, missing upstream, unreadable remote
    file) fails closed with the manual remedy.
    """
    try:
        fetched = runner(["fetch", "--quiet", "origin"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git fetch failed: {exc}"
        )
    if fetched.returncode != 0:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL,
            f"{repo}: git fetch failed: {_git_tail(fetched)}; check the "
            "network and rerun the same command",
        )
    try:
        ahead = runner(["rev-list", "--count", "@{u}..HEAD"], repo)
        subject = runner(["log", "-1", "--format=%s", "HEAD"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git failed: {exc}"
        )
    expected = f"fleet: enroll {label.strip()} as {role}"
    if (
        ahead.returncode != 0
        or ahead.stdout.strip() != "1"
        or subject.returncode != 0
        or subject.stdout.strip() != expected
    ):
        return _diverged(repo, pull_tail)
    if progress is not None:
        progress("another Mac published first; re-applying this Mac's "
                 "enrollment onto the latest shared registry")
    try:
        reset = runner(["reset", "--soft", "--quiet", "@{u}"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git reset failed: {exc}"
        )
    if reset.returncode != 0:
        return _diverged(repo, _git_tail(reset))
    try:
        exists = runner(
            ["cat-file", "-e", "@{u}:fleet/machines.json"], repo
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git failed: {exc}"
        )
    shared = repo / "fleet" / "machines.json"
    if exists.returncode != 0:
        try:
            shared.unlink(missing_ok=True)
        except OSError as exc:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL,
                f"shared registry unwritable: {exc}",
            )
        return None
    try:
        showed = runner(["show", "@{u}:fleet/machines.json"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git show failed: {exc}"
        )
    if showed.returncode != 0:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL,
            f"{repo}: remote registry unreadable: {_git_tail(showed)}; "
            "rerun the same command",
        )
    try:
        shared.write_text(showed.stdout, encoding="utf-8")
    except OSError as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"shared registry unwritable: {exc}"
        )
    return None


def step_publish(
    home: Path,
    machine_id: str,
    *,
    label: str,
    role: str,
    kb_repo: Path,
    git_runner=None,
    progress: Callable[[str], None] | None = None,
) -> StepResult:
    """Upsert this Mac's enrollment into the shared KB registry and push.

    The merge is one-directional and safe: the shared copy wins for every
    other machine (this Mac's synced copy may be stale); only this Mac's
    own freshly enrolled entry overlays. A rerun after a failed push
    pushes the already-written commit instead of duplicating it.
    """
    runner = git_runner or _run_git
    repo = Path(kb_repo).expanduser()
    shared = repo / "fleet" / "machines.json"
    if not repo.is_dir():
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"KB working copy not found: {repo}"
        )
    try:
        top = runner(["rev-parse", "--show-toplevel"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git failed: {exc}"
        )
    if top.returncode != 0:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL,
            f"{repo} is not a git checkout; refusing to publish there",
        )
    try:
        dirty = runner(
            ["status", "--porcelain", "--", "fleet/machines.json"], repo
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git failed: {exc}"
        )
    if dirty.returncode == 0 and dirty.stdout.strip():
        return StepResult(
            STEP_PUBLISH,
            STATUS_FAIL,
            f"{shared} has uncommitted changes; commit or stash them, "
            "then rerun the same command",
        )
    if progress is not None:
        progress(f"fetching the latest shared registry from {repo}")
    try:
        pulled = runner(["pull", "--ff-only", "--quiet"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git pull failed: {exc}"
        )
    if pulled.returncode != 0:
        # Another Mac may have published since this clone: when the only
        # unpushed commit is this Mac's own enroll commit, rebase the
        # registry at the data level (re-union onto the remote file)
        # instead of dead-ending. Anything else needs human eyes.
        recovered = _recover_concurrent_publish(
            runner, repo, label=label, role=role,
            pull_tail=_git_tail(pulled), progress=progress,
        )
        if recovered is not None:
            return recovered
    directory = fleet_dir_for(home)
    try:
        local = _identity.read_registry(directory)
    except _identity.FleetIdentityError as exc:
        return StepResult(STEP_PUBLISH, STATUS_FAIL, str(exc))
    own = local["machines"].get(machine_id)
    if not isinstance(own, dict):
        return StepResult(
            STEP_PUBLISH,
            STATUS_FAIL,
            "local registry has no entry for this machine; enroll step first",
        )
    if shared.is_file():
        try:
            document = json.loads(shared.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL,
                f"shared registry unreadable: {exc}",
            )
        problems = _identity.validate_registry(document)
        if problems:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL,
                "shared registry invalid: " + "; ".join(problems),
            )
    else:
        document = {"schema_version": 1, "machines": {}}
    merged = copy.deepcopy(document)
    merged["machines"][machine_id] = copy.deepcopy(own)
    if _identity.validate_registry(merged):
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL,
            "merged registry invalid: "
            + "; ".join(_identity.validate_registry(merged)),
        )
    committed = False
    if merged != document:
        (repo / "fleet").mkdir(parents=True, exist_ok=True)
        staging = shared.with_suffix(".json.tmp")
        try:
            staging.write_text(
                json.dumps(merged, indent=2) + "\n", encoding="utf-8"
            )
            os.replace(staging, shared)
        except OSError as exc:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL,
                f"shared registry unwritable: {exc}",
            )
        try:
            name = runner(["config", "user.name"], repo)
            email = runner(["config", "user.email"], repo)
        except (OSError, subprocess.SubprocessError) as exc:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL, f"{repo}: git failed: {exc}"
            )
        identity: list[str] = []
        if not name.stdout.strip() or not email.stdout.strip():
            identity = [
                "-c", f"user.name={label.strip()}",
                "-c", f"user.email={machine_id[:8]}@fleet.local",
            ]
        try:
            added = runner(["add", "fleet/machines.json"], repo)
        except (OSError, subprocess.SubprocessError) as exc:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL, f"{repo}: git add failed: {exc}"
            )
        if added.returncode != 0:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL,
                f"{repo}: git add failed: {_git_tail(added)}",
            )
        if progress is not None:
            progress(f"committing this Mac's enrollment in {repo}")
        try:
            made = runner(
                [*identity, "commit", "--quiet", "-m",
                 f"fleet: enroll {label.strip()} as {role}"],
                repo,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL, f"{repo}: git commit failed: {exc}"
            )
        if made.returncode != 0:
            return StepResult(
                STEP_PUBLISH, STATUS_FAIL,
                f"{repo}: git commit failed: {_git_tail(made)}",
            )
        committed = True
    if progress is not None:
        progress(f"pushing the shared registry from {repo}")
    try:
        pushed = runner(["push", "--quiet"], repo)
    except (OSError, subprocess.SubprocessError) as exc:
        return StepResult(
            STEP_PUBLISH, STATUS_FAIL, f"{repo}: git push failed: {exc}"
        )
    if pushed.returncode != 0:
        return StepResult(
            STEP_PUBLISH,
            STATUS_FAIL,
            f"{repo}: git push failed: {_git_tail(pushed)}; check the "
            "network and remote auth, then rerun the same command",
        )
    count = len(merged["machines"])
    if not committed:
        return StepResult(
            STEP_PUBLISH, STATUS_NOOP,
            f"registry already published ({count} machine(s))",
        )
    return StepResult(
        STEP_PUBLISH, STATUS_DONE,
        f"published {label.strip()} ({machine_id}) to the shared "
        f"registry ({count} machine(s))",
    )


def _record(
    home: Path, machine_id: str, result: StepResult
) -> StepResult | None:
    """Write one step receipt immediately; an error step when that fails."""
    try:
        write_receipt(home, result, machine_id)
    except OSError as exc:
        return StepResult(
            "write-receipt", STATUS_FAIL, f"receipt failed: {exc}"
        )
    return None


def _report(machine_id: str, results: list[StepResult]) -> dict:
    return {
        "machine_id": machine_id,
        "steps": [asdict(result) for result in results],
        "ok": all(result.status != STATUS_FAIL for result in results),
    }


def bootstrap(
    *,
    home: Path,
    source_root: Path,
    label: str,
    role: str,
    repos: list[dict] | None = None,
    fleet_registry: Path | None = None,
    kb_repo: Path | None = None,
    hostname: str | None = None,
    label_source: str | None = None,
    git_runner=None,
    install_runner=None,
    doctor_runner=None,
    progress: Callable[[str], None] | None = None,
) -> dict:
    """Run every bootstrap step in order; stop at the first failure.

    Each step receipt lands before the next step starts, so an
    interrupted run keeps evidence for everything it finished. The
    publish phase runs only when ``kb_repo`` names the knowledge
    working copy that carries the shared registry.
    """
    home = Path(home).expanduser()
    results: list[StepResult] = []
    machine_id = ""
    try:
        machine_id = _identity.read_machine_id(fleet_dir_for(home)) or ""
    except _identity.FleetIdentityError:
        machine_id = ""

    def run_step(result: StepResult) -> dict | None:
        results.append(result)
        error = _record(home, machine_id, result)
        if error is not None:
            results.append(error)
            _record(home, machine_id, error)
            return _report(machine_id, results)
        if result.status == STATUS_FAIL:
            return _report(machine_id, results)
        return None

    results.append(step_identity(home))
    try:
        machine_id = _identity.read_machine_id(fleet_dir_for(home)) or machine_id
    except _identity.FleetIdentityError:
        pass
    error = _record(home, machine_id, results[-1])
    if error is not None:
        results.append(error)
        return _report(machine_id, results)
    if results[-1].status == STATUS_FAIL:
        return _report(machine_id, results)

    stopped = run_step(
        step_repos(home, repos or [], git_runner=git_runner, progress=progress)
    )
    if stopped is not None:
        return stopped

    stopped = run_step(
        step_install(home, Path(source_root), install_runner=install_runner)
    )
    if stopped is not None:
        return stopped

    stopped = run_step(
        step_enroll(
            home, label=label, role=role, fleet_registry=fleet_registry,
            hostname=hostname, label_source=label_source,
        )
    )
    if stopped is not None:
        return stopped

    stopped = run_step(
        step_doctor(home, machine_id, doctor_runner=doctor_runner)
    )
    if stopped is not None:
        return stopped

    if kb_repo is not None:
        stopped = run_step(
            step_publish(
                home, machine_id, label=label, role=role,
                kb_repo=kb_repo, git_runner=git_runner, progress=progress,
            )
        )
        if stopped is not None:
            return stopped

    return _report(machine_id, results)


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
    parser.add_argument(
        "--kb-repo",
        type=Path,
        default=None,
        help="Knowledge working copy carrying fleet/machines.json; the "
        "final step publishes this Mac's enrollment there.",
    )
    args = parser.parse_args(argv)
    try:
        repos = parse_repos_manifest(args.repos_manifest, args.home)
    except FleetBootstrapError as exc:
        print(f"FAIL bootstrap: {exc}", file=sys.stderr)
        return 1
    problems = preflight(args.home, args.role, args.fleet_registry)
    if problems:
        for problem in problems:
            print(f"FAIL bootstrap: {problem}", file=sys.stderr)
        return 1
    if args.kb_repo is None:
        print(
            "WARN bootstrap: no --kb-repo; this Mac's enrollment stays "
            "local until it is published to the shared registry",
            file=sys.stderr,
        )

    def progress(line: str) -> None:
        print(line, flush=True)

    label = args.label.strip()
    if not label:
        print("FAIL bootstrap: --label must be a non-empty string",
              file=sys.stderr)
        return 1
    try:
        hostname = socket.gethostname().split(".")[0].strip() or None
    except OSError:
        hostname = None
    try:
        report = bootstrap(
            home=args.home,
            source_root=args.source_root,
            label=label,
            role=args.role,
            repos=repos,
            fleet_registry=args.fleet_registry,
            kb_repo=args.kb_repo,
            hostname=hostname,
            label_source="explicit",
            progress=progress,
        )
    except KeyboardInterrupt:
        print(
            "INTERRUPTED bootstrap: rerun the same command to resume; "
            "finished steps are kept",
            file=sys.stderr,
        )
        return EXIT_INTERRUPTED
    for step in report["steps"]:
        print(f"{step['status'].upper()} bootstrap-{step['step']}: {step['detail']}")
        if step["receipt"]:
            print(f"  receipt: {step['receipt']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
