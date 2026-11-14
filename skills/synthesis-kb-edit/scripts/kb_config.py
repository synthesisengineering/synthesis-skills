#!/usr/bin/env python3
"""Validate and query a repository's .agents/knowledge-base.yaml contract."""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import json
import os
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root or the installed runtime: holds synthesis/
try:
    from synthesis import yamlish  # noqa: E402
except ImportError as exc:  # no runtime beside this copy; one that fails otherwise as it loads keeps its traceback
    print(f"{__file__} needs the synthesis runtime, which cannot be imported ({exc}), so nothing ran. Run it from the "
          "installed synthesis-skills plugin or a checkout of it", file=sys.stderr)
    sys.exit(2)


CONFIG_RELATIVE = Path(".agents/knowledge-base.yaml")
HOSTS = {"github", "bitbucket"}
SHIP_MODES = {"pr", "direct"}
RESERVED = {"index.md", "log.md"}
# Every key the contract names, by the mapping that holds it. Any other is refused: a misspelled optional key would
# otherwise switch off what it configures, in silence.
KEYS = {"": {"bundle_path", "git_host", "default_branch", "branch_prefix", "ship", "review", "editable", "refuse",
             "generated_artifacts", "topic_routing", "taxonomy_path", "frontmatter", "confidentiality", "notes"},
        "review": {"who_merges", "default_reviewers", "setup_guide"},
        "frontmatter": {"required", "house", "date_field", "reserved_files"},
        "confidentiality": {"forbidden_words_source", "hook_path", "visible_to", "sharing_policy", "backstop_phrases",
                            "unread_allowed"}}
POLICY = ".agents/sharing-policy.md"  # where adopting writes the policy when the contract names no path
TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "sharing-policy.template.md"
# The template's audience lines as it leaves them: a policy that still holds one has not said who reads it, and naming
# it would switch knowledge capture to sharing by default under a policy with no audience.
UNFILLED = ("- **The repository's readers.** **Yours:** who they are.",
            "- **The readers of the copy it publishes.** **Yours:** who they are, and what the copy is (an assistant that answers")


def unfilled(text: str) -> bool:
    return any(line.strip() in UNFILLED for line in text.splitlines())


def is_relative_text(value: Any, *, allow_glob: bool = False) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        return False
    if not allow_glob and any(char in value for char in "*?[]"):
        return False
    return True


def string_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def add_error(errors: list[str], field: str, message: str) -> None:
    errors.append(f"{field}: {message}")


