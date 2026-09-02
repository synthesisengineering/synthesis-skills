#!/usr/bin/env python3
"""Google Chat preflight: the declared read-target set for the watermark gate, fail closed.

Slack got its declared set from a config that names every channel and DM by
id. Google Chat has no such list: spaces come from a live enumeration whose
wrapper returns preformatted text (one space per line), ignores its own type
filter, pages at 100 with no cursor, orders undocumented, and shows every DM
as "Unnamed Space". On 2026-09-01 a surface-level watermark on this surface
recorded coverage that no per-space read backed, and a colleague's four DMs
went unsurfaced through two syncs and a day-end. A watermark records that an
agent CLAIMED coverage; this script makes the claim mechanical and bounded.

The declared set has two parts:

* the config's explicit ``targets`` — space ids with labels the workspace
  assigns — the auditable core (a human can read it; "Unnamed Space" cannot
  be audited);
* the saved enumeration (``--spaces``: the text the space-list call
  returned), parsed line by line and filtered CLIENT-SIDE by the config's
  ``scope`` (the wrapper's type filter is not trusted), marked BOUNDED when
  the header count exceeds the records parsed or a page cap was hit.

Output: the resolved-target table for the sync report, a census by type, a
BOUND line when the enumeration was capped or short, and (``--json`` /
``--out``) the ``{"gchat": [space ids]}`` the watermark gate consumes. Exit 0
when the set is complete, 1 when it is bounded or a config target is
unresolved (the report must name it), 2 on an empty set or a malformed
config. Nothing is guessed: a config target that is not ``spaces/<id>`` is
unresolved, and a ``users/<id>`` is a person, never a read target.

    gchat_preflight.py --config .agents/gchat-sync.yaml --spaces spaces.txt --json --out declared.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SURFACE = "gchat"
PAGE_CAP = 100
SPACE_ID = re.compile(r"^spaces/[A-Za-z0-9_-]+$")
RECORD = re.compile(r"^\s*[-*]\s*(?P<name>.*?)\s*\(ID:\s*(?P<id>spaces/[A-Za-z0-9_-]+),\s*Type:\s*(?P<type>[A-Z_]+)\)\s*$")
HEADER = re.compile(r"Found\s+(?P<count>\d+)\s+Chat spaces", re.IGNORECASE)
SCOPE_KEYS = {
    "DIRECT_MESSAGE": "direct_messages",
    "GROUP_CHAT": "group_chats",
    "SPACE": "named_spaces",
}


class ConfigError(ValueError):
    """The config or the enumeration cannot be read as a declared set."""


@dataclass(frozen=True)
class Target:
    space: str | None
    label: str
    kind: str
    source: str
    reason: str | None = None

    @property
    def resolved(self) -> bool:
        return self.space is not None


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise ConfigError("PyYAML is required to read the sync config") from exc
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"{path} must be a mapping at the top level")
    return payload


def config_targets(config: dict) -> list[Target]:
    """The explicit, labeled core of the declared set."""
    entries = config.get("targets") or []
    if not isinstance(entries, list):
        raise ConfigError("targets must be a list of {space, label} entries")
    targets: list[Target] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigError(f"targets[{index}] must be a mapping, got {type(entry).__name__}")
        label = str(entry.get("label") or entry.get("space") or f"targets[{index}]")
        kind = str(entry.get("type") or "DIRECT_MESSAGE").upper()
        raw = str(entry.get("space") or "").strip()
        if not raw:
            targets.append(Target(None, label, kind, "config", "no space id in the config entry"))
        elif raw.startswith("users/"):
            targets.append(Target(None, label, kind, "config", f"{raw} is a person, not a space"))
        elif not SPACE_ID.match(raw):
            targets.append(Target(None, label, kind, "config", f"{raw} is not a spaces/<id>"))
        else:
            targets.append(Target(raw, label, kind, "config"))
    return targets


def parse_enumeration(text: str) -> tuple[list[Target], int | None]:
    """Records from the space-list call's text, and the count its header claimed."""
    claimed = None
    records: list[Target] = []
    for line in text.splitlines():
        header = HEADER.search(line)
        if header and claimed is None:
            claimed = int(header.group("count"))
            continue
        match = RECORD.match(line)
        if match:
            records.append(Target(match.group("id"), match.group("name").strip() or "Unnamed Space",
                                  match.group("type").upper(), "enumeration"))
    return records, claimed


