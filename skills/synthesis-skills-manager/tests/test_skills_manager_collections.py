"""build_collections.py: the five collections, plugins of the synthesis skills without hooks, each built from the flat
folder into a folder of its own beside the whole set, which the release publishes as the collections branch.

Three groups, as for the directory package. The first reads one real build of this checkout: what each folder holds,
where each byte came from, its three manifests and the two marketplace files. The second gives the checks checkouts
and built folders that must fail. The third is the command line, and the git tree a release commits.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_collections as collections  # noqa: E402

SPEC = json.loads((ROOT / collections.LIST).read_text(encoding="utf-8"))
FIVE = ["core", "project-management", "engineering", "writing", "chief-of-staff"]  # the owner's ruling, 2026-11-14
WHOLE = "https://github.com/synthesisengineering/synthesis-skills"


def categories(skill_md: str) -> list:
    """`metadata.category` as tests/test_source_lint.py reads it: every name its value or values give."""
    match = re.match(r"---\n(.*?)\n---\n", skill_md, re.S)
    meta = re.search(r"^metadata:[ \t]*\n((?:[ \t]+\S.*(?:\n|$))*)", match.group(1) if match else "", re.M)
    return [name.strip().strip("\"'") for value in re.findall(r"^[ \t]+category:(.*)$", meta.group(1) if meta else "", re.M)
            for name in value.strip().strip("[]").split(",") if name.strip()]


def homes() -> dict:
    """{skill: its collection}, read from each SKILL.md and the file's awaiting_room, apart from the build."""
    waiting = SPEC.get("awaiting_room", {})
    found = {p.parent.name: categories(p.read_text(encoding="utf-8")) + ([waiting[p.parent.name]] if p.parent.name in waiting else [])
             for p in ROOT.glob("skills/*/SKILL.md")}
    assert all(len(names) == 1 for names in found.values()), found
    return {name: names[0] for name, names in found.items()}


def is_test(name: str) -> bool:
    return "tests" in name.split("/") or name.rsplit("/", 1)[-1].startswith("test_")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          env=None if repo == ROOT else OWN_GIT).stdout


# A checkout a test makes is written with none of the machine's git settings: its hooks, signing and identity stay out.
OWN_GIT = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t",
           "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


# ---- one real build, read back -----------------------------------------------------

@pytest.fixture(scope="module")
def this_checkout():
    """The collections are cut from the files git tracks, so a test of the real ones needs the checkout itself."""
    top = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode or Path(top.stdout.strip()).resolve() != ROOT.resolve():
        pytest.skip("not a git checkout of this repository: the collections are cut from the files git tracks")
    return ROOT


@pytest.fixture(scope="module")
def built(this_checkout):
    """{path: bytes} of one build of this checkout."""
    return collections.build(ROOT)[0]


def folder(built, collection) -> dict:
    """{path inside the collection's folder: bytes}."""
    return {path[len(collection) + 1:]: data for path, data in built.items() if path.startswith(collection + "/")}


def manifest(built, collection, path) -> dict:
    return json.loads(built[f"{collection}/{path}"])


def test_the_owner_ruled_five_collections_the_fifth_named_chief_of_staff():
    assert list(SPEC["collections"]) == FIVE and SPEC["core"] == "core"
    assert [entry["name"] for entry in SPEC["collections"].values()] == [f"synthesis-skills-{name}" for name in FIVE]


def test_each_folder_holds_its_skills_its_three_manifests_and_the_two_licenses(built):
    home = homes()
    for name in FIVE:
        mine = folder(built, name)
        assert {path.split("/")[1] for path in mine if path.startswith("skills/")} == {
            skill for skill, collection in home.items() if collection == name}, name
        carried = {"synthesis/__init__.py", "synthesis/yamlish.py"} if name in ("core", "project-management", "chief-of-staff") else set()
        assert {path for path in mine if not path.startswith("skills/")} == {*collections.MANIFESTS, *collections.LICENSES,
                                                                              *carried}
    assert {path for path in built if path.split("/")[0] not in FIVE} == set(collections.MARKETPLACES)


def test_every_skill_is_carried_once_whole_but_for_its_tests(built):
    tracked = sorted(name for name in git(ROOT, "ls-files", "-z", "--", "skills").split("\0") if name and not is_test(name))
    carried = sorted(path.split("/", 1)[1] for path in built if path.split("/")[1:2] == ["skills"])
    assert carried == tracked


def test_every_carried_file_is_byte_identical_to_its_source(built):
    carried = {path.split("/", 1)[1]: data for path, data in built.items()
               if path.split("/")[0] in FIVE and path.split("/", 1)[1] not in collections.MANIFESTS}
    assert carried and [path for path, data in carried.items() if (ROOT / path).read_bytes() != data] == []


def test_no_folder_holds_or_registers_a_hook(built):
    assert [path for path in built if "hooks" in path.split("/") or path.endswith("hooks.json")] == []
    for name in FIVE:
        claude, codex, muse = (manifest(built, name, path) for path in collections.MANIFESTS)
        assert "hooks" not in claude and "hooks" not in codex and muse["capabilities"]["hooks"] == []
        assert not any(map(collections.hooked, (claude, codex, muse)))


