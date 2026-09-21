"""Autopilot run profiles — the delegation contract as data.

The failure this exists to prevent: a principal retypes a paragraph of
standing instructions for every autonomous run ("follow the project
protocols, keep the files current, capture lessons, use my decision
framework, ..."). Retyped instructions drift (each retelling drops a
clause), decay (compaction eats them mid-run), and skip silently (a
dropped clause simply doesn't happen). This module resolves the
effective checklist deterministically at engagement, freezes it into
the plan file, and verifies every item's disposition before close.

Layers, weakest first: shipped default < user profile
(~/.synthesis/autopilot/profile.json, synced across the fleet) <
project overlay (<project>/resources/autopilot-profile.json) < spoken
deltas from the delegation message. Every item carries its provenance;
disabled-by-config items stay visible in the resolution instead of
vanishing.

Authority rule (D7): profiles may narrow authority, never grant it. A
deploy grant stored in any file layer is forced to "none" with a
warning; only the run's delegation message (the delta layer) can grant
deployment authority, and the grant's provenance is recorded.

Single source of disposition: the plan file's "## Standing checklist
(frozen ...)" section. verify parses it strictly; gate close
--goals-met refuses without a fresh verifier receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
USER_PROFILE_DEFAULT = os.path.expanduser("~/.synthesis/autopilot/profile.json")
PROJECT_OVERLAY_NAME = "resources/autopilot-profile.json"

# The shipped default. Single source: `init` emits exactly this.
DEFAULT_PROFILE = {
    "schema": SCHEMA,
    "_comment": "Autopilot run profile. enabled:false skips an item for every run (visible in the resolution, never silent). Added items need id, text, evidence_hint. deploy_grant in a FILE is always ignored — authority comes only from the run's delegation message.",
    "deploy_grant": None,
    "items": {
        "end-to-end": {
            "text": "Complete the work end to end — all phases closed or honestly incomplete.",
            "evidence_hint": "Phases section of the plan file.",
        },
        "framework-decisions": {
            "text": "Open important decisions go through the thinking framework, recorded with rationale.",
            "evidence_hint": "Dated entries in the plan file's Decisions log.",
        },
        "plan-current": {
            "text": "Plan file re-read after any suspected compaction and updated at every phase boundary.",
            "evidence_hint": "Cycle ledger entries and phase checkboxes.",
        },
        "project-files-current": {
            "text": "Project files (CONTEXT, sessions, state) current at every phase boundary and at close.",
            "evidence_hint": "Checkpoint receipt or git log of the project.",
        },
        "verify-before-done": {
            "text": "Verification before any completion claim: focused tests per change, full affected suites per phase.",
            "evidence_hint": "Test commands and results in the session record.",
        },
        "lessons-filed": {
            "text": "Durable lessons filed as work proceeds, not at the end.",
            "evidence_hint": "Lesson file paths, or WAIVED with a reason.",
        },
        "blog-seeds": {
            "text": "Blog-material seeds captured as work proceeds.",
            "evidence_hint": "Seed file paths, or WAIVED with a reason.",
        },
        "morning-report": {
            "text": "Completion report plus batched questions (decision packet when complex) ready at close.",
            "evidence_hint": "Report path and packet paths.",
        },
    },
}

CHECKLIST_HEADING = "## Standing checklist (frozen"
ITEM_RE = re.compile(r"^-\s+\[(x| )\]\s+(\S+)\s+[—–-]\s+(.*)$")
DEPLOY_LINE_RE = re.compile(r"^Deploy authority this run:\s+(.*)$")


def warn(message: str) -> None:
    print(f"run_profile: {message}", file=sys.stderr)


def load_layer(path: Path, label: str) -> dict | None:
    """Load one profile layer. Missing file is fine (None); malformed JSON is fatal."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"run_profile: {label} {path} is unreadable: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"run_profile: {label} {path} must be a JSON object")
    if data.get("schema", SCHEMA) != SCHEMA:
        raise SystemExit(
            f"run_profile: {label} {path} has schema {data.get('schema')!r}, "
            f"this loader speaks {SCHEMA}")
    for key in data:
        if key not in ("schema", "_comment", "deploy_grant", "items"):
            warn(f"{label} {path}: unknown key {key!r} ignored")
    items = data.get("items", {})
    if not isinstance(items, dict):
        raise SystemExit(f"run_profile: {label} {path}: 'items' must be an object")
    return data


