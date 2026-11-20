"""The Claude homes the config names (C2, 2026-11-20): a seat signed in to another Claude account runs from a Claude Code
configuration folder of its own, and synthesis keeps that folder as it keeps ~/.claude. Its sessions are archived; the
record an approval of its sessions is checked against resolves, from the prompt hook's note and from an older note
that names no folders; its records, settings and shell snapshots are guarded in every session, and in a session of
that home the default home's are still guarded; and the sandbox's sealed set holds its records, settings, state and
plugins. Every home here is a temporary folder: nothing signs in."""

import json
import re

import pytest

from synthesis import approvals, guards, paths, sandbox, sessions


@pytest.fixture
def team(tmp_path, monkeypatch, write_config):
    """A home folder whose config names ~/.claude-team as another Claude account's folder, with a team workspace."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))  # `~` in the config, and ~/.claude, are this test's, never the machine's
    write_config({"claude_homes": ["~/.claude-team"], "workspace_roots": [str(home / "workspaces" / "*")]})
    folder, space = home / ".claude-team", home / "workspaces" / "team"
    (folder / "projects").mkdir(parents=True)
    space.mkdir(parents=True)
    return home, folder, space


def _record(folder, space, sid: str):
    """A session's transcript where Claude Code keeps it in a configuration folder, holding one prompt typed there."""
    path = folder / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(space)) / f"{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "user", "cwd": str(space), "sessionId": sid, "timestamp": "2026-11-20T09:00:00.000Z",
                                "message": {"role": "user", "content": "Read the team page."}}) + "\n", encoding="utf-8")
    return path


def test_the_archive_copies_the_sessions_of_each_claude_home_the_config_names(team):
    home, folder, space = team
    record = _record(folder, space, "TEAM1")
    assert ("claude-code", record) in sessions.natives()
    sessions.export()
    assert list((paths.sessions() / "team").glob("*/claude-code-TEAM1")), "the team seat's session is not in the archive"


def test_a_config_the_archive_cannot_read_is_named_never_passed_over(team):
    """A run that cannot know every Claude home is no complete run (2026-11-12: a run stamped complete over a folder it
    could not list)."""
    paths.config_file().write_text("{not json", encoding="utf-8")
    unread = []
    sessions.natives(0, unread)
    assert any("Claude homes" in why for _, _, why in unread), unread


def test_the_record_a_claude_homes_session_is_checked_against_resolves(team, tmp_path, monkeypatch):
    """The prompt hook's note names the folders each harness keeps records in, each Claude home the config names among
    them, whatever folder this process's environment names; an older note that names none is read against the
    account's own home, never HOME, which a command sets (A9)."""
    home, folder, space = team
    record = _record(folder, space, "TEAM2")
    approvals.remember("TEAM2", str(record))  # this process's CLAUDE_CONFIG_DIR names another folder
    assert approvals.transcript({"session_id": "TEAM2"}) == str(record)
    account = tmp_path / "account"
    monkeypatch.setattr(paths, "account_home", lambda: account)
    older = _record(account / ".claude-team", space, "TEAM3")
    paths.write_json(paths.approvals() / "records" / "TEAM3.json", {"path": str(older)})  # 5.23's note: no folders
    assert approvals.transcript({"session_id": "TEAM3"}) == str(older)


def test_a_claude_homes_records_settings_and_snapshots_are_guarded_as_the_default_homes_are(team, tmp_path, monkeypatch):
    home, folder, space = team
    config, me = paths.config(), {"session_id": "S1"}

    def write(path):
        return guards.check("Write", {"file_path": str(path), "content": "x"}, config, cwd=str(tmp_path), session=me) or ""
    assert "session transcripts" in write(_record(folder, space, "TEAM4"))
    assert write(folder / "projects" / "-team" / "memory" / "notes.md") == ""  # the agent's own notes, as in ~/.claude
    for kept in (folder / "settings.json", folder / "settings.local.json", folder / "shell-snapshots" / "snapshot-zsh-1.sh"):
        assert "approve followed by the code" in write(kept), kept
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))  # a session of that home: the default home is still guarded
    assert "session transcripts" in write(home / ".claude" / "projects" / "-team" / "S9.jsonl")
    assert "approve followed by the code" in write(home / ".claude" / "settings.json")


def test_the_sealed_set_holds_each_claude_home_the_config_names(team, monkeypatch):
    """Claude Code's managed settings and Codex's requirements are staged from the one sealed set, so a Claude home the
    config names is sealed as ~/.claude is; staged from a session of that home, ~/.claude stays in it."""
    home, folder, _ = team
    sealed = {p: (whole, only) for p, whole, only in sandbox.sealed()}
    assert sealed[folder / "projects"] == (True, True) and sealed[folder / "plugins"] == (True, False)
    assert all(sealed[folder / name] == (False, False) for name in ("settings.json", "settings.local.json", ".claude.json"))
    managed = sandbox.claude_managed()
    assert "~/.claude-team/projects" in managed["sandbox"]["filesystem"]["denyWrite"]
    assert {"Edit(~/.claude-team/settings.json)", "Edit(~/.claude-team/.claude.json)", "Edit(~/.claude-team/plugins/**)"} <= set(
        managed["permissions"]["deny"])
    assert (folder, "read") in sandbox.codex_rules()
    assert (folder / "settings.json", None) in sandbox._claude_settings()  # its sandbox exceptions are read for the seal
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    assert {home / ".claude" / "projects", home / ".claude" / "settings.json", home / ".claude.json"} <= {p for p, _, _ in sandbox.sealed()}