def test_the_manifests_carry_the_whole_sets_version_and_facts_and_the_collections_own_words(built):
    root = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    versions = {json.loads((ROOT / path).read_text(encoding="utf-8"))["version"] for path in collections.MANIFESTS}
    assert versions == {root["version"]}
    for name, entry in SPEC["collections"].items():
        for path in collections.MANIFESTS:
            made = manifest(built, name, path)
            assert (made["name"], made["version"]) == (entry["name"], root["version"]), (name, path)
            assert made["description"].startswith(entry["description"])
        for path in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            made = manifest(built, name, path)
            assert {key: made[key] for key in collections.SHARED} == {key: root[key] for key in collections.SHARED}
            assert made["skills"] == "./skills/" and made["keywords"] == entry["keywords"]
        interface = manifest(built, name, ".codex-plugin/plugin.json")["interface"]
        assert interface["displayName"] == entry["displayName"] and len(interface["displayName"]) <= 30
        assert interface["shortDescription"] == entry["shortDescription"] and len(entry["shortDescription"]) <= 30
        assert interface["longDescription"] == manifest(built, name, ".codex-plugin/plugin.json")["description"]
        assert "defaultPrompt" not in interface  # the whole set's prompts name skills a collection may not hold
        assert manifest(built, name, ".muse-plugin/plugin.json")["displayName"] == entry["displayName"]


def test_every_collection_but_the_core_declares_the_core_as_its_claude_code_dependency(built):
    for name in FIVE:
        claude = manifest(built, name, ".claude-plugin/plugin.json")
        assert claude.get("dependencies", []) == ([] if name == "core" else ["synthesis-skills-core"]), name
        assert "dependencies" not in manifest(built, name, ".codex-plugin/plugin.json")  # Codex resolves none


def test_the_muse_manifest_lists_exactly_the_folders_skills(built):
    for name in FIVE:
        listed = manifest(built, name, ".muse-plugin/plugin.json")["capabilities"]["skills"]
        mine = sorted({path.split("/")[1] for path in folder(built, name) if path.startswith("skills/")})
        assert listed == [{"id": skill, "path": f"skills/{skill}/SKILL.md"} for skill in mine]


def test_each_description_names_the_whole_set_as_the_way_to_the_guards_board_and_rituals(built):
    """In each manifest, and in the marketplace entry, which is what Claude Code shows of a plugin that is not
    installed yet and in its details (the probe of 2026-11-14)."""
    listed = {entry["name"]: entry["description"] for entry in json.loads(built[".claude-plugin/marketplace.json"])["plugins"]}
    for name in FIVE:
        said = manifest(built, name, ".claude-plugin/plugin.json")["description"]
        assert [word for word in ("guards", "board", "rituals", "synthesis-skills", WHOLE) if word not in said] == []
        assert ("core collection" in said) == (name != "core")  # the other four say they build on it
        assert {manifest(built, name, path)["description"] for path in collections.MANIFESTS} == {said}
        assert listed[SPEC["collections"][name]["name"]] == said


def test_the_two_marketplaces_list_the_five_each_from_its_folder_the_core_first(built):
    want = [(entry["name"], f"./{name}") for name, entry in SPEC["collections"].items()]
    claude = json.loads(built[".claude-plugin/marketplace.json"])
    codex = json.loads(built[".agents/plugins/marketplace.json"])
    assert claude["name"] == codex["name"] == SPEC["marketplace"]["name"] != "synthesis-engineering"  # the whole set's
    assert [(entry["name"], entry["source"]) for entry in claude["plugins"]] == want
    assert [(entry["name"], entry["source"]["path"]) for entry in codex["plugins"]] == want
    assert all(entry["source"]["source"] == "local" and entry["policy"]["installation"] == "AVAILABLE"
               for entry in codex["plugins"])


def test_a_dependency_that_a_skills_scripts_load_is_in_its_own_folder():
    """The sheet's scripts load the packet's engine from beside them, and release.py loads onboarding's setup.py: a
    collection's folder is installed apart from the core's, so each pair shares a collection."""
    home = homes()
    assert home["synthesis-action-sheet"] == home["synthesis-decision-packet"]
    assert home["synthesis-skills-manager"] == home["synthesis-onboarding"]


