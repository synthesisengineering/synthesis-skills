import json

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
