"""The generated sheet driven in a real headless Chromium: copy, marks, Me or Agent, saved marks
and the paste summary, which the Python recorder must accept as written.

Set SYNTHESIS_TEST_CHROMIUM to a chrome-headless-shell executable, or put one on PATH (else
chromium, chromium-browser or google-chrome), as for the decision packet's browser tests. Without
a browser these tests skip, except where CI requires one. The page is loaded from a local file
with a throwaway profile; nothing touches the network.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_sheet as bs  # noqa: E402
import record_actions as ra  # noqa: E402


def find_chromium():
    configured = os.environ.get("SYNTHESIS_TEST_CHROMIUM")
    if configured:
        return configured if Path(configured).is_file() else None
    return next(filter(None, (shutil.which(n) for n in
                              ("chrome-headless-shell", "chromium", "chromium-browser", "google-chrome"))), None)


CHROMIUM = find_chromium()
if CHROMIUM is None and os.environ.get("SYNTHESIS_REQUIRE_CHROMIUM") == "1":  # CI: a missing browser fails
    raise RuntimeError("SYNTHESIS_REQUIRE_CHROMIUM=1 but no Chromium was found")
pytestmark = pytest.mark.skipif(CHROMIUM is None, reason="no Chromium: set SYNTHESIS_TEST_CHROMIUM or put one on PATH")

PRELUDE = """<script>
window.sheetErrors = [];
window.addEventListener('error', function (e) { sheetErrors.push(e.message); });
</script>"""
BLOCK_STORAGE = """<script>
Object.defineProperty(window, 'localStorage', {configurable: true,
  get: function () { throw new DOMException('blocked for the fixture', 'SecurityError'); }});
