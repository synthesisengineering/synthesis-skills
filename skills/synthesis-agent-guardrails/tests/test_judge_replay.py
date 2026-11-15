"""The judge replay: recorded shortcut sendbacks and sampled turn ends from all three harnesses, judged again, with
counts printed and each cleared sendback written as its record's path, line and digest, never its text.

Every record here is invented, and the model is a fake server on the loopback address.
"""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "judge_replay.py"
spec = importlib.util.spec_from_file_location("judge_replay", SCRIPT)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

SENT = "Before this reply goes out, revise it: lazy-shortcut phrasing: \"for now\". Do the work or name the real blocker."


class _Handler(BaseHTTPRequestHandler):
    def _answer(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._answer({"models": []})  # /api/ps: nothing loaded before the run

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        self.server.asked.append((self.path, body))
        if self.path == "/api/chat" and getattr(self.server, "missing", False):
            return self._answer({"error": "model not found"}, 404)
        verdict = {"verdict": "pass", "rule": "none", "span": "", "reason": "nothing is put off", "sure": True}
        if self.path == "/v1/messages":  # the cloud judge, as the provider answers
            self.server.keys.append(self.headers.get("x-api-key"))
            return self._answer({"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": json.dumps(verdict)}],
                                 "stop_reason": "end_turn", "usage": {"input_tokens": 2000, "output_tokens": 150}})
        self._answer({"message": {"role": "assistant", "content": json.dumps(verdict)}, "done": True}
                     if self.path == "/api/chat" else {"done": True})

    def log_message(self, *args):
        pass


