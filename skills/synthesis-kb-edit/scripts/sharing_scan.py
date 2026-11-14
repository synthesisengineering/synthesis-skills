#!/usr/bin/env python3
"""The sharing policy's backstop: the organization's own phrases, in the lines a change adds to a knowledge base.

It reads the policy path and the phrases from the contract (`confidentiality.sharing_policy` and
`confidentiality.backstop_phrases` in `.agents/knowledge-base.yaml`) and judges lines under the bundle, never the
policy or the contract, which name what they keep out. A hit is printed as its file, line and phrase, never the rest
of the line, which may be the very thing that should not be shown. It cannot see meaning: the editor and the reviewer
apply the policy, and this catches a phrase they missed. The plugin ships no phrases, so with none named it refuses to
run. It needs the standard library and the checkout's own YAML reader (through kb_config.py beside it), so it runs by
path from a checkout pinned to a tag, with nothing installed.

    sharing_scan.py <repo-root> --range <base>...<head>   the lines the range adds (a review request, a pipeline)
    sharing_scan.py <repo-root> --staged                   the lines the index adds (a commit hook)
    sharing_scan.py <repo-root> <path>...                  every line of these files, and of the files in these folders

Exit 0 when nothing is held, 1 when a line is held, 2 when it cannot run.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))  # kb_config beside it, in isolated mode too
import kb_config  # noqa: E402  the contract's reader and checks; it imports the checkout's YAML reader

SHORT = 5  # a phrase this long or shorter matches only as a whole word: "opal" never holds "opalescent"
HUNK = re.compile(rb"@@ -\d+(?:,\d+)? \+(\d+)")


class Refused(Exception):
    """The scan cannot run; the message says why."""


def matcher(phrase: str):
    """Where the phrase starts a word, in any letter case, with any run of spaces between its words. A short phrase
    must also end a word; a longer one may run on ("zephyr ledger" holds "zephyr ledgers")."""
    words = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.compile(r"(?<!\w)" + words + (r"(?!\w)" if len(phrase.strip()) <= SHORT else ""), flags=re.IGNORECASE)


def read_contract(repo: Path):
    """The bundle, the policy and the phrases, or Refused naming what is missing and what to do."""
    config = kb_config.load_config(repo, None)[1]
    errors, contract = kb_config.validate_config(config), kb_config.CONFIG_RELATIVE
    if errors:
        raise Refused(f"{contract} is invalid: {'; '.join(errors)}")
    block = config["confidentiality"]
    policy = block.get("sharing_policy")
    if not policy:
        raise Refused(f"{contract} names no sharing policy (confidentiality.sharing_policy): adopt one with "
                      "kb_config.py adopt-sharing-policy <repo-root>")
    if not kb_config.resolve_inside(repo, policy).is_file():
        raise Refused(f"the sharing policy {policy} named in the contract is not there")
    if not block.get("backstop_phrases"):
        raise Refused(f"{contract} names no backstop phrases (confidentiality.backstop_phrases): the plugin ships "
                      "none, so list this organization's own there; nothing was scanned")
    return PurePosixPath(config["bundle_path"]).as_posix(), PurePosixPath(policy).as_posix(), block["backstop_phrases"]


def git(repo: Path, *args) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), "--literal-pathspecs", *args], capture_output=True)
    if done.returncode:
        raise Refused(done.stderr.decode("utf-8", "replace").strip() or f"git {args[0]} failed")
    return done.stdout


def added(repo: Path, which: str, bundle: str) -> dict:
    """{path: [(line number, text)], or None for a file git reads as binary} for the lines the range or the index adds
    under the bundle. A move is read as a deletion and an addition, so a file moved in from outside it is judged whole."""
    found = {}
    for name in filter(None, git(repo, "diff", "--name-only", "-z", "--no-renames", "--diff-filter=d", which, "--",
                                 bundle).split(b"\0")):
        path, lines, number = name.decode("utf-8", "replace"), [], 0
        for raw in git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", which,
                       "--", name).split(b"\n"):
            hunk = HUNK.match(raw)
            if hunk:
                number = int(hunk.group(1))
            elif number and raw.startswith(b"+"):  # an added line; the header's +++ comes before the first hunk
                lines.append((number, raw[1:].decode("utf-8", "replace")))
                number += 1
            elif raw.startswith(b"Binary files "):
                lines = None
        found[path] = lines
    return found


def whole(repo: Path, given: list) -> dict:
    """{path: [(line number, text)], or None for a file holding a NUL byte, git's test for binary} for every line of
    each named file, and of every file in each named folder."""
    found = {}
    for relative in given:
        target = kb_config.resolve_inside(repo, relative)  # a path that escapes the repository raises
        if not target.exists():
            raise Refused(f"{relative} is not there")
        for file in sorted(p for p in target.rglob("*") if p.is_file()) if target.is_dir() else [target]:
            path = file.relative_to(repo).as_posix()
            if ".git" not in PurePosixPath(path).parts:
                data = file.read_bytes()
                found[path] = None if b"\0" in data else list(enumerate(data.decode("utf-8", "replace").split("\n"), 1))
    return found


def unjudged(path: str, lines, bundle: str, policy: str) -> str:
    """Why a path is not judged, or nothing when it is."""
    if path in (policy, kb_config.CONFIG_RELATIVE.as_posix()):
        return "the policy and the contract name what they keep out"
    if bundle != "." and path != bundle and not path.startswith(bundle + "/"):
        return f"outside the bundle ({bundle})"
    return "not text (the scan reads text only)" if lines is None else ""


def count(number: int, word: str) -> str:
    return f"{number} {word}{'' if number == 1 else 's'}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The sharing policy's backstop phrase scan.")
    parser.add_argument("repo", type=Path, help="the knowledge base's repository root")
    parser.add_argument("paths", nargs="*", help="files or folders whose every line is judged")
    parser.add_argument("--range", metavar="BASE...HEAD", help="judge the lines this range adds")
    parser.add_argument("--staged", action="store_true", help="judge the lines the index adds")
    args = parser.parse_args(argv)
    if [bool(args.paths), bool(args.range), args.staged].count(True) != 1:
        parser.error("name files or folders, --range BASE...HEAD or --staged: exactly one")
    repo = args.repo.resolve()
    try:
        if not (repo / ".git").exists():
            raise Refused(f"not a Git repository root: {repo}")
        bundle, policy, phrases = read_contract(repo)
        if args.range and (".." not in args.range or args.range.startswith("-")):
            raise Refused("--range takes BASE...HEAD (or BASE..HEAD), never one revision")
        lines = whole(repo, args.paths) if args.paths else added(repo, args.range or "--cached", bundle)
    except (Refused, ValueError, OSError) as exc:  # a missing or unreadable contract, a path that escapes, no git
        print(f"sharing scan: cannot run: {exc}", file=sys.stderr)
        return 2
    patterns, held, read = [(phrase, matcher(phrase)) for phrase in dict.fromkeys(phrases)], set(), 0
    for path in sorted(lines):
        why = unjudged(path, lines[path], bundle, policy)
        if why:
            print(f"{path}: not judged, {why}")
            continue
        read += 1
        for number, text in lines[path]:
            for phrase, pattern in patterns:
                if pattern.search(text):
                    print(f'{path}:{number}: "{phrase}"')
                    held.add((path, number))
    if held:
        print(f"sharing scan: {count(len(held), 'line')} held in {count(read, 'file')} read; read each against {policy}")
        return 1
    print(f"sharing scan: clean, {count(read, 'file')} read for {count(len(patterns), 'phrase')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
