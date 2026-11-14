"""The account a site shows in a workspace's browser profile.

2026-11-12: a work browser profile was signed in, on a site where an AI assistant is used, to the principal's
personal account, and the agent called that a limit on the work where it was a misconfiguration to tell him about.
The right profile can show the wrong account: then what is typed or uploaded there goes into an account the
workspace does not own. The guard cannot look at a browser. It can read the session's record, where every result of
a browser call ends with the list of tabs and names the tab the call ran on, and where a page read holds what the
page showed. So a call that puts something into a page of a site the config names (keys, a form's value, an upload,
a script) waits until a read of that site has shown the workspace's account there, and a read that shows another of
the principal's addresses is called what it is.

Replayed as built over thirty days of recorded browser calls (2026-11-13), with the sites where an AI assistant is
used named for two workspaces: of 3,138 browser calls, 349 had a step on a named site. None of the 261 that only
read, pointed or went there was held. Of the 88 that put something into a page there, 22 came after a read that had
shown the workspace's account, and 66 came before any such read, in four sessions.
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
    assert "which page" in call(*TYPE, tab=7)                              # a tab no result has listed: its page is not known
    ran("computer", {"action": "left_click"}, "Clicked", tabs={1: "https://mail.example/inbox"})
    assert call(*TYPE) is None                                             # the tab has left the site
    for address, held in ((f"https://www.{SITE}/x", True), (f"https://{SITE.upper()}/x", True), (f"https://{SITE}./x", True), (f"https://not{SITE}/x", False),
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


def test_a_key_may_name_the_page_by_its_fragment_or_its_query():
    for key, there in ((f"{SITE}/#settings", "/#settings/account"), (f"{SITE}/app?view=account", "/app?view=account&tab=1")):
        using = config({key: MINE})
        ran("navigate")
        shows(MINE)
        assert unread(call(*TYPE, using=using)), key
        shows(MINE, path=there)
        assert call(*TYPE, using=using) is None, key


def test_a_batch_that_went_somewhere_after_it_began_or_ran_on_two_tabs_settles_nothing():
    def did(*steps, body=f"[get_page_text] Title: Account\nSigned in as {MINE}", tabs=None):
        ran("browser_batch", {"actions": [{"name": name, "input": {"tabId": 1, **given}} for name, given in steps]}, body, tabs=tabs)
    read, wait = ("get_page_text", {}), ("computer", {"action": "wait", "duration": 1})
    ran("navigate")
    did(("navigate", {"url": "https://mail.example/"}), read, ("navigate", {"url": f"https://{SITE}/chat"}))   # read on the page before
    assert unread(call(*TYPE))
    did(read, ("get_page_text", {"tabId": 2}), tabs={1: f"https://{SITE}/chat", 2: "https://mail.example/"})   # which tab said it is not known
    assert unread(call(*TYPE))
    did(("navigate", {"url": f"https://{SITE}/settings"}), wait, read)     # went there first, then read: the page it ended on
    assert call(*TYPE) is None


def test_an_account_routing_of_another_shape_does_not_stop_the_reading():
    ran("navigate")
    for routing in ("x", {"workspaces": [7], "default_account": OTHER}, {"workspaces": {"/a": 7, "/b": {"account": ALIAS, "aliases": "x"}}}):
        using = {**config({SITE: MINE}), "account_routing": routing}
        assert unread(call(*TYPE, using=using))
    shows(OTHER)
    assert misrouted(call(*TYPE, using={**config({SITE: MINE}), "account_routing": {"workspaces": [7], "default_account": OTHER}}))


@pytest.mark.parametrize("accounts", [[], "x", 7, {SITE: 7}, {SITE: "not an address"}, {SITE: ""}, {"": MINE}, {"/settings": MINE},
                                      {SITE: MINE, f"{SITE}/settings": OTHER}, {SITE: [MINE]}, {7: MINE}, {f"{SITE}:443": MINE},
                                      {"assistant example": MINE}, {"assistant": MINE}, {SITE: MINE, f"www.{SITE}": MINE},
                                      {f"www.{SITE}": MINE, SITE: MINE}])
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


# --- from the review of 2026-11-13 -----------------------------------------------------------------------------------

def test_a_batch_of_keys_reads_the_record_once_for_a_site(monkeypatch):
    """Each step of a batch read the whole record again: thirty keys, thirty readings (3.7 s on a large record)."""
    ran("navigate")
    shows(MINE)
    read, real = [], guards._account_shown
    monkeypatch.setattr(guards, "_account_shown", lambda *given: read.append(1) or real(*given))
    assert batch(*[TYPE] * 10, ("computer", {"action": "key", "text": "Return"})) is None
    assert len(read) == 1
    shows(OTHER)
    assert misrouted(batch(*[TYPE] * 10)) and len(read) == 2


def test_a_put_on_a_large_record_stays_inside_a_hooks_time(pace):
    """A read that settles the account far back, then 6 MB of reads of the site that hold an address the config does
    not know: one put took about 130 ms, against 50 for a hook on a normal call."""
    ran("navigate")
    shows(MINE)
    assert call(*TYPE) is None                                             # the selection is confirmed before the record grows
    tabs = "\n".join(f'  • tabId {k}: "Page {k}" ("https://{SITE}/c/{k}")' for k in range(1, 6))
    body = "lorem ipsum dolor sit amet " * 70 + f"Contact help@{SITE} for support.\n\nTab Context:\n- Executed on tabId: 1\n- Available tabs:\n{tabs}"
    with RECORD.open("a", encoding="utf-8") as out:
        for n in range(2600):
            out.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"toolu_big{n}", "name": guards.BROWSER + "get_page_text", "input": {"tabId": 1}}]}}) + "\n")
            out.write(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"toolu_big{n}", "content": [{"type": "text", "text": body}]}]}}) + "\n")
    assert 5 << 20 < RECORD.stat().st_size < 8 << 20
    took = []
    for _ in range(3):
        began = time.perf_counter()
        assert batch(*[TYPE] * 10) is None
        took.append(time.perf_counter() - began)
    assert min(took) < 0.05 * pace, took


def test_a_put_on_a_tab_whose_page_the_record_does_not_show_waits_for_a_list_of_tabs():
    """A tab's address that had dropped out of the record's last 8 MB counted as "not on the site", so typing went
    through on a site whose last read had shown another account."""
    reason = call(*TYPE, tab=7)
    assert reason and "which page" in reason and "tab 7" in reason and "misconfiguration" not in reason
    for tool, given in READS:
        assert call(tool, given, tab=7) is None                           # what puts nothing never waits
    ran("computer", {"action": "screenshot", "tabId": 7}, "", front=7, tabs={7: "https://mail.example/"})
    assert call(*TYPE, tab=7) is None
    assert call(*TYPE, tab=7, using=config({})) is None and call(*TYPE, tab=9, using=config({})) is None   # and only where a site is named


@pytest.mark.parametrize("url", ["back", "forward", "/new", "", "javascript:void(0)", "about:blank"])
def test_a_batch_step_that_goes_nowhere_the_guard_can_name_leaves_the_tabs_page_unknown(url):
    ran("navigate")
    reason = batch(("navigate", {"url": url}), TYPE)
    assert reason and "which page" in reason
    assert batch(("navigate", {"url": url}), ("get_page_text", {})) is None


@pytest.mark.parametrize("url", ["back", "forward", "/new", "javascript:void(0)"])
def test_such_a_step_from_a_messaging_sites_page_leaves_the_page_unknown_here_too(url):
    """The send guard judges the page such a step opens from a messaging site's page as that site's, since it may be
    that site's still (5.21.0). For the account it stays unknown: the step may have left for a site named here."""
    ran("navigate", tabs={1: "https://www.linkedin.com/feed/"})
    reason = batch(("navigate", {"url": url}), TYPE)
    assert reason and "which page" in reason


