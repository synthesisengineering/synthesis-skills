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
        problems = guards.message_problems(f"mcp__workspace-mcp__{tool}", {"attachments": [{"path": str(outside)}]}, {})
        assert len(problems) == 1, problems
        for words in ("is outside the folders the mail connector reads", "copy the file into", "file this send again"):
            assert words in problems[0] and words in FLAT, words
    for named in ("`path`", "`content`", "`url`"):  # the key a file goes under, and what needs no staging
        assert named in REFERENCE


def test_the_reference_says_only_what_the_connector_reads_counts_and_its_words_for_each_entry_are_the_guards(home) -> None:
    """A file goes under `path` and no other key, and an entry the connector would not attach as given is
    refused: the reference lists each kind with the words the guard refuses it with."""
    assert "`path`, `file_path` or `filePath`" not in FLAT  # the earlier text, which had a file go under three keys
    assert "Only what the connector reads counts as attached" in FLAT
    paths.outbox().mkdir(parents=True)
    staged, secret = paths.outbox() / "plan.pdf", paths.outbox() / ".env"
    for file in (staged, secret):
        file.write_bytes(b"%PDF-1.4\n")
    said = {"has none of `path`, `content` and `url`": {"file_path": str(staged)},
            "the mail connector reads only the": {"url": "https://files.example.com/plan.pdf", "path": str(staged)},
            "gives `content` with no `filename`": {"content": "UEsDBA=="},
            "gives `content` that is not standard base64": {"filename": "plan.pdf", "content": "UEsD-A_="},
            "has an empty `url`": {"url": ""},
            "is one the mail connector never reads": {"path": str(secret)}}
    for words, entry in said.items():
        problems = guards.message_problems("mcp__workspace-mcp__send_gmail_message", {"attachments": [entry]}, {})
        assert len(problems) == 1 and words in problems[0] and words in FLAT, words
    for named in ("`file_path`", "`filePath`", "`filename`", "`data:`"):  # the keys that are not read, and what content needs
        assert named in REFERENCE, named
    alone = guards.message_problems("mcp__workspace-mcp__send_gmail_message", {"attachments": {"path": str(staged)}}, {})
    words = "is neither a list of entries nor the JSON text of one"  # one entry given bare, where the connector takes a list
    assert len(alone) == 1 and words in alone[0] and words in FLAT


def test_the_reference_names_each_drive_tool_that_reads_a_local_file_with_its_parameter_and_refusal(home) -> None:
    outside = home / "scratch" / "plan.docx"
    outside.parent.mkdir()
    outside.write_bytes(b"PK\x03\x04")
    for tool, key in guards.FILE_DRIVE_TOOLS.items():
        assert f"`{tool}`" in REFERENCE and f"`{key}`" in REFERENCE, tool
        named = outside.as_uri() if key == "fileUrl" else str(outside)
        problems = guards.message_problems(f"mcp__workspace-mcp__{tool}", {key: named}, {})
        assert len(problems) == 1, problems
        for words in ("is outside the folders the connector reads", "copy the file into", "make this call again"):
            assert words in problems[0] and words in FLAT, words
    for named in ("`file://`", "`file_url`"):  # the form a URL takes, and the parameter that is fetched and never read here
        assert named in REFERENCE, named


def test_the_reference_says_the_approval_covers_the_files_bytes_and_who_may_write_the_outbox() -> None:
    assert "not the file's bytes" not in FLAT  # the earlier text
    for said in ("The approval covers the file's bytes", "needs a new approval", "cannot be read",
                 f"{guards.HASH_SECONDS:g} seconds", "Codex", "`codex board access`", "`install-autostart.sh`", "`doctor.sh`"):
        assert said in FLAT, said


def test_skill_md_points_at_the_section_and_keeps_its_size() -> None:
    skill = (SKILL / "SKILL.md").read_bytes()
    contents = skill.decode("utf-8").split("## Contents", 1)[1].split("\n## ", 1)[0]
    assert "staging attachments in the outbox" in " ".join(contents.split())
    assert len(skill) <= 8000
