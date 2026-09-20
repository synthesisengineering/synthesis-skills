#!/usr/bin/env python3
"""Cross-owner overlap service over the shared time-block layer (§3).

Ownership is exclusive — a task belongs to exactly one workspace — but
visibility is shared: every seat publishes its owned commitments' time
blocks, with real titles, to one JSON layer file in the personal repo
(`coordination/time-blocks.json`), and any seat can call this script to
find conflicts across owners for a window.

This script is a pure reader. It makes no MCP calls, touches no calendar,
and never writes — not to the layer, not anywhere. Seats publish through
their own calendar reads (the daily-rituals skill's publish procedure);
this answers "what collides" from the published blocks alone.

Layer resolution: `--layer PATH`, else `$SYNTHESIS_TIME_BLOCKS`. There is
no default path — the personal repo lives somewhere different per machine,
and a wrong guess would silently read a stale copy.

Commands:
  validate   schema-check a layer file (exit 2 names the bad block)
  overlaps   cross-owner overlapping pairs clipped to a window (exit 0;
             an empty list is an answer, not a failure)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

FORMAT_TAG = "synthesis-time-blocks/v1"
LAYER_ENV = "SYNTHESIS_TIME_BLOCKS"

REQUIRED_TEXT_FIELDS = ("owner", "title", "source")


class LayerError(ValueError):
    """A layer file that fails closed with a human-readable reason."""


def _parse_moment(value: object, *, where: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise LayerError(f"{where} is missing or not a string")
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise LayerError(f"{where} {value!r} is not ISO-8601") from None
    if moment.tzinfo is None:
        raise LayerError(f"{where} {value!r} needs a UTC offset")
    return moment


def load_layer(path: Path) -> list[dict]:
    """Read and schema-check a layer file; return its blocks."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LayerError(f"cannot read {path}: {exc}") from None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LayerError(f"{path} is not valid JSON: {exc}") from None
    if not isinstance(payload, dict) or payload.get("format") != FORMAT_TAG:
        raise LayerError(f"{path} is not a {FORMAT_TAG} layer (check 'format')")
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise LayerError(f"{path} has no 'blocks' list")
    for index, block in enumerate(blocks):
        where = f"block {index}"
        if not isinstance(block, dict):
            raise LayerError(f"{where} is not an object")
        for field in REQUIRED_TEXT_FIELDS:
            value = block.get(field)
            if not isinstance(value, str) or not value.strip():
                raise LayerError(f"{where} needs a non-empty {field!r}")
        start = _parse_moment(block.get("start"), where=f"{where} start")
        end = _parse_moment(block.get("end"), where=f"{where} end")
        if end <= start:
            raise LayerError(f"{where} end {block.get('end')!r} is not after its start")
    return blocks


def resolve_layer(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get(LAYER_ENV, "").strip()
    if env:
        return Path(env)
    raise LayerError(f"no layer: pass --layer or set ${LAYER_ENV}")


def find_overlaps(
    blocks: list[dict], *, window_start: datetime, window_end: datetime
) -> list[dict]:
    """Cross-owner overlapping pairs intersecting [window_start, window_end).

    Same-owner pairs are excluded — each seat already sees its own calendar;
    this service exists for what no single seat can see. Touching endpoints
    (one block's end is another's start) are not overlaps. Pairs sort by
    overlap start, then owner and title, so output is deterministic.
    """
    parsed = [
        (
            block,
            datetime.fromisoformat(block["start"]),
            datetime.fromisoformat(block["end"]),
        )
        for block in blocks
    ]
    pairs: list[dict] = []
    for left in range(len(parsed)):
        block_a, start_a, end_a = parsed[left]
        if end_a <= window_start or start_a >= window_end:
            continue
        for right in range(left + 1, len(parsed)):
            block_b, start_b, end_b = parsed[right]
            if block_a["owner"] == block_b["owner"]:
                continue
            if end_b <= window_start or start_b >= window_end:
                continue
            overlap_start = max(start_a, start_b, window_start)
            overlap_end = min(end_a, end_b, window_end)
            if overlap_start < overlap_end:
                first, second = sorted(
                    (block_a, block_b),
                    key=lambda b: (b["owner"], b["title"], b["start"]),
                )
                pairs.append(
                    {
                        "a": first,
                        "b": second,
                        "overlap_start": overlap_start.isoformat(),
                        "overlap_end": overlap_end.isoformat(),
                    }
                )
    pairs.sort(
        key=lambda p: (
            p["overlap_start"],
            p["a"]["owner"],
            p["a"]["title"],
            p["b"]["owner"],
            p["b"]["title"],
        )
    )
    return pairs


def _window(value: str, *, name: str) -> datetime:
    return _parse_moment(value, where=f"window {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="schema-check a layer file")
    validate.add_argument("--layer", default=None)
    overlaps = sub.add_parser("overlaps", help="cross-owner overlaps in a window")
    overlaps.add_argument("--layer", default=None)
    overlaps.add_argument("--from", dest="window_from", required=True)
    overlaps.add_argument("--to", dest="window_to", required=True)
    overlaps.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        layer = resolve_layer(args.layer)
        blocks = load_layer(layer)
    except LayerError as exc:
        print(f"overlap refused: {exc}", file=sys.stderr)
        return 2
    if args.command == "validate":
        print(f"overlap: {layer} holds {len(blocks)} valid blocks")
        return 0
    try:
        window_start = _window(args.window_from, name="--from")
        window_end = _window(args.window_to, name="--to")
    except LayerError as exc:
        print(f"overlap refused: {exc}", file=sys.stderr)
        return 2
    if window_end <= window_start:
        print("overlap refused: window --to is not after --from", file=sys.stderr)
        return 2
    pairs = find_overlaps(blocks, window_start=window_start, window_end=window_end)
    if args.json:
        print(
            json.dumps(
                {
                    "window": {"from": args.window_from, "to": args.window_to},
                    "overlaps": pairs,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif not pairs:
        print("no cross-owner overlaps in the window")
    else:
        print(f"{len(pairs)} cross-owner overlap(s):")
        for pair in pairs:
            print(
                f"{pair['overlap_start']}–{pair['overlap_end']}: "
                f"[{pair['a']['owner']}] {pair['a']['title']} "
                f"vs [{pair['b']['owner']}] {pair['b']['title']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
