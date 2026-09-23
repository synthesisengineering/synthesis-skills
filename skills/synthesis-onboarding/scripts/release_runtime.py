"""Standalone verified execution contract embedded in the managed launcher.

This module has only standard-library dependencies. Setup embeds these exact
bytes in its pinned Python launcher; private consumers import that receipt-owned
launcher rather than importing Python from an unverified release or checkout.
"""
import argparse
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
import stat
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit


RUNTIME_SCHEMA = 1
MAC_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
PUBLIC_ENTRYPOINTS = frozenset({
    "synthesis-message-guard/scripts/message_guard.py",
    "synthesis-repo-guard/checkpoint_sync.py",
    "synthesis-repo-guard/repo_sync_check.py",
    "synthesis-agent-conformance/scripts/conformance.py",
    "synthesis-agent-conformance/scripts/session_context.py",
    "synthesis-context-lifecycle/scripts/context_doctor.py",
    "synthesis-daily-rituals/scripts/ritual_state.py",
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
})


class RuntimeContractError(ValueError):
    """Execution cannot be bound to its setup receipt and immutable release."""


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_interpreter():
    if os.environ.get("SYNTHESIS_RUNTIME_POLICY") == "packaged-python-v1":
        return str(Path(sys.executable).absolute())
    return MAC_PYTHON if sys.platform == "darwin" else str(Path(sys.executable).absolute())


def validate_python_version(version, *, platform=None, policy="prescribed-python-v1"):
    platform = sys.platform if platform is None else platform
    if policy == "packaged-python-v1":
        if platform not in {"darwin", "linux"}:
            raise RuntimeContractError("package execution supports macOS and Linux")
        if not re.fullmatch(r"3\.(12|13|14)\.[0-9]+", version):
            raise RuntimeContractError("package execution requires validated Python 3.12, 3.13 or 3.14")
        return
    if policy != "prescribed-python-v1":
        raise RuntimeContractError("unknown interpreter policy")
    if platform == "darwin" and version != "3.12.3":
        raise RuntimeContractError("macOS execution requires the prescribed python.org 3.12.3 interpreter")
    if not re.fullmatch(r"3\.12\.[0-9]+", version):
        raise RuntimeContractError("execution requires the CI-validated Python 3.12 interpreter family")


def interpreter_pin(path=None):
    policy = os.environ.get("SYNTHESIS_RUNTIME_POLICY", "prescribed-python-v1")
    path = str(path or selected_interpreter())
    if not Path(path).is_absolute() or any(c.isspace() for c in path):
        raise RuntimeContractError("interpreter must have an absolute executable path without whitespace")
    try:
        resolved = Path(path).resolve(strict=True)
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise RuntimeContractError("pinned interpreter is not executable")
        if resolved == Path(sys.executable).resolve():
            if sys.version_info.releaselevel != "final":
                raise RuntimeContractError("execution requires a final Python release")
            version = ".".join(str(v) for v in sys.version_info[:3])
        else:
            result = subprocess.run([path, "-I", "-B", "-c", "import sys; print('.'.join(map(str, sys.version_info[:3]))); sys.exit(0 if sys.version_info.releaselevel == 'final' else 1)"],
                capture_output=True, text=True, check=False, timeout=10)
            if result.returncode:
                raise RuntimeContractError("prescribed interpreter could not report its version")
            version = result.stdout.strip()
        validate_python_version(version, policy=policy)
        if policy == "prescribed-python-v1" and sys.platform == "darwin" and path != MAC_PYTHON:
            raise RuntimeContractError("macOS interpreter must use the prescribed python.org 3.12.3 framework path")
        return {"schema_version": 1, "policy": policy, "executable": path, "resolved_executable": str(resolved),
                "version": version, "sha256": file_digest(resolved), "platform": sys.platform}
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeContractError("prescribed interpreter is unavailable: %s" % exc) from exc


