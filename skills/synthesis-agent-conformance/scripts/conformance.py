#!/usr/bin/env python3
"""Cross-agent conformance checks for the synthesis ecosystem."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import uuid
from graphlib import CycleError, TopologicalSorter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by dependency health checks
    yaml = None


SCRIPT_PATH = Path(__file__).resolve()
SCRIPTS_DIR = SCRIPT_PATH.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
PROJECT_MANAGEMENT_SCRIPTS_DIR = (
    SCRIPT_PATH.parents[2] / "synthesis-project-management" / "scripts"
)
if str(PROJECT_MANAGEMENT_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_MANAGEMENT_SCRIPTS_DIR))

from client_binaries import missing_binary_detail, resolve_client_binary
from active_project import (
    lease_url,
    load_and_validate,
    sessions as coordination_sessions,
    validate as validate_active_project,
)
from codex_hook_audit import audit as codex_hook_audit
from codex_skill_catalog import audit as codex_skill_catalog_audit
from live_receipt import transcript_binds_session
from project_context import next_actions, record_freshness
from pointer_lock import locked_pointer

DEFAULT_SOURCE_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_ACTIVE_PROJECT = Path.home() / ".synthesis" / "active-project.json"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
)
DEFAULT_PUBLIC_CODEX_SESSIONSTART_RECEIPT = (
    Path.home()
    / ".synthesis"
    / "agent-conformance"
    / "live"
    / "public-sessionstart-codex.json"
)
DEFAULT_PUBLIC_CLAUDE_SESSIONSTART_RECEIPT = (
    Path.home()
    / ".synthesis"
    / "agent-conformance"
    / "live"
    / "public-sessionstart-claude.json"
)
DEFAULT_PRIVATE_CODEX_SESSIONSTART_RECEIPT = (
    Path.home()
    / ".synthesis"
    / "agent-control"
    / "live"
    / "codex-sessionstart.json"
)
DEFAULT_CAPABILITY_EVIDENCE = (
    Path.home()
    / ".synthesis"
    / "agent-conformance"
    / "capabilities.json"
)
COORDINATION_HELPER = (
    SCRIPT_PATH.parents[2]
    / "synthesis-project-management"
    / "scripts"
    / "coordination.py"
)
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CHANGELOG_VERSION_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)
PROMPT_VISIBLE_PUBLIC_SKILLS = {
    "synthesis-agent-conformance",
    "synthesis-anti-shortcuts",
    "synthesis-autopilot",
    "synthesis-checkpoint",
    "synthesis-code-planning",
    "synthesis-context-lifecycle",
    "synthesis-implementation-integrity",
    "synthesis-project-management",
    "synthesis-skill-router",
    "synthesis-thinking-framework",
}


@dataclass
class Check:
    name: str
    ok: bool | None
    detail: str
    required: bool = True
    plane: str = "unspecified"
    outcome: str | None = None

    @property
    def status(self) -> str:
        if self.outcome is not None:
            return self.outcome
        if self.ok is True:
            return "PASS"
        if self.ok is False:
            return "FAIL" if self.required else "WARN"
        return "UNKNOWN"

    def serialized(self) -> dict[str, object]:
        return {**asdict(self), "status": self.status}


PLANE_BY_PREFIX = {
    "source": "source",
    "hook-definition": "source",
    "parity": "installed",
    "runtime": "installed",
    "catalog": "installed",
    "instructions": "installed",
    "instruction-budget": "installed",
    "hook-trust": "installed",
    "coordination": "continuity",
    "pointer": "continuity",
    "handoff": "continuity",
    "hook-live": "live",
    "capability": "capability",
    "surface": "capability",
}


def add(
    checks: list[Check],
    name: str,
    ok: bool | None,
    detail: str,
    required: bool = True,
    *,
    plane: str | None = None,
    outcome: str | None = None,
) -> None:
    prefix = name.split(".", 1)[0]
    checks.append(
        Check(
            name=name,
            ok=ok,
            detail=detail,
            required=required,
            plane=plane or PLANE_BY_PREFIX.get(prefix, "unspecified"),
            outcome=outcome,
        )
    )


def run(
    command: list[str], timeout: int = 30, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        input=input_text,
    )


def json_from_output(output: str) -> object:
    decoder = json.JSONDecoder()
    for position, character in enumerate(output):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(output, position)
        except json.JSONDecodeError:
            continue
        return value
    raise ValueError("command returned no JSON")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json_write(destination: Path, payload: dict[str, object]) -> None:
    """Durably replace a JSON report without shared fixed-temp collisions."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(json.dumps(payload, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, destination)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and item.name not in {".source.json", ".DS_Store"}
    )
    for item in files:
        digest.update(str(item.relative_to(path)).encode())
        digest.update(b"\0")
        digest.update(file_digest(item).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def parse_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening YAML delimiter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError("missing closing YAML delimiter")
    if yaml is not None:
        parsed = yaml.safe_load(parts[1])
        if not isinstance(parsed, dict):
            raise ValueError("YAML frontmatter is not a mapping")
        return parsed

    values: dict[str, object] = {}
    for line in parts[1].splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def source_checks(source_root: Path) -> list[Check]:
    checks: list[Check] = []
    skills_root = source_root / "skills"
    add(checks, "source.skills-root", skills_root.is_dir(), str(skills_root))

    manifests: list[dict[str, object]] = []
    for manifest in (
        source_root / ".codex-plugin" / "plugin.json",
        source_root / ".claude-plugin" / "plugin.json",
    ):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            ok = data.get("name") == "synthesis-skills" and data.get("skills") == "./skills/"
            add(checks, f"source.manifest.{manifest.parent.name}", ok, str(manifest))
            manifests.append(data)
        except Exception as exc:
            add(checks, f"source.manifest.{manifest.parent.name}", False, f"{manifest}: {exc}")

    versions = {str(manifest.get("version")) for manifest in manifests}
    add(checks, "source.manifest-version-parity", len(versions) == 1, ", ".join(sorted(versions)))

    # A release is manifests + CHANGELOG moving together; the repeated miss is
    # bumping one surface and not the other, which every other check passes.
    changelog = source_root / "CHANGELOG.md"
    try:
        match = CHANGELOG_VERSION_RE.search(changelog.read_text(encoding="utf-8"))
        changelog_version = match.group(1) if match else None
        parity = changelog_version is not None and versions == {changelog_version}
        add(
            checks,
            "source.changelog-version-parity",
            parity,
            f"changelog={changelog_version or 'no release heading'}, "
            f"manifests={', '.join(sorted(versions)) or 'none'}",
        )
    except OSError as exc:
        add(checks, "source.changelog-version-parity", False, f"{changelog}: {exc}")

    for config in (
        source_root / ".agents" / "plugins" / "marketplace.json",
        source_root / ".claude-plugin" / "marketplace.json",
        source_root / "hooks" / "hooks.json",
    ):
        try:
            json.loads(config.read_text(encoding="utf-8"))
            add(checks, f"source.json.{config.name}", True, str(config))
        except Exception as exc:
            add(checks, f"source.json.{config.name}", False, f"{config}: {exc}")

    add(
        checks,
        "source.yaml-runtime",
        yaml is not None,
        "PyYAML available" if yaml is not None else "PyYAML is required for full frontmatter validation",
    )

    skill_dirs = sorted(path.parent for path in skills_root.glob("*/SKILL.md"))
    names: list[str] = []
    dependency_graph: dict[str, list[str]] = {}
    prompt_visible: set[str] = set()
    for skill_dir in skill_dirs:
        try:
            meta = parse_frontmatter(skill_dir / "SKILL.md")
            declared = str(meta.get("name", ""))
            valid = declared == skill_dir.name and bool(SKILL_NAME_RE.fullmatch(declared))
            add(checks, f"source.skill.{skill_dir.name}", valid, f"declared={declared}")
            license_id = meta.get("license")
            dependencies = meta.get("depends_on")
            metadata = meta.get("metadata")
            contract_ok = (
                license_id in {"CC0-1.0", "Apache-2.0"}
                and isinstance(dependencies, list)
                and all(isinstance(dependency, str) for dependency in dependencies)
                and isinstance(metadata, dict)
                and all(
                    isinstance(metadata.get(field), str) and metadata.get(field)
                    for field in ("author", "version", "source_repo", "source_type")
                )
            )
            add(
                checks,
                f"source.skill-contract.{skill_dir.name}",
                contract_ok,
                f"license={license_id}; depends_on={dependencies}; metadata={metadata}",
            )
            if isinstance(dependencies, list) and all(
                isinstance(dependency, str) for dependency in dependencies
            ):
                dependency_graph[declared] = dependencies
            names.append(declared)
            interface = skill_dir / "agents" / "openai.yaml"
            if not interface.is_file():
                add(
                    checks,
                    f"source.skill-ui.{skill_dir.name}",
                    False,
                    f"missing {interface.relative_to(source_root)}",
                )
            else:
                try:
                    ui = yaml.safe_load(interface.read_text(encoding="utf-8"))
                    prompt = ui["interface"]["default_prompt"]
                    short_description = ui["interface"]["short_description"]
                    policy = ui.get("policy")
                    if policy is None:
                        policy = {}
                    if not isinstance(policy, dict):
                        raise ValueError("policy must be a mapping when present")
                    if policy.get("allow_implicit_invocation", True):
                        prompt_visible.add(declared)
                    ui_ok = (
                        isinstance(ui["interface"]["display_name"], str)
                        and isinstance(short_description, str)
                        and 25 <= len(short_description) <= 64
                        and isinstance(prompt, str)
                        and f"${declared}" in prompt
                    )
                    add(
                        checks,
                        f"source.skill-ui.{skill_dir.name}",
                        ui_ok,
                        str(interface.relative_to(source_root)),
                    )
                except Exception as exc:
                    add(
                        checks,
                        f"source.skill-ui.{skill_dir.name}",
                        False,
                        f"{interface}: {exc}",
                    )
        except Exception as exc:
            add(checks, f"source.skill.{skill_dir.name}", False, str(exc))

    duplicates = sorted({name for name in names if names.count(name) > 1})
    add(checks, "source.skill-names-unique", not duplicates, ", ".join(duplicates) or f"{len(names)} skills")
    missing_dependencies = sorted(
        f"{skill}->{dependency}"
        for skill, dependencies in dependency_graph.items()
        for dependency in dependencies
        if dependency not in dependency_graph
    )
    add(
        checks,
        "source.dependencies-present",
        not missing_dependencies,
        ", ".join(missing_dependencies) or "all declared dependencies exist",
    )
    try:
        tuple(TopologicalSorter(dependency_graph).static_order())
        dependency_cycle = None
    except CycleError as exc:
        dependency_cycle = " -> ".join(str(value) for value in exc.args[1])
    add(
        checks,
        "source.dependencies-acyclic",
        dependency_cycle is None,
        dependency_cycle or "dependency graph is acyclic",
    )
    if "synthesis-skill-router" in names:
        add(
            checks,
            "source.prompt-visible-policy",
            prompt_visible == PROMPT_VISIBLE_PUBLIC_SKILLS,
            f"visible={','.join(sorted(prompt_visible))}",
        )
    root_skills = sorted(path.parent.name for path in source_root.glob("*/SKILL.md"))
    add(checks, "source.no-root-skills", not root_skills, ", ".join(root_skills) or "none")

    forbidden_patterns = {
        "source.no-client-copy-paths": re.compile(
            r"(?:~|\$HOME)/\.(?:codex|claude|agents)/skills/synthesis-"
        ),
        "source.no-old-source-layout": re.compile(r"synthesis-skills/synthesis-"),
        # Repository rule 8: no personal paths in this public repository. A
        # workspace path segment must be a placeholder (<you>, *, $VAR,
        # example-…) or a documented generic sample name (demo, personal,
        # work, user) — never a real username. The second alternation
        # catches home-anchored personal checkout paths in prose.
        "source.no-personal-workspace-paths": re.compile(
            r"workspaces/(?!<|\*|\$|example|demo/|personal/|work/|user/)[\w.-]+/"
            r"|/(?:Users|home)/(?!user/|<)[\w.-]+/workspaces/"
        ),
    }
    def scannable(path: Path) -> bool:
        if not path.is_file():
            return False
        # Exclusions apply RELATIVE to the source root: a checkout may
        # itself sit under a .claude/worktrees/ directory, and matching
        # ancestor components would empty the scan into a silent pass.
        rel_parts = path.relative_to(source_root).parts
        if ".git" in rel_parts or ".claude" in rel_parts:
            return False
        if path.resolve() in (
            SCRIPT_PATH,
            SCRIPT_PATH.with_name("test_conformance.py"),
        ):
            return False
        return path.suffix in {".md", ".py", ".sh", ".yaml", ".yml", ".json"}

    text_files = [path for path in source_root.rglob("*") if scannable(path)]
    for name, pattern in forbidden_patterns.items():
        matches = []
        for path in text_files:
            try:
                if pattern.search(path.read_text(encoding="utf-8")):
                    matches.append(str(path.relative_to(source_root)))
            except UnicodeDecodeError:
                continue
        add(checks, name, not matches, ", ".join(matches) or "none")

    skill_local_npx = re.compile(
        r"npx\s+skills\s+add\s+synthesisengineering/synthesis-skills"
    )
    matches = []
    for path in text_files:
        if skills_root not in path.parents:
            continue
        try:
            if skill_local_npx.search(path.read_text(encoding="utf-8")):
                matches.append(str(path.relative_to(source_root)))
        except UnicodeDecodeError:
            continue
    add(
        checks,
        "source.no-skill-local-fallback-installs",
        not matches,
        ", ".join(matches) or "none",
    )
    return checks


def plugin_inventory(client: str) -> tuple[bool, str]:
    binary = resolve_client_binary(client)
    if not binary:
        return False, missing_binary_detail(client)
    try:
        result = run([binary, "plugin", "list", "--json"])
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    try:
        data = json_from_output(result.stdout + "\n" + result.stderr)
    except Exception as exc:
        return False, f"invalid JSON: {exc}"
    if client == "claude":
        items = data if isinstance(data, list) else []
        found = [
            item
            for item in items
            if isinstance(item, dict)
            and str(item.get("id", "")).startswith("synthesis-skills@")
            and item.get("enabled", True)
        ]
    else:
        installed = data.get("installed", []) if isinstance(data, dict) else []
        found = [
            item
            for item in installed
            if isinstance(item, dict)
            and item.get("name") == "synthesis-skills"
            and item.get("enabled")
        ]
    return len(found) == 1, f"{len(found)} enabled installation(s) via {binary}"


def direct_public_copies(home: Path) -> list[str]:
    roots = (
        home / ".claude" / "skills",
        home / ".agents" / "skills",
        home / ".codex" / "skills",
    )
    return sorted(
        str(path.relative_to(home))
        for root in roots
        for path in root.glob("synthesis-*")
        if path.is_dir()
    )


PLUGIN_NAME = "synthesis-skills"


def _version_key(version: str) -> tuple:
    parts = []
    for piece in re.split(r"[.\-+]", version):
        parts.append((0, int(piece)) if piece.isdigit() else (1, piece))
    return tuple(parts)


def newest_cached_plugin_version(client_home: Path) -> str | None:
    """Newest plugin version present in a client's plugin cache, or None."""
    cache = client_home / "plugins" / "cache"
    versions: list[str] = []
    if not cache.is_dir():
        return None
    for marketplace in cache.iterdir():
        plugin_dir = marketplace / PLUGIN_NAME
        if not plugin_dir.is_dir():
            continue
        for entry in plugin_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                versions.append(entry.name)
    return max(versions, key=_version_key) if versions else None


def parity_checks(source_root: Path, home: Path | None = None) -> list[Check]:
    """Dual-client version-drift detection, filesystem-only.

    The dual-runtime guarantee has three existing layers: CI source
    conformance (every skill ships a Codex adapter; the two source manifests
    agree), the documented release protocol (merge, release, refresh BOTH
    marketplaces), and runtime conformance (both clients report the plugin
    enabled). None of them notices the day someone releases a version and
    refreshes only one client — or neither. This mode is that missing layer:
    fast enough to run at every day-start and session start, no client
    binaries required, and it fails on drift rather than describing it.
    """
    checks: list[Check] = []
    home = home or Path.home()

    # A plugin cache is a COPY of the source, pinned at its own version.
    # Comparing installed clients against a cache would compare them against
    # themselves and always pass — the degenerate check that hides exactly
    # the drift this mode exists to catch. Fail closed instead.
    if "plugins" in source_root.parts and "cache" in source_root.parts:
        add(
            checks,
            "parity.source-root",
            False,
            f"{source_root} is a plugin cache, not the source checkout; "
            "pass --source-root pointing at the synthesis-skills repository",
        )
        return checks

    source_version: str | None = None
    versions: dict[str, str | None] = {}
    for manifest_dir in (".claude-plugin", ".codex-plugin"):
        manifest = source_root / manifest_dir / "plugin.json"
        try:
            versions[manifest_dir] = str(
                json.loads(manifest.read_text(encoding="utf-8")).get("version")
            )
        except (OSError, ValueError):
            versions[manifest_dir] = None
    manifest_values = {v for v in versions.values() if v}
    add(
        checks,
        "parity.source-manifests",
        len(manifest_values) == 1,
        ", ".join(f"{k}={v}" for k, v in sorted(versions.items())),
    )
    source_version = next(iter(manifest_values)) if len(manifest_values) == 1 else None

    installed: dict[str, str | None] = {
        "claude": newest_cached_plugin_version(home / ".claude"),
        "codex": newest_cached_plugin_version(home / ".codex"),
    }
    for client, version in installed.items():
        add(
            checks,
            f"parity.{client}-installed",
            version is not None,
            version or f"no {PLUGIN_NAME} in {home}/.{client}/plugins/cache",
        )

    both = all(installed.values())
    add(
        checks,
        "parity.clients-match",
        both and installed["claude"] == installed["codex"],
        f"claude={installed['claude']} codex={installed['codex']}",
    )
    add(
        checks,
        "parity.clients-current",
        both
        and source_version is not None
        and installed["claude"] == installed["codex"] == source_version,
        f"source={source_version} claude={installed['claude']} "
        f"codex={installed['codex']}",
    )
    return checks


def runtime_checks() -> list[Check]:
    checks: list[Check] = []
    ok, detail = plugin_inventory("claude")
    add(checks, "runtime.claude-plugin", ok, detail)
    ok, detail = plugin_inventory("codex")
    add(checks, "runtime.codex-plugin", ok, detail)

    home = Path.home()
    duplicates = direct_public_copies(home)
    add(
        checks,
        "runtime.no-direct-public-skill-copies",
        not duplicates,
        ", ".join(duplicates) or "none",
    )

    codex_binary = resolve_client_binary("codex")
    if not codex_binary:
        add(checks, "runtime.codex-doctor", False, missing_binary_detail("codex"))
        return checks
    try:
        doctor = run([codex_binary, "doctor", "--json"])
        data = json_from_output(doctor.stdout + "\n" + doctor.stderr)
        provider = data["checks"]["network.provider_reachability"]["status"] == "ok"
        websocket = data["checks"]["network.websocket_reachability"]["status"] == "ok"
        add(checks, "runtime.codex-provider", provider, f"HTTP reachability via {codex_binary}")
        add(checks, "runtime.codex-websocket", websocket, "Responses WebSocket")
    except Exception as exc:
        add(checks, "runtime.codex-doctor", False, str(exc))
    return checks


def hook_definition_checks(source_root: Path) -> list[Check]:
    """Validate the portable hook contract without claiming it ran live."""
    checks: list[Check] = []
    hook_file = source_root / "hooks" / "hooks.json"
    try:
        payload = json.loads(hook_file.read_text(encoding="utf-8"))
        hooks = payload.get("hooks")
        mapping = hooks if isinstance(hooks, dict) else {}
        add(
            checks,
            "hook-definition.public-config",
            bool(mapping),
            str(hook_file),
        )
        session_start = mapping.get("SessionStart", [])
        commands = [
            hook.get("command", "")
            for group in session_start
            if isinstance(group, dict)
            for hook in group.get("hooks", [])
            if isinstance(hook, dict) and hook.get("type") == "command"
        ]
        add(
            checks,
            "hook-definition.public-sessionstart",
            len(commands) == 1
            and "session_context.py" in commands[0]
            and "--format" in commands[0],
            f"{len(commands)} command hook(s): {commands}",
        )
    except Exception as exc:
        add(checks, "hook-definition.public-config", False, f"{hook_file}: {exc}")
    return checks


def hook_trust_checks(cwd: Path) -> list[Check]:
    """Read Codex's normalized hook hashes and trust decisions."""
    checks: list[Check] = []
    payload = codex_hook_audit([str(cwd.resolve())])
    status = payload.get("status")
    hooks = payload.get("hooks", [])
    errors = payload.get("errors", [])
    pending = payload.get("pending_review")
    ok: bool | None
    if status == "PASS":
        ok = True
    elif status == "FAIL":
        ok = False
    else:
        ok = None
    add(
        checks,
        "hook-trust.codex-authoritative",
        ok,
        f"{len(hooks)} hook(s); {pending} pending human review"
        + (f"; errors={errors}" if errors else ""),
    )
    public = [
        hook
        for hook in hooks
        if isinstance(hook, dict)
        and hook.get("plugin_id")
        and str(hook.get("plugin_id")).startswith("synthesis-skills@")
        and hook.get("event") == "SessionStart"
    ]
    if status == "UNKNOWN":
        public_ok = None
    else:
        public_ok = len(public) == 1 and all(
            hook.get("enabled")
            and (hook.get("managed") or hook.get("trust_status") == "trusted")
            for hook in public
        )
    detail = (
        "; ".join(
            f"{hook.get('key')}={hook.get('trust_status')} "
            f"{hook.get('current_hash')}"
            for hook in public
        )
        or "public SessionStart hook not present in Codex inventory"
    )
    add(checks, "hook-trust.codex-public-sessionstart", public_ok, detail)
    add(
        checks,
        "hook-trust.claude-policy",
        True,
        "Claude Code executes enabled matching plugin hooks without Codex-style per-hash human trust state",
    )
    return checks


def _receipt_check(
    checks: list[Check],
    name: str,
    path: Path,
    *,
    expected_client: str | None = None,
    expected_plugin_version: str | None = None,
    expected_plugin_root: Path | None = None,
    max_age_hours: int = 24,
) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        event = payload.get("hook_event_name")
        session_id = payload.get("session_id")
        client = payload.get("client")
        provenance = payload.get("provenance_env")
        transcript_path = payload.get("transcript_path")
        plugin_root = payload.get("plugin_root")
        try:
            uuid.UUID(str(session_id))
            valid_session_id = True
        except ValueError:
            valid_session_id = False
        ok = bool(event == "SessionStart" and valid_session_id)
        if expected_client is not None:
            ok = bool(
                ok
                and client == expected_client
                and provenance == f"{expected_client}-transcript"
                and transcript_path
            )
            transcript_root = Path(
                os.environ.get(
                    "CODEX_HOME" if expected_client == "codex" else "CLAUDE_CONFIG_DIR",
                    str(Path.home() / (".codex" if expected_client == "codex" else ".claude")),
                )
            ).expanduser()
            try:
                transcript = Path(str(transcript_path)).expanduser()
                transcript.resolve().relative_to(transcript_root.resolve())
                ok = bool(
                    ok
                    and transcript.is_absolute()
                    and transcript.is_file()
                    and transcript_binds_session(
                        transcript, expected_client, str(session_id)
                    )
                )
            except (OSError, ValueError):
                ok = False
        actual_version = payload.get("plugin_version")
        if expected_plugin_version is not None:
            ok = bool(
                ok
                and actual_version == expected_plugin_version
                and plugin_root
            )
            if expected_plugin_root is None:
                ok = False
            else:
                try:
                    ok = ok and Path(str(plugin_root)).resolve() == expected_plugin_root.resolve()
                except OSError:
                    ok = False
        recorded_at = payload.get("recorded_at")
        age_seconds: float | None = None
        try:
            recorded = datetime.fromisoformat(str(recorded_at))
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - recorded).total_seconds()
            ok = ok and -300 <= age_seconds <= max_age_hours * 60 * 60
        except ValueError:
            ok = False
        detail = (
            f"receipt={path}; client={client}; session_id={session_id}; "
            f"plugin_version={actual_version}; expected_plugin_version={expected_plugin_version}; "
            f"plugin_root={plugin_root}; expected_plugin_root={expected_plugin_root}; "
            f"provenance_env={provenance}; transcript_path={transcript_path}; "
            f"recorded_at={recorded_at}; age_seconds="
            f"{int(age_seconds) if age_seconds is not None else 'invalid'}"
        )
        add(checks, name, ok, detail)
    except FileNotFoundError:
        add(
            checks,
            name,
            None,
            f"no live receipt at {path}; static probes are not accepted",
        )
    except Exception as exc:
        add(checks, name, False, f"{path}: {exc}")


