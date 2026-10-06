"""R1.1 and R1.2: resuming a project from its files and local git alone, and the questions resume
asks instead of guessing (code evaluation, project state, section 3)."""

import subprocess

import pytest

from synthesis import board, project

CONTEXT = """# Alpha

<!-- synthesis-current-state:start -->
**Phase:** M2 core
**Status:** active
**Last session:** 2026-10-04
**Plan:** [the plan](resources/plan.md)
<!-- synthesis-current-state:end -->

## What's Next

1. [x] Write the board
2. [ ] Write the guards
   and their tests
3. [ ] Wire the hook

Older notes.
"""


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit_all(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


@pytest.fixture
def kb(tmp_path, write_config):
    """A knowledge checkout with one project, published to a bare remote it tracks."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    root = tmp_path / "ai-knowledge-test"
    subprocess.run(["git", "clone", "-q", str(remote), str(root)], check=True, capture_output=True)
    proj = root / "projects" / "alpha"
    (proj / "sessions").mkdir(parents=True)
    (proj / "resources").mkdir()
    (proj / "resources" / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (proj / "PRIME-DIRECTIVE.md").write_text("# Prime directive\nShip the core first.\n", encoding="utf-8")
    (proj / "CONTEXT.md").write_text(CONTEXT, encoding="utf-8")
    (proj / "sessions" / "2026-10.md").write_text("# October\n\n### 2026-10-04: board\n\nDone.\n", encoding="utf-8")
    (root / "projects" / "alpha-site").mkdir()
    (root / "projects" / "alpha-site" / "CONTEXT.md").write_text("# Alpha site\n", encoding="utf-8")
    _commit_all(root, "start")
    _git(root, "push", "-q", "origin", "main")
    _git(root, "fetch", "-q", "origin")
    write_config({"knowledge_roots": [str(root)]})
    return root


def _other_machine(kb, tmp_path):
    other = tmp_path / "other-mac"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "remote.git"), str(other)], check=True, capture_output=True)
    return other


# --- R1.1: what a fresh session gets ------------------------------------------------------------

def test_a_fresh_resume_states_the_directive_phase_and_next_action_from_the_files_alone(kb):
    out = project.resume("alpha", "S1")
    assert "Ship the core first." in out
    assert "Phase: M2 core" in out and "Status: active" in out
    assert "newest session entry: 2026-10-04 in sessions/2026-10.md" in out
    assert "Next: 2. [ ] Write the guards and their tests" in out
    assert "Write the board" not in out  # done items are not next actions
    assert "Plan: resources/plan.md" in out
    assert board.load("S1").project == "alpha"  # the session now works this project


def test_a_session_working_another_project_is_asked_before_switching(kb):
    board.touch("S1", project="beta")
    out = project.resume("alpha", "S1")
    assert "working project beta" in out and "resume alpha" in out and "Nothing was switched" in out
    assert board.load("S1").project == "beta"
    out = project.resume("alpha", "S1", switch=True)  # after the principal says yes
    assert "Ship the core first." in out and board.load("S1").project == "alpha"


def test_resuming_the_project_this_session_already_holds_confirms_in_one_line(kb):
    board.touch("S1", project="alpha")
    out = project.resume("alpha", "S1")
    assert out.count("\n") == 0 and "Already working alpha" in out


def test_an_unknown_id_offers_to_start_a_project_and_never_picks_a_near_match(kb):
    out = project.resume("alph", "S1")
    assert "Start a new project named 'alph'" in out
    assert "alpha-site" not in out and "Ship the core" not in out
    assert board.load("S1") is None


def test_another_live_session_on_the_project_is_named_because_one_session_owns_context(kb):
    board.touch("S2", project="alpha", goal="write the guards")
    out = project.resume("alpha", "S1")
    assert "Live session S2" in out and "write the guards" in out and "one session owns CONTEXT.md" in out


# --- R1.1: newer copies, from local git only ---------------------------------------------------

def test_a_checkout_behind_its_fetched_upstream_lists_the_changes_since(kb, tmp_path):
    other = _other_machine(kb, tmp_path)
    (other / "projects" / "alpha" / "CONTEXT.md").write_text(CONTEXT.replace("M2 core", "M3 skills"), encoding="utf-8")
    _commit_all(other, "Move alpha to M3")
    _git(other, "push", "-q", "origin", "main")
    assert "commit(s) behind" not in project.resume("alpha", "S1")  # not fetched yet: resume never touches the network
    _git(kb, "fetch", "-q", "origin")
    out = project.resume("alpha", "S2")
    assert "1 commit(s) behind its fetched origin/main" in out and "Move alpha to M3" in out
    assert "pull --ff-only" in out
    assert "Phase: M2 core" in out  # the local file is still what it says; the warning says it is old


def test_local_uncommitted_changes_are_listed_and_never_pulled_over(kb, tmp_path):
    other = _other_machine(kb, tmp_path)
    (other / "projects" / "alpha" / "REFERENCE.md").write_text("# Ref\n", encoding="utf-8")
    _commit_all(other, "Add reference")
    _git(other, "push", "-q", "origin", "main")
    _git(kb, "fetch", "-q", "origin")
    (kb / "projects" / "alpha" / "notes.md").write_text("local\n", encoding="utf-8")
    out = project.resume("alpha", "S1")
    assert "do not pull over them" in out and "projects/alpha/notes.md" in out
    assert (kb / "projects" / "alpha" / "notes.md").read_text() == "local\n"


def test_an_unreachable_remote_or_no_upstream_is_said_once_and_resume_continues(kb):
    _git(kb, "remote", "set-url", "origin", "/nonexistent/remote.git")
    assert "Ship the core first." in project.resume("alpha", "S1")  # nothing reached for the remote
    _git(kb, "branch", "--unset-upstream")
    out = project.resume("alpha", "S2")
    assert out.count("No fetched upstream") == 1 and "Ship the core first." in out


def test_a_newer_copy_on_an_unmerged_worktree_branch_is_named_with_where(kb, tmp_path):
    worktree = tmp_path / "wt"
    _git(kb, "worktree", "add", "-q", "-b", "feature", str(worktree))
    (worktree / "projects" / "alpha" / "CONTEXT.md").write_text(CONTEXT.replace("M2 core", "M2 done"), encoding="utf-8")
    _commit_all(worktree, "Finish M2 on the feature branch")
    out = project.resume("alpha", "S1")
    assert "newer copy on branch feature" in out and str(worktree) in out and "Finish M2" in out
    assert "Phase: M2 core" in out  # nothing was switched or merged
    assert _git(kb, "rev-parse", "--abbrev-ref", "HEAD") == "main"


def test_two_diverged_copies_are_reported_as_a_conflict_and_neither_is_picked(kb):
    _git(kb, "branch", "side")
    _git(kb, "checkout", "-q", "side")
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text(CONTEXT.replace("M2 core", "side"), encoding="utf-8")
    _commit_all(kb, "side change")
    _git(kb, "checkout", "-q", "main")
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text(CONTEXT.replace("M2 core", "main"), encoding="utf-8")
    _commit_all(kb, "main change")
    out = project.resume("alpha", "S1")
    assert "CONFLICT: branch side and this checkout both changed these records" in out
    assert "newer copy" not in out


def test_a_branch_whose_records_this_checkout_already_moved_past_is_not_reported(kb):
    _git(kb, "branch", "old")
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text(CONTEXT.replace("M2 core", "later"), encoding="utf-8")
    _commit_all(kb, "later")
    assert "branch old" not in project.resume("alpha", "S1")


def test_uncommitted_edits_in_two_working_copies_are_a_conflict(kb, tmp_path):
    worktree = tmp_path / "wt"
    _git(kb, "worktree", "add", "-q", "-b", "feature", str(worktree))
    (worktree / "projects" / "alpha" / "CONTEXT.md").write_text("there\n", encoding="utf-8")
    assert "worktree " + str(worktree) + " has 1 uncommitted change(s)" in project.resume("alpha", "S1")
    (kb / "projects" / "alpha" / "CONTEXT.md").write_text(CONTEXT + "here\n", encoding="utf-8")
    assert "CONFLICT: worktree" in project.resume("alpha", "S2")


def test_the_newest_session_ignores_dates_in_entry_bodies_and_the_generated_index(kb):
    proj = kb / "projects" / "alpha"
    (proj / "sessions" / "2026-10.md").write_text(
        "# October\n\n### 2026-10-04: board\n\nDue 2099-01-01, per the vendor.\n", encoding="utf-8")
    (proj / "sessions" / "INDEX.md").write_text("## 2099-12-31\n", encoding="utf-8")
    assert project.newest_session(proj) == ("2026-10-04", "2026-10.md")


# --- R1.2: the plan named on re-injection --------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("**Plan:** none\n", "Plan: none"),
    ("**Controlling plan:** none.\n", "Plan: none"),
    ("Earlier we followed [the old plan](resources/plan.md).\n", "Plan: none declared"),
    ("```\n**Plan:** resources/plan.md\n```\n", "Plan: none declared"),
    ("**Controlling plan:** [plan](resources/plan.md)\n", "Plan: resources/plan.md"),
    ("**Plan:** resources/missing.md\n", "Plan: resources/missing.md (file not found)"),
])
def test_the_plan_comes_from_one_field_and_none_means_none(kb, text, expected):
    assert project.plan(kb / "projects" / "alpha", text)[1] == expected


def test_two_plan_declarations_are_ambiguous_and_neither_is_chosen(kb):
    target, line = project.plan(kb / "projects" / "alpha", "**Plan:** a.md\n**Controlling plan:** b.md\n")
    assert target is None and "ambiguous, 2 declarations" in line


def test_the_reinjected_brief_names_the_plan_or_says_there_is_none(kb):
    proj = kb / "projects" / "alpha"
    assert "Plan: resources/plan.md" in project.brief(proj)
    (proj / "CONTEXT.md").write_text(CONTEXT.replace("[the plan](resources/plan.md)", "none"), encoding="utf-8")
    assert "Plan: none" in project.brief(proj) and "resources/plan.md" not in project.brief(proj)


# --- ported helpers ------------------------------------------------------------------------------

def test_next_actions_reads_a_next_actions_field_when_there_is_no_whats_next_section():
    text = "**Next actions:**\n- [ ] land wave 2\n- [x] done already\n- wire the hook\n\n## Notes\n- not an action\n"
    assert project.next_actions(text) == ["land wave 2", "wire the hook"]
    assert project.next_actions("**Next:** write the guards") == ["write the guards"]
    assert project.next_actions("## What's Next\n\n" + "".join(f"- [ ] item {i}\n" for i in range(9)), 2) == [
        "- [ ] item 0", "- [ ] item 1"]


def test_record_freshness_compares_with_the_fetched_upstream_only(kb, tmp_path):
    proj = kb / "projects" / "alpha"
    assert project.record_freshness(proj) == (True, "record current with fetched origin/main")
    other = _other_machine(kb, tmp_path)
    (other / "projects" / "alpha" / "x.md").write_text("x\n", encoding="utf-8")
    _commit_all(other, "x")
    _git(other, "push", "-q", "origin", "main")
    assert project.record_freshness(proj)[0] is True  # unfetched: unknown here, and never fetched for you
    _git(kb, "fetch", "-q", "origin")
    fresh, detail = project.record_freshness(proj)
    assert not fresh and "1 commit(s) behind fetched origin/main" in detail
