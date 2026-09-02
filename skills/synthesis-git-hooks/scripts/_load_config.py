#!/usr/bin/env python3
"""synthesis-engineering git-hook config loader (sidecar) — v2.

Reads ~/.synthesis/git-hook-config.yaml (or `$SYNTHESIS_GIT_HOOK_CONFIG`),
classifies the current repo by examining its push remotes against the
configured `personal_remote_patterns`, and emits the active pattern set
for the bash engine at `./pre-commit`.

v2 design changes (fail-closed hardening):

* **Zero third-party dependencies.** v1 imported PyYAML; when the invoking
  environment's `python3` lacked it, the sidecar exited 2 and the engine's
  `eval "$(...)"` discarded that status — the hook then treated "engine
  broken" as "nothing to scan" and passed the commit unscanned. Protection
  silently varied with PATH resolution across interpreters. v2 vendors a
  strict YAML-subset parser (stdlib only) so ANY python3 >= 3.6 yields the
  same result on every machine, every environment, every PATH.
* **Success sentinel.** `--emit-shell-vars` prints `SYNTHESIS_SIDECAR_OK=1`
  as its final line. The engine requires it; absence means the sidecar died
  mid-emit and the commit is blocked (fail closed).
* **Strict parsing.** Anything outside the supported YAML subset (tabs,
  flow style `[...]`/`{...}`, anchors, multi-line scalars) is a hard error,
  never a guess. A policy file that cannot be parsed with certainty blocks
  commits until fixed.
* **`--doctor`.** Self-check for rituals/bootstrap: config parses, every
  pattern compiles under both Python `re` and `grep -E`, core.hooksPath is
  wired, installed engine matches the skill source (drift detection), and
  the cwd repo's classification + chained hook are reported. The drift
  source resolves portably — `$SYNTHESIS_GIT_HOOKS_SOURCE` (authoritative;
  invalid values fail closed), else this script's own directory when it is
  not itself an installed copy, else documented install locations — never
  a hardcoded personal checkout path.

Supported config subset (see README / SKILL.md):
  - comments (# ...), full-line or trailing outside quotes
  - nested mappings via 2+-space indentation: `key:` / `key: value`
  - string lists: `- item`, `- 'item'`, `- "item"`
  - scalars: single/double-quoted strings, bare strings, ints, true/false

Exit codes: 0 success · 2 config missing/unparsable/invalid.

This file ships with the `synthesis-git-hooks` skill at
https://github.com/synthesisengineering/synthesis-skills.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any, List, Optional, Tuple

SIDECAR_VERSION = "2.4.0"
REQUIRED_CONFIG_VERSION = 2

DEFAULT_CONFIG = Path.home() / ".synthesis" / "git-hook-config.yaml"

# The installed engine includes the coordination runtime because a configured
# board turns check-staged into a fail-closed commit boundary. The source files
# remain canonical in synthesis-project-management; source_engine_path maps the
# dependency instead of duplicating it in this skill.
CORE_ENGINE_FILES = ("pre-commit", "commit-msg", "_load_config.py")
COORDINATION_ENGINE_FILES = (
    "coordination.py",
    "coordination_schema.py",
    "pointer_lock.py",
    "peer_addressing.py",
)
ENGINE_FILES = CORE_ENGINE_FILES + COORDINATION_ENGINE_FILES
COORDINATION_ASSET = "session-words-v1.txt.zlib.b85"

SOURCE_ENV = "SYNTHESIS_GIT_HOOKS_SOURCE"
SOURCE_POINTER_NAME = "source-path"


class ConfigError(Exception):
    """Raised for any config condition we cannot interpret with certainty."""


# ─── strict YAML-subset parser (stdlib only) ─────────────────────────────

def _strip_trailing_comment(text: str) -> str:
    """Remove a trailing ` # comment` that is OUTSIDE any quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(text):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or text[i - 1] in (" ", "\t"):
                return text[:i].rstrip()
    return text.rstrip()


def _parse_scalar(raw: str, lineno: int) -> Any:
    """Parse a scalar value: quoted string, bare string, int, or bool."""
    s = raw.strip()
    if not s:
        raise ConfigError(f"line {lineno}: empty scalar value")
    if s[0] in ("[", "{"):
        raise ConfigError(
            f"line {lineno}: flow-style YAML ('{s[0]}...') is outside the "
            "supported subset"
        )
    if s[0] in ("&", "*", "|", ">", "?"):
        raise ConfigError(
            f"line {lineno}: YAML feature '{s[0]}' is outside the supported "
            "subset"
        )
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        # Literal text only. `unicode_escape` would silently turn a regex
        # `\b` into a backspace character: the pattern still compiles, the
        # doctor still passes, and the protection is dead.
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if s[0] in ("'", '"'):
        raise ConfigError(f"line {lineno}: unterminated quoted string")
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?[0-9]+", s):
        return int(s)
    return s


