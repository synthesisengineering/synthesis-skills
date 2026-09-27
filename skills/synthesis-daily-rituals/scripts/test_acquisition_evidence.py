"""Acquisition coverage controls use synthetic accounts, IDs and local bytes only."""

import hashlib
import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

D = Path(__file__).resolve().parent
sys.path.insert(0, str(D))
A = importlib.import_module("acquisition_evidence")
W = importlib.import_module("sync_watermark")

NOW = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
START = NOW - timedelta(hours=1)
END = NOW - timedelta(minutes=1)


def saved(tmp_path, body):
    p = tmp_path / "saved.md"
    p.write_text(body)
    return [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}]


def observation():
    return {
        "observed_at": NOW.isoformat(),
        "tool_call_id": "synthetic-call",
        "complete": True,
        "next_cursor": None,
    }


def meeting(tmp_path):
    return {
        "schema": 1,
        "workspace": "fixture",
        "surface": "meetings",
        "from": START.isoformat(),
        "through": END.isoformat(),
        "archive_root": str(tmp_path),
        "archives": saved(
            tmp_path,
            "# Synthetic\n**Source ID:** google-drive:doc-1\n"
            + "".join(
                f"00:{i:02}:00\nAlice Chen: Synthetic dialogue.\nBob Smith: Reply.\n"
                for i in range(10)
            ),
        ),
        "declared_sources": ["google-drive"],
        "sources": [
            {
                "id": "google-drive",
                "account": "synthetic@example.invalid",
                "readiness": {
                    "status": "authenticated",
                    "account": "synthetic@example.invalid",
                    "observed_at": NOW.isoformat(),
                    "tool_call_id": "identity-call",
                },
                "inventory": {
                    **observation(),
                    "from": START.isoformat(),
                    "through": END.isoformat(),
                    "positive_control": {
                        "observed": True,
                        "source": "google-drive",
                        "account": "synthetic@example.invalid",
                        "observed_at": NOW.isoformat(),
                        "source_id": "doc-1",
                        "tool_call_id": "control-call",
                    },
                    "documents": [
                        {"source_id": "doc-1", "occurred_at": START.isoformat()}
                    ],
                },
            }
        ],
    }


def validate(e, **kw):
    return A.validate(
        e, workspace="fixture", surface=e["surface"], through=END, now=NOW, **kw
    )


def test_meeting_positive_and_actual_archive_bytes(tmp_path):
    e = meeting(tmp_path)
    assert validate(e)["can_advance"]
    (tmp_path / "saved.md").write_text("changed")
    with pytest.raises(ValueError, match="bytes differ"):
        validate(e)


@pytest.mark.parametrize(
    "mutation",
    [
        "auth",
        "account",
        "stale",
        "cursor",
        "bounded",
        "control",
        "window",
        "duplicate",
        "foreign",
        "missing-header",
    ],
)
def test_meeting_negative_controls(tmp_path, mutation):
    e = meeting(tmp_path)
    s = e["sources"][0]
    i = s["inventory"]
    if mutation == "auth":
        s["readiness"]["status"] = "unknown"
    if mutation == "account":
        s["readiness"]["account"] = "foreign@example.invalid"
    if mutation == "stale":
        s["readiness"]["observed_at"] = (NOW - timedelta(days=2)).isoformat()
    if mutation == "cursor":
        i["next_cursor"] = "more"
    if mutation == "bounded":
        i["complete"] = False
    if mutation == "control":
        i["positive_control"]["observed"] = False
    if mutation == "window":
        i["from"] = END.isoformat()
    if mutation == "duplicate":
        i["documents"] *= 2
    if mutation == "foreign":
        e["workspace"] = "foreign"
    if mutation == "missing-header":
        e["archives"] = saved(tmp_path, "# Synthetic without source ID\n")
    with pytest.raises(ValueError):
        validate(e)


def test_gap_decision_preserves_unknown_coverage_and_watermark(tmp_path):
    e = meeting(tmp_path)
    e["sources"][0]["inventory"]["documents"].append(
        {"source_id": "doc-2", "occurred_at": START.isoformat()}
    )
    e["gap_decisions"] = [
        {
            "source": "google-drive",
            "source_id": "doc-2",
            "disposition": "source-unavailable",
            "reason": "fixture unavailable",
            "evidence_ref": "fixture-call",
        }
    ]
    r = validate(e)
    assert not r["can_advance"] and r["gaps"][0]["decision"]
    home = tmp_path / "state"
    W.begin("fixture", now=START, home=home)
    p = W.store_path("fixture", home)
    before = p.read_bytes()
    with pytest.raises(ValueError, match="unresolved gaps"):
        W.advance(
            "fixture", "meetings", END.isoformat(), now=NOW, home=home, acquisition=e
        )
    assert p.read_bytes() == before


def test_successful_watermark_binds_coverage(tmp_path):
    e = meeting(tmp_path)
    home = tmp_path / "state"
    r = W.advance(
        "fixture", "meetings", END.isoformat(), now=NOW, home=home, acquisition=e
    )
    assert r["moved"]
    assert (
        W.load("fixture", home)["surfaces"]["meetings"]["acquisition"][
            "archived_documents"
        ]
        == 1
    )


