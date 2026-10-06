"""R3.1, 2026-08-03 shape: a correctly signed agent message passes the register scan; a miscased
signature is blocked, because a rule can be case-sensitive while the scan defaults to ignoring case."""

import json
from pathlib import Path

from synthesis import guards

SHAPE = json.loads((Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "incidents.json")
                   .read_text(encoding="utf-8"))["signed_agent_message"]
CONFIG = {"forbidden_phrases": SHAPE["rules"]}


def test_a_correctly_signed_message_reaches_the_approval_step():
    reason = guards.check(SHAPE["tool"], SHAPE["passes"], CONFIG)
    assert "approval" in reason and "brand casing" not in reason


def test_a_miscased_signature_is_blocked_by_name():
    assert "brand casing" in guards.check(SHAPE["tool"], SHAPE["blocked"], CONFIG)


def test_rules_still_ignore_case_unless_they_say_otherwise():
    message = {**SHAPE["passes"], "message": "SORRY for the delay. " + SHAPE["passes"]["message"]}
    assert "no apologies" in guards.check(SHAPE["tool"], message, CONFIG)
