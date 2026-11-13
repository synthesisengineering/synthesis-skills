"""Source lint (R7.3, R7.4, R4.3): what must hold in the repository before anything ships.

The plugin manifests agree; the CHANGELOG names the version; skill names are unique and match
their folders; every `depends_on` resolves; every skill carries an SPDX license and
`agents/openai.yaml`; Muse's manifest lists every skill; Codex's skill catalog fits its
budget; no personal path appears anywhere; nothing needs PyYAML (one standard-library YAML
reader serves everything); and every config a skill documents as fail-closed ships an
example, because a guard that refuses to run without config blocks a new user.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from synthesis import doctor

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(ROOT.glob("skills/*/SKILL.md"))
LICENSES = {"Apache-2.0", "CC0-1.0"}  # the repository ships LICENSE-APACHE and LICENSE-CC0
MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json")


def frontmatter(skill_md: Path) -> dict:
    """name, description, license and depends_on, from flow (`[a, b]`) or block (`- a`) lists."""
    match = re.match(r"---\n(.*?)\n---\n", skill_md.read_text(encoding="utf-8"), re.S)
    text, found = (match.group(1) if match else ""), {}
    for key in ("name", "description", "license"):
        value = re.search(rf"^{key}:\s*(.*)$", text, re.M)
        found[key] = value.group(1).strip().strip("\"'") if value else ""
    deps = re.search(r"^depends_on:\s*(\[.*?\])?\s*$((?:\n\s+- .*)*)", text, re.M)
    if deps and deps.group(1):
        found["depends_on"] = [d.strip().strip("\"'") for d in deps.group(1)[1:-1].split(",") if d.strip()]
    else:
        found["depends_on"] = re.findall(r"^\s+- \"?([\w.-]+)\"?\s*$", deps.group(2), re.M) if deps else []
    return found


FRONT = {p.parent.name: frontmatter(p) for p in SKILLS}


def manifest_version() -> str:
    versions = {name: json.loads((ROOT / name).read_text(encoding="utf-8")).get("version") for name in MANIFESTS}
    assert len(set(versions.values())) == 1, versions
    return next(iter(versions.values()))


def test_plugin_manifests_agree_on_one_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest_version())


def test_changelog_newest_entry_is_the_manifest_version():
    newest = re.search(r"^## \[?(\d+\.\d+\.\d+)\]?", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert newest and newest.group(1) == manifest_version(), (
        f"CHANGELOG's newest entry is {newest.group(1) if newest else 'missing'}; add one for {manifest_version()}")


def test_the_runtime_carries_the_manifest_version():
    """From 5.0.16 to 5.1.17 the runtime still said 5.0.15: running sessions were never told what a release
    changed, and a session start never moved the runtime forward, since both compare this number."""
    from synthesis import __version__
    assert __version__ == manifest_version(), f"synthesis/__init__.py says {__version__}; set {manifest_version()}"


def test_skill_names_are_unique_and_match_their_folders():
    assert {folder: f["name"] for folder, f in FRONT.items() if f["name"] != folder} == {}
    names = [f["name"] for f in FRONT.values()]
    assert len(names) == len(set(names))


def test_every_dependency_resolves_to_a_skill_here():
    dangling = {folder: [d for d in f["depends_on"] if d not in FRONT] for folder, f in FRONT.items()}
    assert {k: v for k, v in dangling.items() if v} == {}


def test_every_skill_has_an_spdx_license_and_codex_metadata():
    assert {folder: f["license"] for folder, f in FRONT.items() if f["license"] not in LICENSES} == {}
    assert [s.parent.name for s in SKILLS if not (s.parent / "agents" / "openai.yaml").is_file()] == []


def test_muse_manifest_lists_every_skill():
    muse = json.loads((ROOT / ".muse-plugin" / "plugin.json").read_text(encoding="utf-8"))
    listed = {s["path"] for s in muse["capabilities"]["skills"]}
    assert listed == {f"skills/{s.parent.name}/SKILL.md" for s in SKILLS}


def test_codex_catalog_fits_even_its_fallback_budget():
    """Every skill under its synthesis-skills: name; the cost against Codex's 8,000-character
    fallback, the smallest budget it can apply when the model's window is unknown."""
    skills = [{"name": f"synthesis-skills:{folder}", "description": f["description"],
               "path": str(ROOT / "skills" / folder / "SKILL.md")} for folder, f in FRONT.items()]
    assert all(re.fullmatch(r"synthesis-skills:[a-z0-9-]+", s["name"]) for s in skills)
    cost, budget = doctor.catalog_cost(skills, None)
    assert cost <= budget, f"Codex catalog {cost} tokens over its {budget}-token fallback budget"


