#!/usr/bin/env python3
"""Unit test for the rule-engine resolver.

Hand-rolls a minimal RULES manifest in memory, monkey-patches `_lib.RULES`,
and exercises each resolver path: never_touch addresses/domains, subject_rules
in all four shapes (domain+contains, domain+starts_with, any-domain+contains,
any-domain+starts_with), sender address/domain/name precedence, class_defaults,
and unmatched fallback.

Exits 0 if all assertions pass; non-zero with a diff on regression.

Why this exists: the resolver is the load-bearing decision logic for every
disposition. The adversarial fixtures in run_poisoned.py test the sanitizer,
not the resolver. Without this, engine changes ship with no automated check
that the precedence order survived.
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)

import _lib  # noqa: E402


# Minimal manifest exercising every resolver branch.
TEST_RULES = {
    "never_touch": {
        "addresses": ["always@example.com"],
        "domains": ["never-touch-this.example"],
    },
    "subject_rules": [
        # Domain + subject_contains (the v1.0.0 / v1.1.0 shape).
        {"if": {"domain": "chase.com", "subject_contains": "Fraud"}, "disposition": "keep"},
        # Domain + subject_starts_with (v1.2.0 — domain-anchored prefix match).
        {"if": {"domain": "jpmorgan.com", "subject_starts_with": "URGENT:"}, "disposition": "keep"},
        # Any-domain + subject_starts_with (v1.2.0 — calendar protocol pattern).
        {"if": {"subject_starts_with": "Accepted:"}, "disposition": "archive"},
        {"if": {"subject_starts_with": "Declined:"}, "disposition": "archive"},
        # Any-domain + subject_contains (v1.2.0 — generic substring across any sender).
        {"if": {"subject_contains": "[BULK]"}, "disposition": "trash"},
    ],
    "senders": [
        {"match": {"address": "specific@friend.example"}, "disposition": "keep"},
        {"match": {"domain": "marketing.example"}, "class": "retail_marketing"},
        {"match": {"name": "Acme Sales"}, "class": "cold_sales"},
    ],
    "class_defaults": {
        "retail_marketing": "trash",
        "cold_sales": "trash",
        "transactional": "archive",
    },
}


def run_case(name, addr, domain, subject, want_disp, want_reason):
    got_disp, got_reason = _lib.resolve(name or "", addr, domain, subject)
    if got_disp != want_disp:
        return f"FAIL  name={name!r} addr={addr!r} subj={subject!r}: " \
               f"want disposition={want_disp!r} got {got_disp!r} (reason={got_reason!r})"
    if want_reason and got_reason != want_reason:
        return f"FAIL  name={name!r} addr={addr!r} subj={subject!r}: " \
               f"want reason={want_reason!r} got {got_reason!r}"
    return None


CASES = [
    # ── never_touch addresses ────────────────────────────────────────────
    ("VIP", "always@example.com", "example.com", "anything", "keep", "never_touch"),
    # ── never_touch domains ──────────────────────────────────────────────
    ("any", "rando@never-touch-this.example", "never-touch-this.example",
        "anything", "keep", "never_touch"),
    # ── subject_rules: domain + contains ─────────────────────────────────
    ("Chase", "alerts@chase.com", "chase.com", "Possible Fraud on your account",
        "keep", "subject_rule"),
    # Non-matching subject on same domain falls through to unmatched (no sender rule).
    ("Chase", "noreply@chase.com", "chase.com", "Statement available",
        "keep", "unmatched"),
    # ── subject_rules: domain + starts_with ──────────────────────────────
    ("JPM", "alerts@jpmorgan.com", "jpmorgan.com", "URGENT: action required",
        "keep", "subject_rule"),
    # Subject that contains the prefix mid-string must NOT match starts_with.
    ("JPM", "alerts@jpmorgan.com", "jpmorgan.com", "Re: URGENT: was earlier",
        "keep", "unmatched"),
    # ── subject_rules: any-domain + starts_with (calendar protocol) ──────
    ("Colleague A", "alice@anywhere.example", "anywhere.example",
        "Accepted: Sprint planning @ Mon", "archive", "subject_rule"),
    ("Colleague B", "bob@another.example", "another.example",
        "Declined: Lunch @ Tue", "archive", "subject_rule"),
    # Real reply ABOUT an acceptance (mid-string) must NOT match starts_with.
    ("Human", "carol@friend.example", "friend.example",
        "Re: Accepted: should we discuss?", "keep", "unmatched"),
    # ── subject_rules: any-domain + contains ─────────────────────────────
    ("List", "list@somewhere.example", "somewhere.example",
        "Notice [BULK] please ignore", "trash", "subject_rule"),
    # ── senders: address > domain > name precedence ──────────────────────
    ("Friend", "specific@friend.example", "friend.example", "lunch?",
        "keep", "sender:addr"),
    ("Marketing", "any@marketing.example", "marketing.example", "Sale!",
        "trash", "sender:dom"),
    ("Acme Sales Team", "sdr@cold-sales-corp.example", "cold-sales-corp.example",
        "Quick question", "trash", "sender:name"),
    # ── unmatched fallback ───────────────────────────────────────────────
    ("Unknown", "stranger@unknown.example", "unknown.example", "Hi there",
        "keep", "unmatched"),
]


def main():
    _lib.RULES = TEST_RULES
    _lib.CLASS = TEST_RULES["class_defaults"]
    print(f"# Resolver test — {len(CASES)} case(s)")
    fails = []
    for c in CASES:
        err = run_case(*c)
        if err:
            fails.append(err)
            print(f"  ✗ {err}")
        else:
            print(f"  ✓ {c[3][:60]}")
    if fails:
        print(f"\nFAILED — {len(fails)} regression(s)")
        sys.exit(1)
    print("\nPASSED — all resolver paths behave as specified.")


if __name__ == "__main__":
    main()
