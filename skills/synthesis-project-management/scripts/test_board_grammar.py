"""Synthetic board grammar regressions; no private board content is a fixture."""
from __future__ import annotations

import pytest

import board_inbox
import coordination
import coordination_schema as schema
import project_state


def board_fixture(*, version: int = 4, markup: bool = False) -> str:
    identity = schema.identity_from_uuid("019f0132-0000-7000-8000-000000000001")
    values = {
        "session uuid": identity.session_uuid,
        "compact id": identity.compact_id,
        "speakable id v1": identity.speakable_id,
        "legacy id": "",
        "id": "old-seat",
        "agent": "Example agent",
        "machine": "example-machine",
        "machine label": "Example Mac",
        "client session ref": "codex:example-session",
        "project": "example-project",
        "started": "2026-09-01T12:00:00+00:00",
        "heartbeat": "2026-09-01T12:01:00+00:00",
        "mode": "interactive",
        "workspace(s) / branch": "/example/repo @ feature/example",
        "goal": "Review café → result",
        "claimed areas (advisory lock)": "/example/repo/docs/**",
        "context role": "owner",
        "status": "active",
    }
    columns = getattr(schema, f"V{version}_COLUMNS")
    if markup:
        values["session uuid"] = f'`{values["session uuid"]}`'
        values["context role"] = "**owner**"
        values["status"] = "`active`"
    return (
        f"# Coordination\n\nSchema: v{version}\n\n## Active sessions\n\n"
        + coordination.table_header(columns)
        + "\n| " + " | ".join(values[column] for column in columns) + " |"
        + "\n\n## Messages\n\nExample message.\n\n## Protocol\n\nKeep this text.\n"
    )


def consumer_rows(text: str, tmp_path):
    path = tmp_path / "board.md"
    path.write_text(text, encoding="utf-8")
    dictionaries = schema.parse_table_rows(text)
    recovered = project_state._parse_board_rows(path)
    sessions = coordination.rows(text)
    return dictionaries, recovered, sessions


def test_markdown_cell_meaning_is_identical_for_all_consumers(tmp_path):
    dictionaries, recovered, sessions = consumer_rows(board_fixture(markup=True), tmp_path)
    assert recovered == dictionaries
    assert recovered[0]["session uuid"] == sessions[0].session_uuid
    assert recovered[0]["context role"] == sessions[0].context_role == "owner"
    assert recovered[0]["status"] == sessions[0].status == "active"


def test_message_tables_cannot_create_active_claims(tmp_path):
    text = board_fixture()
    active_row = next(line for line in text.splitlines() if line.startswith("| 019f"))
    text = text.replace("Example message.", "Example message.\n\n" + active_row)
    dictionaries, recovered, sessions = consumer_rows(text, tmp_path)
    assert len(dictionaries) == len(recovered) == len(sessions) == 1


def test_claim_globs_survive_the_table_parse_for_all_consumers(tmp_path):
    # Regression 2026-09-21 (S13): the grammar's bold strip ate the **
    # pairs across multi-glob claim cells, so exact-match verbs could not
    # name what the row held and every re-serialization rewrote the file.
    text = board_fixture().replace(
        "/example/repo/docs/**",
        "/example/repo/docs/**, /example/repo/skills/**",
    )
    dictionaries, recovered, sessions = consumer_rows(text, tmp_path)
    assert dictionaries[0]["claimed areas (advisory lock)"] == (
        "/example/repo/docs/**, /example/repo/skills/**"
    )
    assert recovered == dictionaries
    assert sessions[0].claims == [
        "/example/repo/docs/**", "/example/repo/skills/**",
    ]


@pytest.mark.parametrize("consumer", ["schema", "coordination", "project_state"])
@pytest.mark.parametrize("damage", ["extra-column", "future-schema", "missing-delimiter", "wrong-width", "header-mismatch", "mixed-schema"])
def test_invalid_authority_rows_fail_in_every_consumer(tmp_path, consumer, damage):
    text = board_fixture()
    active_row = next(line for line in text.splitlines() if line.startswith("| 019f"))
    if damage == "extra-column":
        text = text.replace(active_row, active_row + " future-cell |")
    elif damage == "future-schema":
        text = text.replace("Schema: v4", "Schema: v6")
    elif damage == "missing-delimiter":
        text = text.replace(active_row, active_row[:-1])
    elif damage == "wrong-width":
        text = text.replace(active_row, "| " + " | ".join(["x"] * 15) + " |")
    elif damage == "mixed-schema":
        text = text.replace("Schema: v4", "Schema: v3")
    else:
        text = text.replace("| heartbeat |", "| status |", 1)
    path = tmp_path / "board.md"
    path.write_text(text, encoding="utf-8")
    readers = {
        "schema": lambda: schema.parse_table_rows(text),
        "coordination": lambda: coordination.rows(text),
        "project_state": lambda: project_state._parse_board_rows(path),
    }
    with pytest.raises((ValueError, project_state.ProjectStateError)):
        readers[consumer]()


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_supported_versions_have_one_named_column_contract(tmp_path, version):
    text = board_fixture(version=version)
    dictionaries, recovered, sessions = consumer_rows(text, tmp_path)
    assert recovered == dictionaries
    assert tuple(dictionaries[0]) == getattr(schema, f"V{version}_COLUMNS")
    assert sessions[0].status == recovered[0]["status"]
    assert sessions[0].goal == recovered[0]["goal"]


def test_canonical_v4_roundtrip_preserves_every_byte():
    text = board_fixture()
    assert coordination.replace_table(text, coordination.rows(text)).encode() == text.encode()


def test_canonical_v5_roundtrip_preserves_every_byte():
    text = board_fixture(version=5)
    assert coordination.replace_table(text, coordination.rows(text)).encode() == text.encode()


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_mutation_requires_explicit_schema_migration(version):
    text = board_fixture(version=version)
    sessions = coordination.rows(text)
    with pytest.raises(ValueError, match="migrate"):
        coordination.replace_table(text, sessions)
    migrated = coordination.replace_table(text, sessions, force_schema=4)
    assert coordination.board_schema(migrated) == 4
    assert len(board_inbox._board_rows(migrated, strict=True)) == 1


@pytest.mark.parametrize("damage", ["missing-schema", "duplicate-schema", "duplicate-active", "missing-messages", "wrong-header", "bad-separator", "non-row", "invalid-identity"])
def test_strict_inbox_authority_refuses_malformed_boards(damage):
    text = board_fixture()
    assert len(board_inbox._board_rows(text, strict=True)) == 1
    if damage == "missing-schema":
        text = text.replace("Schema: v4\n", "")
    elif damage == "duplicate-schema":
        text = text.replace("Schema: v4", "Schema: v4\nSchema: v4")
    elif damage == "duplicate-active":
        text += "\n## Active sessions\n"
    elif damage == "missing-messages":
        text = text.replace("## Messages", "## Other")
    elif damage == "wrong-header":
        text = text.replace("| session uuid |", "| SESSION UUID |", 1)
    elif damage == "bad-separator":
        text = text.replace("|---|", "|:--:|", 1)
    elif damage == "non-row":
        text = text.replace("\n\n## Messages", "\nnot a row\n\n## Messages")
    else:
        text = text.replace("s-0000-0000-0001", "s-0000-0000-0002")
    with pytest.raises(ValueError):
        board_inbox._board_rows(text, strict=True)
