from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-message-guard/scripts"))
import message_guard as guard  # noqa: E402 - source-bound import follows path/bootstrap initialization


def request():
    return {
        "tool_name": "synthetic_email_send",
        "tool_input": {
            "to": ["recipient@example.test"],
            "subject": "Synthetic",
            "body_html": "<p>Measured result.</p>",
            "body_text": "Measured result.",
        },
        "grounding": {
            "channel": "email",
            "recipient": "recipient@example.test",
            "is_reply": False,
            "claims": [
                {"claim": "Measured result.", "source": "fixture:observation-one"}
            ],
            "no_factual_claims": False,
            "voice_rules_pass": True,
            "invented_precision_scan": True,
            "recipient_address_check": True,
            "ragbot_branding_check": True,
        },
    }


def test_digest_is_computed_from_complete_actual_payload():
    r = request()
    ledger = guard.build_grounding_envelope(r)
    assert ledger["message_sha256"] == guard.message_digest(
        r["tool_name"], r["tool_input"]
    )
    assert ledger["claims"] == r["grounding"]["claims"] and "created_at" in ledger
    r["tool_input"]["to"] = ["other@example.test"]
    assert (
        guard.build_grounding_envelope(r)["message_sha256"] != ledger["message_sha256"]
    )
    r["tool_input"]["body_text"] = "Different plain part"
    assert (
        guard.build_grounding_envelope(r)["message_sha256"] != ledger["message_sha256"]
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["grounding"].update(message_sha256="a" * 64),
        lambda r: r["grounding"].update(created_at="2000-01-01"),
        lambda r: r.update(tool_input="input-command"),
        lambda r: r["grounding"].update(voice_rules_pass="true"),
        lambda r: r["grounding"].update(claims=[], no_factual_claims=False),
    ],
)
def test_invalid_or_fabricated_envelope_refuses(change):
    r = request()
    change(r)
    with pytest.raises(ValueError):
        guard.build_grounding_envelope(r)


def test_judgment_is_never_inferred():
    r = request()
    r["grounding"]["voice_rules_pass"] = False
    assert guard.build_grounding_envelope(r)["voice_rules_pass"] is False
