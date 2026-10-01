import sys
import pytest
import native_resume as owner


@pytest.mark.parametrize("fault", [None, "future", "duplicate", "unknown"])
@pytest.mark.parametrize("jsonrpc", [True, False])
def test_real_shared_rpc_rejects_unsolicited_reply_and_keeps_notifications(
    tmp_path, fault, jsonrpc
):
    source = tmp_path / "endpoint.py"
    source.write_text("""import sys,json
fault=sys.argv[1]
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 frames=[{'jsonrpc':'2.0','method':'synthetic/progress','params':{'sequence':r['id']}},{'jsonrpc':'2.0','id':r['id'],'result':{'okay':True}}]
 if r['id']==1 and fault!='None':
  frames.append({'jsonrpc':'2.0','id':2 if fault=='future' else 1 if fault=='duplicate' else 999,'result':{'okay':True}})
 sys.stdout.write(''.join(json.dumps(x)+'\\n' for x in frames));sys.stdout.flush()
""")
    c = owner.MuseConnection(
        sys.executable,
        tmp_path,
        timeout=3,
        max_bytes=65536,
        command=[sys.executable, "-I", str(source), str(fault)],
        require_jsonrpc=jsonrpc,
    )
    try:
        if fault:
            with pytest.raises(ValueError, match="reply|response"):
                c.call("initialize", {})
        else:
            assert c.call("initialize", {}) == {"okay": True}
            assert c.call("next", {}) == {"okay": True}
            assert len(c.notifications) == 2
    finally:
        cleanup = c.close()
        assert cleanup["group_absent"] and cleanup["leader_reaped"]


@pytest.mark.parametrize("future", [False, True])
def test_partial_frame_must_finish_before_new_request(tmp_path, future):
    script = tmp_path / "partial.py"
    script.write_text("""import sys,json,time
r=json.loads(sys.stdin.readline())
row={'jsonrpc':'2.0','id':2,'result':{'okay':True}} if sys.argv[1]=='True' else {'jsonrpc':'2.0','method':'synthetic/progress','params':{}}
s=json.dumps(row)+'\\n'
sys.stdout.write(json.dumps({'jsonrpc':'2.0','id':1,'result':{'okay':True}})+'\\n'+s[:10]);sys.stdout.flush()
time.sleep(.1)
sys.stdout.write(s[10:]);sys.stdout.flush()
r=json.loads(sys.stdin.readline())
if sys.argv[1]!='True':
 sys.stdout.write(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':{'okay':True}})+'\\n');sys.stdout.flush()
time.sleep(.2)
""")
    c = owner.MuseConnection(
        sys.executable,
        tmp_path,
        timeout=3,
        max_bytes=65536,
        command=[sys.executable, "-I", str(script), str(future)],
    )
    try:
        assert c.call("initialize", {}) == {"okay": True}
        if future:
            with pytest.raises(ValueError, match="reply|response"):
                c.call("next", {})
            assert len(c.raw_stdin.splitlines()) == 1
        else:
            assert c.call("next", {}) == {"okay": True}
    finally:
        cleanup = c.close()
        assert cleanup["group_absent"] and cleanup["leader_reaped"]
