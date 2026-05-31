#!/usr/bin/env python3
"""iCloud / generic-IMAP INBOX dry-run planner (READ-ONLY).

Applies the manifest to every INBOX message and reports the action plan
(keep / archive / trash / newsletter) with per-sender breakdowns. NO changes.
Shares disposition logic with the executor via _lib (cannot diverge).
"""
import collections
from _lib import connect, resolve, msg_fields


def main():
    M, user = connect(readonly=True)
    ids = M.search(None, "ALL")[1][0].split()
    total = len(ids)
    disp_count = collections.Counter()
    by_disp_sender = collections.defaultdict(collections.Counter)
    CHUNK = 400
    for i in range(0, total, CHUNK):
        seq = b",".join(ids[i:i + CHUNK]).decode()
        for part in M.fetch(seq, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")[1]:
            if isinstance(part, tuple):
                name, addr, domain, subject = msg_fields(part[1].decode("utf-8", "replace"))
                disp, _ = resolve(name, addr, domain, subject)
                disp_count[disp] += 1
                by_disp_sender[disp][f"{name or addr}  <{addr}>"] += 1
    M.logout()

    print(f"# DRY-RUN PLAN  user={user}  inbox=INBOX  total={total}\n")
    for d in ["trash", "archive", "newsletter", "keep"]:
        print(f"  {d.upper():11s} {disp_count.get(d, 0):6d}")
    for d in ["trash", "newsletter", "archive"]:
        print(f"\n## → {d.upper()}  ({disp_count.get(d, 0)} msgs)  — by sender")
        for snd, c in by_disp_sender[d].most_common():
            print(f"{c:5d}  {snd}")
    print(f"\n## → KEEP ({disp_count.get('keep', 0)} msgs) — top senders (stay in inbox)")
    for snd, c in by_disp_sender['keep'].most_common(40):
        print(f"{c:5d}  {snd}")


if __name__ == "__main__":
    main()
