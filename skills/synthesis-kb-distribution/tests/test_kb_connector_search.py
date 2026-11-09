"""Ranking over the fixture tree: fields weighted, words folded, phrases favored, snippets from the body."""

from kb_connector.corpus import Corpus, Document
from kb_connector.search import Index, query_terms, snippet, stem, tokens


def index(published):
    return Index(Corpus.load(published).documents.values())


def ids(hits):
    return [hit.id for hit in hits]


def test_a_title_match_ranks_first(published):
    assert ids(index(published).search("pricing"))[0] == "datasets/active/pricing-decision.md"
    assert ids(index(published).search("glossary"))[0] == "datasets/reference/glossary.md"
    assert ids(index(published).search("roadmap 2027"))[0] == "datasets/active/roadmap.md"


def test_words_fold_so_forms_of_a_word_match(published):
    for word in ("price", "prices", "priced", "pricing"):
        assert ids(index(published).search(word))[0] == "datasets/active/pricing-decision.md", word
    assert {stem(w) for w in ("price", "prices", "priced", "pricing")} == {"pric"}
    assert stem("policies") == stem("policy") and stem("matches") == stem("match")
    assert stem("business") == "business" and stem("status") == "status"


def test_body_only_terms_still_find_their_document(published):
    hits = index(published).search("reminders text message")
    assert ids(hits)[0] == "datasets/active/roadmap.md"
    assert "reminders by text message" in hits[0].snippet


def test_a_phrase_outranks_the_same_words_apart(tmp_path):
    together = Document("together.md", "Notes", "", "The seat price changes next year.")
    apart = Document("apart.md", "Notes", "", "The price of a chair and the seat of a car.")
    hits = Index([together, apart]).search("seat price")
    assert ids(hits) == ["together.md", "apart.md"] and hits[0].score > hits[1].score


def test_no_match_no_results_and_stop_words_alone_still_search(published):
    assert index(published).search("zebra") == []
    assert index(published).search("") == []
    assert query_terms("the and of") == ["the", "and", "of"]
    assert tokens("The Seat-price, renewal!") == ["seat", "pric", "renewal"]


def test_results_are_limited_and_ordered_the_same_way_every_time(published):
    first = index(published).search("clinic", limit=2)
    assert len(first) == 2 and first == index(published).search("clinic", limit=2)
    assert all(a.score >= b.score for a, b in zip(first, first[1:]))


def test_snippets_skip_the_stamp_and_are_cut_around_the_match():
    body = "> Published from `source/x.md` in r at commit `abc1234` (2026-11-01).\n\n# Heading\n\n" + \
           ("filler " * 60) + "the renewal date is in March " + ("filler " * 60)
    text = snippet(body, ["renewal"])
    assert "renewal" in text and "Published from" not in text
    assert len(text) <= 242 and text.startswith("…") and text.endswith("…")
    assert snippet("> Published from `a` in b at commit `abc1234` (x).\n", ["zzz"], "the description") == \
        "the description"
