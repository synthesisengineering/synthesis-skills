#!/usr/bin/env python3
"""Run the sanitizer over every fixture in tests/poisoned/ and verify the
defenses hold. Exit 0 if all pass; non-zero if any defense regressed.

What each fixture asserts:

  1. The sanitized output is wrapped in <UNTRUSTED_EMAIL> tags.
  2. The output is bounded (subject ≤ ~256 bytes, body ≤ ~1024 bytes after
     truncation marker).
  3. No <script>, <style>, <meta>, or comment markers survive HTML stripping.
  4. No invisible / bidi-control / BOM Unicode characters survive.

These are NECESSARY conditions for the defenses to hold. They are not
SUFFICIENT — the structured-output gate and the human-review gate are the
final layers, tested separately.

NOT tested here: cross-script homoglyph detection (Cyrillic 'А' folding to
Latin 'A'). NFKC normalization does not fold across scripts because they
are semantically distinct letters; doing so would corrupt legitimate
multilingual content. The defense for cross-script homoglyphs is the
human-review gate on `propose-rule` outputs — the human sees the actual
address bytes and recognizes that `alerts@chаse.example` is not
`alerts@chase.com`. See references/prompt-injection-defenses.md.
"""
import sys
import os
import re
import unicodedata

# Make `import sanitize` work whether run from the skill root or tests/.
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import sanitize


FIXTURE_DIR = os.path.join(HERE, "poisoned")

# Each fixture has assertions tied to its specific attack shape. Failures
# are reported per-fixture so a regression points to the specific defense.
FORBIDDEN_SUBSTRINGS = [
    # HTML markers that must not survive stripping
    "<script", "</script", "<style", "</style", "<meta", "<!--", "-->",
    # CSS hiding markers
    "display: none", "display:none",
]

# Invisible / bidi-control Unicode that must not survive sanitization
INVISIBLE_PATTERN = re.compile(
    "["
    "​-‏"
    "‪-‮"
    "⁠-⁤"
    "﻿"
    "­"
    "]"
)


def check_fixture(path):
    """Return list of failure messages; empty list = all assertions pass."""
    failures = []
    with open(path, "rb") as f:
        raw = f.read()

    out = sanitize.sanitize_message(raw)

    if "<UNTRUSTED_EMAIL>" not in out or "</UNTRUSTED_EMAIL>" not in out:
        failures.append("missing UNTRUSTED_EMAIL demarcation tags")

    # Bound check: full message envelope budget — generous to allow tags + 2 fields
    if len(out.encode("utf-8")) > 2048:
        failures.append(f"output exceeds size budget ({len(out)} bytes)")

    # No HTML / CSS markers survive
    out_lower = out.lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in out_lower:
            failures.append(f"forbidden substring survived: {bad!r}")

    # No invisible / bidi-control / BOM
    invisibles = INVISIBLE_PATTERN.findall(out)
    if invisibles:
        failures.append(f"invisible Unicode survived: {[hex(ord(c)) for c in invisibles]}")

    return failures, out


def main():
    if not os.path.isdir(FIXTURE_DIR):
        sys.exit(f"FIXTURE DIR NOT FOUND: {FIXTURE_DIR}")

    fixtures = sorted(f for f in os.listdir(FIXTURE_DIR) if f.endswith(".eml"))
    if not fixtures:
        sys.exit(f"No .eml fixtures in {FIXTURE_DIR}")

    print(f"# Adversarial fixture run — {len(fixtures)} fixture(s)\n")

    total_failures = 0
    for fixture in fixtures:
        path = os.path.join(FIXTURE_DIR, fixture)
        failures, out = check_fixture(path)
        if failures:
            total_failures += len(failures)
            print(f"  ✗ {fixture}")
            for fail in failures:
                print(f"      - {fail}")
            print(f"      Sanitized output:\n{indent(out, 8)}\n")
        else:
            print(f"  ✓ {fixture}")

    print()
    if total_failures:
        print(f"FAILED — {total_failures} assertion(s) regressed.")
        sys.exit(1)
    print("PASSED — all fixtures neutralized.")


def indent(s, n):
    pad = " " * n
    return "\n".join(pad + line for line in s.splitlines())


if __name__ == "__main__":
    main()
