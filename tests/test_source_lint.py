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
