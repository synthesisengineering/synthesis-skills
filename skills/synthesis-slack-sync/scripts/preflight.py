#!/usr/bin/env python3
"""Slack sync preflight: resolve every read target from the sync config, fail closed.

Standard library only: the config is read with a small block-style YAML subset parser
(or as JSON when the file ends in .json).

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
* emits the declared set the daily-rituals watermark status consumes
  (``--json`` / ``--out``: ``{"slack": ["C…", "D…"]}``, the file
  ``sync_watermark.py status --targets-from`` reads), derived at sync time
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


def _scalar(text: str):
    """One YAML scalar: quoted or bare text, true/false, null, or a flow list of scalars."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return json.loads(text)  # YAML's double-quoted escapes (\u2014, \n, \") are JSON's
        except ValueError as exc:
            raise ConfigError(f"unsupported escape in {text[:40]!r}") from exc
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(part) for part in text[1:-1].split(",") if part.strip()]
    if text.startswith(("{", "&", "*", "|", ">")):
        raise ConfigError(f"unsupported YAML form {text[:20]!r}: write block-style lists of `key: value` entries")
    return {"true": True, "false": False, "null": None, "~": None, "": None}.get(text.lower(), text)


def _uncomment(line: str) -> str:
    quote = None
    for i, char in enumerate(line):
        if char in "'\"" and quote in (None, char):
            quote = None if quote else char
        elif char == "#" and quote is None and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def parse_yaml(text: str) -> dict:
    """The block-style YAML subset a sync config uses, with the standard library only: top-level
    `key: value` scalars, and `key:` followed by `- field: value` entries or nested `field: value`."""
    data: dict = {}
    key = entry = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = _uncomment(raw).rstrip()
        if not line.strip():
            continue
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise ConfigError(f"line {number}: tabs are not valid YAML indentation")
        body = line.strip()
        if not line[0].isspace():
            name, colon, value = body.partition(":")
            if not colon or not name.strip():
                raise ConfigError(f"line {number}: expected `key: value`")
            key, entry = name.strip(), None
            data[key] = _scalar(value) if value.strip() else None
            continue
        if key is None:
            raise ConfigError(f"line {number}: indented line before any key")
        if body == "-" or body.startswith("- "):
            if data[key] is None:
                data[key] = []
            if not isinstance(data[key], list):
                raise ConfigError(f"line {number}: {key} mixes a list with other values")
            body = body[1:].strip()
            if ":" not in body or body.startswith(("'", '"')):
                data[key].append(_scalar(body))  # a bare scalar entry; resolve_targets refuses it
                entry = None
                continue
            entry = {}
            data[key].append(entry)
        elif entry is None:
            if data[key] is None:
                data[key] = {}
            if not isinstance(data[key], dict):
                raise ConfigError(f"line {number}: unexpected indented line under {key}")
            entry = data[key]
        name, colon, value = body.partition(":")
        if not colon or not name.strip():
            raise ConfigError(f"line {number}: expected `field: value`")
        entry[name.strip()] = _scalar(value)
    return data


def _load_config(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if path.suffix == ".json":
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise ConfigError(f"{path} is not valid JSON: {exc}") from exc
    else:
        payload = parse_yaml(text)
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
    parser.add_argument("--out", help="also write the declared set JSON to this file (sync_watermark.py status --targets-from)")
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
