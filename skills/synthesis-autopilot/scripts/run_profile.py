"""Strict profile preferences and read-only verification through the run engine.

Source profile schema 2 explicitly migrates schema 1 preferences. Effective
profiles use the engine's schema 1 contract. No file, JSON delta, plan checkbox
or profile text grants authority. The engine owns immutable profile bindings,
verified dispositions, amendments and the only durable execution state.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from workflow import resolve_profile

SCHEMA = 2
EFFECTIVE_SCHEMA = 1
USER_PROFILE_DEFAULT = os.path.expanduser("~/.synthesis/autopilot/profile.json")
PROJECT_OVERLAY_NAME = "resources/autopilot-profile.json"
DEFAULT_DIMENSIONS = {"domains": ["operations"], "uncertainty": "low", "effect": "none",
                      "horizon": "session", "parallelizable": False}
DEFAULT_PROFILE = {
    "schema": SCHEMA,
    "_comment": "Workflow preferences only. Action authority stays with existing action owners. Blog seeds are opt-in; lessons apply when reusable evidence emerges.",
    "items": {
        "end-to-end": {"text": "Complete the authorized outcome or report honestly incomplete work.", "evidence_hint": "Bound outcome criteria and retained obligations."},
        "framework-decisions": {"text": "Record important decisions with reasoning and evidence.", "evidence_hint": "Bound accepted reasoning or justified direct-task non-applicability.", "applicability": "if_material_decision"},
        "plan-current": {"text": "Keep the controlling plan current at material boundaries.", "evidence_hint": "Current plan and run projection."},
        "project-files-current": {"text": "Keep project recovery records current.", "evidence_hint": "Current checkpoint evidence."},
        "verify-before-done": {"text": "Verify actual outcomes before reporting completion.", "evidence_hint": "Fresh criterion-bound outcome evidence."},
        "lessons-filed": {"text": "Capture reusable lessons when evidence supports one.", "evidence_hint": "Accepted capture evidence when selected or triggered by a recorded reusable finding.", "applicability": "if_reusable_evidence"},
        "blog-seeds": {"text": "Capture user-requested blog material.", "evidence_hint": "Seed artifact.", "enabled": False, "reason": "Optional personal preference; opt in explicitly."},
        "completion-report": {"text": "Provide the domain-appropriate outcome, evidence, remaining obligations and decisions.", "evidence_hint": "Factual report derived from current accepted owner evidence; explicit report criteria add semantic requirements."},
    },
}


def _fields(data, allowed, required=()):
    if not isinstance(data, dict) or set(data) - set(allowed) or set(required) - set(data):
        raise ValueError("Profile contains unknown or missing fields")


def _text(value, name="text"):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("Profile requires nonempty bounded " + name)
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ValueError("Invalid profile item ID")
    return value


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key: " + key)
        value[key] = item
    return value


def _read_json(text):
    return json.loads(text, object_pairs_hook=_unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON value")))


def migrate_profile(data, label="profile"):
    """Validate/migrate preferences in memory; never overwrite the source file."""
    _fields(data, {"schema", "_comment", "deploy_grant", "items", "checks", "dimensions"})
    schema = data.get("schema", 1)
    if type(schema) is not int or schema not in {1, SCHEMA}:
        raise ValueError("Unsupported profile schema")
    if "_comment" in data:
        _text(data["_comment"], "comment")
    result = copy.deepcopy(data)
    migration = None
    if schema == 1:
        migration = {"source": label, "from_schema": 1, "to_schema": SCHEMA, "renamed_items": {}}
        grant = result.pop("deploy_grant", None)
        if grant not in (None, "none", ""):
            migration["rejected_authority"] = "Legacy file grant was not authority and was not migrated"
    elif "deploy_grant" in data:
        raise ValueError("Profiles cannot grant authority; use authenticated action-owner approvals")
    result["schema"] = SCHEMA
    items = result.setdefault("items", {})
    if not isinstance(items, dict) or len(items) > 256:
        raise ValueError("Profile items must be a bounded object")
    if schema == 1 and "morning-report" in items:
        if "completion-report" in items:
            raise ValueError("Legacy report migration conflicts with an explicit completion-report item")
        items["completion-report"] = items.pop("morning-report")
        migration["renamed_items"]["morning-report"] = "completion-report"
    for item_id, spec in items.items():
        _id(item_id)
        _fields(spec, {"text", "evidence_hint", "enabled", "reason", "applicability", "criterion_ids"})
        if "enabled" in spec and type(spec["enabled"]) is not bool:
            raise ValueError("Profile enabled must be boolean")
        for key in ("text", "evidence_hint", "reason"):
            if key in spec:
                _text(spec[key], key)
        if "applicability" in spec and spec["applicability"] not in {"always", "if_reusable_evidence", "if_material_decision"}:
            raise ValueError("Unknown profile applicability")
        if "criterion_ids" in spec:
            refs = spec["criterion_ids"]
            if not isinstance(refs, list) or not refs or len(refs) > 256 or any(not isinstance(ref, str) for ref in refs) or len(refs) != len(set(refs)):
                raise ValueError("Profile criterion references must be nonempty unique IDs")
            for ref in refs:
                _id(ref)
    if "checks" in result and not isinstance(result["checks"], dict):
        raise ValueError("Adaptive checks must be an object")
    if "dimensions" in result:
        resolve_profile(result["dimensions"])
    return result, migration


def load_layer(path: Path, label: str) -> dict | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError("Profile layer must be a regular local file")
    try:
        data = _read_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unreadable {label}: {exc}") from exc
    # Validate here, retain original version for explicit migration provenance.
    migrate_profile(data, label)
    return data


def _merge_items(items, changes, source):
    for ident, spec in changes.items():
        _id(ident)
        old = items.get(ident, {})
        current = {**old, **copy.deepcopy(spec)}
        current.setdefault("enabled", True)
        current.setdefault("applicability", "always")
        if not current.get("text") or not current.get("evidence_hint"):
            raise ValueError("A new profile item needs text and evidence_hint")
        history = copy.deepcopy(old.get("history", []))
        history.append({"source": source, "enabled": current["enabled"], "applicability": current["applicability"], "reason": current.get("reason", "Explicit preference"),
                        "fields": sorted(spec)})
        current["history"] = history
        current["provenance"] = source
        items[ident] = current


def resolve_layers(user=None, project=None, deltas=None, *, dimensions=None):
    """Deterministic pure resolution; later layers change preferences only."""
    items = {}
    _merge_items(items, DEFAULT_PROFILE["items"], "shipped")
    migrations = []
    layers = {"shipped": "built-in", "user": None, "project": None, "deltas": None}
    adaptive_layers = []
    selected_dimensions = copy.deepcopy(DEFAULT_DIMENSIONS)
    for source, data in (("user", user), ("project", project)):
        if data is None:
            continue
        validated, migration = migrate_profile(data, source)
        if migration:
            migrations.append(migration)
        layers[source] = "provided"
        _merge_items(items, validated["items"], source)
        if "dimensions" in validated:
            selected_dimensions = validated["dimensions"]
        if "checks" in validated:
            adaptive_layers.append({"source": source, "checks": validated["checks"]})
    if deltas is not None:
        _fields(deltas, {"disable", "add", "checks"})
        layers["deltas"] = "explicit preferences; not authority"
        disabled = deltas.get("disable", [])
        added = deltas.get("add", [])
        if not isinstance(disabled, list) or not isinstance(added, list) or len(disabled) + len(added) > 256:
            raise ValueError("Profile deltas must be bounded lists")
        for ident in disabled:
            _id(ident)
            if ident not in items:
                raise ValueError("Cannot disable an unknown item")
            _merge_items(items, {ident: {"enabled": False, "reason": "Explicit user preference"}}, "deltas")
        seen = set()
        for item in added:
            _fields(item, {"id", "text", "evidence_hint", "criterion_ids"}, {"id", "text", "evidence_hint"})
            ident = _id(item["id"])
            if ident in seen:
                raise ValueError("Duplicate added item")
            seen.add(ident)
            spec = {k: v for k, v in item.items() if k != "id"}
            spec["enabled"] = True
            validated, _ = migrate_profile({"schema": SCHEMA, "items": {ident: spec}}, "deltas")
            _merge_items(items, validated["items"], "deltas")
        if "checks" in deltas:
            adaptive_layers.append({"source": "deltas", "checks": deltas["checks"]})
    if dimensions is not None:
        selected_dimensions = copy.deepcopy(dimensions)
    adaptive = resolve_profile(selected_dimensions, adaptive_layers)
    for ident, check in adaptive["checks"].items():
        if ident in items:
            raise ValueError("Personal item collides with a mandatory adaptive check")
        enabled = check["status"] in {"required", "enabled"}
        items[ident] = {"text": check.get("description", "Verify " + ident + " against the requested outcome."),
                        "evidence_hint": "Fresh bound domain evidence or validated optional disposition.",
                        "enabled": enabled, "applicability": "always", "required": check["status"] == "required",
                        "history": copy.deepcopy(check["provenance"]), "provenance": "adaptive", "status": check["status"]}
    effective, disabled = [], []
    for ident, spec in items.items():
        item = {"id": ident, **spec}
        if item["enabled"]:
            item.setdefault("required", item["applicability"] == "always")
            effective.append(item)
        else:
            disabled.append(item)
    result = {"schema": EFFECTIVE_SCHEMA, "source_schema": SCHEMA, "layers": layers, "migrations": migrations,
            "deploy_grant": {"text": "none", "provenance": "none"}, "authority_granted": False,
            "disabled": disabled, "items": effective, "adaptive": adaptive}
    validate_profile_contract(result)
    return result


def validate_profile_contract(profile, contract=None):
    """Custom preferences need concrete criteria; canonical meaning stays fixed.

    A contract criterion may declare profile_item_ids to make a decision,
    report or lesson part of the accepted outcome without another preference
    file. These references select obligations, never action authority.
    """
    from profile_evidence import CANONICAL_IDS
    declared = {row["id"] for row in contract["criteria"]} if contract is not None else None
    items = {row["id"]: row for row in profile["items"]}
    mapped = {}
    if contract is not None:
        for criterion in contract["criteria"]:
            if "profile_item_ids" not in criterion:
                continue
            refs = criterion["profile_item_ids"]
            if not isinstance(refs, list) or not refs or len(refs) > 32 or any(not isinstance(ref, str) for ref in refs) or len(refs) != len(set(refs)):
                raise ValueError("Criterion profile item references must be bounded unique IDs")
            for identity in refs:
                _id(identity)
                if identity not in CANONICAL_IDS and identity not in items:
                    raise ValueError("Criterion maps an unknown profile item")
                mapped.setdefault(identity, set()).add(criterion["id"])
    for identity, item in items.items():
        refs = item.get("criterion_ids", [])
        if (not isinstance(refs, list) or len(refs) > 256 or any(not isinstance(ref, str) for ref in refs) or len(refs) != len(set(refs))):
            raise ValueError("Profile criterion mapping must be bounded and unique")
        for reference in refs:
            _id(reference)
        if declared is not None and set(refs) - declared:
            raise ValueError("Profile item maps an undeclared criterion: " + identity)
        if identity not in CANONICAL_IDS and not refs and not mapped.get(identity):
            raise ValueError("Custom profile item requires concrete criterion_ids: " + identity)
    return profile


def resolve(project: Path, user_profile: Path, deltas=None, *, dimensions=None):
    user = load_layer(Path(user_profile), "user")
    overlay = load_layer(Path(project) / PROJECT_OVERLAY_NAME, "project")
    return resolve_layers(user, overlay, deltas, dimensions=dimensions)


def verify(project: Path, run_id: str, *, actor: dict):
    """Read the current engine report; do not mint or write a verification receipt."""
    from autopilot import engine
    # The same registry used by native hooks includes workflow and capability constraints.
    return engine().completion_report(Path(project), run_id, actor=actor)


def cmd_init(stdout: bool) -> int:
    payload = json.dumps(DEFAULT_PROFILE, indent=2) + "\n"
    if stdout:
        sys.stdout.write(payload)
        return 0
    dest = Path(USER_PROFILE_DEFAULT)
    if dest.exists() or dest.is_symlink():
        raise ValueError("User profile exists; explicit migration preserves its preferences")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as handle:
        handle.write(payload)
    print(f"User profile written: {dest}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Resolve strict adaptive preferences; verify durable run evidence.")
    sub = parser.add_subparsers(dest="mode", required=True)
    init = sub.add_parser("init")
    init.add_argument("--stdout", action="store_true")
    resolver = sub.add_parser("resolve")
    resolver.add_argument("--project", required=True)
    resolver.add_argument("--user-profile", default=USER_PROFILE_DEFAULT)
    resolver.add_argument("--delta-json")
    resolver.add_argument("--dimensions-json")
    resolver.add_argument("--out")
    verifier = sub.add_parser("verify")
    verifier.add_argument("--project", required=True)
    verifier.add_argument("--run-id", required=True)
    verifier.add_argument("--actor", required=True, help="Native actor JSON file; identity is independently admitted by PM")
    try:
        args = parser.parse_args(argv)
        if args.mode == "init":
            return cmd_init(args.stdout)
        if args.mode == "resolve":
            effective = resolve(Path(args.project), Path(args.user_profile), _read_json(args.delta_json) if args.delta_json else None,
                                dimensions=_read_json(args.dimensions_json) if args.dimensions_json else None)
            encoded = json.dumps(effective, indent=2) + "\n"
            if args.out:
                with Path(args.out).open("x", encoding="utf-8") as handle:
                    handle.write(encoded)
            else:
                sys.stdout.write(encoded)
            return 0
        report = verify(Path(args.project), args.run_id, actor=_read_json(Path(args.actor).read_text(encoding="utf-8")))
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 2
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"run_profile: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
