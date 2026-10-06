# SPDX-License-Identifier: Apache-2.0
"""The guarded iMessage send (R3.1, E84). The real fixed JXA programs run under a Node double of
the Messages scripting bridge: synthetic accounts and chats only, nothing reaches Messages."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess

import pytest

import messages_send as ms

NODE = shutil.which("node")
DEST = "+15551234567"
TEXT = "Review \"quoted\" text.\n\nSecond paragraph: 'single' \\ path. 😀"
FIXTURE = r"""
const fs = require('fs'), vm = require('vm');
const source = Buffer.from(process.argv[1], 'base64').toString('utf8');
const args = JSON.parse(process.argv[2]), world = JSON.parse(process.argv[3]);
const mode = world.mode, dest = world.destination;
const person = (id, handle, acct) => ({id: () => id, handle: () => handle, account: () => acct});
const chat = (id, acct, people) => ({id: () => id, account: () => acct, participants: () => people});
function account(id, service, connected) {
  const a = {id: () => id, enabled: () => true, serviceType: () => service, list: [],
             connectionStatus: () => connected ? 'connected' : 'disconnected'};
  a.chats = () => a.list;
  return a;
}
const a = account('account-a', mode === 'sms' ? 'SMS' : 'iMessage', mode !== 'offline');
if (mode !== 'none') a.list.push(chat('chat-1', a, [person('participant-1', dest, a)]));
a.list.push(chat('chat-group', a, [person('p-2', dest, a), person('p-3', '+15550000003', a)]));
a.list.push(chat('chat-other', a, [person('p-4', '+15550000004', a)]));
const accounts = [a];
if (mode === 'two-accounts') {
  const b = account('account-b', 'iMessage', true);
  b.list.push(chat('chat-b', b, [person('participant-b', dest, b)]));
  accounts.push(b);
}
const context = {ObjC: {import: () => {}, unwrap: x => x}, $: {NSUTF8StringEncoding: 4,
  NSFileHandle: {alloc: {initWithFileDescriptor: fd => ({get readDataToEndOfFile() { return fs.readFileSync(fd, 'utf8'); }})}},
  NSString: {alloc: {initWithDataEncoding: x => x}}},
  Application: name => { if (name !== 'Messages') throw Error('unexpected app'); return {accounts: () => accounts,
    send: (text, options) => {
      fs.appendFileSync(world.calls, JSON.stringify({text, chat: options.to.id()}) + '\n');
      if (mode === 'lost') throw Error('lost after effect');
      if (mode === 'process-loss') process.exit(23);
    }}; }};
try {
  vm.createContext(context);
  vm.runInContext(source, context, {timeout: 1000});
  process.stdout.write(String(context.run(args)));
} catch (error) {
  process.stderr.write('execution error: Error: ' + error.message + ' (-2700)\n');
  process.exit(1);
}
"""


class FakeMessages:
    """Stands in for /usr/bin/osascript: runs the real script source under the Node double."""

    def __init__(self, tmp_path: Path, route="one", transport="ok"):
        self.route, self.transport = route, transport
        self.calls_file = tmp_path / "send-calls.jsonl"
        self.invocations, self.packets = [], []

    def __call__(self, script: Path, args: list, fd=None):
        self.invocations.append((script.name, list(args)))
        mode = self.route if script.name == "messages_route.js" else self.transport
        if fd is not None:
            self.packets.append(os.pread(fd, 1 << 20, 0).decode("utf-8"))
        if mode == "timeout":
            return None
        world = {"mode": mode, "destination": DEST, "calls": str(self.calls_file)}
        return subprocess.run([NODE, "-e", FIXTURE, base64.b64encode(script.read_bytes()).decode(), json.dumps(args),
                               json.dumps(world)], capture_output=True, text=True, timeout=30,
                              pass_fds=(fd,) if fd is not None else ())

    @property
    def sends(self) -> list:
        if not self.calls_file.exists():
            return []
        return [json.loads(line) for line in self.calls_file.read_text().splitlines()]


@pytest.fixture
def messages(tmp_path, monkeypatch):
    if not NODE:
        pytest.skip("node is needed to run the fixed JXA programs under the Messages double")
    fake = FakeMessages(tmp_path)
    monkeypatch.setattr(ms, "osascript", fake)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))  # the session's transcript lives here
    monkeypatch.setenv("SYNTHESIS_SESSION", "S-imessage")
    return fake


def approve(result: dict) -> None:
    """The principal types the code; the harness records it in the session's transcript, and the prompt hook
    grants it. The guard uses a grant only when that transcript shows the principal's own prompt."""
    assert result["status"] == "needs-approval", result
    code = re.search(r"\bcode ([a-z0-9]{6})", result["reason"]).group(1)
    record = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "-work" / "S-imessage.jsonl"
    record.parent.mkdir(parents=True, exist_ok=True)
    when = (datetime.now(timezone.utc) + timedelta(milliseconds=1)).isoformat()
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "user", "timestamp": when, "message": {"role": "user",
                                                                                "content": f"please approve {code}"}}) + "\n")
    from synthesis import approvals
    assert approvals.grant_from_prompt(f"please approve {code}")


def pending_requests() -> list:
    _, paths = ms.core()
    folder = paths.state() / "approval-requests"
    return list(folder.glob("*.json")) if folder.is_dir() else []


