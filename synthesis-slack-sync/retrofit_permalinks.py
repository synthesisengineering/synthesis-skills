#!/usr/bin/env python3
"""Retrofit a daily plan (or any markdown file) to use clickable Slack permalinks.

Finds legacy bare-TS references like `(TS: 1234567890.123456)` or
`TS 1234567890.123456` and replaces each with a clickable Slack permalink in
the v3.1.0+ format: `[<human time>](https://workspace.slack.com/archives/CHID/p<ts>)`.

The visible text is the human-readable time nearest the TS on the same line.
The Unix TS hides in the URL path (`/pNNNNNNNNNNNNNNNN`) so the rendered
output in synthesis-console (or any Markdown viewer) shows just the clickable
time, no Unix-TS clutter.

Workspace specifics — the Slack URL host, channel-name → channel-ID map, and
DM-name → DM-channel-ID map — come from a `slack-sync.yaml` config file. The
script itself stays generic; nothing about a particular Slack workspace is
hardcoded.

Skip rules:
  - "parent thread TS" references are left alone. The visible human time on
    the line is the *reply* time; linking it to the parent's TS would be wrong.
  - Lines with no resolvable channel context (no `#channel-name`, no `D0…`/`C0…`
    ID inline) are left unchanged. The script needs at least one channel hint
    on the same line to construct a permalink.
  - Lines with no human-readable time near the TS get a small `[(↗)](url)`
    suffix instead of in-place linkification.

Usage:
    python3 retrofit_permalinks.py <plan.md> --config <slack-sync.yaml>
    python3 retrofit_permalinks.py <plan.md> --config <slack-sync.yaml> --dry-run

Multi-workspace daily plans: run once per workspace's slack-sync.yaml. Each
run only retrofits TSes whose channel resolves via the config it was given;
other lines are left for the next pass.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. Install with `pip install pyyaml`.\n")
    sys.exit(1)


# Slack TS in float form (e.g., "1234567890.123456"), optionally preceded by
# "reply " or wrapped in parentheses. We capture the TS itself; surrounding
# parens/whitespace are handled in the line-rewrite logic below.
TS_RE = re.compile(r'(?:reply\s+)?TS[:=\s]+(\d{10}\.\d{6})')

# Human-readable time patterns, ordered most-specific first so multi-token
# matches ("Wed Apr 29, 11:52 AM EDT") beat their substring ("11:52 AM EDT").
TIME_PATTERNS = [
    re.compile(r'\w{3,9},?\s+\w{3,9}\.?\s+\d{1,2},?\s+\d{1,2}:\d{2}\s*[AP]M\s+[A-Z]{2,4}'),
    re.compile(r'\d{1,2}:\d{2}\s*[AP]M\s+[A-Z]{2,4}'),
    re.compile(r'\b\d{1,2}:\d{2}\s+[A-Z]{2,4}\b'),
]


def load_config(config_path: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    """Load slack_workspace_domain + channel/DM ID maps from a slack-sync.yaml."""
    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    domain = cfg.get("slack_workspace_domain")
    if not domain:
        raise ValueError(
            f"slack_workspace_domain not set in {config_path}. "
            "Add `slack_workspace_domain: <subdomain>.slack.com` to the config "
            "(see synthesis-slack-sync v3.1.0 docs)."
        )

    channel_map: dict[str, str] = {}
    for ch in cfg.get("channels", []) or []:
        if "name" in ch and "id" in ch:
            channel_map[ch["name"]] = ch["id"]

    dm_map: dict[str, str] = {}
    for dm in cfg.get("dm_channels", []) or []:
        if "name" in dm and "dm_id" in dm:
            dm_map[dm["name"]] = dm["dm_id"]

    # Group DMs use channel IDs (not user IDs), reachable via #channel-style
    # references in some workflows. Include them under channel_map keyed by
    # name where present.
    for gdm in cfg.get("group_dm_channels", []) or []:
        if "name" in gdm and "id" in gdm:
            channel_map[gdm["name"]] = gdm["id"]

    return domain, channel_map, dm_map


def find_channel_id(line: str, channel_map: dict[str, str]) -> str | None:
    """Resolve a channel/DM ID from the most reliable hint on the line."""
    m = re.search(r'#([a-z0-9_-]+)', line)
    if m and m.group(1) in channel_map:
        return channel_map[m.group(1)]
    # Inline DM channel ID, e.g., "DM with X (D0AL2JPH68H)"
    m = re.search(r'\b(D0[A-Z0-9]{8,})\b', line)
    if m:
        return m.group(1)
    # Inline channel ID, e.g., "(C0AKDAQN34G)"
    m = re.search(r'\b(C0[A-Z0-9]{8,})\b', line)
    if m:
        return m.group(1)
    return None


def find_latest_time_in(prefix: str):
    """Find the human-readable time match closest to the END of `prefix`."""
    best = None
    for tp in TIME_PATTERNS:
        for tm in tp.finditer(prefix):
            if best is None or tm.start() > best.start():
                best = tm
    return best


def cleanup_line(line: str) -> str:
    """Normalize artifacts left after TS removal (orphan commas, double dots, etc.)."""
    # Stranded "Reply." word ("thread. Reply. Sent" -> "thread. Sent")
    line = re.sub(r'(?<![A-Za-z])[Rr]eply\.\s+', '', line)
    line = re.sub(r'\(\s*[Rr]eply\s*\)', '', line)
    # Double commas; orphan commas adjacent to parens
    line = re.sub(r',,', ',', line)
    line = re.sub(r',\s*\)', ')', line)
    line = re.sub(r'\(\s*,\s*', '(', line)
    line = re.sub(r'\(\s*\)', '', line)
    # Double periods, comma-then-period
    line = re.sub(r'\.\s*\.', '.', line)
    line = re.sub(r',\s*\.', '.', line)
    # Space before punctuation
    line = re.sub(r'\s+([.,;])', r'\1', line)
    # Collapse runs of spaces, but preserve leading indentation
    leading_ws = re.match(r'^(\s*)', line).group(1)
    rest = line[len(leading_ws):]
    rest = re.sub(r'  +', ' ', rest)
    return leading_ws + rest


def process_line(line: str, domain: str, channel_map: dict[str, str]) -> str:
    channel_id = find_channel_id(line, channel_map)
    if not channel_id:
        return line

    matches = list(TS_RE.finditer(line))
    if not matches:
        return line

    # Find the FIRST primary TS — skip ones preceded by "parent" within 30 chars.
    primary = None
    for m in matches:
        prefix_30 = line[max(0, m.start() - 30):m.start()].lower()
        if 'parent' in prefix_30:
            continue
        primary = m
        break

    if primary is None:
        return line

    ts = primary.group(1)
    permalink = f"https://{domain}/archives/{channel_id}/p{ts.replace('.', '')}"

    # Prefer a human time BEFORE the TS; fall back to the first one AFTER it
    # (covers bracketed annotation lines like "[#channel, TS X, 13:19 EDT, ...]").
    time_match = find_latest_time_in(line[:primary.start()])
    time_after_ts = False
    if time_match is None:
        suffix = line[primary.end():]
        for tp in TIME_PATTERNS:
            tm = tp.search(suffix)
            if tm is None:
                continue
            if time_match is None or tm.start() < time_match.start():
                time_match = re.compile(re.escape(tm.group(0))).search(line, primary.end())
                time_after_ts = True

    if time_match:
        time_text = time_match.group(0)
        ts_start = primary.start()
        ts_end = primary.end()

        # Walk back over a "reply " / "Reply " word that precedes the TS so
        # we strip the whole "Reply TS: ..." phrase cleanly.
        m_prefix = re.search(r'(?:[Rr]eply\s+)$', line[:ts_start])
        if m_prefix:
            ts_start = ts_start - len(m_prefix.group(0))

        # If the TS sits inside surrounding parens with no other content,
        # consume the parens too.
        before = line[:ts_start].rstrip()
        after = line[ts_end:].lstrip()
        if before.endswith('(') and after.startswith(')'):
            ts_start = before.rfind('(')
            ts_end = line.index(')', ts_end) + 1

        if time_after_ts:
            t_start, t_end = time_match.start(), time_match.end()
            new_line = (
                line[:ts_start].rstrip()
                + line[ts_end:t_start]
                + f"[{time_text}]({permalink})"
                + line[t_end:]
            )
        else:
            new_line = (
                line[:time_match.start()]
                + f"[{time_text}]({permalink})"
                + line[time_match.end():ts_start].rstrip()
                + line[ts_end:]
            )
        return cleanup_line(new_line)

    # No human time anywhere — append a small clickable suffix in the TS's
    # spot. The TS text itself is replaced (not duplicated).
    new_line = (
        line[:primary.start()]
        + f"[(↗)]({permalink})"
        + line[primary.end():]
    )
    return cleanup_line(new_line)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See synthesis-slack-sync SKILL.md (v3.1.0+) for context.",
    )
    parser.add_argument("plan", help="Daily plan markdown file to retrofit")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to slack-sync.yaml with slack_workspace_domain + channel list",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show unified diff without writing the file",
    )
    args = parser.parse_args()

    plan_path = Path(args.plan).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()

    if not plan_path.is_file():
        sys.stderr.write(f"ERROR: daily plan not found: {plan_path}\n")
        return 1
    if not config_path.is_file():
        sys.stderr.write(f"ERROR: config not found: {config_path}\n")
        return 1

    try:
        domain, channel_map, _dm_map = load_config(config_path)
    except ValueError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1

    content = plan_path.read_text()
    lines = content.split("\n")
    new_lines = [process_line(line, domain, channel_map) for line in lines]
    new_content = "\n".join(new_lines)

    if new_content == content:
        print(f"No changes needed for {plan_path.name}.")
        return 0

    changed = sum(1 for a, b in zip(lines, new_lines) if a != b)

    if args.dry_run:
        print(f"DRY RUN: would update {changed} lines in {plan_path.name}.\n")
        for diff_line in difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"{plan_path.name} (before)",
            tofile=f"{plan_path.name} (after)",
            lineterm="",
        ):
            sys.stdout.write(diff_line)
    else:
        plan_path.write_text(new_content)
        print(f"Updated {changed} lines in {plan_path.name}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
