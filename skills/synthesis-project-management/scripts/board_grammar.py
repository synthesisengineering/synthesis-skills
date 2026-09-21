#!/usr/bin/env python3
"""The shared, versioned grammar for the coordination board's active table.

Only rows inside the single Active sessions section confer claims. All readers
use the named v1-v4 columns, strip the same display markup, and refuse malformed
rows instead of treating unreadable authority as an empty board. Strict mode
also requires the canonical metadata and table shape used by the inbox guard.
Identity and ownership validation remain the callers' responsibility.
"""
from __future__ import annotations

import re
from pathlib import Path

SCHEMA_VERSION = 5
V5_COLUMNS = (
    "session uuid",
    "compact id",
    "speakable id v1",
    "legacy id",
    "agent",
    "machine",
    "machine label",
    "client session ref",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V4_COLUMNS = (
    "session uuid",
    "compact id",
    "speakable id v1",
    "legacy id",
    "agent",
    "machine",
    "client session ref",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V3_COLUMNS = (
    "session uuid",
    "compact id",
    "speakable id v1",
    "legacy id",
    "agent",
    "machine",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V2_COLUMNS = (
    "id",
    "agent",
    "machine",
    "project",
    "started",
    "heartbeat",
    "mode",
    "workspace(s) / branch",
    "goal",
    "claimed areas (advisory lock)",
    "context role",
    "status",
)
V1_COLUMNS = (
    "id",
    "agent",
    "started",
    "mode",
    "goal",
    "claimed areas (advisory lock)",
    "status",
)

_COLUMNS = {
    1: V1_COLUMNS,
    2: V2_COLUMNS,
    3: V3_COLUMNS,
    4: V4_COLUMNS,
    5: V5_COLUMNS,
}
_WIDTHS = frozenset(map(len, _COLUMNS.values()))
_ENGINE = Path(__file__).with_name("coordination.py")


class UnsupportedBoardSchemaError(ValueError):
    """A board newer than this engine; writers refuse before any mutation.

    Guarded protocol evolution (fleet design section 1.3): a writer that
    does not understand the declared schema fails closed instead of
    reinterpreting columns it was never taught.
    """


def ensure_writable_schema(text: str, *, supported: int | None = None) -> int | None:
    """Refuse a write to a board newer than this engine understands.

    Returns the declared schema (None for undeclared legacy boards, which
    stay readable for explicit migration). Raises the named
    UnsupportedBoardSchemaError before the caller touches the lease remote.
    """
    from coordination_schema import engine_remedy

    effective = SCHEMA_VERSION if supported is None else supported
    declared = board_schema(text)
    if declared is not None and declared > effective:
        raise UnsupportedBoardSchemaError(
            f"board declares schema v{declared}, newer than this engine's "
            f"v{effective}; {engine_remedy(_ENGINE)}"
        )
    return declared


def plain(value: str) -> str:
    # One strip rule for every reader: claim globs such as docs/** must
    # survive the table parse exactly as written, or exact-match verbs
    # (narrow, request-narrow, the honor pass) cannot name what the row
    # holds and every re-serialization silently rewrites the file.
    from claim_scope import plain as claim_plain

    return claim_plain(value)


def board_schema(text: str) -> int | None:
    """Read the declared schema without consuming following blank lines."""
    match = re.search(r"(?m)^Schema:[ \t]*v(\d+)[ \t]*$", text)
    return int(match.group(1)) if match else None


def _cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.rstrip().endswith("|"):
        raise ValueError("coordination board has an invalid active-session row delimiter")
    return [value.strip() for value in line.rstrip().split("|")[1:-1]]


def parse_cells(line: str) -> list[str] | None:
    """Read one row, excluding recognized headers and separator rows."""
    if not line.startswith("|"):
        return None
    cells = _cells(line)
    if not cells or plain(cells[0]).lower() in {"id", "session uuid"}:
        return None
    if all(re.fullmatch(r":?-{3,}:?", value) for value in cells):
        return None
    return cells


def parse_table_rows(text: str, *, strict: bool = False) -> list[dict[str, str]]:
    """Parse one active table; schema and column errors are never ignored.

    Undeclared legacy boards remain readable for explicit migration. Strict
    reads require a declared supported schema and exactly one Messages section,
    plus the canonical (unformatted, lowercase) header and plain separators.
    """
    # Import diagnostics at call time: the schema module re-exports this
    # grammar alongside its identity API, without maintaining a second parser.
    from coordination_schema import column_count_error, engine_remedy

    lines = text.splitlines()
    declared = board_schema(text)
    declarations = [line for line in lines if line.startswith("Schema:")]
    if declared is not None and declared > SCHEMA_VERSION:
        raise UnsupportedBoardSchemaError(
            f"board declares schema v{declared}, newer than this engine's "
            f"v{SCHEMA_VERSION}; {engine_remedy(_ENGINE)}"
        )
    if (
        declarations and (len(declarations) != 1 or declared not in _COLUMNS)
    ) or (strict and declared is None):
        raise ValueError("coordination board has an invalid or unsupported schema")
    starts = [i for i, line in enumerate(lines) if line.strip() == "## Active sessions"]
    if len(starts) != 1:
        raise ValueError("coordination board must have one Active sessions section")
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("## ")),
        len(lines),
    )
    if strict:
        messages = [i for i, line in enumerate(lines) if line.strip() == "## Messages"]
        if len(messages) != 1 or messages[0] != end:
            raise ValueError("coordination board must have one Messages section after Active sessions")
    table = [line for line in lines[start + 1:end] if line.strip()]
    if len(table) < 2:
        raise ValueError("coordination board has an invalid active-session table header")
    header = _cells(table[0])
    columns = tuple(plain(cell).lower() for cell in header)
    if columns not in _COLUMNS.values() or (
        declared is not None and columns != _COLUMNS[declared]
    ):
        raise ValueError("coordination board has an invalid active-session table header")
    separators = _cells(table[1])
    separator_pattern = r"-{3,}" if strict else r":?-{3,}:?"
    if (
        (strict and header != list(columns))
        or len(separators) != len(columns)
        or any(re.fullmatch(separator_pattern, cell) is None for cell in separators)
    ):
        raise ValueError("coordination board has an invalid active-session table header")
    result: list[dict[str, str]] = []
    for line in table[2:]:
        cells = parse_cells(line)
        if cells is None:
            raise ValueError("coordination board has an invalid active-session row")
        if len(cells) not in _WIDTHS:
            raise column_count_error(cells, _ENGINE)
        if len(cells) != len(columns):
            raise ValueError(
                f"active-session row has {len(cells)} columns but its table header "
                f"requires {len(columns)}; malformed row"
            )
        result.append(dict(zip(columns, (plain(cell) for cell in cells))))
    return result
