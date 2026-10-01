#!/usr/bin/env python3
"""Public synthetic causal controls; no native client, account or provider use."""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import hermes_adapter  # noqa: E402
from live_receipt import hermes_source_binding  # noqa: E402


def probe(fixture_root):
    root = Path(fixture_root)
    if not root.is_absolute():
        raise ValueError("absolute new fixture directory required")
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    profile = root / "profile"
    profile.mkdir(mode=0o700)
    installed = profile / "skills/synthesis-example/SKILL.md"
    installed.parent.mkdir(parents=True)
    installed.write_text("# Synthetic protected artifact\n")
    payload = {
        "tool_name": "write_file",
        "tool_input": {"path": str(installed), "content": "unauthorized"},
        "cwd": str(root),
    }
    denied = hermes_adapter.guard(payload, profile)
    allowed = hermes_adapter.guard(
        {
            "tool_name": "read_file",
            "tool_input": {"path": str(installed)},
            "cwd": str(root),
        },
        profile,
    )
    identity = hermes_source_binding(
        profile, "synthetic-session", profile="default", cwd=str(root)
    )
    controls = {
        "installed_write_refused": denied.get("action") == "block",
        "ordinary_read_retains_native_behavior": allowed == {},
        "missing_native_source_refused": identity["status"] == "UNKNOWN",
        "protected_bytes_unchanged": installed.read_text()
        == "# Synthetic protected artifact\n",
    }
    return {
        "schema": 1,
        "kind": "synthetic-source-controls",
        "status": "PASS" if all(controls.values()) else "FAIL",
        "controls": controls,
        "native_acceptance": "UNKNOWN",
        "provider_fault_attribution": "UNKNOWN",
        "external_calls": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture-root", required=True, type=Path)
    args = p.parse_args(argv)
    result = probe(args.fixture_root)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
