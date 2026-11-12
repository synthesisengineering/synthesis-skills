"""Outgoing attachments are staged in the outbox before a send is filed: the sending reference says so, and why.

Its words are held to the code that enforces them, so the two cannot drift apart: the folder it names is the one
`synthesis.paths.outbox()` gives, and the tools, keys and refusal it quotes are the send guard's own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parents[1]))  # the plugin root, which holds synthesis/
from synthesis import guards, paths  # noqa: E402

REFERENCE = (SKILL / "references" / "gates-and-sending.md").read_text(encoding="utf-8")
FLAT = " ".join(REFERENCE.split())  # the reference wraps its lines


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A temporary home, and none of the connector's settings inherited from the machine the tests run on."""
    for key in ("SYNTHESIS_HOME", "ALLOWED_FILE_DIRS", "WORKSPACE_ATTACHMENT_DIR"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_the_sending_reference_says_to_stage_every_attachment_in_the_outbox_and_why() -> None:
    assert "Stage every file attachment in the outbox before filing the send" in FLAT
    for reason in ("reads a local file only from", "`ALLOWED_FILE_DIRS`", "after the principal approved the call",
                   "that approval and a second one", "sends the message without the second"):
        assert reason in FLAT, reason
    listed = REFERENCE.split("\n## ", 1)[0]  # the reference's own contents list, above its first section
    assert "Attachments: stage the file in the outbox first" in listed
    assert "\n## Attachments: stage the file in the outbox first\n" in REFERENCE


def test_the_folder_the_reference_names_is_the_one_the_code_uses(home, monkeypatch) -> None:
    assert paths.outbox() == home / ".synthesis" / "v5" / "outbox" and "`~/.synthesis/v5/outbox`" in REFERENCE
    monkeypatch.setenv("SYNTHESIS_HOME", str(home / "elsewhere"))
    assert paths.outbox() == home / "elsewhere" / "outbox" and "`$SYNTHESIS_HOME/outbox`" in REFERENCE


def test_the_tools_keys_and_refusal_the_reference_quotes_are_the_guards(home) -> None:
    outside = home / "scratch" / "plan.pdf"
    outside.parent.mkdir()
    outside.write_bytes(b"%PDF-1.4\n")
    for tool in sorted(guards.FILE_MAIL_TOOLS):
        assert f"`{tool}`" in REFERENCE
        for key in guards.FILE_KEYS:
            assert f"`{key}`" in REFERENCE
            problems = guards.message_problems(f"mcp__workspace-mcp__{tool}", {"attachments": [{key: str(outside)}]}, {})
            assert len(problems) == 1, problems
            for words in ("is outside the folders the mail connector reads", "copy the file into", "file this send again"):
                assert words in problems[0] and words in FLAT, words
    for unaffected in ("`content`", "`url`"):  # what needs no staging
        assert unaffected in REFERENCE


def test_skill_md_points_at_the_section_and_keeps_its_size() -> None:
    skill = (SKILL / "SKILL.md").read_bytes()
    contents = skill.decode("utf-8").split("## Contents", 1)[1].split("\n## ", 1)[0]
    assert "staging attachments in the outbox" in " ".join(contents.split())
    assert len(skill) <= 8000