def apply_layer(effective: dict[str, dict], disabled: list[dict],
                data: dict, provenance: str, label: str) -> None:
    """Merge one layer into the effective item set. Later layers win."""
    for item_id, spec in data.get("items", {}).items():
        if not isinstance(spec, dict):
            raise SystemExit(f"run_profile: {label}: item {item_id!r} must be an object")
        for key in spec:
            if key not in ("text", "evidence_hint", "enabled"):
                warn(f"{label}: item {item_id!r} has unknown key {key!r}, ignored")
        if spec.get("enabled", True) is False:
            effective.pop(item_id, None)
            disabled.append({"id": item_id, "by": provenance})
            continue
        merged = dict(effective.get(item_id, {}))
        if "text" in spec:
            merged["text"] = spec["text"]
        if "evidence_hint" in spec:
            merged["evidence_hint"] = spec["evidence_hint"]
        if "text" not in merged or "evidence_hint" not in merged:
            raise SystemExit(
                f"run_profile: {label}: item {item_id!r} needs text and "
                "evidence_hint (it is new — shipped defaults carry their own)")
        merged["provenance"] = provenance
        effective[item_id] = merged


def resolve(project: Path, user_profile: Path,
            deltas: dict | None) -> dict:
    """Resolve the effective checklist from all layers. Pure except warnings."""
    effective: dict[str, dict] = {}
    disabled: list[dict] = []
    shipped = {"schema": SCHEMA, "items": DEFAULT_PROFILE["items"]}
    apply_layer(effective, disabled, shipped, "shipped", "shipped default")
    layers: dict[str, str | None] = {"shipped": "built-in", "user": None,
                                     "project": None, "deltas": None}
    user_data = load_layer(user_profile, "user profile")
    if user_data is not None:
        layers["user"] = str(user_profile)
        if user_data.get("deploy_grant"):
            warn("user profile deploy_grant ignored: authority comes only "
                 "from the run's delegation message, never from a file (D7)")
        apply_layer(effective, disabled, user_data, "user", "user profile")
    overlay = project / PROJECT_OVERLAY_NAME
    project_data = load_layer(overlay, "project overlay")
    if project_data is not None:
        layers["project"] = str(overlay)
        if project_data.get("deploy_grant"):
            warn("project overlay deploy_grant ignored: authority comes only "
                 "from the run's delegation message, never from a file (D7)")
        apply_layer(effective, disabled, project_data, "project",
                    "project overlay")
    deploy_grant = {"text": "none", "provenance": "none"}
    if deltas:
        layers["deltas"] = f"{len(deltas)} spoken delta(s)"
        if not isinstance(deltas, dict):
            raise SystemExit("run_profile: --delta-json must be a JSON object")
        for key in deltas:
            if key not in ("disable", "add", "deploy_grant"):
                warn(f"spoken deltas: unknown key {key!r} ignored")
        for item_id in deltas.get("disable", []) or []:
            effective.pop(item_id, None)
            disabled.append({"id": item_id, "by": "spoken"})
        for spec in deltas.get("add", []) or []:
            if not isinstance(spec, dict) or "id" not in spec:
                raise SystemExit("run_profile: each added item needs id, "
                                 "text, evidence_hint")
            apply_layer(effective, disabled,
                        {"items": {spec["id"]: spec}}, "spoken",
                        "spoken deltas")
        grant = deltas.get("deploy_grant")
        if grant:
            deploy_grant = {"text": " ".join(str(grant).split()),
                            "provenance": "spoken"}
    items = [{"id": item_id, **spec} for item_id, spec in effective.items()]
    return {
        "schema": SCHEMA,
        "resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layers": layers,
        "deploy_grant": deploy_grant,
        "disabled": disabled,
        "items": items,
    }


def gate_entry_for_plan(plan: Path) -> Path:
    """Mirror of autopilot_gate.entry_path (duplicated: no import coupling).

    Byte-identical derivation: abspath WITHOUT resolve, because /tmp is a
    symlink on macOS and the gate keys on the unresolved spelling.
    """
    abs_plan = os.path.abspath(os.path.expanduser(str(plan)))
    key = hashlib.sha1(abs_plan.encode()).hexdigest()[:12]
    state = Path(os.environ.get(
        "AUTOPILOT_GATE_STATE_DIR",
        os.path.expanduser("~/.synthesis/autopilot/engagements")))
    return state / f"{Path(abs_plan).stem[:40]}-{key}.json"


