"""R3: browser actions run in the Chrome profile of the session's workspace. One Chrome extension serves every
session and acts in whichever browser was selected last; on 2026-10-21 a session worked 15 minutes, a public post
included, in another workspace's profile after another session's selection."""

import json

import pytest

from synthesis import board, guards, paths

PERSONAL, CLIENT = "DEV-PERSONAL-0001", "DEV-CLIENT-0002"


@pytest.fixture
def setup(tmp_path):
    dirs = {name: tmp_path / name for name in ("personal", "clientco", "elsewhere")}
    for d in dirs.values():
        d.mkdir()
    config = {"browser_routing": {"workspaces": {
        str(dirs["personal"]): {"device": PERSONAL, "label": "personal"},
        str(dirs["clientco"]): {"device": CLIENT, "label": "ClientCo"}}}}
    board.touch("S1", cwd=str(dirs["personal"]))
    board.touch("S2", cwd=str(dirs["clientco"]))
    return dirs, config


def _transcript(path, *calls):
    """A Claude Code transcript with select_browser calls: (id, device, result text or None, is_error)."""
    lines = []
    for ident, device, text, error in calls:
        lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": ident,
                      "name": guards.BROWSER + "select_browser", "input": {"deviceId": device}}]}})
        if text is not None:
            lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": ident,
                          "is_error": error, "content": [{"type": "text", "text": text}]}]}})
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return str(path)


def _call(tool, tool_input, config, cwd, session):
    return guards.check(guards.BROWSER + tool, tool_input, config, cwd=str(cwd), session=session)


def test_without_browser_routing_nothing_is_checked(setup, tmp_path):
    dirs, _ = setup
    assert _call("navigate", {"url": "https://example.com"}, {}, dirs["personal"], {"session_id": "S1"}) is None


def test_a_browser_call_waits_for_this_sessions_own_selection(setup, tmp_path):
    dirs, config = setup
    me = {"session_id": "S1", "transcript_path": _transcript(tmp_path / "t1.jsonl")}
    assert "No browser is selected for this session" in _call("navigate", {}, config, dirs["personal"], me)
    assert _call("list_connected_browsers", {}, config, dirs["personal"], me) is None


def test_another_workspaces_browser_and_switch_browser_are_refused(setup, tmp_path):
    dirs, config = setup
    me = {"session_id": "S1"}
    assert f"This session's browser is personal ({PERSONAL})" in _call("select_browser", {"deviceId": CLIENT}, config, dirs["personal"], me)
    assert f"deviceId {PERSONAL}" in _call("switch_browser", {}, config, dirs["personal"], me)


def test_a_selection_counts_once_the_transcript_shows_it_succeeded(setup, tmp_path):
    dirs, config = setup
    pending = _transcript(tmp_path / "t1.jsonl", ("toolu_1", PERSONAL, None, False))
    me = {"session_id": "S1", "transcript_path": pending}
    assert _call("select_browser", {"deviceId": PERSONAL}, config, dirs["personal"], me) is None
    assert "has not reported success" in _call("navigate", {}, config, dirs["personal"], me)  # no result yet
    _transcript(tmp_path / "t1.jsonl", ("toolu_1", PERSONAL, "Browser not connected", True))
    assert "has not reported success" in _call("navigate", {}, config, dirs["personal"], me)
    _transcript(tmp_path / "t1.jsonl", ("toolu_1", PERSONAL, "Browser not connected", True),
                ("toolu_2", PERSONAL, 'Selected browser "Browser 1".', False))
    assert _call("navigate", {}, config, dirs["personal"], me) is None
    assert paths.read_json(paths.state() / "browser.json")["confirmed"] is True
    assert _call("computer", {"action": "screenshot"}, config, dirs["personal"], me) is None


def test_another_sessions_selection_rearms_the_guard(setup, tmp_path):
    dirs, config = setup
    mine = {"session_id": "S1", "transcript_path": _transcript(
        tmp_path / "t1.jsonl", ("toolu_1", PERSONAL, 'Selected browser "Browser 1".', False))}
    theirs = {"session_id": "S2", "transcript_path": _transcript(
        tmp_path / "t2.jsonl", ("toolu_9", CLIENT, 'Selected browser "Browser 2".', False))}
    assert _call("select_browser", {"deviceId": PERSONAL}, config, dirs["personal"], mine) is None
    assert _call("navigate", {}, config, dirs["personal"], mine) is None
    assert _call("select_browser", {"deviceId": CLIENT}, config, dirs["clientco"], theirs) is None
    assert "made by session S2, at" in _call("navigate", {}, config, dirs["personal"], mine)
    assert _call("select_browser", {"deviceId": PERSONAL}, config, dirs["personal"], mine) is None
    assert _call("navigate", {}, config, dirs["personal"], mine) is None


def test_the_workspace_is_the_one_the_session_started_in(setup, tmp_path):
    dirs, config = setup
    me = {"session_id": "S1"}  # started in personal, now working in a client folder
    assert _call("select_browser", {"deviceId": PERSONAL}, config, dirs["clientco"], me) is None
    assert f"Select {PERSONAL} instead" in _call("select_browser", {"deviceId": CLIENT}, config, dirs["clientco"], me)
    assert _call("navigate", {}, config, dirs["elsewhere"], {"session_id": "S3"}) is None  # in no workspace


def test_a_malformed_map_a_missing_device_or_an_unreadable_config_blocks(setup):
    dirs, _ = setup
    me = {"session_id": "S1"}
    assert "needs a \"workspaces\" map" in _call("navigate", {}, {"browser_routing": []}, dirs["personal"], me)
    bare = {"browser_routing": {"workspaces": {str(dirs["personal"]): {"label": "personal"}}}}
    assert "names no browser" in _call("navigate", {}, bare, dirs["personal"], me)
    assert guards.guarded(guards.BROWSER + "navigate")
