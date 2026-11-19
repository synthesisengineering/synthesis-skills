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
    (blind / "feature.md").write_text("unpushed\n", encoding="utf-8")  # a commit no remote holds
    git(blind, "add", "-A")
    git(blind, "commit", "-q", "-m", "Unpushed")
    detached = _published(remotes, ws / "detached", "detached")
    git(detached, "switch", "-q", "--detach")  # at a commit origin/main holds: nothing at risk
    loose = _published(remotes, ws / "loose", "loose")
    git(loose, "switch", "-q", "--detach")
    (loose / "loose.md").write_text("on no branch\n", encoding="utf-8")  # a commit made detached, which no remote holds
    git(loose, "add", "-A")
    git(loose, "commit", "-q", "-m", "On no branch")
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
        ("fail", "repositories", "~/workspaces/acme/loose"),
        ("fail", "repositories", "~/workspaces/acme/missing"),
        ("fail", "projects", alpha),
        ("warn", "schedules", EXPORT),
        ("warn", "claims", "S-stale"),
        ("warn", "repositories", "~/workspaces/acme/ahead"),
        ("warn", "repositories", "~/workspaces/acme/behind"),
        ("warn", "repositories", "~/workspaces/acme/dirty"),
        ("warn", "repositories", "1 checkout"),
    ]
    assert [f["id"] for f in report["findings"]] == [f"F{n}" for n in range(1, 11)]
    said = {f["subject"]: f["detail"] for f in report["findings"]}
    assert "feature" in said["~/workspaces/acme/blind"] and "no upstream" in said["~/workspaces/acme/blind"]
    assert "detached" in said["~/workspaces/acme/loose"] and "no branch" in said["~/workspaces/acme/loose"]
    assert "~/workspaces/acme/detached (detached, on origin/main)" in said["1 checkout"]
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
        ("principal", "put HEAD back on a branch: `git -C ~/workspaces/acme/loose switch -c <a new branch>` keeps what was "
                      "committed while detached; `git -C ~/workspaces/acme/loose branch --contains HEAD` names the branches "
                      "that already hold it", ["F2"]),
        ("agent", f"git clone {machine.remotes / 'missing.git'} ~/workspaces/acme/missing", ["F3"]),
        ("agent", f"make the remedies `{records}` lists (freshness)", ["F4"]),
        ("agent-with-code", f"python3 -s {runtime / 'synthesis-onboarding' / 'scripts' / 'setup.py'} plugin --sessions-export", ["F5"]),
    ]
    assert steps[5] == ("agent", "synthesis claim ~/workspaces/acme/dirty --take", ["F6"])  # the board tells its holder
    who, do, fixes = steps[6]  # the live seat's own work: a message to it, nothing more
    assert (who, fixes) == ("agent", ["F7"]) and do.startswith("synthesis msg S-live ") and "&&" not in do
    assert steps[7:] == [
        ("agent", "git -C ~/workspaces/acme/behind merge --ff-only origin/main", ["F8"]),
        ("agent", "git -C ~/workspaces/acme/dirty add -- README.md && git -C ~/workspaces/acme/dirty commit -m 'Commit work left "
                  "uncommitted' -- README.md", ["F9"]),  # the files by name, never -A (round 1, finding 2)
        ("agent", "git -C ~/workspaces/acme/dirty push", ["F9"]),
    ]
    assert [s["step"] for s in report["plan"]] == list(range(1, 11))
    assert report["counts"] == {"fail": 4, "unknown": 0, "warn": 6} and report["exit"] == 1 and report["healthy"] is False


