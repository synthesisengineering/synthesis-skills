"""R3.1: a message sent by computer use waits for the principal's code like any other send.

2026-10-22: a photo with a caption went out through computer_batch, a click on WhatsApp's Send button, and the
guard never ran, because it recognized sends by tool name. In a messaging app a click on Send, a Return in the
compose field, a typed line break and the Send menu item now wait for the code; reading and navigation do not.
These tests load the public example config (skills/synthesis-message-guard/config.example.json).
"""

import json
from pathlib import Path

import pytest

from synthesis import guards, sends

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
BATCH = "mcp__computer-use__computer_batch"
CLICK, KEY, TYPE, MENU = (f"mcp__computer-use__app_{n}" for n in ("click", "key", "type", "menu"))
WHATSAPP, MAIL, MESSAGES, NOTES = "net.whatsapp.WhatsApp", "com.apple.mail", "com.apple.MobileSMS", "com.apple.Notes"
SESSION = {"session_id": "S-principal"}
SEND_CLICK = {"actions": [{"action": "left_click", "coordinate": [1340, 793],
                           "action_summary": "Sends the photo with caption to +1 (555) 010-0199"},
                          {"action": "wait", "duration": 3}, {"action": "screenshot"}]}


def check(tool, tool_input, config=CONFIG):
    return guards.check(tool, tool_input, config, session=SESSION)


def grant(*apps):
    assert check("mcp__computer-use__request_access", {"apps": list(apps), "reason": "test"}) is None


def test_the_incident_send_waits_for_the_code_and_goes_once_approved(principal):
    grant("WhatsApp")
    reason = check(BATCH, SEND_CLICK)
    assert "approval of this exact call" in reason and WHATSAPP in reason and "Sends the photo" in reason
    principal(reason)
    assert check(BATCH, SEND_CLICK) is None
    assert sends.ledger(__import__("time").strftime("%Y-%m-%d"))[-1]["channel"] == "whatsapp"
    assert "approve" in check(BATCH, SEND_CLICK)  # one approval, one send


def test_an_approval_covers_only_the_call_it_was_given_for(principal):
    grant("WhatsApp")
    principal(check(BATCH, SEND_CLICK))
    moved = {"actions": [{**SEND_CLICK["actions"][0], "coordinate": [1340, 700]}]}
    assert "approve" in check(BATCH, moved)


@pytest.mark.parametrize("tool,call", [
    (CLICK, {"app": WHATSAPP, "coordinate": [417, 670], "action_summary": "Opens the chat with Pat"}),
    (BATCH, {"actions": [{"action": "screenshot", "scale": 0.5}, {"action": "zoom", "region": [0, 0, 9, 9]}]}),
    (BATCH, {"actions": [{"action": "left_click", "coordinate": [775, 794], "action_summary": "Opens the attach menu"},
                         {"action": "scroll", "coordinate": [5, 5], "scroll_direction": "down"}]}),
    (BATCH, {"actions": [{"action": "key", "text": "shift+Return",
                          "action_summary": "Inserts a line break in the caption without sending"}]}),
    (MENU, {"app": WHATSAPP, "list": "Window"}),
    (MENU, {"app": WHATSAPP, "path": ["Window", "Fill"], "action_summary": "Resizes the window to fill the screen"}),
    ("mcp__computer-use__app_screenshot", {"app": WHATSAPP}),
    ("mcp__computer-use__app_ax_find", {"app": WHATSAPP, "role": "AXButton"}),
])
def test_reading_and_navigating_a_messaging_app_need_no_code(tool, call):
    grant("WhatsApp")
    assert check(tool, call) is None


@pytest.mark.parametrize("tool,call", [
    (KEY, {"app": WHATSAPP, "combo": "return", "action_summary": "Presses Return in the compose field"}),
    (KEY, {"app": WHATSAPP, "combo": "cmd+return", "action_summary": "Presses Return"}),
    (KEY, {"app": MESSAGES, "combo": "shift+return", "action_summary": "Presses shift-Return"}),
    (KEY, {"app": MAIL, "combo": "cmd+shift+d", "action_summary": "Presses the shortcut"}),
    (KEY, {"app": MAIL, "combo": "cmd+Return", "action_summary": "Presses the shortcut"}),
    (TYPE, {"app": "com.tinyspeck.slackmacgap", "text": "On my way.\n", "action_summary": "Types the reply"}),
    (CLICK, {"app": "ru.keepcoder.Telegram", "coordinate": [10, 10]}),
    (MENU, {"app": MAIL, "path": ["Message", "Send"], "action_summary": "Chooses the menu item"}),
    ("mcp__computer-use__app_batch", {"app": "org.whispersystems.signal-desktop", "actions": [
        {"action": "click", "coordinate": [4, 4], "action_summary": "Focuses the compose field"},
        {"action": "type", "text": "Running late.", "action_summary": "Types the message"},
        {"action": "key", "combo": "return", "action_summary": "Presses Return"}]}),
])
def test_a_return_a_typed_line_break_a_send_shortcut_or_an_unsaid_click_waits(tool, call):
    assert "approval of this exact call" in check(tool, call)


