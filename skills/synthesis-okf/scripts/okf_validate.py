#!/usr/bin/env python3
"""okf-validate — conformance checker for Open Knowledge Format (OKF) v0.1 bundles.

Google's OKF repo (github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
ships an enrichment agent and an HTML visualizer, but no conformance validator.
This implements the spec's §9 conformance rules plus light structural checks on
the two reserved files (index.md, log.md).

Conformance (§9) — a bundle is conformant if:
  1. Every non-reserved .md file contains a parseable YAML frontmatter block.
  2. Every frontmatter block contains a non-empty `type` field.
  3. Reserved filenames (index.md, log.md) follow §6 / §7 structure when present.

Everything else in the spec is "soft guidance"; we surface it as warnings, never
errors. Broken cross-links are explicitly valid per §5.3 and are reported only
under --check-links.

Usage:
    okf_validate.py <bundle_dir> [--summary] [--check-links] [--quiet]

Exit codes: 0 = conformant (no errors), 1 = errors found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("okf-validate requires PyYAML (pip install pyyaml)")

RESERVED = {"index.md", "log.md"}
# Warn only on broadly-applicable recommended fields. `resource` and `tags` are
# legitimately absent for abstract concepts (§4.1), so their absence isn't a warning.
WARN_FIELDS = ("title", "description", "timestamp")
ISO_DATE_HEADING = re.compile(r"^#{1,6}\s+(\d{4}-\d{2}-\d{2})\s*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def split_frontmatter(text: str):
    """Return (frontmatter_str | None, body_str). None means no frontmatter block."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1:])
    return None, text  # unterminated block


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []
        self.types: dict[str, int] = {}
        self.concepts = 0
        self.indexes = 0
        self.logs = 0

    def error(self, rel, msg):
        self.errors.append(f"{rel}: {msg}")

    def warn(self, rel, msg):
        self.warnings.append(f"{rel}: {msg}")


def validate_concept(rel: str, text: str, rep: Report):
    fm_str, _ = split_frontmatter(text)
    if fm_str is None:
        rep.error(rel, "missing or unterminated YAML frontmatter block (§9.1)")
        return
    try:
        fm = yaml.safe_load(fm_str)
    except yaml.YAMLError as exc:
        rep.error(rel, f"unparseable frontmatter (§9.1): {exc}")
        return
    if not isinstance(fm, dict):
        rep.error(rel, "frontmatter is not a YAML mapping (§9.1)")
        return
    t = fm.get("type")
    if not (isinstance(t, str) and t.strip()):
        rep.error(rel, "missing or empty required `type` field (§9.2)")
    else:
        rep.types[t] = rep.types.get(t, 0) + 1
    for field in WARN_FIELDS:
        if field not in fm:
            rep.warn(rel, f"missing recommended field `{field}` (§4.1, soft)")
    rep.concepts += 1


def validate_index(rel: str, text: str, is_root: bool, rep: Report):
    rep.indexes += 1
    fm_str, _ = split_frontmatter(text)
    if fm_str is not None:
        if not is_root:
            rep.error(rel, "index.md must not contain frontmatter except at bundle root (§6, §11)")
        else:
            try:
                fm = yaml.safe_load(fm_str) or {}
            except yaml.YAMLError as exc:
                rep.error(rel, f"unparseable root index frontmatter: {exc}")
                fm = {}
            extra = [k for k in fm if k != "okf_version"]
            if extra:
                rep.warn(rel, f"root index.md frontmatter should only carry okf_version; also has {extra} (§11)")


def validate_log(rel: str, text: str, rep: Report):
    rep.logs += 1
    for line in text.splitlines():
        s = line.strip()
        # A second-level (or deeper) heading that looks like a date must be ISO YYYY-MM-DD.
        if s.startswith("##"):
            if not ISO_DATE_HEADING.match(s) and re.search(r"\d", s):
                rep.warn(rel, f"log date heading not ISO 8601 YYYY-MM-DD: {s!r} (§7, soft)")


def check_links(bundle: Path, rel: str, text: str, rep: Report):
    _, body = split_frontmatter(text)
    for target in LINK_RE.findall(body or text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        if path_part.startswith("/"):
            resolved = bundle / path_part.lstrip("/")
        else:
            resolved = (bundle / rel).parent / path_part
        if path_part.endswith("/"):
            resolved = resolved / "index.md"
        if not resolved.exists():
            rep.info.append(f"{rel}: broken link -> {target} (valid per §5.3, informational)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate an OKF v0.1 bundle directory.")
    ap.add_argument("bundle", type=Path, help="path to the bundle root directory")
    ap.add_argument("--summary", action="store_true", help="print type/file summary")
    ap.add_argument("--check-links", action="store_true", help="report broken internal links (informational)")
    ap.add_argument("--quiet", action="store_true", help="only print the final verdict line")
    args = ap.parse_args(argv)

    bundle = args.bundle
    if not bundle.is_dir():
        print(f"error: {bundle} is not a directory", file=sys.stderr)
        return 2

    rep = Report()
    for md in sorted(bundle.rglob("*.md")):
        rel = str(md.relative_to(bundle))
        text = md.read_text(encoding="utf-8")
        name = md.name
        if name == "index.md":
            validate_index(rel, text, is_root=(md.parent == bundle), rep=rep)
        elif name == "log.md":
            validate_log(rel, text, rep)
        else:
            validate_concept(rel, text, rep)
        if args.check_links:
            check_links(bundle, rel, text, rep)

    if not args.quiet:
        for e in rep.errors:
            print(f"  ERROR   {e}")
        for w in rep.warnings:
            print(f"  warn    {w}")
        if args.check_links:
            for i in rep.info:
                print(f"  info    {i}")
        if args.summary:
            print("\n  Summary:")
            print(f"    concepts: {rep.concepts} | index.md: {rep.indexes} | log.md: {rep.logs}")
            for t, n in sorted(rep.types.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"      type {t!r}: {n}")

    ok = not rep.errors
    verdict = "CONFORMANT" if ok else "NON-CONFORMANT"
    print(f"\n{verdict} — {len(rep.errors)} error(s), {len(rep.warnings)} warning(s) "
          f"across {rep.concepts} concept doc(s) in {bundle}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
