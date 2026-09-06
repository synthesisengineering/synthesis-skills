#!/usr/bin/env python3
"""Bounded-memory validation of native JSONL transcript identity evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import tracemalloc
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import live_receipt  # noqa: E402


SESSION = "019fff79-5858-7993-a329-b301bccf5d31"
OTHER = "019fff79-5858-7993-a329-b301bccf5d32"


def _binding(client: str, session: str = SESSION) -> dict:
    if client == "codex":
        return {"type": "session_meta", "payload": {"id": session}}
    return {"sessionId": session}


def _write(path: Path, *records: object) -> Path:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return path


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_large_single_record_binds_with_bounded_memory(tmp_path: Path, client: str) -> None:
    """A valid identity after a >64 MiB string cannot require that allocation."""
    path = tmp_path / "large.jsonl"
    with path.open("wb") as handle:
        handle.write(b'{"discarded":"')
        for _ in range(1025):
            handle.write(b"x" * (64 * 1024))
        handle.write(b'",')
        handle.write(json.dumps(_binding(client))[1:].encode("utf-8") + b"\n")
    before = _digest(path)
    assert path.stat().st_size > 64 * 1024 * 1024

    tracemalloc.start()
    try:
        result = live_receipt.transcript_binding_state(path, client, SESSION)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert result == "bound"
    assert peak < 4 * 1024 * 1024, "binding retained an oversized transcript record"
    assert _digest(path) == before


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_conflicting_declaration_after_large_discarded_string_is_rejected(
    tmp_path: Path, client: str
) -> None:
    path = tmp_path / "conflicting.jsonl"
    with path.open("wb") as handle:
        handle.write(json.dumps(_binding(client)).encode("utf-8") + b"\n")
        handle.write(b'{"discarded":"')
        for _ in range(33):
            handle.write(b"x" * (64 * 1024))
        handle.write(b'",')
        handle.write(json.dumps(_binding(client, OTHER))[1:].encode("utf-8") + b"\n")
    assert live_receipt.transcript_binding_state(path, client, SESSION) == "conflicting"


@pytest.mark.parametrize(
    "record",
    [
        '{"sessionId":"%s","sessionId":"%s"}' % (OTHER, SESSION),
        '{"sessionId":"%s","sessionId":"%s"}' % (SESSION, OTHER),
        '{"sessionId":"%s","discarded":"bad\\q"}' % SESSION,
        '{"sessionId":"%s","discarded":01}' % SESSION,
        '{"sessionId":"%s","discarded":NaN}' % SESSION,
        '{"sessionId":"%s","discarded":[true,]}' % SESSION,
        '{"sessionId":"%s","discarded":true} trailing' % SESSION,
        '{"sessionId":"%s","discarded":' % SESSION,
    ],
    ids=["duplicate-before", "duplicate-after", "escape", "number", "nan", "array", "trailing", "partial"],
)
def test_malformed_or_ambiguous_record_cannot_supply_binding(tmp_path: Path, record: str) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text(record + "\n", encoding="utf-8")
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "invalid"


@pytest.mark.parametrize(
    "record",
    [
        '{"type":"message","type":"session_meta","payload":{"id":"%s"}}' % SESSION,
        '{"type":"session_meta","payload":{"id":"%s","id":"%s"}}' % (OTHER, SESSION),
        '{"type":"session_meta","payload":{"id":"%s"},"payload":{"id":"%s"}}' % (OTHER, SESSION),
    ],
)
def test_codex_duplicate_identity_keys_fail_closed(tmp_path: Path, record: str) -> None:
    path = tmp_path / "ambiguous.jsonl"
    path.write_text(record + "\n", encoding="utf-8")
    assert live_receipt.transcript_binding_state(path, "codex", SESSION) == "invalid"


def test_malformed_record_after_positive_binding_fails_closed(tmp_path: Path) -> None:
    path = _write(tmp_path / "invalid-after.jsonl", _binding("codex"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"type":"session_meta","payload":{"id":"%s"},broken}\n' % OTHER)
    assert live_receipt.transcript_binding_state(path, "codex", SESSION) == "invalid"


def test_nesting_exhaustion_is_a_verdict_not_a_recursion_error(tmp_path: Path) -> None:
    path = tmp_path / "deep.jsonl"
    path.write_text(
        '{"sessionId":"%s","discarded":' % SESSION + "[" * 2048 + "0" + "]" * 2048 + "}\n",
        encoding="utf-8",
    )
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "invalid"


def test_escaped_identity_keys_and_values_bind(tmp_path: Path) -> None:
    path = tmp_path / "escaped.jsonl"
    escaped_session = "".join("\\u%04x" % ord(character) for character in SESSION)
    path.write_text('{"session\\u0049d":"%s"}\r\n' % escaped_session, encoding="utf-8")
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "bound"


def test_uuid_in_ignored_strings_or_nested_objects_does_not_bind(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "not-identity.jsonl",
        {"text": SESSION, "nested": {"sessionId": SESSION}},
        {"type": "message", "payload": {"id": SESSION}},
    )
    for client in ("claude", "codex"):
        assert live_receipt.transcript_binding_state(path, client, SESSION) == "pending"


def test_scan_boundary_is_explicit_and_preserves_earlier_conflicts(tmp_path: Path) -> None:
    path = tmp_path / "boundary.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(_binding("claude")) + "\n")
        for _ in range(live_receipt.MAX_BINDING_LINES - 2):
            handle.write('{}\n')
        handle.write(json.dumps(_binding("claude", OTHER)) + "\n")
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "conflicting"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(_binding("claude")) + "\n")
        for _ in range(live_receipt.MAX_BINDING_LINES - 1):
            handle.write('{}\n')
        handle.write(json.dumps(_binding("claude", OTHER)) + "\n")
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "bound"


def test_giant_unselected_key_and_scalar_are_not_retained(tmp_path: Path) -> None:
    path = tmp_path / "wide.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write('{"' + "x" * (256 * 1024) + '":' + "7" * (256 * 1024))
        handle.write(',"sessionId":"%s"}\n' % SESSION)
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "bound"


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_client_root_helper_accepts_only_the_configured_native_root(tmp_path: Path, client: str) -> None:
    root = tmp_path / ("." + client)
    relative = (
        Path("projects") / "encoded" / (SESSION + ".jsonl")
        if client == "claude" else Path("sessions") / "native.jsonl"
    )
    path = root / relative
    path.parent.mkdir(parents=True)
    _write(path, _binding(client))
    helper = live_receipt.client_root_transcript_path
    assert helper(path, client, SESSION, root)
    assert not helper(tmp_path / "outside.jsonl", client, SESSION, root)
    assert not helper(relative, client, SESSION, root)
    assert not helper(root / "segment" / ".." / relative, client, SESSION, root)
    assert not helper(path, "unknown", SESSION, root)
    assert not helper(path, client, "not-a-uuid", root)


@pytest.mark.parametrize("client", ["claude", "codex"])
def test_client_root_helper_rejects_symlinked_transcript_or_parent(tmp_path: Path, client: str) -> None:
    root = tmp_path / ("." + client)
    parent = root / ("projects" if client == "claude" else "sessions")
    parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = _write(outside / (SESSION + ".jsonl"), _binding(client))
    if client == "claude":
        (parent / "encoded").symlink_to(outside, target_is_directory=True)
        path = parent / "encoded" / target.name
    else:
        path = parent / target.name
        path.symlink_to(target)
    assert not live_receipt.client_root_transcript_path(path, client, SESSION, root)


def test_claude_root_helper_rejects_subagent_and_wrong_filename(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    helper = live_receipt.client_root_transcript_path
    assert not helper(root / "projects" / "encoded" / "other.jsonl", "claude", SESSION, root)
    assert not helper(
        root / "projects" / "encoded" / SESSION / "subagents" / "agent.jsonl",
        "claude", SESSION, root,
    )


@pytest.mark.parametrize("read_chars", [1, 2, 3, 7])
@pytest.mark.parametrize("client", ["claude", "codex"])
def test_chunk_boundaries_preserve_json_grammar_and_identity(
    tmp_path: Path, monkeypatch, read_chars: int, client: str
) -> None:
    monkeypatch.setattr(live_receipt, "TRANSCRIPT_READ_CHARS", read_chars)
    escaped_session = "".join("\\u%04x" % ord(character) for character in SESSION)
    identity = (
        '"t\\u0079pe":"session_meta","payload":{"i\\u0064":"%s"}'
        if client == "codex" else '"session\\u0049d":"%s"'
    ) % escaped_session
    discarded = (
        '"discarded":{"numbers":[-12.5e+2,0,1E-3],'
        '"nested":[true,false,null,{"text":"snowman ☃ \\u2603 \\\\ \\""}]}'
    )
    path = tmp_path / "chunks.jsonl"
    path.write_text("{" + discarded + "," + identity + "}\r\n", encoding="utf-8")
    assert live_receipt.transcript_binding_state(path, client, SESSION) == "bound"
    path.write_text(
        "{" + identity + ',"discarded":"invalid\\u12z4"}\r\n', encoding="utf-8"
    )
    assert live_receipt.transcript_binding_state(path, client, SESSION) == "invalid"


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b"\r"])
def test_native_text_reader_preserves_universal_newline_boundaries(
    tmp_path: Path, ending: bytes
) -> None:
    path = tmp_path / "newlines.jsonl"
    path.write_bytes(json.dumps(_binding("claude")).encode("utf-8") + ending)
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "bound"
    with path.open("ab") as handle:
        handle.write(json.dumps(_binding("claude", OTHER)).encode("utf-8") + ending)
    assert live_receipt.transcript_binding_state(path, "claude", SESSION) == "conflicting"


@pytest.mark.parametrize("read_chars", [1, 7, 64 * 1024])
def test_invalid_utf8_in_scanned_records_fails_closed(
    tmp_path: Path, monkeypatch, read_chars: int
) -> None:
    monkeypatch.setattr(live_receipt, "TRANSCRIPT_READ_CHARS", read_chars)
    path = tmp_path / "invalid-encoding.jsonl"
    path.write_bytes(
        json.dumps(_binding("codex")).encode("utf-8")
        + b'\n{"discarded":"\xff"}\n'
    )
    assert live_receipt.transcript_binding_state(path, "codex", SESSION) == "invalid"
