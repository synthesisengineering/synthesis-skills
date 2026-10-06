import json
import re
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own synthesis state and no inherited harness identity."""
    home = tmp_path / "synthesis-home"
    monkeypatch.setenv("SYNTHESIS_HOME", str(home))
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))  # no machine-wide hooks or identity
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return home


@pytest.fixture
def write_config(isolated_home):
    def write(data: dict):
        isolated_home.mkdir(parents=True, exist_ok=True)
        (isolated_home / "config.json").write_text(json.dumps(data), encoding="utf-8")
    return write


@pytest.fixture
def principal(tmp_path, monkeypatch):
    """The principal's side of an approval: they type "approve <code>" in this session, which the harness
    records in its transcript (Claude Code's format here), and the prompt hook grants it. The session is
    found the way a script run from a harness shell finds it: by its id, under the harness's own folder."""
    record = tmp_path / "claude-config" / "projects" / "-work" / "S-principal.jsonl"
    record.parent.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-config"))
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-principal")

    def approve(reason: str, prompt: str = "approve {code}", grant: bool = True):
        from synthesis import approvals
        code = re.search(r"\bcode ([a-z0-9]{6})\b", reason).group(1)
        when = (datetime.now(timezone.utc) + timedelta(milliseconds=5)).isoformat()
        with record.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "user", "timestamp": when, "origin": {"kind": "human"}, "sessionId": "S-principal",
                                     "message": {"role": "user", "content": prompt.format(code=code)}}) + "\n")
        return approvals.grant_from_prompt(prompt.format(code=code)) if grant else code

    approve.transcript = record
    return approve
