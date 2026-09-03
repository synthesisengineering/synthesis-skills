#!/usr/bin/env python3
"""Stable public command for synthesis installation and lifecycle management."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import onboard
import organization
from system_contract import (
    DESCRIPTOR_FIELDS,
    LAUNCHER_MARK,
    TRUTH_PLANES,
    ContractError,
    SystemState,
    active_release_descriptor,
    consume_invite,
    default_desired_state,
    json_digest,
    validate_invite,
    validate_desired_state,
    validate_repository_url,
    verify_materialized_release,
    verify_outcome,
)


ENGINE_VERSION = "2.1.0"
REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_COMMANDS = (
    "setup",
    "update",
    "repair",
    "status",
    "doctor",
    "workspace ensure",
    "outcome verify",
    "uninstall",
)


class EngineFailure(RuntimeError):
    def __init__(self, code: int):
        super().__init__("onboarding engine exited %d" % code)
        self.code = code


class RebootstrapRequired(RuntimeError):
    def __init__(self, channel: str, version_pin: str | None):
        super().__init__("selected policy requires a different immutable release")
        self.channel = channel
        self.version_pin = version_pin


def _common_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    parser.add_argument("--verbose", action="store_true", help="show successful child output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synthesis",
        description="Install, reconcile, diagnose, and update the synthesis work system.",
    )
    _common_output(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    setup = commands.add_parser("setup", help="converge a full or skills-only installation")
    setup.add_argument("--profile", choices=["full", "skills-only"], default="full")
    setup.add_argument("--clients")
    setup.add_argument("--channel", choices=["stable", "edge"])
    setup.add_argument("--pin", help="exact X.Y.Z release pin")
    setup.add_argument("--answers", type=Path)
    setup.add_argument("--org-repo")
    setup.add_argument("--invite", type=Path)
    setup.add_argument("--no-services", action="store_true")
    _common_output(setup)

    for name in ("update", "repair"):
        sub = commands.add_parser(name, help="%s the declared installation" % name)
        _common_output(sub)

    status = commands.add_parser("status", help="show desired and observed state")
    _common_output(status)
    doctor = commands.add_parser("doctor", help="verify every selected truth plane")
    _common_output(doctor)

    workspace = commands.add_parser("workspace", help="manage a personal workspace")
    workspace_commands = workspace.add_subparsers(dest="workspace_command", required=True)
    ensure = workspace_commands.add_parser("ensure", help="create or repair a tracked workspace")
    ensure.add_argument("--name", required=True)
    ensure.add_argument("--remote")
    _common_output(ensure)

    outcome = commands.add_parser("outcome", help="verify a trusted user outcome")
    outcome_commands = outcome.add_subparsers(dest="outcome_command", required=True)
    verify = outcome_commands.add_parser("verify", help="run a release-owned outcome verifier")
    verify.add_argument("--task", required=True)
    verify.add_argument("--workspace", required=True, type=Path)
    verify.add_argument("--source-class", required=True)
    _common_output(verify)

    uninstall = commands.add_parser("uninstall", help="archive and remove generated resources")
    uninstall.add_argument(
        "--purge",
        action="store_true",
        help="after verified removal, also delete the launcher, release caches, state, and configuration",
    )
    _common_output(uninstall)
    return parser


def _clients(value: str) -> list[str]:
    clients = [part.strip() for part in value.split(",") if part.strip()]
    if not clients or set(clients) - {"claude", "codex"}:
        raise ContractError("--clients must contain claude and/or codex")
    return sorted(set(clients))


def _active_release() -> dict[str, Any] | None:
    return active_release_descriptor()


def _policy_text(channel: str, version_pin: str | None) -> str:
    if version_pin:
        return "pinned release %s" % version_pin
    return "%s channel" % channel


def _transcript_binder() -> Callable[[Path, str, str], bool]:
    """The conformance transcript-binding check, loaded from this release tree."""
    scripts = REPO_ROOT / "skills" / "synthesis-agent-conformance" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from live_receipt import transcript_binds_session
    except ImportError as exc:
        raise ContractError("live receipt binder is unavailable: %s" % exc) from exc
    return transcript_binds_session


def _promote_live_receipts(state: SystemState) -> tuple[list[dict[str, Any]], str | None]:
    """Attach fresh client SessionStart receipts that bind their transcript now."""
    try:
        return state.promote_live_receipts(binder=_transcript_binder()), None
    except ContractError as exc:
        return [], str(exc)


def _release_label(release: dict[str, Any] | None) -> str:
    if not isinstance(release, dict) or not release.get("version"):
        return "unknown release"
    commit = str(release.get("commit") or "")
    return "%s from %s%s" % (
        release.get("version"),
        release.get("ref"),
        ", commit %s" % commit[:8] if commit else "",
    )


def _current_planes(
    desired: dict[str, Any],
    latest: dict[str, Any] | None,
    *,
    disabled: bool,
    engine_code: int,
    engine_details: dict[str, Any] | None,
    active: dict[str, Any] | None,
) -> dict[str, Any]:
    """Derive every plane from current evidence, not from the last transaction.

    The transaction record is the receipt of what the update saw when it
    ran. Doctor answers a different question: what is true now. Desired is
    compared by digest, the resolved and source-provenance planes are
    re-verified against the active release root, installed comes from the
    engine that just ran, and live-loaded reflects the receipts attached so
    far, including any promoted from the registry moments ago.
    """
    planes: dict[str, Any] = {
        plane: dict((latest or {}).get(plane) or {"status": "missing"})
        for plane in TRUTH_PLANES
    }
    expected_digest = (latest or {}).get(
        "committed_desired_digest", (latest or {}).get("desired_digest")
    )
    if expected_digest != json_digest(desired):
        planes["desired"] = {
            "status": "unverified",
            "detail": "desired state changed outside a committed synthesis transaction",
        }
    elif latest is not None:
        planes["desired"] = {"status": "verified", "sha256": json_digest(desired)}
    if latest is None:
        return planes
    if disabled:
        removal_verified = (
            engine_code == 0
            and bool(engine_details)
            and engine_details.get("uninstall_verified") is True
        )
        planes["installed"] = {
            "status": "removed" if removal_verified else "unverified",
            "command": "doctor",
            "detail": (
                "selected client plugins and receipt-owned resources are absent"
                if removal_verified
                else "absence could not be verified; run synthesis uninstall again"
            ),
        }
        return planes
    recorded = latest.get("release")
    if not isinstance(recorded, dict):
        resolved_plane = planes["resolved"]
        recorded = resolved_plane.get("release") if isinstance(resolved_plane, dict) else None
        if not isinstance(recorded, dict):
            recorded = None
    if active is not None:
        active_release = {key: active.get(key) for key in DESCRIPTOR_FIELDS}
        if recorded and recorded.get("content_digest") != active_release.get("content_digest"):
            planes["resolved"] = {
                "status": "changed",
                "release": active_release,
                "detail": "active release %s differs from generation %s release %s; run synthesis update"
                % (active_release.get("version"), latest.get("generation"), recorded.get("version")),
            }
        else:
            planes["resolved"] = {"status": "verified", "release": active_release}
        try:
            verify_materialized_release(Path(active["release_root"]), active_release)
            planes["source-provenance"] = {
                "status": "verified",
                "root": active["release_root"],
                "commit": active_release.get("commit"),
                "tree": active_release.get("tree"),
                "content_digest": active_release.get("content_digest"),
                "detail": "release root matches its content digest",
            }
        except ContractError as exc:
            planes["source-provenance"] = {
                "status": "drifted",
                "root": active["release_root"],
                "detail": str(exc),
            }
    else:
        planes["resolved"] = {
            "status": "development-source",
            "release": recorded,
            "detail": "no active release descriptor; running from a source checkout",
        }
        planes["source-provenance"] = {
            "status": "development-source",
            "root": str(REPO_ROOT),
            "detail": "no active release descriptor; running from a source checkout",
        }
    if engine_code == 0:
        planes["installed"] = {
            "status": "verified",
            "command": "doctor",
            "detail": "engine checks passed",
        }
    else:
        failing = (engine_details or {}).get("failing_steps") or []
        planes["installed"] = {
            "status": "defective",
            "command": "doctor",
            "detail": "; ".join(failing) or "engine exited %d" % engine_code,
        }
    live = planes["live-loaded"]
    release_version = (recorded or {}).get("version")
    receipts = live.get("receipts") if isinstance(live.get("receipts"), dict) else {}
    missing = [
        client
        for client in desired.get("clients") or []
        if not (
            isinstance(receipts.get(client), dict)
            and receipts[client].get("plugin_version") == release_version
        )
    ]
    if live.get("status") in ("missing", None):
        live = {"status": "restart-required", "detail": "no SessionStart receipt for this generation yet"}
    live = dict(live)
    live["missing_clients"] = missing
    planes["live-loaded"] = live
    return planes


def _non_green(planes: dict[str, Any], disabled: bool) -> bool:
    expected_live = "not-applicable" if disabled else "verified"
    if planes["live-loaded"].get("status") != expected_live:
        return True
    if any(
        planes[name].get("status") in ("missing", "unverified", "drifted", "changed", "defective")
        for name in ("desired", "resolved", "installed", "source-provenance")
    ):
        return True
    if disabled and planes["installed"].get("status") != "removed":
        return True
    return False


def _restart_instruction(client: str) -> str:
    if client == "claude":
        return "restart Claude Code and start a new chat"
    return (
        "restart Codex and start a new thread; if Codex shows pending hook review, "
        "approve the synthesis-skills hooks (Codex runs plugin hooks only after human trust)"
    )


def _next_action(
    desired: dict[str, Any],
    planes: dict[str, Any],
    disabled: bool,
    promotion_note: str | None,
) -> str:
    if disabled:
        if planes["installed"].get("status") == "removed":
            return "None for the removed installation; run synthesis setup to reinstall."
        return "Run synthesis uninstall again; removal could not be verified."
    if planes["desired"].get("status") != "verified":
        return "Run synthesis update to reconcile desired state that changed outside a transaction."
    if planes["resolved"].get("status") == "changed":
        return "Run synthesis update so the recorded generation matches the active release."
    if planes["source-provenance"].get("status") == "drifted":
        return (
            "The active release root no longer matches its content digest; "
            "run synthesis update to re-materialize the release."
        )
    if planes["installed"].get("status") == "defective":
        return "Run synthesis repair; the engine reported: %s" % planes["installed"].get("detail")
    live = planes["live-loaded"]
    if live.get("status") != "verified":
        clients = live.get("missing_clients") or list(desired.get("clients") or [])
        steps = "; ".join(_restart_instruction(client) for client in clients)
        note = " (%s)" % promotion_note if promotion_note else ""
        return "%s; then run synthesis doctor again%s" % (steps, note)
    if planes["outcome-verified"].get("status") in ("not-requested", "missing"):
        return (
            "Optional: synthesis outcome verify --task workspace-grounding-check "
            "--workspace <personal knowledge repository> --source-class personal-knowledge"
        )
    return "None; every plane is verified."


_PLANE_BADGES = {
    "verified": "ok",
    "removed": "ok",
    "development-source": "--",
    "not-requested": "--",
    "not-applicable": "--",
}


def _plane_summary(name: str, plane: dict[str, Any]) -> str:
    status = str(plane.get("status") or "missing")
    if name == "resolved" and isinstance(plane.get("release"), dict):
        return "%s: %s" % (status, _release_label(plane.get("release")))
    if name == "live-loaded":
        receipts = plane.get("receipts") if isinstance(plane.get("receipts"), dict) else {}
        parts = []
        for client, entry in sorted(receipts.items()):
            if isinstance(entry, dict):
                parts.append(
                    "%s at %s (session %s)"
                    % (client, entry.get("plugin_version"), str(entry.get("session_id") or "")[:8])
                )
        for client in plane.get("missing_clients") or []:
            parts.append("%s missing" % client)
        detail = "; ".join(parts) or str(plane.get("detail") or "")
        return "%s%s" % (status, " — " + detail if detail else "")
    detail = plane.get("detail")
    return "%s%s" % (status, " — " + str(detail) if detail else "")


def _render_doctor(
    payload: dict[str, Any], desired: dict[str, Any], latest: dict[str, Any] | None
) -> None:
    release = (latest or {}).get("release") if latest else None
    planes = payload["planes"]
    header = "Synthesis doctor: %s, %s" % (
        _release_label(release if isinstance(release, dict) else planes["resolved"].get("release")),
        "generation %s" % latest.get("generation") if latest else "no committed generation",
    )
    print(header)
    print("  Policy: %s; profile %s; clients %s" % (
        _policy_text(desired["release"]["channel"], desired["release"].get("version_pin")),
        desired.get("profile"),
        ", ".join(desired.get("clients") or []),
    ))
    for name in TRUTH_PLANES:
        plane = planes[name]
        badge = _PLANE_BADGES.get(str(plane.get("status")), "!!")
        print("  %-2s  %-18s %s" % (badge, name, _plane_summary(name, plane)))
    if payload.get("promoted"):
        print("  Attached fresh SessionStart evidence for: %s" % ", ".join(
            "%s (session %s)" % (item["client"], item["session_id"][:8]) for item in payload["promoted"]
        ))
    print("Next action: %s" % payload.get("next_action"))


def _render_status(payload: dict[str, Any]) -> None:
    desired = payload.get("desired")
    observed = payload.get("observed") or {}
    if desired is None:
        print("Synthesis status: no desired state on this machine; run synthesis setup.")
        return
    transactions = observed.get("transactions") or []
    committed = [item for item in transactions if item.get("state") == "committed"]
    aborted = [item for item in transactions if item.get("state") == "aborted"]
    latest = committed[-1] if committed else None
    release = desired["release"]
    print("Synthesis status")
    print("  Profile:     %s (clients: %s)%s" % (
        desired.get("profile"),
        ", ".join(desired.get("clients") or []),
        "" if desired.get("enabled", True) else "; disabled by uninstall",
    ))
    print("  Policy:      %s" % _policy_text(release["channel"], release.get("version_pin")))
    recorded = latest.get("release") if latest else None
    if not isinstance(recorded, dict) and latest:
        resolved = latest.get("resolved")
        recorded = resolved.get("release") if isinstance(resolved, dict) else None
    print("  Release:     %s" % (_release_label(recorded) if isinstance(recorded, dict) else "unknown (no committed generation)"))
    if latest:
        print("  Generation:  generation %s %s at %s (%s)" % (
            latest.get("generation"), latest.get("state"), latest.get("finished_at"), latest.get("command"),
        ))
    print("  History:     %d committed, %d aborted transaction(s)" % (len(committed), len(aborted)))
    print("  Workspace:   %s" % (desired.get("personal_workspace") or "none"))
    live = latest.get("live-loaded") if latest else None
    if isinstance(live, dict):
        receipts = live.get("receipts") if isinstance(live.get("receipts"), dict) else {}
        parts = [
            "%s at %s" % (client, entry.get("plugin_version"))
            for client, entry in sorted(receipts.items())
            if isinstance(entry, dict)
        ]
        recorded_version = recorded.get("version") if isinstance(recorded, dict) else None
        for client in desired.get("clients") or []:
            entry = receipts.get(client)
            if not (isinstance(entry, dict) and entry.get("plugin_version") == recorded_version):
                parts.append("%s missing" % client)
        print("  Live-loaded: %s%s" % (live.get("status"), " — " + "; ".join(parts) if parts else ""))
    else:
        print("  Live-loaded: unknown")
    outcome = latest.get("outcome-verified") if latest else None
    print("  Outcome:     %s" % (outcome.get("status") if isinstance(outcome, dict) else "unknown"))
    if payload.get("promoted"):
        print("  Attached fresh SessionStart evidence for: %s" % ", ".join(
            item["client"] for item in payload["promoted"]
        ))
    print("Next: run synthesis doctor for the verified truth planes and the next action.")


def _retained_paths(state: SystemState) -> list[str]:
    candidates = [
        state.launcher_path,
        state.state_dir / "active-release.json",
        state.cache_dir / "releases",
        state.cache_dir / "acquisition",
        state.desired_path,
        state.config_dir,
        state.state_dir,
    ]
    retained: list[str] = []
    for path in candidates:
        if (path.exists() or path.is_symlink()) and str(path) not in retained:
            retained.append(str(path))
    return retained


def _validate_purge_target(target: Path) -> None:
    """Independent validation of every recursive removal target."""
    if not target.is_absolute():
        raise ContractError("purge target is not absolute: %s" % target)
    if target.is_symlink():
        raise ContractError("purge target is a symbolic link: %s" % target)
    if target.name != "synthesis":
        raise ContractError("purge target is not a synthesis directory: %s" % target)
    resolved = target.resolve()
    forbidden = {Path("/"), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in forbidden or resolved.parent == Path("/"):
        raise ContractError("purge target is a protected directory: %s" % target)


def _force_writable(root: Path) -> None:
    for directory, dirnames, filenames in os.walk(root):
        current = Path(directory)
        for name in [*dirnames, *filenames]:
            path = current / name
            if path.is_symlink():
                continue
            try:
                os.chmod(path, 0o755 if path.is_dir() else 0o644)
            except OSError:
                pass
        try:
            os.chmod(current, 0o755)
        except OSError:
            pass


def _purge_installation(state: SystemState) -> list[str]:
    """Remove the launcher, caches, state, and configuration after a verified uninstall."""
    desired = state.read_desired()
    if desired is None or desired.get("enabled", True):
        raise ContractError("purge requires a verified uninstall; desired state is still enabled")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = state.synthesis_dir / "onboarding" / "backups" / stamp
    backup.mkdir(parents=True, exist_ok=True)
    for source in (state.desired_path, state.observation_path):
        if source.is_file() and not source.is_symlink():
            shutil.copy2(source, backup / source.name)
    purged: list[str] = []
    launcher = state.launcher_path
    if launcher.exists() or launcher.is_symlink():
        if launcher.is_symlink() or not launcher.is_file():
            raise ContractError("refusing to remove a launcher that is not a regular file")
        if LAUNCHER_MARK not in launcher.read_text(encoding="utf-8", errors="replace"):
            raise ContractError("refusing to remove a launcher this engine did not generate")
        launcher.unlink()
        purged.append(str(launcher))
    for target in (state.cache_dir, state.config_dir, state.state_dir):
        _validate_purge_target(target)
        if target.exists():
            _force_writable(target)
            shutil.rmtree(target)
            purged.append(str(target))
    return purged


def _planes(
    desired: dict[str, Any], command: str, *, removal_verified: bool = False
) -> dict[str, Any]:
    active_release = _active_release()
    release = None
    if active_release:
        release = {
            key: active_release.get(key)
            for key in (
                "schema_version",
                "version",
                "channel",
                "ref",
                "commit",
                "tree",
                "content_digest",
                "digest_algorithm",
                "tree_policy",
                "source_url",
                "resolved_at",
            )
        }
    source = {
        "status": "verified" if release else "development-source",
        "root": str(
            Path(active_release["release_root"]).resolve()
            if active_release and active_release.get("release_root")
            else REPO_ROOT
        ),
    }
    if release:
        source.update(
            {
                "commit": release.get("commit"),
                "tree": release.get("tree"),
                "content_digest": release.get("content_digest"),
            }
        )
    disabled = not desired.get("enabled", True)
    return {
        "desired": {"status": "verified", "sha256": json_digest(desired)},
        "resolved": {
            "status": "verified" if release else "development-source",
            "release": release,
        },
        "installed": {
            "status": (
                "removed"
                if disabled and removal_verified
                else "unverified"
                if disabled
                else "verified"
            ),
            "command": command,
        },
        "source-provenance": source,
        "live-loaded": {
            "status": "not-applicable" if disabled else "restart-required",
            "detail": (
                "No client load is expected for a disabled installation."
                if disabled
                else "Start a fresh selected-client session to establish live-loaded state."
            ),
        },
        "outcome-verified": {"status": "not-applicable" if disabled else "not-requested"},
        **({"release": release} if release else {}),
    }


def _engine_args(
    desired: dict[str, Any],
    command: str,
    args: argparse.Namespace,
    *,
    desired_state_path: Path | None = None,
) -> list[str]:
    clients = ",".join(desired["clients"])
    release = desired["release"]
    translated = [command, "--clients", clients, "--channel", release["channel"]]
    if release.get("version_pin"):
        translated.extend(["--version-pin", release["version_pin"]])
    if getattr(args, "answers", None):
        translated.extend(["--answers", str(args.answers)])
    if getattr(args, "no_services", False):
        translated.append("--no-services")
    if desired_state_path is not None:
        translated.extend(["--desired-state", str(desired_state_path)])
    return translated


def _validate_effective_selection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("onboarding engine effective selection must be an object")
    if set(value) != {
        "profile", "clients", "personal_workspace", "personal_configuration",
        "layers",
    }:
        raise ContractError("onboarding engine effective selection has invalid fields")
    normalized = default_desired_state(
        profile=value.get("profile"),
        clients=value.get("clients"),
        channel="stable",
        personal_workspace=value.get("personal_workspace"),
        personal_configuration=value.get("personal_configuration"),
        layers=value.get("layers"),
    )
    return {
        "profile": normalized["profile"],
        "clients": normalized["clients"],
        "personal_workspace": normalized["personal_workspace"],
        "personal_configuration": normalized["personal_configuration"],
        "layers": normalized["layers"],
    }


def _run_mutation(
    state: SystemState,
    desired: dict[str, Any],
    transaction_command: str,
    engine_args: list[str],
    engine_runner: Callable[[list[str]], Any],
    post_success: Callable[[], None] | None = None,
    already_locked: bool = False,
    extra_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_desired = state.read_desired()

    def operation(_transaction: dict[str, Any]) -> dict[str, Any]:
        code, engine_details = _execute_engine(engine_runner, engine_args)
        if code:
            raise EngineFailure(code)
        if not desired.get("enabled", True) and not (
            engine_details and engine_details.get("uninstall_verified") is True
        ):
            raise ContractError("uninstall completed without absence verification")
        if post_success:
            post_success()
        result = _planes(
            desired,
            transaction_command,
            removal_verified=bool(
                engine_details and engine_details.get("uninstall_verified") is True
            ),
        )
        details: dict[str, Any] = {}
        if engine_details is not None:
            details["engine"] = engine_details
        if extra_details:
            details.update(extra_details)
        if details:
            result["details"] = details
        return result

    def rollback(_error: BaseException) -> None:
        if previous_desired is None:
            return
        if previous_desired.get("enabled", True):
            rollback_args = _engine_args(
                previous_desired,
                "install",
                argparse.Namespace(answers=None, no_services=True),
            )
        else:
            rollback_args = [
                "uninstall",
                "--clients",
                ",".join(previous_desired["clients"]),
            ]
        code, details = _execute_engine(engine_runner, rollback_args)
        if code:
            raise EngineFailure(code)
        if not previous_desired.get("enabled", True) and not (
            details and details.get("uninstall_verified") is True
        ):
            raise ContractError("rollback could not verify the prior disabled state")

    return state.run_transaction(
        transaction_command,
        desired,
        operation,
        rollback=rollback,
        already_locked=already_locked,
    )


def _prepare_organization(
    state: SystemState,
    desired: dict[str, Any],
    *,
    verify_only: bool = False,
) -> tuple[dict[str, Any], Path | None, dict[str, Any] | None]:
    organizations = desired.get("organizations") or []
    if not organizations:
        return desired, None, None
    if len(organizations) != 1:
        raise ContractError("one organization repository may be enrolled per setup transaction")
    entry = dict(organizations[0])
    expected = entry.get("commit") if verify_only or entry.get("commit_policy") == "pinned" else None
    root, commit = organization.acquire_repository(
        entry["repository"],
        organization.default_data_root(state.home),
        expected_commit=expected,
        refresh=not verify_only,
    )
    manifest_path = root / organization.MANIFEST_RELATIVE
    manifest = onboard.load_manifest(manifest_path)
    entry["commit"] = commit
    updated = dict(desired)
    updated["organizations"] = [entry]
    if not verify_only:
        ecosystem = manifest.get("ecosystem") or {}
        updated["clients"] = sorted(
            set(ecosystem.get("clients", ["claude", "codex"]))
        )
        updated["release"] = {
            "channel": ecosystem.get("channel", "stable"),
            "version_pin": ecosystem.get("version_pin"),
        }
    validate_desired_state(updated)
    return updated, manifest_path, manifest


def _active_matches_policy(active: dict[str, Any], desired: dict[str, Any]) -> bool:
    release = desired["release"]
    pin = release.get("version_pin")
    if pin:
        return (
            active.get("channel") == "pin"
            and active.get("ref") == "v%s" % pin
            and active.get("version") == pin
        )
    expected_ref = "main" if release["channel"] == "edge" else "stable"
    return active.get("channel") == release["channel"] and active.get("ref") == expected_ref


def _render(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload.get("transaction_id"):
        print(
            "Synthesis generation %s %s. Restart selected clients before live verification."
            % (payload.get("generation"), payload.get("state"))
        )
        retained = (payload.get("details") or {}).get("retained") or []
        if retained and not payload.get("purged"):
            print("Retained (not removed by uninstall):")
            for path in retained:
                print("  - %s" % path)
            print("Run synthesis uninstall --purge to remove them; the launcher goes with them.")
        if payload.get("purged"):
            print("Purged:")
            for path in payload["purged"]:
                print("  - %s" % path)
    elif "desired" in payload and "observed" in payload:
        _render_status(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


def _quiet_engine_runner(engine_args: list[str], verbose: bool = False) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    structured_args = list(engine_args)
    if "--json" not in structured_args:
        structured_args.append("--json")
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = onboard.main(structured_args)
    if verbose or code:
        combined = stdout.getvalue() + stderr.getvalue()
        if combined:
            print(combined, end="" if combined.endswith("\n") else "\n", file=sys.stderr)
    rendered = stdout.getvalue()
    start = rendered.find("{")
    if start < 0:
        raise ContractError("onboarding engine emitted no structured result")
    try:
        payload = json.loads(rendered[start:])
    except ValueError as exc:
        raise ContractError("onboarding engine emitted an invalid structured result") from exc
    if not isinstance(payload, dict) or payload.get("exit") != code:
        raise ContractError("onboarding engine result disagrees with its exit status")
    return payload


def _execute_engine(
    engine_runner: Callable[[list[str]], Any], engine_args: list[str]
) -> tuple[int, dict[str, Any] | None]:
    raw = engine_runner(engine_args)
    if isinstance(raw, bool) or not isinstance(raw, (int, dict)):
        raise ContractError("onboarding engine runner returned an unsupported result")
    if isinstance(raw, int):
        return raw, None
    code = raw.get("exit")
    counts = raw.get("counts") or {}
    if isinstance(code, bool) or not isinstance(code, int) or not isinstance(counts, dict):
        raise ContractError("onboarding engine structured result is incomplete")
    safe_counts = {
        key: int(value)
        for key, value in counts.items()
        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
    }
    effective_selection = raw.get("effective_selection")
    if effective_selection is not None:
        effective_selection = _validate_effective_selection(effective_selection)
    failing_steps = [
        str(step.get("detail"))
        for step in (raw.get("steps") or [])
        if isinstance(step, dict)
        and step.get("status") in ("action-needed", "error")
        and step.get("detail")
    ]
    return code, {
        "version": raw.get("engine"),
        "status_counts": dict(sorted(safe_counts.items())),
        "changed_resources": safe_counts.get("changed", 0),
        "uninstall_verified": any(
            isinstance(step, dict)
            and step.get("phase") == "uninstall-verification"
            and step.get("status") == "ok"
            and step.get("uninstall_verified") is True
            for step in (raw.get("steps") or [])
        ),
        **(
            {"effective_selection": effective_selection}
            if effective_selection is not None
            else {}
        ),
        **({"failing_steps": failing_steps} if failing_steps else {}),
    }


def _run_release_bootstrap(
    argv: list[str] | None,
    active: dict[str, Any],
    channel: str,
    version_pin: str | None,
) -> int:
    bootstrap = Path(active["release_root"]) / "onboard.sh"
    if bootstrap.is_symlink() or not bootstrap.is_file():
        raise ContractError("active release has no trusted update bootstrap")
    command = [str(bootstrap), *(argv if argv is not None else sys.argv[1:])]
    environment = dict(os.environ)
    environment.pop("SYNTHESIS_ONBOARD_SOURCE_DIR", None)
    environment["SYNTHESIS_ONBOARD_CHANNEL"] = channel
    if version_pin:
        environment["SYNTHESIS_ONBOARD_VERSION_PIN"] = version_pin
    else:
        environment.pop("SYNTHESIS_ONBOARD_VERSION_PIN", None)
    return subprocess.call(command, env=environment)


def _bootstrap_update(
    argv: list[str] | None,
    state: SystemState,
) -> int | None:
    """Transfer an installed update to the newly resolved release exactly once."""
    if os.environ.get("SYNTHESIS_BOOTSTRAP_RESOLVED") == "1":
        return None
    active = _active_release()
    if active is None:
        return None
    desired = state.read_desired()
    if desired is None:
        return None
    if not desired.get("enabled", True):
        raise ContractError("the synthesis system is disabled; run synthesis setup")
    release = desired["release"]
    return _run_release_bootstrap(
        argv, active, release["channel"], release.get("version_pin")
    )


def _legacy_plugin_only_desired(state: SystemState) -> dict[str, Any]:
    """Migrate only a legacy receipt that proves a plugin-only installation."""
    legacy = state.legacy_migration_input()
    if legacy is None:
        raise ContractError(
            "no desired or legacy installation state exists; run synthesis setup"
        )

    valid_fields = (
        "receipt_version_valid",
        "profile_valid",
        "plugin_policy_valid",
        "layer_choices_valid",
        "component_choices_valid",
        "generated_files_valid",
        "adopted_repositories_valid",
        "managed_json_entries_valid",
        "managed_text_entries_valid",
        "runs_valid",
    )
    no_whole_system_state = (
        legacy.get("profile") in (None, "skills-only")
        and not legacy.get("personal_workspace_present")
        and not legacy.get("layer_choices")
        and not legacy.get("component_choices")
        and legacy.get("generated_file_count") == 0
        and legacy.get("adopted_repository_count") == 0
        and legacy.get("managed_json_entry_count") == 0
        and legacy.get("managed_text_entry_count") == 0
        and legacy.get("organization_run_count") == 0
        and not legacy.get("instruction_state_present")
        and legacy.get("unknown_field_count") == 0
    )
    if (
        not all(legacy.get(name) is True for name in valid_fields)
        or not no_whole_system_state
    ):
        raise ContractError(
            "legacy installation contains ambiguous whole-system or organization state; "
            "run synthesis setup to select the intended profile"
        )

    clients: list[str] = []
    uncertain: list[str] = []
    for client in ("claude", "codex"):
        binary = onboard.resolve_client(client)
        if not binary:
            continue
        present = onboard.plugin_present(client, binary)
        if present is None:
            uncertain.append(client)
        elif present is True:
            clients.append(client)
    if uncertain:
        raise ContractError(
            "legacy client plugin inventory is unreadable for: %s; run synthesis setup"
            % ", ".join(uncertain)
        )
    if not clients:
        raise ContractError(
            "legacy plugin-only installation has no verifiable installed client plugin; "
            "run synthesis setup"
        )

    policy = legacy.get("plugin_policy") or {
        "channel": "stable",
        "version_pin": None,
    }
    return default_desired_state(
        "skills-only",
        clients,
        policy["channel"],
        policy.get("version_pin"),
    )


def main(
    argv: list[str] | None = None,
    *,
    state: SystemState | None = None,
    engine_runner: Callable[[list[str]], Any] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    state = state or SystemState()
    engine_runner = engine_runner or (
        lambda engine_args: _quiet_engine_runner(engine_args, verbose=args.verbose)
    )
    try:
        if args.command == "update":
            transferred = _bootstrap_update(argv, state)
            if transferred is not None:
                return transferred
        if args.command == "setup":
            previous_desired = state.read_desired()
            engine_mutation_started = False
            if args.org_repo and args.invite:
                raise ContractError("use either --org-repo or --invite, not both")
            invite = None
            repository = args.org_repo
            expected_commit = None
            if args.invite:
                try:
                    invite = validate_invite(
                        json.loads(args.invite.read_text(encoding="utf-8"))
                    )
                except (OSError, ValueError) as exc:
                    raise ContractError("invite is unreadable: %s" % exc) from exc
                repository = invite["repository"]
                expected_commit = invite.get("repository_commit")
            if repository:
                validate_repository_url(repository)
            else:
                # Without an organization the release policy is fully known
                # here, so a needed transfer to the bootstrap happens before
                # any transaction is opened; it is a control handoff, not a
                # failed attempt.
                active = _active_release()
                probe = {
                    "release": {"channel": args.channel or "stable", "version_pin": args.pin}
                }
                if active and not _active_matches_policy(active, probe):
                    return _run_release_bootstrap(
                        argv, active, probe["release"]["channel"], args.pin
                    )
            request = {
                "schema_version": 1,
                "profile": args.profile,
                "clients": args.clients,
                "channel": args.channel,
                "version_pin": args.pin,
                "organization_repository": repository,
                "organization_commit": expected_commit,
            }

            def setup_operation(_transaction: dict[str, Any]) -> dict[str, Any]:
                nonlocal engine_mutation_started
                organizations = []
                manifest = None
                manifest_path = None
                if repository:
                    org_root, org_commit = organization.acquire_repository(
                        repository,
                        organization.default_data_root(state.home),
                        expected_commit=expected_commit,
                    )
                    manifest_path = org_root / organization.MANIFEST_RELATIVE
                    manifest = onboard.load_manifest(manifest_path)
                    organizations.append(
                        {
                            "repository": repository,
                            "manifest_path": organization.MANIFEST_RELATIVE,
                            "commit_policy": "pinned" if expected_commit else "floating",
                            "commit": org_commit,
                        }
                    )
                ecosystem = (manifest or {}).get("ecosystem") or {}
                clients_value = args.clients or ",".join(
                    ecosystem.get("clients", ["claude", "codex"])
                )
                channel = args.channel or ecosystem.get("channel", "stable")
                version_pin = (
                    args.pin
                    if args.pin is not None
                    else ecosystem.get("version_pin")
                )
                desired = default_desired_state(
                    profile=args.profile,
                    clients=_clients(clients_value),
                    channel=channel,
                    version_pin=version_pin,
                    organizations=organizations,
                )
                active = _active_release()
                if active and not _active_matches_policy(active, desired):
                    raise RebootstrapRequired(channel, version_pin)
                engine_args = _engine_args(desired, "init", args)
                engine_args[1:1] = ["--profile", args.profile]
                if manifest_path:
                    engine_args.extend(["--manifest", str(manifest_path)])
                engine_mutation_started = True
                code, engine_details = _execute_engine(engine_runner, engine_args)
                if code:
                    raise EngineFailure(code)
                final_desired = desired
                if engine_details is not None:
                    selection = engine_details.get("effective_selection")
                    if selection is None:
                        raise ContractError(
                            "onboarding engine omitted its effective selection"
                        )
                    if selection["profile"] != desired["profile"]:
                        raise ContractError(
                            "onboarding engine selected a different profile"
                        )
                    final_desired = default_desired_state(
                        profile=selection["profile"],
                        clients=selection["clients"],
                        channel=desired["release"]["channel"],
                        version_pin=desired["release"].get("version_pin"),
                        layers=selection["layers"],
                        organizations=desired["organizations"],
                        personal_workspace=selection["personal_workspace"],
                        personal_configuration=selection[
                            "personal_configuration"
                        ],
                    )
                if invite:
                    consume_invite(invite, state, already_locked=True)
                result = _planes(final_desired, "setup")
                result["_desired"] = final_desired
                if engine_details is not None:
                    result["details"] = {"engine": engine_details}
                return result

            def setup_rollback(_error: BaseException) -> None:
                if previous_desired is None or not engine_mutation_started:
                    return
                if previous_desired.get("enabled", True):
                    rollback_args = _engine_args(
                        previous_desired,
                        "install",
                        argparse.Namespace(answers=None, no_services=True),
                    )
                else:
                    rollback_args = [
                        "uninstall",
                        "--clients",
                        ",".join(previous_desired["clients"]),
                    ]
                rollback_code, rollback_details = _execute_engine(
                    engine_runner, rollback_args
                )
                if rollback_code:
                    raise EngineFailure(rollback_code)
                if not previous_desired.get("enabled", True) and not (
                    rollback_details
                    and rollback_details.get("uninstall_verified") is True
                ):
                    raise ContractError(
                        "rollback could not verify the prior disabled state"
                    )

            try:
                transaction = state.run_transaction(
                    "setup", request, setup_operation, rollback=setup_rollback
                )
            except RebootstrapRequired as exc:
                active = _active_release()
                if active is None:
                    raise ContractError("setup cannot transfer to its selected release")
                return _run_release_bootstrap(
                    argv, active, exc.channel, exc.version_pin
                )
            _render(transaction, args.json)
            return 0

        if args.command in ("update", "repair"):
            try:
                with state.locked():
                    desired = state.read_desired()
                    migrated_legacy = desired is None
                    if desired is None:
                        desired = _legacy_plugin_only_desired(state)
                    if not desired.get("enabled", True):
                        raise ContractError("the synthesis system is disabled; run synthesis setup")
                    # Without an organization the release policy is fully
                    # known before any transaction: a needed transfer to the
                    # bootstrap is a control handoff, not a failed attempt.
                    # An organization can still move the policy during
                    # resolution, so that case keeps the in-transaction check.
                    active_now = _active_release()
                    if (
                        not desired.get("organizations")
                        and active_now
                        and not _active_matches_policy(active_now, desired)
                    ):
                        release_policy = desired["release"]
                        raise RebootstrapRequired(
                            release_policy["channel"], release_policy.get("version_pin")
                        )

                    def update_operation(_transaction: dict[str, Any]) -> dict[str, Any]:
                        resolved, manifest_path, _manifest = _prepare_organization(
                            state, desired, verify_only=args.command == "repair"
                        )
                        active = _active_release()
                        if active and not _active_matches_policy(active, resolved):
                            release = resolved["release"]
                            raise RebootstrapRequired(
                                release["channel"], release.get("version_pin")
                            )
                        engine_args = _engine_args(
                            resolved,
                            args.command,
                            args,
                            desired_state_path=(
                                None if migrated_legacy else state.desired_path
                            ),
                        )
                        if resolved["release"] != desired["release"]:
                            engine_args.append("--policy-transition")
                        if manifest_path:
                            engine_args.extend(["--manifest", str(manifest_path)])
                        code, engine_details = _execute_engine(engine_runner, engine_args)
                        if code:
                            raise EngineFailure(code)
                        result = _planes(resolved, args.command)
                        result["_desired"] = resolved
                        if engine_details is not None:
                            result["details"] = {"engine": engine_details}
                        return result

                    transaction = state.run_transaction(
                        args.command,
                        desired,
                        update_operation,
                        already_locked=True,
                    )
            except RebootstrapRequired as exc:
                active = _active_release()
                if active is None:
                    raise ContractError("update cannot transfer to its selected release")
                asked_channel = os.environ.get("SYNTHESIS_ONBOARD_CHANNEL")
                asked_pin = os.environ.get("SYNTHESIS_ONBOARD_VERSION_PIN") or None
                if (
                    os.environ.get("SYNTHESIS_BOOTSTRAP_RESOLVED") == "1"
                    and (asked_channel, asked_pin) == (exc.channel, exc.version_pin)
                ):
                    # The bootstrap was already asked for exactly this policy
                    # and activated something else: re-running it would loop.
                    raise ContractError(
                        "the bootstrap activated %s (%s) but the selected policy needs %s; "
                        "the active release and desired state disagree, so the transfer "
                        "stopped instead of looping"
                        % (
                            active.get("version"),
                            active.get("ref"),
                            _policy_text(exc.channel, exc.version_pin),
                        )
                    )
                return _run_release_bootstrap(
                    argv, active, exc.channel, exc.version_pin
                )
            _render(transaction, args.json)
            return 0

        if args.command == "workspace":
            with state.locked():
                desired = state.read_desired()
                if desired is None:
                    detected = [
                        name for name in ("claude", "codex") if onboard.resolve_client(name)
                    ]
                    if not detected:
                        raise ContractError(
                            "no supported AI client was found and synthesis setup has not run; "
                            "install Claude Code or Codex and run the stable bootstrap first"
                        )
                    desired = default_desired_state(
                        "skills-only", detected, "stable", personal_workspace=args.name
                    )
                if not desired.get("enabled", True):
                    raise ContractError("the synthesis system is disabled; run synthesis setup")
                desired = dict(desired)
                desired["personal_workspace"] = args.name
                engine_args = ["init-workspace", "--workspace", args.name]
                if args.remote:
                    engine_args.extend(["--remote", args.remote])
                transaction = _run_mutation(
                    state,
                    desired,
                    "workspace-ensure",
                    engine_args,
                    engine_runner,
                    already_locked=True,
                )
            _render(transaction, args.json)
            return 0

        if args.command == "outcome":
            with state.locked():
                receipt = verify_outcome(
                    args.task,
                    {"workspace": str(args.workspace), "source_class": args.source_class},
                    REPO_ROOT,
                )
                recorded = state.record_outcome(receipt, already_locked=True)
            _render(recorded, args.json)
            return 0

        if args.command == "status":
            promoted, _promotion_note = _promote_live_receipts(state)
            with state.locked():
                payload = {"desired": state.read_desired(), "observed": state.read_observation()}
            payload["promoted"] = promoted
            _render(payload, args.json)
            return 0 if payload["desired"] is not None else 1

        if args.command == "doctor":
            with state.locked():
                desired = state.read_desired()
                if desired is None:
                    raise ContractError("no desired state exists; run synthesis setup")
                disabled = not desired.get("enabled", True)
                desired, manifest_path, _manifest = _prepare_organization(
                    state, desired, verify_only=True
                )
                code = 0
                engine_details: dict[str, Any] | None = None
                if disabled:
                    engine_args = [
                        "uninstall-doctor",
                        "--clients",
                        ",".join(desired["clients"]),
                    ]
                    code, engine_details = _execute_engine(engine_runner, engine_args)
                    if not code and not (
                        engine_details and engine_details.get("uninstall_verified") is True
                    ):
                        code = 1
                else:
                    engine_args = _engine_args(
                        desired,
                        "doctor",
                        args,
                        desired_state_path=state.desired_path,
                    )
                    if manifest_path:
                        engine_args.extend(["--manifest", str(manifest_path)])
                    code, engine_details = _execute_engine(engine_runner, engine_args)
            promoted: list[dict[str, Any]] = []
            promotion_note = None
            if not disabled:
                promoted, promotion_note = _promote_live_receipts(state)
            with state.locked():
                observation = state.read_observation()
            committed = [item for item in observation["transactions"] if item.get("state") == "committed"]
            latest = committed[-1] if committed else None
            active = None if disabled else _active_release()
            planes = _current_planes(
                desired,
                latest,
                disabled=disabled,
                engine_code=code,
                engine_details=engine_details,
                active=active,
            )
            next_action = _next_action(desired, planes, disabled, promotion_note)
            payload: dict[str, Any] = {
                "engine_exit": code,
                "planes": planes,
                "promoted": promoted,
                "next_action": next_action,
            }
            if promotion_note:
                payload["promotion_note"] = promotion_note
            if args.json:
                _render(payload, True)
            else:
                _render_doctor(payload, desired, latest)
            return 1 if code or _non_green(planes, disabled) else 0

        if args.command == "uninstall":
            with state.locked():
                desired = state.read_desired() or default_desired_state(
                    "skills-only", ["claude", "codex"], "stable"
                )
                desired = dict(desired)
                desired["enabled"] = False
                transaction = _run_mutation(
                    state,
                    desired,
                    "uninstall",
                    ["uninstall", "--clients", ",".join(desired["clients"])],
                    engine_runner,
                    already_locked=True,
                    extra_details={"retained": _retained_paths(state)},
                )
            payload = dict(transaction)
            if args.purge:
                payload["purged"] = _purge_installation(state)
            _render(payload, args.json)
            return 0
    except EngineFailure as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc), "exit": exc.code}, sort_keys=True))
        else:
            print("Synthesis failed: %s" % exc, file=sys.stderr)
        return exc.code
    except (ContractError, OSError, ValueError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc), "exit": 2}, sort_keys=True))
        else:
            print("Synthesis refused: %s" % exc, file=sys.stderr)
        return 2
    raise AssertionError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
