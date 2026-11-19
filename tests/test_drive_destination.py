"""5.27.1: a Drive call that makes or copies a file waits by where the file lands, not by where its bytes come from.

The principal asked on 2026-11-19 why a Drive import asked for a code. The gate exists because content reaches people
in his name (his ruling for calendar writes, 2026-10-06). A file made in his own My Drive, with no folder or `root`,
reaches no one; one made in a named folder may land in a shared one (on 11-11, 34 knowledge files went into a shared
drive's folder), so it waits for a code naming the file and the folder whatever its source: a file on this disk, a URL,
or bytes inline. 5.26.1 held by the source, so a private upload waited and inline bytes into a shared folder did not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synthesis import guards

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "skills" / "synthesis-message-guard" / "config.example.json")
                    .read_text(encoding="utf-8"))
SESSION = {"session_id": "S-principal"}
ME = {"user_google_email": "me@example.com", "file_name": "Plan"}
MAKERS = [("mcp__workspace-mcp__create_drive_file", "folder_id"), ("mcp__workspace_mcp__import_to_google_doc", "folder_id"),
          ("mcp__workspace-mcp__import_to_google_sheets", "folder_id"), ("mcp__drive_server__import_to_google_slides", "folder_id"),
          ("mcp__workspace-mcp__copy_drive_file", "parent_folder_id")]
SOURCES = [{"content": "# Plan"}, {"base64_content": "UGxhbg=="}, {"file_url": "https://files.example.com/plan.docx"},
           {"fileUrl": "https://files.example.com/plan.docx"}, {"file_id": "1sourceFileId"}]


def held(reason) -> bool:
    return bool(reason) and "approve followed by the code" in reason


@pytest.mark.parametrize("tool,key", MAKERS)
@pytest.mark.parametrize("mine", [None, "root", "ROOT", " root ", ""])
def test_a_file_made_in_the_principals_own_my_drive_asks_for_no_code(tool, key, mine):
    for source in SOURCES:
        given = {**ME, **source, **({} if mine is None else {key: mine})}
        assert guards.check(tool, given, CONFIG, session=SESSION) is None, (tool, given)


@pytest.mark.parametrize("tool,key", MAKERS)
def test_a_file_made_or_copied_into_a_named_folder_waits_for_a_code_naming_the_folder(tool, key):
    for source in SOURCES:
        reason = guards.check(tool, {**ME, **source, key: "1sharedFolderId"}, CONFIG, session=SESSION)
        assert held(reason) and "This call uploads" in reason and "1sharedFolderId" in reason, (tool, source, reason)


@pytest.mark.parametrize("folder", [["1sharedFolderId"], 7, {"id": "1sharedFolderId"}, True])
def test_a_folder_given_as_anything_but_a_name_is_judged_as_named(folder):
    assert held(guards.check("mcp__workspace-mcp__create_drive_file", {**ME, "content": "# Plan", "folder_id": folder},
                             CONFIG, session=SESSION))


def test_an_update_of_a_drive_file_still_waits_as_a_document_edit():
    """It writes into a file others may already read, wherever that file sits."""
    for given in ({"file_id": "1aBcD3fGh1jK", "content": "# Plan"}, {"file_id": "1aBcD3fGh1jK", "name": "Plan v2"}):
        assert "approval" in guards.check("mcp__workspace-mcp__update_drive_file", {**ME, **given}, CONFIG, session=SESSION)


def test_reading_drive_never_asks_for_a_code():
    """The rituals read from Drive all day: search, metadata, contents, a document, a download link."""
    reads = {"search_drive_files": {"query": "name contains 'notes'"}, "get_drive_file_content": {"file_id": "1a"},
             "get_doc_content": {"document_id": "1a"}, "get_doc_as_markdown": {"document_id": "1a"},
             "list_drive_items": {"folder_id": "1sharedFolderId"}, "get_drive_file_permissions": {"file_id": "1a"},
             "get_drive_file_download_url": {"file_id": "1a"}, "read_sheet_values": {"spreadsheet_id": "1a", "range_name": "A1:B2"}}
    for name, given in reads.items():
        assert guards.check(f"mcp__workspace-mcp__{name}", {"user_google_email": "me@example.com", **given}, CONFIG,
                            session=SESSION) is None, name


# --- review round 1 of 5.27.1, finding 2: the same act under other names --------------------------------------------------
GOOGLE = "mcp__7512aea3-58de-400a-851f-20f5336abdb7__"
NAMED = [(GOOGLE + "create_file", {"title": "Plan", "textContent": "# Plan", "contentMimeType": "text/plain", "parentId": "1sharedFolderId"}),
         (GOOGLE + "copy_file", {"fileId": "1privateFileId", "parentId": "1sharedFolderId"}),
         (GOOGLE + "copy_file", {"fileId": "1privateFileId"}),  # this connector puts the copy beside its original
         (GOOGLE + "update_file", {"fileId": "1privateFileId", "parentId": "1sharedFolderId"}),  # a move into the folder
         ("mcp__workspace-mcp__create_doc", {**ME, "title": "Plan", "content": "# Plan", "folder_id": "1sharedFolderId"}),
         ("mcp__workspace-mcp__export_doc_to_pdf", {**ME, "document_id": "1privateDocId", "folder_id": "1sharedFolderId"}),
         ("mcp__workspace-mcp__create_spreadsheet", {**ME, "title": "Plan", "sheet_names": ["Q4"], "folder_id": "1sharedFolderId"}),
         ("mcp__workspace-mcp__create_drive_folder", {**ME, "folder_name": "Plan", "parent_folder_id": "1sharedFolderId"})]
MINE = [(GOOGLE + "create_file", {"title": "Plan", "textContent": "# Plan", "contentMimeType": "text/plain"}),
        (GOOGLE + "copy_file", {"fileId": "1privateFileId", "parentId": "root"}),
        (GOOGLE + "update_file", {"fileId": "1privateFileId", "title": "Plan v2"}),
        ("mcp__workspace-mcp__create_doc", {**ME, "title": "Plan", "content": "# Plan"}),
        ("mcp__workspace-mcp__export_doc_to_pdf", {**ME, "document_id": "1privateDocId"}),
        ("mcp__workspace-mcp__create_spreadsheet", {**ME, "title": "Plan", "folder_id": "root"}),
        ("mcp__workspace-mcp__create_drive_folder", {**ME, "folder_name": "Plan"}),
        ("mcp__filesystem__create_file", {"path": "/tmp/plan.md", "content": "# Plan"}),  # another server's name, its own keys
        ("mcp__filesystem__copy_file", {"source": "/tmp/a.md", "destination": "/tmp/b.md"})]


@pytest.mark.parametrize("tool,given", NAMED)
def test_a_file_made_moved_or_copied_into_a_named_folder_by_any_drive_tool_waits(tool, given):
    assert held(guards.check(tool, given, CONFIG, session=SESSION)), tool


@pytest.mark.parametrize("tool,given", MINE)
def test_the_same_tools_into_the_principals_own_my_drive_or_another_servers_tools_ask_nothing(tool, given):
    assert guards.check(tool, given, CONFIG, session=SESSION) is None, tool


# --- review round 2 of 5.27.1 -----------------------------------------------------------------------------------------

LINES = "# Plan\nFirst step.\nSecond step.\n"
WITH_LINES = [("mcp__workspace-mcp__create_drive_file", {**ME, "content": LINES, "folder_id": "1sharedFolderId"}),
              ("mcp__workspace-mcp__create_doc", {**ME, "title": "Plan", "content": LINES, "folder_id": "1sharedFolderId"}),
              ("mcp__workspace-mcp__import_to_google_sheets", {**ME, "content": "a,b\n1,2\n3,4\n", "folder_id": "1sharedFolderId"})]
ONE_LINE_RULE = {**CONFIG, "message_format": {"allow_line_breaks_in_paragraphs": False}}


@pytest.mark.parametrize("tool,given", WITH_LINES)
def test_a_file_of_several_lines_into_a_named_folder_waits_for_a_code_and_is_not_refused_as_a_message(tool, given):
    """Finding A: a file's own lines read as a message's line breaks, refused before any code was offered."""
    reason = guards.check(tool, given, ONE_LINE_RULE, session=SESSION)
    assert held(reason) and "line break" not in reason, reason


def test_an_empty_key_does_not_carry_an_upload_past_the_drive_rule():
    """Open list 1: an input with a key named "" took any tool into the Drive branch, past the upload checks after it."""
    given = {"file_path": "/tmp/a.pdf", "folder_id": "1"}
    assert held(guards.check("mcp__box__upload_file", given, CONFIG, session=SESSION))
    assert held(guards.check("mcp__box__upload_file", {**given, "": ""}, CONFIG, session=SESSION))

