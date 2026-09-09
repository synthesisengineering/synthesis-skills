"""Resolve report destinations from explicit registry links; never project authority.

Only the registry's block project mappings and scalar routing fields are read.
No prose, active pointer, board title, or client memory supplies a relationship.
The parser is deliberately stdlib-only and refuses unsupported routing syntax.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import stat
import subprocess

PROJECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z")
FIELD = re.compile(r'''(?:'([^']+)'|"([^"]+)"|([^\s:]+)):\s*(.*)\Z''')
ROUTING_FIELDS = {"id", "status", "superseded_by"}
MAX_REGISTRY_BYTES = 4 * 1024 * 1024


def error(detail: str) -> ValueError:
    return ValueError("report recipient " + detail)


def scalar(raw: str) -> str:
    # Routing IDs/statuses are literal scalars, not YAML aliases, lists, tags,
    # block strings, escapes, merges, or expressions.
    match = re.fullmatch(r'''(?:'([A-Za-z0-9_.-]+)'|"([A-Za-z0-9_.-]+)"|([A-Za-z0-9_.-]+))(?:\s+#.*)?\s*''', raw)
    if not match:
        raise error("registry routing field is not a single literal scalar")
    value = next(value for value in match.groups() if value is not None)
    if not PROJECT_ID.fullmatch(value):
        raise error("registry routing scalar is invalid")
    return value


def quote_open(text: str, quote: str, *, continuation: bool = False) -> bool:
    """Track quoted narrative so its continuation cannot become a routing key."""
    offset = 0 if continuation else 1
    while offset < len(text):
        character = text[offset]
        if quote == '"' and character == "\\":
            offset += 2
            continue
        if character == quote:
            if quote == "'" and text[offset:offset + 2] == "''":
                offset += 2
                continue
            remainder = text[offset + 1:].strip()
            if remainder and not remainder.startswith("#"):
                raise error("registry quoted scalar has trailing syntax")
            return False
        offset += 1
    return True


def registry_entries(text: str) -> dict[str, dict[str, str]]:
    """Read unambiguous block mappings under projects:, or a bare project list.

    Other registry sections and nested metadata are not project entries. Every
    entry starts with id; routing keys must be direct mapping fields. Full YAML
    generality is unnecessary for this contract and is never guessed at.
    """
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if re.match(r"^projects\s*:", line)]
    if headers:
        if len(headers) != 1 or not re.fullmatch(r"projects:\s*(?:#.*)?", lines[headers[0]]):
            raise error("registry projects section is ambiguous or unsupported")
        lines = lines[headers[0] + 1:]
    else:
        first = next((line for line in lines if line.strip() and not line.lstrip().startswith("#")), "")
        if not first.startswith("- "):
            raise error("registry has no block project list")
    entries = []
    current = None
    entry_indent = None
    narrative_quote = None
    for line in lines:
        if narrative_quote:
            if not quote_open(line, narrative_quote, continuation=True):
                narrative_quote = None
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent_text = line[:len(line) - len(line.lstrip())]
        if "\t" in indent_text:
            raise error("registry indentation is unsupported")
        indent, body = len(indent_text), line.strip()
        if headers and indent == 0 and not body.startswith("- "):
            break  # next top-level registry section
        if entry_indent is None:
            if not body.startswith("- "):
                raise error("registry projects value is not a block list")
            entry_indent = indent
        if indent == entry_indent and body.startswith("- "):
            field = FIELD.fullmatch(body[2:])
            if not field or next(v for v in field.groups()[:3] if v is not None) != "id":
                raise error("registry project entries must start with one id")
            current = {"id": scalar(field.group(4))}
            entries.append(current)
            continue
        if current is None or indent <= entry_indent:
            raise error("registry project structure is unsupported")
        if indent != entry_indent + 2:
            continue  # nested metadata or block prose cannot create links
        field = FIELD.fullmatch(body)
        if not field:
            if body.startswith("- "):
                continue  # metadata sequences at the field indentation
            raise error("registry project field is unsupported")
        name = next(v for v in field.groups()[:3] if v is not None)
        value = field.group(4)
        if name == "<<":
            raise error("registry mapping merges cannot establish routing")
        if name in ROUTING_FIELDS:
            if name in current:
                raise error("registry routing fields are duplicated")
            current[name] = scalar(value)
        elif value.startswith(("'", '"')) and quote_open(value, value[0]):
            narrative_quote = value[0]
    if narrative_quote or not entries:
        raise error("registry project list is incomplete")
    result = {}
    for entry in entries:
        key = entry["id"]
        if key in result:
            raise error("registry project ids are duplicated")
        result[key] = entry
    return result


def project_route(index: Path, project_id: str) -> dict:
    if not PROJECT_ID.fullmatch(project_id):
        raise error("project selector is invalid")
    try:
        if not index.is_absolute() or index.is_symlink() or not stat.S_ISREG(index.stat().st_mode):
            raise error("registry must be an absolute regular file")
        if index.stat().st_size > MAX_REGISTRY_BYTES:
            raise error("registry is oversized")
        def git(*args):
            done = subprocess.run(["git", "--no-optional-locks", "-C", str(index.parent), *args], capture_output=True, text=True)
            if done.returncode:
                raise error("registry Git evidence is unavailable")
            return done.stdout.strip()
        root = Path(git("rev-parse", "--show-toplevel")).resolve()
        relative = index.resolve().relative_to(root).as_posix()
        tracked = git("ls-files", "--stage", "--", ":(top,literal)" + relative).splitlines()
        if len(tracked) != 1 or not re.match(r"100(?:644|755) [0-9a-f]+ 0\t", tracked[0]):
            raise error("registry is not an unambiguous Git-tracked regular file")
        raw = index.read_bytes()
        entries = registry_entries(raw.decode("utf-8"))
    except (OSError, UnicodeError) as exc:
        raise error("registry is unreadable") from exc
    chain = []
    current = project_id
    while True:
        if current in chain:
            raise error("successor relationship is cyclic")
        chain.append(current)
        entry = entries.get(current)
        if entry is None:
            raise error("project or successor is missing from the registry")
        lifecycle = entry.get("status")
        successor = entry.get("superseded_by")
        if lifecycle in {"active", "paused", "ongoing"}:
            if successor:
                raise error("live project has a contradictory successor relationship")
            break
        if lifecycle not in {"archived", "superseded", "completed"} or not successor:
            raise error("terminal or unknown project has no verified live successor")
        current = successor
    return {"requested_project": project_id, "resolved_project": current, "chain": chain,
            "registry": str(index), "registry_sha256": hashlib.sha256(raw).hexdigest(),
            "scope": "report delivery only; no project identity, claim or execution authority"}
