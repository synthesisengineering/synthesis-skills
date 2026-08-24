#!/usr/bin/env python3
"""Tests for fail-closed durable-context edits."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_edit import (
    ContextEditError,
    apply_replacement,
    insert_before,
    main,
    replace_once,
    set_field,
)

RECORD = """# Project — Context

**Phase:** Adversarial round 2 complete
**Status:** Active
**Last session:** 2026-08-23

## Body

Round 2 findings were adjudicated.
"""


def record(tmp_path: Path, text: str = RECORD) -> Path:
    path = tmp_path / "CONTEXT.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_replaces_and_verifies_on_disk(tmp_path: Path) -> None:
    path = record(tmp_path)

    result = replace_once(
        path,
        anchor="**Phase:** Adversarial round 2 complete",
        replacement="**Phase:** Adversarial round 3 complete",
    )

    assert result["changed"] is True
    assert "round 3 complete" in path.read_text(encoding="utf-8")


def test_missing_anchor_refuses_and_leaves_file_untouched(tmp_path: Path) -> None:
    """The routed defect: another agent rewrote the header between sessions.

    A bare str.replace() would no-op here and any surrounding success message
    would be false. The helper must refuse instead.
    """
    path = record(tmp_path)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ContextEditError, match="anchor not found"):
        replace_once(
            path,
            anchor="**Phase:** Adversarial round 1 complete",
            replacement="**Phase:** Adversarial round 3 complete",
        )

    assert path.read_text(encoding="utf-8") == before


def test_cli_missing_anchor_exits_nonzero_without_success_output(
    tmp_path: Path, capsys
) -> None:
    path = record(tmp_path)

    code = main(
        [
            "replace",
            "--file",
            str(path),
            "--anchor",
            "text that is not present",
            "--replacement",
            "new text",
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "refused" in captured.err
    assert path.read_text(encoding="utf-8") == RECORD


def test_ambiguous_anchor_refuses_without_explicit_count(tmp_path: Path) -> None:
    path = record(tmp_path, "alpha\nalpha\n")

    with pytest.raises(ContextEditError, match="matched 2 time"):
        replace_once(path, anchor="alpha", replacement="beta")

    assert path.read_text(encoding="utf-8") == "alpha\nalpha\n"


def test_ambiguous_anchor_allowed_with_explicit_count(tmp_path: Path) -> None:
    path = record(tmp_path, "alpha\nalpha\n")

    result = replace_once(path, anchor="alpha", replacement="beta", count=2)

    assert result["replacements"] == 2
    assert path.read_text(encoding="utf-8") == "beta\nbeta\n"


def test_identical_replacement_refuses(tmp_path: Path) -> None:
    path = record(tmp_path)

    with pytest.raises(ContextEditError, match="byte-identical"):
        replace_once(path, anchor="**Status:** Active", replacement="**Status:** Active")


def test_symlink_is_refused(tmp_path: Path) -> None:
    target = record(tmp_path)
    link = tmp_path / "LINK.md"
    link.symlink_to(target)

    with pytest.raises(ContextEditError, match="symlink"):
        replace_once(link, anchor="**Status:** Active", replacement="**Status:** Done")


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ContextEditError, match="not a file"):
        replace_once(tmp_path / "absent.md", anchor="a", replacement="b")


def test_empty_anchor_is_refused(tmp_path: Path) -> None:
    path = record(tmp_path)

    with pytest.raises(ContextEditError, match="must not be empty"):
        replace_once(path, anchor="", replacement="b")


def test_budget_violation_refuses_before_writing(tmp_path: Path) -> None:
    path = record(tmp_path)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ContextEditError, match="line budget"):
        replace_once(
            path,
            anchor="## Body",
            replacement="## Body\n" + "\n".join(f"line {n}" for n in range(50)),
            max_lines=20,
        )

    assert path.read_text(encoding="utf-8") == before


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    path = record(tmp_path)

    result = replace_once(
        path,
        anchor="**Status:** Active",
        replacement="**Status:** Complete",
        dry_run=True,
    )

    assert result["changed"] is False and result["dry_run"] is True
    assert path.read_text(encoding="utf-8") == RECORD


def test_dry_run_still_refuses_a_missing_anchor(tmp_path: Path) -> None:
    path = record(tmp_path)

    with pytest.raises(ContextEditError, match="anchor not found"):
        replace_once(path, anchor="absent", replacement="x", dry_run=True)


def test_set_field_replaces_whole_header_line(tmp_path: Path) -> None:
    path = record(tmp_path)

    set_field(path, field="Phase", value="Adversarial round 3 complete")

    text = path.read_text(encoding="utf-8")
    assert "**Phase:** Adversarial round 3 complete" in text
    assert "round 2" not in text


def test_set_field_refuses_absent_field(tmp_path: Path) -> None:
    path = record(tmp_path)

    with pytest.raises(ContextEditError, match="header field not found"):
        set_field(path, field="Milestone", value="x")


def test_set_field_refuses_duplicated_field(tmp_path: Path) -> None:
    path = record(tmp_path, "**Phase:** one\n**Phase:** two\n")

    with pytest.raises(ContextEditError, match="appears 2 times"):
        set_field(path, field="Phase", value="three")


def test_insert_before_preserves_the_anchor(tmp_path: Path) -> None:
    """Prepending a section must not consume the heading it anchors on."""
    path = record(tmp_path, "## [1.1.0]\n\nold release\n")

    insert_before(path, anchor="## [1.1.0]", text="## [1.2.0]\n\nnew release\n\n")

    text = path.read_text(encoding="utf-8")
    assert text.index("## [1.2.0]") < text.index("## [1.1.0]")
    assert "old release" in text and "new release" in text


def test_insert_before_refuses_a_missing_anchor(tmp_path: Path) -> None:
    path = record(tmp_path, "## [1.1.0]\n")

    with pytest.raises(ContextEditError, match="anchor not found"):
        insert_before(path, anchor="## [9.9.9]", text="x\n")


def test_apply_replacement_is_pure(tmp_path: Path) -> None:
    edited = apply_replacement("alpha beta", "beta", "gamma")

    assert edited == "alpha gamma"


def test_failed_edit_leaves_no_temporary_files(tmp_path: Path) -> None:
    path = record(tmp_path)

    with pytest.raises(ContextEditError):
        replace_once(path, anchor="absent", replacement="x")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["CONTEXT.md"]


INCOHERENT = """# P

