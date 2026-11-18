"""`synthesis review`, the whole-machine review and repair plan (BACKLOG C3, roadmap FUTURE-01; the principal ruled it built
on 2026-11-18). A synthetic machine with one of each problem yields its findings and its plan, a healthy one yields an
empty plan, and nothing the review reads changes: no file, no index, no bytecode beside the scripts it loads. Each
machine lives in the test's own folders, with HOME and the synthesis home there; the checks that read the real Mac's
own settings (machine security, the sandbox's administrator files, the interpreters installed) are set to a healthy
answer where a test needs the whole picture, and the harnesses are found nowhere."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from synthesis import board, cli, doctor, install, paths, review

ROOT = Path(__file__).resolve().parents[1]
EXPORT = "com.synthesis.sessions-export"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def _published(remotes: Path, folder: Path, name: str) -> Path:
    """A repository at `folder` with one commit on main, pushed to a bare repository of its own and level with it."""
    bare = remotes / f"{name}.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(folder)], check=True)
    (folder / "README.md").write_text(f"{name}\n", encoding="utf-8")
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", "First")
    git(folder, "remote", "add", "origin", str(bare))
    git(folder, "push", "-q", "-u", "origin", "main")
    return folder


def _racy(repo: Path) -> None:
    """A tracked file touched with its content unchanged: `git status` then refreshes the index, unless told not to."""
    os.utime(repo / "README.md", ns=(time.time_ns() + 5_000_000_000,) * 2)


def _records(kb: Path, last_session: str) -> None:
    alpha = kb / "projects" / "alpha"
    (alpha / "sessions").mkdir(parents=True, exist_ok=True)
    (kb / "projects" / "index.yaml").write_text("projects:\n  - id: alpha\n    status: active\n", encoding="utf-8")
    (alpha / "CONTEXT.md").write_text(f"# Alpha\n\n**Status:** Active\n**Last session:** {last_session}\n\nA project.\n",
                                      encoding="utf-8")
    (alpha / "sessions" / "2026-11.md").write_text("# 2026-11\n\n## 2026-11-17\n\nWork.\n", encoding="utf-8")


def _schedule(plist: Path, command: Path) -> None:
    import plistlib
    plist.parent.mkdir(parents=True, exist_ok=True)
    line = f'"{command}" sessions export --all --scheduled; "{command}" sessions sync'
    plist.write_bytes(plistlib.dumps({"Label": plist.stem, "ProgramArguments": ["/bin/bash", "-lc", line]}))


def _launchd(loaded: set):
    """launchctl as the review may ask it: only `print` of a label, answered from `loaded`; any other program fails."""
    def run(argv, **kw):
        assert list(argv[:2]) == ["launchctl", "print"], f"the review ran {argv}"
        return subprocess.CompletedProcess(argv, 0 if argv[2].rsplit("/", 1)[-1] in loaded else 113, "", "")
    return run


def _real_mac_read_healthy(monkeypatch) -> None:
    """The checks that read the real Mac's own settings, answered healthy; temporary folders' virtual environments are
    the Mac's own too, so none is looked for there; and no harness is found."""
    monkeypatch.setattr(doctor, "check_security", lambda home, **kw: [doctor.Check("ok", "machine security", "set")])
    monkeypatch.setattr(doctor, "check_sandbox", lambda found=(): doctor.Check("ok", "sandbox", "set"))
    monkeypatch.setattr(doctor, "check_interpreter", lambda home: doctor.Check("ok", "hook interpreter", "set"))
    temporary = doctor.check_temporary_work
    monkeypatch.setattr(doctor, "check_temporary_work", lambda repos, cwds, roots=None, venv_roots=None: temporary(repos, cwds, roots, ()))
    monkeypatch.setattr(review, "_present", lambda harness: False)


