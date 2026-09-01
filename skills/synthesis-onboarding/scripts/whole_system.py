#!/usr/bin/env python3
"""Declarative whole-system model for synthesis-onboarding.

The JSON catalog defines the layer universe. This module owns deterministic,
stdlib-only transformations shared by init, kernel generation, doctor, and CI.
It performs no network access and no installation by itself.
"""

from __future__ import annotations

import copy
import json
import re
import shlex
from pathlib import Path


CATALOG_REL = Path("skills/synthesis-onboarding/references/layers.json")
SCAFFOLDS_REL = Path("skills/synthesis-onboarding/references/scaffolds.json")
POLICY_TEMPLATE_REL = Path(
    "skills/synthesis-onboarding/references/personal-policy.example.json"
)
KERNEL_TEMPLATE_REL = Path(
    "skills/synthesis-onboarding/references/kernel.example.md"
)
MESSAGE_TEMPLATE_REL = Path(
    "skills/synthesis-message-guard/patterns.example.json"
)
CHIEF_TEMPLATE_REL = Path(
    "skills/synthesis-chief-of-staff/preferences.example.json"
)
CAPTURE_TEMPLATE_REL = Path(
    "skills/synthesis-knowledge-capture/config.example.json"
)

KERNEL_HARD_LIMIT = 55_000
KERNEL_WARN_RATIO = 0.85
WORKSPACE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62})$")

SEND_TOOL_MATCHER = (
    "mcp__.*__(slack_send_message|slack_send_message_draft|"
    "slack_schedule_message|draft_gmail_message|send_gmail_message|"
    "create_draft|update_draft|send_email|send_message)$"
)

KERNEL_EDIT_MATCHERS = {
    "claude": "Edit|Write|MultiEdit|NotebookEdit|Bash",
    "codex": "apply_patch|Edit|Write|NotebookEdit|Bash|exec_command|exec",
}


def _json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def load_catalog(repo_root: Path) -> dict:
    catalog = _json(Path(repo_root) / CATALOG_REL)
    if catalog.get("schema_version") != 1:
        raise ValueError("layer catalog schema_version must be 1")
    layers = catalog.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("layer catalog needs a non-empty layers list")
    ids = []
    for layer in layers:
        if not isinstance(layer, dict):
            raise ValueError("every layer must be an object")
        layer_id = layer.get("id")
        if not isinstance(layer_id, str) or not layer_id:
            raise ValueError("every layer needs an id")
        if layer.get("probe") != layer_id:
            raise ValueError("layer %s probe must equal its id" % layer_id)
        ids.append(layer_id)
    if len(ids) != len(set(ids)):
        raise ValueError("layer ids must be unique")
    for name, profile in (catalog.get("profiles") or {}).items():
        selected = profile.get("selected") if isinstance(profile, dict) else None
        if not isinstance(selected, list) or set(selected) - set(ids):
            raise ValueError("profile %s references unknown layers" % name)
    return catalog


def catalog_ids(catalog: dict) -> list[str]:
    return [layer["id"] for layer in catalog["layers"]]


def profile_choices(catalog: dict, profile: str, manifest_present: bool) -> dict:
    profiles = catalog.get("profiles") or {}
    if profile not in profiles:
        raise ValueError("profile must be one of: %s" % ", ".join(sorted(profiles)))
    selected = set(profiles[profile]["selected"])
    if manifest_present and profile == "full":
        selected.add("organization")
    return {
        layer_id: ("selected" if layer_id in selected else "declined")
        for layer_id in catalog_ids(catalog)
    }


def load_answers(path: Path | None) -> dict:
    if path is None:
        return {}
    return _json(Path(path))


def validate_answers(answers: dict, require_workspace: bool) -> dict:
    if not isinstance(answers, dict):
        raise ValueError("answers must be a JSON object")
    workspace = str(answers.get("workspace") or "").strip()
    if require_workspace and not workspace:
        raise ValueError("answers.workspace is required for this profile")
    if workspace and not WORKSPACE_RE.fullmatch(workspace):
        raise ValueError(
            "answers.workspace must contain lowercase letters, digits, and hyphens"
        )
    timezone = str(answers.get("timezone") or "UTC").strip()
    if not timezone or any(char.isspace() for char in timezone):
        raise ValueError("answers.timezone must be a non-empty IANA-style value")
    tone = answers.get("tone", ["direct", "substantive", "kind"])
    avoid = answers.get("avoid_phrases", [])
    for key, value in (("tone", tone), ("avoid_phrases", avoid)):
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise ValueError("answers.%s must be a list of non-empty strings" % key)
    git_name = str(answers.get("git_name") or "").strip()
    git_email = str(answers.get("git_email") or "").strip()
    if bool(git_name) != bool(git_email):
        raise ValueError("answers.git_name and answers.git_email must be provided together")
    if git_name and ("\n" in git_name or "\r" in git_name):
        raise ValueError("answers.git_name must be one line")
    if git_email and (
        any(char.isspace() for char in git_email) or "@" not in git_email
    ):
        raise ValueError("answers.git_email must be a valid single-token email address")
    return {
        **answers,
        "workspace": workspace,
        "timezone": timezone,
        "tone": [item.strip() for item in tone],
        "avoid_phrases": [item.strip() for item in avoid],
        "git_name": git_name,
        "git_email": git_email,
    }


