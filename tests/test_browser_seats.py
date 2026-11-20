"""A seat signed in to another Claude account (C2, 2026-11-20). Claude Code reaches only the browsers whose extension is
signed in to its own Claude account, so a workspace whose Chrome profile is paired with another account is worked from
a Claude Code configuration folder of its own (`CLAUDE_CONFIG_DIR`), signed in to that account. A `browser_routing`
entry's `claude_home` binds the workspace's browser to the sessions of that folder: only they drive its device, they
drive no other entry's, each Claude home keeps its own latest selection, since one account's extension pairing cannot
move another's, and a session's home is read from where the hook payload's transcript lies, never from a variable a
command sets. Every home here is a temporary folder and every transcript a made-up file: no login, browser or secret."""

import json
import os
import re
from pathlib import Path

import pytest

from synthesis import board, guards, paths

PERSONAL, TEAM = "DEV-PERSONAL-0001", "DEV-TEAM-0002"
TEAM_LABEL = "the team Chrome profile, me@team.example, driven only by the team-account seat (~/.claude-team)"
PAGE = {"url": "https://example.com/next"}


@pytest.fixture
def seat(tmp_path, monkeypatch):
    """A home folder with a personal, a team and an unmapped workspace; the default Claude home the conftest names; and
    two more Claude homes: ~/.claude-team, which the team workspace's entry binds (named there alone, as the evaluation's
    lines name it), and ~/.claude-spare, which claude_homes lists and no entry binds."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))  # `~` in the config, and ~/.claude, are this test's, never the machine's
    spaces = {name: home / "workspaces" / name for name in ("personal", "team", "other")}
    for folder in spaces.values():
        folder.mkdir(parents=True)
    homes = {"default": Path(os.environ["CLAUDE_CONFIG_DIR"]), "team": home / ".claude-team", "spare": home / ".claude-spare"}
    config = {"claude_homes": ["~/.claude-spare"],
              "browser_routing": {"workspaces": {
                  "~/workspaces/personal": {"device": PERSONAL, "label": "the personal Chrome profile"},
                  "~/workspaces/team": {"device": TEAM, "label": TEAM_LABEL, "claude_home": "~/.claude-team",
                                        "accounts": {"assistant.example": "me@team.example"}}}}}
    return spaces, homes, config


def _in(folder: Path, started: Path, sid: str) -> Path:
    """Where Claude Code keeps a session's transcript in a configuration folder: projects/<its start folder>/<id>.jsonl."""
    return folder / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(started)) / f"{sid}.jsonl"


def _write(record: Path, calls) -> None:
    """A Claude Code transcript with select_browser calls: (id, device, the result's text or None, is_error)."""
    lines = []
    for ident, device, text, error in calls:
        lines.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": ident,
                      "name": guards.BROWSER + "select_browser", "input": {"deviceId": device}}]}})
        if text is not None:
            lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": ident,
                          "is_error": error, "content": [{"type": "text", "text": text}]}]}})
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def _session(sid: str, started: Path, record: Path, *calls) -> dict:
    """A session that started in `started`, whose hook payload names `record` as its transcript."""
    board.touch(sid, cwd=str(started))
    _write(record, calls)
    return {"session_id": sid, "transcript_path": str(record)}


def _call(tool: str, given: dict, config: dict, cwd: Path, session: dict):
    return guards.check(guards.BROWSER + tool, given, config, cwd=str(cwd), session=session)


def _drives(session: dict, device: str, config: dict, cwd: Path, ident: str = "toolu_1") -> None:
    """The session selects its device, its record shows that selection succeeded, and a page call passes."""
    assert _call("select_browser", {"deviceId": device}, config, cwd, session) is None
    _write(Path(session["transcript_path"]), [(ident, device, 'Selected browser "Browser 1".', False)])
    assert _call("navigate", PAGE, config, cwd, session) is None


def _homes_records() -> list:
    """What each configured Claude home's own latest-selection record holds; the default one's, browser.json, apart."""
    return [paths.read_json(p) for p in sorted((paths.approvals() / "browser-homes").glob("*.json"))]


