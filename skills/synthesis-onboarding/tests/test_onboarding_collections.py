"""setup.py --collections: pick collections of the synthesis skills in place of the whole set (ruling C8, 2026-11-20).

"Someone may want only the synthesis writing skills. However, core/shared skills and guards required by the writing
skills should also be installed. It should also make it easy for the user to add other synthesis skills collections
later." So a person names the collections they want; setup builds the five collections from its own checkout, the
core carrying the guard (the whole set's hooks and the runtime they run), and installs the core and those collections
in each harness with the harness's own commands. Naming another collection later adds it and keeps the first.

Every harness here is a fake that does what the harness does with its own files under the test's home: it adds a
marketplace from a folder, installs a plugin by copying it into its cache (Claude Code reads a folder marketplace's
plugin in place, and installs a plugin's declared dependencies), lists what it holds, and records each call with
whether the guard's runtime was installed when it ran.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import setup

CORE, WRITING, ENGINEERING = "synthesis-skills-core", "synthesis-skills-writing", "synthesis-skills-engineering"
MARKET, FOLDER = "synthesis-collections", "collections"
NAMES = "core, project-management, engineering, writing and chief-of-staff"
HOOKS = json.loads((setup.REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
MUSE_HOOKS = json.loads((setup.REPO / ".muse-plugin" / "plugin.json").read_text(encoding="utf-8"))["capabilities"]["hooks"]


@pytest.fixture(autouse=True)
def the_principal_approves_each_change_of_the_runtime(monkeypatch):
    """As in test_onboarding_setup.py: a setup run over an installed runtime spends the principal's code inside
    install; these tests are about the collections, so it is given."""
    monkeypatch.setattr(setup.install, "_approve", lambda *args, **kwargs: None)


@pytest.fixture(scope="module")
def one_build():
    """One build of this checkout's collections, which every run below reads in place of building again."""
    build = setup.collections_builder()
    files, modes = build.build(setup.REPO)
    return files, modes, build.verify(setup.REPO, files)


@pytest.fixture(autouse=True)
def built_once(one_build, monkeypatch):
    build = setup.collections_builder()
    real = build.verify
    monkeypatch.setattr(build, "build", lambda repo, commit=False: (dict(one_build[0]), dict(one_build[1])))
    monkeypatch.setattr(build, "verify", lambda repo, files, commit=False: list(one_build[2]) if files == one_build[0]
                        else real(repo, files, commit))


