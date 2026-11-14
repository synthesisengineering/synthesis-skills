"""The sharing policy's backstop scan: the organization's own phrases, in the lines a change adds to a knowledge base.

The plugin ships no phrase list (the principal's ruling of 2026-11-14), so every phrase here is made up and neutral,
and with none named the scan refuses to run. A hit names its file, line and phrase and nothing else of the line, since
what it found may be the very thing that should not be shown. Committed before the script."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sharing_scan.py"
ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "sharing-policy.template.md"
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


def write_contract(repo: Path, bundle: str = "source", notes: str = "", **confidentiality) -> None:
    """A valid contract whose confidentiality block takes these keys; ABSENT leaves a key out."""
    block = {"forbidden_words_source": None, "hook_path": None, "visible_to": "Everyone in the organization",
             "sharing_policy": POLICY, "backstop_phrases": list(PHRASES), **confidentiality}
    config = {"bundle_path": bundle, "git_host": "github", "default_branch": "main", "branch_prefix": "kb/",
              "ship": "pr", "review": {"who_merges": "A maintainer", "default_reviewers": [], "setup_guide": None},
              "editable": ["source/**"], "refuse": [".agents/**"], "generated_artifacts": [],
              "topic_routing": {"reference": "source/reference"}, "taxonomy_path": None,
              "frontmatter": {"required": ["type"], "house": ["title", "timestamp"], "date_field": "timestamp",
                              "reserved_files": ["index.md", "log.md"]},
              "confidentiality": {key: value for key, value in block.items() if value is not ABSENT}, "notes": notes}
    (repo / ".agents" / "knowledge-base.yaml").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")


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
    write(repo, POLICY, "# Sharing policy\n\nCode names stay out.\n")
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


def test_the_policy_and_the_contract_are_judged_all_but_the_phrase_list(kb):
    """R1-4 and R1-27: only the phrase list is the list itself. A fact written into the policy (its examples, its
    rulings) or into the contract's notes reaches every reader of the repository, so both are judged."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write_contract(kb, notes="The zephyr ledger deal closes Friday.")
    write(kb, POLICY, "# Sharing policy\n\nAn example that stayed out: the violet harbor terms.\n")
    commit(kb, "notes and an example")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1, out
    assert '.agents/knowledge-base.yaml: notes: "zephyr ledger"' in out and f'{POLICY}:3: "violet harbor"' in out
    assert "backstop_phrases" not in out  # the list itself is not held
    code, out, _ = scan(kb, POLICY, ".agents/knowledge-base.yaml")  # named, in whole-file mode
    assert code == 1 and f'{POLICY}:3: "violet harbor"' in out and 'knowledge-base.yaml: notes: "zephyr ledger"' in out


def test_a_named_file_outside_the_bundle_is_said_and_not_judged(kb):
    write(kb, "docs/guide.md", "How the violet harbor survey ran.\n")
    code, out, _ = scan(kb, "docs/guide.md")
    assert code == 0 and "docs/guide.md: not judged, outside the bundle (source)" in out


def test_a_file_the_scan_cannot_read_is_held_for_a_person_never_passed(kb):
    """R1-2 and R1-7: a PDF, an image, or text in another encoding (Windows-1252) is held for a person to read, with
    its reason, in every mode; a file is never passed for being unreadable."""
    held = {"source/reference/chart.png": b"\x89PNG\r\n\x1a\n\0\0zephyr ledger\0",
            "source/reference/terms.pdf": b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj (zephyr ledger) endobj\n%%EOF\n",
            "source/reference/memo.txt": "Call Ren\u00e9e about the violet harbor.\n".encode("cp1252")}
    for relative, data in held.items():
        (kb / relative).write_bytes(data)
    said = [f"{relative}: held, not text: a person must read it" for relative in sorted(held)]
    code, out, _ = scan(kb, *sorted(held))
    assert code == 1 and [line for line in out.splitlines() if ": held, not text" in line] == said, out
    git(kb, "add", "-A")
    code, out, _ = scan(kb, "--staged")
    assert code == 1 and [line for line in out.splitlines() if ": held, not text" in line] == said, out


