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
            {"value": "yes", "label": "Ship the fix", "tone": "ok"},
            {"value": "no", "label": "Leave the code as it stands", "tone": "danger"},
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


def test_build_emits_a_verifiable_provenance_marker():
    """Marker pins the embedded spec: skill_outputs verifies it, the context
    doctor runs the check. A hand-authored page has no marker."""
    import hashlib
    import re
    out = bp.build(spec())
    m = re.search(r"<!-- synthesis-decision-packet spec-sha256:([0-9a-f]{64}) -->", out)
    assert m, "page must carry the provenance marker"
    embedded = re.search(r'<script type="application/json" id="spec">(.*?)</script>', out, re.S)
    assert embedded, "page must embed its spec"
    assert hashlib.sha256(embedded.group(1).encode("utf-8")).hexdigest() == m.group(1)


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


def test_ids_with_edge_or_doubled_whitespace_are_refused():
    """The pasted summary prints "id  label" and record_rulings.py splits on the
    first double space, so an id with a doubled space or surrounding whitespace
    would parse into the wrong id."""
    for bad in (" R-01", "R-01 ", "R  01"):
        s = spec()
        s["rows"][0]["id"] = bad
        problems = bp.validate(s)
        assert any("doubled whitespace" in p for p in problems), (bad, problems)
    assert not [p for p in bp.validate(spec()) if "doubled whitespace" in p]


# ---------------------------------------------------------------------------
# Option labels name consequences (v1.4.0). Fixture of the failure, 2026-09-14:
# on a 9-row packet, three rows carrying the options {"Yes, do that", "No"}
# collected notes instead of decisions - the principal could not tell what
# pressing each button would DO, so the note boxes carried what the buttons
# should have.
# ---------------------------------------------------------------------------

ACCEPTED_FORM = 'label each option by what pressing it does, e.g. "Keep them on my phone" / "Take them off my phone"'


def nine_row_packet_with_three_bare_rows():
    s = spec(n=9, audience="Rajiv, deciding what to keep on his phone")
    for r in s["rows"]:
        r["impact"] = {"accept": "They stay on the phone.", "decline": "They come off the phone."}
    for rid in ("R-03", "R-05", "R-08"):
        row = [r for r in s["rows"] if r["id"] == rid][0]
        row["options"] = [
            {"value": "yes", "label": "Yes, do that", "tone": "ok"},
            {"value": "no", "label": "No", "tone": "danger"},
        ]
    return s


def test_bare_acknowledgement_labels_raise_reader_findings_naming_row_and_labels():
    problems = bp.validate(nine_row_packet_with_three_bare_rows())
    label_findings = [p for p in problems if p.startswith("READER:") and "bare acknowledgement" in p]
    assert len(label_findings) == 3, problems
    for rid in ("R-03", "R-05", "R-08"):
        hit = [p for p in label_findings if f"({rid})" in p]
        assert len(hit) == 1, (rid, label_findings)
        assert "'Yes, do that'" in hit[0] and "'No'" in hit[0], hit[0]
        assert ACCEPTED_FORM in hit[0], hit[0]
    # The compliant rows raise no label finding at all.
    assert not [p for p in problems if "(R-01)" in p and "option label" in p], problems


def test_every_listed_bare_acknowledgement_is_caught_after_trimming_and_case_folding():
    bare = ["yes", "No", "OK", "okay", "Cancel", "Accept", "Decline", "Approve",
            "Reject", "Do it", "Yes do that", "Go", "Stop", "Yes, do that!", "No thanks.",
            "  ok  ", "GO!",
            # Padded with a stopword: the same shape as "Yes, do that" with a
            # different stopword, missed before the repair round.
            "Accept it", "Approve this", "Reject that", "Do that", "Stop it", "Go on"]
    for label in bare:
        s = spec(options=[{"value": "a", "label": label},
                          {"value": "b", "label": "Keep the current version this quarter"}])
        s["rows"][0]["recommendation"] = "a"
        problems = bp.validate(s)
        assert any("bare acknowledgement" in p and repr(label) in p for p in problems), (label, problems)


def test_packet_level_bare_labels_are_reported_once_at_packet_level():
    s = spec(options=[{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}])
    problems = bp.validate(s)
    hits = [p for p in problems if "bare acknowledgement" in p]
    assert len(hits) == 1, problems
    assert hits[0].startswith("READER: options:"), hits[0]
    assert "'Yes'" in hits[0] and "'No'" in hits[0]
    assert ACCEPTED_FORM in hits[0]


def test_labels_that_share_every_content_word_raise_a_reader_finding():
    s = spec(options=[{"value": "a", "label": "Keep it"}, {"value": "b", "label": "Keep that"}])
    s["rows"][0]["recommendation"] = "a"
    problems = bp.validate(s)
    hits = [p for p in problems if "do not differ in a content word" in p]
    assert len(hits) == 1, problems
    assert "'Keep it' / 'Keep that'" in hits[0], hits[0]
    assert ACCEPTED_FORM in hits[0]
    # Stopwords and short words carry no meaning: "Keep it on my phone" vs
    # "Keep it in my phone" differ only in stopwords.
    s2 = spec(options=[{"value": "a", "label": "Keep it on my phone"},
                       {"value": "b", "label": "Keep it in my phone"}])
    s2["rows"][0]["recommendation"] = "a"
    assert any("do not differ in a content word" in p for p in bp.validate(s2))