@pytest.fixture
def machine(tmp_path, monkeypatch, compiled_runtime, write_config):
    """A healthy Mac: the runtime installed, the hourly export scheduled and fresh, one workspace with a repository level
    with its upstream and a knowledge repository whose one project's records are current, and a live seat's claim."""
    home, synthesis = tmp_path / "home", compiled_runtime.parent
    monkeypatch.setenv("HOME", str(home))
    ws, remotes = home / "workspaces" / "acme", tmp_path / "remotes"
    for folder in (ws, remotes):
        folder.mkdir(parents=True)
    current = _published(remotes, ws / "current", "current")
    kb = ws / "ai-knowledge-acme"
    kb.mkdir()
    _records(kb, "2026-11-17")
    _published(remotes, kb, "ai-knowledge-acme")
    _racy(current)
    (ws / ".agents").mkdir()
    (ws / ".agents" / "repos.yaml").write_text(
        f"workspace: acme\nstatus: active\nrepos:\n  - name: current\n    path: current/\n    remotes:\n      origin: {remotes}/current.git\n"
        f"    ritual_sync: yes\n  - name: old\n    path: old/\n    remotes:\n      origin: {remotes}/old.git\n    status: dormant\n"
        "    ritual_sync: no\n", encoding="utf-8")
    write_config({"knowledge_roots": ["~/workspaces/acme/ai-knowledge-acme"]})
    _schedule(home / "Library" / "LaunchAgents" / f"{EXPORT}.plist", synthesis / "bin" / "synthesis")
    state, now = synthesis / "sessions" / ".state", time.time()
    state.mkdir(parents=True, exist_ok=True)
    fresh = datetime.fromtimestamp(now - 600).astimezone().isoformat()
    (state / "export.json").write_text(json.dumps({"exported": fresh, "scheduled": fresh}), encoding="utf-8")
    (state / "fetch.json").write_text(json.dumps({"at": fresh, "repos": {}}), encoding="utf-8")
    board.save(board.Session(session="S-live", harness="claude-code", project="alpha", started=now - 60, seen=now,
                             claims=[os.path.realpath(current) + "/**"]))
    _real_mac_read_healthy(monkeypatch)
    return SimpleNamespace(home=home, synthesis=synthesis, ws=ws, remotes=remotes, kb=kb, current=current, now=now,
                           run=_launchd({EXPORT}), tmp=tmp_path)


def _break(m) -> None:
    """One of each problem: repositories in each state the strand scan names, a declared repository with no clone, a
    project record behind its session log, a seat gone quiet with claims over uncommitted work, a live seat's claim over
    unpushed work, and the hourly export's launch agent gone."""
    ws, remotes = m.ws, m.remotes
    ahead = _published(remotes, ws / "ahead", "ahead")
    (ahead / "notes.md").write_text("more\n", encoding="utf-8")
    git(ahead, "add", "-A")
    git(ahead, "commit", "-q", "-m", "Second")
    behind = _published(remotes, ws / "behind", "behind")
    other = m.tmp / "elsewhere" / "behind"
    subprocess.run(["git", "clone", "-q", str(remotes / "behind.git"), str(other)], check=True)
    (other / "notes.md").write_text("theirs\n", encoding="utf-8")
    git(other, "add", "-A")
    git(other, "commit", "-q", "-m", "Theirs")
    git(other, "push", "-q")
    git(behind, "fetch", "-q")
    blind = _published(remotes, ws / "blind", "blind")
    git(blind, "switch", "-q", "-c", "feature")
    detached = _published(remotes, ws / "detached", "detached")
    git(detached, "switch", "-q", "--detach")
    dirty = _published(remotes, ws / "dirty", "dirty")
    (dirty / "README.md").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remotes / "missing.git")], check=True)
    with (ws / ".agents" / "repos.yaml").open("a", encoding="utf-8") as declared:
        declared.write(f"  - name: missing\n    path: missing/\n    remotes:\n      origin: {remotes}/missing.git\n    ritual_sync: yes\n")
    _records(m.kb, "2026-11-10")
    git(m.kb, "add", "-A")
    git(m.kb, "commit", "-q", "-m", "Records")
    git(m.kb, "push", "-q")
    board.save(board.Session(session="S-stale", harness="codex", project="alpha", started=m.now - 40000, seen=m.now - 36000,
                             claims=[os.path.realpath(dirty) + "/**"]))
    board.save(board.Session(session="S-live", harness="claude-code", project="alpha", started=m.now - 60, seen=m.now,
                             claims=[os.path.realpath(ahead) + "/**"]))
    (m.home / "Library" / "LaunchAgents" / f"{EXPORT}.plist").unlink()