def test_the_build_reads_categories_as_the_lint_does():
    for skill_md in sorted(ROOT.glob("skills/*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        assert collections.category(text) == categories(text), skill_md.parent.name
    assert collections.category("---\nname: x\nmetadata:\n  category: [a, b]\n---\n") == ["a", "b"]
    assert collections.category("---\nname: x\ncategory: a\nmetadata:\n  format: v5\n---\n") == []  # not in metadata
    assert collections.category("---\nname: x\n---\nmetadata:\n  category: a\n") == []  # not in the frontmatter


def test_the_real_collections_pass_their_own_check(capsys, this_checkout):
    assert collections.main(["--check"]) == 0
    assert capsys.readouterr().out.startswith(f"ok: 5 collections, {len(homes())} skills, ")


# ---- checkouts and built folders that must fail --------------------------------------

FIXTURE = {"core": "core", "branch": "collections",
           "marketplace": {"name": "kit", "displayName": "Kit", "description": "Kits.", "owner": {"name": "Kit"}},
           "with_core": "It builds on the core collection.", "without": "No guards, no board, no rituals.",
           "collections": {"core": {"name": "kit-core", "description": "The core."},
                           "writing": {"name": "kit-writing", "description": "Writing."},
                           "engineering": {"name": "kit-engineering", "description": "Engineering."}}}
WHOLE_MANIFEST = {"name": "kit", "version": "5.8.0", "author": {"name": "A"}, "homepage": "https://example.com",
                  "repository": "https://example.com/kit", "license": "CC0-1.0",
                  "interface": {"displayName": "Kit", "developerName": "A", "category": "Developer Tools",
                                "defaultPrompt": ["Use every skill."]}}


def skill(name, category="core", depends="[]", body="Prose only.\n"):
    line = f"  category: {category}\n" if category else ""
    return {"SKILL.md": f"---\nname: {name}\ndepends_on: {depends}\nmetadata:\n  format: v5\n{line}---\n\n{body}",
            "agents/openai.yaml": "interface:\n  display_name: \"x\"\n"}


SOUND = {"base": skill("base"), "pen": skill("pen", "writing", '["base"]'), "gear": skill("gear", "engineering")}


RUNTIME = {"synthesis/__init__.py": '__version__ = "5.8.0"\n', "synthesis/yamlish.py": "import json\nimport re\n",
           "synthesis/board.py": "from synthesis import paths\n", "synthesis/paths.py": "import os\n"}


def checkout(tmp_path, skills=None, spec=None, runtime=None):
    """A committed checkout holding these skills ({name: {part: text}}), the collections file, the whole set's
    Codex manifest and licenses, and the runtime's package (`RUNTIME`, or these files in its place)."""
    repo = tmp_path / "checkout"
    files = {collections.MANIFEST: json.dumps(WHOLE_MANIFEST), collections.LIST: json.dumps(spec or FIXTURE),
             "LICENSE-APACHE": "Apache terms.\n", "LICENSE-CC0": "CC0 terms.\n", **(RUNTIME if runtime is None else runtime)}
    for name, parts in (SOUND if skills is None else skills).items():
        files.update({f"skills/{name}/{part}": text for part, text in parts.items()})
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    return repo


def problems(repo):
    return collections.verify(repo, collections.build(repo)[0])


def test_a_sound_checkout_builds_with_no_problem_and_each_part_where_it_belongs(tmp_path):
    repo = checkout(tmp_path)
    files, modes = collections.build(repo)
    assert problems(repo) == []
    assert sorted(files) == sorted(
        [f"{name}/{path}" for name in ("core", "writing", "engineering")
         for path in (*collections.MANIFESTS, *collections.LICENSES)]
        + ["core/skills/base/SKILL.md", "core/skills/base/agents/openai.yaml", "writing/skills/pen/SKILL.md",
           "writing/skills/pen/agents/openai.yaml", "engineering/skills/gear/SKILL.md",
           "engineering/skills/gear/agents/openai.yaml", *collections.MARKETPLACES])
    pen = json.loads(files["writing/.claude-plugin/plugin.json"])
    assert pen == {"name": "kit-writing", "version": "5.8.0",
                   "description": "Writing. It builds on the core collection. No guards, no board, no rituals.",
                   "author": {"name": "A"}, "homepage": "https://example.com", "repository": "https://example.com/kit",
                   "license": "CC0-1.0", "keywords": [], "skills": "./skills/", "dependencies": ["kit-core"]}
    assert json.loads(files["core/.claude-plugin/plugin.json"])["description"] == "The core. No guards, no board, no rituals."
    assert json.loads(files["writing/.codex-plugin/plugin.json"])["interface"] == {
        "displayName": "kit-writing", "developerName": "A", "category": "Developer Tools", "shortDescription": "",
        "longDescription": pen["description"]}
    assert [entry["name"] for entry in json.loads(files[".claude-plugin/marketplace.json"])["plugins"]] == [
        "kit-core", "kit-writing", "kit-engineering"]


def test_a_build_from_the_commit_is_the_build_of_a_clean_checkout(tmp_path):
    repo = checkout(tmp_path)
    assert collections.build(repo, commit=True) == collections.build(repo)


@pytest.mark.parametrize("skills, spec, expected", [
    ({**SOUND, "lost": skill("lost", category=None)}, None,
     "skills/lost/SKILL.md: in no collection; a skill is in exactly one that the collections file lists"),
    ({**SOUND, "both": skill("both", "[core, writing]")}, None, "skills/both/SKILL.md: in core and writing; "),
    ({**SOUND, "twice": {**skill("twice"), "SKILL.md": skill("twice")["SKILL.md"].replace(
        "  category: core\n", "  category: core\n  category: writing\n")}}, None, "skills/twice/SKILL.md: in core and writing"),
    ({**SOUND, "odd": skill("odd", "design")}, None, "skills/odd/SKILL.md: in design; "),
    (SOUND, {**FIXTURE, "awaiting_room": {"pen": "writing"}}, "skills/pen/SKILL.md: in writing and writing; "),
    (SOUND, {**FIXTURE, "awaiting_room": {"ghost": "writing"}},
     f"{collections.LIST}: awaiting_room names ghost, which is no skill here"),
    ({**SOUND, "gear": skill("gear", "engineering", '["pen"]')}, None,
     "skills/gear/SKILL.md: depends on pen, which is in writing, not in engineering or the core"),
    ({**SOUND, "gear": skill("gear", "engineering", "\n  - pen")}, None,
     "skills/gear/SKILL.md: depends on pen, which is in writing, not in engineering or the core"),
    ({**SOUND, "core-reach": skill("core-reach", "core", '["pen"]')}, None,
     "skills/core-reach/SKILL.md: depends on pen, which is in writing, not in the core"),
    ({**SOUND, "pen": {**skill("pen", "writing", '["base"]'),
                       "scripts/run.py": "ENGINE = Path(__file__).parents[2] / 'base' / 'scripts'\n"}}, None,
     "skills/pen/SKILL.md: depends on base, which is in core, not beside it where its scripts load it"),
    ({**SOUND, "pen": {**skill("pen", "writing"), "hooks/hooks.json": "{}\n"}}, None,
     "writing/skills/pen/hooks/hooks.json: holds a hook"),
])
def test_a_checkout_that_must_fail_does(tmp_path, skills, spec, expected):
    found = problems(checkout(tmp_path, skills, spec))
    assert any(problem.startswith(expected) for problem in found), found


def test_a_skill_in_awaiting_room_is_built_into_its_collection(tmp_path):
    repo = checkout(tmp_path, {**SOUND, "full": skill("full", category=None)}, {**FIXTURE, "awaiting_room": {"full": "writing"}})
    files, _ = collections.build(repo)
    assert problems(repo) == [] and "writing/skills/full/SKILL.md" in files
    assert {"id": "full", "path": "skills/full/SKILL.md"} in json.loads(
        files["writing/.muse-plugin/plugin.json"])["capabilities"]["skills"]


def test_a_test_a_skill_mentions_its_dependency_in_loads_nothing(tmp_path):
    repo = checkout(tmp_path, {**SOUND, "pen": {**skill("pen", "writing", '["base"]'),
                                                "scripts/test_run.py": "import base\n", "tests/test_pen.py": "import base\n"}})
    assert problems(repo) == []


def rebuilt(files: dict, change: dict) -> dict:
    """The built files with these added or replaced ({path: bytes}) or removed ({path: None})."""
    return {path: data for path, data in {**files, **change}.items() if data is not None}


def edited(files: dict, path: str, edit) -> bytes:
    made = json.loads(files[path])
    edit(made)
    return json.dumps(made).encode()


@pytest.mark.parametrize("change, expected", [
    (lambda f: {"writing/README.md": b"Extra.\n"}, "writing/README.md: not a manifest, a license or a file of a skill in writing"),
    (lambda f: {"writing/skills/base/SKILL.md": f["core/skills/base/SKILL.md"]},
     "writing/skills/base/SKILL.md: not a manifest, a license or a file of a skill in writing"),
    (lambda f: {"writing/skills/pen/tests/test_pen.py": b"x = 1\n"},
     "writing/skills/pen/tests/test_pen.py: not a manifest, a license or a file of a skill in writing"),
    (lambda f: {"writing/skills/pen/SKILL.md": b"Reworded.\n"}, "writing/skills/pen/SKILL.md: differs from its source"),
    (lambda f: {"writing/LICENSE-CC0": b"Other terms.\n"}, "writing/LICENSE-CC0: differs from its source"),
    (lambda f: {"writing/skills/pen/SKILL.md": None}, "writing/skills/pen/SKILL.md: missing"),
    (lambda f: {"writing/LICENSE-APACHE": None}, "writing/LICENSE-APACHE: missing"),
    (lambda f: {"writing/hooks/hooks.json": b"{}\n"}, "writing/hooks/hooks.json: holds a hook"),
    (lambda f: {"writing/.claude-plugin/plugin.json": None}, "writing/.claude-plugin/plugin.json: missing, or not JSON"),
    (lambda f: {"writing/.codex-plugin/plugin.json": b"{"}, "writing/.codex-plugin/plugin.json: missing, or not JSON"),
    (lambda f: {"writing/.claude-plugin/plugin.json": edited(f, "writing/.claude-plugin/plugin.json",
                                                            lambda m: m.update(hooks="./hooks/hooks.json"))},
     "writing/.claude-plugin/plugin.json: registers a hook"),
    (lambda f: {"writing/.codex-plugin/plugin.json": edited(f, "writing/.codex-plugin/plugin.json",
                                                           lambda m: m.update(extensions={"com.openai": {"hooks": {"Stop": []}}}))},
     "writing/.codex-plugin/plugin.json: registers a hook"),
    (lambda f: {"writing/.muse-plugin/plugin.json": edited(f, "writing/.muse-plugin/plugin.json",
                                                          lambda m: m["capabilities"]["hooks"].append({"id": "x"}))},
     "writing/.muse-plugin/plugin.json: registers a hook"),
    (lambda f: {"writing/.codex-plugin/plugin.json": edited(f, "writing/.codex-plugin/plugin.json",
                                                           lambda m: m.update(version="9.9.9"))},
     "writing/.codex-plugin/plugin.json: names kit-writing 9.9.9, not kit-writing 5.8.0"),
    (lambda f: {"writing/.muse-plugin/plugin.json": edited(f, "writing/.muse-plugin/plugin.json",
                                                          lambda m: m.update(name="kit-core"))},
     "writing/.muse-plugin/plugin.json: names kit-core 5.8.0, not kit-writing 5.8.0"),
    (lambda f: {"writing/.claude-plugin/plugin.json": edited(f, "writing/.claude-plugin/plugin.json",
                                                            lambda m: m.pop("dependencies"))},
     "writing/.claude-plugin/plugin.json: depends on [], not on ['kit-core']"),
    (lambda f: {"core/.claude-plugin/plugin.json": edited(f, "core/.claude-plugin/plugin.json",
                                                         lambda m: m.update(dependencies=["kit-writing"]))},
     "core/.claude-plugin/plugin.json: depends on ['kit-writing'], not on []"),
    (lambda f: {"writing/.muse-plugin/plugin.json": edited(f, "writing/.muse-plugin/plugin.json",
                                                          lambda m: m["capabilities"]["skills"].clear())},
     "writing/.muse-plugin/plugin.json: does not list exactly the skills of writing"),
    (lambda f: {"design/.claude-plugin/plugin.json": b"{}\n"}, "design/.claude-plugin/plugin.json: in no collection's folder"),
    (lambda f: {".claude-plugin/marketplace.json": edited(f, ".claude-plugin/marketplace.json",
                                                         lambda m: m["plugins"].pop())},
     ".claude-plugin/marketplace.json: does not list exactly the 3 collections, each from its folder"),
    (lambda f: {".agents/plugins/marketplace.json": edited(f, ".agents/plugins/marketplace.json",
                                                          lambda m: m["plugins"][0]["source"].update(path="./"))},
     ".agents/plugins/marketplace.json: does not list exactly the 3 collections, each from its folder"),
    (lambda f: {".agents/plugins/marketplace.json": None},
     ".agents/plugins/marketplace.json: does not list exactly the 3 collections, each from its folder"),
])
def test_built_folders_that_are_not_the_checkout_are_refused(tmp_path, change, expected):
    repo = checkout(tmp_path)
    files, _ = collections.build(repo)
    found = collections.verify(repo, rebuilt(files, change(files)))
    assert any(problem.startswith(expected) for problem in found), found


def test_a_symbolic_link_in_a_skill_stops_the_build(tmp_path, capsys):
    """Followed, a link could carry a file from outside its skill, or from the machine that builds."""
    repo = checkout(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("Not the skill's.\n")
    (repo / "skills" / "pen" / "linked.md").symlink_to(outside)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "a link")
    code, lines = run(capsys, "--check", "--repo-root", repo)
    assert code == 2 and "skills/pen/linked.md is a symbolic link" in lines[0]


# ---- the command line, and the tree a release commits ----------------------------------

def run(capsys, *argv):
    code = collections.main([str(arg) for arg in argv])
    return code, capsys.readouterr().out.strip().splitlines()


def test_a_build_writes_the_folders_from_the_commit_and_says_what_they_hold(tmp_path, capsys):
    repo = checkout(tmp_path, {**SOUND, "pen": {**skill("pen", "writing", '["base"]'), "scripts/run.sh": "echo pen\n"}})
    (repo / "skills" / "pen" / "scripts" / "run.sh").chmod(0o755)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "executable")
    out = tmp_path / "out"
    code, lines = run(capsys, out, "--repo-root", repo)
    files, _ = collections.build(repo, commit=True)
    assert (code, lines) == (0, [f"built {out}: 3 collections, 3 skills, {len(files)} files, version 5.8.0"])
    assert {path.relative_to(out).as_posix(): path.read_bytes() for path in out.rglob("*") if path.is_file()} == files
    assert os.access(out / "writing" / "skills" / "pen" / "scripts" / "run.sh", os.X_OK)
    assert not os.access(out / "writing" / "skills" / "pen" / "SKILL.md", os.X_OK)
    assert git(repo, "status", "--porcelain") == ""  # nothing is written into the checkout
    assert run(capsys, out, "--repo-root", repo)[0] == 2  # nor over a folder that exists


def test_check_verifies_and_writes_nothing(tmp_path, capsys, monkeypatch):
    repo = checkout(tmp_path)
    monkeypatch.chdir(tmp_path)
    before = sorted(path for path in tmp_path.rglob("*") if ".git" not in path.parts)
    code, lines = run(capsys, "--check", "--repo-root", repo)
    assert code == 0 and re.fullmatch(r"ok: 3 collections, 3 skills, \d+ files, version 5\.8\.0; nothing written", lines[0])
    assert sorted(path for path in tmp_path.rglob("*") if ".git" not in path.parts) == before


def test_a_defect_refuses_the_build_names_it_and_writes_nothing(tmp_path, capsys):
    repo = checkout(tmp_path, {**SOUND, "lost": skill("lost", category=None)})
    out = tmp_path / "out"
    for argv in ((out, "--repo-root", repo), ("--check", "--repo-root", repo)):
        code, lines = run(capsys, *argv)
        assert code == 1 and lines[0] == "refused: 1 problem; nothing written"
        assert lines[1].startswith("skills/lost/SKILL.md: in no collection")
    assert not out.exists()


def test_collections_are_cut_from_committed_files(tmp_path, capsys):
    repo = checkout(tmp_path)
    (repo / "skills" / "pen" / "SKILL.md").write_text(skill("pen", "writing", '["base"]', "Edited.\n")["SKILL.md"])
    out = tmp_path / "out"
    code, lines = run(capsys, out, "--repo-root", repo)
    assert code == 1 and not out.exists()
    assert lines[1] == "skills/pen/SKILL.md: differs from the last commit; collections are cut from committed files"
    assert run(capsys, "--check", "--repo-root", repo)[0] == 0  # the check reads the files as they are
    git(repo, "commit", "-qam", "edit")
    assert run(capsys, out, "--repo-root", repo)[0] == 0
    assert (out / "writing" / "skills" / "pen" / "SKILL.md").read_text().endswith("Edited.\n")


def test_what_cannot_be_read_exits_2_and_says_why(tmp_path, capsys):
    repo = checkout(tmp_path)
    (repo / collections.LIST).write_text("{")
    code, lines = run(capsys, "--check", "--repo-root", repo)
    assert code == 2 and lines[0].startswith("cannot continue: ") and collections.LIST in lines[0]
    (repo / collections.LIST).write_text(json.dumps({**FIXTURE, "core": "design"}))
    assert run(capsys, "--check", "--repo-root", repo)[0] == 2  # the core must be one of the collections
    code, lines = run(capsys, tmp_path / "out", "--repo-root", tmp_path)  # no checkout there
    assert code == 2 and lines[0].startswith("cannot continue: ")


@pytest.mark.parametrize("argv", [[], ["out", "--check"]])
def test_exactly_one_thing_is_asked_for(argv, capsys):
    with pytest.raises(SystemExit) as stopped:
        collections.main(argv)
    assert stopped.value.code == 2


def test_the_tree_a_release_commits_holds_exactly_the_built_files(tmp_path):
    repo = checkout(tmp_path, {**SOUND, "pen": {**skill("pen", "writing"), "scripts/run.sh": "echo pen\n"}})
    (repo / "skills" / "pen" / "scripts" / "run.sh").chmod(0o755)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "executable")
    files, modes = collections.build(repo, commit=True)
    tree = collections.tree(repo, files, modes)
    listed = {line.split("\t")[1]: line.split()[0] for line in git(repo, "ls-tree", "-r", tree).splitlines()}
    assert set(listed) == set(files)
    assert {path for path, mode in listed.items() if mode == "100755"} == {"writing/skills/pen/scripts/run.sh"}
    assert all(git(repo, "show", f"{tree}:{path}") == data.decode() for path, data in files.items())
    assert collections.tree(repo, files, modes) == tree  # the same files give the same tree
    assert git(repo, "status", "--porcelain") == ""  # the checkout's own index is untouched


