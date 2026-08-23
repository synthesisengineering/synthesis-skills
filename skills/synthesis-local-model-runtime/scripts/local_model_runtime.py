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
HOMEBREW_OLLAMA_LABEL = "homebrew.mxcl.ollama"
OLLAMA_KV_CACHE_TYPES = {"f16", "q8_0", "q4_0"}
GIB = 1024**3
SUPPORTED_CATALOG_SCHEMAS = {1, 2}
CATALOG_SCHEMA = 2
POLICY_SCHEMA = 1
INVENTORY_SCHEMA = 1
MANAGED_RUNTIMES = {"ollama", "lm_studio"}

RUNTIME_CAPABILITIES: dict[str, dict[str, Any]] = {
    "ollama": {
        "mode": "managed",
        "recommend": True,
        "install": True,
        "inventory": True,
        "verify": True,
        "update": True,
        "execute": True,
        "serve": True,
        "benchmark": True,
        "configuration": True,
    },
    "lm_studio": {
        "mode": "managed",
        "recommend": True,
        "install": True,
        "inventory": True,
        "verify": True,
        "update": False,
        "execute": True,
        "serve": True,
        "benchmark": False,
        "configuration": False,
    },
    "llama_cpp": {
        "mode": "direct",
        "recommend": False,
        "install": False,
        "inventory": False,
        "verify": False,
        "update": False,
        "execute": True,
        "serve": True,
        "benchmark": False,
        "configuration": False,
    },
    "mlx_lm": {
        "mode": "direct",
        "recommend": False,
        "install": False,
        "inventory": False,
        "verify": False,
        "update": False,
        "execute": True,
        "serve": True,
        "benchmark": False,
        "configuration": False,
    },
}

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


