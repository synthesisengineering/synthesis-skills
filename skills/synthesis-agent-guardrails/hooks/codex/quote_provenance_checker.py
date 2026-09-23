#!/usr/bin/env python3
"""Codex Stop hook for Slack quote provenance checks.

Detects Slack-TS-shaped values that were written into transcript, daily-plan,
or project context files during this Codex session without appearing
in any other visible session input or output.

This is a Codex-native companion to the Claude quote_provenance_checker,
sharing the _transcript_state projection core. It is a logging backstop,
not a blocker; the main rule remains self-checking quote provenance
before writing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CLAUDE_HOOKS = Path(__file__).resolve().parent.parent / "claude"
if str(CLAUDE_HOOKS) not in sys.path:
    sys.path.insert(0, str(CLAUDE_HOOKS))
HOOKS_ROOT = CLAUDE_HOOKS.parent
if str(HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(HOOKS_ROOT))
from _transcript_state import project_jsonl, provenance_state_valid  # noqa: E402
from _settings import doctor_prologue, hook_enabled  # noqa: E402

HOOK_NAME = "quote_provenance_checker"

REDUCER_REVISION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

LOG_FILE = Path(os.environ.get("CODEX_QUOTE_PROVENANCE_LOG", Path.home() / ".codex" / "quote-provenance-log.jsonl"))

TS_FLOAT = re.compile(r"\b(\d{10}\.\d{6})\b")
TS_PERMALINK = re.compile(r"/p(\d{10})(\d{6})\b")

CHECKED_PATH_PATTERNS = [
    re.compile(r"(^|/)transcripts/slack/"),
    re.compile(r"(^|/)transcripts/(gchat|email|meetings)/"),
    re.compile(r"(^|/)daily-plans/"),
    re.compile(r"(^|/)projects/[^/]+/(CONTEXT|REFERENCE)\.md\b"),
    re.compile(r"(^|/)projects/[^/]+/sessions/"),
]

STRUCTURED_WRITING_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATCH_TOOLS = {"apply_patch", "functions.apply_patch"}


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") in {"text", "input_text", "output_text"}:
                    parts.append(str(item.get("text", "")))
                elif item.get("type") in {"tool_result", "function_call_output"}:
                    parts.append(stringify(item.get("content", item.get("output", ""))))
                else:
                    parts.append(stringify(item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return str(value)


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def extract_tses(value: Any) -> set[str]:
    text = stringify(value)
    out: set[str] = set()
    for match in TS_FLOAT.finditer(text):
        out.add(match.group(1))
    for match in TS_PERMALINK.finditer(text):
        out.add(f"{match.group(1)}.{match.group(2)}")
    return out


def path_is_checked(path: str | None) -> bool:
    if not path:
        return False
    cleaned = os.path.expanduser(str(path).strip().strip('"').strip("'"))
    return any(pattern.search(cleaned) for pattern in CHECKED_PATH_PATTERNS)


def path_for_record(path: str | None, cwd: str) -> str:
    if not path:
        return ""
    cleaned = os.path.expanduser(str(path).strip().strip('"').strip("'"))
    if cleaned.startswith("/") or not cwd:
        return cleaned
    return str(Path(cwd) / cleaned)


def extract_paths_from_patch_header(line: str) -> str | None:
    match = re.match(r"\*\*\* (?:Add|Update|Delete) File: (.+)$", line)
    if match:
        return match.group(1).strip()
    return None


def audit_patch(patch_text: str, cwd: str) -> tuple[list[dict[str, Any]], set[str]]:
    """Return write records from added patch lines plus TSes seen in old/context lines."""
    written: list[dict[str, Any]] = []
    seen: set[str] = set()
    current_file = ""
    added_lines: list[str] = []
    old_or_context_lines: list[str] = []

    def flush() -> None:
        nonlocal added_lines, old_or_context_lines, current_file
        if current_file and path_is_checked(current_file):
            added_text = "\n".join(added_lines)
            old_text = "\n".join(old_or_context_lines)
            added_tses = extract_tses(added_text) - extract_tses(old_text)
            if added_tses:
                written.append(
                    {
                        "tool": "apply_patch",
                        "file": path_for_record(current_file, cwd),
                        "added_tses": sorted(added_tses),
                    }
                )
            seen.update(extract_tses(old_text))
        added_lines = []
        old_or_context_lines = []

    for line in patch_text.splitlines():
        next_file = extract_paths_from_patch_header(line)
        if next_file is not None:
            flush()
            current_file = next_file
            continue
        if not current_file:
            continue
        if line.startswith("+") and not line.startswith("+++"):  # added file content
            added_lines.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            old_or_context_lines.append(line[1:])
        elif line.startswith(" "):
            old_or_context_lines.append(line[1:])

    flush()
    return written, seen


def audit_structured_write(name: str, tool_input: dict[str, Any], cwd: str) -> tuple[list[dict[str, Any]], set[str]]:
    file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path") or ""
    if not path_is_checked(file_path):
        return [], extract_tses(tool_input)

    if name == "Write":
        new_text = tool_input.get("content", "")
        old_text = ""
    elif name == "Edit":
        new_text = tool_input.get("new_string", "")
        old_text = tool_input.get("old_string", "")
    elif name == "MultiEdit":
        edits = tool_input.get("edits", []) or []
        new_text = "\n".join(edit.get("new_string", "") for edit in edits if isinstance(edit, dict))
        old_text = "\n".join(edit.get("old_string", "") for edit in edits if isinstance(edit, dict))
    else:
        new_text = stringify(tool_input)
        old_text = ""

    added = extract_tses(new_text) - extract_tses(old_text)
    records = []
    if added:
        records.append(
            {
                "tool": name,
                "file": path_for_record(file_path, cwd),
                "added_tses": sorted(added),
            }
        )
    return records, extract_tses(old_text)


def locate_transcript(input_data: dict[str, Any]) -> Path | None:
    for key in ("transcript_path", "session_path", "conversation_path"):
        value = input_data.get(key)
        if isinstance(value, str) and value:
            path = Path(os.path.expanduser(value))
            if path.is_file():
                return path

    session_id = str(input_data.get("session_id") or "")
    if not session_id:
        return None

    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.is_dir():
        return None

    matches = sorted(
        (path for path in sessions_root.rglob("rollout-*.jsonl") if session_id in path.name),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def iter_events(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def handle_codex_response_item(payload: dict[str, Any], cwd: str) -> tuple[set[str], list[dict[str, Any]]]:
    seen: set[str] = set()
    written: list[dict[str, Any]] = []
    item_type = payload.get("type")

    if item_type == "message":
        seen.update(extract_tses(payload.get("content", "")))
    elif item_type == "function_call_output":
        seen.update(extract_tses(payload.get("output", "")))
    elif item_type == "function_call":
        name = str(payload.get("name") or "")
        args = parse_jsonish(payload.get("arguments", {}))
        if name in STRUCTURED_WRITING_TOOLS and isinstance(args, dict):
            records, old_seen = audit_structured_write(name, args, cwd)
            written.extend(records)
            seen.update(old_seen)
        elif name in PATCH_TOOLS:
            patch = args.get("patch", "") if isinstance(args, dict) else stringify(args)
            records, old_seen = audit_patch(patch, cwd)
            written.extend(records)
            seen.update(old_seen)
        else:
            seen.update(extract_tses(args))
    elif item_type == "custom_tool_call":
        name = str(payload.get("name") or "")
        tool_input = payload.get("input", "")
        if name in PATCH_TOOLS:
            records, old_seen = audit_patch(stringify(tool_input), cwd)
            written.extend(records)
            seen.update(old_seen)
        elif name in STRUCTURED_WRITING_TOOLS and isinstance(tool_input, dict):
            records, old_seen = audit_structured_write(name, tool_input, cwd)
            written.extend(records)
            seen.update(old_seen)
        else:
            seen.update(extract_tses(tool_input))
    return seen, written


def handle_claude_message(event: dict[str, Any], cwd: str) -> tuple[set[str], list[dict[str, Any]]]:
    """Compatibility with Claude-style JSONL if a transcript path is passed."""
    seen: set[str] = set()
    written: list[dict[str, Any]] = []
    msg = event.get("message", {}) or {}
    content = msg.get("content", [])
    if isinstance(content, str):
        return extract_tses(content), []
    if not isinstance(content, list):
        return seen, written

    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            seen.update(extract_tses(block.get("text", "")))
        elif block_type == "tool_result":
            seen.update(extract_tses(block.get("content", "")))
        elif block_type == "tool_use":
            name = str(block.get("name") or "")
            tool_input = block.get("input", {}) or {}
            if name in STRUCTURED_WRITING_TOOLS and isinstance(tool_input, dict):
                records, old_seen = audit_structured_write(name, tool_input, cwd)
                written.extend(records)
                seen.update(old_seen)
            elif name in PATCH_TOOLS:
                patch = tool_input.get("patch", "") if isinstance(tool_input, dict) else stringify(tool_input)
                records, old_seen = audit_patch(patch, cwd)
                written.extend(records)
                seen.update(old_seen)
            else:
                seen.update(extract_tses(tool_input))
    return seen, written


def scan_transcript(transcript: Path, cwd: str) -> tuple[set[str], list[dict[str, Any]]]:
    def reduce(state, event):
        if event.get("type") == "response_item" and isinstance(event.get("payload"), dict):
            seen, written = handle_codex_response_item(event["payload"], cwd)
        else:
            seen, written = handle_claude_message(event, cwd)
        state["seen"].update((value, True) for value in seen)
        state["written"].extend(written)

    state = project_jsonl(
        transcript, namespace="codex-quote-provenance", revision=REDUCER_REVISION,
        context={"cwd": cwd, "home": str(Path.home())},
        initial=lambda: {"seen": {}, "written": []}, reduce=reduce,
        validate=provenance_state_valid,
    )
    return set(state["seen"]), state["written"]


def doctor() -> int:
    lines, _healthy = doctor_prologue(HOOK_NAME)
    lines.append(f"log_file={LOG_FILE}")
    lines.append(f"checked_path_patterns={len(CHECKED_PATH_PATTERNS)}")
    lines.append(f"writing_tools={sorted(STRUCTURED_WRITING_TOOLS)}")
    lines.append(f"patch_tools={sorted(PATCH_TOOLS)}")
    print("\n".join(lines))
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--doctor" in argv:
        return doctor()
    if not hook_enabled(HOOK_NAME):
        return 0

    try:
        input_data = json.load(sys.stdin)
    except Exception:
        return 0

    session_id = str(input_data.get("session_id") or "unknown")
    cwd = str(input_data.get("cwd") or "")
    transcript = locate_transcript(input_data)
    if transcript is None:
        return 0

    try:
        seen_tses, written_records = scan_transcript(transcript, cwd)
    except Exception:
        return 0

    violations: list[dict[str, Any]] = []
    for record in written_records:
        fabricated = sorted(set(record.get("added_tses", [])) - seen_tses)
        if fabricated:
            violations.append(
                {
                    "tool": record.get("tool", "unknown"),
                    "file": record.get("file", ""),
                    "fabricated_tses": fabricated,
                }
            )

    if not violations:
        return 0

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "cwd": cwd,
        "transcript_path": str(transcript),
        "seen_ts_count": len(seen_tses),
        "violations": violations,
    }
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

    warning = (
        "Quote-provenance checker found Slack-TS-shaped values written into "
        "transcript, daily-plan, or project context files without provenance "
        f"elsewhere in this Codex session. Logged to {LOG_FILE}."
    )
    print(json.dumps({"continue": True, "systemMessage": warning}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