def test_the_readme_lists_each_collection_with_its_plugin_its_skills_and_its_install_lines():
    """The table is what someone choosing a collection reads, so it is held to the data: a skill that changes collection
    changes the table in the same pull request. The install lines name the branch and the marketplace the data names."""
    section = (ROOT / "README.md").read_text(encoding="utf-8").split("### One collection, without the hooks", 1)[1]
    section = section.split("\n### ", 1)[0]
    rows = {found.group(1): found.group(2).split(", ")
            for found in re.finditer(r"^\| [^|]+ \| `([\w-]+)` \| ([^|]+?) \|$", section, re.M)}
    home = homes()
    assert rows == {entry["name"]: sorted(skill[len("synthesis-"):] for skill, collection in home.items()
                                          if collection == name) for name, entry in SPEC["collections"].items()}
    market, branch = SPEC["marketplace"]["name"], SPEC["branch"]
    for line in (f"claude plugin marketplace add synthesisengineering/synthesis-skills@{branch}",
                 f"codex plugin marketplace add synthesisengineering/synthesis-skills --ref {branch}",
                 f"muse plugins marketplace add {market} {WHOLE}.git#{branch}",
                 f"claude plugin install synthesis-skills-engineering@{market}",
                 f"codex plugin add synthesis-skills-core@{market}", f"muse plugins install synthesis-skills-core@{market}"):
        assert line in section, line