@pytest.mark.parametrize("address", [f"https:{SITE}/x", f"https://{SITE}\\@mail.example/", f"HTTPS://{SITE}./x", "https://assistant%2Eexample/x",
                                     f"https://user:secret@{SITE}:8443/x", f"//{SITE}/x"])
def test_an_address_a_browser_reads_as_the_sites_is_the_sites(address):
    ran("navigate", tabs={1: "https://mail.example/"})
    assert unread(batch(("navigate", {"url": address}), TYPE)), address
    ran("navigate", tabs={1: address})
    assert unread(call(*TYPE)), address


def test_a_batch_that_could_have_moved_after_its_read_settles_nothing():
    """A batch's result names one tab, the one it ended on. A click or a Return after its read may have moved the
    tab, so what it read may be another page's."""
    def did(*steps, body=f"[get_page_text] Title: Inbox\nSigned in as {MINE}"):
        ran("browser_batch", {"actions": [{"name": name, "input": {"tabId": 1, **given}} for name, given in steps]}, body)
    read, click, wait = ("get_page_text", {}), ("computer", {"action": "left_click", "ref": "ref_1"}), ("computer", {"action": "wait", "duration": 1})
    ran("navigate")
    for after in (click, ("computer", {"action": "key", "text": "Return"}), ("javascript_tool", {"action": "javascript_exec", "text": "go()"}),
                  ("form_input", {"ref": "ref_2", "value": "x"}), ("navigate", {"url": f"https://{SITE}/settings"})):
        did(read, after)
        assert unread(call(*TYPE)), after
    did(click, wait, ("find", {"query": "signed in as"}), ("computer", {"action": "screenshot"}), ("computer", {"action": "scroll", "scroll_direction": "down"}),
        body=f"[find] Found 1 element\n- ref_9: button \"{MINE}\"")           # a menu opened, then read: nothing moved after the read
    assert call(*TYPE) is None


