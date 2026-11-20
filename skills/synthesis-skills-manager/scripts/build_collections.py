"""Build the five collections: the synthesis skills in plugins of their own, one folder each, beside the whole set.

    python3 skills/synthesis-skills-manager/scripts/build_collections.py OUT_DIR
    python3 skills/synthesis-skills-manager/scripts/build_collections.py --check

assets/collections.json lists the collections. Each skill names its own in its SKILL.md frontmatter (metadata.category),
or the file's awaiting_room names it while that SKILL.md has no room for the line under 8,000 bytes. A collection's
folder holds every tracked file of its skills that is not a test, byte for byte, the repository's two license files, and
its own manifests for Claude Code, Codex and Muse at the repository's version. The core also carries the whole set's
guard (ruling C8, 2026-11-20): its hooks as each harness reads them and the runtime they run, as the runtime's install
takes it, every byte the whole set's; no other collection holds or registers a hook. Every collection but the core
declares the core as a dependency in its Claude Code manifest; Codex and Muse resolve none, so their install lines name
both. Two marketplace files at the top list the five. The release publishes it all as the `collections` branch, through
`tree`; setup.py builds the same folders to install the collections a person picks. Files are read as
build_directory_package.py reads a package's, with its code.

The build refuses, writing nothing, when a skill names no collection, more than one, or one the file does not list;
when a skill depends on one outside its own collection and the core, or on one outside its own folder that its scripts
load (the core installs in a folder of its own); and when the folders built are not what they should be: a file that is
no manifest, license, file of the collection's skills or of the core's guard, a file that differs from its source, a
hook outside the core, a guard file, skill or license missing, a manifest with another name, version, dependency or
hook, a Muse manifest that does not list exactly the collection's skills, or a marketplace that does not list exactly
the collections, each from its folder.

One line on stdout, and the exit code:
  OUT_DIR              built OUT_DIR: 5 collections, 73 skills, 753 files, version 5.22.0             0
  --check              ok: 5 collections, 73 skills, 753 files, version 5.22.0; nothing written        0
  either, on a defect  refused: 2 problems; nothing written      (then each problem on its own line)    1
  any                  cannot continue: <why>    (the file, a manifest, a file or git cannot be read, a
                       skill holds a symbolic link, or OUT_DIR exists or cannot be written)            2
Folders are cut from the last commit, as a package is, and a build refuses with 1 while a file it would read differs
from that commit; `--check` reads the checkout's files. `--repo-root DIR` reads another checkout. Standard library only;
runs on Python 3.9.
"""

import argparse
import ast
import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_directory_package import (MANIFEST, Unreadable, committed, count, depends_on, git, is_test,  # noqa: E402
                                     read_json, tracked)

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:  # the runtime's own rule for what its install takes, which the core's guard carries
    sys.path.insert(1, str(REPO))
try:
    from synthesis import install  # noqa: E402
except ImportError as exc:  # no runtime beside this copy; one that fails otherwise as it loads keeps its traceback
    print(f"{__file__} needs the synthesis runtime, which cannot be imported ({exc}), so nothing ran. Run it from a "
          "checkout of synthesis-skills, or the core collection, which carries the runtime", file=sys.stderr)
    sys.exit(2)
LIST = "skills/synthesis-skills-manager/assets/collections.json"
MANIFESTS = (".claude-plugin/plugin.json", MANIFEST, ".muse-plugin/plugin.json")  # each collection's own, at its top
MARKETPLACES = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")  # at the top of the branch
LICENSES = ("LICENSE-APACHE", "LICENSE-CC0")  # the terms its skills' SPDX identifiers name travel with each folder
SHARED = ("author", "homepage", "repository", "license")  # what each collection's manifests take from the whole set's
LINK = re.compile(r"(\]\()([^)\s]+)(\))")  # an inline Markdown link: its target between `](` and `)`
CARRIABLE = ("yamlish",)  # runtime modules a collection may carry beside its scripts: the standard library alone, no
#                           state, no hook (R1-3 of 5.22.0's review: of 34 scripts that imported the runtime, 23 read it)
CAUGHT = ("ImportError", "ModuleNotFoundError", "Exception")  # an `except` that takes a module's absence
PRESENT = ("is_file", "exists", "is_dir")  # an `if` that asks first whether a file is there
HOOKS, MUSE_HOOKS = "hooks/hooks.json", ".muse-plugin/hooks"  # the whole set's hooks: Claude Code's and Codex's, Muse's


