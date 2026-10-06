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
    python3 scan_impersonation.py --check-config   # validate the private config only

Never trashes. Removal is a separate, human-reviewed step, per the engine's rule
that the LLM proposes and the deterministic layer disposes. A false positive here
is a legitimate vendor notice; deleting one automatically is its own harm.

The private ``~/.synthesis/inbox-cleanup/impersonation.yaml`` must declare the
principal: ``principal.names`` (the account owner's display name and aliases) and
``principal.addresses`` (the exact mailboxes allowed to send under those names).
Display-name impersonation of the account owner is a common pretext for invoice
fraud, so a scan without that rule refuses (exit 2) before reading any mail: a
scan that silently lacks it would look clean. ``--check-config`` validates the
file without touching mail. ``brands`` is optional; omitting it selects the
built-in seed below. A shared or public domain never authorizes the principal's
name; only an exact listed address does, and even that is not proof of safety.
A report is a review candidate, never proof of identity or permission to remove.
"""

from __future__ import annotations

import argparse
import email
import email.errors
from email import policy
from email.header import decode_header, make_header
from email.parser import HeaderParser
import json
import re
import stat
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root or the installed runtime: holds synthesis/
from synthesis import yamlish  # noqa: E402

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


class ConfigError(ValueError):
    """No scan may silently lose configured identity protection."""


MAX_CONFIG_BYTES = 65536
MAX_HEADER_CHARS = 16384


def dec(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (ValueError, LookupError, UnicodeError):
        return value


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = "".join(c for c in value if unicodedata.category(c) != "Cf")
    return " ".join(value.casefold().split())


def normalize_domain(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 253:
        raise ConfigError("invalid domain")
    try:
        result = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ConfigError("invalid domain") from exc
    if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
               for part in result.split(".")):
        raise ConfigError("invalid domain")
    return result


def normalize_address(value: str) -> str:
    # Exact mailbox identity: no wildcard, suffix, plus-tag or dot stripping.
    if not isinstance(value, str) or len(value) > 254 or value.count("@") != 1:
        raise ConfigError("principal addresses must be exact mailboxes")
    local, domain = value.split("@")
    if (not local or len(local) > 64 or local.startswith(".") or local.endswith(".")
            or ".." in local or not re.fullmatch(r"[A-Za-z0-9.!#$%&'+/=?^_`{|}~-]+", local)):
        raise ConfigError("principal addresses must be exact mailboxes")
    return local.lower() + "@" + normalize_domain(domain)


def validate_config(data: object) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    if not isinstance(data, dict) or set(data) - {"brands", "principal"}:
        raise ConfigError("configuration requires only brands and principal fields")
    principal = data.get("principal")
    if not isinstance(principal, dict) or set(principal) != {"names", "addresses"}:
        raise ConfigError("principal requires explicit names and exact addresses")
    names, addresses = principal["names"], principal["addresses"]
    if (not isinstance(names, list) or not 1 <= len(names) <= 32
            or not all(isinstance(n, str) and 0 < len(n) <= 256
                       and not any(unicodedata.category(c) == "Cc" for c in n) for n in names)):
        raise ConfigError("principal names must be a bounded nonempty text list")
    normalized_names = [normalize_name(n) for n in names]
    if not all(normalized_names) or len(set(normalized_names)) != len(names):
        raise ConfigError("principal names are empty or repeated after normalization")
    if not isinstance(addresses, list) or not 1 <= len(addresses) <= 256:
        raise ConfigError("principal addresses must be a bounded nonempty list")
    normalized_addresses = [normalize_address(a) for a in addresses]
    if len(set(normalized_addresses)) != len(addresses):
        raise ConfigError("principal addresses repeat after normalization")
    brands = data.get("brands", SEED_BRANDS)
    if not isinstance(brands, dict) or not 1 <= len(brands) <= 512:
        raise ConfigError("brands must be a bounded nonempty mapping")
    checked = {}
    for name, domains in brands.items():
        if (not isinstance(name, str) or not name.strip() or len(name) > 256
                or not isinstance(domains, list) or not 1 <= len(domains) <= 64):
            raise ConfigError("brand names require bounded domain lists")
        key = name.lower()
        if key in checked:
            raise ConfigError("brand names repeat after normalization")
        checked[key] = [normalize_domain(d) for d in domains]
    return checked, {"names": normalized_names, "addresses": normalized_addresses}


def load_config(path: Path = CONFIG) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Read the private policy: a bounded regular file (not a symlink), unique keys.
    The YAML reader refuses a repeated key and reads every key as text."""
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONFIG_BYTES:
            raise ConfigError("configuration must be a regular file of at most 64 KiB")
        raw = path.read_bytes()[:MAX_CONFIG_BYTES + 1]
        if len(raw) > MAX_CONFIG_BYTES:
            raise ConfigError("configuration must be a regular file of at most 64 KiB")
        data = yamlish.load(raw.decode("utf-8"))
    except ConfigError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConfigError("cannot read valid impersonation configuration; "
                          "configure principal names and exact addresses") from exc
    return validate_config(data)


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


def assess_header(raw_from: str, brands: dict[str, list[str]],
                  principal: dict[str, list[str]]) -> tuple[str, str] | None:
    """Pure report-only assessment; explicit identity never comes from a domain."""
    if not isinstance(raw_from, str) or len(raw_from) > MAX_HEADER_CHARS:
        raise ValueError("From header exceeds bounded input")
    unfolded = re.sub(r"\r?\n[ \t]+", " ", raw_from)
    if "\n" in unfolded or "\r" in unfolded:
        return ("high", "malformed multi-line From header")
    try:
        header = HeaderParser(policy=policy.default).parsestr("From: " + unfolded + "\n\n")["From"]
        senders = list(header.addresses)
    except (ValueError, IndexError, AttributeError, email.errors.HeaderParseError):
        return ("medium", "malformed From header requires review")
    # A group label is a display-name claim, not an exact mailbox identity.
    # This also catches empty groups, which have no flattened addresses.
    if any(group.display_name is not None
           and normalize_name(group.display_name) in principal["names"]
           for group in header.groups):
        return ("high", "principal name claimed by an ambiguous sender group")
    claimed = any(normalize_name(s.display_name) in principal["names"] for s in senders)
    if claimed:
        if len(senders) != 1 or header.defects:
            return ("high", "principal name claimed by an ambiguous sender")
        try:
            address = normalize_address(senders[0].addr_spec)
        except ConfigError:
            return ("high", "principal name claimed without a valid exact sender address")
        if address not in principal["addresses"]:
            return ("high", "principal name claimed from an address outside the explicit allowlist")
        return None
    for sender in senders:
        try:
            domain = normalize_domain(sender.domain)
        except ConfigError:
            domain = ""
        verdict = assess(sender.display_name, domain, brands)
        if verdict:
            return verdict
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default="INBOX")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-only", action="store_true", help="high-confidence hits only")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--check-config", action="store_true", help="validate identity coverage without reading mail")
    args = parser.parse_args(argv)
    try:
        brands, principal = load_config(args.config)
    except (ConfigError, ImportError) as exc:
        print(f"impersonation configuration refused: {exc}", file=sys.stderr)
        return 2
    if args.check_config:
        print(json.dumps({"status": "CONFIGURED", "principal_names": len(principal["names"]),
                          "principal_addresses": len(principal["addresses"]), "brands": len(brands)}))
        return 0
    # Loading this connector reads account configuration; do so only after the
    # complete scanner policy has passed, never when importing pure assessment.
    from _lib import connect
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
            encoded_from = ", ".join(msg.get_all("From", []))
            # Decode only for presentation after structural assessment. Encoded
            # punctuation belongs to a name, not to address-list syntax.
            verdict = assess_header(encoded_from, brands, principal)
            raw_from = dec(encoded_from)
            display, domain = split_from(raw_from)
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
