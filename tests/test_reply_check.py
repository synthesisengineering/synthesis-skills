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
    "awaiting": "Awaiting the reviewer's verdict on the second draft.",
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
    config = {"wait_phrases": ["parked"]}
    assert _sent_back("Parked for the vendor.") is None                               # not a built-in form
    assert "parked" in _sent_back("Parked for the vendor.", config)
    assert _sent_back("Parked for the vendor. You can review the draft meanwhile.", config)
    assert _sent_back("Parked until you send the code.", config) is None
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


# A second list from an agent that never saw the code, across other kinds of work. Nine were wrong. Sent back needlessly:
# a subject judged in the passive ("resuming after a crash is handled by"), a subject that holds "before the debrief", a
# short wait after a request ("Send me the code ... I'll wait"), after a question, and "waiting on that before I ...".
# Passed: the event in front with any verb after "when" or "after" ("when the bank confirms, I will record"), and
# "after it does".
INDEPENDENT2_NO_WATCHER = {
    "FN01": 'Waiting for the cache to warm is what makes the first request slow, not the query itself.',
    "FN02": 'Resuming after a crash is handled by the checkpoint file, so the loader never reprocesses a partition twice.',
    "FN03": 'In the onboarding flow, the app holds the splash screen until the profile request returns, and then it '
            'routes to the home tab.',
    "FN04": 'Escrow works like this: the title company holds the deposit until both parties sign, and releases it when '
            'the deed is recorded.',
    "FN05": 'Waiting until every interviewer has submitted a scorecard before the debrief is a common way to reduce '
            "anchoring, and I'd keep that rule.",
    "FN06": "Waiting for the supplier's reply would have cost another day, so I ordered the standard part instead and the"
            ' repair is booked for Friday.',
    "FN07": 'The backfill finished after I waited out the warehouse maintenance window; all 31 partitions loaded and the '
            'row counts match.',
    "FN08": 'After the recruiter replied this morning, I booked the three interviews; they are on the calendar for '
            'Thursday.',
    "FN09": 'Status: the queue is empty, no jobs are waiting, and the last batch finished at 09:40 with zero errors.',
    "FN10": 'I held the release until the security scan came back clean, then published version 2.4.1; nothing is '
            'outstanding.',
    "FN11": 'When the certificate renews next spring, remember to restart the proxy so it picks up the new file.',
    "FN12": "I'd recommend waiting until the reindex completes before you cut traffic over; switching earlier risks stale"
            ' search results.',
    "FN13": "After the refund posts, you'll want to check that the statement shows the full amount, since partial credits"
            ' are common with disputes like this one.',
    "FN14": 'For future runs, you could trigger the export once the upstream job has finished instead of at a fixed time;'
            ' that would avoid the partial files we saw today.',
    "FN15": 'When the preprint is updated, you should re-check the sample size in table 2, since the authors said it '
            'would change.',
    "FN16": 'The deploy log\'s last line reads "waiting for rollout to finish, will retry in 30s"; that message is '
            'routine, and the deploy itself completed at 14:02.',
    "FN17": "The repair shop's auto-reply says 'we are waiting on parts and will call once they arrive'. I saved it in "
            'the appliance folder.',
    "FN18": 'A line you could use in the status update: “We’re waiting on the vendor’s patch and will redeploy as soon as'
            ' it ships.”',
    "FN19": 'I added this comment above the polling loop:\n```python\n# wait until the job finishes, then fetch the '
            'results\n```\nThe change is committed on the branch.',
    "FN20": "Here is the template for the on-call handoff note:\n~~~\nWaiting for the batch to finish; I'll restart the "
            'workers when it does.\n~~~\nAdjust the wording to suit your team.',
    "FN21": "The hiring manager's note on the ticket says:\n> I'm waiting for the background check to clear and will send "
            'the offer once it does.\nI copied it into the candidate summary.',
    "FN22": 'On startup the service prints `waiting for database, will continue once it is ready`, which is expected and '
            'not an error.',
    "FN23": 'The methods section states, "we waited until the cultures reached confluence and then applied the '
            'treatment"; I added that detail to the comparison table.',
    "FN24": "The bookkeeper's last email says 'I'll wait for the bank's confirmation and close the month when it "
            "arrives', and I filed it under March.",
    "FN25": "I'll continue with the literature search once you confirm which years to cover.",
    "FN26": "Send me the six-digit code from your authenticator app and I'll finish the sign-in. I'll wait.",
    "FN27": "The transfer needs your approval in the banking app; I'm waiting on that before I record the payment.",
    "FN28": "Once your review of the offer letter is done, I'll send it to the candidate.",
    "FN29": 'Holding the email to the contractor until you tell me which of the two quotes you prefer.',
    "FN30": "As soon as you pick a date for the dinner, I'll book the table and send the invitations.",
    "FN31": "Waiting for your decision on the two chart styles; I'll finalize the figures after you choose.",
    "FN32": "The pull request description is drafted, and I won't open it until you've read it over. When you approve, "
            "I'll push the branch and open it.",
    "FN33": "Tell me when you've signed the lease and I'll set up the utilities transfer.",
    "FN34": 'I am, at the moment, paused on the release notes until your answer about the version number comes in.',
    "FN35": "We'll be able to continue the budget review after you find the two cash receipts; only you have those.",
    "FN36": "I'll keep waiting for your go-ahead before touching the production database, and I'll start the cutover when"
            ' you give it.',
    "FN37": "You'll need to sign the engagement letter first, and I'll hold the filing until you have.",
    "FN38": "I need the door code that only you have; once I have it, I'll schedule the cleaner.",
    "FN39": "Which of the three caterers would you like me to book? I'm waiting on that and nothing else.",
    "FN40": "The sync job runs once a day at 02:00 UTC, so today's dashboard includes orders through yesterday only.",
    "FN41": 'Once the token expires, the client requests a new one automatically, so no change was needed in the login '
            'code.',
    "FN42": 'Company policy is that an expense is reimbursed when a receipt is attached, which is why the two claims '
            'without receipts were rejected.',
    "FN43": 'As soon as the queue drains, the autoscaler removes the extra workers; that explains the drop in node count '
            'at 14:10.',
    "FN44": "When a candidate reschedules, the booking tool frees the original slot immediately, so the panel's calendars"
            ' are already correct.',
    "FN45": 'I ran the import once more after fixing the date format, and all 212 rows loaded.',
}
INDEPENDENT2_OWN_WAIT = {
    "FW01": "I'll rerun the integration suite once the staging deploy finishes.",
    "FW02": "Once the nightly export lands in the bucket, I'll load it and rebuild the revenue table.",
    "FW03": "Now that you've pushed the fix, I am waiting for CI to finish on the branch and will tag the release when it"
            ' passes.',
    "FW04": "We're holding until the certificate is issued by the certificate authority, then we'll switch the load "
            'balancer over.',
    "FW05": 'Waiting on the app store review to come back; will publish the release notes as soon as the build is '
            'approved.',
    "FW06": "As soon as the recruiter replies with the candidate's availability, I'll send the calendar invites.",
    "FW07": 'After the backfill job completes I will compare the row counts against the source tables.',
    "FW08": "I'll wait for the plumber's reply and book the Tuesday visit when he confirms the slot.",
    "FW09": "The infrastructure provisioning run is still going; I'll be able to continue with the DNS change once it's "
            'done.',
    "FW10": "Your build is compiling now, and I'll pick up the signing step when it finishes.",
    "FW11": 'The search index is rebuilding, so the import is paused. Resuming after the rebuild completes.',
    "FW12": "Waiting until the emulator boots, then I'll run the UI tests.",
    "FW13": "You approved the sofa order yesterday, so it now sits with the supplier; I'll update the delivery schedule "
            'as soon as they confirm a date.',
    "FW14": "I'll hold here until the `payments-db` migration job exits, then run `verify_totals.sql`.",
    "FW15": "The corresponding author hasn't answered yet. I'll wait for her reply before adding the dataset details to "
            'the literature summary.',
    "FW16": "Once your pull request has been approved by the second reviewer, I'll merge it and delete the branch.",
    "FW17": "When the reimbursement posts to your account, I'll mark the expense report as settled.",
    "FW18": "I'm going to wait for the pharmacy to text that the prescription is ready, and then I'll arrange the pickup.",
    "FW19": 'We will continue with the rollout as soon as the canary metrics have been collected.',
    "FW20": "The scheduling poll is still open. Once the interviewers have all responded, I'll lock the panel times and "
            'notify the candidate.',
    "FW21": "The warehouse team's notice reads:\n> Maintenance ends at 03:00 UTC.\nI'll wait for the cluster to come back "
            'online and then restart the nightly load.',
    "FW22": 'The wire has been submitted. When the bank confirms it has cleared, I will record the payment against '
            'invoice 2207.',
    "FW23": "I can't finish the chart until the survey export finishes generating, so I'm waiting on that and will "
            'complete the figure afterwards.',
    "FW24": "I'm currently still waiting for the background-check provider to return its report, and I'll finalize the "
            'offer packet as soon as it has.',
    "FW25": "Waiting for your landlord to send the signed lease back; I'll file it and then set up the rent autopay.",
    "FW26": "The symbol upload for the crash reports is in progress. I'll resume triage after it's processed.",
    "FW27": "The payroll provider's batch hasn't settled yet, so I'll hold the journal entries and post them after it "
            'does.',
    "FW28": "The bank's export page shows:\n```\nStatement for October: generating\n```\nI'll download it once it's ready and"
            ' finish the reconciliation.',
    "FW29": 'I\'ll rerun the "Nightly Sales" dashboard refresh once the `orders_raw` load completes.',
    "FW30": "Once the 'Release' workflow finishes, I'll attach the signed package to the ticket.",
    "FW31": "I have to wait for the payment processor to release the hold before I can issue the refund, so I'll issue it"
            ' when the hold lifts.',
    "FW32": "We are, as of this message, waiting on the data vendor to deliver the corrected file; we'll rerun the "
            "pipeline once it's delivered.",
    "FW33": "I will, in the meantime, keep waiting for the library to confirm the interlibrary loan, and I'll extract the"
            ' three chapters when the scan arrives.',
    "FW34": "Until the firmware vendor ships the fixed version, I'm holding the device rollout; I'll resume it when the "
            'new version is out.',
    "FW35": "Your refund request is with the airline now, and I'm holding off on the hotel until their confirmation email"
            " comes through, then I'll rebook it.",
}
MORE_OF_THE_SIXTH_LISTS_CLASSES = {
    "a-request-then-waiting-on-it": "Type the code from the terminal below. I'm waiting on it.",
    "a-question-then-waiting-on-that": "Do you want the long version? I'm waiting on that before I draft anything.",
    "when-a-build-fails": "When a build fails, I'll look at the first error before anything else.",
}
MORE_WAITS_OF_THE_SIXTH_LISTS_CLASSES = {
    "the-export-then-waiting-on-that": "The export is running; I'm waiting on that before I rebuild the index.",
    "when-the-courier-scans": "When the courier scans the parcel, I'll forward the tracking link.",
    "until-with-a-before-clause": "Waiting until the deploy finishes before the cache is warmed.",
}


