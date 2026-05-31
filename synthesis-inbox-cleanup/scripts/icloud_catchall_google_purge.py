#!/usr/bin/env python3
"""Trash Google notices addressed to stranger aliases on a catch-all domain.

If you own a domain with catch-all routing to this IMAP inbox (e.g., your
domain `example.com` routes all *@example.com to your iCloud), strangers
who use made-up addresses on it (`fake@example.com`) when signing up for
Google services produce sign-in / billing / inactive notices that land
here. Your REAL Google accounts live elsewhere — they're never @example.com.

This script trashes those stranger-aliased notices.

Filter (INBOX):
  FROM domain == google.com, *.google.com, googlemail.com, or googleapis.com
  AND any To/Cc recipient ends with @<catchall-domain> (or .<catchall-domain>)
  AND recipient is NOT in spare_recipients
  AND subject does NOT contain any spare_subject_keywords

Configuration: read from ~/.synthesis/inbox-cleanup/config.yaml, section `catchall`:
  domains:               list of catch-all domains you own
  spare_recipients:      addresses on the domain that ARE yours (spare these)
  spare_subject_keywords: substrings that spare a message regardless of recipient
                         (e.g., when you administer Google Workspace under a
                          family member's domain and notices arrive here)

Dry-run by default; --apply to actually trash. Trash is recoverable ~30 days.
"""
import argparse, collections, re, email
from email.utils import getaddresses
from _lib import connect, dec, CONFIG

GOOGLE_EXACT = {"google.com", "googlemail.com", "googleapis.com"}

CATCHALL = CONFIG.get("catchall", {})
DOMAINS = [d.lower() for d in (CATCHALL.get("domains") or [])]
SPARE_RECIPIENTS = {a.lower() for a in (CATCHALL.get("spare_recipients") or [])}
SPARE_SUBJECT_KEYWORDS = {k.lower() for k in (CATCHALL.get("spare_subject_keywords") or [])}


def is_google_from(addr: str) -> bool:
    addr = addr.lower()
    if "@" not in addr:
        return False
    domain = addr.rsplit("@", 1)[1]
    return domain in GOOGLE_EXACT or domain.endswith(".google.com")


def is_catchall_recipient(addr: str) -> bool:
    for d in DOMAINS:
        if addr.endswith("@" + d) or addr.endswith("." + d):
            return True
    return False


def find_match(addrs, subject: str = ""):
    """Return the matched catch-all address (trash candidate), or None if spared / no match.

    Spare conditions (any one triggers spare):
      - any recipient is in spare_recipients
      - subject contains any spare_subject_keywords substring (case-insensitive)
    """
    addrs_lower = [a.lower() for a in addrs]
    if any(a in SPARE_RECIPIENTS for a in addrs_lower):
        return None
    sl = (subject or "").lower()
    if any(kw in sl for kw in SPARE_SUBJECT_KEYWORDS):
        return None
    for a in addrs_lower:
        if is_catchall_recipient(a):
            return a
    return None


def parse_addrs(header_value: str):
    if not header_value:
        return []
    try:
        decoded = dec(header_value)
    except Exception:
        decoded = header_value
    return [a for _, a in getaddresses([decoded]) if a]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually trash (default: dry-run)")
    args = ap.parse_args()

    if not DOMAINS:
        import sys
        sys.exit("ERROR: config.yaml has no catchall.domains entries.\n"
                 "This script is a no-op without at least one catch-all domain.")

    M, user = connect(readonly=not args.apply)
    uids = M.uid("SEARCH", None, "ALL")[1][0].split()
    total = len(uids)

    matches = []          # (uid, from_addr, matched_addr, subject)
    sender_count = collections.Counter()
    CHUNK = 400
    for i in range(0, total, CHUNK):
        seq = b",".join(uids[i:i + CHUNK]).decode()
        resp = M.uid("FETCH", seq, "(UID BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT)])")[1]
        for part in resp:
            if not isinstance(part, tuple):
                continue
            m = re.search(r"UID (\d+)", part[0].decode("utf-8", "replace"))
            if not m:
                continue
            uid = m.group(1)
            msg = email.message_from_string(part[1].decode("utf-8", "replace"))
            from_addrs = parse_addrs(msg.get("From", ""))
            if not from_addrs or not is_google_from(from_addrs[0]):
                continue
            recipients = parse_addrs(msg.get("To", "")) + parse_addrs(msg.get("Cc", ""))
            subj = dec(msg.get("Subject", ""))
            ra = find_match(recipients, subj)
            if not ra:
                continue
            matches.append((uid, from_addrs[0].lower(), ra, subj))
            sender_count[from_addrs[0].lower()] += 1

    print(f"# Google → catch-all aliases in INBOX  user={user}  "
          f"matches={len(matches)} / scanned {total}  domains={DOMAINS}")
    if not matches:
        M.logout()
        return

    print("\n## By sender")
    for s, c in sender_count.most_common(20):
        print(f"{c:5d}  {s}")
    print("\n## Sample (first 15)")
    for uid, f, t, s in matches[:15]:
        print(f"UID={uid:>7s}  TO={t[:28]:28s}  FROM={f[:38]:38s}  {s[:55]}")

    if args.apply:
        caps = [(c.decode() if isinstance(c, bytes) else c).upper() for c in M.capabilities]
        has_move = "MOVE" in caps
        done = 0
        all_uids = [u for u, *_ in matches]
        for i in range(0, len(all_uids), 200):
            batch = all_uids[i:i + 200]
            csv = ",".join(batch)
            if has_move:
                M.uid("MOVE", csv, "Trash")
            else:
                M.uid("COPY", csv, "Trash")
                M.uid("STORE", csv, "+FLAGS", r"(\Deleted)")
                M.uid("EXPUNGE", csv)
            done += len(batch)
        print(f"\nTRASHED: {done}")
    else:
        print("\n(dry-run — re-run with --apply to trash)")
    M.logout()


if __name__ == "__main__":
    main()
