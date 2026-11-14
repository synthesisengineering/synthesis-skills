#!/usr/bin/env python3
"""Replay the turn-end shortcut check's judge over recorded list hits, before its model or policy changes ship.

    judge_replay.py --since YYYY-MM-DD [--claude DIR] [--codex DIR] [--muse DIR] [--model NAME]... [--url URL]
                    [--labels FILE [--split dev|test|all] [--seed N]] [--deadline SECONDS] [--cleared FILE] [--measure-only]

Reads the harnesses' session records changed since the date (Claude Code's projects folder, Codex's sessions folder,
Muse's sessions folder; each defaults to where the harness keeps it) and finds every turn end: an agent's last reply
before the next prompt, with no tool call after it. A turn end the reply check sent back for shortcut phrasing is a
recorded sendback: Claude Code records the hook's words beside the reply; in Codex and Muse they arrive as the next
prompt. It counts the turn ends the list flags (the built-in phrases and the config's `shortcut_phrases`), the only
replies the judge reads. For each model named it judges every recorded sendback the list flags, or, with --labels, the
labeled list hits of the split asked for: a labels file's rows give a record's path and line, the reply's digest, its
source (`list-hit` or `no-list-hit`) and a label (`shortcut`, `legitimate` or `unsure`). The list hits are split in
two with the seed, each label's larger half to dev; an item is judged only while its digest still matches. It prints,
by label, how many the judge cleared (a sure pass: what the check lets through), held, passed unsure and left without
a verdict, and the gate: no real shortcut and no unsure item cleared, and the warm 95th percentile inside the longest
deadline a config may give. Latency is the first verdict of a model not yet loaded, then the median and 95th
percentile of the rest.

Uses the runtime beside it and the synthesis config of SYNTHESIS_HOME (point it at a copy), with the judge section
replaced by each model in turn; the verdicts are cached and logged in that home. A model it loaded is unloaded at the
end (keep_alive 0). Prints counts, dates and fixed words only, never a record's text. --cleared names a file for each
cleared item: its record's path, line and digest, never its text, so a person can read each one in its record. Exit 0
when it ran, 2 when it could not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # an installed plugin must stay byte-identical; Muse verifies its bundle
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the plugin root or the installed runtime: holds synthesis/
try:
    from synthesis import judge, paths, reply_check  # noqa: E402
except Exception as exc:  # a collection without the runtime: the one line that says nothing was replayed
    print(f"NOT REPLAYED: the synthesis runtime cannot be imported: {exc}", file=sys.stderr)
    sys.exit(2)

MARK = "Before this reply goes out, revise it:"
LABEL = "lazy-shortcut phrasing"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(str(part.get("text") or "") for part in content or [] if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text"))


def claude_events(path: Path, seen: set):
    """(kind, line, text, message) for a Claude Code record: replies, tool calls, prompts and the reply check's
    sendbacks, each entry once across records (a resumed session copies its history)."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, raw in enumerate(handle, 1):
            if '"api-request-blob"' in raw[:200]:
                continue
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("isSidechain") or row.get("uuid") in seen:
                continue
            seen.add(row.get("uuid")) if row.get("uuid") else None
            attachment, message = row.get("attachment"), row.get("message") if isinstance(row.get("message"), dict) else {}
            if isinstance(attachment, dict):
                blob = json.dumps(attachment)
                if attachment.get("type") == "hook_blocking_error" and MARK in blob:
                    yield "stop", number, blob, None
                continue
            parts = message.get("content") if isinstance(message.get("content"), list) else [{"type": "text", "text": message.get("content")}]
            if row.get("type") == "assistant":
                for part in (p for p in parts if isinstance(p, dict)):
                    if part.get("type") == "text" and part.get("text"):
                        yield "text", number, part["text"], message.get("id")
                    elif part.get("type") == "tool_use":
                        yield "use", number, "", message.get("id")
            elif row.get("type") == "user" and not row.get("isMeta") and not any(isinstance(p, dict) and p.get("type") == "tool_result" for p in parts):
                yield "prompt", number, _text(parts), None


def codex_events(path: Path, seen: set):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, raw in enumerate(handle, 1):
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            payload = row.get("payload") if isinstance(row, dict) and isinstance(row.get("payload"), dict) else {}
            kind = str(payload.get("type") or "")
            if row.get("type") == "response_item" and kind == "message":
                said = _text(payload.get("content"))
                yield ("text", number, said, number) if payload.get("role") == "assistant" else (
                    "stop" if said.lstrip().startswith(MARK) else "prompt", number, said, None)
            elif row.get("type") == "response_item" and kind.endswith("_call"):
                yield "use", number, "", None


def muse_events(path: Path, seen: set):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, raw in enumerate(handle, 1):
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            for frame in [row] + [c for c in row.get("children") or [] if isinstance(c, dict)] if isinstance(row, dict) else []:
                payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
                event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
                if frame.get("payload_type") == "runtime.user_intent.accepted":
                    said = "\n".join(_text(m.get("content")) for m in payload.get("model_messages") or [] if isinstance(m, dict))
                    yield "stop" if said.lstrip().startswith(MARK) else "prompt", number, said, None
                elif event.get("kind") == "assistant_message_committed":
                    yield "text", number, str(event.get("text") or ""), number
                elif event.get("kind") == "assistant_tool_calls_committed":
                    yield "use", number, "", None


