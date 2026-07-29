#!/usr/bin/env python3
"""One-time imperative archive of INBOX messages from specific senders.

The escape hatch for the past-archive-but-future-keep pattern. The manifest
engine routes by sender pattern, not by date or thread state — so it can't
express "archive this person's existing inbox backlog, but keep their future
mail visible." That pattern recurs for personal contacts whose mail has gone
stale (settled recruiting threads, completed intros, past event chatter) but
who you still want to hear from in the future.

Workflow:
  1. Add a people_known (or other keep-class) rule for the address in
     ~/.synthesis/inbox-cleanup/rules.yaml so future mail keeps in inbox.
  2. Run this script with the address to archive the current backlog.

Usage:
  python3 icloud_archive_senders.py <address> [<address> ...] [--apply]

Dry-run by default; --apply to actually move. Archive is reversible (move
back from the Archive folder). UID-based (no sequence-shift bugs).
"""
import argparse
import email
import re
from email.utils import parseaddr

from _lib import connect, dec


def main():
    ap = argparse.ArgumentParser(
        description="One-time archive of INBOX messages from specific senders.",
    )
    ap.add_argument("addresses", nargs="+",
                    help="Exact From addresses (case-insensitive) to archive.")
    ap.add_argument("--apply", action="store_true",
                    help="Actually move messages (default: dry-run).")
    args = ap.parse_args()

    targets = {a.lower() for a in args.addresses}
    M, user = connect(readonly=not args.apply)
    uids = M.uid("SEARCH", None, "ALL")[1][0].split()

    matches = []  # (uid, addr, subject)
    CHUNK = 400
    for i in range(0, len(uids), CHUNK):
        seq = b",".join(uids[i:i + CHUNK]).decode()
        for part in M.uid("FETCH", seq, "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")[1]:
            if not isinstance(part, tuple):
                continue
            m = re.search(r"UID (\d+)", part[0].decode("utf-8", "replace"))
            if not m:
                continue
            uid = m.group(1)
            msg = email.message_from_string(part[1].decode("utf-8", "replace"))
            _, addr = parseaddr(dec(msg.get("From", "")))
            if addr.lower() in targets:
                matches.append((uid, addr.lower(), dec(msg.get("Subject", ""))))

    print(f"# one-time archive  user={user}  targets={sorted(targets)}  matches={len(matches)}")
    for uid, addr, subj in matches[:20]:
        print(f"  UID={uid:>7s}  {addr:32s}  {subj[:60]}")
    if len(matches) > 20:
        print(f"  ... ({len(matches) - 20} more)")

    if not matches:
        M.logout()
        return

    if args.apply:
        M.create("Archive")
        M.subscribe("Archive")
        caps = [(c.decode() if isinstance(c, bytes) else c).upper() for c in M.capabilities]
        has_move = "MOVE" in caps
        uid_list = [u for u, _, _ in matches]
        done = 0
        for i in range(0, len(uid_list), 200):
            batch = uid_list[i:i + 200]
            csv = ",".join(batch)
            if has_move:
                M.uid("MOVE", csv, "Archive")
            else:
                M.uid("COPY", csv, "Archive")
                M.uid("STORE", csv, "+FLAGS", r"(\Deleted)")
                M.uid("EXPUNGE", csv)
            done += len(batch)
        print(f"\nMOVED {done} to Archive")
    else:
        print("\n(dry-run — re-run with --apply to move)")
    M.logout()


if __name__ == "__main__":
    main()
