#!/usr/bin/env python3
"""Validate a synthesis-absence-coordination config.

A config error in this skill is not a crash — it is a wrong message sent to the
wrong person, or a message silently not sent at all. Both are discovered late and
cost trust. This validator moves those failures to config time.

Exit codes follow the synthesis guard contract:
    0 — valid
    1 — defects found
    2 — could not establish ground truth (missing/unreadable/unparseable config)

A check that cannot run must never look like a check that passed.

Usage:
    python3 validate_config.py [path]          # defaults to the standard location
    python3 validate_config.py --quiet [path]  # exit code plus one summary line
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_PATH = "~/.synthesis/absence-coordination/config.yaml"

CONTENT_POLICIES = {
    "dates_only",
    "dates_city",
    "dates_city_coverage",
    "dates_city_coverage_reach",
    "dates_coverage_reach",
    "dates_child_logistics",
    "dates_timezone_facilities",
}

CORE_GATES = {
    "no_group_post_before_principals_notified",
    "no_send_before_conflict_check_all_calendars",
    "no_send_before_coverage_statement_present",
    "principal_tier_is_draft_only",
    "amendments_update_existing_rows_never_repost",
}

# Local-parts that usually indicate a distribution alias rather than a person.
# An alias cannot be audited, dies silently in provider migrations, and cannot
# carry two content policies. See SKILL.md, "Never use a distribution alias".
ALIAS_HINTS = {
    "family", "team", "all", "everyone", "group", "staff",
    "leadership", "list", "announce", "everybody", "folks",
}

defects: list[str] = []
warnings: list[str] = []


def defect(msg: str, fix: str = "") -> None:
    defects.append(msg + (f"\n        -> {fix}" if fix else ""))


def warn(msg: str, fix: str = "") -> None:
    warnings.append(msg + (f"\n        -> {fix}" if fix else ""))


def load(path: Path):
    try:
        import yaml
    except ImportError:
        print("UNVERIFIED: pyyaml is not installed, so the config could not be parsed.")
        print("  -> pip install pyyaml (or run via `uv run --with pyyaml`)")
        raise SystemExit(2)

    if not path.exists():
        print(f"UNVERIFIED: no config at {path}")
        print("  -> copy example-config.yaml there and fill it in")
        raise SystemExit(2)

    try:
        data = yaml.safe_load(path.read_text())
    except Exception as exc:  # noqa: BLE001 - report any parse failure verbatim
        print(f"UNVERIFIED: {path} is not parseable YAML: {exc}")
        raise SystemExit(2)

    if not isinstance(data, dict):
        print(f"UNVERIFIED: {path} did not parse to a mapping.")
        raise SystemExit(2)
    return data


def check_tiers(cfg: dict) -> dict:
    tiers = cfg.get("recipient_tiers")
    if not isinstance(tiers, list) or not tiers:
        defect("no recipient_tiers defined", "add at least one tier; see example-config.yaml")
        return {}

    by_id: dict[str, dict] = {}
    for i, tier in enumerate(tiers):
        if not isinstance(tier, dict) or "id" not in tier:
            defect(f"recipient_tiers[{i}] has no id")
            continue
        tid = tier["id"]
        if tid in by_id:
            defect(f"duplicate tier id '{tid}'", "tier ids must be unique")
        by_id[tid] = tier

        policy = tier.get("content")
        if policy is None:
            defect(f"tier '{tid}' has no content policy",
                   "disclosure must be mechanical, not decided per send")
        elif policy not in CONTENT_POLICIES:
            defect(f"tier '{tid}' uses unknown content policy '{policy}'",
                   "one of: " + ", ".join(sorted(CONTENT_POLICIES)))

        members = tier.get("members") or []
        targets = tier.get("targets") or []
        if not members and not targets and tier.get("send_mode") != "draft_only":
            warn(f"tier '{tid}' has no members or targets", "it will never notify anyone")

        # Alias heuristic — the failure this catches is invisible until someone
        # who should have known says they never heard.
        for addr in members:
            if not isinstance(addr, str) or "@" not in addr:
                # A non-email member (TODO marker, name, note) cannot receive
                # mail. It fails loudly at send time — good — but the config
                # should say so up front rather than let it look complete.
                warn(f"tier '{tid}' member '{addr}' is not an email address",
                     "placeholder? fill it in before this tier is used")
                continue
            local = addr.split("@", 1)[0].lower()
            if local in ALIAS_HINTS:
                warn(
                    f"tier '{tid}' member '{addr}' looks like a distribution alias",
                    "use explicit recipients: an alias cannot be audited, dies silently "
                    "in provider migrations, and cannot carry two content policies",
                )

    # The ordering fix.
    principals = by_id.get("principals")
    if principals is None:
        warn("no 'principals' tier", "most setups need one; skip only if genuinely flat")
    else:
        if principals.get("send_mode") != "draft_only":
            defect("principals tier is not send_mode: draft_only",
                   "a note to your manager or CEO about your own absence is never agent-sent")
        cc = principals.get("cc")
        if not cc:
            warn("principals tier has no cc",
                 "cc: tier:exec_assistants gives assistants identical lead time in one message")
        elif isinstance(cc, str) and cc.startswith("tier:"):
            ref = cc.split(":", 1)[1]
            if ref not in by_id:
                defect(f"principals.cc references unknown tier '{ref}'")

    # Group posts must be gated.
    for tid, tier in by_id.items():
        if tier.get("channel") == "chat" and tier.get("gate") != "after_principals":
            defect(f"chat tier '{tid}' is not gated behind principals",
                   "set gate: after_principals — a manager must never learn of an "
                   "absence from a group channel")

    return by_id


def check_types(cfg: dict, tier_ids: set[str]) -> None:
    types = cfg.get("absence_types")
    if not isinstance(types, dict) or not types:
        defect("no absence_types defined")
        return

    for name, spec in types.items():
        if not isinstance(spec, dict):
            defect(f"absence_types.{name} is not a mapping")
            continue
        for field in ("lead_time_days", "visibility"):
            if field not in spec:
                defect(f"absence_types.{name} is missing '{field}'")
        vis = spec.get("visibility")
        if vis not in (None, "standard", "minimal"):
            defect(f"absence_types.{name}.visibility '{vis}' is invalid",
                   "use 'standard' or 'minimal'")

    if not any(
        isinstance(s, dict) and s.get("visibility") == "minimal" for s in types.values()
    ):
        warn("no absence type with visibility: minimal",
             "without a quiet type the system can only broadcast, and gets abandoned "
             "exactly when discretion matters most")

    for tid in cfg.get("notify_on_commit_tiers") or []:
        if tid not in tier_ids:
            defect(f"notify_on_commit_tiers references unknown tier '{tid}'")


def check_travel(cfg: dict) -> None:
    integrations = cfg.get("integrations") or {}
    svc = integrations.get("travel_service") or {}
    if not svc.get("enabled"):
        return

    verified = ((cfg.get("principal") or {}).get("travel_verified_address") or "").strip()
    sends_from = (svc.get("must_send_from") or "").strip()

    if not sends_from:
        defect("travel_service.enabled but must_send_from is unset",
               "forwards from an unverified address are discarded SILENTLY")
    elif verified and sends_from.lower() != verified.lower():
        # The highest-value check in this file.
        defect(
            f"travel_service.must_send_from ({sends_from}) does not match "
            f"principal.travel_verified_address ({verified})",
            "the service discards mail from unverified senders with no bounce — "
            "the trip simply never appears, and nothing surfaces the failure",
        )

    if not svc.get("verify_trip_created"):
        warn("travel_service.verify_trip_created is not set",
             "forwarding failures are silent; verify the trip exists afterwards")

    ooo = integrations.get("out_of_office") or {}
    if ooo.get("enabled") and not ooo.get("clear_on_return"):
        warn("out_of_office.clear_on_return is not set",
             "a responder still firing after return signals nobody owns the system")


def check_coverage_and_gates(cfg: dict) -> None:
    coverage = cfg.get("coverage") or {}
    src = coverage.get("source")
    if src not in ("external", "inline"):
        defect(f"coverage.source '{src}' is invalid", "use 'external' or 'inline'")
    if not coverage.get("required_before"):
        warn("coverage.required_before is empty",
             "coverage is required content — an absence without a delegate relocates "
             "the blocker rather than removing it")

    declared = set(cfg.get("gates") or [])
    for missing in sorted(CORE_GATES - declared):
        warn(f"core gate not declared: {missing}")


def check_calendars(cfg: dict) -> None:
    cals = cfg.get("calendars") or {}
    if not cals.get("personal") and not cals.get("work_ooo"):
        defect("no personal or work calendar configured")
    for entry in cals.get("shared") or []:
        if isinstance(entry, dict) and entry.get("status") == "unknown":
            warn(f"shared calendar '{entry.get('id')}' is unresolved",
                 "absences will not appear on it until the URL is filled in")
    if not cals.get("outside_mirror"):
        warn("calendars.outside_mirror is empty",
             "if any calendar sits outside your cross-calendar blocker, list it — "
             "those are invisible exactly when you check for conflicts")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--quiet"]
    quiet = "--quiet" in sys.argv
    path = Path(args[0] if args else DEFAULT_PATH).expanduser()

    cfg = load(path)

    if cfg.get("version") != 1:
        warn(f"version is {cfg.get('version')!r}, expected 1")

    tiers = check_tiers(cfg)
    check_types(cfg, set(tiers))
    check_travel(cfg)
    check_coverage_and_gates(cfg)
    check_calendars(cfg)

    if not quiet:
        print(f"absence-coordination config check — {path}\n")
        for d in defects:
            print(f"  FAIL  {d}")
        for w in warnings:
            print(f"  warn  {w}")
        if not defects and not warnings:
            print("  ok    all checks passed")
        print()

    if defects:
        print(f"DEFECTS: {len(defects)} defect(s), {len(warnings)} warning(s).")
        return 1
    print(f"VALID: 0 defects, {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