def _template(repo_root: Path, relative: Path) -> dict:
    return copy.deepcopy(_json(Path(repo_root) / relative))


def build_personal_policy(repo_root: Path, answers: dict) -> dict:
    policy = _template(repo_root, POLICY_TEMPLATE_REL)
    workspace = answers["workspace"]
    policy["workspace"] = workspace
    policy["identity"]["display_name"] = str(
        answers.get("display_name") or ""
    ).strip()
    policy["identity"]["working_relationship"] = str(
        answers.get("working_relationship") or "peer advisor"
    ).strip()
    policy["voice"]["tone"] = answers["tone"]
    policy["voice"]["avoid_phrases"] = answers["avoid_phrases"]
    policy["preferences"]["timezone"] = answers["timezone"]
    if isinstance(answers.get("working_hours"), dict):
        policy["preferences"]["working_hours"] = answers["working_hours"]
    if isinstance(answers.get("protected_hours"), list):
        policy["preferences"]["protected_hours"] = answers["protected_hours"]
    for key in ("personal_remote_patterns", "confidential_terms"):
        value = answers.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("answers.%s must be a list of strings" % key)
        policy["guard_patterns"][key] = value
    return policy


def build_message_guard_config(repo_root: Path, answers: dict) -> dict:
    config = _template(repo_root, MESSAGE_TEMPLATE_REL)
    existing = {entry["name"] for entry in config["block_patterns"]}
    for index, phrase in enumerate(answers["avoid_phrases"], start=1):
        name = "personal-avoid-%d" % index
        if name in existing:
            raise ValueError("duplicate message-guard pattern name: %s" % name)
        config["block_patterns"].append(
            {"name": name, "regex": re.escape(phrase)}
        )
    validate_message_guard(config)
    return config


def build_chief_preferences(repo_root: Path, answers: dict) -> dict:
    config = _template(repo_root, CHIEF_TEMPLATE_REL)
    config["timezone"] = answers["timezone"]
    if isinstance(answers.get("working_hours"), dict):
        config["working_hours"] = answers["working_hours"]
    if isinstance(answers.get("protected_hours"), list):
        config["protected_hours"] = answers["protected_hours"]
    validate_chief_preferences(config)
    return config


def build_capture_config(repo_root: Path, answers: dict, repo_path: Path) -> dict:
    config = _template(repo_root, CAPTURE_TEMPLATE_REL)
    config["domains"]["personal"]["repo"] = str(repo_path)
    config["confidential_terms"] = list(answers.get("confidential_terms") or [])
    validate_capture_config(config)
    return config


def validate_message_guard(config: dict) -> None:
    required = {
        "config_version",
        "gated_tool_patterns",
        "exempt_tool_patterns",
        "block_patterns",
        "warn_patterns",
        "ledger_max_age_minutes",
        "text_field_candidates",
    }
    missing = required - set(config)
    if missing:
        raise ValueError("message-guard config missing: %s" % ", ".join(sorted(missing)))
    if config.get("config_version") != 1:
        raise ValueError("message-guard config_version must be 1")
    if not config["gated_tool_patterns"] or not config["text_field_candidates"]:
        raise ValueError("message-guard needs gated tools and text fields")
    for item in config["block_patterns"] + config["warn_patterns"]:
        if not isinstance(item, dict) or not item.get("name") or not item.get("regex"):
            raise ValueError("message-guard patterns need name and regex")
        re.compile(item["regex"], re.IGNORECASE)
    for pattern in config["gated_tool_patterns"] + config["exempt_tool_patterns"]:
        re.compile(pattern)


def validate_chief_preferences(config: dict) -> None:
    required = {
        "config_version",
        "timezone",
        "working_hours",
        "protected_hours",
        "tiers",
        "meeting_defaults",
        "calendar_guardian",
    }
    missing = required - set(config)
    if missing:
        raise ValueError("chief-of-staff preferences missing: %s" % ", ".join(sorted(missing)))
    if config.get("config_version") != 1:
        raise ValueError("chief-of-staff config_version must be 1")
    hours = config["working_hours"]
    if not isinstance(hours, dict) or not hours.get("start") or not hours.get("end"):
        raise ValueError("chief-of-staff working_hours needs start and end")
    if not isinstance(config["tiers"], dict):
        raise ValueError("chief-of-staff tiers must be an object")


def validate_capture_config(config: dict) -> None:
    domains = config.get("domains")
    if config.get("config_version") != 1 or not isinstance(domains, dict) or not domains:
        raise ValueError("knowledge-capture config needs version 1 and at least one domain")
    for name, domain in domains.items():
        if not isinstance(domain, dict):
            raise ValueError("knowledge-capture domain %s must be an object" % name)
        missing = {"repo", "tier", "bundle_path"} - set(domain)
        if missing:
            raise ValueError(
                "knowledge-capture domain %s missing: %s"
                % (name, ", ".join(sorted(missing)))
            )


