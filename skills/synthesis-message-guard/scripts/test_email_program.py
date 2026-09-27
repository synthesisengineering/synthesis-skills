import importlib.util
import json
import shlex
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from email import policy
from email.parser import Parser
import pytest

PATH = Path(
    os.environ.get(
        "EMAIL_GUARD_SOURCE", str(Path(__file__).with_name("message_guard.py"))
    )
)
spec = importlib.util.spec_from_file_location("email_guard_under_test", PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
TOOL = "mcp__workspace-mcp__draft_gmail_message"


def config():
    return json.loads((PATH.parent.parent / "patterns.example.json").read_text())


def ledger(digest):
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message_sha256": digest,
        "is_reply": False,
        "no_factual_claims": True,
        "voice_rules_pass": True,
        "invented_precision_scan": True,
        "recipient_address_check": True,
    }


def gate(tmp_path, body, digest=None, cfg=None):
    cfg = cfg or config()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    state = tmp_path / "state"
    (state / "ledger").mkdir(parents=True, exist_ok=True)
    if digest:
        (state / "ledger" / (digest + ".json")).write_text(json.dumps(ledger(digest)))
    env = {
        **os.environ,
        "MESSAGE_GUARD_CONFIG": str(path),
        "MESSAGE_GUARD_STATE_DIR": str(state),
    }
    return subprocess.run(
        [sys.executable, "-B", str(PATH), "--gate"],
        input=json.dumps({"tool_name": TOOL, "tool_input": body}),
        text=True,
        capture_output=True,
        timeout=5,
        env=env,
    )


def test_original_second_populated_field_is_scanned(tmp_path):
    body = {
        "body": "Clean ordinary text.",
        "htmlBody": "<p>Sorry for the delay.</p>",
        "body_format": "html",
    }
    result = gate(tmp_path, body, guard.sha256_text(body["body"]))
    assert result.returncode == 2 and "register scan" in result.stderr, result.stderr


def test_original_second_field_change_invalidates_first_field_ledger(tmp_path):
    body = {
        "body": "Clean ordinary text.",
        "htmlBody": "<p>Different unreviewed words.</p>",
        "body_format": "html",
    }
    result = gate(tmp_path, body, guard.sha256_text(body["body"]))
    assert result.returncode == 2, result.stderr


def test_canonical_digest_binds_every_field_and_key_order():
    body = {
        "body": "<p>Words.</p>",
        "body_format": "html",
        "to": "reader@example.test",
        "subject": "Synthetic",
    }
    digest = guard.message_digest(TOOL, body)
    assert digest == guard.message_digest(TOOL, dict(reversed(list(body.items()))))
    for key, value in [
        ("htmlBody", "<p>Other part.</p>"),
        ("to", "other@example.test"),
        ("subject", "Changed"),
        ("body_format", "plain"),
    ]:
        assert guard.message_digest(TOOL, {**body, key: value}) != digest
    assert guard.message_digest(TOOL + "changed", body) != digest


def test_nested_multipart_fields_are_complete():
    body = {
        "body": {"content": "first", "contentType": "text/plain"},
        "parts": [{"mimeType": "text/html", "body": {"content": "<p>second</p>"}}],
    }
    fields = guard.message_fields(body, ["body"])
    assert any("first" == text for path, text in fields)
    assert any("<p>second</p>" == text for path, text in fields)


@pytest.mark.parametrize(
    "bad",
    [
        "<p>Sorry for the delay.</p>",
        "<p>So<em>rry</em> for the delay.</p>",
        "<p>S&#111;rry for the delay.</p>",
    ],
)
def test_html_register_cannot_hide_behind_markup(tmp_path, bad):
    body = {"body": "<p>Clean.</p>", "body_format": "html", "htmlBody": bad}
    result = gate(tmp_path, body, guard.message_digest(TOOL, body))
    assert result.returncode == 2 and "register scan" in result.stderr


def test_exact_multifield_message_passes_once(tmp_path):
    body = {
        "body": "<p>Clean synthetic message.</p>",
        "body_format": "html",
        "subject": "Synthetic fixture",
        "to": "reader@example.test",
    }
    digest = guard.message_digest(TOOL, body)
    result = gate(tmp_path, body, digest)
    assert result.returncode == 0, result.stderr
    result = gate(tmp_path, body)
    assert result.returncode == 2