def test_files_people_read_are_exempt_only_when_the_contract_before_the_change_says_so(kb):
    """R1-2: an organization may name the files only people read (`unread_allowed`); a change cannot exempt itself."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write_contract(kb, unread_allowed=["source/**/*.png"])
    (kb / "source" / "reference" / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0")
    middle = commit(kb, "the change grants its own exemption")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and "source/reference/chart.png: held, not text: a person must read it" in out
    (kb / "source" / "reference" / "graph.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\1")
    commit(kb, "an image under an exemption the base already had")
    code, out, _ = scan(kb, "--range", f"{middle}...HEAD")
    assert code == 0 and "source/reference/graph.png: not judged, read by people (unread_allowed)" in out


def test_a_file_gitattributes_marks_as_binary_is_still_read(kb):
    """R1-2: `.gitattributes` (`-diff`, `binary`), added anywhere, cannot turn the bundle's text into unread files."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write(kb, ".gitattributes", "*.md -diff\n")
    write(kb, "source/reference/deal.md", "The zephyr ledger deal closes Friday.\n")
    commit(kb, "attributes and a deal")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and 'source/reference/deal.md:1: "zephyr ledger"' in out, out


def test_utf16_text_with_its_byte_order_mark_is_read(kb):
    """R1-2: Excel's "Unicode Text" export is UTF-16 with a byte-order mark."""
    base = git(kb, "rev-parse", "HEAD").strip()
    (kb / "source" / "reference" / "terms.txt").write_bytes("\ufeffItem\tPrice\nzephyr ledger\t4.2\n".encode("utf-16-le"))
    commit(kb, "an export")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and 'source/reference/terms.txt:2: "zephyr ledger"' in out, out


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


# ---- review round 1: what the scan reads, and what governs it --------------------------------------------------------

def test_a_bundle_the_change_renamed_away_stops_the_scan(kb):
    """R1-1: a change that renames the bundle folder and leaves the contract as it was would read nothing, and pass."""
    base = git(kb, "rev-parse", "HEAD").strip()
    git(kb, "mv", "source", "knowledge")
    write(kb, "knowledge/reference/plans.md", "The zephyr ledger deal closes Friday.\n")
    commit(kb, "the bundle renamed; the contract left as it was")
    code, out, err = scan(kb, "--range", f"{base}...HEAD")
    assert code == 2 and out == "" and "the bundle source holds no file git tracks" in err, err


def test_a_bundle_spelled_in_another_letter_case_stops_the_scan_in_every_mode(kb):
    """R1-1: a Mac's disk finds `Source` for `source`; git's pathspec does not, so the scan read nothing."""
    write_contract(kb, bundle="Source")
    base = commit(kb, "the contract says Source; git tracks source")
    write(kb, "source/reference/plans.md", "The zephyr ledger deal closes Friday.\n")
    git(kb, "add", "-A")
    code, out, err = scan(kb, "--staged")
    assert code == 2 and "the bundle Source holds no file git tracks" in err, err
    code, out, err = scan(kb, "source/reference/plans.md")
    assert code == 2 and "Source" in err, err  # the configuration gate names it (spelled otherwise, or not there)
    commit(kb, "the edit")
    code, out, err = scan(kb, "--range", f"{base}...HEAD")
    assert code == 2 and "the bundle Source holds no file git tracks" in err, err


def test_a_change_cannot_drop_the_phrase_that_would_hold_it(kb):
    """R1-4: the contract before the change governs too; the reader is told which phrases the change takes out."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write_contract(kb, backstop_phrases=["opal"])
    write(kb, "source/reference/deal.md", "The zephyr ledger deal closes Friday.\n")
    commit(kb, "a deal, and a shorter list")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and 'source/reference/deal.md:1: "zephyr ledger"' in out, out
    assert 'sharing scan: the change takes 2 phrases out of the contract, still judged here: "zephyr ledger", "violet harbor"' in out


def test_a_change_cannot_point_the_policy_at_the_file_that_leaks(kb):
    base = git(kb, "rev-parse", "HEAD").strip()
    write_contract(kb, sharing_policy="source/reference/leak.md")
    write(kb, "source/reference/leak.md", "The zephyr ledger deal closes Friday.\n")
    commit(kb, "the policy re-pointed")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and 'source/reference/leak.md:1: "zephyr ledger"' in out, out


def test_staged_judges_with_the_stricter_of_head_and_the_index_never_the_working_tree(kb):
    """R1-4: an unstaged edit to the contract does not govern the commit, and a staged one cannot loosen it."""
    write(kb, "source/reference/deal.md", "The zephyr ledger deal closes Friday.\n")
    git(kb, "add", "-A")
    write_contract(kb, backstop_phrases=["opal"])  # in the working tree only
    code, out, _ = scan(kb, "--staged")
    assert code == 1 and 'source/reference/deal.md:1: "zephyr ledger"' in out, out
    git(kb, "add", "-A")  # and now staged too
    code, out, _ = scan(kb, "--staged")
    assert code == 1 and 'source/reference/deal.md:1: "zephyr ledger"' in out and "takes 2 phrases out" in out, out


def test_file_and_folder_names_are_judged(kb):
    """R1-5: a path is the first thing every reader sees: listings, links and indexes."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write(kb, "source/projects/zephyr-ledger-acquisition.md", "# Plan\n\nNothing here.\n")
    write(kb, "source/violet harbor/notes.md", "# Notes\n")
    commit(kb, "two pages")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1, out
    assert 'source/projects/zephyr-ledger-acquisition.md: name: "zephyr ledger"' in out
    assert 'source/violet harbor/notes.md: name: "violet harbor"' in out
    code, out, _ = scan(kb, "source/projects")
    assert code == 1 and 'source/projects/zephyr-ledger-acquisition.md: name: "zephyr ledger"' in out