**Phase:** Round 10 review complete
**Status:** Active
**Last session:** 2026-08-23 (round 10, Codex)

## Body
"""


def test_phase_update_leaving_last_session_behind_is_refused(
    tmp_path: Path,
) -> None:
    """The round-10/11 defect, blocked at write time: a fresh Phase over a
    stale Last session must never reach disk silently."""
    path = record(tmp_path, INCOHERENT)
    before = path.read_text(encoding="utf-8")

    with pytest.raises(ContextEditError, match="header incoherent"):
        set_field(path, field="Phase", value="Round 11 — convergence call was wrong")

    assert path.read_text(encoding="utf-8") == before


def test_last_session_may_lead_phase_with_a_note(tmp_path: Path) -> None:
    """The legitimate two-call transition: Last session updates first."""
    path = record(tmp_path, INCOHERENT)

    result = set_field(
        path, field="Last session", value="2026-08-23 (round 11, Claude)"
    )

    assert "finish by updating Phase" in (result["note"] or "")

    finish = set_field(path, field="Phase", value="Round 11 in review")

    # The completion signal always names body status on CONTEXT.md now.
    assert "body currency unverifiable" in (finish["note"] or "")
    text = path.read_text(encoding="utf-8")
    assert "Round 11 in review" in text and "round 11, Claude" in text


def test_allow_header_lag_records_the_override(tmp_path: Path) -> None:
    path = record(tmp_path, INCOHERENT)

    result = set_field(
        path,
        field="Phase",
        value="Round 11 staged",
        allow_header_lag=True,
    )

    assert "override --allow-header-lag recorded" in (result["note"] or "")


def test_unrelated_edit_on_preexisting_incoherence_warns_not_blocks(
    tmp_path: Path,
) -> None:
    stale = INCOHERENT.replace(
        "**Phase:** Round 10 review complete", "**Phase:** Round 11 staged"
    )
    path = record(tmp_path, stale)

    result = replace_once(path, anchor="## Body", replacement="## Body\n\nmore")

    assert "pre-existing header incoherence" in (result["note"] or "")
    assert "more" in path.read_text(encoding="utf-8")


def test_non_context_files_are_not_gated(tmp_path: Path) -> None:
    path = tmp_path / "REFERENCE.md"
    path.write_text(
        "**Phase:** round 11\n**Last session:** 2026-08-23 (round 10)\n",
        encoding="utf-8",
    )

    result = replace_once(path, anchor="round 11", replacement="round 12")

    assert result["note"] is None


def test_cli_refuses_the_defect_state_with_nonzero_exit(
    tmp_path: Path, capsys
) -> None:
    path = record(tmp_path, INCOHERENT)

    code = main(
        [
            "set-field",
            "--file",
            str(path),
            "--field",
            "Phase",
            "--value",
            "Round 11 closed",
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "header incoherent" in captured.err


def test_cli_success_reports_line_count(tmp_path: Path, capsys) -> None:
    path = record(tmp_path)

    code = main(
        [
            "set-field",
            "--file",
            str(path),
            "--field",
            "Status",
            "--value",
            "Complete",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "changed" in captured.out and "1 replacement(s)" in captured.out
    assert "**Status:** Complete" in path.read_text(encoding="utf-8")