def test_only_the_seats_sessions_drive_its_workspaces_browser_and_any_other_is_told_to_hand_the_task_over(seat):
    """(a) Today's refusal tells a session of another account to select a device it cannot see. Bound, the workspace
    refuses any other session before it selects, names the handoff and prints the entry's label: a session of the
    default home, of the desktop app's agent mode, of an unbound Claude home and of Codex alike. Listing still passes."""
    spaces, homes, config = seat
    team = spaces["team"]
    desktop = Path(os.environ["SYNTHESIS_CLAUDE_DESKTOP_DIR"]) / "local-agent-mode-sessions" / "acct" / "org" / "local_s1" / ".claude"
    others = {"MINE": _in(homes["default"], team, "MINE"), "DESK": _in(desktop, team, "DESK"), "SPARE": _in(homes["spare"], team, "SPARE"),
              "CODEX": Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "11" / "20" / "rollout-2026-11-20T09-00-00-c0.jsonl"}
    for sid, record in others.items():
        other = _session(sid, team, record)
        for tool, given in (("select_browser", {"deviceId": TEAM}), ("switch_browser", {}), ("navigate", PAGE),
                            ("computer", {"action": "screenshot"})):
            said = _call(tool, given, config, team, other) or ""
            assert TEAM_LABEL in said and "~/.claude-team" in said and "synthesis msg" in said, (sid, tool, said)
        assert _call("list_connected_browsers", {}, config, team, other) is None
    assert not (paths.approvals() / "browser.json").exists() and not _homes_records()  # refused before any selected
    mine = _session("SEAT", team, _in(homes["team"], team, "SEAT"), ("toolu_1", TEAM, None, False))
    assert _call("select_browser", {"deviceId": TEAM}, config, team, mine) is None
    assert "has not reported success" in _call("navigate", PAGE, config, team, mine)  # today's rules hold for the seat
    _write(Path(mine["transcript_path"]), [("toolu_1", TEAM, 'Selected browser "Browser 2".', False)])
    assert _call("navigate", PAGE, config, team, mine) is None


def test_the_seats_sessions_drive_no_other_workspaces_browser_nor_any_from_outside_every_workspace(seat):
    """(b) A session of the bound home that started in another workspace, or outside every one, is refused, its
    listing apart, and told whose browser its home drives; one that started in the team workspace keeps it, wherever
    it works now, and may select no other device there."""
    spaces, homes, config = seat
    for where in (spaces["personal"], spaces["other"]):
        sid = f"SEAT-{where.name}"
        mine = _session(sid, where, _in(homes["team"], where, sid))
        for tool, given in (("select_browser", {"deviceId": PERSONAL}), ("select_browser", {"deviceId": TEAM}), ("navigate", PAGE)):
            said = _call(tool, given, config, where, mine) or ""
            assert "~/.claude-team" in said and TEAM_LABEL in said and "~/workspaces/team" in said, (where.name, tool, said)
        assert _call("list_connected_browsers", {}, config, where, mine) is None
    assert not (paths.approvals() / "browser.json").exists() and not _homes_records()
    mine = _session("SEAT", spaces["team"], _in(homes["team"], spaces["team"], "SEAT"))
    assert f"Select {TEAM} instead" in _call("select_browser", {"deviceId": PERSONAL}, config, spaces["team"], mine)
    _drives(mine, TEAM, config, spaces["personal"])  # started in the team workspace, working in the personal one