def in_scope(kind: str, scope: dict) -> bool:
    key = SCOPE_KEYS.get(kind)
    if key is None:
        return False
    return str(scope.get(key, "all")).lower() == "all"


def bound(records: list[Target], claimed: int | None) -> str | None:
    """Why the enumeration cannot be called complete, or None when it can."""
    if len(records) >= PAGE_CAP:
        claim = f" (header claimed {claimed})" if claimed is not None and claimed > len(records) else ""
        return (f"page returned {len(records)} records, the wrapper's cap, and no cursor exists "
                f"to page further{claim}")
    if claimed is not None and claimed > len(records):
        return f"header claimed {claimed} spaces but {len(records)} records were returned"
    return None


def census(targets: list[Target]) -> str:
    counts: dict[str, int] = {}
    for target in targets:
        if target.resolved:
            counts[target.kind] = counts.get(target.kind, 0) + 1
    unresolved = sum(1 for t in targets if not t.resolved)
    parts = [f"{counts[k]} {k}" for k in sorted(counts)]
    parts.append(f"{unresolved} unresolved")
    return "census: " + " / ".join(parts)


def declared_set(targets: list[Target]) -> dict[str, list[str]]:
    seen: list[str] = []
    for target in targets:
        if target.resolved and target.space not in seen:
            seen.append(target.space)
    return {SURFACE: seen}


def merge(core: list[Target], enumerated: list[Target]) -> list[Target]:
    known = {t.space for t in core if t.resolved}
    return core + [t for t in enumerated if t.space not in known]


def render_table(workspace: str, targets: list[Target], enumeration_bound: str | None,
                 enumerated: bool) -> str:
    lines = [f"# Google Chat preflight — workspace {workspace}", "",
             "| type | space | label | source | status |", "|---|---|---|---|---|"]
    for target in targets:
        status = "resolved" if target.resolved else f"UNRESOLVED — {target.reason}"
        lines.append(f"| {target.kind} | {target.space or '—'} | {target.label} | {target.source} | {status} |")
    lines.extend(["", census(targets)])
    if not enumerated:
        lines.append("enumeration: none supplied — the declared set is the config core only; "
                     "coverage is partial and the gate must say so")
    elif enumeration_bound:
        lines.append(f"BOUNDED: {enumeration_bound} — coverage is partial; defer the surface with this bound, "
                     "never advance past it")
    else:
        lines.append("enumeration: complete (header count matches the records parsed, below the page cap)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="path to .agents/gchat-sync.yaml")
    parser.add_argument("--spaces", help="file holding the text the space-list call returned this run")
    parser.add_argument("--json", action="store_true", help="print the declared set as JSON instead of the table")
    parser.add_argument("--out", help="also write the declared set JSON here (the gate's --targets-from)")
    args = parser.parse_args(argv)

    try:
        config = _load_yaml(Path(args.config).expanduser())
        core = config_targets(config)
        enumerated: list[Target] = []
        claimed = None
        if args.spaces:
            try:
                text = Path(args.spaces).expanduser().read_text(encoding="utf-8")
            except OSError as exc:
                raise ConfigError(f"cannot read {args.spaces}: {exc}") from exc
            records, claimed = parse_enumeration(text)
            scope = config.get("scope") or {}
            if not isinstance(scope, dict):
                raise ConfigError("scope must be a mapping")
            enumerated = [t for t in records if in_scope(t.kind, scope)]
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    targets = merge(core, enumerated)
    resolved = [t for t in targets if t.resolved]
    if not resolved:
        print("error: no read target could be resolved; the sweep is refused rather than reported "
              "as a quiet day", file=sys.stderr)
        return 2

    enumeration_bound = bound(enumerated, claimed) if args.spaces else None
    declared = declared_set(targets)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(declared, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(declared, indent=2))
    else:
        print(render_table(str(config.get("workspace") or "?"), targets, enumeration_bound, bool(args.spaces)))

    partial = []
    unresolved = [t for t in targets if not t.resolved]
    if unresolved:
        partial.append(f"{len(unresolved)} config target(s) unresolved — name each in the sync report")
    if not args.spaces:
        partial.append("no enumeration supplied — coverage is the config core only")
    elif enumeration_bound:
        partial.append(f"enumeration bounded: {enumeration_bound}")
    if partial:
        print("; ".join(partial), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
