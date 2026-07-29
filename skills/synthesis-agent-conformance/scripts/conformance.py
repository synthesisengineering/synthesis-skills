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
DEFAULT_SOURCE_ROOT = SCRIPT_PATH.parents[3]
DEFAULT_ACTIVE_PROJECT = Path.home() / ".synthesis" / "active-project.json"
DEFAULT_COORDINATION_BOARD = (
    Path.home() / ".synthesis" / "coordination" / "active-sessions.md"
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


def run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def json_from_output(output: str) -> object:
    starts = [pos for pos in (output.find("{"), output.find("[")) if pos >= 0]
    if not starts:
        raise ValueError("command returned no JSON")
    return json.loads(output[min(starts) :])


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
        except Exception as exc:
            add(checks, f"source.skill.{skill_dir.name}", False, str(exc))

    duplicates = sorted({name for name in names if names.count(name) > 1})
    add(checks, "source.skill-names-unique", not duplicates, ", ".join(duplicates) or f"{len(names)} skills")
    root_skills = sorted(path.parent.name for path in source_root.glob("*/SKILL.md"))
    add(checks, "source.no-root-skills", not root_skills, ", ".join(root_skills) or "none")

    stale_patterns = {
        "source.no-codex-copy-paths": re.compile(r"~/.codex/skills/synthesis-"),
        "source.no-claude-copy-paths": re.compile(r"~/.claude/skills/synthesis-"),
        "source.no-old-source-layout": re.compile(r"synthesis-skills/synthesis-"),
    }
    text_files = [
        path
        for path in source_root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and ".claude" not in path.parts
        and path.resolve() != SCRIPT_PATH
        and path.suffix in {".md", ".py", ".sh", ".yaml", ".yml", ".json"}
    ]
    for name, pattern in stale_patterns.items():
        matches = []
        for path in text_files:
            try:
                if pattern.search(path.read_text(encoding="utf-8")):
                    matches.append(str(path.relative_to(source_root)))
            except UnicodeDecodeError:
                continue
        add(checks, name, not matches, ", ".join(matches) or "none")
    return checks


def plugin_inventory(command: list[str], client: str) -> tuple[bool, str]:
    try:
        result = run(command)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    try:
        data = json_from_output(result.stdout + "\n" + result.stderr)
    except Exception as exc:
        return False, f"invalid JSON: {exc}"
    if client == "claude":
        found = [item for item in data if item.get("id", "").startswith("synthesis-skills@")]
    else:
        found = [
            item
            for item in data.get("installed", [])
            if item.get("name") == "synthesis-skills" and item.get("enabled")
        ]
    return len(found) == 1, f"{len(found)} enabled installation(s)"


def runtime_checks() -> list[Check]:
    checks: list[Check] = []
    ok, detail = plugin_inventory(["claude", "plugin", "list", "--json"], "claude")
    add(checks, "runtime.claude-plugin", ok, detail)
    ok, detail = plugin_inventory(["codex", "plugin", "list", "--json"], "codex")
    add(checks, "runtime.codex-plugin", ok, detail)

    duplicate_root = Path.home() / ".codex" / "skills"
    duplicates = sorted(
        path.name
        for path in duplicate_root.glob("synthesis-*")
        if path.is_dir() and path.name != ".system"
    )
    add(
        checks,
        "runtime.no-codex-skill-duplicates",
        not duplicates,
        ", ".join(duplicates) or "none",
    )

    doctor = run(["codex", "doctor", "--json"])
    try:
        data = json_from_output(doctor.stdout)
        provider = data["checks"]["network.provider_reachability"]["status"] == "ok"
        websocket = data["checks"]["network.websocket_reachability"]["status"] == "ok"
        add(checks, "runtime.codex-provider", provider, "HTTP reachability")
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
            "| id |",
            "claimed areas (advisory lock)",
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
    return checks


def project_summary(project: Path) -> tuple[dict[str, object], list[Check]]:
    checks: list[Check] = []
    context = project / "CONTEXT.md"
    reference = project / "REFERENCE.md"
    sessions = project / "sessions"
    add(checks, "handoff.context", context.is_file(), str(context))
    add(checks, "handoff.reference", reference.is_file(), str(reference))
    add(checks, "handoff.sessions", sessions.is_dir(), str(sessions))

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

        next_section = re.search(
            r"^## What's Next[^\n]*\n(.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        summary["next"] = (
            [line.strip() for line in next_section.group(1).splitlines() if line.strip()][:5]
            if next_section
            else []
        )

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