@pytest.mark.parametrize("tool,call", [
    (KEY, {"app": MESSAGES, "combo": "option+return", "action_summary": "Inserts a line break"}),
    (KEY, {"app": MAIL, "combo": "return", "action_summary": "Starts a new paragraph"}),
    (TYPE, {"app": MAIL, "text": "The plan is attached.\n\nTuesday works.", "action_summary": "Types the body"}),
    (KEY, {"app": NOTES, "combo": "return", "action_summary": "Starts a new line"}),
    (CLICK, {"app": NOTES, "coordinate": [10, 10]}),
])
def test_keys_that_write_a_line_and_other_apps_need_no_code(tool, call):
    assert check(tool, call) is None


@pytest.mark.parametrize("summary", ["Sends the note to Pat", "Clicks Send", "Replies to the thread",
                                     "Posts the update in #general", "Shares the file with Pat"])
def test_an_action_that_says_it_sends_waits_in_any_app(summary):
    assert "approve" in check(CLICK, {"app": NOTES, "coordinate": [1, 1], "action_summary": summary})


def test_words_typed_in_a_messaging_app_pass_the_register_scan_as_they_are_typed():
    bad = "I'm sorry for the delay. I went quiet on you."
    reason = check(TYPE, {"app": WHATSAPP, "text": bad, "action_summary": "Types the reply"})
    assert reason.startswith("These words can't go out as written") and "delay-apology" in reason
    assert check(TYPE, {"app": NOTES, "text": bad, "action_summary": "Types a note"}) is None
    signed = "Here's the photo. 🤖 Sent by Helperbot (helperbot.example)"
    assert check(TYPE, {"app": WHATSAPP, "text": signed, "action_summary": "Types the caption"}) is None


def test_a_session_whose_grants_are_unseen_is_held_as_if_in_every_messaging_app():
    enter = {"actions": [{"action": "key", "text": "Return", "action_summary": "Selects the file in the picker"}]}
    assert "request_access" in check(BATCH, enter)
    assert check("mcp__computer-use__request_access", {"apps": "Notes"}) is None
    assert "request_access" in check(BATCH, enter)  # a malformed request records nothing
    grant("Notes", "Finder")
    assert check(BATCH, enter) is None
    grant("Messages")
    assert "approve" in check(BATCH, enter)
    assert check(BATCH, {"actions": [{"action": "key", "text": "option+Return", "action_summary": "Line break"}]}) is None


def test_teach_steps_and_a_linked_device_are_held_the_same_way():
    grant("Slack")
    step = {"explanation": "x", "next_preview": "y", "actions": [
        {"action": "left_click", "coordinate": [1, 1], "action_summary": "Sends the message"}]}
    assert "approve" in check("mcp__computer-use__teach_step", step)
    assert "approve" in check("mcp__computer-use__teach_batch", {"steps": [step]})
    assert "approve" in guards.check("mcp__remote-devices__computer_batch", SEND_CLICK, CONFIG, session={})


@pytest.mark.parametrize("tool,name", [(BATCH, "batch"), (CLICK, "app_click"), ("mcp__remote-devices__computer_batch", "batch"),
                                       ("mcp__computer-use__app_screenshot", ""), ("mcp__claude-in-chrome__computer", "browser"),
                                       ("mcp__Claude_Browser__browser_batch", "browser_batch"), ("mcp__notes__type", ""),
                                       ("mcp__plugin_playwright_playwright__browser_click", ""), ("mcp__computer-use__key", "key"),
                                       ("mcp__claude-in-chrome__javascript_tool", "browser_script"),
                                       ("mcp__Claude_Browser__form_input", "browser_form")])
def test_computer_use_tools_are_recognized_by_name_on_any_server(tool, name):
    assert guards.desktop_tool(tool) == name
    assert guards.guarded(tool, {}) is bool(name)


CHROME, PANE = "mcp__claude-in-chrome__browser_batch", "mcp__Claude_Browser__computer"


def _steps(*steps):
    return {"actions": [{"name": n, "input": i} for n, i in steps]}


@pytest.mark.parametrize("tool,call", [
    (CHROME, _steps(("computer", {"action": "left_click", "ref": "ref_9",
                                  "action_summary": "Sends the approved message to Pat on LinkedIn"}))),
    (PANE, {"action": "left_click", "coordinate": [5, 5], "action_summary": "Publishes the approved post"}),
    ("mcp__claude-in-chrome__computer", {"action": "left_click", "coordinate": [5, 5], "action_summary": "Clicks the Send button"}),
])
def test_a_browser_action_that_says_it_sends_waits_for_the_code(tool, call):
    assert "sends in the browser" in check(tool, call)


@pytest.mark.parametrize("call", [
    _steps(("navigate", {"url": "https://example.com/inbox"}), ("find", {"query": "Send"}),
           ("computer", {"action": "left_click", "ref": "ref_1", "action_summary": "Opens the inbox"})),
    _steps(("computer", {"action": "left_click", "ref": "ref_2", "action_summary": "Closes the send options menu"})),
    _steps(("computer", {"action": "key", "text": "Return", "action_summary": "Submits the search"})),
    _steps(("form_input", {"ref": "ref_3", "value": "I'm sorry for the delay.", "action_summary": "Fills the search box"})),
])
def test_browsing_and_searching_need_no_code(call):
    assert check(CHROME, call) is None


