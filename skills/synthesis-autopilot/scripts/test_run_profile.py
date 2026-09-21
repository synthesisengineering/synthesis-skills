"""Fixtures for autopilot run profiles.

Derived from the principal's standing complaint: every autonomous run
starts with a retyped paragraph of standing instructions, and each
retelling drops a clause that then silently doesn't happen. The profile
resolves the checklist deterministically, freezes it into the plan, and
refuses a goals-met close until every item is done or waived aloud.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("run_profile.py")
GATE_PATH = Path(__file__).with_name("autopilot_gate.py")
SPEC = importlib.util.spec_from_file_location("run_profile", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def ensure_board(tmp_path: Path) -> Path:
    board = tmp_path / "board.md"
    if not board.exists():
        board.write_text(
            "# Board\n\nSchema: v4\n\n## Active sessions\n\n"
            "| session uuid | compact id | speakable id v1 | legacy id | agent | machine | client session ref | project | started | heartbeat | mode | workspace(s) / branch | goal | claimed areas (advisory lock) | context role | status |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| session-a | s-aaaa-bbbb-cccc | words-1 | | agent | machine | tool:session-a | alpha | 2026-09-03T12:00:00-04:00 | 2026-09-03T12:00:00-04:00 | interactive | /tmp/p | fixture | /tmp/p/** | owner | active |\n"
            "\n## Messages\n",
            encoding="utf-8",
        )
    return board


def run_cli(tmp_path: Path, *args: str, env_extra=None):
    board = ensure_board(tmp_path)
    env = {
        **os.environ,
        "AUTOPILOT_GATE_STATE_DIR": str(tmp_path / "engagements"),
        "AUTOPILOT_GATE_SESSION_ID": "session-a",
        "AUTOPILOT_GATE_PROJECT_ID": "alpha",
        "AUTOPILOT_GATE_COORDINATION_BOARD": str(board),
        "SYNTHESIS_CLIENT_SESSION_REF": "tool:session-a",
        **(env_extra or {}),
    }
    return subprocess.run([sys.executable, str(MODULE_PATH), *args],
                          capture_output=True, text=True, env=env)


def run_gate(tmp_path: Path, *args: str):
    board = ensure_board(tmp_path)
    env = {
        **os.environ,
        "AUTOPILOT_GATE_STATE_DIR": str(tmp_path / "engagements"),
        "AUTOPILOT_GATE_SESSION_ID": "session-a",
        "AUTOPILOT_GATE_PROJECT_ID": "alpha",
        "AUTOPILOT_GATE_COORDINATION_BOARD": str(board),
        "SYNTHESIS_CLIENT_SESSION_REF": "tool:session-a",
    }
    return subprocess.run([sys.executable, str(GATE_PATH), *args],
                          capture_output=True, text=True, env=env)


def check_plan(items: list[str], grant: str = "none") -> str:
    lines = ["# Plan", "", "## Standing checklist (frozen test)"]
    for item in items:
        lines.append(f"- [x] {item} — evidence here")
    lines.append(f"Deploy authority this run: {grant}")
    lines.append("")
    lines.append("## Phases")
    return "\n".join(lines) + "\n"


def test_resolve_shipped_default_only(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "resolve", "--project", str(tmp_path),
                   "--user-profile", str(tmp_path / "absent.json"))
    assert done.returncode == 0, done.stderr
    effective = json.loads(done.stdout)
    assert len(effective["items"]) == 8
    assert all(i["provenance"] == "shipped" for i in effective["items"])
    assert effective["deploy_grant"] == {"text": "none", "provenance": "none"}
    assert effective["disabled"] == []


def test_resolve_user_disables_and_adds(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({
        "schema": 1,
        "items": {
            "blog-seeds": {"enabled": False},
            "custom-1": {"text": "Custom.", "evidence_hint": "Custom evidence."},
        },
    }), encoding="utf-8")
    done = run_cli(tmp_path, "resolve", "--project", str(tmp_path),
                   "--user-profile", str(profile))
    assert done.returncode == 0, done.stderr
    effective = json.loads(done.stdout)
    ids = [i["id"] for i in effective["items"]]
    assert "blog-seeds" not in ids
    assert "custom-1" in ids
    assert {"id": "blog-seeds", "by": "user"} in effective["disabled"]
    custom = next(i for i in effective["items"] if i["id"] == "custom-1")
    assert custom["provenance"] == "user"


def test_resolve_file_deploy_grant_ignored(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({
        "schema": 1, "deploy_grant": "always approve everything",
        "items": {},
    }), encoding="utf-8")
    done = run_cli(tmp_path, "resolve", "--project", str(tmp_path),
                   "--user-profile", str(profile))
    assert done.returncode == 0, done.stderr
    effective = json.loads(done.stdout)
    assert effective["deploy_grant"]["text"] == "none"
    assert "never from a file" in done.stderr


def test_resolve_spoken_grant_honored(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "resolve", "--project", str(tmp_path),
                   "--user-profile", str(tmp_path / "absent.json"),
                   "--delta-json",
                   '{"disable": ["blog-seeds"], '
                   '"deploy_grant": "overnight deploys approved"}')
    assert done.returncode == 0, done.stderr
    effective = json.loads(done.stdout)
    assert effective["deploy_grant"] == {
        "text": "overnight deploys approved", "provenance": "spoken"}
    assert {"id": "blog-seeds", "by": "spoken"} in effective["disabled"]


def test_resolve_malformed_user_profile_fails(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text("{nope", encoding="utf-8")
    done = run_cli(tmp_path, "resolve", "--project", str(tmp_path),
                   "--user-profile", str(profile))
    assert done.returncode == 2
    assert "unreadable" in done.stderr


def test_init_stdout_emits_default(tmp_path: Path) -> None:
    done = run_cli(tmp_path, "init", "--stdout")
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["items"].keys() == (
        MODULE.DEFAULT_PROFILE["items"].keys())


def fixture_plan(tmp_path: Path) -> Path:
    """Plans must sit under the fixture board's claimed area (/tmp/p/**)."""
    claimed = Path("/tmp/p")
    claimed.mkdir(parents=True, exist_ok=True)
    return claimed / f"profile-{tmp_path.name}.md"


