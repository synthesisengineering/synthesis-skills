"""Campaign declarations cannot impersonate native acknowledgement or execution."""

import importlib
import json
from pathlib import Path
import sys
import uuid
import pytest
from system_contract import SystemState

SID = "019fff79-5858-7993-a329-b301bccf5d31"


def campaign():
    return {
        "id": "refresh-records",
        "version": 1,
        "not_before": "2026-01-01T00:00:00+00:00",
        "expires_at": "2027-01-01T00:00:00+00:00",
        "clients": ["codex", "claude", "muse"],
        "minimum_release": "4.100.0",
        "maximum_release": "5.0.0",
        "projects": [],
        "notice": "Review the selected project and report findings.",
        "action": "refresh-and-report",
        "mode": "report-only",
    }


def api():
    return importlib.import_module("upgrade_campaigns")


def test_applicability_expiry_and_no_effects(tmp_path):
    a = api()
    state = SystemState(tmp_path / "home")
    state.config_dir.mkdir(parents=True)
    path = state.config_dir / "campaigns.json"
    path.write_text(json.dumps({"schema": 1, "campaigns": [campaign()]}))
    before = {p: p.read_bytes() for p in state.home.rglob("*") if p.is_file()}
    report = a.applicability(
        state,
        client="codex",
        release="4.149.9",
        project=None,
        now="2026-01-03T00:00:00+00:00",
    )
    assert report["campaigns"][0]["status"] == "applicable"
    assert not report["execution_authorized"]
    assert (
        a.applicability(
            state, client="codex", release=None, now="2026-01-03T00:00:00+00:00"
        )["campaigns"][0]["status"]
        == "unknown-release"
    )
    assert (
        a.applicability(
            state, client="codex", release="4.149.9", now="2028-01-03T00:00:00+00:00"
        )["campaigns"][0]["status"]
        == "expired"
    )
    assert before == {p: p.read_bytes() for p in state.home.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("mode", "execute"),
        ("clients", ["unknown"]),
        ("minimum_release", "latest"),
        ("expires_at", "2025-01-01"),
        ("action", "sh x"),
        ("notice", "x" * 1025),
    ],
)
def test_invalid_catalog_refused(tmp_path, field, value):
    a = api()
    state = SystemState(tmp_path / "home")
    state.config_dir.mkdir(parents=True)
    row = campaign()
    row[field] = value
    (state.config_dir / "campaigns.json").write_text(
        json.dumps({"schema": 1, "campaigns": [row]})
    )
    with pytest.raises((ValueError, RuntimeError)):
        a.applicability(state, client="codex", release="4.149.9")


def native(tmp_path, monkeypatch):
    a = api()
    state = SystemState(tmp_path / "home")
    state.config_dir.mkdir(parents=True)
    (state.config_dir / "campaigns.json").write_text(
        json.dumps({"schema": 1, "campaigns": [campaign()]})
    )
    conformance = (
        Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
    )
    sys.path.insert(0, str(conformance))
    import session_context

    transcript = tmp_path / "codex/sessions/fixture.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": SID}}) + "\n"
    )
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.delenv("SYNTHESIS_CLIENT_SESSION_REF", raising=False)
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": SID,
        "transcript_path": str(transcript),
        "cwd": str(tmp_path),
    }
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin/plugin.json").write_text(
        json.dumps({"version": "4.149.9"})
    )
    (plugin / ".codex-plugin").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(
        json.dumps({"version": "4.149.9"})
    )
    (plugin / "hooks").mkdir()
    (plugin / "hooks/hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": []}})
    )
    monkeypatch.setattr(session_context, "SystemState", lambda: state)
    monkeypatch.setattr(
        session_context,
        "plugin_identity",
        lambda: ("4.149.9", str(tmp_path / "plugin")),
    )
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    assert session_context.record_live_receipt(payload, latest)
    receipt = json.loads(latest.read_text())
    event = session_context.receipt_event_path(
        latest, client="codex", session_id=SID, event_id=receipt["receipt_event_id"]
    )
    return a, state, payload, event, receipt


