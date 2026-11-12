"""build_directory_package.py: the hook-free package of method skills, for a plugin directory that lists no
plugin with lifecycle hooks.

Three groups. The first reads one real build, made once into a temporary folder: what the ZIP holds, where each
byte came from, and that no packaged line promises what the package cannot do. The second gives the checks
checkouts and archives that must fail. The third is the command line: one line of output and an exit code.

Which phrases count, decided from what the skills outside the list say (the guards, the board, the rituals):

  a hook claim            PreToolUse, SessionStart, UserPromptSubmit; "Stop hook", "session-start hook", "prompt
                          hook", "lifecycle hooks", "git hooks", "v5 hooks", "synthesis-hook"; "the commit check";
                          hooks.json; core.hooksPath; and "hook" before a verb of enforcement ("the hook refuses"):
                          refuse, block, deny, stop, check, enforce, catch, hold, ask, wait, let, run, re-inject
  a guard claim           a guard by its name, spaced or hyphenated, so the name of a guard skill counts: a send,
                          message, deploy, shell, write, browser, account-routing, repo, commit, publish, pre-tool,
                          synthesis or v5 guard; "the guard"; "agent guardrails"; guards.py; and "guard" before
                          one of the same verbs ("each guard blocks")
  an approval-code claim  "approve <code>", "approval code", "six-character code", "type approve" and
                          "waits for the code"
  a runtime need          the `synthesis` command in backticks, ~/.synthesis/v5, SYNTHESIS_HOME and an import of
                          the synthesis core

The same words in their ordinary senses pass: a writer's opening hook, a guard clause, a pull request someone
approved, a project's own pre-commit hooks in a review checklist. SPARED pins them.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_directory_package as package  # noqa: E402

SPEC = json.loads((ROOT / package.LIST).read_text(encoding="utf-8"))
LISTED = SPEC["skills"]
LEFT_OUT = SPEC.get("left_out", {})  # skills the list names as left out, each with the reason
PLUGIN_MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json")
EVERY_KIND = {"a hook claim", "a guard claim", "an approval-code claim", "a runtime need"}


# A checkout a test makes is written with none of the machine's git settings: its hooks, signing and identity
# stay out. The real checkout is read with the settings it was cloned under.
OWN_GIT = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env=None if repo == ROOT else OWN_GIT).stdout


def is_test(name: str) -> bool:
    return "tests" in name.split("/") or name.rsplit("/", 1)[-1].startswith("test_")


def dependencies(skill_md: str) -> list:
    """`depends_on` in either YAML list form, read as tests/test_source_lint.py reads it."""
    match = re.match(r"---\n(.*?)\n---\n", skill_md, re.S)
    found = re.search(r"^depends_on:\s*(\[.*?\])?\s*$((?:\n\s+- .*)*)", match.group(1) if match else "", re.M)
    if found and found.group(1):
        return [name.strip().strip("\"'") for name in found.group(1)[1:-1].split(",") if name.strip()]
    return re.findall(r"^\s+- \"?([\w.-]+)\"?\s*$", found.group(2), re.M) if found else []


def claimed(skill: str) -> list:
    """(path, line number, kinds) for each line a package of this skill would carry that the check refuses."""
    found = []
    for path in sorted((ROOT / "skills" / skill).rglob("*")):
        name = path.relative_to(ROOT).as_posix()
        if path.is_file() and "__pycache__" not in path.parts and not is_test(name):
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            found += [(name, number, kinds) for number, line in enumerate(lines, 1)
                      for kinds in [package.claims(line)] if kinds]
    return found


# ---- one real build, read back -----------------------------------------------------

@pytest.fixture(scope="module")
def zip_path(tmp_path_factory):
    out = tmp_path_factory.mktemp("directory-package") / "methods.zip"
    out.write_bytes(package.build(ROOT, SPEC))
    return out


@pytest.fixture(scope="module")
def built(zip_path):
    """{name in the ZIP: its bytes}."""
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.testzip() is None
        return {name: archive.read(name) for name in archive.namelist()}


def test_the_zip_holds_no_hooks_folder_and_registers_no_hook(built):
    def keys(value):
        for key, inner in value.items() if isinstance(value, dict) else ():
            yield key
            yield from keys(inner)
        for inner in value if isinstance(value, list) else ():
            yield from keys(inner)

    assert [name for name in built if "hooks" in name.split("/") or name.endswith("hooks.json")] == []
    assert "hooks" not in set(keys(json.loads(built[package.MANIFEST])))
    assert [name for name in built if name.endswith("plugin.json")] == [package.MANIFEST]  # no second manifest


def test_the_zip_holds_only_the_listed_skills_and_the_manifest(built):
    outside = [name for name in built if name != package.MANIFEST
               and not (name.startswith("skills/") and name.split("/")[1] in LISTED and name.count("/") >= 2)]
    assert outside == []
    assert {name.split("/")[1] for name in built if name != package.MANIFEST} == set(LISTED)


def test_each_listed_skill_is_whole_but_for_its_tests(built):
    """A test is the repository's check on a skill, not the skill: one of them imports the synthesis core."""
    tracked = git(ROOT, "ls-files", "-z", "--", *[f"skills/{name}" for name in LISTED]).split("\0")
    assert set(built) - {package.MANIFEST} == {name for name in tracked if name and not is_test(name)}
    assert [name for name in built if is_test(name)] == []
    assert all(f"skills/{name}/{part}" in built for name in LISTED for part in ("SKILL.md", "agents/openai.yaml"))