def test_a_bare_label_is_not_also_reported_as_an_indistinct_pair():
    s = spec(options=[{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}])
    problems = bp.validate(s)
    assert not [p for p in problems if "do not differ" in p], problems


def test_consequence_phrased_labels_raise_no_label_findings():
    """Positive control: the accepted form itself passes, as do labels that
    differ in one content word."""
    good_sets = [
        [{"value": "keep", "label": "Keep them on my phone"},
         {"value": "drop", "label": "Take them off my phone"}],
        [{"value": "take", "label": "Upgrade to the new version"},
         {"value": "hold", "label": "Keep the current version this quarter"},
         {"value": "pin", "label": "Pin the current version and record why"}],
        [{"value": "a", "label": "Publish it today"},
         {"value": "b", "label": "Publish it after the freeze"}],
    ]
    for opts in good_sets:
        s = spec(audience="A principal with no project context", options=opts)
        for r in s["rows"]:
            r["recommendation"] = opts[0]["value"]
            r["impact"] = {"accept": "Nothing changes today.", "decline": "The item is dropped."}
        problems = bp.validate(s)
        assert not [p for p in problems if p.startswith("READER:")], (opts, problems)


def test_strict_reader_refuses_bare_labels_naming_row_labels_and_accepted_form():
    with tempfile.TemporaryDirectory() as td:
        sp = pathlib.Path(td) / "s.json"
        sp.write_text(json.dumps(nine_row_packet_with_three_bare_rows()), encoding="utf-8")
        out_file = pathlib.Path(td) / "o.html"
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp),
             "-o", str(out_file), "--strict-reader"],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert not out_file.exists()
        for rid in ("R-03", "R-05", "R-08"):
            assert f"({rid})" in proc.stderr, proc.stderr
        assert "'Yes, do that'" in proc.stderr and "'No'" in proc.stderr
        assert ACCEPTED_FORM in proc.stderr
        assert "will not build:" in proc.stderr and "--strict-reader" in proc.stderr
        # Without the flag the same packet builds and the findings are warnings.
        proc2 = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "-o", str(out_file)],
            capture_output=True, text=True)
        assert proc2.returncode == 0, proc2.stdout + proc2.stderr
        assert out_file.exists()
        assert "bare acknowledgement" in proc2.stderr


# ---------------------------------------------------------------------------
# The consequence sits on the control (v1.4.0)
# ---------------------------------------------------------------------------

def test_each_option_button_carries_its_consequence():
    s = spec(audience="A principal with no project context")
    for r in s["rows"]:
        r["impact"] = {"accept": "The fix ships in the next release.",
                       "decline": "The defect stays live until someone else finds it."}
    s["rows"][0]["options"] = [
        {"value": "yes", "label": "Ship the fix", "consequence": "One PR lands today."},
        {"value": "no", "label": "Leave the code as it stands"},
    ]
    out = bp.build(s)
    # Resolution order: an explicit per-option consequence wins; otherwise the
    # impact block maps accept -> the recommended option, decline -> every other.
    fn = out[out.index("function consequenceFor"):]
    fn = fn[:fn.index("}\n", fn.index("return row.recommendation === o.value"))]
    assert "if (o.consequence) return o.consequence;" in fn
    assert "return row.recommendation === o.value ? row.impact.accept : row.impact.decline;" in fn
    assert fn.index("o.consequence") < fn.index("row.impact.accept")
    # The text is attached to the button element itself, under the label.
    build = out[out.index("function buildRow"):out.index("function render()")]
    assert 'lab.className = "olabel"' in build and "b.appendChild(lab)" in build
    assert 'why.className = "oconseq"' in build and "b.appendChild(why)" in build
    assert build.index("consequenceFor(row, o)") < build.index("b.addEventListener")
    assert ".opts button .oconseq" in out, "the consequence needs its own style on the control"
    # The explicit consequence travels in the embedded spec.
    payload = out[out.index('<script type="application/json"'):out.index("</script>")]
    assert '"consequence": "One PR lands today."' in payload
    # The row-level impact block stays as the row's summary.
    assert "If you take the recommendation:" in out


def test_per_option_consequence_must_be_a_non_empty_string():
    s = spec(options=[{"value": "yes", "label": "Ship the fix", "consequence": ""},
                      {"value": "no", "label": "Leave the code as it stands"}])
    problems = bp.validate(s)
    assert any("options[0].consequence must be a non-empty string" in p for p in problems), problems
    s2 = spec()
    s2["rows"][1]["options"] = [{"value": "yes", "label": "Ship the fix", "consequence": 7},
                               {"value": "no", "label": "Leave the code as it stands"}]
    problems2 = bp.validate(s2)
    assert any("rows[1] (R-02) options[0].consequence must be a non-empty string" in p
               for p in problems2), problems2