def test_slugs_identifiers_and_camel_case_are_read_as_words(kb):
    """R1-6: the forms code names most often take in a knowledge base."""
    write(kb, "source/reference/forms.md",
          "See [plan](../projects/zephyr-ledger/plan.md).\n"  # 1: a slug in a link
          "Set `zephyr_ledger_enabled` to true.\n"            # 2: snake_case
          "The ZephyrLedger service.\n"                       # 3: CamelCase
          "tag: project_opal\n"                               # 4: a short phrase after an underscore
          "bucket: client_violetharbor_exports\n"             # 5: words run together after an underscore
          "An opalescent glaze.\n")                           # 6: still not a short phrase inside a longer word
    code, out, _ = scan(kb, "source/reference/forms.md")
    assert code == 1 and [line.split(":")[1] for line in out.splitlines()[:-1]] == ["1", "2", "3", "4", "5"], out


def test_unicode_variants_of_a_phrase_are_held(kb):
    """R1-7: decomposed accents (a macOS paste), typographic apostrophes (Word, Docs, Slack) and invisible characters."""
    write_contract(kb, backstop_phrases=PHRASES + ["renée", "o'hara"])
    write(kb, "source/reference/variants.md",
          "Call Renée about it.\n"         # 1: NFD
          "Ask O’Hara first.\n"             # 2: a typographic apostrophe
          "The zeph­yr ledger plan.\n"      # 3: a soft hyphen inside a word
          "The zephyr​ ledger plan.\n"      # 4: a zero-width space
          "The zephyr‑ledger plan.\n")      # 5: a non-breaking hyphen
    code, out, _ = scan(kb, "source/reference/variants.md")
    assert code == 1 and [line.split(":")[1] for line in out.splitlines()[:-1]] == ["1", "2", "3", "4", "5"], out


def test_a_phrase_wrapped_across_two_lines_is_held(kb):
    """R1-8: hard-wrapped Markdown, and a phrase whose first word is on a line the change does not touch."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write(kb, "source/reference/a.md", "The team that runs the zephyr\nledger met today.\n")
    middle = commit(kb, "a wrapped phrase")
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and out.splitlines()[0] == 'source/reference/a.md:2: "zephyr ledger"', out
    write(kb, "source/reference/b.md", "We met the violet\n")
    write(kb, "source/reference/c.md", "The zephyr ledger is old news.\n")
    later = commit(kb, "two lines the next change leaves alone")
    write(kb, "source/reference/b.md", "We met the violet\nharbor team.\n")
    write(kb, "source/reference/c.md", "The zephyr ledger is old news.\nA new line.\n")
    commit(kb, "the second word added; and a line after an old phrase")
    code, out, _ = scan(kb, "--range", f"{later}...HEAD")
    assert code == 1 and out.splitlines()[:-1] == ['source/reference/b.md:2: "violet harbor"'], out
    assert middle


def test_whole_file_mode_never_follows_a_link_and_judges_where_it_points(kb, tmp_path):
    """R1-19: a link is listed and judged by where it points, as git stores it; what it points at is never read."""
    outside = tmp_path / "outside-notes.txt"
    outside.write_text("The zephyr ledger deal closes Friday.\n", encoding="utf-8")
    os.symlink(outside, kb / "source" / "link.md")
    os.symlink("zephyr-ledger.md", kb / "source" / "alias.md")
    code, out, _ = scan(kb, "source")
    assert "source/link.md: a link, not followed" in out and "source/alias.md: a link, not followed" in out, out
    assert 'source/alias.md:1: "zephyr ledger"' in out and "source/link.md:1" not in out and code == 1


def test_a_ranges_commit_messages_are_judged(kb):
    """R1-25: the repository's readers read its history."""
    base = git(kb, "rev-parse", "HEAD").strip()
    write(kb, "source/reference/notes.md", "# Notes\n")
    commit(kb, "Add notes\n\nAbout the zephyr ledger term sheet.")
    sha = git(kb, "rev-parse", "HEAD").strip()[:12]
    code, out, _ = scan(kb, "--range", f"{base}...HEAD")
    assert code == 1 and f'commit {sha}:3: "zephyr ledger"' in out, out


