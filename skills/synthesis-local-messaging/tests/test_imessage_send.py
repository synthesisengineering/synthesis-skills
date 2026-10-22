# SPDX-License-Identifier: Apache-2.0
"""The guarded iMessage send (R3.1, E84). The real fixed JXA programs run under a Node double of
the Messages scripting bridge: synthetic accounts and chats only, nothing reaches Messages."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

from local_messaging_fixtures import approve as principal_approves
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
if (mode === 'opaque') {  // Messages can list an account whose service type it cannot report (-10000)
  accounts.unshift({id: () => 'account-x', enabled: () => true, connectionStatus: () => 'connected', chats: () => [],
                    serviceType: () => { throw Error('AppleEvent handler failed.'); }});
}
if (mode === 'two-accounts') {
  const b = account('account-b', 'iMessage', true);
  b.list.push(chat('chat-b', b, [person('participant-b', dest, b)]));
  accounts.push(b);
}
if (mode === 'both-services') {  // the same two people in an iMessage group and an SMS group
  const b = account('account-b', 'SMS', true);
  b.list.push(chat('chat-sms-group', b, [person('p-6', dest, b), person('p-7', '+15550000003', b)]));
  accounts.push(b);
}
if (mode === 'group-changed') {  // someone joined the group after the approval
  a.list[a.list.findIndex(c => c.id() === 'chat-group')] = chat('chat-group', a,
    [person('p-2', dest, a), person('p-3', '+15550000003', a), person('p-5', '+15550000005', a)]);
}
const stat = p => { try { return fs.statSync(p, {bigint: true}); } catch (e) { return null; } };
const context = {ObjC: {import: () => {}, unwrap: x => x}, $: {NSUTF8StringEncoding: 4,
  NSFileHandle: {alloc: {initWithFileDescriptor: fd => ({get readDataToEndOfFile() { return fs.readFileSync(fd, 'utf8'); }})}},
  NSString: {alloc: {initWithDataEncoding: x => x}},
  NSFileManager: {defaultManager: {attributesOfItemAtPathError: p => { const st = stat(p); return st && {objectForKey: k =>
    k === 'NSFileSize' ? Number(st.size) : {timeIntervalSince1970: Number(st.mtimeNs) / 1e9}}; }}}},
  Path: p => ({path: p}),
  Application: name => { if (name !== 'com.apple.MobileSMS') throw Error('unexpected app'); return {accounts: () => accounts,
    send: (item, options) => {
      const part = typeof item === 'string' ? {text: item} : {photo: item.path};
      fs.appendFileSync(world.calls, JSON.stringify({...part, chat: options.to.id()}) + '\n');
      if (mode === 'lost') throw Error('lost after effect');
      if (mode === 'process-loss') process.exit(23);
      if (mode === 'caption-fails' && typeof item === 'string') throw Error('caption lost');
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
    principal_approves(result["reason"])


def pending_requests() -> list:
    _, paths = ms.core()
    folder = paths.state() / "approval-requests"
    return list(folder.glob("*.json")) if folder.is_dir() else []


def test_send_waits_for_exact_approval_then_sends_once(messages):
    first = ms.send(DEST, TEXT)
    assert messages.sends == [] and "approve" in first["reason"]
    approve(first)
    result = ms.send(DEST, TEXT)
    assert result == {"status": "dispatched", "parts": ["text"], "delivery": "unknown", "acknowledgement": "unknown"}
    assert messages.sends == [{"text": TEXT, "chat": "chat-1"}]
    with pytest.raises(ms.Refused, match="Never resend"):
        ms.send(DEST, TEXT)
    assert len(messages.sends) == 1


def test_an_account_without_a_readable_service_type_is_skipped(messages):
    messages.route = messages.transport = "opaque"
    approve(ms.send(DEST, TEXT))
    assert ms.send(DEST, TEXT)["status"] == "dispatched"
    assert messages.sends == [{"text": TEXT, "chat": "chat-1"}]


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


# --- members: an existing group or SMS chat, named by exactly its members (2026-10-20) --------------------------

P3 = "+15550000003"


def test_members_reach_the_existing_group_once_and_the_approval_names_everyone(messages):
    first = ms.send_members([P3, DEST], TEXT)
    assert messages.sends == [] and first["status"] == "needs-approval"
    summary = json.loads(pending_requests()[0].read_text())["summary"]
    assert DEST in summary and P3 in summary and "iMessage" in summary
    approve(first)
    assert ms.send_members([DEST, P3], TEXT)["status"] == "dispatched"  # the order of members never matters
    assert messages.sends == [{"text": TEXT, "chat": "chat-group"}]
    with pytest.raises(ms.Refused, match="Never resend"):
        ms.send_members([DEST, P3], TEXT)


def test_members_reach_an_sms_chat_and_never_an_imessage_one(messages):
    messages.route = messages.transport = "sms"
    approve(ms.send_members([DEST], TEXT))
    assert ms.send_members([DEST], TEXT)["status"] == "dispatched"
    assert messages.sends == [{"text": TEXT, "chat": "chat-1"}]
    assert json.loads(messages.packets[-1])["payload"]["tool_input"]["route"]["service"] == "SMS"


def test_an_approval_for_one_set_of_members_covers_no_other(messages):
    approve(ms.send_members([DEST, P3], TEXT))
    assert ms.send_members([DEST], TEXT)["status"] == "needs-approval"
    assert messages.sends == []


def test_a_member_change_after_the_approval_stops_the_send(messages):
    approve(ms.send_members([DEST, P3], TEXT))
    messages.transport = "group-changed"
    result = ms.send_members([DEST, P3], TEXT)
    assert result["status"] == "not-sent" and "participants changed" in result["reason"]
    assert messages.sends == []


def test_no_chat_with_exactly_these_members_refuses_before_any_approval(messages):
    with pytest.raises(ms.Refused, match="no existing chat whose members are exactly"):
        ms.send_members([DEST, "+15550000009"], TEXT)
    assert pending_requests() == [] and messages.sends == []


def test_chats_on_both_services_need_a_choice(messages):
    messages.route = messages.transport = "both-services"
    with pytest.raises(ms.Refused, match="--service"):
        ms.send_members([DEST, P3], TEXT)
    approve(ms.send_members([DEST, P3], TEXT, service="SMS"))
    assert ms.send_members([DEST, P3], TEXT, service="SMS")["status"] == "dispatched"
    assert messages.sends == [{"text": TEXT, "chat": "chat-sms-group"}]


@pytest.mark.parametrize("members,service", [([], None), (["5551234567"], None), ([DEST], "RCS")])
def test_malformed_members_or_service_refuse_before_messages_is_read(messages, members, service):
    with pytest.raises(ms.Refused):
        ms.send_members(members, TEXT, service=service)
    assert messages.invocations == []


def test_members_command_line(messages, tmp_path, capsys):
    text_file = tmp_path / "text.txt"
    text_file.write_text(TEXT, encoding="utf-8")
    assert ms.main(["--members", f"{DEST},{P3}", "--text-file", str(text_file)]) == 2
    approve(json.loads(capsys.readouterr().out))
    assert ms.main(["--members", f"{P3}, {DEST}", "--text-file", str(text_file)]) == 0
    assert ms.main(["--to", DEST, "--service", "SMS", "--text-file", str(text_file)]) == 2
    assert "--service goes with --members" in json.loads(capsys.readouterr().out.splitlines()[-1])["reason"]


def test_command_line_exit_codes(messages, tmp_path, capsys):
    text_file = tmp_path / "text.txt"
    text_file.write_text(TEXT, encoding="utf-8")
    assert ms.main(["--to", DEST, "--text-file", str(text_file)]) == 2
    approve(json.loads(capsys.readouterr().out))
    assert ms.main(["--to", DEST, "--text-file", str(text_file)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "dispatched"
    assert ms.main(["--to", DEST, "--text-file", str(text_file)]) == 2


# --- photos (2026-10-22, the principal's ruling: iMessage and SMS photos send directly) ----------------------------

@pytest.fixture
def picture(tmp_path):
    path = tmp_path / "dinner.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0 synthetic jpeg bytes \xff\xd9")
    return path


def test_a_photo_and_its_caption_go_after_one_approval_photo_first(messages, picture):
    shot = ms.photo(str(picture))
    approve(ms.send(DEST, TEXT, attachment=shot))
    result = ms.send(DEST, TEXT, attachment=shot)
    assert result["status"] == "dispatched" and result["parts"] == ["photo", "text"]
    assert messages.sends == [{"photo": str(picture.resolve()), "chat": "chat-1"}, {"text": TEXT, "chat": "chat-1"}]
    assert picture.read_bytes() not in messages.packets[-1].encode("utf-8", "surrogateescape")  # the path, never the bytes
    with pytest.raises(ms.Refused, match="Never resend"):
        ms.send(DEST, TEXT, attachment=shot)


def test_a_photo_alone_needs_no_text_and_text_alone_keeps_its_old_key(messages, picture):
    shot = ms.photo(str(picture))
    approve(ms.send(DEST, "", attachment=shot))
    assert ms.send(DEST, "", attachment=shot)["parts"] == ["photo"]
    assert messages.sends == [{"photo": str(picture.resolve()), "chat": "chat-1"}]
    assert ms._key(DEST, TEXT) == __import__("hashlib").sha256(f"{DEST}\0{TEXT}".encode()).hexdigest()[:32]


def test_the_approval_binds_the_photo_by_its_bytes(messages, picture, tmp_path):
    approve(ms.send(DEST, TEXT, attachment=ms.photo(str(picture))))
    other = tmp_path / "other.jpg"
    other.write_bytes(b"\xff\xd8 a different photo \xff\xd9")
    assert ms.send(DEST, TEXT, attachment=ms.photo(str(other)))["status"] == "needs-approval"
    assert messages.sends == []


def test_a_photo_changed_after_it_was_read_is_not_sent(messages, picture):
    shot = ms.photo(str(picture))
    approve(ms.send(DEST, TEXT, attachment=shot))
    picture.write_bytes(b"\xff\xd8 edited after the approval, so a new size \xff\xd9")
    result = ms.send(DEST, TEXT, attachment=shot)
    assert result["status"] == "not-sent" and "attachment changed" in result["reason"]
    assert messages.sends == []


def test_a_caption_that_fails_after_its_photo_is_uncertain_and_never_resent(messages, picture):
    messages.transport = "caption-fails"
    shot = ms.photo(str(picture))
    approve(ms.send(DEST, TEXT, attachment=shot))
    result = ms.send(DEST, TEXT, attachment=shot)
    assert result["status"] == "uncertain" and "the text's failed" in result["reason"]
    assert [list(s) for s in messages.sends] == [["photo", "chat"], ["text", "chat"]]
    with pytest.raises(ms.Refused, match="Never resend"):
        ms.send(DEST, TEXT, attachment=shot)


def test_a_group_gets_the_photo_under_the_same_member_bound_approval(messages, picture):
    shot = ms.photo(str(picture))
    members = [DEST, "+15550000003"]
    approve(ms.send_members(members, TEXT, attachment=shot))
    assert ms.send_members(members, TEXT, attachment=shot)["parts"] == ["photo", "text"]
    assert {s["chat"] for s in messages.sends} == {"chat-group"}


def test_photos_that_are_not_images_missing_or_absent_refuse(messages, tmp_path, capsys):
    note = tmp_path / "note.txt"
    note.write_text("not a photo", encoding="utf-8")
    for path in (note, tmp_path / "missing.jpg"):
        with pytest.raises(ms.Refused):
            ms.photo(str(path))
    assert ms.main(["--to", DEST]) == 2 and "--text-file, --photo, or both" in capsys.readouterr().out

