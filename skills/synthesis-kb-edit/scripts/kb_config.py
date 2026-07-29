#!/usr/bin/env python3
"""Validate and query a repository's .agents/knowledge-base.yaml contract."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("kb-config requires PyYAML (pip install pyyaml)")


CONFIG_RELATIVE = Path(".agents/knowledge-base.yaml")
HOSTS = {"github", "bitbucket"}
SHIP_MODES = {"pr", "direct"}
RESERVED = {"index.md", "log.md"}


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
        for field in ("forbidden_words_source", "hook_path"):
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
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing configuration: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    return path, data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and query .agents/knowledge-base.yaml."
    )
    parser.add_argument("repo", type=Path, help="repository root")
    parser.add_argument("--config", type=Path, help="alternate config path")
    parser.add_argument("--check-paths", action="store_true")
    parser.add_argument("--resolve", action="append", default=[], metavar="PATH")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        print(f"error: not a Git repository root: {repo}", file=sys.stderr)
        return 2
    try:
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
