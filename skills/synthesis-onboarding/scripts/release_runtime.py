"""Standalone verified execution contract embedded in the managed launcher.

This module has only standard-library dependencies. Setup embeds these exact
bytes in its pinned Python launcher; private consumers import that receipt-owned
launcher rather than importing Python from an unverified release or checkout.
"""

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import re
import select
import shlex
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit


SOURCE_IMPORT_CONTRACT = '''import sys as _source_sys
import os as _source_os
import _frozen_importlib_external as _source_loaders

def enable_source_imports(root):
    """Compile Python source; cached code never substitutes for checked text.

    Frozen/builtin modules and native extensions keep the interpreter's trust
    boundary. External source-only libraries continue to work; sourceless code
    is refused inside the verified release, not globally for third-party roots.
    """
    root = _source_os.path.realpath(_source_os.fspath(root))
    # The frozen loader module is shared by independently loaded copies of this
    # contract. Install once and retain every verified root; repeated private
    # hook loads must not grow a recursive chain or discard earlier boundaries.
    state_name = "_synthesis_source_import_state_v1"
    state = getattr(_source_loaders, state_name, None)
    if state is not None:
        state["roots"].add(root)
        _source_sys.dont_write_bytecode = True
        _source_sys.pycache_prefix = None
        return
    state = {"roots": {root},
             "previous_sourceless": _source_loaders.SourcelessFileLoader.get_code}

    def contained(path):
        absolute = _source_os.path.abspath(path)
        resolved = _source_os.path.realpath(absolute)
        inside = any(
            _source_os.path.commonpath((protected, absolute)) == protected or
            _source_os.path.commonpath((protected, resolved)) == protected
            for protected in state["roots"])
        if inside and absolute != resolved:
            raise ImportError("verified source import crosses a symbolic link")
        return inside

    def source_code(loader, fullname):
        # Bypass SourceFileLoader.get_code's cache lookup for timestamp and
        # hash-based caches, including PYTHONPYCACHEPREFIX locations. Reading
        # source through the loader preserves encoding-cookie handling.
        contained(loader.path)
        return loader.source_to_code(loader.get_data(loader.path), loader.path)

    def sourceless_code(loader, fullname):
        if contained(loader.path):
            raise ImportError("verified release requires Python source")
        return state["previous_sourceless"](loader, fullname)

    setattr(_source_loaders, state_name, state)
    _source_loaders.SourceFileLoader.get_code = source_code
    _source_loaders.SourcelessFileLoader.get_code = sourceless_code
    _source_sys.dont_write_bytecode = True
    _source_sys.pycache_prefix = None
'''
SOURCE_EXECUTION_CONTRACT = (
    SOURCE_IMPORT_CONTRACT
    + """
_source_root, _source_target = _source_sys.argv[1:3]
enable_source_imports(_source_root)
# -I -S admits only the pinned interpreter's library before this contract.
# Initialize its ordinary site dependencies after cache substitution is disabled.
import site
site.main()
import types
_source_sys.path.insert(0, _source_os.path.dirname(_source_target))
_source_sys.argv = [_source_target, *_source_sys.argv[3:]]
_source_main = types.ModuleType("__main__")
_source_main.__file__ = _source_target
_source_main.__package__ = None
_source_main.__spec__ = None
_source_main.__cached__ = None
_source_main.__loader__ = _source_loaders.SourceFileLoader("__main__", _source_target)
_source_sys.modules["__main__"] = _source_main
with open(_source_target, "rb") as _source_stream:
    _source_bytes = _source_stream.read()
exec(compile(_source_bytes, _source_target, "exec", dont_inherit=True), _source_main.__dict__)
"""
)

# This constant is part of the pinned runtime, never acquired from the environment.
_source_contract_namespace = {}
exec(SOURCE_IMPORT_CONTRACT, _source_contract_namespace)
enable_source_imports = _source_contract_namespace["enable_source_imports"]


def source_command(root, target, arguments):
    """Start a source-only process before site or release-owned imports."""
    return [
        sys.executable,
        "-B",
        "-I",
        "-S",
        "-c",
        SOURCE_EXECUTION_CONTRACT,
        str(root),
        str(target),
        *arguments,
    ]


RUNTIME_SCHEMA = 1
MAC_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
PUBLIC_ENTRYPOINTS = frozenset(
    {
        "synthesis-local-messaging/scripts/local_messaging_cli.py",
        "synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py",
        "synthesis-slack-sync/scripts/acquire.py",
        "synthesis-agent-conformance/scripts/hermes_adapter.py",
        "synthesis-agent-conformance/scripts/vendor_bundle.py",
        "synthesis-message-guard/scripts/message_guard.py",
        "synthesis-daily-rituals/scripts/repo_state.py",
        "synthesis-project-management/scripts/team_contract.py",
        "synthesis-project-management/scripts/team_records.py",
        "synthesis-project-management/scripts/contribution_evidence.py",
        "synthesis-agent-conformance/scripts/provider_intake.py",
        "synthesis-adversarial-review/scripts/review_contract.py",
        "synthesis-repo-guard/checkpoint_sync.py",
        "synthesis-repo-guard/repo_sync_check.py",
        "synthesis-agent-conformance/scripts/conformance.py",
        "synthesis-agent-conformance/scripts/session_context.py",
        "synthesis-context-lifecycle/scripts/context_doctor.py",
        "synthesis-context-lifecycle/scripts/context_edit.py",
        "synthesis-daily-rituals/scripts/ritual_state.py",
        "synthesis-daily-rituals/scripts/portfolio_review.py",
        "synthesis-daily-rituals/scripts/decay_sweep.py",
        "synthesis-daily-rituals/scripts/pr_queue_scan.py",
        "synthesis-daily-rituals/scripts/sync_watermark.py",
        "synthesis-daily-rituals/scripts/gchat_preflight.py",
        "synthesis-project-management/scripts/board_inbox.py",
        "synthesis-project-management/scripts/peer_send_gate.py",
        "synthesis-project-management/scripts/project_state.py",
        "synthesis-autopilot/scripts/autopilot_gate.py",
        "synthesis-agent-guardrails/guards/account_routing_guard.py",
        "synthesis-agent-guardrails/guards/publish_guard.py",
        "synthesis-agent-guardrails/hooks/claude/bare_filename_detector.py",
        "synthesis-agent-guardrails/hooks/claude/lazy_shortcut_detector.py",
        "synthesis-agent-guardrails/hooks/claude/long_session_detector.py",
        "synthesis-agent-guardrails/hooks/claude/pre_tool_temporal_reminder.py",
        "synthesis-agent-guardrails/hooks/claude/quote_provenance_checker.py",
        "synthesis-agent-guardrails/hooks/claude/sub_agent_brief_scanner.py",
        "synthesis-agent-guardrails/hooks/codex/bare_filename_detector.py",
        "synthesis-agent-guardrails/hooks/codex/installed_skill_edit_guard.py",
        "synthesis-agent-guardrails/hooks/codex/lazy_shortcut_detector.py",
        "synthesis-agent-guardrails/hooks/codex/quote_provenance_checker.py",
        "synthesis-agent-guardrails/hooks/codex/repo_guard_stop.py",
        "synthesis-agent-guardrails/hooks/codex/session_end_checkpoint.py",
        "synthesis-agent-guardrails/hooks/muse/lazy_shortcut_detector.py",
    }
)

# Recognized event identities may override a mislabeled Stop command. An
# unknown, empty, or malformed identity cannot exonerate a declared Stop.
NON_STOP_NATIVE_EVENTS = frozenset(
    {
        "SessionStart",
        "SessionEnd",
        "UserPromptSubmit",
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "PostToolUseFailure",
        "Notification",
        "SubagentStart",
        "PreCompact",
        "PostCompact",
        "TeammateIdle",
        "TaskCompleted",
        "ConfigChange",
        "InstructionsLoaded",
        "WorktreeCreate",
        "WorktreeRemove",
        "StopFailure",
        "Elicitation",
        "ElicitationResult",
    }
)


class RuntimeContractError(ValueError):
    """Execution cannot be bound to its setup receipt and immutable release."""


class ExecutionDeadline(BaseException):
    """Escape dependency recovery handlers and terminate at the launcher."""


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_interpreter():
    if os.environ.get("SYNTHESIS_RUNTIME_POLICY") == "packaged-python-v1":
        return str(Path(sys.executable).absolute())
    return (
        MAC_PYTHON if sys.platform == "darwin" else str(Path(sys.executable).absolute())
    )


def validate_python_version(version, *, platform=None, policy="prescribed-python-v1"):
    platform = sys.platform if platform is None else platform
    if policy == "packaged-python-v1":
        if platform not in {"darwin", "linux"}:
            raise RuntimeContractError("package execution supports macOS and Linux")
        if not re.fullmatch(r"3\.(12|13|14)\.[0-9]+", version):
            raise RuntimeContractError(
                "package execution requires validated Python 3.12, 3.13 or 3.14"
            )
        return
    if policy != "prescribed-python-v1":
        raise RuntimeContractError("unknown interpreter policy")
    if platform == "darwin" and version != "3.12.3":
        raise RuntimeContractError(
            "macOS execution requires the prescribed python.org 3.12.3 interpreter"
        )
    if not re.fullmatch(r"3\.12\.[0-9]+", version):
        raise RuntimeContractError(
            "execution requires the CI-validated Python 3.12 interpreter family"
        )