def _split_key(line: str, lineno: int) -> Tuple[str, str]:
    """Split `key: rest` at the first colon outside quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ":" and not in_single and not in_double:
            key = line[:i].strip()
            rest = line[i + 1:].strip()
            if not key:
                raise ConfigError(f"line {lineno}: empty mapping key")
            if key[0] in ("'", '"'):
                key = str(_parse_scalar(key, lineno))
            return key, rest
    raise ConfigError(
        f"line {lineno}: expected `key:` or `key: value`, got: {line.strip()!r}"
    )


def parse_simple_yaml(text: str) -> dict:
    """Parse the supported YAML subset. Raise ConfigError on ANYTHING else.

    Never guesses: a construct outside the subset is a hard error so the
    engine fails closed instead of running with a misread policy.
    """
    root: dict = {}
    # stack of (indent, container); root container is the dict at indent -1
    stack: List[Tuple[int, Any]] = [(-1, root)]
    pending_key: Optional[Tuple[int, dict, str]] = None  # (indent, parent, key)

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        if "\t" in raw_line:
            raise ConfigError(
                f"line {lineno}: tab character — use spaces (strict subset)"
            )
        line = _strip_trailing_comment(raw_line)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()

        # Resolve pending key (a `key:` opened a nested container).
        if pending_key is not None:
            p_indent, p_parent, p_key = pending_key
            if indent > p_indent:
                container: Any = [] if content.startswith("- ") or content == "-" else {}
                p_parent[p_key] = container
                stack.append((indent, container))
                pending_key = None
            else:
                # `key:` with nothing nested → explicit empty mapping.
                p_parent[p_key] = {}
                pending_key = None

        # Pop levels shallower than this line's indent.
        while stack and indent < stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigError(f"line {lineno}: indentation underflow")
        cur_indent, cur = stack[-1]
        if indent > cur_indent and cur_indent != -1:
            raise ConfigError(
                f"line {lineno}: unexpected indent (no open block at "
                f"column {indent})"
            )

        if content.startswith("- ") or content == "-":
            if not isinstance(cur, list):
                raise ConfigError(
                    f"line {lineno}: list item outside a list context"
                )
            item_raw = content[1:].strip()
            if not item_raw:
                raise ConfigError(
                    f"line {lineno}: nested list structures are outside the "
                    "supported subset"
                )
            if item_raw.endswith(":") or re.match(r"^[^'\"]*:\s", item_raw):
                raise ConfigError(
                    f"line {lineno}: mappings inside lists are outside the "
                    "supported subset"
                )
            cur.append(_parse_scalar(item_raw, lineno))
            continue

        if not isinstance(cur, dict):
            raise ConfigError(
                f"line {lineno}: mapping entry inside a list is outside the "
                "supported subset"
            )
        key, rest = _split_key(content, lineno)
        if rest == "":
            pending_key = (indent, cur, key)
        else:
            cur[key] = _parse_scalar(rest, lineno)

    if pending_key is not None:
        p_indent, p_parent, p_key = pending_key
        p_parent[p_key] = {}
    return root


# ─── policy logic (unchanged semantics from v1) ──────────────────────────

def get_push_remotes() -> List[str]:
    """Return the URLs of all push remotes for the cwd repo, or []."""
    try:
        result = subprocess.run(
            ["git", "remote", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:  # pragma: no cover - git not on PATH
        return []
    urls: List[str] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "(push)":
            urls.append(parts[1])
    return urls


def _match_any(patterns: List[str], url: str) -> bool:
    return any(re.search(p, url, re.IGNORECASE) for p in patterns)


def classify_repo(config: dict, push_urls: List[str]) -> str:
    """Classify the repo by PUBLICATION SURFACE, not repo visibility.

    Returns one of three classes, decided in strict-first precedence:

    - ``"strict"`` when ANY push remote matches ``strict_repo_patterns``
      (public OSS and multi-tenant repos pinned strict even when their
      remotes would otherwise read as personal), when the remote list is
      empty, or when no other class matches. Full Tier 1, no allowances.
    - ``"public-surface"`` when EVERY push remote matches
      ``public_surface_patterns``: repositories whose content the user
      personally authors and publishes (their sites). Full Tier 1, minus
      only the names the disclosure ledger records as published-precedent.
    - ``"personal"`` when EVERY push remote matches
      ``personal_remote_patterns``: content only the user reads. Tier 0
      only, unchanged semantics.

    The old model classified by remote ownership alone, which failed in
    both directions: it blocked the user's own published biography on
    their sites, and it left published surfaces with personal remotes
    completely unguarded.
    """
    if not push_urls:
        return "strict"
    strict_patterns = flatten_patterns(config.get("strict_repo_patterns") or [])
    surface_patterns = flatten_patterns(config.get("public_surface_patterns") or [])
    personal_patterns = flatten_patterns(
        config.get("personal_remote_patterns") or []
    )
    if strict_patterns and any(_match_any(strict_patterns, u) for u in push_urls):
        return "strict"
    if surface_patterns and all(_match_any(surface_patterns, u) for u in push_urls):
        return "public-surface"
    # Escalation, never demotion: a repo that partially matches a published
    # or strict surface must not fall THROUGH to the least-protected class
    # because a broad personal namespace pattern also matches it.
    if surface_patterns and any(_match_any(surface_patterns, u) for u in push_urls):
        return "strict"
    if personal_patterns and all(_match_any(personal_patterns, u) for u in push_urls):
        return "personal"
    return "strict"


def flatten_patterns(node: Any) -> List[str]:
    """Recursively gather string leaves from a config node (list/dict/str)."""
    out: List[str] = []
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, list):
        for item in node:
            out.extend(flatten_patterns(item))
    elif isinstance(node, dict):
        for value in node.values():
            out.extend(flatten_patterns(value))
    return out


def load_ledger_allowances(config: dict) -> List[str]:
    """Read the disclosure ledger and return its allowed hook patterns.

    The ledger is the machine-readable record of published-precedent
    disclosures: names the user has personally published in biography
    register on their own public surfaces, each entry carrying evidence
    citations. Entries opt specific Tier-1 patterns out of enforcement in
    ``public-surface`` repos ONLY, via ``hook_patterns`` values that must
    TEXTUALLY EQUAL entries in ``tier_1_strict_only`` — exact string
    equality, so every allowance is auditable and no regex-subsumption
    reasoning is involved.

    Fail closed: a configured ledger path that is missing or unparsable is
    a ConfigError (the sidecar exits 2 and the engine blocks the commit).
    No configured ledger simply means no allowances.
    """
    path_value = config.get("disclosure_ledger")
    if not path_value:
        return []
    path = Path(os.path.expanduser(str(path_value)))
    if not path.exists():
        raise ConfigError(
            f"disclosure_ledger configured but missing: {path} — "
            "public-surface allowances refuse to run without their ledger"
        )
    try:
        ledger = parse_simple_yaml(path.read_text())
    except ConfigError as exc:
        raise ConfigError(f"disclosure ledger unparsable ({path}): {exc}")
    entities = ledger.get("entities")
    if not isinstance(entities, dict) or not entities:
        raise ConfigError(
            f"disclosure ledger has no entities mapping: {path}"
        )
    # An allowance may only ever subtract an IDENTITY pattern (who), never a
    # topic pattern (what). Without this, a ledger entry could quietly
    # disable NDA, compensation, or internal-URL detection.
    allowed_groups = flatten_patterns(
        config.get("ledger_allowance_groups") or ["confidential_names"]
    )
    tier1 = config.get("tier_1_strict_only") or {}
    eligible = set()
    for group in allowed_groups:
        eligible.update(flatten_patterns(tier1.get(group) or []))
    registers_vocabulary = set(
        flatten_patterns(config.get("ledger_registers") or ["biography"])
    )
    allowances: List[str] = []
    for name, entry in entities.items():
        if not isinstance(entry, dict):
            raise ConfigError(
                f"disclosure ledger entity {name!r} is not a mapping: {path}"
            )
        if not flatten_patterns(entry.get("evidence") or []):
            raise ConfigError(
                f"disclosure ledger entity {name!r} has no evidence "
                f"citations — precedent without evidence is not precedent: "
                f"{path}"
            )
        registers = flatten_patterns(entry.get("registers") or [])
        if not registers:
            raise ConfigError(
                f"disclosure ledger entity {name!r} declares no registers: "
                f"{path}"
            )
        for register in registers:
            if register not in registers_vocabulary:
                raise ConfigError(
                    f"disclosure ledger entity {name!r} declares register "
                    f"{register!r}, which is not in the approved vocabulary "
                    f"({', '.join(sorted(registers_vocabulary))}): {path}"
                )
        for pattern in flatten_patterns(entry.get("hook_patterns") or []):
            if pattern not in eligible:
                raise ConfigError(
                    f"disclosure ledger entity {name!r} claims hook pattern "
                    f"{pattern!r}, which is not in an allowance-eligible "
                    f"group ({', '.join(allowed_groups)}) — allowances may "
                    f"only subtract identity patterns: {path}"
                )
            allowances.append(pattern)
    return allowances


def build_active_regex(config: dict, repo_class: str) -> str:
    """Concatenate the active patterns into a single alternation regex."""
    parts: List[str] = []
    tier0 = config.get("tier_0_always") or {}
    parts.extend(flatten_patterns(tier0))
    if repo_class == "strict":
        tier1 = config.get("tier_1_strict_only") or {}
        parts.extend(flatten_patterns(tier1))
    elif repo_class == "public-surface":
        tier1 = config.get("tier_1_strict_only") or {}
        allowed = set(load_ledger_allowances(config))
        # Published surfaces enforce the IDENTITY boundary (who is named or
        # identifiable), not private-notes topic vocabulary. Words like
        # "salary" or "proprietary" occur legitimately across a long
        # published archive; an unapproved NAME is the actual exposure.
        # Absent explicit configuration every group applies (fail closed).
        groups = flatten_patterns(config.get("public_surface_groups") or [])
        selected = (
            {g: tier1.get(g) for g in groups if tier1.get(g) is not None}
            if groups
            else tier1
        )
        parts.extend(
            p for p in flatten_patterns(selected) if p not in allowed
        )
    seen: set = set()
    deduped: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return "|".join(deduped)


def build_allowlist_regex(config: dict) -> str:
    """Concatenate allowlist lines (legitimate matches to suppress)."""
    parts = flatten_patterns(config.get("allowlist_lines") or [])
    return "|".join(parts)


# Built-in path exclusions — paths whose content is, by design, the pattern
# catalog itself. The diff scanner skips these so adding a name to the policy
# is not flagged as leaking it.
DEFAULT_DIFF_EXCLUDE_PATHS = (
    r'(^|/)\.githooks/pre-commit$',
    r'(^|/)\.githooks/extra-patterns\.ya?ml$',
    r'^\.synthesis/git-hook-config\.ya?ml$',
    r'(^|/)git-hook-config\.example\.ya?ml$',
    r'(^|/)anti-shortcut-catalog\.ya?ml$',
    # The disclosure-policy methodology and the hook engine's own docs and
    # tests discuss the pattern system by example — pattern-catalog class.
    # ANCHORED to their real locations: a bare basename anywhere would be a
    # free pass any repo could claim by naming a file conveniently.
    r'^skills/synthesis-disclosure-policy/',
    r'^skills/synthesis-git-hooks/',
    r'^agent-control/git-hook-config\.ya?ml$',
    r'^agent-control/disclosure/ledger\.ya?ml$',
)

# Tier 0 is never excluded: credentials in any path, in any repo class,
# always block. Path exclusions exist for pattern-catalog files, whose
# risk is false positives on Tier 1 vocabulary — never for secrets.



def build_diff_exclude_regex(config: dict) -> str:
    """Concatenate path-exclusion regexes (defaults + user-configured)."""
    user_paths = flatten_patterns(config.get("diff_exclude_paths") or [])
    all_paths = list(DEFAULT_DIFF_EXCLUDE_PATHS) + user_paths
    return "|".join(all_paths)


ALL_PATTERN_KEYS = (
    "personal_remote_patterns",
    "strict_repo_patterns",
    "public_surface_patterns",
    "allowlist_lines",
    "diff_exclude_paths",
)


def validate_all_patterns(config: dict) -> List[str]:
    """Return problems for every configured regex in the policy.

    v2.1 validated only the tier patterns. An invalid exclusion or
    allowlist regex made grep fail, `|| true` swallowed it, and the engine
    ran with scanning silently disabled while the doctor reported healthy.
    """
    problems: List[str] = []
    groups = {
        "tier_0_always": flatten_patterns(config.get("tier_0_always") or {}),
        "tier_1_strict_only": flatten_patterns(
            config.get("tier_1_strict_only") or {}
        ),
    }
    for key in ALL_PATTERN_KEYS:
        groups[key] = flatten_patterns(config.get(key) or [])
    for key, patterns in groups.items():
        for pattern in patterns:
            if not pattern:
                problems.append(
                    f"{key}: empty pattern — an empty alternation branch "
                    "matches everything or nothing depending on position"
                )
                continue
            if any(ord(ch) < 32 for ch in pattern):
                problems.append(
                    f"{key}: pattern contains a control character "
                    f"({pattern!r}) — a regex escape was interpreted as a "
                    "literal (check double-quoted YAML scalars)"
                )
            try:
                # POSIX bracket expressions ([[:alnum:]]) are valid ERE and
                # are what grep actually runs; Python's parser warns about
                # them as "nested sets". The compile here is only a validity
                # smoke test, so silence that noise — a protective tool that
                # prints benign warnings teaches its user to ignore it.
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    re.compile(pattern)
            except re.error as exc:
                problems.append(f"{key}: rejected by python re: {pattern!r} ({exc})")
            err = _grep_validates(pattern)
            if err:
                problems.append(f"{key}: rejected by grep -E: {pattern!r} ({err})")
    return problems


def load_config(path: Path) -> dict:
    if not path.exists():
        print(
            f"synthesis-git-hooks: config not found at {path}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        config = parse_simple_yaml(path.read_text())
    except ConfigError as exc:
        print(
            f"synthesis-git-hooks: cannot parse {path}: {exc}\n"
            "  The policy engine refuses to guess. Fix the config (or reduce "
            "it to the supported subset documented in the skill README).",
            file=sys.stderr,
        )
        sys.exit(2)
    if not isinstance(config, dict) or not config:
        print(
            f"synthesis-git-hooks: config at {path} is not a mapping",
            file=sys.stderr,
        )
        sys.exit(2)
    if not flatten_patterns(config.get("tier_0_always") or {}):
        print(
            f"synthesis-git-hooks: config at {path} defines no tier_0_always "
            "patterns — refusing to run with an empty credential tier "
            "(fail closed).",
            file=sys.stderr,
        )
        sys.exit(2)
    version = config.get("config_version")
    if not isinstance(version, int) or version < REQUIRED_CONFIG_VERSION:
        print(
            f"synthesis-git-hooks: config at {path} declares config_version "
            f"{version!r}; this engine (v{SIDECAR_VERSION}) requires "
            f"{REQUIRED_CONFIG_VERSION}. A v1 config paired with this engine "
            "would silently skip the surface classes and ledger. Update the "
            "config, or reinstall the matching engine.",
            file=sys.stderr,
        )
        sys.exit(2)
    coordination_board = config.get("coordination_board")
    if coordination_board is not None and (
        not isinstance(coordination_board, str) or not coordination_board.strip()
    ):
        print(
            "synthesis-git-hooks: coordination_board must be a non-empty "
            "path string when configured (fail closed)",
            file=sys.stderr,
        )
        sys.exit(2)
    problems = validate_all_patterns(config)
    if problems:
        print(
            "synthesis-git-hooks: invalid pattern(s) in "
            f"{path} (fail closed):\n  " + "\n  ".join(problems),
            file=sys.stderr,
        )
        sys.exit(2)
    return config


def emit_shell_vars(config: dict) -> None:
    push_urls = get_push_remotes()
    try:
        repo_class = classify_repo(config, push_urls)
    except re.error as exc:
        print(
            f"synthesis-git-hooks: classification pattern invalid: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        active = build_active_regex(config, repo_class)
    except ConfigError as exc:
        print(f"synthesis-git-hooks: {exc}", file=sys.stderr)
        sys.exit(2)
    # Commit messages never get ledger allowances: a message names the
    # nature of an edit, which no precedent covers, and site commit logs
    # stay generic.
    try:
        message_regex = build_active_regex(config, "strict")
    except ConfigError as exc:
        print(f"synthesis-git-hooks: {exc}", file=sys.stderr)
        sys.exit(2)
    allowlist = build_allowlist_regex(config)
    diff_excludes = build_diff_exclude_regex(config)
    check_msg_enabled = bool(config.get("check_commit_message", True))
    # Commit messages stay generic on every published surface, so the
    # message scan runs for public-surface exactly as it does for strict.
    check_msg = (
        "1"
        if (repo_class in ("strict", "public-surface") and check_msg_enabled)
        else "0"
    )
    # shlex.quote handles regex escapes safely under bash `eval`.
    print(f"REPO_CLASS={shlex.quote(repo_class)}")
    print(f"ACTIVE_REGEX={shlex.quote(active)}")
    print(f"MESSAGE_REGEX={shlex.quote(message_regex)}")
    # Credentials are scanned across EVERY staged path, exclusions included:
    # a pattern-catalog file is a plausible place for a false positive on
    # Tier-1 vocabulary, never a legitimate place for a secret.
    print(f"TIER0_REGEX={shlex.quote(build_active_regex(config, 'personal'))}")
    print(f"ALLOWLIST_REGEX={shlex.quote(allowlist)}")
    print(f"DIFF_EXCLUDE_REGEX={shlex.quote(diff_excludes)}")
    print(f"CHECK_COMMIT_MSG={check_msg}")
    coordination_board = config.get("coordination_board")
    if coordination_board is None:
        print("COORDINATION_CHECK_STAGED=0")
        print("COORDINATION_BOARD=''")
    else:
        expanded_board = str(Path(coordination_board).expanduser())
        print("COORDINATION_CHECK_STAGED=1")
        print(f"COORDINATION_BOARD={shlex.quote(expanded_board)}")
    # MUST be last: the engine treats its absence as sidecar failure.
    print("SYNTHESIS_SIDECAR_OK=1")


# ─── doctor ──────────────────────────────────────────────────────────────

def _grep_validates(pattern: str) -> Optional[str]:
    """Return an error string if `grep -E` rejects the pattern, else None."""
    try:
        proc = subprocess.run(
            ["grep", "-E", pattern],
            input="",
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:  # pragma: no cover
        return "grep not found on PATH"
    if proc.returncode > 1:
        return proc.stderr.strip() or f"grep exit {proc.returncode}"
    return None


def source_engine_path(path: Path, name: str) -> Path:
    """Map an installed filename to its canonical source path.

    Direct engine bundles may carry the dependency beside the core files. In
    the plugin/source tree, coordination stays canonical in its owning skill.
    """
    local = path / name
    if name in CORE_ENGINE_FILES or local.is_file():
        return local
    if len(path.parents) < 2:
        return local
    return (
        path.parents[1]
        / "synthesis-project-management"
        / "scripts"
        / name
    )


def source_coordination_asset(path: Path) -> Path:
    local = path.parent / "references" / COORDINATION_ASSET
    if local.is_file():
        return local
    if len(path.parents) < 2:
        return local
    return (
        path.parents[1]
        / "synthesis-project-management"
        / "references"
        / COORDINATION_ASSET
    )


def installed_coordination_asset(hooks_path: Path) -> Path:
    return hooks_path.parent / "references" / COORDINATION_ASSET


def _is_engine_source(path: Path) -> bool:
    """True when ``path`` resolves every engine file and required asset."""
    return all(source_engine_path(path, name).is_file() for name in ENGINE_FILES) and (
        source_coordination_asset(path).is_file()
    )


def _installed_engine_dirs(hooks_path: Optional[Path]) -> set:
    """Directories holding INSTALLED engine copies — never a drift source.

    Comparing an installed copy against itself would report "no drift"
    unconditionally, which is exactly the false health the check exists to
    prevent.
    """
    dirs = {(Path.home() / ".synthesis" / "git-hooks").resolve()}
    if hooks_path is not None:
        dirs.add(hooks_path.resolve())
    return dirs


def _documented_source_dirs() -> List[Path]:
    """Stable locations this ecosystem's own installers create.

    Direct-copy skill installs plus the shared installer's cached clone.
    Client plugin caches are deliberately absent: they are version-numbered,
    client-owned layouts where several stale versions coexist, and when the
    doctor runs from a plugin cache the running script's own directory
    already covers it — the same reasoning as the conformance suite's
    client-binary resolution (client_binaries.py).
    """
    home = Path.home()
    rel = Path("synthesis-git-hooks") / "scripts"
    cache_home = Path(os.environ.get("XDG_CACHE_HOME") or (home / ".cache"))
    return [
        home / ".claude" / "skills" / rel,
        home / ".agents" / "skills" / rel,
        home / ".codex" / "skills" / rel,
        cache_home / "synthesis-skills" / "skills" / rel,
    ]


def _persisted_source_dir(
    hooks_path: Optional[Path],
) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve the source pointer written by the generation-zero installer."""
    if hooks_path is None:
        return None, None
    pointer = hooks_path / SOURCE_POINTER_NAME
    if not pointer.exists() and not pointer.is_symlink():
        return None, None
    if pointer.is_symlink() or not pointer.is_file():
        return None, f"persisted source pointer is not a regular file: {pointer}"
    try:
        raw = pointer.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, f"persisted source pointer is unreadable: {pointer}: {exc}"
    lines = raw.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        return None, f"persisted source pointer must contain one path: {pointer}"
    candidate = Path(lines[0]).expanduser()
    if not candidate.is_absolute():
        return None, f"persisted source pointer must be absolute: {pointer}"
    candidate = candidate.resolve()
    if not _is_engine_source(candidate):
        return None, (
            f"persisted source pointer does not resolve an engine source: "
            f"{pointer} -> {candidate} (fail closed)"
        )
    return candidate, None