# ---- no personal paths -----------------------------------------------------------

# Placeholders and generic sample names; anything else after workspaces/ or a home folder reads as a real one.
PLACEHOLDER = (r"(?![<*$({]|[a-z]/|[A-Z][A-Z_-]*/|example|demo/|personal/|work/|user/|you/|me/|acme/|someone/"
               r"|site/|project/|repo/|team/|org/|client/|foo/|bar/|my[\w-]*/")
HOME_PATH = re.compile("/(?:Us" + r"ers|home)/" + PLACEHOLDER + r"|name/|alice/|bob/|person/|operator/|other/|runner/|test/)[\w.-]+/")
WORKSPACE_PATH = re.compile(r"workspaces/" + PLACEHOLDER + r")[\w.-]+/")


def personal_paths(files) -> dict:
    hits = {}
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = {m.group(0) for pattern in (HOME_PATH, WORKSPACE_PATH) for m in pattern.finditer(text)}
        if found:
            hits[str(path.relative_to(ROOT))] = sorted(found)
    return hits


def test_no_personal_paths_anywhere_in_the_repository():
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard"],
                            capture_output=True, text=True)
    files = [ROOT / f for f in listed.stdout.splitlines()] if listed.returncode == 0 else list(ROOT.rglob("*"))
    files = [f for f in files if f.is_file() and f.name != Path(__file__).name and ".git" not in f.parts]
    assert personal_paths(files) == {}


def test_the_personal_path_rule_catches_real_paths_and_spares_placeholders(tmp_path):
    sample = tmp_path / "x.md"
    sample.write_text("see /Us" + "ers/jdoe/workspaces/acme-corp/repo and ~/workspaces/jdoe/notes\n")
    ok = tmp_path / "ok.md"
    ok.write_text("~/workspaces/<workspace>/ai-knowledge-<workspace>/ and /Us" + "ers/<name>/x and $HOME/workspaces/*/\n")
    global ROOT
    old, ROOT = ROOT, tmp_path
    try:
        assert personal_paths([sample]) == {"x.md": ["/Us" + "ers/jdoe/", "workspaces/acme-corp/", "workspaces/jdoe/"]}
        assert personal_paths([ok]) == {}
    finally:
        ROOT = old


# ---- one YAML reader -------------------------------------------------------------

PYYAML = re.compile(r"^\s*(?:import\s+yaml\b|from\s+yaml\s+import\b)|importorskip\(\s*['\"]yaml['\"]|-c\s+['\"]import\s+yaml\b",
                    re.M)
OPTIONAL_PYYAML = {"tests/test_yamlish.py"}  # compares its readings with PyYAML's only where PyYAML is installed


def pyyaml_users(root: Path) -> list:
    """Code that needs PyYAML. Apple's /usr/bin/python3 has none and CI installs none, and a test
    that skips without it leaves its script untested: every YAML read goes through synthesis/yamlish.py."""
    files = [p for d in ("synthesis", "hooks", "skills", "tests") for p in (root / d).rglob("*")
             if p.suffix in (".py", ".sh") and "__pycache__" not in p.parts and p.name != Path(__file__).name]
    return sorted(p.relative_to(root).as_posix() for p in files if p.relative_to(root).as_posix() not in OPTIONAL_PYYAML
                  and PYYAML.search(p.read_text(encoding="utf-8", errors="replace")))


def test_nothing_needs_pyyaml():
    assert pyyaml_users(ROOT) == []


def test_the_yaml_rule_finds_pyyaml_and_spares_the_plugin_reader(tmp_path):
    files = {"skills/a/scripts/x.py": "try:\n    import yaml\nexcept ImportError:\n    pass\n",
             "skills/b/tests/test_b.py": 'yaml = pytest.importorskip("yaml")\n',
             "skills/c/scripts/install.sh": "python3 -c 'import yaml' || echo missing\n",
             "synthesis/y.py": "from yaml import safe_load\n",
             "skills/d/scripts/ok.py": "from synthesis import yamlish\nCONFIG = 'rules.yaml'  # import yaml files\n",
             "tests/test_yamlish.py": "    import yaml\n"}
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    assert pyyaml_users(tmp_path) == ["skills/a/scripts/x.py", "skills/b/tests/test_b.py",
                                      "skills/c/scripts/install.sh", "synthesis/y.py"]


