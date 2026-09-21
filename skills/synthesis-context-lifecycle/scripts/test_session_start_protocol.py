"""The Session Start Protocol names the session after the project.

2026-09-21: Rajiv asked that a session working a project set its own
title to the project id on clients that support rename, so the thread
list reads as the work queue.
"""
from pathlib import Path


def test_session_start_protocol_names_the_session_after_the_project() -> None:
    skill = Path(__file__).resolve().parents[1] / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "Name this session after the project" in text
    assert "set_session_title" in text
