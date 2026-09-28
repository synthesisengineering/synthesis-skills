#!/usr/bin/env python3
"""Hermes CLI recovery and installed-artifact protection via verified owners.

This pilot has no execution/claim authority. It prepares an inert native config,
observes selected native metadata and handles the documented shell-hook wire.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from hermes_source import chain, read_regular  # noqa: E402
from live_receipt import hermes_source_binding  # noqa: E402

ENTRY = "synthesis-agent-conformance/scripts/hermes_adapter.py"
SUPPORTED_WRITERS = frozenset({"terminal", "write_file", "patch"})


def _load(name, path):
    path = Path(path)
    raw, _, _ = read_regular(path)
    # Compile the exact inspected bytes, with no pyc or ambient path fallback.
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def prepare(root, profile_home, index, project, launcher, skills, *, capture_socket=None):
    root, profile_home, index, launcher = map(
        Path, (root, profile_home, index, launcher)
    )
    if any(not p.is_absolute() for p in (root, profile_home, index, launcher)):
        raise ValueError("explicit absolute paths required")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", project):
        raise ValueError("invalid project id")
    if not skills or len(skills) > 32 or len(set(skills)) != len(skills):
        raise ValueError("one to 32 distinct selected skills required")
    sys.path.insert(0, str(root / "skills/synthesis-onboarding/scripts"))
    import modular
    from vendor_bundle import source_inventory, digest

    selected = set(skills)
    pending = list(skills)
    while pending:
        name = pending.pop()
        if not re.fullmatch(r"synthesis-[a-z0-9-]+", name):
            raise ValueError("invalid public skill name")
        read_regular(root / "skills" / name / "SKILL.md")
        for dependency in modular._declared_dependencies(
            root / "skills" / name / "SKILL.md"
        ):
            if dependency not in selected:
                selected.add(dependency)
                pending.append(dependency)
        if len(selected) > 64:
            raise ValueError("skill dependency closure exceeds budget")
    manifest = []
    for name in sorted(selected):
        if not re.fullmatch(r"synthesis-[a-z0-9-]+", name):
            raise ValueError("invalid public skill name")
        relative = f"skills/{name}/SKILL.md"
        raw, _, _ = read_regular(root / relative)
        manifest.append(
            {
                "source": relative,
                "destination": str(profile_home / "skills" / name / "SKILL.md"),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "tree": source_inventory(root / "skills" / name),
                "tree_digest": digest(source_inventory(root / "skills" / name)),
            }
        )
    command = shlex.join(
        [
            str(launcher),
            "exec-public",
            ENTRY,
            "hook",
            "--profile-home",
            str(profile_home),
            "--index",
            str(index),
            "--project",
            project,
        ]
    )
    if capture_socket is not None:
        if not Path(capture_socket).is_absolute():
            raise ValueError("capture channel must be explicitly selected")
        command += " --capture-socket " + shlex.quote(str(capture_socket))
    return {
        "schema": 1,
        "client": "hermes",
        "surface": "cli-shell-hooks",
        "hooks": {
            event: [{"command": command, "timeout": 30, "fail_closed": True}]
            for event in ("pre_tool_call", "pre_llm_call", "on_session_start") + (("pre_api_request",) if capture_socket is not None else ())
        },
        "hooks_auto_accept": False,
        "skills": manifest,
        "activation": "NOT_PERFORMED",
        "native_live": "UNKNOWN",
        "execution_authority": "UNSUPPORTED",
        "trust_action": "Review and approve each native hook command in Hermes; never auto-accept.",
        "installation": {
            "owner": "direct_copy.sh",
            "argv": [str(root / "install.sh"), "install"],
            "environment": {
                "SYNTHESIS_SKILLS_SOURCE_DIR": str(root),
                "SYNTHESIS_SKILLS_TARGETS": str(profile_home / "skills"),
                "SYNTHESIS_SKILLS_SELECT": " ".join(sorted(selected)),
            },
        },
        "skill_installation": "The existing source installer owns copying, backup and provenance. Apply only this explicit reviewed destination; merge the hook fragment separately without replacing unrelated settings.",
        "coverage": sorted(SUPPORTED_WRITERS),
        "limits": "Other tools keep native behavior; this is not complete repository/communication admission.",
    }


def inspect_skills(root, profile_home, skills):
    plan = prepare(
        root,
        profile_home,
        Path("/projects/index.yaml"),
        "example",
        Path("/bin/synthesis"),
        skills,
    )
    result = []
    for item in plan["skills"]:
        try:
            from vendor_bundle import source_inventory

            installed = source_inventory(Path(item["destination"]).parent)
            installed = [v for v in installed if v["path"] != ".source.json"]
            status = "PASS" if installed == item["tree"] else "FAIL"
        except (OSError, ValueError):
            status = "UNKNOWN"
        result.append(
            {
                "skill": item["source"].split("/")[1],
                "installed": status,
                "native_live": "UNKNOWN",
            }
        )
    return result


def recover(index, project):
    import session_context
    from project_state import resolve_project

    home = Path(os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis")))
    report = resolve_project(
        project,
        Path(index),
        repo_guard_root=home / "repo-guard",
        coordination_board=(
            home / "coordination/active-sessions.md"
            if os.path.lexists(home / "coordination/active-sessions.md")
            else None
        ),
        checkpoint_receipt_root=home / "project-state/receipts",
        fetch=False,
        fast_forward_canonical=False,
        refresh_coordination=False,
    )
    if report.status not in {"PASS", "LOCAL_RECOVERABLE"} or not report.selected_path:
        raise ValueError(
            "project recovery is " + report.status + ": " + "; ".join(report.issues)
        )
    lines = []
    session_context.append_project_context(
        lines, Path(report.selected_path), label="Recovered project", diagnostic=True
    )
    result = "\n".join(lines)
    if len(result.encode()) > 16384:
        raise ValueError("recovered context exceeds the native injection budget")
    return (
        result
        + "\nHermes pilot is read/recovery plus installed-artifact protection. Authenticated managed writes remain unsupported; use a qualified owner."
    )


def guard(payload, profile_home):
    try:
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")
        tool = payload.get("tool_name")
        if not isinstance(tool, str) or not tool:
            raise ValueError("native tool name missing")
        if tool not in SUPPORTED_WRITERS:
            return {}
        args = payload.get("tool_input")
        if not isinstance(args, dict):
            raise ValueError("native tool arguments must be an object")
        normalized = {}
        if tool == "terminal":
            if not isinstance(args.get("command"), str) or not args["command"].strip():
                raise ValueError("terminal command is missing")
            normalized["command"] = args["command"]
            if "workdir" in args:
                if (
                    not isinstance(args["workdir"], str)
                    or not Path(args["workdir"]).is_absolute()
                ):
                    raise ValueError(
                        "native terminal workdir must be explicit and absolute"
                    )
                normalized["workdir"] = args["workdir"]
        elif tool == "patch" and args.get("mode", "replace") == "patch":
            if not isinstance(args.get("patch"), str):
                raise ValueError("patch body missing")
            normalized["patch"] = args["patch"]
        else:
            if tool == "patch" and args.get("mode", "replace") != "replace":
                raise ValueError("unsupported native patch mode")
            if not isinstance(args.get("path"), str) or not args["path"].strip():
                raise ValueError("native write path is missing")
            if not Path(args["path"]).is_absolute():
                raise ValueError(
                    "native persistent file-tool cwd is unavailable; absolute write path required"
                )
            normalized["path"] = args["path"]
        owner = _load(
            "_synthesis_hermes_installed_guard",
            ROOT
            / "skills/synthesis-agent-guardrails/guards/installed_artifact_guard.py",
        )
        if (
            tool == "patch"
            and args.get("mode") == "patch"
            and not owner.is_complete_patch_envelope(args["patch"])
        ):
            raise ValueError("incomplete native patch")
        if tool == "patch" and args.get("mode") == "patch":
            if any(
                not Path(path).is_absolute()
                for path in owner.patch_paths(args["patch"])
            ):
                raise ValueError(
                    "native persistent patch cwd is unavailable; absolute paths required"
                )
        owner.PROTECTED_ROOTS = (
            *owner.PROTECTED_ROOTS,
            Path(profile_home) / "skills",
            Path(profile_home) / "plugins",
        )
        spellings = []
        original_resolve = owner.resolve

        def tracked_resolve(value, cwd):
            if isinstance(value, str):
                cleaned = os.path.expanduser(value.strip().strip('"').strip("'"))
                spelling = Path(cleaned)
                if not spelling.is_absolute():
                    spelling = Path(cwd or os.getcwd()) / spelling
                spellings.append(Path(os.path.abspath(spelling)))
            return original_resolve(value, cwd)

        owner.resolve = tracked_resolve
        if tool == "terminal":
            # Hermes reports process cwd, but its terminal keeps a separate
            # session cwd/environment. Never substitute the process cwd for it.
            paths, errors = owner.shell_write_paths(
                normalized["command"],
                normalized.get("workdir", payload.get("cwd", "")),
                unknown_cwd="workdir" not in normalized,
                unknown_home=True,
            )
        else:
            paths, errors = owner.candidates(
                {"tool_input": normalized, "cwd": payload.get("cwd")}
            )
        if errors:
            raise ValueError(errors[0])
        for path in [*spellings, *paths]:
            reason = owner.reason_for(path)
            if reason:
                raise ValueError(reason)
        return {}
    except (OSError, ValueError, RuntimeError, ImportError, KeyError) as exc:
        return {
            "action": "block",
            "message": "Synthesis installed-artifact protection refused: "
            + str(exc)[:500],
        }


def handle(payload, profile_home, index, project, *, active=None, state_home=None, capture_socket=None):
    event = payload.get("hook_event_name") if isinstance(payload, dict) else None
    try:
        if event not in {"pre_tool_call", "pre_llm_call", "on_session_start", "pre_api_request"}:
            raise ValueError("unsupported hook event")
        profile_home = Path(profile_home)
        chain(profile_home)
        if Path(os.environ.get("HERMES_HOME", "")) != profile_home:
            raise ValueError("selected profile does not match native HERMES_HOME")
        binding = hermes_source_binding(
            profile_home,
            payload.get("session_id"),
            profile=payload.get("profile"),
            cwd=payload.get("cwd", ""),
        )
        if binding["status"] != "BOUND":
            raise ValueError(
                "native source binding is UNKNOWN: "
                + binding.get("reason", "unavailable")
            )
        if event == "pre_api_request":
            if capture_socket is None or active is None:
                raise ValueError("request observation requires the admitted capture channel")
            sys.path.insert(0, str(ROOT / "skills/synthesis-autopilot/scripts"))
            from hermes_transport import send
            send(capture_socket, payload, {}, active)
            return {}  # The native observer return never grants execution authority.
        context = recover(index, project)
        if event == "pre_tool_call":
            return guard(payload, profile_home)
        if active is not None:
            import session_context

            receipt = session_context.record_hermes_observation(
                payload, profile_home, active, state_home,
                context=context if capture_socket is not None and event == "pre_llm_call" else None,
            )
            if capture_socket is not None and event == "pre_llm_call":
                raw, _, _ = read_regular(receipt)
                context += "\nSYNTHESIS_NATIVE_RECEIPT " + json.dumps({
                    "event_id": receipt.stem, "sha256": hashlib.sha256(raw).hexdigest()}, sort_keys=True)
        result = {
            **({"context": context} if event == "pre_llm_call" else {}),
            "synthesis_observation": {
                "client": "hermes",
                "event": event,
                "source_binding": binding,
                "context_delivery": (
                    "NATIVE_CONSUMER_UNVERIFIED"
                    if event == "pre_llm_call"
                    else "NOT_APPLICABLE_OBSERVER"
                ),
                "native_live": "UNKNOWN",
                "authority": False,
            },
        }
        if capture_socket is not None and event == "pre_llm_call":
            if active is None:
                raise ValueError("verified execution source required for capture")
            sys.path.insert(0, str(ROOT / "skills/synthesis-autopilot/scripts"))
            from hermes_transport import send
            send(capture_socket, payload, result, active)
        return result
    except (OSError, ValueError, RuntimeError, ImportError, TypeError, KeyError) as exc:
        # Only pre_tool_call honors block. pre_llm_call teaches the same refusal;
        # the independently configured protective event still blocks tool use.
        reason = "Synthesis Hermes recovery refused: " + str(exc)[:500]
        return {
            "action": "block",
            "message": reason,
            "context": reason,
            "native_live": "UNKNOWN",
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["prepare", "hook", "inspect"])
    parser.add_argument("--profile-home", type=Path, required=True)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--project")
    parser.add_argument("--skill", action="append")
    parser.add_argument("--capture-socket", type=Path)
    args = parser.parse_args(argv)
    try:
        # A direct invocation never substitutes an arbitrary checkout for the
        # source and dependency closure already selected by exec-public.
        sys.path.insert(0, str(ROOT / "skills/synthesis-onboarding/scripts"))
        import release_runtime

        active = release_runtime.verified_release()
        if Path(active["release_root"]) != ROOT:
            raise ValueError("adapter is not the verified selected release")
        release_runtime.verify_dependencies(active, ENTRY)
        if args.operation == "hook":
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("hook input exceeds byte ceiling")
            from provider_intake import _unique_json

            payload = json.loads(raw, object_pairs_hook=_unique_json)
            result = handle(
                payload,
                args.profile_home,
                args.index,
                args.project,
                active=active,
                capture_socket=args.capture_socket,
                state_home=Path(
                    os.environ.get("SYNTHESIS_HOME", str(Path.home() / ".synthesis"))
                ),
            )
        elif args.operation == "prepare":
            launcher = release_runtime.verified_launcher(
                active, release_runtime.verify_interpreter(active["interpreter"])
            )
            result = prepare(
                ROOT,
                args.profile_home,
                args.index,
                args.project,
                launcher,
                args.skill or ["synthesis-project-management"],
                capture_socket=args.capture_socket,
            )
        else:
            result = {
                "skills": inspect_skills(
                    ROOT,
                    args.profile_home,
                    args.skill or ["synthesis-project-management"],
                ),
                "native_live": "UNKNOWN",
            }
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "action": "block",
                    "message": "Synthesis Hermes adapter unavailable: "
                    + str(exc)[:500],
                    "native_live": "UNKNOWN",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