def test_default_constructor_normalizes_prose_and_escapes_markup():
    body = guard.build_email(
        {"paragraphs": ["First line\ncontinues <safely>.", "Second paragraph."]}
    )
    assert body["body_format"] == "html"
    assert (
        body["body"]
        == "<p>First line continues &lt;safely&gt;.</p><p>Second paragraph.</p>"
    )


@pytest.mark.parametrize(
    "html",
    [
        "<p>First<br>continues.</p>",
        '<p style="white-space:pre">First\ncontinues.</p>',
        "<script>alert(1)</script>",
        '<p onclick="evil()">Hello</p>',
        '<p><a href="javascript:evil()">Hello</a></p>',
    ],
)
def test_html_format_negative_controls(html):
    assert guard.email_format_failures(
        TOOL, {"body": html, "body_format": "html"}, config()
    )


def test_html_source_whitespace_is_not_a_rendered_break():
    assert (
        guard.email_format_failures(
            TOOL,
            {"body": "<p>A long\nsource line.</p><p>Next.</p>", "body_format": "html"},
            config(),
        )
        == []
    )


def test_plain_requires_config_owned_override():
    body = {
        "body": "First paragraph.\n\nSecond paragraph.",
        "body_format": "plain",
        "format_override": True,
    }
    assert guard.email_format_failures(TOOL, body, config())
    cfg = config()
    cfg["email_policy"] = {
        "default_format": "plain",
        "allow_intra_paragraph_breaks": False,
    }
    assert guard.email_format_failures(TOOL, body, cfg) == []
    assert guard.email_format_failures(TOOL, {**body, "body": "First\ncontinues."}, cfg)
    cfg["email_policy"]["allow_intra_paragraph_breaks"] = True
    assert (
        guard.email_format_failures(TOOL, {**body, "body": "First\ncontinues."}, cfg)
        == []
    )


def test_unknown_capability_cannot_be_self_asserted():
    with pytest.raises(ValueError, match="capability"):
        guard.capability_for("mcp__new__transmit", {"capability": "read-only"})


def test_configured_new_transport_is_capability_keyed():
    cfg = config()
    cfg["message_capabilities"] = [
        {
            "tool_pattern": "^mcp__new__transmit$",
            "channel": "email",
            "body_field": "data",
            "format_field": "kind",
            "html_value": "rich",
            "plain_value": "text",
        }
    ]
    assert (
        guard.email_format_failures(
            "mcp__new__transmit", {"data": "<p>Words.</p>", "kind": "rich"}, cfg
        )
        == []
    )
    assert guard.email_format_failures(
        "mcp__new__transmit", {"data": "Words.", "kind": "text"}, cfg
    )


def test_mime_roundtrip_and_raw_transport_wrapping():
    body = guard.build_email(
        {
            "paragraphs": ["long " + ("sentence " * 35) + ".", "Second."],
            "subject": "Synthetic",
            "to": "reader@example.test",
        }
    )
    raw = guard.email_mime(body)
    result = guard.verify_email_readback(body, raw, config())
    assert result["status"] == "VERIFIED_SUPPLIED_READBACK", result
    assert result["provenance_verified"] is False
    assert result["mime_parts"] == 2


def test_readback_corruption_and_missing_html_refuse():
    body = guard.build_email(
        {
            "paragraphs": ["Original words."],
            "subject": "Synthetic",
            "to": "reader@example.test",
        }
    )
    raw = guard.email_mime(body)
    with pytest.raises(ValueError):
        guard.verify_email_readback(
            body, raw.replace("Original words.", "Changed words."), config()
        )
    from email.message import EmailMessage

    plain = EmailMessage()
    plain["To"] = "reader@example.test"
    plain["Subject"] = "Synthetic"
    plain.set_content("Original words.")
    with pytest.raises(ValueError):
        guard.verify_email_readback(body, plain.as_string(), config())


def test_monitor_reports_all_records_and_bad_readback():
    good = guard.email_mime(guard.build_email({"paragraphs": ["Words."]}))
    report = guard.monitor_email_records(
        [
            {"message_id": "synthetic-good", "raw_mime": good},
            {"message_id": "synthetic-bad", "raw_mime": "broken"},
        ],
        config(),
    )
    assert report["checked"] == 2 and report["violations"] == 1, report
    assert report["real_transport_observed"] is False


