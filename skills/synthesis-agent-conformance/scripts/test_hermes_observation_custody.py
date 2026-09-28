import os
import sys
import json
import hashlib
import sqlite3
import time
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import session_context as sc  # noqa: E402


def setup(tmp_path):
    profile = tmp_path / "hermes"
    profile.mkdir(mode=0o700)
    db = sqlite3.connect(profile / "state.db")
    db.execute(
        "CREATE TABLE sessions (id TEXT,source TEXT,parent_session_id TEXT,started_at REAL,ended_at REAL,cwd TEXT,profile_name TEXT)"
    )
    db.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?)",
        ("synthetic", "cli", None, time.time(), None, str(tmp_path), "default"),
    )
    db.commit()
    db.close()
    (profile / "state.db").chmod(0o600)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    payload = {
        "hook_event_name": "on_session_start",
        "session_id": "synthetic",
        "profile": "default",
        "cwd": str(tmp_path),
    }
    return profile, state, payload


def test_observation_parent_swap_never_writes_foreign(tmp_path, monkeypatch):
    profile, state, payload = setup(tmp_path)
    other = tmp_path / "foreign"
    other.mkdir()
    target = (
        state
        / "agent-conformance/observations/hermes"
        / hashlib.sha256(b"synthetic").hexdigest()
    )
    real = sc.os.open
    fired = []

    def swap(path, flags, *a, **kw):
        if (
            not fired
            and flags & os.O_CREAT
            and (str(path).endswith(".json") or str(path).endswith(".tmp"))
        ):
            fired.append(True)
            target.rename(tmp_path / "parked-owned")
            target.symlink_to(other, target_is_directory=True)
        return real(path, flags, *a, **kw)

    monkeypatch.setattr(sc.os, "open", swap)
    try:
        sc.record_hermes_observation(
            payload, profile, {"content_digest": "a" * 64}, state
        )
    except (OSError, ValueError):
        pass
    assert fired and not list(other.iterdir())


def test_observation_genuine_source_positive_remains_non_native(tmp_path):
    profile, state, payload = setup(tmp_path)
    result = sc.record_hermes_observation(
        payload, profile, {"content_digest": "a" * 64}, state
    )
    body = json.loads(result.read_text())
    assert (
        body["kind"] == "callback-source-observation"
        and body["native_live"] == "UNKNOWN"
        and body["authority"] is False
    )
