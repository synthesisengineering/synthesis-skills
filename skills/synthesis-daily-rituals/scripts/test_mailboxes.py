"""Declared mailbox manifest: every account swept, every gap named.

§5a repair: the ritual swept "email" (Gmail in practice) while the
personal-life iCloud mailbox rotted unread. The manifest declares every
account; plan/report judge SWEPT / BLIND / UNREACHABLE per account and
fail closed on BLIND.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _load(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MAILBOXES = _load("mailboxes.py")
WATERMARKS = _load("sync_watermark.py")

WS = "testspace"
TZ = timezone(timedelta(hours=-4))
RUN_START = datetime(2026, 9, 18, 8, 0, tzinfo=TZ)
NOW = datetime(2026, 9, 18, 9, 0, tzinfo=TZ)

MANIFEST = """\
workspace: testspace
accounts:
  - address: personal@gmail.com
    transport: gmail
    role: primary-personal
    sweep: every-ritual
  - address: life@mac.com
    transport: apple-mail
    mailboxes: [INBOX]
    role: personal-life
    sweep: every-ritual
  - address: quiet@outlook.com
    transport: apple-mail
    role: low-traffic
    sweep: weekly
  - address: alias@example.com
    transport: forwards-to
    delivers_to: life@mac.com
"""


def write_manifest(tmp_path: Path, text: str = MANIFEST) -> Path:
    path = tmp_path / "mailboxes.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def begin_run(home: Path):
    WATERMARKS.begin(WS, "day-start", now=RUN_START, home=home)


# --- manifest validation ----------------------------------------------------


def test_valid_manifest_loads(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    assert manifest["workspace"] == "testspace"
    assert [a["address"] for a in manifest["accounts"]] == [
        "personal@gmail.com", "life@mac.com", "quiet@outlook.com", "alias@example.com",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "workspace: testspace\naccounts: []\n",
        "accounts:\n  - address: a@b.co\n    transport: gmail\n    role: r\n    sweep: every-ritual\n",
        "workspace: testspace\naccounts:\n  - address: a@b.co\n    transport: pager\n    role: r\n    sweep: every-ritual\n",
        "workspace: testspace\naccounts:\n  - address: a@b.co\n    transport: forwards-to\n",
        "workspace: testspace\naccounts:\n  - address: a@b.co\n    transport: gmail\n    sweep: every-ritual\n",
        "workspace: testspace\naccounts:\n  - address: a@b.co\n    transport: gmail\n    role: r\n    sweep: sometimes\n",
        "workspace: testspace\naccounts:\n  - address: a@b.co\n    transport: gmail\n    role: r\n    sweep: every-ritual\n  - address: a@b.co\n    transport: gmail\n    role: r\n    sweep: every-ritual\n",
        "workspace: testspace\naccounts:\n  - address: not-an-address\n    transport: gmail\n    role: r\n    sweep: every-ritual\n",
        "workspace: testspace\naccounts:\n  - address: a@b.co\n    transport: gmail\n    role: r\n    sweep: every-ritual\n    mailboxes: []\n",
    ],
)
def test_invalid_manifests_refuse(tmp_path: Path, text: str) -> None:
    with pytest.raises(ValueError):
        MAILBOXES.load_manifest(write_manifest(tmp_path, text))


def test_missing_manifest_refuses(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        MAILBOXES.load_manifest(tmp_path / "absent.yaml")


# --- due computation --------------------------------------------------------


def test_due_covers_always_weekly_and_skips_aliases(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    due = MAILBOXES.due_accounts(manifest, WS, NOW, home=tmp_path)
    assert [a["address"] for a in due] == [
        "personal@gmail.com", "life@mac.com", "quiet@outlook.com",
    ]


def test_weekly_not_due_when_recently_swept(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    WATERMARKS.advance(WS, "email", "now", targets=["quiet@outlook.com"],
                       now=NOW - timedelta(days=1), home=tmp_path)
    due = MAILBOXES.due_accounts(manifest, WS, NOW, home=tmp_path)
    assert "quiet@outlook.com" not in [a["address"] for a in due]


def test_weekly_due_again_after_seven_days(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    WATERMARKS.advance(WS, "email", "now", targets=["quiet@outlook.com"],
                       now=NOW - timedelta(days=8), home=tmp_path)
    due = MAILBOXES.due_accounts(manifest, WS, NOW, home=tmp_path)
    assert "quiet@outlook.com" in [a["address"] for a in due]


def test_on_request_only_when_included(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path, MANIFEST + """\
  - address: archive@example.com
    transport: m365
    role: archive
    sweep: on-request