# ---- fail-closed configs ship an example ------------------------------------------

HARD_STOP = re.compile(r"config[^\n]{0,120}missing[^\n]{0,120}STOP|engine refuses to run without it", re.I)
USER_CONFIG = re.compile(r"~/\.synthesis/[\w./-]+\.(?:json|ya?ml|toml)")


def missing_examples(skill_dirs) -> list:
    missing = []
    for skill in skill_dirs:
        text = "\n".join(p.read_text(encoding="utf-8") for p in skill.rglob("*.md"))
        if HARD_STOP.search(text) and USER_CONFIG.search(text):
            examples = [p for p in skill.rglob("*") if "example" in p.name.lower()
                        and p.suffix in (".json", ".yaml", ".yml", ".toml")]
            if not examples:
                missing.append(skill.name)
    return missing


def test_every_fail_closed_config_has_a_shipped_example():
    assert missing_examples([s.parent for s in SKILLS]) == []


def test_the_example_rule_finds_a_hard_stop_without_an_example(tmp_path):
    skill = tmp_path / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text("Read ~/.synthesis/demo/config.json. If the config is missing, STOP.\n")
    assert missing_examples([skill]) == ["demo"]
    (skill / "config.example.json").write_text("{}\n")
    assert missing_examples([skill]) == []


# ---- every skill test is collected by `pytest tests/ skills/` ------------------------

def uncollected_tests(root: Path) -> list:
    """test_*.py under skills/ that `python -m pytest -q tests/ skills/` would not run: inside a
    folder pytest does not enter, excluded by pytest.ini, or sharing a file name with another test
    module outside a package (the default import mode can import only one of them)."""
    from fnmatch import fnmatch
    ini = (root / "pytest.ini").read_text(encoding="utf-8") if (root / "pytest.ini").is_file() else ""
    setting = lambda key: (re.search(rf"^{key}\s*=\s*(.+)$", ini, re.M) or [None, ""])[1].split()  # noqa: E731
    norecurse = setting("norecursedirs") or ["*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules",
                                             "venv", "{arch}"]
    patterns = setting("python_files") or ["test_*.py", "*_test.py"]
    ignored = [a.split("=", 1)[1] for a in setting("addopts") if a.startswith("--ignore=")]
    tests = sorted(p for p in (root / "skills").rglob("test_*.py") if "__pycache__" not in p.parts)
    problems, modules = [], {}
    for path in tests:
        rel = path.relative_to(root).as_posix()
        hidden = [d for d in path.relative_to(root).parts[:-1] if any(fnmatch(d, n) for n in norecurse)]
        if hidden:
            problems.append(f"{rel}: inside {hidden[0]}/, which pytest does not enter")
        elif not any(fnmatch(path.name, n) for n in patterns) or any(rel.startswith(i) for i in ignored):
            problems.append(f"{rel}: excluded by pytest.ini")
    for path in tests + sorted((root / "tests").rglob("test_*.py")):
        if not (path.parent / "__init__.py").exists():
            modules.setdefault(path.name, []).append(path.relative_to(root).as_posix())
    problems += [f"{', '.join(paths)}: same module name {name}; rename all but one"
                 for name, paths in sorted(modules.items()) if len(paths) > 1]
    return problems


def test_every_skill_test_is_collected_by_the_ci_command():
    assert uncollected_tests(ROOT) == []


def test_the_collection_rule_finds_hidden_folders_and_shared_names(tmp_path):
    for rel in ("skills/a/scripts/test_x.py", "skills/b/.cache/test_y.py", "skills/c/tests/test_x.py",
                "skills/d/pkg/__init__.py", "skills/d/pkg/test_x.py", "tests/test_z.py", "skills/e/test_z.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")
    assert uncollected_tests(tmp_path) == [
        "skills/b/.cache/test_y.py: inside .cache/, which pytest does not enter",
        "skills/a/scripts/test_x.py, skills/c/tests/test_x.py: same module name test_x.py; rename all but one",
        "skills/e/test_z.py, tests/test_z.py: same module name test_z.py; rename all but one"]


