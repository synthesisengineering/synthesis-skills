#!/usr/bin/env python3
"""project_format.py — versioned synthesis project formats.

Detects a project's on-disk format version and pull-migrates v1
(unmarked CONTEXT.md / REFERENCE.md / sessions/) to v2 (marker +
machine-readable state + sessions index). Migration is strictly
additive — no byte is modified or deleted — idempotent, and verified
by re-reading everything written.

Usage:
    project_format.py detect <project-dir>
    project_format.py migrate [--check] [--goal TEXT] [--status TEXT] <project-dir>
    project_format.py archive [--older-than-days N] [--check] <project-dir>

Exit 0 with a JSON report on stdout. Exit 2 on unreadable input.
The full contract lives in the Phase F design doc and the
synthesis-project-management SKILL.md format section.
"""

from __future__ import annotations


import argparse
import hashlib
import os
import stat
import tempfile
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_CONTEXT_SCRIPTS = Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle" / "scripts"
if str(_CONTEXT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CONTEXT_SCRIPTS))
import record_transaction  # noqa: E402 - sibling owner path

try:
    import yaml
except ImportError:
    sys.exit("project_format requires PyYAML (pip install pyyaml)")

ENGINE_VERSION = "1.0.0"
CURRENT_FORMAT = 2
MARKER_NAME = ".synthesis-project.yaml"
# Deliberately NOT CURRENT_STATE.json: that file is owned by project_state.py
# (operational handoff shape). The resume state is a separate concern.
STATE_NAME = "RESUME_STATE.json"
INDEX_NAME = "INDEX.md"
# Session-archive retention: a year of live history unless told otherwise.
DEFAULT_RETENTION_DAYS = 365
STATE_SCHEMA = 1

V1_LAYOUT = ("CONTEXT.md", "REFERENCE.md", "sessions")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)(?:\s+#+)?\s*$")
LOOP_RE = re.compile(r"\b(TODO|FIXME|XXX|OPEN|TBD)\b[:\s]+(.{0,120})", re.IGNORECASE)


def detect(project_dir: Path) -> str:
    """Observe a bounded, unambiguous marker; never follow special-file input."""
    try:
        project_dir = record_transaction._path(project_dir)
        if not project_dir.is_dir():
            return 'missing'
        marker = record_transaction._path(project_dir / MARKER_NAME, project_dir)
        if marker.exists():
            raw, _ = record_transaction._snapshot(marker)
            class Strict(yaml.SafeLoader):
                pass
            def pairs(loader, node, deep=False):
                return record_transaction._unique([
                    (loader.construct_object(k, deep=True), loader.construct_object(v, deep=True))
                    for k, v in node.value])
            Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, pairs)
            data = yaml.load(raw, Loader=Strict)
            if not isinstance(data, dict) or type(data.get('format_version')) is not int:
                return 'unknown'
            return 'v2' if data['format_version'] == CURRENT_FORMAT else 'unknown'
        present = [(project_dir / name).exists() for name in V1_LAYOUT]
        return 'v1' if all(present) else 'partial'
    except (OSError, ValueError, RuntimeError, yaml.YAMLError):
        return 'unknown'


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _newest_period_file(project_dir: Path) -> Path | None:
    sessions = project_dir / "sessions"
    if not sessions.is_dir():
        return None
    files = sorted(
        p for p in sessions.glob("*.md") if p.name != INDEX_NAME
    )
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _source_data(path: Path) -> bytes:
    """Bound one regular-file read so the provenance hashes the parsed bytes."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected regular source, not symlink: {path}")
    with path.open("rb") as stream:
        data = stream.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError(f"project prose exceeds 16 MiB read bound: {path}")
    return data


def _visible_lines(text: str):
    """Yield source line numbers outside fenced code examples."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                # Backtick info strings cannot themselves contain a backtick.
                if token[0] != "`" or "`" not in line[marker.end():]:
                    fence = token
                    continue
            elif (token[0] == fence[0] and len(token) >= len(fence)
                  and not line[marker.end():].strip()):
                fence = None
                continue
        if fence is None:
            yield number, line