def test_a_branch_with_no_upstream_whose_commits_a_remote_holds_is_nothing_at_risk(machine):
    """On the principal's Mac, 86 of the 130 checkouts on a branch with no upstream held commits a remote already had (a
    worktree whose pull request merged), and each was a failure with a push in the plan. Such a checkout with nothing
    else to repair is now one warning for them all, with no step; one whose commits no remote holds still fails."""
    for name, branch in (("landed", "merged-work"), ("landed-too", "done")):
        git(_published(machine.remotes, machine.ws / name, name), "switch", "-q", "-c", branch)  # origin/main holds it
    lost = _published(machine.remotes, machine.ws / "lost", "lost")
    git(lost, "switch", "-q", "-c", "unpushed")
    (lost / "work.md").write_text("only here\n", encoding="utf-8")
    git(lost, "add", "-A")
    git(lost, "commit", "-q", "-m", "Only here")
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("fail", "repositories", "~/workspaces/acme/lost"), ("warn", "repositories", "2 checkouts")]
    said = {f["subject"]: f["detail"] for f in report["findings"]}
    assert "no remote" in said["~/workspaces/acme/lost"]
    assert "~/workspaces/acme/landed (merged-work, on origin/main)" in said["2 checkouts"]
    assert "~/workspaces/acme/landed-too (done, on origin/main)" in said["2 checkouts"]
    assert _steps(report) == [("agent", "git -C ~/workspaces/acme/lost push -u origin unpushed", ["F1"])]
    assert report["counts"] == {"fail": 1, "unknown": 0, "warn": 1}


