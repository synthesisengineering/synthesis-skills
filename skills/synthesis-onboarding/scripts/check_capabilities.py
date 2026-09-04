#!/usr/bin/env python3
"""Fail closed when public install surfaces drift from the engine contract."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from synthesis_cli import CLI_COMMANDS
from system_contract import (
    ContractError,
    load_contract_documents,
    validate_invite,
    validate_org_manifest,
)


class CapabilityError(ValueError):
    pass


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CapabilityError("%s must contain an object" % path)
    return value


def _require(text: str, fragment: str, surface: str) -> None:
    if fragment not in text:
        raise CapabilityError("%s is missing required capability text: %s" % (surface, fragment))


def _frontmatter_description(text: str) -> str:
    match = re.search(r'^description:\s*["\'](.*)["\']\s*$', text, re.MULTILINE)
    if not match:
        raise CapabilityError("quick-answers skill has no one-line description")
    return match.group(1)


def validate(repo_root: Path) -> None:
    root = Path(repo_root).resolve()
    refs = root / "skills" / "synthesis-onboarding" / "references"
    contracts = load_contract_documents(root)
    capabilities = contracts["capabilities"]
    layers = _json(refs / "layers.json")
    components = _json(refs / "components.json")

    if tuple(capabilities["cli"]["commands"]) != CLI_COMMANDS:
        raise CapabilityError("release capability commands do not match the public CLI")
    if capabilities["release_policy"]["default_channel"] != "stable":
        raise CapabilityError("stable must remain the default release channel")
    if capabilities["release_policy"]["channels"] != {"stable": "stable", "edge": "main"}:
        raise CapabilityError("stable and edge refs drifted")
    if capabilities["release_policy"]["automatic_updates"] is not False:
        raise CapabilityError("updates must remain user or agent initiated")
    if capabilities["manifest_schema_version"] != 2:
        raise CapabilityError("organization manifest capability must match schema 2")

    layer_ids = [entry["id"] for entry in layers["layers"]]
    if len(layer_ids) != len(set(layer_ids)):
        raise CapabilityError("layer identifiers must be unique")
    if capabilities["layers"] != [
        {"id": entry["id"], "title": entry["title"], "description": entry["description"]}
        for entry in layers["layers"]
    ]:
        raise CapabilityError("release capability layer catalog drifted")
    for profile, layer_profile in layers["profiles"].items():
        declared = capabilities["profiles"].get(profile)
        if declared is None:
            raise CapabilityError("release capabilities omit profile %s" % profile)
        if declared["selected_layers"] != layer_profile["selected"]:
            raise CapabilityError("profile layer drift: %s" % profile)
        if set(declared["selected_layers"]) - set(layer_ids):
            raise CapabilityError("profile %s names an unknown layer" % profile)
    if capabilities["profiles"]["full"]["conditional_layers"] != ["organization"]:
        raise CapabilityError("organization must be the full profile's only conditional layer")
    if capabilities["profiles"]["skills-only"]["conditional_layers"] != ["organization"]:
        raise CapabilityError("skills-only must expose the additive organization layer")

    component_paths = {entry["path"] for entry in components["installers"]}
    for path in ("install.sh", "onboard.sh"):
        if path not in component_paths or not (root / path).is_file():
            raise CapabilityError("installer capability is missing: %s" % path)
    direct_copy = root / "skills" / "synthesis-onboarding" / "scripts" / "direct_copy.sh"
    if not direct_copy.is_file():
        raise CapabilityError("fixed direct-copy capability is missing")

    readme = (root / "README.md").read_text(encoding="utf-8")
    for fragment in (
        "raw.githubusercontent.com/synthesisengineering/synthesis-skills/stable/onboard.sh",
        "setup --profile skills-only",
        "synthesis update",
        "synthesis doctor",
        "synthesis workspace ensure",
        "synthesis enroll",
    ):
        _require(readme, fragment, "README.md")

    bootstrap = (root / "onboard.sh").read_text(encoding="utf-8")
    for fragment in (
        'stable) SOURCE_REF="stable"',
        'edge) SOURCE_REF="main"',
        'SOURCE_REF="v$VERSION_PIN"',
        "GIT_ALLOW_PROTOCOL=https",
    ):
        _require(bootstrap, fragment, "onboard.sh")

    org_doc = (refs / "org-manifest.md").read_text(encoding="utf-8")
    _require(org_doc, "version: 2", "organization manifest guide")
    example_match = re.search(
        r"## Schema 2 example\s+```yaml\n(.*?)\n```", org_doc, re.DOTALL
    )
    if not example_match:
        raise CapabilityError("organization guide has no parseable Schema 2 example")
    validate_org_manifest(yaml.safe_load(example_match.group(1)), "org-manifest.md example")
    for forbidden in ("installer_args:", "source_env:", "status_args:", "superseded_remotes:", "migrations:"):
        if forbidden in org_doc:
            raise CapabilityError("organization guide still permits executable or migration field %s" % forbidden)
    invite_schema = _json(refs / "invite.schema.json")
    if "nonce" not in invite_schema.get("required", []):
        raise CapabilityError("invite schema does not require its replay nonce")
    nonce_pattern = (
        (invite_schema.get("properties") or {}).get("nonce") or {}
    ).get("pattern")
    if nonce_pattern != "^[A-Za-z0-9_-]{16,128}$":
        raise CapabilityError("invite nonce schema drifted from the runtime")
    now = datetime.now(timezone.utc)
    invite = {
        "schema_version": 1,
        "repository": "https://example.test/org/onboarding.git",
        "provider": "generic",
        "manifest_path": ".agents/onboarding.yaml",
        "nonce": "capability_nonce_0123456789",
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
    }
    validate_invite(invite, now=now)
    try:
        validate_invite({key: value for key, value in invite.items() if key != "nonce"}, now=now)
    except ContractError:
        pass
    else:
        raise CapabilityError("runtime accepts an invite without the required nonce")

    quick = (root / "skills" / "synthesis-quick-answers" / "SKILL.md").read_text(encoding="utf-8")
    if len(_frontmatter_description(quick)) > 1024:
        raise CapabilityError("quick-answers description exceeds the catalog budget")
    for fragment in ("synthesis workspace ensure", ".agents/workspace-AGENTS.md"):
        _require(quick, fragment, "quick-answers skill")
    if "onboard.py init-workspace" in quick:
        raise CapabilityError("quick-answers bypasses the stable public CLI")

    claude = _json(root / ".claude-plugin" / "plugin.json")
    codex = _json(root / ".codex-plugin" / "plugin.json")
    if claude.get("version") != codex.get("version"):
        raise CapabilityError("client release identities disagree")
    if capabilities["release_identity_source"] != ".codex-plugin/plugin.json":
        raise CapabilityError("release identity source drifted")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]) if args else Path(__file__).resolve().parents[3]
    try:
        validate(root)
    except (CapabilityError, KeyError, OSError, ValueError) as exc:
        print("FAIL release capability contract: %s" % exc, file=sys.stderr)
        return 1
    print("PASS release capability contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
