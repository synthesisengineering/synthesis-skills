#!/usr/bin/env python3
"""Check configured OKF house-schema and body/frontmatter consistency.

Reads the repository contract `.agents/knowledge-base.yaml` (and its
`taxonomy_path`) and reports, for each concept document in the configured
bundle, `file:line — SEVERITY — finding` plus a fix:

1. inline metadata that duplicates frontmatter;
2. date aliases and inline dates that conflict with `frontmatter.date_field`;
3. status/confidence and lifecycle/current-phase conflicts;
4. missing required fields, fields outside the house schema, malformed tags,
   and values absent from the taxonomy;
5. long resource-linked concepts without a canonical-source note;
6. frontmatter title and H1 disagreement;
7. filename, date-in-name and topic-routing placement problems.

Exit 1 when a CONFLICT or DUPLICATE exists (warnings too with --strict);
exit 2 for a missing or invalid contract, or a path that escapes the repo.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root or the installed runtime: holds synthesis/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthesis import yamlish  # noqa: E402
from okf_validate import split_frontmatter  # noqa: E402  (beside this script; one splitter for all three)

CONFIG_RELATIVE = Path(".agents/knowledge-base.yaml")
TAG_RE = re.compile(r"^[a-z][a-z0-9-]*:[a-z0-9][a-z0-9.-]*$")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
INLINE_RE = re.compile(
    r"^\s*\*\*(Last Updated|Updated|Created|Status|Owner|Author|"
    r"Main Contact|Current Phase|Next Milestones)\s*:?\*\*\s*:?\s*(.*?)\s*$",
    re.IGNORECASE | re.MULTILINE)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
DATE_IN_FILENAME_RE = re.compile(r"(?:^|-)\d{4}(?:-\d{2})?(?:-\d{2})?(?:-|$)")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
MIRROR_NOTE_RE = re.compile(r"\b(mirror(?:s|ed)?|canonical source|source of truth|summary of)\b", re.IGNORECASE)
DEFAULT_STATUSES = {"canonical", "draft", "needs-verification", "archived"}
DATE_ALIASES = {"last_updated", "last-updated", "updated_at", "updated-at"}
ORDER = {"CONFLICT": 0, "DUPLICATE": 1, "WARN": 2}


@dataclass(frozen=True)
class Finding:
    path: str
    line: Optional[int]
    severity: str
    message: str
    fix: str

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location} — {self.severity} — {self.message}\n   fix: {self.fix}"


def field_line(text: str, field: str) -> Optional[int]:
    match = re.search(rf"^{re.escape(field)}\s*:", text, re.MULTILINE)
    return text[: match.start()].count("\n") + 2 if match else None


def normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def normalize_date(value: Any) -> Optional[str]:
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


def parse_taxonomy(path: Optional[Path]) -> tuple:
    """(valid dimension:value tags, valid types) from the taxonomy's code spans."""
    if path is None or not path.is_file():
        return set(), set()
    text = path.read_text(encoding="utf-8")
    tags = {token for token in CODE_SPAN_RE.findall(text) if TAG_RE.fullmatch(token)}
    types: set = set()
    in_type = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^\*\*type\*\*", stripped, re.IGNORECASE):
            in_type = True
            continue
        if in_type and (stripped.startswith("## ") or re.match(r"^\*\*[a-z][^*]*:\*\*", stripped, re.IGNORECASE)):
            break
        if in_type:
            types.update(t for t in CODE_SPAN_RE.findall(line) if re.fullmatch(r"[a-z][a-z0-9-]*", t))
    return tags, types


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


def load_contract(repo: Path, configured: Optional[Path]) -> tuple:
    path = repo / CONFIG_RELATIVE if configured is None else (configured if configured.is_absolute() else repo / configured)
    try:
        config = yamlish.load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing configuration: {path}") from exc
    except ValueError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError(f"configuration is not a mapping: {path}")
    try:
        fm = config["frontmatter"]
        shapes = ((fm, dict), (fm["required"], list), (fm["house"], list), (fm["date_field"], str),
                  (fm["reserved_files"], list), (config["bundle_path"], str), (config["topic_routing"], dict))
    except (KeyError, TypeError) as exc:
        raise ValueError(f"incomplete knowledge-base contract: {exc}") from exc
    if not all(isinstance(value, kind) for value, kind in shapes):
        raise ValueError("knowledge-base contract fields have invalid types")
    return config, path


def metadata_preamble(body: str) -> str:
    """Document-level metadata: the body before the first H2 or section break."""
    h1 = H1_RE.search(body)
    start = h1.end() if h1 else 0
    boundary = re.search(r"^(?:##\s+|---\s*$)", body[start:], re.MULTILINE)
    return body[: start + boundary.start() if boundary else len(body)]


