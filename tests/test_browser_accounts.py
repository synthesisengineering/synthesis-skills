"""The account a site shows in a workspace's browser profile.

2026-11-12: a work browser profile was signed in, on a site where an AI assistant is used, to the principal's
personal account, and the agent called that a limit on the work where it was a misconfiguration to tell him about.
The right profile can show the wrong account: then what is typed or uploaded there goes into an account the
workspace does not own. The guard cannot look at a browser. It can read the session's record, where every result of
a browser call ends with the list of tabs and names the tab the call ran on, and where a page read holds what the
page showed. So a call that puts something into a page of a site the config names (keys, a form's value, an upload,
a script) waits until a read of that site has shown the workspace's account there, and a read that shows another of
the principal's addresses is called what it is.
"""

import json
import time

import pytest

from synthesis import board, doctor, guards, paths, reply_check

WORK, SITE = "DEV-WORK-0001", "assistant.example"
MINE, OTHER, ALIAS, THIRD = "me@work.example", "me@home.example", "me@alias.example", "someone@else.example"
TYPE = ("computer", {"action": "type", "text": "Summarize the attached plan."})
PUTS = [TYPE, ("computer", {"action": "key", "text": "Return"}), ("form_input", {"ref": "ref_2", "value": "the plan"}),
        ("file_upload", {"paths": ["/tmp/plan.pdf"], "ref": "ref_3"}), ("upload_image", {"imageId": "shot-1", "ref": "ref_3"}),
        ("javascript_tool", {"action": "javascript_exec", "text": "document.title"})]
READS = [("navigate", {"url": f"https://{SITE}/settings"}), ("get_page_text", {}), ("read_page", {"filter": "interactive"}),
         ("find", {"query": "account menu"}), ("computer", {"action": "left_click", "coordinate": [10, 10]}),
         ("computer", {"action": "double_click", "coordinate": [10, 10]}), ("computer", {"action": "screenshot"}),
         ("computer", {"action": "scroll", "coordinate": [10, 10], "scroll_direction": "down"}),
         ("computer", {"action": "hover", "coordinate": [10, 10]}), ("computer", {"action": "wait", "duration": 1}),
         ("tabs_context_mcp", {}), ("read_console_messages", {})]


def config(accounts, **more):
    return {"browser_routing": {"workspaces": {str(ROOT): {"device": WORK, "label": "WorkCo", "accounts": accounts}}},
            "account_routing": {"default_account": OTHER, "workspaces": {str(ROOT): {"account": MINE, "aliases": [ALIAS]}}}, **more}


@pytest.fixture(autouse=True)
def _session(tmp_path):
    global ROOT, RECORD, ME, CONFIG, COUNT
    ROOT, RECORD, COUNT = tmp_path / "work", tmp_path / "record.jsonl", 0
    ROOT.mkdir()
    ME, CONFIG = {"session_id": "S1", "transcript_path": str(RECORD), "cwd": str(ROOT)}, config({SITE: MINE})
    board.touch("S1", cwd=str(ROOT))
    RECORD.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "Try it in the browser."}}) + "\n", encoding="utf-8")
    ran("select_browser", {"deviceId": WORK}, 'Selected browser "Browser 1".', tabs={})
    assert call("select_browser", {"deviceId": WORK}) is None


def ran(tool, given=None, body="", front=1, tabs=None, error=False, name=None, title="A page"):
    """A browser call and its result in the record: what it returned, then the list of tabs, the call having run on
    `front`. With no tabs given, one tab on a page of the site."""
    global COUNT
    COUNT += 1
    ident = f"toolu_{COUNT:04}"
    tabs = {1: f"https://{SITE}/chat"} if tabs is None else tabs
    listing = "\n".join(f'  • tabId {tab}: "{title}" ("{address}")' for tab, address in tabs.items())
    text = body + (f"\n\nTab Context:\n- Executed on tabId: {front}\n- Available tabs:\n{listing}" if tabs else "")
    with RECORD.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": ident, "name": name or guards.BROWSER + tool, "input": given or {}}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": ident, "is_error": error, "content": [{"type": "text", "text": text}]}]}}) + "\n")


def shows(*addresses, tool="get_page_text", path="/chat", **more):
    """A read of a page of the site that returned these addresses."""
    ran(tool, {"tabId": 1}, "Account\nSigned in as " + " and ".join(addresses), tabs={1: f"https://{SITE}{path}"}, **more)


def call(tool, given=None, using=None, tab=1):
    return guards.check(guards.BROWSER + tool, {"tabId": tab, **(given or {})}, CONFIG if using is None else using, cwd=str(ROOT), session=ME)