def interpreter_pin(path=None):
    policy = os.environ.get("SYNTHESIS_RUNTIME_POLICY", "prescribed-python-v1")
    path = str(path or selected_interpreter())
    if not Path(path).is_absolute() or any(c.isspace() for c in path):
        raise RuntimeContractError(
            "interpreter must have an absolute executable path without whitespace"
        )
    try:
        resolved = Path(path).resolve(strict=True)
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise RuntimeContractError("pinned interpreter is not executable")
        if resolved == Path(sys.executable).resolve():
            if sys.version_info.releaselevel != "final":
                raise RuntimeContractError("execution requires a final Python release")
            version = ".".join(str(v) for v in sys.version_info[:3])
        else:
            result = subprocess.run(
                [
                    path,
                    "-I",
                    "-B",
                    "-c",
                    "import sys; print('.'.join(map(str, sys.version_info[:3]))); sys.exit(0 if sys.version_info.releaselevel == 'final' else 1)",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if result.returncode:
                raise RuntimeContractError(
                    "prescribed interpreter could not report its version"
                )
            version = result.stdout.strip()
        validate_python_version(version, policy=policy)
        if (
            policy == "prescribed-python-v1"
            and sys.platform == "darwin"
            and path != MAC_PYTHON
        ):
            raise RuntimeContractError(
                "macOS interpreter must use the prescribed python.org 3.12.3 framework path"
            )
        return {
            "schema_version": 1,
            "policy": policy,
            "executable": path,
            "resolved_executable": str(resolved),
            "version": version,
            "sha256": file_digest(resolved),
            "platform": sys.platform,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeContractError(
            "prescribed interpreter is unavailable: %s" % exc
        ) from exc


def verify_interpreter(pin, *, require_current=True):
    """Validate setup ownership; executable dispatch always requires current identity."""
    if not isinstance(pin, dict) or pin.get("schema_version") != 1:
        raise RuntimeContractError("setup has not recorded an interpreter pin")
    path = pin.get("executable")
    if (
        not isinstance(path, str)
        or not Path(path).is_absolute()
        or any(c.isspace() for c in path)
    ):
        raise RuntimeContractError("interpreter pin is not an absolute executable path")
    try:
        resolved = Path(path).resolve(strict=True)
        if (
            str(resolved) != pin.get("resolved_executable")
            or not resolved.is_file()
            or not os.access(resolved, os.X_OK)
        ):
            raise RuntimeContractError("pinned interpreter target drifted")
        if file_digest(resolved) != pin.get("sha256"):
            raise RuntimeContractError("pinned interpreter bytes drifted")
        current = resolved == Path(sys.executable).resolve()
        if require_current and not current:
            raise RuntimeContractError("running interpreter differs from the setup pin")
        version = pin.get("version")
        if (
            not isinstance(version, str)
            or pin.get("platform") != sys.platform
            or (current and version != ".".join(str(v) for v in sys.version_info[:3]))
        ):
            raise RuntimeContractError(
                "running interpreter version or platform differs from the setup pin"
            )
        policy = pin.get("policy", "prescribed-python-v1")
        validate_python_version(version, policy=policy)
        if (
            policy == "prescribed-python-v1"
            and sys.platform == "darwin"
            and path != MAC_PYTHON
        ):
            raise RuntimeContractError(
                "macOS execution requires the prescribed python.org 3.12.3 framework path"
            )
        return path
    except OSError as exc:
        raise RuntimeContractError(
            "pinned interpreter is unavailable: %s" % exc
        ) from exc


def tree_digest(root):
    root = Path(root)
    entries = []
    try:
        for directory, dirnames, filenames in os.walk(
            root, topdown=True, followlinks=False
        ):
            current = Path(directory)
            kept = []
            for name in sorted(dirnames + filenames):
                path = current / name
                relative = path.relative_to(root).as_posix()
                if relative == ".git":
                    continue
                meta = path.lstat()
                if stat.S_ISLNK(meta.st_mode) or not (
                    stat.S_ISDIR(meta.st_mode) or stat.S_ISREG(meta.st_mode)
                ):
                    raise RuntimeContractError(
                        "release tree contains a link or special object"
                    )
                if stat.S_ISDIR(meta.st_mode):
                    kept.append(name)
                entries.append((relative, meta, path))
            dirnames[:] = kept
        digest = hashlib.sha256()
        for relative, meta, path in sorted(entries, key=lambda entry: entry[0]):
            if stat.S_ISDIR(meta.st_mode):
                digest.update(b"D\0" + relative.encode() + b"\0")
            else:
                mode = b"755" if meta.st_mode & stat.S_IXUSR else b"644"
                digest.update(
                    b"F\0"
                    + relative.encode()
                    + b"\0"
                    + mode
                    + b"\0"
                    + str(meta.st_size).encode()
                    + b"\0"
                    + bytes.fromhex(file_digest(path))
                )
        return digest.hexdigest()
    except OSError as exc:
        raise RuntimeContractError("release tree is unreadable: %s" % exc) from exc


def descriptor_path(home=None):
    explicit = os.environ.get("SYNTHESIS_ACTIVE_DESCRIPTOR")
    if explicit:
        return Path(explicit).expanduser()
    home = Path(home) if home is not None else Path.home()
    state = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state")))
    return state / "synthesis/active-release.json"


def verify_projection(root, descriptor):
    """Verify a reduced payload without weakening its original source binding."""
    projection = descriptor.get("projection")
    if projection is None:
        return descriptor["content_digest"]
    fields = {
        "schema_version",
        "kind",
        "content_digest",
        "source_content_digest",
        "selection",
        "files",
    }
    if (
        not isinstance(projection, dict)
        or set(projection) != fields
        or type(projection["schema_version"]) is not int
        or projection["schema_version"] != 1
        or projection["kind"] != "modular"
    ):
        raise RuntimeContractError("release projection shape is invalid")
    if projection["source_content_digest"] != descriptor["content_digest"]:
        raise RuntimeContractError(
            "projection differs from its verified source binding"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", str(projection["content_digest"])):
        raise RuntimeContractError("projection digest is invalid")
    selected = projection["selection"]
    if (
        not isinstance(selected, dict)
        or set(selected) != {"roots", "skills", "support_skills", "stage_core"}
        or type(selected["stage_core"]) is not bool
    ):
        raise RuntimeContractError("projection selection is invalid")
    for key in ("roots", "skills", "support_skills"):
        values = selected[key]
        if (
            not isinstance(values, list)
            or any(
                not isinstance(value, str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value)
                for value in values
            )
            or len(values) != len(set(values))
        ):
            raise RuntimeContractError("projection skill list is invalid")
    if not selected["roots"] or not set(selected["roots"]) <= set(selected["skills"]):
        raise RuntimeContractError("projection omits requested skills")
    records = projection["files"]
    if not isinstance(records, dict) or not records:
        raise RuntimeContractError("projection file inventory is invalid")
    observed = {}
    # tree_digest rejects symlinks and special objects before this walk.
    if tree_digest(root) != projection["content_digest"]:
        raise RuntimeContractError("projection content digest drifted")
    for path in Path(root).rglob("*"):
        if path.is_file():
            observed[path.relative_to(root).as_posix()] = {
                "sha256": file_digest(path),
                "mode": 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644,
            }
    if observed != records:
        raise RuntimeContractError("projection file membership or bytes drifted")
    return projection["content_digest"]


VERIFICATION_RECEIPT_SCHEMA = 1
VERIFICATION_MODE_RECEIPT = "activation-receipt-v1"
VERIFICATION_MODE_FULL = "full-digest-legacy"
# Entrypoints hashed at activation and re-checked per call, as paths
# relative to skills/ (the CLI shares the entrypoint layout).
ENTRYPOINT_DEPENDENCIES = {
    "synthesis-meeting-transcripts/optional-workspace-mcp/fetch-meeting.py": (
        "synthesis-daily-rituals/scripts/acquisition_transport.py",
        "synthesis-daily-rituals/scripts/archive_publish.py",
        "synthesis-daily-rituals/scripts/acquisition_evidence.py",
        "synthesis-daily-rituals/scripts/ritual_workers.py",
        "synthesis-daily-rituals/scripts/sync_watermark.py",
        "synthesis-meeting-transcripts/verify_transcripts.py",
        "synthesis-meeting-transcripts/optional-workspace-mcp/mcp_client.py",
        "synthesis-meeting-transcripts/optional-workspace-mcp/document_tabs.py",
        "synthesis-meeting-transcripts/optional-workspace-mcp/google_read.py",
        "synthesis-meeting-transcripts/optional-workspace-mcp/workspace_mcp_read.py",
    ),
    "synthesis-slack-sync/scripts/acquire.py": (
        "synthesis-daily-rituals/scripts/acquisition_transport.py",
        "synthesis-daily-rituals/scripts/archive_publish.py",
        "synthesis-daily-rituals/scripts/acquisition_evidence.py",
        "synthesis-daily-rituals/scripts/ritual_workers.py",
        "synthesis-daily-rituals/scripts/sync_watermark.py",
        "synthesis-meeting-transcripts/verify_transcripts.py",
        "synthesis-slack-sync/scripts/preflight.py",
        "synthesis-slack-sync/scripts/slack_workspaces.py",
        "synthesis-slack-sync/thread_checker.py",
        "synthesis-slack-sync/scripts/slack_read.py",
        "synthesis-slack-sync/scripts/connector_replay.py",
    ),
    "synthesis-agent-conformance/scripts/conformance.py": (
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
        "synthesis-repo-guard/publication_receipt.py",
    ),
    "synthesis-agent-conformance/scripts/session_context.py": (
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
        "synthesis-repo-guard/publication_receipt.py",
        "synthesis-onboarding/scripts/upgrade_campaigns.py",
        "synthesis-project-management/scripts/run_admission.py",
    ),
    "synthesis-autopilot/scripts/autopilot_gate.py": (
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
        "synthesis-repo-guard/publication_receipt.py",
    ),
    "synthesis-context-lifecycle/scripts/context_doctor.py": (
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
        "synthesis-repo-guard/publication_receipt.py",
    ),
    "synthesis-daily-rituals/scripts/pr_queue_scan.py": (
        "synthesis-bitbucket/scripts/pr_queue.py",
    ),
    "synthesis-daily-rituals/scripts/ritual_state.py": (
        "synthesis-daily-rituals/scripts/credential_paths.py",
        "synthesis-daily-rituals/scripts/ritual_workers.py",
    ),
    "synthesis-daily-rituals/scripts/sync_watermark.py": (
        "synthesis-daily-rituals/scripts/acquisition_evidence.py",
        "synthesis-daily-rituals/scripts/ritual_workers.py",
        "synthesis-meeting-transcripts/verify_transcripts.py",
    ),
    "synthesis-onboarding/scripts/synthesis_cli.py": (
        "synthesis-onboarding/scripts/maintenance_cli.py",
        "synthesis-onboarding/scripts/machine_review.py",
        "synthesis-onboarding/scripts/upgrade_campaigns.py",
        "synthesis-project-management/scripts/project_migration.py",
        "synthesis-project-management/scripts/project_format.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
    ),
    "synthesis-project-management/scripts/project_state.py": (
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
        "synthesis-repo-guard/publication_receipt.py",
    ),
    "synthesis-repo-guard/checkpoint_sync.py": (
        "synthesis-context-lifecycle/scripts/record_succession.py",
        "synthesis-context-lifecycle/scripts/record_transaction.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
        "synthesis-repo-guard/publication_receipt.py",
    ),
}
# Explicit direct consumers keep new helpers under the verified runtime owner.
ENTRYPOINT_DEPENDENCIES["synthesis-daily-rituals/scripts/repo_state.py"] = (
    "synthesis-daily-rituals/scripts/credential_paths.py",
    "synthesis-daily-rituals/scripts/ritual_workers.py",
    "synthesis-project-management/scripts/coordination_process.py",
)
# The peer gate imports the same schema owner in source and installed payloads.
# Receipt-mode invocation must authenticate the complete lazy import closure.
ENTRYPOINT_DEPENDENCIES["synthesis-message-guard/scripts/message_guard.py"] = (
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/coordination_schema.py",
)
# The organization selector is part of the actual onboarding call chain.
ENTRYPOINT_DEPENDENCIES["synthesis-onboarding/scripts/synthesis_cli.py"] = tuple(
    dict.fromkeys(
        (
            *ENTRYPOINT_DEPENDENCIES.get(
                "synthesis-onboarding/scripts/synthesis_cli.py", ()
            ),
            "synthesis-onboarding/scripts/team_enrollment.py",
            "synthesis-project-management/scripts/team_contract.py",
        )
    )
)
for _entry in (
    "synthesis-agent-conformance/scripts/conformance.py",
    "synthesis-agent-conformance/scripts/session_context.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/board_inbox.py",
    "synthesis-project-management/scripts/peer_send_gate.py",
    "synthesis-repo-guard/checkpoint_sync.py",
):
    ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
        dict.fromkeys(
            (
                *ENTRYPOINT_DEPENDENCIES.get(_entry, ()),
                "synthesis-project-management/scripts/team_contract.py",
            )
        )
    )

ENTRYPOINT_DEPENDENCIES["synthesis-agent-guardrails/guards/publish_guard.py"] = tuple(
    dict.fromkeys(
        (
            *ENTRYPOINT_DEPENDENCIES.get(
                "synthesis-agent-guardrails/guards/publish_guard.py", ()
            ),
            "synthesis-project-management/scripts/team_contract.py",
        )
    )
)

# Explicit team routes verify every local record/enrollment/journal owner they
# can invoke. Ordinary CLI routes retain their separately verified closure.
ENTRYPOINT_DEPENDENCIES["synthesis-project-management/scripts/team_records.py"] = (
    "synthesis-agent-conformance/scripts/active_project.py",
    "synthesis-agent-conformance/scripts/client_binaries.py",
    "synthesis-agent-conformance/scripts/live_receipt.py",
    "synthesis-agent-conformance/scripts/project_context.py",
    "synthesis-agent-conformance/scripts/session_context.py",
    "synthesis-autopilot/scripts/autopilot.py",
    "synthesis-autopilot/scripts/capabilities.py",
    "synthesis-autopilot/scripts/consumer_checks.py",
    "synthesis-autopilot/scripts/controller.py",
    "synthesis-autopilot/scripts/decision_uncertainty.py",
    "synthesis-autopilot/scripts/delegation_boundary.py",
    "synthesis-autopilot/scripts/domain_quality.py",
    "synthesis-autopilot/scripts/evaluation.py",
    "synthesis-autopilot/scripts/evaluation_artifacts.py",
    "synthesis-autopilot/scripts/evidence_bridge.py",
    "synthesis-autopilot/scripts/journal_storage.py",
    "synthesis-autopilot/scripts/native_adapter_sdk.py",
    "synthesis-autopilot/scripts/native_archive.py",
    "synthesis-autopilot/scripts/native_archive_stream.py",
    "synthesis-autopilot/scripts/native_claude.py",
    "synthesis-autopilot/scripts/native_codex.py",
    "synthesis-autopilot/scripts/native_doctor.py",
    "synthesis-autopilot/scripts/native_codex_turn.py",
    "synthesis-autopilot/scripts/native_callback.py",
    "synthesis-autopilot/scripts/managed_permissions.py",
    "synthesis-autopilot/scripts/managed_native.py",
    "synthesis-autopilot/scripts/native_protection.py",
    "synthesis-autopilot/scripts/native_copilot.py",
    "synthesis-autopilot/scripts/native_cursor.py",
    "synthesis-autopilot/scripts/native_muse.py",
    "synthesis-autopilot/scripts/native_muse_contract.py",
    "synthesis-autopilot/scripts/native_observations.py",
    "synthesis-autopilot/scripts/native_opencode.py",
    "synthesis-autopilot/scripts/native_resume.py",
    "synthesis-autopilot/scripts/native_review.py",
    "synthesis-autopilot/scripts/native_review_observer.py",
    "synthesis-autopilot/scripts/observation_bridge.py",
    "synthesis-autopilot/scripts/operator_status.py",
    "synthesis-autopilot/scripts/persistence_policy.py",
    "synthesis-autopilot/scripts/prepared_native_launch.py",
    "synthesis-autopilot/scripts/profile_evidence.py",
    "synthesis-autopilot/scripts/recovery_capsule.py",
    "synthesis-autopilot/scripts/required_citations.py",
    "synthesis-autopilot/scripts/resource_policy.py",
    "synthesis-autopilot/scripts/run_profile.py",
    "synthesis-autopilot/scripts/run_state.py",
    "synthesis-autopilot/scripts/supervision.py",
    "synthesis-autopilot/scripts/workflow.py",
    "synthesis-context-lifecycle/scripts/context_currency.py",
    "synthesis-context-lifecycle/scripts/context_edit.py",
    "synthesis-context-lifecycle/scripts/record_succession.py",
    "synthesis-context-lifecycle/scripts/record_transaction.py",
    "synthesis-decision-packet/scripts/build_packet.py",
    "synthesis-decision-packet/scripts/record_rulings.py",
    "synthesis-onboarding/scripts/enrollment.py",
    "synthesis-onboarding/scripts/machine_review.py",
    "synthesis-onboarding/scripts/maintenance_cli.py",
    "synthesis-onboarding/scripts/onboard.py",
    "synthesis-onboarding/scripts/organization.py",
    "synthesis-onboarding/scripts/owned_registrations.py",
    "synthesis-onboarding/scripts/plugin_currency.py",
    "synthesis-onboarding/scripts/reload_guidance.py",
    "synthesis-onboarding/scripts/runtime_payload.py",
    "synthesis-onboarding/scripts/system_contract.py",
    "synthesis-onboarding/scripts/team_enrollment.py",
    "synthesis-onboarding/scripts/team_retirement.py",
    "synthesis-onboarding/scripts/upgrade_campaigns.py",
    "synthesis-onboarding/scripts/whole_system.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/board_inbox.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/contribution_evidence.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/execution_checkpoint.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/native_identity.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/plan_reference.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_format.py",
    "synthesis-project-management/scripts/project_migration.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-repo-guard/publication_receipt.py",
    "synthesis-skills-manager/scripts/cache_guardian.py",
)
ENTRYPOINT_DEPENDENCIES[
    "synthesis-project-management/scripts/contribution_evidence.py"
] = (
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-project-management/scripts/coordination_process.py",
)
for _reader in (
    "synthesis-context-lifecycle/scripts/context_doctor.py",
    "synthesis-daily-rituals/scripts/portfolio_review.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-agent-guardrails/guards/publish_guard.py",
):
    ENTRYPOINT_DEPENDENCIES[_reader] = tuple(
        dict.fromkeys(
            (
                *ENTRYPOINT_DEPENDENCIES.get(_reader, ()),
                "synthesis-project-management/scripts/team_contract.py",
                "synthesis-project-management/scripts/native_identity.py",
                "synthesis-project-management/scripts/coordination_process.py",
            )
        )
    )

# Native identity is now a canonical dependency of every route that can load
# the existing project/native or team owners. Bind it before execution too.
_NATIVE_IDENTITY_CONSUMERS = {
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/coordination.py",
}
for _entry, _dependencies in tuple(ENTRYPOINT_DEPENDENCIES.items()):
    if ({_entry} | set(_dependencies)) & _NATIVE_IDENTITY_CONSUMERS:
        ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
            dict.fromkeys(
                (
                    *_dependencies,
                    "synthesis-project-management/scripts/native_identity.py",
                )
            )
        )

# Signed observations and exact-spec corpus review remain under their original
# conformance/decision owners in the verified entrypoint dependency inventory.
for _entry, _dependencies in {
    "synthesis-agent-conformance/scripts/conformance.py": (
        "synthesis-agent-conformance/scripts/live_receipt.py",
        "synthesis-agent-conformance/scripts/signed_receipt.py",
        "synthesis-onboarding/scripts/system_contract.py",
        "synthesis-skills-manager/scripts/cache_guardian.py",
    ),
    "synthesis-agent-conformance/scripts/provider_intake.py": (
        "synthesis-agent-conformance/scripts/signed_receipt.py",
        "synthesis-decision-packet/scripts/build_packet.py",
        "synthesis-decision-packet/scripts/record_rulings.py",
    ),
}.items():
    ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
        dict.fromkeys((*ENTRYPOINT_DEPENDENCIES.get(_entry, ()), *_dependencies))
    )

# Native pilot and vendor packages bind their actual static import closure.
# Dynamic YAML/vendor content retains its existing content-owning validator.
_NATIVE_PILOT_DEPENDENCIES = (
    # Existing first-run, report and identity owners are reached transitively.
    "synthesis-agent-conformance/scripts/report_contract.py",
    "synthesis-agent-conformance/references/conformance-report-v1.schema.json",
    "synthesis-onboarding/scripts/first_run_store.py",
    "synthesis-project-management/scripts/native_identity.py",
    "synthesis-agent-conformance/scripts/active_project.py",
    "synthesis-agent-conformance/scripts/capability_evidence.py",
    "synthesis-agent-conformance/scripts/client_binaries.py",
    "synthesis-agent-conformance/scripts/codex_app_server.py",
    "synthesis-agent-conformance/scripts/codex_hook_audit.py",
    "synthesis-agent-conformance/scripts/codex_skill_catalog.py",
    "synthesis-agent-conformance/scripts/conformance.py",
    "synthesis-agent-conformance/scripts/hermes_adapter.py",
    "synthesis-agent-conformance/scripts/hermes_source.py",
    "synthesis-agent-conformance/scripts/signed_receipt.py",
    "synthesis-agent-conformance/scripts/live_receipt.py",
    "synthesis-agent-conformance/scripts/project_context.py",
    "synthesis-agent-conformance/scripts/provider_intake.py",
    "synthesis-agent-conformance/scripts/session_context.py",
    "synthesis-agent-conformance/scripts/vendor_bundle.py",
    "synthesis-agent-conformance/scripts/yaml_runtime.py",
    "synthesis-agent-guardrails/guards/installed_artifact_guard.py",
    "synthesis-autopilot/scripts/native_adapter_sdk.py",
    "synthesis-context-lifecycle/scripts/context_currency.py",
    "synthesis-context-lifecycle/scripts/context_edit.py",
    "synthesis-context-lifecycle/scripts/record_succession.py",
    "synthesis-context-lifecycle/scripts/record_transaction.py",
    "synthesis-decision-packet/scripts/build_packet.py",
    "synthesis-decision-packet/scripts/record_rulings.py",
    "synthesis-onboarding/scripts/direct_copy.sh",
    "synthesis-onboarding/scripts/modular.py",
    "synthesis-onboarding/scripts/plugin_currency.py",
    "synthesis-onboarding/scripts/release_runtime.py",
    "synthesis-onboarding/scripts/system_contract.py",
    "synthesis-onboarding/scripts/upgrade_campaigns.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/board_inbox.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/plan_reference.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/publication_command.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-repo-guard/publication_receipt.py",
    "synthesis-skills-manager/scripts/cache_guardian.py",
)
for _entry in (
    "synthesis-agent-conformance/scripts/hermes_adapter.py",
    "synthesis-agent-conformance/scripts/vendor_bundle.py",
    "synthesis-agent-conformance/scripts/conformance.py",
    "synthesis-agent-conformance/scripts/session_context.py",
):
    ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
        dict.fromkeys(
            (
                *ENTRYPOINT_DEPENDENCIES.get(_entry, ()),
                *(_dep for _dep in _NATIVE_PILOT_DEPENDENCIES if _dep != _entry),
            )
        )
    )

