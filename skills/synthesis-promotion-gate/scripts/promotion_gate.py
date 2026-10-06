#!/usr/bin/env python3
"""Refuse a deploy whose built site still carries a configured internal marker.

Run it on the built output folder after the build and before the deploy
command (which still needs the principal's approval):

    python3 promotion_gate.py dist --config .agents/promotion-markers.json

Each marker in the JSON config names a pattern and where to look in every
built page: "text" (what a reader sees: tags, scripts, styles and comments
removed, entities decoded), "headings" (h1 to h6 text), "comments" (HTML
comment bodies) or "source" (the raw file). A marker must match at least one
of its positive examples and none of its negatives, or the config is refused:
a pattern that matches nothing protects nothing.

Exit 0: clean. Exit 1: markers found, one line each; do not deploy. Exit 2:
config or folder unusable, or nothing to scan (an empty scan is not clean).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

WHERE = ("text", "headings", "comments", "source")
DEFAULT_GLOBS = ("**/*.html", "**/*.htm", "**/*.xml", "**/*.txt", "**/*.json")
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
# Not displayed prose: scripts, styles, templates, and code (the destination renders code apart).
HIDDEN = re.compile(r"<(script|style|template|noscript|pre|code)\b.*?</\1\s*>", re.S | re.I)
# A heading runs to its close, the next heading, or the end: browsers repair a missing close.
HEADING = re.compile(r"<h[1-6]\b[^>]*>(.*?)(?=</h[1-6]\s*>|<h[1-6]\b|$)", re.S | re.I)
# Any element given the heading role reads as a heading to assistive technology (a 2026-08 review bypass).
ARIA_HEADING = re.compile(r"<([a-z][\w-]*)\b[^>]*\brole\s*=\s*[\"']?heading\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
# Inline tags join their neighbours ("Public<a>ation</a>" reads "Publication"); others separate.
INLINE = re.compile(r"</?(?:a|abbr|b|bdi|bdo|cite|data|dfn|em|i|kbd|mark|q|s|samp|small|span|strong|sub|sup|"
                    r"time|u|var|wbr)\b[^>]*>", re.I)
TAG = re.compile(r"<[^>]*>")


def _text(fragment: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", INLINE.sub("", fragment))).split())


def views(raw: str) -> dict:
    """The four places a marker can hide in one built file. Attributes are never text."""
    body = HIDDEN.sub(" ", COMMENT.sub(" ", raw))
    return {"source": raw, "comments": "\n".join(" ".join(c.split()) for c in COMMENT.findall(raw)),
            "text": _text(body), "headings": "\n".join([_text(h) for h in HEADING.findall(body)]
                                                       + [_text(h) for _, h in ARIA_HEADING.findall(body)])}


def load(path: Path) -> tuple:
    data = json.loads(path.read_text(encoding="utf-8"))
    markers, seen = data.get("markers"), set()
    if not isinstance(markers, list) or not markers:
        raise ValueError("config needs a non-empty 'markers' list")
    for m in markers:
        if not isinstance(m, dict) or not m.get("id") or m["id"] in seen:
            raise ValueError(f"each marker needs a unique id: {m!r}")
        seen.add(m["id"])
        where = m.get("in") or ["text", "comments", "source"]
        if not set(where) <= set(WHERE):
            raise ValueError(f"{m['id']}: 'in' takes {', '.join(WHERE)}")
        m["in"], m["rx"] = where, re.compile(m.get("pattern", ""), re.I | re.M)
        if not m["rx"].pattern or not any(m["rx"].search(p) for p in m.get("positive", [])):
            raise ValueError(f"{m['id']}: the pattern must match at least one positive example")
        if any(m["rx"].search(n) for n in m.get("negative", [])):
            raise ValueError(f"{m['id']}: the pattern matches a negative example")
    return markers, data.get("file_globs") or list(DEFAULT_GLOBS)


def scan(root: Path, markers: list, globs: list) -> tuple:
    files = sorted({p for g in globs for p in root.glob(g) if p.is_file() and not p.is_symlink()})
    hits = []
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="replace")
        seen = views(raw)
        for m in markers:
            for where in m["in"]:
                found = m["rx"].search(seen[where])
                if not found:
                    continue
                line = raw[: found.start()].count("\n") + 1 if where == "source" else None
                place = f"{path.relative_to(root)}" + (f":{line}" if line else "")
                hits.append(f"{place}: {m['id']} in {where}" + (f" ({m['rationale']})" if m.get("rationale") else ""))
    return files, hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dist", type=Path, help="the built output folder")
    ap.add_argument("--config", type=Path, required=True, help="marker config (JSON)")
    args = ap.parse_args(argv)
    try:
        markers, globs = load(args.config)
        if not args.dist.is_dir():
            raise ValueError(f"{args.dist} is not a folder; build first")
        files, hits = scan(args.dist, markers, globs)
    except (OSError, ValueError, re.error) as exc:
        print(f"promotion gate refused: {exc}", file=sys.stderr)
        return 2
    if not files:
        print(f"promotion gate refused: no files under {args.dist} match {globs}", file=sys.stderr)
        return 2
    for hit in hits:
        print(hit)
    print(f"{len(files)} file(s) scanned, {len(markers)} marker(s), {len(hits)} hit(s)"
          + (": do not deploy" if hits else ": clean"))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
