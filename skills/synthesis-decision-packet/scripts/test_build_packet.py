#!/usr/bin/env python3
"""Fixtures for synthesis-decision-packet.

Two of these are regressions for defects the reference implementation actually shipped,
one of which reached the principal in real use. They are fixtures, not suggestions.

    python3 test_build_packet.py          # run everything
    python3 -m pytest test_build_packet.py -q

Stdlib only; runnable without pytest so the gate works anywhere.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_packet as bp  # noqa: E402

HERE = pathlib.Path(__file__).parent


def spec(n=6, **over):
    s = {
        "title": "Fixture packet",
        "options": [
            {"value": "yes", "label": "Yes", "tone": "ok"},
            {"value": "no", "label": "No", "tone": "danger"},
        ],
        "rows": [
            {"id": f"R-{i:02d}", "label": f"Item {i}", "recommendation": "yes"}
            for i in range(1, n + 1)
        ],
    }
    s.update(over)
    return s


# ---------------------------------------------------------------------------
# Regression 1 — charset in the first bytes
# ---------------------------------------------------------------------------

def test_charset_is_declared_in_the_first_bytes():
    """Without this, typographic punctuation is mojibake over a plain local HTTP server.

    The reference implementation shipped without it. The defect was found by actually
    loading the page, not by reading the source — so this fixture asserts on bytes.
    """
    out = bp.build(spec())
    head = out[:200]
    assert '<meta charset="utf-8">' in head, "charset must be in the first bytes, got: " + head[:120]
    assert head.index("<meta charset") < head.index("<title"), "charset must precede <title>"


def test_typographic_punctuation_survives_a_utf8_roundtrip():
    curly = "Don’t “converge” first — surface it."
    out = bp.build(spec(rows=[
        {"id": "R-1", "label": curly, "recommendation": "yes"},
        *[{"id": f"R-{i}", "label": f"Item {i}", "recommendation": "yes"} for i in range(2, 7)],
    ]))
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "p.html"
        p.write_text(out, encoding="utf-8")
        # Decoding as utf-8 must succeed and the glyphs must be intact.
        back = p.read_bytes().decode("utf-8")
    assert "’" in back and "“" in back and "—" in back


# ---------------------------------------------------------------------------
# Regression 2 — the clipboard control must never fail silently
# ---------------------------------------------------------------------------

def test_copy_selects_before_it_tries_any_programmatic_path():
    """Selection first is what makes a manual Cmd/Ctrl+C work when both paths are blocked.

    navigator.clipboard.writeText is blocked inside a sandboxed artifact iframe that lacks
    clipboard-write. In the origin run the button reported nothing and did nothing, and
    Rajiv worked around it by hand.
    """
    out = bp.build(spec())
    fn = out[out.index("function copySummary"):]
    fn = fn[:fn.index("document.getElementById(\"copy\")")]

    i_select = fn.index("ta.select()")
    i_exec = fn.index("document.execCommand")
    i_async = fn.index("navigator.clipboard")
    assert i_select < i_exec < i_async, (
        "required order is select -> execCommand -> async API; "
        f"got select@{i_select} exec@{i_exec} async@{i_async}"
    )


def test_copy_reports_something_synchronously_before_any_async_path():
    """An unsettled promise must not leave the control silent.

    Found by driving the real button in a browser: execCommand was blocked, the async
    clipboard promise had not resolved, and the status line was empty in between. A
    control that says nothing for an unbounded interval is the same defect as one that
    says nothing forever.
    """
    out = bp.build(spec())
    fn = out[out.index("function copySummary"):out.index('document.getElementById("copy").addEventListener')]
    i_sync = fn.index('status.textContent = "Selected')
    i_exec = fn.index("document.execCommand")
    i_async = fn.index("navigator.clipboard")
    assert i_sync < i_exec < i_async, "a synchronous status write must precede both copy attempts"


def test_every_copy_path_reports_its_outcome():
    """A control whose failure is silent is a bug — the rule these skills argue for guards."""
    out = bp.build(spec())
    fn = out[out.index("function copySummary"):out.index('document.getElementById("copy").addEventListener')]
    # Each terminal branch must write to the status element.
    assert fn.count("status.textContent") >= 3, (
        "all three outcomes (execCommand ok, async ok, async fail) must report; "
        f"found {fn.count('status.textContent')} status writes"
    )
    assert "the text is selected" in fn, "the failure message must tell the user what to do instead"


# ---------------------------------------------------------------------------
# The five load-bearing properties
# ---------------------------------------------------------------------------

def test_recommendation_is_marked_on_the_control_not_only_prose():
    """Mutation-hardened: an external review deleted the marker statements and
    this test still passed, because it only asserted generic button plumbing.
    It now asserts the exact marking behavior it is named for."""
    out = bp.build(spec())
    # The marked-control affordance itself: the data attribute and the
    # accessible title, set exactly when the option is the recommendation.
    assert 'b.dataset.recommended = "true";' in out
    assert 'b.title = "The agent recommends this";' in out
    assert "row.recommendation === o.value" in out
    # The visual treatment binds to the marker, and marking never presses:
    # aria-pressed derives from saved state alone (guarded by the fresh-packet
    # test), while the recommended styling keys off data-recommended.
    assert 'button[data-recommended="true"]' in out
    assert "recommended: " in out, "the recommendation must be shown on the control, not just in text"


def test_a_fresh_packet_has_nothing_selected():
    """The property the old test NAME contradicted.

    This test previously read `..._is_a_preselected_button_...` while the
    implementation deliberately pre-selects nothing. The assertions were always
    about the recommendation being *marked on the control*, but a name is read
    far more often than a body, and the wrong name invited someone to "fix" the
    code to match it — which would ship a packet that opens fully decided and
    cannot tell "I agreed" from "I never looked".

    So the property gets its own explicit guard: pressed state is set from saved
    storage alone, never from the recommendation.
    """
    out = bp.build(spec())

    # Pressed state is computed from the saved decision for that row and from
    # nothing else. If this ever reads the recommendation, a fresh packet opens
    # already decided.
    assert 'b.setAttribute("aria-pressed", String(b.dataset.value === d))' in out
    assert "var d = decisionOf(r);" in out

    # And no option button is emitted pre-pressed in the served markup. Buttons
    # are constructed in script, so the body carries none before restore runs.
    body = out.split("<body", 1)[1].split("<script", 1)[0]
    assert 'aria-pressed="true"' not in body, (
        "no option may be rendered pre-pressed before saved state is read"
    )


def test_every_row_gets_a_free_text_box():
    out = bp.build(spec())
    assert "Anything the buttons cannot say" in out
    assert 'note.appendChild(ta)' in out


def test_state_persists_per_item_and_degrades_when_storage_throws():
    out = bp.build(spec())
    assert 'localStorage.getItem(KEY)' in out and 'localStorage.setItem(KEY' in out
    # Private mode / blocked site data must not break the packet.
    assert "persists = false" in out, "storage access must be guarded, not assumed"


def test_summary_is_generated_by_the_tool():
    out = bp.build(spec())
    assert "function renderSummary" in out
    assert "not yet decided" in out
    assert "OVERRODE" in out, "an override must be visible to the agent reading the paste"


def test_no_option_is_selected_before_the_principal_acts():
    """The initial state must be undecided, matching the reference implementation.

    The reference sets aria-pressed only from saved storage, so a fresh packet has
    nothing pressed. A packet that opens fully decided cannot distinguish "I agreed"
    from "I never looked", and would report decisions nobody made.
    """
    out = bp.build(spec())
    assert 'b.setAttribute("aria-pressed", String(b.dataset.value === d))' in out, \
        "pressed state must derive from the stored decision, never from the recommendation"
    # The recommendation may only set the marker attribute, never the pressed state.
    block = out[out.index("if (row.recommendation === o.value)"):]
    block = block[:block.index("b.addEventListener")]
    assert "aria-pressed" not in block, "the recommendation must mark, not select"


def test_bulk_accept_is_recorded_as_bulk():
    """A routine set should not cost N considered clicks — but the record must say so."""
    out = bp.build(spec())
    assert "accepted in bulk" in out
    assert "weight them accordingly" in out, "the paste must tell the agent not to over-read it"
    assert "window.confirm" in out, "bulk acceptance must be an affirmative, confirmed gesture"
    # Touching a row individually clears the bulk flag.
    assert "bulk: false" in out, "an individual click must clear the bulk marker"


def test_disagreement_is_surfaced_not_resolved():
    s = spec()
    s["rows"][0]["disagreement"] = {
        "a": {"who": "Reviewer A", "view": "Ship it."},
        "b": {"who": "Reviewer B", "view": "Hold it."},
    }
    out = bp.build(s)
    assert "Unresolved disagreement" in out
    assert "Reviewer A" in out and "Reviewer B" in out


# ---------------------------------------------------------------------------
# Validation and the anti-trigger
# ---------------------------------------------------------------------------

def test_rejects_a_packet_with_no_recommendations():
    s = spec()
    for r in s["rows"]:
        r.pop("recommendation")
    problems = bp.validate(s)
    assert any("questionnaire" in p for p in problems), problems


def test_flags_a_sub_five_row_packet():
    problems = bp.validate(spec(n=3))
    assert any(p.startswith("NOTE:") and "just ask" in p for p in problems), problems


def test_rejects_duplicate_ids_because_they_key_local_storage():
    s = spec()
    s["rows"][1]["id"] = s["rows"][0]["id"]
    assert any("duplicate id" in p for p in bp.validate(s))


def test_rejects_a_recommendation_outside_its_option_set():
    s = spec()
    s["rows"][0]["recommendation"] = "maybe"
    assert any("not one of its options" in p for p in bp.validate(s))


def test_cli_refuses_a_small_packet_without_the_flag():
    with tempfile.TemporaryDirectory() as d:
        sp = pathlib.Path(d) / "s.json"
        sp.write_text(json.dumps(spec(n=3)), encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "build_packet.py"), str(sp),
                            "-o", str(pathlib.Path(d) / "o.html")], capture_output=True, text=True)
        assert r.returncode == 2, r.stdout + r.stderr
        assert "--allow-small" in r.stderr


# ---------------------------------------------------------------------------
# Emission safety
# ---------------------------------------------------------------------------

def test_embedded_json_cannot_close_the_host_script_block():
    s = spec()
    s["rows"][0]["context"] = 'evil </script><script>alert(1)</script>'
    out = bp.build(s)
    body = out[out.index('<script type="application/json"'):]
    body = body[:body.index("</script>")]
    assert "</script>" not in body
    assert "<\\/script>" in body


def test_theme_tokens_are_defined_on_bare_root():
    """A token defined only inside a media query borrows the host's theme."""
    out = bp.build(spec())
    base = out[out.index(":root {"):out.index("@media (prefers-color-scheme: dark)")]
    for token in ("--bg:", "--ink:", "--panel:", "--line:", "--accent:"):
        assert token in base, f"{token} must have a light-mode definition on bare :root"
    assert 'body {' in out and 'background: var(--bg)' in out