FAKE = r'''#!{python}
"""A {name} that keeps what it holds in a state file, as the harness keeps it in its own files."""
import json, os, shutil, sys
from pathlib import Path
HOME = Path(os.environ["HOME"])
NAME, LOG, STATE = {name!r}, Path({log!r}), Path({state!r})
args = sys.argv[1:]
hook = Path(os.environ["SYNTHESIS_HOME"]) / "bin" / "synthesis-hook"
with LOG.open("a") as log:
    log.write(" ".join(args) + ("" if hook.exists() else "  [no runtime]") + "\n")
state = json.loads(STATE.read_text()) if STATE.exists() else {{"markets": {{}}, "plugins": {{}}}}
fail = os.environ.get("FAKE_FAIL", "")
if fail and " ".join(args).startswith(fail):
    print(f"error: {{fail}} failed", file=sys.stderr); sys.exit(1)


def save():
    STATE.write_text(json.dumps(state))


def out(value, code=0):
    print(json.dumps(value)); save(); sys.exit(code)


def manifest(folder):
    for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json"):
        if (Path(folder) / name).is_file():
            return json.loads((Path(folder) / name).read_text())
    return {{}}


def folder_of(market, plugin):
    """The plugin's folder in a marketplace added from a folder; None for one added from GitHub."""
    path = state["markets"].get(market, {{}}).get("path")
    if not path:
        return None
    listing = Path(path) / (".claude-plugin/marketplace.json" if NAME == "claude" else ".agents/plugins/marketplace.json")
    for entry in json.loads(listing.read_text())["plugins"]:
        if entry["name"] == plugin:
            source = entry["source"] if isinstance(entry["source"], str) else entry["source"]["path"]
            return str((Path(path) / source).resolve())
    print(f"error: {{plugin}} is not in {{market}}", file=sys.stderr); sys.exit(1)


def install(plugin_id, cache_root):
    plugin, market = plugin_id.split("@")
    folder = folder_of(market, plugin)
    version = manifest(folder).get("version", "5.0.0") if folder else "5.0.0"
    if NAME == "claude" and folder:  # Claude Code installs a plugin's declared dependencies with it
        for need in manifest(folder).get("dependencies", []):
            if f"{{need}}@{{market}}" not in state["plugins"]:
                install(f"{{need}}@{{market}}", cache_root)
    cache = cache_root / market / plugin / version
    shutil.rmtree(cache, ignore_errors=True)
    if folder:
        shutil.copytree(folder, cache)
    else:
        cache.mkdir(parents=True)
    state["plugins"][plugin_id] = {{"version": version, "cache": str(cache), "folder": folder}}


if NAME == "claude":
    cache_root = HOME / ".claude" / "plugins" / "cache"
    if args[:2] == ["plugin", "list"]:
        out([{{"id": pid, "version": p["version"], "enabled": True, "installPath": p["cache"],
               **({{"readFromFolder": p["folder"]}} if p["folder"] else {{}})}} for pid, p in state["plugins"].items()])
    if args[:3] == ["plugin", "marketplace", "list"]:
        out([{{"name": n, "source": m["kind"], **({{"path": m["path"]}} if m.get("path") else {{"repo": m["repo"]}})}}
             for n, m in state["markets"].items()])
    if args[:3] == ["plugin", "marketplace", "add"]:
        source = args[3]
        if Path(source).is_dir():
            name, market = json.loads((Path(source) / ".claude-plugin/marketplace.json").read_text())["name"], {{"kind": "directory", "path": source}}
        else:
            name, market = "synthesis-engineering", {{"kind": "github", "repo": source}}
        if name in state["markets"]:
            print("marketplace already exists", file=sys.stderr); sys.exit(1)
        state["markets"][name] = market; save(); sys.exit(0)
    if args[:3] == ["plugin", "marketplace", "update"]:
        sys.exit(0 if args[3] in state["markets"] else 1)
    if args[:3] == ["plugin", "marketplace", "remove"]:
        state["markets"].pop(args[3], None)
        state["plugins"] = {{k: v for k, v in state["plugins"].items() if not k.endswith("@" + args[3])}}
        save(); sys.exit(0)
    if args[:2] == ["plugin", "install"]:
        install(args[2], cache_root); save(); sys.exit(0)
    if args[:2] == ["plugin", "update"]:
        sys.exit(0 if args[2] in state["plugins"] else 1)
    if args[:2] == ["plugin", "uninstall"]:
        state["plugins"].pop(args[2], None); save(); sys.exit(0)
if NAME == "codex":
    cache_root = Path(os.environ.get("CODEX_HOME") or HOME / ".codex") / "plugins" / "cache"
    if args[:2] == ["plugin", "list"]:
        only = args[args.index("-m") + 1] if "-m" in args else None
        out({{"installed": [{{"pluginId": pid, "name": pid.split("@")[0], "marketplaceName": pid.split("@")[1],
                              "version": p["version"], "enabled": True}} for pid, p in state["plugins"].items()
                             if only in (None, pid.split("@")[1])], "available": []}})
    if args[:3] == ["plugin", "marketplace", "list"]:
        out({{"marketplaces": [{{"name": n, "root": m.get("path") or "", "marketplaceSource": {{
            "sourceType": m["kind"], "source": m.get("path") or m.get("repo")}}}} for n, m in state["markets"].items()]}})
    if args[:3] == ["plugin", "marketplace", "add"]:
        source = args[3]
        if Path(source).is_dir():
            name, market = json.loads((Path(source) / ".agents/plugins/marketplace.json").read_text())["name"], {{"kind": "local", "path": source}}
        else:
            name, market = "synthesis-engineering", {{"kind": "git", "repo": source}}
        if name in state["markets"]:
            out({{"marketplaceName": name, "alreadyAdded": True}})
        state["markets"][name] = market
        out({{"marketplaceName": name, "alreadyAdded": False}})
    if args[:3] == ["plugin", "marketplace", "upgrade"]:
        if state["markets"].get(args[3], {{}}).get("kind") != "git":
            print(f"Error: marketplace `{{args[3]}}` is not configured as a Git marketplace", file=sys.stderr); sys.exit(1)
        out({{}})
    if args[:3] == ["plugin", "marketplace", "remove"]:
        state["markets"].pop(args[3], None); save(); sys.exit(0)
    if args[:2] == ["plugin", "add"]:
        install(args[2], cache_root); save(); print(f"Added plugin `{{args[2]}}`"); sys.exit(0)
    if args[:2] == ["plugin", "remove"]:
        state["plugins"].pop(args[2], None); out({{}})
if NAME == "muse":
    cache_root = HOME / ".local" / "share" / "muse" / "plugins" / "cache" / "local"
    if args[:2] == ["plugins", "--help"]:
        print("usage: muse plugins <command>\n\nCommands:\n  install <path>\n  list [--json]\n  update <id>\n  remove <id>\n"
              "  inspect <id>\n  approve <id>"); sys.exit(0)
    if args[:2] == ["plugins", "list"]:
        out({{"plugins": [{{"record": {{"id": pid, "version": p["version"], "enabled": True, "source": {{"path": p["folder"]}},
                                        "cache_path": p["cache"]}}}} for pid, p in state["plugins"].items()]}})
    if args[:2] in (["plugins", "install"], ["plugins", "update"]):
        folder = args[2] if args[1] == "install" else state["plugins"][args[2]]["folder"]
        made = manifest(folder)
        cache = cache_root / made["name"] / "package"
        shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(folder, cache)
        state["plugins"][made["name"]] = {{"version": made["version"], "cache": str(cache), "folder": folder}}
        out({{}})
    if args[:2] == ["plugins", "remove"]:
        state["plugins"].pop(args[2], None); out({{}})
print("unknown command: " + " ".join(args), file=sys.stderr)
sys.exit(2)
'''