# Hermes observation is a typed existing PM worker capability. Every entry
# reaching the journal or callback verifies its complete local owner closure.
_HERMES_OBSERVATION_DEPS = (
    "synthesis-autopilot/scripts/hermes_transport.py",
    "synthesis-autopilot/scripts/hermes_worker.py",
    "synthesis-autopilot/scripts/native_hermes.py",
    "synthesis-agent-conformance/scripts/vendor_hermes.py",
)
for _entry, _deps in list(ENTRYPOINT_DEPENDENCIES.items()):
    if (
        _entry
        in {
            "synthesis-agent-conformance/scripts/hermes_adapter.py",
            "synthesis-agent-conformance/scripts/vendor_bundle.py",
        }
        or "synthesis-autopilot/scripts/native_observations.py" in _deps
        or "synthesis-autopilot/scripts/delegation_boundary.py" in _deps
    ):
        ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
            dict.fromkeys((*_deps, *_HERMES_OBSERVATION_DEPS))
        )

# Host-specific PR support is optional in a modular release. A dependency
# present at activation must still verify; absence never means scanned.
ENTRYPOINT_DEPENDENCIES["synthesis-agent-conformance/scripts/conformance.py"] += (
    "synthesis-agent-conformance/scripts/report_contract.py",
    "synthesis-agent-conformance/references/conformance-report-v1.schema.json",
)