@pytest.mark.parametrize("reply", _cases(INDEPENDENT2_NO_WATCHER, MORE_OF_THE_SIXTH_LISTS_CLASSES))
def test_a_second_list_written_without_sight_of_the_code_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(INDEPENDENT2_OWN_WAIT, MORE_WAITS_OF_THE_SIXTH_LISTS_CLASSES))
def test_a_second_list_written_without_sight_of_the_code_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# A third list from an agent that never saw the code, across support, contracts, publishing, experiments, security and
# events. Eleven were wrong, nine of them waits that passed: any verb before "when" or "after" and an arrival ("I'll
# proof the pages when the second pass comes back"), "the moment", "we'll" with any verb before "once", and "pausing
# until". Two were sent back needlessly: "until I have it" after the principal's decision, and "waiting until every RSVP
# is in is not realistic". One stays wrong: "Standing by for their reply" is no built-in form (the test above pins
# that; `wait_phrases` adds it), so GW33 is marked as the miss it is.
INDEPENDENT3_NO_WATCHER = {
    "GN01": "Both replies to the customer are saved as drafts. I'm waiting on your review of the second one before either"
            ' is sent.',
    "GN02": 'The carrier\'s tracking page now reads "We will attempt delivery again once the recipient confirms an '
            'address." I copied that line into the case notes so the next person sees it.',
    "GN03": 'Here is a holding reply you can paste into the ticket:\n```\nWe are waiting for our shipping partner to '
            'confirm the delivery date and will write to you as soon as they do.\n```\nChange the sign-off to match your '
            "team's style.",
    "GN04": 'My suggestion for the follow-up: when the customer writes back with the serial number, look it up in the '
            'warranty table before you offer a replacement. The table is on the second tab of the sheet.',
    "GN05": "The courier's system shows the parcel waiting at the depot until customs clears it. That is the status I "
            'passed on to the customer, and the ticket is closed on our side.',
    "GN06": "Waiting for the counterparty's redline before commenting on indemnity was the right call last quarter; it "
            'saved a full round of edits. The memo you asked for summarises that history.',
    "GN07": "Clause 14 works like an escrow: the buyer's payment is held until the inspector files a clean report and is "
            'released automatically after that. Nothing in the clause lets either side shorten the holding period.',
    "GN08": "Once you choose between the two governing-law options, I'll finish section 12 and renumber the cross-"
            'references. Everything else in the draft is complete.',
    "GN09": "Opposing counsel's email is short:\n> We will send our comments once our client has reviewed the liability "
            'cap.\nI filed it under correspondence and changed nothing in the draft.',
    "GN10": "A party that waits for the other side's signature before performing is usually on safer ground, because "
            'starting work early can be read as accepting the unsigned terms. That is the reasoning behind the note I '
            'added to clause 3.',
    "GN11": 'The two versions of the non-compete differ only in duration. Read both when you have a moment and tell me '
            "which one you prefer; I'll wait.",
    "GN12": "I will, of course, send nothing to the tenant's solicitor until I have your signature on the notice. The "
            'final text is attached for you to read.',
    "GN13": 'The copyedit of chapters one to six is done and my queries are in the margins. Will resume with chapter '
            "seven as soon as you've answered them.",
    "GN14": 'I read the manuscript through once for continuity and once more for house style. All 31 changes are tracked,'
            ' and none of them touches the dialogue.',
    "GN15": "The style guide's own example is the clearest: “We will publish the correction once the author confirms the "
            'figure.” I matched the wording of your correction notice to it.',
    "GN16": 'My plan for the next pass is simple: tighten the introduction first, and once that reads cleanly, rework the'
            ' conclusion to echo it. Both steps use only the text already in the file.',
    "GN17": 'Holding the cover reveal until the endorsements arrive would cost the book its place in the spring '
            'catalogue. I recommend revealing now and adding the quotes to the second printing.',
    "GN18": "This is the notice the journal's system shows authors at this stage:\n~~~\nYour manuscript is awaiting "
            'reviewer reports, and we will contact you when a decision has been made.\n~~~\nIt is a standard message and '
            'says nothing about your paper in particular.',
    "GN19": 'I held the newsletter until the legal team cleared the headline, which they did at noon, and it went out at '
            "12:15. Open rates so far are in line with last month's.",
    "GN20": 'The early-stopping callback waits until validation loss has failed to improve for five epochs and then '
            'restores the best weights. That is why the run ended at epoch 37 and not at the configured 60.',
    "GN21": 'Both sweeps finished overnight. I waited for the last seed before averaging, so the table covers all five '
            'runs, and the larger learning rate wins by 0.8 points.',
    "GN22": 'The line `waiting for checkpoint, will resume when available` in the trainer log is harmless. It is printed '
            'on every start and does not mean the job has stalled.',
    "GN23": 'When the next batch of labels comes back from the annotators, you should rerun the agreement script before '
            'merging them into the training set. A kappa below 0.6 would mean the guidelines need another revision.',
    "GN24": 'Waiting until the loss curve flattened would have burned another six GPU hours for no gain, so I stopped at '
            'step 40,000 and saved the checkpoint. The evaluation numbers are in the table above.',
    "GN25": 'The scheduler releases a node only after every process on it has exited, which is why your queue position '
            'did not move during the evaluation. Nothing was wrong with the submission.',
    "GN26": 'Containment is complete: the laptop was isolated, and after the forensic image finished I verified its hash '
            'against the original. The timeline is in the incident record.',
    "GN27": 'The runbook says an account stays disabled until its owner has re-enrolled a hardware key, and the help desk'
            ' re-enables it once that is logged. I added that paragraph to the summary for the affected staff.',
    "GN28": "I've listed the six firewall rules I would remove, with the reason for each. Nothing changes until I have "
            'your approval.',
    "GN29": "The alert text is misleading. It says 'holding session until the scanner returns a verdict', but that is the"
            ' proxy describing its own behaviour, not a sign of compromise.',
    "GN30": 'As soon as the vendor publishes the patch, apply it to the mail gateway first and the file servers second. '
            'The temporary rule I described covers the gap in the meantime.',
    "GN31": "The sign-in page is asking for the six-digit code from your authenticator app. I'll continue once you've "
            'typed it in.',
    "GN32": 'The credential-stuffing rule fired once in the past thirty days, on the 3rd, and the source address was '
            'already on the blocklist. The threshold needs no change.',
    "GN33": "I have two workable seating plans for the dinner. Pick one when you've had a look, and we'll wait to print "
            'the place cards until then.',
    "GN34": 'The registration form closes itself when the two-hundredth guest signs up, and anyone after that goes onto '
            'the waiting list. I tested it with a dummy entry and deleted the entry afterwards.',
    "GN35": 'Once the florist sends the final invoice, pay it from the events account and not the general one. That keeps'
            ' the conference budget report accurate.',
    "GN36": 'For the save-the-date, a line such as "We\'ll share the full programme as soon as the speakers confirm" sets '
            'the right expectation. I left it as the last sentence of the draft.',
    "GN37": "The shuttle schedule depends on your decision about the Saturday start time. I'm holding the booking request"
            ' until I have it.',
    "GN38": 'Waiting until every RSVP is in is not realistic for a dinner of 300; caterers want a number ten days out. I '
            'based the order on the 240 guests confirmed so far.',
    "GN39": 'The passport renewal form is filled in except for the emergency contact, which only you can supply. Send me '
            "the name and number whenever it suits you. I'll wait.",
    "GN40": 'Your insurance claim was approved yesterday after three weeks in review, and the payment reached your '
            "account this morning. I've marked the item closed on your list.",
    "GN41": 'The bank holds a mobile deposit until the cheque clears, usually two working days, and then the funds show '
            'as available. That is why your balance and your available balance differ today.',
    "GN42": "Compare the new premium with this year's when the renewal notice arrives next spring, and switch insurers if"
            " the increase is above ten percent. I've saved this year's figures in the household folder for that purpose.",
    "GN43": "After I finish reconciling March, I'll go straight on to April; both statements are already downloaded and "
            'nothing else is needed. The February summary is attached.',
    "GN44": "The letter to the school is drafted. I'll finalise it once your edits are in, and it can go in tomorrow's "
            'post.',
    "GN45": "The accountant is waiting for last year's donation receipts, which are in your desk and not in any folder I "
            'can reach. Everything else on the checklist has been sent.',
}
INDEPENDENT3_OWN_WAIT = {
    "GW01": 'The warehouse team wrote back "stock count in progress" and nothing more. I\'ll write to the customer with a '
            'delivery date as soon as they confirm the count.',
    "GW02": "Waiting for the payment processor to post the reversal; once it shows on the account, I'll send the customer"
            ' the confirmation and close the ticket.',
    "GW03": 'The escalation is with tier two now. When their engineer replies, I will summarise the fix for the customer '
            'and update the help article.',
    "GW04": "Your refund request has gone to the billing system, which normally approves these within a few minutes. I'll"
            " check the outcome when it's done and then email the customer the receipt.",
    "GW05": "Still waiting on the courier's answer about the lost parcel, so the claim form stays open; I'll file it the "
            'moment they respond.',
    "GW06": "The revised agreement is out for signature with the supplier. Once it has been countersigned, I'll file the "
            'executed copy and update the renewal tracker.',
    "GW07": "I'll wait for your lawyer's comments on the indemnity clause and fold them into the draft when they arrive.",
    "GW08": 'Opposing counsel has the redline. I am holding the cover letter until their response comes in, and I will '
            'revise the liability section to match whatever they accept.',
    "GW09": "The court's e-filing system is still processing the motion. I'll serve the other side and calendar the "
            'response deadline after it issues the stamped copy.',
    "GW10": "You signed the engagement letter yesterday, so the only thing outstanding is the conflict check the firm's "
            "system is running. I'll open the matter file as soon as that check comes back.",
    "GW11": "The typesetter has the corrected files. I'll proof the new pages against your markup when the second pass "
            'comes back.',
    "GW12": 'Waiting for the "Final Proof" PDF from the printer; when it lands I\'ll check the page breaks and the running'
            ' heads.',
    "GW13": "Your manuscript is with the two peer reviewers now. As soon as both reports are in, I'll draft the response "
            'letter and mark up the revisions.',
    "GW14": "We are, I'm afraid, stuck until the rights holder answers the permission request for the two photographs. "
            "I'll place the images and finish the captions once the licence arrives.",
    "GW15": 'The plagiarism scan on chapter four is running. Will send you the similarity report and my notes when it '
            'finishes.',
    "GW16": 'Will resume the write-up once the fine-tuning run completes; it is at epoch 3 of 10 and the baseline numbers'
            ' are already in the table.',
    "GW17": 'Kicked off the hyperparameter sweep on the shared cluster. Holding the analysis notebook until all twelve '
            "trials have been scored by the evaluation harness; then I'll rank them and plot the top three.",
    "GW18": "I'll rerun the comparison as soon as the `eval-nightly` job posts its numbers.",
    "GW19": "The annotation vendor still owes us the last 500 labels. Until those are delivered, I'm pausing the "
            "retraining, and I'll restart it when the file shows up in the bucket.",
    "GW20": 'After the data-export job finishes writing the shards, I will launch the tokenizer and start the first pass.'
            ' Nothing else is blocking the experiment.',
    "GW21": "The full-disk scan on the finance server is about a third done. I'll let you know what it flags the moment "
            'it completes.',
    "GW22": "Waiting until the identity provider finishes revoking the old tokens, then I'll re-enable the service "
            'accounts one at a time.',
    "GW23": "I've asked the hosting provider to preserve the logs for the affected hour. As soon as their abuse desk "
            'sends the archive, I will rebuild the timeline and attach it to the incident record.',
    "GW24": "Your password reset has been submitted and is sitting in the directory's sync queue. I'm going to wait for "
            'the sync to go through and then test the sign-in.',
    "GW25": "The sandbox is detonating the attachment now, and we'll release or quarantine the message once it returns a "
            'verdict.',
    "GW26": "The hotel has the room-block request and promised an answer today. I'll have to wait for their confirmation "
            'before sending the booking link to the guests.',
    "GW27": 'Holding the invitations until the venue confirms the date; they go out the moment it does.',
    "GW28": "I have not heard back from the keynote speaker's office. I'll come back to the running order when they reply"
            ' with the travel dates, and book the flights then.',
    "GW29": "Pausing here until the ticketing platform finishes importing the attendee list; I'll run the duplicate check"
            ' right after.',
    "GW30": "You approved the menu on Monday, and the caterer is now pricing it. I'll update the budget sheet when their "
            'quote comes through.',
    "GW31": "You've uploaded the scans, and the tax portal is validating them now. I'll wait, then file the return when "
            'the validation is finished.',
    "GW32": 'Your visa application is with the consulate, and nothing more can be done from here until they issue a '
            'decision. I will book the flights when the approval comes through.',
    "GW33": "I've asked the landlord's office for the countersigned lease. Standing by for their reply; the utilities "
            'transfer gets scheduled as soon as I have it.',
    "GW34": "Waiting on the bank's review of your dispute over the duplicate charge. After the provisional credit has "
            "been posted, I'll reconcile the statement and close the item on your list.",
    "GW35": 'I will just wait for the pharmacy to confirm the prescription is ready and then arrange the courier pickup.',
}
MORE_OF_THE_SEVENTH_LISTS_CLASSES = {
    "cached-copy-when-the-network-is-down": "I'll use the cached copy when the network is down.",
    "flag-it-when-it-happens-again": "I'll flag it when it happens again.",
    "we-will-need-to-once": "We'll need to revisit the pricing once the vendor publishes the new tiers; I noted it in the plan.",
}
MORE_WAITS_OF_THE_SEVENTH_LISTS_CLASSES = {
    "continue-once-i-have-it": "The export is still running. I'll continue once I have it.",
    "i-will-pause-until": "I'll pause the rollout until the error budget recovers.",
    "we-will-file-once": "We'll file the amended return once the bank reissues the statement.",
}