def test_previous_watermark_gap_refuses(tmp_path):
    e = meeting(tmp_path)
    with pytest.raises(ValueError, match="gap after"):
        validate(e, previous=START - timedelta(seconds=1))


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "unreadable", "ancestor"])
def test_archive_alias_modes_and_ownership_bounds(tmp_path, kind):
    e = meeting(tmp_path)
    p = tmp_path / "saved.md"
    if kind == "symlink":
        p.rename(tmp_path / "real.md")
        p.symlink_to(tmp_path / "real.md")
    if kind == "hardlink":
        os.link(p, tmp_path / "linked.md")
    if kind == "unreadable":
        p.chmod(0)
    if kind == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        e["archive_root"] = str(alias)
    try:
        with pytest.raises((ValueError, OSError)):
            validate(e)
    finally:
        if kind == "unreadable":
            p.chmod(0o600)


def slack(tmp_path):
    parent = f"{int(START.timestamp()) - 900}.000000"
    reply = f"{int(START.timestamp()) + 10}.000000"
    top = f"{int(START.timestamp()) + 20}.000000"
    return {
        "schema": 1,
        "workspace": "fixture",
        "surface": "slack",
        "from": START.isoformat(),
        "through": END.isoformat(),
        "archive_root": str(tmp_path),
        "archives": saved(
            tmp_path,
            f"**Message ID:** C123:{reply}\nSynthetic reply\n**Message ID:** C123:{top}\nSynthetic top level\n",
        ),
        "declared_targets": ["C123"],
        "channels": [
            {
                "id": "C123",
                "known_thread_ids": [],
                "history": {
                    **observation(),
                    "detail": "detailed",
                    "from": START.isoformat(),
                    "through": END.isoformat(),
                    "messages": [{"ts": top, "reply_count": 0}],
                },
                "reply_search": {
                    **observation(),
                    "from": START.isoformat(),
                    "through": END.isoformat(),
                    "positive_control_ids": [reply],
                    "messages": [{"ts": reply, "thread_ts": parent}],
                },
                "threads": [
                    {
                        **observation(),
                        "parent_ts": parent,
                        "messages": [{"ts": parent}, {"ts": reply}],
                    }
                ],
            }
        ],
    }


def test_old_parent_with_in_window_reply_positive_control(tmp_path):
    e = slack(tmp_path)
    r = validate(e, targets=["C123"])
    assert (
        r["can_advance"] and r["checked_threads"] == 1 and r["required_messages"] == 2
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "concise",
        "thread-missing",
        "reply-missing",
        "oldest",
        "out-of-window-control",
        "control-missing",
        "cursor",
        "wrong-target",
        "archive-missing",
        "reply-gap",
    ],
)
def test_slack_realistic_negatives(tmp_path, mutation):
    e = slack(tmp_path)
    c = e["channels"][0]
    if mutation == "concise":
        c["history"]["detail"] = "concise"
    if mutation == "thread-missing":
        c["threads"] = []
    if mutation == "reply-missing":
        c["threads"][0]["messages"].pop()
    if mutation == "oldest":
        c["threads"][0]["oldest"] = int(START.timestamp())
    if mutation == "out-of-window-control":
        c["reply_search"]["positive_control_ids"] = [c["threads"][0]["parent_ts"]]
    if mutation == "control-missing":
        c["reply_search"]["positive_control_ids"] = []
    if mutation == "cursor":
        c["threads"][0]["next_cursor"] = "next"
    if mutation == "wrong-target":
        e["declared_targets"] = ["C999"]
    if mutation == "archive-missing":
        e["archives"] = []
    if mutation == "reply-gap":
        top = c["history"]["messages"][0]["ts"]
        e["archives"] = saved(tmp_path, f"**Message ID:** C123:{top}\nTop only\n")
    try:
        r = validate(e, targets=["C123"])
    except ValueError:
        return
    assert not r["can_advance"]


def test_no_positive_control_never_proves_empty_channel(tmp_path):
    e = slack(tmp_path)
    c = e["channels"][0]
    c["reply_search"]["messages"] = []
    c["reply_search"]["positive_control_ids"] = []
    with pytest.raises(ValueError, match="positive control"):
        validate(e, targets=["C123"])


def test_slack_advance_cannot_use_surface_override(tmp_path):
    with pytest.raises(ValueError, match="acquisition"):
        W.advance(
            "fixture",
            "slack",
            END.isoformat(),
            surface_level=True,
            home=tmp_path,
            now=NOW,
        )


def test_duplicate_json_and_size_limits(tmp_path):
    p = tmp_path / "e.json"
    p.write_text('{"schema":1,"schema":1}')
    with pytest.raises(ValueError, match="duplicate"):
        A.read_json(p)
    p.write_bytes(b" " * (A.MAX_BYTES + 1))
    with pytest.raises(ValueError):
        A.read_json(p)