# ---- a collection's scripts run where it is installed (R1-3 of 5.22.0's review) -----------------

# R1-3: 34 collected scripts imported a runtime no collection carried, so each exited 2 in every collection install,
# kb-edit's configuration gate among them. 23 of them need only the runtime's YAML reader, which reads with the standard
# library alone and keeps no state; a collection whose scripts read it carries it, at the same place as in the whole set.
# A script that needs more (the board, approvals, the rituals' records, installing synthesis) is named in the
# collections file, and says so in one line.
RUNTIME_MISSING = re.compile(r"synthesis runtime(?:, which)? cannot be imported")


@pytest.fixture(scope="module")
def written(tmp_path_factory, this_checkout):
    """One build of this checkout written to disk as a harness installs each collection: a folder apiece."""
    folder = tmp_path_factory.mktemp("collections")
    files, modes = collections.build(ROOT)
    for path, data in files.items():
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_bytes(data)
        (folder / path).chmod(0o755 if modes.get(path) == "100755" else 0o644)
    return folder


def alone(tmp_path) -> dict:
    """The environment of a Mac with no synthesis runtime installed."""
    return {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "SYNTHESIS_HOME": str(tmp_path / "no-runtime")}


def test_every_collected_script_runs_from_its_folder_or_says_in_a_line_that_it_needs_the_whole_set(written, tmp_path):
    """Each entry point (a file with a `__main__` guard) is run as a person runs it, with --help, from the folder the
    build wrote. It runs, or it is one the collections file names as needing the whole set and says so in one line;
    none ends in a traceback. A script that refuses for its own reasons (a config to fill in, an installer of its own)
    passes: it ran."""
    declared, wrong, seen = set(SPEC.get("needs_the_whole_set", {})), [], set()
    for script in sorted(written.glob("*/skills/*/**/*.py")):
        source = script.relative_to(written).as_posix().split("/", 1)[1]
        if is_test(source) or "__main__" not in script.read_text(encoding="utf-8"):
            continue
        done = subprocess.run([sys.executable, "-E", "-s", str(script), "--help"], capture_output=True, text=True,
                              env=alone(tmp_path), cwd=tmp_path, stdin=subprocess.DEVNULL, timeout=120)
        said = (done.stdout + done.stderr).strip()
        needs = bool(RUNTIME_MISSING.search(said))
        if "Traceback" in done.stderr or needs != (source in declared) or needs and (
                done.returncode == 0 or len(said.splitlines()) != 1):
            wrong.append(f"{script.relative_to(written)}: exit {done.returncode}: {said.splitlines()[-1:]}")
        seen.add(script.relative_to(written).parts[0])
    assert wrong == [] and seen == set(FIVE)


