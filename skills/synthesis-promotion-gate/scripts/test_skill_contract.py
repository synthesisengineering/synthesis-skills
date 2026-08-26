from __future__ import annotations

import pathlib

import yaml


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]


def test_skill_distinguishes_acceptance_from_enforcement_and_names_remainder() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split()).lower()
    for phrase in (
        "A successful build is not a publication-safety signal",
        "acceptance-test",
        "enforced-gate",
        "authority_receipt: false",
        "unverified remainder",
        "does not decide whether ordinary prose is appropriate to disclose",
    ):
        assert phrase.lower() in normalized


def test_skill_names_destination_representations_and_frontmatter_routes() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for phrase in (
        "dom-text",
        "dom-heading-text",
        "html-comments",
        "raw-page-source",
        "frontmatter",
        "Directory-name substring selection is forbidden",
    ):
        assert phrase in text


def test_templates_use_one_policy_and_a_complete_renderer_mapping() -> None:
    config = yaml.safe_load(
        (SKILL_ROOT / "templates/promotion-gate.example.yaml").read_text(encoding="utf-8")
    )
    policy = yaml.safe_load(
        (SKILL_ROOT / "templates/marker-policy.example.yaml").read_text(encoding="utf-8")
    )
    surfaces = yaml.safe_load(
        (SKILL_ROOT / "templates/surface-manifest.example.yaml").read_text(encoding="utf-8")
    )
    assert config["marker_policy"] == ".agents/promotion-marker-policy.yaml"
    assert config["acceptance_suite"] == ".agents/promotion-acceptance-suite.yaml"
    assert config["additional_unverified_remainder"]
    assert config["destination_projection"]["expected_identity"] == {
        "parser": "parse5",
        "parser_version": "7.3.0",
        "renderer": "astro@5.0.0",
    }
    assert len({marker["id"] for marker in policy["markers"]}) == len(policy["markers"])
    assert {surface["renderer"] for surface in config["inspected_surfaces"]} == {
        renderer["id"] for renderer in surfaces["renderers"]
    }
    assert all("projections" in marker for marker in policy["markers"])


def test_acceptance_manifest_classifies_only_boundary_cases_as_enforced() -> None:
    manifest = yaml.safe_load((SKILL_ROOT / "acceptance-suite.yaml").read_text(encoding="utf-8"))
    enforced = {
        case["id"] for case in manifest["cases"] if case["control_class"] == "enforced-gate"
    }
    assert enforced == {
        "refusal-precedes-state-change",
        "receipt-consumer-topology",
        "changed-input-revalidation",
        "closed-output-universe",
        "captured-content-handoff",
    }


def test_all_four_repository_contract_templates_are_shipped() -> None:
    assert {
        path.name for path in (SKILL_ROOT / "templates").glob("*.example.yaml")
    } == {
        "acceptance-suite.example.yaml",
        "marker-policy.example.yaml",
        "promotion-gate.example.yaml",
        "surface-manifest.example.yaml",
    }


def test_renderer_derived_fixture_matrix_covers_round15_grammar_planes() -> None:
    corpus = yaml.safe_load(
        (SKILL_ROOT / "fixtures/destination-representations.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert corpus["identity"]["parser"] == "parse5"
    assert {
        case["plane"] for case in corpus["cases"]
    } >= {
        "inline",
        "entity",
        "comment",
        "attribute",
        "code",
        "hidden-container",
        "malformed",
    }


def test_prompt_hidden_skill_is_reachable_through_router() -> None:
    router = (REPO_ROOT / "skills/synthesis-skill-router/SKILL.md").read_text(encoding="utf-8")
    assert "../synthesis-promotion-gate/SKILL.md" in router
    adapter = yaml.safe_load((SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8"))
    assert adapter["policy"]["allow_implicit_invocation"] is False