@pytest.fixture
def harnesses(tmp_path, monkeypatch):
    """Claude Code, Codex and Muse as fakes that keep their own state; {name: (binary, log, state)}."""
    found = {}
    for name in ("claude", "codex", "muse"):
        log, state, binary = tmp_path / f"{name}.log", tmp_path / f"{name}-state.json", tmp_path / "bin" / name
        binary.parent.mkdir(exist_ok=True)
        binary.write_text(FAKE.format(python=sys.executable, name=name, log=str(log), state=str(state)))
        binary.chmod(0o755)
        found[name] = (str(binary), log, state)
    monkeypatch.setattr(setup.doctor, "find_client", lambda name: found[name][0] if name in found else None)
    return found


def calls(harnesses, name) -> list:
    log = harnesses[name][1]
    return log.read_text().splitlines() if log.exists() else []


def acts(harnesses, name) -> list:
    """The calls that change what the harness holds: every call but its listings and its help."""
    return [line for line in calls(harnesses, name) if not (" list" in line or "--help" in line)]


def held(harnesses, name) -> dict:
    """{plugin id: what the harness holds of it}: its version, its cache folder and the folder it came from."""
    state = harnesses[name][2]
    return json.loads(state.read_text())["plugins"] if state.exists() else {}


def loaded(harnesses, name, plugin) -> Path:
    """The folder a harness loads a plugin from: Claude Code reads a folder marketplace's plugin in place."""
    entry = next(entry for pid, entry in held(harnesses, name).items() if pid.split("@")[0] == plugin)
    return Path(entry["folder"] if name == "claude" else entry["cache"])


def run(*argv, capsys) -> tuple:
    code = setup.main([*argv, "--no-input"])
    return code, capsys.readouterr().out.splitlines()


def collections_folder() -> Path:
    return setup.install._home() / FOLDER


def record() -> Path:
    return setup.install._home() / "install" / "collections.json"


def assert_guarded(harnesses, picked):
    """Each harness holds the core and exactly the collections picked; the core it loads carries the whole set's hooks
    as that harness reads them, and no collection beside it holds one."""
    for name in ("claude", "codex", "muse"):
        assert sorted(pid.split("@")[0] for pid in held(harnesses, name)) == sorted([CORE, *picked]), name
        core = loaded(harnesses, name, CORE)
        if name == "muse":
            assert json.loads((core / ".muse-plugin" / "plugin.json").read_text())["capabilities"]["hooks"] == MUSE_HOOKS
            assert all((core / hook["command"][1]).is_file() for hook in MUSE_HOOKS)
        else:
            assert json.loads((core / "hooks" / "hooks.json").read_text()) == HOOKS
        assert (core / "synthesis" / "hook.py").read_bytes() == (setup.REPO / "synthesis" / "hook.py").read_bytes()
        for plugin in picked:
            assert not (loaded(harnesses, name, plugin) / "hooks").exists(), (name, plugin)
            assert json.loads((loaded(harnesses, name, plugin) / ".muse-plugin" / "plugin.json").read_text())[
                "capabilities"]["hooks"] == []


# ---- choosing a collection --------------------------------------------------------------------------------

