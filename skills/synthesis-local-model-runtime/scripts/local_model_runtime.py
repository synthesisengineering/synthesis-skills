#!/usr/bin/env python3
"""Fit open-weight models to this computer; install and update them through Ollama or LM Studio.

Every command prints JSON. Exit 0: done, or the plan is ready. Exit 1: `catalog` is valid but
stale (verified more than three months ago). Exit 2: blocked, invalid or failed.
Nothing is downloaded, installed or reconfigured without --yes.
"""

from __future__ import annotations

import argparse
import calendar
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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

Json = Dict[str, Any]
SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = SKILL_ROOT / "assets" / "model_catalog.json"
DEFAULT_STATE_DIR = Path.home() / ".synthesis" / "local-models"
OLLAMA_API = "http://127.0.0.1:11434"
HOMEBREW_LABEL = "homebrew.mxcl.ollama"
KV_CACHE_TYPES = ("f16", "q4_0", "q8_0")
GIB = 1024**3
STALE_AFTER_MONTHS = 3
STALE_WARNING = "catalog is stale: re-verify its artifacts (references/catalog-maintenance.md) before relying on them"
RUNNER = subprocess.run  # every runtime CLI runs through this as an argument list; tests replace it with a fake
FORBIDDEN_KEYS = "serial uuid udid hostname host_name user_name account provisioning ip_address mac_address".split()
UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
NAME_RE = r"[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9][A-Za-z0-9._-]*)?"
_CAPABILITIES = "recommend install inventory verify update execute serve configuration".split()
RUNTIMES = {  # (capabilities, guidance): a command runs only where the selected adapter marks it true
    "ollama": ({"mode": "managed", **dict.fromkeys(_CAPABILITIES, True)},
               "Default: scriptable install, inventory, digest verification, updates and service configuration."),
    "lm_studio": ({"mode": "managed", **dict.fromkeys(_CAPABILITIES, True), "update": False, "configuration": False},
                  "Optional managed choice: exact catalog downloads and JSON inventory. Its CLI exposes no stable "
                  "content identity, so a re-download is never reported as a verified update."),
    "llama_cpp": ({"mode": "direct", **dict.fromkeys(_CAPABILITIES, False), "execute": True, "serve": True},
                  "Direct GGUF execution and serving; model acquisition and lifecycle stay with the caller."),
    "mlx_lm": ({"mode": "direct", **dict.fromkeys(_CAPABILITIES, False), "execute": True, "serve": True},
               "Direct Apple-silicon-native execution and serving; the Hugging Face cache is not a managed registry."),
}
DEFAULT_POLICY: Json = {
    "schema_version": 1, "required_families": [], "excluded_families": [], "excluded_organizations": [],
    "excluded_base_families": [], "excluded_artifacts": [], "artifact_overrides": {},
    "allow_minimum_memory_fit": False, "memory_headroom_gib": 16, "minimum_free_disk_after_install_gib": 40,
    "planning_context_tokens": 32768, "protected_roots": []}
ARTIFACT_FIELDS = set("""id family organization upstream_model base_family runtime runtime_model distribution_channel
    artifact_publisher upstream_source_url artifact_source_url license quantization total_parameters_billion
    active_parameters_billion disk_gib minimum_memory_gib recommended_memory_gib planning_context_tokens
    minimum_runtime_version quality_rank roles expected_digest_prefix status""".split())
POSITIVE = ("total_parameters_billion", "active_parameters_billion", "disk_gib", "minimum_memory_gib",
            "recommended_memory_gib", "planning_context_tokens", "quality_rank")


class LocalModelError(RuntimeError):
    """A refusal or failure the user should see."""


def need(condition: Any, message: str) -> None:
    if not condition:
        raise LocalModelError(message)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def load_json(path: Path) -> Json:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalModelError(f"Cannot read JSON {path}: {exc}") from exc
    need(isinstance(value, dict), f"Expected a JSON object in {path}")
    return value


def write_private(path: Path, data: bytes, mode: int = 0o600) -> None:
    """Atomic write that refuses to follow a symlinked file or directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    need(not path.is_symlink() and not path.parent.is_symlink(), f"Refusing to write through a symlink: {path}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: Json) -> None:
    write_private(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))


def probe(argv: List[str], timeout: int = 8) -> Optional[str]:
    """A read-only command's stdout and stderr together, or None when it cannot run."""
    try:
        result = RUNNER(argv, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip() or None


def act(argv: List[str], timeout: int = 7200) -> int:
    """Run a runtime CLI, never through a shell; its progress goes to stderr so stdout stays JSON."""
    try:
        return RUNNER(argv, check=False, stdin=subprocess.DEVNULL, stdout=sys.stderr, timeout=timeout).returncode
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return -1


def version(text: Optional[str]) -> Optional[str]:
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)", text or "")
    return ".".join(match.groups()) if match else None


def at_least(current: Optional[str], minimum: str) -> bool:
    have, want = version(current), version(minimum)
    return bool(have and want and [int(x) for x in have.split(".")] >= [int(x) for x in want.split(".")])


def display(path: Path) -> str:
    """A path for output, home-relative so no account name appears."""
    resolved = Path(path).expanduser().resolve(strict=False)
    try:
        relative = resolved.relative_to(Path.home().resolve(strict=False)).as_posix()
    except ValueError:
        return str(resolved)
    return "~" if relative == "." else f"~/{relative}"


