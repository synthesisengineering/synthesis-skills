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

Exit codes: 0 changed, 1 refused (nothing written), 2 usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

import context_currency


class ContextEditError(Exception):
    """A durable-context edit was refused. Nothing was written."""


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
    leading = [(f, p, l) for f, p, l in after if p > l]
    trailing = [(f, p, l) for f, p, l in after if l > p]
    notes: list[str] = []
    if trailing:
        notes.append(
            "note: Last session now leads Phase ("
            + "; ".join(f"{f} {l} vs {p}" for f, p, l in trailing)
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
    if path.is_symlink():
        raise ContextEditError(f"refusing to edit a symlink: {path}")
    if not path.is_file():
        raise ContextEditError(f"not a file: {path}")
    return path.read_text(encoding="utf-8")


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, then rename.

    A durable record must never be left half-written by an interrupted edit.
    """
    directory = path.parent
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, delete=False
    )
    try:
        with handle as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def apply_replacement(
    text: str,
    anchor: str,
    replacement: str,
    *,
    count: int = 1,
) -> str:
    """Return edited text, or raise ContextEditError explaining the refusal."""
    if not anchor:
        raise ContextEditError("anchor must not be empty")
    if count < 1:
        raise ContextEditError(f"count must be at least 1, got {count}")

    found = text.count(anchor)
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

    edited = text.replace(anchor, replacement, count)
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
) -> dict:
    """Apply one verified replacement to a durable context file."""
    path = Path(path)
    original = _read(path)
    edited = apply_replacement(original, anchor, replacement, count=count)
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


FIELD = "^\\*\\*{name}:\\*\\*[^\\n]*"


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
    )


def _value(raw: str) -> str:
    return sys.stdin.read() if raw == "-" else raw


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
    replace.add_argument("--anchor", required=True)
    replace.add_argument("--replacement", required=True)
    replace.add_argument("--count", type=int, default=1)

    field = sub.add_parser("set-field", parents=[common])
    field.add_argument("--field", required=True)
    field.add_argument("--value", required=True)

    insert = sub.add_parser("insert-before", parents=[common])
    insert.add_argument("--anchor", required=True)
    insert.add_argument("--text", required=True)

    args = parser.parse_args(argv)

    try:
        if args.command == "insert-before":
            result = insert_before(
                args.file,
                anchor=_value(args.anchor),
                text=_value(args.text),
                max_lines=args.max_lines,
                dry_run=args.dry_run,
                allow_header_lag=args.allow_header_lag,
                allow_stale_body=args.allow_stale_body,
                state_reviewed=args.state_reviewed,
            )
        elif args.command == "replace":
            result = replace_once(
                args.file,
                anchor=_value(args.anchor),
                replacement=_value(args.replacement),
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
    except ContextEditError as exc:
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
