from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("message_guard.py")
SPEC = importlib.util.spec_from_file_location("message_guard", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SAMPLE_TOOLS = [
    "mcp__abc__slack_send_message",
    "mcp__abc__slack_send_message_draft",
    "mcp__abc__slack_schedule_message",
    "mcp__workspace__draft_gmail_message",
    "mcp__workspace__send_gmail_message",
    "mcp__mail__create_draft",
    "mcp__mail__update_draft",
    "mcp__apple-mail__send_email",
    "mcp__mail__send_message",
]
MATCHER = (
    "mcp__.*__(slack_send_message|slack_send_message_draft|"
    "slack_schedule_message|draft_gmail_message|send_gmail_message|"
    "create_draft|update_draft|send_email|send_message)$"
)


def write_hooks(path: Path, matcher: str, command: str) -> None:
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": matcher,
                            "hooks": [{"type": "command", "command": command}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def test_hook_config_accepts_claude_and_codex_shape(tmp_path: Path) -> None:
    for filename in ("settings.json", "hooks.json"):
        path = tmp_path / filename
        write_hooks(path, MATCHER, "python3 message_guard.py --gate")
        assert MODULE.hook_config_covers(path, SAMPLE_TOOLS)


def test_hook_config_rejects_partial_matcher(tmp_path: Path) -> None:
    path = tmp_path / "hooks.json"
    write_hooks(
        path,
        "mcp__.*__slack_send_message$",
        "python3 message_guard.py --gate",
    )
    assert not MODULE.hook_config_covers(path, SAMPLE_TOOLS)


def test_hook_config_rejects_missing_guard(tmp_path: Path) -> None:
    path = tmp_path / "hooks.json"
    write_hooks(path, MATCHER, "python3 another_guard.py --gate")
    assert not MODULE.hook_config_covers(path, SAMPLE_TOOLS)


# --- doctor controls from the 2026-08 config incidents ----------------------


def test_dead_surrogate_pattern_detection() -> None:
    """A pattern whose source carries lone surrogates (the escaped-emoji
    authoring mistake) can never match decoded text; the doctor's control
    predicate must identify it while a real-character pattern passes."""
    import re

    dead_source = "\ud83e\uddde|RagBot"
    live_source = "\U0001F9DE|RagBot"
    def is_dead(rx):
        return any("\ud800" <= ch <= "\udfff" for ch in rx.pattern)
    assert is_dead(re.compile(dead_source))
    assert not is_dead(re.compile(live_source))
    # And the dead form genuinely fails to match the decoded emoji — the
    # incident's mechanism, kept here as the reason the control exists.
    assert re.compile(dead_source).search("\U0001F9DE hello") is None
    assert re.compile(live_source).search("\U0001F9DE hello") is not None


def test_config_clean_controls_scan() -> None:
    """doctor_clean_controls entries run through the live scanner: a
    canonical legitimate message must produce zero hits, and a config
    change that starts blocking real traffic must be detectable."""
    import re

    cblock = [("bad-brand", re.compile("RagBot"))]
    cwarn: list = []
    canonical = "Ragbot here with the summary — details at ragbot.ai"
    hits, _ = MODULE.scan_text(canonical, cblock, cwarn)
    assert hits == []
    over_broad = [("bad-brand", re.compile("ragbot", re.IGNORECASE))]
    hits2, _ = MODULE.scan_text(canonical, over_broad, cwarn)
    assert hits2, "an over-broad pattern must be visible to the control"


# --- signature wire-form enforcement (2026-08-30 incident) ------------------

WIRE_CFG = {
    "signature_link_enforcement": {
        "markers": ["\U0001F9DE", "\U0001F916"],
        "domains": ["ragenie.ai", "ragbot.ai", "synthesiswriting.org"],
        "html_body_format_tools": "send_gmail_message|draft_gmail_message",
        "linkless_fallback_tools": "workspace-mcp__send_message$",
    }
}

RAGENIE_PLAIN = ("\U0001F9DE\u200d\u2642\ufe0f I wrote this with my Ragenie "
                 "(ragenie.ai) \u2014 synthesis writing: I personally write")
RAGENIE_HTML = ("\U0001F9DE\u200d\u2642\ufe0f <em>I wrote this with my "
                "<a href=\"https://ragenie.ai/\">Ragenie</a> \u2014 "
                "<a href=\"https://synthesiswriting.org/#from-a-message\">"
                "synthesis writing</a>: I personally write</em>")
RAGBOT_SLACK = ("\U0001F916 _I\u2019m Rajiv\u2019s "
                "<https://ragbot.ai/|Ragbot>, sent under his standing "
                "direction \u2014 he reads every reply_")


def test_wire_incident_shape_blocks() -> None:
    """The exact 2026-08-30 failure: persona-signed email, body_format
    plain, bare visible domain — the doctrine existed and nothing read it."""
    fails = MODULE.signature_wire_failures(
        "mcp__workspace-mcp__send_gmail_message",
        {"body_format": "plain"}, RAGENIE_PLAIN, WIRE_CFG)
    joined = " ".join(fails)
    assert "body_format html" in joined
    assert "visible-URL fallback" in joined


def test_wire_html_anchors_pass() -> None:
    fails = MODULE.signature_wire_failures(
        "mcp__workspace-mcp__send_gmail_message",
        {"body_format": "html"}, RAGENIE_HTML, WIRE_CFG)
    assert fails == []


def test_wire_slack_mrkdwn_passes() -> None:
    fails = MODULE.signature_wire_failures(
        "mcp__abc__slack_send_message", {}, RAGBOT_SLACK, WIRE_CFG)
    assert fails == []


def test_wire_markdown_in_email_blocks() -> None:
    text = ("\U0001F916 _I\u2019m Rajiv\u2019s "
            "[Ragbot](https://ragbot.ai/) \u2014 he approved this_")
    fails = MODULE.signature_wire_failures(
        "mcp__workspace-mcp__draft_gmail_message",
        {"body_format": "html"}, text, WIRE_CFG)
    assert any("markdown" in f for f in fails)


def test_wire_linkless_fallback_tool_exempt() -> None:
    """Google Chat user sends cannot render links; the visible form is the
    legitimate form there."""
    fails = MODULE.signature_wire_failures(
        "mcp__workspace-mcp__send_message", {},
        "\U0001F916 I\u2019m Rajiv\u2019s Ragbot (ragbot.ai)", WIRE_CFG)
    assert fails == []


def test_wire_unsigned_traffic_untaxed() -> None:
    fails = MODULE.signature_wire_failures(
        "mcp__workspace-mcp__send_gmail_message", {"body_format": "plain"},
        "Plain operational note mentioning ragbot.ai in prose.", WIRE_CFG)
    assert fails == []


def test_wire_absent_config_is_off() -> None:
    fails = MODULE.signature_wire_failures(
        "mcp__workspace-mcp__send_gmail_message", {"body_format": "plain"},
        RAGENIE_PLAIN, {})
    assert fails == []


# --- peer-session send resolution (2026-09-01) ------------------------------
#
# Misdelivery, not register drift, is the peer-lane failure mode: a target
# chosen by chat-title guesswork. The check requires the target session id to
# be a registered ACTIVE client ref on the coordination board.

PEER_BOARD = (
    "# Coordination\n\nSchema: v4\n\n## Active sessions\n\n"
    "| session uuid | compact id | speakable id v1 | legacy id | agent | "
    "machine | client session ref | project | started | heartbeat | mode | "
    "workspace(s) / branch | goal | claimed areas (advisory lock) | "
    "context role | status |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    "| u1 | s-aaaa-aaaa-aaaa | a-b-c-d-00001 |  | Claude Code | m1 | "
    "ccd:local_good | proj-a | t | t | interactive | w | g | a/** | owner | "
    "active |\n"
    "| u2 | s-bbbb-bbbb-bbbb | a-b-c-d-00002 |  | Claude Code | m1 | "
    "ccd:local_gone | proj-b | t | t | interactive | w | g | b/** | owner | "
    "released |\n"
    "\n## Messages\n\n---\n\n## Protocol\n"
)


def peer_cfg(board_path) -> dict:
    return {
        "peer_send_resolution": {
            "tool_pattern": "ccd_session_mgmt__send_message$",
            "target_field": "session_id",
            "board": str(board_path),
        }
    }


def test_peer_registered_active_target_passes(tmp_path: Path) -> None:
    board = tmp_path / "board.md"
    board.write_text(PEER_BOARD, encoding="utf-8")
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__ccd_session_mgmt__send_message",
        {"session_id": "local_good", "message": "hello"},
        peer_cfg(board),
    )
    assert handled and fails == []


def test_peer_unregistered_target_blocks_with_resolve_guidance(
    tmp_path: Path,
) -> None:
    board = tmp_path / "board.md"
    board.write_text(PEER_BOARD, encoding="utf-8")
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__ccd_session_mgmt__send_message",
        {"session_id": "local_guessed", "message": "hello"},
        peer_cfg(board),
    )
    assert handled
    joined = " ".join(fails)
    assert "resolve" in joined
    assert "never guess" in joined