def read_spec(repo: Path, commit: bool = False) -> dict:
    spec = committed(repo, LIST) if commit else read_json(repo / LIST)
    entries = spec.get("collections") if isinstance(spec, dict) else None
    named = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")  # a folder of the branch, and a plugin's name, in every harness
    if not (isinstance(entries, dict) and spec.get("core") in entries and isinstance(spec.get("marketplace"), dict)
            and named.fullmatch(str(spec["marketplace"].get("name"))) and all(
                named.fullmatch(name) and isinstance(entry, dict) and named.fullmatch(str(entry.get("name")))
                and entry.get("description") for name, entry in entries.items())):
        raise Unreadable(f"{repo / LIST} needs `collections`, each with a name and a description, the `core` among "
                         "them, and a `marketplace` with a name")
    return spec


def order(spec: dict) -> list:
    """The collections, the core first."""
    return [spec["core"], *[name for name in spec["collections"] if name != spec["core"]]]


def category(skill_md: str) -> list:
    """Every collection a SKILL.md's frontmatter names as `metadata.category`; a list, or the key twice, names more."""
    front = re.match(r"---\n(.*?)\n---\n", skill_md, re.S)
    meta = re.search(r"^metadata:[ \t]*\n((?:[ \t]+\S.*(?:\n|$))*)", front.group(1) if front else "", re.M)
    values = re.findall(r"^[ \t]+category:(.*)$", meta.group(1) if meta else "", re.M)
    return [name.strip().strip("\"'") for value in values for name in value.strip().strip("[]").split(",") if name.strip()]


def homes(spec: dict, skills: dict) -> tuple:
    """({skill: its collection}, [each skill in no collection, in more than one, or in one the file does not list])."""
    waiting, home, problems = spec.get("awaiting_room") or {}, {}, []
    for path in sorted(path for path in skills if re.fullmatch(r"skills/[^/]+/SKILL\.md", path)):
        name = path.split("/")[1]
        found = category(skills[path].decode("utf-8", "replace")) + ([waiting[name]] if name in waiting else [])
        if len(found) == 1 and found[0] in spec["collections"]:
            home[name] = found[0]
        else:
            problems.append(f"{path}: in {' and '.join(found) or 'no collection'}; a skill is in exactly one that the "
                            "collections file lists")
    return home, problems + [f"{LIST}: awaiting_room names {name}, which is no skill here" for name in sorted(waiting)
                             if f"skills/{name}/SKILL.md" not in skills]


def bounds(spec: dict, skills: dict, home: dict) -> list:
    """Each dependency outside a skill's own collection and the core, or outside its own folder where its scripts load
    it: a collection installs in a folder apart from the core's, so a path from one into the other leads nowhere."""
    found = []
    for name, collection in sorted(home.items()):
        code = "\n".join(data.decode("utf-8", "replace") for path, data in skills.items()
                         if path.startswith(f"skills/{name}/") and path.endswith((".py", ".sh")))
        for need in depends_on(skills[f"skills/{name}/SKILL.md"].decode("utf-8", "replace")):
            loaded = re.search(rf"(?<![\w-]){re.escape(need)}(?![\w-])", code)
            if home.get(need) not in ({collection} if loaded else {collection, spec["core"]}):
                where = ("not beside it where its scripts load it" if loaded else "not in the core"
                         if collection == spec["core"] else f"not in {collection} or the core")
                found.append(f"skills/{name}/SKILL.md: depends on {need}, which is in "
                             f"{home.get(need) or 'no collection'}, {where}")
    return found


def hooked(value) -> bool:
    """Whether a manifest registers a hook: a `hooks` entry, at any depth, that holds anything."""
    if isinstance(value, dict):
        return any(key == "hooks" and bool(inner) or hooked(inner) for key, inner in value.items())
    return isinstance(value, list) and any(map(hooked, value))