def test_per_row_option_sets_are_validated_like_the_packet_level_set():
    s = spec()
    s["rows"][2]["options"] = [{"value": "yes"}, {"value": "no", "label": "Leave it", "tone": "loud"}]
    problems = bp.validate(s)
    assert any("rows[2] (R-03) options[0] needs both 'value' and 'label'" in p for p in problems), problems
    assert any("rows[2] (R-03) options[1].tone 'loud'" in p for p in problems), problems


# ---------------------------------------------------------------------------
# Filing in the owning project (v1.4.0)
# ---------------------------------------------------------------------------

def compliant_spec():
    s = spec(audience="A principal with no project context", title="Phone contacts — keep or drop")
    for r in s["rows"]:
        r["impact"] = {"accept": "Nothing changes today.", "decline": "The item is dropped."}
    return s


def test_file_into_writes_dated_spec_and_page():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        sp = td / "s.json"
        s = compliant_spec()
        sp.write_text(json.dumps(s), encoding="utf-8")
        target = td / "resources" / "artifacts"
        target.mkdir(parents=True)
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "--strict-reader",
             "--file-into", str(target), "--date", "2026-09-14"],
            capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        spec_copy = target / "2026-09-14-phone-contacts-keep-or-drop-spec.json"
        page_copy = target / "2026-09-14-phone-contacts-keep-or-drop.html"
        assert spec_copy.exists() and page_copy.exists(), sorted(p.name for p in target.iterdir())
        assert json.loads(spec_copy.read_text(encoding="utf-8")) == s
        assert page_copy.read_text(encoding="utf-8") == bp.build(s)
        assert str(spec_copy) in proc.stdout and str(page_copy) in proc.stdout
        # Filing alone does not spray the page onto stdout.
        assert "<!doctype html>" not in proc.stdout
        # -o and --file-into together: the working copy and the filed copy.
        work = td / "work.html"
        proc2 = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "-o", str(work),
             "--file-into", str(target), "--date", "2026-09-15"],
            capture_output=True, text=True)
        assert proc2.returncode == 0, proc2.stdout + proc2.stderr
        assert work.exists() and (target / "2026-09-15-phone-contacts-keep-or-drop.html").exists()


def test_file_into_refuses_a_missing_directory_before_building():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        sp = td / "s.json"
        sp.write_text(json.dumps(compliant_spec()), encoding="utf-8")
        missing = td / "nope" / "artifacts"
        work = td / "work.html"
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "-o", str(work),
             "--file-into", str(missing)],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert str(missing) in proc.stderr and "not an existing directory" in proc.stderr
        assert "resources/artifacts/" in proc.stderr, proc.stderr
        assert not work.exists(), "a refused filing must not leave a half-built run"
        assert not missing.exists()


def test_date_is_validated_and_requires_file_into():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        sp = td / "s.json"
        sp.write_text(json.dumps(compliant_spec()), encoding="utf-8")
        target = td / "artifacts"
        target.mkdir()
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "--stdout", "--date", "2026-09-14"],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "--date requires --file-into" in proc.stderr
        for bad in ("2026/09/14", "20260914", "2026-13-01", "yesterday"):
            proc = subprocess.run(
                [sys.executable, str(HERE / "build_packet.py"), str(sp),
                 "--file-into", str(target), "--date", bad],
                capture_output=True, text=True)
            assert proc.returncode == 2, (bad, proc.stdout + proc.stderr)
            assert "YYYY-MM-DD" in proc.stderr and bad in proc.stderr, (bad, proc.stderr)
        assert not list(target.iterdir())


# ---------------------------------------------------------------------------
# record_rulings.py: the paste comes back as a filed record (v1.4.0)
# ---------------------------------------------------------------------------

def _rr():
    import record_rulings
    return record_rulings


def test_summary_format_literals_are_pinned_to_the_packet_javascript():
    """compose_summary() is the Python rendering of the format renderSummary()
    emits in the browser. Every literal it uses must appear in the JS, so the
    two cannot drift apart without this test failing."""
    rr = _rr()
    js = bp.TEMPLATE[bp.TEMPLATE.index("function renderSummary"):bp.TEMPLATE.index("function revealSummary")]
    for literal in rr.JS_FORMAT_LITERALS:
        assert literal in js, f"format literal not in renderSummary(): {literal!r}"
    assert '"=".repeat(SPEC.title.length)' in js
    assert 'r.id + "  " + r.label' in js
    assert '"    -> " + mark' in js
    assert '"    note: " + s.note.trim()' in js
    assert '"Decided " + decided + " of " + SPEC.rows.length + "."' in js