def _rows(report: dict) -> list:
    return [(f["severity"], f["area"], f["subject"]) for f in report["findings"]]


def _steps(report: dict) -> list:
    return [(s["who"], s["do"], s["fixes"]) for s in report["plan"]]


# ---- the two machines ----------------------------------------------------------------------------------------------

def test_a_healthy_machine_yields_no_finding_and_an_empty_plan(machine, capsys):
    report = review.review(run=machine.run, platform="darwin")
    assert report["findings"] == [] and report["plan"] == [], report["findings"]
    assert report["healthy"] is True and report["exit"] == 0 and report["fetched"] is False
    assert report["counts"] == {"fail": 0, "unknown": 0, "warn": 0}
    assert {k: report["read"][k] for k in ("workspaces", "repositories", "projects", "sessions", "schedules")} == {
        "workspaces": 1, "repositories": 2, "projects": 1, "sessions": 1, "schedules": 1}
    assert report["read"]["doctor checks"] >= 15
    assert "synthesis doctor" in report["not_run"] and "self-test" in report["not_run"]
    text = review.render(report)
    assert text.splitlines()[0].startswith("synthesis review: nothing to repair") and "Repair plan" not in text
    code = cli.main(["review", "--json"])  # the CLI's own command; on a Mac it asks launchd itself, which only reads
    printed = json.loads(capsys.readouterr().out)
    assert set(printed) >= {"healthy", "exit", "fetched", "ms", "counts", "read", "not_run", "findings", "plan"}
    assert code == printed["exit"] and printed["fetched"] is False


def test_a_machine_with_one_of_each_problem_yields_its_findings_and_its_plan(machine):
    _break(machine)
    report = review.review(run=machine.run, platform="darwin")
    alpha = "~/workspaces/acme/ai-knowledge-acme/projects/alpha"
    assert _rows(report) == [
        ("fail", "repositories", "~/workspaces/acme/blind"),
        ("fail", "repositories", "~/workspaces/acme/detached"),
        ("fail", "repositories", "~/workspaces/acme/missing"),
        ("fail", "projects", alpha),
        ("warn", "schedules", EXPORT),
        ("warn", "claims", "S-stale"),
        ("warn", "repositories", "~/workspaces/acme/ahead"),
        ("warn", "repositories", "~/workspaces/acme/behind"),
        ("warn", "repositories", "~/workspaces/acme/dirty"),
    ]
    assert [f["id"] for f in report["findings"]] == [f"F{n}" for n in range(1, 10)]
    said = {f["subject"]: f["detail"] for f in report["findings"]}
    assert "feature" in said["~/workspaces/acme/blind"] and "no upstream" in said["~/workspaces/acme/blind"]
    assert "detached" in said["~/workspaces/acme/detached"]
    assert "repos.yaml" in said["~/workspaces/acme/missing"] and "no clone" in said["~/workspaces/acme/missing"]
    assert "freshness" in said[alpha] and "2026-11-10" in said[alpha]
    assert "not scheduled" in said[EXPORT]
    assert "quiet 10 h" in said["S-stale"] and "uncommitted" in said["S-stale"]
    assert "1 commit ahead of origin/main" in said["~/workspaces/acme/ahead"] and board.short_name("S-live") in said["~/workspaces/acme/ahead"]
    assert "1 commit behind origin/main" in said["~/workspaces/acme/behind"]
    assert "1 uncommitted file" in said["~/workspaces/acme/dirty"] and "README.md" in said["~/workspaces/acme/dirty"]
    runtime = machine.synthesis / "current" / "skills"
    records = f"python3 -s {runtime / 'synthesis-context-lifecycle' / 'scripts' / 'context_doctor.py'} --project {alpha}"
    steps = _steps(report)
    assert steps[:5] == [
        ("agent", "git -C ~/workspaces/acme/blind push -u origin feature", ["F1"]),
        ("agent", "git -C ~/workspaces/acme/detached switch main", ["F2"]),
        ("agent", f"git clone {machine.remotes / 'missing.git'} ~/workspaces/acme/missing", ["F3"]),
        ("agent", f"make the remedies `{records}` lists (freshness)", ["F4"]),
        ("agent-with-code", f"python3 -s {runtime / 'synthesis-onboarding' / 'scripts' / 'setup.py'} plugin --sessions-export", ["F5"]),
    ]
    assert steps[5] == ("agent", "synthesis claim ~/workspaces/acme/dirty --take", ["F6"])  # the board tells its holder
    who, do, fixes = steps[6]  # the live seat's own work: a message to it, nothing more
    assert (who, fixes) == ("agent", ["F7"]) and do.startswith("synthesis msg S-live ") and "&&" not in do
    assert steps[7:] == [
        ("agent", "git -C ~/workspaces/acme/behind merge --ff-only origin/main", ["F8"]),
        ("agent", "git -C ~/workspaces/acme/dirty add -A && git -C ~/workspaces/acme/dirty commit -m 'Commit work left uncommitted'", ["F9"]),
        ("agent", "git -C ~/workspaces/acme/dirty push", ["F9"]),
    ]
    assert [s["step"] for s in report["plan"]] == list(range(1, 11))
    assert report["counts"] == {"fail": 4, "unknown": 0, "warn": 5} and report["exit"] == 1 and report["healthy"] is False