def test_words_a_browser_send_carries_pass_the_register_scan_first():
    call = _steps(("form_input", {"ref": "ref_3", "value": "I'm sorry for the delay.", "action_summary": "Fills the reply"}),
                  ("computer", {"action": "left_click", "ref": "ref_4", "action_summary": "Sends the reply"}))
    assert "delay-apology" in check(CHROME, call)


def _result(ident, tool, front, tabs):
    """A tool call and its result listing these tabs, the call having run on front."""
    listing = "\n".join(f'  \u2022 tabId {t[3:]}: "Inbox \u2013 \"Team\" (3)" ("{u}")' for t, u in tabs.items())
    text = f"Clicked\n\nTab Context:\n- Executed on tabId: {front}\n- Available tabs:\n{listing}"
    call = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": ident, "name": tool, "input": {}}]}}
    result = {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": text}]}]}}
    return json.dumps(call) + "\n" + json.dumps(result) + "\n"


def _on(tmp_path, front, **tabs):
    """A session whose transcript's newest browser result lists these tabs."""
    path = tmp_path / "transcript.jsonl"
    path.write_text(_result("toolu_1", CHROME, front, tabs), encoding="utf-8")
    return {**SESSION, "transcript_path": str(path)}


RETURN = ("computer", {"action": "key", "text": "Return", "action_summary": "Presses Return in the compose box"})


@pytest.mark.parametrize("url", ["https://chat.google.com/room/AAA", "https://mail.google.com/chat/u/0/#chat/dm/x",
                                 "https://app.slack.com/client/T1/C2", "https://example.slack.com/archives/C2",
                                 "https://web.whatsapp.com/", "https://www.linkedin.com/messaging/thread/2-x/",
                                 "https://teams.microsoft.com/v2/", "https://www.facebook.com/messages/t/1234567890/",
                                 "https://web.facebook.com/messages/", "https://www.instagram.com/direct/t/1234/"])
def test_return_on_a_messaging_site_waits_for_the_code(tmp_path, url):
    """2026-10-22: Return in a Google Chat compose box went out with no code, since a page counted as no app."""
    reason = guards.check(CHROME, _steps(RETURN), CONFIG, session=_on(tmp_path, 7, tab7=url))
    assert "approve" in reason and "sends in the browser (" in reason


@pytest.mark.parametrize("url, step", [
    ("https://docs.google.com/document/d/x", RETURN),                         # not a messaging site
    ("https://outlook.office.com/mail/inbox", RETURN),                        # Return writes a line in an email
    ("https://chat.google.com/room/AAA", ("computer", {"action": "key", "text": "shift+Return",
                                                       "action_summary": "Starts a new line"})),
    ("https://mail.google.com/mail/u/0/#inbox", ("computer", {"action": "key", "text": "shift+Return",
                                                              "action_summary": "Starts a new line"})),
])
def test_return_that_writes_a_line_or_is_elsewhere_needs_no_code(tmp_path, url, step):
    assert guards.check(CHROME, _steps(step), CONFIG, session=_on(tmp_path, 7, tab7=url)) is None


@pytest.mark.parametrize("url", ["https://www.facebook.com/", "https://facebook.com/groups/1/", "https://www.linkedin.com/feed/",
                                 "https://www.facebook.com/search/top?q=x", "https://www.instagram.com/p/x/"])
def test_every_facebook_instagram_and_linkedin_page_holds_return(tmp_path, url):
    """2026-11-14: the guard knew www.messenger.com, but Messenger also runs inside facebook.com, in its own page and in
    chat pop-ups on every page, and Return in a comment box posts in the principal's name. A page cannot show which box
    has the focus, so every page of the two sites holds Return, a search box's included. LinkedIn's messages open in
    an overlay on every page too. Over 30 days of recorded browser calls, none of the 55 Return presses was on these
    sites (43 were on other sites, 12 on pages the record does not place); the control counted 320 calls on LinkedIn in
    all, 290 on its messages and 30 elsewhere, and 10 on facebook.com. Holding them costs nothing measured."""
    reason = guards.check(CHROME, _steps(RETURN), CONFIG, session=_on(tmp_path, 7, tab7=url))
    assert "approve" in reason and "sends in the browser (" in reason


def _opened(url, *steps):
    """The steps on tab 7, after a navigate step to url earlier in the same batch."""
    return _steps(("navigate", {"url": url, "tabId": 7}), *[(n, {**i, "tabId": 7}) for n, i in steps])


@pytest.mark.parametrize("url", [
    "linkedin.com/messaging/thread/2-x/", "https://linkedin.com/feed/", "http://linkedin.com/in/pat",
    "https://uk.linkedin.com/in/pat", "messenger.com/t/123", "https://m.me/pat", "https://fb.com/messages/t/1",
    "https://fb.me/pat", "https://instagr.am/p/x/", "https://ig.me/m/pat", "https://wa.me/15550100199",
    "whatsapp.com/send?phone=15550100199", "https://api.whatsapp.com/send?phone=15550100199", "https://twitter.com/messages",
    "https://mobile.twitter.com/messages", "https://chat.x.com/", "https://x.com/i/chat/1", "https://x.com/home",
    "https://canary.discord.com/channels/1/2", "https://discordapp.com/channels/1/2", "https://discord.gg/abc",
    "https://t.me/pat", "https://telegram.org/", "https://slack.com/", "https://teams.cloud.microsoft/v2/",
])
def test_every_host_the_browser_lands_on_a_messaging_site_from_holds_return(url):
    """The review of 5.21.0: the guard matched the host as typed, so a batch that navigated to `linkedin.com/...`,
    `uk.linkedin.com`, `messenger.com`, `m.me` or `fb.com` and pressed Return went out with no code, while the browser
    landed on www.linkedin.com or www.messenger.com. A site is its host and every host under it, with the short hosts
    that land on one, and Teams' web app, which moved to teams.cloud.microsoft in 2026."""
    assert "approve" in check(CHROME, _opened(url, RETURN))


@pytest.mark.parametrize("url", ["https://notlinkedin.com/feed/", "https://linkedin.com.example.org/feed/",
                                 "https://www.google.com/search?q=chat", "https://outlook.cloud.microsoft/mail/"])
def test_a_look_alike_host_and_an_email_page_still_take_return(url):
    assert check(CHROME, _opened(url, RETURN)) is None  # Return writes a line in an email


def test_outlooks_new_address_holds_its_send_shortcut():
    send = ("computer", {"action": "key", "text": "cmd+Return", "action_summary": "Presses the shortcut"})
    assert "approve" in check(CHROME, _opened("https://outlook.cloud.microsoft/mail/", send))


ONLY = [{"name": "messenger-only", "pattern": "ttyl", "channels": ["messenger"], "why": "not in Messenger"},
        {"name": "facebook-only", "pattern": "fwiw", "channels": ["facebook"], "why": "not on Facebook"},
        {"name": "instagram-only", "pattern": "dm me", "channels": ["instagram"], "why": "not on Instagram"}]


@pytest.mark.parametrize("url, rules", [
    ("https://m.facebook.com/messages/t/1", ["messenger-only"]), ("https://web.facebook.com/messages/", ["messenger-only"]),
    ("https://facebook.com/messages/t/1", ["messenger-only"]), ("https://fb.com/messages/t/1", ["messenger-only"]),
    ("https://www.messenger.com/t/1", ["messenger-only"]), ("https://m.me/pat", ["messenger-only"]),
    ("https://business.facebook.com/latest/inbox/all", ["messenger-only", "facebook-only", "instagram-only"]),
    ("https://www.facebook.com/groups/1/", ["messenger-only", "facebook-only"]),  # a Messenger pop-up, or a comment
])
def test_messengers_channel_reaches_its_other_hosts_its_inbox_and_its_pop_ups(url, rules):
    """The review of 5.21.0: only www.facebook.com/messages was `messenger`, so a register rule for Messenger missed it
    on m.facebook.com, in Business Suite's inbox and in the pop-ups on every other page of facebook.com."""
    config = {**CONFIG, "forbidden_phrases": ONLY}
    for rule in ONLY:
        words = ("form_input", {"ref": "ref_3", "value": f"ok {rule['pattern']}", "action_summary": "Fills the reply"})
        reason = check(CHROME, _opened(url, words, RETURN), config) or ""
        assert (rule["name"] in reason) is (rule["name"] in rules), (url, rule["name"])


PUBLISHERS = ["Clicks the Post button", "Clicks Comment", "Presses the Reply button", "Taps Share",
              "Clicks on the Repost option", "Clicks “Publish”", "Clicks Submit", "Clicks on Send",
              "Fills nothing, then clicks the Post button"]


@pytest.mark.parametrize("url", ["https://www.facebook.com/groups/1/", "https://www.linkedin.com/feed/",
                                 "https://www.instagram.com/p/x/", "https://x.com/home"])
@pytest.mark.parametrize("summary", PUBLISHERS)
def test_a_click_on_a_control_that_publishes_waits_on_these_sites(url, summary):
    """The review of 5.21.0: Return was held on these sites, but a click on Post, Comment, Reply or Share went out with no
    code, since the summary rule took a click verb for a send only with Send as its object."""
    fill = ("form_input", {"ref": "ref_2", "value": "Congratulations, Pat", "action_summary": "Fills the comment box"})
    click = ("computer", {"action": "left_click", "ref": "ref_9", "action_summary": summary})
    assert "approve" in check(CHROME, _opened(url, fill, click))


@pytest.mark.parametrize("summary", ["Clicks Comment to open the comment box", "Clicks the comment box",
                                     "Clicks the Reply link, which opens a reply box", "Clicks Share to show the share options",
                                     "Clicks the Repost button to open its menu", "Opens the comment box under the post",
                                     "Clicks the Like button"])
def test_a_click_that_only_opens_a_box_passes_on_these_sites(summary):
    click = ("computer", {"action": "left_click", "ref": "ref_9", "action_summary": summary})
    assert check(CHROME, _opened("https://www.linkedin.com/feed/", click)) is None


@pytest.mark.parametrize("summary", PUBLISHERS + ["Clicks the Submit rating button", "Presses the Post review button"])
def test_a_click_on_a_control_that_publishes_waits_on_every_page(summary):
    """2026-11-13: a public review typed and submitted through the browser on a site that is no messaging site went out
    with no code, since there only a click on Send counted. Over 30 days of records no click named one of these
    controls on any site, so holding them everywhere costs nothing measured."""
    fill = ("form_input", {"ref": "ref_2", "value": "Great work, thank you", "action_summary": "Fills the review box"})
    click = ("computer", {"action": "left_click", "ref": "ref_9", "action_summary": summary})
    assert "approve" in check(CHROME, _opened("https://www.example.com/tasks/1/review", fill, click))


def test_a_click_that_only_opens_a_box_passes_on_any_page():
    click = ("computer", {"action": "left_click", "ref": "ref_9", "action_summary": "Clicks Comment to open the comment box"})
    assert check(CHROME, _opened("https://example.com/forum/", click)) is None
    assert check(CHROME, _opened("https://example.com/forum/", ("computer", {**click[1], "action_summary": "Clicks the Like button"}))) is None


SEARCH = ("form_input", {"ref": "ref_3", "value": "I'm sorry for the delay.", "action_summary": "Fills the search box"})


def test_words_typed_with_nothing_sent_on_these_sites_can_go_on_a_code(principal):
    """The review of 5.21.0: on every page of these sites typed words faced the register scan with nothing sent, so a
    search word that hit a rule was refused and no code could release it. A call that only types, on a page where a box
    may be a search, is still scanned; it goes on the principal's code, which names the rule it broke."""
    search = _opened("https://www.linkedin.com/feed/", SEARCH)
    reason = check(CHROME, search)
    assert "delay-apology" in reason and "approve followed by the code" in reason and "sends nothing" in reason
    principal(reason)
    assert check(CHROME, search) is None
    assert "approve" in check(CHROME, search)  # one code, one call


@pytest.mark.parametrize("url, steps", [
    ("https://www.linkedin.com/feed/", [SEARCH, RETURN]),  # a call that sends
    ("https://www.linkedin.com/feed/", [SEARCH, ("computer", {"action": "left_click", "ref": "ref_4",
                                                            "action_summary": "Clicks the blue button"})]),  # it does more
    ("https://www.linkedin.com/messaging/thread/2-x/", [SEARCH]),  # a page of messages, where typing is writing one
    ("https://chat.google.com/room/AAA", [SEARCH]),
    ("https://www.facebook.com/messages/t/1", [SEARCH]),
    ("https://mail.google.com/mail/u/0/#inbox", [SEARCH]),  # Gmail's pages only get stricter
])
def test_words_that_break_a_rule_in_a_call_that_sends_or_on_a_page_of_messages_are_refused_outright(url, steps):
    reason = check(CHROME, _opened(url, *steps))
    assert reason.startswith("These words can't go out as written") and "approve" not in reason


def test_an_email_sites_send_shortcut_and_a_typed_line_break_in_chat_wait(tmp_path):
    send = ("computer", {"action": "key", "text": "cmd+Return", "action_summary": "Presses the shortcut"})
    assert "approve" in guards.check(CHROME, _steps(send), CONFIG,
                                     session=_on(tmp_path, 7, tab7="https://mail.google.com/mail/u/0/#inbox"))
    typed = ("computer", {"action": "type", "text": "On my way\n", "action_summary": "Types the reply"})
    assert "approve" in guards.check(CHROME, _steps(typed), CONFIG,
                                     session=_on(tmp_path, 7, tab7="https://chat.google.com/room/AAA"))


GMAIL = ["https://mail.google.com/mail/u/0/#inbox", "https://mail.google.com/mail/u/0/#inbox/FMfcgzQ",
         "https://mail.google.com/mail/u/1/?compose=new", "https://mail.google.com/mail/u/0/#search/plan",
         "https://mail.google.com/mail/u/0/#chat/dm/x"]


@pytest.mark.parametrize("url", GMAIL)
@pytest.mark.parametrize("step", [
    RETURN, ("computer", {"action": "type", "text": "On my way\n", "action_summary": "Types the reply"}),
    ("form_input", {"ref": "ref_3", "value": "See you then\n", "action_summary": "Fills the reply"}),
    ("computer", {"action": "key", "text": "cmd+Return", "action_summary": "Presses the shortcut"}),
    ("computer", {"action": "key", "text": "ctrl+Enter", "action_summary": "Presses the shortcut"}),
    ("computer", {"action": "left_click", "ref": "ref_9", "action_summary": "Clicks the Send button"}),
])
def test_every_gmail_page_holds_return_a_typed_line_break_a_send_click_and_the_send_shortcut(tmp_path, url, step):
    """Google Chat runs in pop-ups on Gmail's own pages too, where Return sends. Those pages counted as email, where
    Return writes a line, so Return in a pop-up went out with no code. A page cannot show which box has the focus, and
    over 30 days of recorded browser calls none pressed Return or typed a line break on Gmail's pages (2026-11-14)."""
    assert "approve" in (check(CHROME, _opened(url, step)) or "")  # a page a navigate step opened
    assert "approve" in (guards.check(CHROME, _steps(step), CONFIG, session=_on(tmp_path, 7, tab7=url)) or "")  # the tab list's


def test_a_rule_for_google_chat_holds_on_gmails_pages_and_one_for_email_still_does():
    rules = [{"name": "chat-only", "pattern": "ttyl", "channels": ["google chat"], "why": "not in Chat"},
             {"name": "email-only", "pattern": "fwiw", "channels": ["email"], "why": "not in email"}]
    for url, held in (("https://mail.google.com/mail/u/0/#inbox", {"chat-only", "email-only"}),  # a pop-up, or a draft
                      ("https://mail.google.com/chat/u/0/#chat/dm/x", {"chat-only"}),
                      ("https://outlook.office.com/mail/inbox", {"email-only"})):
        for rule in rules:
            words = ("form_input", {"ref": "ref_3", "value": f"ok {rule['pattern']}", "action_summary": "Fills the reply"})
            reason = check(CHROME, _opened(url, words), {**CONFIG, "forbidden_phrases": rules}) or ""
            assert (rule["name"] in reason) is (rule["name"] in held), (url, rule["name"])


# The second review of 5.21.0 (with 5.21.1): what still went out, and what was held for nothing.
REVIEWS = "https://www.example-reviews.com/business/acme/review"
REVIEW = ("form_input", {"ref": "ref_2", "value": "Prompt, careful work. Five stars.", "action_summary": "Fills the review box"})


def _click(summary):
    return ("computer", {"action": "left_click", "ref": "ref_9", "action_summary": summary})


def _key(keys, summary="Presses the key"):
    return ("computer", {"action": "key", "text": keys, "action_summary": summary})


@pytest.mark.parametrize("call", [_opened(REVIEWS, REVIEW, _click("Submits the five-star public review of Pat")),
                                  _steps(REVIEW, _click("Submits the five-star public review of Pat"))])
def test_the_incidents_own_effect_first_summary_waits(call):
    """2026-11-13: the review went out through two clicks on its Submit rating control (12:56 and 12:57 EST). The record
    holds each one's summary in the form the tools ask for, effect first, "Submits the five-star public review of" a
    person, and 5.21.1's rule wanted a click verb before the label. Here with a placeholder for the person."""
    assert "approve" in (check(CHROME, call) or "")


@pytest.mark.parametrize("summary", [
    "Reposts the update to the principal's feed", "Submits the comment", "Clicks the blue Post button",
    "Clicks LinkedIn's Post button", "Clicking Post", "Clicked the Post button", "Clicks Post; the comment then shows under Pat's update",
    "Clicks Reply, posting the reply that starts with 'Congratulations'", "Clicks Comment to publish it, which shows it under the post",
    "Retweets the post", "Quotes the post with a comment"])
def test_accurate_summaries_of_a_click_that_posts_wait(summary):
    fill = ("form_input", {"ref": "ref_2", "value": "Congratulations, Pat", "action_summary": "Fills the comment box"})
    assert "approve" in (check(CHROME, _opened("https://www.linkedin.com/feed/", fill, _click(summary))) or "")


@pytest.mark.parametrize("summary", ["Clicks Comment to open the comment box", "Opens the photo", "Clicks the Like button",
                                     "Clicks the comment box", "Clicks Done to close the dialog", "Clicks Share to open the share menu"])
def test_a_click_that_only_opens_or_closes_a_box_passes(summary):
    assert check(CHROME, _opened("https://www.linkedin.com/feed/", _click(summary))) is None


@pytest.mark.parametrize("steps", [
    [REVIEW, _click("Clicks the blue Submit rating button")], [REVIEW, _click("Clicking Submit rating")],
    [REVIEW, _click("Clicks Submit rating, which shows the review on the page")], [REVIEW, _click("Clicks the Add comment button")],
    [REVIEW, _click("Clicks the Tweet button")], [REVIEW, _click("Clicks Done to finish the review")],
    [REVIEW, _key("Return", "Presses Return")], [("computer", {"action": "type", "text": "Five stars.\n", "action_summary": "Types the review"})],
    [REVIEW, _key("Tab space", "Moves to the button and presses it")], [REVIEW, _key("Tab"), _key("space")],
    [REVIEW, ("javascript_tool", {"action": "javascript_exec", "text": "document.forms[0].requestSubmit()"})],
    [("computer", {"action": "type", "text": "Summarize the attached plan."}), _key("Return")],  # it says neither: held when unsure
])
def test_other_ways_a_review_is_submitted_on_a_site_that_is_no_messaging_site_wait(steps):
    """The second review: on a page that is no messaging site, a word before the label, an -ing form, a later "shows",
    a label outside the list, Return or Tab then Space after the words, a typed line break and a page script went out."""
    assert "approve" in (check(CHROME, _opened(REVIEWS, *steps)) or "")


@pytest.mark.parametrize("url, steps", [
    ("https://www.example.com/login", [("form_input", {"ref": "ref_1", "value": "test-user", "action_summary": "Fills the username"}),
                                       _click("Clicks the Submit button to sign in")]),
    ("http://localhost:3000/login", [("form_input", {"ref": "ref_1", "value": "test-user"}), _click("Clicks the Submit button")]),
    ("https://www.example.com/search", [("form_input", {"ref": "ref_1", "value": "garden hose", "action_summary": "Fills the search box"}),
                                        _click("Clicks Submit to run the search")]),
    ("https://www.example.com/", [("form_input", {"ref": "ref_1", "value": "garden hose", "action_summary": "Fills the search box"}),
                                  _key("Return", "Submits the search")]),
    ("http://127.0.0.1:8080/form", [("computer", {"action": "type", "text": "hello\n", "action_summary": "Types the text"})]),
    ("https://www.example.com/login", [("form_input", {"ref": "ref_2", "value": "s3cret-test-pass", "action_summary": "Fills the password"}),
                                       _key("Return", "Presses Return")]),
])
def test_a_sign_in_a_search_and_the_principals_own_local_app_pass(url, steps):
    """The second review: 5.21.1 held a sign-in, a site search and the principal's own app on localhost, which post
    nothing. A summary that signs in or searches and names nothing that posts passes, as does a local app's page."""
    assert check(CHROME, _opened(url, *steps)) is None


def test_typed_words_never_land_in_an_approval_record_in_plain_text():
    from synthesis import paths
    call = _opened("https://www.example.com/account", ("form_input", {"ref": "ref_2", "value": "s3cret-test-pass"}),
                   _click("Clicks the Submit button"))
    assert "approve" in (check(CHROME, call) or "")
    stored = [f.read_text(encoding="utf-8") for f in (paths.state() / "approval-requests").glob("*.json")]
    assert stored and not any("s3cret-test-pass" in text for text in stored)


def test_a_register_hit_in_a_send_on_a_site_that_is_no_messaging_site_goes_on_a_code_that_names_it(principal):
    words = ("form_input", {"ref": "ref_2", "value": "Sorry for the delay in reviewing; great work", "action_summary": "Fills the review box"})
    call = _opened(REVIEWS, words, _click("Clicks the Submit rating button"))
    reason = check(CHROME, call) or ""
    assert "delay-apology" in reason and "approve followed by the code" in reason
    principal(reason)
    assert check(CHROME, call) is None


@pytest.mark.parametrize("script", [
    "document.querySelector('button.comments-comment-box__submit-button').click()",
    "document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))",
    "fetch('/voyager/api/messaging/conversations', {method: 'POST', body: '{}'})"])
def test_a_page_script_that_can_send_on_a_messaging_site_waits(tmp_path, script):
    """The second review: a page script never reached the send guard, so one that clicks a comment's submit button or
    presses Enter in LinkedIn's message overlay went out with no code."""
    session = _on(tmp_path, 7, tab7="https://www.linkedin.com/feed/")
    alone = {"action": "javascript_exec", "text": script, "tabId": 7}
    assert "approve" in (guards.check("mcp__claude-in-chrome__javascript_tool", alone, CONFIG, session=session) or "")
    fill = ("form_input", {"ref": "ref_2", "value": "Congratulations, Pat", "action_summary": "Fills the comment box"})
    assert "approve" in (check(CHROME, _opened("https://www.linkedin.com/feed/", fill, ("javascript_tool", alone))) or "")


@pytest.mark.parametrize("url, script", [
    ("https://www.linkedin.com/feed/", "[...document.querySelectorAll('h2')].map(h => h.innerText).join(', ')"),
    ("https://www.example.com/list", "document.querySelector('.load-more').click()"),
    ("https://www.example.com/", "document.querySelector('form#search').requestSubmit()"),
])
def test_a_page_script_that_reads_expands_a_list_or_searches_passes(tmp_path, url, script):
    alone = {"action": "javascript_exec", "text": script, "tabId": 7}
    assert guards.check("mcp__claude-in-chrome__javascript_tool", alone, CONFIG, session=_on(tmp_path, 7, tab7=url)) is None


def test_a_form_fill_alone_passes_the_register_scan(tmp_path):
    fill = {"ref": "ref_3", "value": "I'm sorry for the delay.", "action_summary": "Fills the reply", "tabId": 7}
    reason = guards.check("mcp__claude-in-chrome__form_input", fill, CONFIG, session=_on(tmp_path, 7, tab7="https://chat.google.com/room/AAA"))
    assert reason and "delay-apology" in reason


def test_a_send_after_words_the_typed_code_released_shows_them_and_their_rule(principal):
    """The second review: words released by the typed-words code ("nothing sent, may be a search"), then a Return in the
    next call, waited for a code whose hold named neither the words nor the rule they broke."""
    search = _opened("https://www.linkedin.com/feed/", SEARCH)
    principal(check(CHROME, search))
    assert check(CHROME, search) is None
    reason = check(CHROME, _opened("https://www.linkedin.com/feed/", RETURN)) or ""
    assert "approve" in reason and "I'm sorry for the delay." in reason and "delay-apology" in reason


@pytest.mark.parametrize("url, keys", [
    ("https://gmail.com/", "Return"), ("https://www.google.com/gmail/", "Return"), ("https://gmail.com/", "cmd+Return"),
    ("https://outlook.com/", "ctrl+Return"), ("https://www.hotmail.com/", "ctrl+Return"), ("https://live.com/mail/0/", "ctrl+Return"),
    ("https://voice.google.com/u/0/messages", "Return")])
def test_gmail_outlook_and_google_voice_reached_by_the_host_typed_hold_their_send_keys(url, keys):
    """The second review: R1-5's class. Gmail and Outlook by the host a person types, and Google Voice's texts."""
    assert "approve" in (check(CHROME, _opened(url, _key(keys))) or "")


def test_return_on_outlook_by_its_short_host_writes_a_line():
    assert check(CHROME, _opened("https://outlook.com/mail/", RETURN)) is None


def test_the_page_is_the_tab_each_step_names_or_the_one_a_navigate_step_opened(tmp_path):
    session = _on(tmp_path, 7, tab7="https://docs.google.com/document/d/x", tab8="https://chat.google.com/room/AAA")
    assert guards.check(CHROME, _steps(RETURN), CONFIG, session=session) is None
    named = ("computer", {**RETURN[1], "tabId": 8})
    assert "approve" in guards.check(CHROME, _steps(named), CONFIG, session=session)
    assert "approve" in guards.check("mcp__claude-in-chrome__computer", {**RETURN[1], "tabId": 8}, CONFIG, session=session)
    opened = ("navigate", {"url": "app.slack.com/client/T1/C2", "tabId": 7})
    assert "approve" in guards.check(CHROME, _steps(opened, RETURN), CONFIG, session=session)


def test_a_navigate_that_names_no_host_keeps_a_messaging_sites_page(tmp_path):
    """Hold when unsure: `back`, `forward`, a path or a script names no page, and from a messaging site's page the page
    it opens may be that site's still, so it is judged as that site's; from any other page it is unknown, as before."""
    for where, held in (("https://www.facebook.com/groups/1/", True), ("https://docs.google.com/document/d/x", False)):
        session = _on(tmp_path, 7, tab7=where)
        for url in ("back", "forward", "/messages/t/1", "javascript:void(0)"):
            reason = guards.check(CHROME, _steps(("navigate", {"url": url, "tabId": 7}), RETURN), CONFIG, session=session)
            assert bool(reason and "approve" in reason) is held, (where, url)


def test_a_tab_list_printed_by_another_tool_is_not_the_browsers(tmp_path):
    """A shell that prints a transcript (or anything shaped like a tab list) does not move the browser's page."""
    session = _on(tmp_path, 7, tab7="https://chat.google.com/room/AAA")
    with open(session["transcript_path"], "a", encoding="utf-8") as transcript:
        transcript.write(_result("toolu_2", "Bash", 7, {"tab7": "https://docs.google.com/document/d/x"}))
    assert "approve" in guards.check(CHROME, _steps(RETURN), CONFIG, session=session)
    assert guards.check(CHROME, _steps(RETURN), CONFIG, session={**session, "transcript_path": str(tmp_path / "gone")}) is None


def test_words_typed_on_a_messaging_site_pass_the_register_scan(tmp_path):
    fill = ("form_input", {"ref": "ref_3", "value": "I'm sorry for the delay.", "action_summary": "Fills the reply"})
    session = _on(tmp_path, 7, tab7="https://chat.google.com/room/AAA")
    assert "delay-apology" in guards.check(CHROME, _steps(fill), CONFIG, session=session)
    assert guards.check(CHROME, _steps(fill), CONFIG, session=_on(tmp_path, 7, tab7="https://example.com/")) is None


def test_the_config_can_name_more_messaging_apps_and_a_malformed_list_fails_closed():
    call = {"app": "im.example.Chat", "combo": "return", "action_summary": "Presses Return"}
    assert check(KEY, call) is None
    assert "approve" in check(KEY, call, {**CONFIG, "messaging_apps": ["im.example.Chat"]})
    with pytest.raises(ValueError, match="messaging_apps"):
        check(KEY, call, {**CONFIG, "messaging_apps": "im.example.Chat"})
    with pytest.raises(ValueError, match="not an object"):
        check(BATCH, {"actions": ["left_click"]})


def test_a_signed_send_in_an_open_window_goes_when_typed_in_the_same_call():
    sends.open_window(1, ["slack"], count=2)
    config = {**CONFIG, "send_window_signatures": [r"helperbot\.example"]}
    call = {"app": "com.tinyspeck.slackmacgap", "actions": [
        {"action": "type", "text": "Deploy is done. 🤖 Helperbot (helperbot.example)", "action_summary": "Types the update"},
        {"action": "key", "combo": "return", "action_summary": "Sends the update"}]}
    assert check("mcp__computer-use__app_batch", call, config) is None
    assert "approve" in check("mcp__computer-use__app_batch", {**call, "app": WHATSAPP}, config)


def _hook(payload, env):
    import os
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-S", str(Path(__file__).resolve().parents[1] / "synthesis" / "hook.py"),
                          "pre-tool-use"], input=json.dumps(payload), capture_output=True, text=True,
                         env={**os.environ, **env}, check=True)
    return json.loads(out.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if out.stdout.strip() else None


def test_the_hook_holds_the_incident_call_and_fails_closed(isolated_home, write_config):
    env, base = {"SYNTHESIS_HOME": str(isolated_home)}, {"session_id": "S-hook", "cwd": str(isolated_home)}
    write_config(CONFIG)
    assert _hook({**base, "tool_name": "mcp__computer-use__request_access", "tool_input": {"apps": ["WhatsApp"]}}, env) is None
    assert "approve followed by the code" in _hook({**base, "tool_name": BATCH, "tool_input": SEND_CLICK}, env)
    assert "guard failed" in _hook({**base, "tool_name": BATCH, "tool_input": {"actions": ["left_click"]}}, env)
    (isolated_home / "config.json").write_text("{not json", encoding="utf-8")
    assert "unreadable" in _hook({**base, "tool_name": BATCH, "tool_input": SEND_CLICK}, env)
    assert _hook({**base, "tool_name": "mcp__computer-use__app_screenshot", "tool_input": {"app": WHATSAPP}}, env) is None