def validate_personal_policy(policy: dict) -> None:
    required = {"version", "workspace", "identity", "voice", "preferences", "guard_patterns"}
    missing = required - set(policy)
    if policy.get("version") != 1 or missing:
        raise ValueError("personal policy is not schema version 1")
    if not WORKSPACE_RE.fullmatch(str(policy.get("workspace") or "")):
        raise ValueError("personal policy workspace is invalid")


def render_kernel_source(policy: dict) -> str:
    validate_personal_policy(policy)
    relationship = policy["identity"].get("working_relationship") or "peer advisor"
    tone = ", ".join(policy["voice"].get("tone") or ["direct", "substantive"])
    avoids = policy["voice"].get("avoid_phrases") or []
    lines = [
        "<!-- synthesis-onboarding kernel source; edit this file, then run onboard.py kernel -->",
        "",
        "# Agent instruction kernel",
        "",
        "## Working relationship",
        "",
        "Work with me as a %s. Use a %s voice." % (relationship, tone),
        "",
        "## Always-on invariants",
        "",
        "- Search current source and local state before changing a system.",
        "- Never present an unverified external-state claim as confirmed.",
        "- Treat destructive operations and outward publication as separate approval gates.",
        "- Preserve user-edited files and unrelated concurrent work.",
        "- Use generic, non-identifying text on audible and banner notification surfaces.",
        "",
        "## Routing",
        "",
        "- Project or session work: load synthesis project management and context lifecycle.",
        "- Code implementation: load synthesis code planning; verify completion with synthesis implementation integrity.",
        "- Evidence, absence, or provenance questions: load synthesis grounding discipline.",
        "- Writing work: load the available content-quality, craft, pitfalls, and voice stack.",
        "",
        "## Enforcement declarations",
        "",
        "- Commit-boundary checks are enforced by synthesis git hooks; never bypass them.",
        "- Outgoing correspondence is enforced by synthesis message guard when that layer is selected and healthy.",
        "- Session lifecycle and coordination receipts are verified by the installed plugin.",
    ]
    if avoids:
        lines.extend(["", "## Personal wording boundaries", ""])
        lines.extend("- Avoid: %s" % phrase for phrase in avoids)
    return "\n".join(lines) + "\n"


def kernel_budget(content: str) -> tuple[int, str]:
    size = len(content.encode("utf-8"))
    if size > KERNEL_HARD_LIMIT:
        return size, "over"
    if size >= int(KERNEL_HARD_LIMIT * KERNEL_WARN_RATIO):
        return size, "warning"
    return size, "ok"


def rendered_kernel(source: str, client: str) -> str:
    if client not in ("claude", "codex"):
        raise ValueError("kernel client must be claude or codex")
    return (
        "<!-- generated by synthesis-onboarding from AGENTS.source.md; edit the source -->\n\n"
        + source
    )


def message_guard_hook(command_path: Path) -> dict:
    command = "python3 %s --gate" % shlex.quote(str(command_path))
    return {
        "matcher": SEND_TOOL_MATCHER,
        "hooks": [{"type": "command", "command": command}],
    }


def kernel_sync_hook(command_path: Path, client: str) -> dict:
    if client not in KERNEL_EDIT_MATCHERS:
        raise ValueError("kernel hook client must be claude or codex")
    command = "python3 %s --hook" % shlex.quote(str(command_path))
    return {
        "matcher": KERNEL_EDIT_MATCHERS[client],
        "hooks": [{"type": "command", "command": command, "timeout": 60}],
    }


def merge_message_guard_hook(existing: dict, command_path: Path) -> tuple[dict, bool]:
    if not isinstance(existing, dict):
        raise ValueError("client hook config must be a JSON object")
    result = copy.deepcopy(existing)
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("client hook config 'hooks' must be an object")
    entries = hooks.setdefault("PreToolUse", [])
    if not isinstance(entries, list):
        raise ValueError("client PreToolUse hooks must be a list")
    wanted = message_guard_hook(command_path)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        commands = [
            hook.get("command", "")
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ]
        if any("message_guard.py" in command for command in commands):
            if entry == wanted:
                return result, False
            entries[index] = wanted
            return result, True
    entries.append(wanted)
    return result, True


def merge_kernel_sync_hook(
    existing: dict, command_path: Path, client: str
) -> tuple[dict, bool]:
    if not isinstance(existing, dict):
        raise ValueError("client hook config must be a JSON object")
    result = copy.deepcopy(existing)
    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("client hook config 'hooks' must be an object")
    entries = hooks.setdefault("PostToolUse", [])
    if not isinstance(entries, list):
        raise ValueError("client PostToolUse hooks must be a list")
    wanted = kernel_sync_hook(command_path, client)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        commands = [
            hook.get("command", "")
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        ]
        if any("kernel_sync.py" in command for command in commands):
            if entry == wanted:
                return result, False
            entries[index] = wanted
            return result, True
    entries.append(wanted)
    return result, True


def dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
