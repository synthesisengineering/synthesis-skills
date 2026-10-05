"""R2: parallel sessions."""

import time

import pytest

from synthesis import board


def test_overlapping_claim_is_refused_with_the_holders_name_and_goal(tmp_path):
    repo = tmp_path / "repo"
    (repo / "projects" / "alpha").mkdir(parents=True)
    board.claim("A", [f"{repo}/projects/alpha/**"], project="alpha", goal="write the plan", harness="codex")
    with pytest.raises(board.ClaimConflict, match="held by A .*write the plan"):
        board.claim("B", [str(repo / "projects" / "alpha" / "CONTEXT.md")])
    board.claim("B", [f"{repo}/projects/beta/**"])  # disjoint claims coexist


def test_parent_subtree_claim_overlaps_a_child_claim(tmp_path):
    board.claim("A", [str(tmp_path / "x" / "file.md")])
    with pytest.raises(board.ClaimConflict):
        board.claim("B", [f"{tmp_path}/x/**"])


def test_sibling_names_with_a_shared_prefix_do_not_overlap(tmp_path):
    board.claim("A", [f"{tmp_path}/feature/**"])
    board.claim("B", [f"{tmp_path}/feature-sibling/**"])


def test_stale_claim_is_taken_over_only_on_request_and_the_holder_is_told(tmp_path):
    board.claim("A", [f"{tmp_path}/p/**"])
    old = board.load("A")
    old.seen = time.time() - board.STALE_SECONDS - 1
    board.save(old)
    with pytest.raises(board.ClaimConflict, match="stale, retry with --take"):
        board.claim("B", [f"{tmp_path}/p/**"])
    board.claim("B", [f"{tmp_path}/p/**"], take_stale=True)
    assert board.load("A").claims == []
    assert "Took over" in board.inbox("A")[0]["text"]


def test_messages_reach_sessions_and_projects_once(tmp_path):
    board.touch("A", project="alpha")
    board.message("A", "B", "direct")
    board.message("project:alpha", "B", "to the project")
    assert [m["text"] for m in board.inbox("A", "alpha", mark_read=True)] == ["direct", "to the project"]
    assert board.inbox("A", "alpha") == []


def test_who_reads_only_small_per_session_files(tmp_path, isolated_home):
    for i in range(50):
        board.claim(f"S{i}", [f"{tmp_path}/area{i}/**"])
    start = time.perf_counter()
    assert len(board.sessions()) == 50
    assert time.perf_counter() - start < 0.2
    assert all(f.stat().st_size < 2000 for f in (isolated_home / "state" / "sessions").glob("*.json"))


def test_release_drops_claims():
    board.claim("A", ["/tmp/one", "/tmp/two"])
    board.release("A", [board.load("A").claims[0]])
    assert len(board.load("A").claims) == 1
    board.release("A")
    assert board.load("A").claims == []