def verify_interpreter(pin, *, require_current=True):
    """Validate setup ownership; executable dispatch always requires current identity."""
    if not isinstance(pin, dict) or pin.get("schema_version") != 1:
        raise RuntimeContractError("setup has not recorded an interpreter pin")
    path = pin.get("executable")
    if not isinstance(path, str) or not Path(path).is_absolute() or any(c.isspace() for c in path):
        raise RuntimeContractError("interpreter pin is not an absolute executable path")
    try:
        resolved = Path(path).resolve(strict=True)
        if str(resolved) != pin.get("resolved_executable") or not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise RuntimeContractError("pinned interpreter target drifted")
        if file_digest(resolved) != pin.get("sha256"):
            raise RuntimeContractError("pinned interpreter bytes drifted")
        current = resolved == Path(sys.executable).resolve()
        if require_current and not current:
            raise RuntimeContractError("running interpreter differs from the setup pin")
        version = pin.get("version")
        if (not isinstance(version, str) or pin.get("platform") != sys.platform
                or (current and version != ".".join(str(v) for v in sys.version_info[:3]))):
            raise RuntimeContractError("running interpreter version or platform differs from the setup pin")
        policy = pin.get("policy", "prescribed-python-v1")
        validate_python_version(version, policy=policy)
        if policy == "prescribed-python-v1" and sys.platform == "darwin" and path != MAC_PYTHON:
            raise RuntimeContractError("macOS execution requires the prescribed python.org 3.12.3 framework path")
        return path
    except OSError as exc:
        raise RuntimeContractError("pinned interpreter is unavailable: %s" % exc) from exc


def tree_digest(root):
    root = Path(root)
    entries = []
    try:
        for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(directory)
            kept = []
            for name in sorted(dirnames + filenames):
                path = current / name
                relative = path.relative_to(root).as_posix()
                if relative == ".git":
                    continue
                meta = path.lstat()
                if stat.S_ISLNK(meta.st_mode) or not (stat.S_ISDIR(meta.st_mode) or stat.S_ISREG(meta.st_mode)):
                    raise RuntimeContractError("release tree contains a link or special object")
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
                digest.update(b"F\0" + relative.encode() + b"\0" + mode + b"\0" + str(meta.st_size).encode() + b"\0" + bytes.fromhex(file_digest(path)))
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
    fields = {"schema_version", "kind", "content_digest", "source_content_digest", "selection", "files"}
    if not isinstance(projection, dict) or set(projection) != fields or type(projection["schema_version"]) is not int or projection["schema_version"] != 1 or projection["kind"] != "modular":
        raise RuntimeContractError("release projection shape is invalid")
    if projection["source_content_digest"] != descriptor["content_digest"]:
        raise RuntimeContractError("projection differs from its verified source binding")
    if not re.fullmatch(r"[0-9a-f]{64}", str(projection["content_digest"])):
        raise RuntimeContractError("projection digest is invalid")
    selected = projection["selection"]
    if not isinstance(selected, dict) or set(selected) != {"roots", "skills", "support_skills", "stage_core"} or type(selected["stage_core"]) is not bool:
        raise RuntimeContractError("projection selection is invalid")
    for key in ("roots", "skills", "support_skills"):
        values = selected[key]
        if not isinstance(values, list) or any(not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value) for value in values) or len(values) != len(set(values)):
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
            observed[path.relative_to(root).as_posix()] = {"sha256": file_digest(path), "mode": 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644}
    if observed != records:
        raise RuntimeContractError("projection file membership or bytes drifted")
    return projection["content_digest"]


