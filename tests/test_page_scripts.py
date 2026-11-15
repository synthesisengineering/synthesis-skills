"""Page scripts on a messaging site's page, and navigates to a javascript: address (round 4 of 5.24.0's review, findings 1
and 3, on 5.23.0 too).

- #1: the navigate tool called by itself was never judged, and inside a batch a navigate's address was read as written,
  while a URL parser drops tabs and line breaks anywhere and control characters at the start: a `javascript:` address
  ran a page script that clicked Send. Every navigate, from any browser tool, is now read as a URL parser reads it, and
  a `javascript:` one is a page script on the page it runs on.
- #3: on a messaging site's page a script was judged by a pattern over its text, and `el['cli' + 'ck']()` is no text it
  sees. Every page script there but the plugin's shipped read-only ones (the extractors) is now refused: 60 days of
  records held 178 other scripts on those pages, in 4 sessions, so a code for each would have asked the principal 173
  times for scripts the old pattern passed; the browser's own read tools read a page with no code.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from synthesis import guards, install

ROOT = Path(__file__).resolve().parents[1]
CHROME, NAVIGATE, SCRIPT = ("mcp__claude-in-chrome__browser_batch", "mcp__claude-in-chrome__navigate",
                            "mcp__claude-in-chrome__javascript_tool")
PANE = "mcp__Claude_Browser__"
CONFIG = {"send_tools": ["mcp__*__slack_send_message"]}
CHAT = "https://www.facebook.com/messages/e2ee/t/1000000001/"
SEND = "javascript:void(document.querySelector('[aria-label=\"Press enter to send\"]').click())"
BUILT = "document.querySelector('[aria-label=\"Send now\"]')['cli' + 'ck']()"
PAGES = {"slack": "https://app.slack.com/client/T0001/C0001", "whatsapp": "https://web.whatsapp.com/",
         "linkedin": "https://www.linkedin.com/messaging/thread/2-abc/", "gmail": "https://mail.google.com/mail/u/0/#inbox",
         "x": "https://x.com/messages/1-2", "messenger": CHAT, "google chat": "https://chat.google.com/room/AAA"}


def _ran(record: Path, name: str, given: dict, said: str) -> None:
    ident = f"toolu_{len(record.read_text(encoding='utf-8').splitlines()) if record.exists() else 0}"
    with record.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": ident, "name": name, "input": given}]}}) + "\n")
        handle.write(json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": ident, "content": [{"type": "text", "text": said}]}]}}) + "\n")


def _listing(tabs: dict, front, quoted: bool = True) -> str:
    rows = "".join(f'\n  • tabId {t}: "Page" ({json.dumps(u) if quoted else u})' for t, u in tabs.items())
    return f"Done\n\nTab Context:\n- Executed on tabId: {front}\n- Available tabs:{rows}"


def _session(tmp_path, url: str = CHAT, tab=7) -> dict:
    """A session whose newest Claude in Chrome result lists the tab on the page."""
    record = tmp_path / "record.jsonl"
    _ran(record, "mcp__claude-in-chrome__computer", {"action": "screenshot", "tabId": tab}, _listing({tab: url}, tab))
    return {"session_id": "S-principal", "transcript_path": str(record)}


def _script(text: str, tab=7) -> dict:
    return {"action": "javascript_exec", "text": text, "tabId": tab}


def _refused(verdict) -> bool:
    return bool(verdict) and "approve" not in verdict


def test_the_navigate_tool_alone_runs_no_script_on_a_messaging_sites_page(tmp_path):
    session = _session(tmp_path)
    verdict = guards.check(NAVIGATE, {"url": SEND, "tabId": 7}, CONFIG, session=session)
    assert _refused(verdict) and "javascript:" in verdict, verdict
    assert guards.check(NAVIGATE, {"url": "https://www.facebook.com/messages/t/1000000002/", "tabId": 7}, CONFIG, session=session) is None


def test_a_javascript_address_off_a_messaging_site_is_judged_as_the_page_script_it_is(tmp_path):
    session = _session(tmp_path, "https://www.example.com/reviews", tab=3)
    verdict = guards.check(NAVIGATE, {"url": "javascript:document.querySelector('button.post').click()", "tabId": 3}, CONFIG, session=session)
    assert verdict and "approve followed by the code" in verdict, verdict  # a click with a word that publishes, as a script
    assert guards.check(NAVIGATE, {"url": "javascript:void(document.title)", "tabId": 3}, CONFIG, session=session) is None
    # percent-encoded as the browser decodes it before it runs
    encoded = "javascript:document.querySelector('button.post')%2Eclick%28%29"
    assert "approve followed by the code" in (guards.check(NAVIGATE, {"url": encoded, "tabId": 3}, CONFIG, session=session) or "")


@pytest.mark.parametrize("url", ["javascript:void(0)", "java\tscript:void(0)", "\x01javascript:void(0)", "javascript\n:void(0)",
                                 " JavaScript:void(0)", "javas\r\ncript:void(0)"])
def test_a_javascript_address_is_read_as_a_url_parser_reads_it(tmp_path, url):
    session = _session(tmp_path)
    verdict = guards.check(CHROME, {"actions": [{"name": "navigate", "input": {"url": url, "tabId": 7}}]}, CONFIG, session=session)
    assert _refused(verdict), (url, verdict)
    assert _refused(guards.check(NAVIGATE, {"url": url, "tabId": 7}, CONFIG, session=session)), url


def test_the_panes_navigate_and_its_tab_list_are_read(tmp_path):
    record = tmp_path / "record.jsonl"
    _ran(record, PANE + "navigate", {"url": "https://www.linkedin.com/feed/"},
         "navigated to https://www.linkedin.com/feed/\n" + _listing({"tab-1": "https://www.linkedin.com/feed/"}, "tab-1", quoted=False))
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    assert _refused(guards.check(PANE + "navigate", {"url": "javascript:void(0)"}, CONFIG, session=session))
    assert _refused(guards.check(PANE + "javascript_tool", {"action": "javascript_exec", "text": "document.title"}, CONFIG, session=session))


def test_the_panes_own_tab_list_and_a_local_app_there(tmp_path):
    record = tmp_path / "record.jsonl"
    _ran(record, PANE + "tabs_context", {}, json.dumps({"browserOpen": True, "tabs": [
        {"tabId": "tab-2", "origin": "http://localhost:3000", "isActive": True}]}) + "\nThe pane is currently displayed.")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    assert guards.check(PANE + "javascript_tool", {"action": "javascript_exec", "text": "document.title"}, CONFIG, session=session) is None
    _ran(record, PANE + "navigate", {"url": "https://x.com/messages"}, "opened https://x.com/messages in the browser pane")
    assert _refused(guards.check(PANE + "javascript_tool", {"action": "javascript_exec", "text": "document.title"}, CONFIG, session=session))


def test_each_browser_keeps_its_own_tab_ids(tmp_path):
    """The pane's tab 1 and Chrome's tab 1 are two tabs: one browser's list never names the other's page."""
    record = tmp_path / "record.jsonl"
    _ran(record, PANE + "navigate", {"url": "http://localhost:3000/", "tabId": "1"},
         "navigated to http://localhost:3000/\n" + _listing({"1": "http://localhost:3000/"}, "1", quoted=False))
    _ran(record, "mcp__claude-in-chrome__computer", {"action": "screenshot", "tabId": 1}, _listing({1: CHAT}, 1))
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    assert guards.check(PANE + "javascript_tool", {"action": "javascript_exec", "text": "document.title", "tabId": "1"}, CONFIG,
                        session=session) is None
    assert _refused(guards.check(SCRIPT, _script("document.title", tab=1), CONFIG, session=session))


def test_a_driven_browsers_navigate_to_a_javascript_address(tmp_path):
    record = tmp_path / "record.jsonl"
    _ran(record, "mcp__plugin_playwright_playwright__browser_navigate", {"url": CHAT}, f"- Page URL: {CHAT}\n")
    session = {"session_id": "S-principal", "transcript_path": str(record)}
    assert _refused(guards.check("mcp__plugin_playwright_playwright__browser_navigate", {"url": SEND}, CONFIG, session=session))
    assert guards.check("mcp__plugin_playwright_playwright__browser_navigate", {"url": "https://example.com/"}, CONFIG, session=session) is None


@pytest.mark.parametrize("site", sorted(PAGES))
@pytest.mark.parametrize("text", [BUILT, "document.querySelector('[aria-label=\"Send now\"]').click()", "document.title",
                                  "[...document.querySelectorAll('h2')].map(h => h.innerText)", "location.href"])
def test_on_a_messaging_sites_page_only_the_shipped_readers_run(tmp_path, site, text):
    session = _session(tmp_path, PAGES[site], tab=5)
    verdict = guards.check(SCRIPT, _script(text, tab=5), CONFIG, session=session)
    assert _refused(verdict) and "get_page_text" in verdict, (site, verdict)
    batch = {"actions": [{"name": "javascript_tool", "input": _script(text, tab=5)}]}
    assert _refused(guards.check(CHROME, batch, CONFIG, session=session)), site


def _printed(rel: str, *args) -> str:
    done = subprocess.run([sys.executable, "-I", str(ROOT / rel), *args], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-500:]
    return done.stdout.strip()


READERS = [("skills/synthesis-message-exports/scripts/chat_page.py", "extractor"),
           ("skills/synthesis-daily-rituals/scripts/messenger_messages.py", "extractor", "--inbox", "chats")]


@pytest.mark.parametrize("reader", READERS, ids=["chat_page", "messenger_messages"])
@pytest.mark.parametrize("page", [CHAT, "https://www.messenger.com/t/1000000003/", "https://www.facebook.com/messages/"])
def test_the_shipped_readers_run_on_messenger_pages(tmp_path, reader, page):
    session = _session(tmp_path, page, tab=7)
    assert guards.check(SCRIPT, _script(_printed(*reader)), CONFIG, session=session) is None


def test_the_installed_runtime_carries_both_readers_and_runs_them(tmp_path):
    """Round 4, #4: install.py copied only its listed skills' scripts into the release, and chat_page.py was not among
    them, so its extractor was refused on every Messenger tab in the runtime the hook runs from."""
    shipped = {rel for rel, _ in install._stable_skill_files(ROOT)}
    assert {"skills/synthesis-message-exports/scripts/chat_page.py", "skills/synthesis-daily-rituals/scripts/messenger_messages.py"} <= shipped
    release = tmp_path / "release"
    shutil.copytree(ROOT / "synthesis", release / "synthesis", ignore=shutil.ignore_patterns("__pycache__"))
    for rel, path in install._stable_skill_files(ROOT):
        (release / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, release / rel)
    session = _session(tmp_path, CHAT, tab=7)
    program = ("import json, sys; sys.path.insert(0, sys.argv[1]); from synthesis import guards; "
               "print(json.dumps(guards.check(sys.argv[2], {'action': 'javascript_exec', 'text': sys.argv[3], 'tabId': 7}, "
               "{}, session={'session_id': 'S-principal', 'transcript_path': sys.argv[4]})))")
    for reader in READERS:
        done = subprocess.run([sys.executable, "-I", "-c", program, str(release), SCRIPT, _printed(*reader), session["transcript_path"]],
                              capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stderr[-800:]
        assert json.loads(done.stdout) is None, (reader[0], done.stdout[:200])


@pytest.mark.parametrize("url, text", [("https://docs.google.com/document/d/1abc/edit", "document.title"),
                                       ("http://localhost:3000/", "document.querySelector('#send').click()"),
                                       ("https://www.example.com/list", "document.querySelector('.load-more').click()")])
def test_scripts_elsewhere_are_judged_as_before(tmp_path, url, text):
    assert guards.check(SCRIPT, _script(text, tab=4), CONFIG, session=_session(tmp_path, url, tab=4)) is None
