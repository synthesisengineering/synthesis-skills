#!/usr/bin/env python3
"""okf-convert — bring an AI-Knowledge `source/` bundle into OKF v0.1 conformance.

Mechanical 80% of the conversion (reviewed by a human for the remaining 20% —
description quality, tag curation). Reusable across every ai-knowledge-* repo:
the concept taxonomy (top-level subdir) maps to the OKF `type` via --type-map.

What it does:
  1. Adds YAML frontmatter (type, title, description, tags, timestamp) to every
     concept doc that lacks it. `type` from --type-map by top-level subdir;
     `title` from the first H1; `description` seeded from the first prose line
     (FLAGGED for human review); `timestamp` from the file's last git commit.
     Existing frontmatter is preserved and only back-filled (never overwritten).
  2. Renames each in-bundle README.md to index.md and regenerates it in OKF
     index style (§6): the README's lead paragraph, then a type-grouped list of
     the directory's concepts and a Subdirectories section — links + descriptions
     drawn from sibling frontmatter. The bundle-root index.md carries okf_version.
  3. Never deletes content irrecoverably: READMEs are git-tracked, so the rename
     is reversible; review the diff before committing.

Usage:
    okf_convert.py <bundle_dir> --type-map instructions=Instruction,runbooks=Runbook,datasets=Dataset,contexts=Context
                   [--default-type Reference] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("okf-convert requires PyYAML (pip install pyyaml)")

RESERVED = {"index.md", "log.md"}
EMPH = re.compile(r"(\*\*|\*|__|_|`)")


def split_frontmatter(text: str):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1:])
    return None, text


def derive_title(body: str) -> str | None:
    for line in body.splitlines():
        m = re.match(r"#\s+(.*)", line.strip())
        if m:
            return re.sub(r"\*\*?|`", "", m.group(1)).strip() or None
    return None


def lead_paragraph(body: str) -> str:
    """First prose paragraph after the H1 — description seed and index lead.
    Fence-aware: skips fenced code blocks so stubs don't seed shell commands as prose."""
    out, started, in_fence = [], False, False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            if out:
                break
            continue
        if in_fence:
            continue
        if not started:
            if re.match(r"#\s+", s):
                started = True
            continue
        if not s:
            if out:
                break
            continue
        if s.startswith(("#", ">", "-", "*", "|", "<")):
            if out:
                break
            continue
        # Skip provenance/metadata lines (a recurring convention: "Last verified:", "Source:", …)
        if re.match(r"(?i)^(last verified|last updated|sources?|verified)\b", s):
            if out:
                break
            continue
        out.append(s)
    return " ".join(out).strip()


def index_lead(text: str) -> str:
    """Lead prose of an existing index.md — text before its first heading.
    Lets re-runs recover the directory lead after README.md is gone (idempotency)."""
    _, body = split_frontmatter(text)
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            break
        if s:
            out.append(s)
    return " ".join(out).strip()