VERIFICATION_RECEIPT_SCHEMA = 1
VERIFICATION_MODE_RECEIPT = "activation-receipt-v1"
VERIFICATION_MODE_FULL = "full-digest-legacy"
# Entrypoints hashed at activation and re-checked per call, as paths
# relative to skills/ (the CLI shares the entrypoint layout).
RECEIPT_ENTRYPOINTS = sorted(PUBLIC_ENTRYPOINTS | {
    "synthesis-onboarding/scripts/synthesis_cli.py",
})


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
    root = Path(root)
    snapshot = {}
    try:
        for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(directory)
            kept = []
            for name in sorted(dirnames + filenames):
                path = current / name
                relative = path.relative_to(root).as_posix()
                if relative == ".git":
                    continue
                meta = path.lstat()
                if stat.S_ISLNK(meta.st_mode) or not (stat.S_ISDIR(meta.st_mode) or stat.S_ISREG(meta.st_mode)):
                    raise RuntimeContractError("release tree contains a link or special object")
                if stat.S_ISDIR(meta.st_mode):
                    kept.append(name)
                    continue
                snapshot[relative] = [meta.st_size, stat.S_IMODE(meta.st_mode), meta.st_mtime_ns]
            dirnames[:] = kept
        return snapshot
    except OSError as exc:
        raise RuntimeContractError("release tree is unreadable: %s" % exc) from exc


def build_activation_receipt(*, release_root, descriptor_bytes, descriptor_meta,
                             launcher_sha256, interpreter_sha256, generation,
                             content_digest, projection):
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
            raise RuntimeContractError("activation receipt needs a projection file inventory")
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
    if not isinstance(receipt, dict) or receipt.get("schema_version") != VERIFICATION_RECEIPT_SCHEMA:
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
    if receipt.get("descriptor_inode") != meta.st_ino or receipt.get("descriptor_mtime_ns") != meta.st_mtime_ns:
        raise RuntimeContractError("active descriptor replaced since activation")
    if hashlib.sha256(blob).hexdigest() != receipt.get("descriptor_sha256"):
        raise RuntimeContractError("active descriptor bytes drifted")
    if receipt.get("generation") != active.get("generation", active.get("version")):
        raise RuntimeContractError("activation receipt is for another generation")
    root = Path(active["release_root"])
    snapshot = stat_walk(root)
    if snapshot != receipt.get("tree_stat"):
        raise RuntimeContractError("release tree stat drifted since activation: %s" % _first_stat_diff(snapshot, receipt.get("tree_stat") or {}))
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
        raise RuntimeContractError("entrypoint bytes drifted since activation: %s" % script)


def full_digest_report(root):
    """Full tree digest for doctor and the once-per-session SessionStart line.

    Reports, never writes. Returns tree_digest, file count, elapsed ms.
    """
    started = time.monotonic()
    digest = tree_digest(root)
    snapshot = stat_walk(root)
    return {"tree_digest": digest, "files": len(snapshot),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 1)}


def verified_release(pointer=None, *, require_current_interpreter=True):
    if os.environ.get("SYNTHESIS_PUBLIC_SKILLS_SOURCE"):
        raise RuntimeContractError("canonical public source override is forbidden for installed execution")
    pointer = Path(pointer) if pointer is not None else descriptor_path()
    lock = pointer.with_name(pointer.name + ".lock")
    pending = pointer.with_name(pointer.name + ".activation-pending.json")
    try:
        if lock.is_symlink() or not lock.is_file():
            raise RuntimeContractError("setup activation lock is missing or unsafe")
        with lock.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            if pending.exists() or pending.is_symlink():
                raise RuntimeContractError("unfinished setup activation requires recovery")
            return _verified_release_unlocked(pointer, require_current_interpreter=require_current_interpreter)
    except OSError as exc:
        raise RuntimeContractError("setup activation cannot be read safely: %s" % exc) from exc