# The CLI reaches declared-machine mapping through the existing maintenance owner.
ENTRYPOINT_DEPENDENCIES["synthesis-onboarding/scripts/synthesis_cli.py"] += (
    "synthesis-onboarding/scripts/maintenance_cli.py",
    "synthesis-onboarding/scripts/runtime_payload.py",
    "synthesis-onboarding/references/platform-ownership-v1.json",
)

_VENDOR_NATIVE_DEPENDENCIES = (
    "synthesis-agent-conformance/scripts/hermes_source.py",
    "synthesis-agent-conformance/scripts/live_receipt.py",
    "synthesis-agent-conformance/scripts/signed_receipt.py",
    "synthesis-agent-conformance/scripts/vendor_bundle.py",
    "synthesis-agent-conformance/scripts/vendor_native.py",
    "synthesis-autopilot/scripts/autopilot.py",
    "synthesis-autopilot/scripts/capabilities.py",
    "synthesis-autopilot/scripts/consumer_checks.py",
    "synthesis-autopilot/scripts/controller.py",
    "synthesis-autopilot/scripts/decision_uncertainty.py",
    "synthesis-autopilot/scripts/delegation_boundary.py",
    "synthesis-autopilot/scripts/domain_quality.py",
    "synthesis-autopilot/scripts/evaluation.py",
    "synthesis-autopilot/scripts/evaluation_artifacts.py",
    "synthesis-autopilot/scripts/evidence_bridge.py",
    "synthesis-autopilot/scripts/journal_storage.py",
    "synthesis-autopilot/scripts/native_adapter_sdk.py",
    "synthesis-autopilot/scripts/native_archive.py",
    "synthesis-autopilot/scripts/native_archive_stream.py",
    "synthesis-autopilot/scripts/native_claude.py",
    "synthesis-autopilot/scripts/native_codex.py",
    "synthesis-autopilot/scripts/native_doctor.py",
    "synthesis-autopilot/scripts/native_codex_turn.py",
    "synthesis-autopilot/scripts/native_callback.py",
    "synthesis-autopilot/scripts/managed_permissions.py",
    "synthesis-autopilot/scripts/managed_native.py",
    "synthesis-autopilot/scripts/native_protection.py",
    "synthesis-autopilot/scripts/native_copilot.py",
    "synthesis-autopilot/scripts/native_cursor.py",
    "synthesis-autopilot/scripts/native_muse.py",
    "synthesis-autopilot/scripts/native_muse_contract.py",
    "synthesis-autopilot/scripts/native_observations.py",
    "synthesis-autopilot/scripts/native_opencode.py",
    "synthesis-autopilot/scripts/native_resume.py",
    "synthesis-autopilot/scripts/native_review.py",
    "synthesis-autopilot/scripts/native_review_observer.py",
    "synthesis-autopilot/scripts/observation_bridge.py",
    "synthesis-autopilot/scripts/persistence_policy.py",
    "synthesis-autopilot/scripts/prepared_native_launch.py",
    "synthesis-autopilot/scripts/profile_evidence.py",
    "synthesis-autopilot/scripts/recovery_capsule.py",
    "synthesis-autopilot/scripts/required_citations.py",
    "synthesis-autopilot/scripts/resource_policy.py",
    "synthesis-autopilot/scripts/run_profile.py",
    "synthesis-autopilot/scripts/run_state.py",
    "synthesis-autopilot/scripts/supervision.py",
    "synthesis-autopilot/scripts/workflow.py",
    "synthesis-context-lifecycle/scripts/context_currency.py",
    "synthesis-context-lifecycle/scripts/context_edit.py",
    "synthesis-context-lifecycle/scripts/record_succession.py",
    "synthesis-context-lifecycle/scripts/record_transaction.py",
    "synthesis-decision-packet/scripts/build_packet.py",
    "synthesis-decision-packet/scripts/record_rulings.py",
    "synthesis-onboarding/scripts/release_runtime.py",
    "synthesis-onboarding/scripts/system_contract.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/execution_checkpoint.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/plan_reference.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-repo-guard/publication_receipt.py",
    "synthesis-skills-manager/scripts/cache_guardian.py",
)
for _entry in ("synthesis-agent-conformance/scripts/vendor_bundle.py",):
    ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
        dict.fromkeys(
            (
                *ENTRYPOINT_DEPENDENCIES.get(_entry, ()),
                *(_dep for _dep in _VENDOR_NATIVE_DEPENDENCIES if _dep != _entry),
            )
        )
    )

# Host-specific PR support is optional in a modular release. A dependency
# present at activation must still verify; absence never means scanned.
# Native consumers may reach managed invocation via a vendor/team owner. Bind
# the newly executable helpers at every such public receipt boundary, including
# callers which contain that owner transitively rather than a direct import.
for _entry, _dependencies in tuple(ENTRYPOINT_DEPENDENCIES.items()):
    if any(
        _owner in _dependencies
        for _owner in (
            "synthesis-autopilot/scripts/autopilot.py",
            "synthesis-autopilot/scripts/delegation_boundary.py",
            "synthesis-agent-conformance/scripts/vendor_bundle.py",
        )
    ):
        ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
            dict.fromkeys(
                (
                    *_dependencies,
                    "synthesis-autopilot/scripts/managed_permissions.py",
                    "synthesis-autopilot/scripts/managed_native.py",
                    "synthesis-autopilot/scripts/native_protection.py",
                    "synthesis-autopilot/scripts/native_codex_turn.py",
                )
            )
        )

# Transcript identity has one stdlib-only source owner. Bind it for every
# verified entrypoint that reaches either receipt or native identity consumers.
for _entry, _dependencies in tuple(ENTRYPOINT_DEPENDENCIES.items()):
    if ({_entry} | set(_dependencies)) & {
        "synthesis-agent-conformance/scripts/live_receipt.py",
        "synthesis-project-management/scripts/native_identity.py",
    }:
        ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
            dict.fromkeys(
                (
                    *_dependencies,
                    "synthesis-agent-conformance/scripts/native_transcript_identity.py",
                )
            )
        )