def batch(*steps, using=None):
    actions = [{"name": name, "input": {"tabId": 1, **given}} for name, given in steps]
    return guards.check(guards.BROWSER + "browser_batch", {"actions": actions}, CONFIG if using is None else using, cwd=str(ROOT), session=ME)


def unread(reason) -> bool:
    return bool(reason) and "has not shown" in reason and "misconfiguration" not in reason


def misrouted(reason) -> bool:
    return bool(reason) and "misconfiguration" in reason and "not a limit" in reason


def seen():
    return paths.read_json(paths.state() / "browser-accounts.json").get(f"{WORK} {SITE}")


def test_a_workspace_that_names_no_site_is_asked_nothing():
    ran("navigate")
    for accounts in ({}, None):
        using = config(accounts)
        if accounts is None:
            del using["browser_routing"]["workspaces"][str(ROOT)]["accounts"]
        assert call(*TYPE, using=using) is None


@pytest.mark.parametrize("tool, given", READS)
def test_going_to_a_named_site_reading_it_and_pointing_at_it_never_wait(tool, given):
    ran("navigate")
    assert call(tool, given) is None
    shows(OTHER)
    assert call(tool, given) is None                                       # nor once another account is seen: a menu must open


@pytest.mark.parametrize("tool, given", PUTS)
def test_what_puts_something_into_a_named_sites_page_waits_until_a_read_shows_the_workspaces_account(tool, given):
    ran("navigate")
    reason = call(tool, given)
    assert unread(reason)
    assert SITE in reason and "WorkCo" in reason and MINE in reason
    assert "get_page_text" in reason and "read_page" in reason and "find" in reason
    shows(MINE)
    assert call(tool, given) is None


@pytest.mark.parametrize("tool, given", [("get_page_text", {}), ("read_page", {"filter": "all"}), ("find", {"query": "account menu"}),
                                         ("browser_batch", {"actions": [{"name": "computer", "input": {"action": "left_click", "ref": "ref_9"}},
                                                                        {"name": "find", "input": {"query": "signed in as"}}]})])
def test_any_read_of_the_site_that_holds_the_account_shows_it(tool, given):
    ran("navigate")
    ran(tool, given, f"button \"Account menu\"\n  text \"{MINE.upper()}\"")       # a page may write it in capitals
    assert call(*TYPE) is None


def test_a_read_that_shows_another_of_the_principals_addresses_is_called_a_misconfiguration():
    ran("navigate")
    for other in (OTHER, ALIAS):
        shows(other)
        reason = call(*TYPE)
        assert misrouted(reason)
        assert other in reason and MINE in reason and SITE in reason and "WorkCo" in reason
        assert seen()["seen"] == other and seen()["session"] == "S1"
    shows(MINE)
    assert call(*TYPE) is None
    assert seen()["seen"] == MINE


def test_the_newest_read_that_settles_it_decides():
    ran("navigate")
    shows(MINE)
    assert call(*TYPE) is None
    shows(OTHER)
    assert misrouted(call(*TYPE))
    shows(THIRD)                                                           # an address the config does not know settles nothing
    assert misrouted(call(*TYPE))
    shows(MINE, OTHER)                                                     # nor does a page that shows both, an account switcher's
    assert misrouted(call(*TYPE))
    shows(MINE)
    assert call(*TYPE) is None


def test_a_page_that_shows_both_or_an_address_the_config_does_not_know_settles_nothing():
    ran("navigate")
    shows(MINE, OTHER)
    assert unread(call(*TYPE)) and seen() is None
    shows(THIRD)
    assert unread(call(*TYPE)) and seen() is None


def test_what_shows_the_account_is_a_read_of_that_site_and_nothing_else():
    two = {1: f"https://{SITE}/chat", 2: "https://mail.example/inbox"}
    ran("navigate", tabs=two)
    ran("get_page_text", {"tabId": 2}, f"Signed in as {MINE}", front=2, tabs=two)              # another site's page
    assert unread(call(*TYPE))
    ran("get_page_text", {"tabId": 1}, "A conversation", tabs=two, title=f"Inbox - {MINE}")    # a tab's title in the list of tabs
    assert unread(call(*TYPE))
    ran("find", {"tabId": 1, "query": f"the account {MINE}"}, f"Nothing matches \"the account {MINE}\"")  # the call's own words
    assert unread(call(*TYPE))
    ran("get_page_text", {"tabId": 1}, f"Signed in as {MINE}", error=True)                     # a call that failed
    assert unread(call(*TYPE))
    ran("run", {"command": "cat notes.txt"}, f"Signed in as {MINE}", name="Bash")              # a shell that printed such a result
    assert unread(call(*TYPE))
    ran("get_page_text", {"tabId": 1}, f"Signed in as {MINE}", tabs={})                        # a result that names no tab
    assert unread(call(*TYPE))
    ran("navigate", tabs=two)
    ran("get_page_text", {"tabId": 2}, f"Signed in as {OTHER}", front=2, tabs=two)             # nor is another site's page a wrong account
    assert unread(call(*TYPE))


