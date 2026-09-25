import copy, json, sys
from pathlib import Path
import pytest
import native_codex as adapter
ROOT = {"client":"codex", "thread_id":"root", "root_session_id":"root", "parent_thread_id":None, "agent_path":None}
ACTUAL = {"timestamp":"2026-09-25T19:59:29.711Z","ordinal":87187,"type":"inter_agent_communication_metadata","payload":{"trigger_turn":False}}

@pytest.mark.parametrize("trigger", [False, True])
def test_metadata_is_typed_non_authority_observation(trigger):
    row=copy.deepcopy(ACTUAL); row["payload"]["trigger_turn"]=trigger
    observed=adapter.decode_record(row,ROOT)
    assert len(observed)==1
    fact=observed[0]
    assert fact["kind"]=="communication.observation"
    assert fact["status"]=="observed"
    assert fact["data"]=={"trigger_turn":trigger,"portable_completion":False,"grants_authority":False,"proves_wake":False}
    assert fact["native"]["call_id"] is None
    assert not adapter.is_ignored_projection({"type":row["type"]},ROOT)

@pytest.mark.parametrize("payload", [{},{"trigger_turn":None},{"trigger_turn":0},{"trigger_turn":1},{"trigger_turn":"false"},{"trigger_turn":False,"grants_authority":True},{"trigger_turn":False,"future":0}])
def test_unknown_and_malformed_metadata_are_not_accepted(payload):
    row=copy.deepcopy(ACTUAL);row["payload"]=payload
    with pytest.raises(ValueError):adapter.decode_record(row,ROOT)

@pytest.mark.parametrize("field,value", [("thread_id","foreign"),("session_id","foreign"),("ordinal",True),("ordinal",-1),("future_authority",True)])
def test_metadata_envelope_refuses_foreign_or_unknown_fields(field,value):
    row=copy.deepcopy(ACTUAL);row[field]=value
    with pytest.raises(ValueError):adapter.decode_record(row,ROOT)

@pytest.mark.parametrize("position", ["before","after"])
def test_metadata_cannot_mask_cancel_or_user_instruction(position):
    row=copy.deepcopy(ACTUAL)
    cancel={"type":"event_msg","payload":{"type":"turn_aborted","turn_id":"turn"}}
    instruction={"type":"event_msg","payload":{"type":"user_message","message":"Stop work"}}
    rows=[cancel,instruction];rows.insert(0 if position=="before" else len(rows),row)
    facts=[f for r in rows for f in adapter.decode_record(r,ROOT)]
    assert len([f for f in facts if f["kind"]=="lifecycle.cancelled"])==1
    assert len([f for f in facts if f["kind"]=="message.user"])==1
    assert not any(f["kind"]=="lifecycle.completed" for f in facts)

@pytest.mark.parametrize("page_bytes", [31, 1048576])
def test_exact_source_readback_retains_metadata_and_detects_changed_bytes(tmp_path,page_bytes):
    import native_observations as no
    row=copy.deepcopy(ACTUAL)
    header={"type":"session_meta","payload":{"id":"root","cwd":str(tmp_path)}}
    source=tmp_path/"fixture.jsonl"
    source.write_text(json.dumps(header)+"\n"+json.dumps(row)+"\n")
    binding,cursor=no.enroll_source(source,client="codex",expected_root_session_id="root",expected_thread_id="root")
    events=[];projection=no.empty_projection()
    for _ in range(100):
        batch=no.read_page(binding,cursor,limits=no.Limits(page_bytes=page_bytes))
        cursor=batch["cursor"];events.extend(batch["events"]);projection=no.reduce_observations(projection,batch)
        if not batch["coverage"]["backlog_bytes"]:break
    else:pytest.fail("bounded observation did not drain")
    assert not projection["gaps"] and not projection["diagnostics"]
    assert len(events)==1 and events[0]["kind"]=="communication.observation"
    assert not projection["pairs"] and not events[0]["data"]["proves_wake"]
    result=no.revalidate_observations(binding,events,required_interval=(0,source.stat().st_size))
    assert result["status"]=="current" and result["negative_coverage"]=="CURRENT_BOUNDED_INTERVAL"
    source.write_bytes(source.read_bytes().replace(b'"trigger_turn": false',b'"trigger_turn": true '))
    assert no.revalidate_observations(binding,events)["status"]=="invalid"