# Stop selects desktop identity and registered owners lazily. Bind the entire
# local import closure before the activation hash inventory is constructed.
# These are source-owned fixed paths, never discovered from caller input.
_AUTOPILOT_STOP_DEPENDENCIES = (
    "synthesis-agent-conformance/scripts/hermes_source.py",
    "synthesis-agent-conformance/scripts/live_receipt.py",
    "synthesis-agent-conformance/scripts/native_transcript_identity.py",
    "synthesis-agent-conformance/scripts/signed_receipt.py",
    "synthesis-agent-conformance/scripts/vendor_bundle.py",
    "synthesis-agent-conformance/scripts/vendor_hermes.py",
    "synthesis-agent-conformance/scripts/vendor_native.py",
    "synthesis-autopilot/scripts/autopilot.py",
    "synthesis-autopilot/scripts/capabilities.py",
    "synthesis-autopilot/scripts/consumer_checks.py",
    "synthesis-autopilot/scripts/controller.py",
    "synthesis-autopilot/scripts/decision_uncertainty.py",
    "synthesis-autopilot/scripts/delegation_boundary.py",
    "synthesis-autopilot/scripts/domain_quality.py",
    "synthesis-autopilot/scripts/evaluation.py",
    "synthesis-autopilot/scripts/evaluation_artifacts.py",
    "synthesis-autopilot/scripts/evidence_bridge.py",
    "synthesis-autopilot/scripts/hermes_transport.py",
    "synthesis-autopilot/scripts/hermes_worker.py",
    "synthesis-autopilot/scripts/journal_storage.py",
    "synthesis-autopilot/scripts/managed_native.py",
    "synthesis-autopilot/scripts/managed_permissions.py",
    "synthesis-autopilot/scripts/native_adapter_sdk.py",
    "synthesis-autopilot/scripts/native_archive.py",
    "synthesis-autopilot/scripts/native_archive_stream.py",
    "synthesis-autopilot/scripts/native_callback.py",
    "synthesis-autopilot/scripts/native_claude.py",
    "synthesis-autopilot/scripts/native_codex.py",
    "synthesis-autopilot/scripts/native_doctor.py",
    "synthesis-autopilot/scripts/native_codex_turn.py",
    "synthesis-autopilot/scripts/native_copilot.py",
    "synthesis-autopilot/scripts/native_cursor.py",
    "synthesis-autopilot/scripts/native_hermes.py",
    "synthesis-autopilot/scripts/native_muse.py",
    "synthesis-autopilot/scripts/native_muse_contract.py",
    "synthesis-autopilot/scripts/native_observations.py",
    "synthesis-autopilot/scripts/native_opencode.py",
    "synthesis-autopilot/scripts/native_protection.py",
    "synthesis-autopilot/scripts/native_resume.py",
    "synthesis-autopilot/scripts/native_review.py",
    "synthesis-autopilot/scripts/native_review_observer.py",
    "synthesis-autopilot/scripts/native_stop.py",
    "synthesis-autopilot/scripts/observation_bridge.py",
    "synthesis-autopilot/scripts/persistence_policy.py",
    "synthesis-autopilot/scripts/prepared_native_launch.py",
    "synthesis-autopilot/scripts/profile_evidence.py",
    "synthesis-autopilot/scripts/recovery_capsule.py",
    "synthesis-autopilot/scripts/required_citations.py",
    "synthesis-autopilot/scripts/resource_policy.py",
    "synthesis-autopilot/scripts/run_profile.py",
    "synthesis-autopilot/scripts/run_state.py",
    "synthesis-autopilot/scripts/supervision.py",
    "synthesis-autopilot/scripts/workflow.py",
    "synthesis-context-lifecycle/scripts/context_currency.py",
    "synthesis-context-lifecycle/scripts/context_edit.py",
    "synthesis-context-lifecycle/scripts/record_succession.py",
    "synthesis-context-lifecycle/scripts/record_transaction.py",
    "synthesis-decision-packet/scripts/build_packet.py",
    "synthesis-decision-packet/scripts/record_rulings.py",
    "synthesis-onboarding/scripts/first_run_store.py",
    "synthesis-onboarding/scripts/release_runtime.py",
    "synthesis-onboarding/scripts/system_contract.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/execution_checkpoint.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/native_identity.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/plan_reference.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-repo-guard/publication_receipt.py",
    "synthesis-skills-manager/scripts/cache_guardian.py",
)
ENTRYPOINT_DEPENDENCIES["synthesis-autopilot/scripts/autopilot_gate.py"] = tuple(
    dict.fromkeys(
        (
            *ENTRYPOINT_DEPENDENCIES["synthesis-autopilot/scripts/autopilot_gate.py"],
            *_AUTOPILOT_STOP_DEPENDENCIES,
        )
    )
)

_CHECKPOINT_STOP_DEPENDENCIES = (
    "synthesis-agent-conformance/scripts/native_transcript_identity.py",
    "synthesis-context-lifecycle/scripts/context_currency.py",
    "synthesis-context-lifecycle/scripts/context_edit.py",
    "synthesis-context-lifecycle/scripts/record_succession.py",
    "synthesis-context-lifecycle/scripts/record_transaction.py",
    "synthesis-decision-packet/scripts/build_packet.py",
    "synthesis-decision-packet/scripts/record_rulings.py",
    "synthesis-onboarding/scripts/release_runtime.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/native_identity.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/plan_reference.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-repo-guard/publication_receipt.py",
)
ENTRYPOINT_DEPENDENCIES["synthesis-project-management/scripts/project_state.py"] = (
    tuple(
        dict.fromkeys(
            (
                *ENTRYPOINT_DEPENDENCIES[
                    "synthesis-project-management/scripts/project_state.py"
                ],
                *_CHECKPOINT_STOP_DEPENDENCIES,
            )
        )
    )
)

ENTRYPOINT_DEPENDENCIES["synthesis-context-lifecycle/scripts/context_edit.py"] = (
    "synthesis-project-management/scripts/project_state.py",
    *_CHECKPOINT_STOP_DEPENDENCIES,
)

# Local messaging uses the existing sandbox, process and guard owners. Bind the
# full direct/lazy Python import closure and the fixed native script asset.
# These dependencies confer source custody, never send or endpoint authority.
ENTRYPOINT_DEPENDENCIES["synthesis-local-messaging/scripts/local_messaging_cli.py"] = (
    "synthesis-agent-conformance/scripts/hermes_source.py",
    "synthesis-agent-conformance/scripts/live_receipt.py",
    "synthesis-agent-conformance/scripts/native_transcript_identity.py",
    "synthesis-agent-conformance/scripts/signed_receipt.py",
    "synthesis-agent-conformance/scripts/vendor_bundle.py",
    "synthesis-agent-conformance/scripts/vendor_hermes.py",
    "synthesis-agent-conformance/scripts/vendor_native.py",
    "synthesis-autopilot/scripts/autopilot.py",
    "synthesis-autopilot/scripts/capabilities.py",
    "synthesis-autopilot/scripts/consumer_checks.py",
    "synthesis-autopilot/scripts/controller.py",
    "synthesis-autopilot/scripts/decision_uncertainty.py",
    "synthesis-autopilot/scripts/delegation_boundary.py",
    "synthesis-autopilot/scripts/domain_quality.py",
    "synthesis-autopilot/scripts/evaluation.py",
    "synthesis-autopilot/scripts/evaluation_artifacts.py",
    "synthesis-autopilot/scripts/evidence_bridge.py",
    "synthesis-autopilot/scripts/hermes_transport.py",
    "synthesis-autopilot/scripts/hermes_worker.py",
    "synthesis-autopilot/scripts/journal_storage.py",
    "synthesis-autopilot/scripts/managed_native.py",
    "synthesis-autopilot/scripts/managed_permissions.py",
    "synthesis-autopilot/scripts/native_adapter_sdk.py",
    "synthesis-autopilot/scripts/native_archive.py",
    "synthesis-autopilot/scripts/native_archive_stream.py",
    "synthesis-autopilot/scripts/native_callback.py",
    "synthesis-autopilot/scripts/native_claude.py",
    "synthesis-autopilot/scripts/native_codex.py",
    "synthesis-autopilot/scripts/native_doctor.py",
    "synthesis-autopilot/scripts/native_codex_turn.py",
    "synthesis-autopilot/scripts/native_copilot.py",
    "synthesis-autopilot/scripts/native_cursor.py",
    "synthesis-autopilot/scripts/native_hermes.py",
    "synthesis-autopilot/scripts/native_muse.py",
    "synthesis-autopilot/scripts/native_muse_contract.py",
    "synthesis-autopilot/scripts/native_observations.py",
    "synthesis-autopilot/scripts/native_opencode.py",
    "synthesis-autopilot/scripts/native_protection.py",
    "synthesis-autopilot/scripts/native_resume.py",
    "synthesis-autopilot/scripts/native_review.py",
    "synthesis-autopilot/scripts/native_review_observer.py",
    "synthesis-autopilot/scripts/observation_bridge.py",
    "synthesis-autopilot/scripts/persistence_policy.py",
    "synthesis-autopilot/scripts/prepared_native_launch.py",
    "synthesis-autopilot/scripts/profile_evidence.py",
    "synthesis-autopilot/scripts/recovery_capsule.py",
    "synthesis-autopilot/scripts/required_citations.py",
    "synthesis-autopilot/scripts/resource_policy.py",
    "synthesis-autopilot/scripts/run_profile.py",
    "synthesis-autopilot/scripts/run_state.py",
    "synthesis-autopilot/scripts/supervision.py",
    "synthesis-autopilot/scripts/workflow.py",
    "synthesis-context-lifecycle/scripts/context_currency.py",
    "synthesis-context-lifecycle/scripts/context_edit.py",
    "synthesis-context-lifecycle/scripts/record_succession.py",
    "synthesis-context-lifecycle/scripts/record_transaction.py",
    "synthesis-decision-packet/scripts/build_packet.py",
    "synthesis-decision-packet/scripts/record_rulings.py",
    "synthesis-local-messaging/scripts/local_messaging.py",
    "synthesis-local-messaging/scripts/messages_boundary.py",
    "synthesis-local-messaging/scripts/messages_native.py",
    "synthesis-local-messaging/scripts/messages_outbound.py",
    "synthesis-local-messaging/scripts/messages_transport.js",
    "synthesis-message-guard/scripts/message_guard.py",
    "synthesis-onboarding/scripts/first_run_store.py",
    "synthesis-onboarding/scripts/release_runtime.py",
    "synthesis-onboarding/scripts/system_contract.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/execution_checkpoint.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/native_identity.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/plan_reference.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/project_state.py",
    "synthesis-project-management/scripts/run_admission.py",
    "synthesis-project-management/scripts/team_contract.py",
    "synthesis-repo-guard/publication_receipt.py",
    "synthesis-skills-manager/scripts/cache_guardian.py",
)


# Peer delivery and inbox commands authenticate their complete direct/lazy
# coordination closure before any receipt-bound dispatch.
_PEER_DELIVERY_DEPENDENCIES = (
    "synthesis-agent-conformance/scripts/native_transcript_identity.py",
    "synthesis-project-management/scripts/board_grammar.py",
    "synthesis-project-management/scripts/claim_scope.py",
    "synthesis-project-management/scripts/coordination.py",
    "synthesis-project-management/scripts/coordination_archive.py",
    "synthesis-project-management/scripts/coordination_lock.py",
    "synthesis-project-management/scripts/coordination_process.py",
    "synthesis-project-management/scripts/coordination_schema.py",
    "synthesis-project-management/scripts/fleet_doctor.py",
    "synthesis-project-management/scripts/fleet_handoff.py",
    "synthesis-project-management/scripts/fleet_identity.py",
    "synthesis-project-management/scripts/fleet_paths.py",
    "synthesis-project-management/scripts/fleet_subscriptions.py",
    "synthesis-project-management/scripts/native_git.py",
    "synthesis-project-management/scripts/native_identity.py",
    "synthesis-project-management/scripts/peer_addressing.py",
    "synthesis-project-management/scripts/pointer_lock.py",
    "synthesis-project-management/scripts/project_recipient.py",
    "synthesis-project-management/scripts/team_contract.py",
)
for _entry in (
    "synthesis-project-management/scripts/peer_send_gate.py",
    "synthesis-project-management/scripts/board_inbox.py",
):
    ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
        dict.fromkeys(
            (
                *ENTRYPOINT_DEPENDENCIES.get(_entry, ()),
                *(_dep for _dep in _PEER_DELIVERY_DEPENDENCIES if _dep != _entry),
            )
        )
    )

