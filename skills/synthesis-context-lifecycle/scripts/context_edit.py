#!/usr/bin/env python3
"""Fail-closed edits to durable context files.

A scripted edit to `CONTEXT.md`, `REFERENCE.md`, or a session log is an
assertion that a specific change was made. Hand-rolled `str.replace()` does not
assert anything: when an anchor no longer matches — because another agent
legitimately rewrote that region between sessions — the replacement silently
becomes a no-op, and any surrounding "updated" message is false. That output
then gets committed, and record-versus-git checks still pass, because the file
is committed; it is simply not current.

This helper makes the assertion real. Every operation verifies that the anchor
matched the expected number of times, that content actually changed, and that
the change is present in the file after writing. Anything else exits non-zero
without writing. There is no flag to make a missing anchor succeed.

Line-oriented insertion requires a line-start anchor and newline-terminated
text. Replacement protects the region's outer separators against accidental
line fusion, including the combined effect of repeated adjacent matches.
Interior restructuring remains explicit editing. LF and CRLF bytes are not
normalized during reading, writing, or verification.

Use it from any session or script that edits a durable context file, rather
than reimplementing replacement logic per project.

Command line
------------

    context_edit.py replace --file F --anchor TEXT --replacement TEXT
                            [--count N] [--max-lines N] [--dry-run]
    context_edit.py set-field --file F --field Phase --value TEXT
                            [--max-lines N] [--dry-run]
    context_edit.py insert-before --file F --anchor TEXT --text TEXT
                            [--max-lines N] [--dry-run]
    context_edit.py delete-line --file F --anchor TEXT
                            [--max-lines N] [--dry-run]

Use `insert-before` to prepend a section — a changelog release, a session-log
entry — rather than a `replace` that restates the anchor inside its own
replacement. Forgetting to restate it deletes the heading you anchored on, and
the edit still reports success because content did change.

Value arguments accept `-` to read from stdin, which keeps multi-line and
quote-heavy content out of shell escaping.

Python
------

    from context_edit import replace_once, ContextEditError

    replace_once(path, anchor="**Phase:** old", replacement="**Phase:** new")

Exit codes: 0 changed or valid dry-run, 1 refusal/I/O/verification failure,
2 usage error. Preflight failures write nothing; post-write failures require
re-reading the target before retrying.
"""

from __future__ import annotations

import argparse
import json
import stat
import os
import re
import sys
import tempfile
from pathlib import Path

import context_currency

import record_transaction


class ContextEditError(Exception):
    """Preflight refusal or post-write verification failure; inspect the phase."""


def _coherence_gate(
    path: Path,
    original: str,
    edited: str,
    allow_header_lag: bool,
    allow_stale_body: bool = False,
    state_reviewed: bool = False,
) -> str | None:
    """Refuse an edit that creates or changes an incoherent CONTEXT.md header.

    Phase and Last session describe one state and must move together. A
    round-11 Phase over a round-10 Last session is exactly the stale-header
    defect this tooling exists to prevent, so an edit that produces that pair
    is refused at write time — the file is never wrong, rather than detected
    wrong later.

    Pre-existing incoherence that this edit does not touch is warned about,
    not blocked: an unrelated body edit must not be hostage to an earlier
    session's defect. Returns a warning string in that case, None otherwise.
    """
    if path.name != "CONTEXT.md":
        return None
    notes_out: list[str] = []
    after = context_currency.header_incoherence(edited)
    if not after:
        notes_out.extend(
            _body_gate(original, edited, allow_stale_body, state_reviewed)
        )
        return "; ".join(notes_out) if notes_out else None
    # Only Phase-ahead-of-Last-session is the defect shape: a described new
    # state over a stale log pointer. Last session leading Phase is the normal
    # transition while a two-call update is in flight, and the doctor's
    # read-time field check catches a Phase left behind. A symmetric refusal
    # would deadlock every legitimate two-call header update.
    leading = [(family, phase, last) for family, phase, last in after if phase > last]
    trailing = [(family, phase, last) for family, phase, last in after if last > phase]
    notes: list[str] = []
    if trailing:
        notes.append(
            "note: Last session now leads Phase ("
            + "; ".join(f"{family} {last} vs {phase}" for family, phase, last in trailing)
            + ") — finish by updating Phase"
        )
    if leading:
        described = "; ".join(
            f"**Phase:** says {family} {phase_n} while **Last session:** "
            f"still says {family} {last_n}"
            for family, phase_n, last_n in leading
        )
        before = context_currency.header_incoherence(original)
        if [x for x in before if x[1] > x[2]] == leading:
            notes.append(
                f"warning: pre-existing header incoherence left untouched "
                f"({described}); repair it with set-field"
            )
        elif allow_header_lag:
            notes.append(f"override --allow-header-lag recorded ({described})")
        else:
            raise ContextEditError(
                f"edit would leave the header incoherent: {described}.\n"
                "Update Last session in the same change (or first), or pass "
                "--allow-header-lag to record an explicit override."
            )
    notes.extend(_body_gate(original, edited, allow_stale_body, state_reviewed))
    return "; ".join(notes) if notes else None


def _header_identity(text: str) -> tuple[str | None, dict[str, int]]:
    """(Last-session date, per-family header ordinal) for gate comparisons.

    Per family, the identity is the max of Phase and Last session — by the
    time the header gate has passed, the two agree; mid-edit, the larger one
    is the state the edit is advancing toward.
    """
    fields = context_currency.header_fields(text)
    date_match = context_currency.HEADER_DATE.search(text)
    identity: dict[str, int] = {}
    for value in fields.values():
        for family, number in context_currency.first_ordinals(value).items():
            if number > identity.get(family, -1):
                identity[family] = number
    return (date_match.group(1) if date_match else None), identity


def _section_prose(text: str, section: str) -> str:
    """A section's text minus its as-of marker lines, for change detection."""
    lines = text.splitlines()
    collected: list[str] = []
    inside = section == "(top)"
    for line in lines:
        heading = context_currency.SECTION_HEADING.match(line)
        if heading:
            inside = heading.group(1) == section
            continue
        if inside and not context_currency.STATE_AS_OF.match(line):
            collected.append(line)
    return "\n".join(collected).strip()