def test_peer_released_target_blocks(tmp_path: Path) -> None:
    board = tmp_path / "board.md"
    board.write_text(PEER_BOARD, encoding="utf-8")
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__ccd_session_mgmt__send_message",
        {"session_id": "local_gone"},
        peer_cfg(board),
    )
    assert handled and fails


def test_peer_missing_board_blocks(tmp_path: Path) -> None:
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__ccd_session_mgmt__send_message",
        {"session_id": "local_good"},
        peer_cfg(tmp_path / "absent.md"),
    )
    assert handled and any("unreadable" in f for f in fails)


def test_peer_missing_target_field_blocks(tmp_path: Path) -> None:
    board = tmp_path / "board.md"
    board.write_text(PEER_BOARD, encoding="utf-8")
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__ccd_session_mgmt__send_message",
        {"message": "hello"},
        peer_cfg(board),
    )
    assert handled and any("fails closed" in f for f in fails)


def test_peer_absent_config_is_not_handled() -> None:
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__ccd_session_mgmt__send_message", {"session_id": "x"}, {}
    )
    assert (handled, fails) == (False, [])


def test_peer_other_tools_stay_in_correspondence_lane(tmp_path: Path) -> None:
    board = tmp_path / "board.md"
    board.write_text(PEER_BOARD, encoding="utf-8")
    handled, fails = MODULE.peer_send_resolution_failures(
        "mcp__abc__slack_send_message",
        {"session_id": "local_good"},
        peer_cfg(board),
    )
    assert (handled, fails) == (False, [])


