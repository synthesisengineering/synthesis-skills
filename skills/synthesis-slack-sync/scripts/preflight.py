#!/usr/bin/env python3
"""Slack sync preflight: resolve every read target from the sync config, fail closed.

A sync config carries two id-like fields per DM entry: ``id`` (the user id,
``U…``) and ``dm_id`` (the conversation id, ``D…``). Channels and group DMs
use ``id`` for the conversation, so a reader that reaches for ``id``
uniformly hands user ids to a conversation-read call — which resolves while
the account is active and turns into a phantom dead surface once the person
leaves, or returns quiet empties that read as "no traffic". The 2026-09-01
evidence: a careful reader with the config open, warned about the trap
minutes earlier, still derived every DM target as a user id.

Resolution therefore belongs in one place that fails closed. This script:

* emits the resolved-target table for the sync report (surface class, the
  one id a conversation-read call accepts, display name, resolved or
  unresolved with the reason) and a **prefix census** line, so a wrong
  derivation shows up as a wrong shape instead of quiet empties;
* validates the id prefix per class — ``C``/``G`` for channels and group
  DMs, ``D`` for DMs; a ``U``-prefixed id in a read set is never a target;
* emits the declared set the daily-rituals watermark gate consumes
  (``--json`` / ``--out``: ``{"slack": ["C…", "D…"]}``), derived at sync time
  and never hand-maintained;
* refuses an empty resolved set or a malformed config (exit 2), and exits 1
  when any declared target is unresolved so the sweep report must name it.

    preflight.py --config .agents/slack-sync.yaml
    preflight.py --config .agents/slack-sync.yaml --json --out /tmp/declared.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SURFACE = "slack"
CLASSES = (
    # (config key, class label, read-id field, accepted prefixes)
    ("channels", "channel", "id", ("C", "G")),
    ("dm_channels", "dm", "dm_id", ("D",)),
    ("group_dm_channels", "group-dm", "id", ("C", "G")),
)


class ConfigError(ValueError):
    """The config cannot be read as a declared set; nothing is guessed."""


@dataclass(frozen=True)
class Target:
    kind: str
    name: str
    read_id: str | None
    reason: str | None = None

    @property
    def resolved(self) -> bool:
        return self.read_id is not None


def _load_config(path: Path) -> dict:
    try:
        import yaml  # PyYAML: the same dependency the repository's tests use
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


def resolve_targets(config: dict) -> list[Target]:
    """One Target per declared entry, resolved or unresolved with a reason."""
    targets: list[Target] = []
    for key, kind, field, prefixes in CLASSES:
        entries = config.get(key) or []
        if not isinstance(entries, list):
            raise ConfigError(f"{key} must be a list of entries")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ConfigError(f"{key}[{index}] must be a mapping, got {type(entry).__name__}")
            name = str(entry.get("name") or entry.get("id") or f"{key}[{index}]")
            if entry.get("active") is False:
                continue
            raw = entry.get(field)
            if raw is None or not str(raw).strip():
                targets.append(Target(kind, name, None, f"no {field} in the config entry"))
                continue
            read_id = str(raw).strip()
            prefix = read_id[:1].upper()
            if prefix == "U":
                targets.append(Target(kind, name, None, f"{field} {read_id} is a user id, not a conversation id"))
            elif prefix not in prefixes:
                targets.append(Target(kind, name, None,
                                      f"{field} {read_id} has prefix {prefix}, expected {' or '.join(prefixes)}"))
            else:
                targets.append(Target(kind, name, read_id))
    return targets


def census(targets: list[Target]) -> str:
    counts: dict[str, int] = {}
    for target in targets:
        if target.resolved:
            counts[target.read_id[:1].upper()] = counts.get(target.read_id[:1].upper(), 0) + 1
    unresolved = sum(1 for target in targets if not target.resolved)
    parts = [f"{counts[p]} {p}" for p in sorted(counts)]
    parts.append(f"{unresolved} unresolved")
    return "census: " + " / ".join(parts)


def declared_set(targets: list[Target]) -> dict[str, list[str]]:
    return {SURFACE: [target.read_id for target in targets if target.resolved]}


def render_table(workspace: str, targets: list[Target]) -> str:
    lines = [f"# Slack preflight — workspace {workspace}", "",
             "| class | read id | name | status |", "|---|---|---|---|"]
    for target in targets:
        status = "resolved" if target.resolved else f"UNRESOLVED — {target.reason}"
        lines.append(f"| {target.kind} | {target.read_id or '—'} | {target.name} | {status} |")
    lines.extend(["", census(targets)])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="path to .agents/slack-sync.yaml")
    parser.add_argument("--json", action="store_true", help="print the declared set as JSON instead of the table")
    parser.add_argument("--out", help="also write the declared set JSON to this file (the gate's --targets-from)")
    args = parser.parse_args(argv)

    try:
        config = _load_config(Path(args.config).expanduser())
        targets = resolve_targets(config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    resolved = [target for target in targets if target.resolved]
    if not resolved:
        print("error: no read target could be resolved from the config; the sweep is refused "
              "rather than reported as a quiet day", file=sys.stderr)
        if targets:
            print(render_table(str(config.get("workspace") or "?"), targets), file=sys.stderr)
        return 2

    declared = declared_set(targets)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(declared, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(declared, indent=2))
    else:
        print(render_table(str(config.get("workspace") or "?"), targets))
    unresolved = [target for target in targets if not target.resolved]
    if unresolved:
        print(f"{len(unresolved)} declared target(s) unresolved — report each one in the sync report; "
              "never as unreadable, never as a config defect", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
