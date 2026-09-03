#!/usr/bin/env python3
"""Stable public command for synthesis installation and lifecycle management."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import onboard
import organization
from system_contract import (
    ContractError,
    SystemState,
    consume_invite,
    default_desired_state,
    json_digest,
    validate_invite,
    validate_desired_state,
    validate_release_descriptor,
    validate_repository_url,
    verify_outcome,
)


ENGINE_VERSION = "2.0.0"
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
    _common_output(uninstall)
    return parser


def _clients(value: str) -> list[str]:
    clients = [part.strip() for part in value.split(",") if part.strip()]
    if not clients or set(clients) - {"claude", "codex"}:
        raise ContractError("--clients must contain claude and/or codex")
    return sorted(set(clients))


def _active_release() -> dict[str, Any] | None:
    path_value = os.environ.get("SYNTHESIS_ACTIVE_DESCRIPTOR")
    if not path_value:
        return None
    try:
        path = Path(path_value)
        if path.is_symlink() or not path.is_file():
            raise ContractError("active release descriptor must be a regular file")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError("active release descriptor is unreadable: %s" % exc)
    if not isinstance(value, dict):
        raise ContractError("active release descriptor must be an object")
    release = validate_release_descriptor(
        {key: value.get(key) for key in (
            "schema_version", "version", "channel", "ref", "commit", "tree",
            "content_digest", "digest_algorithm", "tree_policy", "source_url",
            "resolved_at",
        )}
    )
    root_value = value.get("release_root")
    if not isinstance(root_value, str) or not root_value:
        raise ContractError("active release descriptor has no release root")
    root = Path(root_value)
    if root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise ContractError("active release descriptor has an unsafe release root")
    value.update(release)
    return value


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
        if engine_details is not None:
            result["details"] = {"engine": engine_details}
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
    elif "desired" in payload and "observed" in payload:
        desired = payload["desired"]
        observed = payload["observed"]
        print("Desired state: %s" % ("configured" if desired else "missing"))
        print("Observed generation: %s" % observed.get("generation", 0))
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
        raise ContractError("no desired state exists; run synthesis setup")
    if not desired.get("enabled", True):
        raise ContractError("the synthesis system is disabled; run synthesis setup")
    release = desired["release"]
    return _run_release_bootstrap(
        argv, active, release["channel"], release.get("version_pin")
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
                    if desired is None:
                        raise ContractError("no desired state exists; run synthesis setup")
                    if not desired.get("enabled", True):
                        raise ContractError("the synthesis system is disabled; run synthesis setup")

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
                            desired_state_path=state.desired_path,
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
                return _run_release_bootstrap(
                    argv, active, exc.channel, exc.version_pin
                )
            _render(transaction, args.json)
            return 0

        if args.command == "workspace":
            with state.locked():
                desired = state.read_desired() or default_desired_state(
                    "skills-only", ["claude", "codex"], "stable",
                    personal_workspace=args.name,
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
            with state.locked():
                payload = {"desired": state.read_desired(), "observed": state.read_observation()}
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
                    code, _engine_details = _execute_engine(engine_runner, engine_args)
                observation = state.read_observation()
            committed = [item for item in observation["transactions"] if item.get("state") == "committed"]
            latest = committed[-1] if committed else None
            plane_states = {
                plane: (latest or {}).get(plane, {"status": "missing"})
                for plane in ("desired", "resolved", "installed", "source-provenance", "live-loaded", "outcome-verified")
            }
            expected_desired_digest = (latest or {}).get(
                "committed_desired_digest", (latest or {}).get("desired_digest")
            )
            if expected_desired_digest != json_digest(desired):
                plane_states["desired"] = {
                    "status": "unverified",
                    "detail": "desired state changed outside a committed synthesis transaction",
                }
            payload = {"engine_exit": code, "planes": plane_states}
            _render(payload, args.json)
            expected_live = "not-applicable" if disabled else "verified"
            non_green = plane_states["live-loaded"].get("status") != expected_live
            non_green = non_green or any(
                plane_states[name].get("status") in ("missing", "unverified")
                for name in ("desired", "resolved", "installed", "source-provenance")
            )
            if disabled:
                non_green = non_green or plane_states["installed"].get("status") != "removed"
            return 1 if code or non_green else 0

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
                )
            _render(transaction, args.json)
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