@pytest.mark.parametrize("reply", _cases(INDEPENDENT3_NO_WATCHER, MORE_OF_THE_SEVENTH_LISTS_CLASSES))
def test_a_third_list_written_without_sight_of_the_code_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(INDEPENDENT3_OWN_WAIT, MORE_WAITS_OF_THE_SEVENTH_LISTS_CLASSES))
def test_a_third_list_written_without_sight_of_the_code_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# A fourth list from an agent that never saw the code, run against the check as it stood after the third: six of 80
# were wrong. Sent back needlessly: "your decision between ...", a short wait after "Please read ... and tell me", and a
# past hold judged by what it cost. Passed: "the day the file comes in", "the day it does", "I have paused ... until",
# and an event stated first whose subject is "a seat".
INDEPENDENT4_NO_WATCHER = {
    "HN01": 'The `await` on line 42 suspends the handler until the database call returns, so nothing blocks the event '
            'loop. That is expected behavior and I left it alone.',
    "HN02": 'You approved the change this morning; CI took eleven minutes, and after it passed I merged the branch and '
            'deleted it. The release notes are in the changelog.',
    "HN03": "I'm deliberately holding the merge until you've looked at the two open comments on the diff. Everything else"
            ' in the pull request is ready.',
    "HN04": 'Here is the status line the bot could post while a release is in flight:\n```\nWaiting for the build to '
            "finish; I'll publish the package once it passes.\n```\nThat text is only a template for you to edit.",
    "HN05": 'Waiting for the flaky test to pass on a rerun would only have hidden the race condition. The fix I committed'
            ' removes the shared fixture instead.',
    "HN06": 'I reproduced the crash once in forty runs, and that one time the cache was cold. The stack trace is attached'
            ' to the ticket.',
    "HN07": "The parser refactor is done. Next I'll update the call sites, and once I've finished those I'll rewrite the "
            'two tests that depended on the old signature.',
    "HN08": 'When the next minor version ships, remember to drop the compatibility flag from the config. Until then it '
            'does no harm.',
    "HN09": 'The autoscaler adds a node only after pending pods have been unschedulable for thirty seconds, which '
            'explains the delay you saw. No configuration change is needed.',
    "HN10": 'We held the rollout until the canary error rate settled, and it has been serving all traffic since 09:40. '
            'Latency is back to baseline.',
    "HN11": "Once I have your approval for the maintenance window, I'll start the `db-failover` runbook. The steps are "
            'listed above.',
    "HN12": 'The provider\'s status page says "We are waiting on a fix from our network team and will post an update once '
            'traffic recovers," so the packet loss is on their side. Our own health checks have been green all morning.',
    "HN13": 'Holding a deploy until the queue drains is the standard way to avoid dropped messages with this broker. The '
            'script already does that on line 18.',
    "HN14": "You'll need to wait for the DNS change to propagate before the new hostname resolves, which usually takes "
            'under an hour. After that, check that the load balancer is serving the new certificate chain.',
    "HN15": 'The disk alert fired once, at 03:12, when the log rotation ran late. It cleared by itself four minutes '
            'later.',
    "HN16": 'Your "March cohort" export sat in the queue for an hour; once it finished I loaded it, and the totals now '
            'include the late-arriving rows. Revenue for the quarter comes to 4.2 million.',
    "HN17": 'The cohort definition is the one open point. Waiting on your decision between the 30-day and 90-day windows;'
            " I'll rerun the retention table as soon as I have it.",
    "HN18": 'The scheduler pauses the aggregation step until both upstream loads report success, which is why the task '
            'showed as pending this morning. That dependency is intentional.',
    "HN19": 'The notebook prints `waiting for query... will plot once results arrive` on every poll, which is why the '
            'output cell looks so long. I collapsed it; the charts below are unaffected.',
    "HN20": "Once next month's data lands, you should rerun the seasonality check before trusting the forecast. The "
            'current fit rests on only eleven months.',
    "HN21": 'Waiting until a survey closes before weighting the responses is standard practice, because early respondents'
            ' tend to skew younger. The interim numbers above are unweighted for that reason.',
    "HN22": 'Please read the revised discussion section and tell me whether the limitation paragraph says what you '
            "intended. I'll wait.",
    "HN23": 'The journal sends proofs only after the copyright form has been received, and it allows 48 hours for '
            'corrections. Both rules are stated in the acceptance letter.',
    "HN24": "The second reviewer's comment reads:\n> I will wait for the authors to share the replication code and will "
            'complete my report once it arrives.\n\nI have added the repository link to the response letter.',
    "HN25": "The reference list still follows the old style. Whenever you've decided which journal to target, let me know"
            " and I'll continue with the formatting.",
    "HN26": 'Wait until both reviewer reports are in before you start the response letter, since the editor wants a '
            'single consolidated reply. A point-by-point table usually works best for that.',
    "HN27": "The literature table is complete. I'll draft the methods section next, and after that I'll go back and "
            'reconcile the citation keys.',
    "HN28": "We'll keep the purchase order in draft until your sign-off on the revised quantities. The supplier's quote "
            'is valid through the 30th.',
    "HN29": 'Under the contract, the supplier invoices only after delivery is confirmed at the dock, and payment is due '
            '45 days later. Nothing is owed on the second shipment yet.',
    "HN30": "The account manager's email says “we’re waiting on our finance team and will send the countersigned order "
            'form as soon as they approve it,” and it is dated Monday. I filed it under the renewal thread.',
    "HN31": "The prospect's buyer replied after two reminders, and once their redlines arrived I updated the proposal. "
            'The discount now stands at 12% on a three-year term.',
    "HN32": 'As soon as the trial ends, ask the vendor for usage figures before you negotiate seat counts. Those numbers '
            'are the strongest argument you will have.',
    "HN33": 'Holding the order until the supplier confirmed the lead time cost us nothing last quarter, and it avoided a '
            'double shipment. It is a reasonable default for long-lead parts.',
    "HN34": "The airline's site says it sent a six-digit code to your phone. Paste it here when you have it and I'll "
            'continue with the seat change.',
    "HN35": 'Refunds on this fare are issued only after the airline confirms the cancellation, and they usually reach the'
            ' card within seven to ten business days. The cancellation itself went through at 14:05.',
    "HN36": "A sample auto-reply you could set while you travel:\n~~~\nI'm waiting on the carrier to confirm my new flight "
            'and will answer as soon as I land.\n~~~\nChange the wording however you like.',
    "HN37": "Both itineraries are on hold with the fare locked for 24 hours. I'll resume the booking as soon as I have "
            'your answer on the layover.',
    "HN38": "When the gate is announced, you'll want to check the walking time between terminals, because the connection "
            'is only 50 minutes. Online check-in opens 24 hours before departure.',
    "HN39": 'I held the two rooms until the rate dropped yesterday and then booked both at the lower price. The '
            'confirmation numbers are in the itinerary document.',
    "HN40": "The referral packet is assembled and ready to submit. I'm holding it for your confirmation of the diagnosis "
            'code, since only you can verify that against the chart.',
    "HN41": 'Prior authorization requests for this payer sit in a queue until a nurse reviewer picks them up, which '
            'typically takes three to five business days. That is the reason the two June referrals moved slowly.',
    "HN42": "The scheduling note says 'waiting for the insurer to approve; will call the patient once the authorization "
            "arrives', and it was written by the front desk on the 4th. No later entry appears in the record.",
    "HN43": 'Waiting on prior authorization is the main reason these imaging referrals take two weeks. Of the 31 I '
            'reviewed, 24 spent more than nine days in that step.',
    "HN44": 'After the payer posts its updated fee schedule in January, it is worth comparing it with the charge master '
            "before the first claims go out. Last year's mismatch caused most of the denials.",
    "HN45": 'The claim was resubmitted on the 2nd, and after the payer reprocessed it the remittance posted for the full '
            'amount. I closed the denial in the work queue.',
}
INDEPENDENT4_OWN_WAIT = {
    "HW01": "Pushed the fix to `fix/session-timeout`. Waiting for CI to finish, then I'll merge and tag v2.4.1.",
    "HW02": "I'll rerun `make integration` once the `db-restore` job finishes. The unit tests already pass locally.",
    "HW03": 'The pull request is with the second reviewer now. As soon as she approves, I will squash the commits and '
            'merge.',
    "HW04": "You approved the release plan earlier, so the package build is already running. I'll publish to the registry"
            ' when it completes.',
    "HW05": "We are, at this point, just waiting on the nightly build to be published by the release bot. I'll start the "
            'bisect as soon as that artifact is available.',
    "HW06": "The snapshot restore is in progress on the replica. Once it has been restored, I'll repoint the read traffic"
            ' and drop the old instance.',
    "HW07": "Holding the cutover until replication lag reaches zero. I'll flip the DNS record the moment it does.",
    "HW08": "I'm going to wait for the certificate authority to issue the renewed certificate and then install it on both"
            ' load balancers.',
    "HW09": 'Your cluster upgrade is still rolling through the node pools. After the last pool finishes, I will rerun the'
            ' conformance checks and send you the results.',
    "HW10": "The provider has an open incident on the storage tier, so I can't finish the migration yet. Will resume the "
            'copy when their status page shows the incident resolved.',
    "HW11": 'I need to wait for the March backfill to show "SUCCEEDED" in the warehouse console before I rebuild the '
            'revenue dashboard. Everything else in the report is current.',
    "HW12": 'Waiting for the "Q3 actuals" export to land in the shared bucket; once it\'s there I\'ll recompute the '
            'variance table.',
    "HW13": "Thanks for confirming the cohort definition. The query is in the queue now, and as soon as it returns I'll "
            'continue with the retention chart and the summary.',
    "HW14": "I still need the vendor's data team to resend the corrected file. Until that arrives, I'm leaving the churn "
            "model untouched, and I'll refit it the day the file comes in.",
    "HW15": 'Your training job is at epoch 14 of 20 on the shared cluster. When it finishes I will pull the validation '
            'metrics and compare them against the baseline.',
    "HW16": "Proofs are due from the journal's production office this week. I'll check them against our corrections list "
            'as soon as they are sent out.',
    "HW17": "We're waiting on the ethics committee's decision on the amended protocol. Once it is approved, I'll update "
            'the consent form version number and the recruitment materials.',
    "HW18": "The request for the raw data went to the original authors' lab this morning. Standing by for their reply, "
            "and I'll rerun the meta-analysis with the full sample when it comes.",
    "HW19": 'Your grant application shows as "under administrative review" in the funder\'s portal. I\'ll download the '
            'reviewer summary and draft the response once the portal releases it.',
    "HW20": 'The simulation batch is still running on the department cluster, with 62 of 200 runs complete. I will be '
            'waiting for the rest to finish before I compute the confidence intervals.',
    "HW21": "The prospect's security questionnaire is still with their IT team. I'll pick the proposal back up once their"
            ' answers arrive.',
    "HW22": "Until the vendor's legal team returns the redlined agreement, I'm keeping the order form in draft. I'll "
            'route it for signature the moment their markup arrives.',
    "HW23": "You've already signed the renewal, so it is with the reseller for countersignature. When the countersigned "
            "copy comes back, I'll file it and update the contract register.",
    "HW24": "Waiting until the distributor confirms stock on the 40 units, then I'll place the order against the approved"
            ' budget line.',
    "HW25": "Your purchase request is sitting in the finance system's approval queue. As soon as it is released by the "
            'budget office, I will send the order to the supplier.',
    "HW26": "I am waiting for the airline to finish processing the schedule change. I'll reissue the ticket and send the "
            'new itinerary once the change is confirmed.',
    "HW27": "I won't book the hotel until the airline confirms the new arrival time. Once it does, I'll reserve the room "
            'you picked for the right night.',
    "HW28": 'Your visa application is marked "in process" at the consulate. I\'m holding the flight purchase until the '
            "visa is issued, and I'll buy the refundable fare right after.",
    "HW29": "The waitlist for the direct flight hasn't cleared. When a seat opens up, I'll move the booking over and "
            'cancel the connection.',
    "HW30": "You chose the aisle seat on the outbound leg, and that request is in. We'll just have to wait for the "
            "carrier's system to release seats for the return, after which I'll match it.",
    "HW31": "The prior authorization request went to the payer on Monday. I'm waiting on their approval, and I'll "
            'schedule the MRI as soon as it is posted to the portal.',
    "HW32": "Waiting on the lab interface to deliver the pending culture result. I'll add it to the discharge summary and"
            ' close the encounter after it arrives.',
    "HW33": "Your signed referral was faxed to the specialist's office at 10:20. Once their intake team accepts it, I'll "
            'book the first available slot and notify the patient.',
    "HW34": 'The clearinghouse has not yet returned the eligibility response for the three new patients. I have paused '
            'their registrations until it comes back, and I will complete them the day it does.',
    "HW35": "I'll now simply wait for the payer to reprocess the corrected claim, and when the remittance posts I'll "
            'reconcile it against the ledger.',
}
MORE_OF_THE_EIGHTH_LISTS_CLASSES = {
    "please-pick-one": "Please pick one of the two titles. I'm waiting on that.",
    "retry-when-a-request-fails": "I'll retry when a request fails with a timeout.",
}
MORE_WAITS_OF_THE_EIGHTH_LISTS_CLASSES = {
    "review-is-pending-elsewhere": "Review is pending on the vendor's side. I'll wait.",
    "when-an-earlier-slot-opens-up": "When an earlier slot opens up, I'll move the appointment.",
    "the-vendor-to-tell-me": "I'm waiting on the vendor to tell me the delivery date.",
}