def inventory(client="codex"):
    return {
        "client": client,
        "complete": True,
        "total_tools": 2,
        "next_cursor": None,
        "source": "synthetic native catalog fixture",
        "tools": [
            {"name": TOOL, "input_schema": {"body": "string", "body_format": "string"}},
            {
                "name": "mcp__fictional__fetch",
                "input_schema": {},
                "annotations": {"readOnlyHint": True},
            },
        ],
    }


def enrollment(client="codex"):
    observed = inventory(client)
    plan = guard.capability_plan(observed, config())
    decisions = []
    for row in plan["proposals"]:
        cap = row["capability"] or {"channel": "non-correspondence"}
        cap.pop("tool_names", None)
        decisions.append(
            {
                "name": row["name"],
                "descriptor_sha256": row["descriptor_sha256"],
                "capability": cap,
            }
        )
    return guard.capability_enroll(
        {
            "inventory": observed,
            "owner_review": {
                "inventory_digest": plan["inventory_digest"],
                "source": "synthetic owner review fixture; not live authorization",
            },
            "decisions": decisions,
        },
        config(),
    )


def test_native_inventory_hints_do_not_create_permission():
    result = guard.capability_plan(inventory(), config())
    assert result["unclassified"] == 1
    unknown = next(
        x for x in result["proposals"] if x["name"] == "mcp__fictional__fetch"
    )
    assert unknown["read_only_hint"] is True and unknown["capability"] is None
    assert result["hint_is_authority"] is False


@pytest.mark.parametrize("change", ["added", "removed", "changed", "client"])
def test_native_inventory_drift_blocks_activation(change):
    reg = enrollment()
    cfg = {
        **config(),
        "message_capabilities": reg["capabilities"],
        "_capability_registry": reg,
    }
    observed = inventory()
    assert (
        guard.capability_readiness(observed, cfg)["status"]
        == "READY_FOR_OWNER_ACTIVATION"
    )
    if change == "added":
        observed["tools"].append({"name": "mcp__new__tool", "input_schema": {}})
    elif change == "removed":
        observed["tools"].pop()
    elif change == "changed":
        observed["tools"][0]["input_schema"]["body"] = "object"
    else:
        observed["client"] = "claude"
    with pytest.raises(ValueError):
        guard.capability_readiness(observed, cfg)


def test_partial_or_stale_enrollment_is_rejected():
    observed = inventory()
    plan = guard.capability_plan(observed, config())
    with pytest.raises(ValueError):
        guard.capability_enroll(
            {
                "inventory": observed,
                "owner_review": {
                    "inventory_digest": plan["inventory_digest"],
                    "source": "synthetic",
                },
                "decisions": [],
            },
            config(),
        )
    with pytest.raises(ValueError):
        guard.capability_enroll(
            {
                "inventory": observed,
                "owner_review": {"inventory_digest": "wrong", "source": "synthetic"},
                "decisions": [],
            },
            config(),
        )


def test_non_correspondence_cannot_be_a_catch_all_regex():
    with pytest.raises(ValueError):
        guard.capability_for(
            "mcp__new__send",
            {
                "message_capabilities": [
                    {"tool_pattern": ".*", "channel": "non-correspondence"}
                ]
            },
        )


def test_every_populated_string_is_scanned(tmp_path):
    body = {
        "body": "<p>Clean.</p>",
        "body_format": "html",
        "alternate_caption": "Sorry for the delay.",
    }
    result = gate(tmp_path, body, guard.message_digest(TOOL, body))
    assert result.returncode == 2 and "register scan" in result.stderr


def test_secondary_html_part_cannot_hide_breaks():
    assert guard.email_format_failures(
        TOOL,
        {
            "body": "<p>Clean.</p>",
            "body_format": "html",
            "htmlBody": "<p>Other<br>part</p>",
        },
        config(),
    )


def test_nested_declared_transport_fields():
    cfg = config()
    cfg["message_capabilities"] = [
        {
            "tool_names": ["mcp__fictional__draft"],
            "channel": "email",
            "body_field": "/body/content",
            "format_field": "/body/contentType",
            "html_value": "HTML",
            "plain_value": "Text",
        }
    ]
    assert not guard.email_format_failures(
        "mcp__fictional__draft",
        {"body": {"content": "<p>Nested.</p>", "contentType": "HTML"}},
        cfg,
    )
    assert guard.email_format_failures(
        "mcp__fictional__draft",
        {"body": {"content": "<p>Nested.</p>", "contentType": "Text"}},
        cfg,
    )


