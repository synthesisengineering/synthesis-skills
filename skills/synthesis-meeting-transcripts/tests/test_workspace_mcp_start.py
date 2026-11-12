"""start.sh starts the server with the synthesis outbox among the folders it may read.

workspace-mcp reads a local file (a mail attachment given as a path, a Drive upload from a path) only from its
own attachment folder and the folders ALLOWED_FILE_DIRS names. An agent stages outgoing attachments in one
folder, the synthesis outbox, so start.sh makes that folder and names it there.

No server is started: a stand-in `uvx` in a temporary HOME records what it was started with and exits.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
START = SKILL / "optional-workspace-mcp" / "start.sh"


def executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def start(tmp_path: Path, foreground: bool = True, **extra: str):
    """Run start.sh under /bin/bash; returns (its result, the environment the server got, its arguments)."""
    home, record = tmp_path / "home", tmp_path / "started"
    executable(home / ".local" / "bin" / "uvx",
               f'env > "{record}.env"\nprintf "%s\\n" "$*" > "{record}.args"\n: > "{record}.done"\n')
    # By hand, start.sh waits two seconds before it looks at the server: wait for the record instead.
    executable(home / ".local" / "bin" / "sleep", f'while [ ! -f "{record}.done" ]; do /bin/sleep 0.05; done\n')
    secret = tmp_path / "client-secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    environment = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                   "XDG_STATE_HOME": str(tmp_path / "state"), "GOOGLE_CLIENT_SECRET_PATH": str(secret),
                   "WORKSPACE_MCP_FOREGROUND": "1" if foreground else "0", **extra}
    for name in ("env", "args", "done"):  # a run before this one in the same test
        Path(f"{record}.{name}").unlink(missing_ok=True)
    result = subprocess.run(["/bin/bash", str(START)], env=environment, text=True, capture_output=True, check=False,
                            timeout=30)
    lines = Path(f"{record}.env").read_text(encoding="utf-8").splitlines()
    served = dict(line.split("=", 1) for line in lines if "=" in line)
    return result, served, Path(f"{record}.args").read_text(encoding="utf-8")


def test_the_server_is_started_with_the_outbox_made_and_allowed(tmp_path: Path) -> None:
    outbox = tmp_path / "home" / ".synthesis" / "v5" / "outbox"
    result, served, arguments = start(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert outbox.is_dir()
    assert served["ALLOWED_FILE_DIRS"] == str(outbox)
    # and nothing else about the start changes
    assert arguments.startswith("workspace-mcp --single-user --transport streamable-http --tool-tier complete")
    assert served["WORKSPACE_MCP_PORT"] == "8765" and served["OAUTHLIB_INSECURE_TRANSPORT"] == "1"


def test_a_server_started_by_hand_gets_the_same(tmp_path: Path) -> None:
    """Without a supervisor start.sh puts the server in the background; the stand-in exits at once, so start.sh
    may say it failed to start. What it was started with is what is under test."""
    outbox = tmp_path / "home" / ".synthesis" / "v5" / "outbox"
    _, served, arguments = start(tmp_path, foreground=False)
    assert outbox.is_dir() and served["ALLOWED_FILE_DIRS"] == str(outbox)
    assert arguments.startswith("workspace-mcp --single-user")


def test_the_outbox_follows_the_synthesis_home(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    result, served, _ = start(tmp_path, SYNTHESIS_HOME=str(elsewhere))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (elsewhere / "outbox").is_dir() and served["ALLOWED_FILE_DIRS"] == str(elsewhere / "outbox")
    assert not (tmp_path / "home" / ".synthesis").exists()


def test_folders_already_allowed_are_kept_and_the_outbox_is_named_once(tmp_path: Path) -> None:
    outbox = tmp_path / "home" / ".synthesis" / "v5" / "outbox"
    _, served, _ = start(tmp_path, ALLOWED_FILE_DIRS="/srv/reports:/srv/exports")
    assert served["ALLOWED_FILE_DIRS"] == f"/srv/reports:/srv/exports:{outbox}"
    _, served, _ = start(tmp_path, ALLOWED_FILE_DIRS=f"/srv/reports:{outbox}")
    assert served["ALLOWED_FILE_DIRS"] == f"/srv/reports:{outbox}"
    _, served, _ = start(tmp_path, ALLOWED_FILE_DIRS="")
    assert served["ALLOWED_FILE_DIRS"] == str(outbox)


def test_a_server_still_starts_when_the_outbox_cannot_be_made(tmp_path: Path) -> None:
    """The server does much besides mail: it starts, start.sh says what it could not make, and the folder is
    still named so a later mkdir is enough."""
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the synthesis home would be\n", encoding="utf-8")
    result, served, arguments = start(tmp_path, SYNTHESIS_HOME=str(blocked))
    assert result.returncode == 0, result.stdout + result.stderr
    assert arguments.startswith("workspace-mcp --single-user")
    assert served["ALLOWED_FILE_DIRS"] == str(blocked / "outbox")
    assert str(blocked / "outbox") in result.stderr and "could not" in result.stderr


@pytest.mark.parametrize("document", ["references/setup.md", "optional-workspace-mcp/README.md"])
def test_the_setup_documents_say_what_the_start_script_exports_and_it_does(document: str, tmp_path: Path) -> None:
    text = " ".join((SKILL / document).read_text(encoding="utf-8").split())  # the documents wrap their lines
    for said in ("`ALLOWED_FILE_DIRS`", "added to whatever the variable already holds", "`~/.synthesis/v5/outbox`",
                 "`$SYNTHESIS_HOME/outbox`", "`WORKSPACE_ATTACHMENT_DIR`", "`~/.workspace-mcp/attachments`",
                 "keeps the folders it was started with", "`synthesis doctor`"):
        assert said in text, said
    # and the script does what they say
    _, served, _ = start(tmp_path, ALLOWED_FILE_DIRS="/srv/reports")
    assert served["ALLOWED_FILE_DIRS"] == f"/srv/reports:{tmp_path / 'home' / '.synthesis' / 'v5' / 'outbox'}"
    _, served, _ = start(tmp_path, SYNTHESIS_HOME=str(tmp_path / "elsewhere"))
    assert served["ALLOWED_FILE_DIRS"] == str(tmp_path / "elsewhere" / "outbox")


def test_skill_md_says_where_to_read_it_and_keeps_its_size() -> None:
    skill = (SKILL / "SKILL.md").read_bytes()
    contents = " ".join(skill.decode("utf-8").split("## Contents", 1)[1].split("\n## ", 1)[0].split())
    assert "what `start.sh` sets for the server" in contents and len(skill) <= 8000