def _body_gate(
    original: str,
    edited: str,
    allow_stale_body: bool,
    state_reviewed: bool,
) -> list[str]:
    """Gate the body's as-of markers against the header the edit produces.

    Returns note strings; raises ContextEditError on the defect shape. Three
    rules, each tied to a real occurrence:

    - A header advance over a lagging marker is refused: in all three real
      occurrences the agent advanced the header and stopped, so this is the
      control that interrupts exactly that motion.
    - A marker advanced (or added) while its section's prose is byte-identical
      requires --state-reviewed: the marker is an assertion that the section
      was re-read and still holds, and bumping it mechanically would just
      recreate the header defect one level down. The flag converts a silent
      bump into a recorded assertion.
    - Whatever happens, the completion signal names the body state, because a
      success message that says less than it verified manufactures completion
      for partial work.
    """
    notes: list[str] = []
    new_date, new_ordinals = _header_identity(edited)
    old_date, old_ordinals = _header_identity(original)
    header_advanced = bool(
        (new_date and old_date and new_date > old_date)
        or any(
            number > old_ordinals.get(family, number)
            for family, number in new_ordinals.items()
        )
    )

    markers = context_currency.body_markers(edited)
    if not markers:
        notes.append(
            "body: no *State as of:* markers — body currency unverifiable"
        )
        return notes

    old_markers = {
        m["section"]: m for m in context_currency.body_markers(original)
    }
    stale: list[str] = []
    for marker in markers:
        lag = (new_date and marker["date"] < new_date) or any(
            number < new_ordinals.get(family, number)
            for family, number in marker["ordinals"].items()
        )
        if lag:
            stale.append(marker["section"])
        previous = old_markers.get(marker["section"])
        advanced = previous is None or (
            marker["date"] > previous["date"]
            or any(
                number > previous["ordinals"].get(family, -1)
                for family, number in marker["ordinals"].items()
            )
        )
        if advanced:
            before = _section_prose(original, marker["section"])
            after = _section_prose(edited, marker["section"])
            if before == after and before != "":
                if state_reviewed:
                    notes.append(
                        f"reviewed-no-change recorded for "
                        f"'{marker['section']}'"
                    )
                else:
                    raise ContextEditError(
                        f"the as-of marker in '{marker['section']}' advanced "
                        "while the section's prose is unchanged. The marker "
                        "asserts the section was re-read and still holds — "
                        "pass --state-reviewed to record that assertion, or "
                        "update the prose in the same edit."
                    )

    if stale:
        named = ", ".join(f"'{s}'" for s in stale)
        if header_advanced and not allow_stale_body:
            raise ContextEditError(
                f"edit advances the header while the body lags: {named} "
                "still carry an older *State as of:* marker. Rewrite those "
                "sections (or record a no-change review) in the same change, "
                "or pass --allow-stale-body to record an explicit override."
            )
        prefix = (
            "override --allow-stale-body recorded"
            if header_advanced
            else "warning: body lags the header"
        )
        notes.append(f"{prefix} ({named} behind the current state)")
    else:
        notes.append("body: as-of markers current")
    return notes


