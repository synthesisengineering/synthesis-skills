"""Native asynchronous restart proofs; all native records are synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from test_owner_resume import resumed  # noqa: F401
from test_run_state import engine, world, command  # noqa: F401


def encoded(row):
    return (json.dumps(row) + "\n").encode()


def append_question(w, payload, *, rows=None):
    title = "Resume this project's saved work with existing approval limits?"
    answer = "Resume the saved work"
    now = datetime.now(timezone.utc).isoformat()
    if rows is None:
        rows = [
            {"type": "response_item", "timestamp": now, "payload": {"type": "function_call", "name": "request_user_input_async",
                "call_id": "resume-question", "arguments": json.dumps({"questions": [{"title": title, "options": [answer, "Keep waiting"]}]})}},
            {"type": "response_item", "timestamp": now, "payload": {"type": "function_call_output", "call_id": "resume-question", "output": '{"accepted":true}'}},
            {"type": "response_item", "timestamp": now, "payload": {"type": "message", "role": "user", "id": "resume-answer", "content": [{"type": "input_text", "text":
                "<send_user_message_question_reply>\n" + json.dumps([{"questionItemId": json.dumps(["request_user_input_async", "resume-question", 0]), "question": title, "answer": answer}]) + "\n</send_user_message_question_reply>"}]}}
        ]
    raw = [encoded(row) for row in rows]
    start = w['transcript'].stat().st_size
    with w['transcript'].open('ab') as stream:
        stream.write(b''.join(raw))
    payload['user_message'] = {"offset": start + sum(map(len, raw[:-1])), "length": len(raw[-1]),
        "sha256": hashlib.sha256(raw[-1]).hexdigest(), "excerpt": answer,
        "question": {"offset": start, "length": len(raw[0]), "sha256": hashlib.sha256(raw[0]).hexdigest(), "interval_sha256": hashlib.sha256(b"".join(raw)).hexdigest(),
                     "call_id": "resume-question", "message_id": "resume-answer", "question_index": 0, "title": title}}
    return rows


@pytest.mark.parametrize("resumed", ["codex"], indirect=True)
@pytest.mark.parametrize("acknowledge_wait", [False, True])
def test_exact_async_answer_renews_only_same_native_seat(engine, resumed, acknowledge_wait):
    w, old, payload, _ = resumed
    append_question(w, payload)
    if acknowledge_wait:
        payload['restart_wait'] = {'id': 'human', 'sha256': engine._digest(old['waits']['human'])}
    new = command(engine, w, old, 'owner.resume', payload, command_id='async-resume')
    assert new['owner']['session_uuid'] != old['owner']['session_uuid']
    assert new['owner']['native_ref'] == old['owner']['native_ref']
    assert new['status'] == 'recovering'
    for key in ('contract', 'profile', 'effects', 'extensions', 'artifacts'):
        assert new[key] == old[key]
    proof = new['ownership_recoveries'][-1]['user_message']
    assert proof['decision']['answer'] == payload['user_message']['excerpt']
    assert proof['decision']['question']['title'] == payload['user_message']['question']['title']
    assert len(proof['decision']['records']) == 3
    assert proof['decision']['native_session_id'] == old['owner']['native_session_id']
    assert proof['authority_granted'] is False
    if acknowledge_wait:
        assert new['waits']['human']['restart_acknowledgment']['prior'] == old['waits']['human']
    else:
        assert new['waits'] == old['waits']
    assert command(engine, w, old, 'owner.resume', payload, command_id='async-resume') == new
    with pytest.raises(ValueError):
        command(engine, w, new, 'owner.resume', payload, command_id='replay-as-new')


@pytest.mark.parametrize("resumed", ["codex"], indirect=True)
@pytest.mark.parametrize('fault', ['call-id', 'message-id', 'index', 'index-bool', 'title', 'option', 'call-hash', 'reply-hash',
    'call-boundary', 'call-after', 'oversized-window', 'missing-ack', 'bad-ack', 'numeric-ack', 'duplicate-ack', 'wrong-tool', 'assistant',
    'quote', 'heartbeat', 'meta', 'sidechain', 'old-reply', 'future-reply', 'wrong-answer-question', 'extra-answer-field',
    'wrong-answer-id', 'duplicate-answer', 'wrong-native', 'call-future', 'foreign-source', 'recipient-assertion'])
def test_async_fault_never_changes_run(engine, resumed, fault):
    w, old, payload, _ = resumed
    rows = append_question(w, payload)
    spec = payload['user_message']; q = spec['question']
    if fault in {'missing-ack', 'bad-ack', 'numeric-ack', 'duplicate-ack', 'wrong-tool', 'assistant', 'quote', 'heartbeat', 'meta', 'sidechain',
                 'old-reply', 'future-reply', 'wrong-answer-question', 'extra-answer-field', 'wrong-answer-id', 'duplicate-answer',
                 'wrong-native', 'call-future'}:
        if fault == 'missing-ack': rows.pop(1)
        elif fault == 'bad-ack': rows[1]['payload']['output'] = '{"accepted":false}'
        elif fault == 'numeric-ack': rows[1]['payload']['output'] = '{"accepted":1}'
        elif fault == 'duplicate-ack': rows.insert(1, deepcopy(rows[1]))
        elif fault == 'wrong-tool': rows[0]['payload']['name'] = 'exec'
        elif fault == 'assistant': rows[-1]['payload']['role'] = 'assistant'
        elif fault in {'quote', 'heartbeat'}:
            text = rows[-1]['payload']['content'][0]['text']
            rows[-1]['payload']['content'][0]['text'] = ('> ' + text) if fault == 'quote' else ('<heartbeat>' + text + '</heartbeat>')
        elif fault in {'meta', 'sidechain'}: rows[-1]['isMeta' if fault == 'meta' else 'isSidechain'] = True
        elif fault in {'old-reply', 'future-reply', 'call-future'}:
            rows[0 if fault == 'call-future' else -1]['timestamp'] = (datetime.now(timezone.utc) + timedelta(hours=-1 if fault == 'old-reply' else 1)).isoformat()
        elif fault == 'wrong-native': rows[-1]['thread_id'] = '01990000-0000-7000-8000-000000000099'
        else:
            text = rows[-1]['payload']['content'][0]['text']
            answers = json.loads(text.split('\n')[1])
            if fault == 'wrong-answer-question': answers[0]['question'] += 'changed'
            elif fault == 'extra-answer-field': answers[0]['approved'] = True
            elif fault == 'wrong-answer-id': answers[0]['questionItemId'] = json.dumps(['request_user_input_async', 'other', 0])
            else: answers.append(deepcopy(answers[0]))
            rows[-1]['payload']['content'][0]['text'] = '<send_user_message_question_reply>\n' + json.dumps(answers) + '\n</send_user_message_question_reply>'
        append_question(w, payload, rows=rows)
    elif fault == 'call-id': q['call_id'] = 'other'
    elif fault == 'message-id': q['message_id'] = 'other'
    elif fault == 'index': q['question_index'] = 1
    elif fault == 'index-bool': q['question_index'] = False
    elif fault == 'title': q['title'] += 'changed'
    elif fault == 'option': spec['excerpt'] = 'Keep waiting'
    elif fault == 'call-hash': q['sha256'] = '0' * 64
    elif fault == 'reply-hash': spec['sha256'] = '0' * 64
    elif fault == 'call-boundary': q['offset'] += 1
    elif fault == 'call-after': q['offset'] = spec['offset']
    elif fault == 'oversized-window': spec['offset'] += 32 * 1024 * 1024
    elif fault == 'foreign-source': spec['source_native_payload'] = deepcopy(w['actor']['native_payload'])
    else: q['recipient'] = old['owner']['native_ref']
    before = {p: p.read_bytes() for p in engine._home(w['project'], old['run_id']).rglob('*') if p.is_file()}
    with pytest.raises(ValueError):
        command(engine, w, old, 'owner.resume', payload)
    assert engine.load_run(w['project'], old['run_id']) == old
    assert all(p.read_bytes() == raw for p, raw in before.items())


@pytest.mark.parametrize("resumed", ["codex"], indirect=True)
@pytest.mark.parametrize('fault', ['question', 'ack', 'seat'])
def test_async_proof_and_seat_revalidated_before_commit(engine, resumed, fault):
    import coordination
    w, old, payload, _ = resumed
    append_question(w, payload)
    def invalidate(state, name, body, context):
        if name != 'owner.resume': return
        if fault == 'seat':
            text = w['board'].read_text(); rows = coordination.rows(text)
            next(row for row in rows if row.status == 'active').session_uuid = '01990000-0000-7000-8000-000000000066'
            w['board'].write_text(coordination.replace_table(text, rows))
        else:
            data = w['transcript'].read_bytes()
            data = data.replace(b'Resume this project', b'Cancel this project') if fault == 'question' else data.replace(b'accepted\\":true', b'accepted\\":false')
            w['transcript'].write_bytes(data)
    engine.register_constraint('invalidate-async', invalidate)
    with pytest.raises(ValueError): command(engine, w, old, 'owner.resume', payload)
    assert engine.load_run(w['project'], old['run_id']) == old


@pytest.mark.parametrize('resumed', ['codex'], indirect=True)
def test_resumption_cannot_extend_an_expired_workflow_budget(engine, resumed):
    """Seat recovery is allowed for reconciliation; new budget admission refuses."""
    import workflow
    w, old, payload, _ = resumed
    # Use the released-seat fixture's real journal, with a real budget configured
    # on its currently admitted replacement seat after renewal.
    append_question(w, payload)
    renewed = command(engine, w, old, 'owner.resume', payload)
    workflow.register_commands(engine.register_command)
    state = command(engine, w, renewed, 'workflow.configure', {'dimensions': {'domains': ['software'], 'uncertainty': 'low',
        'effect': 'local-reversible', 'horizon': 'session', 'parallelizable': False}})
    deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    state = command(engine, w, state, 'workflow.budget', {'limits': {'model_tokens': {'limit': 1000, 'enforcement': 'forecast'}}, 'deadline': deadline})
    ledger = deepcopy(state['extensions']['workflow']['budget'])
    # Exercise the actual admission owner with an elapsed observation clock.
    with pytest.raises(ValueError, match='deadline exhausted'):
        workflow._admission_open(state['extensions']['workflow'], {'now': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()})
    assert state['extensions']['workflow']['budget'] == ledger
    with pytest.raises(ValueError):
        command(engine, w, state, 'workflow.budget', {'limits': ledger['limits'], 'deadline': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()})
    assert engine.load_run(w['project'], state['run_id']) == state