# The codex delivery lane is offered only after the conformance skill's client
# binary owner finds a runnable Codex CLI, so every entrypoint that reaches peer
# addressing carries that owner in its verified closure.
for _entry, _dependencies in tuple(ENTRYPOINT_DEPENDENCIES.items()):
    if "synthesis-project-management/scripts/peer_addressing.py" in {_entry, *_dependencies}:
        ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
            dict.fromkeys(
                (*_dependencies, "synthesis-agent-conformance/scripts/client_binaries.py")
            )
        )

OPTIONAL_ENTRYPOINT_DEPENDENCIES = frozenset(
    {"synthesis-bitbucket/scripts/pr_queue.py"}
)
RECEIPT_ENTRYPOINTS = sorted(
    PUBLIC_ENTRYPOINTS
    | {
        dependency
        for dependencies in ENTRYPOINT_DEPENDENCIES.values()
        for dependency in dependencies
    }
    | {
        "synthesis-onboarding/scripts/synthesis_cli.py",
    }
)


def activation_receipt_path(pointer):
    pointer = Path(pointer)
    return pointer.with_name(pointer.name + ".verification.json")


def stat_walk(root):
    """One walk of the release tree: relpath -> [size, mode, mtime_ns].

    Same traversal and link/special refusal as tree_digest, minus the
    byte hashing. A same-size-same-mode-same-mtime substitution passes
    this walk by design (the accepted A1 residual); the full digest at
    activation, in doctor, and once per session at SessionStart catches
    what the walk cannot.
    """
    root = os.fspath(Path(root))
    # os.walk retains this literal root prefix in every yielded directory.
    # Carry names through the traversal instead of reconstructing all parents
    # with Path.relative_to for every file in each hook invocation.
    prefix_size = len(root) + (not root.endswith(os.sep))
    snapshot = {}
    try:
        for directory, dirnames, filenames in os.walk(
            root, topdown=True, followlinks=False
        ):
            relative_directory = (
                ""
                if directory == root
                else directory[prefix_size:].replace(os.sep, "/")
            )
            kept = []
            for name in sorted(dirnames + filenames):
                relative = (
                    relative_directory + "/" + name if relative_directory else name
                )
                if relative == ".git":
                    continue
                meta = os.lstat(os.path.join(directory, name))
                if stat.S_ISLNK(meta.st_mode) or not (
                    stat.S_ISDIR(meta.st_mode) or stat.S_ISREG(meta.st_mode)
                ):
                    raise RuntimeContractError(
                        "release tree contains a link or special object"
                    )
                if stat.S_ISDIR(meta.st_mode):
                    kept.append(name)
                    continue
                snapshot[relative] = [
                    meta.st_size,
                    stat.S_IMODE(meta.st_mode),
                    meta.st_mtime_ns,
                ]
            dirnames[:] = kept
        return snapshot
    except OSError as exc:
        raise RuntimeContractError("release tree is unreadable: %s" % exc) from exc


def build_activation_receipt(
    *,
    release_root,
    descriptor_bytes,
    descriptor_meta,
    launcher_sha256,
    interpreter_sha256,
    generation,
    content_digest,
    projection,
):
    """Snapshot everything the per-call fast path re-checks.

    Called inside the activation lock after the tree was fully verified.
    descriptor_meta is the os.stat_result of the just-written descriptor.
    """
    root = Path(release_root)
    entrypoints = {}
    for rel in RECEIPT_ENTRYPOINTS:
        target = root / "skills" / rel
        # Modular releases omit entrypoints; record what the tree holds.
        # Per-call execution refuses a script with no activation hash.
        if target.is_file() and not target.is_symlink():
            entrypoints[rel] = file_digest(target)
    files = None
    if isinstance(projection, dict):
        records = projection.get("files")
        if not isinstance(records, dict) or not records:
            raise RuntimeContractError(
                "activation receipt needs a projection file inventory"
            )
        files = {rel: {"mode": rec["mode"]} for rel, rec in records.items()}
    return {
        "schema_version": VERIFICATION_RECEIPT_SCHEMA,
        "mode": VERIFICATION_MODE_RECEIPT,
        "generation": generation,
        "content_digest": content_digest,
        "descriptor_sha256": hashlib.sha256(descriptor_bytes).hexdigest(),
        "descriptor_inode": descriptor_meta.st_ino,
        "descriptor_mtime_ns": descriptor_meta.st_mtime_ns,
        "launcher_sha256": launcher_sha256,
        "interpreter_sha256": interpreter_sha256,
        "entrypoints": entrypoints,
        "tree_stat": stat_walk(root),
        "projection_files": files,
    }


def _load_activation_receipt(pointer):
    try:
        raw = activation_receipt_path(pointer).read_bytes()
    except OSError:
        return None
    try:
        receipt = json.loads(raw)
    except ValueError:
        return None
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema_version") != VERIFICATION_RECEIPT_SCHEMA
    ):
        return None
    return receipt


def verify_fast(pointer, active):
    """Light per-call verification. Returns the mode, or None for legacy full.

    A swapped descriptor, a swapped launcher, a stat-drifted tree, or a
    projection membership change refuses. A missing or unreadable receipt
    returns None so installs activated before S19 keep the full digest.
    """
    receipt = _load_activation_receipt(pointer)
    if receipt is None:
        return None
    pointer = Path(pointer)
    try:
        meta = pointer.lstat()
        blob = pointer.read_bytes()
    except OSError as exc:
        raise RuntimeContractError("active release descriptor is unreadable: %s" % exc)
    if (
        receipt.get("descriptor_inode") != meta.st_ino
        or receipt.get("descriptor_mtime_ns") != meta.st_mtime_ns
    ):
        raise RuntimeContractError("active descriptor replaced since activation")
    if hashlib.sha256(blob).hexdigest() != receipt.get("descriptor_sha256"):
        raise RuntimeContractError("active descriptor bytes drifted")
    if receipt.get("generation") != active.get("generation", active.get("version")):
        raise RuntimeContractError("activation receipt is for another generation")
    root = Path(active["release_root"])
    snapshot = stat_walk(root)
    if snapshot != receipt.get("tree_stat"):
        raise RuntimeContractError(
            "release tree stat drifted since activation: %s"
            % _first_stat_diff(snapshot, receipt.get("tree_stat") or {})
        )
    if receipt.get("projection_files") is not None:
        want = receipt["projection_files"]
        if set(snapshot) != set(want):
            raise RuntimeContractError("projection file membership drifted")
        for rel, fields in want.items():
            # Inventory modes are exec-bit-normalized (755/644), like the
            # tree digest; the snapshot keeps exact modes for the drift
            # comparison above.
            observed = 0o755 if snapshot[rel][1] & 0o100 else 0o644
            if observed != fields["mode"]:
                raise RuntimeContractError("projection file mode drifted: %s" % rel)
    launcher_path = (active.get("launcher") or {}).get("path")
    if launcher_path and Path(launcher_path).is_file():
        if file_digest(launcher_path) != receipt.get("launcher_sha256"):
            raise RuntimeContractError("launcher bytes drifted since activation")
    return VERIFICATION_MODE_RECEIPT


def _first_stat_diff(observed, recorded):
    for rel in sorted(set(observed) | set(recorded)):
        if observed.get(rel) != recorded.get(rel):
            return rel
    return "<unknown>"


def verify_entrypoint(active, receipt_mode, script):
    """Per-call entrypoint check for the public execution route.

    Under the receipt the entrypoint bytes hash against the activation
    snapshot. Under the legacy full digest the tree was just hashed, so
    there is nothing left to check.
    """
    if receipt_mode != VERIFICATION_MODE_RECEIPT:
        return
    pointer = active.get("_verification_pointer")
    if not pointer:
        raise RuntimeContractError("verified release lost its descriptor pointer")
    receipt = _load_activation_receipt(pointer)
    if receipt is None:
        raise RuntimeContractError("activation receipt vanished mid-call")
    want = (receipt.get("entrypoints") or {}).get(script)
    if want is None:
        raise RuntimeContractError("entrypoint %s has no activation hash" % script)
    target = Path(active["release_root"]) / "skills" / script
    if file_digest(target) != want:
        raise RuntimeContractError(
            "entrypoint bytes drifted since activation: %s" % script
        )


def full_digest_report(root):
    """Full tree digest for doctor and the once-per-session SessionStart line.

    Reports, never writes. Returns tree_digest, file count, elapsed ms.
    """
    started = time.monotonic()
    digest = tree_digest(root)
    snapshot = stat_walk(root)
    return {
        "tree_digest": digest,
        "files": len(snapshot),
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
    }


def verified_release(pointer=None, *, require_current_interpreter=True):
    if os.environ.get("SYNTHESIS_PUBLIC_SKILLS_SOURCE"):
        raise RuntimeContractError(
            "canonical public source override is forbidden for installed execution"
        )
    pointer = Path(pointer) if pointer is not None else descriptor_path()
    lock = pointer.with_name(pointer.name + ".lock")
    pending = pointer.with_name(pointer.name + ".activation-pending.json")
    try:
        if lock.is_symlink() or not lock.is_file():
            raise RuntimeContractError("setup activation lock is missing or unsafe")
        with lock.open("rb") as handle:
            # Activation is an unavailable runtime, not permission to wait
            # beyond the host hook deadline and restart a failed Stop forever.
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            if pending.exists() or pending.is_symlink():
                raise RuntimeContractError(
                    "unfinished setup activation requires recovery"
                )
            active = _verified_release_unlocked(
                pointer, require_current_interpreter=require_current_interpreter
            )
            # Private in-process consumers import public modules after this
            # boundary. Activate only the root that has passed all verification.
            enable_source_imports(active["release_root"])
            return active
    except OSError as exc:
        raise RuntimeContractError(
            "setup activation cannot be read safely: %s" % exc
        ) from exc