def test_dispatch_only_passes_explicit_owner_classification(tmp_path):
    cfgpath = tmp_path / "cfg.json"
    cfgpath.write_text(json.dumps(config()))
    regpath = tmp_path / "capabilities.json"
    regpath.write_text(json.dumps(enrollment()))
    env = {
        **os.environ,
        "MESSAGE_GUARD_CONFIG": str(cfgpath),
        "MESSAGE_GUARD_STATE_DIR": str(tmp_path / "state"),
    }

    def invoke(name, tool_input):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(PATH),
                "--dispatch",
                "--capabilities-file",
                str(regpath),
            ],
            input=json.dumps({"tool_name": name, "tool_input": tool_input}),
            text=True,
            capture_output=True,
            timeout=5,
            env=env,
        )

    assert invoke("mcp__fictional__fetch", {}).returncode == 0
    unknown = invoke(
        "mcp__unclassified__fetch",
        {"capability": "non-correspondence", "readOnlyHint": True},
    )
    assert unknown.returncode == 2 and "capability" in unknown.stderr
    # Declared outgoing email still has the complete ledger boundary.
    assert (
        invoke(TOOL, {"body": "<p>Words.</p>", "body_format": "html"}).returncode == 2
    )


@pytest.mark.parametrize(
    "change", ["missing-cap", "wrong-review", "extra-tool", "duplicate-cap", "wildcard"]
)
def test_corrupt_enrollment_never_becomes_readiness(change):
    inv, registry = inventory(), enrollment()
    import copy

    bad = copy.deepcopy(registry)
    if change == "missing-cap":
        bad["capabilities"].pop()
    elif change == "wrong-review":
        bad["owner_review"]["inventory_digest"] = "0" * 64
    elif change == "extra-tool":
        bad["inventory"]["tools"].append({"name": "new", "descriptor_sha256": "0" * 64})
    elif change == "duplicate-cap":
        bad["capabilities"][1] = bad["capabilities"][0]
    else:
        bad["capabilities"][0]["tool_pattern"] = ".*"
    cfg = config()
    cfg["_capability_registry"] = bad
    cfg["message_capabilities"] = bad["capabilities"]
    with pytest.raises(ValueError):
        guard.capability_readiness(inv, cfg)


def test_nested_declared_body_is_recognized_and_scanned(tmp_path):
    cfg = config()
    cfg["message_capabilities"] = [
        {
            "tool_names": [TOOL],
            "channel": "email",
            "body_field": "/payload/data",
            "format_field": "/payload/format",
        }
    ]
    body = {"payload": {"data": "<p>Words.</p>", "format": "html"}}
    result = gate(tmp_path, body, guard.message_digest(TOOL, body), cfg)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), {"x": object()}])
def test_invalid_canonical_values_refuse(bad):
    with pytest.raises((ValueError, TypeError)):
        guard.message_digest(TOOL, {"body": bad})


def test_canonical_byte_depth_and_node_limits():
    with pytest.raises(ValueError, match="byte"):
        guard.message_digest(TOOL, {"body": "a" * (guard.MAX_MESSAGE_BYTES + 1)})
    value = "text"
    for _ in range(guard.MAX_MESSAGE_DEPTH + 2):
        value = {"body": value}
    with pytest.raises(ValueError, match="structure"):
        guard.message_digest(TOOL, value)
    with pytest.raises(ValueError, match="structure"):
        guard.message_digest(TOOL, {"body": ["x"] * guard.MAX_MESSAGE_NODES})


def test_readback_all_parts_and_headers_are_compared():
    from email import policy
    from email.parser import Parser

    body = guard.build_email(
        {"paragraphs": ["Words."], "subject": "Synthetic", "to": "reader@example.test"}
    )
    original = guard.email_mime(body)
    for field in ["Subject", "To"]:
        changed = Parser(policy=policy.default).parsestr(original)
        changed.replace_header(
            field, "Changed" if field == "Subject" else "other@example.test"
        )
        with pytest.raises(ValueError, match="header"):
            guard.verify_email_readback(body, changed.as_string(), config())
    changed = Parser(policy=policy.default).parsestr(original)
    changed.add_alternative("<p>Hidden additional part.</p>", subtype="html")
    with pytest.raises(ValueError, match="parts"):
        guard.verify_email_readback(body, changed.as_string(), config())


def test_header_injection_constructor_mime_refuses():
    body = guard.build_email(
        {"paragraphs": ["Words."], "subject": "Synthetic\nBcc: injected@example.test"}
    )
    with pytest.raises(ValueError):
        guard.email_mime(body)