@pytest.mark.parametrize("reply", _cases(INDEPENDENT4_NO_WATCHER, MORE_OF_THE_EIGHTH_LISTS_CLASSES))
def test_a_fourth_list_written_without_sight_of_the_code_of_replies_that_need_no_watcher_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(INDEPENDENT4_OWN_WAIT, MORE_WAITS_OF_THE_EIGHTH_LISTS_CLASSES))
def test_a_fourth_list_written_without_sight_of_the_code_of_unarmed_waits_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# What 30 days of recorded turn-ending replies showed (2026-11-12, 4,842 of them): the check as it stood would have sent
# back 815, and 586 of those were turns the harness itself was holding (a background agent, shell, workflow or monitor
# that had not reported); of the 202 others read one by one, 96 were the session's own unarmed wait, 57 awaited the
# principal's own next step in words the check did not read, 30 were status lists and labels, 12 sat inside a message
# drafted for someone else. The cases below are those classes, rewritten with nothing of the replies in them.

def _entry(**fields):
    return json.dumps(fields)


def _started(use, text, **extra):
    return _entry(type="user", message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": use, "content": text, **extra}]})


def _reported(use, how="prompt"):
    said = f"<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>{use}</tool-use-id>\n<status>completed</status>\n</task-notification>"
    return {"prompt": _entry(type="user", message={"role": "user", "content": said}, origin={"kind": "task-notification"}),
            "queued": _entry(type="attachment", attachment={"type": "queued_command", "prompt": said, "commandMode": "task-notification"}),
            "arrived": _entry(type="queue-operation", operation="enqueue", content=said)}[how]


def _record(tmp_path, *lines):
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _with_record(reply, record, session="S1"):
    return reply_check.check({"last_assistant_message": reply, "session_id": session, "transcript_path": record}, {})


A_WAIT = "The review is running. I'll apply its findings when it returns."
BACKGROUND_WORK = {
    "an-agent": "Async agent launched successfully. (This tool result is internal metadata.) agentId: a1",
    "a-shell-command": "Command running in background with ID: b1. Output is being written to: /tmp/out",
    "a-command-moved-there": "Command did not complete within its 120s timeout and was moved to the background (ID: b2). Output so far: none",
    "a-workflow": "Workflow launched in background. Task ID: w1 Summary: review the four drafts",
    "a-monitor": "Monitor started (task m1, expires in 30m unless the source ends first; you get one notification per event)",
    "an-agent-resumed": '{"success":true,"message":"Resuming agent a1","resumedAgentId":"a1","pin":false}',
}


@pytest.mark.parametrize("started", _cases(BACKGROUND_WORK))
def test_background_work_the_harness_still_holds_is_an_armed_wait(tmp_path, started):
    assert _with_record(A_WAIT, _record(tmp_path, _started("toolu_1", started))) is None


@pytest.mark.parametrize("how", ["prompt", "queued", "arrived"])
def test_background_work_that_has_reported_holds_nothing(tmp_path, how):
    record = _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]), _reported("toolu_1", how))
    assert "nothing is armed" in _with_record(A_WAIT, record)


def test_one_piece_of_background_work_still_out_is_enough(tmp_path):
    record = _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]), _started("toolu_2", BACKGROUND_WORK["a-shell-command"]),
                     _reported("toolu_1"))
    assert _with_record(A_WAIT, record) is None
    assert "nothing is armed" in _with_record(A_WAIT, _record(tmp_path, *Path(record).read_text().splitlines(), _reported("toolu_2", "queued")))