def test_the_core_s_knowledge_base_gate_runs_from_the_core_s_folder(written, tmp_path):
    """kb-edit's rule 5: a protective control that cannot run blocks shipping. Its gate exited 2 in the core, so every
    knowledge-base edit in a collection install stopped there."""
    kb = tmp_path / "kb"
    (kb / ".agents").mkdir(parents=True)
    (kb / "source").mkdir()
    shutil.copy(ROOT / "skills/synthesis-onboarding/assets/workspace/agents/knowledge-base.yaml", kb / ".agents")
    git(kb, "init", "-q")
    done = subprocess.run([sys.executable, "-E", "-s", str(written / "core/skills/synthesis-kb-edit/scripts/kb_config.py"),
                           str(kb)], capture_output=True, text=True, env=alone(tmp_path), cwd=tmp_path)
    assert done.returncode == 0 and done.stdout.startswith("VALID"), (done.stdout + done.stderr)[-400:]


def test_a_collection_carries_the_runtime_s_yaml_reader_only_where_its_scripts_read_it(written):
    for name in FIVE:
        held = sorted(path.name for path in (written / name / "synthesis").glob("*"))
        reads = any("yamlish" in path.read_text(encoding="utf-8")
                    for path in (written / name / "skills").rglob("*.py") if not is_test(path.as_posix()))
        assert held == (["__init__.py", "yamlish.py"] if reads else []), name
        assert all((written / name / "synthesis" / file).read_bytes() == (ROOT / "synthesis" / file).read_bytes()
                   for file in held)


