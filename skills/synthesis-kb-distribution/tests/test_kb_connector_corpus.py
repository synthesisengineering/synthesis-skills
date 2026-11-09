"""The published tree read as documents: ids, titles, front matter and the provenance stamp."""

import pytest

from kb_connector.corpus import Corpus, CorpusError, find_references, split_front_matter

IDS = ["datasets/active/pricing-decision.md", "datasets/active/roadmap.md",
       "datasets/reference/company.md", "datasets/reference/glossary.md"]


def test_every_published_file_is_a_document_and_hidden_folders_are_not(published):
    corpus = Corpus.load(published)
    assert sorted(corpus.documents) == IDS
    assert corpus.get(".drafts/unpublished.md") is None


def test_front_matter_fields_title_description_and_provenance(published):
    doc = Corpus.load(published).get("datasets/active/pricing-decision.md")
    assert doc.title == "Pricing decision for 2027"
    assert doc.description == "The decision to move clinic plans to per-seat pricing in 2027."
    assert doc.fields["tags"] == ["pricing", "decision"]
    assert doc.fields["owners"] == {"lead": "Finance", "reviewer": "Product"}
    assert doc.fields["timestamp"] == "2026-10-12"  # dates stay text
    assert doc.provenance == {
        "stamp": "> Published from `source/datasets/active/pricing-decision.md` in example/knowledge-base at commit "
                 "`abc1234` (2026-11-01).",
        "source_path": "source/datasets/active/pricing-decision.md", "source_repo": "example/knowledge-base",
        "commit": "abc1234", "published": "2026-11-01"}
    assert doc.body.startswith("> Published from") and "---" not in doc.body.splitlines()[0]


def test_title_falls_back_to_the_heading_then_the_file_name(published, references):
    (references / "notes.md").write_text("# Meeting notes\n\nText.\n", encoding="utf-8")
    (references / "plain-name.md").write_text("Just text.\n", encoding="utf-8")
    corpus = Corpus.load(published)
    assert corpus.get("notes.md").title == "Meeting notes" and corpus.get("notes.md").fields == {}
    assert corpus.get("plain-name.md").title == "plain name"
    assert corpus.get("notes.md").provenance == {}


def test_front_matter_the_reader_cannot_read_is_served_without_fields(published, references, caplog):
    (references / "odd.md").write_text("---\ntitle: &anchor Odd\n---\n\n# Odd file\n", encoding="utf-8")
    doc = Corpus.load(published).get("odd.md")
    assert doc.fields == {} and doc.title == "Odd file"
    assert "front matter of odd.md not read" in caplog.text


def test_split_front_matter_needs_a_closing_line_of_its_own():
    assert split_front_matter("---\ntype: A\n---\nbody\n") == ("type: A\n", "body\n")
    assert split_front_matter("---\n---\nbody") == ("", "body")
    assert split_front_matter("---\ntype: A\n---more\n") == ("", "---\ntype: A\n---more\n")
    assert split_front_matter("no front matter") == ("", "no front matter")


def test_the_references_folder_must_be_one_and_inside_the_tree(published, references, tmp_path):
    assert find_references(published) == references.resolve()
    assert find_references(published, str(references.relative_to(published))) == references.resolve()
    with pytest.raises(CorpusError, match="leaves the published tree"):
        find_references(published, "../")
    with pytest.raises(CorpusError, match="not a folder"):
        find_references(published, "plugins/missing")
    (published / "plugins/second/skills/second/references").mkdir(parents=True)
    with pytest.raises(CorpusError, match="expected one"):
        find_references(published)
    empty = tmp_path / "empty"
    (empty / "plugins/x/skills/x/references").mkdir(parents=True)
    with pytest.raises(CorpusError, match="no markdown files"):
        Corpus.load(empty)


def test_links_are_never_followed_out_of_the_references_folder(published, references, tmp_path):
    secret = tmp_path / "deploy_key"
    secret.write_text("secret material\n", encoding="utf-8")
    (references / "leak.md").symlink_to(secret)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "elsewhere.md").write_text("# Elsewhere\n", encoding="utf-8")
    (references / "linked").symlink_to(outside, target_is_directory=True)
    corpus = Corpus.load(published)
    assert corpus.get("leak.md") is None and corpus.get("linked/elsewhere.md") is None
    assert not [doc for doc in corpus.documents.values() if "secret material" in doc.body]