def test_send_waits_for_exact_approval_then_sends_once(messages):
    first = ms.send(DEST, TEXT)
    assert messages.sends == [] and "approve" in first["reason"]
    approve(first)
    result = ms.send(DEST, TEXT)
    assert result == {"status": "dispatched", "delivery": "unknown", "acknowledgement": "unknown"}
    assert messages.sends == [{"text": TEXT, "chat": "chat-1"}]
    with pytest.raises(ms.Refused, match="Never resend"):
        ms.send(DEST, TEXT)
    assert len(messages.sends) == 1


def test_approval_covers_only_the_exact_text_and_recipient(messages):
    approve(ms.send(DEST, TEXT))
    assert ms.send(DEST, TEXT + " ")["status"] == "needs-approval"  # one extra space is another message
    assert messages.sends == []


def test_text_travels_by_private_descriptor_never_by_argv(messages):
    approve(ms.send(DEST, TEXT))
    ms.send(DEST, TEXT)
    name, args = messages.invocations[-1]
    assert name == "messages_transport.js" and len(args) == 1 and args[0].isdigit()
    assert all(TEXT not in " ".join(a) for _, a in messages.invocations)
    assert json.loads(messages.packets[-1])["payload"]["tool_input"]["text"] == TEXT


@pytest.mark.parametrize("mode", ["lost", "process-loss", "timeout"])
def test_e84_an_uncertain_outcome_is_never_resent(messages, mode):
    messages.transport = mode
    approve(ms.send(DEST, TEXT))
    result = ms.send(DEST, TEXT)
    assert result["status"] == "uncertain"
    sent = len(messages.sends)
    with pytest.raises(ms.Refused, match="ended uncertain"):
        ms.send(DEST, TEXT)  # refused before any approval is asked for or spent
    assert len(messages.sends) == sent and pending_requests() == []


def test_e84_a_matching_outbound_row_does_not_turn_uncertain_into_sent(messages, tmp_path):
    messages.transport = "lost"
    approve(ms.send(DEST, TEXT))
    assert ms.send(DEST, TEXT)["status"] == "uncertain"
    # A row with the same text in the Messages database could be the principal's own send.
    db = sqlite3.connect(tmp_path / "chat.db")
    db.execute("create table message(text text, is_from_me integer, is_sent integer, error integer)")
    db.execute("insert into message values(?, 1, 1, 0)", (TEXT,))
    db.commit()
    db.close()
    with pytest.raises(ms.Refused, match="ended uncertain"):
        ms.send(DEST, TEXT)
    _, paths = ms.core()
    record = json.loads(next((paths.state() / "imessage-sends").glob("*.json")).read_text())
    assert record["status"] == "uncertain" and TEXT not in json.dumps(record)


def test_a_refusal_before_the_send_call_is_not_sent_and_may_be_retried(messages):
    messages.transport = "offline"  # the account went offline between route and send
    approve(ms.send(DEST, TEXT))
    result = ms.send(DEST, TEXT)
    assert result["status"] == "not-sent" and "account unavailable" in result["reason"]
    assert messages.sends == []
    messages.transport = "ok"
    again = ms.send(DEST, TEXT)  # the spent approval does not carry over
    approve(again)
    assert ms.send(DEST, TEXT)["status"] == "dispatched"


@pytest.mark.parametrize("route,reason", [("none", "no existing one-to-one"), ("sms", "no existing one-to-one"),
                                          ("offline", "no existing one-to-one"), ("two-accounts", "--account")])
def test_no_unique_existing_chat_refuses_before_any_approval(messages, route, reason):
    messages.route = route
    with pytest.raises(ms.Refused, match=reason):
        ms.send(DEST, TEXT)
    assert pending_requests() == [] and messages.sends == []


def test_account_flag_picks_one_of_two_accounts(messages):
    messages.route = "two-accounts"
    approve(ms.send(DEST, TEXT, account="account-a"))
    assert ms.send(DEST, TEXT, account="account-a")["status"] == "dispatched"


def test_forbidden_phrases_block_before_approval_and_bad_config_blocks_everything(messages, monkeypatch):
    _, paths = ms.core()
    paths.config_file().parent.mkdir(parents=True, exist_ok=True)
    paths.config_file().write_text(json.dumps({"forbidden_phrases": [{"name": "no hype", "pattern": "game-changing"}]}))
    result = ms.send(DEST, "This is game-changing.")
    assert result["status"] == "refused" and "no hype" in result["reason"] and pending_requests() == []
    paths.config_file().write_text("{not json")
    with pytest.raises(ms.Refused, match="unreadable"):
        ms.send(DEST, TEXT)
    assert messages.sends == []


@pytest.mark.parametrize("to,text", [("5551234567", TEXT), ("someone", TEXT), (DEST, "   "), (DEST, "a\0b")])
def test_malformed_recipient_or_text_refuses(messages, to, text):
    with pytest.raises(ms.Refused):
        ms.send(to, text)
    assert messages.invocations == []


def test_command_line_exit_codes(messages, tmp_path, capsys):
    text_file = tmp_path / "text.txt"
    text_file.write_text(TEXT, encoding="utf-8")
    assert ms.main(["--to", DEST, "--text-file", str(text_file)]) == 2
    approve(json.loads(capsys.readouterr().out))
    assert ms.main(["--to", DEST, "--text-file", str(text_file)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dispatched"
    assert ms.main(["--to", DEST, "--text-file", str(text_file)]) == 2