def test_standalone_installed_copy_has_same_digest_and_gate(tmp_path):
    import shutil

    script = tmp_path / "installed" / "message_guard.py"
    script.parent.mkdir()
    shutil.copyfile(PATH, script)
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config()))
    env = {
        **os.environ,
        "MESSAGE_GUARD_CONFIG": str(cfg),
        "MESSAGE_GUARD_STATE_DIR": str(tmp_path / "state"),
    }
    env.pop("PYTHONPATH", None)
    env.pop("MESSAGE_GUARD_CAPABILITIES", None)
    body = {"body": "<p>Standalone.</p>", "body_format": "html"}
    payload = {"tool_name": TOOL, "tool_input": body}

    def call(mode, data):
        return subprocess.run(
            [sys.executable, "-B", str(script), mode],
            input=json.dumps(data),
            text=True,
            capture_output=True,
            timeout=10,
            env=env,
            cwd=tmp_path,
        )

    hashed = call("--message-sha", payload)
    assert hashed.returncode == 0 and hashed.stdout.strip() == guard.message_digest(
        TOOL, body
    )
    assert call("--write-ledger", ledger(hashed.stdout.strip())).returncode == 0
    assert call("--gate", payload).returncode == 0
    assert call("--gate", payload).returncode == 2
    made = call("--build-email", {"paragraphs": ["A line\ncontinued."]})
    assert made.returncode == 0
    assert json.loads(made.stdout)["body"] == "<p>A line continued.</p>"


def test_doctor_checks_muse_wiring_without_claiming_native_loading(
    tmp_path, monkeypatch, capsys
):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps(config()))
    monkeypatch.setenv("MESSAGE_GUARD_CONFIG", str(cfg))
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("MESSAGE_GUARD_CAPABILITIES", raising=False)
    registry_file = tmp_path / "synthetic-capabilities.json"
    registry_file.write_text(json.dumps(enrollment()))
    monkeypatch.setenv("MESSAGE_GUARD_CAPABILITIES", str(registry_file))
    for client, var in [
        ("claude", "MESSAGE_GUARD_CLAUDE_SETTINGS"),
        ("codex", "MESSAGE_GUARD_CODEX_HOOKS"),
        ("muse", "MESSAGE_GUARD_MUSE_SETTINGS"),
    ]:
        path = tmp_path / (client + ".json")
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": ".*",
                                "hooks": [
                                    {"command": shlex.join([sys.executable, str(PATH), "--dispatch"])}
                                ],
                            }
                        ]
                    }
                }
            )
        )
        monkeypatch.setenv(var, str(path))
    assert guard.run_doctor() == 0
    output = capsys.readouterr().out
    assert "Muse Code PreToolUse wiring" in output and "native hook loading" in output
    (tmp_path / "muse.json").write_text("{}")
    assert guard.run_doctor() == 2
    assert "FAIL Muse Code" in capsys.readouterr().out


def test_human_text_constructor_and_override():
    assert guard.build_text({"paragraphs": ["One\nline.", "Second."]}, {}) == {
        "message": "One line.\n\nSecond."
    }
    cfg = {"paragraph_policy": {"allow_intra_paragraph_breaks": True}}
    assert (
        guard.build_text({"paragraphs": ["One\nline."]}, cfg)["message"] == "One\nline."
    )
    with pytest.raises(ValueError):
        guard.build_text({"paragraphs": ["Words."], "override": True}, {})


def test_human_text_readback_and_negative_controls():
    assert (
        guard.verify_text_readback("Words.", "Words.", {})["provenance_verified"]
        is False
    )
    with pytest.raises(ValueError):
        guard.verify_text_readback("Two lines.", "Two\nlines.", {})
    with pytest.raises(ValueError):
        guard.verify_text_readback("Words.", "Other.", {})
    cfg = {"paragraph_policy": {"allow_intra_paragraph_breaks": True}}
    assert (
        guard.verify_text_readback("Two\nlines.", "Two\nlines.", cfg)["status"]
        == "VERIFIED_SUPPLIED_READBACK"
    )