def test_record_rulings_round_trips_a_generated_packet():
    rr = _rr()
    s = compliant_spec()
    s["rows"][1]["disagreement"] = {"a": {"who": "A", "view": "x"}, "b": {"who": "B", "view": "y"}}
    s["rows"][4].pop("recommendation")  # a row with no recommendation
    state = {
        "R-01": {"choice": "yes"},
        "R-02": {"choice": "no", "note": "Do it behind a branch.\nReviewer B is right\nabout the window."},
        "R-03": {"choice": "yes", "bulk": True},
        "R-04": {"note": "Come back to this one."},
        "R-05": {"choice": "no"},
    }
    text = rr.compose_summary(s, state)
    assert text.startswith("Phone contacts — keep or drop\n=============================\n\n")
    assert "R-02  Item 2\n    -> Leave the code as it stands  (OVERRODE: recommended Ship the fix)\n    note: Do it behind a branch.\nReviewer B is right\nabout the window.\n\n" in text
    assert "R-03  Item 3\n    -> Ship the fix  (accepted in bulk)\n\n" in text
    assert "R-04  Item 4\n    -> — not yet decided\n    note: Come back to this one.\n\n" in text
    assert "R-05  Item 5\n    -> Leave the code as it stands\n\n" in text
    assert "R-06  Item 6\n    -> — not yet decided\n\n" in text
    assert text.endswith("Decided 4 of 6.\n1 of those were accepted in bulk rather than considered one by one — weight them accordingly.")

    record = rr.parse_summary(text)
    assert record["packet"] == "Phone contacts — keep or drop"
    assert record["decided"] == 4 and record["total"] == 6
    by_id = {r["id"]: r for r in record["rulings"]}
    assert list(by_id) == ["R-01", "R-02", "R-03", "R-04", "R-05", "R-06"]
    assert by_id["R-01"] == {"id": "R-01", "label": "Item 1", "choice_label": "Ship the fix",
                             "took_recommendation": True, "accepted_in_bulk": False,
                             "recommended_label": "Ship the fix", "note": None}
    assert by_id["R-02"]["choice_label"] == "Leave the code as it stands"
    assert by_id["R-02"]["took_recommendation"] is False
    assert by_id["R-02"]["recommended_label"] == "Ship the fix"
    assert by_id["R-02"]["note"] == "Do it behind a branch.\nReviewer B is right\nabout the window."
    assert by_id["R-03"]["took_recommendation"] is True and by_id["R-03"]["accepted_in_bulk"] is True
    assert by_id["R-04"]["choice_label"] is None and by_id["R-04"]["took_recommendation"] is None
    assert by_id["R-04"]["note"] == "Come back to this one."
    assert by_id["R-05"]["choice_label"] == "Leave the code as it stands"
    assert by_id["R-05"]["took_recommendation"] is None, "a row with no recommendation has nothing to take"
    assert by_id["R-06"]["choice_label"] is None and by_id["R-06"]["note"] is None

    # And through the CLI into the owning project's artifacts directory.
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        paste = td / "paste.txt"
        paste.write_text(text + "\n", encoding="utf-8")
        target = td / "artifacts"
        target.mkdir()
        # Rulings attach to the filed spec: file it first, as build_packet does.
        (target / "2026-09-14-phone-contacts-keep-or-drop-spec.json").write_text(
            json.dumps(s), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste),
             "--file-into", str(target), "--date", "2026-09-14"],
            capture_output=True, text=True)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        filed = target / "2026-09-14-phone-contacts-keep-or-drop-rulings.json"
        assert filed.exists(), sorted(p.name for p in target.iterdir())
        data = json.loads(filed.read_text(encoding="utf-8"))
        assert data["ruled_on"] == "2026-09-14"
        assert data["packet"] == record["packet"] and data["rulings"] == record["rulings"]
        assert str(filed) in proc.stdout
        # The rulings file shares its stem with the spec and page build_packet files.
        assert filed.name.startswith("2026-09-14-" + bp.slugify(s["title"]))
        # A second run refuses to overwrite the principal's record unless told to.
        proc2 = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste),
             "--file-into", str(target), "--date", "2026-09-14"],
            capture_output=True, text=True)
        assert proc2.returncode == 2, proc2.stdout + proc2.stderr
        assert str(filed) in proc2.stderr and "--replace" in proc2.stderr
        proc3 = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste),
             "--file-into", str(target), "--date", "2026-09-14", "--replace"],
            capture_output=True, text=True)
        assert proc3.returncode == 0, proc3.stdout + proc3.stderr


def test_record_rulings_refuses_a_paste_with_no_filed_spec():
    """A hand-authored page has no spec, so its paste can never become rulings.

    This closes the skill_outputs loop: unmarked pages can never graduate to
    closed records by hand-filing a paste.
    """
    rr = _rr()
    s = compliant_spec()
    state = {"R-01": {"choice": "yes"}}
    text = rr.compose_summary(s, state)
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        paste = td / "paste.txt"
        paste.write_text(text + "\n", encoding="utf-8")
        target = td / "artifacts"
        target.mkdir()
        proc = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste),
             "--file-into", str(target), "--date", "2026-09-14"],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "spec.json" in proc.stderr
        assert list(target.iterdir()) == []