def test_choosing_one_collection_installs_it_the_core_and_the_guards_hooks_in_each_harness(harnesses, capsys):
    code, lines = run("plugin", "--collections", "writing", capsys=capsys)
    assert code == 0, lines
    assert_guarded(harnesses, [WRITING])
    folder = collections_folder()
    assert acts(harnesses, "claude") == [f"plugin marketplace add {folder}", f"plugin install {CORE}@{MARKET}",
                                         f"plugin install {WRITING}@{MARKET}"]
    assert acts(harnesses, "codex") == [f"plugin marketplace add {folder} --json", f"plugin add {CORE}@{MARKET}",
                                        f"plugin add {WRITING}@{MARKET}"]
    assert acts(harnesses, "muse") == [f"plugins install {folder / 'core'} --json", f"plugins install {folder / 'writing'} --json"]
    assert not [line for name in harnesses for line in calls(harnesses, name) if line.endswith("[no runtime]")
                and ("install" in line or " add " in line)]  # the runtime the hooks run was in place before any plugin
    assert (setup.install._home() / "bin" / "synthesis-hook").is_file()
    assert "hooks = true" in (Path.home() / ".codex" / "config.toml").read_text()  # Codex runs a plugin's hooks only so
    assert json.loads(record().read_text()) == {"collections": ["writing"]}
    assert f"claude: installed {CORE}, {WRITING} (from {folder}); {CORE} carries the guard" in lines
    assert any(line.startswith(f"muse: installed {CORE}, {WRITING} (from {folder}); {CORE} carries the guard") and
               f"`muse plugins approve {CORE}`" in line for line in lines)
    assert not any("synthesis-skills@synthesis-engineering" in line for name in harnesses for line in calls(harnesses, name))


def test_a_collection_added_later_keeps_the_first_and_adds_the_second(harnesses, capsys):
    assert run("plugin", "--collections", "writing", capsys=capsys)[0] == 0
    code, lines = run("plugin", "--collections", "engineering", capsys=capsys)
    assert code == 0, lines
    assert_guarded(harnesses, [WRITING, ENGINEERING])
    assert json.loads(record().read_text()) == {"collections": ["engineering", "writing"]}
    folder = collections_folder()
    assert f"claude: installed {ENGINEERING}; current {CORE}, {WRITING} (from {folder}); {CORE} carries the guard" in lines
    assert acts(harnesses, "claude")[-2:] == [f"plugin marketplace update {MARKET}", f"plugin install {ENGINEERING}@{MARKET}"]
    assert acts(harnesses, "muse")[-3:] == [f"plugins update {CORE} --json", f"plugins install {folder / 'engineering'} --json",
                                             f"plugins update {WRITING} --json"]  # the core first, then the file's order


def test_a_later_run_that_names_no_collection_keeps_and_updates_the_ones_chosen(harnesses, capsys):
    """An install keeps its shape, as one that follows a channel keeps it: the update is the same command as before."""
    assert run("plugin", "--collections", "writing", capsys=capsys)[0] == 0
    code, lines = run("plugin", capsys=capsys)
    assert code == 0, lines
    assert_guarded(harnesses, [WRITING])
    assert acts(harnesses, "codex")[-2:] == [f"plugin add {CORE}@{MARKET}", f"plugin add {WRITING}@{MARKET}"]  # copied again
    assert not any("synthesis-engineering" in line for name in harnesses for line in acts(harnesses, name))


def test_an_unknown_collection_is_refused_with_the_name_of_every_collection(harnesses, capsys):
    before = sorted(Path.home().rglob("*"))
    code, lines = run("plugin", "--collections", "writing,writng", capsys=capsys)
    assert code == 1 and lines == [f"stopped: no collection is named writng; the collections are {NAMES}"]
    assert [calls(harnesses, name) for name in harnesses] == [[], [], []] and sorted(Path.home().rglob("*")) == before
    assert run("plugin", "--collections", ",", capsys=capsys)[1] == [f"stopped: --collections names no collection; the collections are {NAMES}"]


def test_core_alone_is_a_choice_and_installs_the_guard(harnesses, capsys):
    assert run("plugin", "--collections", "core", capsys=capsys)[0] == 0
    assert_guarded(harnesses, [])
    assert json.loads(record().read_text()) == {"collections": ["core"]}


# ---- no path installs skills without the guard ------------------------------------------------------------

