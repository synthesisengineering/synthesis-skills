"""stop_reprompts.py: the weekly count of replies the Stop hook sent back, read from a fixture archive."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import stop_reprompts  # noqa: E402

MARK = stop_reprompts.MARK


def _session(root, workspace, month, folder, records, age_days=0):
    path = root / workspace / month / folder / "transcript-0001.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))
    return path


def _feedback(at, problems):
    return {"seq": 1, "at": at, "kind": "system", "text": "Stop hook feedback:\n" + MARK + problems}


def _blocking(at, problems):
    report = {"hookName": "Stop", "hookEvent": "Stop", "blockingError": {"blockingError": MARK + problems}}
    return {"seq": 2, "at": at, "kind": "system", "source": "hook_blocking_error", "text": json.dumps(report)}


def test_each_send_back_counts_once_by_check_and_names_what_recurs(tmp_path):
    links = "files named without a clickable link: CLAUDE.md, AGENTS.md. Write each as [name](/absolute/path)."
    phrase = 'lazy-shortcut phrasing: "your call". Do the work or name the real blocker.'
    quote = "quotes not found in this session's record: \"he said so\". Quote only what a tool surfaced."
    _session(tmp_path, "rajiv", "2026-09", "claude-code-aaaa", [  # started in September, wrote in October
        _feedback("2026-10-27T10:00:00Z", links), _blocking("2026-10-27T10:00:00Z", links),  # one send-back, two records
        _blocking("2026-10-28T09:00:00Z", phrase + " " + links),  # only the blocking-error record, two checks
        _feedback("2026-10-20T09:00:00Z", phrase),  # before the window
        {"seq": 9, "at": "2026-10-28T09:05:00Z", "kind": "assistant", "text": "I quoted " + MARK + phrase},  # not the hook
    ])
    _session(tmp_path, "rajiv", "2026-10", "codex-bbbb", [_feedback("2026-10-29T12:00:00Z", quote)])
    _session(tmp_path, "client", "2026-10", "claude-code-cccc", [_feedback("2026-10-29T12:00:00Z", phrase)])
    _session(tmp_path, "rajiv", "2026-08", "claude-code-dddd", [_feedback("2026-10-27T10:00:00Z", phrase)], age_days=60)

    since, until = stop_reprompts.date(2026, 10, 24), stop_reprompts.date(2026, 10, 30)
    found = stop_reprompts.send_backs(tmp_path, since, until, ["rajiv"])
    result = stop_reprompts.report(found, since, until)
    assert result["replies"] == 3 and result["sessions"] == 2
    assert result["checks"] == {"file links": 2, "shortcut phrasing": 1, "unsourced quotes": 1}
    assert result["harnesses"] == {"claude-code": 2, "codex": 1}
    assert ["file links: CLAUDE.md", 2] in result["most_named"] and ["file links: AGENTS.md", 2] in result["most_named"]
    assert not any(item.startswith("unsourced quotes") for item, _ in result["most_named"])
    assert stop_reprompts.report(stop_reprompts.send_backs(tmp_path, since, until, []), since, until)["replies"] == 4


def test_no_archive_is_reported_and_never_fails(tmp_path, capsys):
    assert stop_reprompts.main(["--archive", str(tmp_path / "missing")]) == 0
    assert "no archive" in capsys.readouterr().out
    assert stop_reprompts.main(["--archive", str(tmp_path), "--since", "2026-10-24", "--until", "2026-10-30"]) == 0
    assert "0 replies in 0 sessions" in capsys.readouterr().out
