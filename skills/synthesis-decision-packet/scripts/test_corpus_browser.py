"""Generated provider-corpus page to actual exact-spec review consumer."""

from pathlib import Path
import html
import importlib
import json
import os
import re
import subprocess
import sys
import pytest
from test_browser_packet import browser_environment

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-agent-conformance/scripts"))
sys.path.insert(0, str(ROOT / "skills/synthesis-decision-packet/scripts"))
intake = importlib.import_module("provider_intake")
build_packet = importlib.import_module("build_packet")


def test_complete_corpus_page_preserves_review_without_publication(tmp_path):
    chromium = Path(os.environ["SYNTHESIS_TEST_CHROMIUM"])
    assert chromium.is_file()
    request = {
        "schema": 1,
        "corpus_id": "browser-fixture",
        "source_kind": "synthetic",
        "members": [
            {
                "id": "one",
                "text": "Synthetic </script><script>window.p15Injected=true</script> context.",
            },
            {
                "id": "two",
                "text": "The only person in a small synthetic group has a rare role.",
            },
        ],
    }
    package = intake.corpus_review_packet(request)
    page = build_packet.build(package["spec"])
    (tmp_path / "original.html").write_text(page)
    driver = """<script>
    Array.from(document.querySelectorAll('.row')).forEach(function(row){row.querySelector('.opts button').click();});
    let output=document.createElement('pre');output.id='p15-result';output.textContent=JSON.stringify({summary:document.getElementById('summary').value,spec:JSON.parse(document.getElementById('spec').textContent),injected:window.p15Injected===true});document.body.appendChild(output);
    </script>"""
    path = tmp_path / "instrumented.html"
    path.write_text(page.replace("</body>", driver + "</body>"))
    command = [
        str(chromium),
        "--headless",
        "--disable-background-networking",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--user-data-dir=" + str(tmp_path / "profile"),
        "--dump-dom",
        path.as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=25,
                            env=browser_environment(tmp_path))
    (tmp_path / "browser-dom.html").write_text(result.stdout)
    (tmp_path / "browser-stderr.txt").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    match = re.search(r'<pre id="p15-result">(.*?)</pre>', result.stdout, re.S)
    assert match
    observed = json.loads(html.unescape(match.group(1)))
    (tmp_path / "observed.json").write_text(json.dumps(observed, indent=2))
    assert not observed["injected"]
    assert observed["spec"] == {
        **package["spec"],
        "storage_key": build_packet.slugify(package["spec"]["title"]),
        "filters": [],
    }
    provenance = {
        "principal": "Synthetic reviewer",
        "source_ref": "fixture-only",
        "received_at": "2026-09-27T00:00:00Z",
        "scope": "exact candidate",
        "authority_ref": "not authenticated",
    }
    reviewed = intake.review_corpus(request, observed["summary"], provenance)
    assert reviewed["disclosure_status"] == "EXACT_SPEC_REVIEWED"
    assert not reviewed["publication_authorized"]
    with pytest.raises(ValueError, match="actual action owner"):
        intake.require_corpus_publication(request, observed["summary"], provenance)
