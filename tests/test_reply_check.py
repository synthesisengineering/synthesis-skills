"""S15: the final reply is revised once when it defers work or quotes words with no source."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from synthesis import reply_check

ROOT = Path(__file__).resolve().parents[1]


def test_shortcut_phrasing_blocks_once():
    payload = {"last_assistant_message": "I'll handle the rest for now and revisit later."}
    reason = reply_check.check(payload, {})
    assert '"for now"' in reason and '"revisit later"' in reason
    assert reply_check.check({**payload, "stop_hook_active": True}, {}) is None


def test_a_wait_handed_back_to_the_principal_is_sent_back():
    """2026-11-02: a merged release waiting on CI was parked behind the principal's next message."""
    reason = reply_check.check({"last_assistant_message": "CI is still queued; any message from you, even release, "
                                                          "starts it."}, {})
    assert reason and '"any message from you"' in reason
    assert reply_check.check({"last_assistant_message": "A watcher releases it when CI passes."}, {}) is None


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


def _turn(path, *entries):
    with open(path, "a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _prompt(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _call(ident, name, **extra):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": ident, "name": name, "input": extra}]}}


def _result(ident, error=False):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": ident, "is_error": error, "content": "done"}]}}


def test_a_calendar_write_with_no_read_after_it_sends_the_reply_back(tmp_path):
    """2026-10-27: a series moved to a new hour revived a meeting canceled at the old hour, double-booked on an
    accepted one, and nobody read the day back; the principal found it himself."""
    record = tmp_path / "t.jsonl"
    write = "mcp__ws__manage_event"
    _turn(record, _prompt("Move the series to 2pm."), _call("w1", write, action="update"), _result("w1"))
    payload = {"last_assistant_message": "Moved.", "transcript_path": str(record)}
    assert "manage_event" in reply_check.check(payload, {}) and "read" in reply_check.check(payload, {})
    _turn(record, _call("r1", "mcp__ws__get_events"), _result("r1"))
    assert reply_check.check(payload, {}) is None  # read back after the write
    _turn(record, _prompt("Cancel today's."), _call("w2", "mcp__ws__delete_event"), _result("w2", error=True))
    assert reply_check.check(payload, {}) is None  # refused by the guard: nothing changed
    _turn(record, _call("w3", "mcp__ws__delete_event"), _result("w3"))
    assert "delete_event" in reply_check.check(payload, {})
    _turn(record, _prompt("Thanks."))
    assert reply_check.check(payload, {}) is None  # a new turn starts clean


# --- an announced wait, read clause by clause ----------------------------------------------------------------------
# Review round 1 of 5.8.0 (2026-11-12): the check read its phrases anywhere in a reply. It sent back 15 of 34 replies
# that need no watcher (an explanation of code, a status report, a wait on the principal's own next move) and let
# through 9 of 17 that announce the session's own wait. Each reply below is its own case; the N and W ids are the
# review's, and the rest are written as an agent ends a turn.

NO_WATCHER_NEEDED = {
    "N05": "The function returns when it finishes reading the file.",
    "N06": "The child process is reaped once it returns.",
    "N07": "The response is queued; the callback runs when it arrives.",
    "N08": "The handler queues a retry when it finishes.",
    "N09": "When it finishes, the job writes its result to disk.",
    "N11": "The package should arrive shortly; the courier has your phone number.",
    "N16": "I'm waiting for a yes from you.",
    "N17": "I'll wait for the approval code from you.",
    "N18": "Waiting for the decision you promised.",
    "N22": "Your refund is pending and should arrive shortly. No further action is needed.",
    "N23": "The release was blocked yesterday: waiting for a runner was the cause.",
    "N26": "The server returns a response when it finishes processing the request.",
    "N27": "The recruiter should come shortly to escort you upstairs.",
    "N29": "Your download starts once it arrives at the front of the queue.",
    "N32": "The waiter told the kitchen that the order should come shortly.",
}
OWN_WAIT = {
    "W07": "I'm awaiting the vendor's confirmation before continuing.",
    "W08": "I'll continue once the reviewer responds.",
    "W09": "I will resume when the build completes.",
    "W10": "We're waiting for the second reviewer before I merge.",
    "W11": "I'm still waiting for CI to finish; your code review comments are already applied.",
    "W12": "I'll wait for the build. You can review the draft while it runs.",
    "W13": "Waiting for the vendor. I will update your decision log after the reply.",
    "W16": "Waiting until the vendor replies before I continue.",
    "W17": "I'll wait for your colleague to reply, then finish the review.",
}
# Sent back before the rebuild, as the review's fifteen were.
MORE_NO_WATCHER = {
    "a-fix-explained": "Fixed. The worker no longer blocks when it finishes a batch, and retries are capped at three.",
    "a-cache-explained": "I could not reproduce the hang. The cache entry is evicted once it returns to the pool, which is why "
                         "the second read was slow.",
    "a-hook-explained": "The hook was right to block the commit: the linter exits non-zero when it finishes with warnings.",
    "a-travel-status": "Your flight is on time, and the car should arrive shortly before nine. Nothing needs your attention "
                       "tonight.",
    "a-wait-as-the-cause": "Root cause found. Waiting on the license server was what stalled every build; the tests "
                           "themselves ran in four minutes.",
    "a-wait-as-a-hazard": "Waiting for a lock inside the handler can deadlock, so I moved the call outside the critical section.",
    "a-test-described": "I added a test that fails when it returns early, and it passes with the fix.",
    "a-third-party-report": "The vendor wrote that the invoice should arrive shortly, and I filed their note in the project record.",
    "a-deploy-described": "You'll see the banner once it lands in production; the change is merged and deployed to staging.",
    "numbers-you-promised": "The draft is ready to send. I'm waiting for the two numbers you promised.",
    "go-ahead-from-you": "Both deploys are staged. I'll wait for the go-ahead from you.",
    "form-from-you": "Still waiting for the signed form from you; everything else on the list is done.",
    "two-things-from-you": "I'm waiting on two things from you:\n1. The approval code for the deploy\n2. Which title to use",
    "your-sign-off-after-a-colon": "I'm waiting on one thing before I send it: your sign-off on the last paragraph.",
    "a-draft-in-a-block-quote": "The draft is below; send it as it is, or tell me what to change.\n\n> Thanks for the note. I'm "
                                "waiting for the venue's answer and will confirm the time as soon as I have it.",
}
# Passed before the rebuild too. Each stands beside a form the rebuild reads, so none of those forms may catch it.
STILL_NO_WATCHER = {
    "merge-once-you-approve": "I'll merge once you approve the pull request.",
    "once-you-confirm-i-proceed": "Once you confirm the date, I'll proceed with the booking.",
    "hold-until-you-type": "I'll hold the release until you type the approval code.",
    "we-wait-on-your-decision": "We're waiting on your decision about the venue; everything else is booked.",
    "awaiting-your-go": "Awaiting your go on the migration before I touch production.",
    "your-next-message": "I'll wait here for your next message.",
    "your-guidance": "Awaiting your guidance on which of the two drafts to send.",
    "your-green-light": "I'll hold the deploy until I have your green light.",
    "your-thoughts": "I'm waiting for your thoughts on the outline before I draft the rest.",
    "which-you-prefer": "I'm waiting to hear which option you prefer.",
    "a-list-of-the-principals-moves": "Still waiting on:\n- your approval of the draft\n- your decision on the venue",
    "a-calendar-hold": "The meeting is moved to 3 pm and the room is booked. I'll hold the 4 pm slot as a backup.",
    "a-meeting-held": "We'll hold the review meeting on Tuesday at ten; the agenda is in the invitation.",
    "our-wait-in-a-quoted-draft": "Here is the reply for you to send:\n\n> We're still waiting on the venue, so the time is not "
                                  "fixed yet.",
    "a-thing-waited-on": "I'd add the delivery date to the list of things we're waiting on from the printer.",
    "a-wait-refused": "I will not wait for the second review: the first one covered the change, so I merged.",
    "continue-to-support": "We will continue to support the old flag until the next major version.",
    "someone-elses-wait": "The reviewer is still waiting for access to the staging site; I asked the administrator to grant it.",
    "a-past-wait": "I was waiting on the lock for nine seconds in the trace, which explains the timeout.",
    "ends-with-a-question": "I'm waiting for the build to finish. Should I keep polling it or stop here?",
}
# Passed before the rebuild, as the review's nine did.
MORE_OWN_WAIT = {
    "now-waiting-on": "The pull request is open and I'm now waiting on CI.",
    "we-are-still-waiting": "We are still waiting for the vendor's signed contract.",
    "hold-until": "I pushed the fix. I'll hold the merge until the second reviewer signs off.",
    "once-green-i-merge": "Once CI is green, I'll merge.",
    "report-back-when": "The benchmark is running in the other terminal. I'll report back when the run ends.",
    "proceed-as-soon-as": "We'll proceed as soon as legal returns the redlines.",
    "a-bold-status-label": "Deployed to staging.\n\n**Status:** waiting for the smoke tests to pass.",
    "awaiting": "Awaiting the reviewer's verdict on the second draft.",
    "after-a-dash": "The draft is with the editor — still waiting on her notes.",
    "check-back-after": "I'll check back after the DNS change propagates.",
    "you-in-the-next-clause": "I'm waiting for the build; you can read the draft in the meantime.",
    "your-colleague": "I'll follow up once the vendor replies to your colleague's question.",
    "pick-this-back-up": "I'll pick this back up when the upstream fix is released.",
    "your-settings-in-the-next-clause": "We're awaiting the registrar's confirmation; your domain settings are unchanged.",
    "be-waiting": "I'll be waiting for the vendor's reply to the security questionnaire.",
    "in-bold": "**Waiting on the second reviewer.** Nothing else is open.",
    "when-it-completes-i-resume": "When the export completes, I'll resume the import from row 40,001.",
    "have-to-wait": "I'll have to wait for the registrar before the domain can move.",
    "let-you-know-when": "The tests are running in the background. I'll let you know when they pass.",
    "now-waiting": "The pull request is open. Now waiting on CI.",
    "come-back-once": "I'll come back to this once the vendor replies.",
    "after-an-arrow": "The branch is rebased and pushed.\n→ Waiting on the release checks before I tag.",
}
# Sent back before the rebuild too.
STILL_OWN_WAIT = {
    "wait-until": "I will wait until the nightly export completes, then rebuild the index.",
    "a-numbered-item": "1. The branch is rebased.\n2. Waiting on the integration suite before I tag the release.",
    "you-as-the-one-told": "I'm waiting for the migration to finish so I can send you the row counts.",
    "your-notes": "I'm waiting for the vendor's reply, and your notes from this morning are already in the draft.",
    "a-list-of-others-moves": "Waiting on:\n- CI on the release branch\n- the second reviewer's verdict",
    "what-i-wait-for": "What I'm waiting for is the registrar's confirmation.",
    "the-answer-to-your-message": "I passed it on, and I'm waiting for the peer session to answer your message.",
}