def _verified_release_unlocked(pointer, *, require_current_interpreter=True):
    try:
        if pointer.is_symlink() or not pointer.is_file():
            raise RuntimeContractError(
                "active release descriptor must be a regular file established by setup"
            )
        active = json.loads(pointer.read_text())
        if (
            not isinstance(active, dict)
            or type(active.get("schema_version")) is not int
            or active.get("schema_version") != 1
        ):
            raise RuntimeContractError("active release descriptor schema is invalid")
        version = active.get("version")
        channel = active.get("channel")
        if not isinstance(version, str) or not re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+", version
        ):
            raise RuntimeContractError("active release version is invalid")
        refs = {"stable": "stable", "edge": "main", "pin": "v" + version}
        if channel not in refs or active.get("ref") != refs[channel]:
            raise RuntimeContractError("active release channel/ref binding is invalid")
        if any(
            not re.fullmatch(r"[0-9a-f]{40}", str(active.get(field, "")))
            for field in ("commit", "tree")
        ):
            raise RuntimeContractError("active release Git provenance is invalid")
        source = urlsplit(str(active.get("source_url", "")))
        if (
            source.scheme != "https"
            or not source.hostname
            or source.username
            or source.password
        ):
            raise RuntimeContractError(
                "active release source must be credential-free HTTPS"
            )
        resolved = datetime.fromisoformat(
            str(active.get("resolved_at", "")).replace("Z", "+00:00")
        )
        if resolved.tzinfo is None:
            raise RuntimeContractError(
                "active release resolution time is not timezone bound"
            )
        root_value = active.get("release_root")
        if not isinstance(root_value, str) or not Path(root_value).is_absolute():
            raise RuntimeContractError("active release root must be absolute")
        root = Path(root_value)
        if (
            root.is_symlink()
            or not root.is_dir()
            or root.resolve() != root
            or os.path.lexists(root / ".git")
        ):
            raise RuntimeContractError(
                "active release root must be an immutable materialized generation"
            )
        if (
            active.get("digest_algorithm") != "sha256-tree-v1"
            or active.get("tree_policy") != "regular-files-and-directories-no-links-v1"
        ):
            raise RuntimeContractError("active release digest contract is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(active.get("content_digest", ""))):
            raise RuntimeContractError("active release digest is invalid")
        for client in ("claude", "codex"):
            manifest = json.loads(
                (root / ("." + client + "-plugin") / "plugin.json").read_text()
            )
            if (
                manifest.get("version") != active.get("version")
                or manifest.get("name") != "synthesis-skills"
            ):
                raise RuntimeContractError(
                    "active release manifests disagree with the descriptor"
                )
        mode = verify_fast(pointer, active)
        if mode is None:
            if tree_digest(root) != verify_projection(root, active):
                raise RuntimeContractError("active release content digest drifted")
            mode = VERIFICATION_MODE_FULL
        active["_verification_mode"] = mode
        active["_verification_pointer"] = os.fspath(pointer)
        executable = verify_interpreter(
            active.get("interpreter"), require_current=require_current_interpreter
        )
        verified_launcher(active, executable)
        return active
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, RuntimeContractError):
            raise
        raise RuntimeContractError(
            "active release cannot be verified: %s" % exc
        ) from exc


def verify_dependencies(active, script):
    root = Path(active["release_root"])
    if active.get("_verification_mode") == VERIFICATION_MODE_FULL:
        # A caller may retain a verified descriptor before dispatch. Without
        # activation hashes the existing full-digest owner must be fresh here.
        if tree_digest(root) != verify_projection(root, active):
            raise RuntimeContractError(
                "active release content digest drifted before dispatch"
            )
    verify_entrypoint(active, active.get("_verification_mode"), script)
    for dependency in ENTRYPOINT_DEPENDENCIES.get(script, ()):
        helper = root / "skills" / dependency
        if dependency in OPTIONAL_ENTRYPOINT_DEPENDENCIES and not os.path.lexists(
            helper
        ):
            if active.get("_verification_mode") == VERIFICATION_MODE_RECEIPT:
                receipt = _load_activation_receipt(active.get("_verification_pointer"))
                if receipt is None or dependency in receipt.get("entrypoints", {}):
                    raise RuntimeContractError(
                        "optional entrypoint dependency disappeared after activation"
                    )
            continue
        if not helper.is_file() or helper.is_symlink() or helper.resolve() != helper:
            raise RuntimeContractError(
                "public entrypoint dependency is unavailable or unsafe"
            )
        verify_entrypoint(active, active.get("_verification_mode"), dependency)


def command(active, script, arguments):
    if script not in PUBLIC_ENTRYPOINTS:
        raise RuntimeContractError(
            "public entrypoint is not declared by the execution contract"
        )
    root = Path(active["release_root"])
    target = root / "skills" / script
    if (
        not target.is_file()
        or target.is_symlink()
        or target.resolve() != target
        or not target.is_relative_to(root)
    ):
        raise RuntimeContractError(
            "public entrypoint is unavailable or escapes the verified release"
        )
    verify_interpreter(active.get("interpreter"))
    verify_dependencies(active, script)
    return source_command(root, target, arguments)


def verified_launcher(active, executable):
    receipt = active.get("launcher")
    if not isinstance(receipt, dict) or receipt.get("runtime_schema") != RUNTIME_SCHEMA:
        raise RuntimeContractError("setup has not recorded the pinned launcher")
    path = receipt.get("path")
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise RuntimeContractError("recorded launcher path is invalid")
    launcher = Path(path)
    try:
        if (
            launcher.is_symlink()
            or not launcher.is_file()
            or launcher.resolve() != launcher
        ):
            raise RuntimeContractError("recorded launcher is missing or unsafe")
        content = launcher.read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != receipt.get("sha256")
            or content.splitlines()[0] != ("#!%s -BIS" % executable).encode()
        ):
            raise RuntimeContractError(
                "launcher differs from the recorded interpreter or bytes"
            )
        return launcher
    except (OSError, ValueError, IndexError) as exc:
        if isinstance(exc, RuntimeContractError):
            raise
        raise RuntimeContractError("installed launcher is invalid: %s" % exc) from exc


def runtime_health(active, *, home=None):
    """Installed-plane verification; source validation never calls this probe."""
    executable = verify_interpreter(active.get("interpreter"))
    launcher = verified_launcher(active, executable)
    try:
        home = Path(home) if home is not None else Path.home()
        label = "org.synthesisengineering.synthesis-skills-cache-guardian"
        plist = home / "Library/LaunchAgents" / (label + ".plist")
        service = home / ".config/systemd/user" / (label + ".service")
        declarations = []
        if plist.exists() or plist.is_symlink():
            if plist.is_symlink() or not plist.is_file():
                raise RuntimeContractError("guardian launchd declaration is unsafe")
            declarations.append(
                plistlib.loads(plist.read_bytes()).get("ProgramArguments")
            )
        if service.exists() or service.is_symlink():
            if service.is_symlink() or not service.is_file():
                raise RuntimeContractError("guardian systemd declaration is unsafe")
            commands = [
                line.removeprefix("ExecStart=")
                for line in service.read_text().splitlines()
                if line.startswith("ExecStart=")
            ]
            if len(commands) != 1:
                raise RuntimeContractError("guardian systemd command is ambiguous")
            declarations.append(shlex.split(commands[0]))
        for arguments in declarations:
            if (
                not isinstance(arguments, list)
                or len(arguments) < 2
                or not isinstance(arguments[0], str)
                or arguments[1] != "-B"
            ):
                raise RuntimeContractError(
                    "guardian service does not use the recorded interpreter"
                )
            try:
                declared = Path(arguments[0]).expanduser().resolve()
                expected = Path(executable).expanduser().resolve()
            except (OSError, RuntimeError):
                raise RuntimeContractError(
                    "guardian service does not use the recorded interpreter"
                )
            if declared != expected:
                raise RuntimeContractError(
                    "guardian service does not use the recorded interpreter"
                )
        return {
            "status": "verified",
            "interpreter": executable,
            "version": active["interpreter"]["version"],
            "launcher": str(launcher),
            "guardian_declarations": len(declarations),
        }
    except (OSError, ValueError, IndexError, AttributeError) as exc:
        if isinstance(exc, RuntimeContractError):
            raise
        raise RuntimeContractError(
            "installed runtime declaration is invalid: %s" % exc
        ) from exc


