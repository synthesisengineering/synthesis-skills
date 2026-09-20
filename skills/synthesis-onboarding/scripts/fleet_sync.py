#!/usr/bin/env python3
"""One-command fleet sync: update, pull repos, heartbeat, verify, repair.

``synthesis sync`` is the enrolled Mac's daily driver: it brings the
whole machine to current without questions. Every step reports
ok/fail/skipped; failures are reported, never hidden, and nothing
here rewrites user work — pulls are fast-forward-only, dirty or
diverged checkouts are left alone and named.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

import fleet_join


class FleetSyncError(RuntimeError):
    """Sync cannot proceed (not enrolled, no manifest, no network path)."""


def _announce(line: str, progress=None, as_json: bool = False) -> None:
    if as_json:
        return
    if progress is not None:
        progress(line)
    else:
        print(line, flush=True)


def _run_cli(*argv: str) -> int:
    import synthesis_cli

    return synthesis_cli.main(list(argv))


def discover_kb_checkout(
    home: Path, machine_id: str
) -> Path:
    """Find the local KB checkout whose registry carries this machine.

    The enrolled Mac's registry copy is not enough: sync needs the
    knowledge checkout itself (manifests live there). Ambiguity and
    absence refuse with a --kb hint rather than guessing.
    """
    hits: list[Path] = []
    for candidate in sorted((home / "workspaces").glob("*")):
        for kb in sorted(candidate.glob("ai-knowledge-*")):
            registry = kb / "fleet" / "machines.json"
            try:
                doc = json.loads(registry.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (
                isinstance(doc, dict)
                and machine_id in doc.get("machines", {})
            ):
                hits.append(kb)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise FleetSyncError(
            "no knowledge checkout under ~/workspaces carries this "
            "machine's enrollment; pass --kb PATH"
        )
    names = ", ".join(str(path) for path in hits)
    raise FleetSyncError(
        f"multiple knowledge checkouts carry this machine ({names}); "
        "pass --kb PATH"
    )


def pull_repo(
    target: Path,
    branch: str,
    *,
    git_runner=None,
) -> tuple[str, str]:
    """Fast-forward one checkout; (status, detail), never destructive.

    Dirty trees, foreign branches, and diverged histories are skipped
    with a reason — sync reports them, it does not resolve them.
    """
    runner = git_runner or fleet_join._run_git
    current = runner(["branch", "--show-current"], target)
    if current.returncode != 0:
        return "skipped", "cannot read current branch"
    if current.stdout.strip() != branch:
        return "skipped", f"on {current.stdout.strip() or 'detached HEAD'}, not {branch}"
    dirty = runner(["status", "--porcelain"], target)
    if dirty.returncode != 0:
        return "skipped", "cannot read working tree"
    if dirty.stdout.strip():
        return "skipped", "dirty working tree"
    fetched = runner(["fetch", "--prune", "origin"], target)
    if fetched.returncode != 0:
        return "fail", "fetch failed"
    pulled = runner(
        ["pull", "--ff-only", "origin", branch], target
    )
    if pulled.returncode != 0:
        return "skipped", "diverged from origin (needs a rebase)"
    if "Already up to date" in pulled.stdout:
        return "ok", "already current"
    return "ok", "fast-forwarded"


def sync(
    args,
    *,
    release_root: Path,
    home: Path | None = None,
    bootstrap=None,
    git_runner=None,
    run_update: Callable[[], int] | None = None,
    run_doctor: Callable[[], int] | None = None,
    run_repair: Callable[[], int] | None = None,
    progress=None,
) -> int:
    """Run ``synthesis sync``; return the process exit code."""
    home = Path(home).expanduser() if home is not None else Path.home()
    as_json = bool(getattr(args, "json", False))
    announce = lambda line: _announce(  # noqa: E731
        line, progress, as_json
    )
    failures: list[str] = []
    engine = bootstrap
    if engine is None:
        engine = fleet_join.load_bootstrap(release_root)
    # load_bootstrap puts the project-management scripts on sys.path.
    import fleet_identity as FI

    fleet_dir = FI.fleet_dir_for_board(home / ".synthesis" / "coordination" / "board.md")
    machine_id = FI.read_machine_id(fleet_dir)
    if machine_id is None:
        raise FleetSyncError(
            "this Mac is not enrolled; run synthesis onboard first"
        )

    # 1. Update the installation (release, skills, clients).
    announce("update: refreshing the installation")
    update_code = (run_update or (lambda: _run_cli("update")))()
    if update_code != 0:
        failures.append("update")
        announce(f"update: exit {update_code} (continuing to local checks)")
    else:
        announce("update: ok")

    # 2. Knowledge checkout: pull it, then resolve the manifest.
    kb_arg = getattr(args, "kb", None)
    workspace = getattr(args, "workspace", None)
    try:
        if kb_arg:
            kb_dir, workspace = fleet_join.ensure_kb_checkout(
                kb_arg, home, workspace, git_runner=git_runner,
                progress=announce,
            )
            workspace = workspace or getattr(args, "workspace", None)
        else:
            kb_dir = discover_kb_checkout(home, machine_id)
        kb_status, kb_detail = pull_repo(
            kb_dir,
            _kb_branch(kb_dir, git_runner or fleet_join._run_git),
            git_runner=git_runner,
        )
        announce(f"knowledge checkout: {kb_status} ({kb_detail})")
        if kb_status == "fail":
            failures.append("knowledge checkout")
        manifest, workspace = fleet_join.discover_manifest(
            kb_dir, workspace, allow_empty=True,
        )
    except FleetSyncError as exc:
        announce(f"repos: skipped ({exc})")
        manifest, kb_dir, workspace = None, None, workspace
    except fleet_join.FleetJoinError as exc:
        announce(f"repos: skipped ({exc})")
        manifest, kb_dir, workspace = None, None, workspace

    # 3. Manifest repos: clone what's missing, pull what's present.
    if manifest is not None:
        repos = engine.parse_repos_manifest(manifest, home)
        cloned = engine.step_repos(
            home, repos, git_runner=git_runner, progress=announce
        )
        if cloned.status == "fail":
            failures.append("repos")
            announce(f"repos: fail ({cloned.detail})")
        else:
            for entry in repos:
                target = Path(entry["path"])
                if not (target / ".git").exists():
                    continue
                status, detail = pull_repo(
                    target, entry.get("branch", "main"),
                    git_runner=git_runner,
                )
                announce(f"{target.name}: {status} ({detail})")
                if status == "fail":
                    failures.append(str(target))

    # 4. Heartbeat: refresh last_seen and publish it back.
    if kb_dir is not None:
        try:
            local = FI.read_registry(fleet_dir)
            entry = local.get("machines", {}).get(machine_id, {})
            published = engine.step_publish(
                home, machine_id,
                label=entry.get("label", ""),
                role=entry.get("role", "secondary"),
                kb_repo=kb_dir, git_runner=git_runner,
                progress=announce,
            )
            if published.status == "fail":
                failures.append("heartbeat")
                announce(f"heartbeat: fail ({published.detail})")
            else:
                announce(f"heartbeat: {published.status}")
        except (OSError, ValueError) as exc:
            failures.append("heartbeat")
            announce(f"heartbeat: fail ({exc})")
    else:
        announce("heartbeat: skipped (no knowledge checkout)")

    # 5. Verify, repairing once when the doctor complains.
    doctor_code = (run_doctor or (lambda: _run_cli("doctor")))()
    if doctor_code == 0:
        announce("doctor: every plane green")
    else:
        announce(f"doctor: exit {doctor_code} — repairing")
        repair_code = (run_repair or (lambda: _run_cli("repair")))()
        if repair_code != 0:
            failures.append("repair")
            announce(f"repair: exit {repair_code}")
        else:
            announce("repair: done")

    if failures:
        announce(f"sync finished with {len(failures)} problem(s): " + ", ".join(failures))
        return 1
    announce("sync finished: this Mac is current")
    return 0


def _kb_branch(kb_dir: Path, git_runner) -> str:
    current = git_runner(["branch", "--show-current"], kb_dir)
    name = current.stdout.strip() if current.returncode == 0 else ""
    return name or "main"


def main(argv: list[str] | None = None) -> int:
    """Direct entry (tests and debugging); the CLI calls sync()."""
    import argparse

    parser = argparse.ArgumentParser(prog="fleet_sync")
    parser.add_argument("--kb", default=None)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--home", default=None)
    parser.add_argument("--json", action="store_true")
    parsed = parser.parse_args(argv)
    release_root = Path(__file__).resolve().parents[3]
    try:
        return sync(
            parsed, release_root=release_root,
            home=Path(parsed.home).expanduser() if parsed.home else None,
        )
    except FleetSyncError as exc:
        print(f"fleet sync failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