def test_record_rulings_reads_the_storage_blocked_trailer_and_stdin():
    rr = _rr()
    s = compliant_spec()
    text = rr.compose_summary(s, {"R-01": {"choice": "yes"}}, storage_blocked=True)
    assert text.endswith("Decided 1 of 6.\n(This browser blocked local storage, so nothing was saved between sittings.)")
    record = rr.parse_summary(text)
    assert record["decided"] == 1
    proc = subprocess.run(
        [sys.executable, str(HERE / "record_rulings.py"), "-", "--stdout"],
        input=text, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["rulings"][0]["choice_label"] == "Ship the fix"


def test_record_rulings_refuses_malformed_input_naming_the_expected_first_line():
    rr = _rr()
    s = compliant_spec()
    good = rr.compose_summary(s, {"R-01": {"choice": "yes"}})
    bad_inputs = {
        "prose": "Here are my decisions:\n\nR-01 yes\n",
        "no underline": good.replace("=" * len(s["title"]), "-" * len(s["title"]), 1),
        "underline too short": good.replace("=" * len(s["title"]), "=" * 5, 1),
        "empty": "",
        "truncated": good[:good.index("R-04")],
        "decision line missing": good.replace("    -> Ship the fix  (took the recommendation)\n", "", 1),
        "count edited": good.replace("Decided 1 of 6.", "Decided 2 of 6."),
        "stray line": good.replace("\n\nR-02", "\nhello\n\nR-02", 1),
    }
    for name, text in bad_inputs.items():
        try:
            rr.parse_summary(text)
        except rr.SummaryError as exc:
            msg = str(exc)
        else:
            raise AssertionError(f"{name}: malformed paste was accepted")
        assert "Copy summary" in msg or "paste the whole summary" in msg or "line " in msg, (name, msg)
    # The first-line refusal names the expected first line exactly.
    with tempfile.TemporaryDirectory() as td:
        paste = pathlib.Path(td) / "p.txt"
        paste.write_text(bad_inputs["prose"], encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste), "--stdout"],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "the first line must be the packet title" in proc.stderr, proc.stderr
        assert 'the same number of "=" characters' in proc.stderr, proc.stderr
        assert "Copy summary" in proc.stderr, proc.stderr
        assert "Here are my decisions:" in proc.stderr, "the refusal quotes the first line it got"
        assert proc.stdout == ""