def test_the_text_groups_the_findings_by_severity_and_numbers_the_plan(machine):
    _break(machine)
    text = review.render(review.review(run=machine.run, platform="darwin"))
    lines = text.splitlines()
    assert lines[0].startswith("synthesis review: 4 fail, 0 unknown, 5 warn") and "nothing was changed" in lines[0]
    heads = [line for line in lines if line in ("FAIL", "UNKNOWN", "WARN")]
    assert heads == ["FAIL", "WARN"]
    assert lines.index("FAIL") < lines.index("WARN") < next(i for i, line in enumerate(lines) if line.startswith("Repair plan"))
    numbered = [line for line in lines if re.match(r"\s+\d+\. \[", line)]
    assert len(numbered) == 10 and numbered[0].lstrip().startswith("1. [agent] git -C ~/workspaces/acme/blind push")
    assert "[agent, with the principal's code]" in text and "none has run" in text


# ---- read only ------------------------------------------------------------------------------------------------------

def _snapshot(root: Path) -> dict:
    """Every file, link and folder under root, with its mode, size and modification time: a write anywhere changes one."""
    found = {}
    for folder, folders, files in os.walk(root):
        for name in [".", *folders, *files]:
            path = os.path.normpath(os.path.join(folder, name))
            info = os.lstat(path)
            found[path] = (info.st_mode, info.st_size, info.st_mtime_ns)
    return found


def test_the_review_as_installed_writes_nothing_on_the_machine_it_reads(machine):
    """The installed runtime's own command, run as its launcher runs it (the pinned interpreter, isolated), over the
    broken machine: every file and folder is as it was, the repositories' indexes (one racy) and the runtime's carried
    scripts, beside which nothing is compiled, among them."""
    _break(machine)
    _racy(machine.ws / "dirty")
    python = install.pinned(machine.synthesis) or sys.executable
    before = _snapshot(machine.tmp)
    done = subprocess.run([python, "-I", "-S", "-c", "import sys; sys.path.insert(0, sys.argv.pop(1)); from synthesis.cli import main; "
                           "sys.exit(main())", str(machine.synthesis / "current"), "review", "--json"],
                          capture_output=True, text=True, timeout=300, env={**os.environ, "HOME": str(machine.home)})
    assert done.returncode in (1, 2), done.stderr
    printed = json.loads(done.stdout)
    assert printed["fetched"] is False and printed["findings"]
    after = _snapshot(machine.tmp)
    assert sorted(set(after) ^ set(before)) == [] and {p: v for p, v in after.items() if before[p] != v} == {}


