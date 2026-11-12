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