def test_output_is_self_contained():
    out = bp.build(spec())
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', out)
    assert not external, f"packet must be self-contained; found external refs: {external}"


# ---------------------------------------------------------------------------
# The reader contract (v1.1.0) - born from a measured failure: a 15-row packet
# written in project-internal language collected 0 decisions from the same
# principal whose plain-language packets ran 30/30. Structure without
# comprehension collects nothing.
# ---------------------------------------------------------------------------

def test_impact_block_renders_both_consequences():
    s = spec()
    s["rows"][0]["impact"] = {"accept": "The rule waits for one more test round.",
                              "decline": "The strongest candidate from this research is discarded."}
    out = bp.build(s)
    assert "If you take the recommendation:" in out
    assert "The rule waits for one more test round." in out
    assert "The strongest candidate from this research is discarded." in out


def test_glossary_renders_as_a_terms_band_and_escapes():
    s = spec(glossary=[{"term": "holdout", "meaning": "material set aside <before> tuning"}])
    out = bp.build(s)
    assert "Terms used below (1)" in out
    assert "holdout" in out
    band = re.search(r'<details class="gloss">.*?</details>', out, re.S).group(0)
    assert "&lt;before&gt;" in band and "<before>" not in band


def test_audience_line_renders_under_the_intro():
    s = spec(audience="Rajiv, who has not read this project's research records")
    out = bp.build(s)
    assert "Written for:" in out
    assert "who has not read" in out