def resolve_source_dir(
    hooks_path: Optional[Path],
) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve the skill-source directory the drift check compares against.

    Order (mirrors the conformance suite's client-binary resolution):

    1. ``$SYNTHESIS_GIT_HOOKS_SOURCE``. A set override is authoritative:
       empty means "no source on this machine — skip drift deliberately",
       and a value that is not an engine source directory is a doctor
       problem rather than a fallthrough, so a misconfigured override
       fails closed instead of silently comparing against nothing.
    2. This script's own directory, unless it is itself an installed engine
       copy — running the doctor from a repo checkout, a worktree, or a
       client plugin cache compares the installation against that copy.
    3. The source path persisted by ``install.sh``. A present but invalid
       pointer is a doctor problem, never a reason to fall through.
    4. Documented locations the ecosystem's own installers create, first
       complete candidate wins.

    Returns ``(source_dir, problem)``. Both ``None`` means no source is
    available and the drift check is skipped.
    """
    if SOURCE_ENV in os.environ:
        override = os.environ[SOURCE_ENV]
        if not override:
            return None, None
        path = Path(override).expanduser()
        if _is_engine_source(path):
            return path, None
        return None, (
            f"{SOURCE_ENV} is set to {override!r}, which is not an engine "
            f"source directory (needs {', '.join(ENGINE_FILES)}) — fix or "
            "unset it (fail closed)"
        )
    installed = _installed_engine_dirs(hooks_path)
    own_dir = Path(__file__).resolve().parent
    if own_dir not in installed and _is_engine_source(own_dir):
        return own_dir, None
    persisted, persisted_problem = _persisted_source_dir(hooks_path)
    if persisted_problem:
        return None, persisted_problem
    if persisted is not None:
        return persisted, None
    for candidate in _documented_source_dirs():
        if candidate.resolve() not in installed and _is_engine_source(candidate):
            return candidate, None
    return None, None


def run_doctor(config_path: Path) -> int:
    """Self-check the whole protection chain. Exit 0 = healthy."""
    problems: List[str] = []
    infos: List[str] = []

    infos.append(f"sidecar version: {SIDECAR_VERSION}")
    infos.append(f"python: {sys.version.split()[0]} at {sys.executable}")

    # 1. Config parses and has teeth.
    config: Optional[dict] = None
    if not config_path.exists():
        problems.append(f"config missing: {config_path}")
    else:
        try:
            config = parse_simple_yaml(config_path.read_text())
            t0 = flatten_patterns((config or {}).get("tier_0_always") or {})
            t1 = flatten_patterns(
                (config or {}).get("tier_1_strict_only") or {}
            )
            infos.append(
                f"config OK: {len(t0)} tier-0 + {len(t1)} tier-1 patterns"
            )
            if not t0:
                problems.append("tier_0_always is empty — no credential tier")
            version = config.get("config_version")
            if not isinstance(version, int) or version < REQUIRED_CONFIG_VERSION:
                problems.append(
                    f"config_version is {version!r}; engine v{SIDECAR_VERSION} "
                    f"requires {REQUIRED_CONFIG_VERSION}"
                )
            # 2. EVERY configured regex valid under both python re and grep -E
            # (tiers, remote patterns, allowlist, exclusions).
            problems.extend(validate_all_patterns(config))
            if config.get("public_surface_patterns") and not config.get(
                "disclosure_ledger"
            ):
                problems.append(
                    "public_surface_patterns configured without a "
                    "disclosure_ledger — public-surface repos get zero "
                    "allowances, which blocks published-precedent content"
                )
            coordination_board = config.get("coordination_board")
            if coordination_board is None:
                infos.append(
                    "coordination check-staged control absent: no "
                    "coordination_board configured"
                )
            elif not isinstance(coordination_board, str) or not coordination_board.strip():
                problems.append(
                    "coordination_board must be a non-empty path string"
                )
            else:
                board_path = Path(coordination_board).expanduser()
                infos.append(f"coordination check-staged configured: {board_path}")
                if not board_path.is_file():
                    problems.append(
                        f"configured coordination board is unavailable: {board_path}"
                    )
        except ConfigError as exc:
            problems.append(f"config unparsable: {exc}")

    # 3. hooksPath wiring.
    hooks_path = ""
    try:
        proc = subprocess.run(
            ["git", "config", "--global", "core.hooksPath"],
            capture_output=True,
            text=True,
        )
        hooks_path = proc.stdout.strip()
    except FileNotFoundError:
        problems.append("git not found on PATH")
    hp_dir: Optional[Path] = None
    if hooks_path:
        hp_dir = Path(os.path.expanduser(hooks_path))
        infos.append(f"core.hooksPath: {hp_dir}")
        for name in ENGINE_FILES:
            f = hp_dir / name
            if not f.exists():
                problems.append(f"hooksPath missing {name}: {f}")
            elif name in ("pre-commit", "commit-msg") and not os.access(f, os.X_OK):
                problems.append(f"{f} is not executable")
        asset = installed_coordination_asset(hp_dir)
        if not asset.is_file():
            problems.append(f"coordination runtime missing asset: {asset}")
    else:
        problems.append(
            "core.hooksPath is not set globally — the engine is not wired in"
        )

    # 4. Drift: installed engine vs skill source. See resolve_source_dir for
    # the portable resolution order (env override, own directory, documented
    # install locations) — never a hardcoded checkout path.
    src_dir, src_problem = resolve_source_dir(hp_dir)
    if src_problem:
        problems.append(src_problem)
    elif src_dir is None:
        infos.append(
            "skill source not found (drift check skipped) — set "
            f"{SOURCE_ENV} to the skill's scripts/ directory to enable it"
        )
    elif hp_dir is not None:
        drift_found = False
        for name in ENGINE_FILES:
            src, inst = source_engine_path(src_dir, name), hp_dir / name
            if inst.exists() and src.read_bytes() != inst.read_bytes():
                drift_found = True
                problems.append(
                    f"DRIFT: installed {name} differs from skill source "
                    f"({inst} vs {src}) — reinstall or sync back"
                )
        source_asset = source_coordination_asset(src_dir)
        installed_asset = installed_coordination_asset(hp_dir)
        if (
            installed_asset.exists()
            and source_asset.read_bytes() != installed_asset.read_bytes()
        ):
            drift_found = True
            problems.append(
                "DRIFT: installed coordination asset differs from skill source "
                f"({installed_asset} vs {source_asset}) — reinstall or sync back"
            )
        if not drift_found:
            infos.append(
                f"installed engine matches skill source (no drift): {src_dir}"
            )

    # 5. Disclosure ledger (when configured): must exist, parse, carry
    # evidence, and every allowance must correspond to a real Tier-1
    # pattern — a stale allowance protects nothing and hides intent.
    if config is not None and config.get("disclosure_ledger"):
        try:
            allowances = load_ledger_allowances(config)
            tier1 = set(
                flatten_patterns(config.get("tier_1_strict_only") or {})
            )
            stale = [a for a in allowances if a not in tier1]
            infos.append(
                f"disclosure ledger OK: {len(allowances)} allowance(s) "
                "for public-surface repos"
            )
            for pattern in stale:
                problems.append(
                    "ledger allowance matches no tier_1_strict_only "
                    f"pattern (stale or typo): {pattern!r}"
                )
        except ConfigError as exc:
            problems.append(str(exc))

    # 6. Current repo context (best-effort).
    if config is not None:
        push_urls = get_push_remotes()
        if push_urls:
            cls = classify_repo(config, push_urls)
            infos.append(
                f"cwd repo class: {cls} ({len(push_urls)} push remotes)"
            )
            try:
                top = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            except FileNotFoundError:
                top = ""
            if top:
                chained = Path(top) / ".githooks" / "pre-commit"
                if chained.exists():
                    if os.access(chained, os.X_OK):
                        infos.append("chained repo-local hook: present, executable")
                    else:
                        problems.append(
                            f"chained hook not executable: {chained}"
                        )

    print("synthesis-git-hooks doctor")
    for line in infos:
        print(f"  ok  {line}")
    for line in problems:
        print(f"  !!  {line}")
    if problems:
        print(
            f"UNHEALTHY: {len(problems)} problem(s). Commits will be blocked "
            "until fixed (fail closed)."
        )
        return 1
    print("HEALTHY: policy engine fully operational.")
    return 0


# ─── entry point ─────────────────────────────────────────────────────────

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="synthesis-engineering git-hook config loader",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "SYNTHESIS_GIT_HOOK_CONFIG",
            str(DEFAULT_CONFIG),
        ),
        help="Path to git-hook-config.yaml (default: $SYNTHESIS_GIT_HOOK_CONFIG or ~/.synthesis/git-hook-config.yaml)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--emit-shell-vars",
        action="store_true",
        help="Emit shell-quoted assignments for REPO_CLASS, ACTIVE_REGEX, ALLOWLIST_REGEX, CHECK_COMMIT_MSG + the SYNTHESIS_SIDECAR_OK sentinel (default).",
    )
    mode.add_argument(
        "--classify",
        action="store_true",
        help="Print just the repo class (personal|public-surface|strict) and exit.",
    )
    mode.add_argument(
        "--print-active-regex",
        action="store_true",
        help="Print the active regex (Tier 0 [+ Tier 1]) and exit.",
    )
    mode.add_argument(
        "--doctor",
        action="store_true",
        help="Self-check the protection chain: config, patterns, hooksPath wiring, source drift, cwd classification. Exit 0 = healthy.",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)

    if args.doctor:
        return run_doctor(config_path)

    config = load_config(config_path)

    if args.classify:
        print(classify_repo(config, get_push_remotes()))
        return 0

    if args.print_active_regex:
        repo_class = classify_repo(config, get_push_remotes())
        try:
            print(build_active_regex(config, repo_class))
        except ConfigError as exc:
            print(f"synthesis-git-hooks: {exc}", file=sys.stderr)
            return 2
        return 0

    # Default: emit shell vars.
    emit_shell_vars(config)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
