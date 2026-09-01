#!/usr/bin/env python3
"""Fail when a documented fail-closed config has no shipped scaffold."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


HARD_STOP = re.compile(
    r"(?:config[^\n]{0,120}missing[^\n]{0,120}STOP|"
    r"engine refuses to run without it)",
    re.IGNORECASE,
)
INSTALLER_NAMES = ("install.sh", "onboard.sh")
INSTALLER_GLOBS = ("install*.sh", "install*.py", "*_installer.py")


def component_catalog_errors(repo_root: Path) -> list[str]:
    catalog_path = (
        repo_root / "skills/synthesis-onboarding/references/components.json"
    )
    layers_path = repo_root / "skills/synthesis-onboarding/references/layers.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        layers = json.loads(layers_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["component catalog unreadable: %s" % exc]
    if catalog.get("schema_version") != 1:
        return ["component catalog schema_version must be 1"]
    errors = []
    declared_skills = catalog.get("skills") or []
    if len(declared_skills) != len(set(declared_skills)):
        errors.append("component catalog contains duplicate skills")
    actual_skills = {
        path.parent.name for path in (repo_root / "skills").glob("*/SKILL.md")
    }
    declared_skill_set = set(declared_skills)
    for skill in sorted(actual_skills - declared_skill_set):
        errors.append("skill missing from component catalog: %s" % skill)
    for skill in sorted(declared_skill_set - actual_skills):
        errors.append("component catalog names missing skill: %s" % skill)

    actual_installers = {
        name for name in INSTALLER_NAMES if (repo_root / name).is_file()
    }
    for pattern in INSTALLER_GLOBS:
        actual_installers.update(
            str(path.relative_to(repo_root))
            for path in (repo_root / "skills").glob("*/scripts/%s" % pattern)
            if path.is_file()
        )
    entries = catalog.get("installers") or []
    declared_installers = {
        entry.get("path")
        for entry in entries
        if isinstance(entry, dict) and entry.get("path")
    }
    if len(entries) != len(declared_installers):
        errors.append("component catalog contains duplicate or malformed installers")
    for installer in sorted(actual_installers - declared_installers):
        errors.append("installer missing from component catalog: %s" % installer)
    for installer in sorted(declared_installers - actual_installers):
        errors.append("component catalog names missing installer: %s" % installer)
    layer_ids = {
        layer.get("id")
        for layer in layers.get("layers", [])
        if isinstance(layer, dict)
    }
    for entry in entries:
        if isinstance(entry, dict) and entry.get("layer") not in layer_ids:
            errors.append(
                "installer %s references unknown layer: %s"
                % (entry.get("path"), entry.get("layer"))
            )
    return errors


def audit(repo_root: Path) -> list[str]:
    repo_root = Path(repo_root)
    manifest_path = (
        repo_root / "skills/synthesis-onboarding/references/scaffolds.json"
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["scaffold manifest unreadable: %s" % exc]
    entries = manifest.get("hard_stop_consumers") or []
    by_skill = {
        entry.get("skill"): entry for entry in entries if isinstance(entry, dict)
    }
    errors = component_catalog_errors(repo_root)
    discovered = set()
    for skill_file in sorted((repo_root / "skills").glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        if HARD_STOP.search(text):
            discovered.add(skill_file.parent.name)
    for skill in sorted(discovered):
        if skill not in by_skill:
            errors.append("%s hard-stops on missing config but has no scaffold entry" % skill)
    for skill, entry in sorted(by_skill.items()):
        if not skill:
            errors.append("scaffold entry missing skill")
            continue
        skill_file = repo_root / "skills" / skill / "SKILL.md"
        if not skill_file.is_file():
            errors.append("scaffold skill missing: %s" % skill)
        template = repo_root / str(entry.get("template") or "")
        if not template.is_file():
            errors.append("%s scaffold template missing: %s" % (skill, template))
        if not entry.get("config") or not entry.get("validator"):
            errors.append("%s scaffold needs config and validator" % skill)
        if template.suffix == ".json":
            try:
                parsed = json.loads(template.read_text(encoding="utf-8"))
                if not isinstance(parsed, dict):
                    errors.append("%s JSON scaffold must be an object" % skill)
            except (OSError, ValueError) as exc:
                errors.append("%s JSON scaffold invalid: %s" % (skill, exc))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    repo_root = Path(args[0]) if args else Path(__file__).resolve().parents[3]
    errors = audit(repo_root)
    if errors:
        for error in errors:
            print("FAIL: %s" % error)
        return 1
    print(
        "PASS: every documented fail-closed config has a scaffold; "
        "every skill and installer is cataloged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