def test_the_text_groups_the_findings_by_severity_and_numbers_the_plan(machine):
    _break(machine)
    text = review.render(review.review(run=machine.run, platform="darwin"))
    lines = text.splitlines()
    assert lines[0].startswith("synthesis review: 4 fail, 0 unknown, 6 warn") and "nothing was changed" in lines[0]
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
    live seat that claims another part of it is not asked, and the work outside every live claim is committed (an
    untracked folder named as one path, as git's status lists it)."""
    (machine.current / "notes").mkdir()
    (machine.current / "notes" / "a.md").write_text("a\n", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")  # S-live claims the whole repository: it is asked
    assert [(s["who"], s["do"].split()[:3]) for s in report["plan"]] == [("agent", ["synthesis", "msg", "S-live"])]
    assert report["findings"][0]["detail"].startswith("1 untracked folder (notes/); live session ")  # never "0 uncommitted files"
    board.save(board.Session(session="S-live", harness="claude-code", project="alpha", started=machine.now - 60, seen=machine.now,
                             claims=[os.path.realpath(machine.current / "docs") + "/**"]))
    report = review.review(run=machine.run, platform="darwin")
    assert [(s["who"], s["do"]) for s in report["plan"]] == [
        ("agent", "git -C ~/workspaces/acme/current add -- notes/ && git -C ~/workspaces/acme/current commit -m 'Commit work "
                  "left uncommitted' -- notes/"),
        ("agent", "git -C ~/workspaces/acme/current push")]
    assert board.short_name("S-live") not in report["findings"][0]["detail"]


def test_a_declared_clone_deeper_than_discovery_reaches_is_read_and_an_unreadable_declaration_is_unknown(machine):
    """Discovery looks one and two folders down; a repository the workspace declares deeper is read all the same. A
    declared list that cannot be read (a link into a knowledge repository that is not here) is unknown, never empty."""
    deep = machine.ws / "group" / "team" / "deep"
    deep.parent.mkdir(parents=True)
    _published(machine.remotes, deep, "deep")
    (deep / "README.md").write_text("changed\n", encoding="utf-8")
    with (machine.ws / ".agents" / "repos.yaml").open("a", encoding="utf-8") as declared:
        declared.write(f"  - name: deep\n    path: group/team/deep/\n    remotes:\n      origin: {machine.remotes}/deep.git\n    ritual_sync: yes\n")
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("warn", "repositories", "~/workspaces/acme/group/team/deep")]
    manifest = machine.ws / ".agents" / "repos.yaml"
    manifest.unlink()
    manifest.symlink_to(machine.tmp / "no-knowledge-repository-here" / "repos.yaml")
    report = review.review(run=machine.run, platform="darwin")
    assert ("unknown", "workspaces", "~/workspaces/acme/.agents/repos.yaml") in _rows(report)
    assert report["exit"] == 2


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


# ---- review round 1 --------------------------------------------------------------------------------------------------

def _guard(command: str, cwd: Path):
    """What the guard's own check answers for one step of the plan, as a session's shell would meet it: None runs it."""
    from synthesis import guards
    return guards.check("Bash", {"command": command}, paths.config(), str(cwd), None)


def test_every_agent_step_runs_with_no_code_where_pushes_publish_or_are_gated(machine, write_config):
    """Finding 1: a push the guard holds (to a repository that publishes on push, or to a gated repository's default
    branch) was classed `agent`. Every git step is classed by the guard's own deciders, which record no request: what they
    hold waits for the principal's code, and every step left to the agent runs with none."""
    _break(machine)
    write_config({"knowledge_roots": ["~/workspaces/acme/ai-knowledge-acme"],
                  "push_deploys": ["~/workspaces/acme/blind", "~/workspaces/acme/dirty"],
                  "pr_gated": {"remotes/blind": {"since": "2026-01-01"}}})
    before = _snapshot(paths.approvals())
    report = review.review(run=machine.run, platform="darwin")
    assert _snapshot(paths.approvals()) == before  # classing a step filed no request for a code
    who = {s["do"]: s["who"] for s in report["plan"]}
    assert who["git -C ~/workspaces/acme/blind push -u origin feature"] == "agent-with-code"
    assert who["git -C ~/workspaces/acme/dirty push"] == "agent-with-code"
    agent = [do for do, by in who.items() if by == "agent" and do.split()[0] in ("git", "synthesis")]
    assert len(agent) >= 5 and {do: _guard(do, machine.home) for do in agent} == dict.fromkeys(agent)


def test_classing_a_push_reaches_no_other_repository_and_runs_no_program_its_configuration_names(machine, write_config):
    """The push decider asks a remote which version tags it holds when a push may carry one. Classing reaches no other
    repository, a local path included, so an `uploadpack` the repository's own configuration names never runs (a fetch
    is not among the subcommands its git was screened for), and the push the decider could settle only by asking is
    held for the principal's code."""
    tagged, ran = _published(machine.remotes, machine.ws / "tagged", "tagged"), machine.tmp / "uploadpack-ran"
    git(tagged, "switch", "-q", "-c", "feature")
    git(tagged, "push", "-q", "-u", "origin", "feature")
    git(tagged, "tag", "-a", "v1.0.0", "-m", "One")
    (tagged / "next.md").write_text("next\n", encoding="utf-8")
    git(tagged, "add", "next.md")
    git(tagged, "commit", "-q", "-m", "Next")
    git(tagged, "config", "push.followTags", "true")
    git(tagged, "config", "remote.origin.uploadpack", f"touch {ran} && git-upload-pack")
    write_config({"knowledge_roots": ["~/workspaces/acme/ai-knowledge-acme"],
                  "pr_gated": {"remotes/tagged": {"since": "2026-01-01", "branch": "main"}}})
    report = review.review(run=machine.run, platform="darwin")
    assert {s["do"]: s["who"] for s in report["plan"]}["git -C ~/workspaces/acme/tagged push"] == "agent-with-code"
    assert not ran.exists()


def test_a_live_seats_file_past_the_scans_first_twenty_is_left_out_of_the_commit_and_its_seat_asked(machine):
    """Finding 2: the strand scan lists twenty uncommitted files, so a live seat's file after them was committed with
    `git add -A`, then pushed, and the seat was never asked. The whole list is read: the commit names each file no live
    claim covers, the seat whose claim covers the rest is asked, and nothing is pushed under a seat at work."""
    names = [f"a{n:02d}.md" for n in range(25)]
    for name in names:
        (machine.current / name).write_text("a\n", encoding="utf-8")
    (machine.current / "zz").mkdir()
    (machine.current / "zz" / "theirs.md").write_text("theirs\n", encoding="utf-8")
    board.save(board.Session(session="S-live", harness="claude-code", project="alpha", started=machine.now - 60, seen=machine.now,
                             claims=[os.path.realpath(machine.current / "zz") + "/**"]))
    report = review.review(run=machine.run, platform="darwin")
    files, where = " ".join(names), "~/workspaces/acme/current"
    commit, ask = [(s["who"], s["do"]) for s in report["plan"]]
    assert commit == ("agent", f"git -C {where} add -- {files} && git -C {where} commit -m 'Commit work left uncommitted' -- {files}")
    assert ask[0] == "agent" and ask[1].startswith("synthesis msg S-live ")
    assert "25 uncommitted files and 1 untracked folder" in report["findings"][0]["detail"]
    assert board.short_name("S-live") in report["findings"][0]["detail"]


def test_more_uncommitted_paths_than_one_step_names_are_the_principals_to_sort(machine):
    """A checkout on this Mac held 181,511 uncommitted entries, and the plan's commit named each twice: 71 MB, past what
    a shell takes. An untracked folder is one path, as git's status lists it, and past the most one step names the
    principal decides what is work there; below it the commit names each path."""
    heap, tidy = _published(machine.remotes, machine.ws / "heap", "heap"), _published(machine.remotes, machine.ws / "tidy", "tidy")
    for n in range(review.NAMED):
        (heap / f"n{n:03d}.md").write_text("n\n", encoding="utf-8")
    for folder in (heap / "big", tidy / "data"):
        folder.mkdir()
        for n in range(300):
            (folder / f"d{n:03d}.md").write_text("d\n", encoding="utf-8")
    for name in ("a.md", "b.md"):
        (tidy / name).write_text("t\n", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")
    said, steps = {f["subject"]: f["detail"] for f in report["findings"]}, [(s["who"], s["do"]) for s in report["plan"]]
    assert f"{review.NAMED} uncommitted files and 1 untracked folder" in said["~/workspaces/acme/heap"]
    assert [who for who, do in steps if "acme/heap" in do] == ["principal"] and not any(" add -- " in do for _, do in steps if "acme/heap" in do)
    assert ("agent", "git -C ~/workspaces/acme/tidy add -- a.md b.md data/ && git -C ~/workspaces/acme/tidy commit -m 'Commit work left "
                     "uncommitted' -- a.md b.md data/") in steps


def test_a_git_entry_git_cannot_read_is_unknown_and_a_worktree_is_read(machine):
    """Finding 3a: discovery kept only a `.git` that is a folder, so a dangling link and a worktree's file naming a folder
    that is gone were passed over, and a live worktree's uncommitted work was never read."""
    ghost, broken, tree = machine.ws / "ghost", machine.ws / "broken", machine.ws / "current-wt"
    for folder in (ghost, broken):
        folder.mkdir()
    (ghost / ".git").symlink_to(machine.tmp / "nowhere" / ".git")
    (broken / ".git").write_text(f"gitdir: {machine.tmp / 'gone' / '.git' / 'worktrees' / 'broken'}\n", encoding="utf-8")
    git(machine.current, "worktree", "add", "-q", "-b", "wt", str(tree))
    (tree / "work.md").write_text("unsaved\n", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")
    rows, said = _rows(report), {f["subject"]: f["detail"] for f in report["findings"]}
    assert {("unknown", "repositories", "~/workspaces/acme/broken"), ("unknown", "repositories", "~/workspaces/acme/ghost")} <= set(rows)
    assert "not there" in said["~/workspaces/acme/ghost"] and "not there" in said["~/workspaces/acme/broken"]
    assert ("warn", "repositories", "~/workspaces/acme/current-wt") in rows  # its branch's commits are origin/main's: the file is the work
    assert "1 uncommitted file" in said["~/workspaces/acme/current-wt"] and "branch wt has no upstream" in said["~/workspaces/acme/current-wt"]
    assert report["exit"] == 2


def test_a_git_entry_that_is_a_pipe_is_unknown_and_never_opened(machine):
    """A `.git` that is neither a folder nor a file (a named pipe) is never opened, since opening a pipe waits for a writer
    and the review would never end: it is unknown. Should a read wait all the same, the writer here ends it after ten
    seconds, so the test fails rather than hangs."""
    import threading
    (machine.ws / "piped").mkdir()
    os.mkfifo(machine.ws / "piped" / ".git")

    def writer():
        try:
            os.close(os.open(machine.ws / "piped" / ".git", os.O_WRONLY | os.O_NONBLOCK))
        except OSError:  # nothing waits to read it
            pass
    timer = threading.Timer(10, writer)
    timer.daemon = True
    timer.start()
    began = time.time()
    report = review.review(run=machine.run, platform="darwin")
    took, _ = time.time() - began, timer.cancel()
    assert took < 10 and ("unknown", "repositories", "~/workspaces/acme/piped") in _rows(report)
    assert "neither a folder nor a file" in {f["subject"]: f["detail"] for f in report["findings"]}["~/workspaces/acme/piped"]


def test_a_declared_repository_whose_git_cannot_be_read_is_unknown_once_and_never_cloned_over(machine):
    """Finding 3a, declared: a repository the workspace declares, with a `.git` git cannot read, was a repository with no
    clone here, whose step clones into the folder that holds it; one discovery also found was said twice. Each is unknown,
    said once, with the principal's step, wherever it lies."""
    gone, lost = machine.ws / "gone", machine.ws / "group" / "team" / "lost"
    for folder in (gone, lost):
        folder.mkdir(parents=True)
    (gone / ".git").symlink_to(machine.tmp / "nowhere" / ".git")
    (lost / ".git").write_text(f"gitdir: {machine.tmp / 'gone' / '.git' / 'worktrees' / 'lost'}\n", encoding="utf-8")
    with (machine.ws / ".agents" / "repos.yaml").open("a", encoding="utf-8") as declared:
        for name, path in (("gone", "gone/"), ("lost", "group/team/lost/")):
            declared.write(f"  - name: {name}\n    path: {path}\n    remotes:\n      origin: {machine.remotes}/{name}.git\n    ritual_sync: yes\n")
    report = review.review(run=machine.run, platform="darwin")
    assert sorted(_rows(report)) == [("unknown", "repositories", "~/workspaces/acme/gone"),
                                     ("unknown", "repositories", "~/workspaces/acme/group/team/lost")]
    assert all("not there" in f["detail"] and "no clone" not in f["detail"] for f in report["findings"])
    assert [s["who"] for s in report["plan"]] == ["principal", "principal"] and report["exit"] == 2


def test_a_doctor_line_that_could_not_tell_is_unknown(machine):
    """Finding 3b: the doctor's could-not-tell lines came through as warnings, by the words they began with. The doctor
    gives them a status of their own, which the review keeps."""
    (machine.synthesis / "teardown.jsonl").mkdir()
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("unknown", "installed", "teardown")] and report["exit"] == 2 and report["healthy"] is False


def test_a_declaration_of_another_shape_is_unknown_and_the_review_still_reports(machine, monkeypatch, capsys):
    """Finding 3c: a repos.yaml whose repositories are bare names raised in the strand scan's reader and ended the review
    with exit 1 and no report. What raises in an area is an unknown finding for it; exit 2 is the last resort."""
    (machine.ws / ".agents" / "repos.yaml").write_text("workspace: acme\nrepos:\n  - current\n  - old\n", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("unknown", "workspaces", "~/workspaces/acme/.agents/repos.yaml")] and report["exit"] == 2
    monkeypatch.setattr(review, "review", lambda **kw: 1 / 0)
    assert review.main(["--json"]) == 2 and "ZeroDivisionError" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a file no one may read")
def test_a_session_file_that_cannot_be_opened_is_unknown_and_the_review_still_reports(machine):
    """Finding 3c: a board session file no one may read raised PermissionError and ended the review."""
    locked = paths.board() / "sessions" / "S-locked.json"
    locked.write_text("{}", encoding="utf-8")
    locked.chmod(0)
    try:
        report = review.review(run=machine.run, platform="darwin")
    finally:
        locked.chmod(0o644)
    assert _rows(report) == [("unknown", "claims", "board")] and "S-locked.json" in report["findings"][0]["detail"]
    assert report["exit"] == 2


def test_a_session_file_the_board_cannot_parse_is_counted_and_unknown(machine):
    """Finding 3d: board.sessions() passes over a file it cannot parse, and the review passed it over in silence."""
    (paths.board() / "sessions" / "S-bad.json").write_text("{not json", encoding="utf-8")
    report = review.review(run=machine.run, platform="darwin")
    assert _rows(report) == [("unknown", "claims", "board")] and "S-bad.json" in report["findings"][0]["detail"]
    assert report["read"]["sessions"] == 2 and report["exit"] == 2


def test_each_claim_is_normalized_once_however_many_repositories_and_files(machine, monkeypatch):
    """From the open list: each claim was normalized again for every repository and every uncommitted file (583,803
    calls and 17.5 s on a machine the size of the principal's). A claim is normalized once, as its session is read, and a
    claim outside a repository is passed over before any file is compared."""
    for n in range(4):
        repo = _published(machine.remotes, machine.ws / f"r{n}", f"r{n}")
        for k in range(25):
            (repo / f"f{k}.md").write_text("x\n", encoding="utf-8")
    for s in range(20):
        board.save(board.Session(session=f"S-{s:02d}", harness="codex", project="p", started=machine.now - 50000, seen=machine.now - 36000,
                                 claims=[os.path.realpath(machine.ws / f"r{s % 4}") + f"/sub{k}/**" for k in range(3)]))
    calls = []
    normalize = board.normalize
    monkeypatch.setattr(board, "normalize", lambda claim: calls.append(claim) or normalize(claim))
    report = review.review(run=machine.run, platform="darwin")
    assert len([f for f in report["findings"] if f["area"] == "claims"]) == 20
    assert len(calls) == 20 * 3 + 1, len(calls)  # each stale seat's three claims and the live seat's one, read once


def test_the_pr_gate_check_runs_no_git_where_a_gated_checkout_names_a_program(machine, write_config):
    """Found with round 1 (the reviewer's probe): the doctor's PR-gate check, which the review runs, read a gated
    checkout's history with `git log`, which ran the program its own configuration names (gpg.program, with
    log.showSignature). That checkout's git is screened like any other: the check cannot read it, and says so."""
    gated = _published(machine.remotes, machine.ws / "gated", "gated")
    head, tree = git(gated, "rev-parse", "HEAD"), git(gated, "rev-parse", "HEAD^{tree}")
    signed = subprocess.run(["git", "-C", str(gated), "hash-object", "-t", "commit", "-w", "--stdin"], check=True, capture_output=True,
                            text=True, input=f"tree {tree}\nparent {head}\nauthor t <t@e> 1763400000 +0000\ncommitter t <t@e> 1763400000 "
                            "+0000\ngpgsig -----BEGIN PGP SIGNATURE-----\n \n abc\n -----END PGP SIGNATURE-----\n\nSigned\n").stdout.strip()
    git(gated, "update-ref", "refs/heads/main", signed)  # a signature, which `git log` hands its gpg.program to check
    git(gated, "push", "-q", "origin", "main")
    git(gated, "remote", "set-head", "origin", "--auto")
    ran, program = machine.tmp / "gpg-ran", machine.tmp / "gpg.sh"
    program.write_text(f"#!/bin/sh\ntouch {shlex.quote(str(ran))}\nexit 1\n", encoding="utf-8")
    program.chmod(0o755)
    git(gated, "config", "log.showSignature", "true")
    git(gated, "config", "gpg.program", str(program))
    write_config({"knowledge_roots": ["~/workspaces/acme/ai-knowledge-acme"], "pr_gated": {"remotes/gated": {"since": "2020-01-01"}}})
    report = review.review(run=machine.run, platform="darwin")
    assert not ran.exists()
    assert {("unknown", "installed", "pr gate"), ("unknown", "repositories", "~/workspaces/acme/gated")} <= set(_rows(report))
