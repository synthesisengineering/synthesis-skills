#!/usr/bin/env python3
"""Build an organization's knowledge-base plugin for Claude and ChatGPT from its OKF source folder.

    python3 build_plugin.py --config <file> --source <folder> --out <folder> [--commit <sha>]

Every organization-specific value comes from the config file (templates/kb-plugin.example.json
shows each setting), the exclusion list it names and, when it names them, the organization's own
SKILL.md and README.md templates; otherwise the generic ones in templates/ are used. The output is
the published tree references/published-layout.md describes; publish_plugin.sh pushes it.

The build checks everything before it writes anything, and stops with every problem listed when a
file it would publish has no OKF front matter with a `type`, holds text addressed to an AI
assistant, is a symbolic link or is not UTF-8 text; when the source folder differs from the commit
its stamps would name; when the plugin is over its limits; or when a template leaves a placeholder
unfilled. It replaces only an empty folder or its own previous output. It prints
`Built <plugin> <version> from <sha7> (<date>) into <out>`, the file count and size, and each file
it left out with the glob that matched. Exit 1 on a refusal, 2 on a usage error.
Standard library only, Python 3.9 or newer, so a CI image needs nothing installed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[2]), str(HERE / "connector")]  # the plugin root (synthesis/) and the connector
from synthesis import yamlish  # noqa: E402
from kb_connector.corpus import split_front_matter  # noqa: E402  the connector reads what this build writes

TEMPLATES = HERE.parent / "templates"
BUILD_ENTRIES = {".claude-plugin", ".agents", "README.md", "plugins"}  # all a build writes at its top
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SEMVER = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
PLACEHOLDER = re.compile(r"\{\{([A-Z][A-Z0-9_]*)(\|quoted)?\}\}")
VERSION_PARTS = {"date", "time", "count"}
KINDS = {str: "text", int: "a whole number", list: "a list", dict: "an object"}
BUILT_IN_VALUES = {"PLUGIN_NAME", "DISPLAY_NAME", "PLUGIN_DESCRIPTION", "SKILL_DESCRIPTION", "AUTHOR", "SOURCE_REPO",
                   "SOURCE_PATH", "COMMIT", "COMMIT_SHORT", "COMMIT_DATE", "VERSION", "FILE_COUNT", "EXCLUDE_FILE",
                   "CORRECTIONS_CONTACT", "INDEX"}
# Claude's limits for an organization plugin and the Agent Skills description limit; a config can lower or raise them.
DEFAULT_LIMITS = {"max_files": 5000, "max_bytes": 200 * 1024 * 1024, "max_skill_description": 1024}
# Text that speaks to an AI assistant. A knowledge file describes the organization; a line like these would be
# read as an instruction by every assistant that loads the plugin, so the build stops and a person decides.
DEFAULT_PATTERNS = [
    r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}?\b(?:previous|prior|above|earlier|preceding|all)\b"
    r"[^.\n]{0,40}?\binstructions?\b",
    r"\byou are (?:now )?(?:an? |the )?(?:ai|assistant|chatbot|language model|llm)\b",
    r"\bsystem prompt\b",
    r"\b(?:do not|don't|never) (?:tell|reveal|disclose|mention)\b[^.\n]{0,40}?\bthe user\b",
    r"\bas an ai(?: language model)?\b",
]
# Each setting: (type, required). A dict type is a section whose settings are checked the same way.
SCHEMA = {
    "source_repository": (str, True), "exclude_file": (str, True), "version": (str, False),
    "corrections_contact": (str, False), "template_values": (dict, False),
    "marketplace": ({"name": (str, True), "display_name": (str, False), "description": (str, False),
                     "owner": (str, False)}, True),
    "plugin": ({"name": (str, True), "display_name": (str, True), "description": (str, True),
                "skill_description": (str, True), "author": (str, True), "developer": (str, False),
                "category": (str, False), "policy": (dict, False)}, True),
    "templates": ({"skill": (str, False), "readme": (str, False)}, False),
    "index": ({"sections": (list, False), "other_heading": (str, False), "date_field": (str, False)}, False),
    "lint": ({"patterns": (list, False), "extra_patterns": (list, False)}, False),
    "limits": ({key: (int, False) for key in DEFAULT_LIMITS}, False),
}


def die(message: str):
    print(f"build_plugin: {message}", file=sys.stderr)
    sys.exit(1)


def check_shape(data, schema: dict, where: str, problems: list):
    """Every setting is known, present when required, of its type, and a text setting is one non-empty line."""
    if not isinstance(data, dict):
        problems.append(f"{where.rstrip('.') or 'the config'}: expected an object")
        return
    problems += [f"{where}{key}: not a setting this build knows" for key in sorted(set(data) - set(schema))]
    for key, (kind, required) in schema.items():
        value = data.get(key)
        if key not in data:
            problems += [f"{where}{key}: required"] if required else []
        elif isinstance(kind, dict):
            check_shape(value, kind, f"{where}{key}.", problems)
        elif not isinstance(value, kind) or isinstance(value, bool):
            problems.append(f"{where}{key}: expected {KINDS[kind]}")
        elif kind is str and (not value.strip() or "\n" in value):
            problems.append(f"{where}{key}: expected one non-empty line")
        elif kind is int and value < 1:
            problems.append(f"{where}{key}: expected a positive number")


def load_config(path: Path) -> dict:
    """The config with its defaults filled in; every problem in it is reported at once."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        die(f"cannot read the config {path}: {error}")
    problems, compiled = [], []
    check_shape(config, SCHEMA, "", problems)
    if not problems:
        plugin, market, lint = config["plugin"], config["marketplace"], config.get("lint", {})
        problems += [f"{where}.name: {item['name']!r} is not a lowercase, hyphenated name of at most 64 characters"
                     for where, item in (("plugin", plugin), ("marketplace", market))
                     if not NAME.match(item["name"]) or len(item["name"]) > 64]
        if "`" in config["source_repository"]:
            problems.append("source_repository: a backtick would break the provenance stamp")
        problems += [f"version: {{{part}}} is not one of {{date}}, {{time}}, {{count}}"
                     for part in sorted(set(re.findall(r"\{(\w*)\}", config.get("version", ""))) - VERSION_PARTS)]
        for number, section in enumerate(config.get("index", {}).get("sections", []), 1):
            if not (isinstance(section, dict) and set(section) == {"prefix", "heading"}
                    and all(isinstance(v, str) and v.strip() and "\n" not in v for v in section.values())):
                problems.append(f"index.sections[{number}]: expected {{\"prefix\": text, \"heading\": text}}")
        for key, value in config.get("template_values", {}).items():
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not isinstance(value, str) or key in BUILT_IN_VALUES:
                problems.append(f"template_values.{key}: expected an UPPER_CASE name of its own with a text value")
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in plugin.get("policy", {}).items()):
            problems.append("plugin.policy: expected text values")
        patterns = lint.get("patterns", DEFAULT_PATTERNS) + lint.get("extra_patterns", [])
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern if isinstance(pattern, str) else None, re.I))
            except (re.error, TypeError) as error:
                problems.append(f"lint: {pattern!r} is not a regular expression ({error})")
        if not patterns:
            problems.append("lint: no patterns left; the check for text addressed to an assistant cannot be turned off")
    if problems:
        die(f"the config {path} has problems:\n  " + "\n  ".join(problems))
    plugin, market = config["plugin"], config["marketplace"]
    plugin.setdefault("developer", plugin["author"])
    plugin.setdefault("category", "Productivity")
    plugin.setdefault("policy", {"installation": "AVAILABLE", "authentication": "ON_INSTALL"})
    for key, default in (("display_name", plugin["author"]), ("owner", plugin["author"]),
                         ("description", plugin["description"])):
        market.setdefault(key, default)
    config.setdefault("version", "1.{date}.{time}")
    config["limits"] = {**DEFAULT_LIMITS, **config.get("limits", {})}
    config["patterns"] = compiled
    return config