def test_the_commit_message_hook_form_judges_the_message_and_not_gits_comments(kb, tmp_path):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("Add notes\n\nAbout the violet harbor survey.\n# git's own comment lines are stripped: opal\n",
                       encoding="utf-8")
    code, out, _ = scan(kb, "--message", str(message))
    assert code == 1 and out.splitlines()[:-1] == ['commit message:3: "violet harbor"'], out


def test_a_named_policy_still_the_template_as_written_stops_the_scan(kb):
    """R1-18: a policy that does not yet say who reads it cannot decide what is shared."""
    write(kb, POLICY, TEMPLATE.read_text(encoding="utf-8"))
    code, out, err = scan(kb, "source/reference/team.md")
    assert code == 2 and "fill in who reads it" in err, err
    base = commit(kb, "the template, unfilled")
    write(kb, "source/reference/more.md", "More.\n")
    commit(kb, "an edit")
    code, out, err = scan(kb, "--range", f"{base}...HEAD")
    assert code == 2 and "fill in who reads it" in err, err


def test_the_standards_hooks_run_as_printed_from_the_runtime_synthesis_installs(kb, monkeypatch):
    """R1-9: the hooks the standard prints work against the stable runtime the installer builds, with no environment
    variable set, and the doctor fails a runtime that has lost the scan."""
    sys.path.insert(0, str(ROOT))
    from synthesis import doctor, install, paths
    monkeypatch.delenv("SYNTHESIS_SKILLS", raising=False)
    install.install(ROOT)
    home = paths.home()
    scanner = home / "current" / "skills" / "synthesis-kb-edit" / "scripts" / "sharing_scan.py"
    assert scanner.is_file() and doctor.check_runtime(home).status == "ok"
    standard = (ROOT / "skills" / "synthesis-kb-edit" / "references" / "sharing-standard.md").read_text(encoding="utf-8")
    for hook in ("pre-commit", "commit-msg"):
        text = re.search(r"```sh\n(#!/bin/sh\n# \.githooks/" + hook + r":.*?)```", standard, flags=re.S).group(1)
        (kb / ".githooks").mkdir(exist_ok=True)
        (kb / ".githooks" / hook).write_text(text, encoding="utf-8")
        (kb / ".githooks" / hook).chmod(0o755)
    git(kb, "config", "core.hooksPath", ".githooks")
    write(kb, "source/reference/clean.md", "A clean line.\n")
    git(kb, "add", "-A")
    assert subprocess.run(["git", "-C", str(kb), "commit", "-qm", "A clean edit"], capture_output=True).returncode == 0
    write(kb, "source/reference/deal.md", "The zephyr ledger deal closes Friday.\n")
    git(kb, "add", "-A")
    assert subprocess.run(["git", "-C", str(kb), "commit", "-qm", "A deal"], capture_output=True).returncode != 0
    git(kb, "reset", "-q", "HEAD", "--", "source/reference/deal.md")
    write(kb, "source/reference/other.md", "Another clean line.\n")
    git(kb, "add", "source/reference/other.md")
    assert subprocess.run(["git", "-C", str(kb), "commit", "-qm", "About the violet harbor"],
                          capture_output=True).returncode != 0  # the message alone holds a phrase
    os.chmod(scanner, 0o644)
    scanner.unlink()
    assert doctor.check_runtime(home).status == "fail"