# --- machine profile: allowlisted facts only; unknown facts stay unknown -----------------------

def homebrew_service(path: Optional[Path] = None) -> Optional[Tuple[Path, Json]]:
    path = path or Path.home() / "Library" / "LaunchAgents" / f"{HOMEBREW_LABEL}.plist"
    try:
        payload = plistlib.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return (path, payload) if isinstance(payload, dict) else None


def service_env() -> Optional[Json]:
    loaded = homebrew_service() if platform.system() == "Darwin" else None
    env = loaded[1].get("EnvironmentVariables") if loaded else None
    return env if isinstance(env, dict) else None


def model_store(explicit: Optional[str]) -> Tuple[Path, str]:
    """Ollama's effective store: --model-store, OLLAMA_MODELS, the Homebrew service, then the default."""
    configured = os.environ.get("OLLAMA_MODELS") or None
    service = (service_env() or {}).get("OLLAMA_MODELS") if not (explicit or configured) else None
    for value, source in ((explicit, "explicit"), (configured, "environment"), (service, "homebrew-service")):
        if isinstance(value, str) and value:
            return Path(value).expanduser(), source
    return Path.home() / ".ollama" / "models", "standard-default"


def check_store(store: Path, extra_roots: List[str]) -> List[str]:
    """Refuse a model store inside iCloud, cloud storage, ~/workspaces, the current repo or a named root."""
    home, top = Path.home(), (probe(["git", "rev-parse", "--show-toplevel"]) or "").splitlines()
    roots = [home / "Library" / "Mobile Documents", home / "Library" / "CloudStorage", home / "workspaces",
             *(Path(item).expanduser() for item in extra_roots)]
    roots += [Path(top[0])] if top and top[0].startswith("/") else []
    roots = list(dict.fromkeys(root.resolve(strict=False) for root in roots))  # resolved: a symlink proves nothing
    resolved = store.expanduser().resolve(strict=False)
    inside = [display(root) for root in roots if resolved == root or root in resolved.parents]
    need(not inside, f"Model store {display(resolved)} is inside protected root(s): {', '.join(inside)}")
    return [display(root) for root in roots]