def first_inline(preamble: str, body_start: int, labels: set) -> Optional[tuple]:
    for match in INLINE_RE.finditer(preamble):
        if match.group(1).lower() in labels:
            return match.group(2).strip(), body_start + preamble[: match.start()].count("\n")
    return None


def tag_value(tags: list, dimension: str) -> Optional[str]:
    return next((t.split(":", 1)[1] for t in tags if isinstance(t, str) and t.startswith(dimension + ":")), None)


def configured_values(valid_tags: set, dimension: str) -> set:
    return {tag.split(":", 1)[1] for tag in valid_tags if tag.startswith(dimension + ":")}


def check_document(repo: Path, bundle: Path, path: Path, config: dict, valid_tags: set, valid_types: set) -> list:
    rel = path.relative_to(repo).as_posix()
    findings: list = []

    def add(line, severity, message, fix):
        findings.append(Finding(rel, line, severity, message, fix))

    fm_text, body = split_frontmatter(path.read_text(encoding="utf-8"))
    body_start = fm_text.count("\n") + 3 if fm_text is not None else 1  # the body's first line number
    if fm_text is None:
        return [Finding(rel, 1, "CONFLICT", "missing or unterminated YAML frontmatter",
                        "add a parseable frontmatter block using the configured schema")]
    try:
        meta = yamlish.load(fm_text)
    except ValueError as exc:
        return [Finding(rel, 1, "CONFLICT", f"frontmatter is not parseable YAML: {exc}", "repair the YAML before shipping")]
    if not isinstance(meta, dict):
        return [Finding(rel, 1, "CONFLICT", "frontmatter is not a mapping", "replace it with a key-value mapping")]

    fm = config["frontmatter"]
    required, date_field = set(fm["required"]), fm["date_field"]
    for field in sorted(required):
        if meta.get(field) in (None, "", []):
            add(1, "CONFLICT", f"missing required frontmatter field `{field}`",
                f"add `{field}` using the configured schema and taxonomy")
    for field in sorted(set(meta) - required - set(fm["house"])):
        add(field_line(fm_text, field), "WARN", f"frontmatter field `{field}` is outside the configured schema",
            "add the field to the repository contract or remove it")
    for alias in sorted(a for a in DATE_ALIASES - {date_field} if a in meta):
        add(field_line(fm_text, alias), "CONFLICT", f"`{alias}` duplicates configured date field `{date_field}`",
            f"keep only `{date_field}`")

    preamble = metadata_preamble(body)
    configured_date = normalize_date(meta.get(date_field))
    inline_date = first_inline(preamble, body_start, {"last updated", "updated", "created"})
    if inline_date:
        value, line = inline_date
        inline_normalized = normalize_date(value)
        if configured_date and inline_normalized and configured_date != inline_normalized:
            add(line, "CONFLICT", f"{date_field} {configured_date} disagrees with inline date {value!r}",
                f"remove the inline date and keep `{date_field}` as the source of truth")
        else:
            add(line, "DUPLICATE", f"inline date duplicates frontmatter `{date_field}`",
                f"remove the inline date and keep `{date_field}` as the source of truth")

    inline_status = first_inline(preamble, body_start, {"status"})
    if inline_status and meta.get("status") is not None:
        value, line = inline_status
        if normalize_scalar(value) in (configured_values(valid_tags, "confidence") or DEFAULT_STATUSES):
            same = normalize_scalar(value) == normalize_scalar(meta["status"])
            add(line, "DUPLICATE" if same else "CONFLICT",
                "inline status duplicates frontmatter `status`" if same
                else f"frontmatter status {meta['status']!r} disagrees with inline {value!r}",
                "remove the inline status and keep frontmatter as the source of truth")

    for label, fields in (("owner", ("owner", "owners")), ("author", ("author", "authors")),
                          ("main contact", ("owner", "owners"))):
        inline_identity = first_inline(preamble, body_start, {label})
        field = next((f for f in fields if f in meta), None)
        if not inline_identity or field is None:
            continue
        value, line = inline_identity
        candidates = meta[field] if isinstance(meta[field], list) else [meta[field]]
        same = normalize_scalar(value) in {normalize_scalar(c) for c in candidates}
        add(line, "DUPLICATE" if same else "CONFLICT",
            f"inline {label} duplicates frontmatter `{field}`" if same
            else f"frontmatter `{field}` disagrees with inline {label} {value!r}",
            f"keep `{field}` in frontmatter and remove the inline copy")

    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        add(field_line(fm_text, "tags"), "CONFLICT", "`tags` is not a list", "use a YAML list of taxonomy values")
        tags = []
    for tag in tags:
        if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
            add(field_line(fm_text, "tags"), "WARN", f"tag {tag!r} does not use dimension:value syntax",
                "map it to a configured taxonomy value")
        elif valid_tags and tag not in valid_tags:
            add(field_line(fm_text, "tags"), "WARN", f"tag `{tag}` is absent from the configured taxonomy",
                "use an existing value or update the taxonomy in the same change")
    concept_type = meta.get("type")
    if valid_types and isinstance(concept_type, str) and concept_type not in valid_types:
        add(field_line(fm_text, "type"), "WARN", f"type `{concept_type}` is absent from the configured taxonomy",
            "use an allowed type or update the taxonomy in the same change")

    confidence = tag_value(tags, "confidence")
    if confidence and meta.get("status") is not None and normalize_scalar(confidence) != normalize_scalar(meta["status"]):
        add(field_line(fm_text, "status"), "CONFLICT",
            f"status {meta['status']!r} disagrees with confidence tag `{confidence}`",
            "choose one state and make status and confidence agree")
    lifecycle = tag_value(tags, "lifecycle")
    inline_phase = first_inline(preamble, body_start, {"current phase"})
    if lifecycle and inline_phase:
        value, line = inline_phase
        phase = normalize_scalar(re.sub(r"\bphase\b", "", value).strip())
        if phase in configured_values(valid_tags, "lifecycle") and normalize_scalar(lifecycle) != phase:
            add(line, "CONFLICT", f"lifecycle tag `{lifecycle}` disagrees with current phase {value!r}",
                "keep lifecycle in frontmatter and remove or reconcile the body copy")

    h1 = H1_RE.search(body)
    if meta.get("title") and h1:
        body_title = re.sub(r"[*_`]", "", h1.group(1)).strip()
        if str(meta["title"]).strip() != body_title:
            add(body_start + body[: h1.start()].count("\n"), "WARN",
                f"frontmatter title {meta['title']!r} differs from H1 {body_title!r}",
                "make the frontmatter title and H1 agree")

    if path.name not in set(fm["reserved_files"]):
        if not KEBAB_RE.fullmatch(path.name):
            add(None, "WARN", "filename is not lowercase kebab-case",
                "rename it with git mv to a lowercase descriptive name")
        if DATE_IN_FILENAME_RE.search(path.stem):
            add(None, "WARN", "filename contains a date", f"remove the date from the name and use `{date_field}`")
    routed = [safe_repo_path(repo, value) for value in config["topic_routing"].values()]
    if routed and not any(path == root or path.is_relative_to(root) for root in routed):
        add(None, "WARN", "concept is outside every configured topic-routing directory",
            "move it to the owning routed directory or update the repository contract")
    if meta.get("resource") and len(body.split()) >= 180 and not MIRROR_NOTE_RE.search(body[:1200]):
        add(field_line(fm_text, "resource"), "WARN",
            "long resource-linked concept has no canonical-source or synchronization note",
            "state whether the file summarizes or mirrors the linked source")
    return findings


