"""Recording the returned summary: spec-bound parsing, refusals that quote, filing, bulk.

Edge cases E45, E46, E50 and E51 of the v5 evaluation carry their number in the test name.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_packet as bp  # noqa: E402
import record_rulings as rr  # noqa: E402


def spec(n=5):
    return {
        "title": "Synthetic release choices", "audience": "Fixture principal",
        "options": [{"value": "test", "label": "Test the fixture"},
                    {"value": "hold", "label": "Keep the fixture unchanged"}],
        "rows": [{"id": f"R-{i}", "label": f"Synthetic target {i}", "context": "Fixture target, never a real service.",
                  "impact": {"accept": "Run the fixture test.", "decline": "Retain the fixture."},
                  "recommendation": "test"} for i in range(n)],
    }


def refused(text, current):
    with pytest.raises(rr.SummaryError) as caught:
        rr.parse_summary(text, current)
    return str(caught.value)


def record(*args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPTS / "record_rulings.py"), *map(str, args)],
                          input=stdin, capture_output=True, text=True)


def filed(tmp_path, current):
    artifacts = tmp_path / "resources" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    spec_copy, page_copy = bp.file_packet(current, bp.build(current), artifacts, "2026-09-24")
    return artifacts, spec_copy, page_copy


def test_js_format_literals_are_pinned_to_the_page_javascript():
    template = (SKILL / "assets" / "packet-template.html").read_text(encoding="utf-8")
    render = template[template.index("function renderSummary"):template.index("function revealSummary")]
    for literal in rr.JS_FORMAT_LITERALS:
        assert literal in render, literal


def test_compose_and_parse_round_trip_and_label_overrides():
    current = spec()
    text = rr.compose_summary(current, {"R-0": {"choice": "test"}, "R-1": {"choice": "hold", "note": "Not yet."}})
    assert "    -> Test the fixture  (took the recommendation)" in text
    assert "    -> Keep the fixture unchanged  (OVERRODE: recommended Test the fixture)" in text
    assert "    -> — not yet decided" in text and "Decided 2 of 5." in text
    parsed = rr.parse_summary(text, current)
    assert set(parsed) == {"packet", "decided", "total", "rulings", "schema_version", "binding"}
    assert parsed["binding"] == {"status": "spec-bound", "spec_sha256": bp.spec_digest(current)}
    first, second = parsed["rulings"][:2]
    assert first["took_recommendation"] is True and second["took_recommendation"] is False
    assert second["note"] == "Not yet." and parsed["rulings"][2]["choice_value"] is None


def test_record_succession_contract_parse_and_compose_signatures():
    """skills/synthesis-context-lifecycle/scripts/record_succession.py rebuilds a filed
    record with parse_summary(compose_summary(spec, state), spec) and compares every key."""
    assert list(inspect.signature(rr.parse_summary).parameters)[:2] == ["text", "spec"]
    assert list(inspect.signature(rr.compose_summary).parameters)[:2] == ["spec", "state"]
    current = spec()
    parsed = rr.parse_summary(rr.compose_summary(current, {"R-0": {"choice": "test", "note": "a  "}}), current)
    state = {r["id"]: {"choice": r["choice_value"], "note": r["note"] or "", "bulk": r["accepted_in_bulk"]}
             for r in parsed["rulings"]}
    assert rr.parse_summary(rr.compose_summary(current, state), current) == parsed


def test_e46_bulk_acceptance_is_labelled_in_the_paste_and_in_the_record(tmp_path):
    current = spec()
    state = {f"R-{i}": {"choice": "test", "bulk": True} for i in range(3)}
    state["R-3"] = {"choice": "test"}
    text = rr.compose_summary(current, state)
    assert text.count("(accepted in bulk)") == 3 and text.count("(took the recommendation)") == 1
    assert "3 of those were accepted in bulk rather than considered one by one" in text
    parsed = rr.parse_summary(text, current)
    assert [r["accepted_in_bulk"] for r in parsed["rulings"]] == [True, True, True, False, False]
    forged = text.replace('"choice":"test","note":"","bulk":false', '"choice":null,"note":"","bulk":true', 1)
    assert "bulk acceptance must take the row's recommendation" in refused(forged, current)
    artifacts, spec_copy, _ = filed(tmp_path, current)
    (tmp_path / "paste.txt").write_text(text, encoding="utf-8")
    assert record(tmp_path / "paste.txt", "--spec", spec_copy, "--file-into", artifacts).returncode == 0
    rulings = json.loads(next(artifacts.glob("*-rulings.json")).read_text(encoding="utf-8"))
    assert sum(r["accepted_in_bulk"] for r in rulings["rulings"]) == 3


def test_e45_a_storage_blocked_paste_alone_records_every_decision_and_says_so(tmp_path):
    """With storage blocked nothing survives between sittings, so the paste is the record."""
    current = spec()
    state = {f"R-{i}": {"choice": "hold" if i % 2 else "test"} for i in range(5)}
    text = rr.compose_summary(current, state, storage_blocked=True)
    assert rr.STORAGE_TRAILER in text and '"storage_blocked":true' in text
    out = record("-", "--spec", filed(tmp_path, current)[1], "--stdout", stdin=text)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result["storage_blocked"] is True and result["decided"] == 5
    assert [r["choice_value"] for r in result["rulings"]] == ["test", "hold", "test", "hold", "test"]


@pytest.mark.parametrize("change", [
    lambda s: s["options"][0].update(consequence="Publish to a different synthetic target."),
    lambda s: s["options"][0].update(label="Test a different fixture"),
    lambda s: s["rows"][0].update(label="A different target"),
    lambda s: s["rows"].reverse(),
    lambda s: s["rows"].pop(),
    lambda s: s.update(scope="A wider scope"),
])
def test_e50_an_old_paste_is_refused_when_the_spec_changed_after_the_answer(tmp_path, change):
    """A paste made against an older option meaning is refused, never mapped onto the new one."""
    original = spec()
    text = rr.compose_summary(original, {"R-0": {"choice": "test"}})
    changed = copy.deepcopy(original)
    change(changed)
    assert "different version of the spec" in refused(text, changed)
    artifacts, spec_copy, _ = filed(tmp_path, changed)
    (tmp_path / "paste.txt").write_text(text, encoding="utf-8")
    result = record(tmp_path / "paste.txt", "--spec", spec_copy, "--file-into", artifacts)
    assert result.returncode == 2 and "different version of the spec" in result.stderr
    assert not list(artifacts.glob("*-rulings.json"))


def test_e51_rows_or_options_that_do_not_match_are_refused_quoting_what_was_received():
    current = spec()
    good = rr.compose_summary(current, {"R-0": {"choice": "test", "note": "Private note text."}})
    message = refused(good.replace("R-1  Synthetic target 1", "R-0  Synthetic target 0"), current)
    assert "row R-1: label line" in message and "received 'R-0  Synthetic target 0'" in message
    message = refused(good.replace("    -> Test the fixture", "    -> Publish all fixtures"), current)
    assert "row R-0: decision line" in message and "received '    -> Publish all fixtures" in message
    message = refused(good.replace('"choice":"test"', '"choice":"publish"', 1), current)
    assert "received option value 'publish'" in message
    message = refused(good.replace('{"id":"R-0"', '{"id":"R-9"', 1), current)
    assert "bound row 1 is 'R-9'; the spec's row 1 is 'R-0'" in message
    message = refused("Something else\n" + good, current)
    assert "got first line: 'Something else'" in message
    message = refused(good + "\nthanks!", current)
    assert "received 'thanks!'" in message
    message = refused(good.replace("    note: Private note text.", "    note: Edited note text."), current)
    assert "row R-0: note differs at summary line 6" in message
    assert "Private" not in message and "Edited" not in message  # a refusal never repeats a note
    message = refused(good.replace("\nDecided 1 of 5.", "\nDecided 1 of 5.\nstray line"), current)
    assert "received 'stray line'" in message


def test_e51_a_valid_paste_is_filed_beside_the_spec_and_page(tmp_path):
    current = spec()
    artifacts, spec_copy, page_copy = filed(tmp_path, current)
    text = rr.compose_summary(current, {"R-0": {"choice": "test"}, "R-4": {"choice": "hold"}})
    paste = tmp_path / "paste.txt"
    paste.write_text(text, encoding="utf-8")
    result = record(paste, "--file-into", artifacts, "--date", "2026-09-24")  # spec found by title
    assert result.returncode == 0, result.stderr
    rulings = artifacts / "2026-09-24-synthetic-release-choices-rulings.json"
    assert rulings.parent == spec_copy.parent == page_copy.parent
    data = json.loads(rulings.read_text(encoding="utf-8"))
    assert data["spec_file"] == spec_copy.name and data["decided"] == 2 and data["ruled_on"] == "2026-09-24"
    assert data["authorization"]["granted"] is False and data["authorization"]["authentication"] == "unverified"
    assert "no action authority granted" in result.stdout
    assert record(paste, "--file-into", artifacts, "--date", "2026-09-24").returncode == 0  # idempotent
    assert len(list(artifacts.glob("*-rulings.json"))) == 1
    paste.write_text(rr.compose_summary(current, {"R-0": {"choice": "hold"}}), encoding="utf-8")
    assert record(paste, "--file-into", artifacts, "--date", "2026-09-24").returncode == 0
    assert len(list(artifacts.glob("*-rulings.json"))) == 2 and json.loads(rulings.read_text())["decided"] == 2


def test_the_spec_must_be_named_when_the_title_is_not_unique(tmp_path):
    current = spec()
    artifacts, spec_copy, _ = filed(tmp_path, current)
    revised = copy.deepcopy(current)
    revised["rows"][0]["context"] = "Revised fixture."
    bp.file_packet(revised, bp.build(revised), artifacts, "2026-09-25")
    paste = tmp_path / "paste.txt"
    paste.write_text(rr.compose_summary(current, {"R-0": {"choice": "test"}}), encoding="utf-8")
    ambiguous = record(paste, "--file-into", artifacts)
    assert ambiguous.returncode == 2 and "found 2 filed *-spec.json" in ambiguous.stderr
    assert record(paste, "--spec", spec_copy, "--file-into", artifacts).returncode == 0
    assert record(paste, "--stdout").returncode == 2  # --stdout alone has no spec to bind to


def test_a_summary_without_the_binding_line_is_refused_with_the_reason():
    current = spec()
    text = rr.compose_summary(current, {"R-0": {"choice": "test"}}).rsplit("\n", 1)[0]
    message = refused(text, current)
    assert "binding line" in message and "received 'Decided 1 of 5.'" in message and "rebuild" in message


def test_note_whitespace_tolerance_applies_only_to_notes():
    """Clipboards and editors add CRLF and trailing spaces; the note's own words, indentation
    and paragraph breaks still bind, and no other field gains tolerance."""
    current = spec()
    text = rr.compose_summary(current, {"R-0": {"choice": "test", "note": "First line\n\n  indented"}})
    noisy = text.replace("    note: First line", "    note: First line   ").replace("\n", "\r\n")
    assert rr.parse_summary(noisy, current)["rulings"][0]["note"] == "First line\n\n  indented"
    assert "label line" in refused(text.replace("R-0  Synthetic target 0", "R-0  Synthetic target 0 "), current)


def test_title_underline_counts_utf16_units_like_the_page():
    current = spec()
    current["title"] = "Phone \U0001F4F1 contacts"
    assert len(current["title"]) == 16 and rr.js_length(current["title"]) == 17
    text = rr.compose_summary(current, {"R-0": {"choice": "test"}})
    assert text.split("\n")[1] == "=" * 17
    assert "Copy summary" in refused(text.replace("=" * 17, "=" * 16, 1), current)


def test_unavailable_review_material_cannot_carry_a_choice():
    current = spec()
    current["rows"][0].update({"revision": "r1", "delivery": {"format": "Plain", "destinations": [], "attachments": []},
                               "review_assets": [{"id": "gone", "title": "Missing", "kind": "plain_text",
                                                  "content": {"unavailable": "Not supplied"}}]})
    with pytest.raises(rr.SummaryError, match="unavailable review material"):
        rr.compose_summary(current, {"R-0": {"choice": "test"}})
    text = rr.compose_summary(current, {"R-1": {"choice": "test"}})
    forged = text.replace('{"id":"R-0","choice":null', '{"id":"R-0","choice":"test"', 1)
    assert "unavailable review material" in refused(forged, current)
    parsed = rr.parse_summary(text, current)
    assert parsed["rulings"][0]["review_assets"] == current["rows"][0]["review_assets"]


def test_worked_example_paste_parses_to_the_rulings_file_it_shows(tmp_path):
    """references/worked-example.md shows a spec, the paste its page produces, and the
    rulings file record_rulings.py writes from that paste; all three must agree."""
    doc = (SKILL / "references" / "worked-example.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^```([a-z]*)\n(.*?)^```", doc, re.S | re.M)
    json_blocks = [b for lang, b in blocks if lang == "json"]
    pastes = [b for lang, b in blocks if lang == ""]
    bash = [b for lang, b in blocks if lang == "bash"]
    assert len(json_blocks) == 2 and len(pastes) == 1 and len(bash) == 3, [lang for lang, _ in blocks]
    example, shown, paste = json.loads(json_blocks[0]), json.loads(json_blocks[1]), pastes[0].rstrip("\n")
    assert [p for p in bp.validate(example) if not p.startswith("NOTE:")] == []
    assert "--allow-small" in bash[0] and "--strict-reader" in bash[0]
    state = {"D-01": {"choice": "take"}, "D-02": {"choice": "take", "note": shown["rulings"][1]["note"]}}
    assert rr.compose_summary(example, state) == paste
    current = tmp_path / shown["spec_file"]
    current.write_bytes(bp.canonical_spec_bytes(example))
    result = record("-", "--stdout", "--date", shown["ruled_on"], "--spec", current, stdin=paste)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == shown
    assert hashlib.sha256(bp.canonical_spec_bytes(example)).hexdigest() == shown["binding"]["spec_sha256"]
    # The example's carry-forward step: both rows are decided, so nothing is carried.
    (tmp_path / "2026-09-14-dependency-sweep-q3-rulings.json").write_text(result.stdout, encoding="utf-8")
    assert "carry_forward.py" in bash[2] and "--successor" in bash[2]
    carried = subprocess.run([sys.executable, str(SCRIPTS / "carry_forward.py"), str(current),
                              "--successor", str(tmp_path / "dep-sweep-continued.json")],
                             capture_output=True, text=True)
    assert carried.returncode == 0, carried.stderr
    assert carried.stdout.strip() == "all 2 decisions have recorded rulings; nothing to carry forward"
    assert "all 2 decisions have recorded rulings; nothing to" in doc
    assert not (tmp_path / "dep-sweep-continued.json").exists()
