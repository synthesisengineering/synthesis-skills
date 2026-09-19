#!/usr/bin/env python3
"""Declared mailbox manifest: every account swept, every gap named.

Defect class (§5a): the ritual swept "email" — meaning Gmail in practice —
while the personal-life iCloud mailbox rotted unread and cost Rajiv a
friend's memorial. A seat sweeps whatever it decides to sweep unless the
workspace declares its accounts, so each workspace carries
`.agents/mailboxes.yaml` (same idea as `repos.yaml`): every address, its
transport, its role, and its sweep cadence. Exactly one workspace declares
each account.

This tool plans the sweep and reports its coverage. `plan` lists the due
accounts the agent must sweep; `report` judges each one SWEPT / BLIND /
UNREACHABLE / DEFERRED from the watermark store and fails closed on any
due account left BLIND — declared but neither swept nor deferred with a
reason. UNREACHABLE (attempted, transport failed; defer with a reason
starting `unreachable:`) passes loud: the report names it, the denominator
stays honest.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_watermark as watermarks

SURFACE = "email"
TRANSPORTS = ("gmail", "apple-mail", "m365", "forwards-to")
SWEEPS = ("every-ritual", "weekly", "on-request")
WEEKLY_DUE_AFTER = timedelta(days=7)
UNREACHABLE_PREFIX = "unreachable:"


def load_manifest(path: Path) -> dict:
    """Parse and validate a mailboxes manifest, fail-closed on any gap."""
    try:
        import yaml
    except ImportError as exc:
        raise ValueError("pyyaml is required to read the mailbox manifest") from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"mailbox manifest unreadable: {path}: {exc}")
    if not isinstance(data, dict):
        raise ValueError(f"mailbox manifest is not a mapping: {path}")
    if not isinstance(data.get("workspace"), str) or not data["workspace"].strip():
        raise ValueError(f"mailbox manifest names no workspace: {path}")
    accounts = data.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise ValueError(f"mailbox manifest declares no accounts: {path}")
    seen: set[str] = set()
    for index, account in enumerate(accounts):
        where = f"account {index} ({account.get('address') if isinstance(account, dict) else account!r})"
        if not isinstance(account, dict):
            raise ValueError(f"{where} is not a mapping")
        address = account.get("address")
        if not isinstance(address, str) or not address.strip() or "@" not in address:
            raise ValueError(f"{where} has no valid address")
        if address in seen:
            raise ValueError(f"duplicate account {address}")
        seen.add(address)
        transport = account.get("transport")
        if transport not in TRANSPORTS:
            raise ValueError(f"{where} transport must be one of {', '.join(TRANSPORTS)}")
        if transport == "forwards-to":
            if not isinstance(account.get("delivers_to"), str) or not account["delivers_to"].strip():
                raise ValueError(f"{where} forwards-to requires delivers_to")
            continue
        if not isinstance(account.get("role"), str) or not account["role"].strip():
            raise ValueError(f"{where} names no role")
        if account.get("sweep") not in SWEEPS:
            raise ValueError(f"{where} sweep must be one of {', '.join(SWEEPS)}")
        mailboxes = account.get("mailboxes")
        if mailboxes is not None and (
            not isinstance(mailboxes, list)
            or not mailboxes
            or not all(isinstance(box, str) and box.strip() for box in mailboxes)
        ):
            raise ValueError(f"{where} mailboxes must be a non-empty string list")
    data["accounts"] = accounts
    return data


def _last_advance(store: dict, address: str) -> datetime | None:
    entry = watermarks._entry(store, SURFACE, address)
    return watermarks._stored(entry.get("updated_at"))


def due_accounts(
    manifest: dict,
    workspace: str,
    now: datetime | None = None,
    *,
    include_on_request: frozenset[str] = frozenset(),
    home: Path | None = None,
) -> list[dict]:
    """Accounts this run must sweep. Weekly is due past 7 days without an
    advance; on-request only when explicitly included; forwards-to never."""
    moment = now or watermarks.now_local()
    store = watermarks.load(workspace, home, moment)
    due: list[dict] = []
    for account in manifest["accounts"]:
        if account["transport"] == "forwards-to":
            continue
        sweep = account["sweep"]
        if sweep == "every-ritual":
            due.append(account)
        elif sweep == "weekly":
            last = _last_advance(store, account["address"])
            if last is None or (moment - last) > WEEKLY_DUE_AFTER:
                due.append(account)
        elif account["address"] in include_on_request:
            due.append(account)
    return due


def _judge_account(store: dict, address: str, run_started: datetime) -> tuple[str, str | None]:
    entry = watermarks._entry(store, SURFACE, address)
    advanced_at = watermarks._stored(entry.get("updated_at"))
    if advanced_at is not None and advanced_at >= run_started:
        through = entry.get("through")
        return "SWEPT", f"advanced this run (through {through})"
    deferral = store.get("deferrals", {}).get(f"{SURFACE}:{address}") or {}
    deferred_at = watermarks._stored(deferral.get("deferred_at"))
    reason = (deferral.get("reason") or "").strip()
    live = (
        deferred_at is not None
        and reason
        and (run_started - deferred_at) <= watermarks.DEFERRAL_MAX_AGE
    )
    if live and reason.lower().startswith(UNREACHABLE_PREFIX):
        return "UNREACHABLE", reason
    if live:
        return "DEFERRED", reason
    return "BLIND", "due and neither swept nor deferred with a reason"


def report_accounts(
    manifest: dict,
    workspace: str,
    now: datetime | None = None,
    *,
    home: Path | None = None,
) -> tuple[list[dict], bool]:
    """Judge every due account. Returns (rows, ok); ok is False when any
    due account is BLIND. Requires an open run (`begin` first)."""
    moment = now or watermarks.now_local()
    store = watermarks.load(workspace, home, moment)
    run = store.get("run") or {}
    run_started = watermarks._stored(run.get("started_at"))
    if run_started is None:
        raise ValueError("no open run; begin the ritual run before reporting mailbox coverage")
    rows: list[dict] = []
    ok = True
    due = due_accounts(manifest, workspace, moment, home=home)
    seen = {account["address"] for account in due}
    for account in due:
        state, detail = _judge_account(store, account["address"], run_started)
        if state == "BLIND":
            ok = False
        rows.append(
            {
                "address": account["address"],
                "transport": account["transport"],
                "role": account["role"],
                "sweep": account["sweep"],
                "state": state,
                "detail": detail,
            }
        )
    by_address = {account["address"]: account for account in manifest["accounts"]}
    targets = (store.get("surfaces", {}).get(SURFACE, {}).get("targets") or {})
    for address in sorted(targets):
        if address in seen:
            continue
        advanced_at = watermarks._stored((targets[address] or {}).get("updated_at"))
        if advanced_at is None or advanced_at < run_started:
            continue
        account = by_address.get(address, {})
        state, detail = _judge_account(store, address, run_started)
        rows.append(
            {
                "address": address,
                "transport": account.get("transport", "undeclared"),
                "role": account.get("role", "undeclared"),
                "sweep": account.get("sweep", "undeclared"),
                "state": state,
                "detail": detail,
            }
        )
    return rows, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workspace", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="list the accounts this run must sweep")
    plan.add_argument("--include-on-request", action="append", default=[])
    plan.add_argument("--json", action="store_true")
    status = sub.add_parser("report", help="judge swept/blind/unreachable per due account")
    status.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
    except ValueError as exc:
        print(f"mailboxes refused: {exc}", file=sys.stderr)
        return 2
    if args.command == "plan":
        due = due_accounts(
            manifest,
            args.workspace,
            include_on_request=frozenset(args.include_on_request),
        )
        if args.json:
            print(json.dumps(due, indent=2, sort_keys=True))
        else:
            if not due:
                print("no mailbox due this run")
            for account in due:
                boxes = account.get("mailboxes") or ["INBOX"]
                print(
                    f"{account['address']} [{account['transport']}] "
                    f"role={account['role']} sweep={account['sweep']} "
                    f"boxes={','.join(boxes)}"
                )
        return 0
    try:
        rows, ok = report_accounts(manifest, args.workspace)
    except ValueError as exc:
        print(f"mailboxes refused: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"accounts": rows, "ok": ok}, indent=2, sort_keys=True))
    else:
        swept = sum(1 for row in rows if row["state"] == "SWEPT")
        print(f"mailboxes: {swept} of {len(rows)} swept")
        for row in rows:
            print(f"{row['state']:>11} {row['address']} — {row['detail']}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