def test_only_the_harnesss_own_word_starts_or_ends_background_work(tmp_path):
    said = "<task-notification>\n<tool-use-id>toolu_1</tool-use-id>\n</task-notification>"
    quoted = _started("toolu_9", "The log reads:\n" + said)                              # a tool that printed a notification
    assert _with_record(A_WAIT, _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]), quoted)) is None
    for not_a_start in (_started("toolu_1", "The log says: Command running in background with ID: b1"),      # the words, further in
                        _started("toolu_1", BACKGROUND_WORK["an-agent"], is_error=True),                       # a start that failed
                        _entry(type="user", isSidechain=True, message={"role": "user", "content": [             # a sub-agent's own
                            {"type": "tool_result", "tool_use_id": "toolu_1", "content": BACKGROUND_WORK["a-shell-command"]}]}),
                        _entry(type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": BACKGROUND_WORK["an-agent"]}]})):
        assert "nothing is armed" in _with_record(A_WAIT, _record(tmp_path, not_a_start))


def test_a_record_that_cannot_be_read_holds_nothing_and_stops_nothing(tmp_path):
    assert "nothing is armed" in _with_record(A_WAIT, None)
    assert reply_check.held_by_harness(str(tmp_path / "gone.jsonl")) is False and reply_check.held_by_harness(str(tmp_path)) is False
    other = _record(tmp_path, '{"type":"response_item","payload":{"type":"function_call_output","output":"Command running in background"}}',
                    "not json at all", "[1, 2, 3]", '"a string"')
    assert "nothing is armed" in _with_record(A_WAIT, other)


def test_work_started_many_megabytes_before_the_turn_ended_still_holds(tmp_path):
    """A busy session writes megabytes between a launch and the turn that waits on it. Over thirty days of recorded
    turn ends a 4 MB tail missed ten launches that had not reported, each of which sent back a reply whose wait the
    harness was holding; 32 MB reads them, at about 46 ms on the one turn end in eight that reads as a wait."""
    path = tmp_path / "busy.jsonl"
    filler = _entry(type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "x" * 900}]}) + "\n"
    with path.open("w", encoding="utf-8") as record:
        record.write(_started("toolu_far", BACKGROUND_WORK["an-agent"]) + "\n")
        for _ in range(9_000):  # about 8.6 MB
            record.write(filler)
    assert path.stat().st_size > 8_000_000
    assert reply_check.held_by_harness(str(path)) is True


def test_the_record_is_read_from_its_end_and_fast(tmp_path):
    path = tmp_path / "long.jsonl"
    filler = _entry(type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": "x" * 900}]}) + "\n"
    with path.open("w", encoding="utf-8") as record:
        record.write(_started("toolu_old", BACKGROUND_WORK["an-agent"]) + "\n")           # started long ago, never reported
        for _ in range(40_000):
            record.write(filler)
        record.write(_started("toolu_new", BACKGROUND_WORK["a-shell-command"]) + "\n" + _reported("toolu_new") + "\n")
    began = time.perf_counter()
    assert reply_check.held_by_harness(str(path)) is False                              # the old start is beyond what is read
    assert time.perf_counter() - began < 0.5
    assert reply_check.held_by_harness(str(path), tail=10**9) is True


# "Standing by for" something is a wait, as "waiting for" it is, when the thing is neither the principal's nor open-ended.
# In thirty days of recorded turn ends 22 replies used the phrase: read as a wait whatever followed, it newly sent back
# six, four of them an idle line to the principal ("for your choice", "for whatever's next", "on the open question");
# read only before a thing that is named, it newly sent back two, both the session's own wait.
STANDING_BY_FOR_A_THING = {
    "their-reply": "I've asked the landlord's office for the countersigned lease. Standing by for their reply.",
    "the-registry": "The tag is pushed. Standing by for the registry to publish the package.",
    "first-person": "The export is running on their side. I'm standing by for the vendor's file.",
    "still": "The mirror is syncing. Still standing by for the second replica to catch up.",
}
STANDING_BY_FOR_THE_PRINCIPAL = {
    "your-choice": "Both drafts are above. Standing by for your choice between the two.",
    "whatever-is-next": "Nothing is pending here. Standing by for whatever's next.",
    "anything-else": "All four are closed. Standing by for anything else you need.",
    "the-next-task": "The queue is empty. Standing by for the next task.",
    "more": "That is the whole list. Standing by for more if you have it.",
    "a-judgment-on-it": "Standing by for a reply costs nothing here, so the batch goes on.",
    "no-thing-named": "The run is finished and the report is filed. Standing by.",
}


# A wait whose next clause asks the principal to hand over the thing awaited is theirs to end, whichever word waits.
THE_NEXT_CLAUSE_HANDS_IT_OVER = {
    "waiting-then-paste": "I'm waiting for the confirmation code that was emailed to you; paste it here and I'll complete the registration.",
    "standing-by-then-paste": "I'm standing by for the confirmation code that was emailed to you; paste it here and I'll complete the registration.",
    "next-sentence": "I'm waiting for the signed form from their office. Forward it to me when it lands in your inbox.",
    "reply-with": "Waiting on the reference number from the portal. Reply with it and I'll file the claim.",
}
THE_NEXT_CLAUSE_HANDS_NOTHING_OVER = {
    "an-aside": "I'm waiting for the registry to publish the package. Check the logs if you are curious.",
    "a-statement": "I'm waiting for the vendor's file. The paste buffer is empty, so nothing is staged.",
    "another-subject": "I'm waiting for the build. Sharing the report comes after it.",
}


@pytest.mark.parametrize("reply", _cases(THE_NEXT_CLAUSE_HANDS_IT_OVER))
def test_a_wait_followed_by_a_request_to_hand_the_thing_over_is_the_principals_to_end(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(THE_NEXT_CLAUSE_HANDS_NOTHING_OVER))
def test_a_wait_followed_by_anything_else_is_still_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(STANDING_BY_FOR_A_THING))
def test_standing_by_for_a_named_thing_with_nothing_armed_is_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(STANDING_BY_FOR_THE_PRINCIPAL))
def test_standing_by_for_the_principal_or_for_nothing_named_passes(reply):
    assert _sent_back(reply) is None


THE_PRINCIPALS_TURN = {
    "an-approval-code": "The note is staged. To send it, type `approve 7c41d2` within 15 minutes. Once it's out, I'll read it back from the sent folder.",
    "a-code-in-bold": "Held for **approve 51efe9**, or tell me what to change. Once that's done, I'll bring you the next decision.",
    "a-code-named-as-one": "Two sends are held. Code: **`5d0e9a`** for the first, and the second follows it. Once both go through, I'll read them back.",
    "a-code-as-a-label": "Both earlier codes expired, so I filed the calls again:\n\n- **2f8b41:** the summary email.\n\nOnce it runs, I'll read it back.",
    "a-staged-message": "Here is the reply.\n\nBEGIN\nThanks for the steps. I'll send the list as soon as the project exists.\nEND\n\nOnce it's sent, I'll log it in the ledger.",
    "a-staged-message-in-rules": "----- BEGIN -----\nI'll confirm the date once the venue answers.\n----- END -----\nWhen it's sent, I'll close the row.",
    "say-go": "The draft is above. Say go and it's out, and I'll schedule as soon as the vendor replies.",
    "tell-me-when": "Sign in on that page, then approve the prompt. Tell me when it's done and I'll confirm with the doctor.",
    "message-me": "Start the transcription in the app. Message me when it's done and I'll pull the file.",
    "send-me-the-file": "Send me the export when it arrives and I'll re-run the match.",
    "only-you-can": "The dashboard step is one only you can do. I'll send the four links once that's done.",
    "one-step-from-you": "I'm holding the edit until the skill is in the session. One step from you unblocks it: run the installer.",
    "press-enter": "In that tab, press Enter and confirm in the browser. I'll verify the registry once it goes through.",
    "your-sign-in": "No new sign-in has come in. I'm still waiting on your sign-in retry from the plugin.",
    "your-two-answers": "Still waiting on your two answers before I write the session log.",
    "your-scoring": "Evaluation work: waiting on your scoring of the 24 checks.",
    "your-login": "The recording tool: waiting on your login.",
}
STILL_THE_SESSIONS_OWN = {
    "tell-you-is-not-tell-me": "The copy is running on the other machine. I'll tell you when it finishes.",
    "the-reviewer-says-yes": "The reviewer will say yes or no by Friday, and I'll merge once she answers.",
    "an-approval-in-the-past": "You approved the send at noon and it went out. I'll schedule as soon as the vendor replies.",
    "begin-as-a-word": "I'll begin the import once the export lands. The end state is one folder.",
    "a-code-that-is-not-one": "The commit is 7c41d2e. I'll tag it once the tests pass.",
    "your-pipeline": "I'm waiting on your pipeline to finish the nightly build.",
    "your-tests": "Still waiting on your test suite, which is on its last job.",
    "your-registrar": "We're waiting on your registrar to release the domain.",
    "your-lawyers-comments": "I'll wait for your lawyer's comments on the clause and fold them in when they arrive.",
    "once-your-code": "I'll continue once your code has finished compiling.",
    "further-on": "I'm waiting on the bank to release the hold on your card.",
    "your-approval-already-given": "Your approval is recorded. I'm waiting for the deploy job to complete before I close the ticket.",
    "i-wait-on-a-list": "I'm waiting on:\n- the build\n- the lint job",
}


@pytest.mark.parametrize("reply", _cases(THE_PRINCIPALS_TURN))
def test_a_reply_that_hands_the_turn_to_the_principal_needs_no_watcher(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(STILL_THE_SESSIONS_OWN))
def test_words_that_only_look_like_the_principals_turn_exempt_nothing(reply):
    assert "nothing is armed" in _sent_back(reply)


A_LIST_OF_OPEN_LOOPS = {
    "a-bold-label": "Done today: the two drafts.\n\n**Waiting on others:** the venue on a time; the vendor on the quote.",
    "a-label-and-a-list": "Waiting on:\n- CI on the release branch\n- the second reviewer's verdict",
    "a-label-with-words": "Still waiting on peers, both asked and named:\n- the release gate\n- the routing guard",
    "what-we-wait-for": "Everything imported is live. What we're waiting on others for: the address and its DNS record.",
    "two-things": "We're now waiting on two answers: the fee and whether the host sees the messages.",
    "a-heading": "## Awaiting the vendor's go\n\n1. Merge the first request.\n2. Refresh the installed copy.",
    "a-table-cell": "| account | state |\n|---|---|\n| billing | awaiting re-auth |\n| travel | clean |",
    "an-item-after-a-dash": "- **The venue** — sent; awaiting their pick of a date\n- **The caterer** — two threads out, no reply yet",
    "a-fragment-in-a-sentence": "Where that leaves things: exclusions done in all three exhibits; waiting on the lawyer's scope language; then the signing link.",
    "a-label-in-an-item": "- **Capacity note** — waiting on the director's answer, which is the point\n- **The role description** — ready",
}
# Sent back before the recorded replies were read: in them a wait after a label, a dash or a semicolon was a status
# line every time, so these forms are left unread, and a true wait written this way passes.
A_WAIT_AFTER_A_LABEL_A_DASH_OR_A_SEMICOLON = {
    "a-bold-status-label": "Deployed to staging.\n\n**Status:** waiting for the smoke tests to pass.",
    "after-a-dash": "The draft is with the editor — still waiting on her notes.",
    "EW24": "Your approval is recorded; waiting for the deploy job to complete before I close the ticket.",
}
A_SENTENCE_THAT_OPENS_WITH_THE_WAIT = {
    "the-whole-reply": "Waiting on the channel lookup, which says which entries can be renamed.",
    "after-a-sentence": "Nothing outstanding. Awaiting the board reply.",
    "a-numbered-sentence": "1. The branch is rebased.\n2. Waiting on the integration suite before I tag the release.",
    "still": "Still waiting on the offline-tests agent; no report yet, nothing new to act on.",
}
A_RULE_NOT_A_WAIT = {
    "from-now-on": "You're right. From now on, when an approved send fails on its usual route, I'll finish it through the browser.",
    "next-time": "Next time I'll check the sent folder once the send returns, before I report it.",
    "every-time": "Every time a run finishes, I'll read its last line before I quote it.",
}