@pytest.mark.parametrize("change",["unknown","duplicate","nonbool"])
def test_source_never_turns_unrecognized_metadata_into_clear_coverage(tmp_path,change):
    import native_observations as no
    raw=json.dumps(ACTUAL)
    if change=="unknown":raw=raw.replace('"trigger_turn": false','"trigger_turn": false, "authority": true')
    elif change=="duplicate":raw=raw.replace('"trigger_turn": false','"trigger_turn": false, "trigger_turn": true')
    else:raw=raw.replace('"trigger_turn": false','"trigger_turn": 0')
    source=tmp_path/"invalid.jsonl";source.write_text(json.dumps({"type":"session_meta","payload":{"id":"root"}})+"\n"+raw+"\n")
    binding,cursor=no.enroll_source(source,client="codex",expected_root_session_id="root",expected_thread_id="root")
    batch=no.read_page(binding,cursor)
    assert batch["gaps"] and not batch["events"] and batch["cursor"]["first_gap"] is not None

from test_run_state import engine, world
from test_controller import facade
from test_observation_bridge import bridge, append

@pytest.mark.parametrize('kind', [None, 'turn_aborted', 'user_message'])
@pytest.mark.parametrize('position', ['before', 'after'])
def test_owner_journal_communication_metadata_preserves_current_invalidations(bridge, engine, facade, world, monkeypatch, kind, position):
    from test_controller import invoke, request, start_request, state_of
    native = world['actor']['native_payload']['session_id']
    home = world['scratch'] / 'fixture-codex'
    directory = home / 'sessions/2026/09/25'; directory.mkdir(parents=True)
    transcript = directory / ('rollout-' + native + '.jsonl')
    transcript.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': native,
        'cwd': str(world['repo'])}}) + '\n')
    world['transcript'] = transcript
    world['actor']['native_payload']['transcript_path'] = str(transcript)
    world['board'].write_text(world['board'].read_text().replace('| claude |', '| codex |').replace('cc:' + native, 'codex:' + native))
    monkeypatch.setenv('CODEX_HOME', str(home))
    monkeypatch.setenv('SYNTHESIS_CLIENT_SESSION_REF', 'codex:' + native)
    started = invoke(facade, world, start_request(world))
    assert started['status'] == 'READY', started
    state = state_of(world, started)
    rows = [{"type": "inter_agent_communication_metadata", "payload": {"trigger_turn": False}}]
    if kind:
        change = {'type': 'event_msg', 'payload': {'type': kind, 'turn_id': 'turn', 'message': 'Pause this task'}}
        rows.insert(0 if position == 'before' else 1, change)
    for ordinal, row in enumerate(rows, 1): row['ordinal'] = ordinal
    append(world, *rows)
    pending = bridge.current_invalidation(engine.inspect_context(state, world['actor']))
    assert pending['status'] == ('invalidated' if kind else 'clear'), pending
    recorded = invoke(facade, world, request('record', {'kind': 'native', 'source_handle': 'root',
        'through_event': None, 'task_id': None, 'attempt_id': None}, state, 'metadata-record'))
    assert recorded['status'] == 'RECORDED', recorded
    state = state_of(world, recorded)
    source = state['extensions']['native_observations']
    assert not source['latest_batch']['gaps'] and not source['latest_batch']['diagnostics']
    assert len([e for e in source['latest_batch']['events'] if e['kind'] == 'communication.observation']) == 1
    current = bridge.current_invalidation(engine.inspect_context(state, world['actor']))
    assert current['status'] == ('invalidated' if kind else 'clear'), current
    assert engine.load_run(world['project'], state['run_id']) == state
    assert state['status'] != 'completed' and not source['projection']['pairs']


@pytest.mark.parametrize("stamp", [None,False,0,[],{},"","invalid","2026-99-99T99:99:99Z","2026-09-25T12:00:00","2026-09-25T12:00:00+25:00","2026-09-25T12:00:00+01:99","2026-09-25T12:00:00+00:60","2026-09-25T12:00:00-01:99","2026-09-25T12:00:00Z"+"x"*65])
def test_supplied_metadata_timestamp_must_be_bounded_valid_and_aware(stamp):
    row=copy.deepcopy(ACTUAL);row["timestamp"]=stamp
    with pytest.raises(adapter.DialectError):adapter.decode_record(row,ROOT)

@pytest.mark.parametrize("stamp", [None,"2026-09-25T12:00:00Z","2026-09-25T12:00:00.123456789+05:30"])
def test_optional_metadata_timestamp_preserves_valid_native_forms(stamp):
    row=copy.deepcopy(ACTUAL)
    if stamp is None:row.pop("timestamp")
    else:row["timestamp"]=stamp
    observed=adapter.decode_record(row,ROOT)[0]
    assert observed["native_timestamp"]==stamp
    assert observed["kind"]=="communication.observation" and not observed["data"]["proves_wake"]
