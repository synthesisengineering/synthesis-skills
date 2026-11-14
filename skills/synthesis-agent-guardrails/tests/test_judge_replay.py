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
    def _answer(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._answer({"models": []})  # /api/ps: nothing loaded before the run

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        self.server.asked.append((self.path, body))
        verdict = {"verdict": "pass", "rule": "none", "span": "", "reason": "nothing is put off", "sure": True}
        self._answer({"message": {"role": "assistant", "content": json.dumps(verdict)}, "done": True}
                     if self.path == "/api/chat" else {"done": True})

    def log_message(self, *args):
        pass


@pytest.fixture
def model():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads, server.asked = True, []
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


def test_the_replay_counts_judges_and_writes_where_to_read_never_what_was_written(tmp_path, model, capsys):
    server, url = model
    roots, cleared = _records(tmp_path), tmp_path / "cleared.jsonl"
    code = replay.main(["--since", "2000-01-01", "--claude", roots["claude"], "--codex", roots["codex"], "--muse", roots["muse"],
                        "--model", "small-judge", "--url", url, "--sample", "10", "--cleared", str(cleared), "--deadline", "5"])
    out = capsys.readouterr().out
    assert code == 0
    assert "claude-code: 1 records, 3 turn ends, 1 shortcut sendbacks, 1 of them a list hit today" in out
    assert "codex: 1 records, 2 turn ends, 1 shortcut sendbacks, 1 of them a list hit today" in out
    assert "muse: 1 records, 1 turn ends, 0 shortcut sendbacks" in out
    assert "small-judge: sampled pass: pass 1, sendback: pass 2" in out  # the exporter reply reaches it by its words
    rows = [json.loads(line) for line in cleared.read_text(encoding="utf-8").splitlines()]
    assert sorted((r["harness"], r["line"]) for r in rows) == [("claude-code", 2), ("codex", 2)]
    assert all(set(r) == {"harness", "path", "line", "digest", "model", "rule"} for r in rows)
    for words in ("importer", "exporter", "Config", "parser"):
        assert words not in out and words not in cleared.read_text(encoding="utf-8")
    assert [path for path, _ in server.asked].count("/api/chat") == 3
    assert server.asked[-1] == ("/api/generate", {"model": "small-judge", "keep_alive": 0})  # unloaded at the end


def test_measuring_alone_asks_no_model(tmp_path, model, capsys):
    server, url = model
    roots = _records(tmp_path)
    assert replay.main(["--since", "2000-01-01", "--claude", roots["claude"], "--codex", roots["codex"], "--muse", roots["muse"],
                        "--url", url, "--measure-only"]) == 0
    out = capsys.readouterr().out
    assert "turn ends: 6; would reach the judge: 3" in out and server.asked == []
