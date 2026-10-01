# SPDX-License-Identifier: Apache-2.0
"""Synthetic endpoints only. Execute the actual fixed JXA under a Node app double."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
from types import SimpleNamespace

import pytest

import local_messaging as lm
import messages_boundary as mb
import messages_native as native
import messages_outbound as outbound
from test_messages_boundary import setup_guard

NODE_FIXTURE = r"""
const fs = require('fs'), vm = require('vm');
const source = Buffer.from(process.argv[1], 'base64').toString('utf8');
const mode = process.argv[3];
const calls = [];
let packet, clock = Date.now();
const account = {id:()=>packet.payload.tool_input.route.account_id,
 enabled:()=>mode !== 'disabled', connectionStatus:()=>mode === 'offline' ? 'disconnected':'connected',
 serviceType:()=>mode === 'service' ? 'SMS':'iMessage', chats:()=>mode === 'missing-chat' ? []:[chat]};
const participant = {id:()=>mode === 'participant' ? 'wrong':packet.payload.tool_input.route.participant_id,
 account:()=>mode === 'participant-account' ? {id:()=> 'wrong'}:account,
 handle:()=>mode === 'recipient' ? '+15557654321':packet.payload.tool_input.destination};
const chat = {id:()=>packet.payload.tool_input.route.chat_id, account:()=>mode === 'chat-account' ? {id:()=> 'wrong'}:account,
 participants:()=>{if(mode === 'expiry') clock = packet.expires_ms + 1; return mode === 'group' ? [participant,participant]:[participant];}};
const context = {ObjC:{import:()=>{},unwrap:x=>x}, $:{NSUTF8StringEncoding:4,
 NSFileHandle:{alloc:{initWithFileDescriptor:fd=>({get readDataToEndOfFile(){ const raw=fs.readFileSync(fd,'utf8'); packet=JSON.parse(raw); return raw;}})}},
 NSString:{alloc:{initWithDataEncoding:x=>x}}},
 Date:{now:()=>clock}, Application:name=>{if(name !== 'Messages')throw Error('unexpected app');return {
 accounts:()=>mode === 'missing-account' ? []:mode === 'duplicate-account' ? [account,account]:[account],
 send:(text,options)=>{calls.push({text,chat:options.to.id()});if(mode === 'process-loss'){fs.writeFileSync('synthetic-effect.json',JSON.stringify(calls));process.exit(23);}if(mode === 'lost')throw Error('lost after effect');}};}};