READERS = {"claude-code": claude_events, "codex": codex_events, "muse": muse_events}


def turn_ends(events) -> list:
    """[(line, reply, the sendback's words or "")]: the last message's text before a prompt, a sendback or the end,
    with no tool call after it."""
    found, words, line, message, used = [], [], 0, None, False
    for kind, number, text, ident in events:
        if kind == "text":
            words = (words if ident == message and not used else []) + [text]
            line, message, used = number, ident, False
        elif kind == "use":
            used = True
        else:
            found += [(line, "\n\n".join(words), text if kind == "stop" else "")] if words and not used else []
            words, used = [], False
    return found + ([(line, "\n\n".join(words), "")] if words and not used else [])


def split(rows: list, seed: int) -> tuple:
    """(dev, test): each label's items in a fixed order, shuffled with the seed, the larger half of each to dev."""
    dev, test = [], []
    for label in sorted({str(row.get("label")) for row in rows}):
        group = sorted((r for r in rows if str(r.get("label")) == label), key=lambda r: (str(r.get("path")), str(r.get("line")), str(r.get("digest"))))
        random.Random(f"{seed}:{label}").shuffle(group)
        dev, test = dev + group[:(len(group) + 1) // 2], test + group[(len(group) + 1) // 2:]
    return dev, test


def labeled(args, items: list) -> list:
    """[(part, label, turn end)] for the labeled list hits of the split asked for that the records still hold."""
    with open(args.labels, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    listed, at = [r for r in rows if r.get("source") == "list-hit"], {(e[1], e[2]): e for e in items}
    found = {id(r): at.get((str(r.get("path")), r.get("line"))) for r in listed}
    same = {k: e for k, e in found.items() if e and hashlib.sha256(e[3].encode()).hexdigest()[:16] == next(
        r.get("digest") for r in listed if id(r) == k)}
    labels, aside = sorted({str(r.get("label")) for r in listed}), len(rows) - len(listed)
    sizes = ", ".join(f"{k} {sum(str(r.get('label')) == k for r in listed)}" for k in labels)
    print(f"labels: {len(listed)} list hits ({sizes}); "
          f"found {len(same)}, digest changed {sum(1 for v in found.values() if v) - len(same)}, not found {sum(1 for v in found.values() if not v)}; "
          f"{aside} no-list-hit label{'s' * (aside != 1)} set aside")
    return [(part, str(r.get("label")), same[id(r)]) for part, group in zip(("dev", "test"), split(listed, args.seed))
            if args.split in (part, "all") for r in group if id(r) in same]


def _ollama(url: str, path: str, body: dict | None = None):
    request = urllib.request.Request(url + path, data=json.dumps(body).encode() if body else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=120) as response:
        return json.load(response)


def percentile(values: list, share: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))] if ordered else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    roots = paths.transcript_roots()
    parser.add_argument("--since", required=True)
    parser.add_argument("--claude", default=str(roots["claude-code"]))
    parser.add_argument("--codex", default=str(roots["codex"]))
    parser.add_argument("--muse", default=str(roots["muse"]))
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--url", default=judge.LOCAL_URL)
    parser.add_argument("--labels", default="")
    parser.add_argument("--split", choices=("dev", "test", "all"), default="all")
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--deadline", type=float, default=30.0, help="seconds a verdict may take here; past the hook's are counted")
    parser.add_argument("--cleared", default="")
    parser.add_argument("--measure-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        since = datetime.fromisoformat(args.since).timestamp()
        config = paths.config()
    except (ValueError, OSError) as exc:
        print(f"NOT REPLAYED: {exc}", file=sys.stderr)
        return 2
    extra, seen, items = list(config.get("shortcut_phrases", [])), set(), []
    for harness, root in (("claude-code", args.claude), ("codex", args.codex), ("muse", args.muse)):
        files = sorted(p for p in Path(root).rglob("*.jsonl") if p.is_file() and p.stat().st_mtime >= since) if Path(root).is_dir() else []
        ends = [(harness, str(path), *end) for path in files for end in turn_ends(READERS[harness](path, seen))]
        sent = [e for e in ends if e[4] and LABEL in e[4]]
        print(f"{harness}: {len(files)} records, {len(ends)} turn ends, {len(sent)} shortcut sendbacks, "
              f"{sum(bool(reply_check.shortcut_hits(e[3], extra)) for e in sent)} of them a list hit today")
        items += ends
    print(f"turn ends: {len(items)}; list hits, the replies the judge reads: {sum(bool(reply_check.shortcut_hits(e[3], extra)) for e in items)}")
    if args.measure_only:
        return 0
    try:
        jobs = labeled(args, items) if args.labels else [("sendbacks", "", e) for e in items if e[4] and LABEL in e[4]]
    except (OSError, ValueError) as exc:
        print(f"NOT REPLAYED: the labels could not be read ({exc})", file=sys.stderr)
        return 2
    jobs = [(part, label, e, reply_check.shortcut_hits(e[3], extra)) for part, label, e in jobs]
    hook, judge.LONGEST = judge.LONGEST, max(judge.LONGEST, args.deadline)  # slow verdicts are counted here, not cut
    policy = judge.load_policy("shortcut-phrasing")
    for model in args.model:
        try:
            loaded = any(m.get("name") == model for m in _ollama(args.url, "/api/ps").get("models", []))
        except (OSError, ValueError) as exc:
            print(f"NOT REPLAYED on {model}: the local model server did not answer ({exc})", file=sys.stderr)
            return 2
        settings = {**config, "judge": {"local": {"models": [model], "url": args.url, "keep_alive": "10m"}, "deadline_seconds": args.deadline}}
        times, cold, outcomes, cleared = [], None, [], []
        for part, label, entry, hits in jobs:
            harness, path, line, reply, _ = entry
            began = time.monotonic()
            found = reply_check.shortcut_verdict(reply, hits, settings) if hits else None  # both questions, as the hook asks
            took = int((time.monotonic() - began) * 1000)
            alone = judge.ask("shortcut-phrasing", policy, reply_check._judged(reply, hits), {"where": reply_check.WHERE,
                              "list_hits": hits}, settings) if found is not None else None  # the first reading, from its cache
            if found is not None and not found.cached:
                cold, times = (took, times) if cold is None and not loaded else (cold, times + [took])
            outcome, first = (("no verdict" if v is None else "held" if v.verdict == "hold" else "cleared" if v.sure else "passed unsure")
                              for v in (found, alone))
            outcomes.append((part, label, outcome, first))
            if outcome == "cleared":
                cleared.append({"harness": harness, "path": path, "line": line, "digest": hashlib.sha256(reply.encode()).hexdigest()[:16],
                                "model": model, "rule": found.rule, **({"label": label, "part": part} if label else {})})
        if not loaded:
            _ollama(args.url, "/api/generate", {"model": model, "keep_alive": 0})  # unload what this run loaded
        report(model, outcomes, bool(args.labels), args.split, times, cold, hook)
        if args.cleared:
            with open(args.cleared, "a", encoding="utf-8") as handle:
                handle.writelines(json.dumps(row) + "\n" for row in cleared)
    return 0


def report(model: str, outcomes: list, by_label: bool, part: str, times: list, cold, hook: float) -> None:
    """The counts of one model's run: by label for each part with a gate, or for the recorded sendbacks."""
    count = lambda rows, **want: sum(all(dict(zip(("part", "label", "outcome"), row))[k] == v for k, v in want.items()) for row in rows)
    p95 = percentile(times, 0.95)
    if not by_label:
        print(f"{model}: sendbacks {len(outcomes)}: confirmed {count(outcomes, outcome='held')}, cleared {count(outcomes, outcome='cleared')}, "
              f"passed unsure {count(outcomes, outcome='passed unsure')}, no verdict {count(outcomes, outcome='no verdict')}")
    for name in (["dev", "test", "all"] if part == "all" else [part]) if by_label else []:
        rows = [row for row in outcomes if name == "all" or row[0] == name]
        print(f"{model} {name} ({len(rows)}): " + ", ".join(f"{label} {count(rows, label=label, outcome='cleared')} of {count(rows, label=label)} cleared"
                                                          for label in ("shortcut", "unsure", "legitimate"))
              + f"; held {count(rows, outcome='held')}, passed unsure {count(rows, outcome='passed unsure')}, no verdict {count(rows, outcome='no verdict')}")
    if by_label:
        bad, good, legit = count(outcomes, label="shortcut", outcome="cleared"), count(outcomes, label="unsure", outcome="cleared"), count(outcomes, label="legitimate")
        fine = count(outcomes, label="legitimate", outcome="cleared")
        print(f"{model} {part}, the first question alone: " + ", ".join(f"{label} {count([r[:2] + r[3:] for r in outcomes], label=label, outcome='cleared')} "
                                                                           f"of {count(outcomes, label=label)} cleared" for label in ("shortcut", "unsure", "legitimate")))
        print(f"{model} gate on {len(outcomes)} list hits: real shortcuts cleared {bad}, unsure cleared {good}, legitimate cleared {fine} of "
              f"{legit} ({100 * fine // max(1, legit)}%); warm 95th {p95} ms against the {hook * 1000:.0f} ms deadline: "
              + ("PASSES" if outcomes and not bad and not good and p95 <= hook * 1000 else "FAILS"))
    print(f"{model}: latency ms: first {cold if cold is not None else 'n/a (already loaded)'}, median {percentile(times, 0.5)}, "
          f"95th {p95}, over {judge.DEADLINE:g} s {sum(t > judge.DEADLINE * 1000 for t in times)} of {len(times)}")


if __name__ == "__main__":
    sys.exit(main())