GUARDED = ("import sys\nsys.dont_write_bytecode = True\ntry:\n    from synthesis import {module}\nexcept ImportError as exc:\n"
           "    print(f'needs the synthesis runtime, which cannot be imported ({{exc}})', file=sys.stderr)\n"
           "    sys.exit(2)\nif __name__ == '__main__':\n    pass\n")


def scripted(**files) -> dict:
    """SOUND with these files in pen (writing): {name under scripts/: text}."""
    return {**SOUND, "pen": {**skill("pen", "writing", '["base"]'), **{f"scripts/{name}": text for name, text in files.items()}}}


def test_the_yaml_reader_is_carried_byte_for_byte_into_the_collection_whose_script_reads_it(tmp_path):
    repo = checkout(tmp_path, scripted(**{"run.py": GUARDED.format(module="yamlish")}))
    files, _ = collections.build(repo)
    assert problems(repo) == []
    assert {path for path in files if "/synthesis/" in path} == {"writing/synthesis/__init__.py", "writing/synthesis/yamlish.py"}
    assert files["writing/synthesis/yamlish.py"] == (repo / "synthesis" / "yamlish.py").read_bytes()


@pytest.mark.parametrize("files, extra, expected", [
    ({"run.py": GUARDED.format(module="board")}, {},
     "writing/skills/pen/scripts/run.py: imports synthesis.board as it starts, which writing does not carry, so it "
     "cannot run there"),
    ({"run.py": "import helper\nif __name__ == '__main__':\n    pass\n", "helper.py": GUARDED.format(module="board")}, {},
     "writing/skills/pen/scripts/run.py: imports synthesis.board as it starts"),  # through a module beside it
    ({"run.py": "def main():\n    from synthesis import board\n    return board\n"}, {},
     "writing/skills/pen/scripts/run.py: imports synthesis.board inside a function, with nothing to catch its absence"),
    ({"run.py": GUARDED.format(module="yamlish")}, {"needs_the_whole_set": {"skills/pen/scripts/run.py": "the board"}},
     f"{collections.LIST}: needs_the_whole_set names skills/pen/scripts/run.py, which runs in its collection now"),
    ({"run.py": GUARDED.format(module="yamlish")}, {"needs_the_whole_set": {"skills/pen/scripts/gone.py": "the board"}},
     f"{collections.LIST}: needs_the_whole_set names skills/pen/scripts/gone.py, which is no script of any collection"),
])
def test_a_script_that_cannot_run_in_its_collection_fails_the_build(tmp_path, files, extra, expected):
    found = problems(checkout(tmp_path, scripted(**files), {**FIXTURE, **extra}))
    assert any(problem.startswith(expected) for problem in found), found