def execute(active, script, arguments, payload, *, timeout=60):
    if (
        not isinstance(timeout, (float, int))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise RuntimeContractError(
            "public execution timeout must be finite and positive"
        )
    try:
        return subprocess.run(
            command(active, script, arguments),
            input=payload,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeContractError(
            "public entrypoint failed to start or finish: %s" % exc
        ) from exc


def valid_stop_payload(payload):
    return (
        isinstance(payload, dict)
        and payload.get("hook_event_name") in ("Stop", "SubagentStop")
        and isinstance(payload.get("session_id"), str)
        and 0 < len(payload["session_id"].strip()) <= 256
        and not any(ord(char) < 32 for char in payload["session_id"])
        and type(payload.get("stop_hook_active")) is bool
    )


def stop_failure(payload, reason, system_message=None, *, terminal=False):
    """Bound native Stop feedback; termination never certifies failed work.

    The native re-entry bit spans all matching hooks. Error wording, timestamps
    and sibling order cannot reset this budget. Missing native identity cannot
    authorize even one corrective continuation. This is NOT a tool denial API.
    """
    # Structured diagnostics already carry their own FAIL/UNKNOWN verdict and
    # have consumers that parse their prefix. Preserve them byte-for-byte.
    output = {
        "systemMessage": system_message
        or (reason if reason.startswith("UNRESOLVED: ") else "UNRESOLVED: " + reason)
    }
    # No current owner reservation exists on this error path.
    output.update({"continue": False, "stopReason": reason})
    return output


def _policy_reservation(payload, proof, *, consume):
    # The launcher itself is pinned by the release descriptor. Resolve only
    # its sibling policy owner, never a caller-provided module/search path.
    active = verified_release()
    # Corrective Stop feedback imports the workflow owner in the launcher
    # process, after the child returns. Verify its complete closure here too.
    verify_dependencies(active, "synthesis-autopilot/scripts/autopilot_gate.py")
    path = Path(active["release_root"]) / "skills/synthesis-autopilot/scripts"
    helper = path / "workflow.py"
    if helper.is_symlink() or not helper.is_file():
        raise RuntimeContractError("Stop policy owner helper is unavailable")
    import importlib.util

    previous = list(sys.path)
    enable_source_imports(active["release_root"])
    try:
        sys.path.insert(0, str(path))
        spec = importlib.util.spec_from_file_location(
            "release_stop_policy_owner", helper
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_stop_reservation(payload, proof, consume=consume)
    finally:
        sys.path[:] = previous


def stop_result(payload, result, *, consume_policy=True):
    """Validate Stop wire output before the host can re-enter the model."""
    try:
        output = json.loads(result.stdout) if result.stdout.strip() else {}
        allowed = {
            "continue",
            "stopReason",
            "systemMessage",
            "suppressOutput",
            "decision",
            "reason",
            "_synthesis_policy",
        }
        if (
            not isinstance(output, dict)
            or set(output) - allowed
            or ("continue" in output and type(output["continue"]) is not bool)
            or (
                "suppressOutput" in output
                and type(output["suppressOutput"]) is not bool
            )
            or ("decision" in output and output["decision"] != "block")
            or (output.get("decision") == "block" and not output.get("reason"))
            or any(
                key in output and not isinstance(output[key], str)
                for key in ("stopReason", "systemMessage", "reason")
            )
        ):
            raise ValueError("invalid native Stop result")
    except (ValueError, UnicodeError):
        return stop_failure(
            payload,
            "Stop hook returned invalid output; protection remains unverified.",
            terminal=True,
        )
    if output.get("continue") is False:
        output.pop("_synthesis_policy", None)
        return output
    proof = output.pop("_synthesis_policy", None)
    if (
        proof is not None
        and not result.returncode
        and output.get("decision") == "block"
    ):
        try:
            if not valid_stop_payload(payload) or not _policy_reservation(
                payload, proof, consume=consume_policy
            ):
                raise ValueError("Stop reservation was not verified")
        except Exception:
            return stop_failure(
                payload,
                "Stop correction reservation is unavailable, stale or consumed.",
                terminal=True,
            )
        if not consume_policy:
            output["_synthesis_policy"] = proof
        return output
    if result.returncode or output.get("decision") == "block":
        reason = (
            output.get("reason")
            or result.stderr.decode("utf-8", errors="replace").strip()
            or "Stop hook failed without a diagnostic."
        )
        return stop_failure(
            payload,
            reason,
            output.get("systemMessage"),
            terminal=result.returncode not in {0, 2},
        )
    return output


def read_payload(wait_seconds):
    stream = sys.stdin.buffer
    try:
        descriptor = stream.fileno()
        if os.isatty(descriptor):
            return b""
        os.fstat(descriptor)
    except (AttributeError, ValueError, OSError):
        return b""
    chunks = []
    size = 0
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            ready, _, _ = select.select(
                [descriptor], [], [], max(0, deadline - time.monotonic())
            )
            chunk = os.read(descriptor, 65536) if ready else b""
        except (OSError, ValueError):
            break
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > 8 * 1024 * 1024:
            raise RuntimeContractError("public hook input exceeds the 8 MiB limit")
    return b"".join(chunks)


@contextmanager
def _execution_deadline(seconds, message):
    """Borrow SIGALRM only for bounded work, never for terminal response I/O.

    Block delivery while transferring ownership. A queued alarm from this scope
    must not run through the restored caller handler. A caller's already-pending
    alarm is not ours to consume; refuse the loan and preserve its delivery.
    """
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)
    started = time.monotonic()
    owned = False
    armed = False
    pending = False
    expired_outcome = False

    def expired(_signum, _frame):
        nonlocal expired_outcome
        expired_outcome = True
        if armed:
            raise ExecutionDeadline(message)

    try:
        if signal.SIGALRM in signal.sigpending():
            raise RuntimeContractError("caller alarm is pending; execution cannot borrow its timer")
        signal.signal(signal.SIGALRM, expired)
        owned = True
        signal.setitimer(signal.ITIMER_REAL, seconds)
        armed = True
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask - {signal.SIGALRM})
        yield
    finally:
        # Preserve cancellation or any other exception already in flight.
        unwinding = sys.exc_info()[0] is not None
        # Mark the handler inactive before any cancellation call can be
        # interrupted. Block and drain a queued owned signal before restoring
        # the caller's handler, interval and elapsed-time-adjusted deadline.
        armed = False
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
        try:
            if owned:
                signal.setitimer(signal.ITIMER_REAL, 0)
                pending = signal.SIGALRM in signal.sigpending()
                if pending:
                    signal.sigwait({signal.SIGALRM})
            signal.signal(signal.SIGALRM, previous_handler)
            if previous_timer[0] > 0:
                signal.setitimer(
                    signal.ITIMER_REAL,
                    max(0.001, previous_timer[0] - (time.monotonic() - started)),
                    previous_timer[1],
                )
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        # Expiration is an outcome, even if bounded work caught its signal.
        # Never replace an unrelated exception while draining our own alarm.
        if not unwinding and (expired_outcome or pending or time.monotonic() - started >= seconds):
            raise ExecutionDeadline(message)


def _invalid_arguments_result(argv):
    """Identify native Stop after a parse failure without running any child."""
    declared_stop = False
    budget = 2.0
    index = 0
    # Only launcher options can declare the event. A child's flags after its
    # script or `--` cannot turn an unrelated parser failure into Stop success.
    while index < len(argv):
        token = argv[index]
        if token == "--" or not token.startswith("--"):
            break
        name, equals, value = token.partition("=")
        if name not in {
            "--hook-event",
            "--timeout-seconds",
            "--stdin-wait-seconds",
            "--success-exit-code",
        }:
            break
        if not equals:
            index += 1
            value = argv[index] if index < len(argv) else None
        if name == "--hook-event" and value in ("Stop", "SubagentStop"):
            declared_stop = True
        if name in ("--timeout-seconds", "--stdin-wait-seconds"):
            try:
                seconds = float(value)
                if math.isfinite(seconds) and seconds > 0:
                    budget = min(budget, seconds)
            except (TypeError, ValueError):
                pass
        index += 1

    payload = None
    try:
        with _execution_deadline(
            budget, "invalid launcher arguments exhausted the input deadline"
        ):
            payload = json.loads(read_payload(budget))
    except (RuntimeContractError, ExecutionDeadline, ValueError, UnicodeError):
        pass

    native_event = payload.get("hook_event_name") if isinstance(payload, dict) else None
    if isinstance(native_event, str) and native_event in NON_STOP_NATIVE_EVENTS:
        # A positively identified PreToolUse (or other event) must fail closed
        # with its nonzero contract even when the command was mislabeled Stop.
        declared_stop = False
    elif native_event in ("Stop", "SubagentStop"):
        declared_stop = True
    if declared_stop:
        print(
            json.dumps(
                stop_failure(
                    payload,
                    "Synthesis launcher arguments are invalid; protection remains unverified.",
                    terminal=True,
                )
            )
        )
        return 0
    return 2


def exec_public_main(argv, pointer):
    parser = argparse.ArgumentParser(
        prog="synthesis exec-public",
        description="Execute a declared public script from the verified active release.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--stdin-wait-seconds", type=float, default=2)
    parser.add_argument(
        "--success-exit-code", action="append", type=int, choices=[1], default=[]
    )
    parser.add_argument("--hook-event", choices=["Stop", "SubagentStop"])
    parser.add_argument("script", choices=sorted(PUBLIC_ENTRYPOINTS))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    try:
        args = parser.parse_args(argv)
        if not math.isfinite(args.stdin_wait_seconds) or args.stdin_wait_seconds < 0:
            parser.error("stdin wait must be finite and nonnegative")
        if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
            parser.error("public execution timeout must be finite and positive")
    except SystemExit as exc:
        if exc.code == 0:  # Help has already printed and must never read stdin.
            return 0
        return _invalid_arguments_result(argv)
    forwarded = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    started = time.monotonic()
    payload = None
    stop_event = bool(args.hook_event)
    result = None
    response = None
    reason = None
    try:
        with _execution_deadline(
            args.timeout_seconds, "public execution exceeded its total deadline"
        ):
            raw_payload = read_payload(min(args.stdin_wait_seconds, args.timeout_seconds))
            try:
                payload = json.loads(raw_payload)
            except (ValueError, UnicodeError):
                payload = None
            native_event = (
                payload.get("hook_event_name") if isinstance(payload, dict) else None
            )
            if (
                args.hook_event
                and isinstance(native_event, str)
                and native_event in NON_STOP_NATIVE_EVENTS
            ):
                # A Stop envelope must never replace a native tool denial.
                stop_event = False
                raise RuntimeContractError(
                    "declared hook event conflicts with the native event"
                )
            if isinstance(payload, dict) and payload.get("hook_event_name") in (
                "Stop",
                "SubagentStop",
            ):
                stop_event = True
            if stop_event and (
                not valid_stop_payload(payload)
                or (args.hook_event and payload["hook_event_name"] != args.hook_event)
            ):
                raise RuntimeContractError(
                    "Stop hook input is invalid or lacks native identity; protection remains unverified."
                )
            active = verified_release(pointer)
            os.environ["SYNTHESIS_ACTIVE_DESCRIPTOR"] = str(pointer)
            remaining = args.timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise ExecutionDeadline(
                    "public execution exhausted its total deadline before worker dispatch"
                )
            result = execute(active, args.script, forwarded, raw_payload, timeout=remaining)
            if stop_event:
                # Includes reservation verification/consumption, which is work
                # and must remain under the same execution deadline.
                response = stop_result(payload, result)
    except (RuntimeContractError, ExecutionDeadline) as exc:
        reason = "Synthesis execution refused: %s" % exc
        if stop_event:
            response = stop_failure(payload, reason, terminal=True)

    # There is one response boundary, after the owned timer has been released.
    # Neither JSON formatting nor a later diagnostic write can trigger a second
    # Stop envelope from the execution deadline. Caller alarms retain ownership.
    if reason is not None:
        print(reason, file=sys.stderr)
    if stop_event:
        print(json.dumps(response))
    elif reason is None:
        sys.stdout.buffer.write(result.stdout)
    if reason is None:
        sys.stderr.buffer.write(result.stderr)
    if stop_event:
        return 0
    if reason is not None:
        return 2
    return 0 if result.returncode in args.success_exit_code else result.returncode


def launcher_main(pointer, argv):
    if argv[:1] == ["exec-public"]:
        return exec_public_main(argv[1:], pointer)
    try:
        active = verified_release(pointer)
        root = Path(active["release_root"])
        cli = root / "skills/synthesis-onboarding/scripts/synthesis_cli.py"
        if not cli.is_file() or cli.is_symlink() or cli.resolve() != cli:
            raise RuntimeContractError("verified release has no trusted synthesis CLI")
        verify_dependencies(active, "synthesis-onboarding/scripts/synthesis_cli.py")
        if argv[:1] == ["team"]:
            verify_dependencies(
                active, "synthesis-project-management/scripts/team_records.py"
            )
        os.environ["SYNTHESIS_ACTIVE_DESCRIPTOR"] = str(pointer)
        os.execv(sys.executable, source_command(root, cli, argv))
    except (RuntimeContractError, OSError) as exc:
        print("Synthesis execution refused: %s" % exc, file=sys.stderr)
        return 2


for _entry, _deps in list(ENTRYPOINT_DEPENDENCIES.items()):
    if (
        "synthesis-autopilot/scripts/delegation_boundary.py" in _deps
        or "synthesis-agent-conformance/scripts/vendor_native.py" in _deps
    ):
        ENTRYPOINT_DEPENDENCIES[_entry] = tuple(
            dict.fromkeys((*_deps, *_HERMES_OBSERVATION_DEPS))
        )
