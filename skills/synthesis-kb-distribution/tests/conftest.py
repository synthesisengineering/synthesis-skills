import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts" / "connector"))  # the kb_connector package
FIXTURE = HERE / "fixtures" / "published"
REFERENCES = "plugins/example-knowledge/skills/example-knowledge/references"


@pytest.fixture(autouse=True)
def isolated_git(tmp_path, monkeypatch):
    """Git in these tests sees no machine-wide hooks or identity, only a test author."""
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n[init]\n\tdefaultBranch = main\n",
                      encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def published(tmp_path) -> Path:
    """A writable copy of the fixture's published tree."""
    target = tmp_path / "published"
    shutil.copytree(FIXTURE, target)
    return target


@pytest.fixture
def references(published) -> Path:
    """The copy's references folder, where each published knowledge file lives."""
    return published / REFERENCES