def test_every_packaged_file_is_byte_identical_to_its_source(built):
    assert [name for name, data in built.items()
            if name != package.MANIFEST and (ROOT / name).read_bytes() != data] == []


def test_a_script_keeps_its_executable_bit_and_a_build_is_repeatable(zip_path):
    with zipfile.ZipFile(zip_path) as archive:
        modes = {entry.filename: entry.external_attr >> 16 for entry in archive.infolist()}
        assert {entry.date_time for entry in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}  # no build's own clock
    executable = {name.split("\t", 1)[1] for name in git(ROOT, "ls-files", "-s", "-z").split("\0")
                  if name.startswith("100755")}
    assert {name for name, mode in modes.items() if mode & 0o111} == executable & set(modes)
    assert package.build(ROOT, SPEC) == zip_path.read_bytes()


def test_every_dependency_of_a_listed_skill_is_listed():
    def closure(name, seen):
        for need in dependencies((ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")):
            if need not in seen:
                seen.add(need)
                closure(need, seen)
        return seen

    outside = {name: sorted(closure(name, set()) - set(LISTED)) for name in LISTED}
    assert {name: needs for name, needs in outside.items() if needs} == {}


def test_the_build_reads_dependencies_in_both_list_forms():
    for skill_md in sorted(ROOT.glob("skills/*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        assert package.depends_on(text) == dependencies(text), skill_md.parent.name
    block = "---\nname: x\ndepends_on:\n  - synthesis-a\n  - \"synthesis-b\"\nmetadata:\n  format: v5\n---\n"
    assert package.depends_on(block) == ["synthesis-a", "synthesis-b"]
    unindented = block.replace("\n  - ", "\n- ")  # YAML allows a block list at its key's own indent
    assert package.depends_on(unindented) == ["synthesis-a", "synthesis-b"]
    assert package.depends_on("---\nname: x\n---\ndepends_on: [\"not-frontmatter\"]\n") == []


def test_the_manifest_carries_the_repository_version_and_the_words_of_the_list(built):
    manifest = json.loads(built[package.MANIFEST])
    versions = {json.loads((ROOT / name).read_text(encoding="utf-8"))["version"] for name in PLUGIN_MANIFESTS}
    assert versions == {manifest["version"]}
    assert {key: manifest[key] for key in SPEC["manifest"]} == SPEC["manifest"]
    assert manifest["skills"] == "./skills/"
    plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert {key: manifest[key] for key in ("author", "homepage", "repository", "license")} == \
        {key: plugin[key] for key in ("author", "homepage", "repository", "license")}
    assert manifest["name"] != plugin["name"]  # its own name: it is not the plugin, and must not pass for it


def test_the_description_says_what_the_package_lacks_and_where_the_whole_system_is(built):
    manifest = json.loads(built[package.MANIFEST])
    said = manifest["description"]
    assert [word for word in ("guards", "board", "rituals") if word not in said] == []
    assert manifest["repository"] in said
    assert manifest["interface"]["longDescription"] == said


def test_every_name_on_the_list_is_a_skill_here_and_none_is_both_listed_and_left_out():
    assert len(LISTED) == len(set(LISTED))
    assert [name for name in [*LISTED, *LEFT_OUT] if not (ROOT / "skills" / name / "SKILL.md").is_file()] == []
    assert set(LEFT_OUT) & set(LISTED) == set()


def test_no_packaged_line_claims_a_hook_a_guard_or_an_approval_code_or_needs_the_runtime(built):
    found = [f"{name}:{number}: {', '.join(kinds)}: {line.strip()[:100]}"
             for name, data in sorted(built.items())
             for number, line in enumerate(data.decode("utf-8").splitlines(), 1)
             for kinds in [package.claims(line)] if kinds]
    assert found == []


def test_the_real_package_passes_its_own_check(capsys):
    assert package.main(["--check"]) == 0
    assert capsys.readouterr().out.startswith(f"ok: {len(LISTED)} skills, ")


# ---- the phrases, against skills that must fail ------------------------------------------

@pytest.mark.parametrize("skill, at_least", [
    ("synthesis-message-guard", EVERY_KIND),
    ("synthesis-agent-guardrails", EVERY_KIND),
    ("synthesis-git-hooks", {"a hook claim", "an approval-code claim", "a runtime need"}),
    ("synthesis-repo-guard", {"a guard claim"}),
    # A skill that mentions a guard or a command only in passing is caught too, whatever it mentions.
    ("synthesis-implementation-integrity", set()),
    ("synthesis-anti-shortcuts", set()),
    ("synthesis-adversarial-review", set()),
    ("synthesis-decision-packet", set()),
    ("synthesis-agent-correspondence", set()),
])
def test_a_runtime_skill_fails_on_its_own_text(skill, at_least):
    kinds = {kind for _, _, found in claimed(skill) for kind in found}
    assert skill not in LISTED
    assert kinds and at_least <= kinds, f"{skill} no longer fails as it did; if it needs nothing now, it may be listed"


def test_a_skill_left_out_of_the_list_is_recorded_with_its_reason_and_still_fails():
    """Left out, never edited to pass. When its text stops failing, this test says it may come back."""
    for name, why in LEFT_OUT.items():
        assert why.strip()
        assert claimed(name), f"{name} no longer fails the check: it may return to the list"


CLAIMED = [  # (kind, a line as a skill outside the list writes it)
    ("a hook claim", "the hook refuses this send until the principal approves"),  # the promise the check keeps out
    ("a hook claim", "closed. The v5 PreToolUse hook runs `guards.check_send` on every Slack, Gmail, email,"),
    ("a hook claim", "CONTEXT.md, which the SessionStart hook re-injects."),
    ("a hook claim", "These five are also in the v5 Stop hook's built-in list, so a reply using them bare is sent"),
    ("a hook claim", "the code in their own prompt; the prompt hook records the grant."),
    ("a hook claim", "commit check refuses credentials and unapproved disclosures. Record which"),
    ("a hook claim", "`synthesis doctor` then shows `git hooks: core.hooksPath -> ~/.synthesis/v5/git-hooks`."),
    ("a hook claim", "The hook enforces this at the commit boundary because the alternative"),
    ("a hook claim", "if a pre-commit hook blocks a commit, STOP and ask the user."),
    ("a hook claim", "- Install or diagnose repository policy hooks: `../synthesis-git-hooks/SKILL.md`"),
    ("a guard claim", "in v5, a merge refuses without passing PR CI, the send and deploy guards refuse"),
    ("a guard claim", "name a narrower target; never route around the guard."),
    ("a guard claim", "approval of that exact command (the v5 deploy guard, R3.2), and a clean scan covers only"),
    ("a guard claim", "- **Procedure** (below): configure, and what to do when each guard blocks."),
    ("a guard claim", "- Enforce outbound-message safety: `../synthesis-message-guard/SKILL.md`"),
    ("a guard claim", "- Sync machines or protect repository state: `../synthesis-mac-sync/SKILL.md`, "
                      "`../synthesis-repo-guard/SKILL.md`"),
    ("an approval-code claim", "only the principal typing `approve <code>` in their own prompt grants it"),
    ("an approval-code claim", "without the principal's single-use approval code for that exact action, and the"),
    ("an approval-code claim", "A blocked send files a request with a six-character code;"),
    ("an approval-code claim", "type approve followed by the code <code>`. Show the principal the exact text"),
    ("an approval-code claim", "wait for the code; work in the principal's `own_repos` does not."),
    ("a runtime need", "1. Find the holder: `synthesis who`."),
    ("a runtime need", "1. **Configure** in `~/.synthesis/v5/config.json` (references/config.md)"),
    ("a runtime need", "For one-off testing of the engine itself, point `SYNTHESIS_HOME` at a scratch folder"),
    ("a runtime need", "from synthesis import yamlish  # noqa: E402"),
]

SPARED = [  # the same words in their ordinary senses: lines of method skills, and one made up at the end
    "#### 1. Opening Hook (Personal Experience)",
    "- First tweet is the hook",
    "- Start strong to hook readers",
    "When the diff introduces a new component, utility, hook, or abstraction, search the codebase",
    # A review checklist's item about the reviewed project's own hooks, and advice to add a check of one's own.
    "- [ ] Standard: **Pre-Commit Secret Scanning** — Pre-commit hooks using tools like `gitleaks`, `truffleHog`, "
    "or `detect-secrets` to block secret commits before they enter git history",
    "Add a pre-commit check that flags patterns like `log.*secret`, `print.*token`, `console.log.*password` in "
    "staged files.",
    "- [ ] Standard: **Early Returns** — Guard clauses reduce nesting",
    "Add a guard test whenever you:",
    "requirement, its pre-push guard, its pre-PR checklist, and its deploy",
    "## Storage guard",  # a check the skill's own script makes, and the script ships with it
    "12. **Production deploys always require explicit human approval.**",
    "6. **Exclude before scoring:** your own PRs, drafts, PRs you already approved, and PRs you reviewed with no "
    "code commits since.",
    "1. **Reads are free; writes are deliberate.** Never `approve`, `merge`, `decline`, or `create` without the "
    "operator's explicit intent for that specific PR.",
    "            data = json.loads(out.stdout or \"\", object_pairs_hook=_unique_object)",
    "The state directory defaults to `~/.synthesis/local-models/`. A successful",
    # The discipline's name at the start of a wrapped line, and a skill's name in backticks, are no command.
    "synthesis engineering practices, and `synthesis-content-quality` is the skill that checks them",
]


@pytest.mark.parametrize("kind, line", CLAIMED)
def test_each_phrase_is_caught(kind, line):
    assert kind in package.claims(line)


@pytest.mark.parametrize("line", SPARED)
def test_the_ordinary_senses_of_the_words_pass(line):
    assert package.claims(line) == []


# ---- checkouts and archives that must fail --------------------------------------------

def skill(name, depends="[]", body="Prose only.\n"):
    return {"SKILL.md": f"---\nname: {name}\ndepends_on: {depends}\n---\n\n{body}",
            "agents/openai.yaml": "interface:\n  display_name: \"x\"\n"}


def checkout(tmp_path, skills, listed=None, manifest=None, version="5.8.0"):
    """A committed checkout holding these skills, a list that names `listed` (default: all) and one manifest."""
    repo = tmp_path / "checkout"
    files = {package.MANIFEST: json.dumps({"name": "synthesis-skills", "version": version}),
             package.LIST: json.dumps({"skills": sorted(skills) if listed is None else listed,
                                       "manifest": manifest or {"name": "methods", "description": "Methods."}})}
    for name, parts in skills.items():
        files.update({f"skills/{name}/{part}": text for part, text in parts.items()})
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    return repo


def problems(repo):
    spec = package.read_list(repo)
    return package.verify(repo, spec, package.build(repo, spec))


def test_a_sound_checkout_has_no_problem(tmp_path):
    repo = checkout(tmp_path, {"alpha": skill("alpha", '["beta"]'), "beta": skill("beta")})
    assert problems(repo) == []


@pytest.mark.parametrize("skills, listed, manifest, expected", [
    ({"alpha": {**skill("alpha"), "hooks/hooks.json": "{}\n"}}, None, None,
     "skills/alpha/hooks/hooks.json: holds or registers a hook"),
    ({"alpha": skill("alpha")}, None, {"name": "methods", "hooks": "./hooks/hooks.json"},
     ".codex-plugin/plugin.json: holds or registers a hook"),
    ({"alpha": skill("alpha")}, None, {"name": "methods", "extensions": {"com.openai": {"hooks": {"Stop": []}}}},
     ".codex-plugin/plugin.json: holds or registers a hook"),
    ({"alpha": skill("alpha", '["gamma"]'), "gamma": skill("gamma")}, ["alpha"], None,
     "skills/alpha/SKILL.md: depends on gamma, which is not on the list"),
    ({"alpha": skill("alpha", "\n  - gamma"), "gamma": skill("gamma")}, ["alpha"], None,
     "skills/alpha/SKILL.md: depends on gamma, which is not on the list"),
    ({"alpha": skill("alpha")}, ["alpha", "absent"], None,
     "skills/absent/SKILL.md: missing, so absent is no skill of this checkout"),
    ({"alpha": skill("alpha", body="The PreToolUse hook holds a send until the principal types `approve <code>`.\n")},
     None, None, "skills/alpha/SKILL.md:6: a hook claim, an approval-code claim: The PreToolUse hook holds"),
    ({"alpha": {**skill("alpha"), "references/setup.md": "Run `synthesis doctor` first.\n"}}, None, None,
     "skills/alpha/references/setup.md:1: a runtime need: Run `synthesis doctor` first."),
    ({"alpha": {**skill("alpha"), "scripts/run.py": "from synthesis import yamlish\n"}}, None, None,
     "skills/alpha/scripts/run.py:1: a runtime need: from synthesis import yamlish"),
    ({"alpha": skill("alpha")}, None, {"name": "methods", "description": "The guard refuses what it must."},
     ".codex-plugin/plugin.json:4: a guard claim"),
    ({"alpha": skill("alpha")}, None, {"name": "methods", "version": "9.9.9"},
     ".codex-plugin/plugin.json: version 9.9.9, not the repository's 5.8.0"),
])
def test_a_checkout_that_must_fail_does(tmp_path, skills, listed, manifest, expected):
    found = problems(checkout(tmp_path, skills, listed, manifest))
    assert any(problem.startswith(expected) for problem in found), found


def test_a_skill_that_gains_a_claim_drops_out_by_failing_and_passes_once_off_the_list(tmp_path):
    promise = "The send guard holds every message until it is approved.\n"
    repo = checkout(tmp_path, {"alpha": skill("alpha"), "beta": skill("beta", body=promise)})
    assert [problem for problem in problems(repo) if "a guard claim" in problem]
    listing = repo / package.LIST
    listing.write_text(json.dumps({**json.loads(listing.read_text()), "skills": ["alpha"]}))
    assert problems(repo) == []


def test_tests_stay_out_of_the_package_and_everything_else_of_a_skill_goes_in(tmp_path):
    parts = {**skill("alpha"), "scripts/run.py": "print('x')\n", "scripts/test_run.py": "from synthesis import x\n",
             "tests/test_alpha.py": "import run\n", "tests/fixtures/sample.json": "{}\n",
             "references/method.md": "A method.\n", "assets/table.yaml": "a: 1\n"}
    repo = checkout(tmp_path, {"alpha": parts})
    with zipfile.ZipFile(io.BytesIO(package.build(repo, package.read_list(repo)))) as archive:
        names = set(archive.namelist())
    assert names == {package.MANIFEST, "skills/alpha/SKILL.md", "skills/alpha/agents/openai.yaml",
                     "skills/alpha/scripts/run.py", "skills/alpha/references/method.md",
                     "skills/alpha/assets/table.yaml"}
    assert problems(repo) == []


def test_an_untracked_file_in_a_listed_skill_is_not_packaged(tmp_path):
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    (repo / "skills" / "alpha" / "notes-not-committed.md").write_text("A draft nobody reviewed.\n")
    with zipfile.ZipFile(io.BytesIO(package.build(repo, package.read_list(repo)))) as archive:
        assert "skills/alpha/notes-not-committed.md" not in archive.namelist()


def test_a_symbolic_link_in_a_listed_skill_stops_the_build(tmp_path, capsys):
    """Followed, a link could carry a file from outside its skill, or from the machine that builds."""
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    outside = tmp_path / "outside.md"
    outside.write_text("Not the skill's.\n")
    (repo / "skills" / "alpha" / "references").mkdir()
    (repo / "skills" / "alpha" / "references" / "linked.md").symlink_to(outside)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a link")
    for argv in (("--check",), (tmp_path / "methods.zip",)):
        code, lines = run(capsys, *argv, "--repo-root", repo)
        assert code == 2 and "skills/alpha/references/linked.md is a symbolic link" in lines[0]
    assert not (tmp_path / "methods.zip").exists()


def rewritten(data: bytes, change: dict) -> bytes:
    """The archive with members added or replaced ({name: bytes}) or removed ({name: None})."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files.update(change)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, content in files.items():
            if content is not None:
                archive.writestr(name, content)
    return out.getvalue()


@pytest.mark.parametrize("change, expected", [
    ({"README.md": b"Extra.\n"}, "README.md: not a file of a listed skill"),
    ({"hooks/hooks.json": b"{}\n"}, "hooks/hooks.json: holds or registers a hook"),
    ({"skills/gamma/SKILL.md": b"---\nname: gamma\n---\n"}, "skills/gamma/SKILL.md: not a file of a listed skill"),
    ({"skills/alpha/tests/test_alpha.py": b"x = 1\n"},
     "skills/alpha/tests/test_alpha.py: not a file of a listed skill"),
    ({"skills/alpha/SKILL.md": b"---\nname: alpha\ndepends_on: []\n---\n\nReworded.\n"},
     "skills/alpha/SKILL.md: differs from its source"),
    ({"skills/alpha/agents/openai.yaml": b"\xff\xfe not text"},
     "skills/alpha/agents/openai.yaml: not UTF-8 text, so its lines cannot be read"),
    ({".codex-plugin/plugin.json": None}, ".codex-plugin/plugin.json: version None, not the repository's 5.8.0"),
])
def test_an_archive_that_is_not_the_checkout_is_refused(tmp_path, change, expected):
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    spec = package.read_list(repo)
    found = package.verify(repo, spec, rewritten(package.build(repo, spec), change))
    assert any(problem.startswith(expected) for problem in found), found


# ---- the command line: one line and an exit code -----------------------------------------

def run(capsys, *argv):
    code = package.main([str(arg) for arg in argv])
    return code, capsys.readouterr().out.strip().splitlines()


def test_a_build_writes_the_zip_and_says_what_it_holds(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": skill("alpha", '["beta"]'), "beta": skill("beta")})
    out = tmp_path / "methods.zip"
    code, lines = run(capsys, out, "--repo-root", repo)
    assert (code, lines) == (0, [f"built {out}: 2 skills, 5 files, {out.stat().st_size} bytes, version 5.8.0"])
    with zipfile.ZipFile(out) as archive:
        assert json.loads(archive.read(package.MANIFEST)) == {"name": "methods", "version": "5.8.0",
                                                              "description": "Methods."}
    assert git(repo, "status", "--porcelain") == ""  # nothing is written into the checkout


def test_check_verifies_and_writes_nothing(tmp_path, capsys, monkeypatch):
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    monkeypatch.chdir(tmp_path)  # a file written beside the caller would show below too
    before = sorted(path for path in tmp_path.rglob("*") if ".git" not in path.parts)
    code, lines = run(capsys, "--check", "--repo-root", repo)
    assert code == 0 and len(lines) == 1
    assert re.fullmatch(r"ok: 1 skill, 3 files, \d+ bytes, version 5\.8\.0; nothing written", lines[0])
    assert sorted(path for path in tmp_path.rglob("*") if ".git" not in path.parts) == before


def test_a_defect_refuses_the_build_names_it_and_writes_nothing(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": skill("alpha", body="The Stop hook sends the reply back.\n")})
    out = tmp_path / "methods.zip"
    for argv in ((out, "--repo-root", repo), ("--check", "--repo-root", repo)):
        code, lines = run(capsys, *argv)
        assert code == 1 and lines[0] == "refused: 1 problem; nothing written"
        assert lines[1].startswith("skills/alpha/SKILL.md:6: a hook claim: The Stop hook sends")
    assert not out.exists()


def test_a_package_is_cut_from_committed_files(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    (repo / "skills" / "alpha" / "SKILL.md").write_text(skill("alpha", body="Edited, not committed.\n")["SKILL.md"])
    out = tmp_path / "methods.zip"
    code, lines = run(capsys, out, "--repo-root", repo)
    assert code == 1 and not out.exists()
    assert lines[1] == "skills/alpha/SKILL.md: differs from the last commit; a package is cut from committed files"
    assert run(capsys, "--check", "--repo-root", repo)[0] == 0  # the check reads the files as they are
    git(repo, "commit", "-qam", "edit")
    assert run(capsys, out, "--repo-root", repo)[0] == 0 and out.is_file()


def test_changed_since_names_the_listed_skills_that_changed(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": {**skill("alpha"), "tests/test_alpha.py": "x = 1\n"}, "beta": skill("beta"),
                               "gamma": skill("gamma")}, listed=["alpha", "beta"])
    git(repo, "tag", "v5.8.0")
    assert run(capsys, "--changed-since", "v5.8.0", "--repo-root", repo) == \
        (0, ["unchanged since v5.8.0: no new submission is due"])
    # A test of a listed skill and a skill off the list are not in the package, so they change nothing.
    (repo / "skills" / "alpha" / "tests" / "test_alpha.py").write_text("x = 2\n")
    (repo / "skills" / "gamma" / "SKILL.md").write_text(skill("gamma", body="Changed.\n")["SKILL.md"])
    git(repo, "commit", "-qam", "outside the package")
    assert run(capsys, "--changed-since", "v5.8.0", "--repo-root", repo)[0] == 0
    (repo / "skills" / "beta" / "references").mkdir()
    (repo / "skills" / "beta" / "references" / "new.md").write_text("New.\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "beta gains a reference")
    (repo / "skills" / "alpha" / "SKILL.md").write_text(skill("alpha", body="Not committed yet.\n")["SKILL.md"])
    assert run(capsys, "--changed-since", "v5.8.0", "--repo-root", repo) == \
        (1, ["changed since v5.8.0: alpha, beta; a new submission is due"])


def test_a_file_moved_between_listed_skills_changes_both(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": {**skill("alpha"), "references/shared.md": "A shared method.\n" * 20},
                               "beta": skill("beta")})
    git(repo, "tag", "v5.8.0")
    (repo / "skills" / "beta" / "references").mkdir()
    git(repo, "mv", "skills/alpha/references/shared.md", "skills/beta/references/shared.md")
    git(repo, "commit", "-qm", "moved")
    assert run(capsys, "--changed-since", "v5.8.0", "--repo-root", repo) == \
        (1, ["changed since v5.8.0: alpha, beta; a new submission is due"])


def test_changed_since_counts_a_change_to_the_list_itself(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    git(repo, "tag", "v5.8.0")
    listing = repo / package.LIST
    listing.write_text(json.dumps({**json.loads(listing.read_text()),
                                   "manifest": {"name": "methods", "description": "Reworded."}}))
    assert run(capsys, "--changed-since", "v5.8.0", "--repo-root", repo) == \
        (1, ["changed since v5.8.0: the list; a new submission is due"])


def test_what_cannot_be_read_exits_2_and_says_why(tmp_path, capsys):
    repo = checkout(tmp_path, {"alpha": skill("alpha")})
    code, lines = run(capsys, "--changed-since", "v0.0.0", "--repo-root", repo)
    assert code == 2 and lines[0].startswith("cannot continue: ")
    code, lines = run(capsys, tmp_path / "no-such-folder" / "methods.zip", "--repo-root", repo)
    assert code == 2 and lines[0].startswith("cannot continue: ")  # a ZIP that cannot be written
    (repo / package.LIST).write_text("{")
    for argv in (("--check",), (tmp_path / "methods.zip",), ("--changed-since", "v0.0.0")):
        code, lines = run(capsys, *argv, "--repo-root", repo)
        assert code == 2 and lines[0].startswith("cannot continue: ") and package.LIST in lines[0]
    (repo / package.LIST).write_text(json.dumps({"skills": [], "manifest": {}}))
    assert run(capsys, "--check", "--repo-root", repo)[0] == 2
    assert not (tmp_path / "methods.zip").exists()


@pytest.mark.parametrize("argv", [[], ["out.zip", "--check"], ["--check", "--changed-since", "v5.8.0"]])
def test_exactly_one_thing_is_asked_for(argv, capsys):
    with pytest.raises(SystemExit) as stopped:
        package.main(argv)
    assert stopped.value.code == 2