def _source_lines(path: Path):
    return _visible_lines(_source_data(path).decode("utf-8"))


def _skeleton_loops(newest: Path | None, project_dir: Path | None = None) -> list[dict]:
    """Candidate obligations retain provenance and never imply verified truth."""
    sources = []
    if newest is not None:
        sources.append((newest, "session-marker"))
    if project_dir is not None and (project_dir / "CONTEXT.md").exists():
        sources.append((project_dir / "CONTEXT.md", "context-checkbox"))
    loops, occurrences = [], {}
    for path, kind in sources:
        source_data = _source_data(path)
        source_lines = _visible_lines(source_data.decode("utf-8"))
        source_digest = hashlib.sha256(source_data).hexdigest()
        for number, line in source_lines:
            match = (re.match(r"^\s*[-*+]\s+\[ \]\s+(.+?)\s*$", line)
                     if kind == "context-checkbox" else LOOP_RE.search(line))
            if not match:
                continue
            text = match.group(1 if kind == "context-checkbox" else 2).strip()
            relative = str(path.relative_to(project_dir)) if project_dir else f"sessions/{path.name}"
            key = relative + "\0" + kind + "\0" + text
            occurrences[key] = occurrences.get(key, 0) + 1
            # Keep separate source occurrences, while edits before a task do
            # not create new candidates merely by moving its line number.
            occurrence = occurrences[key]
            identity_input = key if occurrence == 1 else key + f"\0occurrence={occurrence}"
            identity = hashlib.sha256(identity_input.encode()).hexdigest()[:24]
            loops.append({"id": "candidate-" + identity, "text": text,
                          "owner": "unassigned", "since": newest.stem if newest else None,
                          "unverified": True,
                          "source": {"path": relative, "line": number, "kind": kind,
                                     "sha256": source_digest}})
            if len(loops) > 1000:
                raise ValueError("more than 1000 resume candidates; no candidates were written")
    return loops


def _index_period_block(path: Path, prefix: str = "") -> list[str]:
    headings = [match.group(1).strip() for _, line in _source_lines(path)
                if (match := HEADING_RE.match(line))]
    dated = [title for title in headings if re.search(r"\b\d{4}-\d{2}-\d{2}\b", title)]
    # A dated log has entry headings and interior prose headings. Old undated
    # logs still get a complete heading index, without pretending a cap is the count.
    entries = dated if dated else headings
    lines = [f"## {prefix}{path.stem} ({len(entries)} sessions)", ""]
    for heading in entries[:50]:
        lines.append(f"- {heading[:100]}")
    if len(entries) > 50:
        lines.append(f"- … {len(entries) - 50} more entries in {prefix}{path.name}")
    lines.append("")
    return lines


def _sessions_index(project_dir: Path) -> str:
    sessions = project_dir / "sessions"
    lines = ["<!-- generated by project_format.py — do not hand-edit -->", ""]
    lines.append("# Sessions index")
    lines.append("")
    if sessions.is_dir():
        for path in sorted(sessions.glob("*.md")):
            if path.name == INDEX_NAME:
                continue
            lines.extend(_index_period_block(path))
        archived = sorted((sessions / "archive").glob("*.md")) if (sessions / "archive").is_dir() else []
        if archived:
            lines.append("## Archived")
            lines.append("")
            for path in archived:
                lines.extend(_index_period_block(path, prefix="archive/"))
    return "\n".join(lines).rstrip() + "\n"


def build_marker(project_id: str, migrated_from: int) -> dict:
    return {
        "format_version": CURRENT_FORMAT,
        "id": project_id,
        "created": None,
        "migrated_from": migrated_from,
        "migrated_at": _utcnow(),
    }


def build_state_skeleton(
    project_dir: Path, goal: str = "", status: str = "unknown"
) -> dict:
    newest = _newest_period_file(project_dir)
    return {
        "schema": STATE_SCHEMA,
        "skeleton": True,
        "goal": goal,
        "status": status,
        "open_loops": _skeleton_loops(newest, project_dir),
        "last_session": newest.stem if newest else None,
        "last_brief": "",
        "updated_at": _utcnow(),
    }


