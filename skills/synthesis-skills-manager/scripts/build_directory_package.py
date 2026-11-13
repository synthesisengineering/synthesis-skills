"""Build the hook-free package of method skills, for a plugin directory that lists no plugin with lifecycle hooks.

    python3 skills/synthesis-skills-manager/scripts/build_directory_package.py OUT.zip
    python3 skills/synthesis-skills-manager/scripts/build_directory_package.py --check
    python3 skills/synthesis-skills-manager/scripts/build_directory_package.py --changed-since v5.7.0

The package is the skills that assets/directory-package.json lists: every tracked file of each that is not a
test, byte for byte; the images kept beside that list in assets/directory-package/, carried as assets/; and one
Codex manifest, which is that file's `manifest` with the repository's version. It holds no hooks folder and
registers no hook. Nothing is submitted: the upload is the owner's.

A ZIP is written only when it passes, and the checks read the ZIP: it holds only files of listed skills, its
images and the manifest; each file equals its source; every dependency of a listed skill is listed; the version
is the repository's; the manifest names a logo and a composer icon among the images, and no image goes unnamed;
and nothing claims a hook, a guard or an approval code at work ("the hook will refuse the send"), sends its reader
to the coordination board ("the board records your claim") or needs the runtime, whose command counts with or
without backticks ("synthesis doctor" in a fenced block) (CLAIMS). A file is read a paragraph at a time, so a
claim that hard wrapping splits is caught, at the line where it begins. A skill that gains such a line fails here
until it leaves the list; its text is never edited to pass.

One line on stdout, and the exit code:
  OUT.zip              built OUT.zip: 32 skills, 235 files, 845797 bytes, version 5.8.0                    0
  --check              ok: 32 skills, 235 files, 845797 bytes, version 5.8.0; nothing written              0
  either, on a defect  refused: 2 problems; nothing written      (then each problem on its own line)       1
  --changed-since TAG  unchanged since TAG: no new submission is due                                       0
                       changed since TAG: the list, its images, synthesis-preplan; a new submission is due 1
  any                  cannot continue: <why>    (the list, a manifest, a file, git or TAG cannot be read,
                       a listed skill holds a symbolic link, or OUT cannot be written)                     2
A build also refuses, with 1, while the list or a file it would carry differs from the last commit: a package
is cut from committed files. `--repo-root DIR` reads another checkout. A wrong command line exits 2 with
argparse's usage. Standard library only; runs on Python 3.9.
"""

import argparse
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
LIST = "skills/synthesis-skills-manager/assets/directory-package.json"
IMAGES = "skills/synthesis-skills-manager/assets/directory-package"  # the package's own images: assets/ in the ZIP
ICONS = ("logo", "composerIcon")  # a package in the Codex format names both; each may have a Dark variant
MANIFEST = ".codex-plugin/plugin.json"  # the repository's, for its version; and the package's own, at the same path
# What no packaged line may say, in the words of the skills that need the runtime: a hook, a guard or an approval
# code at work, or the runtime's command, folder, core or board. The tests name each phrase, hold it against skills
# that must fail, and pin the ordinary senses (a hook that catches the reader, a guard clause) that pass. ACTS: what
# only enforcement does, after a hook, the commit check or a guard with a word between allowed ("will refuse"); BY:
# the passive ("blocked by the hook"). A line break is whitespace to every phrase: `claimed` joins a paragraph.
ACTS = r"(?:\w+\s+)?(?:refus(?:e|es|ed)|block(?:s|ed)?|den(?:y|ies|ied)|enforc(?:e|es|ed)|re-injects?)\b"
BY = r"\b(?:refused|blocked|denied|enforced)\s+(?:\w+\s+)?by\s+(?:the|an?|its|each|every)\s+(?:[\w-]+\s+)?"
COMMANDS = ("claim|release|journal|index|who|msg|worktree|inbox|wait|sends|use|brief|resume|handoff|sessions"
            "|approvals|install|uninstall|doctor|version")  # the subcommands of synthesis/cli.py
