#!/usr/bin/env python3
"""Shared parsing helpers for synthesis project context."""

from __future__ import annotations

import re


CHECKLIST = re.compile(r"^(?:[-*]|\d+\.)\s+\[([ xX])\]\s+")


def extract(context: str, key: str) -> str:
    """Extract a bold metadata field from CONTEXT.md."""
    match = re.search(rf"^\*\*{re.escape(key)}:\*\*\s*(.+)$", context, re.MULTILINE)
    return match.group(1).strip() if match else "unknown"


def next_actions(context: str, limit: int = 5) -> list[str]:
    """Return pending What's Next checklist items, including continuations."""
    match = re.search(
        r"^## What's Next[^\n]*\n(.*?)(?=^## |\Z)",
        context,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return []

    lines = [line.strip() for line in match.group(1).splitlines()]
    items: list[tuple[bool, list[str]]] = []
    current: tuple[bool, list[str]] | None = None
    for line in lines:
        item = CHECKLIST.match(line)
        if item:
            if current is not None:
                items.append(current)
            current = (item.group(1).lower() == "x", [line])
        elif current is not None and line:
            current[1].append(line)
    if current is not None:
        items.append(current)

    pending = [" ".join(parts) for done, parts in items if not done]
    return pending[:limit]