def bytecode_writers(root: Path) -> list:
    """Scripts that import one of their own modules (a sibling, or the plugin's synthesis package) before
    turning bytecode off. Run from an installed plugin, that import writes __pycache__ into it, and Muse,
    which verifies its bundle against its lock record, then refuses the whole plugin (4.102.1)."""
    import ast
    found = []
    for path in sorted(root.glob("skills/*/**/*.py")):  # every folder: a skill-root or helper-folder script ships too
        if path.name.startswith("test_") or "tests" in path.relative_to(root).parts:
            continue
        local = {p.stem for p in path.parent.glob("*.py")} | {"synthesis", "setup"}
        for statement in ast.parse(path.read_text(encoding="utf-8")).body:
            text = ast.unparse(statement)
            if "sys.dont_write_bytecode = True" in text:
                break
            if any(isinstance(n, ast.Import) and any(a.name.split(".")[0] in local for a in n.names)
                   or isinstance(n, ast.ImportFrom) and not n.level and (n.module or "").split(".")[0] in local
                   for n in ast.walk(statement)):
                found.append(f"{path.relative_to(root)}:{statement.lineno}")
                break
    return found


def test_no_script_writes_bytecode_into_an_installed_plugin():
    assert bytecode_writers(ROOT) == []


def test_the_bytecode_rule_finds_a_late_guard_and_spares_an_early_one(tmp_path):
    folder = tmp_path / "skills" / "a" / "scripts"
    folder.mkdir(parents=True)
    (folder / "helper.py").write_text("X = 1\n")
    (folder / "early.py").write_text("import sys\nsys.dont_write_bytecode = True\nimport helper\n")
    (folder / "late.py").write_text("import sys\nimport helper\nif __name__ == '__main__':\n    sys.dont_write_bytecode = True\n")
    (folder / "lazy.py").write_text("def f():\n    from synthesis import board\n")
    # Until 2026-10-07 only scripts/ was checked, and three scripts in other folders imported before the guard.
    helper = tmp_path / "skills" / "b" / "optional-helper"
    helper.mkdir(parents=True)
    (helper / "client.py").write_text("X = 1\n")
    (helper / "fetch.py").write_text("import sys\nimport client\n")
    (tmp_path / "skills" / "b" / "tests").mkdir()
    (tmp_path / "skills" / "b" / "tests" / "conftest.py").write_text("from synthesis import board\n")
    assert bytecode_writers(tmp_path) == ["skills/a/scripts/late.py:2", "skills/a/scripts/lazy.py:1",
                                          "skills/b/optional-helper/fetch.py:2"]


# ---- CI runs the local command's two folders, each in a job of its own ---------------

def unrun_core_tests(root: Path, halves: list) -> list:
    """Test files under tests/ that the halves' patterns do not run exactly once. pytest collects `test_*.py` and
    `*_test.py` and enters folders; a job's shell pattern takes one kind of name in one folder."""
    from fnmatch import fnmatch
    found = []
    for path in sorted((root / "tests").rglob("*.py")):
        if not (fnmatch(path.name, "test_*.py") or fnmatch(path.name, "*_test.py")):
            continue
        name = path.relative_to(root).as_posix()
        runs = [half for half in halves if path.parent == root / "tests" and fnmatch(name, half)]
        if len(runs) != 1:
            found.append(f"{name}: run by {len(runs)} of the jobs")
    return found