def test_the_review_calls_none_of_synthesiss_writers():
    from test_unproven_programs import _writers_in
    writers = _writers_in(ROOT)
    assert {w for w in writers if w.split(".")[0] == "review"} == set()
    assert "cli.cmd_review" not in writers and "wait.held" not in writers and "wait.live" in writers


def test_a_repository_whose_own_config_names_a_program_is_not_read_and_is_unknown(machine):
    """git status runs the program core.fsmonitor names: the review asks the guard's reader first and runs no git there."""
    trap = _published(machine.remotes, machine.ws / "trap", "trap")
    ran = machine.tmp / "ran"
    program = machine.tmp / "monitor.sh"
    program.write_text(f"#!/bin/sh\ntouch {shlex.quote(str(ran))}\n", encoding="utf-8")
    program.chmod(0o755)
    git(trap, "config", "core.fsmonitor", str(program))
    report = review.review(run=machine.run, platform="darwin")
    assert not ran.exists()
    assert _rows(report) == [("unknown", "repositories", "~/workspaces/acme/trap")]
    assert "core.fsmonitor" in report["findings"][0]["detail"]
    assert [(s["who"], s["fixes"]) for s in report["plan"]] == [("principal", ["F1"])]
    assert "core.fsmonitor" in report["plan"][0]["do"] and report["exit"] == 2


def test_only_fetch_reaches_a_remote(machine, monkeypatch):
    """Without --fetch a repository whose remote is gone reads as its last fetch left it, and the stable release is not
    asked for; with it, the repository is unreachable and the release is asked for (here, of a stand-in)."""
    asked = []
    monkeypatch.setattr(doctor, "check_latest", lambda installed, ref="stable", fetch=None: asked.append(ref) or doctor.Check(
        "ok", "latest release", f"{ref} is the installed one"))
    gone = _published(machine.remotes, machine.ws / "gone", "gone")
    import shutil
    shutil.rmtree(machine.remotes / "gone.git")
    assert review.review(run=machine.run, platform="darwin")["findings"] == []
    assert not (gone / ".git" / "FETCH_HEAD").exists() and asked == []
    report = review.review(fetch=True, run=machine.run, platform="darwin")
    assert report["fetched"] is True and asked == ["stable"]
    assert [r for r in _rows(report) if r[1] == "repositories"] == [("fail", "repositories", "~/workspaces/acme/gone")]
    step = next(s for s in report["plan"] if s["fixes"] == [report["findings"][0]["id"]])
    assert step["who"] == "principal" and "git -C ~/workspaces/acme/gone fetch --all --prune" in step["do"]


# ---- claims, approvals and pieces that cannot run ----------------------------------------------------------------------

def test_a_quiet_seat_inside_a_live_wait_is_not_taken_over(machine):
    from synthesis import wait
    board.save(board.Session(session="S-waits", harness="codex", project="alpha", started=machine.now - 40000,
                             seen=machine.now - 36000, claims=[os.path.realpath(machine.current) + "/**"]))
    wait.record("S-waits", "a reply", machine.now + 3600)
    assert review.review(run=machine.run, platform="darwin")["findings"] == []
    board.save(board.Session(session="S-gone", harness="codex", project="alpha", started=machine.now - 40000,
                             seen=machine.now - 36000, claims=[os.path.realpath(machine.current) + "/**"]))
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("warn", "claims", "S-gone")]
    assert [(s["who"], s["do"]) for s in report["plan"]] == [("agent", "synthesis claim ~/workspaces/acme/current --take")]


