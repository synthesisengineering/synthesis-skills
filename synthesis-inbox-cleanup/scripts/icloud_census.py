#!/usr/bin/env python3
"""iCloud / generic-IMAP INBOX sender census (READ-ONLY).

Scans all INBOX From-headers, aggregates by sender, and cross-references the
inbox-cleanup rules manifest to show what existing rules already cover vs. what
is still unclassified (the work-list for triage decisions).

Credential: app-specific password read at runtime from macOS Keychain
(service from config.yaml, default 'inbox-cleanup-imap') or fallback file
~/.synthesis/inbox-cleanup/imap.secret.
This script NEVER writes, prints, or logs the password.

Read-only: INBOX is opened readonly=True. Makes no changes to the mailbox.
"""
import imaplib, email, collections
from email.utils import parseaddr
from _lib import HOST, USER_CANDIDATES, MANIFEST_PATH, get_password, dec, _load_yaml

MASKED_DOMAINS = {"icloud.com", "privaterelay.appleid.com"}


def classify(name, addr, domain, rules):
    if not rules:
        return "UNCLASSIFIED"
    nl = (name or "").lower()
    nt = rules.get("never_touch", {}) or {}
    for d in nt.get("domains", []) or []:
        if domain == d or domain.endswith("." + d):
            return "never_touch"
    for a in nt.get("addresses", []) or []:
        if addr == a.lower():
            return "never_touch"
    for fp in rules.get("friends_protect", []) or []:
        m = fp.get("match", {})
        if m.get("address", "").lower() == addr:
            return "friend"
        if m.get("domain") and domain == m["domain"]:
            return "friend"
    for s in rules.get("senders", []) or []:
        m = s.get("match", {})
        if "address" in m and m["address"].lower() == addr:
            return s.get("class", s.get("disposition", "?"))
        if "domain" in m and (domain == m["domain"] or domain.endswith("." + m["domain"])):
            return s.get("class", s.get("disposition", "?"))
        if "name" in m and m["name"].lower() in nl:
            return s.get("class", s.get("disposition", "?"))
    return "UNCLASSIFIED"


def main():
    pw = get_password()
    M = imaplib.IMAP4_SSL(HOST)
    user = None
    err = None
    for u in USER_CANDIDATES:
        try:
            M.login(u, pw)
            user = u
            break
        except imaplib.IMAP4.error as e:
            err = e
    if not user:
        import sys
        sys.exit(f"ERROR: IMAP login failed for {USER_CANDIDATES}: {err}")

    M.select("INBOX", readonly=True)
    typ, data = M.search(None, "ALL")
    ids = data[0].split()
    total = len(ids)
    rules = _load_yaml(MANIFEST_PATH, "rules manifest")

    vol = collections.Counter()
    meta = {}
    CHUNK = 400
    for i in range(0, total, CHUNK):
        seq = b",".join(ids[i:i + CHUNK]).decode()
        typ, resp = M.fetch(seq, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
        for part in resp:
            if isinstance(part, tuple):
                raw = part[1].decode("utf-8", "replace")
                frm = dec(email.message_from_string(raw).get("From", ""))
                name, addr = parseaddr(frm)
                addr = addr.lower()
                domain = addr.split("@")[-1] if "@" in addr else "(none)"
                key = ("name:" + (name or addr)) if domain in MASKED_DOMAINS else ("dom:" + domain)
                vol[key] += 1
                if key not in meta:
                    meta[key] = (name, addr, domain)
    M.logout()

    rows = []
    for key, c in vol.items():
        name, addr, domain = meta[key]
        rows.append((c, key, name, addr, domain, classify(name, addr, domain, rules)))
    rows.sort(reverse=True)

    print(f"# INBOX census  user={user}  total_messages={total}  distinct_senders={len(vol)}")
    covered = sum(c for c, _, _, _, _, cls in rows if cls != "UNCLASSIFIED")
    pct = 100 * covered // max(total, 1)
    print(f"# covered by existing rules: {covered}/{total} ({pct}%)   unclassified: {total - covered}\n")

    print("## UNCLASSIFIED senders (need a decision) — by volume")
    for c, key, name, addr, domain, cls in rows:
        if cls == "UNCLASSIFIED":
            print(f"{c:5d}  {(name or addr)[:38]:38s}  {addr[:44]}")

    print("\n## Already covered by manifest — by volume")
    for c, key, name, addr, domain, cls in rows:
        if cls != "UNCLASSIFIED":
            print(f"{c:5d}  [{cls:18s}] {(name or addr)[:28]:28s}  {addr[:34]}")


if __name__ == "__main__":
    main()
