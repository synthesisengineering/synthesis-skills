"""R1.5: the context records doctor. Every scenario from the v5 code evaluation (project state,
section 3, R1.5) is a test here, plus the header-lag check carried from the old context editor."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "context_doctor.py"
SPEC = importlib.util.spec_from_file_location("context_doctor", SCRIPT)
doctor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = doctor
SPEC.loader.exec_module(doctor)

TODAY = date.today()
RECENT = (TODAY - timedelta(days=2)).isoformat()


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNTHESIS_HOME", str(tmp_path / "synthesis-home"))
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("SYNTHESIS_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "MUSE_SESSION_ID"):
        monkeypatch.delenv(key, raising=False)


def context(status="Active", phase="Build", last=RECENT, body=""):
    return f"# Project\n\n**Phase:** {phase}\n**Status:** {status}\n**Last session:** {last}\n\n## Current State\n\nWorking.\n{body}"


@pytest.fixture
def kb(tmp_path):
    """A knowledge root published to a remote, with one healthy active project."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    root = tmp_path / "ai-knowledge-test"
    subprocess.run(["git", "clone", "-q", str(remote), str(root)], check=True, capture_output=True)
    root.joinpath("projects").mkdir()
    write_index(root, [{"id": "alpha", "status": "active", "last_session": RECENT}])
    add_project(root, "alpha", context())
    publish(root)
    return root


def write_index(root, entries):
    lines = ["# Projects Index", "projects:"]
    for entry in entries:
        lines.append(f"  - id: {entry['id']}")
        lines += [f"    {k}: {v}" for k, v in entry.items() if k != "id"]
        lines += ["    tags:", "      - nested", "    description: >", "      Folded text: not a field."]
    (root / "projects" / "index.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_project(root, pid, text, log=f"### {RECENT}: work\n\nDone.\n"):
    project = root / "projects" / pid
    (project / "sessions").mkdir(parents=True, exist_ok=True)
    (project / "CONTEXT.md").write_text(text, encoding="utf-8")
    (project / "sessions" / f"{RECENT[:7]}.md").write_text(f"# Log\n\n{log}", encoding="utf-8")
    return project


def publish(root, message="records"):
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message)
    _git(root, "push", "-q", "origin", "main")


def run(*args, capsys):
    code = doctor.main(list(args))
    return code, capsys.readouterr().out


def findings(root, capsys, *extra):
    code, out = run("--root", str(root), "--json", *extra, capsys=capsys)
    data = json.loads(out)
    return code, {(f["project"], f["check"], f["severity"]) for f in data["findings"]}, data


def test_a_healthy_root_exits_zero(kb, capsys):
    code, found, _ = findings(kb, capsys)
    assert code == 0 and found == set()


def test_context_over_150_lines_active_or_80_completed_fails_and_reference_over_300_warns(kb, capsys):
    add_project(kb, "alpha", context(body="line\n" * 160))
    add_project(kb, "done", context(status="Completed", body="line\n" * 90))
    (kb / "projects" / "alpha" / "REFERENCE.md").write_text("fact\n" * 310, encoding="utf-8")
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "done", "status": "completed", "completed_date": RECENT}])
    publish(kb)
    code, found, _ = findings(kb, capsys)
    assert code == 1
    assert {("alpha", "context-budget", "defect"), ("done", "context-budget", "defect"),
            ("alpha", "reference-budget", "warning")} <= found


def test_a_standing_project_over_its_reference_budget_is_told_to_shard(kb, capsys):
    (kb / "projects" / "alpha" / "REFERENCE.md").write_text("fact\n" * 310, encoding="utf-8")
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT, "bounded": "false"}])
    publish(kb)
    _, _, data = findings(kb, capsys)
    assert "shard into reference/" in data["findings"][0]["remedy"]