def test_record_rulings_file_into_must_exist_and_date_is_validated():
    rr = _rr()
    text = rr.compose_summary(compliant_spec(), {})
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        paste = td / "p.txt"
        paste.write_text(text, encoding="utf-8")
        missing = td / "nope"
        proc = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste), "--file-into", str(missing)],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert str(missing) in proc.stderr and "not an existing directory" in proc.stderr
        assert "resources/artifacts/" in proc.stderr
        target = td / "artifacts"
        target.mkdir()
        proc = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste),
             "--file-into", str(target), "--date", "14-09-2026"],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "YYYY-MM-DD" in proc.stderr and "14-09-2026" in proc.stderr
        assert not list(target.iterdir())
        proc = subprocess.run(
            [sys.executable, str(HERE / "record_rulings.py"), str(paste)],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "--file-into" in proc.stderr and "--stdout" in proc.stderr


# ---------------------------------------------------------------------------
# A summary captured from the real page. On 2026-09-14 the packet built from
# browser_fixture_spec() was served over a plain local HTTP server and driven
# in Chromium (Playwright): one considered click with a two-line note on C-01,
# an override on C-02, then "Take all remaining" for the other seven. The text
# below is the summary textarea's value afterwards, verbatim, and BROWSER_STATE
# is the saved localStorage state the page held at that moment.
# ---------------------------------------------------------------------------

def browser_fixture_spec():
    rows = []
    for i in range(1, 10):
        rows.append({"id": f"C-{i:02d}", "label": f"Contact group {i}", "recommendation": "keep",
                     "context": "A group of contacts synced from an old account.",
                     "reasoning": "Keep them: three of them messaged this month.",
                     "impact": {"accept": "They stay on the phone and keep syncing.",
                                "decline": "They come off the phone; the old account still has them."}})
    rows[0]["options"] = [
        {"value": "keep", "label": "Keep them on my phone", "tone": "ok",
         "consequence": "Nothing changes; they keep syncing."},
        {"value": "drop", "label": "Take them off my phone", "tone": "danger",
         "consequence": "Gone from the phone today; still in the old account."}]
    rows[1]["disagreement"] = {"a": {"who": "Pass 1", "view": "Keep: they messaged this month."},
                               "b": {"who": "Pass 2", "view": "Drop: duplicates of the work account."}}
    return {"title": "Phone contacts — keep or drop",
            "audience": "Rajiv, deciding what stays on his phone",
            "options": [{"value": "keep", "label": "Keep them on my phone", "tone": "ok"},
                        {"value": "drop", "label": "Take them off my phone", "tone": "danger"}],
            "rows": rows}


BROWSER_STATE = {
    "C-01": {"choice": "keep", "bulk": False,
             "note": "Keep, but merge the two duplicates first.\nSecond line of the note."},
    "C-02": {"choice": "drop", "bulk": False},
    **{f"C-{i:02d}": {"choice": "keep", "bulk": True} for i in range(3, 10)},
}

BROWSER_SUMMARY = (
    "Phone contacts — keep or drop\n"
    "=============================\n"
    "\n"
    "C-01  Contact group 1\n"
    "    -> Keep them on my phone  (took the recommendation)\n"
    "    note: Keep, but merge the two duplicates first.\n"
    "Second line of the note.\n"
    "\n"
    "C-02  Contact group 2\n"
    "    -> Take them off my phone  (OVERRODE: recommended Keep them on my phone)\n"
    "\n"
    + "".join(
        f"C-{i:02d}  Contact group {i}\n"
        "    -> Keep them on my phone  (accepted in bulk)\n"
        "\n" for i in range(3, 10))
    + "Decided 9 of 9.\n"
    "7 of those were accepted in bulk rather than considered one by one — weight them accordingly."
)


def test_browser_fixture_spec_builds_clean_under_the_reader_contract():
    problems = bp.validate(browser_fixture_spec())
    assert not [p for p in problems if not p.startswith("NOTE:")], problems


def test_record_rulings_parses_a_summary_captured_from_the_real_page():
    rr = _rr()
    assert rr.compose_summary(browser_fixture_spec(), BROWSER_STATE) == BROWSER_SUMMARY, (
        "compose_summary() must reproduce the page's own output byte for byte")
    record = rr.parse_summary(BROWSER_SUMMARY)
    assert record["packet"] == "Phone contacts — keep or drop"
    assert record["decided"] == 9 and record["total"] == 9
    assert [r["id"] for r in record["rulings"]] == [f"C-{i:02d}" for i in range(1, 10)]
    c01, c02 = record["rulings"][0], record["rulings"][1]
    assert c01["choice_label"] == "Keep them on my phone" and c01["took_recommendation"] is True
    assert c01["accepted_in_bulk"] is False
    assert c01["note"] == "Keep, but merge the two duplicates first.\nSecond line of the note."
    assert c02["choice_label"] == "Take them off my phone" and c02["took_recommendation"] is False
    assert c02["recommended_label"] == "Keep them on my phone" and c02["note"] is None
    assert all(r["accepted_in_bulk"] and r["took_recommendation"] for r in record["rulings"][2:])
    assert sum(1 for r in record["rulings"] if r["accepted_in_bulk"]) == 7


# ---------------------------------------------------------------------------
# Repair round, 2026-09-14: a packet that builds must file. Every field the
# summary prints on its own line is single-line, the title underline counts
# the way the page counts, an option set offers a real choice, and the
# parser's refusals quote what they received.
# ---------------------------------------------------------------------------

SINGLE_LINE_FORM = ("the pasted summary is one line per field, so title, row labels "
                    "and option labels must be single-line")


def _refused(rr, text):
    try:
        rr.parse_summary(text)
    except rr.SummaryError as exc:
        return str(exc)
    raise AssertionError("malformed paste was accepted")


def test_line_breaks_in_title_row_label_option_label_or_id_are_refused():
    """Reproduced before the fix: a row label "Item 2\\nsecond line" passed
    validate() and the built packet's own paste was then refused by
    record_rulings.py - a packet that builds and cannot be filed, found only
    after the principal's sitting."""
    rr = _rr()
    cases = [
        (lambda s: s.__setitem__("title", "Two\nlines"),
         "title 'Two\\nlines' contains a line break - " + SINGLE_LINE_FORM),
        (lambda s: s["rows"][1].__setitem__("label", "Item 2\nsecond line"),
         "rows[1] (R-02) label 'Item 2\\nsecond line' contains a line break - " + SINGLE_LINE_FORM),
        (lambda s: s["rows"][1].__setitem__("label", "Item 2\rsecond line"),
         "rows[1] (R-02) label 'Item 2\\rsecond line' contains a line break - " + SINGLE_LINE_FORM),
        (lambda s: s["options"][0].__setitem__("label", "Ship the\nfix"),
         "options[0] label 'Ship the\\nfix' contains a line break - " + SINGLE_LINE_FORM),
        (lambda s: s["rows"][2].__setitem__("options", [
            {"value": "yes", "label": "Ship the\nfix"},
            {"value": "no", "label": "Leave the code as it stands"}]),
         "rows[2] (R-03) options[0] label 'Ship the\\nfix' contains a line break - " + SINGLE_LINE_FORM),
    ]
    for mutate, expected in cases:
        s = compliant_spec()
        mutate(s)
        problems = bp.validate(s)
        assert expected in problems, (expected, problems)
        # Hard, not READER: the build is refused with or without --strict-reader.
        assert not expected.startswith(("NOTE:", "READER:"))
    s = compliant_spec()
    s["rows"][0]["id"] = "R\n01"
    problems = bp.validate(s)
    assert ("rows[0] id 'R\\n01' has leading, trailing or doubled whitespace or a line break - "
            'the pasted summary prints "id  label" on one line and record_rulings.py splits on '
            "the first double space") in problems, problems

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        sp = td / "s.json"
        s = compliant_spec()
        s["rows"][1]["label"] = "Item 2\nsecond line"
        sp.write_text(json.dumps(s), encoding="utf-8")
        out_file = td / "o.html"
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "-o", str(out_file)],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert not out_file.exists()
        assert "rows[1] (R-02) label 'Item 2\\nsecond line' contains a line break" in proc.stderr
        assert SINGLE_LINE_FORM in proc.stderr

    # Positive control: single-line fields round-trip through the parser.
    s = compliant_spec()
    s["title"] = "Two lines"
    s["rows"][1]["label"] = "Item 2 second line"
    s["options"][0]["label"] = "Ship the fix"
    assert not [p for p in bp.validate(s) if "line break" in p]
    state = {"R-01": {"choice": "yes"}, "R-02": {"choice": "no", "note": "Behind a branch."}}
    record = rr.parse_summary(rr.compose_summary(s, state))
    assert record["packet"] == "Two lines" and record["decided"] == 2
    assert record["rulings"][1]["label"] == "Item 2 second line"
    assert record["rulings"][1]["choice_label"] == "Leave the code as it stands"
    assert record["rulings"][1]["note"] == "Behind a branch."