def _verified_release_unlocked(pointer, *, require_current_interpreter=True):
    try:
        if pointer.is_symlink() or not pointer.is_file():
            raise RuntimeContractError("active release descriptor must be a regular file established by setup")
        active = json.loads(pointer.read_text())
        if not isinstance(active, dict) or type(active.get("schema_version")) is not int or active.get("schema_version") != 1:
            raise RuntimeContractError("active release descriptor schema is invalid")
        version = active.get("version")
        channel = active.get("channel")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise RuntimeContractError("active release version is invalid")
        refs = {"stable": "stable", "edge": "main", "pin": "v" + version}
        if channel not in refs or active.get("ref") != refs[channel]:
            raise RuntimeContractError("active release channel/ref binding is invalid")
        if any(not re.fullmatch(r"[0-9a-f]{40}", str(active.get(field, ""))) for field in ("commit", "tree")):
            raise RuntimeContractError("active release Git provenance is invalid")
        source = urlsplit(str(active.get("source_url", "")))
        if source.scheme != "https" or not source.hostname or source.username or source.password:
            raise RuntimeContractError("active release source must be credential-free HTTPS")
        resolved = datetime.fromisoformat(str(active.get("resolved_at", "")).replace("Z", "+00:00"))
        if resolved.tzinfo is None:
            raise RuntimeContractError("active release resolution time is not timezone bound")
        root_value = active.get("release_root")
        if not isinstance(root_value, str) or not Path(root_value).is_absolute():
            raise RuntimeContractError("active release root must be absolute")
        root = Path(root_value)
        if root.is_symlink() or not root.is_dir() or root.resolve() != root or os.path.lexists(root / ".git"):
            raise RuntimeContractError("active release root must be an immutable materialized generation")
        if active.get("digest_algorithm") != "sha256-tree-v1" or active.get("tree_policy") != "regular-files-and-directories-no-links-v1":
            raise RuntimeContractError("active release digest contract is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", str(active.get("content_digest", ""))):
            raise RuntimeContractError("active release digest is invalid")
        for client in ("claude", "codex"):
            manifest = json.loads((root / ("." + client + "-plugin") / "plugin.json").read_text())
            if manifest.get("version") != active.get("version") or manifest.get("name") != "synthesis-skills":
                raise RuntimeContractError("active release manifests disagree with the descriptor")
        mode = verify_fast(pointer, active)
        if mode is None:
            if tree_digest(root) != verify_projection(root, active):
                raise RuntimeContractError("active release content digest drifted")
            mode = VERIFICATION_MODE_FULL
        active["_verification_mode"] = mode
        active["_verification_pointer"] = os.fspath(pointer)
        executable = verify_interpreter(active.get("interpreter"), require_current=require_current_interpreter)
        verified_launcher(active, executable)
        return active
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, RuntimeContractError):
            raise
        raise RuntimeContractError("active release cannot be verified: %s" % exc) from exc


def command(active, script, arguments):
    if script not in PUBLIC_ENTRYPOINTS:
        raise RuntimeContractError("public entrypoint is not declared by the execution contract")
    root = Path(active["release_root"])
    target = root / "skills" / script
    if not target.is_file() or target.is_symlink() or target.resolve() != target or not target.is_relative_to(root):
        raise RuntimeContractError("public entrypoint is unavailable or escapes the verified release")
    verify_interpreter(active.get("interpreter"))
    verify_entrypoint(active, active.get("_verification_mode"), script)
    return [sys.executable, "-B", str(target), *arguments]