def test_a_key_that_names_a_page_counts_only_reads_of_that_page():
    using = config({f"{SITE}/settings": MINE})
    ran("navigate")
    shows(MINE)                                                            # a conversation that mentions the address
    reason = call(*TYPE, using=using)
    assert unread(reason) and f"https://{SITE}/settings" in reason
    shows(OTHER)
    assert unread(call(*TYPE, using=using))                                # and no misconfiguration from one either
    shows(OTHER, path="/settings/account")
    assert misrouted(call(*TYPE, using=using))
    shows(MINE, path="/settings/account")
    ran("navigate")                                                        # back on a conversation: the site is the same
    assert call(*TYPE, using=using) is None
    assert unread(call(*TYPE, using=config({f"https://{SITE}/billing": MINE})))  # a key may be written as an address


def test_the_site_a_call_acts_on_is_its_tabs_in_the_newest_list_of_tabs():
    two = {1: f"https://{SITE}/chat", 2: "https://mail.example/inbox"}
    ran("navigate", tabs=two)
    assert unread(call(*TYPE, tab=1)) and call(*TYPE, tab=2) is None
    assert call(*TYPE, tab=7) is None                                      # a tab no result has listed: its page is not known
    ran("computer", {"action": "left_click"}, "Clicked", tabs={1: "https://mail.example/inbox"})
    assert call(*TYPE) is None                                             # the tab has left the site
    for address, held in ((f"https://www.{SITE}/x", True), (f"https://{SITE.upper()}/x", True), (f"https://not{SITE}/x", False),
                          (f"https://{SITE}.elsewhere.example/x", False), (f"https://elsewhere.example/{SITE}", False)):
        ran("navigate", tabs={1: address})
        assert bool(call(*TYPE)) is held, address


def test_a_batch_is_judged_by_its_steps_and_held_whole():
    click, read, away = ("computer", {"action": "left_click", "ref": "ref_1"}), ("get_page_text", {}), ("navigate", {"url": "https://mail.example/"})
    ran("navigate")
    assert batch(click, read) is None
    assert unread(batch(click, TYPE))
    assert unread(batch(read, TYPE))                                       # its read is not in the record until it has run
    assert batch(away, TYPE) is None                                       # the step types on the page the batch went to
    ran("navigate", tabs={1: "https://mail.example/inbox"})
    assert batch(click, TYPE) is None
    assert unread(batch(("navigate", {"url": f"https://{SITE}/new"}), TYPE))
    assert unread(batch(("navigate", {"url": f"{SITE}/new"}), ("form_input", {"ref": "ref_2", "value": "x"})))
    shows(MINE)
    assert batch(("navigate", {"url": f"https://{SITE}/new"}), TYPE, ("computer", {"action": "key", "text": "Return"})) is None


@pytest.mark.parametrize("accounts", [[], "x", 7, {SITE: 7}, {SITE: "not an address"}, {SITE: ""}, {"": MINE}, {"/settings": MINE},
                                      {SITE: MINE, f"{SITE}/settings": OTHER}, {SITE: [MINE]}, {7: MINE}])
def test_a_map_of_another_shape_blocks_the_workspaces_browser_calls(accounts):
    ran("navigate")
    for tool, given in (TYPE, ("navigate", {"url": "https://example.com"}), ("get_page_text", {})):
        reason = call(tool, given, using=config(accounts))
        assert reason and "accounts" in reason and "blocked until it is fixed" in reason
    using = config({SITE: MINE})
    using["browser_routing"]["workspaces"][str(ROOT)]["accounts"] = None   # a setting that cannot be read
    assert "blocked until it is fixed" in call(*TYPE, using=using)