CLAIMS = tuple((kind, re.compile(pattern)) for kind, pattern in (
    ("a hook claim",
     r"(?i)\b(?:PreToolUse|SessionStart|UserPromptSubmit)\b|\bhooks\.json\b|core\.hooksPath"
     r"|\b(?:stop|session-start|prompt|lifecycle|v5|synthesis)[\s-]hooks?\b|(?:\bthe\s+git\s|\bgit-)hooks?\b"
     r"|(?:\bhooks?|(?<![\w-])commit[\s-]checks?)\s+" + ACTS + "|" + BY + r"(?:hooks?|commit[\s-]checks?)\b"),
    ("a guard claim",
     r"(?i)\b(?:send|messages?|deploy|shell|browser|account(?:-routing)?|repo(?:sitory)?|commit|publish"
     r"|pre-tool|synthesis|v5)[\s-]guards?\b|\bthe\s+guards?\b(?!\s+clauses?\b)|\bagent[\s-]guardrails\b"
     r"|\bguards\.py\b|\bguards?\s+" + ACTS + "|" + BY + r"guards?\b"),
    ("an approval-code claim",
     r"(?i)approve`?\s+`?<code>|\bapproval[\s-]codes?\b|\bsix-character\s+codes?\b"
     r"|\btyp(?:e|es|ed|ing)\s+[`\"']?approve\b"
     r"|\b(?:waits?|waiting|awaiting)\s+(?:for\s+|on\s+)?(?:a|the|their|your|its)\s+codes?\b"),
    ("a runtime need",
     r"`synthesis\s+[a-z]|\.synthesis/v5\b|~/\.synthesis/?(?![\w./-])|\bSYNTHESIS_HOME\b"
     r"|(?:(?<![^\n])[ \t]*(?:\$\s+)?|\bpython3?\s+-m\s+)synthesis\s+(?:" + COMMANDS + r")\b"
     r"|(?<![^\n])[ \t]*(?:from|import)\s+synthesis\b|(?i:\b(?:coordination\s+board|board\s+(?:claims?|rows?))\b)"
     r"|(?i:\bboard\s+(?:records?|holds?|shows?|lists?|keeps?|grants?|refuses?)\s+(?:\w+\s+){0,2}claims?\b)"
     r"|(?i:\breleas(?:e|es|ed|ing)\s+(?:the|its|your|their|this\s+session's|those)\s+claims?\b)"),
))


class Unreadable(Exception):
    """The list, a manifest, a file or git cannot be read, so nothing can be said about the package (exit 2)."""


def claims(text: str) -> list:
    """The kinds of claim a text makes, in the order of CLAIMS."""
    return [kind for kind, pattern in CLAIMS if pattern.search(text)]


def claimed(lines: list) -> list:
    """(line number, kinds, line) for each line on which a claim begins. The lines are read a paragraph at a time
    (consecutive lines that are not blank, each stripped, joined by a line break), so a claim that hard wrapping
    splits is read whole; it is reported at the line where it begins."""
    found, start = {}, 0
    for end in range(len(lines) + 1):
        if end == len(lines) or not lines[end].strip():
            text = "\n".join(line.strip() for line in lines[start:end])
            for kind, pattern in CLAIMS:
                for match in pattern.finditer(text):
                    kinds = found.setdefault(start + text.count("\n", 0, match.start()), [])
                    kinds += [kind] * (kind not in kinds)
            start = end + 1
    return [(at + 1, kinds, lines[at]) for at, kinds in sorted(found.items())]


def is_test(path: str) -> bool:
    return "tests" in path.split("/") or path.rsplit("/", 1)[-1].startswith("test_")


def source(path: str) -> str:
    """Where a packaged file is kept in the checkout: an image beside the list, anything else under its own name."""
    return IMAGES + path[len("assets"):] if path.startswith("assets/") else path


def depends_on(skill_md: str) -> list:
    """The names in a skill's frontmatter `depends_on`, written as a flow list or as a block list."""
    front = re.match(r"---\n(.*?)\n---\n", skill_md, re.S)
    found = re.search(r"^depends_on:(.*(?:\n[ \t]*-.*)*)", front.group(1) if front else "", re.M)
    return re.findall(r"[A-Za-z][\w.-]*", found.group(1)) if found else []


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, encoding="utf-8", errors="replace")
    if done.returncode:
        raise Unreadable(f"git {args[0]}: {done.stderr.strip() or 'failed'}")
    return done.stdout


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Unreadable(f"cannot read {path}: {error}")


def read_list(repo: Path) -> dict:
    spec = read_json(repo / LIST)
    if not (isinstance(spec, dict) and isinstance(spec.get("skills"), list) and spec["skills"]
            and isinstance(spec.get("manifest"), dict)):
        raise Unreadable(f"{repo / LIST} needs a `skills` list that names a skill and a `manifest` object")
    return spec


