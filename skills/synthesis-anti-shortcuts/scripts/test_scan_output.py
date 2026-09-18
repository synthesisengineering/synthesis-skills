"""First tests for scan_output.py: the effort_rationale category (Case 7).

Covers the new category's tight phrasings plus the quoted/discussion-mode
exemptions shared with the rest of the catalog. Older categories remain
covered by the hook fixtures in agent-control, not here.
"""

import scan_output


def _ids(text):
    catalog = scan_output.load_embedded_catalog()
    return [d.phrase_id for d in scan_output.scan(text, catalog)]


def test_fraction_of_cost_hits_bare_usage():
    ids = _ids("I recommend A over B at a fraction of the cost.")
    assert "er_fraction_of_cost" in ids


def test_fraction_of_cost_hits_case_insensitive():
    ids = _ids("At a Fraction of Their Effort, A still wins.")
    assert "er_fraction_of_cost" in ids


def test_fraction_of_cost_misses_quoted_discussion():
    ids = _ids('The catalog entry "fraction of the cost" needs examples.')
    assert "er_fraction_of_cost" not in ids


def test_cheaper_option_hits_bare_usage():
    ids = _ids("Take the cheaper option and move on.")
    assert "er_cheaper_option" in ids


def test_cheaper_option_misses_quoted_discussion():
    ids = _ids("We discussed the 'cheaper option' framing yesterday.")
    assert "er_cheaper_option" not in ids


def test_clean_recommendation_is_quiet():
    ids = _ids(
        "B is the better solution on robustness and failure modes; "
        "it costs roughly twice as much to build."
    )
    assert "er_fraction_of_cost" not in ids
    assert "er_cheaper_option" not in ids


def test_effort_rationale_category_registered():
    assert "effort_rationale" in scan_output.CATEGORIES
