"""Complete real-browser artifact inspection; every input and ruling is synthetic."""

import html
import json
import re
import subprocess

import pytest
import build_packet as bp
import record_rulings as rr
from test_browser_packet import chromium as chromium_fixture
from test_review_assets import review_spec, text_asset, binary_asset


@pytest.fixture(scope="module")
def chromium():
    return chromium_fixture.__wrapped__()


@pytest.mark.parametrize("width", [1280, 390])
def test_actual_asset_reader_and_unavailable_boundary(tmp_path, chromium, width):
    current = review_spec()
    text = (
        "Hello, fixture.\n\nComplete Unicode paragraph 🧪 e\u0301.\n\n"
        + "https://example.test/"
        + "x" * 300
    )
    current["rows"][0]["review_assets"] = [
        text_asset(text),
        binary_asset(),
        text_asset(
            '# Fixture\n\nOne soft\nline.\n\n- Item\n\n```\n<img src="https://example.test/x" onerror="window.assetRan=true">\n```',
            "markdown",
            "md",
        ),
        binary_asset(
            b"%PDF-1.4\n%%EOF", "document", "application/pdf", "fixture.pdf", "pdf"
        ),
    ]
    current["rows"][1].update(
        revision="r1",
        delivery={"format": "unknown", "destinations": [], "attachments": []},
        review_assets=[
            {
                "id": "missing",
                "title": "Missing fixture",
                "kind": "plain_text",
                "content": {
                    "unavailable": "No bytes",
                    "source": "https://example.test/missing",
                },
            }
        ],
    )
    page = bp.build(current)
    (tmp_path / "generated.html").write_text(page)
    driver = """<script>
    document.execCommand=function(){return false;};
    Object.defineProperty(navigator,'clipboard',{value:{writeText:function(){return new Promise(function(){});}}});
    document.querySelector('.review-actions button').click();
    window.confirm=function(){return true;};document.getElementById('bulk').click();
    setTimeout(function(){
      var bounds=Array.from(document.querySelectorAll('.bar button')).filter(x=>!x.hidden).map(x=>({left:x.getBoundingClientRect().left,right:x.getBoundingClientRect().right}));
      var exact=document.querySelector('.review-exact textarea');
      var data={text:document.querySelector('.review-plain').textContent,exact:exact.value,selected:[exact.selectionStart,exact.selectionEnd],
        status:document.querySelector('.review-status').textContent,summary:document.getElementById('summary').value,
        untrustedRan:window.assetRan===true,unexpectedImages:document.querySelector('[data-asset-id=md]').querySelectorAll('img').length,
        paragraphs:Array.from(document.querySelector('[data-asset-id=md] .review-content').querySelectorAll('p')).map(x=>x.textContent),
        disabled:Array.from(document.querySelectorAll('.row')[1].querySelectorAll('.opts button')).every(x=>x.disabled),
        doc:document.querySelector('[data-asset-id=pdf]').textContent,bounds:bounds,width:innerWidth};
      var out=document.createElement('pre');out.id='review-browser-result';out.textContent=JSON.stringify(data);document.body.appendChild(out);
    },2200);
    </script>"""
    probe = tmp_path / "probe.html"
    probe.write_text(page.replace("</body>", driver + "</body>"))
    cmd = [
        chromium,
        "--headless",
        "--disable-background-networking",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--user-data-dir=" + str(tmp_path / "profile"),
        "--window-size=" + str(width) + ",900",
        "--virtual-time-budget=3000",
        "--screenshot=" + str(tmp_path / "page.png"),
        "--dump-dom",
        probe.as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    (tmp_path / "dom.html").write_text(result.stdout)
    (tmp_path / "stderr.log").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    match = re.search(
        r'<pre id="review-browser-result">(.*?)</pre>', result.stdout, re.S
    )
    assert match
    actual = json.loads(html.unescape(match.group(1)))
    (tmp_path / "observed.json").write_text(json.dumps(actual, indent=2))
    assert actual["text"] == actual["exact"] == text
    assert actual["selected"] == [0, len(text.encode("utf-16-le")) // 2]
    assert "not confirmed" in actual["status"]
    assert (
        actual["disabled"]
        and not actual["untrustedRan"]
        and actual["unexpectedImages"] == 0
    )
    assert actual["paragraphs"] == ["One soft\nline."]
    assert "preview unavailable" in actual["doc"]
    assert all(
        b["left"] >= 0 and b["right"] <= actual["width"] for b in actual["bounds"]
    )
    recorded = rr.parse_summary(actual["summary"], current)
    assert recorded["decided"] == 4 and recorded["rulings"][1]["choice_value"] is None