def test_a_harness_whose_core_does_not_install_gets_no_collection(harnesses, capsys, monkeypatch):
    monkeypatch.setenv("FAKE_FAIL", f"plugin add {CORE}@{MARKET}")  # Codex refuses the core; the others take it
    code, lines = run("plugin", "--collections", "writing", capsys=capsys)
    assert code == 1
    assert held(harnesses, "codex") == {} and not any(WRITING in line for line in calls(harnesses, "codex"))
    assert any(line.startswith(f"codex: `plugin add {CORE}@{MARKET}` failed") and "no collection was installed without it"
               in line for line in lines)
    assert sorted(pid.split("@")[0] for pid in held(harnesses, "claude")) == [CORE, WRITING]


def test_a_core_built_without_the_guard_installs_nothing(harnesses, capsys, monkeypatch, one_build):
    """Belt and braces past the build's own check: setup reads the guard in the core it is about to install."""
    build = setup.collections_builder()
    files = {path: data for path, data in one_build[0].items() if path != "core/hooks/hooks.json"}
    monkeypatch.setattr(build, "build", lambda repo, commit=False: (files, dict(one_build[1])))
    monkeypatch.setattr(build, "verify", lambda repo, files, commit=False: [])
    code, lines = run("plugin", "--collections", "writing", capsys=capsys)
    assert code == 1 and any(line.startswith("collections: the core this checkout builds carries no guard (core/hooks/hooks.json "
                                             "is missing), so no collection was installed") for line in lines)
    assert all(held(harnesses, name) == {} for name in harnesses) and not collections_folder().exists()


def test_collections_that_fail_their_check_install_nothing(harnesses, capsys, monkeypatch):
    monkeypatch.setattr(setup.collections_builder(), "verify", lambda repo, files, commit=False: ["skills/x/SKILL.md: in no collection"])
    code, lines = run("plugin", "--collections", "writing", capsys=capsys)
    assert code == 1 and "collections: they fail 1 check, so none was installed: skills/x/SKILL.md: in no collection" in lines
    assert all(held(harnesses, name) == {} for name in harnesses)


@pytest.mark.parametrize("name", ["core", "project-management", "engineering", "writing", "chief-of-staff"])
def test_every_collection_installs_after_the_core_and_every_core_carries_the_hooks(harnesses, capsys, name):
    code, lines = run("plugin", "--collections", name, "--dry-run", capsys=capsys)
    assert code == 0
    for harness in ("claude", "codex", "muse"):
        line = next(line for line in lines if line.startswith(f"{harness}: would run "))
        steps = line[len(f"{harness}: would run "):].split("; ")
        installs = [step for step in steps if step.startswith(("plugin install", "plugin add", "plugins install"))]
        assert installs[0].split()[2].startswith((f"{CORE}@", str(collections_folder() / "core"))), line
    files = setup.collections_builder().build(setup.REPO)[0]
    assert all(f"{folder}/hooks/hooks.json" in files for folder in ["core"])
    assert not [path for path in files if "hooks" in path.split("/") and not path.startswith("core/")]


def test_the_whole_set_and_the_collections_never_both_run_the_guard_in_a_harness(harnesses, capsys):
    """A harness that holds the whole set has every collection already: --collections adds nothing there, and the whole
    set is updated as before. One that holds the core never gets the whole set beside it."""
    claude, log, state = harnesses["claude"]
    state.write_text(json.dumps({"markets": {"synthesis-engineering": {"kind": "github", "repo": "x"}},
                                 "plugins": {"synthesis-skills@synthesis-engineering": {"version": "5.0.0", "cache": "/x", "folder": None}}}))
    code, lines = run("plugin", "--collections", "writing", "--clients", "claude", capsys=capsys)
    assert code == 0 and sorted(held(harnesses, "claude")) == ["synthesis-skills@synthesis-engineering"]
    assert any(line.startswith("claude: holds the whole set, synthesis-skills, which has every collection and the guard, so "
                               "--collections added nothing here") for line in lines)
    assert "plugin update synthesis-skills@synthesis-engineering" in calls(harnesses, "claude")
    state.write_text(json.dumps({"markets": {}, "plugins": {f"{CORE}@{MARKET}": {"version": "5.0.0", "cache": "/x", "folder": None}}}))
    record().unlink()
    with pytest.raises(setup.SetupError, match=f"claude: {CORE}, the guard of the synthesis collections, is installed here"):
        setup.install_plugin("claude", claude)
    assert sorted(held(harnesses, "claude")) == [f"{CORE}@{MARKET}"]


# ---- a dry run, the default, and taking it out -------------------------------------------------------------