"""))
    assert "archive@example.com" not in [
        a["address"] for a in MAILBOXES.due_accounts(manifest, WS, NOW, home=tmp_path)
    ]
    assert "archive@example.com" in [
        a["address"] for a in MAILBOXES.due_accounts(
            manifest, WS, NOW, include_on_request=frozenset({"archive@example.com"}),
            home=tmp_path,
        )
    ]


# --- report judgments -------------------------------------------------------


def test_report_requires_an_open_run(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    with pytest.raises(ValueError, match="no open run"):
        MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)


def test_unswept_due_accounts_are_blind_and_fail(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    begin_run(tmp_path)
    rows, ok = MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)
    assert ok is False
    assert {row["address"]: row["state"] for row in rows} == {
        "personal@gmail.com": "BLIND",
        "life@mac.com": "BLIND",
        "quiet@outlook.com": "BLIND",
    }


def test_swept_accounts_pass(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    begin_run(tmp_path)
    for address in ("personal@gmail.com", "life@mac.com", "quiet@outlook.com"):
        WATERMARKS.advance(WS, "email", "now", targets=[address], now=NOW, home=tmp_path)
    rows, ok = MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)
    assert ok is True
    assert {row["state"] for row in rows} == {"SWEPT"}


def test_unreachable_passes_loud(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    begin_run(tmp_path)
    WATERMARKS.advance(WS, "email", "now", targets=["personal@gmail.com", "quiet@outlook.com"],
                       now=NOW, home=tmp_path)
    WATERMARKS.defer(WS, "email", "unreachable: apple-mail auth expired",
                     target="life@mac.com", now=NOW, home=tmp_path)
    rows, ok = MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)
    assert ok is True
    by_address = {row["address"]: row for row in rows}
    assert by_address["life@mac.com"]["state"] == "UNREACHABLE"
    assert "apple-mail" in by_address["life@mac.com"]["detail"]


def test_plain_deferral_passes_with_reason(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    begin_run(tmp_path)
    WATERMARKS.advance(WS, "email", "now", targets=["personal@gmail.com", "quiet@outlook.com"],
                       now=NOW, home=tmp_path)
    WATERMARKS.defer(WS, "email", "traveling; will sweep tonight",
                     target="life@mac.com", now=NOW, home=tmp_path)
    rows, ok = MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)
    assert ok is True
    by_address = {row["address"]: row for row in rows}
    assert by_address["life@mac.com"]["state"] == "DEFERRED"


def test_stale_deferral_is_blind_again(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path))
    begin_run(tmp_path)
    WATERMARKS.advance(WS, "email", "now", targets=["personal@gmail.com", "quiet@outlook.com"],
                       now=NOW, home=tmp_path)
    WATERMARKS.defer(WS, "email", "unreachable: outage",
                     target="life@mac.com", now=NOW - timedelta(days=2), home=tmp_path)
    rows, ok = MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)
    assert ok is False
    by_address = {row["address"]: row for row in rows}
    assert by_address["life@mac.com"]["state"] == "BLIND"


def test_swept_but_not_due_is_reported(tmp_path: Path) -> None:
    manifest = MAILBOXES.load_manifest(write_manifest(tmp_path, MANIFEST + """\
  - address: archive@example.com
    transport: m365
    role: archive
    sweep: on-request
"""))
    begin_run(tmp_path)
    for address in ("personal@gmail.com", "life@mac.com", "quiet@outlook.com",
                    "archive@example.com"):
        WATERMARKS.advance(WS, "email", "now", targets=[address], now=NOW, home=tmp_path)
    rows, ok = MAILBOXES.report_accounts(manifest, WS, NOW, home=tmp_path)
    assert ok is True
    by_address = {row["address"]: row for row in rows}
    assert by_address["archive@example.com"]["state"] == "SWEPT"


def test_cli_plan_and_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path))
    manifest = write_manifest(tmp_path)
    WATERMARKS.begin(WS, "day-start")
    out = capsys.readouterr()
    assert MAILBOXES.main(["--manifest", str(manifest), "--workspace", WS, "plan"]) == 0
    plan_out = capsys.readouterr().out
    assert "life@mac.com" in plan_out and "alias@example.com" not in plan_out
    assert MAILBOXES.main(["--manifest", str(manifest), "--workspace", WS, "report"]) == 2
    assert "0 of 3 swept" in capsys.readouterr().out
