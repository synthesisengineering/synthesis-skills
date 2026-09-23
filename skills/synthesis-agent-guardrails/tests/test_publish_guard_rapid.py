"""Fixtures for the rapid-redeploy brake (publish_guard v1.2.0).

The motivating incident (2026-08-29): a live post was re-dated and
republished 28 minutes after the publish it was correcting — the rushed
follow-up fix compounded the original mistake. A second publish of the
same repo inside the window now requires the principal's explicit, quoted
rapid-redeploy approval in the ledger.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "guards" / "publish_guard.py"
SPEC = importlib.util.spec_from_file_location("publish_guard_rapid", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

import pytest  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _parser_runtime():
    """Bind the same-repo shell parser eagerly (fails fast on layout drift)."""
    MODULE._ensure_shell_parser()
    assert MODULE.inspect_command is not None
    yield


def _stamp(tmp_path: Path, monkeypatch, repo: str, minutes_ago: float) -> None:
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path))
    path = Path(MODULE.last_publish_path(repo))
    path.parent.mkdir(parents=True, exist_ok=True)
    consumed = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    path.write_text(json.dumps({
        "repo": repo,
        "consumed_at": consumed.isoformat(),
        "summary": "previous approved publish",
    }), encoding="utf-8")


def _ledger(tmp_path: Path, extra: dict | None = None) -> None:
    led = {
        "repo": "/tmp/site", "head_sha": "x", "summary": "s",
        "approved_via": "in-chat",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    led.update(extra or {})
    (tmp_path / "approval.json").write_text(json.dumps(led), encoding="utf-8")


def test_window_engages_on_recent_publish(tmp_path, monkeypatch) -> None:
    _stamp(tmp_path, monkeypatch, "/tmp/site", minutes_ago=10)
    in_window, prior = MODULE.rapid_redeploy_state("/tmp/site")
    assert in_window and prior["summary"] == "previous approved publish"


def test_window_expires(tmp_path, monkeypatch) -> None:
    _stamp(tmp_path, monkeypatch, "/tmp/site", minutes_ago=46)
    in_window, _ = MODULE.rapid_redeploy_state("/tmp/site")
    assert not in_window


def test_window_is_per_repo(tmp_path, monkeypatch) -> None:
    """Publishing the engineering site then the personal site is the normal
    two-site flow and must not trip the brake."""
    _stamp(tmp_path, monkeypatch, "/tmp/site-a", minutes_ago=5)
    in_window, _ = MODULE.rapid_redeploy_state("/tmp/site-b")
    assert not in_window


def test_missing_state_means_no_brake(tmp_path, monkeypatch) -> None:
    """No recorded prior publish = no evidence of recency. The ledger
    remains the fail-closed core; the brake only adds a condition when
    recency is actually recorded."""
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path))
    in_window, prior = MODULE.rapid_redeploy_state("/tmp/site")
    assert not in_window and prior is None


def test_plain_ledger_does_not_authorize_rapid(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path))
    _ledger(tmp_path)
    assert not MODULE.ledger_authorizes_rapid()


def test_quoted_rapid_ledger_authorizes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path))
    _ledger(tmp_path, {"rapid_redeploy": True,
                       "rapid_redeploy_quote": "yes, republish right away"})
    assert MODULE.ledger_authorizes_rapid()


def test_rapid_flag_without_quote_refused(tmp_path, monkeypatch) -> None:
    _ledger(tmp_path, {"rapid_redeploy": True, "rapid_redeploy_quote": "  "})
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(tmp_path))
    assert not MODULE.ledger_authorizes_rapid()


def test_consume_records_last_publish(tmp_path, monkeypatch) -> None:
    """A successful consume stamps the repo's last-publish record so the
    NEXT publish sees the window."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath",
                    "/dev/null"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                    "-c", "user.email=t@t", "commit", "--allow-empty", "-q",
                    "-m", "x"], check=True)
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("PUBLISH_GUARD_STATE_DIR", str(state))
    sha = MODULE.head_sha(str(repo))
    (state / "approval.json").write_text(json.dumps({
        "repo": str(repo), "head_sha": sha, "summary": "publish one",
        "approved_via": "in-chat",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    ok, why = MODULE.consume_ledger(str(repo))
    assert ok, why
    in_window, prior = MODULE.rapid_redeploy_state(str(repo))
    assert in_window and prior["summary"] == "publish one"


def test_builtin_suite_passes() -> None:
    """The guard's hermetic --test suite runs green end to end — it was
    crashing on operator hook config and, once that was fixed, blocking on
    fixture repos with no published base. Both repairs live in the suite
    itself; this fixture keeps them there."""
    import subprocess

    proc = subprocess.run([sys.executable, str(MODULE_PATH), "--test"],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr


if __name__ == "__main__":
    # Without this, `python3 test_publish_guard_rapid.py` exited 0 having run nothing —
    # a silent false pass in a verification path.
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
