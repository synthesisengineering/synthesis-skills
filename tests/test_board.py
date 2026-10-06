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


def _age(session_id, seconds):
    s = board.load(session_id)
    s.seen = time.time() - seconds
    board.save(s)


def test_tilde_relative_and_symlink_spellings_of_one_path_conflict(tmp_path, monkeypatch):
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    (tmp_path / "link").symlink_to(real)
    monkeypatch.setenv("HOME", str(tmp_path))
    board.claim("A", ["~/real/sub/**"])
    monkeypatch.chdir(tmp_path)
    for spelling in ("real/sub/x.md", str(tmp_path / "link" / "sub" / "x.md"), "~/link/sub"):
        with pytest.raises(board.ClaimConflict):
            board.claim("B", [spelling])


def test_a_star_stays_inside_its_segment_and_double_star_covers_the_subtree(tmp_path):
    board.claim("A", [f"{tmp_path}/a/*"])
    board.claim("B", [f"{tmp_path}/a/b/c"])  # `*` stops at "/"
    with pytest.raises(board.ClaimConflict):
        board.claim("C", [f"{tmp_path}/a/b"])
    board.claim("D", [f"{tmp_path}/d/**"])
    with pytest.raises(board.ClaimConflict):
        board.claim("E", [f"{tmp_path}/d/b/c"])


def test_a_claim_may_name_a_path_that_does_not_exist_yet(tmp_path):
    board.claim("A", [f"{tmp_path}/worktrees/new-feature/**"])
    with pytest.raises(board.ClaimConflict):
        board.claim("B", [f"{tmp_path}/worktrees/new-feature/README.md"])


def test_reclaiming_merges_areas(tmp_path):
    board.claim("A", [f"{tmp_path}/one/**"])
    board.claim("A", [f"{tmp_path}/two/**"])
    assert board.load("A").claims == sorted([f"{tmp_path}/one/**", f"{tmp_path}/two/**"])


def test_takeover_refuses_whole_when_a_live_session_also_overlaps_and_changes_nothing(tmp_path):
    board.claim("STALE", [f"{tmp_path}/p/a/**"])
    _age("STALE", board.STALE_SECONDS + 1)
    board.claim("LIVE", [f"{tmp_path}/p/b/**"])
    with pytest.raises(board.ClaimConflict, match="held by LIVE"):
        board.claim("NEW", [f"{tmp_path}/p/**"], take_stale=True)
    assert board.load("STALE").claims == [f"{tmp_path}/p/a/**"]  # no partial takeover


def test_taken_stale_claims_stay_on_record_and_a_second_taker_is_refused(tmp_path):
    board.claim("A", [f"{tmp_path}/p/**"])
    _age("A", board.STALE_SECONDS + 1)
    board.claim("B", [f"{tmp_path}/p/**"], take_stale=True)
    assert board.load("A").ceded == [f"{tmp_path}/p/**"]
    with pytest.raises(board.ClaimConflict, match="held by B"):
        board.claim("C", [f"{tmp_path}/p/**"], take_stale=True)


def test_a_session_with_no_recorded_time_keeps_blocking(tmp_path):
    board.claim("A", [f"{tmp_path}/p/**"])
    s = board.load("A")
    s.seen = 0
    board.save(s)
    with pytest.raises(board.ClaimConflict):
        board.claim("B", [f"{tmp_path}/p/**"], take_stale=True)


def test_a_fresh_machine_with_no_board_lists_no_sessions():
    assert board.sessions() == []


def test_a_newer_schema_is_named_not_rewritten(isolated_home, capsys):
    import json
    from synthesis import cli
    folder = isolated_home / "state" / "sessions"
    folder.mkdir(parents=True)
    newer = {"session": "N", "schema": board.SCHEMA + 1, "seen": time.time(), "claims": [], "future_field": 1}
    (folder / "N.json").write_text(json.dumps(newer))
    assert cli.main(["who"]) == 0
    assert "newer synthesis" in capsys.readouterr().out
    assert json.loads((folder / "N.json").read_text()) == newer


def test_a_shell_cannot_act_as_another_session(monkeypatch, tmp_path):
    from synthesis import cli
    board.claim("OTHER", [f"{tmp_path}/p/**"])
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "MINE")
    with pytest.raises(SystemExit, match="belongs to session MINE"):
        cli.main(["--session", "OTHER", "release"])
    assert board.load("OTHER").claims == [f"{tmp_path}/p/**"]


def test_a_claim_usage_error_reads_as_no_claim(capsys):
    from synthesis import cli
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["claim"])
    assert exit_info.value.code != 0 and "claimed" not in capsys.readouterr().out
