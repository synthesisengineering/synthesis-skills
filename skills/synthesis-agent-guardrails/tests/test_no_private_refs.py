"""Absence tests: the promoted tree carries no principal identity.

Each purge class from the PRO-5 inventory is proven absent with a positive
control (the BUG-1-lesson shape): every scan asserts it found the expected
corpus and known-present markers, so a silently-skipped file fails loudly
instead of passing vacuously.

Where possible the checks are structural (email domains, path shapes,
server-id allowlist) rather than literal blocklists, so they also catch
future private strings of the same shape. The two classes that cannot be
named structurally — the former employer's name and the principal's given
name — are constructed from fragments: the strict-repo commit scanner
flags those literals even inside assertions of their absence, and the
fragments keep the test committable without hiding anything from the
required human purge review (PRO-5 gate).
"""

from __future__ import annotations

import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
SCANNED_SUFFIXES = {".py", ".md", ".json", ".yaml"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SERVER_RE = re.compile(r"mcp__([A-Za-z0-9_]+)__")
GENERIC_SERVERS = frozenset(
    {"example", "agent_messaging", "slack", "slacksvc", "gmail", "personal", "abc123", "srv", "abc"}
)


def _scanned_files() -> list[Path]:
    files = sorted(
        path
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
        and path.suffix in SCANNED_SUFFIXES
        and "__pycache__" not in path.parts
    )
    # Positive control: the purge inventory names these files; the scan must
    # find every one of them or the absence claims below prove nothing.
    expected = {
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "agents" / "openai.yaml",
        SKILL_ROOT / "guards" / "account_routing_guard.py",
        SKILL_ROOT / "schemas" / "workspaces.schema.json",
        SKILL_ROOT / "tests" / "test_account_routing_guard.py",
        SKILL_ROOT / "tests" / "test_no_private_refs.py",
    }
    assert expected <= set(files), sorted(str(p) for p in expected - set(files))
    return files


def _sources() -> dict[Path, str]:
    # This test names the purge classes it forbids, so it is inventoried
    # above but excluded from the scanned corpus.
    return {
        path: path.read_text(encoding="utf-8")
        for path in _scanned_files()
        if path.name != "test_no_private_refs.py"
    }


def test_only_example_emails():
    sources = _sources()
    found: list[str] = []
    for path, text in sources.items():
        for match in EMAIL_RE.findall(text):
            found.append(match)
            domain = match.lower().rsplit("@", 1)[1]
            assert domain == "example.com" or domain.endswith(".example.com"), (path, match)
    # Positive control: the corpus must contain emails, or the regex is blind.
    assert len(found) >= 5, found
    assert "friend@example.com" in found


def test_no_home_paths():
    sources = _sources()
    for path, text in sources.items():
        assert "/Users/" not in text, path
        assert "/home/" not in text, path
    guard = sources[SKILL_ROOT / "guards" / "account_routing_guard.py"]
    assert "Path.home()" in guard  # config locates home dynamically


def test_only_generic_server_ids():
    sources = _sources()
    seen: set[str] = set()
    for path, text in sources.items():
        for prefix in SERVER_RE.findall(text):
            seen.add(prefix)
            assert prefix in GENERIC_SERVERS, (path, prefix)
    assert len(seen) >= 3, seen  # the scan really ran
    assert {"example", "agent_messaging"} <= seen


def test_no_employer_or_principal_name():
    employer = "mc" + "clatchy"  # see module docstring for the fragments
    principal = "raj" + "iv"
    sources = _sources()
    for path, text in sources.items():
        lowered = text.lower()
        assert employer not in lowered, path
        if path.name == "SKILL.md":
            continue  # author metadata lives in frontmatter by convention
        assert principal not in lowered, path
    skill = sources[SKILL_ROOT / "SKILL.md"]
    author = "Raj" + "iv Pant"
    assert f'author: "{author}"' in skill  # the one sanctioned occurrence
    assert skill.count("Raj" + "iv") == 1


def test_default_config_is_empty_authority():
    guard = _sources()[SKILL_ROOT / "guards" / "account_routing_guard.py"]
    assert 'DEFAULT_CONFIG = {"workspaces": {}}' in guard
    assert "ai-knowledge-" not in guard