def test_each_claude_home_keeps_its_own_latest_selection(seat):
    """(c) One account's extension pairing cannot move another's: a selection in one Claude home never re-arms another
    home's sessions, and a record of one home never lets another home's session through. Within a home, another
    session's selection re-arms as today."""
    spaces, homes, config = seat
    team, personal = spaces["team"], spaces["personal"]
    seat_one = _session("SEAT1", team, _in(homes["team"], team, "SEAT1"))
    mine = _session("PERS1", personal, _in(homes["default"], personal, "PERS1"))
    _drives(seat_one, TEAM, config, team)
    _drives(mine, PERSONAL, config, personal)
    assert _call("navigate", PAGE, config, team, seat_one) is None  # the personal selection moved nothing of the seat's
    assert _call("navigate", PAGE, config, personal, mine) is None  # nor the seat's anything of the personal session's
    _drives(_session("PERS2", personal, _in(homes["default"], personal, "PERS2")), PERSONAL, config, personal)
    assert "made by session PERS2, at" in _call("navigate", PAGE, config, personal, mine)
    assert _call("navigate", PAGE, config, team, seat_one) is None
    _drives(_session("SEAT2", team, _in(homes["team"], team, "SEAT2")), TEAM, config, team)
    assert "made by session SEAT2, at" in _call("navigate", PAGE, config, team, seat_one)
    held, = _homes_records()
    assert held["session"] == "SEAT2" and held["home"] == os.path.realpath(homes["team"])
    assert paths.read_json(paths.approvals() / "browser.json")["session"] == "PERS2"
    record, = (paths.approvals() / "browser-homes").glob("*.json")
    paths.write_json(record, {"device": PERSONAL, "session": "PERS1", "at": 0, "confirmed": True, "home": held["home"]})
    assert "made by session PERS2, at" in _call("navigate", PAGE, config, personal, mine)


def test_the_home_is_read_from_the_payloads_transcript_never_from_an_environment_variable(seat, monkeypatch, tmp_path):
    """(d) A command can set CLAUDE_CONFIG_DIR; it cannot write the harness's hook payload. The home is where the
    payload's transcript lies, past any link, and a payload that names none, or a relative one, says no home: with a
    Claude home configured, its browser calls are refused in every workspace, its listing apart."""
    spaces, homes, config = seat
    team, personal = spaces["team"], spaces["personal"]
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(homes["team"]))
    mine = _session("MINE", team, _in(homes["default"], team, "MINE"))
    assert "synthesis msg" in (_call("select_browser", {"deviceId": TEAM}, config, team, mine) or "")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(homes["default"]))
    _drives(_session("SEAT", team, _in(homes["team"], team, "SEAT")), TEAM, config, team)
    linked = tmp_path / "linked-team"
    linked.symlink_to(homes["team"], target_is_directory=True)
    _drives(_session("SEAT3", team, _in(linked, team, "SEAT3")), TEAM, config, team, "toolu_3")
    for given in ({}, {"transcript_path": "BARE.jsonl"}):
        for where, device in ((team, TEAM), (personal, PERSONAL)):
            board.touch(f"BARE-{where.name}", cwd=str(where))
            bare = {"session_id": f"BARE-{where.name}", **given}
            said = _call("select_browser", {"deviceId": device}, config, where, bare) or ""
            assert "cannot tell which Claude home" in said, (given, where.name, said)
            assert _call("list_connected_browsers", {}, config, where, bare) is None


def test_entries_without_the_key_keep_todays_rules(seat):
    """(e) In the personal workspace, whose entry names no claude_home, a session meets today's rules in today's words:
    a session of the default home, its selection kept in browser.json as today, and one of a Claude home no entry
    binds, its selection kept in its own home's record. With no Claude home configured anywhere, a payload with no
    transcript still selects as today."""
    spaces, homes, config = seat
    personal = spaces["personal"]
    for sid, folder in (("PERS1", homes["default"]), ("SPARE1", homes["spare"])):
        me = _session(sid, personal, _in(folder, personal, sid), ("toolu_1", PERSONAL, None, False))
        assert _call("navigate", PAGE, config, personal, me) == (
            "No browser is selected for this session; the extension is shared, so its browser or tab group may have changed. Call "
            f"list_connected_browsers, then select_browser with deviceId {PERSONAL} (the personal Chrome profile), before any other browser call.")
        assert _call("select_browser", {"deviceId": "DEV-ELSE-0003"}, config, personal, me) == (
            f"This session's browser is the personal Chrome profile ({PERSONAL}), set for the workspace it started in; selecting "
            "DEV-ELSE-0003 would act as another profile. Select DEV-PERSONAL-0001 instead.")
        assert f"deviceId {PERSONAL}" in _call("switch_browser", {}, config, personal, me)
        assert _call("select_browser", {"deviceId": PERSONAL}, config, personal, me) is None
        assert "has not reported success" in _call("navigate", PAGE, config, personal, me)
        _write(Path(me["transcript_path"]), [("toolu_1", PERSONAL, 'Selected browser "Browser 1".', False)])
        assert _call("navigate", PAGE, config, personal, me) is None
    kept = paths.read_json(paths.approvals() / "browser.json")
    assert set(kept) == {"device", "session", "at", "confirmed"} and kept["session"] == "PERS1"
    held, = _homes_records()
    assert held["session"] == "SPARE1" and held["home"] == os.path.realpath(homes["spare"])
    plain = {"browser_routing": {"workspaces": {"~/workspaces/personal": {"device": PERSONAL, "label": "the personal Chrome profile"}}}}
    board.touch("BARE", cwd=str(personal))
    assert _call("select_browser", {"deviceId": PERSONAL}, plain, personal, {"session_id": "BARE"}) is None
    assert "has not reported success" in _call("navigate", PAGE, plain, personal, {"session_id": "BARE"})


