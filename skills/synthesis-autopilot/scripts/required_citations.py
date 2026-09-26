"""Bounded retention observation for explicitly required plan/packet citations.

Only named required-evidence declarations form obligations. Ordinary links,
examples and historical prose never grant authority. Referenced Markdown
packets recursively use the same declarations. Every local target must already
have a current digest-bound durable artifact registration; this module neither
copies files nor creates authority from their contents.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
from urllib.parse import unquote, urlsplit

from run_admission import safe_path

MAX_DOCUMENTS = 64
MAX_BYTES = 4 * 1024 * 1024
MAX_CITATIONS = 1024
MARKER = re.compile(r"^\s*(?:#{1,6}\s+)?(?:(?:[-*+]|[0-9]+[.)])\s+)?(?:\*\*|__)?Required (?:acceptance |recovery )?(?:evidence|artifacts|inputs|scripts)(?:\*\*|__)?\s*(?::\s*(.*)|$)", re.I)
LINK = re.compile(r"(?<!!)\[([^\[\]\n]+)\]\(\s*(<[^>\n]+>|[^\s()]+)(?:\s+[\"'][^\n]*?[\"'])?\s*\)|(?<!!)\[([^\[\]\n]+)\]\[([^\[\]\n]*)\]")
DEFINITION = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)\s*$")


def _body(text):
    # Linear scanning also bounds malformed/unclosed generated regions.
    start_pattern = re.compile(r"\n?<!-- autopilot:[0-9a-f-]+:start -->\n")
    end_pattern = re.compile(r"<!-- autopilot:[0-9a-f-]+:end -->\n?")
    parts, cursor = [], 0
    while (start := start_pattern.search(text, cursor)) is not None:
        end = end_pattern.search(text, start.end())
        if end is None:
            break
        parts.append(text[cursor:start.start()]); cursor = end.end()
    parts.append(text[cursor:])
    return "".join(parts)


def plan_text_digest(text):
    return hashlib.sha256(_body(text).rstrip().encode()).hexdigest()


def _without_comments(text):
    parts, cursor = [], 0
    while (start := text.find("<!--", cursor)) >= 0:
        parts.append(text[cursor:start])
        end = text.find("-->", start + 4)
        if end < 0:
            return "".join(parts)
        cursor = end + 3
    parts.append(text[cursor:])
    return "".join(parts)


def _declarations(text):
    # Exclude fenced examples and HTML comments before recognizing declarations.
    text = _without_comments(_body(text))
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append("")
        else:
            lines.append("" if fence else line)
    definitions, ambiguous = {}, set()
    for line in lines:
        match = DEFINITION.match(line)
        if match:
            key = match.group(1).casefold()
            if key in definitions and definitions[key] != match.group(2):
                ambiguous.add(key)
            definitions[key] = match.group(2)
    blocks, active, level = [], None, None
    for line in lines:
        heading = re.match(r"^\s{0,3}(#{1,6})\s+", line)
        # Optional closing ATX hashes are heading syntax, not label text.
        # Normalize only an actual heading; ordinary prose stays non-authoritative.
        marker_line = line
        if heading:
            trimmed = line.rstrip()
            label = trimmed.rstrip("#")
            if len(label) < len(trimmed) and label and label[-1].isspace():
                marker_line = label.rstrip()
        marker = MARKER.match(marker_line)
        if marker:
            if active is not None:
                blocks.append("\n".join(active))
            active = [marker.group(1) or ""]
            level = len(heading.group(1)) if heading else None
        elif active is not None:
            if (heading and (level is None or len(heading.group(1)) <= level)) or (level is None and not line.strip()):
                blocks.append("\n".join(active)); active = None; level = None
            else:
                active.append(line)
    if active is not None:
        blocks.append("\n".join(active))
    result = []
    for block in blocks:
        matches = list(LINK.finditer(block))
        if not matches:
            raise ValueError("required evidence declaration has no supported explicit citation")
        residue = LINK.sub("", block)
        if "[" in residue or "](" in residue or "file:" in residue or re.search(r"`[^`]*(?:/|\\)[^`]*`", residue):
            raise ValueError("required evidence declaration has unresolved citation syntax")
        for match in matches:
            target = match.group(2)
            if target is None:
                key = (match.group(4) or match.group(3)).casefold()
                if key in ambiguous:
                    raise ValueError("ambiguous required citation reference definition")
                if key not in definitions:
                    raise ValueError("required citation reference has no definition")
                target = definitions[key]
            result.append(target.removeprefix("<").removesuffix(">"))
    return result


def _read(path, remaining):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > remaining:
            raise ValueError("required evidence document is not a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(remaining + 1)
        after = os.fstat(fd)
        current = path.stat(follow_symlinks=False)
        fields = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if len(raw) > remaining or fields(before) != fields(after) or fields(after) != fields(current):
            raise ValueError("required evidence document changed during observation")
        return raw
    finally:
        os.close(fd)


def observe_required_citations(project, plan, artifacts, *, expected_plan_digest):
    """Return PASS only for registered, current, durable required local targets.

    Unavailable/unsupported citations are UNKNOWN, not absent or successfully
    verified. The caller uses this observation only for completed closure.
    """
    retained, queue, visited, total, count = {}, [(plan, None)], set(), 0, 0
    project = project.resolve()
    by_path = {}
    for key, record in artifacts.items():
        if record.get("retention") == "durable":
            by_path[str(project / record["path"])] = (key, record)
    try:
        while queue:
            document, registered_digest = queue.pop(0)
            if document in visited:
                continue
            if len(visited) >= MAX_DOCUMENTS:
                raise ValueError("required evidence document-count limit exceeded")
            visited.add(document)
            # The plan was separately admitted, so may reside in its repository
            # outside the project. Every cited artifact remains project-owned.
            raw = _read(document, MAX_BYTES - total)
            total += len(raw)
            digest = hashlib.sha256(raw).hexdigest()
            if registered_digest is not None and digest != registered_digest:
                raise ValueError("required packet changed after artifact verification")
            text = raw.decode("utf-8")
            if document == plan and plan_text_digest(text) != expected_plan_digest:
                raise ValueError("controlling plan changed during citation observation")
            for target in _declarations(text):
                count += 1
                if count > MAX_CITATIONS:
                    raise ValueError("required evidence citation-count limit exceeded")
                uri = urlsplit(target)
                if uri.scheme not in ("", "file") or uri.netloc or uri.query:
                    raise ValueError("required citation lacks locally retained evidence: " + target)
                decoded = unquote(uri.path)
                if not decoded or "\x00" in decoded or "\\" in decoded:
                    raise ValueError("required citation has an unsupported path")
                path = Path(decoded)
                if not path.is_absolute():
                    path = document.parent / path
                if any(component.is_symlink() for component in (path, *path.parents)):
                    raise ValueError("required citation crosses a symlink")
                path = safe_path(Path(os.path.abspath(path)), project)
                selected = by_path.get(str(path))
                if selected is None:
                    raise ValueError("required citation is not a current registered durable artifact: " + target)
                key, record = selected
                retained[key] = record["digest"]
                if path.suffix.casefold() in (".md", ".markdown"):
                    queue.append((path, record["digest"]))
        return {"status": "PASS", "artifacts": retained, "documents": len(visited), "citations": count, "issues": []}
    except (OSError, ValueError, UnicodeError) as exc:
        return {"status": "UNKNOWN", "artifacts": retained, "issues": [str(exc)]}