def validate_config(config: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["root: expected a YAML mapping"]
    for section, known in KEYS.items():
        mapping = config.get(section) if section else config
        for key in sorted(set(mapping) - known) if isinstance(mapping, dict) else ():
            close = difflib.get_close_matches(str(key), sorted(known), n=1, cutoff=0.8)  # a near spelling, not a guess
            add_error(errors, f"{section}.{key}" if section else key, "unknown key: " + (f"did you mean {close[0]}? " if close
                      else "") + "correct its spelling, or move it into notes; the contract names every key it reads")

    for field in ("bundle_path", "default_branch", "branch_prefix"):
        if not isinstance(config.get(field), str) or not config[field].strip():
            add_error(errors, field, "expected a non-empty string")
    if config.get("git_host") not in HOSTS:
        add_error(errors, "git_host", "expected github or bitbucket")
    if config.get("ship") not in SHIP_MODES:
        add_error(errors, "ship", "expected pr or direct")
    if not is_relative_text(config.get("bundle_path")):
        add_error(errors, "bundle_path", "expected a safe repository-relative path")

    review = config.get("review")
    if not isinstance(review, dict):
        add_error(errors, "review", "expected a mapping")
    else:
        if not isinstance(review.get("who_merges"), str) or not review["who_merges"].strip():
            add_error(errors, "review.who_merges", "expected a non-empty string")
        if not string_list(review.get("default_reviewers")):
            add_error(errors, "review.default_reviewers", "expected a list of strings")
        guide = review.get("setup_guide")
        if guide is not None and not is_relative_text(guide):
            add_error(errors, "review.setup_guide", "expected a relative path or null")

    for field in ("editable", "refuse", "generated_artifacts"):
        values = config.get(field)
        if not string_list(values):
            add_error(errors, field, "expected a list of non-empty glob strings")
        elif any(not is_relative_text(item, allow_glob=True) for item in values):
            add_error(errors, field, "globs must be safe and repository-relative")

    routing = config.get("topic_routing")
    if not isinstance(routing, dict) or not all(
        isinstance(key, str)
        and bool(key.strip())
        and is_relative_text(value)
        for key, value in routing.items()
    ):
        add_error(
            errors,
            "topic_routing",
            "expected a mapping of non-empty topics to relative paths",
        )

    taxonomy = config.get("taxonomy_path")
    if taxonomy is not None and not is_relative_text(taxonomy):
        add_error(errors, "taxonomy_path", "expected a relative path or null")

    frontmatter = config.get("frontmatter")
    if not isinstance(frontmatter, dict):
        add_error(errors, "frontmatter", "expected a mapping")
    else:
        required = frontmatter.get("required")
        house = frontmatter.get("house")
        if not string_list(required):
            add_error(errors, "frontmatter.required", "expected a list of fields")
            required = []
        if not string_list(house):
            add_error(errors, "frontmatter.house", "expected a list of fields")
            house = []
        if "type" not in required:
            add_error(errors, "frontmatter.required", "must contain OKF field type")
        duplicates = sorted(set(required).intersection(house))
        if duplicates:
            add_error(
                errors,
                "frontmatter",
                f"required and house overlap: {', '.join(duplicates)}",
            )
        date_field = frontmatter.get("date_field")
        if not isinstance(date_field, str) or not date_field.strip():
            add_error(errors, "frontmatter.date_field", "expected one field name")
        elif date_field not in set(required).union(house):
            add_error(
                errors,
                "frontmatter.date_field",
                "must appear in required or house",
            )
        reserved = frontmatter.get("reserved_files")
        if not string_list(reserved):
            add_error(errors, "frontmatter.reserved_files", "expected a list")
        elif not RESERVED.issubset(reserved):
            add_error(
                errors,
                "frontmatter.reserved_files",
                "must contain index.md and log.md",
            )

    confidentiality = config.get("confidentiality")
    if not isinstance(confidentiality, dict):
        add_error(errors, "confidentiality", "expected a mapping")
    else:
        for field in ("forbidden_words_source", "hook_path", "sharing_policy"):
            value = confidentiality.get(field)
            if value is not None and not is_relative_text(value):
                add_error(
                    errors,
                    f"confidentiality.{field}",
                    "expected a relative path or null",
                )
        visible = confidentiality.get("visible_to")
        if not isinstance(visible, str) or not visible.strip():
            add_error(errors, "confidentiality.visible_to", "expected a non-empty string")
        phrases = confidentiality.get("backstop_phrases", [])  # the organization's own; the plugin ships none
        if not string_list(phrases):
            add_error(errors, "confidentiality.backstop_phrases", "expected a list of phrases")
        elif confidentiality.get("sharing_policy") and not phrases:  # the scan runs on every edit and needs them
            add_error(errors, "confidentiality.backstop_phrases", "the contract names a sharing policy and no phrases, so "
                      "every edit is held: list at least one of this organization's own phrases here, or remove "
                      "confidentiality.sharing_policy")
        allowed = confidentiality.get("unread_allowed", [])  # files only people read; the scan holds every other it cannot
        if not string_list(allowed) or any(not is_relative_text(item, allow_glob=True) for item in allowed):
            add_error(errors, "confidentiality.unread_allowed", "expected a list of safe repository-relative globs")

    if not isinstance(config.get("notes"), str):
        add_error(errors, "notes", "expected a string")
    return errors


def resolve_inside(repo: Path, relative: str) -> Path:
    candidate = (repo / relative).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {relative}") from exc
    return candidate


def spelled(repo: Path, relative: str) -> bool:
    """Whether each part of the path is spelled as the disk spells it. A disk that ignores letter case finds `Source`
    for `source`; git does not, so the phrase scan would read nothing there."""
    folder = repo
    for part in PurePosixPath(relative.replace("\\", "/")).parts:
        try:
            names = {unicodedata.normalize("NFC", name) for name in os.listdir(folder)}
        except OSError:
            return False
        if unicodedata.normalize("NFC", part) not in names:
            return False
        folder = folder / part
    return True


def check_paths(repo: Path, config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_paths: list[tuple[str, str, str]] = [
        ("bundle_path", config["bundle_path"], "directory"),
    ]
    review = config["review"]
    if review.get("setup_guide"):
        required_paths.append(("review.setup_guide", review["setup_guide"], "file"))
    if config.get("taxonomy_path"):
        required_paths.append(("taxonomy_path", config["taxonomy_path"], "file"))
    confidentiality = config["confidentiality"]
    if confidentiality.get("forbidden_words_source"):
        required_paths.append(
            (
                "confidentiality.forbidden_words_source",
                confidentiality["forbidden_words_source"],
                "file",
            )
        )
    if confidentiality.get("hook_path"):
        required_paths.append(
            ("confidentiality.hook_path", confidentiality["hook_path"], "directory")
        )
    if confidentiality.get("sharing_policy"):
        required_paths.append(("confidentiality.sharing_policy", confidentiality["sharing_policy"], "file"))
    for topic, relative in config["topic_routing"].items():
        required_paths.append((f"topic_routing.{topic}", relative, "directory"))

    for field, relative, kind in required_paths:
        try:
            path = resolve_inside(repo, relative)
        except ValueError as exc:
            add_error(errors, field, str(exc))
            continue
        exists = path.is_dir() if kind == "directory" else path.is_file()
        if not exists:
            add_error(errors, field, f"configured {kind} does not exist: {relative}")
        elif not spelled(repo, relative):
            add_error(errors, field, f"configured {kind} is spelled otherwise on disk: {relative} (git reads letter case exactly)")
    policy = confidentiality.get("sharing_policy")
    try:
        unready = bool(policy) and resolve_inside(repo, policy).is_file() and unfilled(
            resolve_inside(repo, policy).read_text(encoding="utf-8", errors="replace"))
    except (ValueError, OSError):  # the loop above names a path that escapes or is not there
        unready = False
    if unready:
        add_error(errors, "confidentiality.sharing_policy", f"{policy} is still the template as written: fill in who reads "
                  "it before the contract names it")
    return errors


def matches(path: str, patterns: list[str]) -> bool:
    normalized = path.removeprefix("./").replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def classify(path: str, config: dict[str, Any]) -> str:
    if matches(path, config["generated_artifacts"]):
        return "generated"
    if matches(path, config["refuse"]):
        return "refused"
    if matches(path, config["editable"]):
        return "editable"
    return "outside"


def load_config(repo: Path, config_path: Path | None) -> tuple[Path, dict[str, Any]]:
    path = config_path or (repo / CONFIG_RELATIVE)
    if not path.is_absolute():
        path = repo / path
    try:
        data = yamlish.load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing configuration: {path}") from exc
    except ValueError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    return path, data


def adopt_sharing_policy(repo: Path, phrases: list[str]) -> tuple[int, list[str]]:
    """Name the sharing policy in the contract with the organization's own phrases. With no policy file yet, write the
    template where the contract says and stop: naming the policy switches knowledge capture to sharing by default, so
    it is named only once it says who reads it. The contract changes in place, keeping every line and its line ending,
    and only when what it would become passes the configuration gate. Nothing is committed."""
    path, config = load_config(repo, None)
    block = config.get("confidentiality") if isinstance(config, dict) else None
    if not isinstance(block, dict):
        return 1, [f"ERROR {error}" for error in validate_config(config)] + ["nothing adopted: the contract must be valid first"]
    relative, listed = block.get("sharing_policy") or POLICY, block.get("backstop_phrases") or []
    if bool(phrases) == bool(listed):  # one list of phrases, given now or already in the contract
        return 1, [f"nothing adopted: {CONFIG_RELATIVE} lists phrases already; change them there, and run this again without"
                   " --phrase" if listed else "nothing adopted: a named policy runs the phrase scan on every edit, and the"
                   " scan needs this organization's own phrases (the plugin ships none): run this again with --phrase"
                   " PHRASE for each one"]
    target = resolve_inside(repo, relative)  # a path that escapes the repository raises before anything is written
    if target.exists() and not target.is_file():
        return 1, [f"nothing adopted: {relative} is there but is not a file, so it can be no policy"]
    raw = path.read_bytes().decode("utf-8")  # as written: its line endings are kept
    eol = "\r\n" if "\r\n" in raw else "\n"
    keys = [key for key, empty in (("sharing_policy", not block.get("sharing_policy")), ("backstop_phrases", bool(phrases)))
            if empty]  # absent, or present and null or empty: written once, never twice
    adding = ([f"sharing_policy: {json.dumps(relative)}"] if "sharing_policy" in keys else []) + (
        ["backstop_phrases:"] + [f"  - {json.dumps(phrase, ensure_ascii=False)}" for phrase in phrases] if phrases else [])
    if adding:
        header = re.search(r"^confidentiality:[ \t]*(?:#.*)?\r?\n", raw, flags=re.M)
        child = header and re.compile(r"^([ \t]+)[^\s#]", flags=re.M).search(raw, header.end())  # its first key
        if not child:
            return 1, [f"nothing adopted: the confidentiality mapping in {CONFIG_RELATIVE} is not in block form; add these"
                       " lines to it by hand:"] + [f"  {line}" for line in adding]
        after = re.compile(r"^[^\s#]", flags=re.M).search(raw, header.end())  # the next top-level key ends the mapping
        stop = after.start() if after else len(raw)
        body = re.sub(r"^[ \t]+(?:" + "|".join(keys) + r"):[ \t]*(?:null|~|\[[ \t]*\])?[ \t]*(?:#.*)?\r?\n", "",
                      raw[header.end():stop], flags=re.M)
        raw = raw[:header.end()] + "".join(f"{child.group(1)}{line}{eol}" for line in adding) + body + raw[stop:]
    try:  # read back as the skills will read it, before anything is written
        result = yamlish.load(raw)
    except ValueError as exc:
        return 1, [f"nothing adopted: the contract it would write cannot be read ({exc})"]
    errors = validate_config(result)
    if errors:
        return 1, [f"ERROR {error}" for error in errors] + ["nothing adopted: the contract it would write is not valid"]
    for key, wanted in (("sharing_policy", relative), ("backstop_phrases", phrases or listed)):
        if result["confidentiality"].get(key) != wanted:
            return 1, [f"nothing adopted: the contract it would write reads confidentiality.{key} as "
                       f"{result['confidentiality'].get(key)!r}, not {wanted!r}"]
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        return 1, [f"{relative}: written from the template; the contract does not name it yet",
                   "next: fill in its parts marked Yours, at least who reads it, then run this again with your phrases; "
                   "naming it is what switches the knowledge base to sharing by default"]
    if unfilled(target.read_text(encoding="utf-8", errors="replace")):
        return 1, [f"nothing adopted: {relative} is still the template as written: fill in who reads it, then run this "
                   "again"]
    errors = check_paths(repo, result)
    if errors:
        return 1, [f"ERROR {error}" for error in errors] + ["nothing adopted: the contract it would write does not pass "
                                                             "the configuration gate"]
    if adding:
        path.write_bytes(raw.encode("utf-8"))
    count = len(phrases or listed)
    return 0, [f"{relative}: kept as it is",
               f"{CONFIG_RELATIVE}: names the policy{'' if adding else ' already'}, with {count} phrase"
               f"{'' if count == 1 else 's'}; every edit runs the phrase scan",
               "next: review and ship this change; nothing was committed"]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    adopting = argv[:1] == ["adopt-sharing-policy"]  # kb_config.py adopt-sharing-policy <repo-root> --phrase PHRASE
    parser = argparse.ArgumentParser(
        description="Validate and query .agents/knowledge-base.yaml; with adopt-sharing-policy first, name the sharing"
                    " policy in the contract with the phrases given, writing its template where the contract says."
    )
    parser.add_argument("repo", type=Path, help="repository root")
    if adopting:
        parser.add_argument("--phrase", action="append", default=[], help="one of the organization's own phrases; repeat it")
    else:
        parser.add_argument("--config", type=Path, help="alternate config path")
        parser.add_argument("--check-paths", action="store_true")
        parser.add_argument("--resolve", action="append", default=[], metavar="PATH")
        parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv[1:] if adopting else argv)

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        print(f"error: not a Git repository root: {repo}", file=sys.stderr)
        return 2
    try:
        if adopting:
            code, lines = adopt_sharing_policy(repo, list(dict.fromkeys(phrase.strip() for phrase in args.phrase)))
            print("\n".join(lines))
            return code
        path, config = load_config(repo, args.config)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors = validate_config(config)
    if not errors and args.check_paths:
        errors.extend(check_paths(repo, config))
    resolutions = [
        {"path": item, "classification": classify(item, config)}
        for item in args.resolve
    ] if not errors else []
    payload = {
        "config": str(path),
        "valid": not errors,
        "errors": errors,
        "resolutions": resolutions,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for error in errors:
            print(f"ERROR {error}")
        for resolution in resolutions:
            print(f"{resolution['classification']:9} {resolution['path']}")
        print(
            f"{'VALID' if not errors else 'INVALID'} — {path}"
            f" ({len(errors)} error(s))"
        )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