def verify(plan: Path) -> dict:
    """Verify the plan's frozen checklist against the registered profile.

    Returns the receipt dict on success; raises SystemExit(2) naming every
    gap on failure. Every frozen item must be [x] with evidence or [ ]
    WAIVED with a reason; the deploy line must match the grant.
    """
    entry = gate_entry_for_plan(plan)
    if not entry.exists():
        raise SystemExit(f"run_profile: no engagement registered for {plan}")
    engagement = json.loads(entry.read_text(encoding="utf-8"))
    profile = engagement.get("profile")
    if not profile:
        raise SystemExit(f"run_profile: engagement for {plan} registered "
                         "without --profile; nothing frozen to verify")
    frozen = {item["id"]: item for item in profile["items"]}
    text = plan.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines)
                     if line.startswith(CHECKLIST_HEADING))
    except StopIteration:
        raise SystemExit(f"run_profile: {plan} has no {CHECKLIST_HEADING!r} "
                         "section; freeze the resolved checklist there")
    section = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        section.append(line)
    seen: dict[str, str] = {}
    problems: list[str] = []
    deploy_text: str | None = None
    for line in section:
        match = ITEM_RE.match(line)
        if match:
            checked, item_id, rest = match.groups()
            if item_id in seen:
                problems.append(f"item {item_id!r} listed twice")
            if item_id not in frozen:
                problems.append(f"item {item_id!r} is not in the frozen "
                                f"checklist ({sorted(frozen)})")
                continue
            rest = rest.strip()
            if checked == "x":
                if not rest:
                    problems.append(f"item {item_id!r} is checked without evidence")
                else:
                    seen[item_id] = f"done: {rest}"
            else:
                if not rest.startswith("WAIVED:") or not rest[7:].strip():
                    problems.append(
                        f"item {item_id!r} is unchecked without 'WAIVED: reason'")
                else:
                    seen[item_id] = f"waived: {rest[7:].strip()}"
            continue
        deploy = DEPLOY_LINE_RE.match(line)
        if deploy:
            deploy_text = " ".join(deploy.group(1).split())
    for item_id in frozen:
        if item_id not in seen:
            problems.append(f"item {item_id!r} has no disposition line")
    want_grant = " ".join(profile["deploy_grant"]["text"].split())
    if deploy_text is None:
        problems.append("'Deploy authority this run:' line missing from "
                       "the frozen checklist")
    elif deploy_text != want_grant:
        problems.append(f"deploy line says {deploy_text!r} but the frozen "
                        f"grant is {want_grant!r}")
    if problems:
        raise SystemExit("run_profile: checklist incomplete:\n  - "
                         + "\n  - ".join(problems))
    receipt = {
        "plan": os.path.abspath(os.path.expanduser(str(plan))),
        "plan_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "items": seen,
        "deploy_grant": profile["deploy_grant"],
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    receipt_path = entry.with_name(entry.stem + ".profile-verified.json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def cmd_init(stdout: bool) -> int:
    payload = json.dumps(DEFAULT_PROFILE, indent=2) + "\n"
    if stdout:
        sys.stdout.write(payload)
        return 0
    dest = Path(USER_PROFILE_DEFAULT)
    if dest.exists():
        print(f"run_profile: {dest} already exists; refusing to overwrite "
              "your profile (delete it to re-init)", file=sys.stderr)
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(payload, encoding="utf-8")
    print(f"user profile written: {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Autopilot run profiles: resolve, freeze, verify.")
    sub = parser.add_subparsers(dest="mode", required=True)
    init = sub.add_parser("init", help="write the default user profile")
    init.add_argument("--stdout", action="store_true",
                      help="print the default instead of writing it")
    resolve_p = sub.add_parser("resolve", help="resolve effective checklist")
    resolve_p.add_argument("--project", required=True,
                           help="project directory (reads its overlay)")
    resolve_p.add_argument("--user-profile", default=USER_PROFILE_DEFAULT)
    resolve_p.add_argument("--delta-json", default="",
                           help="spoken deltas as a JSON object string")
    resolve_p.add_argument("--out", default="",
                           help="write effective JSON here (default: stdout)")
    verify_p = sub.add_parser("verify", help="verify the frozen checklist")
    verify_p.add_argument("--plan", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "init":
            return cmd_init(args.stdout)
        if args.mode == "resolve":
            deltas = None
            if args.delta_json:
                try:
                    deltas = json.loads(args.delta_json)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"run_profile: --delta-json is not "
                                     f"JSON: {exc}")
            effective = resolve(Path(args.project),
                                Path(args.user_profile), deltas)
            payload = json.dumps(effective, indent=2) + "\n"
            if args.out:
                Path(args.out).write_text(payload, encoding="utf-8")
            else:
                sys.stdout.write(payload)
            return 0
        receipt = verify(Path(args.plan))
        print(f"checklist verified ({len(receipt['items'])} items, "
              f"deploy: {receipt['deploy_grant']['provenance']})")
        return 0
    except SystemExit as exc:
        message = str(exc.code) if not isinstance(exc.code, int) else ""
        if message:
            print(message, file=sys.stderr)
        return exc.code if isinstance(exc.code, int) else 2


if __name__ == "__main__":
    sys.exit(main())