@pytest.mark.parametrize("reply", _cases(A_LIST_OF_OPEN_LOOPS, A_RULE_NOT_A_WAIT, A_WAIT_AFTER_A_LABEL_A_DASH_OR_A_SEMICOLON))
def test_a_list_of_open_loops_a_label_or_a_rule_is_no_announcement(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(A_SENTENCE_THAT_OPENS_WITH_THE_WAIT))
def test_a_sentence_that_opens_with_the_wait_is_still_sent_back(reply):
    assert "nothing is armed" in _sent_back(reply)


# --- review round 3 of 5.8.0 (2026-11-12) --------------------------------------------------------------------------
# A third fresh review found ten defects in this check: one of forty replies that need no watcher sent back, three of
# thirty unarmed waits passed, and six more in probes of each exemption and of the transcript reader. Each is fixed as
# a class. The R3 ids are the review's replies; every other reply is written fresh for these tests.

# Finding 1 of the review: what the session will do next is no outside event. After "once", "when", "after" or "until",
# "I" or "we" with a verb of the session's own is a step in its own sequence; with a verb of receiving ("once I have
# it", "when I hear back") the thing still has to come from somewhere, and that is a wait.
R3_OWN_STEP_REVIEW = {"R3-01": "The branch is ready. I will resume after I update the snapshots."}
THE_SESSIONS_OWN_NEXT_STEP = {
    "continue-once-i-have-pushed": "I'll continue once I've pushed the rename.",
    "after-i-finish-i-resume": "After I finish the migration notes, I'll resume the review.",
    "continue-until-i-reach": "I'll continue until I reach the end of the list.",
    "proceed-when-we-are-done": "We'll proceed when we're done with the fixtures.",
    "resuming-after-i-rerun": "Resuming after I rerun the linter.",
    "pick-up-once-i-have-run": "I'll pick the refactor back up once I have run the last test file.",
    "follow-up-after-i-read": "I'll follow up after I read the second log.",
    "merge-when-i-have-checked": "I'll merge when I've checked the diff once more.",
    "finish-as-soon-as-i-get-to-it": "I'll finish the changelog as soon as I get to it.",
    "report-back-once-i-have-time": "I'll report back once I have time to read the whole trace.",
    "hold-until-i-have-rerun": "I'll hold the merge until I've rerun the suite on the rebased branch.",
    "holding-until-i-finish": "Holding the tag until I finish the changelog.",
}
WHAT_THE_SESSION_WAITS_TO_RECEIVE = {
    "resume-once-i-hear": "I'll resume once I hear back from the registrar.",
    "continue-when-i-get": "I'll continue when I get the vendor's file.",
    "proceed-as-soon-as-i-have-word": "I'll proceed as soon as I have word from legal.",
    "after-i-receive-i-finish": "After I receive the signed copy from the landlord, I'll finish the filing.",
    "merge-once-i-see": "I'll merge once I see the checks go green.",
    "follow-up-once-i-have-received": "I'll follow up once I've received the courier's answer.",
    "continue-when-i-am-told": "I'll continue when I'm told the export is ready.",
    "proceed-once-we-know": "We'll proceed once we know the audit result.",
    "resuming-when-i-hear": "Resuming when I hear from the vendor.",
    "an-own-step-then-an-event": "I'll continue after I update the snapshots, once the nightly build is green.",
    "hold-until-i-have-it": "The signed form is with the bank. I'll hold the filing until I have it.",
    "hold-until-i-hear": "I'll hold the release until I hear from the security team.",
    # "when I can" waits to be able: the one recorded reply of thirty days that this class touched, a true wait, said it.
    "report-back-when-i-can-reach-it": "The registry is down for maintenance. I'll report back when I can reach it again.",
    "resume-once-i-am-able-to": "I'll resume once I'm able to reach the staging database again.",
}