def document_paths(repo: Path, bundle: Path, reserved: set, requested: Iterable[str]) -> list:
    requested = list(requested)
    if not requested:
        return [p for p in sorted(bundle.rglob("*.md")) if p.name not in reserved]
    paths = []
    for item in requested:
        path = Path(item) if Path(item).is_absolute() else repo / item
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


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Check configured OKF metadata consistency.")
    parser.add_argument("repo", type=Path, help="repository root")
    parser.add_argument("paths", nargs="*", help="repo-relative documents; default is bundle")
    parser.add_argument("--config", type=Path, help="alternate config path")
    parser.add_argument("--strict", action="store_true", help="treat warnings as a failing result")
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
        taxonomy = config.get("taxonomy_path")
        valid_tags, valid_types = parse_taxonomy(safe_repo_path(repo, taxonomy) if taxonomy else None)
        paths = document_paths(repo, bundle, set(config["frontmatter"]["reserved_files"]), args.paths)
        findings = [f for p in paths for f in check_document(repo, bundle, p, config, valid_tags, valid_types)]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    findings.sort(key=lambda item: (ORDER[item.severity], item.path, item.line or 0))
    for finding in findings:
        print(finding.render())
    counts = {s: sum(item.severity == s for item in findings) for s in ORDER}
    print(f"\nCONSISTENCY — {counts['CONFLICT']} conflict(s), {counts['DUPLICATE']} duplicate(s), "
          f"{counts['WARN']} warning(s) across {len(paths)} document(s); config={loaded_from}")
    failing = counts["CONFLICT"] + counts["DUPLICATE"] + (counts["WARN"] if args.strict else 0)
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