@pytest.mark.parametrize("files", [
    {"run.py": GUARDED.format(module="board")},  # named as needing the whole set: it says so in one line
    {"run.py": "def main():\n    try:\n        from synthesis import board\n    except ImportError:\n        return None\n"},
    {"run.py": "def main(root):\n    if (root / 'synthesis' / 'board.py').is_file():\n        from synthesis import board\n"},
])
def test_a_script_named_as_needing_the_whole_set_or_one_that_catches_the_absence_passes(tmp_path, files):
    declared = {"needs_the_whole_set": {"skills/pen/scripts/run.py": "the board"}} if "sys.exit" in files["run.py"] else {}
    repo = checkout(tmp_path, scripted(**files), {**FIXTURE, **declared})
    files_built, _ = collections.build(repo)
    assert problems(repo) == [] and not any("/synthesis/" in path for path in files_built)


def test_a_yaml_reader_that_imports_the_rest_of_the_runtime_is_carried_by_no_collection(tmp_path):
    repo = checkout(tmp_path, scripted(**{"run.py": GUARDED.format(module="yamlish")}),
                    runtime={**RUNTIME, "synthesis/yamlish.py": "from synthesis import paths\n"})
    assert "synthesis/yamlish.py imports synthesis.paths, so no collection can carry it alone" in problems(repo)


@pytest.mark.parametrize("change, expected", [
    (lambda f: {"writing/synthesis/yamlish.py": None}, "writing/synthesis/yamlish.py: missing"),
    (lambda f: {"writing/synthesis/yamlish.py": b"import os\n"}, "writing/synthesis/yamlish.py: differs from its source"),
    (lambda f: {"core/synthesis/board.py": b"from synthesis import paths\n"},
     "core/synthesis/board.py: a runtime module core does not carry"),
])
def test_carried_runtime_files_that_are_not_the_checkout_are_refused(tmp_path, change, expected):
    repo = checkout(tmp_path, scripted(**{"run.py": GUARDED.format(module="yamlish")}))
    files, _ = collections.build(repo)
    found = collections.verify(repo, rebuilt(files, change(files)))
    assert any(problem.startswith(expected) for problem in found), found



# ---- a path into another skill's folder (R1-20 of 5.22.0's review) -------------------------------

# The build's rule 3 saw only declared dependencies: two scripts reached into another collection's skill by a path,
# undeclared. Every string of a collected script's code that names another skill's folder is now read, and the skill
# must be beside it, or the script must need the whole set, or the collections file must name the load as optional,
# with what the script does without it.
REACH = "import pathlib\nHELPER = pathlib.Path(__file__).resolve().parents[2] / 'toolbox' / 'scripts' / 'tool.py'\n"


def reaching(script=REACH, **extra):
    return ({**SOUND, "toolbox": skill("toolbox", "engineering"),
             "pen": {**skill("pen", "writing", '["base"]'), "scripts/run.py": script}}, {**FIXTURE, **extra})


def test_a_script_that_reaches_another_collection_s_skill_by_a_path_fails_the_build(tmp_path):
    found = problems(checkout(tmp_path, *reaching()))
    assert any(problem.startswith("writing/skills/pen/scripts/run.py: reaches toolbox's folder, which is in engineering, "
                                  "not beside it in writing") for problem in found), found


@pytest.mark.parametrize("script, extra", [
    (REACH, {"optional_loads": {"skills/pen/scripts/run.py": {"toolbox": "it says the tool is not there"}}}),
    (GUARDED.format(module="board") + REACH, {"needs_the_whole_set": {"skills/pen/scripts/run.py": "the board"}}),
    ('"""It loads ../../toolbox/scripts/tool.py by path, in another skill."""\nimport sys\n', {}),  # a docstring loads nothing
])
def test_a_reach_named_as_optional_or_from_a_script_that_needs_the_whole_set_passes(tmp_path, script, extra):
    found = problems(checkout(tmp_path, *reaching(script, **extra)))
    assert [problem for problem in found if "reaches" in problem or "optional_loads" in problem] == [], found


def test_an_optional_load_the_script_does_not_take_fails_the_build(tmp_path):
    found = problems(checkout(tmp_path, *reaching("import sys\n", optional_loads={
        "skills/pen/scripts/run.py": {"toolbox": "it says the tool is not there"}})))
    assert f"{collections.LIST}: optional_loads names toolbox for skills/pen/scripts/run.py, which does not reach it" in found


def test_the_two_paths_the_review_found_across_collections_are_each_accounted_for(written):
    """The rituals' pull-request scan reaches the Bitbucket skill's helper (engineering) from chief of staff, and says a
    Bitbucket repository is unscanned without it; onboarding's setup reaches the rituals' launch file from the core,
    and needs the whole set in any case."""
    assert SPEC["optional_loads"] == {"skills/synthesis-daily-rituals/scripts/pr_queue_scan.py": {
        "synthesis-bitbucket": SPEC["optional_loads"]["skills/synthesis-daily-rituals/scripts/pr_queue_scan.py"]["synthesis-bitbucket"]}}
    assert "skills/synthesis-onboarding/scripts/setup.py" in SPEC["needs_the_whole_set"]
    found = collections.verify(ROOT, {path.relative_to(written).as_posix(): path.read_bytes()
                                      for path in written.rglob("*") if path.is_file()})
    assert [problem for problem in found if "reaches" in problem] == []