def test_a_dry_run_lists_everything_it_would_install_or_write_and_writes_nothing(harnesses, capsys):
    before = sorted(str(path) for path in Path.home().rglob("*"))
    code, lines = run("plugin", "--collections", "writing", "--dry-run", capsys=capsys)
    assert code == 0, lines
    folder, version = collections_folder(), json.loads((setup.REPO / ".codex-plugin" / "plugin.json").read_text())["version"]
    assert f"collections: would build the 5 collections, version {version}, in {folder}; the core carries the guard: the " \
           "whole set's hooks and the runtime they run" in lines
    assert f"claude: would run plugin marketplace add {folder}; plugin install {CORE}@{MARKET}; plugin install {WRITING}@{MARKET}" in lines
    assert f"codex: would run plugin marketplace add {folder} --json; plugin add {CORE}@{MARKET}; plugin add {WRITING}@{MARKET}" in lines
    assert f"muse: would run plugins install {folder / 'core'} --json; plugins install {folder / 'writing'} --json" in lines
    assert f"collections: would record writing in {record()}" in lines
    assert any(line.startswith("runtime: would install it from ") for line in lines)
    assert any(line.startswith("codex config: would ") for line in lines)
    assert lines[-1] == "Dry run: nothing was changed."
    assert sorted(str(path) for path in Path.home().rglob("*")) == before
    asked = [line for name in harnesses for line in calls(harnesses, name)]
    assert asked and all(" list" in line or "--help" in line for line in asked)  # listings only


def test_the_whole_plugin_stays_the_default_when_no_collection_is_named(harnesses, capsys):
    code, lines = run("plugin", "--clients", "claude", capsys=capsys)
    assert code == 0, lines
    assert acts(harnesses, "claude") == ["plugin marketplace add synthesisengineering/synthesis-skills@stable",
                                         "plugin install synthesis-skills@synthesis-engineering"]
    assert sorted(held(harnesses, "claude")) == ["synthesis-skills@synthesis-engineering"]
    assert not collections_folder().exists() and not record().exists()
    assert not any(MARKET in line for line in calls(harnesses, "claude"))


def test_collections_go_with_the_plugin_step_alone(harnesses, capsys):
    code, lines = run("uninstall", "--collections", "writing", capsys=capsys)
    assert code == 1 and lines == ["stopped: --collections goes with setup.py plugin or the full install, not uninstall"]


def test_uninstall_takes_the_collections_out_the_core_last_and_their_folder_and_record(harnesses, capsys):
    assert run("plugin", "--collections", "writing", capsys=capsys)[0] == 0
    code, lines = run("uninstall", capsys=capsys)
    assert code == 0, lines
    assert all(held(harnesses, name) == {} for name in harnesses)
    assert acts(harnesses, "claude")[-3:] == [f"plugin uninstall {WRITING}@{MARKET} --yes", f"plugin uninstall {CORE}@{MARKET} --yes",
                                              f"plugin marketplace remove {MARKET}"]
    assert acts(harnesses, "codex")[-3:] == [f"plugin remove {WRITING}@{MARKET} --json", f"plugin remove {CORE}@{MARKET} --json",
                                             f"plugin marketplace remove {MARKET}"]
    assert acts(harnesses, "muse")[-2:] == [f"plugins remove {WRITING} --json", f"plugins remove {CORE} --json"]
    assert not collections_folder().exists() and not record().exists()
    assert f"claude: removed {WRITING}, {CORE}" in lines


def test_the_codex_option_that_keeps_an_approval_through_releases_switches_the_cores_hooks(harnesses, capsys):
    """--codex-user-hooks declares the guard's hooks in Codex's own hooks.json and switches the plugin's copies off by
    their state keys, which name the plugin that carries them: here the core."""
    code, lines = run("plugin", "--collections", "writing", "--clients", "codex", "--codex-user-hooks", capsys=capsys)
    assert code == 0, lines
    config = (Path.home() / ".codex" / "config.toml").read_text()
    assert f'[hooks.state."{CORE}@{MARKET}:hooks/hooks.json:pre_tool_use:0:0"]' in config
    assert "synthesis-skills@synthesis-engineering:hooks" not in config
    assert "PreToolUse" in json.loads((Path.home() / ".codex" / "hooks.json").read_text())["hooks"]


def test_the_doctor_and_setup_agree_on_the_plugin_that_carries_the_guard():
    spec = setup.collections_builder().read_spec(setup.REPO)
    assert spec["collections"][spec["core"]]["name"] == setup.doctor.CORE
    assert spec["marketplace"]["name"] == setup.doctor.COLLECTIONS
