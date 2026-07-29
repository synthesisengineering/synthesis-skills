#!/usr/bin/env python3
"""Check configured OKF house-schema and body/frontmatter consistency."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    import yaml
except ImportError:
    sys.exit("okf-consistency requires PyYAML (pip install pyyaml)")


CONFIG_RELATIVE = Path(".agents/knowledge-base.yaml")
TAG_RE = re.compile(r"^[a-z][a-z0-9-]*:[a-z0-9][a-z0-9.-]*$")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
INLINE_RE = re.compile(
    r"^\s*\*\*(Last Updated|Updated|Created|Status|Owner|Author|"
    r"Main Contact|Current Phase|Next Milestones)\s*:?\*\*\s*:?\s*(.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
DATE_IN_FILENAME_RE = re.compile(r"(?:^|-)\d{4}(?:-\d{2})?(?:-\d{2})?(?:-|$)")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
MIRROR_NOTE_RE = re.compile(
    r"\b(mirror(?:s|ed)?|canonical source|source of truth|summary of)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int | None
    severity: str
    message: str
    fix: str

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return (
            f"{location} — {self.severity} — {self.message}\n"
            f"   fix: {self.fix}"
        )


def split_frontmatter(text: str) -> tuple[str | None, str, int]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, text, 1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return (
                "".join(lines[1:index]),
                "".join(lines[index + 1 :]),
                index + 2,
            )
    return None, text, 1


def field_line(text: str, field: str) -> int | None:
    pattern = re.compile(rf"^{re.escape(field)}\s*:", re.MULTILINE)
    match = pattern.search(text)
    return text[: match.start()].count("\n") + 2 if match else None


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime,)):
        return value.date().isoformat()
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return str(value.isoformat())[:10]
    text = str(value).strip()
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1)
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def parse_taxonomy(path: Path | None) -> tuple[set[str], set[str]]:
    if path is None or not path.is_file():
        return set(), set()
    text = path.read_text(encoding="utf-8")
    valid_tags = {
        token
        for token in CODE_SPAN_RE.findall(text)
        if TAG_RE.fullmatch(token)
    }
    valid_types: set[str] = set()
    lines = text.splitlines()
    in_type = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\*\*type\*\*", stripped, re.IGNORECASE):
            in_type = True
            continue
        if in_type and (
            stripped.startswith("## ")
            or re.match(r"^\*\*[a-z][^*]*:\*\*", stripped, re.IGNORECASE)
        ):
            break
        if in_type:
            for token in CODE_SPAN_RE.findall(line):
                if re.fullmatch(r"[a-z][a-z0-9-]*", token):
                    valid_types.add(token)
    return valid_tags, valid_types


def config_path(repo: Path, configured: Path | None) -> Path:
    if configured is None:
        return repo / CONFIG_RELATIVE
    return configured if configured.is_absolute() else repo / configured


def safe_repo_path(repo: Path, relative: str) -> Path:
    pure = PurePosixPath(relative.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"unsafe repository-relative path: {relative}")
    resolved = (repo / pure).resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {relative}") from exc
    return resolved


def load_contract(repo: Path, configured: Path | None) -> tuple[dict[str, Any], Path]:
    path = config_path(repo, configured)
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing configuration: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError(f"configuration is not a mapping: {path}")
    try:
        frontmatter = config["frontmatter"]
        required = frontmatter["required"]
        house = frontmatter["house"]
        date_field = frontmatter["date_field"]
        reserved = frontmatter["reserved_files"]
        bundle_path = config["bundle_path"]
        routing = config["topic_routing"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"incomplete knowledge-base contract: {exc}") from exc
    if not all(
        (
            isinstance(frontmatter, dict),
            isinstance(required, list),
            isinstance(house, list),
            isinstance(date_field, str),
            isinstance(reserved, list),
            isinstance(bundle_path, str),
            isinstance(routing, dict),
        )
    ):
        raise ValueError("knowledge-base contract fields have invalid types")
    return config, path


def body_line(body_start: int, body: str, offset: int) -> int:
    return body_start + body[:offset].count("\n")


def first_inline_value(
    body: str, body_start: int, labels: set[str]
) -> tuple[str, int] | None:
    for match in INLINE_RE.finditer(body):
        label = match.group(1).lower()
        if label in labels:
            return match.group(2).strip(), body_line(body_start, body, match.start())
    return None


def metadata_preamble(body: str) -> str:
    """Return document-level metadata before the first H2 or section break."""
    h1 = H1_RE.search(body)
    start = h1.end() if h1 else 0
    boundary = re.search(r"^(?:##\s+|---\s*$)", body[start:], re.MULTILINE)
    end = start + boundary.start() if boundary else len(body)
    return body[:end]


def configured_values(valid_tags: set[str], dimension: str) -> set[str]:
    prefix = f"{dimension}:"
    return {
        tag.split(":", 1)[1]
        for tag in valid_tags
        if tag.startswith(prefix)
    }


def check_document(
    repo: Path,
    bundle: Path,
    path: Path,
    config: dict[str, Any],
    valid_tags: set[str],
    valid_types: set[str],
) -> list[Finding]:
    rel_repo = path.relative_to(repo).as_posix()
    findings: list[Finding] = []
    text = path.read_text(encoding="utf-8")
    fm_text, body, body_start = split_frontmatter(text)
    if fm_text is None:
        return [
            Finding(
                rel_repo,
                1,
                "CONFLICT",
                "missing or unterminated YAML frontmatter",
                "add a parseable frontmatter block using the configured schema",
            )
        ]
    try:
        meta = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        return [
            Finding(
                rel_repo,
                1,
                "CONFLICT",
                f"frontmatter is not parseable YAML: {exc}",
                "repair the YAML before shipping",
            )
        ]
    if not isinstance(meta, dict):
        return [
            Finding(
                rel_repo,
                1,
                "CONFLICT",
                "frontmatter is not a mapping",
                "replace it with a key-value mapping",
            )
        ]

    frontmatter = config["frontmatter"]
    required = set(frontmatter["required"])
    house = set(frontmatter["house"])
    allowed = required | house
    date_field = frontmatter["date_field"]

    for field in sorted(required):
        if field not in meta or meta[field] in (None, "", []):
            findings.append(
                Finding(
                    rel_repo,
                    1,
                    "CONFLICT",
                    f"missing required frontmatter field `{field}`",
                    f"add `{field}` using the configured schema and taxonomy",
                )
            )
    for field in sorted(set(meta) - allowed):
        findings.append(
            Finding(
                rel_repo,
                field_line(fm_text, field),
                "WARN",
                f"frontmatter field `{field}` is outside the configured schema",
                "add the field to the repository contract or remove it",
            )
        )

    aliases = {"last_updated", "last-updated", "updated_at", "updated-at"} - {
        date_field
    }
    present_aliases = sorted(alias for alias in aliases if alias in meta)
    for alias in present_aliases:
        findings.append(
            Finding(
                rel_repo,
                field_line(fm_text, alias),
                "CONFLICT",
                f"`{alias}` duplicates configured date field `{date_field}`",
                f"keep only `{date_field}`",
            )
        )

    configured_date = normalize_date(meta.get(date_field))
    preamble = metadata_preamble(body)
    inline_date = first_inline_value(
        preamble, body_start, {"last updated", "updated", "created"}
    )
    if inline_date:
        value, line = inline_date
        inline_normalized = normalize_date(value)
        severity = (
            "CONFLICT"
            if configured_date and inline_normalized and configured_date != inline_normalized
            else "DUPLICATE"
        )
        message = (
            f"{date_field} {configured_date} disagrees with inline date {value!r}"
            if severity == "CONFLICT"
            else f"inline date duplicates frontmatter `{date_field}`"
        )
        findings.append(
            Finding(
                rel_repo,
                line,
                severity,
                message,
                f"remove the inline date and keep `{date_field}` as the source of truth",
            )
        )

    inline_status = first_inline_value(preamble, body_start, {"status"})
    if inline_status and meta.get("status") is not None:
        value, line = inline_status
        normalized_inline = normalize_scalar(value)
        allowed_statuses = configured_values(valid_tags, "confidence") or {
            "canonical",
            "draft",
            "needs-verification",
            "archived",
        }
        if normalized_inline in allowed_statuses:
            same = normalized_inline == normalize_scalar(meta["status"])
            findings.append(
                Finding(
                    rel_repo,
                    line,
                    "DUPLICATE" if same else "CONFLICT",
                    (
                        "inline status duplicates frontmatter `status`"
                        if same
                        else f"frontmatter status {meta['status']!r} disagrees with inline {value!r}"
                    ),
                    "remove the inline status and keep frontmatter as the source of truth",
                )
            )

    identity_fields = {
        "owner": ("owner", "owners"),
        "author": ("author", "authors"),
        "main contact": ("owner", "owners"),
    }
    for label, fields in identity_fields.items():
        inline_identity = first_inline_value(preamble, body_start, {label})
        configured_field = next((field for field in fields if field in meta), None)
        if not inline_identity or configured_field is None:
            continue
        value, line = inline_identity
        configured = meta[configured_field]
        candidates = configured if isinstance(configured, list) else [configured]
        same = normalize_scalar(value) in {
            normalize_scalar(candidate) for candidate in candidates
        }
        findings.append(
            Finding(
                rel_repo,
                line,
                "DUPLICATE" if same else "CONFLICT",
                (
                    f"inline {label} duplicates frontmatter `{configured_field}`"
                    if same
                    else f"frontmatter `{configured_field}` disagrees with inline {label} {value!r}"
                ),
                f"keep `{configured_field}` in frontmatter and remove the inline copy",
            )
        )

    tags = meta.get("tags", [])
    if tags is None:
        tags = []
    if not isinstance(tags, list):
        findings.append(
            Finding(
                rel_repo,
                field_line(fm_text, "tags"),
                "CONFLICT",
                "`tags` is not a list",
                "use a YAML list of taxonomy values",
            )
        )
        tags = []
    else:
        for tag in tags:
            if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
                findings.append(
                    Finding(
                        rel_repo,
                        field_line(fm_text, "tags"),
                        "WARN",
                        f"tag {tag!r} does not use dimension:value syntax",
                        "map it to a configured taxonomy value",
                    )
                )
            elif valid_tags and tag not in valid_tags:
                findings.append(
                    Finding(
                        rel_repo,
                        field_line(fm_text, "tags"),
                        "WARN",
                        f"tag `{tag}` is absent from the configured taxonomy",
                        "use an existing value or update the taxonomy in the same change",
                    )
                )

    concept_type = meta.get("type")
    if valid_types and isinstance(concept_type, str) and concept_type not in valid_types:
        findings.append(
            Finding(
                rel_repo,
                field_line(fm_text, "type"),
                "WARN",
                f"type `{concept_type}` is absent from the configured taxonomy",
                "use an allowed type or update the taxonomy in the same change",
            )
        )

    confidence = next(
        (
            tag.split(":", 1)[1]
            for tag in tags
            if isinstance(tag, str) and tag.startswith("confidence:")
        ),
        None,
    )
    if confidence and meta.get("status") is not None:
        if normalize_scalar(confidence) != normalize_scalar(meta["status"]):
            findings.append(
                Finding(
                    rel_repo,
                    field_line(fm_text, "status"),
                    "CONFLICT",
                    f"status {meta['status']!r} disagrees with confidence tag `{confidence}`",
                    "choose one state and make status and confidence agree",
                )
            )

    lifecycle = next(
        (
            tag.split(":", 1)[1]
            for tag in tags
            if isinstance(tag, str) and tag.startswith("lifecycle:")
        ),
        None,
    )
    inline_phase = first_inline_value(preamble, body_start, {"current phase"})
    if lifecycle and inline_phase:
        value, line = inline_phase
        normalized_phase = normalize_scalar(re.sub(r"\bphase\b", "", value).strip())
        allowed_lifecycles = configured_values(valid_tags, "lifecycle")
        if normalized_phase in allowed_lifecycles and normalize_scalar(lifecycle) != normalized_phase:
            findings.append(
                Finding(
                    rel_repo,
                    line,
                    "CONFLICT",
                    f"lifecycle tag `{lifecycle}` disagrees with current phase {value!r}",
                    "keep lifecycle in frontmatter and remove or reconcile the body copy",
                )
            )

    h1 = H1_RE.search(body)
    if meta.get("title") and h1:
        body_title = re.sub(r"[*_`]", "", h1.group(1)).strip()
        if str(meta["title"]).strip() != body_title:
            findings.append(
                Finding(
                    rel_repo,
                    body_line(body_start, body, h1.start()),
                    "WARN",
                    f"frontmatter title {meta['title']!r} differs from H1 {body_title!r}",
                    "make the frontmatter title and H1 agree",
                )
            )

    if path.name not in set(frontmatter["reserved_files"]):
        if not KEBAB_RE.fullmatch(path.name):
            findings.append(
                Finding(
                    rel_repo,
                    None,
                    "WARN",
                    "filename is not lowercase kebab-case",
                    "rename it with git mv to a lowercase descriptive name",
                )
            )
        if DATE_IN_FILENAME_RE.search(path.stem):
            findings.append(
                Finding(
                    rel_repo,
                    None,
                    "WARN",
                    "filename contains a date",
                    f"remove the date from the name and use `{date_field}`",
                )
            )

    routed_roots = [
        safe_repo_path(repo, value)
        for value in config["topic_routing"].values()
    ]
    if routed_roots and not any(path == root or path.is_relative_to(root) for root in routed_roots):
        findings.append(
            Finding(
                rel_repo,
                None,
                "WARN",
                "concept is outside every configured topic-routing directory",
                "move it to the owning routed directory or update the repository contract",
            )
        )

    resources = meta.get("resource")
    if resources and len(body.split()) >= 180 and not MIRROR_NOTE_RE.search(body[:1200]):
        findings.append(
            Finding(
                rel_repo,
                field_line(fm_text, "resource"),
                "WARN",
                "long resource-linked concept has no canonical-source or synchronization note",
                "state whether the file summarizes or mirrors the linked source",
            )
        )
    return findings


def document_paths(
    repo: Path, bundle: Path, reserved: set[str], requested: Iterable[str]
) -> list[Path]:
    requested = list(requested)
    if not requested:
        return [
            path
            for path in sorted(bundle.rglob("*.md"))
            if path.name not in reserved
        ]
    paths: list[Path] = []
    for item in requested:
        path = Path(item)
        if not path.is_absolute():
            path = repo / path
        path = path.resolve()
        try:
            path.relative_to(bundle)
        except ValueError as exc:
            raise ValueError(f"path is outside configured bundle: {item}") from exc
        if not path.is_file():
            raise ValueError(f"document does not exist: {item}")
        if path.name not in reserved:
            paths.append(path)
    return sorted(set(paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check configured OKF metadata consistency."
    )
    parser.add_argument("repo", type=Path, help="repository root")
    parser.add_argument("paths", nargs="*", help="repo-relative documents; default is bundle")
    parser.add_argument("--config", type=Path, help="alternate config path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as a failing result",
    )
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        print(f"error: not a Git repository root: {repo}", file=sys.stderr)
        return 2
    try:
        config, loaded_from = load_contract(repo, args.config)
        bundle = safe_repo_path(repo, config["bundle_path"])
        if not bundle.is_dir():
            raise ValueError(f"configured bundle does not exist: {bundle}")
        taxonomy_value = config.get("taxonomy_path")
        taxonomy = safe_repo_path(repo, taxonomy_value) if taxonomy_value else None
        valid_tags, valid_types = parse_taxonomy(taxonomy)
        reserved = set(config["frontmatter"]["reserved_files"])
        paths = document_paths(repo, bundle, reserved, args.paths)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for path in paths:
        findings.extend(
            check_document(
                repo, bundle, path, config, valid_tags, valid_types
            )
        )
    order = {"CONFLICT": 0, "DUPLICATE": 1, "WARN": 2}
    findings.sort(key=lambda item: (order[item.severity], item.path, item.line or 0))
    for finding in findings:
        print(finding.render())

    counts = {
        severity: sum(item.severity == severity for item in findings)
        for severity in ("CONFLICT", "DUPLICATE", "WARN")
    }
    print(
        "\n"
        f"CONSISTENCY — {counts['CONFLICT']} conflict(s), "
        f"{counts['DUPLICATE']} duplicate(s), {counts['WARN']} warning(s) "
        f"across {len(paths)} document(s); config={loaded_from}"
    )
    failing = counts["CONFLICT"] + counts["DUPLICATE"]
    if args.strict:
        failing += counts["WARN"]
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