def test_a_seat_counts_for_a_repository_only_where_its_claims_cover_the_work(machine):
    """In a repository many seats work in, the seat to ask about uncommitted files is the one whose claim covers them; a
    live seat that claims another part of it is not asked, and the work outside every live claim is committed."""
    (machine.current / "notes").mkdir()
    (machine.current / "notes" / "a.md").write_text("a\n", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")  # S-live claims the whole repository: it is asked
    assert [(s["who"], s["do"].split()[:3]) for s in report["plan"]] == [("agent", ["synthesis", "msg", "S-live"])]
    board.save(board.Session(session="S-live", harness="claude-code", project="alpha", started=machine.now - 60, seen=machine.now,
                             claims=[os.path.realpath(machine.current / "docs") + "/**"]))
    report = review.review(run=machine.run, platform="darwin")
    assert [(s["who"], s["do"]) for s in report["plan"]] == [
        ("agent", "git -C ~/workspaces/acme/current add -A && git -C ~/workspaces/acme/current commit -m 'Commit work left uncommitted'"),
        ("agent", "git -C ~/workspaces/acme/current push")]
    assert board.short_name("S-live") not in report["findings"][0]["detail"]


def test_what_the_doctor_last_saw_of_a_harness_hook_approval_is_reported(machine, monkeypatch):
    from synthesis import __version__
    monkeypatch.setattr(review, "_present", lambda harness: harness == "codex")
    codex = paths.codex_home()  # with Codex here its own config is read too, as the doctor reads it: a sound one
    codex.mkdir(parents=True, exist_ok=True)
    (codex / "config.toml").write_text('project_doc_max_bytes = 98304\nsandbox_mode = "danger-full-access"\n\n[features]\n'
                                       "hooks = true\n", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("unknown", "installed", "codex hook trust")]
    assert [(s["who"], s["do"]) for s in report["plan"]] == [("agent", "synthesis doctor")]
    paths.note_wait("codex hook trust", lambda old: {"at": time.time(), "waiting": ["pre_tool_use"], "struck": {},
                                                      "said": "needs /hooks approval: pre_tool_use", "untold": False})
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("fail", "installed", "codex hook trust")] and "pre_tool_use" in report["findings"][0]["detail"]
    assert report["plan"][0]["who"] == "principal" and "/hooks" in report["plan"][0]["do"]
    assert paths.waits()["codex hook trust"]["version"] == __version__


def test_a_piece_that_cannot_run_is_unknown_and_never_fine(machine, monkeypatch, tmp_path):
    _break(machine)
    monkeypatch.setattr(review, "SKILLS", tmp_path / "no-skills-here")
    report = review.review(run=machine.run, platform="darwin")
    unknown = [r for r in _rows(report) if r[0] == "unknown"]
    assert ("unknown", "repositories", "strand scan") in unknown and ("unknown", "projects", "context doctor") in unknown
    assert not [r for r in _rows(report) if r[1] in ("repositories", "projects") and r[0] != "unknown"]
    assert report["exit"] == 2 and report["healthy"] is False
    fixed = {found for step in report["plan"] for found in step["fixes"]}  # one step may fix several: one command, said once
    assert all(f["id"] in fixed for f in report["findings"] if f["severity"] == "unknown")


def test_every_doctor_check_is_run_here_or_named_as_not_run():
    """A check the doctor gains is either run by the review or named, with why, among those it does not run."""
    source = Path(doctor.__file__).read_text(encoding="utf-8")
    checks = set(re.findall(r"^def (check_\w+)\(", source, re.M))
    ran = set(re.findall(r"\bdoctor\.(check_\w+)\(", Path(review.__file__).read_text(encoding="utf-8")))
    assert ran and not ran & set(review.NOT_RUN), ran & set(review.NOT_RUN)
    assert sorted(checks - ran - set(review.NOT_RUN)) == [] and sorted((ran | set(review.NOT_RUN)) - checks) == []
    assert all(isinstance(why, str) and len(why.split()) >= 3 for why in review.NOT_RUN.values())
