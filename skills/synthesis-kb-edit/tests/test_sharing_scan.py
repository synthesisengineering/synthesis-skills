"""The sharing policy's backstop scan: the organization's own phrases, in the lines a change adds to a knowledge base.

The plugin ships no phrase list (the principal's ruling of 2026-11-14), so every phrase here is made up and neutral,
and with none named the scan refuses to run. A hit names its file, line and phrase and nothing else of the line, since
what it found may be the very thing that should not be shown. Committed before the script."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sharing_scan.py"
POLICY = ".agents/sharing-policy.md"
PHRASES = ["zephyr ledger", "violet harbor", "opal"]
ABSENT = object()


@pytest.fixture(autouse=True)
def plain_git(tmp_path, monkeypatch):
    """No machine-wide hooks, identity or settings reach these test repositories."""
    config = tmp_path / "gitconfig"
    config.write_text("[user]\n\temail = test@example.com\n\tname = test\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def write_contract(repo: Path, **confidentiality) -> None:
    """A valid contract whose confidentiality block takes these keys; ABSENT leaves a key out."""
    block = {"forbidden_words_source": None, "hook_path": None, "visible_to": "Everyone in the organization",
             "sharing_policy": POLICY, "backstop_phrases": list(PHRASES), **confidentiality}
    config = {"bundle_path": "source", "git_host": "github", "default_branch": "main", "branch_prefix": "kb/",
              "ship": "pr", "review": {"who_merges": "A maintainer", "default_reviewers": [], "setup_guide": None},
              "editable": ["source/**"], "refuse": [".agents/**"], "generated_artifacts": [],
              "topic_routing": {"reference": "source/reference"}, "taxonomy_path": None,
              "frontmatter": {"required": ["type"], "house": ["title", "timestamp"], "date_field": "timestamp",
                              "reserved_files": ["index.md", "log.md"]},
              "confidentiality": {key: value for key, value in block.items() if value is not ABSENT}, "notes": ""}
    (repo / ".agents" / "knowledge-base.yaml").write_text(json.dumps(config), encoding="utf-8")


def write(repo: Path, relative: str, text: str) -> None:
    (repo / relative).parent.mkdir(parents=True, exist_ok=True)
    (repo / relative).write_text(text, encoding="utf-8")


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def kb(tmp_path):
    repo = tmp_path / "kb"
    (repo / ".agents").mkdir(parents=True)
    write_contract(repo)
    write(repo, POLICY, "# Sharing policy\n\nCode names such as zephyr ledger stay out.\n")
    write(repo, "source/reference/team.md", "# Team\n\nThe team has nine people.\n")
    git(repo.parent, "init", "-q", "-b", "main", str(repo))
    commit(repo, "start")
    return repo


def scan(repo: Path, *args: str):
    done = subprocess.run([sys.executable, str(SCRIPT), str(repo), *args], capture_output=True, text=True)
    return done.returncode, done.stdout, done.stderr


def test_a_held_line_names_its_file_line_and_phrase_and_nothing_else_of_it(kb):
    write(kb, "source/reference/plans.md", "# Plans\n\nThe Zephyr Ledger work opens on Tuesday.\n")
    code, out, err = scan(kb, "source/reference/plans.md", "source/reference/team.md")
    assert code == 1, err
    assert out.splitlines() == ['source/reference/plans.md:3: "zephyr ledger"',
                                f"sharing scan: 1 line held in 2 files read; read each against {POLICY}"]


def test_a_clean_file_passes_and_says_what_it_read(kb):
    code, out, err = scan(kb, "source/reference/team.md")
    assert (code, out.strip(), err) == (0, "sharing scan: clean, 1 file read for 3 phrases", "")


def test_a_range_judges_only_the_lines_it_adds_under_the_bundle(kb):
    base = git(kb, "rev-parse", "HEAD").strip()
    write(kb, "source/reference/old.md", "Notes on the violet harbor survey.\n")
    middle = commit(kb, "before the change under review")
    write(kb, "source/reference/old.md", "Notes on the violet harbor survey.\nNothing new of note.\n")
    write(kb, "source/reference/plan.md", "# Plan\n\nTwo zephyr ledgers close in March.\n")
    write(kb, "docs/guide.md", "How the violet harbor survey ran.\n")  # outside the bundle
    commit(kb, "the change under review")
    code, out, _ = scan(kb, "--range", f"{middle}...HEAD")
    assert code == 1 and out.splitlines()[:-1] == ['source/reference/plan.md:3: "zephyr ledger"']
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and out.splitlines()[:-1] == ['source/reference/old.md:1: "violet harbor"',
                                                   'source/reference/plan.md:3: "zephyr ledger"']
    code, out, _ = scan(kb, "--range", "HEAD...HEAD")
    assert (code, out.strip()) == (0, "sharing scan: clean, 0 files read for 3 phrases")


def test_a_file_moved_into_the_bundle_is_judged_whole(kb):
    """A move read as a rename adds no lines, so a file moved in from outside the bundle would pass unread."""
    write(kb, "docs/survey.md", "The violet harbor survey.\n")
    base = commit(kb, "a note outside the bundle")
    git(kb, "mv", "docs/survey.md", "source/reference/survey.md")
    commit(kb, "moved into the bundle")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and out.splitlines()[0] == 'source/reference/survey.md:1: "violet harbor"'


def test_what_is_staged_is_judged_for_a_commit_hook(kb):
    write(kb, "source/reference/review.md", "The opal review is set.\n")
    assert scan(kb, "--staged")[0] == 0  # written, not yet staged
    git(kb, "add", "-A")
    write(kb, "source/reference/review.md", "The review is set.\n")  # the index still holds the phrase
    code, out, _ = scan(kb, "--staged")
    assert code == 1 and out.splitlines()[0] == 'source/reference/review.md:1: "opal"'


def test_a_short_phrase_is_a_whole_word_and_a_longer_one_may_run_on(kb):
    write(kb, "source/reference/words.md",
          "An opalescent glaze.\n"   # 1: a short phrase inside a longer word
          "OPAL, at last.\n"         # 2: any letter case
          "The zephyr ledgers.\n"    # 3: a longer phrase runs on
          "zephyr \t ledger\n"       # 4: any run of spaces between its words
          "An ultraviolet harbor.\n"  # 5: never from inside a word
          "Two opals.\n")            # 6: a short phrase does not run on
    code, out, _ = scan(kb, "source/reference/words.md")
    assert code == 1 and [line.split(":")[1] for line in out.splitlines()[:-1]] == ["2", "3", "4"]


def test_a_folder_is_read_file_by_file(kb):
    write(kb, "source/projects/a.md", "Opal.\n")
    write(kb, "source/projects/b.md", "Nothing here.\n")
    code, out, _ = scan(kb, "source")
    assert code == 1 and out.splitlines() == ['source/projects/a.md:1: "opal"',
                                              f"sharing scan: 1 line held in 3 files read; read each against {POLICY}"]


def test_the_policy_and_the_contract_are_never_judged(kb):
    inside = "source/reference/sharing-policy.md"
    write_contract(kb, sharing_policy=inside)
    write(kb, inside, "# Sharing policy\n\nCode names such as zephyr ledger stay out.\n")
    code, out, _ = scan(kb, inside, ".agents/knowledge-base.yaml")
    assert code == 0 and f"{inside}: not judged" in out and ".agents/knowledge-base.yaml: not judged" in out
    git(kb, "add", "-A")
    assert scan(kb, "--staged")[0] == 0


def test_a_named_file_outside_the_bundle_is_said_and_not_judged(kb):
    write(kb, "docs/guide.md", "How the violet harbor survey ran.\n")
    code, out, _ = scan(kb, "docs/guide.md")
    assert code == 0 and "docs/guide.md: not judged, outside the bundle (source)" in out


def test_a_file_that_is_not_text_is_said_and_never_counted_as_read(kb):
    """The scan reads text only: a file it cannot read as text is named for the reviewer, never passed as clean."""
    (kb / "source" / "reference" / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0zephyr ledger\0")
    said = "source/reference/chart.png: not judged, not text (the scan reads text only)"
    code, out, _ = scan(kb, "source/reference/chart.png")
    assert code == 0 and out.splitlines() == [said, "sharing scan: clean, 0 files read for 3 phrases"]
    git(kb, "add", "-A")
    code, out, _ = scan(kb, "--staged")
    assert code == 0 and out.splitlines()[0] == said


def test_with_no_phrases_named_it_refuses_to_run_and_says_how_to_fix_it(kb):
    """The plugin ships none, and a scan with nothing to look for would pass everything; a contract that names a policy
    with no phrases holds every edit, and the refusal says both ways out."""
    for phrases in ([], ABSENT):
        write_contract(kb, backstop_phrases=phrases)
        code, out, err = scan(kb, "source/reference/team.md")
        assert code == 2 and out == ""
        assert "confidentiality.backstop_phrases" in err and "every edit is held" in err
        assert "list at least one" in err and "remove confidentiality.sharing_policy" in err


def test_with_no_policy_or_one_that_is_not_there_it_refuses_to_run(kb):
    write_contract(kb, sharing_policy=ABSENT)
    code, out, err = scan(kb, "source/reference/team.md")
    assert code == 2 and out == "" and "names no sharing policy" in err and "adopt-sharing-policy" in err
    write_contract(kb)
    (kb / POLICY).unlink()
    code, out, err = scan(kb, "source/reference/team.md")
    assert code == 2 and out == "" and f"{POLICY} named in the contract is not there" in err


def test_no_contract_an_invalid_one_or_no_repository_stops_it(kb, tmp_path):
    write_contract(kb, sharing_polcy=POLICY)  # a misspelled key
    code, _, err = scan(kb, "source/reference/team.md")
    assert code == 2 and "confidentiality.sharing_polcy" in err
    (kb / ".agents" / "knowledge-base.yaml").unlink()
    code, _, err = scan(kb, "source/reference/team.md")
    assert code == 2 and "missing configuration" in err
    plain = tmp_path / "plain"
    plain.mkdir()
    assert scan(plain, "notes.md")[0] == 2


def test_it_takes_exactly_one_way_of_choosing_lines(kb):
    assert scan(kb)[0] == 2  # nothing named
    assert scan(kb, "--staged", "source/reference/team.md")[0] == 2  # two ways at once
    code, _, err = scan(kb, "--range", "HEAD")  # one revision: git would read the working tree against it
    assert code == 2 and "BASE...HEAD" in err
    code, _, err = scan(kb, "--range", "nowhere...HEAD")
    assert code == 2 and "nowhere" in err  # git's own message, naming the revision it could not find
    code, _, err = scan(kb, "../outside.md")
    assert code == 2 and "escapes" in err


def test_it_needs_only_the_standard_library_and_the_checkouts_yaml_reader(kb, tmp_path):
    """From a checkout pinned to a tag, in a pipeline: no plugin installed and no synthesis home, only these four files
    of the checkout, run in isolated mode."""
    root = Path(__file__).resolve().parents[3]
    pinned = tmp_path / "pinned"
    for relative in ("synthesis/__init__.py", "synthesis/yamlish.py", "skills/synthesis-kb-edit/scripts/kb_config.py",
                     "skills/synthesis-kb-edit/scripts/sharing_scan.py"):
        (pinned / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, pinned / relative)
    done = subprocess.run([sys.executable, "-I", str(pinned / "skills/synthesis-kb-edit/scripts/sharing_scan.py"),
                           str(kb), "source/reference/team.md"], capture_output=True, text=True, cwd=tmp_path,
                          env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    assert done.returncode == 0, done.stderr
    assert not list(pinned.rglob("__pycache__"))  # nothing written into the checkout
