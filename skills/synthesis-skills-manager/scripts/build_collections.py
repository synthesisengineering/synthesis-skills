"""Build the five collections: the synthesis skills in plugins without hooks, one folder each, beside the whole set.

    python3 skills/synthesis-skills-manager/scripts/build_collections.py OUT_DIR
    python3 skills/synthesis-skills-manager/scripts/build_collections.py --check

assets/collections.json lists the collections. Each skill names its own in its SKILL.md frontmatter (metadata.category),
or the file's awaiting_room names it while that SKILL.md has no room for the line under 8,000 bytes. A collection's
folder holds every tracked file of its skills that is not a test, byte for byte, the repository's two license files, and
its own manifests for Claude Code, Codex and Muse at the repository's version, none registering a hook. Every collection
but the core declares the core as a dependency in its Claude Code manifest; Codex and Muse resolve none, so their install
lines name both. Two marketplace files at the top list the five. The release publishes it all as the `collections`
branch, through `tree`. Files are read as build_directory_package.py reads a package's, with its code.

The build refuses, writing nothing, when a skill names no collection, more than one, or one the file does not list;
when a skill depends on one outside its own collection and the core, or on one outside its own folder that its scripts
load (the core installs in a folder of its own); and when the folders built are not what they should be: a file that is
no manifest, license or file of the collection's skills, a file that differs from its source, a hook, a skill or license
missing, a manifest with another name, version or dependency, a Muse manifest that does not list exactly the
collection's skills, or a marketplace that does not list exactly the collections, each from its folder.

One line on stdout, and the exit code:
  OUT_DIR              built OUT_DIR: 5 collections, 72 skills, 744 files, version 5.22.0             0
  --check              ok: 5 collections, 72 skills, 744 files, version 5.22.0; nothing written        0
  either, on a defect  refused: 2 problems; nothing written      (then each problem on its own line)    1
  any                  cannot continue: <why>    (the file, a manifest, a file or git cannot be read, a
                       skill holds a symbolic link, or OUT_DIR exists or cannot be written)            2
Folders are cut from the last commit, as a package is, and a build refuses with 1 while a file it would read differs
from that commit; `--check` reads the checkout's files. `--repo-root DIR` reads another checkout. Standard library only;
runs on Python 3.9.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_directory_package import (MANIFEST, Unreadable, committed, count, depends_on, git, is_test,  # noqa: E402
                                     read_json, tracked)

REPO = Path(__file__).resolve().parents[3]
LIST = "skills/synthesis-skills-manager/assets/collections.json"
MANIFESTS = (".claude-plugin/plugin.json", MANIFEST, ".muse-plugin/plugin.json")  # each collection's own, at its top
MARKETPLACES = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")  # at the top of the branch
LICENSES = ("LICENSE-APACHE", "LICENSE-CC0")  # the terms its skills' SPDX identifiers name travel with each folder
SHARED = ("author", "homepage", "repository", "license")  # what each collection's manifests take from the whole set's


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


def described(spec: dict, name: str) -> str:
    """A collection's description, in its manifests and its marketplace entry, where a harness shows it: what it holds,
    then that it builds on the core (the core's own leaves that out), then what it lacks and where the whole set is."""
    return " ".join(part for part in (spec["collections"][name]["description"],
                                      spec.get("with_core") if name != spec["core"] else "", spec.get("without")) if part)


def manifests(spec: dict, name: str, skills: list, whole: dict) -> dict:
    """{path: manifest} of one collection, at the whole set's version."""
    entry, version, core = spec["collections"][name], whole.get("version"), spec["collections"][spec["core"]]["name"]
    said = described(spec, name)
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
                                 "commands": [], "hooks": [], "mcpServers": [], "reminders": []}}}