def memory_bytes() -> Optional[int]:
    system = platform.system()
    if system in ("Darwin", "Windows"):
        output = probe(["sysctl", "-n", "hw.memsize"] if system == "Darwin" else [
            "powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        return int(output) if output and output.isdigit() else None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def profiler(data_type: str, key: str) -> Json:
    """The one mapping that holds `key`; the rest of system_profiler's output (serials, UUIDs) is dropped."""
    def find(value: Any) -> Any:
        if isinstance(value, dict) and key in value:
            return value
        children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
        return next((found for found in map(find, children) if found), None)

    try:
        return find(json.loads(probe(["system_profiler", data_type, "-json"], 15) or "{}")) or {}
    except json.JSONDecodeError:
        return {}


def hardware() -> Tuple[Json, Json]:
    if platform.system() != "Darwin":
        brand = platform.processor() or platform.machine() or "unknown"
        return ({"brand": brand, "physical_cores": None, "logical_cores": os.cpu_count(), "performance_cores": None,
                 "efficiency_cores": None}, {"gpu": {"name": "unknown", "cores": None}, "npu": {"name": "unknown"}})

    def sysctl(name: str) -> Optional[int]:
        output = probe(["sysctl", "-n", name])
        return int(output) if output and output.isdigit() else None

    chip = str(profiler("SPHardwareDataType", "chip_type").get("chip_type") or platform.processor() or "unknown")
    graphics = profiler("SPDisplaysDataType", "sppci_model")
    cores = re.search(r"\d+", str(graphics.get("sppci_cores") or ""))
    cpu = {"brand": chip, "physical_cores": sysctl("hw.physicalcpu"), "logical_cores": sysctl("hw.logicalcpu"),
           "performance_cores": sysctl("hw.perflevel0.physicalcpu"),
           "efficiency_cores": sysctl("hw.perflevel1.physicalcpu")}
    return cpu, {"gpu": {"name": str(graphics.get("sppci_model") or chip), "cores": int(cores.group()) if cores else None},
                 "npu": {"name": "Apple Neural Engine" if "Apple" in chip else "unknown"}}


def api(path: str, timeout: int = 5) -> Any:
    """GET from the loopback Ollama API; no prompt or request ever goes to a remote host."""
    try:
        with urllib.request.urlopen(OLLAMA_API + path, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # keep a bounded error body: enough to diagnose, never unbounded
        detail = exc.read().decode("utf-8", "replace").strip()[:2000]
        raise LocalModelError(f"Ollama API returned HTTP {exc.code} for {path}: {detail}") from exc
    except (OSError, ValueError) as exc:
        raise LocalModelError(f"Ollama loopback API unavailable for {path}: {exc}") from exc


def api_version(timeout: int = 2) -> Optional[str]:
    try:
        response = api("/api/version", timeout)
    except LocalModelError:
        return None
    return version(str(response.get("version"))) if isinstance(response, dict) else None


def runtimes() -> Dict[str, Json]:
    def find(*names: str) -> Optional[str]:
        return next((path for path in map(shutil.which, names) if path), None)

    found = {"ollama": find("ollama"), "lm_studio": find("lms"), "llama_cpp": find("llama-cli", "llama-server"),
             "mlx_lm": find("mlx_lm.generate", "mlx_lm.server")}
    result = {name: {"available": bool(path), "capabilities": dict(RUNTIMES[name][0]),
                     "version": version(probe([path, "version" if name == "lm_studio" else "--version"])) if path else None}
              for name, path in found.items()}
    env, served = service_env(), api_version()
    values = env if env is not None else os.environ
    source = "homebrew-service" if env is not None else (
        "process-environment" if os.environ.get("OLLAMA_KV_CACHE_TYPE") else "runtime-default")
    result["ollama"].update(version=served or result["ollama"]["version"], api_reachable=bool(served), configuration={
        "source": source, "kv_cache_type": str(values.get("OLLAMA_KV_CACHE_TYPE") or "f16"),
        "flash_attention": str(values.get("OLLAMA_FLASH_ATTENTION") or "0")})
    return result


def assert_safe(profile: Json) -> None:
    text = json.dumps(profile, sort_keys=True).lower()
    leaked = [key for key in FORBIDDEN_KEYS if f'"{key}"' in text]
    leaked += [phrase for phrase in ("serial number", "hardware uuid", "provisioning udid") if phrase in text]
    need(not leaked and not re.search(UUID_RE, text), "Identifier-like value in the profile; refusing to print it")


def machine_profile(store_flag: Optional[str] = None, extra_roots: Optional[List[str]] = None) -> Json:
    store, source = model_store(store_flag)
    checked, existing = check_store(store, list(extra_roots or [])), store.expanduser().resolve(strict=False)
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    usage, total, (cpu, accelerators) = shutil.disk_usage(existing), memory_bytes(), hardware()
    mac = platform.system() == "Darwin"
    profile = {
        "schema_version": 1, "captured_at": now(), "cpu": cpu, "accelerators": accelerators,
        "operating_system": {"name": platform.system(), "architecture": platform.machine(),
                             "version": platform.mac_ver()[0] if mac else platform.release()},
        "memory": {"total_gib": round(total / GIB, 2) if total else None,
                   "unified": mac and platform.machine() == "arm64"},
        "storage": {"model_store": display(store), "model_store_source": source,
                    "free_gib": round(usage.free / GIB, 2), "total_gib": round(usage.total / GIB, 2),
                    "protected_roots_checked": checked},
        "runtimes": runtimes(),
        "privacy": {"unique_hardware_identifiers_collected": False, "hostname_collected": False,
                    "account_data_collected": False}}
    assert_safe(profile)
    return profile


# --- catalog and policy ------------------------------------------------------------------------

def safe_url(value: Any) -> bool:
    parts = urlsplit(value) if isinstance(value, str) else None
    return bool(parts and parts.scheme == "https" and parts.netloc and not parts.username and not parts.password)


def parse_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def lm_target_ok(spec: Any) -> bool:
    terms = spec.get("match_terms") if isinstance(spec, dict) else None
    return bool(
        isinstance(spec, dict) and set(spec) == {"model", "format", "match_terms", "artifact_publisher", "artifact_source_url"}
        and safe_url(spec["model"]) and spec["model"].startswith("https://huggingface.co/")
        and safe_url(spec["artifact_source_url"]) and spec["format"] in ("gguf", "mlx")
        and isinstance(spec["artifact_publisher"], str) and spec["artifact_publisher"]
        and isinstance(terms, list) and len(terms) >= 2
        and all(isinstance(term, str) and re.fullmatch(r"[a-z0-9._/-]+", term) for term in terms))


def validate_catalog(catalog: Json) -> List[Json]:
    artifacts, seen = catalog.get("artifacts"), set()
    need(catalog.get("schema_version") == 2 and parse_date(catalog.get("verified_on")) and isinstance(artifacts, list)
         and artifacts, "Catalog needs schema_version 2, an ISO verified_on date and a non-empty artifacts list")
    for item in artifacts:
        need(isinstance(item, dict) and ARTIFACT_FIELDS <= set(item), f"Catalog artifact lacks fields: {item!r:.80}")
        aid, targets, kv = item["id"], item.get("runtime_targets", {}), item.get("runtime_requirements")
        need(isinstance(aid, str) and re.fullmatch(r"[a-z0-9][a-z0-9.-]*", aid) and aid not in seen,
             f"Invalid or duplicate artifact id {aid!r}")
        seen.add(aid)
        need(item["runtime"] == "ollama" and isinstance(item["runtime_model"], str)
             and not re.search(r"\s|://|@", item["runtime_model"])
             and safe_url(item["upstream_source_url"]) and safe_url(item["artifact_source_url"]),
             f"{aid}: unsafe runtime model, or a source URL that is not credential-free HTTPS")
        need(all(type(item[field]) in (int, float) and item[field] > 0 for field in POSITIVE)
             and item["active_parameters_billion"] <= item["total_parameters_billion"]
             and item["minimum_memory_gib"] <= item["recommended_memory_gib"]
             and version(str(item["minimum_runtime_version"])) and item["status"] in ("verified", "retired"),
             f"{aid}: sizes and ranks must be positive, active <= total parameters, minimum <= recommended "
             "memory, the minimum runtime version dotted, and the status verified or retired")
        digest = item["expected_digest_prefix"]
        need((digest is None or re.fullmatch(r"[0-9a-f]{12,64}", str(digest))) and isinstance(item["roles"], list)
             and all(isinstance(role, str) and role for role in item["roles"]), f"{aid}: invalid digest prefix or roles")
        need(isinstance(targets, dict) and set(targets) <= {"lm_studio"}
             and ("lm_studio" not in targets or lm_target_ok(targets["lm_studio"])),
             f"{aid}: an LM Studio target needs exactly a huggingface.co model, gguf or mlx format, a publisher, "
             "a source URL and at least two safe lowercase match terms (one generic term such as q8_0 matches too much)")
        cache_types = kv.get("ollama_kv_cache_types") if isinstance(kv, dict) else None
        need(kv is None or (set(kv) == {"ollama_kv_cache_types"} and isinstance(cache_types, list) and cache_types
                            and set(cache_types) <= set(KV_CACHE_TYPES)),
             f"{aid}: runtime_requirements may only list supported ollama_kv_cache_types")
    return artifacts


def freshness(catalog: Json, today: Optional[date] = None) -> Json:
    """R9.3's three-month rule: stale once today is past verified_on plus three calendar months."""
    verified = parse_date(catalog.get("verified_on")) or date.min
    month = verified.month - 1 + STALE_AFTER_MONTHS
    year, month = verified.year + month // 12, month % 12 + 1
    limit, today = date(year, month, min(verified.day, calendar.monthrange(year, month)[1])), today or date.today()
    return {"verified_on": verified.isoformat(), "stale_after": limit.isoformat(),
            "age_days": (today - verified).days, "stale": today > limit}


def load_policy(path: Optional[Path]) -> Json:
    supplied = load_json(path) if path else {}
    unknown = sorted(set(supplied) - set(DEFAULT_POLICY))
    need(not unknown, f"Unknown policy fields: {', '.join(unknown)}")
    policy = {**DEFAULT_POLICY, **supplied}
    lists = [field for field, value in DEFAULT_POLICY.items() if isinstance(value, list)]
    numbers = ("memory_headroom_gib", "minimum_free_disk_after_install_gib", "planning_context_tokens")
    need(policy["schema_version"] == 1 and isinstance(policy["artifact_overrides"], dict)
         and isinstance(policy["allow_minimum_memory_fit"], bool)
         and all(isinstance(policy[f], list) and all(isinstance(i, str) for i in policy[f]) for f in lists)
         and all(type(policy[f]) in (int, float) and policy[f] >= 0 for f in numbers),
         "Policy needs schema_version 1, string lists, an overrides object, a boolean minimum-fit flag and "
         "non-negative headroom, disk reserve and context numbers (see assets/policy.example.json)")
    return policy


# --- recommendation: exclusions, then memory, context, runtime and disk gates, then quality ------

def target(artifact: Json, runtime: str) -> Optional[Json]:
    if runtime == "ollama":
        return {"model": artifact["runtime_model"], "minimum_version": artifact["minimum_runtime_version"],
                "artifact_publisher": artifact["artifact_publisher"]}
    return (artifact.get("runtime_targets") or {}).get(runtime)


def excluded(artifact: Json, policy: Json) -> List[str]:
    """Policy exclusions apply before fit and ranking; an explicit request cannot bypass them (E85)."""
    reasons = ["artifact is retired in the catalog"] if artifact["status"] != "verified" else []
    reasons += ["artifact is excluded by policy"] if artifact["id"] in policy["excluded_artifacts"] else []
    for field, key in (("family", "excluded_families"), ("organization", "excluded_organizations"),
                       ("base_family", "excluded_base_families")):
        if artifact[field].casefold() in {value.casefold() for value in policy[key]}:
            reasons.append(f"{field.replace('_', ' ')} {artifact[field]} is excluded by policy")
    return reasons


def fit(artifact: Json, profile: Json, policy: Json, runtime: str) -> Tuple[str, List[str], Optional[float]]:
    """Weights must fit with operating and context headroom; disk fit alone is never enough."""
    memory, blockers = (profile.get("memory") or {}).get("total_gib"), []
    effective = max(0.0, float(memory) - float(policy["memory_headroom_gib"])) if type(memory) in (int, float) else None
    if effective is not None and effective >= artifact["recommended_memory_gib"]:
        level = "recommended"
    elif effective is not None and effective >= artifact["minimum_memory_gib"] and policy["allow_minimum_memory_fit"]:
        level = "constrained"
    else:
        level = "blocked"
        blockers.append("system memory is unknown" if effective is None else
                        f"needs {artifact['recommended_memory_gib']} GiB recommended ({artifact['minimum_memory_gib']} "
                        f"GiB minimum) after {policy['memory_headroom_gib']} GiB headroom; {effective:.2f} GiB available")
    if policy["planning_context_tokens"] > artifact["planning_context_tokens"]:
        blockers.append(f"policy context of {policy['planning_context_tokens']} tokens exceeds the catalog's "
                        f"{artifact['planning_context_tokens']}-token memory sizing; that needs fresh evidence")
    spec, state = target(artifact, runtime), (profile.get("runtimes") or {}).get(runtime) or {}
    blockers += [f"artifact has no verified {runtime} catalog target"] if spec is None else []
    if not state.get("available"):
        blockers.append(f"runtime {runtime} is not installed")
    elif spec and spec.get("minimum_version") and not at_least(state.get("version"), spec["minimum_version"]):
        blockers.append(f"runtime {runtime} {state.get('version') or 'unknown'} is below {spec['minimum_version']}")
    needed = (artifact.get("runtime_requirements") or {}).get("ollama_kv_cache_types") if runtime == "ollama" else None
    current = (state.get("configuration") or {}).get("kv_cache_type")
    if needed and current not in needed:
        blockers.append(f"runtime ollama KV cache is {current or 'unknown'}; artifact requires one of {', '.join(needed)}")
    return level, blockers, effective


def plan(artifacts: List[Json], profile: Json, policy: Json, runtime: str = "ollama",
         ids: Optional[List[str]] = None) -> Json:
    by_id, chosen, blockers, failures = {a["id"]: a for a in artifacts}, [], [], {}
    if ids:
        need(len(ids) == len(set(ids)) and all(aid in by_id for aid in ids), f"Artifact ids must be unique catalog ids: {ids}")
        for aid in ids:
            level, problems, effective = fit(by_id[aid], profile, policy, runtime)
            blockers += [f"{aid}: {reason}" for reason in excluded(by_id[aid], policy) + problems]
            chosen.append((by_id[aid], level, effective))
    else:
        for family in policy["required_families"] or sorted({a["family"] for a in artifacts if not excluded(a, policy)}):
            candidates = [a for a in artifacts if a["family"] == family and not excluded(a, policy)]
            override = policy["artifact_overrides"].get(family)
            if override and by_id.get(override) not in candidates:
                failures[family] = [f"override {override} is unknown, excluded, retired or in another family"]
                continue
            evaluated = [(a, *fit(a, profile, policy, runtime)) for a in ([by_id[override]] if override else candidates)]
            fitting = [(a, level, effective) for a, level, problems, effective in evaluated if not problems]
            if fitting:  # quality first, then curated runtime artifacts, then the larger artifact
                chosen.append(max(fitting, key=lambda c: (c[0]["quality_rank"],
                                                          c[0]["distribution_channel"] == "ollama-curated", c[0]["disk_gib"])))
            else:
                failures[family] = [f"{a['id']}: {'; '.join(p)}" for a, _, p, _ in evaluated] or [
                    "no artifact remains after policy exclusions"]
        blockers += [reason for reasons in failures.values() for reason in reasons]
    selections = [{
        "artifact_id": a["id"], "family": a["family"], "runtime": runtime, "fit": level, "roles": a["roles"],
        "runtime_model": (target(a, runtime) or {}).get("model"), "quantization": a["quantization"],
        "distribution_channel": a["distribution_channel"], "artifact_publisher": (target(a, runtime) or a)["artifact_publisher"],
        "disk_gib": a["disk_gib"], "effective_memory_gib": None if effective is None else round(effective, 2),
        "minimum_runtime_version": a["minimum_runtime_version"], "runtime_requirements": a.get("runtime_requirements", {}),
    } for a, level, effective in chosen]
    total, free = round(sum(float(s["disk_gib"]) for s in selections), 2), (profile.get("storage") or {}).get("free_gib")
    remaining = round(float(free) - total, 2) if type(free) in (int, float) else None
    reserve = float(policy["minimum_free_disk_after_install_gib"])
    if remaining is None or remaining < reserve:  # every artifact of the plan counts, though one loads at a time
        blockers.append("free disk is unknown" if remaining is None else
                        f"plan would leave {remaining:.2f} GiB free; policy requires {reserve:.2f} GiB")
    machine = {"memory_gib": (profile.get("memory") or {}).get("total_gib"), "free_disk_gib": free,
               "model_store": (profile.get("storage") or {}).get("model_store"),
               "selected_runtime_version": ((profile.get("runtimes") or {}).get(runtime) or {}).get("version")}
    return {"schema_version": 1, "generated_at": now(), "runtime": runtime, "machine": machine,
            "planning_context_tokens": policy["planning_context_tokens"], "selections": selections,
            "family_failures": failures, "total_download_gib": total, "estimated_free_disk_after_install_gib": remaining,
            "blockers": blockers, "warnings": [], "ready": not blockers and bool(selections)}


# --- installation and inventory ----------------------------------------------------------------

def ollama_models() -> List[Json]:
    response = api("/api/tags", timeout=8)
    need(isinstance(response, dict) and isinstance(response.get("models"), list), "Ollama /api/tags gave an unexpected reply")
    return [model for model in response["models"] if isinstance(model, dict)]


def norm(name: str) -> str:
    name = name.casefold()
    return name[:-7] if name.endswith(":latest") else name


def installed_model(name: str, models: List[Json]) -> Optional[Json]:
    """Allowlisted metadata of an installed Ollama model; only an implicit :latest tag is normalized."""
    for model in models:
        if any(isinstance(n, str) and norm(n) == norm(name) for n in (model.get("name"), model.get("model"))):
            details = model.get("details") if isinstance(model.get("details"), dict) else {}
            return {"runtime_name": model.get("name") or model.get("model"), "digest": model.get("digest"),
                    "size_bytes": model.get("size"), "modified_at": model.get("modified_at"),
                    **{key: details.get(key) for key in ("format", "family", "parameter_size", "quantization_level")}}
    return None


def install_ollama(artifact: Json, ollama: str) -> Json:
    need(act([ollama, "pull", artifact["runtime_model"]]) == 0, f"Ollama pull failed for {artifact['id']}; nothing "
         "was recorded. Rerun the same install later: Ollama skips the layers it already holds")
    found, expected = installed_model(artifact["runtime_model"], ollama_models()), artifact["expected_digest_prefix"]
    need(found and isinstance(found["digest"], str) and found["digest"] and found["digest"].startswith(expected or ""),
         f"Ollama does not list {artifact['runtime_model']} with a digest matching the catalog prefix {expected}")
    return {**found, "artifact_publisher": artifact["artifact_publisher"], "installation_method": "ollama-pull",
            "distribution_channel": artifact["distribution_channel"]}


def lm_studio_models(lms: str) -> List[Json]:
    try:
        listed = RUNNER([lms, "ls", "--json", "--variants"], check=False, capture_output=True, text=True,
                        stdin=subprocess.DEVNULL, timeout=60)
        payload = json.loads(listed.stdout) if listed.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        payload = None
    need(isinstance(payload, list), "LM Studio inventory (lms ls --json --variants) failed or is not a JSON array")
    models = []
    for item in (entry for entry in payload if isinstance(entry, dict)):
        models.append(item["model"] if isinstance(item.get("model"), dict) else item)
        models += [v for v in item.get("variants") or [] if isinstance(v, dict)] if isinstance(item.get("variants"), list) else []
    return models


def install_lm_studio(artifact: Json, lms: str) -> Json:
    spec = target(artifact, "lm_studio")
    need(spec, f"{artifact['id']} has no verified LM Studio catalog target")
    need(act([lms, "get", spec["model"], "--yes", f"--{spec['format']}"]) == 0, f"LM Studio download failed for {artifact['id']}")
    keys = ("modelKey", "model_key", "path", "displayName", "quantization", "quantizationName")
    matches = [m for m in lm_studio_models(lms) if all(
        term in " ".join(m[k] for k in keys if isinstance(m.get(k), str)).casefold() for term in spec["match_terms"])]
    need(len(matches) == 1, f"LM Studio lists {len(matches)} models matching {artifact['id']}; exactly one is required")
    model = matches[0]
    key = model.get("modelKey") or model.get("model_key") or model.get("path")
    safe = {"runtime_name": Path(key).name if isinstance(key, str) and key.startswith(("/", "~")) else key,
            "size_bytes": model.get("sizeBytes") or model.get("size_bytes"),
            "format": model.get("format") or model.get("compatibilityType"), "family": model.get("architecture"),
            "parameter_size": model.get("paramsString") or model.get("parameterSize"),
            "quantization_level": model.get("quantization") or model.get("quantizationName")}
    need(isinstance(safe["runtime_name"], str) and safe["runtime_name"] and type(safe["size_bytes"]) is int
         and safe["size_bytes"] > 0, "LM Studio inventory entry lacks a safe name or a valid size")
    return {**safe, "identity": hashlib.sha256(json.dumps(safe, sort_keys=True).encode("utf-8")).hexdigest(),
            "identity_strength": "runtime-metadata", "installation_method": "lm-studio-get",
            "artifact_publisher": spec["artifact_publisher"], "artifact_source_url": spec["artifact_source_url"],
            "distribution_channel": f"huggingface-{spec['format']}"}


def machine_id(state_dir: Path) -> str:
    """A random opaque id for this computer, never derived from hardware."""
    path = state_dir / "machine-id"
    if not path.exists() and not path.is_symlink():
        state_dir.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as stream:
            stream.write(f"{uuid.uuid4()}\n")
    need(path.is_file() and not path.is_symlink() and not state_dir.is_symlink(), f"Unsafe machine id path: {display(path)}")
    try:
        return str(uuid.UUID(path.read_text(encoding="utf-8").strip()))
    except ValueError as exc:
        raise LocalModelError(f"Invalid opaque machine id in {display(path)}") from exc


def record_install(state_dir: Path, profile: Json, selections: List[Json], aid: str, entry: Json,
                   label: Optional[str]) -> None:
    """Merge one verified installation into this machine's record; earlier verified selections survive."""
    path, identifier = state_dir / "machines.json", machine_id(state_dir)
    inventory = load_json(path) if path.exists() else {"schema_version": 1, "machines": {}}
    need(inventory.get("schema_version") == 1 and isinstance(inventory.get("machines"), dict), "Malformed inventory")
    previous = inventory["machines"].get(identifier) or {}
    inventory["machines"][identifier] = {
        "label": previous.get("label") if label is None else label, "updated_at": now(), "profile": profile,
        "selections": list(dict.fromkeys([*previous.get("selections", []), *(s["artifact_id"] for s in selections)])),
        "installed": {**previous.get("installed", {}), aid: entry}}
    inventory["updated_at"] = now()
    write_json(path, inventory)


def install(result: Json, artifacts: List[Json], profile: Json, state_dir: Path, label: Optional[str] = None) -> Json:
    runtime = result["runtime"]
    need(result["ready"], "Installation plan is blocked: " + "; ".join(result["blockers"]))
    executable = shutil.which("ollama" if runtime == "ollama" else "lms")
    need(executable, f"The {runtime} command-line tool is not installed")
    by_id, installed = {a["id"]: a for a in artifacts}, {}
    for selection in result["selections"]:  # a failure stops here, before that artifact reaches the inventory (E86)
        artifact = by_id[selection["artifact_id"]]
        entry = install_ollama(artifact, executable) if runtime == "ollama" else install_lm_studio(artifact, executable)
        entry.update(catalog_id=artifact["id"], upstream_model=artifact["upstream_model"], verified_at=now(),
                     runtime=runtime, runtime_version=profile["runtimes"][runtime].get("version"))
        record_install(state_dir, profile, result["selections"], artifact["id"], entry, label)
        installed[artifact["id"]] = entry
    return {"installed": installed, "inventory": display(state_dir / "machines.json")}


# --- updates and service configuration ---------------------------------------------------------

def plan_update(runtime: str, names: List[str], update_all: bool, models: Optional[List[Json]] = None) -> Json:
    need(runtime == "ollama", "LM Studio model updates are blocked: its CLI exposes no stable content identity "
         "that could prove an update replaced the installed model")
    models = ollama_models() if models is None else models
    listed = {m.get("name") or m.get("model") for m in models} - {None, ""}
    requested = sorted((n for n in listed if isinstance(n, str)), key=str.casefold) if update_all else list(names)
    need(requested and len({norm(n) for n in requested}) == len(requested), "Choose unique installed model names, or --all")
    planned = []
    for name in requested:
        before = installed_model(name, models) if re.fullmatch(NAME_RE, name) else None
        need(before, f"Not an installed Ollama model name: {name!r}")
        need(isinstance(before["digest"], str) and before["digest"] and type(before["size_bytes"]) is int
             and re.fullmatch(NAME_RE, str(before["runtime_name"])), f"Ollama gave no usable name, digest or size for {name}")
        planned.append({"runtime_name": before["runtime_name"], "action": "ollama pull", "before": before})
    return {"schema_version": 1, "generated_at": now(), "runtime": "ollama", "execute": False,
            "authorization_required": True, "scope": "all-installed" if update_all else "explicit", "models": planned}


def run_update(update_plan: Json, receipt_dir: Optional[Path] = None) -> Json:
    """Pull each planned model, list it again, and compare digest and size before and after."""
    ollama, results = shutil.which("ollama"), []
    need(ollama, "Ollama executable is not installed")
    for item in update_plan["models"]:
        code, before = act([ollama, "pull", item["runtime_name"]]), item["before"]
        try:
            after = installed_model(item["runtime_name"], ollama_models()) if code == 0 else None
        except LocalModelError:
            after = None
        result = {"runtime_name": item["runtime_name"], "checked_at": now(), "changed": False, "before": before,
                  "exit_code": code, "status": "failed" if code != 0 else "failed-verification"}
        if after and after.get("digest"):  # a model missing after its pull is a failure, never an assumed success
            changed = (before["digest"], before["size_bytes"]) != (after["digest"], after["size_bytes"])
            result.update(status="updated" if changed else "already-current", changed=changed, after=after)
        results.append(result)
        if "after" not in result:
            break
    receipt = {"schema_version": 1, "created_at": now(), "execute": True, "runtime": "ollama", "models": results,
               "scope": update_plan["scope"],
               "success": len(results) == len(update_plan["models"]) and all("after" in r for r in results)}
    if receipt_dir is not None:
        destination = Path(receipt_dir).expanduser().resolve(strict=False)
        need(destination != SKILL_ROOT and SKILL_ROOT not in destination.parents,
             "Receipt directory cannot be inside the skill source")
        path = destination / f"ollama-update-{stamp()}.json"
        receipt["receipt_path"] = display(path)
        write_json(path, receipt)
    return receipt


def wait_for_api(seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if api_version():
            return True
        time.sleep(0.25)
    return False


def configure_ollama(kv_type: str, execute: bool, state_dir: Path, plist_path: Optional[Path] = None,
                     waiter: Any = None) -> Json:
    """Set OLLAMA_KV_CACHE_TYPE in the current user's Homebrew LaunchAgent: backup, reload, health check, rollback."""
    need(platform.system() == "Darwin", "Homebrew Ollama service configuration is macOS-only")
    path, payload = homebrew_service(plist_path) or (None, {})
    arguments, env = payload.get("ProgramArguments"), payload.get("EnvironmentVariables", {})
    need(path and not path.is_symlink() and path.stat().st_uid == os.getuid() and payload.get("Label") == HOMEBREW_LABEL
         and isinstance(arguments, list) and len(arguments) == 2 and Path(str(arguments[0])).name == "ollama"
         and arguments[1] == "serve" and isinstance(env, dict),
         "Expected the standard Homebrew Ollama LaunchAgent: a regular file you own, its label and `ollama serve`")
    current = str(env.get("OLLAMA_KV_CACHE_TYPE") or "f16")
    result = {"schema_version": 1, "execute": execute, "service": HOMEBREW_LABEL, "service_path": display(path),
              "current_kv_cache_type": current, "desired_kv_cache_type": kv_type, "changed": current != kv_type,
              "authorization_required": not execute and current != kv_type}
    if not execute or current == kv_type:
        return result
    original, mode = path.read_bytes(), path.stat().st_mode & 0o777
    backup = state_dir / "backups" / f"{HOMEBREW_LABEL}.{stamp()}.plist"
    write_private(backup, original)
    write_private(path, plistlib.dumps(dict(payload, EnvironmentVariables=dict(env, OLLAMA_KV_CACHE_TYPE=kv_type))), mode)
    healthy = waiter or wait_for_api

    def launchctl(verb: str) -> int:
        return act(["launchctl", verb, f"gui/{os.getuid()}", str(path)], timeout=30)

    if launchctl("bootout") != 0:
        write_private(path, original, mode)
        raise LocalModelError("Could not unload the Homebrew Ollama service; restored its plist")
    if launchctl("bootstrap") == 0 and healthy():
        return dict(result, applied_at=now(), backup_path=display(backup), authorization_required=False,
                    runtime_healthy=True)
    launchctl("bootout")
    write_private(path, original, mode)
    recovered = launchctl("bootstrap") == 0 and healthy()
    raise LocalModelError("Ollama did not reload healthily; restored its prior configuration" + (
        "" if recovered else ", but the restored service did not recover: manual recovery is required"))


# --- command line ------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name: str, text: str, runtime: bool = False, yes: bool = False) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=text, description=text)
        sub.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
        sub.add_argument("--policy", type=Path, help="local policy JSON (see assets/policy.example.json)")
        sub.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR, help="inventory and service backups")
        sub.add_argument("--model-store", help="Ollama model store, when it cannot be discovered")
        sub.add_argument("--protected-root", action="append", default=[], help="another path the store must avoid")
        if runtime:
            sub.add_argument("--runtime", choices=("lm_studio", "ollama"), default="ollama")
        if yes:
            sub.add_argument("--yes", action="store_true", help="execute; without it nothing changes")
        return sub

    command("profile", "Print the privacy-safe machine profile")
    command("runtimes", "Show each runtime's availability and what its adapter can prove")
    command("catalog", "Validate the catalog and report its age; exit 1 when stale")
    command("recommend", "Recommend one fitting artifact per family", runtime=True)
    sub = command("install", "Print the installation plan; install only with --yes", runtime=True, yes=True)
    sub.add_argument("--artifact", action="append", default=[], help="exact catalog id instead of policy selections")
    sub.add_argument("--machine-label", help="optional friendly label; no organization or client names")
    sub = command("update", "Print the update plan for installed Ollama models; pull only with --yes",
                  runtime=True, yes=True)
    scope = sub.add_mutually_exclusive_group(required=True)
    scope.add_argument("--model", action="append", default=[], help="exact installed name, as `ollama list` shows it")
    scope.add_argument("--all", action="store_true", help="every installed Ollama model; never the default")
    sub.add_argument("--receipt-dir", type=Path, help="also save the result JSON here (outside the skill)")
    sub = command("configure-ollama", "Print or apply the Homebrew Ollama KV-cache setting", yes=True)
    sub.add_argument("--kv-cache-type", choices=KV_CACHE_TYPES, required=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_json(args.catalog)
        artifacts, fresh = validate_catalog(catalog), freshness(catalog)
        if args.command == "catalog":
            emit({"status": "stale" if fresh["stale"] else "valid", "valid": True, **fresh,
                  "schema_version": catalog["schema_version"], "catalog_version": catalog.get("catalog_version"),
                  "artifact_count": len(artifacts), "families": sorted({a["family"] for a in artifacts
                                                                        if a["status"] == "verified"}),
                  "runtime_target_counts": {r: sum(target(a, r) is not None for a in artifacts)
                                            for r in ("lm_studio", "ollama")},
                  **({"warning": STALE_WARNING} if fresh["stale"] else {})})
            return 1 if fresh["stale"] else 0
        if args.command == "configure-ollama":
            emit(configure_ollama(args.kv_cache_type, args.yes, args.state_dir.expanduser()))
            return 0
        policy = load_policy(args.policy)
        roots = args.protected_root + policy["protected_roots"]
        if args.command == "update":
            update_plan = plan_update(args.runtime, args.model, args.all)
            if args.yes:
                check_store(model_store(args.model_store)[0], roots)
                update_plan = run_update(update_plan, args.receipt_dir)
            emit(update_plan)
            return 0 if update_plan.get("success", True) else 2
        profile = machine_profile(args.model_store, roots)
        if args.command in ("profile", "runtimes"):
            emit(profile if args.command == "profile" else {"default_runtime": "ollama", "runtimes": {
                name: dict(entry, guidance=RUNTIMES[name][1]) for name, entry in profile["runtimes"].items()}})
            return 0
        result = plan(artifacts, profile, policy, args.runtime, args.artifact if args.command == "install" else None)
        result.update(catalog=fresh, warnings=[STALE_WARNING] if fresh["stale"] else [])
        if args.command == "recommend":
            emit(result)
            return 0 if result["ready"] else 2
        if not args.yes:
            emit({"execute": False, "authorization_required": True, "plan": result})
            return 0 if result["ready"] else 2
        emit({"execute": True, "plan": result,
              **install(result, artifacts, profile, args.state_dir.expanduser(), args.machine_label)})
        return 0
    except LocalModelError as exc:
        emit({"error": str(exc), "status": "blocked"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