try {vm.createContext(context);vm.runInContext(source,context,{timeout:1000});const result=context.run([process.argv[2]]);console.log(JSON.stringify({result,calls}));}
catch(error){console.log(JSON.stringify({error:String(error),calls}));}
"""


class FixtureAuthority:
    def __init__(self):
        self.allow = True
        self.qualified = True
        self.allow_readback = True
        self.contexts = []

    def authorize_send(self, payload, sha):
        return {
            "digest": sha if self.allow else "0" * 64,
            "expires_ms": int(time.time() * 1000) + 120000,
        }

    def qualify(self, context):
        self.contexts.append(context)
        return lm.digest(context) if self.qualified else None

    def authorize_readback(self, payload, sha):
        return sha if self.allow_readback else None


class FixtureProcess:
    def __init__(self, after=None, mode="ok"):
        self.after, self.mode = after, mode
        self.calls = []
        self.commands = []
        self.descriptors = []

    def run(self, command, *, cwd, timeout, output_bytes, pass_fds):
        assert command[:4] == ["/usr/bin/osascript", "-l", "JavaScript", "-e"]
        assert timeout == 15 and output_bytes == 65536 and len(pass_fds) == 1
        fd = pass_fds[0]
        assert command[-1] == str(fd) and os.fstat(fd).st_nlink == 0
        packet = json.loads(os.pread(fd, 131072, 0))
        assert packet["payload"]["tool_input"]["text"] not in command
        self.descriptors.append(packet)
        self.commands.append(command)
        node = shutil.which("node")
        assert node, "Node is required to execute the real fixed script in this fixture"
        owner = lm.existing_owner(
            "synthesis-project-management", "coordination_process"
        )
        outcome = owner.run(
            [
                node,
                "-e",
                NODE_FIXTURE,
                base64.b64encode(command[4].encode()).decode(),
                str(fd),
                self.mode,
            ],
            cwd=cwd,
            timeout=3,
            output_bytes=65536,
            pass_fds=pass_fds,
        )
        if outcome.returncode:
            return outcome
        observed = json.loads(outcome.stdout)
        self.calls.extend(observed["calls"])
        Path(cwd, "synthetic-script-result.json").write_bytes(lm.canonical(observed))
        if self.after:
            self.after()
        return SimpleNamespace(
            returncode=1 if "error" in observed else 0,
            stdout=observed.get("result", observed.get("error")),
        )


@pytest.fixture
def endpoint(tmp_path):
    folder = tmp_path / "fixture-database"
    folder.mkdir()
    path = folder / "synthetic.sqlite"
    db = sqlite3.connect(path)
    db.execute("pragma journal_mode=wal")
    db.execute("pragma wal_autocheckpoint=0")
    db.executescript("""
    create table message (ROWID integer primary key,guid text,text text,attributedBody blob,date integer,is_from_me integer,handle_id integer,service text,error integer,is_sent integer);
    create table chat (ROWID integer primary key,guid text,service_name text,account_id text);
    create table handle (ROWID integer primary key,id text);
    create table chat_handle_join (chat_id integer,handle_id integer);
    create table chat_message_join (chat_id integer,message_id integer);
    insert into chat values (1,'synthetic-chat','iMessage','iMessage;+;fixture@example.invalid');
    insert into handle values (1,'+15551234567');
    insert into chat_handle_join values (1,1);
    insert into message values (1,'prior-message','Earlier fixture',null,1,0,1,'iMessage',0,1);
    insert into chat_message_join values (1,1);
    """)
    db.commit()
    request = {
        "schema": 2,
        "request_id": "synthetic-native-1",
        "destination": "+15551234567",
        "text": "Review \"quoted\" text.\n\nSecond paragraph: 'single' \\ path. 😀",
        "route": {
            "account_id": "synthetic-scripting-account-uuid",
            "service": "iMessage",
            "chat_id": "synthetic-chat",
            "participant_id": "synthetic-participant",
            "database_account_id": "iMessage;+;fixture@example.invalid",
            "database": str(path),
        },
    }

    def append(*, sent=1, error=0, text=None, guid=None, chat=1, service="iMessage"):
        rowid = db.execute("select max(ROWID)+1 from message").fetchone()[0]
        db.execute(
            "insert into message values (?,?,?,?,?,?,?,?,?,?)",
            (
                rowid,
                guid or f"new-message-{rowid}",
                request["text"] if text is None else text,
                None,
                rowid,
                1,
                1,
                service,
                error,
                sent,
            ),
        )
        db.execute("insert into chat_message_join values (?,?)", (chat, rowid))
        db.commit()

    def retain(label):
        custody = tmp_path / label
        custody.mkdir()
        for suffix in ("", "-wal", "-shm"):
            source = Path(str(path) + suffix)
            if source.is_file():
                shutil.copyfile(source, custody / ("synthetic.sqlite" + suffix))

    retain("fixture-input-bytes")
    yield SimpleNamespace(db=db, path=path, request=request, append=append)
    retain("fixture-final-bytes")
    # The WAL remains open through the assertion phase; closing is not mutation by the reader.
    db.close()


def owners(endpoint, tmp_path, monkeypatch, *, mode="ok", after=None):
    setup_guard(tmp_path, monkeypatch, endpoint.request)
    authority = FixtureAuthority()
    process = FixtureProcess(after=after, mode=mode)
    return (
        native.NativeMessagesOwner(authority, process_owner=process),
        process,
        authority,
    )


def test_native_actual_script_descriptor_quotes_and_unattributed_readback(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(
        endpoint, tmp_path, monkeypatch, after=endpoint.append
    )
    result = mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert process.calls == [
        {"text": endpoint.request["text"], "chat": "synthetic-chat"}
    ]
    assert (
        result["status"] == "OBSERVED_MATCH_UNATTRIBUTED"
        and result["acknowledgement"] == "UNKNOWN"
    )
    assert (
        authority.contexts[0]["route"]["account_id"]
        != authority.contexts[0]["route"]["database_account_id"]
    )
    assert process.descriptors[0]["payload"] == mb.prepare(endpoint.request)
    fence = (tmp_path / "state/send.json").read_bytes()
    with pytest.raises(lm.Refused, match="unresolved"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert (
        len(process.calls) == 1 and (tmp_path / "state/send.json").read_bytes() == fence
    )


@pytest.mark.parametrize(
    "mode",
    [
        "missing-account",
        "duplicate-account",
        "disabled",
        "offline",
        "service",
        "missing-chat",
        "chat-account",
        "participant",
        "participant-account",
        "recipient",
        "group",
        "expiry",
    ],
)
def test_actual_script_refuses_wrong_route_and_final_expiry(
    endpoint, tmp_path, monkeypatch, mode
):
    owner, process, _ = owners(endpoint, tmp_path, monkeypatch, mode=mode)
    with pytest.raises(lm.Refused, match="transport failed"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert process.calls == []
    assert lm.file_json(tmp_path / "state/send.json")["status"] == "EFFECT_UNKNOWN"
    with pytest.raises(lm.Refused, match="unresolved"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert len(process.commands) == 1


@pytest.mark.parametrize(
    "case", ["pending", "failed", "duplicate", "missing", "different-text"]
)
def test_outbound_incomplete_evidence_is_unknown(endpoint, tmp_path, monkeypatch, case):
    def after():
        if case == "pending":
            endpoint.append(sent=0)
        elif case == "failed":
            endpoint.append(error=7)
        elif case == "duplicate":
            endpoint.append()
            endpoint.append()
        elif case == "different-text":
            endpoint.append(text="Unrelated fixture message")

    owner, process, _ = owners(endpoint, tmp_path, monkeypatch, after=after)
    result = mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert (
        result["status"] == "EFFECT_UNKNOWN" and result["acknowledgement"] == "UNKNOWN"
    )
    assert len(process.calls) == 1


def test_lost_return_late_row_recovery_never_resends(endpoint, tmp_path, monkeypatch):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch, mode="lost")
    home = tmp_path / "state"
    with pytest.raises(lm.Refused, match="interrupted"):
        mb.send_with_owner(endpoint.request, home, owner)
    fence = (home / "send.json").read_bytes()
    fresh = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    first = mb.recover_with_owner(endpoint.request, home, fresh)
    assert first["status"] == "EFFECT_UNKNOWN"
    endpoint.append()  # Could be a concurrent human action; origin is deliberately unknown.
    second = mb.recover_with_owner(endpoint.request, home, fresh)
    assert second["status"] == "OBSERVED_MATCH_UNATTRIBUTED"
    assert len(process.calls) == 1 and fresh.process.calls == []
    assert (home / "send.json").read_bytes() == fence
    assert lm.file_json(home / "observation-002.json")["previous"] == lm.digest(
        lm.file_json(home / "observation-001.json")
    )


@pytest.mark.parametrize(
    "change", ["account", "recipient", "service", "group", "schema"]
)
def test_database_contract_refused_before_transport(
    endpoint, tmp_path, monkeypatch, change
):
    if change == "account":
        endpoint.db.execute("update chat set account_id='wrong'")
    elif change == "recipient":
        endpoint.db.execute("update handle set id='+15557654321'")
    elif change == "service":
        endpoint.db.execute("update chat set service_name='SMS'")
    elif change == "group":
        endpoint.db.execute("insert into chat_handle_join values (1,1)")
    elif change == "schema":
        endpoint.db.execute("alter table message rename column is_sent to unknown_flag")
    endpoint.db.commit()
    owner, process, _ = owners(endpoint, tmp_path, monkeypatch)
    with pytest.raises(lm.Refused, match="confined outbound"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert process.commands == []


def test_unqualified_account_mapping_and_missing_approval_refuse(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    authority.qualified = False
    with pytest.raises(lm.Refused, match="qualification"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert process.commands == []
    authority.allow = False
    with pytest.raises(lm.Refused, match="approval"):
        mb.send_with_owner(endpoint.request, tmp_path / "other-state", owner)
    assert process.commands == []


def test_changed_source_executes_only_captured_script_then_remains_unknown(
    endpoint, tmp_path, monkeypatch
):
    copy = tmp_path / "source-copy"
    copy.mkdir()
    for name in native.SOURCE_NAMES:
        shutil.copyfile(Path(native.__file__).with_name(name), copy / name)
    monkeypatch.setattr(native, "__file__", str(copy / "messages_native.py"))
    original = (copy / "messages_transport.js").read_text()
    owner, process, _ = owners(
        endpoint,
        tmp_path,
        monkeypatch,
        after=lambda: (copy / "messages_transport.js").write_text(
            "throw Error('changed source');"
        ),
    )
    with pytest.raises(lm.Refused, match="source changed"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert process.commands[0][4] == original and len(process.calls) == 1
    assert lm.file_json(tmp_path / "state/send.json")["status"] == "EFFECT_UNKNOWN"


@pytest.mark.parametrize(
    "case",
    [
        "partial",
        "source-replaced",
        "changed-schema",
        "cursor-regressed",
        "changed-anchor",
        "overflow",
        "wrong-chat",
    ],
)
def test_retained_fence_survives_partial_or_unusable_readback(
    endpoint, tmp_path, monkeypatch, case
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    home = tmp_path / "state"
    assert (
        mb.send_with_owner(endpoint.request, home, owner)["status"] == "EFFECT_UNKNOWN"
    )
    fence = (home / "send.json").read_bytes()
    if case == "partial":
        (home / "observation-002.json").write_text('{"partial":true}')
    elif case == "source-replaced":
        replacement = endpoint.path.with_name("replacement.sqlite")
        replacement.write_bytes(endpoint.path.read_bytes())
        os.replace(replacement, endpoint.path)
    elif case == "changed-schema":
        endpoint.db.execute("alter table message add column extra text")
        endpoint.db.commit()
    elif case == "cursor-regressed":
        endpoint.db.execute("delete from message")
        endpoint.db.commit()
    elif case == "changed-anchor":
        endpoint.db.execute("update message set guid='reused-row'")
        endpoint.db.commit()
    elif case == "overflow":
        for i in range(101):
            endpoint.append(text=f"Synthetic unrelated {i}")
    elif case == "wrong-chat":
        endpoint.append(chat=99)
    fresh = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    with pytest.raises((lm.Refused, json.JSONDecodeError)):
        mb.recover_with_owner(endpoint.request, home, fresh)
    assert fresh.process.commands == [] and len(process.calls) == 1
    assert (home / "send.json").read_bytes() == fence


def test_direct_outbound_worker_refuses_unconfined_read(endpoint):
    query = {
        "schema": outbound.SCHEMA,
        "route": endpoint.request["route"],
        "destination": endpoint.request["destination"],
        "text_sha256": hashlib.sha256(endpoint.request["text"].encode()).hexdigest(),
        "request_digest": "0" * 64,
        "baseline": None,
    }
    with pytest.raises(
        lm.Refused, match="write permission|confinement|writable|sandbox"
    ):
        outbound.query(query)


def test_recovery_authorization_is_distinct_from_expired_send(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    home = tmp_path / "state"
    mb.send_with_owner(endpoint.request, home, owner)
    authority.allow = False
    authority.allow_readback = False
    with pytest.raises(lm.Refused, match="readback authorization"):
        mb.recover_with_owner(
            endpoint.request,
            home,
            native.NativeMessagesOwner(authority, process_owner=FixtureProcess()),
        )
    assert len(process.calls) == 1


def test_original_single_newline_is_guard_refusal_before_transport(
    endpoint, tmp_path, monkeypatch
):
    endpoint.request["text"] = (
        "Review \"quoted\" text.\nSecond line: 'single' \\ path. 😀"
    )
    owner, process, _ = owners(endpoint, tmp_path, monkeypatch)
    with pytest.raises(lm.Refused, match="message guard refused"):
        mb.send_with_owner(endpoint.request, tmp_path / "state", owner)
    assert process.commands == [] and not (tmp_path / "state/send.json").exists()


def test_actual_process_loss_cannot_replay_after_late_observation(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(
        endpoint, tmp_path, monkeypatch, mode="process-loss"
    )
    home = tmp_path / "state"
    with pytest.raises(lm.Refused, match="interrupted"):
        mb.send_with_owner(endpoint.request, home, owner)
    assert lm.file_json(home / "synthetic-effect.json") == [
        {"text": endpoint.request["text"], "chat": "synthetic-chat"}
    ]
    endpoint.append()
    fresh = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    assert (
        mb.recover_with_owner(endpoint.request, home, fresh)["status"]
        == "OBSERVED_MATCH_UNATTRIBUTED"
    )
    with pytest.raises(lm.Refused, match="unresolved"):
        mb.send_with_owner(endpoint.request, home, fresh)
    assert fresh.process.commands == [] and len(process.commands) == 1


def test_human_match_after_zero_transport_calls_remains_unattributed(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(
        endpoint, tmp_path, monkeypatch, mode="disabled", after=endpoint.append
    )
    home = tmp_path / "state"
    with pytest.raises(lm.Refused, match="transport failed"):
        mb.send_with_owner(endpoint.request, home, owner)
    assert process.calls == []
    fresh = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    assert (
        mb.recover_with_owner(endpoint.request, home, fresh)["status"]
        == "OBSERVED_MATCH_UNATTRIBUTED"
    )
    assert fresh.process.commands == []


def test_pending_row_later_status_does_not_gain_causal_attribution(
    endpoint, tmp_path, monkeypatch
):
    owner, process, authority = owners(
        endpoint, tmp_path, monkeypatch, after=lambda: endpoint.append(sent=0)
    )
    home = tmp_path / "state"
    assert (
        mb.send_with_owner(endpoint.request, home, owner)["status"] == "EFFECT_UNKNOWN"
    )
    endpoint.db.execute("update message set is_sent=1 where ROWID=2")
    endpoint.db.commit()
    fresh = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    assert (
        mb.recover_with_owner(endpoint.request, home, fresh)["status"]
        == "OBSERVED_MATCH_UNATTRIBUTED"
    )
    assert len(process.calls) == 1 and fresh.process.commands == []


def test_confined_outbound_read_preserves_database_and_wal_bytes(endpoint, tmp_path):
    paths = [Path(str(endpoint.path) + suffix) for suffix in ("", "-wal", "-shm")]
    before = {str(p): (p.stat().st_ino, p.read_bytes()) for p in paths}
    query = {
        "schema": outbound.SCHEMA,
        "route": endpoint.request["route"],
        "destination": endpoint.request["destination"],
        "text_sha256": hashlib.sha256(endpoint.request["text"].encode()).hexdigest(),
        "request_digest": "0" * 64,
        "baseline": None,
    }
    result = outbound.run_query(query, tmp_path / "query-worker")
    assert result["baseline"]["upper"] == 1 and result["confinement"]
    assert before == {str(p): (p.stat().st_ino, p.read_bytes()) for p in paths}


@pytest.mark.parametrize(
    "case", ["invalid-json", "foreign-digest", "missing-phase", "exception"]
)
def test_transport_receipt_failures_keep_fence_and_cannot_replay(
    endpoint, tmp_path, monkeypatch, case
):
    owner, process, authority = owners(endpoint, tmp_path, monkeypatch)
    original = process.run

    def broken(*args, **kwargs):
        receipt = original(*args, **kwargs)
        if case == "exception":
            raise RuntimeError("synthetic process owner lost return")
        if case == "invalid-json":
            receipt.stdout = "{"
        elif case == "foreign-digest":
            receipt.stdout = json.dumps(
                {"protocol": 1, "request_digest": "0" * 64, "phase": "dispatched"}
            )
        else:
            receipt.stdout = json.dumps({"protocol": 1})
        return receipt

    process.run = broken
    home = tmp_path / "state"
    with pytest.raises((lm.Refused, json.JSONDecodeError, RuntimeError)):
        mb.send_with_owner(endpoint.request, home, owner)
    fence = (home / "send.json").read_bytes()
    with pytest.raises(lm.Refused, match="unresolved"):
        mb.send_with_owner(endpoint.request, home, owner)
    assert len(process.calls) == 1 and (home / "send.json").read_bytes() == fence
    fresh = native.NativeMessagesOwner(authority, process_owner=FixtureProcess())
    assert (
        mb.recover_with_owner(endpoint.request, home, fresh)["status"]
        == "EFFECT_UNKNOWN"
    )
    assert fresh.process.commands == []