def test_title_underline_counts_utf16_units_like_the_page():
    """The page underlines the title with "=".repeat(SPEC.title.length), and a
    JavaScript length counts UTF-16 code units: an emoji is two. A Python
    len() counts one, so before the fix the paste from a page titled with an
    emoji was refused at its second line.

    Positive control, 2026-09-14: the packet built from this spec was served
    over a local HTTP server and read in Chromium (Playwright). The page
    reported SPEC.title.length 17 for the 16-code-point title and its summary
    textarea's second line was 17 "=" characters, the values asserted here."""
    rr = _rr()
    s = compliant_spec()
    s["title"] = "Phone \U0001F4F1 contacts"
    assert len(s["title"]) == 16 and rr.js_length(s["title"]) == 17
    text = rr.compose_summary(s, {"R-01": {"choice": "yes"}})
    assert text.split("\n")[1] == "=" * 17
    record = rr.parse_summary(text)
    assert record["packet"] == s["title"] and record["decided"] == 1
    # An underline of the code-point length is what an edited paste would carry.
    assert "Copy summary" in _refused(rr, text.replace("=" * 17, "=" * 16, 1))


def test_worked_example_paste_parses_to_the_rulings_file_it_shows():
    """references/worked-example.md shows a spec, the paste its page produces,
    and the rulings JSON record_rulings.py writes from that paste. The three
    must agree, and the parser must accept the paste, or the canonical example
    demonstrates output the shipped parser refuses (it did: "Decided 11 of 11."
    above two row blocks)."""
    rr = _rr()
    doc = (HERE.parent / "references" / "worked-example.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^```([a-z]*)\n(.*?)^```", doc, re.S | re.M)
    json_blocks = [b for lang, b in blocks if lang == "json"]
    pastes = [b for lang, b in blocks if lang == ""]
    bash = [b for lang, b in blocks if lang == "bash"]
    assert len(json_blocks) == 2 and len(pastes) == 1 and len(bash) == 2, [lang for lang, _ in blocks]
    example = json.loads(json_blocks[0])
    shown = json.loads(json_blocks[1])
    paste = pastes[0].rstrip("\n")

    # The spec builds clean under --strict-reader --allow-small.
    problems = bp.validate(example)
    assert [p for p in problems if not p.startswith("NOTE:")] == [], problems
    assert "--allow-small" in bash[0], bash[0]

    # The paste is exactly what the page emits for the rulings it shows.
    state = {
        "D-01": {"choice": "take"},
        "D-02": {"choice": "take", "note": shown["rulings"][1]["note"]},
    }
    assert rr.compose_summary(example, state) == paste

    # And the parser turns it into exactly the JSON the document shows.
    parsed = rr.parse_summary(paste)
    assert parsed["total"] == len(example["rows"]) == shown["total"]
    assert parsed["decided"] == shown["decided"]
    assert [r["id"] for r in parsed["rulings"]] == [r["id"] for r in example["rows"]]
    proc = subprocess.run(
        [sys.executable, str(HERE / "record_rulings.py"), "-", "--stdout", "--date", shown["ruled_on"]],
        input=paste, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout) == shown


def test_a_one_button_option_set_is_refused_at_packet_and_row_level():
    tail = ("must offer at least two options - a one-button set records no decision; "
            "give the principal the alternative as a second labelled option")
    s = compliant_spec()
    s["options"] = [{"value": "only", "label": "Keep them on my phone"}]
    for r in s["rows"]:
        r["recommendation"] = "only"
    assert "options " + tail in bp.validate(s), bp.validate(s)

    s = compliant_spec()
    s["rows"][2]["options"] = [{"value": "yes", "label": "Keep them on my phone"}]
    problems = bp.validate(s)
    assert "rows[2] (R-03) options " + tail in problems, problems
    assert not [p for p in problems if "(R-01)" in p or p.startswith("options ")], problems

    # An empty packet-level list is reported once, as the missing field.
    s = compliant_spec()
    s["options"] = []
    problems = bp.validate(s)
    assert "missing required field: options (a non-empty list)" in problems
    assert not [p for p in problems if tail in p], problems

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        sp = td / "s.json"
        s = compliant_spec()
        s["rows"][2]["options"] = [{"value": "yes", "label": "Keep them on my phone"}]
        sp.write_text(json.dumps(s), encoding="utf-8")
        out_file = td / "o.html"
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "-o", str(out_file)],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert not out_file.exists()
        assert "rows[2] (R-03) options " + tail in proc.stderr