def test_human_text_gate_keeps_grounding_and_override_owner(tmp_path):
    tool = "mcp__synthetic__slack_send_message_draft"
    body = {"message": "First line\ncontinued."}
    cfg = config()
    path = tmp_path / "cfg.json"
    state = tmp_path / "state"
    (state / "ledger").mkdir(parents=True)
    env = {
        **os.environ,
        "MESSAGE_GUARD_CONFIG": str(path),
        "MESSAGE_GUARD_STATE_DIR": str(state),
    }
    env.pop("MESSAGE_GUARD_CAPABILITIES", None)

    def call():
        path.write_text(json.dumps(cfg))
        return subprocess.run(
            [sys.executable, "-B", str(PATH), "--gate"],
            input=json.dumps({"tool_name": tool, "tool_input": body}),
            text=True,
            capture_output=True,
            timeout=5,
            env=env,
        )

    digest = guard.message_digest(tool, body)
    lp = state / "ledger" / (digest + ".json")
    lp.write_text(json.dumps(ledger(digest)))
    denied = call()
    assert denied.returncode == 2 and "line break" in denied.stderr
    assert lp.exists()  # refusal does not consume valid grounding
    cfg["paragraph_policy"] = {"allow_intra_paragraph_breaks": True}
    assert call().returncode == 0
    assert call().returncode == 2  # formatting override never supplies a ledger


@pytest.mark.parametrize(
    "field,value",
    [
        ("htmlBody", "<p>Altered alternate.</p>"),
        ("subject", "Altered"),
        ("to", "other@example.test"),
    ],
)
def test_gate_refuses_after_any_field_changes_even_when_text_is_clean(
    tmp_path, field, value
):
    original = {
        "body": "<p>Primary.</p>",
        "htmlBody": "<p>Alternate.</p>",
        "body_format": "html",
        "subject": "Synthetic",
        "to": "reader@example.test",
    }
    digest = guard.message_digest(TOOL, original)
    altered = {**original, field: value}
    result = gate(tmp_path, altered, digest)
    assert (
        result.returncode == 2 and "no grounding ledger" in result.stderr
    ), result.stderr
    assert (tmp_path / "state" / "ledger" / (digest + ".json")).exists()


def test_dispatch_email_classification_cannot_be_bypassed_by_legacy_exemption(tmp_path):
    tool = "mcp__legacy_session__send_message"
    cfg = config()
    cfg["message_capabilities"] = [
        {
            "tool_names": [tool],
            "channel": "email",
            "body_field": "body",
            "format_field": "body_format",
        }
    ]
    observed = {
        "client": "codex",
        "source": "synthetic exemption regression",
        "complete": True,
        "total_tools": 1,
        "next_cursor": None,
        "tools": [{"name": tool, "input_schema": {"type": "object"}}],
    }
    plan = guard.capability_plan(observed, cfg)
    registry = guard.capability_enroll(
        {
            "inventory": observed,
            "owner_review": {
                "inventory_digest": plan["inventory_digest"],
                "source": "synthetic review",
            },
            "decisions": [
                {
                    "name": tool,
                    "descriptor_sha256": plan["tools"][0]["descriptor_sha256"],
                    "capability": {
                        "channel": "email",
                        "body_field": "body",
                        "format_field": "body_format",
                    },
                }
            ],
        },
        cfg,
    )
    cfg["_capability_registry"] = registry
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg))
    env = {
        **os.environ,
        "MESSAGE_GUARD_CONFIG": str(path),
        "MESSAGE_GUARD_STATE_DIR": str(tmp_path / "state"),
    }
    env.pop("MESSAGE_GUARD_CAPABILITIES", None)
    p = subprocess.run(
        [sys.executable, "-B", str(PATH), "--dispatch"],
        input=json.dumps(
            {
                "tool_name": tool,
                "tool_input": {"body": "<p>Words.</p>", "body_format": "html"},
            }
        ),
        text=True,
        capture_output=True,
        timeout=5,
        env=env,
    )
    assert p.returncode == 2 and "no grounding ledger" in p.stderr, p.stderr


# Independent adversarial review controls; initial failures retained in review evidence.


@pytest.mark.parametrize(
    "kind,text",
    [
        ("text/html", "<p>First<br>second</p>"),
        ("text/plain", "First\nsecond"),
        ("text/html", "<script>code</script>"),
    ],
)
def test_independent_nested_mime_alternative_must_be_checked(tmp_path, kind, text):
    body = {
        "body": "<p>Clean primary.</p>",
        "body_format": "html",
        "parts": [{"mimeType": kind, "body": {"content": text}}],
    }
    out = gate(tmp_path, body, guard.message_digest(TOOL, body))
    assert out.returncode == 2, out.stdout + out.stderr