# --- currency claims carry read freshness (v1.5.0) ----------------------------------------------

CURRENCY_CFG = {
    "ledger_max_age_minutes": 30,
    "currency_claim_patterns": [MODULE.DEFAULT_CURRENCY_PATTERN],
    "currency_claim_max_age_minutes": 30,
}
PLAIN_CFG = {"ledger_max_age_minutes": 30}
TEXT = "Following up on the deploy question from this morning."


def _ledger(claims: list[dict]) -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message_sha256": MODULE.sha256_text(TEXT),
        "is_reply": False,
        "claims": claims,
        "voice_rules_pass": True,
        "invented_precision_scan": True,
        "recipient_address_check": True,
    }


def _moment(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def test_currency_claim_without_read_at_is_refused() -> None:
    """The 2026-09-01 failure: 'still unanswered' rested on a read eight hours
    old, and the ledger could not tell because it recorded where, not when."""
    ledger = _ledger([{"claim": "Jordan's question is still unanswered", "source": "DM D0EXAMPLE"}])

    fails = MODULE.validate_ledger(ledger, TEXT, CURRENCY_CFG, "mcp__x__send_gmail_message")

    assert any("read_at" in f and "currency state" in f for f in fails), fails


def test_currency_claim_with_a_stale_read_is_refused() -> None:
    ledger = _ledger([{"claim": "no reply from Jordan yet", "source": "DM D0EXAMPLE",
                       "read_at": _moment(8 * 60)}])

    fails = MODULE.validate_ledger(ledger, TEXT, CURRENCY_CFG, "mcp__x__send_gmail_message")

    assert any("min old" in f for f in fails), fails


def test_currency_claim_with_a_fresh_read_passes() -> None:
    ledger = _ledger([{"claim": "no reply from Jordan yet", "source": "DM D0EXAMPLE",
                       "read_at": _moment(5)}])

    fails = MODULE.validate_ledger(ledger, TEXT, CURRENCY_CFG, "mcp__x__send_gmail_message")

    assert not [f for f in fails if "claims[" in f], fails


def test_a_stable_fact_needs_no_read_at() -> None:
    ledger = _ledger([{"claim": "PR 96 merged this afternoon", "source": "gh pr view 96"}])

    fails = MODULE.validate_ledger(ledger, TEXT, CURRENCY_CFG, "mcp__x__send_gmail_message")

    assert not [f for f in fails if "claims[" in f], fails


def test_currency_lane_is_off_until_adopted() -> None:
    ledger = _ledger([{"claim": "Jordan's question is still unanswered", "source": "DM D0EXAMPLE"}])

    fails = MODULE.validate_ledger(ledger, TEXT, PLAIN_CFG, "mcp__x__send_gmail_message")

    assert not [f for f in fails if "read_at" in f], fails


def test_ledger_template_carries_read_at() -> None:
    template = MODULE.ledger_template() if hasattr(MODULE, "ledger_template") else None
    text = json.dumps(template) if template is not None else MODULE_PATH.read_text(encoding="utf-8")
    assert "read_at" in text



# ---------------------------------------------------------------------------
# Ledger storage — the surface that broke.
#
# The suite above validates ledger CONTENT and never touched ledger STORAGE,
# so a single shared ledger.json passed CI for its whole life while silently
# losing one seat's grounding record every time two seats composed at once.
# These cases pin the storage contract, and the last one runs the engine's
# own behavioral suite so CI stops depending on someone running --test by hand.
# ---------------------------------------------------------------------------


def test_ledger_path_is_keyed_by_message_sha(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path))
    a, b = MODULE.sha256_text("first seat"), MODULE.sha256_text("second seat")
    assert a != b
    assert MODULE.ledger_path_for(a) != MODULE.ledger_path_for(b)
    assert MODULE.ledger_path_for(a).endswith(a + ".json")
    # Both live under one directory, so a sweep can still find them all.
    assert Path(MODULE.ledger_path_for(a)).parent == Path(MODULE.ledger_dir())