def test_real_native_event_and_single_use_report(tmp_path, monkeypatch):
    a, state, payload, event, receipt = native(tmp_path, monkeypatch)
    assert receipt["campaign_notices"]["campaigns"][0]["status"] == "applicable"
    assert receipt["campaign_notices"]["acknowledged"] is False
    report = a.report(
        state,
        event,
        payload,
        campaign_id="refresh-records",
        campaign_version=1,
        outcome="blocked",
        detail="Independent project owner needed.",
    )
    assert (
        report["reported_outcome"] == "blocked"
        and report["verified_completion"] is False
    )
    again = a.report(
        state,
        event,
        payload,
        campaign_id="refresh-records",
        campaign_version=1,
        outcome="blocked",
        detail="Independent project owner needed.",
    )
    assert again == report
    with pytest.raises(ValueError):
        a.report(
            state,
            event,
            payload,
            campaign_id="refresh-records",
            campaign_version=1,
            outcome="complete",
            detail="different",
        )


@pytest.mark.parametrize(
    "bad",
    [
        "forged-native",
        "wrong-event-path",
        "changed-catalog",
        "expired",
        "pending",
        "symlink-report",
    ],
)
def test_report_refuses_wrong_binding(tmp_path, monkeypatch, bad):
    a, state, payload, event, receipt = native(tmp_path, monkeypatch)
    if bad == "forged-native":
        payload["session_id"] = str(uuid.uuid4())
    elif bad == "wrong-event-path":
        copy = tmp_path / "copy.json"
        copy.write_bytes(event.read_bytes())
        event = copy
    elif bad == "changed-catalog":
        row = campaign()
        row["notice"] = "new"
        (state.config_dir / "campaigns.json").write_text(
            json.dumps({"schema": 1, "campaigns": [row]})
        )
    elif bad == "expired":
        monkeypatch.setattr(
            a, "_now", lambda value=None: a.datetime(2028, 1, 1, tzinfo=a.timezone.utc)
        )
    elif bad == "pending":
        receipt["transcript_bound_at_record"] = False
        event.write_text(json.dumps(receipt))
    else:
        directory = event.parent / "campaign-reports"
        directory.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises((ValueError, RuntimeError)):
        a.report(
            state,
            event,
            payload,
            campaign_id="refresh-records",
            campaign_version=1,
            outcome="blocked",
            detail="fixture",
        )


def test_unbound_hook_cannot_acknowledge(tmp_path):
    a = api()
    state = SystemState(tmp_path / "missing")
    assert (
        a.selection(
            state,
            {
                "client": "codex",
                "plugin_version": "4.149.9",
                "transcript_bound_at_record": False,
            },
        )
        is None
    )
    assert not state.home.exists()


@pytest.mark.parametrize("bad", ["expired", "changed-catalog"])
def test_notice_does_not_emit_stale_campaign_selection(tmp_path, monkeypatch, bad):
    a, state, payload, event, receipt = native(tmp_path, monkeypatch)
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    assert "Campaign refresh-records" in a.notice(state, payload, latest)
    if bad == "expired":
        original_now = a._now
        monkeypatch.setattr(
            a,
            "_now",
            lambda value=None: original_now(value)
            if value is not None
            else a.datetime(2028, 1, 1, tzinfo=a.timezone.utc),
        )
    else:
        row = campaign()
        row["notice"] = "Different proposal"
        (state.config_dir / "campaigns.json").write_text(
            json.dumps({"schema": 1, "campaigns": [row]})
        )
    assert a.notice(state, payload, latest) == ""


def test_campaign_receipt_lock_is_bounded_and_does_not_steal(tmp_path, monkeypatch):
    import subprocess
    import sys
    import select
    import time

    a, state, payload, event, receipt = native(tmp_path, monkeypatch)
    import session_context as context

    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    lock = latest.parent / ("." + latest.stem + "-events.lock")
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import fcntl,sys;f=open(sys.argv[1],'a+b');fcntl.flock(f,fcntl.LOCK_EX);print('ready',flush=True);sys.stdin.readline()",
            str(lock),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline().strip() == "ready"
        start = time.monotonic()
        with pytest.raises((ValueError, RuntimeError), match="timed out"):
            with context.receipt_registry_lock(latest, timeout=0.05):
                pass
        assert time.monotonic() - start < 1
    finally:
        child.communicate("\n", timeout=5)
    assert child.returncode == 0


