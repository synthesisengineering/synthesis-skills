"""Retained leaf loops are inventoried without dereference or ownership inference."""

import pytest
from test_project_state import init_repo, state


@pytest.mark.parametrize("kind", ["self", "two-member"])
def test_dirty_loop_preserves_lexical_inventory_and_attribution_requirement(
    tmp_path, kind
):
    repo, project = init_repo(tmp_path)
    first = project / "loop-a"
    if kind == "self":
        first.symlink_to("loop-a")
    else:
        first.symlink_to("loop-b")
        (project / "loop-b").symlink_to("loop-a")
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    assert report.selected_path is None
    assert any("exact attributed manifest" in issue for issue in report.issues)
    rows = [row for candidate in report.candidates for row in candidate.dirty_files]
    assert any(row["path"] == str(first) and row["kind"] == "symlink" for row in rows)
    assert first.is_symlink()
    assert first.readlink().as_posix() == ("loop-a" if kind == "self" else "loop-b")


def test_regular_dirty_evidence_keeps_exact_attribution_requirement(tmp_path):
    repo, project = init_repo(tmp_path)
    (project / "note.md").write_text("retained evidence\n")
    report = state.resolve_project("alpha", repo / "projects/index.yaml", fetch=False)
    assert report.status == "CONFLICT"
    assert any("exact attributed manifest" in issue for issue in report.issues)