def described(spec: dict, name: str, guarded: bool = False) -> str:
    """A collection's description, in its manifests and its marketplace entry, where a harness shows it: what it holds,
    then that it builds on the core (the core's own leaves that out), then that the core carries the guard (where the
    whole set has one to carry), then where the whole set is."""
    return " ".join(part for part in (spec["collections"][name]["description"],
                                      spec.get("with_core") if name != spec["core"] else "",
                                      spec.get("guard") if guarded else "", spec.get("whole_set")) if part)


def guard_paths(paths: set, install_text: str) -> set:
    """The paths of the whole set's guard, which the core carries (ruling C8, 2026-11-20): its hooks as each harness
    reads them, and the runtime they run as the runtime's install takes it (`install.takes`: the runtime package, the
    scripts of each skill it keeps at a stable path, and the CHANGELOG), so the core's runtime is the whole set's to the
    byte. None where the whole set has no hooks/hooks.json, as a checkout made for a test may not."""
    if HOOKS not in paths:
        return set()
    try:
        names = install.carried_in(install_text) if install_text else ()
    except install.Refused as error:
        raise Unreadable(str(error))
    return {path for path in paths if path == HOOKS or path.startswith(MUSE_HOOKS + "/") or install.takes(path, names)}


def manifests(spec: dict, name: str, skills: list, whole: dict, guarded: bool = False, hooks: list = ()) -> dict:
    """{path: manifest} of one collection, at the whole set's version. `guarded`: the core carries the whole set's guard,
    which every description says; `hooks`, the core's alone: the whole set's Muse hooks, which its Muse manifest
    registers (Claude Code and Codex read hooks/hooks.json by its place)."""
    entry, version, core = spec["collections"][name], whole.get("version"), spec["collections"][spec["core"]]["name"]
    said = described(spec, name, guarded)
    shared = {key: whole[key] for key in SHARED if key in whole}
    head = {"name": entry["name"], "version": version, "description": said, **shared,
            "keywords": entry.get("keywords", []), "skills": "./skills/"}
    interface = {**whole.get("interface", {}), "displayName": entry.get("displayName", entry["name"]),
                 "shortDescription": entry.get("shortDescription", ""), "longDescription": said}
    interface.pop("defaultPrompt", None)  # the whole set's prompts name skills a collection may not hold
    return {".claude-plugin/plugin.json": {**head, **({} if name == spec["core"] else {"dependencies": [core]})},
            MANIFEST: {**head, "interface": interface},
            ".muse-plugin/plugin.json": {
                "schemaVersion": 1, "name": entry["name"], "displayName": interface["displayName"], "version": version,
                "description": said, "compat": {"source": "native", "manifestDir": ".muse-plugin"},
                "capabilities": {"skills": [{"id": skill, "path": f"skills/{skill}/SKILL.md"} for skill in skills],
                                 "commands": [], "hooks": list(hooks), "mcpServers": [], "reminders": []}}}


