#!/usr/bin/env python3
"""Replay the turn-end shortcut check's judge over recorded turn ends, before its model or policy changes ship.

    judge_replay.py --since YYYY-MM-DD [--claude DIR] [--codex DIR] [--muse DIR] [--model NAME]...
                    [--sample N] [--seed N] [--deadline SECONDS] [--cleared FILE] [--held FILE] [--measure-only]

Reads the harnesses' session records changed since the date (Claude Code's projects folder, Codex's sessions folder,
Muse's sessions folder; each defaults to where the harness keeps it) and finds every turn end: an agent's last reply
before the next prompt, with no tool call after it. A turn end the reply check sent back for shortcut phrasing is a
recorded sendback: Claude Code records the hook's words beside the reply; in Codex and Muse they arrive as the next
prompt. It counts how many turn ends would reach the judge (a hit of the list, the built-in phrases and the config's
`shortcut_phrases`, or candidate words), then, for each model named, judges every recorded sendback and a seeded
random sample of the turn ends that passed: list hits confirmed and cleared, passes newly held, no verdict and why,
and the latency (the first verdict of a model not yet loaded, then the median and 95th percentile of the rest).

Uses the runtime beside it and the synthesis config of SYNTHESIS_HOME (point it at a copy), with the judge section
replaced by each model in turn; the verdicts are cached and logged in that home. A model it loaded is unloaded at the
end (keep_alive 0). Prints counts, dates and fixed words only, never a record's text. --cleared and --held name files
for each cleared sendback and each newly held pass: its record's path, line and digest, never its text, so a person
can read each one in its record. Exit 0 when it ran, 2 when it could not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
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


def alternatives(pattern: str) -> list:
    """The top-level alternatives of the candidate pattern's group, for counting which words bring turn ends in."""
    body, out, depth, start = pattern[pattern.index("(?:") + 3:pattern.rindex(")")], [], 0, 0
    for at, char in enumerate(body):
        depth += (char == "(") - (char == ")") if body[at - 1:at] != "\\" else 0
        if char == "|" and depth == 0:
            out, start = out + [body[start:at]], at + 1
    return [re.compile(rf"(?i)\b(?:{alt})\b") for alt in out + [body[start:]]]


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
    parser.add_argument("--sample", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--deadline", type=float, default=30.0, help="seconds a verdict may take here; past the hook's are counted")
    parser.add_argument("--cleared", default="")
    parser.add_argument("--held", default="")
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
    plain = lambda text: reply_check.QUOTED.sub(" ", reply_check.CODE.sub(" ", text))
    hit = {id(e): reply_check.shortcut_hits(e[3], extra) for e in items}
    candidate = {id(e): bool(reply_check.CANDIDATE.search(plain(e[3]))) for e in items}
    reach = [e for e in items if hit[id(e)] or candidate[id(e)]]
    reached = {id(e) for e in reach}
    print(f"turn ends: {len(items)}; would reach the judge: {len(reach)} ({100 * len(reach) / max(1, len(items)):.1f}%), "
          f"{sum(bool(hit[id(e)]) for e in items)} by a list hit, {sum(candidate[id(e)] and not hit[id(e)] for e in items)} by candidate words alone")
    terms = alternatives(reply_check.CANDIDATE.pattern)
    counted = sorted(((sum(bool(t.search(plain(e[3]))) for e in items), t.pattern[9:-3]) for t in terms), reverse=True)
    print("candidate words, turn ends each brings in: " + "; ".join(f"{word} {n}" for n, word in counted if n))
    if args.measure_only:
        return 0
    sendbacks = [e for e in items if e[4] and LABEL in e[4] and hit[id(e)]]
    passes = [e for e in items if not e[4]]
    sample = random.Random(args.seed).sample(passes, min(args.sample, len(passes)))
    print(f"sample: {len(sample)} of {len(passes)} turn ends that passed; {sum(id(e) in reached for e in sample)} reach the judge")
    policy, judge.LONGEST = judge.load_policy("shortcut-phrasing"), max(judge.LONGEST, args.deadline)  # slow verdicts are counted, not cut
    for model in args.model:
        try:
            loaded = any(m.get("name") == model for m in _ollama(args.url, "/api/ps").get("models", []))
        except (OSError, ValueError) as exc:
            print(f"NOT REPLAYED on {model}: the local model server did not answer ({exc})", file=sys.stderr)
            return 2
        settings = {**config, "judge": {"local": {"models": [model], "url": args.url, "keep_alive": "10m"}, "deadline_seconds": args.deadline}}
        tally, times, cold, slow, cleared, held, by_word = {}, [], None, 0, [], [], {}
        for group, chosen in (("sendback", sendbacks), ("sampled pass", [e for e in sample if id(e) in reached])):
            for entry in chosen:
                harness, path, line, reply, _ = entry
                began = time.monotonic()
                found = judge.ask("shortcut-phrasing", policy, reply_check._judged(reply, hit[id(entry)]),
                                  {"where": "the final reply an AI agent gives its principal at the end of a turn",
                                   "list_hits": hit[id(entry)]}, settings)
                took = int((time.monotonic() - began) * 1000)
                if found is not None and not found.cached:
                    cold, times = (took, times) if cold is None and not loaded else (cold, times + [took])
                    slow += took > judge.DEADLINE * 1000
                verdict = "no verdict" if found is None else found.verdict
                tally[f"{group}: {verdict}"] = tally.get(f"{group}: {verdict}", 0) + 1
                record = {"harness": harness, "path": path, "line": line, "digest": hashlib.sha256(reply.encode()).hexdigest()[:16],
                          "model": model, "rule": found.rule if found else ""}
                cleared += [record] if group == "sendback" and verdict == "pass" else []
                held += [record] if group == "sampled pass" and verdict == "hold" else []
                for t in terms if group == "sampled pass" and not hit[id(entry)] else ():  # which words brought in what it held
                    if t.search(plain(reply)):
                        key = f"{t.pattern[9:-3]} ({verdict})"
                        by_word[key] = by_word.get(key, 0) + 1
        if not loaded:
            _ollama(args.url, "/api/generate", {"model": model, "keep_alive": 0})  # unload what this run loaded
        print(f"{model}: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
        print(f"{model}: latency ms: first {cold if cold is not None else 'n/a (already loaded)'}, median {percentile(times, 0.5)}, "
              f"95th {percentile(times, 0.95)}, over {judge.DEADLINE:g} s {slow} of {len(times) + (cold is not None)}")
        print(f"{model}: candidate words of sampled passes, by verdict: " + "; ".join(f"{k} {v}" for k, v in sorted(by_word.items())))
        for name, rows in ((args.cleared, cleared), (args.held, held)):
            if name:
                with open(name, "a", encoding="utf-8") as handle:
                    handle.writelines(json.dumps(row) + "\n" for row in rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
