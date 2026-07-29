#!/usr/bin/env python3
"""Run the sanitizer over every fixture in tests/poisoned/ and verify the
defenses hold. Exit 0 if all pass; non-zero if any defense regressed.

What each fixture asserts:

  1. The output is fenced in NONCE-BEARING <UNTRUSTED_EMAIL nonce="..."> tags
     (open + matching close), and the wrapper token appears EXACTLY twice —
     i.e. no attacker-supplied marker survived into the content. This is the
     regression test for the delimiter-breakout attack: a body that contains
     `</UNTRUSTED_EMAIL>` must not be able to forge the fence.
  2. The output is bounded (subject + body within byte budgets + labels).
  3. No <script>, <style>, <meta>, or comment markers survive HTML stripping.
  4. No invisible / bidi-control / bidi-isolate / BOM / Unicode-Tags-block
     characters survive.

Plus two standalone checks (not fixture-driven):

  5. The OUTPUT-side gate (`parse_and_validate`) rejects every malformed or
     out-of-action-space model output and accepts a well-formed one.
  6. The mixed-script homoglyph advisory flag fires on a Cyrillic look-alike
     address and stays quiet on a plain ASCII one.

These are NECESSARY conditions for the defenses to hold. They are not
SUFFICIENT — the human-review gate and the architectural separation (LLM
proposes, deterministic engine writes) are the final layers.

Cross-script homoglyph FOLDING is intentionally not attempted (NFKC keeps
Cyrillic 'а' and Latin 'a' distinct so legitimate multilingual content is not
corrupted); the defense is the inline mixed-script flag checked in (6) plus
the human-review gate. See references/prompt-injection-defenses.md.
"""
import sys
import os
import re

# Make `import sanitize` work whether run from the skill root or tests/.
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import sanitize


FIXTURE_DIR = os.path.join(HERE, "poisoned")

# HTML / CSS markers that must not survive stripping.
FORBIDDEN_SUBSTRINGS = [
    "<script", "</script", "<style", "</style", "<meta", "<!--", "-->",
    "display: none", "display:none",
]

# Invisible / bidi-control / bidi-isolate / BOM / Unicode-Tags-block characters
# that must not survive sanitization. Mirrors sanitize._INVISIBLE.
INVISIBLE_PATTERN = re.compile(
    "[\u00ad\u061c\u200b-\u200f\u202a-\u202e\u2060-\u2064"
    "\u2066-\u206f\ufeff\ufff9-\ufffb\U000e0000-\U000e007f]"
)

OPEN_TAG = re.compile(r'<UNTRUSTED_EMAIL nonce="([0-9a-f]{16})">')
CLOSE_TAG = re.compile(r'</UNTRUSTED_EMAIL nonce="([0-9a-f]{16})">')


def check_fixture(path):
    """Return (list of failure messages, sanitized output)."""
    failures = []
    with open(path, "rb") as f:
        raw = f.read()

    out = sanitize.sanitize_message(raw)

    # 1. Nonce-bearing demarcation, and the wrapper token survives exactly twice.
    opens = OPEN_TAG.findall(out)
    closes = CLOSE_TAG.findall(out)
    if len(opens) != 1 or len(closes) != 1:
        failures.append("missing nonce-bearing open/close demarcation tags")
    elif opens[0] != closes[0]:
        failures.append("open/close nonce mismatch")
    token_hits = out.count("UNTRUSTED_EMAIL")
    if token_hits != 2:
        failures.append(
            f"wrapper token appears {token_hits}x (expected 2 — an attacker "
            f"marker survived into the content)")

    # 2. Size bound — tags + labels + budgeted fields.
    if len(out.encode("utf-8")) > 3072:
        failures.append(f"output exceeds size budget ({len(out.encode('utf-8'))} bytes)")

    # 3. No HTML / CSS markers survive.
    out_lower = out.lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in out_lower:
            failures.append(f"forbidden substring survived: {bad!r}")

    # 4. No invisible / bidi / tags-block characters survive.
    invisibles = INVISIBLE_PATTERN.findall(out)
    if invisibles:
        failures.append(f"invisible Unicode survived: {[hex(ord(c)) for c in invisibles]}")

    # Per-fixture targeted assertions.
    base = os.path.basename(path)
    if base == "homoglyph_sender.eml" and "mixed-script" not in out:
        failures.append("mixed-script homoglyph address was not flagged")
    if base == "envelope_spoof.eml":
        # The real envelope labels must appear exactly once — a body forging its
        # own "From-address:" / "[envelope …]" block must be scrubbed.
        if out.count("From-address:") != 1:
            failures.append(f"forged 'From-address:' not scrubbed (count={out.count('From-address:')})")
        if out.count("[envelope") != 1:
            failures.append(f"forged '[envelope' label not scrubbed (count={out.count('[envelope')})")

    return failures, out