def test_duplicate_option_values_in_one_set_are_refused():
    """Two buttons sharing a value both render pressed for one saved choice,
    and labelFor() returns the first label whichever was pressed, so the filed
    rulings would record the second button's press as the first."""
    tail = ("is used by more than one option - every option in a set needs its own value "
            "because the value keys the pressed state and the summary label")
    s = compliant_spec()
    s["options"] = [{"value": "a", "label": "Keep them on my phone"},
                    {"value": "a", "label": "Take them off my phone"}]
    for r in s["rows"]:
        r["recommendation"] = "a"
    problems = bp.validate(s)
    assert "options value 'a' " + tail in problems, problems

    s = compliant_spec()
    s["rows"][1]["options"] = [{"value": "x", "label": "Keep them on my phone"},
                               {"value": "y", "label": "Take them off my phone"},
                               {"value": "x", "label": "Archive them"},
                               {"value": "y", "label": "Merge them"}]
    s["rows"][1]["recommendation"] = "x"
    problems = bp.validate(s)
    assert ("rows[1] (R-02) options values 'x', 'y' are used by more than one option - every "
            "option in a set needs its own value because the value keys the pressed state and "
            "the summary label") in problems, problems

    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        sp = td / "s.json"
        s = compliant_spec()
        s["options"] = [{"value": "a", "label": "Keep them on my phone"},
                        {"value": "a", "label": "Take them off my phone"}]
        for r in s["rows"]:
            r["recommendation"] = "a"
        sp.write_text(json.dumps(s), encoding="utf-8")
        out_file = td / "o.html"
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_packet.py"), str(sp), "-o", str(out_file)],
            capture_output=True, text=True)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert not out_file.exists()
        assert "options value 'a' " + tail in proc.stderr


def test_option_values_must_be_strings_because_the_page_compares_dataset_strings():
    """b.dataset.value stores a string and the saved choice keeps the JSON
    type, so a numeric value is decided in the counts and never pressed on
    the control; JSON 1 and "1" also collide in the DOM while distinct here."""
    s = compliant_spec()
    s["options"] = [{"value": 1, "label": "Keep them on my phone"},
                    {"value": "1", "label": "Take them off my phone"}]
    for r in s["rows"]:
        r["recommendation"] = "1"
    problems = bp.validate(s)
    assert ("options[0].value 1 must be a non-empty string - the button's pressed state is keyed "
            "through a DOM dataset, which stores strings only") in problems, problems
    assert not [p for p in problems if "used by more than one option" in p], problems
    s = compliant_spec()
    s["rows"][0]["options"] = [{"value": True, "label": "Keep them on my phone"},
                               {"value": "drop", "label": "Take them off my phone"}]
    s["rows"][0]["recommendation"] = "drop"
    assert any("rows[0] (R-01) options[0].value True must be a non-empty string" in p
               for p in bp.validate(s))


def test_record_rulings_refusals_quote_what_they_received():
    """(a) A chat surface that pads blank lines to a single space changes
    nothing, and a non-blank third line is quoted. (b) Content after a block's
    closing blank is quoted with its own line number and the two forms that
    were accepted there; the old message said "got ''" for a blank line it
    had itself required."""
    rr = _rr()
    good = rr.compose_summary(compliant_spec(), {"R-01": {"choice": "yes"}})
    padded = good.replace("\n\n", "\n \n")
    assert padded != good
    assert rr.parse_summary(padded) == rr.parse_summary(good)

    lines = good.split("\n")
    lines.insert(2, "R-01  Item 1")
    assert _refused(rr, "\n".join(lines)) == (
        "line 3: expected a blank line after the title underline, got 'R-01  Item 1'")

    expected_forms = ("expected '    note: ' or the next row header ('<id>  <label>' followed by "
                      "a '    -> ' line) after the decision line")
    stray_after_blank = good.replace("\n\nR-02", "\n\nstray text here\n\nR-02", 1)
    assert _refused(rr, stray_after_blank) == f"line 7: {expected_forms}, got 'stray text here'"
    stray_right_after = good.replace("\n\nR-02", "\nstray text here\n\nR-02", 1)
    assert _refused(rr, stray_right_after) == f"line 6: {expected_forms}, got 'stray text here'"
    # A row header whose decision line went missing is quoted as the header it is.
    broken = good.replace("\nR-02  Item 2\n    -> — not yet decided\n", "\nR-02  Item 2\n", 1)
    assert _refused(rr, broken) == f"line 7: {expected_forms}, got 'R-02  Item 2'"
    # Never "got ''": no refusal quotes a blank line as the offending content.
    for text in (stray_after_blank, stray_right_after, broken):
        assert "got ''" not in _refused(rr, text)


if __name__ == "__main__":
    sys.exit(_run_all())
