#!/usr/bin/env python3
"""The sharing policy's backstop: the organization's own phrases, in what a change adds to a knowledge base.

It judges the lines, the file and folder names and the commit messages a change adds under the bundle, and the policy
file and the contract's values, all but the phrase list itself. A phrase is read as words: in any letter case, with
accents composed and invisible characters dropped, in slugs, snake_case and CamelCase, and wrapped across two lines. A
hit is printed as where it is and the phrase, never the rest of the line, which may be the very thing that should not
be shown. A file it cannot read as text (neither UTF-8 nor UTF-16 with its byte-order mark) is held for a person,
unless the contract names it among the files only people read. The contract before the change governs too, so a change
cannot loosen what judges it. It cannot see meaning: the editor and the reviewer apply the policy, and this catches a
phrase they missed. The plugin ships no phrases, so with none named it refuses to run. It needs the standard library
and the checkout's own YAML reader (through kb_config.py beside it), so it runs by path from a checkout pinned to a tag.

    sharing_scan.py <repo-root> --range <base>...<head>   what the range adds, and its commit messages (a pipeline)
    sharing_scan.py <repo-root> --staged                   what the index adds (a pre-commit hook)
    sharing_scan.py <repo-root> --message <file>           a commit message (a commit-msg hook)
    sharing_scan.py <repo-root> <path>...                  every line and name of these files and folders

Exit 0 when nothing is held, 1 when something is held, 2 when it cannot run.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parent))  # kb_config beside it, in isolated mode too
import kb_config  # noqa: E402  the contract's reader and checks; it imports the checkout's YAML reader

CONTRACT = kb_config.CONFIG_RELATIVE.as_posix()
SHORT = 5  # a phrase this long or shorter matches only as a whole word: "opal" never holds "opalescent"
HUNK = re.compile(rb"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", flags=re.M)
LOOKALIKE = {**dict.fromkeys(map(ord, "‘’ʼ＇"), "'"),  # apostrophes Word, Docs and Slack type
             **dict.fromkeys(map(ord, "‐‑‒–—―−﹣－"), "-")}
BOMS = ((b"\xef\xbb\xbf", "utf-8"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"))
UNREAD = "held, not text: a person must read it"


class Refused(Exception):
    """The scan cannot run; the message says why."""


def canon(text: str, split: bool) -> str:
    """The text as the scan compares it: NFKC, no invisible format characters (soft hyphens, zero-width marks), one
    apostrophe and one hyphen, letter case folded, and -, _, ., / and \\ read as spaces. With `split`, a capital
    inside a word starts a new one: ZephyrLedger, projectOpal, HTTPServer."""
    text = "".join(ch for ch in unicodedata.normalize("NFKC", text).translate(LOOKALIKE) if unicodedata.category(ch) != "Cf")
    if split:
        text = "".join(" " + ch if i and ch.isupper() and (text[i - 1].islower() or text[i - 1].isdigit() or (
            text[i - 1].isupper() and text[i + 1:i + 2].islower())) else ch for i, ch in enumerate(text))
    return re.sub(r"[-_./\\]+", " ", text.casefold())


def matchers(phrase: str) -> list:
    """The phrase in each of its compared forms, where a word starts, its words joined by any run of spaces or none
    (so a slug or an identifier holds it); a phrase of five characters or fewer must also end a word."""
    end = r"(?!\w)" if len(phrase.strip()) <= SHORT else ""
    return [re.compile(r"(?<!\w)" + r"\s*".join(map(re.escape, form.split())) + end)
            for form in {canon(phrase, False), canon(phrase, True)} if form.split()]


def hits(lines: list, judged: set, phrases: list) -> list:
    """(line number, phrase) for each phrase in a judged line, or wrapped onto it from the line before, or from it onto
    a next line the scan does not judge on its own (a word the change adds beside a word it leaves)."""
    forms: dict = {}  # each line's two compared forms, made only for the lines judged and their neighbors

    def form(i: int, k: int) -> str:
        if (i, k) not in forms:
            forms[i, k] = canon(lines[i], bool(k))
        return forms[i, k]

    found = []
    for number in sorted(n for n in judged if 0 < n <= len(lines)):
        i = number - 1
        for phrase, patterns in phrases:
            for k in (0, 1):
                here = form(i, k)
                pairs = [(form(i - 1, k), here)] if i else []
                pairs += [(here, form(i + 1, k))] if i + 1 < len(lines) and number + 1 not in judged else []
                if any(p.search(here) for p in patterns) or any(
                        m.start() < len(a) < m.end() - 1 for a, b in pairs for p in patterns for m in p.finditer(f"{a} {b}")):
                    found.append((number, phrase))
                    break
    return found


def text_of(data: bytes):
    """(text, whether every line is judged) for UTF-8, or for UTF-16 with its byte-order mark, whose lines git cannot
    number; None for anything else, which a person must read."""
    codec, skip = next(((codec, len(bom)) for bom, codec in BOMS if data.startswith(bom)), ("utf-8", 0))
    try:
        return data[skip:].decode(codec), codec != "utf-8"
    except UnicodeDecodeError:
        return None


def git(repo: Path, *args) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), "--literal-pathspecs", *args], capture_output=True)
    if done.returncode:
        raise Refused(done.stderr.decode("utf-8", "replace").strip() or f"git {args[0]} failed")
    return done.stdout


def blob(repo: Path, where):
    """The bytes git holds at `<revision>:<path>` (`:<path>` for the index), as it stores them, or None."""
    done = subprocess.run(["git", "-C", str(repo), "cat-file", "blob", where], capture_output=True)
    return done.stdout if done.returncode == 0 else None


def contract_at(repo: Path, revision: str):
    """The contract a revision holds (`:` for the index), or None when it holds none it can read."""
    data = blob(repo, f"{revision}:{CONTRACT}")
    try:
        return kb_config.yamlish.load(data.decode("utf-8")) if data is not None else None
    except (ValueError, UnicodeDecodeError):
        return None


def rules(new, old):
    """What judges: the contract under review, which must be valid, and the one before it (None when there is no
    before): the phrases and bundles of both, and only the files both let people alone read."""
    errors = kb_config.validate_config(new)
    if errors:
        raise Refused(f"{CONTRACT} is invalid: {'; '.join(errors)}")
    block = new["confidentiality"]
    before = old.get("confidentiality") if isinstance(old, dict) and isinstance(old.get("confidentiality"), dict) else {}
    policies = [PurePosixPath(p).as_posix() for p in (block.get("sharing_policy"), before.get("sharing_policy"))
                if isinstance(p, str) and p.strip()]
    if not policies:
        raise Refused(f"{CONTRACT} names no sharing policy (confidentiality.sharing_policy): adopt one with "
                      "kb_config.py adopt-sharing-policy <repo-root> --phrase PHRASE")
    listed = [p for p in [*(block.get("backstop_phrases") or []), *(before.get("backstop_phrases") or [])]
              if isinstance(p, str) and p.strip()]
    if not listed:  # the contract check holds this too: never a scan with nothing to look for
        raise Refused(f"{CONTRACT} names no backstop phrases (confidentiality.backstop_phrases): the plugin ships none, "
                      "so list this organization's own there; nothing was scanned")
    allowed = set(block.get("unread_allowed") or [])
    if old is not None:  # a change cannot exempt itself
        allowed &= set(before.get("unread_allowed") or [])
    bundles = {PurePosixPath(b).as_posix() for b in (new["bundle_path"], (old or {}).get("bundle_path"))
               if isinstance(b, str) and b.strip()}
    removed = [p for p in before.get("backstop_phrases") or [] if p not in (block.get("backstop_phrases") or [])]
    return SimpleNamespace(policy=policies[0], policies=set(policies), bundle=PurePosixPath(new["bundle_path"]).as_posix(),
                           bundles=bundles, allowed=sorted(allowed), removed=removed, new=new, old=old,
                           phrases=[(p, matchers(p)) for p in dict.fromkeys(listed)])


def unjudged(path: str, rule) -> str:
    """Why a path is not judged, or nothing when it is: the bundles, the policy and the contract are."""
    if path in rule.policies or path == CONTRACT or any(b == "." or path == b or path.startswith(b + "/") for b in rule.bundles):
        return ""
    return f"outside the bundle ({rule.bundle})"


def values(config, where: str = ""):
    """(key path, text) for each key and string of the contract, but the phrase list: that is the list itself."""
    if isinstance(config, dict):
        for key, value in config.items():
            inner = f"{where}.{key}" if where else str(key)
            if inner != "confidentiality.backstop_phrases":
                yield inner, str(key)
                yield from values(value, inner)
    elif isinstance(config, list):
        for value in config:
            yield from values(value, where)
    elif isinstance(config, str):
        yield where, config


def tracked(repo: Path, rule, revision: str = "") -> None:
    """Refuse a bundle git tracks no file under at the revision (the index when none is given): a folder the change
    renamed away, or one spelled in another letter case, which a disk that ignores case accepts and git does not."""
    names = git(repo, *(("ls-tree", "-r", "--name-only", "-z", revision) if revision else ("ls-files", "-z")), "--",
                rule.bundle)
    if not names.strip(b"\0"):
        raise Refused(f"the bundle {rule.bundle} holds no file git tracks{' at ' + revision[:12] if revision else ''}: "
                      "git reads letter case exactly, so correct bundle_path, or commit the knowledge base's files")


def ready(repo: Path, rule, revision: str) -> None:
    """Refuse a policy the contract under review names that is not there, or is still the template as written."""
    named = rule.new["confidentiality"].get("sharing_policy")
    if named:
        data = blob(repo, f"{revision}:{named}")
        if data is None:
            raise Refused(f"the sharing policy {named} named in the contract is not there"
                          f"{' at ' + revision[:12] if revision else ' in the index'}")
        if kb_config.unfilled(data.decode("utf-8", "replace")):
            raise Refused(f"{named} is still the template as written: fill in who reads it before the contract names it")


def judge(path: str, data, numbers, named: bool, rule, report) -> None:
    """One file: its new name, its lines (`numbers`: those added; None: every one), or a hold when it is not text."""
    report.hits += [f'{path}: name: "{phrase}"' for _, phrase in hits([path], {1}, rule.phrases)] if named else []
    if path == CONTRACT:
        new = set(values(rule.new))
        for where, text in sorted(new - set(values(rule.old or {})) if numbers is not None else new):
            lines = text.split("\n")
            found = dict.fromkeys(phrase for _, phrase in hits(lines, set(range(1, len(lines) + 1)), rule.phrases))
            report.hits += [f'{path}: {where}: "{phrase}"' for phrase in found]
        report.read += 1
        return
    decoded = text_of(data) if data is not None else None
    if decoded is None:
        if kb_config.matches(path, rule.allowed):
            report.notes.append(f"{path}: not judged, read by people (unread_allowed)")
        else:
            report.hits.append(f"{path}: {UNREAD}")
        return
    lines = decoded[0].split("\n")
    judged = set(range(1, len(lines) + 1)) if numbers is None or decoded[1] else set(numbers)
    report.hits += [f'{path}:{number}: "{phrase}"' for number, phrase in hits(lines, judged, rule.phrases)]
    report.read += 1


def changed(repo: Path, rule, report, diff: list, revision: str) -> None:
    """Each file a change adds or alters under the bundles, the policies or the contract, judged as it now is."""
    spec = sorted(rule.bundles | rule.policies | {CONTRACT})
    listed = git(repo, "diff", "--name-status", "-z", "--no-renames", "--diff-filter=d", *diff, "--", *spec).split(b"\0")
    for status, name in zip(listed[::2], listed[1::2]):
        path = name.decode("utf-8", "replace")
        why = unjudged(path, rule)
        if why:
            report.notes.append(f"{path}: not judged, {why}")
            continue
        hunks = git(repo, "diff", "-U0", "--text", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames", *diff,
                    "--", name)
        numbers = {n for start, count in HUNK.findall(hunks) for n in range(int(start), int(start) + int(count or 1))}
        judge(path, blob(repo, f"{revision}:".encode() + name), numbers, status.startswith(b"A"), rule, report)


def message(lines: list, label: str, rule, report) -> None:
    """A commit message, its lines numbered as written; a line git strips as a comment is left out."""
    kept = ["" if line.startswith("#") else line for line in lines]
    judged = {n for n, line in enumerate(lines, 1) if not line.startswith("#")}
    report.hits += [f'{label}:{number}: "{phrase}"' for number, phrase in hits(kept, judged, rule.phrases)]


def walked(repo: Path, given: list):
    """(path, bytes, whether a link) for each named file and each file under each named folder. A link is listed and
    never followed: its bytes are where it points, as git stores it."""
    for relative in given:
        start = repo / relative
        if os.path.commonpath([os.path.abspath(start), str(repo)]) != str(repo):
            raise Refused(f"path escapes repository: {relative}")
        kb_config.resolve_inside(repo, str(Path(relative).parent))  # a linked folder above it that leaves raises too
        if not os.path.lexists(start):
            raise Refused(f"{relative} is not there")
        found = [start]
        if start.is_dir() and not start.is_symlink():
            found = []
            for top, folders, files in os.walk(start):  # a linked folder is listed in folders, never entered
                folders[:] = [name for name in folders if name != ".git"]
                found += [Path(top) / name for name in files + [f for f in folders if (Path(top) / f).is_symlink()]]
        for path in sorted(found):
            link = path.is_symlink()
            data = os.readlink(path).encode("utf-8", "surrogateescape") if link else path.read_bytes()
            yield Path(os.path.abspath(path)).relative_to(repo).as_posix(), data, link


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The sharing policy's backstop phrase scan.")
    parser.add_argument("repo", type=Path, help="the knowledge base's repository root")
    parser.add_argument("paths", nargs="*", help="files or folders whose every line and name is judged")
    parser.add_argument("--range", metavar="BASE...HEAD", help="judge what this range adds, and its commit messages")
    parser.add_argument("--staged", action="store_true", help="judge what the index adds")
    parser.add_argument("--message", metavar="FILE", help="judge a commit message (a commit-msg hook)")
    args = parser.parse_args(argv)
    if [bool(args.paths), bool(args.range), args.staged, bool(args.message)].count(True) != 1:
        parser.error("name files or folders, --range BASE...HEAD, --staged or --message FILE: exactly one")
    repo, report = args.repo.resolve(), SimpleNamespace(hits=[], notes=[], read=0)
    try:
        if not (repo / ".git").exists():
            raise Refused(f"not a Git repository root: {repo}")
        if args.range:
            parts = re.fullmatch(r"(.*?)(\.\.\.?)(.*)", args.range)
            if not parts or parts.group(1).startswith("-") or parts.group(3).startswith("-"):
                raise Refused("--range takes BASE...HEAD (or BASE..HEAD), never one revision")
            left, dots, right = parts.group(1) or "HEAD", parts.group(2), parts.group(3) or "HEAD"
            head = git(repo, "rev-parse", "--verify", f"{right}^{{commit}}").decode().strip()
            base = git(repo, *(("merge-base", left, head) if dots == "..." else
                               ("rev-parse", "--verify", f"{left}^{{commit}}"))).decode().strip()
            new = contract_at(repo, head)
            if new is None:
                raise Refused(f"{head[:12]} holds no {CONTRACT} the scan can read")
            rule = rules(new, contract_at(repo, base) or {})
            tracked(repo, rule, head)
            ready(repo, rule, head)
            changed(repo, rule, report, [base, head], head)
            log = git(repo, "log", "--format=%H%x01%B%x02", f"{base}..{head}").decode("utf-8", "replace")
            for entry in filter(str.strip, log.split("\x02")):
                sha, body = entry.strip("\n").split("\x01", 1)
                message(body.rstrip("\n").split("\n"), f"commit {sha[:12]}", rule, report)
        elif args.staged or args.message:
            new = contract_at(repo, "")
            if new is None:
                raise Refused(f"the index holds no {CONTRACT} the scan can read")
            rule = rules(new, contract_at(repo, "HEAD") or {})
            tracked(repo, rule)
            ready(repo, rule, "")
            if args.staged:
                changed(repo, rule, report, ["--cached"], "")
            else:
                message(Path(args.message).read_text(encoding="utf-8", errors="replace").split("\n"), "commit message",
                        rule, report)
                report.read += 1
        else:
            config = kb_config.load_config(repo, None)[1]
            rule = rules(config, None)
            named = config["confidentiality"].get("sharing_policy")
            if named and not kb_config.resolve_inside(repo, named).is_file():
                raise Refused(f"the sharing policy {named} named in the contract is not there")
            errors = kb_config.check_paths(repo, config)
            if errors:
                raise Refused(f"{CONTRACT} does not pass the configuration gate: {'; '.join(errors)}")
            tracked(repo, rule)
            for path, data, link in sorted(walked(repo, args.paths)):
                why = unjudged(path, rule)
                if why:
                    report.notes.append(f"{path}: not judged, {why}")
                    continue
                if link:
                    report.notes.append(f"{path}: a link, not followed")
                judge(path, data, None, True, rule, report)
    except (Refused, ValueError, OSError) as exc:  # a missing or unreadable contract, a path that escapes, no git
        print(f"sharing scan: cannot run: {exc}", file=sys.stderr)
        return 2
    for line in report.notes + report.hits:
        print(line)
    if rule.removed:
        print(f"sharing scan: the change takes {len(rule.removed)} phrase{'s' if len(rule.removed) != 1 else ''} out of "
              f"the contract, still judged here: {', '.join(chr(34) + p + chr(34) for p in rule.removed)}")
    count = len(report.hits)
    files = f"{report.read} file{'' if report.read == 1 else 's'} read"
    if count:
        print(f"sharing scan: {count} line{'' if count == 1 else 's'} held in {files}; read each against {rule.policy}")
        return 1
    print(f"sharing scan: clean, {files} for {len(rule.phrases)} phrase{'' if len(rule.phrases) == 1 else 's'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