# Review round 1, B1: one value that names no folder, or a config that will not parse, dropped every other Claude folder
# from the guard (from a default session the seat's transcript, settings and shell snapshot took writes with no code;
# from the seat, ~/.claude did). Every value that parses is kept, with ~/.claude wherever the config names a Claude home,
# and while the config cannot be read the guard keeps the folders the last config it could read named.
TYPO = {"claude_homes": ["~/.claude-team"], "browser_routing": {"workspaces": {
    "~/workspaces/team": {"device": "DEV-TEAM-0002", "label": "team", "claude_home": "~/.claude-team"},
    "~/workspaces/other": {"device": "DEV-OTHER-0003", "label": "other", "claude_home": ".claude-other"}}}}  # no ~/: a typo


def _other(home, folder, monkeypatch, seat: bool):
    """The other Claude folder of this process: the team folder from a default session, ~/.claude from the seat's own."""
    if seat:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
        return home / ".claude"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    return folder


def _kept(other):
    """What of a Claude folder only the guard keeps from a file tool, with what its answer says."""
    return [(other / "projects" / "-team" / "S9.jsonl", "session transcripts"), (other / "settings.json", "approve followed by the code"),
            (other / "shell-snapshots" / "snapshot-zsh-1.sh", "approve followed by the code")]


def _hooked(payload: dict, capsys) -> str:
    """Why the PreToolUse hook holds a call, as it prints it; "" for a call it lets through."""
    from synthesis import hook
    hook.pre_tool_use(payload)
    out = capsys.readouterr().out
    return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out.strip() else ""


@pytest.mark.parametrize("seat", [False, True])
def test_a_claude_home_that_names_no_folder_drops_no_other_folder_from_the_guard(team, monkeypatch, write_config, tmp_path, seat):
    home, folder, _ = team
    config = json.loads(json.dumps(TYPO))
    write_config(config)
    other = _other(home, folder, monkeypatch, seat)
    for target, said in _kept(other):
        assert said in (guards.check("Write", {"file_path": str(target), "content": "x"}, config, cwd=str(tmp_path),
                                     session={"session_id": "S1"}) or ""), target


@pytest.mark.parametrize("seat", [False, True])
def test_a_config_that_will_not_parse_keeps_the_folders_the_last_readable_one_named(team, monkeypatch, write_config, capsys, seat):
    """The hook judges a file tool without a config it cannot parse (22.20); the Claude folders it guards then come from
    the last config it read in full, kept in the sealed approvals folder."""
    home, folder, space = team
    other, call = _other(home, folder, monkeypatch, seat), {"session_id": "S1", "cwd": str(space)}
    assert _hooked({"tool_name": "Read", "tool_input": {"file_path": "/dev/null"}, **call}, capsys) == ""  # read in full
    paths.config_file().write_text("{not json", encoding="utf-8")
    for target, said in _kept(other):
        assert said in _hooked({"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "{\"disableAllHooks\": true}"},
                                **call}, capsys), target


@pytest.mark.parametrize("seat", [False, True])
def test_a_config_never_read_in_full_falls_back_to_no_folder_alone(team, monkeypatch, capsys, seat):
    """With no config read in full yet, so no record, a config that will not parse still leaves the guard more than this
    process's own folder: ~/.claude, and each ~/.claude* folder in the home, which is how another account's is named."""
    home, folder, space = team
    other, call = _other(home, folder, monkeypatch, seat), {"session_id": "S1", "cwd": str(space)}
    paths.config_file().write_text("{not json", encoding="utf-8")
    for target, said in _kept(other):
        assert said in _hooked({"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "x"}, **call}, capsys), target
    assert not (paths.approvals() / paths.HOMES_KEPT).exists()  # nothing was read in full, so nothing was recorded


@pytest.mark.parametrize("seat", [False, True])
def test_with_a_claude_home_that_names_no_folder_the_sealed_set_still_holds_every_folder(team, monkeypatch, write_config, seat):
    home, folder, _ = team
    write_config(json.loads(json.dumps(TYPO)))
    _other(home, folder, monkeypatch, seat)
    managed = sandbox.claude_managed()
    assert {"Edit(~/.claude/settings.json)", "Edit(~/.claude-team/settings.json)"} <= set(managed["permissions"]["deny"])
    assert {"~/.claude/projects", "~/.claude-team/projects"} <= set(managed["sandbox"]["filesystem"]["denyWrite"])


def test_another_spelling_or_a_link_of_the_default_folder_is_never_a_second_folder(team, monkeypatch):
    """N2 of review round 1: the default folder was told apart by spelling, while the guard compares real paths with case
    folded, so ~/.Claude, or a link to ~/.claude, passed for another account's folder."""
    home, _, _ = team
    (home / ".claude").mkdir()
    (home / ".claude-link").symlink_to(home / ".claude", target_is_directory=True)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    for named in ("~/.Claude", "~/.claude-link"):
        with pytest.raises(ValueError, match="~/.claude, the default home"):
            paths.claude_homes({"claude_homes": [named]})
        assert paths.claude_dirs({"claude_homes": [named]}) == [home / ".claude"]
    assert paths.claude_homes({"claude_homes": ["~/.claude-team", "~/.Claude-Team"]}) == [home / ".claude-team"]  # one folder


def test_the_files_staged_from_a_seats_own_process_are_the_ones_staged_from_any_other(team, monkeypatch):
    """Setup stages Claude Code's managed settings and Codex's requirements from the sealed set, and a seat's own process
    names its folder in CLAUDE_CONFIG_DIR: staged there, they are byte for byte what the doctor, run anywhere, expects,
    so installing them never leaves the sandbox reported out of date."""
    home, folder, _ = team
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    staged = (sandbox.expected("claude"), sandbox.expected("codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    assert (sandbox.expected("claude"), sandbox.expected("codex")) == staged
