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


def test_a_reply_is_sent_back_once_but_a_reply_after_an_autopilot_continuation_is_still_checked(isolated_home):
    env = {**os.environ, "SYNTHESIS_HOME": str(isolated_home)}
    run = lambda payload: subprocess.run([sys.executable, "-S", str(ROOT / "synthesis" / "hook.py"), "stop"],
                                         input=json.dumps(payload), capture_output=True, text=True, env=env)
    lazy = {"session_id": "s1", "last_assistant_message": "Leaving that for now."}
    assert json.loads(run(lazy).stdout)["decision"] == "block"
    assert run({**lazy, "stop_hook_active": True}).stdout.strip() == ""  # revised once; never a loop
    marker = isolated_home / "state" / "stop" / "s1.json"
    marker.write_text(json.dumps({"by": "autopilot"}))
    assert json.loads(run({**lazy, "stop_hook_active": True}).stdout)["decision"] == "block"


LINKED = {"reply_file_links": True}


def test_a_file_named_without_an_absolute_link_is_sent_back_when_the_rule_is_on():
    reply = "I changed synthesis/guards.py and the notes in CONTEXT.md, see [plan](docs/plan.md) and ~/notes/todo.txt."
    reason = reply_check.check({"last_assistant_message": reply}, LINKED)
    for name in ("synthesis/guards.py", "CONTEXT.md", "docs/plan.md", "~/notes/todo.txt"):
        assert name in reason
    assert reply_check.check({"last_assistant_message": reply}, {}) is None  # off unless configured


def test_absolute_links_code_urls_and_framework_names_are_not_flagged():
    reply = ("Updated [guards.py](/Users/example/repo/synthesis/guards.py) and [the doc](/Users/example/repo/docs/a.md:12). "
             "Run `pytest tests/test_guards.py` or:\n```\npython3 tools/check.py\n```\n"
             "Spec at https://example.com/spec/index.html and [site](https://example.com/a.md). Built with Node.js and Next.js. "
             "Mail me at someone@example.md, read [section](#binding-rules), version 3.9.1 is fine.")
    assert reply_check.unlinked_files(reply) == []
    assert reply_check.check({"last_assistant_message": reply}, LINKED) is None


def test_a_filename_ending_a_sentence_is_still_caught():
    assert reply_check.unlinked_files("The fix lives in dupes.json.") == ["dupes.json"]