def glob_to_regex(pattern: str):
    """A glob relative to the source folder as an anchored regex: `**/` is zero or more folders, `**` anything,
    `*` and `?` stay inside one folder name."""
    out, i = [], 0
    while i < len(pattern):
        for token, regex in (("**/", "(?:.*/)?"), ("**", ".*"), ("*", "[^/]*"), ("?", "[^/]")):
            if pattern.startswith(token, i):
                out.append(regex)
                i += len(token)
                break
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def read_excludes(path: Path) -> list:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        die(f"cannot read the exclusion list {path}: {error}")
    return [(line, glob_to_regex(line)) for line in (raw.strip() for raw in lines) if line and not line.startswith("#")]


def git(repo: Path, *args: str, failure: str = "") -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode != 0:
        die(failure or f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def collect(source: Path, excludes: list):
    """(files to publish, [(file, why)] left out, linked files). README.md and hidden paths are never published,
    and symbolic links are never followed: one could reach a key on the build machine."""
    included, left_out, links = [], [], []
    for folder, dirs, names in os.walk(source):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        base = Path(folder)
        left_out += [((base / d).relative_to(source).as_posix(), "a link to a folder, not followed")
                     for d in dirs if (base / d).is_symlink()]
        for name in names:
            rel = (base / name).relative_to(source).as_posix()
            if name.startswith(".") or name == "README.md" or not name.endswith(".md"):
                continue
            glob = next((g for g, regex in excludes if regex.match(rel)), None)
            if glob:
                left_out.append((rel, glob))
            else:
                (links if (base / name).is_symlink() else included).append(rel)
    return sorted(included), sorted(left_out), sorted(links)


def one_line(value) -> str:
    return "" if value is None or isinstance(value, (dict, list)) else " ".join(str(value).split())


def build_index(entries: list, sections: list, other: str) -> str:
    """Every published file as a link with its date and description, grouped by the first section prefix it fits."""
    groups = {heading: [] for _, heading in sections}
    for entry in entries:
        heading = next((h for prefix, h in sections if entry["rel"].startswith(prefix)), other)
        groups.setdefault(heading, []).append(entry)
    lines = []
    for heading, items in groups.items():
        lines += [f"### {heading}", ""] if items else []
        for item in items:
            target = f"references/{item['rel']}"
            target = f"<{target}>" if re.search(r"[\s()<>]", target) else target
            title = item["title"].replace("[", "\\[").replace("]", "\\]")
            updated = f" (updated {item['date']})" if item["date"] else ""
            lines.append(f"- [{title}]({target}){updated}{': ' + item['description'] if item['description'] else ''}")
        lines += [""] if items else []
    return "\n".join(lines).rstrip()  # the template ends the line


def fill(template: str, values: dict, name: str) -> str:
    """`{{KEY}}` becomes the value and `{{KEY|quoted}}` a double-quoted YAML string, in one pass, so a value is never
    read as a placeholder itself."""
    missing = set()

    def one(match):
        if match.group(1) not in values:
            missing.add(match.group(0))
            return match.group(0)
        value = values[match.group(1)]
        return json.dumps(value, ensure_ascii=False) if match.group(2) else value
    text = PLACEHOLDER.sub(one, template)
    if missing:
        die(f"the {name} template leaves placeholders unfilled: {', '.join(sorted(missing))}")
    return text


def guard_output(out: Path, top: Path, source: Path) -> Path:
    """The folder the build may replace: empty, new, or holding only a previous build."""
    out = out.resolve()
    if out in (Path(out.anchor), Path.home().resolve(), source) or out in source.parents or source in out.parents \
            or top / ".git" in (out, *out.parents):
        die(f"refusing to use {out} as the output folder")
    if out.exists():
        entries = {p.name for p in out.iterdir()} if out.is_dir() else {None}
        if entries and not (entries <= BUILD_ENTRIES and (out / ".claude-plugin" / "marketplace.json").is_file()):
            die(f"{out} holds files that are not a previous build of this plugin; choose an empty or new folder")
    return out


def dump(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def resolve_commit(top: Path, commit: str, version_format: str):
    """(full sha, version, commit date). Dates are UTC, so a version never steps back for a time zone."""
    sha = git(top, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}",
              failure=f"{commit!r} is not a commit in {top}").strip()
    when = datetime.fromtimestamp(int(git(top, "show", "-s", "--format=%ct", sha)), timezone.utc)
    parts = {"date": when.strftime("%Y%m%d"), "time": str(int(when.strftime("%H%M")))}
    if "{count}" in version_format:
        if git(top, "rev-parse", "--is-shallow-repository").strip() == "true":
            die("the version uses {count}, which needs the whole history, and this clone is shallow")
        parts["count"] = git(top, "rev-list", "--count", sha).strip()
    version = re.sub(r"\{(\w+)\}", lambda m: parts[m.group(1)], version_format)
    if not SEMVER.match(version):
        die(f"the version format {version_format!r} gives {version!r}, not MAJOR.MINOR.PATCH")
    return sha, version, when.strftime("%Y-%m-%d")


def uncommitted(top: Path, prefix: str, sha: str, published: list) -> list:
    """The stamps name the commit, so the files read must be that commit's (binding rule 2)."""
    changed = [p for p in git(top, "diff", "--name-only", "-z", sha, "--", prefix).split("\0") if p]
    tracked = set(git(top, "ls-tree", "-r", "--name-only", "-z", sha, "--", prefix).split("\0"))
    return [f"{path}: differs from commit {sha[:7]}; commit it first" for path in changed] + \
        [f"{path}: not in commit {sha[:7]}; commit it first" for path in published if path not in tracked]


def read_knowledge(source: Path, included: list, label, stamp, config: dict):
    """(index entries, published text by path under references/, problems) for every file to publish."""
    entries, published, problems = [], {}, []
    date_field = config.get("index", {}).get("date_field", "timestamp")
    for rel in included:
        try:
            text = (source / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError:
            problems.append(f"{label(rel)}: not UTF-8 text")
            continue
        problems += [f"{label(rel)}:{number}: {line.strip()[:120]}" for number, line in enumerate(text.splitlines(), 1)
                     if any(pattern.search(line) for pattern in config["patterns"])]
        front, body = split_front_matter(text)
        try:
            fields = yamlish.load_mapping(front)
        except ValueError as error:
            problems.append(f"{label(rel)}: front matter not readable: {error}")
            continue
        if not front.strip():
            problems.append(f"{label(rel)}: no front matter; OKF needs one with a `type`")
        elif not (isinstance(fields.get("type"), str) and fields["type"].strip()):
            problems.append(f"{label(rel)}: the front matter has no `type`")
        heading = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
        entries.append({"rel": rel, "title": one_line(fields.get("title")) or heading or Path(rel).stem,
                        "description": one_line(fields.get("description")),
                        "date": one_line(fields.get(date_field))[:10]})
        published[rel] = f"---\n{front}---\n\n{stamp(label(rel))}\n\n{body.lstrip(chr(10))}"
    return entries, published, problems


def render_skill(template: str, values: dict, name: str, limit: int) -> str:
    """SKILL.md from its template, with a name that matches its folder and a description within the limit."""
    skill = fill(template, values, "SKILL.md")
    try:
        meta = yamlish.load_mapping(split_front_matter(skill)[0])
    except ValueError as error:
        die(f"the SKILL.md template's front matter is not readable: {error}")
    description = meta.get("description")
    if meta.get("name") != name:
        die(f"SKILL.md's name must be the plugin's name, {name!r}, which is also its folder's name")
    if not (isinstance(description, str) and description.strip()):
        die("SKILL.md needs a description: it tells the assistant when to use the knowledge")
    if len(description) > limit:
        die(f"SKILL.md's description is {len(description)} characters, over {limit}")
    return skill


def manifests(plugin: dict, market: dict, version: str) -> dict:
    """The plugin's three manifests and the two marketplaces, by path in the published tree."""
    name, base = plugin["name"], f"plugins/{plugin['name']}"
    manifest = {"name": name, "version": version, "description": plugin["description"],
                "author": {"name": plugin["author"]}}
    codex = {**manifest, "skills": "./skills/", "interface": {"displayName": plugin["display_name"],
             "shortDescription": plugin["description"], "developerName": plugin["developer"]}}
    return {
        f"{base}/.claude-plugin/plugin.json": dump(manifest), f"{base}/plugin.json": dump(manifest),
        f"{base}/.codex-plugin/plugin.json": dump(codex),
        ".claude-plugin/marketplace.json": dump({
            "name": market["name"], "owner": {"name": market["owner"]},
            "metadata": {"description": market["description"], "version": version},
            "plugins": [{"name": name, "source": f"./{base}", "description": plugin["description"],
                         "version": version}]}),
        ".agents/plugins/marketplace.json": dump({
            "name": market["name"], "interface": {"displayName": market["display_name"]},
            "plugins": [{"name": name, "source": {"source": "local", "path": f"./{base}"}, "policy": plugin["policy"],
                         "category": plugin["category"]}]}),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build an organization's knowledge-base plugin from OKF markdown.")
    parser.add_argument("--config", required=True, help="the organization's build config (JSON)")
    parser.add_argument("--source", required=True, help="the knowledge base's OKF folder, inside its git repository")
    parser.add_argument("--out", required=True, help="an empty or new folder, or a previous build to replace")
    parser.add_argument("--commit", default="HEAD", help="the source commit the stamps name (default HEAD)")
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve()
    config, here = load_config(config_path), config_path.parent
    plugin, limits, index = config["plugin"], config["limits"], config.get("index", {})
    source = Path(args.source).resolve()
    if not source.is_dir():
        die(f"source folder {source} not found")
    top = git(source, "rev-parse", "--show-toplevel", failure=f"{source} is not in a git repository").strip()
    top = Path(top).resolve()
    prefix = source.relative_to(top).as_posix()
    out = guard_output(Path(args.out), top, source)
    sha, version, commit_date = resolve_commit(top, args.commit, config["version"])

    def label(rel):  # a file's path in the source repository
        return rel if prefix == "." else f"{prefix}/{rel}"

    def stamp(path):  # the connector parses this line (kb_connector/corpus.py, STAMP)
        return f"> Published from `{path}` in {config['source_repository']} at commit `{sha[:7]}` ({commit_date})."
    exclude_path = (here / config["exclude_file"]).resolve()
    excludes = read_excludes(exclude_path)
    included, left_out, links = collect(source, excludes)
    if not included and not links:
        die("no knowledge files left after the exclusions")
    problems = [f"{label(rel)}: a symbolic link; only regular files are published" for rel in links]
    problems += uncommitted(top, prefix, sha, [label(rel) for rel in included])
    entries, published, more = read_knowledge(source, included, label, stamp, config)
    if problems + more:
        die("the build stopped; nothing was written:\n  " + "\n  ".join(problems + more))

    name = plugin["name"]
    skill_dir = f"plugins/{name}/skills/{name}"
    sections = [(s["prefix"], s["heading"]) for s in index.get("sections", [])] or \
        [(f"{folder}/", folder) for folder in sorted({rel.split("/")[0] for rel in included if "/" in rel})]
    values = {"PLUGIN_NAME": name, "DISPLAY_NAME": plugin["display_name"], "PLUGIN_DESCRIPTION": plugin["description"],
              "SKILL_DESCRIPTION": plugin["skill_description"], "AUTHOR": plugin["author"],
              "SOURCE_REPO": config["source_repository"], "SOURCE_PATH": prefix, "COMMIT": sha,
              "COMMIT_SHORT": sha[:7], "COMMIT_DATE": commit_date, "VERSION": version,
              "FILE_COUNT": str(len(entries)),
              "EXCLUDE_FILE": exclude_path.relative_to(top).as_posix() if top in exclude_path.parents
              else exclude_path.name,
              "CORRECTIONS_CONTACT": config.get("corrections_contact", "the people who maintain this knowledge base"),
              "INDEX": build_index(entries, sections, index.get("other_heading", "Other")),
              **config.get("template_values", {})}
    chosen = config.get("templates", {})  # the organization's own, else the generic ones beside this script
    try:
        skill, readme = (here / chosen[kind] if kind in chosen else TEMPLATES / f"{file}.tmpl"
                         for kind, file in (("skill", "SKILL.md"), ("readme", "README.md")))
        skill, readme = skill.read_text(encoding="utf-8"), readme.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        die(f"cannot read a template: {error}")
    files = {f"{skill_dir}/references/{rel}": text for rel, text in published.items()}
    files[f"{skill_dir}/SKILL.md"] = render_skill(skill, values, name, limits["max_skill_description"])
    files["README.md"] = fill(readme, values, "README.md")
    files.update(manifests(plugin, config["marketplace"], version))

    plugin_files = [path for path in files if path.startswith(f"plugins/{name}/")]
    size = sum(len(files[path].encode("utf-8")) for path in plugin_files)
    if len(plugin_files) > limits["max_files"] or size > limits["max_bytes"]:
        die(f"the plugin would be {len(plugin_files)} files and {size:,} bytes, over the limits of "
            f"{limits['max_files']} files and {limits['max_bytes']:,} bytes; nothing was written")

    if out.exists():
        shutil.rmtree(out)
    for path, text in files.items():
        (out / path).parent.mkdir(parents=True, exist_ok=True)
        (out / path).write_text(text, encoding="utf-8")
    print(f"Built {name} {version} from {sha[:7]} ({commit_date}) into {out}")
    print(f"  {len(entries)} knowledge files, {size:,} bytes")
    for rel, why in left_out:
        print(f"  left out {label(rel)}  ({why})")
    for glob, regex in excludes:
        if not any(regex.match(rel) for rel, _ in left_out):
            print(f"  note: the exclusion {glob!r} matched no file")


if __name__ == "__main__":
    main()