def build(repo: Path, spec: dict) -> bytes:
    """The package as ZIP bytes. The same checkout gives the same bytes: names in order, one date, and the
    executable bit as git records it."""
    listing = git(repo, "ls-files", "-s", "-z", "--", IMAGES,
                  *[f"skills/{name}" for name in spec["skills"]]).split("\0")
    modes = {path: meta[:6] for meta, path in (entry.split("\t", 1) for entry in listing if entry)}
    links = [path for path, mode in modes.items() if mode == "120000"]
    if links:  # followed, one could carry a file from outside its skill, or from the machine that builds
        raise Unreadable(f"{links[0]} is a symbolic link, and a package follows none")
    files = {("assets" + path[len(IMAGES):] if path.startswith(IMAGES + "/") else path): (repo / path).read_bytes()
             for path in modes if not is_test(path)}
    fields = dict(spec["manifest"])
    made = {"name": fields.pop("name", ""), "version": read_json(repo / MANIFEST).get("version"), **fields}
    files[MANIFEST] = (json.dumps(made, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as package:
        for path in sorted(files):
            entry = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if modes.get(path) == "100755" else 0o100644) << 16
            package.writestr(entry, files[path])
    return data.getvalue()


def verify(repo: Path, spec: dict, data: bytes) -> list:
    """Each reason this ZIP may not ship, read from the ZIP itself; empty when it may."""
    listed, found = set(spec["skills"]), []
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        files = {name: package.read(name) for name in package.namelist()}
    for name in spec["skills"]:
        skill = files.get(f"skills/{name}/SKILL.md")
        if skill is None:
            found.append(f"skills/{name}/SKILL.md: missing, so {name} is no skill of this checkout")
        found += [f"skills/{name}/SKILL.md: depends on {need}, which is not on the list"
                  for need in depends_on((skill or b"").decode("utf-8", "replace")) if need not in listed]
    for path, content in sorted(files.items()):
        parts, kept, image = path.split("/"), repo / source(path), path.startswith("assets/")
        try:
            lines = content.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            lines = []
            if not image:  # a raster image has no lines to read
                found.append(f"{path}: not UTF-8 text, so its lines cannot be read")
        if "hooks" in parts or parts[-1] == "hooks.json" or path == MANIFEST and b'"hooks"' in content:
            found.append(f"{path}: holds or registers a hook")
        if path != MANIFEST and not image and (len(parts) < 3 or parts[0] != "skills" or parts[1] not in listed
                                               or is_test(path)):
            found.append(f"{path}: not a file of a listed skill")
        elif path != MANIFEST and (not kept.is_file() or kept.read_bytes() != content):
            found.append(f"{path}: differs from its source")
        found += [f"{path}:{number}: {', '.join(kinds)}: {line.strip()[:120]}"
                  for number, kinds, line in claimed(lines)]
    version, manifest = read_json(repo / MANIFEST).get("version"), json.loads(files.get(MANIFEST, b"{}"))
    if not version or manifest.get("version") != version:
        found.append(f"{MANIFEST}: version {manifest.get('version')}, not the repository's {version}")
    interface = manifest.get("interface") if isinstance(manifest.get("interface"), dict) else {}
    named = {field: interface.get(field) for icon in ICONS for field in (icon, icon + "Dark")}
    for field, value in named.items():
        if value in (None, ""):  # a Dark variant is optional
            found += [f"{MANIFEST}: interface.{field} is missing: a package names its logo and its composer icon"
                      ] * (field in ICONS)
        elif not (isinstance(value, str) and value.startswith("./assets/") and value[2:] in files):
            found.append(f"{MANIFEST}: interface.{field} names {value}, which is no ./assets/ path to an image the "
                         f"package holds")
    found += [f"{path}: no image field of the manifest names it" for path in sorted(files)
              if path.startswith("assets/") and "./" + path not in named.values()]
    return found


def differing(repo: Path, spec: dict, ref: str) -> list:
    """The list and the files a package would carry, where the checkout differs from `ref`."""
    paths = git(repo, "diff", "--name-only", "--no-renames", "-z", ref, "--", LIST, IMAGES,
                *[f"skills/{name}" for name in spec["skills"]]).split("\0")
    return [path for path in paths if path and not is_test(path)]


def count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build_directory_package.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("out", nargs="?", type=Path, help="the ZIP to write")
    parser.add_argument("--check", action="store_true", help="verify the package and write nothing")
    parser.add_argument("--changed-since", metavar="TAG", help="name what changed in the package since this tag")
    parser.add_argument("--repo-root", type=Path, default=REPO)
    args = parser.parse_args(argv)
    if sum(map(bool, (args.out, args.check, args.changed_since))) != 1:
        parser.error("give the ZIP to write, or --check, or --changed-since TAG")
    repo, tag = args.repo_root.resolve(), args.changed_since
    try:
        spec = read_list(repo)
        if tag:
            paths = differing(repo, spec, f"refs/tags/{tag}")
            images = [path for path in paths if path.startswith(IMAGES + "/")]
            changed = sorted({path.split("/")[1] for path in paths if path != LIST and path not in images})
            changed = (["the list"] if LIST in paths else []) + (["its images"] if images else []) + changed
            print(f"changed since {tag}: {', '.join(changed)}; a new submission is due" if changed
                  else f"unchanged since {tag}: no new submission is due")
            return 1 if changed else 0
        data = build(repo, spec)
        found = verify(repo, spec, data)
        if args.out:
            found = [f"{path}: differs from the last commit; a package is cut from committed files"
                     for path in differing(repo, spec, "HEAD")] + found
        if found:
            print("\n".join([f"refused: {count(len(found), 'problem')}; nothing written"] + found))
            return 1
        if args.out:
            args.out.write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            holds = (f"{count(len(spec['skills']), 'skill')}, {count(len(package.namelist()), 'file')}, "
                     f"{len(data)} bytes, version {read_json(repo / MANIFEST)['version']}")
        print(f"built {args.out}: {holds}" if args.out else f"ok: {holds}; nothing written")
        return 0
    except (Unreadable, OSError) as error:
        print(f"cannot continue: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
