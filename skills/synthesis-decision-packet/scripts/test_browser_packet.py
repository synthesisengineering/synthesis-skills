"""Complete generated-page regressions for HTML parsing and DOM-to-record state.

Set SYNTHESIS_TEST_CHROMIUM to a Chromium/headless-shell executable, or provide
a standard Chromium on PATH. Missing browser capability fails this required
acceptance plane. The browser keeps its sandbox; no network navigation or trusted human
input is involved. These tests do not authenticate a principal or approve an
action. Their observer wraps the generated page without rewriting its scripts.
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

import build_packet as bp
import record_rulings as rr
from test_packet_causal import spec


@pytest.fixture(scope="module")
def chromium():
    configured = os.environ.get("SYNTHESIS_TEST_CHROMIUM")
    if configured:
        assert Path(configured).is_file(), "SYNTHESIS_TEST_CHROMIUM is not a file"
        return configured
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome-headless-shell"):
        executable = shutil.which(name)
        if executable:
            return executable
    pytest.fail("whole-page browser acceptance requires SYNTHESIS_TEST_CHROMIUM or Chromium on PATH")


def test_missing_browser_is_failed_acceptance(monkeypatch):
    monkeypatch.delenv("SYNTHESIS_TEST_CHROMIUM", raising=False)
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(pytest.fail.Exception, match="whole-page browser acceptance requires"):
        chromium.__wrapped__()


PRELUDE = """<script>
window.packetErrors = [];
window.addEventListener('error', function (e) { packetErrors.push(e.message); });
</script>"""

DRIVER = """<script>
(function () {
  var snapshots = [];
  function rows() { return Array.from(document.querySelectorAll('.row')); }
  function snapshot() {
    snapshots.push({
      summary: document.getElementById('summary').value,
      rows: rows().map(function (r) {
        return {id: r.dataset.id, pressed: Array.from(r.querySelectorAll('.opts button'))
          .map(function (b) { return b.getAttribute('aria-pressed'); })};
      })
    });
  }
  function choose(row, option) { rows()[row].querySelectorAll('.opts button')[option].click(); }
  function note() {
    var input = rows()[0].querySelector('textarea');
    input.value = 'Synthetic browser note';
    input.dispatchEvent(new Event('input', {bubbles: true}));
  }
  snapshot();
  if (rows().length) {
    choose(0, 0); note(); snapshot();
    choose(1, 1); choose(0, 1); snapshot();
    choose(0, 1); snapshot();
    window.confirm = function () { return true; };
    document.getElementById('reset').click(); snapshot();
    choose(0, 0); note(); snapshot();
  }
  var result = {errors: packetErrors, snapshots: snapshots,
    spec: JSON.parse(document.getElementById('spec').textContent),
    injectedScriptRan: window.packetFixtureRan === true};
  var out = document.createElement('pre');
  out.id = 'packet-browser-result'; out.textContent = JSON.stringify(result);
  document.body.appendChild(out);
})();
</script>"""


CASES = [
    pytest.param({}, id="ordinary-control"),
    pytest.param({"id": "__proto__"}, id="prototype-id"),
    pytest.param({"id": "constructor"}, id="constructor-id"),
    pytest.param({"id": "Q\f0"}, id="formfeed-id"),
    pytest.param({"id": "Q\x000"}, id="nul-id"),
    pytest.param({"context": "literal </script><script>window.packetFixtureRan=true</script>"},
                 id="html-close-control"),
    pytest.param({"context": "literal <!--<script> sequence in an HTML example"},
                 id="html-double-escape"),
]


@pytest.mark.parametrize("change", CASES)
def test_generated_page_dom_and_record_agree(tmp_path, chromium, change):
    current = spec()
    current["rows"][0].update(change)
    assert not [p for p in bp.validate(current) if not p.startswith(("NOTE:", "READER:"))]
    page = bp.build(current)
    (tmp_path / "generated.html").write_text(page, encoding="utf-8")
    instrumented = page.replace('<script type="application/json"',
                                PRELUDE + '<script type="application/json"', 1)
    instrumented = instrumented.replace("</body>", DRIVER + "</body>", 1)
    probe = tmp_path / "probe.html"
    probe.write_text(instrumented, encoding="utf-8")
    command = [chromium, "--headless", "--disable-background-networking", "--no-first-run",
               "--no-default-browser-check", "--disable-extensions",
               "--user-data-dir=" + str(tmp_path / "profile"), "--dump-dom", probe.as_uri()]
    browser = subprocess.run(command, capture_output=True, text=True, timeout=25)
    (tmp_path / "browser-dom.html").write_text(browser.stdout, encoding="utf-8")
    (tmp_path / "browser-stderr.txt").write_text(browser.stderr, encoding="utf-8")
    assert browser.returncode == 0, browser.stderr
    match = re.search(r'<pre id="packet-browser-result">(.*?)</pre>', browser.stdout, re.S)
    assert match, "complete generated page did not reach its observer"
    observed = json.loads(html.unescape(match.group(1)))
    (tmp_path / "observed.json").write_text(json.dumps(observed, indent=2), encoding="utf-8")
    assert observed["errors"] == []
    assert not observed["injectedScriptRan"]
    assert observed["spec"] == {"storage_key": bp.slugify(current["title"]), "filters": [], **current}
    snapshots = observed["snapshots"]
    assert len(snapshots) == 6
    expected_pressed = [
        [["false", "false"]] * 5,
        [["true", "false"]] + [["false", "false"]] * 4,
        [["false", "true"], ["false", "true"]] + [["false", "false"]] * 3,
        [["false", "false"], ["false", "true"]] + [["false", "false"]] * 3,
        [["false", "false"]] * 5,
        [["true", "false"]] + [["false", "false"]] * 4,
    ]
    for snapshot, pressed, count in zip(snapshots, expected_pressed, [0, 1, 2, 1, 0, 1]):
        assert [row["id"] for row in snapshot["rows"]] == [row["id"] for row in current["rows"]]
        assert [row["pressed"] for row in snapshot["rows"]] == pressed
        assert rr.parse_summary(snapshot["summary"], current)["decided"] == count
    spec_path = tmp_path / "current-spec.json"
    spec_path.write_bytes(bp.canonical_spec_bytes(current))
    recorded = subprocess.run([sys.executable, "-B", str(Path(rr.__file__)), "-", "--spec",
                               str(spec_path), "--stdout"], input=snapshots[-1]["summary"],
                              capture_output=True, text=True, timeout=10)
    assert recorded.returncode == 0, recorded.stderr
    record = json.loads(recorded.stdout)
    assert record["rulings"][0]["id"] == current["rows"][0]["id"]
    assert record["rulings"][0]["choice_value"] == "test"
    assert record["rulings"][0]["note"] == "Synthetic browser note"
    assert record["spec"]["canonical_sha256"] == bp.spec_digest(current)
    assert record["authorization"]["granted"] is False