def atomic_bytes_write(path: Path, value: bytes, mode: int | None = None) -> None:
    reject_symlink_components(path.parent, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(path.parent, path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary_path, mode)
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


def python_distribution_version(
    executable: str | None, distribution: str
) -> str | None:
    if not executable:
        return None
    try:
        with Path(executable).open("rb") as stream:
            first_line = stream.readline(512).decode("utf-8", errors="replace").strip()
    except OSError:
        return None
    if not first_line.startswith("#!"):
        return None
    interpreter = first_line[2:].strip().split()[0]
    if not interpreter or Path(interpreter).name not in {"python", "python3"}:
        return None
    output = command_output(
        [
            interpreter,
            "-c",
            "import importlib.metadata as m, sys; print(m.version(sys.argv[1]))",
            distribution,
        ]
    )
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


def macos_homebrew_ollama_service() -> tuple[Path, dict[str, Any]] | None:
    plist_path = Path.home() / "Library" / "LaunchAgents" / "homebrew.mxcl.ollama.plist"
    try:
        reject_symlink_components(plist_path.parent, plist_path)
        payload = plistlib.loads(plist_path.read_bytes())
    except (FileNotFoundError, plistlib.InvalidFileException, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return plist_path, payload


def macos_homebrew_ollama_store() -> Path | None:
    service = macos_homebrew_ollama_service()
    if service is None:
        return None
    _, payload = service
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
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except OSError:
            body = ""
        detail = body.strip()[:2000] or str(exc)
        raise LocalModelError(
            f"Ollama loopback API returned HTTP {exc.code} for {path}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LocalModelError(f"Ollama loopback API unavailable for {path}: {exc}") from exc


def ollama_service_configuration() -> dict[str, Any]:
    if platform.system() == "Darwin":
        service = macos_homebrew_ollama_service()
        if service is not None:
            _, payload = service
            environment = payload.get("EnvironmentVariables", {})
            if isinstance(environment, dict):
                return {
                    "source": "homebrew-service",
                    "kv_cache_type": str(
                        environment.get("OLLAMA_KV_CACHE_TYPE") or "f16"
                    ),
                    "flash_attention": str(
                        environment.get("OLLAMA_FLASH_ATTENTION") or "0"
                    ),
                }
    return {
        "source": "process-environment"
        if os.environ.get("OLLAMA_KV_CACHE_TYPE")
        else "runtime-default",
        "kv_cache_type": os.environ.get("OLLAMA_KV_CACHE_TYPE", "f16"),
        "flash_attention": os.environ.get("OLLAMA_FLASH_ATTENTION", "0"),
    }


def runtime_profile() -> dict[str, Any]:
    ollama = shutil.which("ollama")
    lms = shutil.which("lms")
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
    lms_build_identity = None
    if lms:
        output = command_output([lms, "version", "--json"])
        if output:
            try:
                value = json.loads(output)
                if isinstance(value, dict):
                    candidate = value.get("version") or value.get("commit")
                    if isinstance(candidate, str) and candidate:
                        lms_build_identity = candidate
            except json.JSONDecodeError:
                pass
    runtimes = {
        "ollama": {
            "available": bool(ollama),
            "version": api_version or ollama_version,
            "api_reachable": api_reachable,
            "configuration": ollama_service_configuration(),
            "adapter_status": "managed-full",
            "capabilities": dict(RUNTIME_CAPABILITIES["ollama"]),
        },
        "lm_studio": {
            "available": bool(lms),
            "version": command_version(lms, "version"),
            "build_identity": lms_build_identity,
            "adapter_status": "managed-partial",
            "capabilities": dict(RUNTIME_CAPABILITIES["lm_studio"]),
            "update_limitation": (
                "LM Studio does not expose a stable, scriptable model-content identity "
                "contract that lets this skill prove an in-place update. Re-downloads are "
                "therefore not represented as verified updates."
            ),
        },
        "llama_cpp": {
            "available": bool(llama_cli),
            "version": command_version(llama_cli, "--version"),
            "adapter_status": "direct-runtime",
            "capabilities": dict(RUNTIME_CAPABILITIES["llama_cpp"]),
            "management_guidance": (
                "Use llama.cpp directly for GGUF execution or serving; model acquisition "
                "and lifecycle remain the caller's responsibility."
            ),
        },
        "mlx_lm": {
            "available": bool(mlx),
            "version": command_version(mlx, "--version")
            or python_distribution_version(mlx, "mlx-lm"),
            "adapter_status": "direct-runtime",
            "capabilities": dict(RUNTIME_CAPABILITIES["mlx_lm"]),
            "management_guidance": (
                "Use MLX-LM directly for Apple-Silicon-native execution or serving; the "
                "Hugging Face cache is not treated as a managed model registry."
            ),
        },
    }
    return runtimes


def runtime_summary(profile: dict[str, Any]) -> dict[str, Any]:
    runtimes = profile.get("runtimes", {})
    return {
        "default_runtime": "ollama",
        "managed_choices": ["ollama", "lm_studio"],
        "direct_choices": ["llama_cpp", "mlx_lm"],
        "selection_guidance": {
            "ollama": "Default for scriptable install, inventory, verification, and updates.",
            "lm_studio": (
                "Optional GUI/headless managed environment with catalog-driven downloads; "
                "verified model-content updates are not automated."
            ),
            "llama_cpp": "Direct GGUF execution and serving with first-class Apple Silicon support.",
            "mlx_lm": "Direct Apple-Silicon-native execution and serving through MLX.",
        },
        "runtimes": runtimes,
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


def runtime_target(artifact: dict[str, Any], runtime_name: str) -> dict[str, Any] | None:
    if runtime_name == "ollama":
        return {
            "model": artifact["runtime_model"],
            "minimum_version": artifact["minimum_runtime_version"],
            "expected_digest_prefix": artifact.get("expected_digest_prefix"),
        }
    targets = artifact.get("runtime_targets", {})
    target = targets.get(runtime_name) if isinstance(targets, dict) else None
    return dict(target) if isinstance(target, dict) else None


def validate_runtime_targets(artifact: dict[str, Any]) -> None:
    artifact_id = artifact["id"]
    targets = artifact.get("runtime_targets")
    if targets is None:
        return
    if not isinstance(targets, dict):
        raise LocalModelError(f"{artifact_id}.runtime_targets must be an object")
    unknown = sorted(set(targets) - {"lm_studio"})
    if unknown:
        raise LocalModelError(
            f"{artifact_id}.runtime_targets has unsupported runtimes: {', '.join(unknown)}"
        )
    lm_studio = targets.get("lm_studio")
    if lm_studio is None:
        return
    if not isinstance(lm_studio, dict):
        raise LocalModelError(f"{artifact_id}.runtime_targets.lm_studio must be an object")
    if set(lm_studio) != {
        "model",
        "format",
        "match_terms",
        "artifact_publisher",
        "artifact_source_url",
    }:
        raise LocalModelError(
            f"{artifact_id}.runtime_targets.lm_studio must contain exactly model, format, "
            "match_terms, artifact_publisher, and artifact_source_url"
        )
    validate_https_url(lm_studio["model"], f"{artifact_id}.runtime_targets.lm_studio.model")
    validate_https_url(
        lm_studio["artifact_source_url"],
        f"{artifact_id}.runtime_targets.lm_studio.artifact_source_url",
    )
    if not isinstance(lm_studio["artifact_publisher"], str) or not lm_studio[
        "artifact_publisher"
    ]:
        raise LocalModelError(f"{artifact_id} LM Studio artifact publisher is invalid")
    if not str(lm_studio["model"]).startswith("https://huggingface.co/"):
        raise LocalModelError(f"{artifact_id} LM Studio target must use huggingface.co")
    if lm_studio["format"] not in {"gguf", "mlx"}:
        raise LocalModelError(f"{artifact_id} LM Studio target format must be gguf or mlx")
    match_terms = lm_studio["match_terms"]
    if (
        not isinstance(match_terms, list)
        or len(match_terms) < 2
        or not all(
            isinstance(term, str)
            and term == term.casefold()
            and re.fullmatch(r"[a-z0-9._/-]+", term)
            for term in match_terms
        )
    ):
        raise LocalModelError(
            f"{artifact_id} LM Studio match_terms must have at least two safe lowercase terms"
        )


def validate_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("schema_version") not in SUPPORTED_CATALOG_SCHEMAS:
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
            raise LocalModelError(f"Unsupported legacy runtime in catalog: {artifact['runtime']}")
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
        validate_runtime_targets(artifact)
        requirements = artifact.get("runtime_requirements")
        if requirements is not None:
            if not isinstance(requirements, dict):
                raise LocalModelError(
                    f"{artifact_id}.runtime_requirements must be an object"
                )
            unknown_requirements = sorted(
                set(requirements) - {"ollama_kv_cache_types"}
            )
            if unknown_requirements:
                raise LocalModelError(
                    f"{artifact_id}.runtime_requirements has unknown fields: "
                    + ", ".join(unknown_requirements)
                )
            cache_types = requirements.get("ollama_kv_cache_types")
            if not isinstance(cache_types, list) or not cache_types:
                raise LocalModelError(
                    f"{artifact_id}.runtime_requirements.ollama_kv_cache_types "
                    "must be a non-empty list"
                )
            if any(value not in OLLAMA_KV_CACHE_TYPES for value in cache_types):
                raise LocalModelError(
                    f"{artifact_id} has an unsupported Ollama KV cache requirement"
                )
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


def artifact_fit(
    artifact: dict[str, Any],
    profile: dict[str, Any],
    policy: dict[str, Any],
    runtime_name: str = "ollama",
) -> dict[str, Any]:
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
    target = runtime_target(artifact, runtime_name)
    if runtime_name not in MANAGED_RUNTIMES:
        runtime_blockers.append(
            f"runtime {runtime_name} is a direct runtime and has no managed catalog adapter"
        )
    if target is None:
        runtime_blockers.append(
            f"artifact has no verified {runtime_name} catalog target"
        )
    runtime = profile.get("runtimes", {}).get(runtime_name, {})
    if not runtime.get("available"):
        runtime_blockers.append(f"runtime {runtime_name} is not installed")
    minimum_version = target.get("minimum_version") if target else None
    if (
        runtime.get("available")
        and isinstance(minimum_version, str)
        and not runtime_satisfies(runtime.get("version"), minimum_version)
    ):
        runtime_blockers.append(
            f"runtime {runtime_name} {runtime.get('version') or 'unknown'} is below "
            f"{minimum_version}"
        )
    requirements = artifact.get("runtime_requirements", {})
    allowed_cache_types = (
        requirements.get("ollama_kv_cache_types") if runtime_name == "ollama" else None
    )
    if allowed_cache_types:
        current_cache_type = runtime.get("configuration", {}).get("kv_cache_type")
        if current_cache_type not in allowed_cache_types:
            runtime_blockers.append(
                f"runtime {runtime_name} KV cache is "
                f"{current_cache_type or 'unknown'}; artifact requires one of "
                f"{', '.join(allowed_cache_types)}"
            )
    return {
        "fit": fit,
        "blockers": blockers + runtime_blockers,
        "runtime_ready": not runtime_blockers,
        "effective_memory_gib": round(effective, 2),
    }


def recommend(
    artifacts: list[dict[str, Any]],
    profile: dict[str, Any],
    policy: dict[str, Any],
    runtime_name: str = "ollama",
) -> dict[str, Any]:
    if runtime_name not in MANAGED_RUNTIMES:
        raise LocalModelError(f"Unsupported managed runtime: {runtime_name}")
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
            (candidate, artifact_fit(candidate, profile, policy, runtime_name))
            for candidate in candidates
        ]
        fitting = [
            item
            for item in evaluated
            if item[1]["fit"] in {"recommended", "constrained"}
            and item[1]["runtime_ready"]
        ]
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
                "runtime": runtime_name,
                "runtime_model": runtime_target(candidate, runtime_name)["model"],
                "quantization": candidate["quantization"],
                "distribution_channel": candidate["distribution_channel"],
                "artifact_publisher": candidate["artifact_publisher"],
                "disk_gib": candidate["disk_gib"],
                "fit": fit["fit"],
                "effective_memory_gib": fit["effective_memory_gib"],
                "minimum_runtime_version": candidate["minimum_runtime_version"],
                "runtime_requirements": candidate.get("runtime_requirements", {}),
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
            "selected_runtime": runtime_name,
            "selected_runtime_version": profile.get("runtimes", {}).get(runtime_name, {}).get("version"),
        },
        "runtime": runtime_name,
        "planning_context_tokens": policy["planning_context_tokens"],
        "selections": selections,
        "family_failures": family_failures,
        "total_download_gib": total_disk,
        "estimated_free_disk_after_install_gib": remaining,
        "blockers": flat_blockers,
        "ready": not flat_blockers and len(selections) == len(families),
    }


def plan_explicit(
    artifacts: list[dict[str, Any]],
    ids: list[str],
    profile: dict[str, Any],
    policy: dict[str, Any],
    runtime_name: str = "ollama",
) -> dict[str, Any]:
    if runtime_name not in MANAGED_RUNTIMES:
        raise LocalModelError(f"Unsupported managed runtime: {runtime_name}")
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
        fit = artifact_fit(artifact, profile, explicit_policy, runtime_name)
        target = runtime_target(artifact, runtime_name)
        selected.append(
            {
                "artifact_id": artifact_id,
                "family": artifact["family"],
                "runtime": runtime_name,
                "runtime_model": target["model"] if target else None,
                "quantization": artifact["quantization"],
                "distribution_channel": artifact["distribution_channel"],
                "artifact_publisher": artifact["artifact_publisher"],
                "disk_gib": artifact["disk_gib"],
                "fit": fit["fit"],
                "effective_memory_gib": fit.get("effective_memory_gib"),
                "minimum_runtime_version": artifact["minimum_runtime_version"],
                "runtime_requirements": artifact.get("runtime_requirements", {}),
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
            "selected_runtime": runtime_name,
            "selected_runtime_version": profile.get("runtimes", {}).get(runtime_name, {}).get("version"),
        },
        "runtime": runtime_name,
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


def _flatten_lm_studio_models(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LocalModelError("LM Studio model inventory must be a JSON array")
    flattened: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        model = item.get("model")
        variants = item.get("variants")
        if isinstance(model, dict):
            flattened.append(model)
        else:
            flattened.append(item)
        if isinstance(variants, list):
            flattened.extend(variant for variant in variants if isinstance(variant, dict))
    return flattened


def lm_studio_models(
    executable: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[dict[str, Any]]:
    resolved = executable or shutil.which("lms")
    if not resolved:
        raise LocalModelError("LM Studio CLI (lms) is not installed")
    try:
        result = runner(
            [resolved, "ls", "--json", "--variants"],
            check=False,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LocalModelError(f"LM Studio inventory could not run: {exc}") from exc
    if result.returncode != 0:
        raise LocalModelError(
            f"LM Studio inventory failed with exit code {result.returncode}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LocalModelError("LM Studio inventory returned invalid JSON") from exc
    return _flatten_lm_studio_models(payload)


def _privacy_safe_model_key(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("/") or value.startswith("~"):
        return Path(value).name
    return value


def safe_lm_studio_metadata(model: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "runtime_name": _privacy_safe_model_key(
            model.get("modelKey") or model.get("model_key") or model.get("path")
        ),
        "size_bytes": model.get("sizeBytes") or model.get("size_bytes"),
        "format": model.get("format") or model.get("compatibilityType"),
        "family": model.get("architecture"),
        "parameter_size": model.get("paramsString") or model.get("parameterSize"),
        "quantization_level": model.get("quantization") or model.get("quantizationName"),
    }
    return metadata


def lm_studio_metadata_identity(metadata: dict[str, Any]) -> str:
    runtime_name = metadata.get("runtime_name")
    size_bytes = metadata.get("size_bytes")
    if not isinstance(runtime_name, str) or not runtime_name:
        raise LocalModelError("LM Studio inventory entry has no safe runtime name")
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
        raise LocalModelError("LM Studio inventory entry has no valid model size")
    encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def find_lm_studio_installed(
    target: dict[str, Any], models: list[dict[str, Any]]
) -> dict[str, Any] | None:
    terms = target.get("match_terms")
    if not isinstance(terms, list) or not terms:
        raise LocalModelError("LM Studio target has no validated match terms")
    matches: list[dict[str, Any]] = []
    for model in models:
        candidates = [
            model.get("modelKey"),
            model.get("model_key"),
            model.get("path"),
            model.get("displayName"),
            model.get("quantization"),
            model.get("quantizationName"),
        ]
        haystack = " ".join(value for value in candidates if isinstance(value, str)).casefold()
        if all(term in haystack for term in terms):
            matches.append(model)
    if len(matches) > 1:
        raise LocalModelError(
            "LM Studio inventory contains multiple models matching the catalog identity"
        )
    return matches[0] if matches else None


def validate_ollama_model_name(value: str) -> None:
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?",
        value,
    ):
        raise LocalModelError(f"Unsafe Ollama model name: {value!r}")


def plan_model_updates(
    runtime_name: str,
    model_names: list[str],
    update_all: bool,
    tags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if runtime_name != "ollama":
        if runtime_name == "lm_studio":
            raise LocalModelError(
                "LM Studio model updates are blocked because the runtime does not expose "
                "a stable content-identity contract that this skill can verify"
            )
        raise LocalModelError(f"Runtime {runtime_name} has no managed update adapter")
    if bool(model_names) == bool(update_all):
        raise LocalModelError("Choose explicit --model values or --all, but not both")
    installed = tags if tags is not None else ollama_tags()
    if update_all:
        names = [safe_runtime_metadata(model).get("runtime_name") for model in installed]
        requested = sorted(
            {name for name in names if isinstance(name, str) and name},
            key=str.casefold,
        )
    else:
        requested = list(model_names)
    if not requested:
        raise LocalModelError("No installed Ollama models were selected for update")
    if len({normalize_model_name(name) for name in requested}) != len(requested):
        raise LocalModelError("Update model names must be unique")
    models: list[dict[str, Any]] = []
    for name in requested:
        validate_ollama_model_name(name)
        found = find_installed(name, installed)
        if found is None:
            raise LocalModelError(f"Ollama model is not installed: {name}")
        safe = safe_runtime_metadata(found)
        if not isinstance(safe.get("digest"), str) or not safe["digest"]:
            raise LocalModelError(f"Ollama returned no content digest for {name}")
        if (
            not isinstance(safe.get("size_bytes"), int)
            or isinstance(safe["size_bytes"], bool)
            or safe["size_bytes"] <= 0
        ):
            raise LocalModelError(f"Ollama returned no valid model size for {name}")
        resolved_name = safe.get("runtime_name")
        if not isinstance(resolved_name, str) or not resolved_name:
            raise LocalModelError(f"Ollama returned no resolved name for {name}")
        validate_ollama_model_name(resolved_name)
        models.append(
            {
                "runtime_name": resolved_name,
                "action": "ollama pull",
                "remote_change": "unknown-until-pull",
                "before": safe,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "runtime": "ollama",
        "execute": False,
        "authorization_required": True,
        "scope": "all-installed" if update_all else "explicit",
        "models": models,
    }


def refresh_inventory_after_ollama_updates(
    state_dir: Path, results: list[dict[str, Any]]
) -> bool:
    inventory_path = state_dir / "machines.json"
    machine_path = state_dir / "machine-id"
    if not inventory_path.exists() or not machine_path.exists():
        return False
    identifier = existing_machine_id(state_dir)
    inventory = load_json(inventory_path)
    if inventory.get("schema_version") != INVENTORY_SCHEMA:
        raise LocalModelError("Unsupported inventory schema")
    machines = inventory.get("machines")
    record = machines.get(identifier) if isinstance(machines, dict) else None
    if not isinstance(record, dict):
        return False
    installed = record.get("installed")
    if not isinstance(installed, dict):
        raise LocalModelError("Current machine installed-artifact map is invalid")
    by_name = {
        normalize_model_name(result["runtime_name"]): result
        for result in results
        if result.get("status") in {"updated", "already-current"}
    }
    changed = False
    for installation in installed.values():
        if not isinstance(installation, dict) or installation.get("runtime") != "ollama":
            continue
        runtime_name = installation.get("runtime_name")
        if not isinstance(runtime_name, str):
            continue
        result = by_name.get(normalize_model_name(runtime_name))
        if not result:
            continue
        after = result["after"]
        installation.update(after)
        installation["last_update"] = {
            "checked_at": result["checked_at"],
            "status": result["status"],
            "changed": result["changed"],
        }
        changed = True
    if changed:
        record["updated_at"] = utc_now()
        inventory["updated_at"] = utc_now()
        atomic_json_write(inventory_path, inventory)
    return changed


def perform_ollama_updates(
    plan: dict[str, Any],
    state_dir: Path,
    receipt_dir: Path | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    tags_provider: Callable[[], list[dict[str, Any]]] = ollama_tags,
) -> dict[str, Any]:
    if plan.get("runtime") != "ollama" or not isinstance(plan.get("models"), list):
        raise LocalModelError("Invalid Ollama update plan")
    executable = shutil.which("ollama")
    if not executable:
        raise LocalModelError("Ollama executable is not installed")
    results: list[dict[str, Any]] = []
    for planned in plan["models"]:
        name = planned.get("runtime_name")
        if not isinstance(name, str):
            raise LocalModelError("Update plan contains no validated runtime model name")
        validate_ollama_model_name(name)
        try:
            result = runner(
                [executable, "pull", name],
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=7200,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            results.append(
                {
                    "runtime_name": name,
                    "status": "failed-runtime",
                    "changed": False,
                    "checked_at": utc_now(),
                    "before": planned["before"],
                }
            )
            break
        checked_at = utc_now()
        if result.returncode != 0:
            results.append(
                {
                    "runtime_name": name,
                    "status": "failed",
                    "changed": False,
                    "checked_at": checked_at,
                    "exit_code": result.returncode,
                    "before": planned["before"],
                }
            )
            break
        found = find_installed(name, tags_provider())
        if found is None:
            results.append(
                {
                    "runtime_name": name,
                    "status": "failed-verification",
                    "changed": False,
                    "checked_at": checked_at,
                    "exit_code": 0,
                    "before": planned["before"],
                }
            )
            break
        after = safe_runtime_metadata(found)
        if not isinstance(after.get("digest"), str) or not after["digest"]:
            results.append(
                {
                    "runtime_name": name,
                    "status": "failed-verification",
                    "changed": False,
                    "checked_at": checked_at,
                    "exit_code": 0,
                    "before": planned["before"],
                }
            )
            break
        before = planned["before"]
        changed = (
            before.get("digest") != after.get("digest")
            or before.get("size_bytes") != after.get("size_bytes")
        )
        results.append(
            {
                "runtime_name": name,
                "status": "updated" if changed else "already-current",
                "changed": changed,
                "checked_at": checked_at,
                "exit_code": 0,
                "before": before,
                "after": after,
            }
        )
    success = len(results) == len(plan["models"]) and all(
        result["status"] in {"updated", "already-current"} for result in results
    )
    inventory_refreshed = refresh_inventory_after_ollama_updates(state_dir, results)
    receipt = {
        "schema_version": 1,
        "created_at": utc_now(),
        "runtime": "ollama",
        "scope": plan.get("scope"),
        "success": success,
        "models": results,
        "inventory_refreshed": inventory_refreshed,
    }
    if receipt_dir is not None:
        destination = receipt_dir.expanduser().resolve(strict=False)
        if path_within(destination, SKILL_ROOT):
            raise LocalModelError("Update receipt directory cannot be inside the skill source")
        destination.mkdir(parents=True, exist_ok=True)
        reject_symlink_components(destination)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        receipt_path = destination / f"ollama-update-{stamp}.json"
        atomic_json_write(receipt_path, receipt)
        receipt["receipt_path"] = display_path(receipt_path)
    return receipt


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
    identity = digest or installation.get("identity")
    identity_strength = installation.get("identity_strength") or (
        "content-digest" if digest else None
    )
    if not isinstance(runtime_name, str) or not runtime_name:
        raise LocalModelError(f"Artifact {artifact_id} has no resolved runtime name")
    if not isinstance(identity, str) or not identity:
        raise LocalModelError(f"Artifact {artifact_id} has no resolved identity")
    return {
        "machine_id": identifier,
        "catalog_id": artifact_id,
        "family": by_id[artifact_id]["family"],
        "runtime": installation.get("runtime"),
        "runtime_name": runtime_name,
        "digest": digest,
        "identity": identity,
        "identity_strength": identity_strength,
        "verified_at": installation.get("verified_at"),
    }


def update_inventory(
    state_dir: Path,
    profile: dict[str, Any],
    selections: list[dict[str, Any]],
    installed: dict[str, dict[str, Any]] | None = None,
    label: str | None = None,
    *,
    merge_selections: bool = False,
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
    selection_ids = [item["artifact_id"] for item in selections]
    if merge_selections:
        previous_selections = previous.get("selections", [])
        if not isinstance(previous_selections, list) or not all(
            isinstance(item, str) and item for item in previous_selections
        ):
            raise LocalModelError("Current machine selection list is invalid")
        selection_ids = list(dict.fromkeys([*previous_selections, *selection_ids]))
    record = {
        "label": label if label is not None else previous.get("label"),
        "updated_at": utc_now(),
        "profile": profile,
        "selections": selection_ids,
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


def perform_lm_studio_install(
    plan: dict[str, Any],
    artifacts: list[dict[str, Any]],
    profile: dict[str, Any],
    state_dir: Path,
    label: str | None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not plan["ready"]:
        raise LocalModelError("Installation plan is blocked: " + "; ".join(plan["blockers"]))
    executable = shutil.which("lms")
    if not executable:
        raise LocalModelError("LM Studio CLI (lms) is not installed")
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    installed: dict[str, dict[str, Any]] = {}
    for selection in plan["selections"]:
        artifact = by_id[selection["artifact_id"]]
        target = runtime_target(artifact, "lm_studio")
        if target is None:
            raise LocalModelError(
                f"{artifact['id']} has no verified LM Studio catalog target"
            )
        arguments = [executable, "get", target["model"], "--yes"]
        arguments.append("--gguf" if target["format"] == "gguf" else "--mlx")
        try:
            result = runner(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=7200,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LocalModelError(
                f"LM Studio download could not run for {artifact['id']}: {exc}"
            ) from exc
        if result.returncode != 0:
            raise LocalModelError(
                f"LM Studio download failed for {artifact['id']} with exit code {result.returncode}"
            )
        found = find_lm_studio_installed(
            target, lm_studio_models(executable=executable, runner=runner)
        )
        if found is None:
            raise LocalModelError(
                f"LM Studio reported success but {artifact['id']} is absent from its JSON inventory"
            )
        safe = safe_lm_studio_metadata(found)
        identity = lm_studio_metadata_identity(safe)
        installed[artifact["id"]] = {
            "catalog_id": artifact["id"],
            "upstream_model": artifact["upstream_model"],
            "artifact_publisher": target["artifact_publisher"],
            "artifact_source_url": target["artifact_source_url"],
            "distribution_channel": "huggingface-gguf",
            "verified_at": utc_now(),
            "runtime": "lm_studio",
            "runtime_version": profile["runtimes"]["lm_studio"].get("version"),
            "runtime_build_identity": profile["runtimes"]["lm_studio"].get(
                "build_identity"
            ),
            "installation_method": "lm-studio-get",
            "identity": identity,
            "identity_strength": "runtime-metadata",
            **safe,
        }
        update_inventory(
            state_dir,
            profile,
            plan["selections"],
            installed,
            label,
            merge_selections=True,
        )
    return {"installed": installed, "inventory": display_path(state_dir / "machines.json")}


def perform_install(
    plan: dict[str, Any],
    artifacts: list[dict[str, Any]],
    profile: dict[str, Any],
    state_dir: Path,
    label: str | None,
    recover_cached: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    runtime_name = plan.get("runtime", "ollama")
    if runtime_name == "lm_studio":
        if recover_cached:
            raise LocalModelError("Cached GGUF recovery is only available for Ollama")
        return perform_lm_studio_install(
            plan, artifacts, profile, state_dir, label, runner
        )
    if runtime_name != "ollama":
        raise LocalModelError(f"Unsupported managed runtime: {runtime_name}")
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
        if not isinstance(digest, str) or not digest:
            raise LocalModelError(
                f"Resolved Ollama metadata for {artifact['id']} has no content digest"
            )
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
        update_inventory(
            state_dir,
            profile,
            plan["selections"],
            installed,
            label,
            merge_selections=True,
        )
    return {"installed": installed, "inventory": display_path(state_dir / "machines.json")}


def verify_artifacts(
    ids: list[str],
    artifacts: list[dict[str, Any]],
    profile: dict[str, Any],
    runtime_name: str = "ollama",
) -> dict[str, Any]:
    by_id = {artifact["id"]: artifact for artifact in artifacts}
    unknown = [artifact_id for artifact_id in ids if artifact_id not in by_id]
    if unknown:
        raise LocalModelError(f"Unknown artifact id(s): {', '.join(unknown)}")
    if runtime_name not in MANAGED_RUNTIMES:
        raise LocalModelError(f"Unsupported managed runtime: {runtime_name}")
    tags = ollama_tags() if runtime_name == "ollama" else []
    lm_models = lm_studio_models() if runtime_name == "lm_studio" else []
    results: dict[str, Any] = {}
    for artifact_id in ids:
        artifact = by_id[artifact_id]
        target = runtime_target(artifact, runtime_name)
        if target is None:
            results[artifact_id] = {
                "installed": False,
                "verified": False,
                "blocker": f"artifact has no verified {runtime_name} catalog target",
            }
            continue
        found = (
            find_installed(target["model"], tags)
            if runtime_name == "ollama"
            else find_lm_studio_installed(target, lm_models)
        )
        if not found:
            results[artifact_id] = {"installed": False, "verified": False}
            continue
        metadata = (
            safe_runtime_metadata(found)
            if runtime_name == "ollama"
            else safe_lm_studio_metadata(found)
        )
        expected = target.get("expected_digest_prefix")
        digest = metadata.get("digest")
        digest_match = None if expected is None else bool(
            isinstance(digest, str) and digest.startswith(expected)
        )
        identity = (
            digest if runtime_name == "ollama" else lm_studio_metadata_identity(metadata)
        )
        results[artifact_id] = {
            "installed": True,
            "verified": (
                bool(isinstance(digest, str) and digest)
                and digest_match is not False
                if runtime_name == "ollama"
                else True
            ),
            "runtime": runtime_name,
            "expected_digest_prefix": expected,
            "expected_digest_match": digest_match,
            "runtime_version": profile["runtimes"][runtime_name].get("version"),
            "identity": identity,
            "identity_strength": (
                "content-digest" if runtime_name == "ollama" else "runtime-metadata"
            ),
            **metadata,
        }
    return {"verified_at": utc_now(), "artifacts": results}


def benchmark_artifact(
    artifact: dict[str, Any],
    output_dir: Path | None,
    prompt: str,
    num_predict: int,
    num_ctx: int,
    think: bool = False,
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
            "think": think,
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
    done_reason = response.get("done_reason")
    reasoning_markup = bool(re.search(r"</?think(?:\s[^>]*)?>", output, re.IGNORECASE))
    final_after_reasoning = False
    if reasoning_markup:
        closing_tags = list(re.finditer(r"</think\s*>", output, re.IGNORECASE))
        final_after_reasoning = bool(
            closing_tags and output[closing_tags[-1].end() :].strip()
        )
    final_response_complete = bool(
        output.strip()
        and done_reason == "stop"
        and (not reasoning_markup or final_after_reasoning)
    )
    accepted = final_response_complete and (think or not reasoning_markup)
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
        "think": think,
        "done_reason": done_reason,
        "reasoning_markup_detected": reasoning_markup,
        "reasoning_suppression_honored": None if think else not reasoning_markup,
        "final_response_complete": final_response_complete,
        "accepted": accepted,
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


def validate_homebrew_ollama_service(
    path: Path, payload: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    reject_symlink_components(path.parent, path)
    if path.stat().st_uid != os.getuid():
        raise LocalModelError("Homebrew Ollama service is not owned by the current user")
    if payload.get("Label") != HOMEBREW_OLLAMA_LABEL:
        raise LocalModelError("Unexpected Homebrew Ollama service label")
    arguments = payload.get("ProgramArguments")
    if (
        not isinstance(arguments, list)
        or len(arguments) != 2
        or not isinstance(arguments[0], str)
        or Path(arguments[0]).name != "ollama"
        or arguments[1] != "serve"
    ):
        raise LocalModelError("Unexpected Homebrew Ollama service command")
    environment = payload.get("EnvironmentVariables", {})
    if not isinstance(environment, dict):
        raise LocalModelError("Homebrew Ollama service environment is malformed")
    return arguments, dict(environment)


def wait_for_ollama_api(timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = api_json("/api/version", timeout=2)
            if isinstance(response, dict) and response.get("version"):
                return True
        except LocalModelError:
            pass
        time.sleep(0.25)
    return False


def configure_homebrew_ollama(
    kv_cache_type: str,
    execute: bool,
    state_dir: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    waiter: Callable[[], bool] = wait_for_ollama_api,
) -> dict[str, Any]:
    if platform.system() != "Darwin":
        raise LocalModelError("Homebrew Ollama service configuration is macOS-only")
    if kv_cache_type not in OLLAMA_KV_CACHE_TYPES:
        raise LocalModelError(
            "kv-cache-type must be one of: " + ", ".join(sorted(OLLAMA_KV_CACHE_TYPES))
        )
    service = macos_homebrew_ollama_service()
    if service is None:
        raise LocalModelError("Standard Homebrew Ollama LaunchAgent was not found")
    plist_path, payload = service
    _, environment = validate_homebrew_ollama_service(plist_path, payload)
    current = str(environment.get("OLLAMA_KV_CACHE_TYPE") or "f16")
    plan = {
        "schema_version": 1,
        "execute": execute,
        "service": HOMEBREW_OLLAMA_LABEL,
        "service_path": display_path(plist_path),
        "current_kv_cache_type": current,
        "desired_kv_cache_type": kv_cache_type,
        "changed": current != kv_cache_type,
        "authorization_required": not execute and current != kv_cache_type,
    }
    if not execute or current == kv_cache_type:
        return plan

    original = plist_path.read_bytes()
    original_mode = plist_path.stat().st_mode & 0o777
    backup_name = (
        "homebrew.mxcl.ollama."
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + ".plist"
    )
    backup_path = state_dir.expanduser() / "backups" / backup_name
    atomic_bytes_write(backup_path, original, 0o600)

    updated = plistlib.loads(original)
    updated_environment = dict(updated.get("EnvironmentVariables", {}))
    updated_environment["OLLAMA_KV_CACHE_TYPE"] = kv_cache_type
    updated["EnvironmentVariables"] = updated_environment
    updated_bytes = plistlib.dumps(updated, fmt=plistlib.FMT_XML, sort_keys=True)
    domain = f"gui/{os.getuid()}"

    def launchctl(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return runner(
            ["launchctl", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )

    def restore_original() -> subprocess.CompletedProcess[str]:
        launchctl(["bootout", domain, str(plist_path)])
        atomic_bytes_write(plist_path, original, original_mode)
        return launchctl(["bootstrap", domain, str(plist_path)])

    atomic_bytes_write(plist_path, updated_bytes, original_mode)
    bootout = launchctl(["bootout", domain, str(plist_path)])
    if bootout.returncode != 0:
        atomic_bytes_write(plist_path, original, original_mode)
        raise LocalModelError(
            "Could not unload the Homebrew Ollama service; restored its plist: "
            + (bootout.stderr.strip() or bootout.stdout.strip() or "unknown launchctl error")
        )
    bootstrap = launchctl(["bootstrap", domain, str(plist_path)])
    if bootstrap.returncode != 0:
        restored = restore_original()
        if restored.returncode != 0:
            raise LocalModelError(
                "Could not reload Ollama or restart the restored service; manual service "
                "recovery is required. Initial error: "
                + (bootstrap.stderr.strip() or bootstrap.stdout.strip() or "unknown")
                + "; restore error: "
                + (restored.stderr.strip() or restored.stdout.strip() or "unknown")
            )
        raise LocalModelError(
            "Could not reload the Homebrew Ollama service; restored its prior configuration: "
            + (bootstrap.stderr.strip() or bootstrap.stdout.strip() or "unknown launchctl error")
        )
    if not waiter():
        restored = restore_original()
        if restored.returncode != 0 or not waiter():
            raise LocalModelError(
                "Ollama did not become healthy and the restored service did not recover; "
                "manual service recovery is required"
            )
        raise LocalModelError(
            "Ollama did not become healthy after reload; restored its prior configuration"
        )
    plan.update(
        {
            "applied_at": utc_now(),
            "backup_path": display_path(backup_path),
            "authorization_required": False,
            "runtime_healthy": True,
        }
    )
    return plan


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

    runtimes_parser = commands.add_parser(
        "runtimes", help="Show managed and direct runtime choices and capabilities"
    )
    add_common(runtimes_parser)

    catalog_parser = commands.add_parser("catalog", help="Validate and summarize the model catalog")
    add_common(catalog_parser)

    recommend_parser = commands.add_parser("recommend", help="Recommend one fitting artifact per family")
    add_common(recommend_parser)
    recommend_parser.add_argument(
        "--runtime", choices=sorted(MANAGED_RUNTIMES), default="ollama"
    )

    install_parser = commands.add_parser("install", help="Plan or execute approved model installation")
    add_common(install_parser)
    install_parser.add_argument(
        "--runtime", choices=sorted(MANAGED_RUNTIMES), default="ollama"
    )
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
    verify_parser.add_argument(
        "--runtime", choices=sorted(MANAGED_RUNTIMES), default="ollama"
    )
    verify_parser.add_argument("--artifact", action="append", required=True)

    update_parser = commands.add_parser(
        "update", help="Plan or execute a verified update of installed models"
    )
    add_common(update_parser)
    update_parser.add_argument(
        "--runtime", choices=sorted(MANAGED_RUNTIMES), default="ollama"
    )
    update_scope = update_parser.add_mutually_exclusive_group(required=True)
    update_scope.add_argument("--model", action="append", default=[])
    update_scope.add_argument("--all", action="store_true")
    update_parser.add_argument("--yes", action="store_true")
    update_parser.add_argument("--receipt-dir", type=Path)

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
    benchmark_parser.add_argument(
        "--think",
        action="store_true",
        help="Include model reasoning when the reasoning trace is the benchmark workload",
    )
    configure_parser = commands.add_parser(
        "configure-ollama",
        help="Plan or apply a validated Homebrew Ollama KV-cache setting",
    )
    add_common(configure_parser)
    configure_parser.add_argument(
        "--kv-cache-type", choices=sorted(OLLAMA_KV_CACHE_TYPES), required=True
    )
    configure_parser.add_argument("--yes", action="store_true")
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
        if args.command == "runtimes":
            emit(runtime_summary(profile))
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
                    "managed_runtimes": sorted(MANAGED_RUNTIMES),
                    "runtime_target_counts": {
                        runtime_name: sum(
                            runtime_target(artifact, runtime_name) is not None
                            for artifact in artifacts
                        )
                        for runtime_name in sorted(MANAGED_RUNTIMES)
                    },
                    "status": "valid",
                }
            )
            return 0
        if args.command == "configure-ollama":
            emit(
                configure_homebrew_ollama(
                    args.kv_cache_type,
                    args.yes,
                    args.state_dir.expanduser(),
                )
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
        if args.command == "update":
            update_plan = plan_model_updates(
                args.runtime, args.model, args.all
            )
            if not args.yes:
                emit(update_plan)
                return 0
            receipt = perform_ollama_updates(
                update_plan,
                args.state_dir.expanduser(),
                args.receipt_dir,
            )
            emit({"execute": True, **receipt})
            return 0 if receipt["success"] else 2
        selected_runtime = getattr(args, "runtime", "ollama")
        plan = recommend(artifacts, profile, policy, selected_runtime)
        if args.command == "recommend":
            emit(plan)
            return 0 if plan["ready"] else 2
        if args.command == "install":
            if args.artifact:
                plan = plan_explicit(
                    artifacts, args.artifact, profile, policy, selected_runtime
                )
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
            result = verify_artifacts(
                args.artifact, artifacts, profile, selected_runtime
            )
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
            receipt = benchmark_artifact(
                artifact,
                args.output_dir,
                prompt,
                args.num_predict,
                args.num_ctx,
                think=args.think,
            )
            emit(receipt)
            return 0 if receipt["accepted"] else 2
        raise LocalModelError(f"Unknown command: {args.command}")
    except LocalModelError as exc:
        emit({"error": str(exc), "status": "blocked"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