@pytest.mark.parametrize("reply", _cases(R3_OWN_STEP_REVIEW, THE_SESSIONS_OWN_NEXT_STEP))
def test_carrying_on_after_the_sessions_own_next_step_waits_on_nothing(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(WHAT_THE_SESSION_WAITS_TO_RECEIVE))
def test_carrying_on_once_something_is_received_is_still_a_wait(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# Finding 7 of the review: the check's own message names a last resort, "say plainly that nothing wakes this seat until
# they prompt it". A reply that says so has done what the check asks, and was sent back with the same advice.
R3_FALLBACK_REVIEW = {"R3-07": "The patch is committed. I am waiting for CI. Nothing wakes this seat until you prompt it."}
NOTHING_WAKES_THIS_SEAT = {
    "nothing-will-wake-this-session": "I'm waiting on the vendor's reply. Nothing will wake this session until you message it.",
    "nothing-is-armed-to-wake-me": "Waiting for the nightly export. Nothing is armed to wake me, so I'll pick it up at your next prompt.",
    "no-watcher-so-it-sleeps": "I'll merge once CI is green. No watcher is armed, so this seat sleeps until you prompt it.",
    "stays-asleep": "I'm waiting for the registrar. This seat stays asleep until your next message.",
    "i-will-not-see-it": "Once the export lands, I'll rebuild the index. I won't see it land until you prompt me.",
    "i-will-only-see-it-when": "I'm waiting for the build. I'll only see the result when you next prompt me.",
    "before-your-next-message": "Waiting on the second reviewer. Nothing wakes me before your next message.",
    "nothing-happens-here": "I'm waiting for the deploy to finish. Nothing happens here until you prompt me.",
    "nobody-wakes-this-seat": "I'll resume when the vendor replies. Nobody wakes this seat until you write again.",
    "will-not-wake": "I am waiting on the pipeline. This session will not wake until you nudge it.",
    "cannot-wake-myself": "I'm waiting for CI; I can't wake myself, so the next step comes with your next prompt.",
    "it-stays-idle": "I'm waiting on the vendor's patch. Nothing can wake this seat; it stays idle until you prompt it.",
    "i-am-idle": "The checks are still running, and I'll tag the release when they pass. I'm idle until you prompt me.",
    "in-a-list-item": "- The export: waiting on the warehouse.\n- Nothing wakes this seat until you prompt it.\n\nI'll load it once it lands.",
}
ONLY_SOUNDS_LIKE_THE_FALLBACK = {
    "another-seat": "I'm waiting on the reviewer's verdict. Nothing wakes her session until you prompt it.",
    "until-the-build-finishes": "I'm waiting on the build. Nothing wakes this seat until the build finishes.",
    "a-watcher-that-is-not-armed": "A watcher wakes this seat when CI finishes. I'm waiting for CI.",
    "in-the-past": "Nothing woke this seat overnight, so the release sat until you prompted it. I'm waiting for CI now.",
    "until-your-registrar": "I'm waiting on the domain transfer. Nothing wakes this seat until your registrar releases the domain.",
    "no-need-to-prompt": "You don't need to prompt me. I'm waiting for CI and will merge when it passes.",
    "in-quotation-marks": "The check asks for \"nothing wakes this seat until you prompt it\", which is not true here. I'm waiting for CI.",
    "a-worker-that-sleeps": "The worker sleeps until you prompt it from the console. I'm waiting on the queue to drain.",
    "until-they-send-it": "I won't see the vendor's reply until they send it. I'm waiting on their answer.",
    "prompt-me-if": "I'm waiting for CI. Prompt me if you want the logs first.",
    "in-a-code-fence": "The message to copy:\n```\nNothing wakes this seat until you prompt it.\n```\nI'm waiting for the registry to publish.",
}


@pytest.mark.parametrize("reply", _cases(R3_FALLBACK_REVIEW, NOTHING_WAKES_THIS_SEAT))
def test_a_reply_that_says_nothing_wakes_this_seat_until_the_principal_prompts_it_passes(reply):
    assert _sent_back(reply) is None


@pytest.mark.parametrize("reply", _cases(ONLY_SOUNDS_LIKE_THE_FALLBACK))
def test_a_reply_that_only_sounds_like_the_fallback_is_still_sent_back(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


# Finding 2 of the review: a code hands the principal the turn when it is offered for typing. One named as used, spent
# or replaced offers nothing, and any code form at all excused the whole reply. In the recorded replies 475 carry a code
# form; in four of them every code is a spent one, and two of those four announce a wait: one the harness held, and one
# true wait that passed. A spent code beside one that is offered leaves the offer standing.
R3_SPENT_CODE_REVIEW = {"R3-02": "The tests are complete. Approval code 1abcde was consumed earlier. I'm waiting on the registry."}
A_CODE_THAT_IS_SPENT = {
    "it-expired": "Code 2f9a01 expired before the send ran. I'm waiting on the registry to publish the package.",
    "it-has-expired-in-brackets": "The code for the calendar change (3e7b10) has expired. I'll file it again once the organizer's reply comes in.",
    "you-typed-it": "You typed approve 4a0c2d at noon and the note went out. I'll file the reply when the vendor answers.",
    "the-earlier-code": "The earlier code `5d1e3f` no longer applies. Waiting on the mirror to sync.",
    "do-not-use-the-old-codes": "Don't use the old codes `6b2f40` and `7e3a51`: both drafts changed. I'll merge once the checks pass.",
    "already-used": "The send went through: code 8c4b62 was already used for it. I'm waiting for the recipient's answer.",
    "replaced": "Code 9d5c73 was replaced when the text changed, and nothing is held now. I'm waiting on legal's redline.",
    "void-in-brackets": "The code from this morning (0e6d84) no longer applies, since the wording changed. I'm waiting for the two reviewers "
                        "before I stage it again.",
    "a-spent-label": "- **1f7e95:** expired, and nothing replaces it.\n\nI'm waiting on the venue's answer.",
}
A_CODE_OFFERED_BESIDE_A_SPENT_ONE = {
    "a-new-code-in-the-next-sentence": "Code 2a8fa6 expired, so I filed the send again. Type `approve 3b90b7` to release it. Once it's out, "
                                       "I'll read it back.",
    "a-new-code-in-the-same-sentence": "The old code died with the edit, so the send is up afresh as `approve 4ca1c8`. Once it's out, I'll read "
                                       "it back.",
    "a-new-label-under-the-old-one": "The earlier code `5db2d9` no longer applies.\n\n- **6ec3ea:** the same note, filed again.\n\nOnce it runs, "
                                     "I'll read it back.",
    "unless-it-has-lapsed": "For the reply to the editor: `approve 7fd4fb`, unless the code has lapsed by now. Once it's out, I'll log it.",
    "codes-from-this-morning-still-held": "Both approval codes from this morning are still held: 8ae50c and 2f9a01. Once both go through, I'll "
                                          "read them back.",
    "wording-seen-earlier": "The digest can go under code `3e7b10`, worded as you saw it earlier. Once it's sent, I'll track the replies.",
    "type-it-again": "The first try timed out, so it is up for your go a second time: type `approve 4a0c2d` and it leaves. Once it's out, I'll "
                     "read it back.",
}


@pytest.mark.parametrize("reply", _cases(R3_SPENT_CODE_REVIEW, A_CODE_THAT_IS_SPENT))
def test_a_code_named_as_used_or_spent_hands_the_principal_nothing(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(A_CODE_OFFERED_BESIDE_A_SPENT_ONE))
def test_a_code_offered_for_typing_still_hands_them_the_turn_beside_a_spent_one(reply):
    assert _sent_back(reply) is None


# Finding 4 of the review: a block between a BEGIN line and an END line excused the whole reply, whatever the block was
# and whatever the reply waited for. Its text is set aside, as quoted text is, and the rest is judged. Of 118 recorded
# replies with such a block, in none does the block alone excuse a wait outside it. Beside a block, a wait for it to be
# sent is a wait for the principal's go (the two staged messages in THE_PRINCIPALS_TURN above stay where they are).
R3_BLOCK_REVIEW = {"R3-04": "The delivery record is below.\nBEGIN\nYour invoice arrived.\nEND\nI'm waiting for the bank to respond."}
A_WAIT_BESIDE_A_BLOCK = {
    "after-the-block": "Here is the note I filed.\n\nBEGIN\nThe room is booked for Tuesday.\nEND\n\nI'll confirm the catering once the venue replies.",
    "before-the-block": "Still waiting on the registrar. For the record, the notice they sent:\nBEGIN\nYour transfer is pending.\nEND",
    "on-someone-else-after-a-staged-message": "The reply is staged.\n\n----- BEGIN -----\nThanks, Tuesday works.\n----- END -----\n\nSeparately, I'm "
                                              "waiting on the caterer's quote.",
    "sent-is-said-only-in-the-block": "BEGIN\nOnce it's sent, we will call you.\nEND\nI'll resume when the vendor's portal is back.",
    "a-code-only-in-the-block": "The text message as delivered:\nBEGIN\nYour sign-in code 482913 is valid for ten minutes.\nEND\nI'm waiting for the "
                                "portal to unlock the account.",
    "a-label-then-the-block": "The reply to the vendor:\nBEGIN\nFriday works.\nEND\nWaiting on the bank.",
}
A_WAIT_FOR_THE_BLOCK_TO_BE_SENT = {
    "once-it-goes-out": "The draft for the landlord:\n\nBEGIN\nThe signed lease is attached.\nEND\n\nOnce it goes out, I'll file the copy.",
    "after-it-has-been-sent": "BEGIN\nTuesday at ten works for us.\nEND\nAfter it has been sent, I'll update the calendar.",
    "once-the-note-is-sent": "Here it is.\n\n**BEGIN**\nThank you for the introduction.\n**END**\n\nI'll log it once the note is sent.",
    "a-wait-only-in-the-block": "Here is the holding reply.\n\nBEGIN\nWe're waiting on the printer and will confirm as soon as the proof "
                                "arrives.\nEND\n\nIt is ready whenever you are.",
}


@pytest.mark.parametrize("reply", _cases(R3_BLOCK_REVIEW, A_WAIT_BESIDE_A_BLOCK))
def test_a_block_between_begin_and_end_excuses_no_wait_outside_it(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(A_WAIT_FOR_THE_BLOCK_TO_BE_SENT))
def test_beside_a_block_a_wait_for_it_to_be_sent_awaits_the_principals_go(reply):
    assert _sent_back(reply) is None


# Finding 3 of the review: a request hands the principal the turn when it is put to them. After "and", "then" or a comma
# the same words may be one more verb of somebody else's ("the worker will restart and send me its result"), and that
# asks the principal for nothing. No recorded reply turns on this: the cases are written for the class.
R3_THIRD_PARTY_REVIEW = {"R3-03": "The build instructions are corrected. The worker will restart and send me its result. I'm waiting on "
                                  "the service."}
ONE_MORE_VERB_OF_SOMEBODY_ELSES = {
    "should-sign-and-send-me": "The vendor should sign today and send me the copy. I'm waiting on that.",
    "she-will-review-and-let-me-know": "She'll review the contract tonight and let me know. I'm waiting for her answer.",
    "asked-to-check-and-tell-me": "I asked the registrar to check the transfer and tell me the date. Waiting on their reply.",
    "waiting-for-the-bank-to-send-me": "I'm waiting for the bank to confirm the wire and send me the receipt.",
    "the-bot-will-then-message-me": "The deploy bot will then message me the result. I'll continue once it does.",
    "a-list-of-its-verbs": "The job will finish the export, send me the totals, and exit. I'll check them when it's done.",
}
STILL_A_REQUEST_PUT_TO_THEM = {
    "you-can-sign-and-send-me": "You can sign the form and send me a photo of it. I'll file it once the bank confirms.",
    "if-the-vendor-can-then-tell-me": "If the vendor can deliver by Friday, tell me and I'll book the room. I'm waiting on that.",
    "check-whether-it-will-and-tell-me": "Check whether the bank will accept the form and tell me. I'll wait.",
    "a-statement-so-tell-me": "The vendor will call at noon, so tell me what to say. Waiting on that before I draft the notes.",
    "wait-for-it-and-tell-me": "Wait for the build to finish and tell me what its last line says. I'll continue once I have it.",
    "you-will-need-to-and-tell-me": "You'll need to approve the prompt on your phone and tell me when it's through. I'm waiting on that.",
    "i-will-draft-then-tell-me": "I'll draft both versions tonight, then tell me which one reads better. I'll send it once the venue confirms.",
}


@pytest.mark.parametrize("reply", _cases(R3_THIRD_PARTY_REVIEW, ONE_MORE_VERB_OF_SOMEBODY_ELSES))
def test_one_more_verb_of_a_third_partys_is_no_request_to_the_principal(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(STILL_A_REQUEST_PUT_TO_THEM))
def test_a_request_put_to_the_principal_still_hands_them_the_turn(reply):
    assert _sent_back(reply) is None


# Finding 6 of the review: "going forward" anywhere in front of a wait made it a rule for next time. A rule phrase
# explains a wait when it governs the wait's own clause: it opens the sentence or a clause of it, and no new clause of
# the session's comes between it and the wait. No recorded reply turns on this either.
R3_INCIDENTAL_RULE_REVIEW = {"R3-06": "The proposed change going forward is documented, and I am waiting on the external review. The "
                                      "branch is ready."}
A_RULE_PHRASE_THAT_GOVERNS_SOMETHING_ELSE = {
    "in-a-noun-phrase": "The plan for next time is in the runbook and I'm waiting on the reviewer.",
    "opens-another-clause": "Going forward, the cache is rebuilt nightly, and I'm waiting for tonight's run to confirm it.",
    "between-commas": "The schedule, going forward, is weekly and I'm waiting on the first export.",
    "inside-the-event": "When the policy for every time zone is approved, I'll resume the rollout.",
    "what-to-do-next-time": "I wrote down what to do next time, and I'm now waiting on the vendor's fix.",
}
A_RULE_THAT_GOVERNS_THE_WAIT = {
    "after-and": "You're right, and from now on I'll wait for the checks before I merge.",
    "after-so": "The merge went out early, so going forward I'll hold the tag until the smoke test passes.",
    "whenever-opens": "Whenever a deploy is in flight, I'll wait for the health check before I report.",
    "as-a-rule-opens": "As a rule I'll wait for the second review before merging to main.",
    "inside-the-wait": "When a send fails, from now on I'll follow up once the retry returns.",
}


@pytest.mark.parametrize("reply", _cases(R3_INCIDENTAL_RULE_REVIEW, A_RULE_PHRASE_THAT_GOVERNS_SOMETHING_ELSE))
def test_a_rule_phrase_that_governs_something_else_explains_no_wait(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(A_RULE_THAT_GOVERNS_THE_WAIT))
def test_a_rule_phrase_that_governs_the_waits_own_clause_still_explains_it(reply):
    assert _sent_back(reply) is None


# Finding 5 of the review: a heading and a table row were dropped whole, and "we" before a colon was a label, so a wait
# the session states in the first person passed in each. A first-person wait is read wherever it stands. What is set
# aside is a label with no subject that names a state: "Waiting on X:", and such a wait in a heading or a table cell.
# The "we" form before a colon decides one recorded verdict in thirty days, a status line that counts what is open and
# lists it after the colon ("two-things" above). So "we" with a count or a pointer before the colon stays a label, and
# "we" with the thing itself named there is the wait it says, as "I" is. One recorded reply holds a first-person wait
# in a table cell, with background work out, so it was armed.
R3_STRUCTURE_REVIEW = {
    "R3-05-we-before-a-colon": "The patch is committed. We are waiting for the required pipeline: no further work is possible.",
    "R3-05-in-a-heading": "The patch is committed.\n## I'm waiting on CI\nThe branch is ready.",
    "R3-05-in-a-table-row": "The patch is committed.\n| State | I'm waiting on CI |\nThe branch is ready.",
}
A_FIRST_PERSON_WAIT_WHEREVER_IT_STANDS = {
    "after-a-label-in-a-heading": "## Where things stand: I'm waiting for the registrar\n\nNothing else is open.",
    "a-future-in-a-table-cell": "| Step | Status |\n|---|---|\n| Export | done |\n| Import | I'll start it once the export is verified by the "
                                "warehouse |",
    "a-subject-left-out-in-a-cell": "| Check | Next |\n|---|---|\n| CI | Will merge once it is green |",
    "a-hold-in-a-heading": "### I'm holding the tag until the smoke test passes\n| Check | State |\n|---|---|\n| smoke | running |",
    "we-and-the-thing-before-a-colon": "We're waiting on the certificate authority: the renewal is in their queue.",
    "we-will-before-a-colon": "We'll resume once the audit closes: the plan is in the runbook.",
    "i-before-a-colon": "I'm waiting on the mirror: the sync started at noon.",
}
A_LABEL_WITH_NO_SUBJECT_IN_A_HEADING_OR_A_CELL = {
    "a-heading-over-a-list": "## Waiting on the vendor\n\n- the signed order form\n- the tax certificate",
    "the-first-cell-of-a-row": "| Waiting on the vendor | 3 items |\n|---|---|\n| Done | 12 items |",
    "a-cell-after-a-sentence": "| Deploy | Done. Awaiting sign-off |\n| Docs | Published |",
    "resuming-in-a-cell": "| Step | State |\n|---|---|\n| Import | Resuming when the index rebuild is done |",
    "a-heading-that-names-the-list": "## What we're waiting on\n\n- the address\n- the DNS record",
    "we-and-a-bare-colon": "We're waiting on: the fee, the venue and the caterer's quote.",
    "we-and-a-count": "We are still waiting on three things from the landlord: the countersigned lease, the keys and the meter reading.",
}


@pytest.mark.parametrize("reply", _cases(R3_STRUCTURE_REVIEW, A_FIRST_PERSON_WAIT_WHEREVER_IT_STANDS))
def test_a_first_person_wait_is_read_in_a_heading_in_a_table_row_and_before_a_colon(reply):
    reason = _sent_back(reply)
    assert reason and "nothing is armed" in reason


@pytest.mark.parametrize("reply", _cases(A_LABEL_WITH_NO_SUBJECT_IN_A_HEADING_OR_A_CELL))
def test_a_label_with_no_subject_that_names_a_state_is_still_set_aside(reply):
    assert _sent_back(reply) is None


# A reply that ends by asking hands the principal the turn. A table or a heading after the question is not what the
# reply ends on: both cases passed while those lines were dropped whole, and reading them must not send them back.
A_QUESTION_BEFORE_A_TABLE_OR_A_HEADING = {
    "options-in-a-table": "I'm waiting on the venue's answer. Which of these should I hold in the meantime?\n\n| Option | Price |\n|---|---|\n"
                          "| Garden room | 400 |\n| Hall | 650 |",
    "a-heading-after-the-question": "I'll resume once the registrar replies. Do you want the long report or the short one?\n\n## Appendix",
}


@pytest.mark.parametrize("reply", _cases(A_QUESTION_BEFORE_A_TABLE_OR_A_HEADING))
def test_a_reply_that_ends_by_asking_still_passes_with_a_table_or_a_heading_after_the_question(reply):
    assert _sent_back(reply) is None


def test_a_table_after_a_wait_and_no_question_excuses_nothing():
    assert "nothing is armed" in _sent_back("I'm waiting on the venue's answer.\n\n| Option | Price |\n|---|---|\n| Garden room | 400 |")


# Findings 8, 9 and 10 of the review, on the reader of what the harness holds. Work is started by the harness's own
# tool-result entry, which is a `user` entry. It is ended by the harness's own notification, in one of the three forms
# it writes, with the tag opening the text. And no record, however malformed, makes the reader raise. In 112 recorded
# transcripts (2026-11-12) every launch the harness wrote is a `user` entry (1,921). 473 more are copies of one inside a
# record of a request, and 17 of those came after their call had reported: each started finished work a second time.
# Every notification the harness wrote opens with its tag (about 7,450). 418 more lines carry one inside other text
# (416 records of a request, one queued prompt, one message marked as meta); none of them named a call still out.
NOTED = "<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>toolu_1</tool-use-id>\n<status>completed</status>\n</task-notification>"
LAUNCHED = [{"type": "tool_result", "tool_use_id": "toolu_1", "content": BACKGROUND_WORK["an-agent"]}]
NOT_THE_HARNESSS_LAUNCH = {
    "R3-08-an-assistant-entry": _entry(type="assistant", message={"role": "assistant", "content": LAUNCHED}),
    "a-record-of-a-request": _entry(type="api-request-blob", message={"role": "user", "content": LAUNCHED}),
    "an-attachment": _entry(type="attachment", message={"role": "user", "content": LAUNCHED}),
    "an-entry-of-no-type": _entry(message={"role": "user", "content": LAUNCHED}),
    "a-type-that-is-no-string": _entry(type=["user"], message={"role": "user", "content": LAUNCHED}),
}
NOT_THE_HARNESSS_NOTIFICATION = {
    "R3-09-quoted-by-the-person": _entry(type="user", message={"role": "user", "content": "Here is an example: " + NOTED}),
    "R3-09-in-the-assistants-words": _entry(type="assistant", message={"role": "assistant", "content": "The tool printed " + NOTED}),
    "an-assistant-entry-that-opens-with-it": _entry(type="assistant", message={"role": "assistant", "content": NOTED}),
    "an-assistants-text-part": _entry(type="assistant", message={"role": "assistant", "content": [{"type": "text", "text": NOTED}]}),
    "quoted-in-a-queued-prompt": _entry(type="attachment", attachment={"type": "queued_command", "prompt": "Look at this: " + NOTED,
                                                                         "commandMode": "prompt"}),
    "quoted-in-a-queue-operation": _entry(type="queue-operation", operation="enqueue", content="Look at this: " + NOTED),
    "quoted-in-a-hooks-message": _entry(type="user", isMeta=True, message={"role": "user", "content": "Stop hook feedback: " + NOTED}),
    "in-a-record-of-a-request": _entry(type="api-request-blob", message={"role": "user", "content": NOTED}),
    "an-attachment-of-another-kind": _entry(type="attachment", attachment={"type": "file", "prompt": NOTED}),
    "an-entry-of-no-type": _entry(content=NOTED),
}
THE_HARNESSS_NOTIFICATION = {
    "a-user-entry-that-opens-with-the-tag": _entry(type="user", message={"role": "user", "content": "\n" + NOTED}),
    "a-task-notification-by-its-origin": _entry(type="user", origin={"kind": "task-notification"},
                                                message={"role": "user", "content": "Background task update\n" + NOTED}),
    "a-queue-operation-that-removes-it": _entry(type="queue-operation", operation="remove", content=NOTED),
}


@pytest.mark.parametrize("entry", _cases(NOT_THE_HARNESSS_LAUNCH))
def test_only_a_user_entrys_tool_result_starts_background_work(tmp_path, entry):
    assert "nothing is armed" in _with_record(A_WAIT, _record(tmp_path, entry))
    reported_then_copied = _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]), _reported("toolu_1"), entry)
    assert "nothing is armed" in _with_record(A_WAIT, reported_then_copied)             # a copy after the report starts nothing again