def test_no_single_shared_ledger_slot_remains() -> None:
    """A fixed-path helper is the defect itself; its absence is the fix."""
    assert not hasattr(MODULE, "ledger_path"), (
        "ledger_path() returned one shared slot for every seat. Restoring it "
        "reintroduces the clobber."
    )


def test_write_ledger_refuses_a_non_digest_sha(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path))
    import subprocess

    for bad in ("nope", "", "z" * 64, "a" * 63):
        proc = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--write-ledger"],
            input=json.dumps({"message_sha256": bad}),
            capture_output=True, text=True,
            env={**__import__("os").environ,
                 "MESSAGE_GUARD_STATE_DIR": str(tmp_path)},
        )
        assert proc.returncode == 2, f"accepted a bad digest: {bad!r}"
    assert not list(tmp_path.glob("ledger/*.json"))


def test_orphan_sweep_spares_fresh_ledgers(monkeypatch, tmp_path) -> None:
    import os
    import time

    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path))
    d = Path(MODULE.ledger_dir())
    d.mkdir(parents=True, exist_ok=True)
    fresh, ancient = d / ("a" * 64 + ".json"), d / ("b" * 64 + ".json")
    fresh.write_text("{}")
    ancient.write_text("{}")
    cfg = {"ledger_max_age_minutes": 30}
    old = time.time() - (30 * 60 * MODULE.LEDGER_ORPHAN_SWEEP_MULTIPLE) - 60
    os.utime(ancient, (old, old))
    assert MODULE.sweep_orphan_ledgers(cfg) == 1
    assert fresh.exists() and not ancient.exists()


def test_engine_behavioral_suite_passes(tmp_path: Path) -> None:
    """Run the engine's own --test so CI covers the gate end to end —
    hermetically. The example config and an isolated home, so the machine's
    private config can neither make the suite pass locally nor fail it in
    CI (2026-09-02: main was red for hours while every developer machine
    was green)."""
    import os as _os
    import subprocess

    env = {
        **_os.environ,
        "HOME": str(tmp_path),
        "MESSAGE_GUARD_CONFIG": str(MODULE_PATH.parent.parent / "patterns.example.json"),
        "MESSAGE_GUARD_STATE_DIR": str(tmp_path / "state"),
    }
    proc = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--test"],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAIL" not in proc.stdout, proc.stdout


def test_behavioral_suite_falls_back_to_the_example_config(tmp_path: Path) -> None:
    """With no private config at all (a CI runner), the harness runs against
    the example config instead of crashing on a missing file."""
    import os as _os
    import subprocess

    env = {k: v for k, v in _os.environ.items() if k != "MESSAGE_GUARD_CONFIG"}
    env["HOME"] = str(tmp_path)
    env["MESSAGE_GUARD_STATE_DIR"] = str(tmp_path / "state")
    proc = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--test"],
        capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "running against patterns.example.json" in proc.stdout