def register_with_profile(tmp_path: Path, plan: Path, grant: str = "none"):
    effective = MODULE.resolve(tmp_path, tmp_path / "absent.json",
                               {"deploy_grant": grant} if grant != "none"
                               else None)
    if grant == "none":
        effective = MODULE.resolve(tmp_path, tmp_path / "absent.json", None)
    frozen = tmp_path / "effective.json"
    frozen.write_text(json.dumps(effective), encoding="utf-8")
    plan.write_text(check_plan([i["id"] for i in effective["items"]],
                               grant), encoding="utf-8")
    done = run_gate(tmp_path, "register", "--plan", str(plan),
                    "--mission", "fixture run", "--profile", str(frozen))
    assert done.returncode == 0, done.stderr
    return effective


def test_verify_happy_path_and_close(tmp_path: Path) -> None:
    plan = fixture_plan(tmp_path)
    effective = register_with_profile(tmp_path, plan)
    done = run_cli(tmp_path, "verify", "--plan", str(plan))
    assert done.returncode == 0, done.stderr
    assert f"{len(effective['items'])} items" in done.stdout
    closed = run_gate(tmp_path, "close", "--plan", str(plan), "--goals-met")
    assert closed.returncode == 0, closed.stderr


def test_close_refused_without_verify(tmp_path: Path) -> None:
    plan = fixture_plan(tmp_path)
    register_with_profile(tmp_path, plan)
    closed = run_gate(tmp_path, "close", "--plan", str(plan), "--goals-met")
    assert closed.returncode == 2
    assert "verify" in closed.stderr


def test_verify_missing_item_fails(tmp_path: Path) -> None:
    plan = fixture_plan(tmp_path)
    effective = register_with_profile(tmp_path, plan)
    dropped = effective["items"][0]["id"]
    kept = [i["id"] for i in effective["items"][1:]]
    plan.write_text(check_plan(kept), encoding="utf-8")
    done = run_cli(tmp_path, "verify", "--plan", str(plan))
    assert done.returncode == 2
    assert dropped in done.stderr


def test_verify_waived_passes_bare_unchecked_fails(tmp_path: Path) -> None:
    plan = fixture_plan(tmp_path)
    effective = register_with_profile(tmp_path, plan)
    ids = [i["id"] for i in effective["items"]]
    lines = ["# Plan", "", "## Standing checklist (frozen test)"]
    lines.append(f"- [x] {ids[0]} — done with evidence")
    lines.append(f"- [ ] {ids[1]} — WAIVED: nothing user-facing changed")
    for item in ids[2:]:
        lines.append(f"- [x] {item} — evidence here")
    lines += ["Deploy authority this run: none", "", "## Phases"]
    plan.write_text("\n".join(lines) + "\n", encoding="utf-8")
    done = run_cli(tmp_path, "verify", "--plan", str(plan))
    assert done.returncode == 0, done.stderr

    bare = plan.read_text(encoding="utf-8").replace(
        f"- [x] {ids[0]} — done with evidence",
        f"- [ ] {ids[0]} — will do later")
    plan.write_text(bare, encoding="utf-8")
    failed = run_cli(tmp_path, "verify", "--plan", str(plan))
    assert failed.returncode == 2
    assert "WAIVED" in failed.stderr


def test_verify_unknown_item_and_grant_mismatch_fail(tmp_path: Path) -> None:
    plan = fixture_plan(tmp_path)
    effective = register_with_profile(tmp_path, plan)
    ids = [i["id"] for i in effective["items"]]
    bad = check_plan(ids + ["invented-item"])
    plan.write_text(bad, encoding="utf-8")
    done = run_cli(tmp_path, "verify", "--plan", str(plan))
    assert done.returncode == 2
    assert "invented-item" in done.stderr

    mismatch = check_plan(ids, grant="someone else approved")
    plan.write_text(mismatch, encoding="utf-8")
    failed = run_cli(tmp_path, "verify", "--plan", str(plan))
    assert failed.returncode == 2
    assert "deploy line" in failed.stderr


def test_close_refused_after_plan_edit(tmp_path: Path) -> None:
    plan = fixture_plan(tmp_path)
    register_with_profile(tmp_path, plan)
    assert run_cli(tmp_path, "verify", "--plan", str(plan)).returncode == 0
    with open(plan, "a", encoding="utf-8") as fh:
        fh.write("\nEdited after verification.\n")
    closed = run_gate(tmp_path, "close", "--plan", str(plan), "--goals-met")
    assert closed.returncode == 2
    assert "changed since" in closed.stderr