@pytest.mark.parametrize("status_line, index_status, disagrees", [
    ("Active", "completed", True),
    ("Completed", "active", True),
    ("Active — Phase 4 is COMPLETE", "active", False),   # the leading clause decides
    ("Not complete; still building", "active", False),   # "not complete" is never completed
])
def test_index_and_context_status_must_agree(kb, capsys, status_line, index_status, disagrees):
    add_project(kb, "alpha", context(status=status_line))
    write_index(kb, [{"id": "alpha", "status": index_status, "last_session": RECENT, "completed_date": RECENT}])
    publish(kb)
    _, found, _ = findings(kb, capsys)
    assert (("alpha", "status-agreement", "defect") in found) is disagrees


def test_status_wins_over_phase_wording(kb, capsys):
    add_project(kb, "alpha", context(phase="Triage — inventory complete"))
    publish(kb)
    assert findings(kb, capsys)[0] == 0


def test_unknown_status_is_a_defect_and_a_retired_one_a_warning(kb, capsys):
    add_project(kb, "beta", context())
    write_index(kb, [{"id": "alpha", "status": "wip", "last_session": RECENT},
                     {"id": "beta", "status": "ongoing", "last_session": RECENT}])
    publish(kb)
    _, found, _ = findings(kb, capsys)
    assert ("alpha", "status-vocabulary", "defect") in found and ("beta", "status-vocabulary", "warning") in found


def test_last_session_behind_the_newest_log_entry_fails(kb, capsys):
    older = (TODAY - timedelta(days=9)).isoformat()
    add_project(kb, "alpha", context(last=older))
    publish(kb)
    _, found, data = findings(kb, capsys)
    assert ("alpha", "freshness", "defect") in found
    assert any("behind the newest dated entry" in f["message"] for f in data["findings"])


def test_same_day_staleness_is_caught_by_round_and_each_field_is_judged_alone(kb, capsys):
    log = f"### {RECENT} (round 10): first\n\nx\n\n### {RECENT} (round 11): second\n\ny\n"
    add_project(kb, "alpha", context(phase="Review (round 11)", last=f"{RECENT} (round 10)"), log=log)
    publish(kb)
    _, _, data = findings(kb, capsys)
    stale = [f["message"] for f in data["findings"] if f["check"] == "header-currency"]
    assert stale == ["**Last session:** says round 10; the session log's newest entry is round 11"]


def test_the_first_ordinal_in_a_field_is_its_identity(kb, capsys):
    log = f"### {RECENT} (round 11): second\n\ny\n"
    add_project(kb, "alpha", context(phase="Review (round 11 — round 10 refuted)",
                                     last=f"{RECENT} (round 11, after round 9)"), log=log)
    publish(kb)
    _, found, _ = findings(kb, capsys)
    assert not any(check in ("header-currency", "header-lag") for _, check, _ in found)


def test_phase_moved_but_last_session_did_not(kb, capsys):
    log = f"### {RECENT} (wave 3): x\n\ny\n"
    add_project(kb, "alpha", context(phase="Wave 4 started", last=f"{RECENT} (wave 3)"), log=log)
    publish(kb)
    _, found, _ = findings(kb, capsys)
    assert ("alpha", "header-lag", "defect") in found


def test_a_bulk_commit_touching_many_projects_is_not_a_session(kb, capsys):
    for pid in ("beta", "gamma"):
        add_project(kb, pid, context())
    write_index(kb, [{"id": p, "status": "active", "last_session": RECENT} for p in ("alpha", "beta", "gamma")])
    publish(kb)
    for pid in ("alpha", "beta", "gamma"):
        (kb / "projects" / pid / "notes.md").write_text("bulk reformat\n", encoding="utf-8")
    publish(kb, "Reformat every project")  # a commit today, but no session was recorded today
    assert findings(kb, capsys)[0] == 0


def test_a_stale_section_marker_fails(kb, capsys):
    add_project(kb, "alpha", context(body="\n*State as of: 2000-01-01*\n"))
    publish(kb)
    assert ("alpha", "body-currency", "defect") in findings(kb, capsys)[1]