def first_sentence(text: str) -> str:
    text = EMPH.sub("", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[0].strip() if parts else text


def git_timestamp(path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", path.name],
            cwd=path.parent, capture_output=True, text=True, check=False,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def dump_frontmatter(meta: dict) -> str:
    body = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return "---\n" + body.strip("\n") + "\n---\n\n"


def top_subdir(rel: Path) -> str:
    return rel.parts[0] if len(rel.parts) > 1 else ""


def resolve_type(rel: Path, type_map: dict, default: str) -> str:
    """Longest path-prefix match: the most specific subtree key wins.
    e.g. 'datasets/.../years' beats 'datasets/personal-private' for a year file."""
    d = rel.parent.as_posix()
    best = None
    for key in type_map:
        if d == key or d.startswith(key + "/"):
            if best is None or len(key) > len(best):
                best = key
    return type_map[best] if best is not None else default


def path_tags(rel: Path) -> list[str]:
    # path segments below the bundle root, excluding the filename
    return [p for p in rel.parts[:-1]]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert an AI-Knowledge source/ bundle to OKF v0.1.")
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--type-map", required=True,
                    help="comma list of subdir=Type, e.g. instructions=Instruction,runbooks=Runbook")
    ap.add_argument("--default-type", default="Reference")
    ap.add_argument("--descriptions", type=Path,
                    help="optional YAML map: relpath -> {description, tags} (curated human input)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    bundle = args.bundle.resolve()
    if not bundle.is_dir():
        sys.exit(f"error: {bundle} is not a directory")
    type_map = dict(kv.split("=", 1) for kv in args.type_map.split(","))
    curated = {}
    if args.descriptions:
        curated = yaml.safe_load(args.descriptions.read_text(encoding="utf-8")) or {}

    md_files = sorted(bundle.rglob("*.md"))
    concept_meta: dict[str, dict] = {}   # rel-posix -> {type,title,description}
    dir_lead: dict[str, dict] = {}       # dir rel-posix -> {title, lead}
    changes: list[str] = []

    # ---- Pass A: capture README leads (for parent subdir descriptions + index lead)
    for md in md_files:
        if md.name != "README.md":
            continue
        body = md.read_text(encoding="utf-8")
        rel_dir = md.parent.relative_to(bundle).as_posix()
        dir_lead[rel_dir] = {"title": derive_title(body) or md.parent.name,
                             "lead": lead_paragraph(body)}
    # Fallback for idempotent re-runs: lead from an existing index.md when no README exists.
    for md in md_files:
        if md.name != "index.md":
            continue
        rel_dir = "" if md.parent == bundle else md.parent.relative_to(bundle).as_posix()
        if rel_dir not in dir_lead:
            dir_lead[rel_dir] = {"title": md.parent.name,
                                 "lead": index_lead(md.read_text(encoding="utf-8"))}

    # ---- Pass B: add/back-fill frontmatter on concept docs
    for md in md_files:
        if md.name in RESERVED or md.name == "README.md":
            continue
        rel = md.relative_to(bundle)
        rel_posix = rel.as_posix()
        text = md.read_text(encoding="utf-8")
        fm_str, body = split_frontmatter(text)
        ctype = resolve_type(rel, type_map, args.default_type)

        if fm_str is not None:
            try:
                meta = yaml.safe_load(fm_str) or {}
                assert isinstance(meta, dict)
            except (yaml.YAMLError, AssertionError):
                changes.append(f"  SKIP bad-YAML  {rel_posix}  (unparseable frontmatter — fix manually)")
                continue
            cur = curated.get(rel_posix, {})
            backfilled = False
            if not meta.get("type"):
                meta = {"type": ctype, **meta}
                backfilled = True
            if cur.get("description") and not meta.get("description"):
                meta["description"] = cur["description"]
                backfilled = True
            if cur.get("tags") and not meta.get("tags"):
                meta["tags"] = cur["tags"]
                backfilled = True
            if not meta.get("timestamp"):
                ts = git_timestamp(md)
                if ts:
                    meta["timestamp"] = ts
                    backfilled = True
            concept_meta[rel_posix] = {
                "type": meta.get("type", ctype),
                "title": meta.get("title") or derive_title(body) or md.stem,
                "description": meta.get("description", ""),
            }
            if backfilled and not args.dry_run:
                md.write_text(dump_frontmatter(meta) + body.lstrip("\n"), encoding="utf-8")
            if backfilled:
                changes.append(f"  backfill       {rel_posix}  -> {meta['type']}")
            continue

        title = derive_title(body) or md.stem.replace("-", " ").title()
        desc = first_sentence(lead_paragraph(body))
        tags = path_tags(rel)
        cur = curated.get(rel_posix, {})
        if cur.get("description"):
            desc = cur["description"]
        if cur.get("tags"):
            tags = cur["tags"]
        meta = {"type": ctype, "title": title}
        if desc:
            meta["description"] = desc
        if tags:
            meta["tags"] = tags
        ts = git_timestamp(md)
        if ts:
            meta["timestamp"] = ts
        concept_meta[rel_posix] = {"type": ctype, "title": title, "description": desc}
        if not args.dry_run:
            md.write_text(dump_frontmatter(meta) + body.lstrip("\n"), encoding="utf-8")
        changes.append(f"  + frontmatter  {rel_posix}  [{ctype}] {title!r}"
                       + (f" — desc: {desc!r}" if desc else "  (NO DESC — review)"))

    # ---- Pass C: (re)generate index.md per directory; remove READMEs
    dirs = {bundle}
    for md in md_files:
        # Every ancestor up to the bundle root needs its own index.md too —
        # not just the file's direct parent. Otherwise a purely-organizational
        # directory (subdirectories only, no concept doc directly inside it)
        # never gets an index.md, leaving its parent's Subdirectories link broken.
        d = md.parent
        while True:
            dirs.add(d)
            if d == bundle:
                break
            d = d.parent
    for d in sorted(dirs, key=lambda p: len(p.parts)):
        rel_dir = "" if d == bundle else d.relative_to(bundle).as_posix()
        concepts = sorted(
            p for p in concept_meta
            if Path(p).parent.as_posix() == (rel_dir or ".") or (rel_dir == "" and "/" not in p)
        )
        subdirs = sorted(
            sd.name for sd in d.iterdir()
            if sd.is_dir() and any(sd.rglob("*.md"))
        )
        if not concepts and not subdirs and rel_dir not in dir_lead:
            continue

        parts: list[str] = []
        lead = dir_lead.get(rel_dir, {}).get("lead")
        if lead:
            parts.append(lead)

        by_type: dict[str, list] = {}
        for cp in concepts:
            m = concept_meta[cp]
            by_type.setdefault(m["type"], []).append((m["title"], Path(cp).name, m["description"]))
        for t in sorted(by_type):
            sec = [f"# {t}", ""]
            for title, fname, desc in sorted(by_type[t]):
                sec.append(f"* [{title}]({fname})" + (f" - {desc}" if desc else ""))
            parts.append("\n".join(sec))

        if subdirs:
            sec = ["# Subdirectories", ""]
            for name in subdirs:
                sub_rel = f"{rel_dir}/{name}" if rel_dir else name
                desc = dir_lead.get(sub_rel, {}).get("lead", "")
                sec.append(f"* [{name}]({name}/index.md)" + (f" - {desc}" if desc else ""))
            parts.append("\n".join(sec))

        index_body = "\n\n".join(parts).rstrip() + "\n"
        if d == bundle:
            index_body = '---\nokf_version: "0.1"\n---\n\n' + index_body

        if not args.dry_run:
            (d / "index.md").write_text(index_body, encoding="utf-8")
            readme = d / "README.md"
            if readme.exists():
                readme.unlink()  # git-tracked: reversible via `git checkout`; review the diff
        changes.append(f"  index.md       {rel_dir or '<root>'}  "
                       f"({len(concepts)} concept(s), {len(subdirs)} subdir(s))")

    print(f"OKF conversion {'(dry-run) ' if args.dry_run else ''}of {bundle}\n")
    print("\n".join(changes))
    print(f"\n{len(concept_meta)} concept doc(s) processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