def marketplaces(spec: dict, whole: dict) -> dict:
    """{path: marketplace}: Claude Code's (which Muse reads too) and Codex's, listing the collections, the core first."""
    market, entries = spec["marketplace"], spec["collections"]
    facts = {key: whole[key] for key in ("author", "homepage") if key in whole}
    return {MARKETPLACES[0]: {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json", "name": market["name"],
        "description": market.get("description", ""), "owner": market.get("owner", {}),
        "plugins": [{"name": entries[name]["name"], "description": described(spec, name), "source": f"./{name}",
                     "category": entries[name].get("category", "development"), **facts} for name in order(spec)]},
            MARKETPLACES[1]: {
        "name": market["name"], "interface": {"displayName": market.get("displayName", market["name"])},
        "plugins": [{"name": entries[name]["name"], "source": {"source": "local", "path": f"./{name}"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                     "category": whole.get("interface", {}).get("category", "Developer Tools")}
                    for name in order(spec)]}}


def text(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sources(repo: Path, commit: bool = False) -> tuple:
    """(the collections file, the whole set's Codex manifest, (skill files, their modes), (licenses, their modes))."""
    spec, whole = read_spec(repo, commit), committed(repo, MANIFEST) if commit else read_json(repo / MANIFEST)
    return spec, whole, tracked(repo, ["skills"], commit), tracked(repo, list(LICENSES), commit)


def build(repo: Path, commit: bool = False) -> tuple:
    """({path: bytes}, {path: git's mode}) of the folders and the two marketplace files, from the checkout's files or
    the last commit's (`commit`). The same commit gives the same bytes. A skill in no collection, or in several, is in
    no folder, and `verify` names it."""
    spec, whole, (skills, modes), (licenses, license_modes) = sources(repo, commit)
    home, files, kept, every = homes(spec, skills)[0], {}, {}, {**modes, **license_modes}
    for name in order(spec):
        mine = sorted(skill for skill, collection in home.items() if collection == name)
        carried = {**{path: data for path, data in skills.items() if path.split("/")[1] in mine}, **licenses}
        files.update({f"{name}/{path}": data for path, data in carried.items()})
        kept.update({f"{name}/{path}": every[path] for path in carried})
        files.update({f"{name}/{path}": text(made) for path, made in manifests(spec, name, mine, whole).items()})
    files.update({path: text(made) for path, made in marketplaces(spec, whole).items()})
    return files, kept


def verify(repo: Path, files: dict, commit: bool = False) -> list:
    """Each reason these folders may not be published, read from the built files themselves; empty when they may."""
    spec, whole, (skills, _), (licenses, _) = sources(repo, commit)
    home, found = homes(spec, skills)
    found += bounds(spec, skills, home)
    core = spec["collections"][spec["core"]]["name"]
    for name, entry in spec["collections"].items():
        mine = sorted(skill for skill, collection in home.items() if collection == name)
        held = {path[len(name) + 1:]: data for path, data in files.items() if path.startswith(name + "/")}
        for path, data in sorted(held.items()):
            parts = path.split("/")
            found += [f"{name}/{path}: holds a hook"] * ("hooks" in parts or parts[-1] == "hooks.json")
            if path in MANIFESTS:
                continue
            ours = parts[0] == "skills" and len(parts) > 2 and parts[1] in mine  # no test is a source: tracked skips it
            source = licenses.get(path) if path in LICENSES else skills.get(path) if ours else None
            found += [f"{name}/{path}: not a manifest, a license or a file of a skill in {name}"] if source is None else \
                [f"{name}/{path}: differs from its source"] * (source != data)
        found += [f"{name}/{path}: missing" for path in [*(f"skills/{skill}/SKILL.md" for skill in mine), *licenses]
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
            found += [f"{name}/{path}: registers a hook"] * hooked(made[path])
        needs, wanted = made[MANIFESTS[0]].get("dependencies", []), [] if name == spec["core"] else [core]
        found += [f"{name}/{MANIFESTS[0]}: depends on {needs}, not on {wanted}"] * (needs != wanted)
        listed = (made[MANIFESTS[2]].get("capabilities") or {}).get("skills")
        pairs = sorted((str(item.get("id")), str(item.get("path"))) if isinstance(item, dict) else ("", "")
                       for item in listed) if isinstance(listed, list) else None
        if pairs != [(skill, f"skills/{skill}/SKILL.md") for skill in mine]:
            found.append(f"{name}/{MANIFESTS[2]}: does not list exactly the skills of {name}")
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
    """The git tree of these files, its objects written into repo's store and its own index untouched: what the release
    commits as the collections branch."""
    with tempfile.TemporaryDirectory() as scratch:
        paths, folder = sorted(files), Path(scratch, "files")
        for path in paths:
            (folder / path).parent.mkdir(parents=True, exist_ok=True)
            (folder / path).write_bytes(files[path])
        objects = git(repo, "hash-object", "-w", "--no-filters", "--stdin-paths",
                      stdin="".join(f"{folder / path}\n" for path in paths).encode()).split()
        index = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch, "index"))}
        entries = (f"{'100755' if modes.get(path) == '100755' else '100644'} {sha}\t{path}\n"
                   for path, sha in zip(paths, objects))
        git(repo, "update-index", "--add", "--index-info", env=index, stdin="".join(entries).encode())
        return git(repo, "write-tree", env=index).strip()


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
