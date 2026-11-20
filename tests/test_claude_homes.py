"""The Claude homes the config names (C2, 2026-11-20): a seat signed in to another Claude account runs from a Claude Code
configuration folder of its own, and synthesis keeps that folder as it keeps ~/.claude. Its sessions are archived; the
record an approval of its sessions is checked against resolves, from the prompt hook's note and from an older note
that names no folders; its records, settings and shell snapshots are guarded in every session, and in a session of
that home the default home's are still guarded; and the sandbox's sealed set holds its records, settings, state and
plugins. Every home here is a temporary folder: nothing signs in."""

import json
import os
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


def test_the_files_staged_from_a_seats_own_process_are_the_ones_staged_from_any_other(team, monkeypatch):
    """Setup stages Claude Code's managed settings and Codex's requirements from the sealed set, and a seat's own process
    names its folder in CLAUDE_CONFIG_DIR: staged there, they are byte for byte what the doctor, run anywhere, expects,
    so installing them never leaves the sandbox reported out of date."""
    home, folder, _ = team
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    staged = (sandbox.expected("claude"), sandbox.expected("codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(folder))
    assert (sandbox.expected("claude"), sandbox.expected("codex")) == staged
