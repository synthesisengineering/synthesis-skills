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
  the cwd repo's classification + chained hook are reported.

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
from pathlib import Path
from typing import Any, List, Optional, Tuple

SIDECAR_VERSION = "2.1.0"

DEFAULT_CONFIG = Path.home() / ".synthesis" / "git-hook-config.yaml"
DEFAULT_SOURCE_DIR = (
    Path.home()
    / "workspaces/rajiv/synthesis-skills/skills/synthesis-git-hooks/scripts"
)


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
        return s[1:-1].encode().decode("unicode_escape")
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


def classify_repo(personal_patterns: List[str], push_urls: List[str]) -> str:
    """Return ``"personal"`` if every push remote matches at least one
    personal-remote pattern (case-insensitive). Otherwise ``"strict"``.

    Empty remote list classifies as ``"strict"`` — the safe default for a
    fresh ``git init`` or any repo without a defined upstream.
    """
    if not push_urls:
        return "strict"
    if not personal_patterns:
        return "strict"
    compiled = [re.compile(p, re.IGNORECASE) for p in personal_patterns]
    for url in push_urls:
        if not any(c.search(url) for c in compiled):
            return "strict"
    return "personal"


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


def build_active_regex(config: dict, repo_class: str) -> str:
    """Concatenate the active patterns into a single alternation regex."""
    parts: List[str] = []
    tier0 = config.get("tier_0_always") or {}
    parts.extend(flatten_patterns(tier0))
    if repo_class == "strict":
        tier1 = config.get("tier_1_strict_only") or {}
        parts.extend(flatten_patterns(tier1))
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
    r'(^|/)\.synthesis/git-hook-config\.ya?ml$',
    r'(^|/)git-hook-config\.example\.ya?ml$',
    r'(^|/)anti-shortcut-catalog\.ya?ml$',
)


def build_diff_exclude_regex(config: dict) -> str:
    """Concatenate path-exclusion regexes (defaults + user-configured)."""
    user_paths = flatten_patterns(config.get("diff_exclude_paths") or [])
    all_paths = list(DEFAULT_DIFF_EXCLUDE_PATHS) + user_paths
    return "|".join(all_paths)


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
    return config


def emit_shell_vars(config: dict) -> None:
    personal_patterns = config.get("personal_remote_patterns") or []
    push_urls = get_push_remotes()
    repo_class = classify_repo(personal_patterns, push_urls)
    active = build_active_regex(config, repo_class)
    allowlist = build_allowlist_regex(config)
    diff_excludes = build_diff_exclude_regex(config)
    check_msg_enabled = bool(config.get("check_commit_message", True))
    check_msg = "1" if (repo_class == "strict" and check_msg_enabled) else "0"
    # shlex.quote handles regex escapes safely under bash `eval`.
    print(f"REPO_CLASS={shlex.quote(repo_class)}")
    print(f"ACTIVE_REGEX={shlex.quote(active)}")
    print(f"ALLOWLIST_REGEX={shlex.quote(allowlist)}")
    print(f"DIFF_EXCLUDE_REGEX={shlex.quote(diff_excludes)}")
    print(f"CHECK_COMMIT_MSG={check_msg}")
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
            # 2. Every pattern valid under BOTH python re and grep -E.
            for p in t0 + t1:
                try:
                    re.compile(p)
                except re.error as exc:
                    problems.append(
                        f"pattern rejected by python re: {p!r} ({exc})"
                    )
                err = _grep_validates(p)
                if err:
                    problems.append(
                        f"pattern rejected by grep -E: {p!r} ({err})"
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
    if hooks_path:
        hp = Path(os.path.expanduser(hooks_path))
        infos.append(f"core.hooksPath: {hp}")
        for name in ("pre-commit", "commit-msg", "_load_config.py"):
            f = hp / name
            if not f.exists():
                problems.append(f"hooksPath missing {name}: {f}")
            elif name in ("pre-commit", "commit-msg") and not os.access(f, os.X_OK):
                problems.append(f"{f} is not executable")
    else:
        problems.append(
            "core.hooksPath is not set globally — the engine is not wired in"
        )

    # 4. Drift: installed engine vs skill source (when the source is present).
    src_dir = Path(
        os.environ.get("SYNTHESIS_GIT_HOOKS_SOURCE", str(DEFAULT_SOURCE_DIR))
    )
    if hooks_path and src_dir.is_dir():
        hp = Path(os.path.expanduser(hooks_path))
        drift_found = False
        for name in ("pre-commit", "commit-msg", "_load_config.py"):
            src, inst = src_dir / name, hp / name
            if src.exists() and inst.exists():
                if src.read_bytes() != inst.read_bytes():
                    drift_found = True
                    problems.append(
                        f"DRIFT: installed {name} differs from skill source "
                        f"({inst} vs {src}) — reinstall or sync back"
                    )
        if not drift_found:
            infos.append("installed engine matches skill source (no drift)")
    elif not src_dir.is_dir():
        infos.append(
            f"skill source not present at {src_dir} (drift check skipped)"
        )

    # 5. Current repo context (best-effort).
    if config is not None:
        push_urls = get_push_remotes()
        if push_urls:
            cls = classify_repo(
                config.get("personal_remote_patterns") or [], push_urls
            )
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
        help="Print just the repo class (personal|strict) and exit.",
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
        push_urls = get_push_remotes()
        print(classify_repo(
            config.get("personal_remote_patterns") or [],
            push_urls,
        ))
        return 0

    if args.print_active_regex:
        push_urls = get_push_remotes()
        repo_class = classify_repo(
            config.get("personal_remote_patterns") or [],
            push_urls,
        )
        print(build_active_regex(config, repo_class))
        return 0

    # Default: emit shell vars.
    emit_shell_vars(config)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