def test_item_stamps(kb, capsys):
    old = (TODAY - timedelta(days=30)).isoformat()
    body = (f"\n## Open items\n\n- [ ] chase the reply (as of {old}, review 7d)\n"
            f"- [ ] fresh item (as of {RECENT}, review 7d)\n- [x] closed item (as of {old})\n"
            "- [ ] no stamp at all\n- [ ] vague (as of yesterday)\n- [ ] impossible (as of 2026-02-30)\n"
            "\n## Narrative\n\n- a bullet of prose is not an obligation\n")
    add_project(kb, "alpha", context(body=body))
    publish(kb)
    _, _, data = findings(kb, capsys)
    messages = [f["message"] for f in data["findings"] if f["check"] == "item-currency"]
    assert any("chase the reply" in m and "past its stamp" in m for m in messages)
    assert any("does not parse as a stamp" in m and "vague" in m for m in messages)
    assert any("impossible stamp date 2026-02-30" in m for m in messages)
    assert any("'Open items' lists 1 live item(s) with no" in m for m in messages)
    assert not any("closed item" in m or "fresh item" in m or "Narrative" in m for m in messages)
    assert all(f["severity"] == "warning" for f in data["findings"])  # a new convention starts as a warning


def test_paused_and_completed_projects_stay_quiet_on_advice_but_not_on_work_after_completion(kb, capsys):
    old = (TODAY - timedelta(days=60)).isoformat()
    add_project(kb, "paused", context(status="Paused", last=old, body="\n## Next\n\n- [ ] someday\n"))
    (kb / "projects" / "paused" / "REFERENCE.md").write_text("fact\n" * 400, encoding="utf-8")
    add_project(kb, "done", context(status="Completed", last=old, body="\n## Open\n\n- [ ] still owed\n"))
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "paused", "status": "paused", "last_session": old},
                     {"id": "done", "status": "completed", "completed_date": old, "last_session": old}])
    publish(kb)
    _, found, data = findings(kb, capsys)
    assert not any(p == "paused" for p, _, _ in found)
    assert ("done", "terminal-project-active", "warning") in found  # its log has a session after completion
    assert ("done", "terminal-project-open-items", "warning") in found
    assert data["coverage"]["item-currency"]["skipped"] == 2


def test_a_post_close_review_silences_the_finding_until_a_new_commit_and_must_resolve(kb, capsys):
    old = (TODAY - timedelta(days=60)).isoformat()
    add_project(kb, "done", context(status="Completed", last=old))
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "done", "status": "completed", "completed_date": old}])
    publish(kb)
    head = _git(kb, "rev-parse", "HEAD")
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "done", "status": "completed", "completed_date": old, "post_close_reviewed_through": head}])
    publish(kb)
    assert not any(c == "terminal-project-active" for _, c, _ in findings(kb, capsys)[1])
    (kb / "projects" / "done" / "late.md").write_text("more\n", encoding="utf-8")
    publish(kb)
    assert ("done", "terminal-project-active", "warning") in findings(kb, capsys)[1]
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "done", "status": "completed", "completed_date": old, "post_close_reviewed_through": "0" * 40}])
    publish(kb)
    assert ("done", "post-close-review-unresolvable", "defect") in findings(kb, capsys)[1]


def test_unreadable_or_non_git_sources_cannot_be_called_healthy(tmp_path, capsys):
    loose = tmp_path / "loose"
    (loose / "projects" / "alpha").mkdir(parents=True)
    (loose / "projects" / "alpha" / "CONTEXT.md").write_text(context(), encoding="utf-8")
    assert run("--root", str(loose), capsys=capsys)[0] == 2
    assert run("--root", str(tmp_path / "missing"), capsys=capsys)[0] == 2


def test_nothing_to_audit_is_not_a_clean_result(tmp_path, capsys):
    root = tmp_path / "empty"
    (root / "projects").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    assert run("--root", str(root), capsys=capsys)[0] == 2