def test_with_no_page_named_the_hold_says_what_a_read_showed_and_no_more():
    """A conversation that mentions another of the principal's addresses was called a sign-in to that account."""
    ran("navigate")
    shows(OTHER)
    reason = call(*TYPE)
    assert misrouted(reason) and "only mentions" in reason and reason.startswith(f"A read of {SITE} in the WorkCo browser profile showed {OTHER}")
    assert f"If the profile is signed in to {SITE} as {OTHER}" in reason  # said as a condition: the page may only mention the address
    assert "only mentions" in stop()
    paged = config({f"{SITE}/settings": MINE})
    shows(OTHER, path="/settings")
    reason = call(*TYPE, using=paged)
    assert misrouted(reason) and "only mentions" not in reason and reason.startswith(f"The WorkCo browser profile is signed in to {SITE} as {OTHER}")
    assert "only mentions" not in stop(using=paged)


@pytest.mark.parametrize("tool", ["autofill_credential", "enter_verification_code", "request_credentials", "list_granted_credentials", "release_credentials"])
def test_signing_in_does_not_wait(tool):
    """These are how a profile comes to show the right account, and what they put in is approved in the password
    manager's own prompt: they are no part of what the rule keeps out of an account."""
    ran("navigate")
    assert call(tool, {}) is None
    shows(OTHER)
    assert call(tool, {}) is None


@pytest.mark.parametrize("keys", ["Escape", "Tab", "shift+Tab", "PageDown", "Page_Up", "ArrowDown", "Up", "Left", "Home", "End", "cmd+r", "ctrl+r", "F5",
                                  "cmd+c", "ctrl+c", "cmd+a", "cmd+f", "Escape Tab Tab", "cmd+Left"])
def test_a_key_that_puts_nothing_does_not_wait(keys):
    ran("navigate")
    assert call("computer", {"action": "key", "text": keys}) is None, keys


@pytest.mark.parametrize("keys", ["Return", "Enter", "KP_Enter", "a", "space", "cmd+v", "ctrl+v", "shift+Insert", "Backspace", "Delete", "cmd+Return",
                                  "Escape Return", "cmd+x", "cmd+z", "", "ctrl+shift+v"])
def test_a_key_that_can_put_or_send_or_change_waits(keys):
    ran("navigate")
    assert unread(call("computer", {"action": "key", "text": keys})), keys


def test_a_page_key_ends_where_a_name_ends_and_may_be_written_without_a_slash():
    using = config({f"{SITE}/settings": MINE})
    ran("navigate")
    for path, counts in (("/settings-archive/2025", False), ("/settingsx", False), ("/settings", True), ("/settings/", True),
                         ("/settings/account", True), ("/settings?tab=1", True), ("/settings#profile", True)):
        ran("navigate")
        shows(OTHER, path="/settings")                                    # the page last showed another account
        shows(MINE, path=path)
        assert (call(*TYPE, using=using) is None) is counts, path
    for key, there in ((f"{SITE}#settings", "/#settings/profile"), (f"{SITE}?view=account", "/?view=account&x=1"), (f" {SITE}/settings ", "/settings"),
                       (f"{SITE.upper()}./settings", "/settings")):
        shows(MINE, path=there)
        assert call(*TYPE, using=config({key: MINE})) is None, key
    assert "blocked until it is fixed" in call(*TYPE, using=config({f"{SITE}/set tings": MINE}))