def test_no_session_of_another_folder_selects_the_bound_device_wherever_it_runs(seat, tmp_path):
    """N1 of review round 1: the device was bound only inside its own workspace, so a session of another folder outside
    every workspace, or in another workspace whose entry names the same device, could select it. Only the bound home's
    sessions select it, wherever any other session runs, and that one is told to hand the task over."""
    spaces, homes, config = seat
    config["browser_routing"]["workspaces"]["~/workspaces/other"] = {"device": TEAM, "label": "a second entry for the team profile"}
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    desktop = Path(os.environ["SYNTHESIS_CLAUDE_DESKTOP_DIR"]) / "local-agent-mode-sessions" / "acct" / "org" / "local_s2" / ".claude"
    for sid, started, folder in (("DESK", outside, desktop), ("MINE", outside, homes["default"]), ("SPARE", outside, homes["spare"]),
                                 ("PERS", spaces["personal"], homes["default"]), ("OTHER", spaces["other"], homes["default"])):
        said = _call("select_browser", {"deviceId": TEAM}, config, started, _session(sid, started, _in(folder, started, sid))) or ""
        assert TEAM_LABEL in said and "~/.claude-team" in said and "synthesis msg" in said, (sid, said)
    assert not (paths.approvals() / "browser.json").exists() and not _homes_records()


@pytest.mark.parametrize("change, named", [
    (lambda c: c.update(claude_homes="~/.claude-spare"), "must be a list"),
    (lambda c: c.update(claude_homes=["relative/folder"]), "'relative/folder'"),
    (lambda c: c.update(claude_homes=["~/.claude"]), "~/.claude"),
    (lambda c: c.update(claude_homes=["~/.Claude"]), "~/.claude"),  # N2: the default folder in another spelling
    (lambda c: c["browser_routing"]["workspaces"]["~/workspaces/team"].update(claude_home=7), "7"),
    (lambda c: c["browser_routing"]["workspaces"]["~/workspaces/team"].update(claude_home=""), "''"),
])
def test_a_claude_home_that_names_no_folder_blocks_every_browser_call(seat, change, named):
    """Fail closed: a Claude home that cannot be read could bind any workspace, so no browser call is judged."""
    spaces, homes, config = seat
    change(config)
    me = _session("PERS1", spaces["personal"], _in(homes["default"], spaces["personal"], "PERS1"))
    for tool in ("list_connected_browsers", "select_browser", "navigate"):
        reason = _call(tool, {"deviceId": PERSONAL}, config, spaces["personal"], me) or ""
        assert "Claude home" in reason and named in reason and "blocked" in reason, (tool, reason)


def test_an_unreadable_selection_record_holds_the_seat(seat):
    """Fail closed: a home's record that cannot be read shows no selection, so the seat selects again."""
    spaces, homes, config = seat
    team = spaces["team"]
    mine = _session("SEAT", team, _in(homes["team"], team, "SEAT"))
    _drives(mine, TEAM, config, team)
    record, = (paths.approvals() / "browser-homes").glob("*.json")
    record.write_text("{not json", encoding="utf-8")
    assert "No browser is selected for this session" in _call("navigate", PAGE, config, team, mine)