def test_projects_without_an_index_and_index_entries_without_a_folder_are_defects(kb, capsys):
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "ghost", "status": "active"}, {"id": "gone", "status": "archived"}])
    add_project(kb, "stray", context())
    publish(kb)
    _, found, _ = findings(kb, capsys)
    assert ("ghost", "context-present", "defect") in found and ("stray", "status-agreement", "defect") in found
    assert not any(p == "gone" for p, _, _ in found)
    (kb / "projects" / "index.yaml").unlink()
    publish(kb)
    assert ("(ai-knowledge-test)", "status-agreement", "defect") in findings(kb, capsys)[1]


def test_a_gitignored_context_is_a_defect_and_an_uncommitted_one_a_warning(kb, capsys):
    add_project(kb, "secret", context())
    (kb / ".gitignore").write_text("projects/secret/CONTEXT.md\n", encoding="utf-8")
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT},
                     {"id": "secret", "status": "active", "last_session": RECENT}])
    publish(kb)
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text(context(body="edited\n"), encoding="utf-8")
    _, found, _ = findings(kb, capsys)
    assert ("secret", "untracked-context", "defect") in found
    assert ("alpha", "uncommitted-context", "warning") in found


def test_durability_no_remote_is_a_defect_and_unpushed_a_warning(kb, capsys):
    (kb / "projects" / "alpha" / "more.md").write_text("x\n", encoding="utf-8")
    _git(kb, "add", "-A")
    _git(kb, "commit", "-qm", "local only")
    assert ("(ai-knowledge-test)", "unpushed-context", "warning") in findings(kb, capsys)[1]
    _git(kb, "remote", "remove", "origin")
    assert ("(ai-knowledge-test)", "unpushed-context", "defect") in findings(kb, capsys)[1]


def test_output_leads_with_the_active_project_and_counts_the_rest(kb, capsys, tmp_path, monkeypatch):
    for i in range(5):
        add_project(kb, f"p{i}", context(body="line\n" * 160))
    add_project(kb, "alpha", context(body="\n## Next\n\n- [ ] unstamped\n"))
    write_index(kb, [{"id": "alpha", "status": "active", "last_session": RECENT}] +
                [{"id": f"p{i}", "status": "active", "last_session": RECENT} for i in range(5)])
    publish(kb)
    sessions = tmp_path / "synthesis-home" / "state" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "S1.json").write_text(json.dumps({"session": "S1", "project": "alpha"}), encoding="utf-8")
    monkeypatch.setenv("SYNTHESIS_SESSION", "S1")
    code, out = run("--root", str(kb), capsys=capsys)
    lines = out.splitlines()
    assert code == 1 and lines[2].startswith("alpha (") and "[item-currency]" in lines[3]
    assert "Other projects: 5 audited, 5 with defects" in out
    assert out.count("CONTEXT.md is 160 lines") == 0  # the rest are counted and named, not listed in full


def test_a_single_project_run_shows_its_full_list(kb, capsys):
    add_project(kb, "alpha", context(body="line\n" * 160))
    publish(kb)
    code, out = run("--project", str(kb / "projects" / "alpha"), capsys=capsys)
    assert code == 1 and "CONTEXT.md is 169 lines, over the active budget of 150" in out


def test_session_start_names_the_session_after_the_project():
    """2026-09-21: a session working a project titles itself with the project id where the client
    allows it, so the thread list reads as the work queue."""
    skill = SCRIPT.parents[1]
    assert "title the session after the project" in (skill / "SKILL.md").read_text(encoding="utf-8")
    protocol = (skill / "references" / "session-protocols.md").read_text(encoding="utf-8")
    assert "Name this session after the project" in protocol and "set_session_title" in protocol


def test_discovered_roots_without_projects_are_skipped_but_a_named_one_cannot_be_audited(kb, tmp_path, capsys):
    bare = tmp_path / "ai-knowledge-empty"
    bare.mkdir()
    (tmp_path / "synthesis-home").mkdir(exist_ok=True)
    (tmp_path / "synthesis-home" / "config.json").write_text(json.dumps({"knowledge_roots": [str(kb), str(bare)]}))
    assert run(capsys=capsys)[0] == 0  # the configured roots, one of them holding no projects
    assert run("--root", str(bare), capsys=capsys)[0] == 2
