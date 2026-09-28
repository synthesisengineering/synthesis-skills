#!/usr/bin/env python3
"""Declared repository fetch and arithmetic, without merge or divergence judgments.

This is the mechanical half of ritual code sync. Fast-forward/reconciliation
remains with authenticated claim-owning workflows. Offline counts are CACHED.
"""

from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import time

from ritual_workers import read_regular, strict_yaml, RitualWorkersError
from credential_paths import _local_git_metadata

MAX_SECONDS = 300
MAX_REPOS = 256


def _git(repo, args, *, remaining):
    if remaining <= 0:
        raise TimeoutError("repository inventory reached its total time bound")
    path = (
        Path(__file__).resolve().parents[2]
        / "synthesis-project-management/scripts/coordination_process.py"
    )
    spec = importlib.util.spec_from_file_location("_ritual_process_owner", path)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    command = ["/usr/bin/env"]
    for name in sorted(os.environ):
        if name.startswith("GIT_"):
            command.extend(["-u", name])
    command += [
        "GIT_TERMINAL_PROMPT=0",
        "GIT_OPTIONAL_LOCKS=0",
        "LC_ALL=C",
        "git",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repo),
        *args,
    ]
    result = owner.run(
        command, cwd=repo, timeout=min(30, remaining), output_bytes=1024 * 1024
    )
    if result.returncode:
        raise ValueError("Git observation/fetch failed; no remote-current claim")
    return result.stdout.strip()


def scan(workspace, *, fetch=False):
    root = Path(workspace).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("workspace must be an exact real directory")
    declaration = root / ".agents/repos.yaml"
    resolved = declaration.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("repository declaration resolves outside workspace")
    raw = read_regular(resolved, 2 * 1024 * 1024)
    document = strict_yaml(raw.decode("utf-8"))
    if not isinstance(document, dict) or not isinstance(
        document.get("repos"), (list, dict)
    ):
        raise ValueError("declared repository inventory is missing")
    rows = document["repos"]
    if isinstance(rows, dict):
        if any(
            not isinstance(v, dict) or ("name" in v and v["name"] != k)
            for k, v in rows.items()
        ):
            raise ValueError("ambiguous repository map")
        rows = [{"name": k, **v} for k, v in rows.items()]
    if not rows or len(rows) > MAX_REPOS:
        raise ValueError("repository inventory must be nonempty and bounded")
    names = []
    for row in rows:
        name = row.get("name") if isinstance(row, dict) else None
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name)
            or name in names
        ):
            raise ValueError(
                "invalid or duplicate repository identity before aggregation"
            )
        names.append(name)
    report = {
        "schema": 1,
        "declared": len(rows),
        "fetched": fetch,
        "repositories": [],
        "authority": "observations-only",
        "fast_forward_performed": False,
    }
    started = time.monotonic()
    for entry in rows:
        row = {"name": entry["name"], "status": "UNREACHABLE", "branches": []}
        report["repositories"].append(row)
        choice = entry.get("ritual_sync", False)
        if (
            document.get("status") == "dormant"
            or entry.get("status") == "dormant"
            or choice in (False, "no", "false")
        ):
            row["status"] = "EXCLUDED"
            continue
        try:
            if choice not in (True, "yes", "true"):
                raise ValueError("ritual_sync must be explicitly yes or no")
            declared = entry.get("path", entry["name"])
            if not isinstance(declared, str):
                raise ValueError("repository path must be text")
            path = Path(declared)
            path = path if path.is_absolute() else root / path
            if (
                ".." in path.parts
                or path.resolve() != path
                or not path.is_relative_to(root)
                or path == root
            ):
                raise ValueError("foreign or linked repository path")
            _local_git_metadata(path, root)
            branches = entry.get("default_branches")
            if (
                not isinstance(branches, list)
                or not branches
                or len(branches) > 32
                or any(
                    not isinstance(b, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", b)
                    or ".." in b
                    or "@{" in b
                    for b in branches
                )
                or len(set(branches)) != len(branches)
            ):
                raise ValueError(
                    "default branches must be an explicit unique bounded list"
                )

            def run(args):
                return _git(
                    path, args, remaining=MAX_SECONDS - (time.monotonic() - started)
                )

            if fetch:
                run(["fetch", "--all", "--no-recurse-submodules"])
            for branch in branches:
                result = {
                    "branch": branch,
                    "status": "BLIND",
                    "ahead": None,
                    "behind": None,
                }
                row["branches"].append(result)
                try:
                    ref = "refs/heads/" + branch
                    before = run(["rev-parse", "--verify", ref])
                    upstream = run(["for-each-ref", "--format=%(upstream)", ref])
                    if (
                        not upstream
                        or not upstream.startswith("refs/")
                        or "\n" in upstream
                    ):
                        raise ValueError("declared branch has no exact upstream")
                    upstream_before = run(["rev-parse", "--verify", upstream])
                    if any(not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid)
                           for oid in (before, upstream_before)):
                        raise ValueError("branch observation has no exact object identity")
                    pair = run(
                        ["rev-list", "--left-right", "--count", before + "..." + upstream_before]
                    )
                    if not re.fullmatch(r"\d+\s+\d+", pair):
                        raise ValueError("ahead/behind result malformed")
                    ahead, behind = map(int, pair.split())
                    if (run(["rev-parse", "--verify", ref]) != before
                            or run(["rev-parse", "--verify", upstream]) != upstream_before
                            or run(["for-each-ref", "--format=%(upstream)", ref]) != upstream):
                        raise ValueError("local branch or upstream changed during observation")
                    result.update(
                        ahead=ahead,
                        behind=behind,
                        status="DECISION"
                        if ahead or behind
                        else ("CURRENT" if fetch else "CACHED"),
                    )
                except (ValueError, OSError, TimeoutError) as exc:
                    result["reason"] = str(exc)
            _local_git_metadata(path, root)
            states = {b["status"] for b in row["branches"]}
            row["status"] = (
                "BLIND"
                if "BLIND" in states
                else (
                    "DECISION"
                    if "DECISION" in states
                    else ("CURRENT" if fetch else "CACHED")
                )
            )
        except (ValueError, OSError, TimeoutError, RitualWorkersError) as exc:
            row["reason"] = str(exc)
    if (
        read_regular(resolved, 2 * 1024 * 1024) != raw
        or declaration.resolve(strict=True) != resolved
    ):
        raise ValueError("repository declaration changed while scanning")
    report["counts"] = {
        status: sum(r["status"] == status for r in report["repositories"])
        for status in (
            "CURRENT",
            "CACHED",
            "DECISION",
            "BLIND",
            "UNREACHABLE",
            "EXCLUDED",
        )
    }
    return report


def main(argv=None):
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("--workspace-root", required=True, type=Path)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--doctor", action="store_true")
    args = p.parse_args(argv)
    if args.doctor and args.fetch:
        p.error("--doctor is read-only; --fetch requires the ritual execution path")
    try:
        result = scan(args.workspace_root, fetch=args.fetch)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2 if result["counts"]["BLIND"] or result["counts"]["UNREACHABLE"] else 0
    except (OSError, ValueError, RitualWorkersError) as exc:
        print(json.dumps({"status": "UNKNOWN", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
