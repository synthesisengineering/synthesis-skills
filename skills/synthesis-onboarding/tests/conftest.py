import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ROOT = Path(__file__).resolve().parents[3]
for path in (str(SCRIPTS), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """A temporary HOME, synthesis home and git config; no real harness or terminal is reached."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SYNTHESIS_HOME", str(home / ".synthesis" / "v5"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = test@example.com\n\tname = test\n[init]\n\tdefaultBranch = main\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("SYNTHESIS_CLAUDE_BIN", "SYNTHESIS_CODEX_BIN", "SYNTHESIS_MUSE_BIN"):
        monkeypatch.setenv(key, "")
    return home