@pytest.fixture
def model():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads, server.asked, server.keys = True, [], []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server, f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def _write(path: Path, rows: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _records(tmp_path: Path) -> dict:
    said = lambda uid, mid, text: {"type": "assistant", "uuid": uid, "message": {"id": mid, "content": [{"type": "text", "text": text}]}}
    _write(tmp_path / "claude" / "proj" / "one.jsonl", [
        {"type": "user", "uuid": "u1", "message": {"content": "Fix the parser."}},
        said("a1", "m1", "Parser fixed. I'll leave the importer for now."),
        {"type": "attachment", "uuid": "h1", "attachment": {"type": "hook_blocking_error", "blockingError": SENT}},
        said("a2", "m2", "Parser and importer fixed; the tests pass."),
        {"type": "user", "uuid": "u2", "message": {"content": "Now the exporter."}},
        {"type": "assistant", "uuid": "a3", "message": {"id": "m3", "content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]}},
        {"type": "user", "uuid": "u3", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
        said("a4", "m4", "The exporter is done. Happy to update the docs later if you want."),
    ])
    message = lambda role, text: {"type": "response_item", "payload": {"type": "message", "role": role,
                                                                       "content": [{"type": "output_text", "text": text}]}}
    _write(tmp_path / "codex" / "2026" / "rollout-one.jsonl", [
        message("user", "Tidy the config."), message("assistant", "Config tidied; the rest waits, for now."),
        message("user", SENT), message("assistant", "Config tidied throughout.")])
    _write(tmp_path / "muse" / "one.jsonl", [
        {"payload_type": "runtime.session", "payload": {"event": {"kind": "assistant_message_committed", "text": "All done."}}}])
    return {name: str(tmp_path / name) for name in ("claude", "codex", "muse")}


def _run(roots: dict, url: str, *more: str) -> int:
    return replay.main(["--since", "2000-01-01", "--claude", roots["claude"], "--codex", roots["codex"], "--muse", roots["muse"],
                        "--url", url, *more])


def test_the_replay_judges_the_list_hits_and_writes_where_to_read_never_what_was_written(tmp_path, model, capsys):
    server, url = model
    roots, cleared = _records(tmp_path), tmp_path / "cleared.jsonl"
    assert _run(roots, url, "--model", "small-judge", "--cleared", str(cleared), "--deadline", "5") == 0
    out = capsys.readouterr().out
    assert "claude-code: 1 records, 3 turn ends, 1 shortcut sendbacks, 1 of them a list hit today" in out
    assert "codex: 1 records, 2 turn ends, 1 shortcut sendbacks, 1 of them a list hit today" in out
    assert "muse: 1 records, 1 turn ends, 0 shortcut sendbacks" in out
    assert "turn ends: 6; list hits, the replies the judge reads: 2" in out
    assert "small-judge: sendbacks 2: confirmed 0, cleared 2, passed unsure 0, no verdict 0" in out
    rows = [json.loads(line) for line in cleared.read_text(encoding="utf-8").splitlines()]
    assert sorted((r["harness"], r["line"]) for r in rows) == [("claude-code", 2), ("codex", 2)]
    assert all(set(r) == {"harness", "path", "line", "digest", "model", "rule"} for r in rows)
    for words in ("importer", "exporter", "Config", "parser"):
        assert words not in out and words not in cleared.read_text(encoding="utf-8")
    assert [path for path, _ in server.asked].count("/api/chat") == 4  # two questions each; no list hit, never asked
    asked = [body["messages"][1]["content"] for path, body in server.asked if path == "/api/chat"]
    assert sum("Fix the parser." in u for u in asked) == 2 and not any("Tidy the config." in u for u in asked)  # as the hook reads
    assert "small-judge: latency ms: the first question alone" in out and "; both questions, median" in out
    assert server.asked[-1] == ("/api/generate", {"model": "small-judge", "keep_alive": 0})  # unloaded at the end


def test_measuring_alone_asks_no_model(tmp_path, model, capsys):
    server, url = model
    assert _run(_records(tmp_path), url, "--measure-only") == 0
    assert "turn ends: 6; list hits, the replies the judge reads: 2" in capsys.readouterr().out and server.asked == []


def test_labels_give_a_matrix_by_label_and_the_gate(tmp_path, model, capsys):
    """A labeled item is found by its record's path and line and judged only when its digest still matches; the
    matrix counts, by label, what the judge cleared (a sure pass), and the gate fails on any real shortcut or unsure
    item cleared."""
    import hashlib
    server, url = model
    roots, labels = _records(tmp_path), tmp_path / "labels.jsonl"
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()[:16]
    claude, codex = str(Path(roots["claude"]) / "proj" / "one.jsonl"), str(Path(roots["codex"]) / "2026" / "rollout-one.jsonl")
    _write(labels, [
        {"path": claude, "line": 2, "digest": digest("Parser fixed. I'll leave the importer for now."), "source": "list-hit",
         "label": "shortcut", "category": "deferral", "reason": "r"},
        {"path": codex, "line": 2, "digest": digest("Config tidied; the rest waits, for now."), "source": "list-hit",
         "label": "legitimate", "category": "other", "reason": "r"},
        {"path": claude, "line": 4, "digest": "0" * 16, "source": "list-hit", "label": "legitimate", "category": "other", "reason": "r"},
        {"path": claude, "line": 8, "digest": "1" * 16, "source": "no-list-hit", "label": "shortcut", "category": "other", "reason": "r"},
    ])
    assert _run(roots, url, "--model", "small-judge", "--labels", str(labels), "--split", "all", "--deadline", "5") == 0
    out = capsys.readouterr().out
    assert "labels: 3 list hits (legitimate 2, shortcut 1); found 2, digest changed 1, not found 0; 1 no-list-hit label set aside" in out
    assert "small-judge all (2): shortcut 1 of 1 cleared, unsure 0 of 0 cleared, legitimate 1 of 1 cleared; held 0, passed unsure 0, no verdict 0" in out
    assert "small-judge gate on 2 list hits: real shortcuts cleared 1, unsure cleared 0, legitimate cleared 1 of 1 (100%)" in out
    assert "FAILS" in out.split("small-judge gate on")[1].splitlines()[0]
    assert "small-judge all, the first question alone: shortcut 1 of 1 cleared, unsure 0 of 0 cleared, legitimate 1 of 1 cleared" in out
    assert [path for path, _ in server.asked].count("/api/chat") == 4


def test_the_split_is_stratified_by_label_with_a_fixed_seed():
    rows = [{"path": "p", "line": n, "digest": f"{n:016x}", "label": label}
            for n, label in enumerate(["shortcut"] * 7 + ["unsure"] * 3 + ["legitimate"] * 60)]
    dev, test = replay.split(rows, 20261114)
    count = lambda part, label: sum(r["label"] == label for r in part)
    assert [count(dev, k) for k in ("shortcut", "unsure", "legitimate")] == [4, 2, 30]
    assert [count(test, k) for k in ("shortcut", "unsure", "legitimate")] == [3, 1, 30]
    assert not {r["line"] for r in dev} & {r["line"] for r in test} and replay.split(rows, 20261114) == (dev, test)


def test_an_item_with_no_verdict_is_counted_and_never_cleared(tmp_path, model, capsys):
    server, url = model
    server.missing, cleared = True, tmp_path / "cleared.jsonl"  # the model is not installed: no verdict
    assert _run(_records(tmp_path), url, "--model", "small-judge", "--cleared", str(cleared)) == 0
    assert "small-judge: sendbacks 2: confirmed 0, cleared 0, passed unsure 0, no verdict 2" in capsys.readouterr().out
    assert not cleared.exists() or cleared.read_text(encoding="utf-8") == ""


def test_a_second_run_in_the_same_process_gates_against_the_hooks_deadline(tmp_path, model, capsys):
    """A run lets slow verdicts finish and counts them; the deadline it raises for that is put back after it, so a second
    run in the same process (one model after another) still gates against the hook's own deadline (2026-11-15)."""
    import hashlib
    server, url = model
    roots, labels = _records(tmp_path), tmp_path / "labels.jsonl"
    claude = str(Path(roots["claude"]) / "proj" / "one.jsonl")
    _write(labels, [{"path": claude, "line": 2, "digest": hashlib.sha256(b"Parser fixed. I'll leave the importer for now.").hexdigest()[:16],
                     "source": "list-hit", "label": "legitimate", "category": "other", "reason": "r"}])
    for _ in range(2):
        assert _run(roots, url, "--model", "small-judge", "--labels", str(labels), "--deadline", "30") == 0
    gates = [line for line in capsys.readouterr().out.splitlines() if " gate on " in line]
    assert len(gates) == 4 and all("against the 3500 ms deadline" in line for line in gates)


def test_the_cloud_replay_reads_each_workspaces_key_and_leaves_out_a_workspace_with_none(tmp_path, model, monkeypatch, capsys):
    """The cloud judge's measurement (the principal's ruling of 2026-11-15): each labeled hit judged with the key of its
    record's workspace, a workspace whose key is not confirmed left out and counted, tokens and dollars reported, and
    no key's value anywhere in what it prints or files."""
    import hashlib
    server, url = model
    monkeypatch.setenv("HOME", str(tmp_path))
    keys = tmp_path / "keys.yaml"
    keys.write_text("default:\n  anthropic: test-key-default-1111\nworkspaces:\n  heldback:\n    anthropic: test-key-held-3333\n")
    rows, labels = [], []
    for name in ("personal", "heldback"):
        cwd = str(tmp_path / "workspaces" / name / "project")
        reply = f"The {name} parser is fixed. I'll leave the importer for now."
        record = _write(tmp_path / "claude" / name / "one.jsonl", [
            {"type": "user", "uuid": f"{name}-u", "cwd": cwd, "message": {"content": "Convert the parser."}},
            {"type": "assistant", "uuid": f"{name}-a", "cwd": cwd, "message": {"id": f"{name}-m", "content": [{"type": "text", "text": reply}]}}])
        labels.append({"path": str(record), "line": 2, "digest": hashlib.sha256(reply.encode()).hexdigest()[:16], "source": "list-hit",
                       "label": "legitimate", "category": "other", "reason": "r"})
    _write(tmp_path / "labels.jsonl", labels)
    cleared = tmp_path / "cleared.jsonl"
    assert replay.main(["--since", "2000-01-01", "--claude", str(tmp_path / "claude"), "--codex", str(tmp_path / "none"), "--muse",
                        str(tmp_path / "none"), "--cloud", "cloud-judge", "--cloud-url", url + "/v1/messages", "--keys-file", str(keys),
                        "--keys", json.dumps({"default": "default.anthropic", "heldback": None}), "--price", "4,20", "--effort", "low",
                        "--labels", str(tmp_path / "labels.jsonl"), "--limit", "8", "--cleared", str(cleared)]) == 0
    out = capsys.readouterr().out
    import re
    left = re.search(r"left out, their workspace's key not confirmed: 1 \(dev (\d), test (\d)\)", out)
    assert left and int(left.group(1)) + int(left.group(2)) == 1  # whichever half the seed put it in
    assert "cloud-judge all (1): shortcut 0 of 0 cleared, unsure 0 of 0 cleared, legitimate 1 of 1 cleared" in out
    assert "cloud-judge: cloud tokens in 4000, out 300; dollars 0.0220" in out  # both questions of the one item judged
    assert "against the 8000 ms limit" in out
    assert server.keys == ["test-key-default-1111"] * 2  # the personal item's two questions, with the default key
    for secret in ("test-key-default-1111", "test-key-held-3333"):
        assert secret not in out and secret not in cleared.read_text(encoding="utf-8")


FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys
sys.stdin.read()
with open(os.environ["FAKE_LOG"], "a") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "marker": os.environ.get("SYNTHESIS_JUDGE_RUN")}) + "\\n")
verdict = {"verdict": "pass", "rule": "none", "span": "", "reason": "nothing is put off", "sure": True}
if sys.argv[1:2] == ["exec"]:  # codex: the last message to the file -o names
    open(sys.argv[sys.argv.index("-o") + 1], "w").write(json.dumps(verdict))
else:
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(verdict), "structured_output": verdict}))
"""


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
def test_the_subscription_replay_runs_the_harness_command_and_leaves_out_a_workspace(tmp_path, monkeypatch, capsys, harness):
    """The judge on the person's own subscription (2026-11-15): each labeled hit judged through the command line of the
    plan --harness names, whichever harness recorded it (the 33 personal items were all recorded in Claude Code, and
    Codex's plan was measured on them), both questions at once, a workspace set aside left out and counted."""
    import hashlib
    monkeypatch.setenv("HOME", str(tmp_path))
    fake = tmp_path / "fake-claude"
    fake.write_text(FAKE_CLAUDE, encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "runs.jsonl"))
    labels = []
    for name in ("personal", "heldback"):
        cwd = str(tmp_path / "workspaces" / name / "project")
        reply = f"The {name} parser is fixed. I'll leave the importer for now."
        record = _write(tmp_path / "claude" / name / "one.jsonl", [
            {"type": "user", "uuid": f"{name}-u", "cwd": cwd, "message": {"content": "Convert the parser."}},
            {"type": "assistant", "uuid": f"{name}-a", "cwd": cwd, "message": {"id": f"{name}-m", "content": [{"type": "text", "text": reply}]}}])
        labels.append({"path": str(record), "line": 2, "digest": hashlib.sha256(reply.encode()).hexdigest()[:16], "source": "list-hit",
                       "label": "legitimate", "category": "other", "reason": "r"})
    _write(tmp_path / "labels.jsonl", labels)
    assert replay.main(["--since", "2000-01-01", "--claude", str(tmp_path / "claude"), "--codex", str(tmp_path / "none"), "--muse",
                        str(tmp_path / "none"), "--subscription", "small-model", "--harness", harness, "--command", str(fake), "--effort", "low",
                        "--leave-out", "heldback", "--labels", str(tmp_path / "labels.jsonl"), "--limit", "8"]) == 0
    out = capsys.readouterr().out
    import re
    left = re.search(r"left out by --leave-out: 1 \(dev (\d), test (\d)\)", out)
    assert left and int(left.group(1)) + int(left.group(2)) == 1
    assert "small-model all (1): shortcut 0 of 0 cleared, unsure 0 of 0 cleared, legitimate 1 of 1 cleared" in out
    assert "both questions at once" in out and "against the 8000 ms limit" in out
    runs = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert len(runs) == 2 and all(r["marker"] == "1" and r["argv"][0] == {"claude-code": "-p", "codex": "exec"}[harness] for r in runs)
