"""Shared loader for the anti-shortcut catalog.

Reads `~/.synthesis/anti-shortcut-catalog.yaml` (or `$ANTI_SHORTCUT_CATALOG_PATH`)
once at module import time. Compiles every phrase's regex and every exempt_when
regex upfront. All matcher calls operate on the pre-compiled catalog.

Failure mode: a missing or malformed catalog is logged once to stderr and
replaced with an empty catalog. Hooks importing this module continue to work
as no-ops rather than crashing. This is the artifact-grade choice: a Stop hook
that silently breaks on a corrupted YAML would be worse than one that simply
detects nothing until the catalog is fixed.

Used by the lazy-shortcut detectors (Stop-hook backstops) and the
sub-agent brief scanner (PreToolUse on dispatch) across clients.

Rules live in the catalog file, never in this loader: phrases,
categories, escalation, acknowledgment signals, and per-category
rewrite hints are all principal-supplied content. An absent catalog
loads empty (hooks pass, doctors report unconfigured).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover — pyyaml is a test dependency.
    yaml = None  # type: ignore


# ---------------------------------------------------------------------------
# Configuration: catalog file path
# ---------------------------------------------------------------------------

_DEFAULT_CATALOG_PATH = Path.home() / ".synthesis" / "anti-shortcut-catalog.yaml"


def _resolve_catalog_path() -> Path:
    """Resolve the catalog path. Honors ANTI_SHORTCUT_CATALOG_PATH for tests."""
    override = os.environ.get("ANTI_SHORTCUT_CATALOG_PATH")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_CATALOG_PATH


# ---------------------------------------------------------------------------
# Acknowledgment signals: regexes from the catalog's `acknowledgment_signals`
# list. An agent emitting one resets the session count when the escalation
# logic kicks in (see escalation.reset_on_acknowledgment). The signals are
# principal content — methodology wording belongs in the catalog file, not
# in this loader — so an empty list means acknowledgments never match.
# ---------------------------------------------------------------------------


def is_acknowledgment(text: str) -> bool:
    """Return True if the text contains an explicit antipattern acknowledgment."""
    if not text:
        return False
    return any(p.search(text) for p in _CATALOG.ack_signals)


# ---------------------------------------------------------------------------
# Data model: frozen dataclasses for the compiled catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryInfo:
    """A category groups related phrases. From catalog `categories.<id>`."""
    id: str
    description: str
    severity: str  # high | medium | low
    hint: str = ""  # principal-supplied rewrite hint for the category


@dataclass(frozen=True)
class PhraseEntry:
    """One compiled phrase entry. From catalog `phrases[]`."""
    id: str
    raw_phrase: str       # original pattern text from YAML, for reporting
    match_kind: str       # literal | regex | phrase_with_context
    category: str         # category id
    severity: str         # propagated from CategoryInfo at compile time
    pattern: re.Pattern   # compiled regex for matching
    exempts: tuple        # tuple[re.Pattern] for exempt_when checks
    rationale: str        # one-line rationale
    lesson: Optional[str] # path to canonical incident record
    skill_ref: Optional[str]  # path within the skill


@dataclass(frozen=True)
class EscalationPolicy:
    """Escalation thresholds from catalog `escalation`."""
    warn_threshold: int
    block_threshold: int
    reset_on_acknowledgment: bool


@dataclass(frozen=True)
class CatalogData:
    """Compiled catalog. Immutable after load."""
    version: int
    last_updated: str
    categories: dict           # category_id -> CategoryInfo
    phrases: tuple             # tuple[PhraseEntry]
    escalation: EscalationPolicy
    excerpt_window_chars: int
    ack_signals: tuple = tuple()  # tuple[re.Pattern] from acknowledgment_signals


_EMPTY_CATALOG = CatalogData(
    version=0,
    last_updated="",
    categories={},
    phrases=tuple(),
    escalation=EscalationPolicy(warn_threshold=1, block_threshold=3, reset_on_acknowledgment=True),
    excerpt_window_chars=120,
    ack_signals=tuple(),
)


@dataclass(frozen=True)
class Detection:
    """One match found in a body of text."""
    phrase_id: str
    category: str
    severity: str
    excerpt: str
    position: int           # character offset of the match start
    matched_text: str       # the actual substring that matched (useful for regex matches)


# ---------------------------------------------------------------------------
# Loading and compilation
# ---------------------------------------------------------------------------


def _warn(msg: str) -> None:
    """Emit a single-line warning to stderr."""
    print(f"[anti-shortcut-catalog] {msg}", file=sys.stderr)


def _compile_phrase(entry: dict, categories: dict) -> Optional[PhraseEntry]:
    """Compile one phrase entry from the raw catalog dict. Returns None on failure."""
    try:
        phrase_id = entry["id"]
        raw = entry["phrase"]
        match_kind = entry.get("match", "literal")
        category_id = entry["category"]

        cat = categories.get(category_id)
        if cat is None:
            _warn(f"phrase {phrase_id!r} references unknown category {category_id!r}; skipping")
            return None

        # Compile the pattern according to match_kind. `phrase_with_context`
        # uses the same compilation as `literal` at v1; the surrounding-window
        # logic is applied at match time via the excerpt window, not via a
        # different regex shape.
        if match_kind == "regex":
            pattern = re.compile(raw, re.IGNORECASE)
        elif match_kind in ("literal", "phrase_with_context"):
            pattern = re.compile(re.escape(raw), re.IGNORECASE)
        else:
            _warn(f"phrase {phrase_id!r} has unknown match kind {match_kind!r}; skipping")
            return None

        # exempt_when: list of regex patterns. Each compiled independently.
        exempts = tuple(
            re.compile(p, re.IGNORECASE)
            for p in (entry.get("exempt_when") or [])
        )

        return PhraseEntry(
            id=phrase_id,
            raw_phrase=raw,
            match_kind=match_kind,
            category=category_id,
            severity=cat.severity,
            pattern=pattern,
            exempts=exempts,
            rationale=(entry.get("rationale") or "").strip(),
            lesson=entry.get("lesson"),
            skill_ref=entry.get("skill_ref"),
        )
    except re.error as e:
        _warn(f"phrase {entry.get('id', '<no-id>')!r}: regex compile failed ({e}); skipping")
        return None
    except Exception as e:
        _warn(f"phrase {entry.get('id', '<no-id>')!r}: compile failed ({type(e).__name__}: {e}); skipping")
        return None


def _load_and_compile() -> CatalogData:
    """Read the catalog YAML and produce a CatalogData. Raises on hard failure."""
    if yaml is None:
        raise RuntimeError("pyyaml is not installed")

    path = _resolve_catalog_path()
    if not path.exists():
        raise FileNotFoundError(f"catalog not found at {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("catalog top-level is not a mapping")

    version = int(data.get("version", 0))
    if version != 1:
        _warn(f"catalog version {version} is not v1; proceeding cautiously")

    # Parse categories
    categories: dict = {}
    for cat_id, cat_body in (data.get("categories") or {}).items():
        if not isinstance(cat_body, dict):
            continue
        categories[cat_id] = CategoryInfo(
            id=cat_id,
            description=(cat_body.get("description") or "").strip(),
            severity=cat_body.get("severity", "medium"),
            hint=(cat_body.get("hint") or "").strip(),
        )

    # Parse + compile phrases
    raw_phrases = data.get("phrases") or []
    phrases = []
    for entry in raw_phrases:
        if not isinstance(entry, dict):
            continue
        compiled = _compile_phrase(entry, categories)
        if compiled is not None:
            phrases.append(compiled)

    # Parse escalation
    esc_raw = data.get("escalation") or {}
    escalation = EscalationPolicy(
        warn_threshold=int(esc_raw.get("warn_threshold", 1)),
        block_threshold=int(esc_raw.get("block_threshold", 3)),
        reset_on_acknowledgment=bool(esc_raw.get("reset_on_acknowledgment", True)),
    )

    match_settings = data.get("match") or {}
    excerpt_window = int(match_settings.get("excerpt_window_chars", 120))

    ack_signals = []
    for raw in data.get("acknowledgment_signals") or []:
        try:
            ack_signals.append(re.compile(str(raw), re.IGNORECASE))
        except re.error as exc:
            _warn(f"acknowledgment signal {raw!r}: regex compile failed ({exc}); skipping")

    return CatalogData(
        version=version,
        last_updated=str(data.get("last_updated", "")),
        categories=categories,
        phrases=tuple(phrases),
        escalation=escalation,
        excerpt_window_chars=excerpt_window,
        ack_signals=tuple(ack_signals),
    )


# ---------------------------------------------------------------------------
# Module-level eager load with error guard
# ---------------------------------------------------------------------------


try:
    _CATALOG = _load_and_compile()
except Exception as e:  # broad on purpose — see module docstring
    _warn(f"load failed ({type(e).__name__}: {e}); using empty catalog")
    _CATALOG = _EMPTY_CATALOG


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_catalog() -> CatalogData:
    """Return the loaded catalog data (already compiled)."""
    return _CATALOG


def iter_phrases() -> Iterable[PhraseEntry]:
    """Iterate the compiled phrase entries."""
    yield from _CATALOG.phrases


def _extract_excerpt(text: str, position: int, length: int, window: int) -> str:
    """Pull a windowed excerpt around a match for logging."""
    start = max(0, position - window)
    end = min(len(text), position + length + window)
    excerpt = text[start:end].replace("\n", " ").replace("\r", " ").strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{excerpt}{suffix}"


def _is_exempt(text: str, position: int, length: int, exempts: tuple, window: int) -> bool:
    """Return True if any exempt_when regex matches within the local window."""
    if not exempts:
        return False
    start = max(0, position - window)
    end = min(len(text), position + length + window)
    local = text[start:end]
    return any(p.search(local) for p in exempts)


def match_in_text(text: str, *, exclude_exempt: bool = True) -> list:
    """Scan `text` and return a list of Detection records.

    When `exclude_exempt` is True (the default), occurrences in a context that
    matches the phrase's exempt_when patterns are filtered out — these are
    discussions of the phrase rather than applications of it.
    """
    if not text or not _CATALOG.phrases:
        return []

    detections = []
    window = _CATALOG.excerpt_window_chars

    for phrase in _CATALOG.phrases:
        for match in phrase.pattern.finditer(text):
            pos = match.start()
            length = match.end() - match.start()

            if exclude_exempt and _is_exempt(text, pos, length, phrase.exempts, window):
                continue

            detections.append(Detection(
                phrase_id=phrase.id,
                category=phrase.category,
                severity=phrase.severity,
                excerpt=_extract_excerpt(text, pos, length, window),
                position=pos,
                matched_text=text[pos:pos + length],
            ))

    return detections


def suggested_rewrite_hint(phrase_id: str) -> str:
    """Return a one-sentence rewrite suggestion for a phrase id.

    The hint comes from the phrase's category in the catalog file; the
    loader keeps only the generic fallback. Terse, actionable.
    """
    phrase = next((p for p in _CATALOG.phrases if p.id == phrase_id), None)
    if phrase is None:
        return "Pattern not in catalog; describe the desired completeness explicitly."

    category = _CATALOG.categories.get(phrase.category)
    hint = (category.hint if category else "") or "Rewrite to address the antipattern directly."
    if phrase.rationale:
        return f"{hint} (Rationale: {phrase.rationale.rstrip('.')})"
    return hint


# ---------------------------------------------------------------------------
# Standalone test invocation (handy for one-off debugging)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read()

    cat = load_catalog()
    print(f"[catalog] version={cat.version} last_updated={cat.last_updated} "
          f"phrases={len(cat.phrases)} categories={len(cat.categories)}", file=sys.stderr)

    detections = match_in_text(text)
    if not detections:
        print("[no detections]", file=sys.stderr)
        sys.exit(0)

    for d in detections:
        print(
            f"{d.severity:6}  {d.category:20}  {d.phrase_id:30}  "
            f"matched={d.matched_text!r}  excerpt={d.excerpt!r}"
        )
        print(f"        hint: {suggested_rewrite_hint(d.phrase_id)}")