def test_another_workspaces_sites_are_not_this_ones(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    using = config({})
    using["browser_routing"]["workspaces"][str(other)] = {"device": "DEV-OTHER-0002", "label": "Other", "accounts": {SITE: OTHER}}
    ran("navigate")
    assert call(*TYPE, using=using) is None


def test_the_other_addresses_are_every_one_the_config_names_as_the_principals():
    using = config({SITE: MINE}, same_day_meetings={"own": ["me@family.example", "*@pattern.example"]})
    using["browser_routing"]["workspaces"]["/elsewhere"] = {"device": "DEV-OTHER-0002", "accounts": {"other.example": "me@third.example"}}
    ran("navigate")
    for other in (OTHER, ALIAS, "me@family.example", "me@third.example"):
        shows(other)
        assert misrouted(call(*TYPE, using=using)), other
    shows("x@pattern.example")                                             # a pattern is no address
    assert misrouted(call(*TYPE, using=using)) and seen()["seen"] == "me@third.example"


def test_what_was_seen_is_written_once_and_not_again_for_the_same_read():
    ran("navigate")
    shows(OTHER)
    assert misrouted(call(*TYPE))
    listed = paths.state() / "browser-accounts.json"
    first, written = seen(), listed.stat().st_mtime_ns
    assert first["session"] == "S1" and first["at"]
    assert misrouted(call(*TYPE)) and listed.stat().st_mtime_ns == written and seen() == first


def test_the_doctor_warns_while_a_named_site_last_showed_another_account():
    assert doctor.check_browser_accounts(CONFIG, {}).status == "ok"
    ran("navigate")
    shows(OTHER)
    assert misrouted(call(*TYPE))
    check = doctor.check_browser_accounts(CONFIG, paths.read_json(paths.state() / "browser-accounts.json"))
    assert check.status == "warn" and check.name == "browser accounts"
    assert SITE in check.detail and "WorkCo" in check.detail and OTHER in check.detail and MINE in check.detail
    assert "misconfiguration" in check.detail
    shows(MINE)
    assert call(*TYPE) is None
    assert doctor.check_browser_accounts(CONFIG, paths.read_json(paths.state() / "browser-accounts.json")).status == "ok"


def test_the_doctor_reads_only_what_the_config_still_names_and_whatever_the_file_holds():
    at = time.time() - 86400
    stale = {f"{WORK} gone.example": {"seen": OTHER, "at": at}, f"{WORK} {SITE}": "not an entry", "x": 7}
    assert doctor.check_browser_accounts(CONFIG, stale).status == "ok"
    last = {f"{WORK} {SITE}": {"seen": OTHER, "at": at, "session": "S0"}}
    check = doctor.check_browser_accounts(CONFIG, last)
    assert check.status == "warn" and time.strftime("%Y-%m-%d %H:%M", time.localtime(at)) in check.detail
    assert doctor.check_browser_accounts(config({SITE: OTHER}), last).status == "ok"  # the config has since named that account there
    assert doctor.check_browser_accounts(config({f"{SITE}/settings": MINE}), last).status == "warn"  # the same site, by its page
    for unread in ("yesterday", None, 1e300, [at]):                        # a time that cannot be read is said to be unknown
        check = doctor.check_browser_accounts(CONFIG, {f"{WORK} {SITE}": {"seen": OTHER, "at": unread}})
        assert check.status == "warn" and "not written down" in check.detail
    for nothing_named in ({}, config({}), config([]), {"browser_routing": 7}, {"browser_routing": {"workspaces": [7]}}):
        assert doctor.check_browser_accounts(nothing_named, last) is None  # a map of another shape is the guard's to say


def stop(reply="I can't test from that profile.", using=None):
    return reply_check.check({"last_assistant_message": reply, "transcript_path": str(RECORD), "session_id": "S1", "cwd": str(ROOT)},
                             CONFIG if using is None else using)


def test_a_turn_that_read_another_account_on_a_named_site_sends_its_reply_back_and_is_written_down():
    ran("navigate")
    shows(OTHER)
    reason = stop()
    assert reason and "misconfiguration" in reason and "not a limit" in reason
    assert SITE in reason and "WorkCo" in reason and OTHER in reason and MINE in reason
    assert seen()["seen"] == OTHER                                         # with no call held: the doctor still learns of it
    shows(MINE)
    assert stop() is None and seen()["seen"] == MINE


def test_the_turns_end_asks_nothing_where_nothing_was_seen_or_named():
    ran("navigate")
    assert stop() is None and seen() is None
    shows(MINE, OTHER)
    assert stop() is None and seen() is None
    shows(OTHER)
    assert stop(using=config({})) is None and seen() is None
    assert stop(using={}) is None
    with RECORD.open("a", encoding="utf-8") as handle:                     # a new prompt: the read belongs to the turn before
        handle.write(json.dumps({"type": "user", "message": {"role": "user", "content": "And now?"}}) + "\n")
    assert stop() is None


def test_a_reply_sent_back_once_is_not_sent_back_again():
    ran("navigate")
    shows(OTHER)
    assert reply_check.check({"last_assistant_message": "As I said.", "transcript_path": str(RECORD), "session_id": "S1",
                              "cwd": str(ROOT), "stop_hook_active": True}, CONFIG) is None