def test_ci_runs_the_local_command_in_three_jobs_that_together_miss_nothing():
    """The suite is run in three jobs for each system and Python: the core's tests in two halves by file name, and
    the skills'. On 2026-11-12 the whole suite took 526 seconds on a macOS runner and one job was cancelled at the
    ten-minute limit with no test failing; run as two jobs, the core's tests took 6 minutes on one macOS runner and
    over 10 on a slower one beside it. Together the three run what `python3 -m pytest -q tests/ skills/` runs."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    parts = re.findall(r'"([^"]+)"', re.search(r"^\s+part: \[(.+)\]$", workflow, re.M).group(1))
    assert "skills/" in parts and len(parts) == 3
    assert "run: python -m pytest -q ${{ matrix.part }}\n" in workflow
    assert "run: python -m pytest -q tests/ skills/" not in workflow  # no job runs the whole of it
    halves = [part for part in parts if part != "skills/"]
    assert list((ROOT / "tests").glob("test_*.py")) and unrun_core_tests(ROOT, halves) == []
    apple = re.findall(r'- os: macos-latest\n\s+python: apple\n\s+part: "([^"]+)"', workflow)
    assert sorted(apple) == sorted(parts)  # an entry added to a matrix by hand names every part


def test_the_split_rule_finds_a_file_no_job_runs_and_one_that_two_run(tmp_path):
    """pytest collects `*_test.py` as well as `test_*.py`, and enters folders; a job's shell pattern does neither.
    A file of either kind ran when the suite was run whole and in no job of CI (a review of 5.8.1)."""
    for rel in ("tests/test_alpha.py", "tests/test_zeta.py", "tests/alpha_test.py", "tests/sub/test_beta.py",
                "tests/sub/gamma_test.py", "tests/helper.py", "tests/conftest.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("")
    halves = ["tests/test_[a-g]*.py", "tests/test_[h-z]*.py"]
    unrun = ["tests/alpha_test.py: run by 0 of the jobs", "tests/sub/gamma_test.py: run by 0 of the jobs",
             "tests/sub/test_beta.py: run by 0 of the jobs"]
    assert unrun_core_tests(tmp_path, halves) == unrun
    assert unrun_core_tests(tmp_path, halves + ["tests/test_a*.py"]) == unrun + ["tests/test_alpha.py: run by 2 of the jobs"]


# ---- No call passes a limit or flags to re by position -----------------------------

def positional_re_limits(root: Path) -> list:
    """Calls such as `re.split(pattern, text, 1)`. Python 3.13 deprecates passing `maxsplit`, `count` or `flags` to
    `re.split`, `re.sub` and `re.subn` by position, and a later Python will refuse it. On 2026-11-12 the core held
    three such calls: silent under 3.12, where the suite is run by hand, and a warning at every use under 3.13.
    This reads the source, so it holds under every Python. It reads the repository's own code: the files at its
    root and under the four folders that hold code, not a virtual environment or a build folder beside them."""
    import ast
    most = {"split": 2, "sub": 3, "subn": 3}
    found = []
    own = [*root.glob("*.py"), *(path for folder in ("synthesis", "hooks", "skills", "tests")
                                 for path in (root / folder).rglob("*.py"))]
    for path in sorted(own):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re" and len(node.args) > most.get(node.func.attr, len(node.args))):
                found.append(f"{path.relative_to(root).as_posix()}:{node.lineno}")
    return found


def test_no_call_passes_a_limit_or_flags_to_re_by_position():
    assert positional_re_limits(ROOT) == []


def test_the_re_rule_finds_a_positional_limit_and_spares_a_named_one(tmp_path):
    (tmp_path / "skills" / "a").mkdir(parents=True)
    (tmp_path / "skills" / "a" / "x.py").write_text(
        "import re\n"
        "re.split(r',', text, 1)\n"              # maxsplit by position
        "re.split(r',', text, maxsplit=1)\n"
        "re.sub(r'a', 'b', text, 1)\n"           # count by position
        "re.sub(r'a', 'b', text, count=1)\n"
        "re.subn(r'a', 'b', text, 0, re.I)\n"    # count and flags by position
        "re.split(r',', text)\n"
        "text.split(',', 1)\n"                   # a string's own split takes its limit by position
        "re.findall(r'a', text, re.I)\n")        # and flags are findall's third argument, by position, as before
    for other in (".venv/y.py", "venv/lib/python3.12/site-packages/pkg/z.py", "build/lib/w.py"):  # not the repository's own
        (tmp_path / other).parent.mkdir(parents=True)
        (tmp_path / other).write_text("import re\nre.split(r',', text, 1)\n")
    (tmp_path / "conftest.py").write_text("import re\nre.sub(r'a', 'b', text, 2)\n")  # a file at the root is
    assert positional_re_limits(tmp_path) == ["conftest.py:2", "skills/a/x.py:2", "skills/a/x.py:4", "skills/a/x.py:6"]


# ---- A deprecated call in the core fails its test on the Python that deprecates it --------

def test_a_deprecation_met_in_the_core_fails_the_test_and_one_met_elsewhere_does_not(request):
    """`pytest.ini` turns a DeprecationWarning raised for a line of the core into an error. The three positional
    limits above warned under Python 3.13 at every use, in a summary at the end of a run that nobody read."""
    import sys
    import warnings
    if request.config.getoption("pythonwarnings") or sys.warnoptions:
        pytest.skip("this run was told how to treat warnings (-W or PYTHONWARNINGS), which outranks or reshapes pytest.ini")
    with pytest.raises(DeprecationWarning):
        warnings.warn_explicit("refused by a later Python", DeprecationWarning, "synthesis/guards.py", 1, module="synthesis.guards")
    with warnings.catch_warnings(record=True) as seen:
        warnings.warn_explicit("another project's to fix", DeprecationWarning, "elsewhere.py", 1, module="elsewhere")
    assert [str(w.message) for w in seen] == ["another project's to fix"]


# A script that imports the runtime at its top says so in one line when the runtime is not there (2026-11-13: run from
# a copy with no `synthesis/` beside it, as a package of skills without the runtime would hold them, two rituals'
# scripts ended in a traceback, even for `--help`). The connector's `corpus.py` is one of them: it is imported, not run,
# and the start that imports it ends the same way, in one line and exit 2.


def bare_runtime_imports(root: Path = ROOT) -> list:
    import ast
    found = []
    for path in sorted(root.glob("skills/**/*.py")):
        name = path.relative_to(root).as_posix()
        if "/tests/" in name or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for node in ast.parse(text).body:  # top-level statements only: a function's own import fails where it is called
            for inner in node.body if isinstance(node, ast.Try) else [node]:
                names = [inner.module or ""] if isinstance(inner, ast.ImportFrom) else [a.name for a in inner.names] if isinstance(inner, ast.Import) else []
                said = "".join(ast.get_source_segment(text, handler) or "" for handler in getattr(node, "handlers", []))
                if any(n == "synthesis" or n.startswith("synthesis.") for n in names) and not ("the synthesis runtime" in said and "sys.exit(2)" in said):
                    found.append(f"{name}:{inner.lineno}")  # bare, or behind a guard that does not say so and exit 2
    return found


def test_no_script_imports_the_runtime_bare_at_its_top():
    assert bare_runtime_imports() == []


@pytest.mark.parametrize("script", ["skills/synthesis-daily-rituals/scripts/decay_sweep.py",
                                    "skills/synthesis-kb-distribution/scripts/build_plugin.py",
                                    "skills/synthesis-kb-distribution/scripts/connector/kb_connector/corpus.py"])
def test_a_script_that_needs_the_runtime_says_so_in_a_line_when_it_is_not_there(script, tmp_path):
    alone = tmp_path / script  # a copy with no `synthesis/` anywhere above it
    alone.parent.mkdir(parents=True)
    alone.write_text((ROOT / script).read_text(encoding="utf-8"), encoding="utf-8")
    import sys
    ran = subprocess.run([sys.executable, "-I", str(alone), "--help"], capture_output=True, text=True, cwd=tmp_path,
                         env={"PATH": "/usr/bin:/bin", "SYNTHESIS_HOME": str(tmp_path / "none"), "HOME": str(tmp_path)})
    assert ran.returncode == 2 and "Traceback" not in ran.stderr and len(ran.stderr.strip().splitlines()) == 1
    assert "needs the synthesis runtime, which cannot be imported" in ran.stderr and alone.name in ran.stderr
    assert "the installed synthesis-skills plugin or a checkout of it" in ran.stderr  # release.py and setup.py run from a checkout


def test_a_runtime_that_is_there_and_fails_as_it_loads_keeps_its_traceback(tmp_path):
    """A review, 2026-11-13: the guard caught every error, so a runtime broken in itself was reported as one that is
    not there, with advice that could not help and no traceback to find the fault by."""
    script = "skills/synthesis-daily-rituals/scripts/decay_sweep.py"
    alone = tmp_path / script
    alone.parent.mkdir(parents=True)
    alone.write_text((ROOT / script).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "synthesis").mkdir()
    (tmp_path / "synthesis" / "__init__.py").write_text("raise RuntimeError('broken in itself')\n", encoding="utf-8")
    (tmp_path / "synthesis" / "rituals.py").write_text("", encoding="utf-8")  # the module the script looks for to find its runtime
    import sys
    ran = subprocess.run([sys.executable, "-I", str(alone), "--help"], capture_output=True, text=True, cwd=tmp_path,
                         env={"PATH": "/usr/bin:/bin", "SYNTHESIS_HOME": str(tmp_path / "none"), "HOME": str(tmp_path)})
    assert ran.returncode == 1 and "Traceback" in ran.stderr and "RuntimeError: broken in itself" in ran.stderr


def test_the_rule_finds_an_import_at_the_top_and_spares_one_that_is_guarded_or_inside_a_function(tmp_path):
    scripts = tmp_path / "skills" / "probe" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "bare.py").write_text("import sys\nfrom synthesis import paths\n", encoding="utf-8")
    (scripts / "whole.py").write_text("import synthesis.paths\n", encoding="utf-8")
    (scripts / "guarded.py").write_text("import sys\ntry:\n    from synthesis import paths\nexcept ImportError as exc:\n"
                                        "    print(f'{__file__} needs the synthesis runtime ({exc})', file=sys.stderr)\n    sys.exit(2)\n", encoding="utf-8")
    (scripts / "silent.py").write_text("import sys\ntry:\n    from synthesis import paths\nexcept ImportError:\n    sys.exit(2)\n", encoding="utf-8")
    (scripts / "late.py").write_text("def run():\n    from synthesis import paths\n    return paths\n", encoding="utf-8")
    (scripts / "test_probe.py").write_text("from synthesis import paths\n", encoding="utf-8")
    assert bare_runtime_imports(tmp_path) == ["skills/probe/scripts/bare.py:2", "skills/probe/scripts/silent.py:3", "skills/probe/scripts/whole.py:1"]


def twice_bound(source: str, defs_only: bool = False) -> list:
    """The names a module binds more than once at its top: a function, a class or an assignment (`defs_only`: a
    function or a class)."""
    import ast
    import collections
    names = collections.Counter()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] += 1
        elif not defs_only and isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                names.update(leaf.id for leaf in ast.walk(target) if isinstance(leaf, ast.Name))
    return sorted(name for name, count in names.items() if count > 1)


def test_no_core_module_binds_a_name_twice_at_its_top():
    """2026-11-13: a helper was given the name of an older one further down the same file, twice in one day (a
    function, then a pattern). The later one won without a word, and each was found only because tests of something
    else failed: 48 of them the first time, 286 the second."""
    assert twice_bound("A = 1\n\n\ndef f():\n    A = 2\n\n\nA = 3\n") == ["A"]
    assert twice_bound("def f():\n    pass\n\n\nclass f:\n    pass\n") == ["f"]
    assert twice_bound("A, B = 1, 2\nC: int = 3\ntry:\n    import x\nexcept ImportError:\n    x = None\n") == []
    for path in sorted((ROOT / "synthesis").glob("*.py")):
        assert twice_bound(path.read_text(encoding="utf-8")) == [], path.name


def test_no_python_file_defines_a_function_or_a_class_twice_at_its_top():
    """2026-11-13, the same day: renaming a helper in a new test file gave two functions one name. A second
    definition replaces the first without a word, and a test function defined twice never runs. Every Python file is
    read for functions and classes; assigning a name again is ordinary in a script and a test (ten files do), so the
    whole rule stays the core's."""
    assert twice_bound("def test_a():\n    pass\n\n\ndef test_a():\n    pass\n", defs_only=True) == ["test_a"]
    assert twice_bound("SPEC = 1\nSPEC = 2\n\n\ndef f():\n    pass\n", defs_only=True) == []
    # a review, 2026-11-13: two methods of one name in a test class were missed, and an overload was taken for a copy
    assert twice_bound("class TestA:\n    def test_a(self):\n        pass\n\n    def test_a(self):\n        pass\n", defs_only=True) == ["TestA.test_a"]
    assert twice_bound("from typing import overload\n\n\n@overload\ndef f(a: int) -> int: ...\n@overload\ndef f(a: str) -> str: ...\ndef f(a):\n    return a\n", defs_only=True) == []
    assert twice_bound("class A:\n    @property\n    def x(self):\n        return 1\n\n    @x.setter\n    def x(self, value):\n        pass\n", defs_only=True) == []
    assert twice_bound("import typing\n\n\n@typing.overload\ndef f(a: int) -> int: ...\ndef f(a):\n    return a\n\n\ndef f(a):\n    return a\n", defs_only=True) == ["f"]
    files = [p for p in sorted(ROOT.rglob("*.py")) if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)]
    assert len(files) > 200
    assert {str(p.relative_to(ROOT)): found for p in files if (found := twice_bound(p.read_text(encoding="utf-8"), defs_only=True))} == {}