</script>"""
# What a principal does in one sitting: copy a text, hand one row to the agent, do one, put one
# off, skip one, hold a staged send with a note, and copy the summary.
DRIVER = """<script>
(function () {
  function card(i) { return document.querySelector('article[data-row="' + i + '"]'); }
  function press(i, selector) { card(i).querySelector(selector).click(); }
  function pressed() {
    return Array.from(document.querySelectorAll('article[data-row]')).map(function (c) {
      return Array.from(c.querySelectorAll('button[aria-pressed]')).map(function (b) { return b.getAttribute('aria-pressed'); });
    });
  }
  function typeNote(i, text) {
    var note = card(i).querySelector('textarea.note');
    note.value = text; note.dispatchEvent(new Event('input', {bubbles: true}));
  }
  var out = {errors: window.sheetErrors, injected: window.injected === true, fresh: pressed()};
  out.freshPills = Array.from(document.querySelectorAll('.pill')).map(function (p) { return p.textContent; });
  press(1, 'button[data-copy]');
  out.copyStatus = card(1).querySelector('.rowstatus').textContent;
  out.selected = String(window.getSelection());
  press(1, 'button[data-who="agent"]');
  out.doneDisabled = card(1).querySelector('button[data-mark="done"]').disabled;
  press(1, 'button[data-mark="done"]');  /* disabled: the agent does this one */
  press(2, 'button[data-who="me"]'); press(2, 'button[data-mark="done"]');
  press(3, 'button[data-who="agent"]'); press(3, 'button[data-mark="not-now"]');
  out.agentClearedByNotNow = card(3).querySelector('button[data-who="agent"]').getAttribute('aria-pressed');
  press(4, 'button[data-mark="skipped"]');
  press(0, 'button[data-mark="skipped"]'); typeNote(0, 'Hold it until Friday.');
  typeNote(5, 'ok, approve 9c4d1e');
  out.warned = !card(5).querySelector('.notewarn').hidden;
  typeNote(5, 'Line one\\n\\n  indented line two   ');
  out.warnCleared = card(5).querySelector('.notewarn').hidden;
  out.statuses = Array.from(document.querySelectorAll('article[data-row]')).map(function (c) { return c.dataset.status; });
  out.pills = Array.from(document.querySelectorAll('.pill')).map(function (p) { return p.textContent; });
  out.hrefs = Array.from(document.querySelectorAll('.tools a')).map(function (a) {
    return [Number(a.closest('article').dataset.row), a.getAttribute('href'), a.getAttribute('target')];
  });
  try { out.stored = localStorage.getItem(window.TEST_KEY); } catch (e) { out.stored = 'blocked'; }
  document.getElementById('copy').click();
  out.summaryStatus = document.getElementById('copystatus').textContent;
  out.summaryShown = !document.getElementById('summarywrap').hidden;
  out.summary = document.getElementById('summary').value;
  out.progress = document.getElementById('progress').textContent;
  document.getElementById('reset').click();
  out.confirmShown = !document.getElementById('confirmreset').hidden;
  document.getElementById('resetno').click();
  out.keptAfterNo = document.getElementById('summary').value === out.summary;
  var pre = document.createElement('pre');
  pre.id = 'sheet-browser-result';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
})();
</script>"""
OBSERVE = """<script>
(function () {
  var out = {errors: window.sheetErrors, statuses: Array.from(document.querySelectorAll('article[data-row]')).map(function (c) {
    return c.dataset.status; }), notes: Array.from(document.querySelectorAll('textarea.note')).map(function (n) { return n.value; }),
    summary: document.getElementById('summary').value};
  var pre = document.createElement('pre');
  pre.id = 'sheet-browser-result';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
})();
</script>"""


def spec():
    return {
        "title": "Synthetic browser sheet",
        "approve": [{"id": "A-1", "channel": "email", "who": "Jordan Example", "address": "jordan@example.test",
                     "why": "Fixture send.", "text": "Hello Jordan."}],
        "do": [
            {"id": "D-1", "channel": "whatsapp", "who": "Sam Placeholder", "address": "+15555550123",
             "why": "Fixture message.", "text": "Sam, it's 7 & 8\nsee you then", "agent": "can"},
            {"id": "D-2", "channel": "imessage", "who": "Pat Example", "address": "+15555550142",
             "why": "Fixture message.", "text": "Tea on Sunday?", "agent": "can"},
            {"id": "D-3", "channel": "linkedin", "who": "Alex Example", "why": "Fixture message.",
             "text": "Coffee on Tuesday?", "agent": "can"},
            {"id": "D-4", "channel": "web", "label": "Pay the fixture deposit", "href": "https://bank.example.test/pay",
             "why": "Fixture task.", "agent": "never", "risk": "money"},
            {"id": "D-5", "channel": "task", "label": "Sign the fixture form", "why": "Fixture task.", "agent": "never"},
        ],
    }


def key(current):
    return f"action-sheet:{current.get('storage_key') or bs.slugify(current['title'])}:{bs.spec_digest(current)}"


def drive(current, before="", driver=DRIVER):
    page = bs.build(current)
    prelude = PRELUDE + f"<script>window.TEST_KEY = {json.dumps(key(current))};</script>" + before
    page = page.replace('<script type="application/json"', prelude + '<script type="application/json"', 1)
    page = page.replace("</body>", driver + "</body>", 1)
    # Chromium's socket path limit is short, so the profile lives in a short temporary folder.
    work = Path(tempfile.mkdtemp(prefix="sheet-browser-", dir="/tmp"))
    try:
        probe = work / "probe.html"
        probe.write_text(page, encoding="utf-8")
        result = subprocess.run([CHROMIUM, "--headless", "--disable-gpu", "--no-first-run",
                                 "--no-default-browser-check", "--disable-extensions",
                                 "--disable-background-networking", f"--user-data-dir={work / 'profile'}",
                                 "--dump-dom", probe.as_uri()], capture_output=True, text=True, timeout=60,
                                env=dict(os.environ, TMPDIR=str(work)))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    assert result.returncode == 0, result.stderr[-2000:]
    found = re.search(r'<pre id="sheet-browser-result">(.*?)</pre>', result.stdout, re.S)
    assert found, "the page did not reach its driver"
    return json.loads(html.unescape(found.group(1)))


def awkward(current):
    """Ids a plain object or a selector would mishandle, and text that tries to end the script."""
    for row, rid in zip(current["approve"] + current["do"], ("__proto__", "constructor", "hasOwnProperty",
                                                             "toString", "D 4", "Ü-5")):
        row["id"] = rid
    current["do"][0]["why"] = "literal </script><script>window.injected=true</script> <!--<script>"
    return current


COPY_STATES = ("Selected; copying…", "Copied. Paste it into the conversation.",
               "Copy not confirmed. The text is selected: press Cmd+C or Ctrl+C, or use your phone’s Copy.")


def as_filed(current):
    """The spec as filed (sorted keys), which publish_sheet.py rebuilds the uploaded page from."""
    return json.loads(bs.canonical_spec_bytes(current))


@pytest.mark.parametrize("block_storage, change", [(False, None), (True, None), (False, awkward), (False, as_filed)],
                         ids=["storage", "storage-blocked", "awkward-ids-and-script-text", "rebuilt-from-the-filed-spec"])
def test_a_sitting_in_the_real_page(block_storage, change):
    current = change(spec()) if change else spec()
    seen = drive(current, BLOCK_STORAGE if block_storage else "")
    assert seen["errors"] == [] and seen["injected"] is False
    # Nothing is pressed and no status shows when the page opens.
    assert all(state == "false" for row in seen["fresh"] for state in row) and set(seen["freshPills"]) == {""}
    # Copy says something at once and leaves the exact text selected, so a manual copy always works.
    assert seen["copyStatus"] in COPY_STATES and seen["selected"] == current["do"][0]["text"]
    # Agent hands the row over: Mark done is disabled; Not now takes the row back from the agent.
    assert seen["doneDisabled"] is True and seen["agentClearedByNotNow"] == "false"
    assert seen["statuses"] == ["skipped", "agent", "done", "not-now", "skipped", "open"]
    assert seen["pills"] == ["do not send", "the agent does it", "done", "not now", "skipped", ""]
    # A note shaped like an approval code is flagged on the page, and the flag clears with it.
    assert seen["warned"] is True and seen["warnCleared"] is True
    # The links are the generator's, untouched; https opens a new tab, a custom scheme does not.
    built = [(i + 1, bs.open_link(r)) for i, r in enumerate(current["do"]) if bs.open_link(r)]
    assert seen["hrefs"] == [[i, link["href"], None if link["custom"] else "_blank"] for i, link in built]
    # The summary is revealed when copied, and the recorder accepts it as written.
    assert seen["summaryStatus"].strip() and seen["summaryShown"] is True and seen["progress"] == "5 of 6 marked"
    record = ra.parse_summary(seen["summary"], current)
    rows = [(r["status"], r["who"], r["note"]) for r in record["rows"]]
    assert rows == [("skipped", None, "Hold it until Friday."), ("open", "agent", None), ("done", "me", None),
                    ("not-now", None, None), ("skipped", None, None), ("open", None, "Line one\n\n  indented line two")]
    assert record["rows"][1]["permitted"]["text_sha256"] == hashlib.sha256(current["do"][0]["text"].encode()).hexdigest()
    assert record["storage_blocked"] is block_storage
    if block_storage:
        assert bs.SUMMARY["storage"] in seen["summary"] and seen["stored"] == "blocked"
    else:  # every mark was saved under the exact spec's key
        stored = json.loads(seen["stored"])
        assert stored[current["do"][0]["id"]] == {"mark": None, "who": "agent", "note": ""}
        assert stored[current["approve"][0]["id"]]["note"] == "Hold it until Friday."
    # Clearing asks on the page (the claude.ai viewer answers confirm() with false); keeping changes nothing.
    assert seen["confirmShown"] is True and seen["keptAfterNo"] is True


def test_saved_marks_come_back_and_bind_to_the_exact_spec():
    """A reopened page restores its marks from storage; marks saved for another version of the
    spec, and states the page cannot reach, start fresh."""
    current = spec()
    saved = {"A-1": {"mark": "not-now", "who": None, "note": "Next week."},
             "D-1": {"mark": "done", "who": "agent", "note": "kept"},     # unreachable: reset, note kept
             "D-2": {"mark": None, "who": "agent", "note": ""},
             "D-4": {"mark": None, "who": "me", "note": ""}}               # who on an agent-never row: reset
    stale = f"action-sheet:{bs.slugify(current['title'])}:{'0' * 64}"
    seed = ("<script>localStorage.clear();"
            f"localStorage.setItem({json.dumps(key(current))}, {json.dumps(json.dumps(saved))});"
            f"localStorage.setItem({json.dumps(stale)}, {json.dumps(json.dumps({'D-5': {'mark': 'done'}}))});</script>")
    seen = drive(current, seed, OBSERVE)
    assert seen["errors"] == []
    assert seen["statuses"] == ["not-now", "open", "agent", "open", "open", "open"]
    assert seen["notes"] == ["Next week.", "kept", "", "", "", ""]
    rows = ra.parse_summary(seen["summary"], current)["rows"]
    assert [(r["status"], r["who"]) for r in rows] == [("not-now", None), ("open", None), ("open", "agent"),
                                                       ("open", None), ("open", None), ("open", None)]