def test_reader_findings_are_warnings_by_default():
    problems = bp.validate(spec())
    reader = [x for x in problems if x.startswith("READER:")]
    assert reader, "a spec with no audience and no impact must raise READER findings"
    hard = [x for x in problems if not x.startswith(("NOTE:", "READER:"))]
    assert not hard, f"reader findings must not hard-fail validate(): {hard}"


def test_reader_contract_satisfied_raises_no_reader_findings():
    s = spec(audience="A principal with no project context")
    for r in s["rows"]:
        r["impact"] = {"accept": "Nothing changes today.", "decline": "The item is dropped."}
    problems = bp.validate(s)
    assert not [x for x in problems if x.startswith("READER:")]


def test_strict_reader_flag_refuses_an_alien_packet(tmp_path=None):
    import tempfile, subprocess, json as _json, pathlib as _pl
    with tempfile.TemporaryDirectory() as td:
        sp = _pl.Path(td) / "s.json"
        sp.write_text(_json.dumps(spec()))
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp),
             "--stdout", "--strict-reader"],
            capture_output=True, text=True)
        assert proc.returncode != 0, "strict-reader must refuse a packet missing audience/impact"
        assert "READER:" in proc.stderr


def test_malformed_impact_and_glossary_are_hard_errors():
    s = spec()
    s["rows"][0]["impact"] = {"accept": "only one half"}
    problems = bp.validate(s)
    assert any("impact needs both" in x for x in problems)
    s2 = spec(glossary=[{"term": "x"}])
    problems2 = bp.validate(s2)
    assert any("glossary[0] needs both" in x for x in problems2)


def _run_all():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  ok    {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL  {name}\n        {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}\n        {type(exc).__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())


def test_ids_that_collide_after_browser_coercion_are_refused():
    """JSON 1 and "1" become the same localStorage key; the generator must
    refuse the collision instead of emitting a packet whose rows share saved
    state (found by the R-02 external review)."""
    s = spec()
    s["rows"][0]["id"] = 1
    s["rows"][1]["id"] = "1"
    assert any("non-empty string" in p for p in bp.validate(s))

    with tempfile.TemporaryDirectory() as d:
        sp = pathlib.Path(d) / "s.json"
        sp.write_text(json.dumps(s), encoding="utf-8")
        out_file = pathlib.Path(d) / "o.html"
        r = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp),
             "-o", str(out_file)],
            capture_output=True, text=True,
        )
        assert r.returncode == 2, r.stdout + r.stderr
        assert not out_file.exists(), "no output may be created for a colliding spec"


def test_whitespace_and_boolean_ids_are_refused():
    s = spec()
    s["rows"][0]["id"] = "  "
    assert any("non-empty string" in p for p in bp.validate(s))

    s = spec()
    s["rows"][0]["id"] = True
    assert any("non-empty string" in p for p in bp.validate(s))