def test_a_result_far_below_its_call_is_still_the_newest_list_of_tabs():
    """The call of a result was looked for in the 200 lines above it. Past that, the list of tabs was passed over,
    an older one was used, and a tab that had since come to the site counted as elsewhere."""
    ran("navigate", tabs={1: "https://mail.example/"})
    lines = [json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_far", "name": guards.BROWSER + "navigate", "input": {"tabId": 1}}]}})]
    lines += [json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"toolu_other{n}", "content": "ok"}]}}) for n in range(450)]
    lines.append(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_far", "content": [
        {"type": "text", "text": f"Navigated\n\nTab Context:\n- Executed on tabId: 1\n- Available tabs:\n  • tabId 1: \"A page\" (\"https://{SITE}/chat\")"}]}]}}))
    with RECORD.open("a", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")
    assert unread(call(*TYPE))


def test_an_address_the_call_named_in_an_encoded_form_shows_nothing():
    ran("navigate")
    ran("navigate", {"tabId": 1, "url": f"https://{SITE}/search?q=" + MINE.replace("@", "%40")}, "Navigated")
    ran("find", {"tabId": 1, "query": MINE.replace("@", "%40").upper()}, f"Nothing matches {MINE}")
    assert unread(call(*TYPE))


def test_the_doctor_names_a_profile_with_no_label_by_its_workspace():
    using = config({SITE: MINE})
    del using["browser_routing"]["workspaces"][str(ROOT)]["label"]
    check = doctor.check_browser_accounts(using, {f"{WORK} {SITE}": {"seen": OTHER, "at": time.time()}})
    assert check.status == "warn" and "the a " not in check.detail and str(ROOT) in check.detail


def test_the_doctor_compares_addresses_as_the_guard_does_and_the_turns_end_survives_a_record_that_is_gone():
    assert doctor.check_browser_accounts(CONFIG, {f"{WORK} {SITE}": {"seen": MINE.upper(), "at": time.time()}}).status == "ok"
    gone = {"last_assistant_message": "Done.", "transcript_path": str(RECORD) + ".gone", "session_id": "S1", "cwd": str(ROOT)}
    assert reply_check.misrouted_accounts(gone, CONFIG) == []


def test_a_list_of_tabs_in_the_extensions_older_form_and_a_new_tabs_empty_address_are_read():
    """Replayed over recorded calls, the hold for a page the record does not show fell on 89 calls, every one in a
    record from July: the extension then wrote a tab's address without quotes, and the reader took only the quoted
    form. A reader that cannot read a list of tabs would hold every put for good."""
    def listed(*tabs):
        text = "Done\n\nTab Context:\n- Executed on tabId: 1\n- Available tabs:\n" + "\n".join(f"  \u2022 tabId {k}: {line}" for k, line in tabs)
        ran("computer", {"action": "screenshot", "tabId": 1}, text, tabs={})
    listed((1, f'"A page (draft)" (https://{SITE}/chat)'), (2, '"Inbox" (https://mail.example/inbox)'), (3, '"New Tab" ("")'))
    assert unread(call(*TYPE, tab=1)) and call(*TYPE, tab=2) is None
    assert call(*TYPE, tab=3) is None                                     # a new tab's page is known: it is no site's
    assert "which page" in call(*TYPE, tab=4)
    listed((1, f'"A page" ("https://mail.example/")'), (2, f'"A (page)" ("https://{SITE}/chat")'))
    assert call(*TYPE, tab=1) is None and unread(call(*TYPE, tab=2))


def test_a_sub_agents_put_is_told_whose_read_the_guard_sees():
    """A sub-agent's calls and results are kept apart from its session's: its own read of the page is in no record
    the guard reads, and a hold that told it to read and try again could not be cleared by it."""
    ran("navigate")
    sub = {**ME, "agent_id": "a1", "agent_type": "general-purpose"}
    reason = guards.check(guards.BROWSER + "computer", {"tabId": 1, **TYPE[1]}, CONFIG, cwd=str(ROOT), session=sub)
    assert unread(reason) and "sub-agent" in reason and "session that started it" in reason
    assert "sub-agent" not in call(*TYPE)
    shows(MINE)                                                           # the session's own read counts for both
    assert guards.check(guards.BROWSER + "computer", {"tabId": 1, **TYPE[1]}, CONFIG, cwd=str(ROOT), session=sub) is None


def test_two_sessions_that_write_what_they_saw_at_once_lose_neither(tmp_path):
    """The file was read, changed and written with no lock, so one of two writers could drop the other's site."""
    import threading
    listed = paths.state() / "browser-accounts.json"
    sites = [f"site{n}.example" for n in range(24)]
    workers = [threading.Thread(target=guards._note_account, args=("DEV", site, (MINE, f"toolu_{n}"), f"S{n}")) for n, site in enumerate(sites)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert set(paths.read_json(listed)) == {f"DEV {site}" for site in sites}


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
