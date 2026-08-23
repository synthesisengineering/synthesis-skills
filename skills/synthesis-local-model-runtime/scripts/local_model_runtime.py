#!/usr/bin/env python3
"""Privacy-safe local model profiler, planner, installer, and inventory."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = SKILL_ROOT / "assets" / "model_catalog.json"
DEFAULT_STATE_DIR = Path.home() / ".synthesis" / "local-models"
OLLAMA_API = "http://127.0.0.1:11434"
GIB = 1024**3
CATALOG_SCHEMA = 1
POLICY_SCHEMA = 1
INVENTORY_SCHEMA = 1

FORBIDDEN_PROFILE_TERMS = {
    "serial",
    "uuid",
    "udid",
    "hostname",
    "host_name",
    "user_name",
    "account",
    "provisioning",
    "ip_address",
    "mac_address",
}

DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": 1,
    "required_families": [],
    "excluded_organizations": [],
    "excluded_base_families": [],
    "excluded_artifacts": [],
    "artifact_overrides": {},
    "allow_minimum_memory_fit": False,
    "memory_headroom_gib": 16,
    "minimum_free_disk_after_install_gib": 40,
    "planning_context_tokens": 32768,
    "protected_roots": [],
}


class LocalModelError(RuntimeError):
    """Expected user-facing validation or runtime failure."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LocalModelError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LocalModelError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LocalModelError(f"Expected a JSON object in {path}")
    return value


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    reject_symlink_components(path.parent, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(path.parent, path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_text_write(path: Path, value: str) -> None:
    reject_symlink_components(path.parent, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(path.parent, path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def command_output(arguments: list[str], timeout: int = 8) -> str | None:
    try:
        result = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return combined.strip() or None


def version_tuple(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)", value)
    if not match:
        return None
    return tuple(int(item) for item in match.groups())


def command_version(executable: str | None, *arguments: str) -> str | None:
    if not executable:
        return None
    output = command_output([executable, *arguments])
    parsed = version_tuple(output)
    return ".".join(str(part) for part in parsed) if parsed else None


def display_path(path: Path) -> str:
    resolved = path.expanduser().resolve(strict=False)
    home = Path.home().resolve(strict=False)
    try:
        relative = resolved.relative_to(home)
    except ValueError:
        return str(resolved)
    return "~" if relative == Path(".") else f"~/{relative.as_posix()}"


def nearest_existing(path: Path) -> Path:
    candidate = path.expanduser().resolve(strict=False)
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.exists():
        raise LocalModelError(f"No existing ancestor for storage path: {path}")
    return candidate


def path_within(path: Path, root: Path) -> bool:
    resolved_path = path.expanduser().resolve(strict=False)
    resolved_root = root.expanduser().resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def reject_symlink_components(*paths: Path) -> None:
    trusted_macos_aliases = {
        Path("/etc"): Path("/private/etc"),
        Path("/tmp"): Path("/private/tmp"),
        Path("/var"): Path("/private/var"),
    }
    for value in paths:
        path = Path(os.path.abspath(os.path.expanduser(str(value))))
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current = current / part
            if os.path.lexists(current) and current.is_symlink():
                expected = trusted_macos_aliases.get(current)
                if (
                    platform.system() == "Darwin"
                    and expected is not None
                    and current.resolve(strict=True) == expected
                    and current.lstat().st_uid == 0
                ):
                    continue
                raise LocalModelError(f"State path contains a symlink component: {current}")


def discover_git_root(start: Path) -> Path | None:
    output = command_output(["git", "-C", str(start), "rev-parse", "--show-toplevel"])
    if not output:
        return None
    first_line = output.splitlines()[0].strip()
    candidate = Path(first_line)
    return candidate if candidate.is_absolute() else None


def protected_roots(explicit: list[str] | None, cwd: Path | None = None) -> list[Path]:
    home = Path.home()
    values = [
        home / "Library" / "Mobile Documents",
        home / "Library" / "CloudStorage",
        home / "workspaces",
    ]
    values.extend(Path(item).expanduser() for item in (explicit or []))
    repo_root = discover_git_root(cwd or Path.cwd())
    if repo_root:
        values.append(repo_root)
    unique: list[Path] = []
    seen: set[str] = set()
    for value in values:
        resolved = value.resolve(strict=False)
        marker = str(resolved)
        if marker not in seen:
            seen.add(marker)
            unique.append(resolved)
    return unique


def validate_model_store(store: Path, explicit_roots: list[str] | None = None) -> list[str]:
    resolved = store.expanduser().resolve(strict=False)
    violations = [
        display_path(root)
        for root in protected_roots(explicit_roots)
        if path_within(resolved, root)
    ]
    if violations:
        raise LocalModelError(
            f"Model store {display_path(resolved)} is inside protected root(s): "
            + ", ".join(violations)
        )
    return [display_path(root) for root in protected_roots(explicit_roots)]


def macos_homebrew_ollama_store() -> Path | None:
    plist_path = Path.home() / "Library" / "LaunchAgents" / "homebrew.mxcl.ollama.plist"
    try:
        payload = plistlib.loads(plist_path.read_bytes())
    except (FileNotFoundError, plistlib.InvalidFileException, OSError):
        return None
    environment = payload.get("EnvironmentVariables", {})
    if not isinstance(environment, dict):
        return None
    value = environment.get("OLLAMA_MODELS")
    return Path(value).expanduser() if isinstance(value, str) and value else None


def resolve_ollama_store(explicit: str | None = None) -> tuple[Path, str]:
    if explicit:
        return Path(explicit).expanduser(), "explicit"
    environment = os.environ.get("OLLAMA_MODELS")
    if environment:
        return Path(environment).expanduser(), "environment"
    if platform.system() == "Darwin":
        service_store = macos_homebrew_ollama_store()
        if service_store:
            return service_store, "homebrew-service"
    return Path.home() / ".ollama" / "models", "standard-default"


def memory_bytes() -> int | None:
    system = platform.system()
    if system == "Darwin":
        output = command_output(["sysctl", "-n", "hw.memsize"])
        if output and output.isdigit():
            return int(output)
        profiler_output = command_output(
            ["system_profiler", "SPHardwareDataType", "-json"], 15
        )
        if profiler_output:
            try:
                mapping = _first_mapping_with_key(
                    json.loads(profiler_output), "physical_memory"
                )
                value = mapping.get("physical_memory") if mapping else None
                match = re.fullmatch(
                    r"\s*(\d+(?:\.\d+)?)\s*(GB|TB)\s*", str(value), re.IGNORECASE
                )
                if match:
                    magnitude = float(match.group(1))
                    multiplier = GIB if match.group(2).upper() == "GB" else 1024 * GIB
                    return int(magnitude * multiplier)
            except json.JSONDecodeError:
                pass
        return None
    if system == "Windows":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        state = MemoryStatus()
        state.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return int(state.total_physical)
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def sysctl_integer(name: str) -> int | None:
    output = command_output(["sysctl", "-n", name])
    return int(output) if output and output.isdigit() else None


def _first_mapping_with_key(value: Any, key: str) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if key in value:
            return value
        for child in value.values():
            found = _first_mapping_with_key(child, key)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _first_mapping_with_key(child, key)
            if found:
                return found
    return None


def macos_hardware() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    chip = platform.processor() or "unknown"
    output = command_output(["system_profiler", "SPHardwareDataType", "-json"], 15)
    if output:
        try:
            mapping = _first_mapping_with_key(json.loads(output), "chip_type")
            if mapping and isinstance(mapping.get("chip_type"), str):
                chip = mapping["chip_type"]
        except json.JSONDecodeError:
            pass

    cpu = {
        "brand": chip,
        "physical_cores": sysctl_integer("hw.physicalcpu") or os.cpu_count(),
        "logical_cores": sysctl_integer("hw.logicalcpu") or os.cpu_count(),
        "performance_cores": sysctl_integer("hw.perflevel0.physicalcpu"),
        "efficiency_cores": sysctl_integer("hw.perflevel1.physicalcpu"),
    }

    gpu: dict[str, Any] = {"name": chip, "cores": None, "status": "unknown"}
    display_output = command_output(["system_profiler", "SPDisplaysDataType", "-json"], 15)
    if display_output:
        try:
            payload = json.loads(display_output)
            mapping = _first_mapping_with_key(payload, "sppci_model")
            if mapping:
                core_value = mapping.get("sppci_cores")
                core_match = re.search(r"\d+", str(core_value)) if core_value else None
                gpu = {
                    "name": str(mapping.get("sppci_model") or chip),
                    "cores": int(core_match.group()) if core_match else None,
                    "status": "present",
                }
        except json.JSONDecodeError:
            pass

    npu = {
        "name": "Apple Neural Engine" if "Apple" in chip else "unknown",
        "cores": None,
        "status": "present-core-count-not-exposed" if "Apple" in chip else "unknown",
    }
    return cpu, gpu, npu


def generic_hardware() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    brand = platform.processor() or platform.machine() or "unknown"
    cpu = {
        "brand": brand,
        "physical_cores": None,
        "logical_cores": os.cpu_count(),
        "performance_cores": None,
        "efficiency_cores": None,
    }
    return cpu, {"name": "unknown", "cores": None, "status": "unknown"}, {
        "name": "unknown",
        "cores": None,
        "status": "unknown",
    }


def api_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 5) -> Any:
    if not path.startswith("/"):
        raise LocalModelError("Loopback API path must begin with '/'")
    data = None
    headers: dict[str, str] = {}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    request = urllib.request.Request(
        f"{OLLAMA_API}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LocalModelError(f"Ollama loopback API unavailable for {path}: {exc}") from exc


def runtime_profile() -> dict[str, Any]:
    ollama = shutil.which("ollama")
    llama_cli = shutil.which("llama-cli") or shutil.which("llama")
    mlx = shutil.which("mlx_lm.generate") or shutil.which("mlx_lm.server")
    ollama_version = command_version(ollama, "--version")
    api_version = None
    api_reachable = False
    try:
        response = api_json("/api/version", timeout=2)
        if isinstance(response, dict):
            parsed = version_tuple(str(response.get("version", "")))
            if parsed:
                api_version = ".".join(str(part) for part in parsed)
                api_reachable = True
    except LocalModelError:
        pass
    return {
        "ollama": {
            "available": bool(ollama),
            "version": api_version or ollama_version,
            "api_reachable": api_reachable,
        },
        "llama_cpp": {
            "available": bool(llama_cli),
            "version": command_version(llama_cli, "--version"),
            "adapter_status": "detected-only",
        },
        "mlx_lm": {
            "available": bool(mlx),
            "version": command_version(mlx, "--version"),
            "adapter_status": "detected-only",
        },
    }


def machine_profile(
    model_store: str | None = None,
    explicit_protected_roots: list[str] | None = None,
) -> dict[str, Any]:
    store, source = resolve_ollama_store(model_store)
    checked_roots = validate_model_store(store, explicit_protected_roots)
    usage = shutil.disk_usage(nearest_existing(store))
    total_memory = memory_bytes()
    if platform.system() == "Darwin":
        cpu, gpu, npu = macos_hardware()
    else:
        cpu, gpu, npu = generic_hardware()
    profile = {
        "schema_version": 1,
        "captured_at": utc_now(),
        "operating_system": {
            "name": platform.system(),
            "version": platform.mac_ver()[0] if platform.system() == "Darwin" else platform.release(),
            "architecture": platform.machine(),
        },
        "cpu": cpu,
        "accelerators": {"gpu": gpu, "npu": npu},
        "memory": {
            "total_gib": round(total_memory / GIB, 2) if total_memory else None,
            "unified": platform.system() == "Darwin" and platform.machine() == "arm64",
        },
        "storage": {
            "model_store": display_path(store),
            "model_store_source": source,
            "free_gib": round(usage.free / GIB, 2),
            "total_gib": round(usage.total / GIB, 2),
            "protected_roots_checked": checked_roots,
        },
        "runtimes": runtime_profile(),
        "privacy": {
            "unique_hardware_identifiers_collected": False,
            "hostname_collected": False,
            "account_data_collected": False,
        },
    }
    assert_profile_safe(profile)
    return profile


def assert_profile_safe(profile: dict[str, Any]) -> None:
    serialized = json.dumps(profile, sort_keys=True).lower()
    for term in FORBIDDEN_PROFILE_TERMS:
        if f'"{term}"' in serialized:
            raise LocalModelError(f"Unsafe profile field detected: {term}")
    for sensitive_pattern in (
        r"serial number",
        r"hardware uuid",
        r"provisioning udid",
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    ):
        if re.search(sensitive_pattern, serialized, re.IGNORECASE):
            raise LocalModelError("Unsafe identifier-like value detected in profile")


def validate_https_url(value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise LocalModelError(f"{label} must be a string")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise LocalModelError(f"{label} must be a credential-free HTTPS URL")


def validate_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("schema_version") != CATALOG_SCHEMA:
        raise LocalModelError(f"Unsupported catalog schema: {catalog.get('schema_version')}")
    artifacts = catalog.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise LocalModelError("Catalog must contain a non-empty artifacts list")
    required = {
        "id",
        "family",
        "organization",
        "upstream_model",
        "base_family",
        "runtime",
        "runtime_model",
        "distribution_channel",
        "artifact_publisher",
        "upstream_source_url",
        "artifact_source_url",
        "license",
        "quantization",
        "total_parameters_billion",
        "active_parameters_billion",
        "disk_gib",
        "minimum_memory_gib",
        "recommended_memory_gib",
        "planning_context_tokens",
        "minimum_runtime_version",
        "quality_rank",
        "roles",
        "expected_digest_prefix",
        "status",
    }
    seen: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise LocalModelError(f"Artifact {index} must be an object")
        missing = sorted(required - artifact.keys())
        if missing:
            raise LocalModelError(f"Artifact {index} missing fields: {', '.join(missing)}")
        artifact_id = artifact["id"]
        if not isinstance(artifact_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", artifact_id):
            raise LocalModelError(f"Invalid artifact id: {artifact_id!r}")
        if artifact_id in seen:
            raise LocalModelError(f"Duplicate artifact id: {artifact_id}")
        seen.add(artifact_id)
        if artifact["runtime"] != "ollama":
            raise LocalModelError(f"Unsupported runtime in 1.0 catalog: {artifact['runtime']}")
        runtime_model = artifact["runtime_model"]
        if not isinstance(runtime_model, str) or re.search(r"\s|://|@", runtime_model):
            raise LocalModelError(f"Unsafe runtime model id for {artifact_id}")
        validate_https_url(artifact["upstream_source_url"], f"{artifact_id}.upstream_source_url")
        validate_https_url(artifact["artifact_source_url"], f"{artifact_id}.artifact_source_url")
        for field in (
            "total_parameters_billion",
            "active_parameters_billion",
            "disk_gib",
            "minimum_memory_gib",
            "recommended_memory_gib",
            "planning_context_tokens",
            "quality_rank",
        ):
            value = artifact[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise LocalModelError(f"{artifact_id}.{field} must be positive")
        if artifact["active_parameters_billion"] > artifact["total_parameters_billion"]:
            raise LocalModelError(f"{artifact_id} has active parameters above total")
        if artifact["minimum_memory_gib"] > artifact["recommended_memory_gib"]:
            raise LocalModelError(f"{artifact_id} minimum memory exceeds recommended")
        if version_tuple(artifact["minimum_runtime_version"]) is None:
            raise LocalModelError(f"{artifact_id} has invalid minimum runtime version")
        if artifact["status"] not in {"verified", "retired"}:
            raise LocalModelError(f"{artifact_id} has invalid status")
        digest = artifact["expected_digest_prefix"]
        if digest is not None and (
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{12,64}", digest)
        ):
            raise LocalModelError(f"{artifact_id} has invalid expected digest prefix")
        if not isinstance(artifact["roles"], list) or not all(
            isinstance(role, str) and role for role in artifact["roles"]
        ):
            raise LocalModelError(f"{artifact_id}.roles must be non-empty strings")
        fallback = artifact.get("local_import_fallback")
        if fallback is not None:
            if artifact["distribution_channel"] != "huggingface-gguf":
                raise LocalModelError(
                    f"{artifact_id}.local_import_fallback is only valid for huggingface-gguf"
                )
            if not isinstance(fallback, dict):
                raise LocalModelError(f"{artifact_id}.local_import_fallback must be an object")
            validate_https_url(
                fallback.get("registry_manifest_url"),
                f"{artifact_id}.local_import_fallback.registry_manifest_url",
            )
            layers = fallback.get("gguf_layers")
            if not isinstance(layers, list) or not layers:
                raise LocalModelError(
                    f"{artifact_id}.local_import_fallback.gguf_layers must be non-empty"
                )
            media_types: list[str] = []
            layer_digests: set[str] = set()
            for layer in layers:
                if not isinstance(layer, dict):
                    raise LocalModelError(f"{artifact_id} fallback layer must be an object")
                media_type = layer.get("media_type")
                if media_type not in {
                    "application/vnd.ollama.image.model",
                    "application/vnd.ollama.image.projector",
                }:
                    raise LocalModelError(f"{artifact_id} fallback layer has unsafe media type")
                layer_digest = layer.get("digest")
                if not isinstance(layer_digest, str) or not re.fullmatch(
                    r"sha256:[0-9a-f]{64}", layer_digest
                ):
                    raise LocalModelError(f"{artifact_id} fallback layer has invalid digest")
                size_bytes = layer.get("size_bytes")
                if (
                    not isinstance(size_bytes, int)
                    or isinstance(size_bytes, bool)
                    or size_bytes <= 0
                ):
                    raise LocalModelError(f"{artifact_id} fallback layer has invalid size")
                if layer_digest in layer_digests:
                    raise LocalModelError(f"{artifact_id} fallback layer digest is duplicated")
                layer_digests.add(layer_digest)
                media_types.append(media_type)
            if media_types.count("application/vnd.ollama.image.model") != 1:
                raise LocalModelError(f"{artifact_id} fallback must contain exactly one model")
            if media_types.count("application/vnd.ollama.image.projector") > 1:
                raise LocalModelError(f"{artifact_id} fallback has multiple projectors")
    return artifacts


def load_catalog(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    catalog = load_json(path)
    return catalog, validate_catalog(catalog)


def load_policy(path: Path | None) -> dict[str, Any]:
    policy = dict(DEFAULT_POLICY)
    if path:
        supplied = load_json(path)
        unknown = sorted(set(supplied) - set(DEFAULT_POLICY))
        if unknown:
            raise LocalModelError(f"Unknown policy fields: {', '.join(unknown)}")
        policy.update(supplied)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise LocalModelError(f"Unsupported policy schema: {policy.get('schema_version')}")
    for list_field in (
        "required_families",
        "excluded_organizations",
        "excluded_base_families",
        "excluded_artifacts",
        "protected_roots",
    ):
        value = policy.get(list_field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise LocalModelError(f"Policy field {list_field} must be a string list")
    if not isinstance(policy.get("artifact_overrides"), dict):
        raise LocalModelError("Policy artifact_overrides must be an object")
    if not isinstance(policy.get("allow_minimum_memory_fit"), bool):
        raise LocalModelError("Policy allow_minimum_memory_fit must be boolean")
    for number_field in (
        "memory_headroom_gib",
        "minimum_free_disk_after_install_gib",
        "planning_context_tokens",
    ):
        value = policy.get(number_field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise LocalModelError(f"Policy field {number_field} must be non-negative")
    return policy


def runtime_satisfies(current: str | None, minimum: str) -> bool:
    current_tuple = version_tuple(current)
    minimum_tuple = version_tuple(minimum)
    return bool(current_tuple and minimum_tuple and current_tuple >= minimum_tuple)


def artifact_fit(artifact: dict[str, Any], profile: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    total_memory = profile.get("memory", {}).get("total_gib")
    if not isinstance(total_memory, (int, float)):
        return {"fit": "blocked", "blockers": ["system memory is unknown"]}
    effective = max(0.0, float(total_memory) - float(policy["memory_headroom_gib"]))
    blockers: list[str] = []
    if effective >= float(artifact["recommended_memory_gib"]):
        fit = "recommended"
    elif effective >= float(artifact["minimum_memory_gib"]) and policy["allow_minimum_memory_fit"]:
        fit = "constrained"
    else:
        fit = "blocked"
        blockers.append(
            f"needs {artifact['recommended_memory_gib']} GiB recommended "
            f"({artifact['minimum_memory_gib']} GiB minimum) after headroom; {effective:.2f} GiB available"
        )
    runtime_blockers: list[str] = []
    runtime = profile.get("runtimes", {}).get(artifact["runtime"], {})
    if not runtime.get("available"):
        runtime_blockers.append(f"runtime {artifact['runtime']} is not installed")
    elif not runtime_satisfies(runtime.get("version"), artifact["minimum_runtime_version"]):
        runtime_blockers.append(
            f"runtime {artifact['runtime']} {runtime.get('version') or 'unknown'} is below "
            f"{artifact['minimum_runtime_version']}"
        )
    return {
        "fit": fit,
        "blockers": blockers + runtime_blockers,
        "runtime_ready": not runtime_blockers,
        "effective_memory_gib": round(effective, 2),
    }


def recommend(
    artifacts: list[dict[str, Any]], profile: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    excluded_orgs = {item.casefold() for item in policy["excluded_organizations"]}
    excluded_bases = {item.casefold() for item in policy["excluded_base_families"]}
    excluded_artifacts = set(policy["excluded_artifacts"])
    overrides = policy["artifact_overrides"]
    families = list(policy["required_families"])
    if not families:
        families = sorted({artifact["family"] for artifact in artifacts if artifact["status"] == "verified"})
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    selections: list[dict[str, Any]] = []
    selection_blockers: list[str] = []
    family_failures: dict[str, list[str]] = {}
    for family in families:
        candidates = [
            artifact
            for artifact in artifacts
            if artifact["family"] == family
            and artifact["status"] == "verified"
            and artifact["id"] not in excluded_artifacts
            and artifact["organization"].casefold() not in excluded_orgs
            and artifact["base_family"].casefold() not in excluded_bases
        ]
        override = overrides.get(family)
        if override:
            candidate = by_id.get(override)
            if not candidate:
                family_failures[family] = [f"override artifact not found: {override}"]
                continue
            if candidate not in candidates:
                family_failures[family] = [f"override artifact is excluded or belongs to another family: {override}"]
                continue
            candidates = [candidate]
        evaluated: list[tuple[dict[str, Any], dict[str, Any]]] = [
            (candidate, artifact_fit(candidate, profile, policy)) for candidate in candidates
        ]
        fitting = [item for item in evaluated if item[1]["fit"] in {"recommended", "constrained"}]
        if not fitting:
            reasons = []
            for candidate, fit in evaluated:
                reasons.append(f"{candidate['id']}: {'; '.join(fit['blockers']) or 'not selected'}")
            family_failures[family] = reasons or ["no catalog artifacts remain after policy filters"]
            continue
        candidate, fit = max(
            fitting,
            key=lambda item: (
                float(item[0]["quality_rank"]),
                item[0]["distribution_channel"] == "ollama-curated",
                float(item[0]["disk_gib"]),
            ),
        )
        selection_blockers.extend(
            f"{candidate['id']}: {blocker}" for blocker in fit["blockers"]
        )
        selections.append(
            {
                "artifact_id": candidate["id"],
                "family": family,
                "runtime_model": candidate["runtime_model"],
                "quantization": candidate["quantization"],
                "distribution_channel": candidate["distribution_channel"],
                "artifact_publisher": candidate["artifact_publisher"],
                "disk_gib": candidate["disk_gib"],
                "fit": fit["fit"],
                "effective_memory_gib": fit["effective_memory_gib"],
                "minimum_runtime_version": candidate["minimum_runtime_version"],
                "roles": candidate["roles"],
            }
        )
    total_disk = round(sum(float(selection["disk_gib"]) for selection in selections), 2)
    free_disk = profile.get("storage", {}).get("free_gib")
    disk_blocker = None
    remaining = None
    if isinstance(free_disk, (int, float)):
        remaining = round(float(free_disk) - total_disk, 2)
        minimum_remaining = float(policy["minimum_free_disk_after_install_gib"])
        if remaining < minimum_remaining:
            disk_blocker = (
                f"plan would leave {remaining:.2f} GiB free; policy requires {minimum_remaining:.2f} GiB"
            )
    else:
        disk_blocker = "free disk is unknown"
    blockers = list(family_failures.values())
    flat_blockers = selection_blockers + [reason for group in blockers for reason in group]
    if disk_blocker:
        flat_blockers.append(disk_blocker)
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "machine": {
            "memory_gib": profile.get("memory", {}).get("total_gib"),
            "model_store": profile.get("storage", {}).get("model_store"),
            "free_disk_gib": free_disk,
            "ollama_version": profile.get("runtimes", {}).get("ollama", {}).get("version"),
        },
        "planning_context_tokens": policy["planning_context_tokens"],
        "selections": selections,
        "family_failures": family_failures,
        "total_download_gib": total_disk,
        "estimated_free_disk_after_install_gib": remaining,
        "blockers": flat_blockers,
        "ready": not flat_blockers and len(selections) == len(families),
    }


def plan_explicit(
    artifacts: list[dict[str, Any]], ids: list[str], profile: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    if len(ids) != len(set(ids)):
        raise LocalModelError("Explicit artifact ids must be unique")
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    missing = [artifact_id for artifact_id in ids if artifact_id not in by_id]
    if missing:
        raise LocalModelError(f"Unknown artifact id(s): {', '.join(missing)}")
    explicit_policy = dict(policy)
    explicit_policy["required_families"] = []
    selected: list[dict[str, Any]] = []
    blockers: list[str] = []
    excluded_orgs = {item.casefold() for item in policy["excluded_organizations"]}
    excluded_bases = {item.casefold() for item in policy["excluded_base_families"]}
    excluded_artifacts = set(policy["excluded_artifacts"])
    for artifact_id in ids:
        artifact = by_id[artifact_id]
        policy_reasons = []
        if artifact["status"] != "verified":
            policy_reasons.append("artifact is not verified in the current catalog")
        if artifact_id in excluded_artifacts:
            policy_reasons.append("artifact is excluded by policy")
        if artifact["organization"].casefold() in excluded_orgs:
            policy_reasons.append("organization is excluded by policy")
        if artifact["base_family"].casefold() in excluded_bases:
            policy_reasons.append("base family is excluded by policy")
        blockers.extend(f"{artifact_id}: {reason}" for reason in policy_reasons)
        fit = artifact_fit(artifact, profile, explicit_policy)
        selected.append(
            {
                "artifact_id": artifact_id,
                "family": artifact["family"],
                "runtime_model": artifact["runtime_model"],
                "quantization": artifact["quantization"],
                "distribution_channel": artifact["distribution_channel"],
                "artifact_publisher": artifact["artifact_publisher"],
                "disk_gib": artifact["disk_gib"],
                "fit": fit["fit"],
                "effective_memory_gib": fit.get("effective_memory_gib"),
                "minimum_runtime_version": artifact["minimum_runtime_version"],
                "roles": artifact["roles"],
            }
        )
        blockers.extend(f"{artifact_id}: {item}" for item in fit["blockers"])
    total_disk = round(sum(float(item["disk_gib"]) for item in selected), 2)
    free = profile.get("storage", {}).get("free_gib")
    remaining = round(float(free) - total_disk, 2) if isinstance(free, (int, float)) else None
    if remaining is None:
        blockers.append("free disk is unknown")
    elif remaining < float(policy["minimum_free_disk_after_install_gib"]):
        blockers.append(
            f"plan would leave {remaining:.2f} GiB free; policy requires "
            f"{float(policy['minimum_free_disk_after_install_gib']):.2f} GiB"
        )
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "machine": {
            "memory_gib": profile.get("memory", {}).get("total_gib"),
            "model_store": profile.get("storage", {}).get("model_store"),
            "free_disk_gib": free,
            "ollama_version": profile.get("runtimes", {}).get("ollama", {}).get("version"),
        },
        "planning_context_tokens": policy["planning_context_tokens"],
        "selections": selected,
        "family_failures": {},
        "total_download_gib": total_disk,
        "estimated_free_disk_after_install_gib": remaining,
        "blockers": blockers,
        "ready": not blockers,
    }


def normalize_model_name(value: str) -> str:
    normalized = value.casefold()
    return normalized[:-7] if normalized.endswith(":latest") else normalized


def ollama_tags() -> list[dict[str, Any]]:
    response = api_json("/api/tags", timeout=8)
    if not isinstance(response, dict) or not isinstance(response.get("models"), list):
        raise LocalModelError("Ollama /api/tags returned an unexpected response")
    return [model for model in response["models"] if isinstance(model, dict)]


def find_installed(runtime_model: str, tags: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = normalize_model_name(runtime_model)
    for model in tags:
        names = [model.get("name"), model.get("model")]
        if any(isinstance(name, str) and normalize_model_name(name) == target for name in names):
            return model
    return None


def safe_runtime_metadata(model: dict[str, Any]) -> dict[str, Any]:
    details = model.get("details") if isinstance(model.get("details"), dict) else {}
    return {
        "runtime_name": model.get("name") or model.get("model"),
        "digest": model.get("digest"),
        "size_bytes": model.get("size"),
        "modified_at": model.get("modified_at"),
        "format": details.get("format"),
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization_level": details.get("quantization_level"),
    }


def machine_id(state_dir: Path) -> str:
    path = state_dir / "machine-id"
    reject_symlink_components(state_dir, path)
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise LocalModelError(f"Unsafe opaque machine id path: {path}")
        value = path.read_text(encoding="utf-8").strip()
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise LocalModelError(f"Invalid opaque machine id in {path}") from exc
        return value
    state_dir.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(state_dir, path)
    value = str(uuid.uuid4())
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def existing_machine_id(state_dir: Path) -> str:
    path = state_dir / "machine-id"
    reject_symlink_components(state_dir, path)
    if not path.is_file() or path.is_symlink():
        raise LocalModelError("This computer has no registered opaque machine id")
    value = path.read_text(encoding="utf-8").strip()
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise LocalModelError(f"Invalid opaque machine id in {path}") from exc
    return value


def resolve_inventory_model(
    state_dir: Path,
    artifacts: list[dict[str, Any]],
    *,
    family: str | None = None,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    if bool(family) == bool(artifact_id):
        raise LocalModelError("Resolve requires exactly one of family or artifact id")
    identifier = existing_machine_id(state_dir)
    inventory = load_json(state_dir / "machines.json")
    if inventory.get("schema_version") != INVENTORY_SCHEMA:
        raise LocalModelError("Unsupported inventory schema")
    machines = inventory.get("machines")
    record = machines.get(identifier) if isinstance(machines, dict) else None
    if not isinstance(record, dict):
        raise LocalModelError("Current machine is absent from the inventory mapping")
    selected = record.get("selections")
    installed = record.get("installed")
    if not isinstance(selected, list) or not isinstance(installed, dict):
        raise LocalModelError("Current machine inventory record is malformed")
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    if family:
        matches = [
            item
            for item in selected
            if isinstance(item, str)
            and item in by_id
            and by_id[item]["family"] == family
        ]
        if len(matches) != 1:
            raise LocalModelError(
                f"Current machine must have exactly one selected {family} artifact; found {len(matches)}"
            )
        artifact_id = matches[0]
    assert artifact_id is not None
    if artifact_id not in selected:
        raise LocalModelError(f"Artifact {artifact_id} is not selected for this machine")
    if artifact_id not in by_id:
        raise LocalModelError(f"Selected artifact {artifact_id} is absent from the current catalog")
    installation = installed.get(artifact_id)
    if not isinstance(installation, dict):
        raise LocalModelError(f"Artifact {artifact_id} is selected but not verified as installed")
    runtime_name = installation.get("runtime_name")
    digest = installation.get("digest")
    if not isinstance(runtime_name, str) or not runtime_name:
        raise LocalModelError(f"Artifact {artifact_id} has no resolved runtime name")
    if not isinstance(digest, str) or not digest:
        raise LocalModelError(f"Artifact {artifact_id} has no resolved digest")
    return {
        "machine_id": identifier,
        "catalog_id": artifact_id,
        "family": by_id[artifact_id]["family"],
        "runtime": installation.get("runtime"),
        "runtime_name": runtime_name,
        "digest": digest,
        "verified_at": installation.get("verified_at"),
    }


def update_inventory(
    state_dir: Path,
    profile: dict[str, Any],
    selections: list[dict[str, Any]],
    installed: dict[str, dict[str, Any]] | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    identifier = machine_id(state_dir)
    inventory_path = state_dir / "machines.json"
    if inventory_path.exists():
        inventory = load_json(inventory_path)
        if inventory.get("schema_version") != INVENTORY_SCHEMA:
            raise LocalModelError("Unsupported inventory schema")
    else:
        inventory = {"schema_version": INVENTORY_SCHEMA, "machines": {}}
    machines = inventory.setdefault("machines", {})
    if not isinstance(machines, dict):
        raise LocalModelError("Inventory machines field is invalid")
    previous = machines.get(identifier, {}) if isinstance(machines.get(identifier), dict) else {}
    previous_installed = previous.get("installed", {})
    if not isinstance(previous_installed, dict):
        raise LocalModelError("Current machine installed-artifact map is invalid")
    record = {
        "label": label if label is not None else previous.get("label"),
        "updated_at": utc_now(),
        "profile": profile,
        "selections": [item["artifact_id"] for item in selections],
        "installed": dict(previous_installed),
    }
    if installed:
        record["installed"].update(installed)
    machines[identifier] = record
    inventory["updated_at"] = utc_now()
    atomic_json_write(inventory_path, inventory)
    return inventory


def model_store_from_profile(profile: dict[str, Any]) -> Path:
    value = profile.get("storage", {}).get("model_store")
    if not isinstance(value, str) or not value:
        raise LocalModelError("Resolved model store is absent from the machine profile")
    if value == "~":
        return Path.home()
    if value.startswith("~/"):
        return Path.home() / value[2:]
    path = Path(value)
    if not path.is_absolute():
        raise LocalModelError("Resolved model store path must be absolute or home-relative")
    return path


def import_cached_gguf_layers(
    artifact: dict[str, Any],
    profile: dict[str, Any],
    executable: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    fallback = artifact.get("local_import_fallback")
    if not isinstance(fallback, dict):
        raise LocalModelError(f"{artifact['id']} has no catalog-pinned local import fallback")
    layers = fallback.get("gguf_layers")
    if not isinstance(layers, list) or not layers:
        raise LocalModelError(f"{artifact['id']} fallback has no GGUF layers")
    store = model_store_from_profile(profile).expanduser().resolve(strict=False)
    blobs = store / "blobs"
    import_parent = store.parent / ".synthesis-local-model-imports"
    reject_symlink_components(store, blobs, import_parent)
    import_parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(import_parent)
    with tempfile.TemporaryDirectory(prefix=f"{artifact['id']}-", dir=import_parent) as value:
        import_dir = Path(value)
        for index, layer in enumerate(layers):
            digest = layer["digest"].removeprefix("sha256:")
            source = blobs / f"sha256-{digest}"
            reject_symlink_components(source)
            if not source.is_file() or source.is_symlink():
                raise LocalModelError(
                    f"Catalog-pinned fallback blob is absent for {artifact['id']}: {digest}"
                )
            observed_size = source.stat().st_size
            if observed_size != layer["size_bytes"]:
                raise LocalModelError(
                    f"Fallback blob size mismatch for {artifact['id']}: {digest}"
                )
            if sha256_file(source) != digest:
                raise LocalModelError(
                    f"Fallback blob digest mismatch for {artifact['id']}: {digest}"
                )
            suffix = (
                "model"
                if layer["media_type"] == "application/vnd.ollama.image.model"
                else "projector"
            )
            destination = import_dir / f"{index:02d}-{suffix}.gguf"
            os.link(source, destination)
        modelfile = import_dir / "Modelfile"
        atomic_text_write(modelfile, f"FROM {import_dir}\n")
        created = runner(
            [executable, "create", artifact["runtime_model"], "-f", str(modelfile)],
            check=False,
            text=True,
            shell=False,
        )
        if created.returncode != 0:
            raise LocalModelError(
                f"Ollama local import failed for {artifact['id']} with exit code "
                f"{created.returncode}"
            )


def cached_recovery_receipt(
    plan: dict[str, Any], artifacts: list[dict[str, Any]]
) -> dict[str, Any]:
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    layer_bytes = 0
    for selection in plan["selections"]:
        artifact = by_id[selection["artifact_id"]]
        fallback = artifact.get("local_import_fallback")
        if not isinstance(fallback, dict):
            raise LocalModelError(
                f"{artifact['id']} has no catalog-pinned cached-layer recovery"
            )
        layer_bytes += sum(layer["size_bytes"] for layer in fallback["gguf_layers"])
    return {
        "mode": "catalog-pinned-cached-layers",
        "network_download_gib": 0.0,
        "possible_additional_runtime_gib": round(layer_bytes / GIB, 2),
        "cache_retention": (
            "Ollama may retain registry cache after materializing normalized runtime layers"
        ),
    }


def perform_install(
    plan: dict[str, Any],
    artifacts: list[dict[str, Any]],
    profile: dict[str, Any],
    state_dir: Path,
    label: str | None,
    recover_cached: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not plan["ready"]:
        raise LocalModelError("Installation plan is blocked: " + "; ".join(plan["blockers"]))
    executable = shutil.which("ollama")
    if not executable:
        raise LocalModelError("Ollama executable is not installed")
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    installed: dict[str, dict[str, Any]] = {}
    for selection in plan["selections"]:
        artifact = by_id[selection["artifact_id"]]
        if recover_cached:
            if not artifact.get("local_import_fallback"):
                raise LocalModelError(
                    f"{artifact['id']} has no catalog-pinned cached-layer recovery"
                )
            import_cached_gguf_layers(artifact, profile, executable, runner)
            installation_method = "catalog-pinned-local-import"
        else:
            installation_method = "ollama-pull"
            result = runner(
                [executable, "pull", artifact["runtime_model"]],
                check=False,
                text=True,
                shell=False,
            )
            if result.returncode != 0:
                if not artifact.get("local_import_fallback"):
                    raise LocalModelError(
                        f"Ollama pull failed for {artifact['id']} with exit code "
                        f"{result.returncode}"
                    )
                import_cached_gguf_layers(artifact, profile, executable, runner)
                installation_method = "catalog-pinned-local-import"
        metadata = find_installed(artifact["runtime_model"], ollama_tags())
        if metadata is None:
            raise LocalModelError(
                f"Ollama reported success but {artifact['runtime_model']} is absent from /api/tags"
            )
        safe = safe_runtime_metadata(metadata)
        expected = artifact.get("expected_digest_prefix")
        digest = safe.get("digest")
        if expected and (not isinstance(digest, str) or not digest.startswith(expected)):
            raise LocalModelError(
                f"Resolved digest for {artifact['id']} does not match catalog prefix {expected}"
            )
        installed[artifact["id"]] = {
            "catalog_id": artifact["id"],
            "upstream_model": artifact["upstream_model"],
            "artifact_publisher": artifact["artifact_publisher"],
            "distribution_channel": artifact["distribution_channel"],
            "verified_at": utc_now(),
            "runtime": "ollama",
            "runtime_version": profile["runtimes"]["ollama"]["version"],
            "installation_method": installation_method,
            **safe,
        }
        update_inventory(state_dir, profile, plan["selections"], installed, label)
    return {"installed": installed, "inventory": display_path(state_dir / "machines.json")}


def verify_artifacts(
    ids: list[str], artifacts: list[dict[str, Any]], profile: dict[str, Any]
) -> dict[str, Any]:
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    unknown = [artifact_id for artifact_id in ids if artifact_id not in by_id]
    if unknown:
        raise LocalModelError(f"Unknown artifact id(s): {', '.join(unknown)}")
    tags = ollama_tags()
    results: dict[str, Any] = {}
    for artifact_id in ids:
        artifact = by_id[artifact_id]
        found = find_installed(artifact["runtime_model"], tags)
        if not found:
            results[artifact_id] = {"installed": False, "verified": False}
            continue
        metadata = safe_runtime_metadata(found)
        expected = artifact.get("expected_digest_prefix")
        digest = metadata.get("digest")
        digest_match = None if expected is None else bool(
            isinstance(digest, str) and digest.startswith(expected)
        )
        results[artifact_id] = {
            "installed": True,
            "verified": digest_match is not False,
            "expected_digest_prefix": expected,
            "expected_digest_match": digest_match,
            "runtime_version": profile["runtimes"]["ollama"]["version"],
            **metadata,
        }
    return {"verified_at": utc_now(), "artifacts": results}


def benchmark_artifact(
    artifact: dict[str, Any],
    output_dir: Path | None,
    prompt: str,
    num_predict: int,
    num_ctx: int,
) -> dict[str, Any]:
    if num_predict <= 0 or num_predict > 2048:
        raise LocalModelError("num-predict must be between 1 and 2048")
    if num_ctx < 1024 or num_ctx > 131072:
        raise LocalModelError("num-ctx must be between 1024 and 131072")
    response = api_json(
        "/api/generate",
        {
            "model": artifact["runtime_model"],
            "prompt": prompt,
            "stream": False,
            "keep_alive": 0,
            "options": {
                "temperature": 0,
                "seed": 7,
                "num_predict": num_predict,
                "num_ctx": num_ctx,
            },
        },
        timeout=1800,
    )
    if not isinstance(response, dict) or not isinstance(response.get("response"), str):
        raise LocalModelError("Ollama generation returned an unexpected response")
    output = response["response"]
    eval_count = response.get("eval_count")
    eval_duration = response.get("eval_duration")
    tokens_per_second = None
    if isinstance(eval_count, int) and isinstance(eval_duration, int) and eval_duration > 0:
        tokens_per_second = round(eval_count / (eval_duration / 1_000_000_000), 2)
    receipt = {
        "schema_version": 1,
        "created_at": utc_now(),
        "catalog_id": artifact["id"],
        "runtime_model": artifact["runtime_model"],
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "num_predict": num_predict,
        "num_ctx": num_ctx,
        "done_reason": response.get("done_reason"),
        "load_duration_ns": response.get("load_duration"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "prompt_eval_duration_ns": response.get("prompt_eval_duration"),
        "eval_count": eval_count,
        "eval_duration_ns": eval_duration,
        "tokens_per_second": tokens_per_second,
        "total_duration_ns": response.get("total_duration"),
    }
    if output_dir:
        destination = output_dir.expanduser().resolve(strict=False)
        if path_within(destination, SKILL_ROOT):
            raise LocalModelError("Benchmark output directory cannot be inside the skill source")
        destination.mkdir(parents=True, exist_ok=True)
        reject_symlink_components(destination)
        stem = artifact["id"]
        output_path = destination / f"{stem}-output.txt"
        receipt_path = destination / f"{stem}-benchmark.json"
        atomic_text_write(output_path, output)
        atomic_json_write(receipt_path, receipt)
        receipt["output_path"] = str(output_path)
        receipt["receipt_path"] = str(receipt_path)
    return receipt


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--model-store")
    parser.add_argument("--protected-root", action="append", default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    profile_parser = commands.add_parser("profile", help="Print a privacy-safe hardware profile")
    add_common(profile_parser)

    catalog_parser = commands.add_parser("catalog", help="Validate and summarize the model catalog")
    add_common(catalog_parser)

    recommend_parser = commands.add_parser("recommend", help="Recommend one fitting artifact per family")
    add_common(recommend_parser)

    install_parser = commands.add_parser("install", help="Plan or execute approved model installation")
    add_common(install_parser)
    install_parser.add_argument("--artifact", action="append", default=[])
    install_parser.add_argument("--yes", action="store_true")
    install_parser.add_argument(
        "--recover-cached",
        action="store_true",
        help="Skip acquisition and import only catalog-pinned cached GGUF layers",
    )
    install_parser.add_argument("--machine-label")

    inventory_parser = commands.add_parser("inventory", help="Register or refresh this machine mapping")
    add_common(inventory_parser)
    inventory_parser.add_argument("--save", action="store_true")
    inventory_parser.add_argument("--machine-label")

    verify_parser = commands.add_parser("verify", help="Verify installed runtime metadata")
    add_common(verify_parser)
    verify_parser.add_argument("--artifact", action="append", required=True)

    resolve_parser = commands.add_parser(
        "resolve", help="Resolve an allowed installed model for this exact machine"
    )
    add_common(resolve_parser)
    resolve_choice = resolve_parser.add_mutually_exclusive_group(required=True)
    resolve_choice.add_argument("--family")
    resolve_choice.add_argument("--artifact")

    benchmark_parser = commands.add_parser("benchmark", help="Run a bounded deterministic local sample")
    add_common(benchmark_parser)
    benchmark_parser.add_argument("--artifact", required=True)
    benchmark_parser.add_argument("--prompt-file", type=Path)
    benchmark_parser.add_argument("--output-dir", type=Path)
    benchmark_parser.add_argument("--num-predict", type=int, default=256)
    benchmark_parser.add_argument("--num-ctx", type=int, default=8192)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog, artifacts = load_catalog(args.catalog)
        policy = load_policy(args.policy)
        protected = list(args.protected_root) + list(policy["protected_roots"])
        profile = machine_profile(args.model_store, protected)

        if args.command == "profile":
            emit(profile)
            return 0
        if args.command == "catalog":
            families = sorted({artifact["family"] for artifact in artifacts if artifact["status"] == "verified"})
            emit(
                {
                    "schema_version": catalog["schema_version"],
                    "catalog_version": catalog.get("catalog_version"),
                    "verified_on": catalog.get("verified_on"),
                    "artifact_count": len(artifacts),
                    "families": families,
                    "status": "valid",
                }
            )
            return 0
        if args.command == "resolve":
            emit(
                resolve_inventory_model(
                    args.state_dir.expanduser(),
                    artifacts,
                    family=args.family,
                    artifact_id=args.artifact,
                )
            )
            return 0
        plan = recommend(artifacts, profile, policy)
        if args.command == "recommend":
            emit(plan)
            return 0 if plan["ready"] else 2
        if args.command == "install":
            if args.artifact:
                plan = plan_explicit(artifacts, args.artifact, profile, policy)
            recovery = (
                cached_recovery_receipt(plan, artifacts) if args.recover_cached else None
            )
            if not args.yes:
                emit(
                    {
                        "execute": False,
                        "authorization_required": True,
                        "recovery": recovery,
                        "plan": plan,
                    }
                )
                return 0 if plan["ready"] else 2
            result = perform_install(
                plan,
                artifacts,
                profile,
                args.state_dir.expanduser(),
                args.machine_label,
                recover_cached=args.recover_cached,
            )
            emit({"execute": True, "recovery": recovery, "plan": plan, **result})
            return 0
        if args.command == "inventory":
            if not args.save:
                inventory_path = args.state_dir.expanduser() / "machines.json"
                if not inventory_path.exists():
                    emit({"exists": False, "path": display_path(inventory_path)})
                else:
                    emit(load_json(inventory_path))
                return 0
            inventory = update_inventory(
                args.state_dir.expanduser(), profile, plan["selections"], label=args.machine_label
            )
            emit(inventory)
            return 0
        if args.command == "verify":
            result = verify_artifacts(args.artifact, artifacts, profile)
            emit(result)
            return 0 if all(item["verified"] for item in result["artifacts"].values()) else 2
        if args.command == "benchmark":
            by_id = {artifact["id"]: artifact for artifact in artifacts}
            artifact = by_id.get(args.artifact)
            if not artifact:
                raise LocalModelError(f"Unknown artifact id: {args.artifact}")
            prompt = (
                args.prompt_file.read_text(encoding="utf-8")
                if args.prompt_file
                else "Explain one practical benefit and one limitation of running an open-weight language model locally."
            )
            emit(
                benchmark_artifact(
                    artifact, args.output_dir, prompt, args.num_predict, args.num_ctx
                )
            )
            return 0
        raise LocalModelError(f"Unknown command: {args.command}")
    except LocalModelError as exc:
        emit({"error": str(exc), "status": "blocked"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
