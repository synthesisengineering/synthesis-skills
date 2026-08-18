#!/usr/bin/env python3
"""Flag brand- and identity-impersonation in an IMAP inbox. READ-ONLY by default.

Why this exists, stated plainly: the rest of this engine sorts mail by *desirability*
— marketing, newsletters, transactional, keep. That taxonomy has no cell for
*hostile*. A phishing message is not low-value bulk to be archived; it is an
attack to be removed, and a cleanup pass that only files things tidily will walk
straight past it. This script adds the adversarial lens the taxonomy lacks.

The detection it implements is the one that catches real campaigns:

**The sending domain is authenticated; the display name is not.**

SPF, DKIM and DMARC authenticate the envelope domain. They say nothing about the
human-readable name a mail client shows in the sender column — which is free text
the attacker chooses. So the highest-yield modern phish does not forge a domain at
all. It sends through infrastructure whose domain passes every check (a survey
platform, a newsletter service, a form host) and puts the impersonated brand in the
display name, where the recipient's eye actually lands:

    From: "mail@noreply.trezor.io via <SurveyPlatform>" <member@surveyplatformuser.com>

Every authentication check passes, because the mail genuinely came from the survey
platform. The brand appears nowhere in the authenticated identity. The reader sees
their hardware-wallet vendor. This is why "the domain checks out" is not a safety
verdict.

The rule here: when the display name claims a brand, the sending domain must
plausibly belong to that brand. Anything else is flagged.

Coverage is deliberately partial. This catches display-name impersonation of a
declared brand list, and near-miss domains that look like a brand without being it
(``ledger-supportcenter.com``, ``notifcations.com``). It does NOT catch a
well-written spear-phish from a plausible domain with no brand claim, and nothing
here replaces reading the message. It reduces a category; it does not close it.

Usage:
    python3 scan_impersonation.py                  # report only (default)
    python3 scan_impersonation.py --json           # machine-readable
    python3 scan_impersonation.py --strict-only    # only high-confidence hits
    python3 scan_impersonation.py --folder Archive # scan another folder

Never trashes. Removal is a separate, human-reviewed step, per the engine's rule
that the LLM proposes and the deterministic layer disposes. A false positive here
is a legitimate vendor notice; deleting one automatically is its own harm.

Brands and their legitimate domains live in
``~/.synthesis/inbox-cleanup/impersonation.yaml`` when present; otherwise the
built-in seed below is used. Keep high-value targets in it: crypto custody,
banking, payments, large platforms, shipping, and the user's own name (display-name
impersonation of the account owner is a common pretext for invoice fraud).
"""

from __future__ import annotations

import argparse
import email
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _lib import connect, dec  # noqa: E402

CONFIG = Path.home() / ".synthesis" / "inbox-cleanup" / "impersonation.yaml"

# Seed list. Crypto custody first — it is the highest-loss, least-reversible target.
SEED_BRANDS: dict[str, list[str]] = {
    "trezor": ["trezor.io"],
    "ledger": ["ledger.com", "ledger.fr"],
    "coinbase": ["coinbase.com"],
    "metamask": ["metamask.io", "consensys.net"],
    "binance": ["binance.com", "binance.us"],
    "kraken": ["kraken.com"],
    "blockchain": ["blockchain.com"],
    "exodus wallet": ["exodus.com"],
    "paypal": ["paypal.com"],
    "docusign": ["docusign.com", "docusign.net"],
    "norton": ["norton.com", "nortonlifelock.com", "gen.com"],
    "mcafee": ["mcafee.com"],
    "apple": ["apple.com", "icloud.com", "apple"],
    "microsoft": ["microsoft.com", "office.com", "outlook.com", "azure.com", "bing.com"],
    "chase": ["chase.com", "jpmorgan.com", "chasetravel.com"],
    "wells fargo": ["wellsfargo.com"],
    "bank of america": ["bankofamerica.com", "bofa.com"],
    "amazon": ["amazon.com", "amazon.ca", "amazon.co.uk", "amazon.de", "epiqnotice.com"],
    "netflix": ["netflix.com"],
    "fedex": ["fedex.com"],
    "ups": ["ups.com"],
    "dhl": ["dhl.com", "bluedart.com"],
}

# Substrings that make a domain suspicious on their own — brand-adjacent hostnames
# and common typosquats. Checked against the FULL domain, not just the TLD.
NEAR_MISS = (
    "-support", "supportcenter", "-secure", "secure-", "-verify", "verify-",
    "-wallet", "wallet-", "notifcation", "notifiction", "-alerts", "account-",
    "-recovery", "recovery-", "-helpdesk", "webmail-",
)

# Bulk-mail platforms whose domains authenticate correctly and are therefore
# frequently abused as carriers. A brand claim arriving through one of these is
# treated as high confidence, because a real brand sends from its own domain.
CARRIER_HINTS = (
    "surveymonkey", "mailchimp", "sendgrid", "constantcontact", "formstack",
    "typeform", "jotform", "hubspot", "mailerlite", "brevo", "sendinblue",
)