def test_independent_nested_clean_mime_alternative_is_legitimate(tmp_path):
    body = {
        "body": "<p>Clean primary.</p>",
        "body_format": "html",
        "parts": [
            {"mimeType": "text/html", "body": {"content": "<p>Clean secondary.</p>"}}
        ],
    }
    out = gate(tmp_path, body, guard.message_digest(TOOL, body))
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.parametrize(
    "metadata",
    [
        {"attachments": [{"name": "approved.txt", "sha256": "a" * 64}]},
        {"thread_id": "approved-thread"},
        {"in_reply_to": "<approved@example.test>"},
        {"references": "<approved@example.test>"},
    ],
)
def test_independent_readback_cannot_certify_omitted_metadata(metadata):
    clean = guard.build_email({"paragraphs": ["Clean."], "to": "reader@example.test"})
    with pytest.raises(ValueError):
        guard.verify_email_readback(
            {**clean, **metadata}, guard.email_mime(clean), config()
        )


def test_independent_text_attachment_cannot_impersonate_body():
    clean = guard.build_email({"paragraphs": ["Clean."]})
    mime = Parser(policy=policy.default).parsestr(guard.email_mime(clean))
    for part in mime.walk():
        if not part.is_multipart():
            part.add_header(
                "Content-Disposition", "attachment", filename="unexpected.txt"
            )
    with pytest.raises(ValueError):
        guard.verify_email_readback(clean, mime.as_string(), config())


@pytest.mark.parametrize(
    "change",
    [
        {"complete": False},
        {"next_cursor": "more"},
        {"complete": True, "total_tools": 999},
    ],
)
def test_independent_incomplete_catalog_cannot_be_readiness_input(change):
    inv = inventory()
    inv.update(change)
    with pytest.raises(ValueError):
        guard.inventory_snapshot(inv)


def test_independent_exact_mime_readback_positive():
    body = guard.build_email({"paragraphs": ["Clean."], "to": "reader@example.test"})
    assert (
        guard.verify_email_readback(body, guard.email_mime(body), config())["status"]
        == "VERIFIED_SUPPLIED_READBACK"
    )


def test_independent_malformed_base64_cannot_receive_verified_status():
    import base64

    body = guard.build_email({"paragraphs": ["Clean."]})
    mime = Parser(policy=policy.default).parsestr(guard.email_mime(body))
    part = next(p for p in mime.walk() if p.get_content_type() == "text/plain")
    part.set_payload(
        base64.b64encode(part.get_payload(decode=True)).decode().rstrip("=")
    )
    part.replace_header("Content-Transfer-Encoding", "base64")
    with pytest.raises(ValueError):
        guard.verify_email_readback(body, mime.as_string(), config())


@pytest.mark.parametrize("bad", ["deep", "cyclic", "nonfinite", "bytes", "huge"])
def test_independent_canonical_input_bounds_refuse(bad):
    value = {}
    if bad == "deep":
        value = {"body": "A"}
        for _ in range(34):
            value = {"nested": value}
    elif bad == "cyclic":
        value["body"] = value
    elif bad == "nonfinite":
        value = {"body": "A", "value": float("nan")}
    elif bad == "bytes":
        value = {"body": b"A"}
    else:
        value = {"body": "A" * (guard.MAX_MESSAGE_BYTES + 1)}
    with pytest.raises(ValueError):
        guard.canonical_message(TOOL, value)


@pytest.mark.parametrize(
    "change",
    [
        ("to", "other@example.test"),
        ("cc", ["other@example.test"]),
        ("thread_id", "other"),
        ("attachments", [{"id": "other"}]),
        ("parts", [{"body": "other"}]),
    ],
)
def test_independent_approved_digest_does_not_authorize_changed_nonbody_fields(
    tmp_path, change
):
    body = {
        "body": "<p>Clean.</p>",
        "body_format": "html",
        "to": "reader@example.test",
        "thread_id": "thread",
        "attachments": [{"id": "attachment"}],
    }
    original = guard.message_digest(TOOL, body)
    mutated = {**body, change[0]: change[1]}
    assert guard.message_digest(TOOL, mutated) != original
    assert gate(tmp_path, mutated, original).returncode == 2


