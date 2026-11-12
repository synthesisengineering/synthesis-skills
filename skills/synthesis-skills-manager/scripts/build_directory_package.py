"""Build the hook-free package of method skills, for a plugin directory that lists no plugin with lifecycle hooks.

    python3 skills/synthesis-skills-manager/scripts/build_directory_package.py OUT.zip
    python3 skills/synthesis-skills-manager/scripts/build_directory_package.py --check
    python3 skills/synthesis-skills-manager/scripts/build_directory_package.py --changed-since v5.7.0

The package is the skills that assets/directory-package.json lists: every tracked file of each that is not a
test, byte for byte, and one Codex manifest, which is that file's `manifest` with the repository's version. It
holds no hooks folder and registers no hook. Nothing is submitted: the upload is the owner's.

A ZIP is written only when it passes, and the checks read the ZIP: it holds only files of listed skills and the
manifest; each file equals its source; every dependency of a listed skill is listed; the version is the
repository's; and no line claims a hook, a guard or an approval code, or needs the runtime (CLAIMS). A skill
that gains such a line fails here until it leaves the list; its text is never edited to pass.

One line on stdout, and the exit code:
  OUT.zip              built OUT.zip: 32 skills, 234 files, 845390 bytes, version 5.8.0                    0
  --check              ok: 32 skills, 234 files, 845390 bytes, version 5.8.0; nothing written              0
  either, on a defect  refused: 2 problems; nothing written      (then each problem on its own line)       1
  --changed-since TAG  unchanged since TAG: no new submission is due                                       0
                       changed since TAG: the list, synthesis-preplan; a new submission is due             1
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
MANIFEST = ".codex-plugin/plugin.json"  # the repository's, for its version; and the package's own, at the same path
# What no packaged line may say, in the words of the skills that need the runtime: a hook, a guard or an approval
# code at work, or the runtime's command, folder or core. The tests name each phrase, hold it against skills that
# must fail, and pin the ordinary senses (an opening hook, a guard clause) that pass. ACTS: the verbs of enforcement.
ACTS = (r"(?:refus(?:e|es|ed)|block(?:s|ed)?|den(?:y|ies|ied)|stop(?:s|ped)?|check(?:s|ed)?|enforc(?:e|es|ed)"
        r"|catch(?:es)?|holds?|asks?|waits?|lets?|runs?|re-injects?)\b")
CLAIMS = tuple((kind, re.compile(pattern)) for kind, pattern in (
    ("a hook claim",
     r"(?i)\b(?:PreToolUse|SessionStart|UserPromptSubmit)\b|\bhooks\.json\b|core\.hooksPath"
     r"|\b(?:stop|session-start|prompt|lifecycle|git|v5|synthesis)[\s-]hooks?\b|(?<![\w-])commit[\s-]check\b"
     r"|\bhooks?\s+(?:that\s+)?" + ACTS),
    ("a guard claim",
     r"(?i)\b(?:send|messages?|deploy|shell|write|browser|account(?:-routing)?|repo(?:sitory)?|commit|publish"
     r"|pre-tool|synthesis|v5)[\s-]guards?\b|\bthe\s+guards?\b|\bagent[\s-]guardrails\b|\bguards\.py\b"
     r"|\bguards?\s+(?:that\s+)?" + ACTS),
    ("an approval-code claim",
     r"(?i)approve`?\s+`?<code>|\bapproval[\s-]codes?\b|\bsix-character\s+codes?\b"
     r"|\btyp(?:e|es|ed|ing)\s+[`\"']?approve\b"
     r"|\b(?:waits?|waiting|awaiting)\s+(?:for\s+|on\s+)?(?:a|the|their|your|its)\s+codes?\b"),
    ("a runtime need", r"`synthesis\s+[a-z]|\.synthesis/v5\b|\bSYNTHESIS_HOME\b|^\s*(?:from|import)\s+synthesis\b"),
))


class Unreadable(Exception):
    """The list, a manifest, a file or git cannot be read, so nothing can be said about the package (exit 2)."""


def claims(line: str) -> list:
    return [kind for kind, pattern in CLAIMS if pattern.search(line)]


def is_test(path: str) -> bool:
    return "tests" in path.split("/") or path.rsplit("/", 1)[-1].startswith("test_")


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
    listing = git(repo, "ls-files", "-s", "-z", "--", *[f"skills/{name}" for name in spec["skills"]]).split("\0")
    modes = {path: meta[:6] for meta, path in (entry.split("\t", 1) for entry in listing if entry)}
    links = [path for path, mode in modes.items() if mode == "120000"]
    if links:  # followed, one could carry a file from outside its skill, or from the machine that builds
        raise Unreadable(f"{links[0]} is a symbolic link, and a package follows none")
    files = {path: (repo / path).read_bytes() for path in modes if not is_test(path)}
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
        parts, source = path.split("/"), repo / path
        try:
            lines = content.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            lines = []
            found.append(f"{path}: not UTF-8 text, so its lines cannot be read")
        if "hooks" in parts or parts[-1] == "hooks.json" or path == MANIFEST and b'"hooks"' in content:
            found.append(f"{path}: holds or registers a hook")
        if path != MANIFEST and (len(parts) < 3 or parts[0] != "skills" or parts[1] not in listed or is_test(path)):
            found.append(f"{path}: not a file of a listed skill")
        elif path != MANIFEST and (not source.is_file() or source.read_bytes() != content):
            found.append(f"{path}: differs from its source")
        found += [f"{path}:{number}: {', '.join(kinds)}: {line.strip()[:120]}"
                  for number, line in enumerate(lines, 1) for kinds in [claims(line)] if kinds]
    version = read_json(repo / MANIFEST).get("version")
    shipped = json.loads(files.get(MANIFEST, b"{}")).get("version")
    if not version or shipped != version:
        found.append(f"{MANIFEST}: version {shipped}, not the repository's {version}")
    return found


def differing(repo: Path, spec: dict, ref: str) -> list:
    """The list and the files a package would carry, where the checkout differs from `ref`."""
    paths = git(repo, "diff", "--name-only", "--no-renames", "-z", ref, "--", LIST,
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
            changed = sorted({path.split("/")[1] for path in paths if path != LIST})
            changed = (["the list"] if LIST in paths else []) + changed
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
