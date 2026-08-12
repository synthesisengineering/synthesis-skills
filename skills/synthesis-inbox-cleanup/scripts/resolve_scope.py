#!/usr/bin/env python3
"""Resolve which mail accounts an inbox-cleanup run covers.

The workspace-scope contract (skill v1.5.0): inbox cleanup is a chief-of-staff
duty that different operations seats invoke with different reach. The personal
(root) workspace's ritual cleans EVERY account; a client workspace's ritual
cleans only the accounts that belong to that workspace. The caller states its
workspace explicitly — rituals know where they run, and an explicit argument
beats environment sniffing that can guess wrong silently.

Config: ~/.synthesis/inbox-cleanup/scopes.yaml

    version: 1
    all_scope_workspaces: [personal]     # workspaces whose default is ALL accounts
    accounts:
      - address: you@work.example.com
        workspace: acme
        stack: gmail                     # gmail | icloud-imap | m365-applescript | ...
      - address: you@example.com
        workspace: personal
        stack: icloud-imap

Usage:
    resolve_scope.py --workspace acme            # acme's accounts only
    resolve_scope.py --workspace personal        # ALL accounts (all-scope workspace)
    resolve_scope.py --workspace acme --all      # explicit override: everything
    resolve_scope.py --workspace acme --json     # machine-readable

Exit codes (guard contract): 0 resolved · 1 defects in config · 2 cannot
establish ground truth (missing/unparseable config, unknown workspace).
An unknown workspace is exit 2, not an empty list — a cleanup run that
resolves to zero accounts by typo must never look like a clean sweep.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_CONFIG = "~/.synthesis/inbox-cleanup/scopes.yaml"


def fail_unverified(msg: str) -> None:
    print(f"UNVERIFIED: {msg}", file=sys.stderr)
    raise SystemExit(2)


def load_config(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        fail_unverified("pyyaml is not installed; cannot parse scopes.yaml")
    if not path.exists():
        fail_unverified(f"no scope config at {path} — copy the schema from resolve_scope.py's docstring")
    try:
        data = yaml.safe_load(path.read_text())
    except Exception as exc:  # noqa: BLE001
        fail_unverified(f"{path} is not parseable YAML: {exc}")
    if not isinstance(data, dict):
        fail_unverified(f"{path} did not parse to a mapping")
    return data


def resolve(cfg: dict, workspace: str, want_all: bool) -> list[dict]:
    accounts = cfg.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        print("DEFECT: scopes.yaml has no accounts list", file=sys.stderr)
        raise SystemExit(1)

    defects = []
    for i, acct in enumerate(accounts):
        if not isinstance(acct, dict) or not acct.get("address") or not acct.get("workspace"):
            defects.append(f"accounts[{i}] needs address and workspace")
    if defects:
        for d in defects:
            print(f"DEFECT: {d}", file=sys.stderr)
        raise SystemExit(1)

    all_scope = set(cfg.get("all_scope_workspaces") or [])
    known = {a["workspace"] for a in accounts} | all_scope

    if workspace not in known:
        fail_unverified(
            f"workspace '{workspace}' is not in scopes.yaml "
            f"(known: {', '.join(sorted(known))}) — refusing to resolve to an "
            f"empty sweep; a typo must not look like a clean run"
        )

    if want_all or workspace in all_scope:
        return list(accounts)
    return [a for a in accounts if a["workspace"] == workspace]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", required=True,
                    help="the workspace whose ritual is running (explicit, never sniffed)")
    ap.add_argument("--all", action="store_true",
                    help="override: every account regardless of workspace")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args()

    cfg = load_config(Path(args.config).expanduser())
    selected = resolve(cfg, args.workspace, args.all)

    if args.as_json:
        print(json.dumps({"workspace": args.workspace,
                          "scope": "all" if (args.all or args.workspace in set(cfg.get("all_scope_workspaces") or [])) else "workspace",
                          "accounts": selected}, indent=2))
    else:
        scope = "ALL accounts" if len(selected) == len(cfg["accounts"]) else f"accounts for '{args.workspace}'"
        print(f"scope: {scope} ({len(selected)} of {len(cfg['accounts'])})")
        for a in selected:
            print(f"  {a['address']}  [{a.get('stack', 'unspecified')}]  ({a['workspace']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
