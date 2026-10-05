"""S15: the final reply is revised once when it defers work or quotes words with no source."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from synthesis import reply_check

ROOT = Path(__file__).resolve().parents[1]


def test_shortcut_phrasing_blocks_once():
    payload = {"last_assistant_message": "I'll handle the rest for now and revisit later."}
    reason = reply_check.check(payload, {})
    assert '"for now"' in reason and '"revisit later"' in reason
    assert reply_check.check({**payload, "stop_hook_active": True}, {}) is None


def test_naming_a_rule_in_quotes_or_code_is_not_a_violation():
    reply = 'The voice rules ban "for now" and `as a first pass`, so I removed both.'
    assert reply_check.check({"last_assistant_message": reply}, {}) is None


def test_private_phrases_extend_the_catalog():
    assert reply_check.check({"last_assistant_message": "That can wait until next quarter."},
                             {"shortcut_phrases": ["can wait until"]}) is not None


def test_attributed_quote_must_appear_in_the_session_record(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"tool_result": "Rajiv wrote: keep native memory on in every client, please"}) + "\n")
    ok = 'Rajiv wrote: "keep native memory on in every client, please".'
    invented = 'Rajiv said: "ship it tonight without the tests, it is fine".'
    assert reply_check.check({"last_assistant_message": ok, "transcript_path": str(transcript)}, {}) is None
    reason = reply_check.check({"last_assistant_message": invented, "transcript_path": str(transcript)}, {})
    assert "not found in this session's record" in reason


def test_large_transcript_is_searched_fast(tmp_path):
    transcript = tmp_path / "big.jsonl"
    with open(transcript, "w") as handle:
        for i in range(400_000):
            handle.write(json.dumps({"n": i, "text": "ordinary tool output line"}) + "\n")
    start = time.perf_counter()
    reply_check.check({"last_assistant_message": 'She said: "this phrase is nowhere in the record at all".',
                       "transcript_path": str(transcript)}, {})
    assert time.perf_counter() - start < 0.2


def test_stop_hook_emits_a_block_decision_and_fails_open_on_bad_input(isolated_home):
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    run = lambda payload: subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "stop"],
                                         input=payload, capture_output=True, text=True, env=env)
    out = run(json.dumps({"last_assistant_message": "Leaving that for now."}))
    assert json.loads(out.stdout)["decision"] == "block"
    out = run(json.dumps({"last_assistant_message": 'X said: "a quote long enough here"', "transcript_path": "/missing"}))
    assert out.returncode == 0 and out.stdout.strip() == ""