def _cases(*groups):
    return [pytest.param(reply, id=name) for group in groups for name, reply in group.items()]


def _sent_back(reply, config=None, session="S1"):
    return reply_check.check({"last_assistant_message": reply, "session_id": session}, config or {})


@pytest.mark.parametrize("reply", _cases(NO_WATCHER_NEEDED))
def test_the_reviews_replies_that_need_no_watcher_pass(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(OWN_WAIT))
def test_the_reviews_unarmed_waits_are_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(MORE_NO_WATCHER, STILL_NO_WATCHER))
def test_an_explanation_a_status_report_or_the_principals_move_needs_no_watcher(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(MORE_OWN_WAIT, STILL_OWN_WAIT))
def test_the_sessions_own_wait_is_sent_back_in_each_of_its_forms(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


def test_the_principals_move_exempts_only_the_clause_it_stands_in():
    assert _sent_back("I'm waiting for your review of the second draft.") is None
    assert _sent_back("I'm waiting for the second reviewer. Your review of the first draft is filed.")
    assert _sent_back("I'll continue once you send the second file.") is None
    assert _sent_back("I'll continue once the second file arrives; you sent the first this morning.")
    assert _sent_back("Waiting on a yes from you.") is None
    assert _sent_back("Waiting on the bank.\nA yes from you is already on file.")


def test_a_configured_phrase_is_judged_in_its_own_clause():
    config = {"wait_phrases": ["standing by"]}
    assert _sent_back("Standing by for the vendor.") is None                          # not a built-in form
    assert "standing by" in _sent_back("Standing by for the vendor.", config)
    assert _sent_back("Standing by for the vendor. You can review the draft meanwhile.", config)
    assert _sent_back("Standing by until you send the code.", config) is None
    assert _sent_back(OWN_WAIT["W08"], {"wait_phrases": None})                        # a null list is no list, not an error


def test_a_live_wait_and_a_reply_already_sent_back_once_still_pass(isolated_home):
    from synthesis import wait
    reply = OWN_WAIT["W08"]
    assert _sent_back(reply)
    assert reply_check.check({"last_assistant_message": reply, "session_id": "S1", "stop_hook_active": True}, {}) is None
    wait.record("S1", "the reviewer's answer", time.time() + 600, pid=os.getpid())
    assert _sent_back(reply) is None
    assert _sent_back(reply, session="S2")                                            # another session's watcher is not this one's


# --- review round 2 of 5.8.0 (2026-11-12) --------------------------------------------------------------------------
# A second fresh pair of lists found 6 of 32 replies that need no watcher sent back and 5 of 20 unarmed waits passed.
# Each finding is fixed as a class of grammar. The R2 ids are the review's; every other reply is written fresh for
# these tests, as an agent or a person would end a turn, and none is taken from the review or from the lists above.

# Finding 3 of the review: ordinary grammar between the subject and the verb, and a subject left out.
R2_GRAMMAR_REVIEW = {
    "R2-W11": "I'll continue to wait until the remote build completes.",
    "R2-W12": "We're currently still waiting for the hosting provider to answer.",
    "R2-W13": "I'll then resume once the replication job ends.",
}
GRAMMAR_OWN_WAIT = {
    "keep-waiting": "I'll keep waiting until the nightly backup finishes.",
    "two-adverbs-we-are": "We are currently just waiting on the certificate authority.",
    "an-ly-adverb-before-resume": "I'll simply resume when the indexer catches up.",
    "going-to-wait": "I'm going to wait for the load test to finish before I write the summary.",
    "and-will-merge": "I pushed the branch and will merge once the checks are green.",
    "no-subject-will-report": "Will report back when the export has been written.",
    "need-to-wait": "I need to wait for the package registry to publish the new version.",
    "then-be-able-to-proceed": "We'll then be able to proceed after the database has been restored.",
    "and-am-now-waiting": "I've opened the pull request and am now waiting on the linter.",
    "at-this-point-only": "At this point I'm only waiting for the mirror to sync.",
    "still-have-to-wait": "We will still have to wait for the app store's approval of the build.",
    "go-ahead-and-finish": "I'll go ahead and finish the migration as soon as the snapshot is taken.",
    "still-just-waiting": "Still just waiting for the container image to build.",
    "stuck-waiting": "I'm stuck waiting on the upstream mirror.",
}
GRAMMAR_NO_WATCHER = {
    "a-wait-declined": "I won't wait for the nightly run; the unit tests cover this change.",
    "software-that-will-resume": "The worker sleeps and will resume once the queue has items.",
    "advice-to-wait": "I'd wait for the vendor's patch before upgrading; the workaround is fragile.",
    "no-longer-have-to-wait": "We no longer have to wait for the cache to warm, because the index is built at deploy time.",
    "continue-to-publish": "We will continue to publish the old feed until the end of March.",
    "a-script-that-waits": "The script waits for the port to open and then runs the migrations.",
    "did-not-need-to-wait": "I did not need to wait for the full suite: the failing test ran in isolation.",
}


@pytest.mark.parametrize("reply", _cases(R2_GRAMMAR_REVIEW, GRAMMAR_OWN_WAIT))
def test_a_wait_is_read_through_adverbs_helping_verbs_and_a_subject_left_out(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(GRAMMAR_NO_WATCHER))
def test_a_wait_refused_advised_or_done_by_software_is_no_announcement(reply):
    assert _sent_back(reply) is None


# Finding 4 of the review: "your code" and "your review" name what belongs to the principal, not what they do next.
R2_OWNERSHIP_REVIEW = {
    "R2-W14": "I'm waiting for your code to compile on the remote builder.",
    "R2-W20": "I'm still waiting for the service to answer your review bot.",
}
THEIR_THING_SOFTWARE_ACTS = {
    "approval-workflow": "I'm waiting for your approval workflow to finish its run.",
    "answer-file": "I'll continue once the registrar processes your answer file.",
    "review-request": "We're waiting on the scanner to clear your review request.",
    "go-the-language": "I'm waiting for your Go tests to pass on the build farm.",
    "code-that-compiles": "I'll resume when your code compiles on the second runner.",
    "decision-log": "I'm waiting for the sync job to pick up your decision log.",
    "per-your-instructions": "I'm waiting for CI to finish, per your instructions.",
    "confirmation-token": "I'll merge once the pipeline accepts your confirmation token.",
    "a-reply-already-sent": "Waiting for the mail server to deliver your reply to the vendor.",
    "code-changes": "I'm waiting for your code changes to deploy to staging.",
    "as-you-want": "I'll wait for the build as you want, then tag it.",
}
THEIR_ACT_AWAITED = {
    "approval-to-merge": "I'm waiting for your approval to merge the branch.",
    "until-sign-off-arrives": "I'll hold the tag until your sign-off arrives.",
    "decision-then-a-comma": "We're waiting on your decision, not on anything technical.",
    "once-i-have-your-answer": "I'll continue once I have your answer on the venue.",
    "awaiting-your-call": "Awaiting your call on the headline.",
    "review-before-i-publish": "I'm waiting for your review before I publish the page.",
    "approval-code": "I'm waiting for your approval code.",
    "when-your-review-is-in": "I'll merge when your review is in.",
    "your-edits": "I'm waiting for your edits to the second section.",
    "your-signature": "I'll wait for your signature on the contract.",
}


@pytest.mark.parametrize("reply", _cases(R2_OWNERSHIP_REVIEW, THEIR_THING_SOFTWARE_ACTS))
def test_a_thing_of_the_principals_that_software_acts_on_is_the_sessions_own_wait(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(THEIR_ACT_AWAITED))
def test_an_act_of_the_principals_that_is_what_is_awaited_needs_no_watcher(reply):
    assert _sent_back(reply) is None


# Finding 5 of the review: "Waiting for X" as the subject of a sentence explains; it announces nothing.
R2_SUBJECT_REVIEW = {
    "R2-N03": "Waiting for a database lock blocks a request thread, so the timeout belongs in the client.",
    "R2-N04": "Waiting for the background import to release its lock is expected during shutdown.",
}
A_WAIT_AS_THE_SUBJECT = {
    "adds": "Waiting on the DNS lookup adds forty milliseconds to every cold request.",
    "stalled-after-an-infinitive": "Waiting for the garbage collector to finish stalled the benchmark twice, so I pinned the heap "
                                   "size.",
    "never-times-out": "Waiting for user input never times out in this mode, which is why the job looked hung.",
    "awaiting-makes": "Awaiting each promise in a loop makes the requests run one after another.",
    "is-what-made": "Waiting on a full table scan is what made the report slow; the new index removes it.",
    "until-takes": "Waiting until the cache is warm takes about two minutes on a cold start.",
    "costs-after-a-colon": "The trace is clear: waiting for the connection pool costs more than the query itself.",
    "would-hide": "Waiting for the retry budget to drain would hide the real failure.",
    "is-not-the-problem": "Waiting on the mutex isn't the problem; the lock is held across a network call.",
    "guarantees": "Waiting for every shard to acknowledge the write guarantees consistency but doubles the latency.",
}
A_WAIT_THAT_OPENS_A_CLAUSE = {
    "a-clause-after-confirm": "Waiting for the reviewer to confirm the fix is right.",
    "a-relative-clause-without-that": "Waiting on the checks the release needs before I tag.",
    "so-the-report-can-run": "Waiting for the migration to finish so the report can run.",
    "that-are-still-in-flight": "Waiting on the two deploys that are still in flight.",
    "which-are-due": "Still waiting for the vendor's logs, which are due today.",
    "waiting-to-hear": "Waiting to hear back from the registrar about the transfer.",
    "holding-until": "Holding the merge until the security scan is done.",
}


@pytest.mark.parametrize("reply", _cases(R2_SUBJECT_REVIEW, A_WAIT_AS_THE_SUBJECT))
def test_waiting_as_the_subject_of_a_sentence_is_an_explanation(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(A_WAIT_THAT_OPENS_A_CLAUSE))
def test_a_clause_that_opens_with_the_wait_and_has_a_verb_further_on_is_still_an_announcement(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# Finding 6 of the review: the principal's move may stand before the words of the wait, in the same clause.
R2_MOVE_FIRST_REVIEW = {
    "R2-N13": "Until you choose the venue, I'll wait.",
    "R2-N14": "Your answer is the only thing I'm awaiting.",
}
THEIR_MOVE_STATED_FIRST = {
    "once-you-have-signed": "Once you've signed the form, I'll wait for the bank's confirmation and file both.",
    "go-ahead-is-what-we-await": "Your go-ahead is what we're still awaiting.",
    "until-you-tell-me-i-hold": "Until you tell me which region to use, I'll hold.",
    "when-you-reply": "When you reply with the date, I'll be waiting with the draft ready.",
    "the-code-from-you": "The approval code from you is the last thing I'm awaiting.",
    "after-you-approve": "After you approve the budget, I'll wait for the vendor's invoice.",
    "it-is-your-decision": "It's your decision that I'm awaiting.",
    "whichever-you-pick": "Whichever date you pick is the one I'll wait for.",
    "until-your-review-comes-back": "Until your review comes back, I'll wait.",
}
THEIR_PAST_MOVE_STATED_FIRST = {
    "review-filed-and-waiting": "Your review is filed and I'm now waiting on the deploy pipeline.",
    "with-your-go-ahead": "With your go-ahead in hand, I started the migration and I'm waiting for it to finish.",
    "after-you-approved": "After you approved the plan this morning, I kicked off the rebuild and I'm waiting for it to complete.",
    "per-your-instructions-first": "Per your instructions, I'll wait for the nightly export before I rebuild the index.",
    "applied-your-feedback": "I applied your feedback, and I'm waiting for the preview build.",
    "until-the-vendor-i-hold": "Until the vendor replies, I'll hold the release.",
    "you-approved-so": "You approved the change, so I'll merge once the checks pass.",
}


@pytest.mark.parametrize("reply", _cases(R2_MOVE_FIRST_REVIEW, THEIR_MOVE_STATED_FIRST))
def test_the_principals_move_stated_before_the_wait_needs_no_watcher(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(THEIR_PAST_MOVE_STATED_FIRST))
def test_what_the_principal_already_did_stated_before_the_wait_exempts_nothing(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# Finding 7 of the review: an example in single quotes or in a tilde fence is quoted text, not the session's words.
R2_QUOTED_REVIEW = {
    "R2-N19": "The draft says 'We are waiting for the caterer's estimate.' You can send it yourself.",
    "R2-N23": "The documented log example is:\n~~~text\nWe are waiting for the venue's deposit receipt.\n~~~",
}
A_WAIT_THAT_IS_ONLY_QUOTED = {
    "single-quotes": "I changed the status line from 'We'll proceed once the audit closes' to a plain date.",
    "curly-single-quotes": "The banner now reads ‘We’re still waiting on the printer’s proof’ until the order ships.",
    "double-quotes": "Her last message was \"I'm waiting for the courier to arrive\", which I logged in the thread notes.",
    "curly-double-quotes": "The template opens with “Awaiting the client’s countersignature” and then lists the open items.",
    "a-four-backtick-fence": "The log line you asked about:\n````\nworker-2: waiting for the lease to expire\n````\nIt is printed "
                             "once per retry.",
    "a-tilde-fence": "Here is the commit message I used:\n~~~\nWaiting on the upstream fix, so pin the old version.\n~~~\nThe pin "
                     "is in the lockfile.",
    "a-block-quote": "The vendor's note, for your records:\n> We will resume once the customs hold is lifted.\nNothing is needed "
                     "from you today.",
    "inline-code": "The spinner text is `Waiting for the build…` and it now clears when the task ends.",
    "an-indented-fence-with-a-language": "The handler prints:\n\n   ```python\n   print(\"We're waiting for the leader election to "
                                         "finish\")\n   ```\n\nand then exits.",
    "single-quotes-around-a-plural-possessive": "The old copy ('We'll follow up when the reviewers' comments arrive') is gone "
                                                "from the page.",
    "a-quoted-label": "The checklist item 'awaiting sign-off' is now ticked for all three tickets.",
    "two-quoted-sentences": "The thread holds \"I'm waiting on legal.\" and then \"We'll proceed after the board meets.\" a day "
                            "later.",
}
A_WAIT_BESIDE_QUOTED_WORDS = {
    "a-name-in-code-ends-the-clause": "I'm still waiting on `integration-tests`.",
    "a-name-in-single-quotes": "I'll merge once the job named 'release-gate' turns green.",
    "a-name-in-double-quotes": "Waiting for \"deploy-prod\" to finish before I announce it.",
    "plural-possessives-are-no-quotes": "The vendors' portal is down, so I'm waiting for the reviewers' sign-off by email.",
    "apostrophes-then-a-quoted-flag": "It's the registrar's turn; I'm waiting for the 'pending transfer' flag to clear.",
    "names-in-a-fence-after-a-colon": "I'm waiting on:\n```\nci/build\nci/lint\n```",
}


@pytest.mark.parametrize("reply", _cases(R2_QUOTED_REVIEW, A_WAIT_THAT_IS_ONLY_QUOTED))
def test_a_wait_inside_quotation_marks_a_fence_or_a_quoted_line_is_not_the_sessions(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(A_WAIT_BESIDE_QUOTED_WORDS))
def test_quoted_words_beside_the_sessions_own_wait_do_not_hide_it(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# A second pair of lists, written without looking at the patterns after the five classes were fixed, as the review
# writes its own: every reply is kept, whatever the check made of it. Two were sent back needlessly, each a class of
# its own: the thing awaited is "that" or "it" and stands in the sentence before, or it is a question the principal
# answers ("which of the dates works for you").
BLIND_NO_WATCHER = {
    "BN01": 'The uploader retries three times and then waits for the operator to press Resume.',
    "BN02": 'Nothing is merged until both checks have passed; that rule is in the branch settings.',
    "BN03": 'The export was held until the audit finished last week, which is why the numbers are late.',
    "BN04": 'We were waiting on the certificate for two days in March; the renewal is automatic now.',
    "BN05": "I'm not waiting on anything: the release is tagged and the notes are published.",
    "BN06": "Once it's approved by you, I'll merge and tag.",
    "BN07": "I'll continue as soon as I hear from you.",
    "BN08": "I'll hold off on the email until you've read the draft.",
    "BN09": "We'll wait for your word before we touch the production database.",
    "BN10": "I'm waiting for you to choose between the two layouts.",
    "BN11": "I'll proceed when you give me the go-ahead.",
    "BN12": 'Waiting for a slow disk is the usual reason this test flakes.',
    "BN13": 'Waiting on the scheduler can add a full minute, so I raised the timeout.',
    "BN14": 'Awaiting a response from a dead peer hangs the whole pool, which the new heartbeat prevents.',
    "BN15": 'The fix is simple: waiting for the socket to drain was never needed.',
    "BN16": 'Polling is cheaper here because waiting on the webhook means keeping a public endpoint.',
    "BN17": "The onboarding email says 'We will let you know when your account is ready', which I left unchanged.",
    "BN18": 'Her reply reads: "We\'re waiting for the bank to release the funds." I filed it under the vendor thread.',
    "BN19": 'The README example is:\n```bash\n# waiting for the database\nuntil pg_isready; do sleep 1; done\n```\nI did not '
            'change it.',
    "BN20": 'The CI log shows:\n~~~\nWaiting for runner to come online...\n~~~\nand the job started nine seconds later.',
    "BN21": 'I quoted the vendor in the summary:\n\n> We are still waiting on customs and will ship once the hold '
            'clears.\n\nThe rest of the summary is mine.',
    "BN22": 'The status page said “We’ll resume service when the provider recovers” for about an hour.',
    "BN23": "The function is named `wait_until_ready`, and I'll keep that name.",
    "BN24": "Your approval is the only thing left; I'm waiting on that.",
    "BN25": "I'm waiting on your answer to the pricing question.",
    "BN26": "As soon as you confirm the address, I'll send the order.",
    "BN27": "I'll wait to hear which of the three dates works for you.",
    "BN28": 'The deploy is done. I waited for the health checks to pass before reporting.',
    "BN29": 'I had to wait for the lock twice, but both migrations are applied now.',
    "BN30": 'If the job fails again, the runbook says to wait for the on-call engineer.',
    "BN31": 'I recommend waiting until the vendor publishes the fix rather than patching it ourselves.',
    "BN32": 'Should I wait for the nightly build, or ship the hotfix now?',
    "BN33": "The queue drains when the consumer catches up, and the alert clears once it's empty.",
    "BN34": "We'll continue to use the old endpoint until the client is updated next quarter.",
    "BN35": "I'll resume the migration when you say so.",
    "BN36": 'The meeting is confirmed, and the room is held until noon.',
    "BN37": "You'll get an email once the transfer completes; nothing more is needed from me.",
    "BN38": 'The tests wait for the server to start, which takes about four seconds.',
    "BN39": "I'll pick this up again whenever you want.",
    "BN40": 'I am awaiting your instructions on the second contract.',
    "BN41": 'The session will be woken when a message arrives, because a watcher is armed for it.',
    "BN42": "I'll be here when you're back.",
}
BLIND_OWN_WAIT = {
    "BW01": "I'm just waiting on the build now.",
    "BW02": "We are still awaiting the registrar's response.",
    "BW03": 'I will then continue once the artifact has been uploaded.',
    "BW04": "I'll hold off on merging until the scan completes.",
    "BW05": "We'll get back to this when the provider answers the ticket.",
    "BW06": "I'm currently waiting for the data import to complete before running the report.",
    "BW07": "Once the DNS record propagates, I'll finish the setup.",
    "BW08": "After the review bot posts its verdict, we'll proceed.",
    "BW09": "I'll check back when the batch job is done.",
    "BW10": "I'm waiting until the rate limit resets.",
    "BW11": "Still waiting on the peer session's answer.",
    "BW12": "Now awaiting the second approver on the vendor's side.",
    "BW13": "I'll follow up as soon as the courier updates the tracking page.",
    "BW14": "The branch is pushed; I'll merge when the pipeline goes green.",
    "BW15": 'I am waiting for the certificate to be issued by the authority.',
    "BW16": "We're waiting on your hosting provider to lift the block.",
    "BW17": "I'm waiting for the migration on your staging server to finish.",
    "BW18": "I'll let you know once your build passes.",
    "BW19": "I'm waiting for your CI to finish before I rebase.",
    "BW20": "I'll resume when your domain's DNS has propagated.",
    "BW21": "I'm waiting for the vendor to answer your question about the invoice.",
    "BW22": "I've kicked off the export and am waiting for it to finish.",
    "BW23": "I'll wait until the queue is empty, then restart the worker.",
    "BW24": 'Will merge once the required checks pass.',
    "BW25": "I'm going to hold the release until the canary has run for an hour.",
    "BW26": "I'll continue after the other session confirms the handoff.",
    "BW27": "I'm waiting to see whether the retry succeeds.",
    "BW28": "We'll report back after the load test finishes tonight.",
    "BW29": "The tests are running; I'm waiting for them.",
    "BW30": "I'll come back to this after the upstream release.",
    "BW31": "Then I'll wait for the reviewer's comments.",
    "BW32": "I'm now only waiting for the mirror, which usually takes ten minutes.",
    "BW33": 'Pushed. Waiting for CI.',
    "BW34": "I'll finish the write-up when the numbers come in from the benchmark.",
    "BW35": "I'm waiting on a reply from the vendor's support desk.",
}
THEIR_MOVE_IN_THE_SENTENCE_BEFORE = {
    "waiting-for-that": "The only open item is your sign-off on the budget. I'm waiting for that.",
    "waiting-on-it": "I need the approval code from you. Waiting on it.",
    "i-will-wait": "Send the signed copy whenever you can. I'll wait.",
    "until-then-i-hold": "I need your decision on the venue first. Until then, I'll hold.",
    "what-you-think": "I'm waiting to hear what you think of the second option.",
    "whether-you-want": "I'll wait to see whether you want the long version or the short one.",
    "how-you-would-like": "Waiting to hear how you'd like the invoice split.",
}
ANOTHERS_MOVE_IN_THE_SENTENCE_BEFORE = {
    "the-deploy-then-it": "The deploy is running; I'm waiting on it.",
    "it-is-the-pipeline": "Your review is filed. The pipeline is running and I'm waiting on it.",
    "waiting-for-theirs": "I sent your reply to the vendor; now I'm waiting for theirs.",
    "whether-the-vendor-can": "I'm waiting to hear whether the vendor can deliver by Friday.",
    "how-the-canary-behaves": "I'll wait to see how the canary behaves on your account's traffic.",
    "the-build-then-i-wait": "The build is running. I'll wait.",
}


@pytest.mark.parametrize("reply", _cases(BLIND_NO_WATCHER, THEIR_MOVE_IN_THE_SENTENCE_BEFORE))
def test_a_second_fresh_list_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(BLIND_OWN_WAIT, ANOTHERS_MOVE_IN_THE_SENTENCE_BEFORE))
def test_a_second_fresh_list_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# A third pair of lists written the same way, in the voice of an assistant that handles mail, travel and code. Four
# were wrong: a thing only the principal can supply ("your headcount"), the turn handed over in so many words ("it is
# your move"), a verb of reporting ("I'll confirm the booking once"), and a longer object between "pick" and "up".
BLIND3_NO_WATCHER = {
    "CN01": 'The hotel has not confirmed the late checkout; they said they would email you directly.',
    "CN02": 'I drafted the reply and left it in your drafts folder. It goes out when you press send.',
    "CN03": 'Your passport renewal is still being processed, and the tracking page says to wait six weeks.',
    "CN04": 'The caterer is waiting on the final headcount, which you said you would send on Friday.',
    "CN05": "I'm waiting on your headcount before I confirm the caterer.",
    "CN06": 'I will hold both table options until you tell me which you prefer.',
    "CN07": "We're waiting for you to sign the lease; the landlord has already signed.",
    "CN08": "Once you forward the receipt, I'll file the expense claim.",
    "CN09": "I've paused here. I'll wait for your reply.",
    "CN10": "I'll stop here and wait for your decision on the refund.",
    "CN11": "Tell me when you have landed and I'll continue from there.",
    "CN12": "I need one thing from you before I book: your loyalty number. I'm waiting on that.",
    "CN13": "The airline's policy is that standby passengers wait until all confirmed passengers have boarded.",
    "CN14": 'Waiting until the last minute to book would cost about two hundred dollars more.',
    "CN15": 'Waiting for the next sale is an option, but the price history shows no dip in October.',
    "CN16": 'The loader shows a spinner while it waits for the first response, then swaps in the table.',
    "CN17": 'The lock is released when the writer finishes, so readers never wait more than a few milliseconds.',
    "CN18": 'The old script waited for a keypress here; I removed that so it can run unattended.',
    "CN19": 'The error message now says "Still waiting for the device to respond" instead of a bare timeout.',
    "CN20": "I renamed the test to 'waits for the worker to drain' so the report reads clearly.",
    "CN21": "The comment in the config reads:\n~~~yaml\n# awaiting the vendor's new endpoint; do not remove\nlegacy_url: "
            'true\n~~~\nI left it in place.',
    "CN22": 'Per the vendor: “We are waiting on parts and will ship when they arrive.” I added that to the order notes.',
    "CN23": "I'll be waiting for your call at three.",
    "CN24": "I'm awaiting your reply to the landlord's counter-offer.",
    "CN25": "It is your move: I'm waiting for the signed form.",
    "CN26": "The moment you approve the budget, I'll place the order.",
    "CN27": "I'll continue the booking as soon as you've chosen a seat.",
    "CN28": "I'm waiting to hear back from you about the Thursday slot.",
    "CN29": 'Do you want me to keep waiting for the cheaper fare, or book now?',
    "CN30": 'No reply from the venue yet. Their office reopens Monday, and nothing needs doing until then.',
    "CN31": 'We have what we need: the vendor replied this morning and the contract is signed.',
    "CN32": 'The report finished while I was waiting, so the numbers below are final.',
    "CN33": "I'm done waiting for the mirror: I switched the build to the primary registry and it passed.",
    "CN34": 'The build no longer waits for the cache; it starts cold in forty seconds.',
    "CN35": "I'll wait for your go before I send anything to the client.",
}
BLIND3_OWN_WAIT = {
    "CW01": "I emailed the venue and I'm waiting for their answer.",
    "CW02": "I'm waiting to hear back from the airline about the refund.",
    "CW03": "I'll confirm the booking once the hotel replies. ",
    "CW04": "I'll come back to you when the visa office responds.",
    "CW05": "We're still awaiting the landlord's countersignature.",
    "CW06": "I'm waiting on the bank to release the hold on your card.",
    "CW07": "I'll proceed with the booking once the fare class reopens.",
    "CW08": "The form is submitted; I'm now waiting for the consulate to schedule the interview.",
    "CW09": "I'm waiting for the tests to finish on your pull request.",
    "CW10": "I'll get back to you after the nightly job has run.",
    "CW11": 'I am still waiting on the vendor for the revised quote.',
    "CW12": "I'll follow up once I hear from the caterer.",
    "CW13": "I'm waiting until the embargo lifts at noon to send the announcement.",
    "CW14": 'Awaiting confirmation from the registrar that the transfer went through.',
    "CW15": "I'll finish the itinerary when the airline releases the schedule.",
    "CW16": 'I will wait for the second reviewer to approve, then merge.',
    "CW17": "We'll resume once the outage at the provider is over.",
    "CW18": "I'm currently waiting for the page to be indexed.",
    "CW19": "I'll check back once the courier has delivered your package.",
    "CW20": "Then I'll wait for the migration to complete and verify the row counts.",
    "CW21": "For the moment I'm waiting on the build queue.",
    "CW22": "I'm waiting for the seller to accept your offer.",
    "CW23": 'Waiting on the insurer; they have your claim form.',
    "CW24": "I'll hold the reservation until the airline confirms the schedule change.",
    "CW25": "I've asked the peer session and am waiting for its reply.",
    "CW26": 'I will let you know when the refund reaches your account.',
    "CW27": "I'll pick the thread back up when the landlord answers.",
    "CW28": "I'm waiting on the vendor's answer to your question.",
}
WHAT_ONLY_THEY_CAN_SUPPLY = {
    "your-dates": "We're waiting for your dates before we hold the room.",
    "once-i-have-your-budget": "I'll book once I have your budget.",
    "over-to-you": "Over to you: I'll wait for the corrected figures.",
    "in-your-court": "The ball is in your court, so I'm waiting for the revised brief.",
    "confirm-once-you-have-read-it": "I'll confirm once you've had a chance to read it.",
}
WHAT_SOFTWARE_DOES_WITH_IT = {
    "numbers-that-sync": "I'm waiting for your numbers to sync from the spreadsheet.",
    "confirm-once-the-supplier": "We'll confirm once the supplier sends the corrected invoice.",
    "update-you-when": "I'll update you when the tracking page changes.",
    "pick-two-threads-back-up": "I'll pick the two open threads back up when the landlord answers.",
}


@pytest.mark.parametrize("reply", _cases(BLIND3_NO_WATCHER, WHAT_ONLY_THEY_CAN_SUPPLY))
def test_a_third_fresh_list_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(BLIND3_OWN_WAIT, WHAT_SOFTWARE_DOES_WITH_IT))
def test_a_third_fresh_list_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# A fourth pair, written as a reviewer who knows the five classes would write it. Six were wrong: a subject's verb
# before a longer object ("explains the first request's latency"), "waiting until" as the subject of "is", the thing
# awaited in front of "awaiting on", "yours", a word between "we're" and "waiting" ("both"), and words between commas
# after "will".
BLIND4_NO_WATCHER = {
    "DN01": 'Waiting for the primary to acknowledge each write is what makes the cluster slow under load.',
    "DN02": "Waiting on a cold cache explains the first request's latency; later requests are fast.",
    "DN03": 'Waiting until every replica agrees is safer, and the design note recommends it.',
    "DN04": 'Awaiting inside the loop serializes the calls, so I gathered them instead.',
    "DN05": 'In the trace, waiting for the mutex accounts for most of the time.',
    "DN06": "The doc's example reads 'I'll resume once the worker's queue drains', and I kept it as written.",
    "DN07": 'The alert text is ‘Still waiting for the replica to catch up’, which matches the runbook.',
    "DN08": 'The reply you asked me to draft says "We\'ll proceed as soon as the contract is signed." Send it when you are'
            ' ready.',
    "DN09": "Sample output from the tool:\n~~~~\nwaiting for lock... acquired\nI'll continue once the index is "
            'rebuilt\n~~~~\nNothing in it is an error.',
    "DN10": 'The hook prints this when it blocks:\n```\nWaiting on approval from the release owner.\n```\nThat text comes '
            'from the config.',
    "DN11": "> I'm waiting for the vendor to confirm.\n\nThat is the line the reviewer objected to; I removed it from the "
            'summary.',
    "DN12": "Until you pick a name, I'll leave the placeholder in.",
    "DN13": "When you've decided on the region, I'll continue with the setup.",
    "DN14": "Your decision on the retention period is all I'm waiting for.",
    "DN15": "Your sign-off is the one thing I'm still awaiting on the release notes.",
    "DN16": "After you send the logo, we'll finish the cover page.",
    "DN17": "The approval is yours to give; I'm waiting for it.",
    "DN18": "I'm waiting for your yes or no on the schema change.",
    "DN19": "I'll hold the invite until your confirmation comes in.",
    "DN20": 'We are waiting on your input about the two pricing tiers.',
    "DN21": 'I am still waiting for your thoughts on the draft, so nothing has been sent.',
    "DN22": "I'm waiting for your review of the migration plan before I run it.",
    "DN23": "I'll merge as soon as you've approved the pull request.",
    "DN24": 'The pipeline waits for manual approval at the deploy stage, which is how the team set it up.',
    "DN25": 'The client library retries and then waits until the server is back.',
    "DN26": 'I waited for the checks before merging, and all of them passed.',
    "DN27": 'Everything is merged. There is nothing left to wait for.',
    "DN28": 'The job is queued behind two others and will start when they finish; no action is needed.',
    "DN29": 'I would hold the release until the audit is done, but that is your call.',
    "DN30": 'We could wait for the next version, or pin the current one today.',
    "DN31": 'Is there anything you want me to wait for before I merge?',
    "DN32": "I'll leave the branch open until you have had a look.",
}
BLIND4_OWN_WAIT = {
    "DW01": "I'm presently waiting on the artifact store to finish replicating.",
    "DW02": "We're both waiting for the staging database to come back.",
    "DW03": "I'll just wait until the scheduled job fires at the top of the hour.",
    "DW04": 'I will, for my part, continue once the fixture data has been regenerated.',
    "DW05": "I'll keep on waiting for the rate limiter to reset.",
    "DW06": "We'll simply proceed after the lock has been released.",
    "DW07": "I shall resume when the vendor's API is reachable again.",
    "DW08": "I'm going to hold the deploy until the error rate has settled.",
    "DW09": "I'll follow up once the ticket is picked up by the platform team.",
    "DW10": "Once the image has been pushed, I'll finish the rollout.",
    "DW11": "When the certificate renews, we'll come back to the redirect.",
    "DW12": "After the backfill completes, I'll report back with the counts.",
    "DW13": "I'm waiting for your tests to finish in CI.",
    "DW14": "I'm waiting for the deploy bot to pick up your approval.",
    "DW15": "I'll continue once your branch has been rebuilt by the pipeline.",
    "DW16": "We're waiting on your registrar to release the domain.",
    "DW17": "I'm waiting for the import of your contacts to complete.",
    "DW18": 'Still waiting on the runner assigned to your project.',
    "DW19": "I'm waiting for the bank to process your payment.",
    "DW20": "I'm waiting on 'build-linux' and 'build-mac' to finish.",
    "DW21": 'I\'ll merge once the check called "license-scan" passes.',
    "DW22": 'Now waiting for `terraform apply` to finish.',
    "DW23": "I'm waiting for the reviewer's second pass, which she said would come today.",
    "DW24": 'Waiting for the sandbox to boot before I rerun the suite.',
    "DW25": 'I started the export a minute ago and am still waiting on it.',
    "DW26": "I'll let you know as soon as the migration is through.",
    "DW27": "We'll get back to the flaky test when the upstream patch lands.",
}
MORE_OF_THE_FOURTH_LISTS_CLASSES = {
    "explains-a-possessive-object": "Waiting on the old index explains last week's slow searches.",
    "until-is-what": "Waiting until the lease expires is what the protocol requires.",
    "awaiting-on-the-budget-line": "Your approval is what I'm awaiting on the budget line.",
    "the-choice-is-yours": "The choice is yours; I'll wait.",
}
MORE_WAITS_OF_THE_FOURTH_LISTS_CLASSES = {
    "we-are-all-waiting": "We're all waiting on the release train to leave.",
    "however-between-commas": "I am, however, still waiting on the vendor.",
    "until-with-a-clause-after-confirms": "Waiting until the vendor confirms the invoice is correct.",
    "holding-until-one-verb": "Holding the tag until the smoke test passes.",
}


@pytest.mark.parametrize("reply", _cases(BLIND4_NO_WATCHER, MORE_OF_THE_FOURTH_LISTS_CLASSES))
def test_a_fourth_fresh_list_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(BLIND4_OWN_WAIT, MORE_WAITS_OF_THE_FOURTH_LISTS_CLASSES))
def test_a_fourth_fresh_list_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# A fifth pair, written by a second agent that was told what the check is for and never saw its code, as the review's
# lists are. Ten were wrong, nine of them waits that passed: a future with any verb and "once" or "as soon as" ("I'll
# send you the comparison as soon as the run finishes"), "when it's done", a clause that opens with "Resuming" or
# "Standing by until", and "I'm holding ... until". One explanation was sent back: "before merging" inside a subject.
INDEPENDENT_NO_WATCHER = {
    "EN01": "Both layouts are in the draft folder. I'll wait for your decision before I touch the stylesheet.",
    "EN02": "Until you choose between the morning and the evening flight, I'll hold off on booking either one.",
    "EN03": 'I am currently still waiting for your answer on the retention period, so the cleanup change stays unmerged.',
    "EN04": 'Will merge once you approve the pull request.',
    "EN05": "I'll continue to wait for your go-ahead before changing anything in production.",
    "EN06": 'I will be able to resume the sign-in as soon as you type the six-digit code from your authenticator app.',
    "EN07": "Once you've pushed your local commits, I can rebase the feature branch on top of them; I can't see them from"
            ' here.',
    "EN08": "We'll hold the invitation until you confirm the guest list.",
    "EN09": "After you review the migration plan, I'll start on the schema changes.",
    "EN10": 'Waiting for your approval of the budget line before I submit the expense report.',
    "EN11": "Your decision on the venue is the only thing I'm waiting for; everything else in the event plan is settled.",
    "EN12": "I'm standing by for the confirmation code that was emailed to you; paste it here and I'll complete the "
            'registration.',
    "EN13": "I'll pick the refactor back up after your answer about whether the legacy endpoint can be removed.",
    "EN14": 'Do you want me to wait for the nightly build before tagging, or tag the release from the current commit?',
    "EN15": "Nothing moves on the contract until you sign page four, so I've left the envelope in draft.",
    "EN16": "When you've decided who should receive the summary, I'll resume and send it.",
    "EN17": "Paused at the payment step: only you can enter the card details, and I'll carry on from the confirmation "
            'page once you have.',
    "EN18": "I'll wait for your answer to the reviewer's question before changing the API.",
    "EN19": "I'll wait for your decision on the vendor's quote; the three options are summarized in the table above.",
    "EN20": 'Holding for your sign-off on the release notes.',
    "EN21": 'Waiting for a lock blocks the worker thread, which is why the second request stalled; I replaced the mutex '
            'with a queue and the test passes.',
    "EN22": 'In this pipeline the deploy stage waits for the test stage to succeed; that ordering is declared in the '
            '`needs` key of the workflow definition.',
    "EN23": "Waiting for DNS propagation is what made yesterday's cutover slow. Every record resolves to the new address "
            'now.',
    "EN24": 'As a general rule, an agent that waits on a long job inside a turn burns context, which is why background '
            'tasks exist. I added that paragraph to the runbook as you asked.',
    "EN25": 'The polling loop continues until the queue is empty, which matches the behaviour you described; the only '
            'thing I changed is the batch size.',
    "EN26": 'For future runs: wait for the green check before merging, because the first two minutes of output are only '
            'cache restores.',
    "EN27": 'Waiting on every reviewer before merging would add about a day per change, so the new policy asks for one '
            'approval. The policy page is updated.',
    "EN28": 'The scheduler holds a job until its dependencies have finished and then releases it to the first free '
            'runner. This patch does not change that behaviour.',
    "EN29": 'Here is how the checkout page behaves: after the customer clicks Pay, the browser waits for the payment '
            'provider to respond and then redirects to the receipt.',
    "EN30": 'I waited for the full test suite to finish; all 412 tests passed and the branch is merged.',
    "EN31": 'Status for your notes: the supplier is still waiting on its bank, which is outside anything I can act on. '
            'The ledger entry is updated and my part is finished.',
    "EN32": 'I did not wait for the nightly build, since this change only touches documentation. It is merged.',
    "EN33": "Earlier I was waiting on the vendor's reply; it arrived at noon and the invoice is reconciled.",
    "EN34": 'There is nothing to wait for: the certificate was issued this morning and the site already serves it.',
    "EN35": 'After the index rebuild finished, I resumed the import and loaded the remaining 2,300 rows. The table is '
            'complete.',
    "EN36": 'Once the airline confirmed the seat change, I updated the itinerary; it now shows 14C on both legs.',
    "EN37": 'The runner\'s last log line reads "waiting for the build to finish", but that message is stale: the run '
            'completed and passed.',
    "EN38": "The vendor's auto-reply says:\n> We are waiting for our finance team to release the payment.\nI saved it to "
            'the thread notes; the reconciliation itself is finished.',
    "EN39": "A reply that should trip the check looks like this:\n```\nI'm waiting for the CI run to finish and will merge "
            'after.\n```\nI added it to the fixtures as a failing case.',
    "EN40": 'The status line now prints `waiting for deploy job...` while the spinner is active. That string is the only '
            'thing I changed.',
    "EN41": 'I added the error text ‘Still waiting on the upstream service’ to the translations for all four languages.',
    "EN42": 'The ticket is titled “Waiting for vendor to confirm delivery date”; I closed it because the delivery arrived'
            ' on Monday.',
    "EN43": 'The docs now show the expected output in a tilde fence:\n~~~\nWaiting for the database to accept '
            'connections...\nReady.\n~~~\nIt matches what the script prints.',
    "EN44": "Your colleague's note in the thread says 'I'll resume once the audit finishes'. I copied it into the meeting"
            ' summary and changed nothing else.',
    "EN45": 'The email template opens with "We will continue as soon as the bank confirms the transfer", which reads '
            'fine, so I left it unchanged.',
}
INDEPENDENT_OWN_WAIT = {
    "EW01": 'I am currently still waiting for the integration tests to finish on the release branch.',
    "EW02": "I'll continue to wait for the export job to complete, then attach the file to the ticket.",
    "EW03": 'The fix is pushed. I will be able to resume once the branch has been rebuilt.',
    "EW04": 'Will merge once the checks pass.',
    "EW05": "We're waiting on the certificate authority to issue the new certificate; the server configuration is ready "
            'for it.',
    "EW06": "I'll send you the comparison as soon as the benchmark run finishes.",
    "EW07": 'Holding off on the release until the security scan comes back clean.',
    "EW08": 'I will pick this up again after the nightly import has run.',
    "EW09": 'Resuming when the index rebuild is done.',
    "EW10": 'Standing by until the container image has been published to the registry.',
    "EW11": "The request is with the vendor. Once their quote arrives, I'll update the renewal sheet.",
    "EW12": 'After the database snapshot has completed, we will proceed with the cutover.',
    "EW13": "I'm waiting for your build to finish before I run the smoke tests.",
    "EW14": "I'll continue once your code has finished compiling.",
    "EW15": 'Waiting for the review bot to answer your review request.',
    "EW16": "I'm holding the announcement until your deployment pipeline reports success.",
    "EW17": 'Waiting for the vendor to reply to your email about the corrected invoice.',
    "EW18": "I'll wait for the reviewer's answer to your question before changing the API.",
    "EW19": 'Waiting for the DNS change to propagate.',
    "EW20": 'Pushed the commit. Waiting for CI.',
    "EW21": "Waiting for the other pipeline's lock on the deploy environment to be released; I'll start the rollout right"
            ' after.',
    "EW22": "You approved the merge, so I'm now waiting for the pipeline to finish.",
    "EW23": "Since you already signed the form, I'm waiting for the supplier to countersign it.",
    "EW24": 'Your approval is recorded; waiting for the deploy job to complete before I close the ticket.',
    "EW25": "You kicked off the build ten minutes ago, and I'm waiting for it to finish before tagging the release.",
    "EW26": 'I\'m waiting for the "nightly-build" job to finish, and then I\'ll publish the package.',
    "EW27": "Will deploy once the 'lint' and 'unit' checks go green.",
    "EW28": "I'll resume once `deploy-prod` completes.",
    "EW29": "The vendor wrote “we will get back to you shortly”, so I'm waiting for their confirmation before I place the"
            ' order.',
    "EW30": "The CI bot commented:\n> Build queued.\nI'm waiting for that build to finish before I merge.",
    "EW31": "The tag push triggered the release workflow:\n```\nrelease  queued  2m ago\n```\nWaiting for it to finish; I'll "
            'upload the artifacts afterwards.',
    "EW32": "As soon as the airline confirms the seat change, I'll finalize the itinerary.",
    "EW33": "I'll request your approval as soon as the staging deploy finishes.",
    "EW34": "Until the migration job finishes I can't verify the row counts; I'll check them when it's done.",
    "EW35": "I've asked the organizer for a new time and am waiting for them to accept before I move the other meetings.",
}
MORE_OF_THE_FIFTH_LISTS_CLASSES = {
    "once-as-one-time": "I'll run the migration once on staging and once on production.",
    "as-soon-as-possible": "I'll update the changelog as soon as possible.",
    "advice-for-later": "We'll want to rotate the key once the audit ends; I added a reminder to the runbook.",
    "once-i-have-read": "I'll have a fuller answer once I've read the vendor's contract.",
    "merging-as-a-subject": "Merging after CI passes is the rule in this repository, so I left the branch protection as it is.",
    "before-signing-in-a-subject": "Waiting on legal before signing was the right call.",
}
MORE_WAITS_OF_THE_FIFTH_LISTS_CLASSES = {
    "i-am-standing-by-until": "I'm standing by until the certificate is issued.",
    "continuing-once": "Continuing once the lock is released.",
    "when-they-are-in": "I'll post the numbers when they're in.",
    "i-am-holding-until": "I'm holding the release until the canary has run for an hour.",
}


@pytest.mark.parametrize("reply", _cases(INDEPENDENT_NO_WATCHER, MORE_OF_THE_FIFTH_LISTS_CLASSES))
def test_a_list_written_without_sight_of_the_code_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(INDEPENDENT_OWN_WAIT, MORE_WAITS_OF_THE_FIFTH_LISTS_CLASSES))
def test_a_list_written_without_sight_of_the_code_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# The edges of the rules the fifth list added: a time or a noun after "until" or "after" with a judgment on it, and a
# future that only reports how something behaves.
A_JUDGMENT_OR_A_DESCRIPTION = {
    "merging-after-review-is-standard": "Merging after review is standard practice here.",
    "until-friday-is-risky": "Waiting until Friday is risky, so I booked the earlier slot.",
    "note-that-once": "I'll note in the runbook that once the cache is warm the page loads in 200 ms.",
    "document-what-happens-once": "I'll document what happens once the token expires.",
    "explain-how-as-soon-as": "I'll explain how the job resumes as soon as the lock clears.",
    "the-bot-merges-then-i-close": "Once the build is green, the bot merges it, and I'll close the ticket then.",
    "once-per-run": "I'll use the staging key once per run.",
    "until-tomorrow-is-fine": "Waiting until tomorrow is fine with the vendor, who confirmed by email.",
    "continuing-to-poll": "Continuing to poll after the deploy is harmless, so I left the loop in.",
}
AN_EVENT_THAT_IS_STILL_TO_COME = {
    "resuming-after-it-is-done": "Resuming after the rebuild is done.",
    "until-the-cache-is-warm": "Waiting until the cache is warm.",
    "ask-again-once": "I'll ask the vendor again once the contract is signed.",
    "until-the-change-is-live": "Waiting until the registrar's change is live.",
    "merging-once": "Merging once the last check is green.",
    "rerun-as-soon-as": "I'll rerun the suite as soon as the fix has landed upstream.",
}


@pytest.mark.parametrize("reply", _cases(A_JUDGMENT_OR_A_DESCRIPTION))
def test_a_judgment_on_a_wait_or_a_description_of_what_happens_once_is_no_announcement(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(AN_EVENT_THAT_IS_STILL_TO_COME))
def test_a_wait_until_a_state_that_is_still_to_come_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason
