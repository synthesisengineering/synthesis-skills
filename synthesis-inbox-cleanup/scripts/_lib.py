#!/usr/bin/env python3
"""Shared logic for inbox-cleanup scripts (census / plan / apply / tail / purge).

ONE source of truth for credential loading, account configuration, header
parsing, and disposition resolution — so the dry-run plan and the executor
can never diverge.

Configuration:
  ~/.synthesis/inbox-cleanup/config.yaml  — account list, IMAP host, behavior
  ~/.synthesis/inbox-cleanup/rules.yaml   — sender rules, never_touch, subjects

Credentials:
  macOS Keychain (service 'inbox-cleanup-imap', or whatever config.yaml sets)
  or fallback file ~/.synthesis/inbox-cleanup/imap.secret
  Never printed or logged.
"""
import imaplib, email, subprocess, sys, os, ssl, yaml
from email.header import decode_header, make_header
from email.utils import parseaddr

CONFIG_PATH = os.path.expanduser("~/.synthesis/inbox-cleanup/config.yaml")
MANIFEST_PATH = os.path.expanduser("~/.synthesis/inbox-cleanup/rules.yaml")


def _load_yaml(path, what):
    if not os.path.exists(path):
        sys.exit(f"ERROR: {what} not found at {path}\n"
                 f"Run the installer first: scripts/install.sh")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


CONFIG = _load_yaml(CONFIG_PATH, "config")
RULES = _load_yaml(MANIFEST_PATH, "rules manifest")
CLASS = RULES.get("class_defaults", {})

IMAP_CFG = CONFIG.get("imap", {})
HOST = IMAP_CFG.get("host", "imap.mail.me.com")
USER_CANDIDATES = IMAP_CFG.get("user_candidates", [])
KEYCHAIN_SERVICE = IMAP_CFG.get("keychain_service", "inbox-cleanup-imap")

if not USER_CANDIDATES:
    sys.exit(f"ERROR: config.yaml has no imap.user_candidates entries.\n"
             f"Edit {CONFIG_PATH} and add at least one account.")


def get_password():
    p = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        return p.stdout.strip()
    f = os.path.expanduser("~/.synthesis/inbox-cleanup/imap.secret")
    if os.path.exists(f):
        # Fail closed if the at-rest credential is readable by group/other.
        mode = os.stat(f).st_mode
        if mode & 0o077:
            sys.exit(f"ERROR: {f} is accessible to group/other "
                     f"(mode {oct(mode & 0o777)}). Run: chmod 600 {f}")
        with open(f, encoding="utf-8") as fh:
            return fh.read().strip()
    sys.exit(f"ERROR: no IMAP password (Keychain '{KEYCHAIN_SERVICE}' "
             f"or ~/.synthesis/inbox-cleanup/imap.secret)")


def dec(s):
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s or ""


def msg_fields(raw):
    msg = email.message_from_string(raw)
    name, addr = parseaddr(dec(msg.get("From", "")))
    addr = addr.lower()
    domain = addr.split("@")[-1] if "@" in addr else "(none)"
    subject = dec(msg.get("Subject", ""))
    return name, addr, domain, subject


def dom_match(domain, pat):
    return domain == pat or domain.endswith("." + pat)


def _disp(s):
    if "disposition" in s:
        return s["disposition"]
    return CLASS.get(s.get("class"), "keep")


def resolve(name, addr, domain, subject):
    """Return (disposition, reason). Precedence:
    never_touch > subject_rules > senders(address>domain>name) > class_defaults > unmatched(keep)."""
    nl, sl = (name or "").lower(), (subject or "").lower()
    nt = RULES.get("never_touch", {})
    if addr in [a.lower() for a in nt.get("addresses", [])]:
        return "keep", "never_touch"
    for d in nt.get("domains", []):
        if dom_match(domain, d):
            return "keep", "never_touch"
    for sr in RULES.get("subject_rules", []):
        c = sr.get("if", {})
        # Domain check: if domain is specified, it must match. Absent domain = any-sender rule.
        if "domain" in c and not dom_match(domain, c["domain"]):
            continue
        # Subject check: subject_contains is a substring match; subject_starts_with is a prefix match.
        # At least one of the two must be specified and must match. Both specified = both must match.
        sc = c.get("subject_contains", "").lower()
        ssw = c.get("subject_starts_with", "").lower()
        if not sc and not ssw:
            continue  # malformed rule (no subject operator)
        if sc and sc not in sl:
            continue
        if ssw and not sl.startswith(ssw):
            continue
        return sr["disposition"], "subject_rule"
    sset = RULES.get("senders", [])
    for s in sset:
        m = s.get("match", {})
        if "address" in m and m["address"].lower() == addr:
            return _disp(s), "sender:addr"
    for s in sset:
        m = s.get("match", {})
        if "domain" in m and dom_match(domain, m["domain"]):
            return _disp(s), "sender:dom"
    for s in sset:
        m = s.get("match", {})
        if "name" in m and m["name"].lower() in nl:
            return _disp(s), "sender:name"
    return "keep", "unmatched"


def connect(readonly=True):
    pw = get_password()
    # Explicit default context: certificate-chain + hostname verification,
    # independent of the host Python's defaults.
    M = imaplib.IMAP4_SSL(HOST, ssl_context=ssl.create_default_context())
    last = None
    for u in USER_CANDIDATES:
        try:
            M.login(u, pw)
            M.select("INBOX", readonly=readonly)
            return M, u
        except imaplib.IMAP4.error as e:
            last = e
    sys.exit(f"ERROR: IMAP login failed for {USER_CANDIDATES}: {last}")
