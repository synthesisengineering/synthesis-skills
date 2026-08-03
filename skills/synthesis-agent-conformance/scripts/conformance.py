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

from client_binaries import missing_binary_detail, resolve_client_binary
from project_context import next_actions, record_freshness

DEFAULT_SOURCE_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_ACTIVE_PROJECT = Path.home() / ".synthesis" / "active-project.json"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
)
COORDINATION_HELPER = (
    SCRIPT_PATH.parents[2]
    / "synthesis-project-management"
    / "scripts"
    / "coordination.py"
)
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def add(checks: list[Check], name: str, ok: bool, detail: str, required: bool = True) -> None:
    checks.append(Check(name=name, ok=ok, detail=detail, required=required))


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
    for skill_dir in skill_dirs:
        try:
            meta = parse_frontmatter(skill_dir / "SKILL.md")
            declared = str(meta.get("name", ""))
            valid = declared == skill_dir.name and bool(SKILL_NAME_RE.fullmatch(declared))
            add(checks, f"source.skill.{skill_dir.name}", valid, f"declared={declared}")
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


def activate(project: Path, pointer: Path) -> list[Check]:
    summary, checks = project_summary(project)
    if any(not check.ok and check.required for check in checks):
        return checks
    pointer.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        **summary,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthesis-agent-conformance",
    }
    temporary = pointer.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, pointer)
    add(checks, "handoff.pointer-written", True, str(pointer))
    return checks


TIMESTAMP_LINE = re.compile(r"^Verified local time: .*$", re.MULTILINE)


def payload_parity(pointer: Path) -> tuple[bool, str]:
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


def handoff_checks(project: Path, pointer: Path) -> list[Check]:
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
        parity, detail = payload_parity(pointer)
        add(checks, "handoff.payload-parity", parity, detail)
    except Exception as exc:
        add(checks, "handoff.pointer", False, f"{pointer}: {exc}")
    return checks


def render(checks: Iterable[Check], as_json: bool) -> int:
    items = list(checks)
    failed = [item for item in items if item.required and not item.ok]
    if as_json:
        print(
            json.dumps(
                {
                    "ok": not failed,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "checks": [asdict(item) for item in items],
                },
                indent=2,
            )
        )
    else:
        for item in items:
            marker = "PASS" if item.ok else ("WARN" if not item.required else "FAIL")
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
        "--coordination-board",
        type=Path,
        default=DEFAULT_COORDINATION_BOARD,
    )
    result.add_argument("--json", action="store_true")
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
    if args.command in {"instructions", "all"}:
        if not args.repo_root:
            raise SystemExit("--repo-root is required")
        checks.extend(instruction_checks(args.repo_root.resolve()))
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
        checks.extend(activate(args.project.resolve(), args.active_project_file.expanduser()))
    if args.command in {"handoff", "all"}:
        if not args.project:
            raise SystemExit("--project is required")
        checks.extend(handoff_checks(args.project.resolve(), args.active_project_file.expanduser()))
    return render(checks, args.json)


if __name__ == "__main__":
    sys.exit(main())