def _read(path: Path) -> str:
    if path.name == "index.yaml" and path.parent.name == "projects":
        raise ContextEditError("registry edits require registry-patch and an exact reviewed preimage")
    if path.is_symlink():
        raise ContextEditError(f"refusing to edit a symlink: {path}")
    if not path.is_file():
        raise ContextEditError(f"not a file: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read()


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, then rename.

    A durable record must never be left half-written by an interrupted edit.
    """
    directory = path.parent
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=directory, delete=False
    )
    try:
        with handle as stream:
            stream.write(text)
            stream.flush()
            os.fchmod(stream.fileno(), stat.S_IMODE(path.stat().st_mode))
            os.fsync(stream.fileno())
        os.replace(handle.name, path)
        # Rename visibility is atomic; directory fsync is the distinct
        # durability boundary. Failure here means inspect the committed file.
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def _line_merge_refusal(
    original: str, anchor: str, replacement: str, edited: str, offsets: list[int],
) -> str | None:
    """Find an outer separator whose removal joins surviving line content.

    Read neighbors from the complete result, not from the original matches:
    adjacent deletions can remove the neighbor a preceding check relied on.
    An absent neighbor or a surviving separator allows whole-line deletion,
    blank-line removal, and edits at the first and last physical boundaries.
    """
    displacement = 0
    for offset in offsets:
        end = offset + len(anchor)
        start_after = offset + displacement
        end_after = start_after + len(replacement)
        boundaries = []
        if anchor.startswith(("\n", "\r\n")) and offset > 0:
            boundaries.append((start_after, offset))
        if anchor.endswith("\n") and end < len(original):
            boundaries.append((end_after, end))
        for position, original_position in boundaries:
            if (
                0 < position < len(edited)
                and edited[position - 1] != "\n"
                and edited[position] != "\n"
                and edited[position : position + 2] != "\r\n"
            ):
                line = original.count("\n", 0, original_position) + 1
                return f"the edit removes the separator at line {line}"
        displacement += len(replacement) - len(anchor)
    return None


def _check_line_insert(original: str, anchor: str, inserted: str) -> None:
    """Validate insertion against the same snapshot the edit will replace."""
    if not inserted.endswith("\n"):
        raise ContextEditError(
            "insert-before would corrupt line structure: --text does not "
            "end with a newline; end the text with a newline"
        )
    offset = original.find(anchor)
    if offset > 0 and original[offset - 1] != "\n":
        line = original.count("\n", 0, offset) + 1
        raise ContextEditError(
            "insert-before would corrupt line structure: "
            f"the anchor begins mid-line (line {line}); anchor on the start "
            "of a line instead"
        )


def _table_cells(line: str) -> list[str] | None:
    """Pipe-table cells, distinguishing escaped pipes from separators."""
    text = line.strip()
    cells: list[str] = []
    start = 0
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == "|":
            cells.append(text[start:cursor].strip())
            start = cursor + 1
        cursor += 1
    if not cells:
        return None
    cells.append(text[start:].strip())
    if not cells[0]:
        cells.pop(0)
    if cells and not cells[-1]:
        cells.pop()
    return cells or None


def _table_regions(text: str) -> list[tuple[int, int]]:
    """Recognize Markdown pipe tables outside fenced code, by text offsets."""
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    regions: list[tuple[int, int]] = []
    fence: str | None = None
    i = 0
    while i < len(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)", lines[i])
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
        elif i + 1 < len(lines):
            header = _table_cells(lines[i])
            rule = _table_cells(lines[i + 1])
            if header and rule and len(header) == len(rule) and all(re.fullmatch(r":?-+:?", cell) for cell in rule):
                end = i + 2
                while end < len(lines) and _table_cells(lines[end]):
                    end += 1
                regions.append((starts[i], starts[end]))
                i = end
                continue
        i += 1
    return regions


def _splice(text: str, anchor: str, replacement: str, offsets: list[int]) -> str:
    parts: list[str] = []
    cursor = 0
    for offset in offsets:
        parts.extend((text[cursor:offset], replacement))
        cursor = offset + len(anchor)
    parts.append(text[cursor:])
    return "".join(parts)


def _check_table_edit(original: str, anchor: str, replacement: str, offsets: list[int]) -> None:
    """Partial edits must leave an existing table as one complete table.

    An anchor naming the entire table permits deliberate replacement of that
    structure. Otherwise its header, delimiter and surviving rows remain a
    unit; a blank replacement must not silently terminate the table.
    """
    edits = [(offset, offset + len(anchor)) for offset in offsets]
    for start, end in _table_regions(original):
        affected = [(a, b) for a, b in edits if a < end and b > start]
        content_end = end - (2 if original[:end].endswith("\r\n") else 1 if original[:end].endswith("\n") else 0)
        if not affected or any(a <= start and b >= content_end for a, b in affected):
            continue
        if any(a < start or b > end for a, b in affected):
            raise ContextEditError("edit crosses a Markdown table boundary; include the complete table in the anchor")
        edited = _splice(original[start:end], anchor, replacement, [a - start for a, _b in affected])
        if _table_regions(edited) != [(0, len(edited))]:
            raise ContextEditError(
                "edit would break a Markdown table; use delete-line for an exact data row, "
                "preserve the header and delimiter, or include the complete table explicitly"
            )


def apply_replacement(
    text: str,
    anchor: str,
    replacement: str,
    *,
    count: int = 1,
    _line_offset: int | None = None,
) -> str:
    """Return edited text, or raise ContextEditError explaining the refusal."""
    if not anchor:
        raise ContextEditError("anchor must not be empty")
    if count < 1:
        raise ContextEditError(f"count must be at least 1, got {count}")

    offsets: list[int] = []
    offset = text.find(anchor)
    while offset != -1:
        offsets.append(offset)
        offset = text.find(anchor, offset + len(anchor))
    if _line_offset is not None:
        # delete-line selected one complete physical line from this same
        # snapshot; suffix matches in other lines are not deletion targets.
        if _line_offset not in offsets or (_line_offset and text[_line_offset - 1] != "\n"):
            raise ContextEditError("delete-line target no longer matches a line boundary")
        offsets = [_line_offset]
    found = len(offsets)
    if found == 0:
        raise ContextEditError(
            f"anchor not found: {anchor[:80]!r}\n"
            "The record may have been rewritten by another session. Re-read "
            "the current file and build the anchor from it rather than from "
            "remembered content."
        )
    if found != count:
        raise ContextEditError(
            f"anchor matched {found} time(s), expected {count}: {anchor[:80]!r}\n"
            "Narrow the anchor, or pass --count to confirm the intended number."
        )

    edited = _splice(text, anchor, replacement, offsets)
    refusal = _line_merge_refusal(text, anchor, replacement, edited, offsets)
    if refusal:
        raise ContextEditError(
            f"edit would merge previously separate lines: {refusal}.\n"
            "Keep a boundary newline, or include the neighboring line "
            "explicitly in both anchor and replacement."
        )
    _check_table_edit(text, anchor, replacement, offsets)
    if edited == text:
        raise ContextEditError(
            "replacement leaves the file byte-identical; nothing to change"
        )
    return edited


def _check_budget(text: str, max_lines: int | None, path: Path) -> int:
    lines = len(text.splitlines())
    if max_lines is not None and lines > max_lines:
        raise ContextEditError(
            f"edit would leave {path.name} at {lines} lines, over the "
            f"{max_lines}-line budget; trim in the same edit"
        )
    return lines


@record_transaction.guarded("path", exclusive=True)
def replace_once(
    path: Path,
    anchor: str,
    replacement: str,
    *,
    count: int = 1,
    max_lines: int | None = None,
    dry_run: bool = False,
    allow_header_lag: bool = False,
    allow_stale_body: bool = False,
    state_reviewed: bool = False,
    _inserted_text: str | None = None,
    _delete_line: bool = False,
) -> dict:
    """Apply one verified replacement to a durable context file."""
    path = Path(path)
    original = _read(path)
    line_offset = None
    if _delete_line:
        if not anchor or "\n" in anchor or "\r" in anchor:
            raise ContextEditError("delete-line requires the complete text of one nonempty line without its line ending")
        matches: list[tuple[int, str]] = []
        cursor = 0
        for line in original.splitlines(keepends=True):
            if line.removesuffix("\r\n").removesuffix("\n") == anchor:
                matches.append((cursor, line))
            cursor += len(line)
        if len(matches) != 1:
            raise ContextEditError(f"delete-line requires one exact whole-line match; found {len(matches)}")
        line_offset, anchor = matches[0]
    edited = apply_replacement(original, anchor, replacement, count=count, _line_offset=line_offset)
    if _inserted_text is not None:
        _check_line_insert(original, anchor, _inserted_text)
    lines = _check_budget(edited, max_lines, path)
    note = _coherence_gate(
        path,
        original,
        edited,
        allow_header_lag,
        allow_stale_body,
        state_reviewed,
    )

    if dry_run:
        return {
            "path": str(path),
            "changed": False,
            "dry_run": True,
            "replacements": count,
            "lines": lines,
            "note": note,
        }

    _atomic_write(path, edited)

    # Verify against the file on disk, not against the in-memory value we
    # intended to write. This is the whole point of the helper.
    written = _read(path)
    if written != edited:
        raise ContextEditError(
            f"post-write verification failed for {path}: on-disk content does "
            "not match the intended edit"
        )
    if replacement and replacement not in written:
        raise ContextEditError(
            f"post-write verification failed for {path}: replacement text is "
            "absent from the file"
        )
    return {
        "path": str(path),
        "changed": True,
        "dry_run": False,
        "replacements": count,
        "lines": len(written.splitlines()),
        "note": note,
    }


FIELD = "^\\*\\*{name}:\\*\\*[^\\r\\n]*"


def set_field(
    path: Path,
    field: str,
    value: str,
    *,
    max_lines: int | None = None,
    dry_run: bool = False,
    allow_header_lag: bool = False,
    allow_stale_body: bool = False,
    state_reviewed: bool = False,
) -> dict:
    """Replace a `**Field:** ...` header line, verifying it existed."""
    path = Path(path)
    original = _read(path)
    pattern = re.compile(FIELD.format(name=re.escape(field)), re.MULTILINE)
    matches = pattern.findall(original)
    if not matches:
        raise ContextEditError(
            f"header field not found: **{field}:**\n"
            "Re-read the current file; the record may use a different header."
        )
    if len(matches) > 1:
        raise ContextEditError(
            f"header field **{field}:** appears {len(matches)} times; "
            "the record is ambiguous and must be repaired by hand"
        )
    return replace_once(
        path,
        anchor=matches[0],
        replacement=f"**{field}:** {value}",
        max_lines=max_lines,
        dry_run=dry_run,
        allow_header_lag=allow_header_lag,
        allow_stale_body=allow_stale_body,
        state_reviewed=state_reviewed,
    )


def insert_before(
    path: Path,
    anchor: str,
    text: str,
    *,
    max_lines: int | None = None,
    dry_run: bool = False,
    allow_header_lag: bool = False,
    allow_stale_body: bool = False,
    state_reviewed: bool = False,
) -> dict:
    """Insert text immediately before an anchor, preserving the anchor.

    Prepending a new section — a changelog release, a session-log entry — with
    a raw replace requires restating the anchor inside the replacement, and
    forgetting to do so deletes the very heading you anchored on. The edit
    still "succeeds", because content did change. This operation removes that
    footgun by construction: the anchor is never consumed.

    The anchor must begin a line and the inserted text must end with a real
    newline. Refuse unsafe boundaries rather than adding separators silently.
    """
    return replace_once(
        path,
        anchor=anchor,
        replacement=f"{text}{anchor}",
        max_lines=max_lines,
        dry_run=dry_run,
        allow_header_lag=allow_header_lag,
        allow_stale_body=allow_stale_body,
        state_reviewed=state_reviewed,
        _inserted_text=text,
    )


def _value(raw: str) -> str:
    return sys.stdin.read() if raw == "-" else raw


def delete_line(
    path: Path, anchor: str, *, max_lines: int | None = None,
    dry_run: bool = False, allow_header_lag: bool = False,
    allow_stale_body: bool = False, state_reviewed: bool = False,
) -> dict:
    """Delete one uniquely matched physical line, including its LF or CRLF."""
    return replace_once(
        path, anchor=anchor, replacement="", max_lines=max_lines,
        dry_run=dry_run, allow_header_lag=allow_header_lag,
        allow_stale_body=allow_stale_body, state_reviewed=state_reviewed,
        _delete_line=True,
    )



def _edit_in_memory(text: str, edit: dict) -> str:
    """Resolve one batch operation against the staged result, without writes."""
    if not isinstance(edit, dict) or not isinstance(edit.get("op"), str):
        raise ContextEditError("each edit must be an object with an op")
    op = edit["op"]
    fields = {
        "replace": {"op", "anchor", "replacement", "count"},
        "append": {"op", "text"},
        "set-field": {"op", "field", "value"},
        "insert-before": {"op", "anchor", "text"},
        "delete-line": {"op", "anchor"},
    }
    if op not in fields or set(edit) - fields[op]:
        raise ContextEditError("unknown operation or fields in batch edit")
    for name in fields[op] - {"op", "count"}:
        if not isinstance(edit.get(name), str):
            raise ContextEditError(f"{op} requires string {name}")
    if op == "append":
        if not edit["text"]:
            raise ContextEditError("append requires nonempty text")
        return text + edit["text"]
    if op == "set-field":
        if not edit["field"] or any(c in edit["field"] + edit["value"] for c in "\r\n"):
            raise ContextEditError("set-field requires one field and one line of text")
        matches = re.findall(FIELD.format(name=re.escape(edit["field"])), text, re.MULTILINE)
        if len(matches) != 1:
            raise ContextEditError(f"header field requires one match; found {len(matches)}")
        return apply_replacement(text, matches[0], f"**{edit['field']}:** {edit['value']}")
    anchor = edit["anchor"]
    if op == "delete-line":
        if not anchor or "\n" in anchor or "\r" in anchor:
            raise ContextEditError("delete-line requires a whole line without its ending")
        matches, cursor = [], 0
        for line in text.splitlines(keepends=True):
            if line.removesuffix("\r\n").removesuffix("\n") == anchor:
                matches.append((cursor, line))
            cursor += len(line)
        if len(matches) != 1:
            raise ContextEditError(f"delete-line requires one exact whole-line match; found {len(matches)}")
        offset, full = matches[0]
        return apply_replacement(text, full, "", _line_offset=offset)
    if op == "insert-before":
        _check_line_insert(text, anchor, edit["text"])
        return apply_replacement(text, anchor, edit["text"] + anchor)
    count = edit.get("count", 1)
    if type(count) is not int or count < 1:
        raise ContextEditError("count must be a positive integer")
    return apply_replacement(text, anchor, edit["replacement"], count=count)


@record_transaction.guarded("path", exclusive=True)
def apply_edits(
    path: Path, edits: list[dict], *, max_lines: int | None = None,
    dry_run: bool = False, allow_header_lag: bool = False,
    allow_stale_body: bool = False, state_reviewed: bool = False,
) -> dict:
    """Preflight an ordered single-file batch, then atomically replace once.

    Every operation resolves against the preceding staged result. Structural
    edit checks apply to each operation; budget and currency apply once to the
    final result. Coordination ownership is still required: the final snapshot
    comparison detects intervening writes, but is not a filesystem CAS against
    uncooperative concurrent writers. No multi-file transaction is implied.
    """
    path = Path(path)
    original = _read(path)
    if not isinstance(edits, list) or not 1 <= len(edits) <= 1000:
        raise ContextEditError("edits must be a nonempty list of at most 1000 operations")
    edited = original
    for number, edit in enumerate(edits, 1):
        try:
            edited = _edit_in_memory(edited, edit)
        except ContextEditError as exc:
            raise ContextEditError(f"edit {number}: {exc}") from exc
    if edited == original:
        raise ContextEditError("batch leaves file byte-identical")
    lines = _check_budget(edited, max_lines, path)
    note = _coherence_gate(path, original, edited, allow_header_lag, allow_stale_body, state_reviewed)
    if _read(path) != original:
        raise ContextEditError("input changed during batch preflight; re-read before retrying")
    if not dry_run:
        _atomic_write(path, edited)
        if _read(path) != edited:
            raise ContextEditError("post-write verification failed: batch result differs on disk")
    return {"path": str(path), "changed": not dry_run, "dry_run": dry_run,
            "replacements": len(edits), "lines": lines, "note": note}


def _registry_nodes(text):
    """Bound structure before YAML composition; never expand aliases or tags."""
    import yaml
    if len(text.encode("utf-8")) > record_transaction.MAX_FILE_BYTES:
        raise ContextEditError("registry exceeds bounded source size")
    # Reject aliases and directives before composition; bound parser work.
    count = depth = 0
    try:
        for token in yaml.scan(text):
            count += 1
            if isinstance(token, (yaml.tokens.BlockMappingStartToken, yaml.tokens.BlockSequenceStartToken,
                                  yaml.tokens.FlowMappingStartToken, yaml.tokens.FlowSequenceStartToken)):
                depth += 1
            elif isinstance(token, (yaml.tokens.BlockEndToken, yaml.tokens.FlowMappingEndToken,
                                    yaml.tokens.FlowSequenceEndToken)):
                depth -= 1
            if count > 100000 or depth > 64 or isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken, yaml.tokens.TagToken, yaml.tokens.DirectiveToken)):
                raise ContextEditError("registry aliases, tags, directives or excessive structure refused")
        node = yaml.compose(text)
    except yaml.YAMLError as exc:
        raise ContextEditError("registry YAML is invalid") from exc
    def mapping(node):
        if not isinstance(node, yaml.MappingNode):
            raise ContextEditError("registry mapping required")
        result = {}
        for key, value in node.value:
            if not isinstance(key, yaml.ScalarNode) or key.value in result:
                raise ContextEditError("registry duplicate or nonscalar key")
            result[key.value] = value
        return result
    if isinstance(node, yaml.MappingNode):
        node = mapping(node).get("projects")
    if not isinstance(node, yaml.SequenceNode) or len(node.value) > 10000:
        raise ContextEditError("registry bounded project list required")
    entries = {}
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, yaml.MappingNode):
            mapping(current)
            stack.extend(value for _, value in current.value)
        elif isinstance(current, yaml.SequenceNode):
            stack.extend(current.value)
    for item in node.value:
        row = mapping(item); ident = row.get("id")
        if not isinstance(ident, yaml.ScalarNode) or ident.value in entries:
            raise ContextEditError("registry missing or duplicate id")
        entries[ident.value] = (item, row)
    return node, entries


def patch_registry(project: Path, entry: str, fields: dict, expected_sha256: str,
                   *, board: Path, native_payload: dict, dry_run=False) -> dict:
    """Apply reviewed entry fields, including creation and structured values.

    Unchanged fields and all other entries retain their exact bytes. Entry
    removal or whole-entry replacement uses apply-transaction's explicit
    @registry edit and the same reviewed SHA, native admission and journal.
    """
    import yaml
    project = record_transaction._path(project)
    path = record_transaction._target(project, "@registry")
    raw, meta = record_transaction._snapshot(path)
    if meta["sha256"] != expected_sha256:
        raise ContextEditError("registry reviewed preimage changed")
    if (not isinstance(entry, str) or not entry or len(entry) > 256
            or not isinstance(fields, dict) or not 1 <= len(fields) <= 64 or "id" in fields):
        raise ContextEditError("registry requires a bounded entry and 1..64 fields excluding id")
    # JSON values are literal YAML flow values. Bound traversal before encoding.
    stack = [(fields, 0)]; count = 0
    while stack:
        value, depth = stack.pop(); count += 1
        if count > 100000 or depth > 64:
            raise ContextEditError("registry field structure exceeds bounds")
        if type(value) is dict:
            if any(type(k) is not str or not k or len(k) > 4096 for k in value):
                raise ContextEditError("registry fields require bounded string keys")
            stack.extend((v, depth + 1) for v in value.values())
        elif type(value) is list:
            stack.extend((v, depth + 1) for v in value)
        elif type(value) not in (str, bool, int, float, type(None)):
            raise ContextEditError("registry field values must be JSON values")
    try:
        encoded = json.dumps(fields, ensure_ascii=False, allow_nan=False)
    except (ValueError, OverflowError) as exc:
        raise ContextEditError("registry field values must be finite JSON") from exc
    if len(encoded.encode("utf-8")) > 1024 * 1024:
        raise ContextEditError("registry fields exceed bounded bytes")
    text = raw.decode("utf-8")
    sequence, entries = _registry_nodes(text)
    edits = []
    target = entries.get(entry)
    if target is None:
        value = json.dumps({"id": entry, **fields}, ensure_ascii=False, allow_nan=False)
        if sequence.flow_style and not sequence.value:
            # The explicit empty state becomes the same id-first block form
            # consumed by routing and transactional registry admission.
            start, end = sequence.start_mark.index, sequence.end_mark.index
            line_start = text.rfind("\n", 0, start) + 1
            wrapped = text[line_start:start].strip() == "projects:"
            indent = "  " if wrapped else ""
            block = ("\n" if wrapped else "") + indent + "- id: " + json.dumps(entry) + "\n"
            block += "".join(indent + "  " + json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False, allow_nan=False) + "\n" for k, v in fields.items())
            edits.append((start, end, block))
        elif sequence.flow_style:
            at = sequence.end_mark.index - 1
            edits.append((at, at, ", " + value))
        else:
            at = sequence.end_mark.index
            prefix = "" if at == 0 or text[at - 1] == "\n" else "\n"
            indent = " " * sequence.start_mark.column
            block = indent + "- id: " + json.dumps(entry) + "\n"
            block += "".join(indent + "  " + json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False, allow_nan=False) + "\n" for k, v in fields.items())
            edits.append((at, at, prefix + block))
    else:
        item, row = target
        missing = {}
        for field, value in fields.items():
            replacement = json.dumps(value, ensure_ascii=False, allow_nan=False)
            old = row.get(field)
            if old is None:
                missing[field] = value
                continue
            # Block values consume a terminating newline/indent before the next
            # key; keep that separator while replacing only the value node.
            if old.end_mark.line > old.start_mark.line and (not isinstance(old, yaml.ScalarNode) or old.style in ("|", ">")):
                replacement += "\n" + " " * old.end_mark.column
            edits.append((old.start_mark.index, old.end_mark.index, replacement))
        if missing:
            if item.flow_style:
                at = item.end_mark.index - 1
                replacement = ", " + json.dumps(missing, ensure_ascii=False, allow_nan=False)[1:-1]
            else:
                at = item.end_mark.index
                indent = item.start_mark.column
                replacement = ("" if at == 0 or text[at - 1] == "\n" else "\n")
                replacement += "".join(" " * indent + json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False, allow_nan=False) + "\n" for k, v in missing.items())
            edits.append((at, at, replacement))
    edited = text
    for start, end, replacement in sorted(edits, reverse=True):
        edited = edited[:start] + replacement + edited[end:]
    _registry_nodes(edited)
    if edited == text:
        raise ContextEditError("registry patch leaves bytes unchanged")
    return apply_transaction(project, [{"file": "@registry", "expected_sha256": expected_sha256,
        "edits": [{"op": "replace", "anchor": text, "replacement": edited}]}],
        board=board, native_payload=native_payload, dry_run=dry_run)


def apply_transaction(project: Path, files: list[dict], *, board: Path,
                      native_payload: dict, dry_run: bool = False,
                      source_custody: list[dict] | None = None,
                      expected_claim_hash: str | None = None,
                      memory_home: dict | None = None) -> dict:
    """One recoverable multi-file project edit with fresh exact PM authority."""
    return record_transaction.apply(project, files, board=board,
                                    native_payload=native_payload, dry_run=dry_run,
                                    source_custody=source_custody,
                                    expected_claim_hash=expected_claim_hash,
                                    memory_home=memory_home)


def recover_transaction(project: Path, *, board: Path, native_payload: dict) -> dict:
    return record_transaction.recover(project, board=board, native_payload=native_payload)


# Native-memory import uses this owner rather than editing context files from a
# harness. Export packets are data, never routing, publication or clear authority.
MEMORY_MAX_ENTRIES = 64
MEMORY_PRESERVE = frozenset({"contract", "pay-equity", "hiring-negotiation",
                           "termination", "review-self", "ip-assignment", "dispute-evidence"})
MEMORY_KINDS = MEMORY_PRESERVE | {"lesson", "project-fact", "workspace-fact", "voice", "public-candidate"}


def _memory_owners():
    import importlib.util
    skills = Path(__file__).resolve().parents[2]
    def load(name, file):
        if name in sys.modules and Path(getattr(sys.modules[name], "__file__", "")).resolve() != file.resolve():
            raise ContextEditError("memory dependency is bound to another source generation")
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        return sys.modules[name]
    local = Path(__file__).resolve().parent
    if (local / "coordination_process.py").is_file():
        load("pending_manifest", local / "pending_manifest.py")
        return (load("ritual_workers", local / "ritual_workers.py"),
                load("publication_receipt", local / "publication_receipt.py"))
    load("pending_manifest", skills / "synthesis-repo-guard/pending_manifest.py")
    return (load("ritual_workers", skills / "synthesis-daily-rituals/scripts/ritual_workers.py"),
            load("publication_receipt", skills / "synthesis-repo-guard/publication_receipt.py"))


def _memory_digest(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def _memory_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def _memory_packet(packet):
    if (not isinstance(packet, dict) or set(packet) != {"schema", "harness", "store", "entries"}
            or type(packet["schema"]) is not int or packet["schema"] != 1
            or not isinstance(packet["harness"], str) or packet["harness"] not in {"codex", "claude", "muse"}
            or not isinstance(packet["entries"], list) or len(packet["entries"]) > MEMORY_MAX_ENTRIES):
        raise ContextEditError("bounded closed native export packet required")
    seen, total = set(), 0
    for item in packet["entries"]:
        if not isinstance(item, dict) or set(item) != {"id", "text", "sha256", "scope", "workspace_hint"}:
            raise ContextEditError("native export cannot contain routing decisions")
        if (not isinstance(item["id"], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", item["id"])
                or item["id"] in seen or not isinstance(item["text"], str) or not item["text"].strip()
                or len(item["text"].encode()) > 65536
                or item["sha256"] != _memory_digest(item["text"].encode())
                or not isinstance(item["scope"], str) or item["scope"] not in {"personal", "workspace", "unknown"}
                or "<!-- native-memory-key:" in item["text"] or "<!-- /native-memory-key:" in item["text"]
                or (item["workspace_hint"] is not None and
                    (not isinstance(item["workspace_hint"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", item["workspace_hint"])))):
            raise ContextEditError("native entry identity/content/scope invalid")
        total += len(item["text"].encode())
        seen.add(item["id"])
    if total > 1024 * 1024:
        raise ContextEditError("native export byte bound exceeded")


def _memory_preflight(packet, store, board, machine):
    _memory_packet(packet)
    workers, _ = _memory_owners()
    probe = workers.memory_probe(store, harness=packet["harness"], machine=machine, board=board)
    if probe["status"] == "PENDING_ACTIVE_HARNESS":
        return probe
    if packet["store"] != probe.get("store"):
        raise ContextEditError("native export store CAS changed; re-export through its own harness")
    return probe


def memory_ingest(project: Path, packet: dict, selection: dict, *, store: Path,
                  board: Path, machine: str, native_payload: dict, dry_run=False) -> dict:
    """Archive reviewed entries and append via the existing recoverable editor.

    Selection is an explicit Synthesis routing decision, not native output. One
    invocation is confined to one already selected private project/deletion unit.
    Files and archive parents must exist; this owner does not invent a project,
    workspace, private skill, publication approval or a model's semantic ruling.
    """
    probe = _memory_preflight(packet, store, board, machine)
    if probe["status"] == "PENDING_ACTIVE_HARNESS":
        return probe
    if (not isinstance(selection, dict) or set(selection) != {"family", "workspace", "archive_dir", "routes"}
            or not isinstance(selection["family"], str) or selection["family"] not in {"personal", "workspace"}
            or not isinstance(selection["routes"], list) or len(selection["routes"]) > MEMORY_MAX_ENTRIES):
        raise ContextEditError("explicit bounded private routing selection required")
    project = record_transaction._path(project)
    if selection["family"] == "workspace":
        if not isinstance(selection["workspace"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", selection["workspace"]):
            raise ContextEditError("workspace deletion-unit owner required")
    elif selection["workspace"] is not None:
        raise ContextEditError("personal root cannot impersonate a workspace deletion unit")
    def path_for(value):
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            raise ContextEditError("project-relative unaliased path required")
        path = record_transaction._path(project / value, project)
        if path == project or record_transaction.STORE in path.relative_to(project).parts:
            raise ContextEditError("reserved memory target")
        return path
    try:
        destination = record_transaction.memory_record_home(project)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ContextEditError("memory destination binding refused: " + str(exc)) from exc
    archive = path_for(selection["archive_dir"])
    if not archive.is_dir():
        raise ContextEditError("selected archive directory must already exist")
    entries = {item["id"]: item for item in packet["entries"]}
    seen, effects, statuses, required, custody = set(), [], [], {}, []
    originals, outputs, eligible_targets = {}, {}, set()
    for route in selection["routes"]:
        if (not isinstance(route, dict) or set(route) != {"id", "kind", "key", "file", "anchor"}
                or not isinstance(route["id"], str) or route["id"] not in entries or route["id"] in seen
                or not isinstance(route["kind"], str) or route["kind"] not in MEMORY_KINDS
                or not isinstance(route["key"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,127}", route["key"])
                or not isinstance(route["anchor"], str) or not route["anchor"]):
            raise ContextEditError("exact reviewed entry routing required")
        seen.add(route["id"])
        entry = entries[route["id"]]
        preserve = route["kind"] in MEMORY_PRESERVE
        if preserve and selection["family"] != "personal":
            raise ContextEditError("ALWAYS-PRESERVE records require the personal private root")
        if (selection["family"], selection["workspace"]) != (destination["family"], destination["workspace"]):
            raise ContextEditError("selected family/workspace differs from actual repository deletion unit")
        if (route["kind"] == "voice" and destination["home"] != "private-skill") or (
                destination["home"] == "private-skill" and route["kind"] != "voice"):
            raise ContextEditError("voice records require their canonical private-skill source")
        if destination["home"] == "lessons" and route["kind"] != "lesson":
            raise ContextEditError("lessons root accepts reviewed lesson routes only")
        if not preserve:
            if entry["scope"] == "unknown":
                statuses.append({"id": entry["id"], "status": "PENDING_OWNER"})
                continue
            if entry["scope"] == "workspace" or entry["workspace_hint"] is not None:
                if (selection["family"] != "workspace" or not entry["workspace_hint"]
                        or selection["workspace"] != entry["workspace_hint"]):
                    raise ContextEditError("workspace-private entry requires its explicit owning deletion unit")
            elif selection["family"] != "personal":
                raise ContextEditError("personal memory cannot be routed to an engagement deletion unit")
        if route["kind"] == "public-candidate":
            statuses.append({"id": entry["id"], "status": "PENDING_PUBLICATION_DECISION"})
            continue
        target = path_for(route["file"])
        if target.is_relative_to(archive):
            raise ContextEditError("canonical target cannot be the memory archive")
        if target not in originals:
            raw, identity = record_transaction._snapshot(target)
            originals[target] = (raw, identity)
            outputs[target] = raw.decode("utf-8")
        original = outputs[target]
        marker = "<!-- native-memory-key:" + route["key"] + " -->"
        end = "<!-- /native-memory-key:" + route["key"] + " -->"
        block = marker + "\n" + entry["text"] + "\n" + end + "\n"
        # A key identifies one canonical assertion. Different bytes remain a
        # decision; a harness cannot silently overwrite a canonical assertion.
        if marker in original:
            if original.count(marker) != 1 or block not in original:
                statuses.append({"id": entry["id"], "status": "PENDING_CONTRADICTION", "key": route["key"]})
                continue
            outcome = "DEDUPLICATED"
        elif "\n" + entry["text"] + "\n" in "\n" + original + "\n":
            # Exact complete text already exists in the selected canonical file.
            outcome = "DEDUPLICATED"
        else:
            if original.count(route["anchor"]) != 1:
                raise ContextEditError("canonical insertion anchor must match exactly once")
            outputs[target] = original.replace(route["anchor"], block + route["anchor"], 1)
            outcome = "INGESTED"
        eligible_targets.add(target)
        record = {"schema": 1, "harness": packet["harness"], "entry": entry,
                  "canonical_key": route["key"], "kind": route["kind"], "file": route["file"], "project": str(project)}
        archived = _memory_json(record).encode()
        archive_path = archive / (_memory_digest(archived) + ".json")
        if archive_path.exists() or archive_path.is_symlink():
            prior, identity = record_transaction._snapshot(archive_path)
            if prior != archived:
                raise ContextEditError("memory archive hash collision or changed custody")
            custody.append({"file": archive_path.relative_to(project).as_posix(), "expected": identity})
        else:
            # Archive creation precedes canonical editing in the transaction's
            # ordered effects. Interrupted creation retains recoverable custody.
            effects.append({"file": archive_path.relative_to(project).as_posix(),
                            "create": {"text": archived.decode(), "mode": 0o600}})
        required[str(archive_path)] = _memory_digest(archived)
        statuses.append({"id": entry["id"], "sha256": entry["sha256"], "status": outcome})
    for target, (raw, identity) in originals.items():
        if target not in eligible_targets:
            continue
        after = outputs[target].encode()
        if after != raw:
            effects.append({"file": target.relative_to(project).as_posix(),
                            "expected_sha256": identity["sha256"],
                            "edits": [{"op": "replace", "anchor": raw.decode(), "replacement": after.decode()}]})
        else:
            custody.append({"file": target.relative_to(project).as_posix(), "expected": identity})
        required[str(target)] = _memory_digest(after)
    # Reobserve the selected store/board immediately before PM admission. The
    # native consumer must do the same before its own export/clear operation.
    again = _memory_preflight(packet, store, board, machine)
    if again["status"] == "PENDING_ACTIVE_HARNESS":
        return again
    if record_transaction.memory_record_home(project) != destination:
        raise ContextEditError("memory destination changed before transaction")
    # Re-admit even a deduplicated no-effect observation. A prior local receipt
    # cannot substitute for this native seat's current exact claims.
    record_transaction._authority(project, board, native_payload,
        [archive, *originals.keys(), project / record_transaction.STORE], memory_home=destination)
    transaction = None
    if effects:
        transaction = apply_transaction(project, effects, board=board, native_payload=native_payload,
                                        dry_run=dry_run, source_custody=custody,
                                        memory_home=destination)
    statuses.extend({"id": item["id"], "status": "PENDING_ROUTING"}
                    for item in packet["entries"] if item["id"] not in seen)
    return {"schema": 1, "status": "DRY_RUN" if dry_run else "LOCAL_INGESTION",
            "harness": packet["harness"], "store": packet["store"], "project": str(project),
            "packet_sha256": _memory_digest(_memory_json(packet).encode()),
            "selection_sha256": _memory_digest(_memory_json(selection).encode()),
            "entries": statuses, "required_files": required,
            "transaction": transaction, "native_export_verified": False,
            "native_clear": "NOT_EXECUTED", "pending": True}


def memory_clear_request(packet: dict, receipt: dict, *, store: Path, board: Path,
                         machine: str, guard_root: Path, native: str,
                         publication_sha256: str) -> dict:
    """Prepare exact eligible hashes; NEVER performs or attests native clearing.

    A publication observation proves only its existing owner's past exact-byte
    delivery. Current native export/clear capability and native operation receipt
    remain separate requirements. This source ships no deletion adapter.
    """
    probe = _memory_preflight(packet, store, board, machine)
    if probe["status"] == "PENDING_ACTIVE_HARNESS":
        return probe
    if (not isinstance(receipt, dict) or receipt.get("status") != "LOCAL_INGESTION"
            or receipt.get("packet_sha256") != _memory_digest(_memory_json(packet).encode())
            or receipt.get("store") != packet["store"] or receipt.get("harness") != packet["harness"]
            or not isinstance(receipt.get("required_files"), dict) or not receipt["required_files"]
            or len(receipt["required_files"]) > MEMORY_MAX_ENTRIES * 2
            or not isinstance(publication_sha256, str) or not re.fullmatch("[a-f0-9]{64}", publication_sha256)):

        raise ContextEditError("exact local ingestion receipt required")
    _, publication = _memory_owners()
    proof = publication.observe(guard_root, native, required_files=receipt.get("required_files"),
                                expected_receipt_sha256=publication_sha256)
    if proof["status"] != "VERIFIED_REMOTE_READY":
        return {"status": "PENDING_PUBLICATION", "pending": True, "native_clear": "NOT_EXECUTED"}
    # Read each member once under the same finite aggregate publication bound.
    # Neither the number of entries nor archive membership multiplies I/O.
    import time
    deadline = time.monotonic() + 10
    eligible, cache, archives = [], {}, []
    workers, _ = _memory_owners()
    remaining = 32 * 1024 * 1024
    for filename, digest in receipt["required_files"].items():
        if time.monotonic() >= deadline:
            raise ContextEditError("memory eligibility time bound exceeded")
        path = Path(filename)
        raw = workers.read_regular(path, min(8 * 1024 * 1024, remaining))
        remaining -= len(raw)
        if _memory_digest(raw) != digest:
            raise ContextEditError("ingested bytes changed after publication observation")
        cache[filename] = raw
        if path.suffix == ".json":
            data = json.loads(raw, object_pairs_hook=_unique_object)
            if not isinstance(data, dict):
                raise ContextEditError("invalid archived memory record")
            archives.append(data)
    for entry in packet["entries"]:
        if time.monotonic() >= deadline:
            raise ContextEditError("memory eligibility time bound exceeded")
        for data in archives:
            if data.get("entry") != entry or data.get("harness") != packet["harness"]:
                continue
            if data.get("project") != receipt.get("project") or not isinstance(data.get("file"), str):
                raise ContextEditError("archive canonical routing binding is missing")
            project = record_transaction._path(Path(data["project"]))
            canonical = record_transaction._path(project / data["file"], project)
            if str(canonical) not in cache or canonical.suffix == ".json":
                raise ContextEditError("archive canonical file is not covered")
            if "\n" + entry["text"] + "\n" in "\n" + cache[str(canonical)].decode("utf-8") + "\n":
                eligible.append({"id": entry["id"], "sha256": entry["sha256"]})
                break
    final_probe = _memory_preflight(packet, store, board, machine)
    if final_probe["status"] == "PENDING_ACTIVE_HARNESS":
        return final_probe
    # Export/clear support is deliberately not guessed from binaries or store
    # paths. In particular, Codex note-only update permission is not clear power.
    return {"status": "PENDING_NATIVE_CAPABILITY", "pending": True,
            "harness": packet["harness"], "store": packet["store"],
            "eligible": eligible, "publication_sha256": proof["receipt_sha256"],
            "native_clear": "NOT_EXECUTED", "dispatch": None,
            "reason": "Own-harness export provenance and supported hash-CAS clear action require native qualification; raw-file deletion is prohibited."}


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContextEditError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _operand(args: argparse.Namespace, name: str) -> str:
    source = getattr(args, name + "_file", None)
    return _read(source) if source is not None else _value(getattr(args, name))


def _operand_flags(parser: argparse.ArgumentParser, name: str) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--" + name)
    group.add_argument("--" + name + "-file", type=Path,
                       help="read exact UTF-8 text from a regular file")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", required=True, type=Path)
    common.add_argument("--max-lines", type=int, default=None)
    common.add_argument("--dry-run", action="store_true")
    common.add_argument(
        "--allow-header-lag",
        action="store_true",
        help="record an explicit override instead of refusing an edit that "
        "leaves Phase ahead of Last session",
    )
    common.add_argument(
        "--allow-stale-body",
        action="store_true",
        help="record an explicit override instead of refusing a header "
        "advance that leaves a *State as of:* marker behind",
    )
    common.add_argument(
        "--state-reviewed",
        action="store_true",
        help="record that a section was re-read and still holds, when "
        "advancing its *State as of:* marker without changing its prose",
    )

    replace = sub.add_parser("replace", parents=[common])
    _operand_flags(replace, "anchor")
    _operand_flags(replace, "replacement")
    replace.add_argument("--count", type=int, default=1)

    field = sub.add_parser("set-field", parents=[common])
    field.add_argument("--field", required=True)
    field.add_argument("--value", required=True)

    insert = sub.add_parser("insert-before", parents=[common])
    _operand_flags(insert, "anchor")
    _operand_flags(insert, "text")

    delete = sub.add_parser("delete-line", parents=[common])
    _operand_flags(delete, "anchor")

    batch = sub.add_parser("apply", parents=[common])
    batch.add_argument("--edits", required=True, type=Path, help="JSON array of ordered single-file edits")

    for command in ("apply-transaction", "recover-transaction"):
        transaction = sub.add_parser(command)
        transaction.add_argument("--project", type=Path, required=True)
        transaction.add_argument("--board", type=Path, required=True)
        transaction.add_argument("--native-payload", type=Path, required=True,
                                 help="native event evidence; PM verifies its transcript/seat binding")
        if command == "apply-transaction":
            transaction.add_argument("--files", type=Path, required=True,
                                     help="JSON array of project-relative file/edit objects")
            transaction.add_argument("--dry-run", action="store_true")
    for command in ("review-succession", "apply-succession"):
        succession = sub.add_parser(command)
        succession.add_argument("--project", type=Path, required=True)
        succession.add_argument("--request", type=Path, required=True)
        if command == "apply-succession":
            succession.add_argument("--board", type=Path, required=True)
            succession.add_argument("--native-payload", type=Path, required=True)
            succession.add_argument("--dry-run", action="store_true")
    registry = sub.add_parser("registry-patch")
    registry.add_argument("--project", type=Path, required=True)
    registry.add_argument("--entry", required=True)
    registry.add_argument("--fields", type=Path, required=True)
    registry.add_argument("--expected-sha256", required=True)
    registry.add_argument("--board", type=Path, required=True)
    registry.add_argument("--native-payload", type=Path, required=True)
    registry.add_argument("--dry-run", action="store_true")
    for command in ("memory-probe", "memory-ingest", "memory-clear-plan"):
        memory = sub.add_parser(command)
        memory.add_argument("--store", type=Path, required=True)
        memory.add_argument("--board", type=Path, required=True)
        memory.add_argument("--machine", required=True)
        if command == "memory-probe":
            memory.add_argument("--harness", choices=["claude", "codex", "muse"], required=True)
            memory.add_argument("--previous", type=Path)
        else:
            memory.add_argument("--packet", type=Path, required=True)
        if command == "memory-ingest":
            memory.add_argument("--project", type=Path, required=True)
            memory.add_argument("--selection", type=Path, required=True)
            memory.add_argument("--native-payload", type=Path, required=True)
            memory.add_argument("--dry-run", action="store_true")
        if command == "memory-clear-plan":
            memory.add_argument("--receipt", type=Path, required=True)
            memory.add_argument("--guard-root", type=Path, required=True)
            memory.add_argument("--native", required=True)
            memory.add_argument("--publication-sha256", required=True)
    args = parser.parse_args(argv)
    if sum(getattr(args, name, None) == "-" for name in ("anchor", "replacement", "text", "value")) > 1:
        parser.error("stdin may supply only one operand; use the file flags for other operands")

    try:
        if args.command == "registry-patch":
            result = patch_registry(args.project, args.entry,
                record_transaction.read_request(args.fields), args.expected_sha256,
                board=args.board, native_payload=record_transaction.read_request(args.native_payload),
                dry_run=args.dry_run)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command.startswith("memory-"):
            if args.command == "memory-probe":
                workers, _ = _memory_owners()
                result = workers.memory_probe(args.store, harness=args.harness, machine=args.machine,
                                              board=args.board, previous=record_transaction.read_request(args.previous)
                                              if args.previous else None)
            else:
                packet = record_transaction.read_request(args.packet)
                if args.command == "memory-ingest":
                    result = memory_ingest(args.project, packet, record_transaction.read_request(args.selection),
                                           store=args.store, board=args.board, machine=args.machine,
                                           native_payload=record_transaction.read_request(args.native_payload),
                                           dry_run=args.dry_run)
                else:
                    result = memory_clear_request(packet, record_transaction.read_request(args.receipt),
                                                  store=args.store, board=args.board, machine=args.machine,
                                                  guard_root=args.guard_root, native=args.native,
                                                  publication_sha256=args.publication_sha256)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command in {"review-succession", "apply-succession"}:
            import record_succession
            request = record_transaction.read_request(args.request)
            if args.command == "review-succession":
                result = record_succession.review(args.project, request)
            else:
                payload = record_transaction.read_request(args.native_payload)
                result = record_succession.apply(args.project, request, board=args.board,
                                                 native_payload=payload, dry_run=args.dry_run)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command in {"apply-transaction", "recover-transaction"}:
            payload = record_transaction.read_request(args.native_payload)
            if args.command == "apply-transaction":
                files = record_transaction.read_request(args.files)
                result = apply_transaction(args.project, files, board=args.board,
                                           native_payload=payload, dry_run=args.dry_run)
            else:
                result = recover_transaction(args.project, board=args.board, native_payload=payload)
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "apply":
            edits = json.loads(_read(args.edits), object_pairs_hook=_unique_object)
            result = apply_edits(args.file, edits, max_lines=args.max_lines, dry_run=args.dry_run,
                                 allow_header_lag=args.allow_header_lag,
                                 allow_stale_body=args.allow_stale_body, state_reviewed=args.state_reviewed)
        elif args.command == "insert-before":
            result = insert_before(
                args.file,
                anchor=_operand(args, "anchor"),
                text=_operand(args, "text"),
                max_lines=args.max_lines,
                dry_run=args.dry_run,
                allow_header_lag=args.allow_header_lag,
                allow_stale_body=args.allow_stale_body,
                state_reviewed=args.state_reviewed,
            )
        elif args.command == "delete-line":
            result = delete_line(
                args.file, anchor=_operand(args, "anchor"), max_lines=args.max_lines,
                dry_run=args.dry_run, allow_header_lag=args.allow_header_lag,
                allow_stale_body=args.allow_stale_body, state_reviewed=args.state_reviewed,
            )
        elif args.command == "replace":
            result = replace_once(
                args.file,
                anchor=_operand(args, "anchor"),
                replacement=_operand(args, "replacement"),
                count=args.count,
                max_lines=args.max_lines,
                dry_run=args.dry_run,
                allow_header_lag=args.allow_header_lag,
                allow_stale_body=args.allow_stale_body,
                state_reviewed=args.state_reviewed,
            )
        else:
            result = set_field(
                args.file,
                field=args.field,
                value=_value(args.value),
                max_lines=args.max_lines,
                dry_run=args.dry_run,
                allow_header_lag=args.allow_header_lag,
                allow_stale_body=args.allow_stale_body,
                state_reviewed=args.state_reviewed,
            )
    except (ContextEditError, record_transaction.RecordTransactionError, OSError, ValueError) as exc:
        print(f"context-edit refused: {exc}", file=sys.stderr)
        return 1

    verb = "would change" if result["dry_run"] else "changed"
    suffix = f" [{result['note']}]" if result.get("note") else ""
    print(
        f"{verb} {result['path']}: {result['replacements']} replacement(s), "
        f"{result['lines']} lines{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