@pytest.mark.parametrize("bad", ["json", "schema", "symlink", "fifo"])
def test_optional_catalog_refusal_retains_native_delivery(tmp_path, monkeypatch, bad):
    import os
    import session_context as context

    a, state, payload, event, receipt = native(tmp_path, monkeypatch)
    catalog = state.config_dir / "campaigns.json"
    if bad == "json":
        catalog.write_text("{")
    elif bad == "schema":
        catalog.write_text(json.dumps({"schema": 99, "campaigns": []}))
    elif bad == "symlink":
        catalog.unlink()
        catalog.symlink_to(tmp_path / "absent")
    else:
        catalog.unlink()
        os.mkfifo(catalog)
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    assert context.record_live_receipt(payload, latest) is True
    saved = json.loads(latest.read_text())
    assert saved["receipt_event_id"] != receipt["receipt_event_id"]
    assert saved["transcript_bound_at_record"] is True
    assert saved["campaign_notice_error"]["status"] == "REFUSED"
    assert "campaign_notices" not in saved
    assert "unavailable" in a.notice(state, payload, latest).lower()
    assert "Campaign refresh-records" not in a.notice(state, payload, latest)


def test_catalog_corruption_after_selection_is_explicit_campaign_refusal(
    tmp_path, monkeypatch
):
    a, state, payload, event, receipt = native(tmp_path, monkeypatch)
    (state.config_dir / "campaigns.json").write_text("{")
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    assert "unavailable" in a.notice(state, payload, latest).lower()
    with pytest.raises((ValueError, RuntimeError)):
        a.report(
            state,
            event,
            payload,
            campaign_id="refresh-records",
            campaign_version=1,
            outcome="acknowledged",
            detail="Synthetic report remains refused.",
        )


@pytest.mark.parametrize("error_type", [ImportError, RuntimeError])
def test_optional_module_failure_preserves_native_delivery(
    tmp_path, monkeypatch, error_type
):
    import builtins

    _api, state, payload, event, original = native(tmp_path, monkeypatch)
    import session_context as context

    original_import = builtins.__import__

    def injected(name, *args, **kwargs):
        if name == "upgrade_campaigns":
            raise error_type("synthetic unavailable optional campaign module")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", injected)
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    assert context.record_live_receipt(payload, latest) is True
    saved = json.loads(latest.read_text())
    assert saved["receipt_event_id"] != original["receipt_event_id"]
    assert (
        saved["session_id"] == original["session_id"]
        and saved["transcript_bound_at_record"] is True
    )
    assert saved["campaign_notice_error"]["status"] == "REFUSED"
    assert saved["campaign_notice_error"]["execution_authorized"] is False
    assert "campaign_notices" not in saved
    assert json.loads(event.read_text()) == original


@pytest.mark.parametrize(
    "error_type", [ImportError, SyntaxError, RuntimeError, AssertionError]
)
def test_optional_module_initialization_refuses_notice_without_erasing_receipt(
    tmp_path, monkeypatch, error_type
):
    import builtins
    import session_context as context

    _, state, payload, event, original = native(tmp_path, monkeypatch)
    original_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "upgrade_campaigns":
            raise error_type("synthetic optional module initialization failure")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken)
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    assert context.record_live_receipt(payload, latest) is True
    saved = json.loads(latest.read_text())
    assert saved["campaign_notice_error"]["status"] == "REFUSED"
    assert saved["campaign_notice_error"]["error_type"] == error_type.__name__
    assert saved["campaign_notice_error"]["execution_authorized"] is False
    assert json.loads(event.read_text()) == original
    notice = context._optional_campaign_notice(payload, latest)
    assert "unavailable" in notice.lower() and "refused" in notice.lower()
    assert "Campaign refresh-records" not in notice


@pytest.mark.parametrize("boundary", ["native-identity", "receipt-write"])
def test_optional_failure_containment_never_swallows_mandatory_owner_failure(
    tmp_path, monkeypatch, boundary
):
    import session_context as context

    _, state, payload, event, original = native(tmp_path, monkeypatch)
    latest = state.home / ".synthesis/agent-conformance/live/public-sessionstart.json"
    before = latest.read_bytes()

    def refused(*args, **kwargs):
        raise PermissionError("synthetic mandatory refusal")

    monkeypatch.setattr(
        context,
        "client_provenance" if boundary == "native-identity" else "atomic_json_write",
        refused,
    )
    with pytest.raises(PermissionError, match="mandatory refusal"):
        context.record_live_receipt(payload, latest)
    assert latest.read_bytes() == before
    assert json.loads(event.read_text()) == original
