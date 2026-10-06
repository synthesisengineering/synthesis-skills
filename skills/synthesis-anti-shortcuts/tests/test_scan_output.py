"""Tests for scan_output.py and the costume catalog it reads.

The effort_rationale tests (Case 7) came with the category; the rest pin the
catalog's shape, the quoted-discussion exemption (scenario E89) and the
command line's exit codes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

import scan_output  # noqa: E402

SCRIPT = SKILL / "scripts" / "scan_output.py"


def _ids(text):
    _, catalog = scan_output.load_catalog()
    return [d.phrase_id for d in scan_output.scan(text, catalog)]


def test_fraction_of_cost_hits_bare_usage():
    assert "er_fraction_of_cost" in _ids("I recommend A over B at a fraction of the cost.")


def test_fraction_of_cost_hits_case_insensitive():
    assert "er_fraction_of_cost" in _ids("At a Fraction of Their Effort, A still wins.")


def test_fraction_of_cost_misses_quoted_discussion():
    assert "er_fraction_of_cost" not in _ids('The catalog entry "fraction of the cost" needs examples.')


def test_cheaper_option_hits_bare_usage():
    assert "er_cheaper_option" in _ids("Take the cheaper option and move on.")


def test_cheaper_option_misses_quoted_discussion():
    assert "er_cheaper_option" not in _ids("We discussed the 'cheaper option' framing yesterday.")


def test_clean_recommendation_is_quiet():
    ids = _ids("B is the better solution on robustness and failure modes; "
               "it costs roughly twice as much to build.")
    assert "er_fraction_of_cost" not in ids
    assert "er_cheaper_option" not in ids


def test_effort_rationale_category_registered():
    categories, _ = scan_output.load_catalog()
    assert "effort_rationale" in categories


# E89: a phrase quoted in discussion is exempt; a bare use is flagged.
@pytest.mark.parametrize("quoted", [
    'The rule bans "preserves existing" as a pro.',
    "The rule bans “preserves existing” as a pro.",
    "The rule bans `preserves existing` as a pro.",
    "Examples:\n```\nthis preserves existing paths\n```\n",
])
def test_quoted_or_code_use_is_exempt(quoted):
    assert "bc_preserves_existing" not in _ids(quoted)


def test_bare_use_is_flagged():
    assert "bc_preserves_existing" in _ids("Option B preserves existing paths.")


def test_for_now_is_flagged_at_the_end_of_a_reply():
    assert "df_for_now" in _ids("I left the old parser in place for now")


def test_catalog_is_well_formed():
    categories, entries = scan_output.load_catalog()
    assert len(entries) >= 54
    assert len({e.id for e in entries}) == len(entries)
    for entry in entries:
        assert entry.category in categories, entry.id
        assert entry.rationale and entry.replacement, entry.id
        scan_output.compile_pattern(entry)


def test_duplicate_ids_and_bad_patterns_are_refused(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"phrases": [{"id": "a", "phrase": "x"}, {"id": "a", "phrase": "y"}]}))
    with pytest.raises(ValueError, match="duplicate"):
        scan_output.load_catalog(bad)
    bad.write_text(json.dumps({"phrases": [{"id": "b", "phrase": "(", "match": "regex"}]}))
    with pytest.raises(ValueError, match="compile"):
        scan_output.load_catalog(bad)


def _run(*args, stdin=""):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                          capture_output=True, text=True, timeout=30)


def test_cli_exit_codes_and_report(tmp_path):
    clean = _run("-", stdin="The work is complete and verified.\n")
    assert clean.returncode == 0 and clean.stdout.startswith("OK")
    hit = _run(stdin="We can revisit later.\n")
    assert hit.returncode == 1
    assert "[df_revisit_later]" in hit.stdout and "rewrite:" in hit.stdout
    quiet = _run("--quiet", stdin="We can revisit later.\n")
    assert quiet.returncode == 1 and quiet.stdout == ""
    data = json.loads(_run("--json", stdin="That's a larger task.\n").stdout)
    assert data["detection_count"] == 1
    assert _run(str(tmp_path / "missing.md")).returncode == 2
    assert _run("--catalog", str(tmp_path / "missing.json"), stdin="x").returncode == 2


def test_category_filter():
    only = _run("--category", "dismissal", "--json", stdin="Not urgent, and we can revisit later.\n")
    ids = [d["phrase_id"] for d in json.loads(only.stdout)["detections"]]
    assert ids == ["dm_not_urgent"]