def marketplaces(spec: dict, whole: dict, guarded: bool = False) -> dict:
    """{path: marketplace}: Claude Code's (which Muse reads too) and Codex's, listing the collections, the core first."""
    market, entries = spec["marketplace"], spec["collections"]
    facts = {key: whole[key] for key in ("author", "homepage") if key in whole}
    return {MARKETPLACES[0]: {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json", "name": market["name"],
        "description": market.get("description", ""), "owner": market.get("owner", {}),
        "plugins": [{"name": entries[name]["name"], "description": described(spec, name, guarded), "source": f"./{name}",
                     "category": entries[name].get("category", "development"), **facts} for name in order(spec)]},
            MARKETPLACES[1]: {
        "name": market["name"], "interface": {"displayName": market.get("displayName", market["name"])},
        "plugins": [{"name": entries[name]["name"], "source": {"source": "local", "path": f"./{name}"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                     "category": whole.get("interface", {}).get("category", "Developer Tools")}
                    for name in order(spec)]}}


def text(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def catches(handler) -> bool:
    kinds = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(kind is None or isinstance(kind, ast.Name) and kind.id in CAUGHT for kind in kinds)


def guards(node) -> bool:
    """Whether a node catches the absence of a module imported inside it."""
    if isinstance(node, ast.Try):
        return any(map(catches, node.handlers))
    return isinstance(node, ast.If) and any(isinstance(part, ast.Attribute) and part.attr in PRESENT
                                            for part in ast.walk(node.test))


def imported(node) -> list:
    """The modules an import statement names: `synthesis.<module>` for each it takes from the runtime's package."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return [f"synthesis.{alias.name}" for alias in node.names] if node.module == "synthesis" else [node.module or ""]


def runtime_imports(path: str, data: bytes) -> tuple:
    """({runtime module a file imports as it starts}, {(runtime module it imports inside a function, caught)}, {other
    module it imports as it starts}), read from its syntax and never by running it. An import is caught inside a `try`
    that takes ImportError, or an `if` that first asks whether a file is there."""
    top, late, plain = set(), set(), set()

    def walk(node, inside: bool, caught: bool):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)) and not getattr(child, "level", 0):
                for head, _, rest in (module.partition(".") for module in imported(child)):
                    if head == "synthesis" and rest:
                        late.add((rest.split(".")[0], caught)) if inside else top.add(rest.split(".")[0])
                    elif not inside:
                        plain.add(head)
            walk(child, inside or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)),
                 caught or guards(child))
    try:
        walk(ast.parse(data.decode("utf-8", "replace")), False, False)
    except SyntaxError as error:
        raise Unreadable(f"{path} cannot be read as Python: {error}")
    return top, late, plain


def needs(files: dict) -> dict:
    """{path: ({runtime module it needs as it starts, through the modules beside it that it imports too}, {(runtime
    module it imports inside a function, caught)})} for each Python file of `files` ({path: bytes}) that is no test."""
    read = {path: runtime_imports(path, data) for path, data in files.items()
            if path.endswith(".py") and not is_test(path)}

    def start(path: str, seen: set) -> set:
        found = set(read[path][0])
        for sibling in (f"{path.rsplit('/', 1)[0]}/{name}.py" for name in read[path][2]):
            found |= start(sibling, seen | {sibling}) if sibling in read and sibling not in seen else set()
        return found
    return {path: (start(path, {path}), read[path][1]) for path in read}


def docstrings(tree) -> set:
    """The ids of a module's docstrings: the first string of a module, class or function, which loads nothing."""
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    return {id(node.body[0].value) for node in ast.walk(tree) if isinstance(node, kinds) and node.body
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}


def reaches(path: str, data: bytes, names: set) -> set:
    """The other skills whose folders a file names as a path in a string of its code (R1-20): a string that is a skill's
    name, or holds it between slashes. A docstring says where something is and loads nothing."""
    tree, found, others = ast.parse(data.decode("utf-8", "replace")), set(), names - {path.split("/")[1]}
    said = docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in said:
            found |= {name for name in others if f"/{name}/" in f"/{node.value}/"}
    return found


def ancestors(paths: set) -> set:
    """Each folder above a path of `paths`, as a path."""
    return {path.rsplit("/", depth)[0] for path in paths for depth in range(1, path.count("/") + 1)}


def leaving(path: str, target: str, held: set, tracked: set) -> str:
    """Where a relative link of the file at `path` leads, when that is a file or folder of the repository (`tracked`,
    with its folders) and not one the collection's folder holds (`held`, with its folders); else ""."""
    target = target.partition("#")[0]
    if not target or re.match(r"[A-Za-z][\w+.-]*:|/|.*[<{$]", target):
        return ""
    whole = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    return whole if whole in tracked and whole not in held else ""


def relink(path: str, data: bytes, held: set, tracked: set, files: set, at: str) -> bytes:
    """A collected Markdown file with each link that leaves its folder pointed at the repository's file at the release's
    tag, `at` (R1-21: 42 such links led nowhere in a collection); every other byte is the source's."""
    def point(match):
        whole, anchor = leaving(path, match.group(2), held, tracked), match.group(2).partition("#")[2]
        kind, mark = "blob" if whole in files else "tree", f"#{anchor}" if anchor else ""
        return f"{match.group(1)}{at.format(kind)}/{whole}{mark}{match.group(3)}" if whole else match.group(0)
    if not path.endswith(".md"):
        return data
    return LINK.sub(point, data.decode("utf-8", "surrogateescape")).encode("utf-8", "surrogateescape")


def carry(need: dict) -> set:
    """The runtime modules a collection carries: those of CARRIABLE that any of its Python files imports."""
    return {module for top, late in need.values() for module in top | {name for name, _ in late}} & set(CARRIABLE)


def impure(text: bytes) -> list:
    """The runtime's own modules a module imports, relative imports among them: one that imports any cannot travel
    alone."""
    found = set()
    for node in ast.walk(ast.parse(text.decode("utf-8", "replace"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names if alias.name.split(".")[0] == "synthesis"}
        elif isinstance(node, ast.ImportFrom) and (node.level or (node.module or "").split(".")[0] == "synthesis"):
            inner = node.module.split(".")[-1] if node.module not in (None, "synthesis") else None
            found |= {f"synthesis.{inner or alias.name}" for alias in node.names}
    return sorted(found)


def sources(repo: Path, commit: bool = False) -> tuple:
    """(the collections file, the whole set's Codex manifest, (skill files, their modes), (licenses, their modes), (the
    runtime's files a collection may carry, their modes), every path the repository tracks, (the whole set's guard,
    which the core carries: {path: bytes}, their modes, and the hooks its Muse manifest registers))."""
    spec, whole = read_spec(repo, commit), committed(repo, MANIFEST) if commit else read_json(repo / MANIFEST)
    runtime = ["synthesis/__init__.py", *(f"synthesis/{module}.py" for module in CARRIABLE)]
    listed = git(repo, "ls-tree", "-r", "--name-only", "-z", "HEAD") if commit else git(repo, "ls-files", "-z")
    paths, skills = set(listed.split("\0")) - {""}, tracked(repo, ["skills"], commit)
    text_of = (lambda path: git(repo, "show", f"HEAD:{path}")) if commit else \
        (lambda path: (repo / path).read_text(encoding="utf-8"))  # noqa: E731
    wanted = guard_paths(paths, text_of("synthesis/install.py") if "synthesis/install.py" in paths else "")
    held, held_modes = tracked(repo, ["synthesis", HOOKS, MUSE_HOOKS, "CHANGELOG.md"], commit) if wanted else ({}, {})
    muse = (committed(repo, ".muse-plugin/plugin.json") if commit else read_json(repo / ".muse-plugin/plugin.json")) \
        if wanted and ".muse-plugin/plugin.json" in paths else {}
    carried = {path: held[path] if path in held else skills[0].get(path) for path in wanted}
    if any(data is None for data in carried.values()):  # a path the guard names that no file read gives: a test's, say
        raise Unreadable(f"the guard names {sorted(p for p, d in carried.items() if d is None)[0]}, which cannot be read")
    return (spec, whole, skills, tracked(repo, list(LICENSES), commit), tracked(repo, runtime, commit), paths,
            (carried, {path: held_modes.get(path) or skills[1].get(path, "100644") for path in carried},
             list((muse.get("capabilities") or {}).get("hooks") or [])))


def build(repo: Path, commit: bool = False) -> tuple:
    """({path: bytes}, {path: git's mode}) of the folders and the two marketplace files, from the checkout's files or
    the last commit's (`commit`). The same commit gives the same bytes. A skill in no collection, or in several, is in
    no folder, and `verify` names it. The core carries the whole set's guard, byte for byte (`guard_paths`)."""
    spec, whole, (skills, modes), (licenses, license_modes), (runtime, _), paths, (guarding, guard_modes, hooks) = \
        sources(repo, commit)
    home, files, kept, every = homes(spec, skills)[0], {}, {}, {**modes, **license_modes}
    everywhere, at = paths | ancestors(paths), f"{whole.get('repository', '')}/{{}}/v{whole.get('version')}"
    for name in order(spec):
        mine = sorted(skill for skill, collection in home.items() if collection == name)
        ours = {path: data for path, data in skills.items() if path.split("/")[1] in mine}
        guarded = name == spec["core"] and bool(guarding)
        modules = set() if guarded else carry(needs(ours))  # the YAML reader where its scripts read it; the core: all
        carried = {**ours, **licenses, **{path: data for path, data in runtime.items()
                                          if modules and (path == "synthesis/__init__.py" or path[10:-3] in modules)}}
        verbatim = guarding if guarded else {}  # the guard: the whole set's bytes, links and all
        held = set(carried) | set(verbatim) | ancestors(set(carried) | outside(verbatim, mine))
        files.update({f"{name}/{path}": relink(path, data, held, everywhere, paths, at) for path, data in carried.items()})
        files.update({f"{name}/{path}": data for path, data in verbatim.items()})
        kept.update({f"{name}/{path}": every.get(path, "100644") for path in carried})
        kept.update({f"{name}/{path}": guard_modes.get(path, "100644") for path in verbatim})
        files.update({f"{name}/{path}": text(made) for path, made in manifests(
            spec, name, mine, whole, bool(guarding), hooks if guarded else ()).items()})
    files.update({path: text(made) for path, made in marketplaces(spec, whole, bool(guarding)).items()})
    return files, kept


def outside(guarding: dict, mine: list) -> set:
    """The guard's paths but its copies of other collections' scripts, whose skill folders the core does not hold: a
    link from the core to such a folder still leads to the repository's."""
    return {path for path in guarding if not (path.startswith("skills/") and path.split("/")[1] not in mine)}


def verify(repo: Path, files: dict, commit: bool = False) -> list:
    """Each reason these folders may not be published, read from the built files themselves; empty when they may."""
    spec, whole, (skills, _), (licenses, _), (runtime, _), paths, (guarding, _, hooks) = sources(repo, commit)
    everywhere, at = paths | ancestors(paths), f"{whole.get('repository', '')}/{{}}/v{whole.get('version')}"
    home, found = homes(spec, skills)
    found += bounds(spec, skills, home)
    core, whole_set, scripts = spec["collections"][spec["core"]]["name"], spec.get("needs_the_whole_set") or {}, set()
    optional, taken = spec.get("optional_loads") or {}, set()
    found += [f"synthesis/{module}.py imports {other}, so no collection can carry it alone" for module in CARRIABLE
              if f"synthesis/{module}.py" in runtime for other in impure(runtime[f"synthesis/{module}.py"])]
    stable = {path.split("/")[1] for path in guarding if path.startswith("skills/")}  # the skills whose scripts it keeps
    for name, entry in spec["collections"].items():
        mine = sorted(skill for skill, collection in home.items() if collection == name)
        held = {path[len(name) + 1:]: data for path, data in files.items() if path.startswith(name + "/")}
        need = needs({path: data for path, data in skills.items() if path.split("/")[1] in mine})
        guarded = name == spec["core"] and bool(guarding)  # the core, carrying the whole set's guard and its runtime
        modules = {path[10:-3] for path in guarding if re.fullmatch(r"synthesis/\w+\.py", path)} if guarded else carry(need)
        scripts |= set(need)
        expected = set(guarding) if guarded else {"synthesis/__init__.py", *(f"synthesis/{module}.py" for module in modules)} \
            if modules else set()
        should = {path for path in skills if path.split("/")[1] in mine} | set(licenses) | expected
        should |= ancestors(should - (expected - outside(guarding, mine) if guarded else set()))  # where a link may lead
        for path, (top, late) in sorted(need.items()):  # a script runs where it is installed, or is named as needing more
            gone = sorted(top - modules)
            if path in whole_set:
                found += [f"{LIST}: needs_the_whole_set names {path}, which runs in its collection now"] * (not gone)
                continue
            found += [f"{name}/{path}: imports synthesis.{gone[0]} as it starts, which {name} does not carry, so it "
                      "cannot run there; make it run without it, or name it under needs_the_whole_set"] if gone else []
            found += [f"{name}/{path}: imports synthesis.{module} inside a function, with nothing to catch its absence, "
                      f"so in {name} that call ends in a traceback" for module, caught in sorted(late)
                      if not caught and module not in modules]
        for path in sorted(need):  # a path into another skill's folder finds it beside the script, or is named (R1-20)
            for other in sorted(reaches(path, skills[path], set(home))):
                taken.add((path, other))  # the guard's copy of a skill's scripts is beside every script of the core
                exempt = home[other] == name or path in whole_set or other in optional.get(path, {}) or (
                    guarded and other in stable)
                found += [] if exempt else [f"{name}/{path}: reaches {other}'s folder, which is in {home[other]}, not "
                                            f"beside it in {name}; name the load under optional_loads with what the "
                                            "script does without it, or keep the two in one collection"]
        for path, data in sorted(held.items()):
            parts = path.split("/")
            if guarded and path in guarding:  # the whole set's guard: its bytes, links and all
                found += [f"{name}/{path}: differs from its source"] * (guarding[path] != data)
                continue
            found += [f"{name}/{path}: holds a hook"] * ("hooks" in parts or parts[-1] == "hooks.json")
            if path in MANIFESTS:
                continue
            if parts[0] == "synthesis":  # a runtime module its scripts read, carried byte for byte
                found += [f"{name}/{path}: a runtime module {name} does not carry"] if path not in expected else \
                    [f"{name}/{path}: differs from its source"] * (runtime.get(path) != data)
                continue
            ours = parts[0] == "skills" and len(parts) > 2 and parts[1] in mine  # no test is a source: tracked skips it
            source = licenses.get(path) if path in LICENSES else skills.get(path) if ours else None
            source = relink(path, source, should, everywhere, paths, at) if source is not None else None
            found += [f"{name}/{path}: its link to {target} leads out of {name}" for _, target, _ in LINK.findall(
                data.decode("utf-8", "replace")) if path.endswith(".md") and leaving(path, target, should, everywhere)]
            found += [f"{name}/{path}: not a manifest, a license or a file of a skill in {name}"] if source is None else \
                [f"{name}/{path}: differs from its source"] * (source != data)
        found += [f"{name}/{path}: missing" + ("; the core carries the guard" if guarded and path in guarding else "")
                  for path in [*(f"skills/{skill}/SKILL.md" for skill in mine), *licenses, *sorted(expected)]
                  if path not in held]
        made = {}
        for path in MANIFESTS:
            try:
                made[path] = json.loads(held[path])
            except (KeyError, ValueError):
                made[path] = None
            if not isinstance(made[path], dict):
                found.append(f"{name}/{path}: missing, or not JSON")
                made[path] = {}
            elif (made[path].get("name"), made[path].get("version")) != (entry["name"], whole.get("version")):
                found.append(f"{name}/{path}: names {made[path].get('name')} {made[path].get('version')}, not "
                             f"{entry['name']} {whole.get('version')}")
            registered = made[path].get("capabilities") if guarded and path == MANIFESTS[2] else None
            if isinstance(registered, dict):  # the core's Muse manifest registers the whole set's hooks, and nothing else
                found += [f"{name}/{path}: registers hooks other than the whole set's"] * (registered.get("hooks") != hooks)
                found += [f"{name}/{path}: registers a hook"] * hooked({**made[path], "capabilities": {
                    **registered, "hooks": []}})
            else:
                found += [f"{name}/{path}: registers a hook"] * hooked(made[path])
        declared, wanted = made[MANIFESTS[0]].get("dependencies", []), [] if name == spec["core"] else [core]
        found += [f"{name}/{MANIFESTS[0]}: depends on {declared}, not on {wanted}"] * (declared != wanted)
        listed = (made[MANIFESTS[2]].get("capabilities") or {}).get("skills")
        pairs = sorted((str(item.get("id")), str(item.get("path"))) if isinstance(item, dict) else ("", "")
                       for item in listed) if isinstance(listed, list) else None
        if pairs != [(skill, f"skills/{skill}/SKILL.md") for skill in mine]:
            found.append(f"{name}/{MANIFESTS[2]}: does not list exactly the skills of {name}")
    found += [f"{LIST}: needs_the_whole_set names {path}, which is no script of any collection"
              for path in sorted(whole_set) if path not in scripts]
    found += [f"{LIST}: optional_loads names {other} for {path}, which does not reach it" for path in sorted(optional)
              for other in sorted(optional[path]) if (path, other) not in taken]
    found += [f"{path}: in no collection's folder" for path in sorted(files)
              if path.split("/")[0] not in spec["collections"] and path not in MARKETPLACES]
    wanted = [(spec["collections"][name]["name"], f"./{name}") for name in order(spec)]
    for path, source in zip(MARKETPLACES, (lambda item: item.get("source"), lambda item: item["source"].get("path"))):
        try:
            listed = [(item.get("name"), source(item)) for item in json.loads(files[path])["plugins"]]
        except (KeyError, ValueError, TypeError, AttributeError):
            listed = None
        found += [f"{path}: does not list exactly the {len(wanted)} collections, each from its folder"] * (
            listed != wanted)
    return found


def tree(repo: Path, files: dict, modes: dict) -> str:
    """The git tree of these files, its objects written into repo's store from memory and its own index untouched: what
    the release commits as the collections branch. Nothing is read back from a folder others can write (review round 2
    of 5.23.1, N3: the files went through a temporary folder and were hashed back from it): `git fast-import` takes the
    blobs on its input, the index lives in the repository's own git folder, and the tree written is held to the ids the
    files' bytes give in memory."""
    paths = sorted(files)
    kind = git(repo, "rev-parse", "--show-object-format").strip() or "sha1"
    ids = {path: hashlib.new(kind, b"blob %d\0" % len(files[path]) + files[path]).hexdigest() for path in paths}
    git(repo, "fast-import", "--quiet", stdin=b"".join(b"blob\ndata %d\n%s\n" % (len(files[p]), files[p]) for p in paths))
    gitdir = Path(git(repo, "rev-parse", "--absolute-git-dir").strip())
    with tempfile.TemporaryDirectory(dir=gitdir) as scratch:  # inside the repository's own git folder
        index = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch, "index"))}
        entries = (f"{'100755' if modes.get(path) == '100755' else '100644'} {ids[path]}\t{path}\n" for path in paths)
        git(repo, "update-index", "--add", "--index-info", env=index, stdin="".join(entries).encode())
        made = git(repo, "write-tree", env=index).strip()
    listed = dict(line.split(" ", 2)[2].split("\t", 1)[::-1] for line in git(repo, "ls-tree", "-r", made).splitlines())
    if listed != ids:
        raise Unreadable(f"the collections tree {made[:12]} is not the files built: {len(set(listed.items()) ^ set(ids.items()))} entries differ")
    return made


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build_collections.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("out", nargs="?", type=Path, help="the folder to write; it must not exist yet")
    parser.add_argument("--check", action="store_true", help="verify the collections and write nothing")
    parser.add_argument("--repo-root", type=Path, default=REPO)
    args = parser.parse_args(argv)
    if bool(args.out) == args.check:
        parser.error("give the folder to write, or --check")
    repo, commit = args.repo_root.resolve(), bool(args.out)
    try:
        if commit and os.path.lexists(args.out):
            raise Unreadable(f"{args.out} exists; a build writes a folder of its own")
        files, modes = build(repo, commit)
        found = verify(repo, files, commit)
        if commit:  # the folders hold the commit either way; an edit they do not hold is said, not passed over
            changed = git(repo, "diff", "--name-only", "--no-renames", "-z", "HEAD", "--", LIST, MANIFEST, "skills",
                          *LICENSES)
            found = [f"{path}: differs from the last commit; collections are cut from committed files"
                     for path in changed.split("\0") if path and not is_test(path)] + found
        if found:
            print("\n".join([f"refused: {count(len(found), 'problem')}; nothing written"] + found))
            return 1
        if commit:  # written whole beside OUT_DIR, then put in its place: a write that fails leaves no OUT_DIR
            staging = Path(tempfile.mkdtemp(prefix=f".{args.out.name}.", dir=args.out.parent))
            for path, data in files.items():
                (staging / path).parent.mkdir(parents=True, exist_ok=True)
                (staging / path).write_bytes(data)
                (staging / path).chmod(0o755 if modes.get(path) == "100755" else 0o644)
            os.rename(staging, args.out)
        spec = read_spec(repo, commit)
        version = json.loads(files[f"{spec['core']}/{MANIFEST}"])["version"]
        skills = {path.split("/")[2] for path in files if path.split("/")[1:2] == ["skills"]}
        holds = (f"{count(len(spec['collections']), 'collection')}, {count(len(skills), 'skill')}, "
                 f"{count(len(files), 'file')}, version {version}")
        print(f"built {args.out}: {holds}" if commit else f"ok: {holds}; nothing written")
        return 0
    except (Unreadable, OSError) as error:
        print(f"cannot continue: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
