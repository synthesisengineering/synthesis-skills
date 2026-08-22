#!/usr/bin/env python3
"""Freeze nonblank source lines for the writing-quality no-removals gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SKILL_ROOTS = (
    "skills/synthesis-content-quality",
    "skills/synthesis-writing-pitfalls",
    "skills/synthesis-writing-craft",
    "skills/synthesis-clean-text",
)


def git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout


def line_hashes(text: str) -> list[str]:
    return [
        hashlib.sha256(line.encode("utf-8")).hexdigest()
        for line in text.splitlines()
        if line.strip()
    ]


def build_baseline(repo: Path, revision: str) -> dict:
    files: dict[str, dict] = {}
    for root in SKILL_ROOTS:
        listing = git(repo, "ls-tree", "-r", "--name-only", revision, "--", root)
        for relative in sorted(line for line in listing.splitlines() if line.endswith(".md")):
            text = git(repo, "show", f"{revision}:{relative}")
            files[relative] = {
                "nonblank_line_count": len(line_hashes(text)),
                "ordered_nonblank_line_sha256": line_hashes(text),
            }
    return {
        "schema_version": 1,
        "baseline_revision": revision,
        "policy": (
            "Every baseline nonblank line must remain byte-identical and in order. "
            "Additions are allowed; changing this fixture requires explicit review."
        ),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = build_baseline(args.repo_root.resolve(), args.revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(baseline['files'])} baseline files to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