def load_brands() -> dict[str, list[str]]:
    if not CONFIG.is_file():
        return dict(SEED_BRANDS)
    try:
        import yaml  # optional; seed is used when unavailable
    except ImportError:
        return dict(SEED_BRANDS)
    try:
        data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return dict(SEED_BRANDS)
    brands = data.get("brands")
    if not isinstance(brands, dict) or not brands:
        return dict(SEED_BRANDS)
    return {str(k).lower(): [str(v).lower() for v in (vals or [])] for k, vals in brands.items()}


def domain_ok(domain: str, legit: list[str]) -> bool:
    return any(domain == good or domain.endswith("." + good) for good in legit)


def split_from(raw_from: str) -> tuple[str, str]:
    """Return (display_name, domain) from a From header."""
    match = re.search(r"<([^>]+)>", raw_from)
    address = (match.group(1) if match else raw_from).strip().lower()
    domain = address.split("@")[-1] if "@" in address else ""
    display = raw_from.split("<")[0].strip().strip('"').strip()
    return display, domain


def assess(display: str, domain: str, brands: dict[str, list[str]]) -> tuple[str, str] | None:
    """Return (confidence, reason) when the pair looks like impersonation."""
    low = display.lower()
    for brand, legit in brands.items():
        if brand not in low:
            continue
        if domain_ok(domain, legit):
            return None
        if any(hint in domain for hint in CARRIER_HINTS):
            return ("high", f"'{brand}' claimed in display name; sent via bulk-mail carrier {domain}")
        if any(token in low for token in NEAR_MISS) or any(token in domain for token in NEAR_MISS):
            return ("high", f"'{brand}' claimed with brand-adjacent hostname ({domain})")
        return ("medium", f"'{brand}' claimed in display name; domain {domain} is not theirs")
    # A brand-adjacent hostname is worth surfacing even with no display-name claim.
    if any(token in domain for token in NEAR_MISS):
        return ("medium", f"brand-adjacent sending domain ({domain})")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-only", action="store_true", help="high-confidence hits only")
    args = parser.parse_args(argv)

    brands = load_brands()
    conn, user = connect(readonly=True)
    if args.folder.upper() != "INBOX":
        conn.select(args.folder, readonly=True)

    typ, data = conn.uid("SEARCH", None, "ALL")
    uids = data[0].split() if data and data[0] else []
    findings = []
    for start in range(0, len(uids), 200):
        chunk = b",".join(uids[start : start + 200])
        # UID must be requested EXPLICITLY and read from the response's `UID n`
        # field. The bare number leading a FETCH response is the message SEQUENCE
        # NUMBER, not the UID, and the two diverge as soon as anything is expunged.
        # Parsing that leading number as a UID yields plausible-looking values that
        # address entirely different messages — which, in a script that then moves
        # or deletes mail, means acting on innocent messages while the intended
        # targets remain. Caught in live use on 2026-08-18; the safe pattern is
        # this one, and a UID SEARCH is authoritative when in doubt.
        typ, resp = conn.uid("FETCH", chunk, "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT TO)])")
        for part in resp:
            if not isinstance(part, tuple):
                continue
            header = part[0].decode(errors="replace")
            uid_match = re.search(r"UID\s+(\d+)", header)
            msg = email.message_from_bytes(part[1])
            raw_from = dec(msg.get("From") or "")
            display, domain = split_from(raw_from)
            verdict = assess(display, domain, brands)
            if not verdict:
                continue
            confidence, reason = verdict
            if args.strict_only and confidence != "high":
                continue
            findings.append(
                {
                    "uid": uid_match.group(1) if uid_match else None,
                    "confidence": confidence,
                    "reason": reason,
                    "display_name": display[:80],
                    "domain": domain,
                    "subject": dec(msg.get("Subject") or "")[:90],
                    "to": dec(msg.get("To") or "")[:70],
                }
            )
    conn.logout()

    if args.json:
        print(json.dumps({"account": user, "folder": args.folder, "findings": findings}, indent=2))
        return 0

    print(f"# impersonation scan  user={user}  folder={args.folder}  scanned={len(uids)}")
    high = [f for f in findings if f["confidence"] == "high"]
    print(f"# flagged={len(findings)}  high-confidence={len(high)}\n")
    for item in sorted(findings, key=lambda f: f["confidence"] != "high"):
        print(f"[{item['confidence'].upper()}] UID={item['uid']}  {item['reason']}")
        print(f"    FROM: {item['display_name']}  <@{item['domain']}>")
        print(f"    SUBJ: {item['subject']}")
        print(f"    TO:   {item['to']}\n")
    if findings:
        print("Report only — nothing was moved. Review each before removing;")
        print("a false positive here is a legitimate vendor notice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