def _enabled_plugin_root(
    client: str, version: str, home: Path | None = None
) -> Path | None:
    """Return the enabled client's immutable cache root for one exact version."""
    home = home or Path.home()
    binary = resolve_client_binary(client)
    if not binary:
        return None
    try:
        result = run([binary, "plugin", "list", "--json"])
        if result.returncode != 0:
            return None
        data = json_from_output(result.stdout + "\n" + result.stderr)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if client == "claude":
        items = data if isinstance(data, list) else []
        matches = [
            item
            for item in items
            if isinstance(item, dict)
            and str(item.get("id", "")).startswith(f"{PLUGIN_NAME}@")
            and item.get("enabled", True)
            and str(item.get("version")) == version
            and item.get("installPath")
        ]
        return Path(str(matches[0]["installPath"])) if len(matches) == 1 else None
    installed = data.get("installed", []) if isinstance(data, dict) else []
    matches = [
        item
        for item in installed
        if isinstance(item, dict)
        and item.get("name") == PLUGIN_NAME
        and item.get("enabled")
        and str(item.get("version")) == version
    ]
    return _plugin_cache_path(home, client, version) if len(matches) == 1 else None


def hook_live_checks(
    public_codex_receipt: Path = DEFAULT_PUBLIC_CODEX_SESSIONSTART_RECEIPT,
    public_claude_receipt: Path = DEFAULT_PUBLIC_CLAUDE_SESSIONSTART_RECEIPT,
    private_codex_receipt: Path | None = None,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    home: Path | None = None,
) -> list[Check]:
    """Require receipts produced only by genuine SessionStart payloads."""
    checks: list[Check] = []
    try:
        source_version = str(
            json.loads(
                (source_root / ".codex-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )["version"]
        )
    except (OSError, ValueError, KeyError) as exc:
        add(
            checks,
            "hook-live.source-version",
            False,
            f"source plugin version is unavailable: {source_root}: {exc}",
        )
        return checks
    codex_root = _enabled_plugin_root("codex", source_version, home)
    claude_root = _enabled_plugin_root("claude", source_version, home)
    _receipt_check(
        checks,
        "hook-live.public-codex-sessionstart",
        public_codex_receipt,
        expected_client="codex",
        expected_plugin_version=source_version,
        expected_plugin_root=codex_root,
    )
    _receipt_check(
        checks,
        "hook-live.public-claude-sessionstart",
        public_claude_receipt,
        expected_client="claude",
        expected_plugin_version=source_version,
        expected_plugin_root=claude_root,
    )
    if private_codex_receipt is not None:
        _receipt_check(
            checks,
            "hook-live.codex-private-sessionstart",
            private_codex_receipt,
            expected_client="codex",
        )
    return checks


def _plugin_cache_path(home: Path, client: str, version: str) -> Path | None:
    cache = home / f".{client}" / "plugins" / "cache"
    if not cache.is_dir():
        return None
    matches = sorted(cache.glob(f"*/{PLUGIN_NAME}/{version}"))
    return matches[-1] if matches else None


def catalog_checks(source_root: Path, home: Path | None = None) -> list[Check]:
    """Check source/install parity and Codex's resolved prompt catalog budget."""
    checks: list[Check] = []
    home = home or Path.home()
    skills = sorted((source_root / "skills").glob("*/SKILL.md"))
    descriptions: list[tuple[str, int]] = []
    for skill in skills:
        try:
            metadata = parse_frontmatter(skill)
            descriptions.append(
                (skill.parent.name, len(str(metadata.get("description", ""))))
            )
        except Exception as exc:
            add(checks, f"catalog.source.{skill.parent.name}", False, str(exc))
    longest = max(descriptions, key=lambda item: item[1], default=("none", 0))
    add(
        checks,
        "catalog.source-count",
        bool(skills),
        f"{len(skills)} skills",
    )
    add(
        checks,
        "catalog.description-limit",
        longest[1] <= 1_024,
        f"longest={longest[0]}:{longest[1]}; Codex per-description limit=1024",
    )
    source_version = None
    try:
        source_version = str(
            json.loads(
                (source_root / ".codex-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )["version"]
        )
    except Exception as exc:
        add(checks, "catalog.source-version", False, str(exc))
    if source_version:
        for client in ("claude", "codex"):
            cache = _plugin_cache_path(home, client, source_version)
            if cache is None:
                add(
                    checks,
                    f"catalog.{client}-cache",
                    False,
                    f"version {source_version} not installed",
                )
                continue
            installed_count = len(list((cache / "skills").glob("*/SKILL.md")))
            source_digest = directory_digest(source_root / "skills")
            installed_digest = directory_digest(cache / "skills")
            add(
                checks,
                f"catalog.{client}-cache",
                installed_count == len(skills) and installed_digest == source_digest,
                f"version={source_version}; source={len(skills)} installed={installed_count}; "
                f"source_digest={source_digest}; installed_digest={installed_digest}; {cache}",
            )
    runtime = codex_skill_catalog_audit(source_root, home=home)
    runtime_status = str(runtime.get("status") or "UNKNOWN")
    runtime_detail = (
        f"discovered={runtime.get('discovered_skill_count', 0)}; "
        f"prompt-visible={runtime.get('skill_count', 0)}; "
        f"cost={runtime.get('full_cost_tokens')} tokens; "
        f"budget={runtime.get('budget_tokens')} tokens; "
        f"model={runtime.get('model')}; missing={runtime.get('missing_skill_names', [])}; "
        f"errors={runtime.get('errors', [])}"
    )
    add(
        checks,
        "catalog.codex-resolved-budget",
        True if runtime_status == "PASS" else False if runtime_status == "FAIL" else None,
        runtime_detail,
    )
    return checks


def _codex_instruction_limit(home: Path) -> int:
    config = home / ".codex" / "config.toml"
    try:
        match = re.search(
            r"^project_doc_max_bytes\s*=\s*(\d+)\s*$",
            config.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        return int(match.group(1)) if match else 32_768
    except OSError:
        return 32_768


def _codex_instruction_fallbacks(home: Path) -> list[str]:
    try:
        payload = tomllib.loads(
            (home / ".codex" / "config.toml").read_text(encoding="utf-8")
        )
        values = payload.get("project_doc_fallback_filenames", [])
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value for value in values
        ):
            return []
        return values
    except (OSError, tomllib.TOMLDecodeError):
        return []


def _codex_instruction_chain(repo_root: Path, home: Path) -> list[Path]:
    """Resolve Codex's user file and root-to-cwd scoped instruction chain."""
    chain: list[Path] = []
    user_root = home / ".codex"
    for name in ("AGENTS.override.md", "AGENTS.md"):
        candidate = user_root / name
        if candidate.is_file():
            chain.append(candidate)
            break

    target = repo_root if repo_root.is_dir() else repo_root.parent
    discovered = run(["git", "-C", str(target), "rev-parse", "--show-toplevel"])
    project_root = (
        Path(discovered.stdout.strip())
        if discovered.returncode == 0 and discovered.stdout.strip()
        else target
    )
    try:
        relative = target.resolve().relative_to(project_root.resolve())
        directories = [project_root.resolve()]
        current = project_root.resolve()
        for part in relative.parts:
            current = current / part
            directories.append(current)
    except ValueError:
        directories = [target.resolve()]

    names = [
        "AGENTS.override.md",
        "AGENTS.md",
        *_codex_instruction_fallbacks(home),
    ]
    for directory in directories:
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                chain.append(candidate)
                break
    return chain


def instruction_budget_checks(repo_root: Path, home: Path | None = None) -> list[Check]:
    """Measure the instructions Codex may concatenate before task content."""
    checks: list[Check] = []
    home = home or Path.home()
    existing = _codex_instruction_chain(repo_root, home)
    total = sum(path.stat().st_size for path in existing)
    limit = _codex_instruction_limit(home)
    reserve = 4_096
    add(
        checks,
        "instruction-budget.codex-bytes",
        total <= limit - reserve,
        f"{total} bytes across {len(existing)} file(s); limit={limit}; required reserve={reserve}",
    )
    return checks


def instruction_checks(repo_root: Path) -> list[Check]:
    checks: list[Check] = []
    agents = repo_root / "AGENTS.md"
    claude = repo_root / "CLAUDE.md"
    add(checks, "instructions.agents", agents.is_file(), str(agents))
    adapter_ok = False
    detail = str(claude)
    if claude.is_symlink():
        adapter_ok = claude.resolve() == agents.resolve()
        detail = f"{claude} -> {os.readlink(claude)}"
    elif claude.is_file():
        adapter_ok = claude.read_text(encoding="utf-8").strip() == "@AGENTS.md"
    add(checks, "instructions.claude-adapter", adapter_ok, detail)
    return checks


def coordination_checks(board: Path, *, required: bool = True) -> list[Check]:
    checks: list[Check] = []
    if not board.is_file():
        add(
            checks,
            "coordination.board",
            False,
            str(board),
            required=required,
        )
        return checks
    try:
        text = board.read_text(encoding="utf-8")
    except Exception as exc:
        add(checks, "coordination.board", False, str(exc), required=required)
        return checks
    add(checks, "coordination.board", True, str(board), required=required)
    for heading in ("## Active sessions", "## Messages", "## Protocol"):
        add(
            checks,
            f"coordination.{heading[3:].lower().replace(' ', '-')}",
            heading in text,
            heading,
            required=required,
        )
    table_ok = all(
        column in text
        for column in (
            "Schema: v2",
            "| id |",
            "| machine |",
            "| project |",
            "| heartbeat |",
            "workspace(s) / branch",
            "claimed areas (advisory lock)",
            "| context role |",
            "| status |",
        )
    )
    add(
        checks,
        "coordination.active-table-schema",
        table_ok,
        str(board),
        required=required,
    )
    if not COORDINATION_HELPER.is_file():
        add(
            checks,
            "coordination.semantic-doctor",
            False,
            f"missing helper: {COORDINATION_HELPER}",
            required=required,
        )
        return checks
    doctor = run(
        [
            sys.executable,
            str(COORDINATION_HELPER),
            "--board",
            str(board),
            "doctor",
        ]
    )
    detail = (doctor.stdout + doctor.stderr).strip()
    add(
        checks,
        "coordination.semantic-doctor",
        doctor.returncode == 0,
        detail or f"exit {doctor.returncode}",
        required=required,
    )
    return checks


def project_summary(project: Path) -> tuple[dict[str, object], list[Check]]:
    checks: list[Check] = []
    context = project / "CONTEXT.md"
    reference = project / "REFERENCE.md"
    sessions = project / "sessions"
    add(checks, "handoff.context", context.is_file(), str(context))
    add(checks, "handoff.reference", reference.is_file(), str(reference))
    add(checks, "handoff.sessions", sessions.is_dir(), str(sessions))
    fresh, detail = record_freshness(project)
    add(checks, "handoff.record-freshness", fresh, detail)

    summary: dict[str, object] = {"project": str(project.resolve())}
    if context.is_file():
        text = context.read_text(encoding="utf-8")
        for key in ("Phase", "Status", "Last session"):
            match = re.search(rf"^\*\*{re.escape(key)}:\*\*\s*(.+)$", text, re.MULTILINE)
            summary[key.lower().replace(" ", "_")] = match.group(1).strip() if match else "unknown"
        plan_match = re.search(r"\((resources/artifacts/[^)]+plan[^)]*\.md)\)", text)
        if plan_match:
            plan = project / plan_match.group(1)
            summary["plan"] = str(plan)
            add(checks, "handoff.plan", plan.is_file(), str(plan))
        else:
            summary["plan"] = "unknown"
            add(checks, "handoff.plan", False, "CONTEXT.md has no linked plan", required=False)

        summary["next"] = next_actions(text)

    git = run(["git", "-C", str(project), "rev-parse", "--show-toplevel"])
    add(checks, "handoff.git", git.returncode == 0, git.stdout.strip() or git.stderr.strip())
    return summary, checks


def activate(
    project: Path,
    pointer: Path,
    *,
    owner_session: str | None = None,
    coordination_board: Path = DEFAULT_COORDINATION_BOARD,
) -> list[Check]:
    summary, checks = project_summary(project)
    if any(not check.ok and check.required for check in checks):
        return checks
    root_result = run(["git", "-C", str(project), "rev-parse", "--show-toplevel"])
    worktree = root_result.stdout.strip() if root_result.returncode == 0 else str(project)
    branch_result = run(["git", "-C", worktree, "branch", "--show-current"])
    branch = branch_result.stdout.strip() or "detached-or-unborn"
    commit_result = run(["git", "-C", worktree, "rev-parse", "HEAD"])
    commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unborn"
    lease = lease_url(coordination_board)
    owner = owner_session or os.environ.get("SYNTHESIS_SESSION_ID")
    active_owners = coordination_sessions(coordination_board)
    owner_state = active_owners.get(owner or "")
    if not lease:
        add(checks, "handoff.pointer-owner", False, "coordination lease unavailable")
        return checks
    if not owner or not owner_state or owner_state["status"] in {
        "released",
        "complete",
        "completed",
        "closed",
    }:
        add(
            checks,
            "handoff.pointer-owner",
            False,
            f"active coordination owner required; requested={owner or 'missing'}",
        )
        return checks
    payload = {
        **summary,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthesis-agent-conformance",
        "worktree": worktree,
        "branch": branch,
        "source_commit": commit,
        "owner_session": owner,
        "owner_lease": lease,
    }
    with locked_pointer(pointer):
        pointer_issues = validate_active_project(payload, coordination_board)
        if pointer_issues:
            add(
                checks,
                "handoff.pointer-owner",
                False,
                "; ".join(pointer_issues),
            )
            return checks
        atomic_json_write(pointer, payload)
    add(checks, "handoff.pointer-written", True, str(pointer))
    return checks


TIMESTAMP_LINE = re.compile(r"^Verified local time: .*$", re.MULTILINE)


def payload_parity(
    pointer: Path,
    coordination_board: Path = DEFAULT_COORDINATION_BOARD,
) -> tuple[bool, str]:
    """Both client formats of the SessionStart payload must carry one context.

    The claude and codex wrappers are native envelopes around the same
    message; this runs the shared script in both formats against the live
    pointer and compares the enveloped context after normalizing the
    timestamp line. No client binary is required — the script itself is the
    shared implementation both clients invoke.
    """
    script = SCRIPTS_DIR / "session_context.py"
    contexts: dict[str, str] = {}
    for client_format in ("claude", "codex"):
        result = run(
            [
                sys.executable,
                str(script),
                "--format",
                client_format,
                "--active-project-file",
                str(pointer),
                "--coordination-board",
                str(coordination_board),
            ],
            input_text="{}",
        )
        if result.returncode != 0:
            return False, (
                f"{client_format} payload failed: "
                + (result.stderr.strip() or f"exit {result.returncode}")
            )
        try:
            envelope = json.loads(result.stdout)
            contexts[client_format] = envelope["hookSpecificOutput"][
                "additionalContext"
            ]
        except Exception as exc:
            return False, f"{client_format} payload is not a valid envelope: {exc}"
    normalized = {
        client_format: TIMESTAMP_LINE.sub("Verified local time: <normalized>", text)
        for client_format, text in contexts.items()
    }
    if normalized["claude"] == normalized["codex"]:
        return True, "claude and codex envelopes carry identical context"
    difference = next(
        (
            f"claude={left!r} codex={right!r}"
            for left, right in zip(
                normalized["claude"].splitlines(),
                normalized["codex"].splitlines(),
            )
            if left != right
        ),
        "payloads differ in length",
    )
    return False, f"client payloads diverge: {difference}"


def handoff_checks(
    project: Path,
    pointer: Path,
    coordination_board: Path = DEFAULT_COORDINATION_BOARD,
) -> list[Check]:
    summary, checks = project_summary(project)
    try:
        active = json.loads(pointer.read_text(encoding="utf-8"))
        matches = Path(active["project"]).resolve() == project.resolve()
        add(checks, "handoff.pointer", matches, str(pointer))
        for key in ("phase", "status", "plan"):
            add(
                checks,
                f"handoff.pointer-{key}",
                active.get(key) == summary.get(key),
                f"active={active.get(key)!r}; project={summary.get(key)!r}",
            )
        parity, detail = payload_parity(pointer, coordination_board)
        add(checks, "handoff.payload-parity", parity, detail)
    except Exception as exc:
        add(checks, "handoff.pointer", False, f"{pointer}: {exc}")
    return checks


def pointer_checks(
    project: Path,
    pointer: Path,
    coordination_board: Path = DEFAULT_COORDINATION_BOARD,
) -> list[Check]:
    """Validate pointer content, ownership, and checkout identity."""
    checks = handoff_checks(project, pointer, coordination_board)
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except Exception as exc:
        add(checks, "pointer.schema", False, f"{pointer}: {exc}")
        return checks
    required_fields = (
        "project",
        "plan",
        "activated_at",
        "source",
        "worktree",
        "branch",
        "source_commit",
        "owner_session",
        "owner_lease",
    )
    missing = [field for field in required_fields if not payload.get(field)]
    add(
        checks,
        "pointer.schema",
        not missing,
        "complete" if not missing else f"missing: {', '.join(missing)}",
    )
    owner = str(payload.get("owner_session") or "")
    add(
        checks,
        "pointer.ownership",
        bool(owner and owner != "unclaimed"),
        f"owner_session={owner or 'missing'}; owner_lease={payload.get('owner_lease')}",
    )
    _, lease_issues = load_and_validate(pointer, coordination_board)
    add(
        checks,
        "pointer.lease-and-freshness",
        not lease_issues,
        "active owner, lease, worktree, plan, branch, commit, and origin/main are current"
        if not lease_issues
        else "; ".join(lease_issues),
    )
    git = run(["git", "-C", str(project), "rev-parse", "--show-toplevel"])
    if git.returncode == 0:
        worktree = git.stdout.strip()
        branch = run(["git", "-C", worktree, "branch", "--show-current"]).stdout.strip()
        commit = run(["git", "-C", worktree, "rev-parse", "HEAD"]).stdout.strip()
        identity_ok = (
            payload.get("worktree") == worktree
            and payload.get("branch") == branch
        )
        recorded = str(payload.get("source_commit") or "")
        ancestry = run(
            ["git", "-C", worktree, "merge-base", "--is-ancestor", recorded, commit]
        )
        identity_ok = identity_ok and ancestry.returncode == 0
        add(
            checks,
            "pointer.checkout-identity",
            identity_ok,
            f"pointer={payload.get('worktree')}@{payload.get('branch')}:{payload.get('source_commit')}; "
            f"actual={worktree}@{branch}:{commit}",
        )
    else:
        add(checks, "pointer.checkout-identity", False, git.stderr.strip())
    return checks


CAPABILITY_NAMES = (
    "repository",
    "project-issue",
    "slack",
    "calendar",
    "mail",
    "workspace",
    "browser",
)
CAPABILITY_CLIENTS = ("claude-code", "codex-desktop", "codex-cli")
CAPABILITY_EVIDENCE_KINDS = (
    "live-read-only",
    "client-health",
    "authenticated-cli",
    "environment-restricted",
    "product-boundary",
)


def capability_checks(
    repo_root: Path, evidence_path: Path = DEFAULT_CAPABILITY_EVIDENCE
) -> list[Check]:
    """Report capability outcomes from timestamped read-only evidence."""
    checks: list[Check] = []
    for client in ("claude", "codex"):
        binary = resolve_client_binary(client)
        add(
            checks,
            f"capability.{client}-binary",
            binary is not None,
            binary or missing_binary_detail(client),
        )
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("schema_version must equal 1")
        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            raise ValueError("entries is not an object")
    except FileNotFoundError:
        entries = {}
    except Exception as exc:
        add(checks, "capability.evidence-schema", False, f"{evidence_path}: {exc}")
        entries = {}
    for client in CAPABILITY_CLIENTS:
        for capability in CAPABILITY_NAMES:
            key = f"{client}.{capability}"
            entry = entries.get(key)
            if not isinstance(entry, dict):
                add(
                    checks,
                    f"capability.{key}",
                    None,
                    f"no timestamped read-only evidence in {evidence_path}",
                )
                continue
            detail = entry.get("detail")
            schema_issues = []
            if entry.get("client") != client:
                schema_issues.append(f"client must equal {client}")
            if entry.get("capability") != capability:
                schema_issues.append(f"capability must equal {capability}")
            if entry.get("status") not in {"PASS", "FAIL", "UNKNOWN", "UNSUPPORTED"}:
                schema_issues.append("status is invalid")
            if entry.get("evidence_kind") not in CAPABILITY_EVIDENCE_KINDS:
                schema_issues.append("evidence_kind is invalid")
            if not isinstance(detail, str) or not 1 <= len(" ".join(detail.split())) <= 500:
                schema_issues.append("detail must contain 1-500 characters")
            if schema_issues:
                add(
                    checks,
                    f"capability.{key}",
                    False,
                    f"malformed evidence in {evidence_path}: " + "; ".join(schema_issues),
                    outcome="FAIL",
                )
                continue
            outcome = str(entry.get("status", "UNKNOWN")).upper()
            if outcome not in {"PASS", "FAIL", "UNKNOWN", "UNSUPPORTED"}:
                outcome = "FAIL"
            checked_at = entry.get("checked_at")
            try:
                checked = datetime.fromisoformat(str(checked_at))
                if checked.tzinfo is None:
                    checked = checked.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - checked).total_seconds()
                fresh = 0 <= age <= 7 * 24 * 60 * 60
            except Exception:
                age = -1
                fresh = False
            ok = outcome == "PASS" and fresh
            status = outcome if fresh else "UNKNOWN"
            add(
                checks,
                f"capability.{key}",
                ok if status in {"PASS", "FAIL"} else None,
                f"{entry.get('evidence_kind')}: {entry.get('detail')}; "
                f"checked_at={checked_at}; age_seconds={int(age)}",
                outcome=status,
            )
    return checks


def surface_checks(source_root: Path) -> list[Check]:
    """Make supported product surfaces explicit."""
    checks: list[Check] = []
    manifests = {
        "claude-code": source_root / ".claude-plugin" / "plugin.json",
        "codex-desktop": source_root / ".codex-plugin" / "plugin.json",
        "codex-cli": source_root / ".codex-plugin" / "plugin.json",
    }
    for surface, manifest in manifests.items():
        add(checks, f"surface.{surface}", manifest.is_file(), str(manifest))
    add(
        checks,
        "surface.codex-ide",
        None,
        "UNSUPPORTED: Codex IDE does not load plugins; a shared user-skill fallback would duplicate the native plugin in desktop/CLI",
        required=False,
        outcome="UNSUPPORTED",
    )
    add(
        checks,
        "surface.chat-only-products",
        None,
        "native filesystem plugin execution is not available on generic chat-only surfaces",
        required=False,
        outcome="UNSUPPORTED",
    )
    return checks


def render(
    checks: Iterable[Check],
    as_json: bool,
    report_file: Path | None = None,
) -> int:
    items = list(checks)
    failed = [item for item in items if item.required and item.ok is not True]
    payload = {
        "ok": not failed,
        "status": "PASS" if not failed else "FAIL",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": [item.serialized() for item in items],
    }
    if report_file is not None:
        destination = report_file.expanduser()
        atomic_json_write(destination, payload)
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for item in items:
            marker = item.status
            print(f"{marker:4} {item.name}: {item.detail}")
        print(f"\n{'PASS' if not failed else 'FAIL'}: {len(items)} checks, {len(failed)} required failure(s)")
    return 0 if not failed else 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "command",
        choices=(
            "source",
            "runtime",
            "parity",
            "instructions",
            "instruction-budget",
            "hook-definition",
            "hook-trust",
            "hook-live",
            "catalog",
            "pointer",
            "capabilities",
            "surfaces",
            "coordination",
            "activate",
            "handoff",
            "all",
        ),
    )
    result.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    result.add_argument("--repo-root", type=Path)
    result.add_argument("--project", type=Path)
    result.add_argument("--active-project-file", type=Path, default=DEFAULT_ACTIVE_PROJECT)
    result.add_argument(
        "--session-id",
        help="Coordination-board session id recorded as active pointer owner.",
    )
    result.add_argument(
        "--public-codex-sessionstart-receipt",
        type=Path,
        default=DEFAULT_PUBLIC_CODEX_SESSIONSTART_RECEIPT,
    )
    result.add_argument(
        "--public-claude-sessionstart-receipt",
        type=Path,
        default=DEFAULT_PUBLIC_CLAUDE_SESSIONSTART_RECEIPT,
    )
    result.add_argument(
        "--private-codex-sessionstart-receipt",
        type=Path,
        help="Opt in to a private control-plane SessionStart receipt check.",
    )
    result.add_argument(
        "--capability-evidence",
        type=Path,
        default=DEFAULT_CAPABILITY_EVIDENCE,
    )
    result.add_argument(
        "--coordination-board",
        type=Path,
        default=DEFAULT_COORDINATION_BOARD,
    )
    result.add_argument("--json", action="store_true")
    result.add_argument(
        "--report-file",
        type=Path,
        help="Atomically write the same structured result rendered to stdout.",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    checks: list[Check] = []
    if args.command in {"source", "all"}:
        checks.extend(source_checks(args.source_root.resolve()))
    if args.command in {"parity", "all"}:
        checks.extend(parity_checks(args.source_root.resolve()))
    if args.command in {"runtime", "all"}:
        checks.extend(runtime_checks())
    if args.command in {"hook-definition", "all"}:
        checks.extend(hook_definition_checks(args.source_root.resolve()))
    if args.command in {"hook-trust", "all"}:
        checks.extend(hook_trust_checks((args.repo_root or Path.cwd()).resolve()))
    if args.command in {"hook-live", "all"}:
        checks.extend(
            hook_live_checks(
                args.public_codex_sessionstart_receipt.expanduser(),
                args.public_claude_sessionstart_receipt.expanduser(),
                args.private_codex_sessionstart_receipt.expanduser()
                if args.private_codex_sessionstart_receipt
                else None,
                args.source_root.resolve(),
            )
        )
    if args.command in {"catalog", "all"}:
        checks.extend(catalog_checks(args.source_root.resolve()))
    if args.command in {"instructions", "all"}:
        if not args.repo_root:
            raise SystemExit("--repo-root is required")
        checks.extend(instruction_checks(args.repo_root.resolve()))
    if args.command in {"instruction-budget", "all"}:
        if not args.repo_root:
            raise SystemExit("--repo-root is required")
        checks.extend(instruction_budget_checks(args.repo_root.resolve()))
    if args.command in {"capabilities", "all"}:
        checks.extend(
            capability_checks(
                (args.repo_root or Path.cwd()).resolve(),
                args.capability_evidence.expanduser(),
            )
        )
    if args.command in {"surfaces", "all"}:
        checks.extend(surface_checks(args.source_root.resolve()))
    if args.command == "coordination":
        checks.extend(
            coordination_checks(args.coordination_board.expanduser(), required=True)
        )
    elif args.command == "all":
        checks.extend(
            coordination_checks(args.coordination_board.expanduser(), required=False)
        )
    if args.command == "activate":
        if not args.project:
            raise SystemExit("--project is required")
        checks.extend(
            activate(
                args.project.resolve(),
                args.active_project_file.expanduser(),
                owner_session=args.session_id,
                coordination_board=args.coordination_board.expanduser(),
            )
        )
    if args.command in {"pointer", "all"}:
        if not args.project:
            raise SystemExit("--project is required")
        checks.extend(
            pointer_checks(
                args.project.resolve(),
                args.active_project_file.expanduser(),
                args.coordination_board.expanduser(),
            )
        )
    if args.command == "handoff":
        if not args.project:
            raise SystemExit("--project is required")
        checks.extend(
            handoff_checks(
                args.project.resolve(),
                args.active_project_file.expanduser(),
                args.coordination_board.expanduser(),
            )
        )
    return render(checks, args.json, args.report_file)


if __name__ == "__main__":
    sys.exit(main())