def test_independent_nested_owner_override_changes_format_only(tmp_path):
    cfg = config()
    cfg["email_policy"]["allow_intra_paragraph_breaks"] = True
    body = {
        "body": "<p>Clean<br>line.</p>",
        "body_format": "html",
        "parts": [{"mimeType": "text/plain", "body": {"content": "First\nsecond"}}],
    }
    assert gate(tmp_path, body, guard.message_digest(TOOL, body), cfg).returncode == 0
    body["parts"][0]["body"]["content"] = "Sorry for the delay."
    assert gate(tmp_path, body, guard.message_digest(TOOL, body), cfg).returncode == 2


@pytest.mark.parametrize("kind", ["missing", "extra", "annotation"])
def test_independent_whole_catalog_descriptor_drift_is_not_an_exemption(kind):
    inv = inventory()
    reg = enrollment()
    cfg = {
        **config(),
        "message_capabilities": reg["capabilities"],
        "_capability_registry": reg,
    }
    if kind == "missing":
        inv["tools"].pop()
    elif kind == "extra":
        inv["tools"].append({"name": "mcp__other__read", "input_schema": {}})
    else:
        inv["tools"][1]["annotations"] = {"readOnlyHint": False}
    inv["total_tools"] = len(inv["tools"])
    with pytest.raises(ValueError):
        guard.capability_readiness(inv, cfg)


def test_independent_reply_headers_and_recipients_bind_actual_readback():
    body = {
        **guard.build_email(
            {
                "paragraphs": ["Clean."],
                "to": ["reader@example.test"],
                "cc": "copy@example.test",
            }
        ),
        "in_reply_to": "<parent@example.test>",
        "references": "<root@example.test> <parent@example.test>",
        "reply_to": "reply@example.test",
    }
    assert (
        guard.verify_email_readback(body, guard.email_mime(body), config())["status"]
        == "VERIFIED_SUPPLIED_READBACK"
    )
    mime = Parser(policy=policy.default).parsestr(guard.email_mime(body))
    mime.replace_header("In-Reply-To", "<other@example.test>")
    with pytest.raises(ValueError):
        guard.verify_email_readback(body, mime.as_string(), config())


def test_independent_duplicate_mime_headers_and_deep_structure_refused():
    body = guard.build_email({"paragraphs": ["Clean."]})
    mime = guard.email_mime(body).replace(
        "MIME-Version: 1.0", "MIME-Version: 1.0\r\nMIME-Version: 1.0", 1
    )
    with pytest.raises(ValueError):
        guard.inspect_email_mime(mime, config())
    from email.message import EmailMessage

    nested = Parser(policy=policy.default).parsestr(guard.email_mime(body))
    for _ in range(18):
        wrapper = EmailMessage()
        wrapper.make_mixed()
        wrapper.attach(nested)
        nested = wrapper
    with pytest.raises(ValueError):
        guard.inspect_email_mime(nested.as_string(), config())


def test_independent_array_json_pointer_is_a_legitimate_transport_mapping():
    cfg = config()
    cfg["message_capabilities"] = [
        {
            "tool_names": [TOOL],
            "channel": "email",
            "body_field": "/parts/0/body/content",
            "format_field": "/parts/0/mimeType",
            "html_value": "text/html",
            "plain_value": "text/plain",
        }
    ]
    body = {"parts": [{"mimeType": "text/html", "body": {"content": "<p>Clean.</p>"}}]}
    assert not guard.email_format_failures(TOOL, body, cfg)
    assert guard.field_value({"parts": [{"body": "clean"}]}, "/parts/00/body") is None


def test_independent_dispatch_requires_complete_enrollment_not_just_one_classification(
    tmp_path,
):
    import subprocess

    cfg = config()
    cfg["message_capabilities"] = [
        {"tool_names": ["mcp__synthetic__fetch"], "channel": "non-correspondence"}
    ]
    path = tmp_path / "configuard.json"
    path.write_text(json.dumps(cfg))
    env = {
        **os.environ,
        "MESSAGE_GUARD_CONFIG": str(path),
        "MESSAGE_GUARD_STATE_DIR": str(tmp_path / "state"),
    }
    env.pop("MESSAGE_GUARD_CAPABILITIES", None)
    out = subprocess.run(
        [sys.executable, "-B", str(PATH), "--dispatch"],
        input=json.dumps({"tool_name": "mcp__synthetic__fetch", "tool_input": {}}),
        text=True,
        capture_output=True,
        timeout=5,
        env=env,
    )
    assert out.returncode == 2, out.stdout + out.stderr
