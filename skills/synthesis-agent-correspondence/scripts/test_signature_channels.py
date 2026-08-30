"""The signature-link channel contract (v3.1.0) stays in the doctrine.

Motivating incident (2026-08-29): a markdown-authored persona signature
reached Gmail as a plain-text body; the recipient saw the persona name
followed by a provider-redirect URL in parentheses — neither the named
link nor a clean URL.
"""
from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


def test_named_hyperlink_rule_present() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "Signature links render natively per channel" in text
    assert "named hyperlink on every channel that can" in text
    assert "last-resort fallback" in text


def test_email_html_never_markdown() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "Email renders HTML, never markdown" in text
    assert '<a href="https://example.com/">Name</a>' in text
    assert "markdown reaching an email body as a defect" in text


def test_fallback_and_notation_distinction() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "Name (example.com)" in text
    assert "notation" in text and "wire format is the channel's own" in text


def test_send_path_byte_faithfulness_rule() -> None:
    """v3.1.1: a provider-composed send path rewrote clean hrefs into
    expiring redirects at ingestion; the byte-faithful raw path did not.
    Verified by raw-MIME read-back of two drafts, 2026-08-29."""
    text = SKILL.read_text(encoding="utf-8")
    assert "The send path is part of the channel" in text
    assert "raw MIME stores the bytes you" in text
    assert "reading the stored message back in raw form" in text