def verified_launcher(active, executable):
    receipt = active.get("launcher")
    if not isinstance(receipt, dict) or receipt.get("runtime_schema") != RUNTIME_SCHEMA:
        raise RuntimeContractError("setup has not recorded the pinned launcher")
    path = receipt.get("path")
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise RuntimeContractError("recorded launcher path is invalid")
    launcher = Path(path)
    try:
        if launcher.is_symlink() or not launcher.is_file() or launcher.resolve() != launcher:
            raise RuntimeContractError("recorded launcher is missing or unsafe")
        content = launcher.read_bytes()
        if (hashlib.sha256(content).hexdigest() != receipt.get("sha256")
                or content.splitlines()[0] != ("#!%s -B" % executable).encode()):
            raise RuntimeContractError("launcher differs from the recorded interpreter or bytes")
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
            declarations.append(plistlib.loads(plist.read_bytes()).get("ProgramArguments"))
        if service.exists() or service.is_symlink():
            if service.is_symlink() or not service.is_file():
                raise RuntimeContractError("guardian systemd declaration is unsafe")
            commands = [line.removeprefix("ExecStart=") for line in service.read_text().splitlines() if line.startswith("ExecStart=")]
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
                raise RuntimeContractError("guardian service does not use the recorded interpreter")
            try:
                declared = Path(arguments[0]).expanduser().resolve()
                expected = Path(executable).expanduser().resolve()
            except (OSError, RuntimeError):
                raise RuntimeContractError("guardian service does not use the recorded interpreter")
            if declared != expected:
                raise RuntimeContractError("guardian service does not use the recorded interpreter")
        return {"status": "verified", "interpreter": executable, "version": active["interpreter"]["version"],
                "launcher": str(launcher), "guardian_declarations": len(declarations)}
    except (OSError, ValueError, IndexError, AttributeError) as exc:
        if isinstance(exc, RuntimeContractError):
            raise
        raise RuntimeContractError("installed runtime declaration is invalid: %s" % exc) from exc


def execute(active, script, arguments, payload, *, timeout=60):
    if not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeContractError("public execution timeout must be finite and positive")
    try:
        return subprocess.run(command(active, script, arguments), input=payload, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeContractError("public entrypoint failed to start or finish: %s" % exc) from exc


def read_payload(wait_seconds):
    stream = sys.stdin.buffer
    try:
        descriptor = stream.fileno()
        if os.isatty(descriptor):
            return b""
        mode = os.fstat(descriptor).st_mode
    except (AttributeError, ValueError, OSError):
        return b""
    if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
        return stream.read()
    chunks = []
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            ready, _, _ = select.select([descriptor], [], [], max(0, deadline - time.monotonic()))
            chunk = os.read(descriptor, 65536) if ready else b""
        except (OSError, ValueError):
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def exec_public_main(argv, pointer):
    parser = argparse.ArgumentParser(prog="synthesis exec-public", description="Execute a declared public script from the verified active release.")
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--stdin-wait-seconds", type=float, default=2)
    parser.add_argument("--success-exit-code", action="append", type=int, choices=[1], default=[])
    parser.add_argument("script", choices=sorted(PUBLIC_ENTRYPOINTS))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if not math.isfinite(args.stdin_wait_seconds) or args.stdin_wait_seconds < 0:
        parser.error("stdin wait must be finite and nonnegative")
    forwarded = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    try:
        active = verified_release(pointer)
        os.environ["SYNTHESIS_ACTIVE_DESCRIPTOR"] = str(pointer)
        result = execute(active, args.script, forwarded, read_payload(args.stdin_wait_seconds), timeout=args.timeout_seconds)
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        return 0 if result.returncode in args.success_exit_code else result.returncode
    except RuntimeContractError as exc:
        print("Synthesis execution refused: %s" % exc, file=sys.stderr)
        return 2


def launcher_main(pointer, argv):
    if argv[:1] == ["exec-public"]:
        return exec_public_main(argv[1:], pointer)
    try:
        active = verified_release(pointer)
        root = Path(active["release_root"])
        cli = root / "skills/synthesis-onboarding/scripts/synthesis_cli.py"
        if not cli.is_file() or cli.is_symlink() or cli.resolve() != cli:
            raise RuntimeContractError("verified release has no trusted synthesis CLI")
        os.environ["SYNTHESIS_ACTIVE_DESCRIPTOR"] = str(pointer)
        os.execv(sys.executable, [sys.executable, "-B", str(cli), *argv])
    except (RuntimeContractError, OSError) as exc:
        print("Synthesis execution refused: %s" % exc, file=sys.stderr)
        return 2
