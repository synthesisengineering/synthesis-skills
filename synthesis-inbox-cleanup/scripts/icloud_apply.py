#!/usr/bin/env python3
"""iCloud / generic-IMAP INBOX executor — moves messages per the manifest dispositions.

Stages: newsletter | archive | trash | all.  DRY-RUN by default; pass --apply to move.
UID-based (no sequence-shift bugs). Shares disposition logic with the planner via _lib.

  newsletter → Newsletters    archive → Archive    trash → Trash    keep → (untouched)

Nothing is permanently deleted: trash goes to the Trash mailbox (recoverable ~30 days
on most providers, including iCloud). Each run re-derives dispositions from the CURRENT
inbox, so stages can run independently.
"""
import argparse, re, collections
from _lib import connect, resolve, msg_fields

TARGET = {"newsletter": "Newsletters", "archive": "Archive", "trash": "Trash"}


def build_uid_disp(M):
    uids = M.uid('SEARCH', None, 'ALL')[1][0].split()
    uid_disp = {}
    CHUNK = 400
    for i in range(0, len(uids), CHUNK):
        seq = b",".join(uids[i:i + CHUNK]).decode()
        for part in M.uid('FETCH', seq, "(UID BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")[1]:
            if isinstance(part, tuple):
                m = re.search(r"UID (\d+)", part[0].decode("utf-8", "replace"))
                if not m:
                    continue
                name, addr, domain, subject = msg_fields(part[1].decode("utf-8", "replace"))
                uid_disp[m.group(1)] = resolve(name, addr, domain, subject)[0]
    return uid_disp


def move_batch(M, uids, target, has_move):
    csv = ",".join(uids)
    if has_move:
        M.uid('MOVE', csv, target)
    else:
        M.uid('COPY', csv, target)
        M.uid('STORE', csv, '+FLAGS', r'(\Deleted)')
        M.uid('EXPUNGE', csv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["newsletter", "archive", "trash", "all"])
    ap.add_argument("--apply", action="store_true", help="actually move (default: dry-run)")
    args = ap.parse_args()
    stages = ["newsletter", "archive", "trash"] if args.stage == "all" else [args.stage]

    M, user = connect(readonly=not args.apply)
    caps = [(c.decode() if isinstance(c, bytes) else c).upper() for c in M.capabilities]
    has_move = "MOVE" in caps

    if args.apply:
        for mb in sorted({TARGET[s] for s in stages}):
            M.create(mb)
            M.subscribe(mb)

    uid_disp = build_uid_disp(M)
    counts = collections.Counter(uid_disp.values())
    print(f"# EXECUTOR  user={user}  apply={args.apply}  MOVE_cap={has_move}  inbox={len(uid_disp)}")
    print("# current plan: " + "  ".join(f"{d}={counts.get(d, 0)}" for d in ['trash', 'archive', 'newsletter', 'keep']))

    for stage in stages:
        target = TARGET[stage]
        todo = [u for u, d in uid_disp.items() if d == stage]
        done = 0
        for i in range(0, len(todo), 200):
            batch = todo[i:i + 200]
            if args.apply:
                move_batch(M, batch, target, has_move)
            done += len(batch)
        print(f"  {stage:11s} → {target:12s} {done:6d} {'MOVED' if args.apply else 'would move'}")
    M.logout()


if __name__ == "__main__":
    main()
