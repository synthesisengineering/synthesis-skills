#!/usr/bin/env python3
"""List INBOX senders matching NO manifest rule (resolve reason == 'unmatched').

These currently default to KEEP — the long-tail work-list for classification.
READ-ONLY. Shares disposition logic with planner/executor via _lib.
"""
import collections
from _lib import connect, resolve, msg_fields


def main():
    M, u = connect(readonly=True)
    ids = M.search(None, "ALL")[1][0].split()
    total = len(ids)
    vol = collections.Counter()
    ex = {}
    CHUNK = 400
    for i in range(0, total, CHUNK):
        seq = b",".join(ids[i:i + CHUNK]).decode()
        for part in M.fetch(seq, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")[1]:
            if isinstance(part, tuple):
                name, addr, domain, subject = msg_fields(part[1].decode("utf-8", "replace"))
                disp, reason = resolve(name, addr, domain, subject)
                if reason == "unmatched":
                    key = f"{name or addr}  <{addr}>"
                    vol[key] += 1
                    ex.setdefault(key, subject)
    M.logout()
    um = sum(vol.values())
    print(f"# UNMATCHED in INBOX (currently kept) — {um} msgs / {len(vol)} senders / inbox total {total}\n")
    for snd, c in vol.most_common(70):
        print(f"{c:4d}  {snd[:50]:50s}  e.g. {ex[snd][:38]}")


if __name__ == "__main__":
    main()