@pytest.mark.parametrize("entry", _cases(NOT_THE_HARNESSS_NOTIFICATION))
def test_a_notification_quoted_in_other_text_or_outside_the_harnesss_forms_ends_nothing(tmp_path, entry):
    assert _with_record(A_WAIT, _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]), entry)) is None


@pytest.mark.parametrize("entry", _cases(THE_HARNESSS_NOTIFICATION))
def test_each_form_of_the_harnesss_own_notification_ends_the_work_it_names(tmp_path, entry):
    assert "nothing is armed" in _with_record(A_WAIT, _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]), entry))


MALFORMED_RECORDS = {
    "R3-10-an-id-that-is-a-list": _started(["bad"], BACKGROUND_WORK["an-agent"]),
    "an-id-that-is-an-object": _started({"id": 1}, BACKGROUND_WORK["an-agent"]),
    "an-id-that-is-null": _started(None, BACKGROUND_WORK["an-agent"]),
    "an-id-that-is-a-number": _started(7, BACKGROUND_WORK["an-agent"]),
    "parts-of-every-wrong-kind": _entry(type="user", message={"role": "user", "content": [
        None, 7, "Async agent launched", ["tool_result"], {"type": "tool_result"}, {"type": "tool_result", "tool_use_id": "t", "content": 7},
        {"type": "tool_result", "tool_use_id": "t", "content": [None, 7, {"text": None}, {"text": ["Async agent launched"]}]}]}),
    "a-message-that-is-a-list": _entry(type="user", message=["tool_result", "Async agent launched"]),
    "content-that-is-an-object": _entry(type="user", message={"content": {"tool_result": "Async agent launched"}}),
    "an-origin-that-is-a-string": _entry(type="user", origin="task-notification", message={"role": "user", "content": ["<task-notification>"]}),
    "an-attachment-that-is-a-string": _entry(type="attachment", attachment="queued_command <task-notification>"),
    "a-prompt-that-is-a-list": _entry(type="attachment", attachment={"type": "queued_command", "prompt": ["<task-notification>"]}),
    "queue-content-that-is-an-object": _entry(type="queue-operation", content={"said": "<task-notification>"}),
    "a-line-cut-short": _started("toolu_1", BACKGROUND_WORK["an-agent"])[:-9],
    "nested-past-what-the-parser-takes": "[" * 100_000 + '"<task-notification>"',
    "a-bare-string": json.dumps(NOTED),
}


@pytest.mark.parametrize("line", _cases(MALFORMED_RECORDS))
def test_a_malformed_record_holds_nothing_and_raises_nothing(tmp_path, line):
    assert reply_check.held_by_harness(_record(tmp_path, line)) is False
    assert "nothing is armed" in _with_record(A_WAIT, _record(tmp_path, line))
    beside = _record(tmp_path, line, _started("toolu_2", BACKGROUND_WORK["a-shell-command"]), line)
    assert reply_check.held_by_harness(beside) is True                                  # and it hides nothing a sound record holds


@pytest.mark.parametrize("path", ["\u0000", "a\u0000b", "", None, 7.5, 2**40, ["x"], {"path": "x"}, b"bytes", "x" * 5000])
def test_a_path_that_cannot_be_used_holds_nothing_and_raises_nothing(path):
    assert reply_check.held_by_harness(path) is False


def test_a_number_given_as_the_path_names_no_file_descriptor(tmp_path):
    record = _record(tmp_path, _started("toolu_1", BACKGROUND_WORK["an-agent"]))
    descriptor = os.open(record, os.O_RDONLY)
    try:
        assert reply_check.held_by_harness(descriptor) is False                         # a number is no path: its descriptor is not read
        os.fstat(descriptor)                                                            # and not closed
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
