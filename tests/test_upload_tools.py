"""A14, the dedicated upload tools: a call whose purpose is to hand a file from this disk to a page or a service waits
for a code naming the upload, as an upload made through computer use does, except on the principal's own app on a local
host, and is in the sends ledger once released.

The rule holds by kind, not by name: a tool whose name says it uploads or attaches, with no verb before that word that
only reads (`slack_get_file_upload_url` hands nothing over) and no word after it that says it reports on one
(`upload_status`), or a browser's way of setting a file input (`set_input_files`); and a Drive call that has its
connector read a file from this disk. Until 5.26.1 Claude in Chrome's `file_upload` and `upload_image` were judged by no
send rule, Playwright's `browser_file_upload` was read as a read, a connector's `upload_file` passed as another tool, and
a Drive import of a local file asked for no code.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from synthesis import guards, paths, sends

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
SESSION = {"session_id": "S-principal"}
CHROME_FILE, CHROME_IMAGE = "mcp__claude-in-chrome__file_upload", "mcp__claude-in-chrome__upload_image"
PLAYWRIGHT = "mcp__plugin_playwright_playwright__"


def held(reason) -> bool:
    return bool(reason) and "approve followed by the code" in reason


def today() -> list:
    return sends.ledger(time.strftime("%Y-%m-%d"))


def _record(path: Path, name: str, given: dict, said: str) -> dict:
    """A session whose record holds one finished call of `name` and its result."""
    at = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as handle:
        for line in ({"type": "assistant", "timestamp": at, "message": {"role": "assistant", "content": [
                         {"type": "tool_use", "id": "toolu_1", "name": name, "input": given}]}},
                     {"type": "user", "timestamp": at, "message": {"role": "user", "content": [
                         {"type": "tool_result", "tool_use_id": "toolu_1", "content": [{"type": "text", "text": said}]}]}}):
            handle.write(json.dumps(line) + "\n")
    return {**SESSION, "transcript_path": str(path)}


def on_tab(tmp_path, url: str) -> dict:
    """A session whose newest Claude in Chrome result shows tab 7 on this page."""
    return _record(tmp_path / "chrome.jsonl", "mcp__claude-in-chrome__computer", {"action": "screenshot", "tabId": 7},
                   f"Done\n\nTab Context:\n- Executed on tabId: 7\n- Available tabs:\n  • tabId 7: \"App\" (\"{url}\")")


def on_page(tmp_path, url: str) -> dict:
    """A session whose newest Playwright result shows its page."""
    return _record(tmp_path / "playwright.jsonl", PLAYWRIGHT + "browser_navigate", {"url": url},
                   f"### Ran Playwright code\n### Page\n- Page URL: {url}\n- Page Title: App\n")


@pytest.mark.parametrize("tool", [CHROME_FILE, CHROME_IMAGE, PLAYWRIGHT + "browser_file_upload", "mcp__box__upload_file",
                                  "mcp__slack__slack_complete_file_upload", "mcp__notion__notion-create-file-upload",
                                  "mcp__devtools__set_input_files", "mcp__tracker__add_attachment", "mcp__files__uploadFile"])
def test_a_tool_whose_name_says_it_hands_over_a_file_is_an_upload(tool):
    assert guards.upload_tool(tool), tool


@pytest.mark.parametrize("tool", ["mcp__slack__slack_get_file_upload_url", "mcp__gmail__download_gmail_attachment",
                                  "mcp__gmail__get_gmail_attachment_content", "mcp__files__upload_status", "mcp__files__list_uploads",
                                  "mcp__claude-in-chrome__read_page", "mcp__notes__create_note", "mcp__workspace-mcp__create_drive_file"])
def test_a_tool_that_reads_or_names_no_upload_is_none(tool):
    assert not guards.upload_tool(tool), tool


@pytest.mark.parametrize("tool,given,named", [
    (CHROME_FILE, {"paths": ["/tmp/receipt.pdf"], "ref": "ref_4", "tabId": 7}, "/tmp/receipt.pdf"),
    (CHROME_IMAGE, {"imageId": "shot-1", "ref": "ref_4", "tabId": 7}, "shot-1"),
], ids=["file-upload", "upload-image"])
def test_a_chrome_upload_waits_for_a_code_naming_it_and_is_logged(principal, tmp_path, tool, given, named):
    session = on_tab(tmp_path, "https://app.example.com/expenses/1")
    reason = guards.check(tool, given, CONFIG, session=session)
    assert held(reason) and "This call uploads a file" in reason and named in reason, reason
    principal(reason)
    assert guards.check(tool, given, CONFIG, session=session) is None
    assert today()[-1]["tool"] == tool and named in today()[-1]["summary"]


def test_a_chrome_upload_on_the_principals_own_local_app_needs_no_code(tmp_path):
    given = {"paths": ["/tmp/receipt.pdf"], "ref": "ref_4", "tabId": 7}
    assert guards.check(CHROME_FILE, given, CONFIG, session=on_tab(tmp_path, "http://localhost:8000/expenses/1")) is None


def test_an_upload_step_in_a_browser_batch_waits(tmp_path):
    batch = {"actions": [{"name": "file_upload", "input": {"paths": ["/tmp/receipt.pdf"], "ref": "ref_4", "tabId": 7}}]}
    reason = guards.check("mcp__claude-in-chrome__browser_batch", batch, CONFIG, session=on_tab(tmp_path, "https://app.example.com/"))
    assert held(reason) and "/tmp/receipt.pdf" in reason, reason


def test_a_driven_browsers_upload_waits_but_not_on_a_local_app_or_when_it_cancels_the_chooser(tmp_path):
    upload = PLAYWRIGHT + "browser_file_upload"
    reason = guards.check(upload, {"paths": ["/tmp/receipt.pdf"]}, CONFIG, session=on_page(tmp_path, "https://app.example.com/expenses"))
    assert held(reason) and "/tmp/receipt.pdf" in reason, reason
    assert guards.check(upload, {}, CONFIG, session=on_page(tmp_path, "https://app.example.com/expenses")) is None  # no file: it cancels
    (tmp_path / "local").mkdir()
    assert guards.check(upload, {"paths": ["/tmp/receipt.pdf"]}, CONFIG, session=on_page(tmp_path / "local", "http://localhost:3000/")) is None


@pytest.mark.parametrize("tool,given,named", [
    ("mcp__box__upload_file", {"file_path": "/tmp/receipt.pdf", "folder_id": "123"}, "/tmp/receipt.pdf"),
    ("mcp__slack__slack_complete_file_upload", {"files": [{"id": "F0EXAMPLE", "title": "receipt.pdf"}], "channel_id": "C0EXAMPLE"},
     "F0EXAMPLE"),
], ids=["box", "slack"])
def test_a_connectors_upload_waits_for_a_code_naming_it_and_is_logged(principal, tool, given, named):
    reason = guards.check(tool, given, CONFIG, session=SESSION)
    assert held(reason) and "This call uploads" in reason and named in reason, reason
    principal(reason)
    assert guards.check(tool, given, CONFIG, session=SESSION) is None
    assert today()[-1]["tool"] == tool


def test_asking_where_to_upload_hands_nothing_over():
    assert guards.check("mcp__slack__slack_get_file_upload_url", {"filename": "receipt.pdf", "length": 1024}, CONFIG,
                        session=SESSION) is None


@pytest.mark.parametrize("tool,key", [("mcp__workspace-mcp__import_to_google_doc", "file_path"),
                                      ("mcp__workspace_mcp__import_to_google_slides", "file_path"),
                                      ("mcp__workspace-mcp__create_drive_file", "fileUrl")])
def test_a_drive_call_that_reads_a_file_from_this_disk_waits_for_a_code_bound_to_its_bytes(principal, tool, key):
    staged = paths.outbox() / "plan.md"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("# Plan\n", encoding="utf-8")
    given = {"user_google_email": "me@example.com", "file_name": "Plan", key: staged.as_uri() if key == "fileUrl" else str(staged)}
    reason = guards.check(tool, given, CONFIG, session=SESSION)
    assert held(reason) and "This call uploads" in reason and str(staged) in reason, reason
    principal(reason)
    staged.write_text("# Another plan\n", encoding="utf-8")  # the code binds the file as it was shown
    assert held(guards.check(tool, given, CONFIG, session=SESSION))
    assert guards.check(tool, {"user_google_email": "me@example.com", "file_name": "Plan", "content": "# Plan"}, CONFIG,
                        session=SESSION) is None  # nothing read from this disk


def test_one_code_releases_one_upload(principal):
    """One approval, one upload: the same call again waits for a code of its own."""
    reason = guards.check("mcp__box__upload_file", {"file_path": "/tmp/a.pdf", "folder_id": "1"}, CONFIG, session=SESSION)
    principal(reason)
    assert guards.check("mcp__box__upload_file", {"file_path": "/tmp/a.pdf", "folder_id": "1"}, CONFIG, session=SESSION) is None
    assert held(guards.check("mcp__box__upload_file", {"file_path": "/tmp/a.pdf", "folder_id": "1"}, CONFIG, session=SESSION))