def test_written_ledger_is_private(monkeypatch, tmp_path) -> None:
    """A ledger carries the full outgoing text and every source behind it."""
    import os as _os
    import subprocess

    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path))
    payload = {"message_sha256": MODULE.sha256_text("hello"), "claims": []}
    proc = subprocess.run(
        [sys.executable, str(MODULE_PATH), "--write-ledger"],
        input=json.dumps(payload), capture_output=True, text=True,
        env={**_os.environ, "MESSAGE_GUARD_STATE_DIR": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    written = Path(proc.stdout.strip())
    assert written.stat().st_mode & 0o777 == 0o600
    assert written.parent.stat().st_mode & 0o777 == 0o700
    assert not list(written.parent.glob("*.tmp")), "no temp file left behind"


def test_loose_ledger_permissions_are_repaired(monkeypatch, tmp_path) -> None:
    import os as _os

    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path))
    d = Path(MODULE.ledger_dir())
    d.mkdir(parents=True, exist_ok=True)
    stray = d / ("c" * 64 + ".json")
    stray.write_text("{}")
    _os.chmod(stray, 0o644)
    _os.chmod(d, 0o755)
    MODULE.tighten_ledger_store()
    assert stray.stat().st_mode & 0o777 == 0o600
    assert d.stat().st_mode & 0o777 == 0o700


# --- the clean control is a canonical signed message (v1.6.0, board ask 2026-08-03) ------


def test_builtin_clean_control_is_a_canonical_signed_message() -> None:
    assert "ragbot.ai" in MODULE.POSITIVE_CONTROL_CLEAN
    assert "🤖" in MODULE.POSITIVE_CONTROL_CLEAN


def test_over_broad_retired_branding_pattern_trips_the_clean_control() -> None:
    """The exact 2026-08-03 defect: 'RagBot|RAGbot' under the engine's global
    IGNORECASE matched the correct 'Ragbot' and blocked every real send while
    the generic clean control kept passing. The canonical control catches it;
    the scoped fix passes it."""
    import re

    over_broad = [("retired-branding", re.compile("RagBot|RAGbot", re.IGNORECASE))]
    hits, _ = MODULE.scan_text(MODULE.POSITIVE_CONTROL_CLEAN, over_broad, [])
    assert hits, "the canonical control must expose the over-broad pattern"

    scoped = [("retired-branding", re.compile(r"(?-i:RagBot|RAGbot|ragbot(?!\.ai))", re.IGNORECASE))]
    hits2, _ = MODULE.scan_text(MODULE.POSITIVE_CONTROL_CLEAN, scoped, [])
    assert hits2 == [], hits2


def test_example_clean_controls_include_the_signature_and_pass_example_patterns() -> None:
    import re

    example = json.loads((MODULE_PATH.parent.parent / "patterns.example.json").read_text(encoding="utf-8"))
    cblock = [(p["name"], re.compile(p["regex"], re.IGNORECASE)) for p in example["block_patterns"]]
    cwarn = [(p["name"], re.compile(p["regex"], re.IGNORECASE)) for p in example["warn_patterns"]]
    controls = example["doctor_clean_controls"]
    assert any("ragbot.ai" in c for c in controls)
    for control in controls:
        hits, _ = MODULE.scan_text(control, cblock, cwarn)
        assert hits == [], (control, hits)


# --- a leftover single-slot ledger names its owner (2026-09-02) ----------------------------


def test_legacy_ledger_detail_names_the_owner(tmp_path: Path) -> None:
    """One seat's stale helper script kept the machine-wide doctor red; the
    finding must let its owner recognise the file without decoding a sha."""
    leftover = tmp_path / "ledger.json"
    leftover.write_text(json.dumps({
        "created_at": "2026-09-02T18:11:27+00:00",
        "channel": "gmail",
        "recipient": "colleague@example.com",
        "message_sha256": "abc",
    }), encoding="utf-8")

    detail = MODULE.legacy_ledger_detail(str(leftover))

    assert "created_at 2026-09-02T18:11:27+00:00" in detail
    assert "channel gmail" in detail
    assert "recipient colleague@example.com" in detail

    leftover.write_text("not json", encoding="utf-8")
    assert MODULE.legacy_ledger_detail(str(leftover)) == "unreadable"