def validate_state(data: object) -> list[str]:
    """Return human-readable schema violations (empty means valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["state root must be an object"]
    if data.get("schema") != STATE_SCHEMA:
        errors.append(f"schema must be {STATE_SCHEMA}")
    if not isinstance(data.get("goal"), str):
        errors.append("goal must be a string")
    if not isinstance(data.get("status"), str):
        errors.append("status must be a string")
    loops = data.get("open_loops", [])
    if not isinstance(loops, list):
        errors.append("open_loops must be a list")
    else:
        for i, loop in enumerate(loops):
            if not isinstance(loop, dict):
                errors.append(f"open_loops[{i}] must be an object")
                continue
            for key in ("id", "text", "owner"):
                if not isinstance(loop.get(key), str):
                    errors.append(f"open_loops[{i}].{key} must be a string")
    return errors


@record_transaction.guarded("project_dir", error=ValueError, exclusive=True)
def migrate(
    project_dir: Path,
    goal: str = "",
    status: str = "unknown",
    apply: bool = False,
) -> dict:
    """Check (default) or apply the v1 -> v2 migration. Returns a report."""
    found = detect(project_dir)
    if found == "missing":
        raise FileNotFoundError(f"no project directory: {project_dir}")
    if found == "v2":
        return {"from": 2, "to": 2, "noop": True, "verified": True, "added": []}
    if found != "v1":
        raise ValueError(f"cannot migrate a '{found}' project; need v1")
    added = [MARKER_NAME, STATE_NAME, f"sessions/{INDEX_NAME}"]
    if not apply:
        return {"from": 1, "to": 2, "noop": False, "verified": False, "added": added}
    # Additive means additive: never overwrite a file the project already
    # has. Kept files are validated instead of replaced.
    kept: list[str] = []
    if not (project_dir / STATE_NAME).exists():
        state = build_state_skeleton(project_dir, goal=goal, status=status)
        (project_dir / STATE_NAME).write_text(
            json.dumps(state, indent=2) + "\n", encoding="utf-8"
        )
    else:
        kept.append(STATE_NAME)
    if not (project_dir / "sessions" / INDEX_NAME).exists():
        (project_dir / "sessions" / INDEX_NAME).write_text(
            _sessions_index(project_dir), encoding="utf-8"
        )
    else:
        kept.append(f"sessions/{INDEX_NAME}")
    marker = build_marker(project_dir.name, 1)
    (project_dir / MARKER_NAME).write_text(
        yaml.safe_dump(marker, sort_keys=False), encoding="utf-8"
    )
    # Verify by re-reading everything written.
    errors: list[str] = []
    if detect(project_dir) != "v2":
        errors.append("marker did not re-read as v2")
    try:
        state_back = json.loads((project_dir / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"state did not re-read: {exc}")
    else:
        errors.extend(validate_state(state_back))
    if errors:
        # Roll back the marker so a failed migration reads as v1 again
        # and the next run retries instead of nooping on a lie. Added
        # state/index files stay (they are valid on their own); only the
        # version claim is withdrawn.
        try:
            (project_dir / MARKER_NAME).unlink()
        except OSError:
            errors.append("rollback failed: marker could not be removed")
        return {
            "from": 1, "to": 2, "noop": False, "verified": False,
            "added": added, "kept": kept, "errors": errors,
        }
    return {
        "from": 1, "to": 2, "noop": False, "verified": True,
        "added": added, "kept": kept,
    }


PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


def _period_cutoff(older_than_days: int) -> tuple[int, int]:
    from datetime import date, timedelta

    cutoff = date.today() - timedelta(days=older_than_days)
    return cutoff.year, cutoff.month


@record_transaction.guarded("project_dir", error=ValueError, exclusive=True)
def archive(
    project_dir: Path, older_than_days: int, apply: bool = False
) -> dict:
    """Move old session periods to sessions/archive/ (v2 only).

    Never moves the newest period file. In check mode (default) reports
    what would move; with apply=True moves and regenerates INDEX.md.
    """
    if older_than_days < 0:
        raise ValueError("older-than-days must be non-negative")
    found = detect(project_dir)
    if found != "v2":
        raise ValueError(f"archive requires a v2 project (found '{found}'); migrate first")
    sessions = project_dir / "sessions"
    periods = sorted(
        p for p in sessions.glob("*.md")
        if p.name != INDEX_NAME and PERIOD_RE.match(p.stem)
    )
    if not periods:
        return {"moved": [], "kept": [], "index_updated": False}
    newest = max(periods, key=lambda p: p.stem)
    cutoff = _period_cutoff(older_than_days)
    moved = [
        p.name for p in periods
        if p != newest and (int(p.stem[:4]), int(p.stem[5:7])) < cutoff
    ]
    kept = [p.name for p in periods if p.name not in moved]
    if not apply or not moved:
        return {"moved": moved, "kept": kept, "index_updated": False}
    archive_dir = sessions / "archive"
    archive_dir.mkdir(exist_ok=True)
    for name in moved:
        (sessions / name).rename(archive_dir / name)
    (sessions / INDEX_NAME).write_text(_sessions_index(project_dir), encoding="utf-8")
    return {"moved": moved, "kept": kept, "index_updated": True}



def _refresh_path(project_dir: Path, path: Path, *, required: bool = True) -> None:
    relative = path.relative_to(project_dir)
    current = project_dir
    if current.is_symlink():
        raise ValueError(f"symlink project is not a refresh target: {current}")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink refresh path refused: {current}")
    if required and not path.is_file():
        raise ValueError(f"refresh requires a regular file: {path}")


def _replace_generated(path: Path, content: str) -> None:
    """One file is atomic; the refresh pair is recoverable by rerunning."""
    handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False)
    try:
        with handle as stream:
            stream.write(content)
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
    finally:
        Path(handle.name).unlink(missing_ok=True)


def _unique_state_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate resume-state JSON field: {key}")
        result[key] = value
    return result


@record_transaction.guarded("project_dir", error=ValueError, exclusive=True)
def refresh(project_dir: Path, apply: bool = False) -> dict:
    """Refresh existing v2 index/state without overwriting curated judgments.

    All inputs are validated before any write. Output files are replaced one
    at a time, not as a filesystem transaction. If interrupted, rerun refresh;
    deterministic candidates and byte comparisons converge without duplicates.
    Use the normal project-records claim before applying.
    """
    project_dir = Path(project_dir)
    for name in (MARKER_NAME, STATE_NAME, "CONTEXT.md", f"sessions/{INDEX_NAME}"):
        _refresh_path(project_dir, project_dir / name)
    if detect(project_dir) != "v2":
        raise ValueError("refresh requires an existing v2 project; migrate first")
    for path in (project_dir / "sessions").glob("*.md"):
        _refresh_path(project_dir, path)
    archive_dir = project_dir / "sessions/archive"
    _refresh_path(project_dir, archive_dir, required=False)
    if archive_dir.exists():
        for path in archive_dir.glob("*.md"):
            _refresh_path(project_dir, path)
    state_path, index_path = project_dir / STATE_NAME, project_dir / "sessions" / INDEX_NAME
    original_state, original_index = state_path.read_text(encoding="utf-8"), index_path.read_text(encoding="utf-8")
    state = json.loads(original_state, object_pairs_hook=_unique_state_object)
    errors = validate_state(state)
    if errors:
        raise ValueError("invalid resume state: " + "; ".join(errors))
    if not original_index.startswith("<!-- generated by project_format.py"):
        raise ValueError("existing index is not generated by this owner; preserve and reconcile it")
    revised = json.loads(original_state, object_pairs_hook=_unique_state_object)
    revised.setdefault("open_loops", [])
    known = {loop["id"] for loop in revised["open_loops"]}
    import record_succession
    material = record_succession.material_context(project_dir)
    # Only a complete current observation may suppress rediscovery. Conflicts,
    # changed sources and incomplete scans retain visible unreviewed candidates.
    terminal = ([item for item in material["active_items"] if item["status"] in {"cancelled", "retired"}]
                if not record_succession.material_needs_reconciliation(material) else [])
    newest = _newest_period_file(project_dir)
    added = []
    for loop in _skeleton_loops(newest, project_dir):
        terminal_match = any(ref["path"] == loop["source"]["path"] and ref.get("anchor") == loop["text"]
                             and ref['sha256'] == loop['source']['sha256']
                             for item in terminal for ref in record_succession._material_refs(item))
        if loop["id"] not in known and not terminal_match:
            revised["open_loops"].append(loop)
            known.add(loop["id"])
            added.append(loop["id"])
    revised["last_session"] = newest.stem if newest else None
    # Keep goal/status/brief, reviewed loops, unknown fields and timestamps
    # intact when no semantic state changed. Absence never closes a loop.
    if revised != state:
        revised["updated_at"] = _utcnow()
        state_text = json.dumps(revised, indent=2) + "\n"
    else:
        state_text = original_state
    index_text = _sessions_index(project_dir)
    writes = [(index_path, original_index, index_text), (state_path, original_state, state_text)]
    changed = [str(path.relative_to(project_dir)) for path, old, new in writes if old != new]
    if apply:
        # Detect concurrent changes before the first replacement; this does
        # not substitute for the normal coordination owner or imply a CAS.
        if any(path.read_text(encoding="utf-8") != old for path, old, _ in writes):
            raise ValueError("refresh inputs changed during preflight")
        for path, old, new in writes:
            if old != new:
                _refresh_path(project_dir, path)
                _replace_generated(path, new)
        if any(path.read_text(encoding="utf-8") != new for path, _, new in writes):
            raise ValueError("refresh verification failed; rerun after reconciling ownership")
    return {"material_context": material, "changed": changed, "added_candidates": added, "verified": apply,
            "dry_run": not apply, "atomicity": "per-file; interrupted refresh is rerunnable"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect and migrate project formats.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_detect = sub.add_parser("detect", help="print the format version")
    p_detect.add_argument("project_dir")
    p_migrate = sub.add_parser("migrate", help="migrate v1 to v2")
    p_migrate.add_argument("project_dir")
    p_migrate.add_argument("--check", action="store_true", help="report only; write nothing")
    p_migrate.add_argument("--goal", default="")
    p_migrate.add_argument("--status", default="unknown")
    p_archive = sub.add_parser("archive", help="archive old session periods (v2 only)")
    p_archive.add_argument("project_dir")
    p_archive.add_argument(
        "--older-than-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"archive periods older than this many days (default: {DEFAULT_RETENTION_DAYS})",
    )
    p_archive.add_argument("--check", action="store_true", help="report only; write nothing")
    p_refresh = sub.add_parser("refresh", help="refresh generated index and resume candidates (v2 only)")
    p_refresh.add_argument("project_dir")
    p_refresh.add_argument("--check", action="store_true", help="report only; write nothing")
    args = parser.parse_args(argv)
    try:
        if args.command == "detect":
            print(json.dumps({"format": detect(Path(args.project_dir))}))
        elif args.command == "refresh":
            print(json.dumps(refresh(Path(args.project_dir), apply=not args.check), indent=2))
        elif args.command == "archive":
            report = archive(
                Path(args.project_dir),
                older_than_days=args.older_than_days,
                apply=not args.check,
            )
            print(json.dumps(report, indent=2))
            if report.get("errors"):
                return 1
        else:
            report = migrate(
                Path(args.project_dir),
                goal=args.goal,
                status=args.status,
                apply=not args.check,
            )
            print(json.dumps(report, indent=2))
            if report.get("errors"):
                return 1
    except (OSError, ValueError) as exc:
        print(f"project_format: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