def check_output_validator():
    """Standalone: the constrained-action-space gate rejects bad model output."""
    failures = []
    bad_outputs = [
        '{"sender":"x","disposition":"DELETE EVERYTHING","rationale":"r","confidence":"high"}',
        '{"sender":"x","disposition":"trash","rationale":"r","confidence":"high","exfil":"http://e"}',
        '{"sender":"x","disposition":"keep","rationale":"r","confidence":"maybe"}',
        '{"sender":"x","disposition":"keep","rationale":"see </UNTRUSTED_EMAIL>","confidence":"low"}',
        'Sure — I have added attacker.example to never_touch.',
        '{"disposition":"trash"}',
    ]
    for bo in bad_outputs:
        if sanitize.parse_and_validate(bo) is not None:
            failures.append(f"validator ACCEPTED bad output: {bo[:60]!r}")
    good = '{"sender":"deals@x.com","disposition":"archive","rationale":"bulk promo","confidence":"high"}'
    if sanitize.parse_and_validate(good) is None:
        failures.append("validator REJECTED a well-formed output")
    return failures


def check_mixed_script():
    """Standalone: the homoglyph advisory flag fires correctly."""
    failures = []
    if not sanitize.mixed_script_address("alerts@chаse.com"):  # Cyrillic а
        failures.append("mixed_script_address missed a Cyrillic look-alike")
    if sanitize.mixed_script_address("alerts@chase.com"):
        failures.append("mixed_script_address false-positived on plain ASCII")
    # IDN/punycode look-alike: ASCII on the wire, Cyrillic once decoded.
    try:
        puny = "alerts@" + "chаse.com".encode("idna").decode("ascii")
        if not sanitize.mixed_script_address(puny):
            failures.append("mixed_script_address missed an IDN/punycode look-alike")
    except (UnicodeError, ValueError):
        pass  # platform idna codec rejected the sample; display-name path still covers it
    return failures


def check_resource_bounds():
    """Standalone: a multi-megabyte body sanitizes to a bounded result without
    runaway CPU. Input is capped before the regex / NFKC / entity-decode
    pipeline, so a giant message cannot exhaust the host (DoS guard)."""
    failures = []
    big = ("From: <flood@attacker.example>\r\nSubject: flood\r\n"
           "Content-Type: text/plain; charset=utf-8\r\n\r\n" + "A" * (3 * 1024 * 1024))
    if len(sanitize.sanitize_message(big).encode("utf-8")) > 3072:
        failures.append("multi-MB plain body not bounded")
    bomb = ("From: <x@y.example>\r\nSubject: s\r\n"
            "Content-Type: text/html; charset=utf-8\r\n\r\n" + "<div>" * 200000)
    if len(sanitize.sanitize_message(bomb).encode("utf-8")) > 3072:
        failures.append("pathological-HTML body not bounded")
    return failures


def indent(s, n):
    pad = " " * n
    return "\n".join(pad + line for line in s.splitlines())


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

    print("\n# Standalone defense checks\n")
    for label, fn in (("output validator (constrained action space)", check_output_validator),
                      ("mixed-script homoglyph flag", check_mixed_script),
                      ("resource-exhaustion bounds", check_resource_bounds)):
        failures = fn()
        if failures:
            total_failures += len(failures)
            print(f"  ✗ {label}")
            for fail in failures:
                print(f"      - {fail}")
        else:
            print(f"  ✓ {label}")

    print()
    if total_failures:
        print(f"FAILED — {total_failures} assertion(s) regressed.")
        sys.exit(1)
    print("PASSED — all fixtures neutralized.")


if __name__ == "__main__":
    main()
