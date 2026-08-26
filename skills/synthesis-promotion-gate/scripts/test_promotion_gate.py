from __future__ import annotations

import json
import hashlib
import pathlib
import subprocess
import sys
from typing import Any

import yaml


SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = pathlib.Path(__file__).with_name("promotion_gate.py")
DESTINATION_FIXTURES = SKILL_ROOT / "fixtures/destination-representations.yaml"

START = "<!-- SYNTHESIS:PUBLISHABLE:START -->"
END = "<!-- SYNTHESIS:PUBLISHABLE:END -->"


def write_yaml(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def source_text(slug: str, body: str, *, outside: str = "") -> str:
    return (
        "---\n"
        f'title: "Fixture {slug}"\n'
        f'slug: "{slug}"\n'
        'date: "2026-08-26"\n'
        "---\n\n"
        f"{outside}\n{START}\n{body}\n{END}\n"
    )


def marker_policy() -> dict[str, Any]:
    return {
        "schema": 1,
        "markers": [
            {
                "id": "private-original-opener",
                "threat_rationale": "A rejected private opener survived in page source.",
                "provenance": "engagement-round-2-sensitive-html-comment",
                "positive_examples": ["ORIGINAL OPENER private holdings"],
                "negative_examples": ["An ordinary public introduction."],
                "projections": {
                    "html-comments": {"pattern": r"original\s+opener.*private\s+holdings"},
                    "raw-page-source": {"pattern": r"original\s+opener.*private\s+holdings"},
                },
            },
            {
                "id": "unresolved-date",
                "threat_rationale": "A publication date placeholder rendered to a reader surface.",
                "provenance": "engagement-round-2-two-date-blocks",
                "positive_examples": ["<DATE>", "&lt;DATE&gt;"],
                "negative_examples": ["2026-08-26"],
                "projections": {
                    "publishable-source": {"pattern": r"<\s*date\s*>"},
                    "dom-text": {"pattern": r"<\s*date\s*>"},
                    "raw-page-source": {"pattern": r"&lt;\s*date\s*&gt;"},
                },
            },
            {
                "id": "publication-notes",
                "threat_rationale": "Internal publication notes rendered as a reader-facing section.",
                "provenance": "engagement-round-2-two-publication-notes-sections",
                "positive_examples": ["Publication Notes"],
                "negative_examples": ["I keep publication notes beside a draft."],
                "projections": {
                    "dom-heading-text": {"pattern": r"^\s*publication\s+notes\s*$"},
                },
            },
            {
                "id": "unresolved-sidecar",
                "threat_rationale": "An unresolved sidecar attestation cannot authorize promotion.",
                "provenance": "engagement-sidecar-flags",
                "positive_examples": ["status: unresolved"],
                "negative_examples": ["status: resolved"],
                "projections": {
                    "sidecar-flags": {"pattern": r"status\s*:\s*unresolved"},
                },
            },
        ],
    }


BUILD_SCRIPT = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

output_root = pathlib.Path(sys.argv[1])
spec = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
for relative, html in spec["outputs"].items():
    target = output_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
if spec.get("mutate_path"):
    target = pathlib.Path(spec["mutate_path"])
    target.write_text(target.read_text(encoding="utf-8") + "\nchanged during build\n", encoding="utf-8")
'''


PROMOTE_SCRIPT = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

candidate = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
output_root = pathlib.Path(sys.argv[2])
sentinel = pathlib.Path(sys.argv[3])
if candidate.get("status") != "pass" or not list(output_root.rglob("*.html")):
    raise SystemExit(9)
sentinel.write_text("promoted", encoding="utf-8")
'''


FIXTURE_PROJECTION_SCRIPT = r'''#!/usr/bin/env python3
import json
import pathlib
import sys

corpus = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
request = json.load(sys.stdin)
by_html = {case["html"]: case["representations"] for case in corpus["cases"]}
documents = []
for document in request.get("documents", []):
    html = document.get("html")
    if html not in by_html:
        print("captured HTML is absent from the closed renderer-derived fixture corpus", file=sys.stderr)
        raise SystemExit(7)
    documents.append({"route": document["route"], "representations": by_html[html]})
sys.stdout.write(json.dumps({
    "schema": 1,
    "identity": corpus["identity"],
    "documents": documents,
}, sort_keys=True))
'''


def destination_fixture_corpus() -> dict[str, Any]:
    return yaml.safe_load(DESTINATION_FIXTURES.read_text(encoding="utf-8"))


def representation_digest(values: list[str]) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_project(
    root: pathlib.Path,
    *,
    articles: list[dict[str, str]],
    outputs: dict[str, str],
    sidecar: str | None = None,
    mutate_source: str | None = None,
    representations: list[str] | None = None,
) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    for article in articles:
        path = root / "drafts" / article["directory"] / "index.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            source_text(
                article["slug"],
                article.get("body", "Public body."),
                outside=article.get("outside", ""),
            ),
            encoding="utf-8",
        )

    (root / "fixture_build.py").write_text(BUILD_SCRIPT, encoding="utf-8")
    (root / "fixture_promote.py").write_text(PROMOTE_SCRIPT, encoding="utf-8")
    (root / "fixture_projection.py").write_text(
        FIXTURE_PROJECTION_SCRIPT, encoding="utf-8"
    )
    corpus = destination_fixture_corpus()
    (root / "destination-fixtures.json").write_text(
        json.dumps(corpus, sort_keys=True), encoding="utf-8"
    )
    build_spec: dict[str, Any] = {"outputs": outputs}
    if mutate_source:
        build_spec["mutate_path"] = str(root / mutate_source)
    (root / "build-map.json").write_text(
        json.dumps(build_spec, sort_keys=True), encoding="utf-8"
    )

    write_yaml(root / "marker-policy.yaml", marker_policy())
    write_yaml(
        root / "surface-manifest.yaml",
        {
            "schema": 1,
            "renderers": [
                {
                    "id": "fixture-html",
                    "version": "fixture-renderer-1",
                    "input_globs": ["drafts/**/index.md"],
                    "route_template": "articles/{slug}/index.html",
                    "output_prefix": "",
                }
            ],
        },
    )
    write_yaml(
        root / "acceptance.yaml",
        {
            "schema": 1,
            "suite": "fixture-promotion-gate",
            "membership": "closed",
            "production_entry_point": "promotion_gate.py enforce",
            "enforcing_boundary": "before the fixture promotion command",
            "receipt_consumer": "fixture promotion command",
            "expected_status": "pass",
            "unverified_remainder": "destination bytes after the fixture command returns",
            "cases": [
                {
                    "id": "fixture",
                    "control_class": "enforced-gate",
                    "fixture": "test_promotion_gate.py::fixture",
                    "motivating_defect": "fixture-boundary",
                }
            ],
        },
    )
    if sidecar is not None:
        path = root / "sidecars" / "attestation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sidecar, encoding="utf-8")

    reps = representations or [
        "publishable-source",
        "dom-text",
        "dom-heading-text",
        "html-comments",
        "raw-page-source",
    ]
    write_yaml(
        root / ".agents" / "promotion-gate.yaml",
        {
            "schema": 1,
            "build": {
                "command": [
                    sys.executable,
                    "fixture_build.py",
                    "{output_root}",
                    "build-map.json",
                ],
                "working_directory": ".",
                "output_root": "dist",
            },
            "inputs": {"root": "drafts", "globs": ["**/index.md"]},
            "destination_projection": {
                "command": [
                    sys.executable,
                    "fixture_projection.py",
                    "destination-fixtures.json",
                ],
                "working_directory": ".",
                "expected_identity": corpus["identity"],
            },
            "publishable_range": {"start": START, "end": END, "required": True},
            "marker_policy": "marker-policy.yaml",
            "surface_manifest": "surface-manifest.yaml",
            "acceptance_suite": "acceptance.yaml",
            "inspected_surfaces": [
                {"renderer": "fixture-html", "representations": reps}
            ],
            "sidecar_flag_globs": ["sidecars/**/*.yaml"],
            "additional_unverified_remainder": [
                "repository-specific consumers not yet declared by this fixture"
            ],
        },
    )
    return root / ".agents" / "promotion-gate.yaml"


def run_gate(
    config: pathlib.Path,
    *,
    mode: str = "check",
    promotion_command: list[str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], pathlib.Path]:
    receipt = config.parent.parent / f"{mode}-receipt.json"
    command = [
        sys.executable,
        str(SCRIPT),
        mode,
        "--config",
        str(config),
        "--receipt",
        str(receipt),
    ]
    if promotion_command:
        command.extend(["--", *promotion_command])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result, receipt


def read_receipt(path: pathlib.Path) -> dict[str, Any]:
    assert path.is_file(), f"receipt missing: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_successful_build_refuses_all_five_round2_rendered_defects(
    tmp_path: pathlib.Path,
) -> None:
    articles = [
        {"directory": "leak", "slug": "leak"},
        {"directory": "date-a", "slug": "date-a"},
        {"directory": "date-b", "slug": "date-b"},
        {"directory": "notes-a", "slug": "notes-a"},
        {"directory": "notes-b", "slug": "notes-b"},
    ]
    outputs = {
        "articles/leak/index.html": "<!-- ORIGINAL OPENER: private holdings REDACTED --><p>Public.</p>",
        "articles/date-a/index.html": "<p>&lt;DATE&gt;</p>",
        "articles/date-b/index.html": "<p>&lt;DATE&gt;</p>",
        "articles/notes-a/index.html": "<h2>Publication Notes</h2>",
        "articles/notes-b/index.html": "<h2>Publication Notes</h2>",
    }
    config = make_project(tmp_path / "project", articles=articles, outputs=outputs)

    result, receipt_path = run_gate(config)

    assert result.returncode == 1, result.stdout + result.stderr
    receipt = read_receipt(receipt_path)
    assert receipt["build"]["exit_code"] == 0
    assert receipt["status"] == "refused"
    assert receipt["authority_receipt"] is False
    dirty_routes = {
        finding["route"] for finding in receipt["findings"] if finding.get("route")
    }
    assert dirty_routes == set(outputs)
    assert {"private-original-opener", "unresolved-date", "publication-notes"} <= {
        finding.get("marker_id") for finding in receipt["findings"]
    }


def test_sensitive_html_comment_is_inspected_as_comment_and_raw_source(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[{"directory": "leak", "slug": "leak"}],
        outputs={
            "articles/leak/index.html": "<!-- ORIGINAL OPENER private holdings REDACTED --><p>Clean.</p>"
        },
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    representations = {
        f["representation"]
        for f in receipt["findings"]
        if f.get("marker_id") == "private-original-opener"
    }
    assert representations == {"html-comments", "raw-page-source"}


def test_dom_heading_preserves_tag_adjacency_instead_of_inventing_spaces(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[{"directory": "adjacency", "slug": "adjacency"}],
        outputs={
            "articles/adjacency/index.html": "<h2>Public<a href='/x'>ation</a> Notes</h2>"
        },
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(
        f.get("marker_id") == "publication-notes"
        and f.get("representation") == "dom-heading-text"
        for f in receipt["findings"]
    )


def test_route_bijection_uses_frontmatter_slug_not_source_directory(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[{"directory": "wrong-directory", "slug": "actual-route"}],
        outputs={"articles/wrong-directory/index.html": "<p>Clean.</p>"},
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(
        f["kind"] == "missing-rendered-output"
        and f["route"] == "articles/actual-route/index.html"
        for f in receipt["findings"]
    )


def test_every_staged_input_must_have_an_inspected_output(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[
            {"directory": "seen", "slug": "seen"},
            {"directory": "never-inspected", "slug": "never-inspected"},
        ],
        outputs={"articles/seen/index.html": "<p>Clean.</p>"},
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    expected = receipt["route_bijection"]["expected"]
    assert len(expected) == 2
    assert any(f["route"].endswith("never-inspected/index.html") for f in receipt["findings"])


def test_publishable_range_excludes_internal_draft_material_but_binds_both_hashes(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[
            {
                "directory": "clean",
                "slug": "clean",
                "outside": "<!-- ORIGINAL OPENER private holdings REDACTED -->",
            }
        ],
        outputs={"articles/clean/index.html": "<h1>Clean public page</h1>"},
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = read_receipt(receipt_path)
    assert receipt["status"] == "pass"
    assert receipt["metadata_class"] == "acceptance-test"
    assert receipt["authority_receipt"] is False
    identity = receipt["inputs"][0]
    assert identity["source_sha256"] != identity["publishable_sha256"]
    assert receipt["unverified_remainder"]


def test_unresolved_sidecar_flag_refuses_promotion_even_when_rendered_page_is_clean(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
        sidecar="status: unresolved\n",
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(
        f.get("marker_id") == "unresolved-sidecar"
        and f.get("representation") == "sidecar-flags"
        for f in receipt["findings"]
    )


def test_dirty_enforced_gate_never_invokes_the_promotion_command(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "dirty", "slug": "dirty"}],
        outputs={"articles/dirty/index.html": "<h2>Publication Notes</h2>"},
    )
    sentinel = root / "promoted.txt"
    command = [
        sys.executable,
        "fixture_promote.py",
        "{candidate_receipt}",
        "{output_root}",
        str(sentinel),
    ]
    result, receipt_path = run_gate(config, mode="enforce", promotion_command=command)
    assert result.returncode == 1
    assert not sentinel.exists()
    assert read_receipt(receipt_path)["authority_receipt"] is False


def test_clean_enforced_gate_revalidates_receipt_then_invokes_the_consumer(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    sentinel = root / "promoted.txt"
    command = [
        sys.executable,
        "fixture_promote.py",
        "{candidate_receipt}",
        "{output_root}",
        str(sentinel),
    ]
    result, receipt_path = run_gate(config, mode="enforce", promotion_command=command)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sentinel.read_text(encoding="utf-8") == "promoted"
    receipt = read_receipt(receipt_path)
    assert receipt["status"] == "pass"
    assert receipt["metadata_class"] == "enforced-gate"
    assert receipt["authority_receipt"] is True
    assert receipt["topology"] == {
        "production_entry_point": "promotion_gate.py enforce",
        "enforcing_boundary": "before the supplied promotion command",
        "receipt_consumer": "built-in candidate revalidation plus supplied command",
    }
    assert receipt["promotion"]["exit_code"] == 0


def test_input_changed_during_build_refuses_before_the_promotion_command(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    relative = "drafts/race/index.md"
    config = make_project(
        root,
        articles=[{"directory": "race", "slug": "race"}],
        outputs={"articles/race/index.html": "<p>Clean.</p>"},
        mutate_source=relative,
    )
    sentinel = root / "promoted.txt"
    command = [
        sys.executable,
        "fixture_promote.py",
        "{candidate_receipt}",
        "{output_root}",
        str(sentinel),
    ]
    result, receipt_path = run_gate(config, mode="enforce", promotion_command=command)
    assert result.returncode == 1
    assert not sentinel.exists()
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] == "input-changed-during-build" for f in receipt["findings"])


def test_surface_manifest_and_inspection_config_must_name_the_same_renderers(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    doc = yaml.safe_load(config.read_text(encoding="utf-8"))
    doc["inspected_surfaces"][0]["renderer"] = "undeclared-renderer"
    write_yaml(config, doc)
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] == "surface-manifest-mismatch" for f in receipt["findings"])


def test_symlinked_config_is_refused_without_following_it(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    linked_config = config.with_name("linked-promotion-gate.yaml")
    linked_config.symlink_to(config.name)
    result, receipt_path = run_gate(linked_config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] in {"symlink-path", "unreadable-config"} for f in receipt["findings"])


def test_symlinked_rendered_output_is_refused_instead_of_inspecting_outside_bytes(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={},
    )
    outside = tmp_path / "outside.html"
    outside.write_text("<p>Clean.</p>", encoding="utf-8")
    (root / "fixture_build.py").write_text(
        "import pathlib, sys\n"
        "target = pathlib.Path(sys.argv[1]) / 'articles/clean/index.html'\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        f"target.symlink_to({str(outside)!r})\n",
        encoding="utf-8",
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] == "symlink-path" for f in receipt["findings"])


def test_unscoped_output_refuses_before_the_whole_root_reaches_promotion(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={
            "articles/clean/index.html": "<p>Clean.</p>",
            "unscoped/internal/index.html": "<h2>Publication Notes</h2>",
        },
    )
    sentinel = root / "promoted.txt"
    command = [
        sys.executable,
        "fixture_promote.py",
        "{candidate_receipt}",
        "{output_root}",
        str(sentinel),
    ]
    result, receipt_path = run_gate(config, mode="enforce", promotion_command=command)
    assert result.returncode == 1
    assert not sentinel.exists()
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] == "unscoped-rendered-output" for f in receipt["findings"])


def test_promotion_consumes_a_captured_snapshot_not_a_build_childs_later_mutation(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={},
    )
    (root / "fixture_build.py").write_text(
        "import pathlib, subprocess, sys\n"
        "target = pathlib.Path(sys.argv[1]) / 'articles/clean/index.html'\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        "target.write_text('<p>Clean.</p>', encoding='utf-8')\n"
        "code = \"import pathlib,time; time.sleep(0.20); pathlib.Path(%r).write_text('<h2>Publication Notes</h2>', encoding='utf-8')\" % str(target)\n"
        "subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)\n",
        encoding="utf-8",
    )
    (root / "consume_after_delay.py").write_text(
        "import json, pathlib, sys, time\n"
        "candidate = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
        "time.sleep(0.45)\n"
        "source = pathlib.Path(sys.argv[2]) / 'articles/clean/index.html'\n"
        "pathlib.Path(sys.argv[3]).write_text(source.read_text(encoding='utf-8'), encoding='utf-8')\n",
        encoding="utf-8",
    )
    consumed = root / "consumed.html"
    command = [
        sys.executable,
        "consume_after_delay.py",
        "{candidate_receipt}",
        "{output_root}",
        str(consumed),
    ]
    result, receipt_path = run_gate(config, mode="enforce", promotion_command=command)
    assert result.returncode == 0, result.stdout + result.stderr
    assert consumed.read_text(encoding="utf-8") == "<p>Clean.</p>"
    receipt = read_receipt(receipt_path)
    assert receipt["authority_receipt"] is True
    assert receipt["handoff"]["mode"] == "captured-content-snapshot"


def test_each_policy_projection_must_match_a_positive_and_reject_negatives(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "dirty", "slug": "dirty"}],
        outputs={"articles/dirty/index.html": "<h2>Publication Notes</h2>"},
    )
    policy_path = root / "marker-policy.yaml"
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    policy["markers"][2]["projections"]["dom-heading-text"]["pattern"] = "^NEVER_MATCH$"
    write_yaml(policy_path, policy)
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] == "invalid-marker-policy" for f in receipt["findings"])


def test_policy_projection_that_matches_a_negative_example_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "dirty", "slug": "dirty"}],
        outputs={"articles/dirty/index.html": "<h2>Publication Notes</h2>"},
    )
    policy_path = root / "marker-policy.yaml"
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    policy["markers"][2]["projections"]["dom-heading-text"]["pattern"] = "publication"
    write_yaml(policy_path, policy)
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(f["kind"] == "invalid-marker-policy" for f in receipt["findings"])


def test_malformed_heading_that_destination_repairs_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    html = "<h2>Publication Notes"
    config = make_project(
        tmp_path / "project",
        articles=[{"directory": "malformed", "slug": "malformed"}],
        outputs={"articles/malformed/index.html": html},
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(
        finding.get("marker_id") == "publication-notes"
        and finding.get("representation") == "dom-heading-text"
        for finding in receipt["findings"]
    )


def test_renderer_derived_destination_fixture_matrix_is_consumed(
    tmp_path: pathlib.Path,
) -> None:
    corpus = destination_fixture_corpus()
    required_planes = {
        "inline",
        "entity",
        "comment",
        "attribute",
        "code",
        "hidden-container",
        "malformed",
    }
    cases = {
        case["plane"]: case
        for case in corpus["cases"]
        if case["plane"] in required_planes
    }
    assert set(cases) == required_planes
    for plane, case in sorted(cases.items()):
        slug = plane.replace("-", "")
        config = make_project(
            tmp_path / plane,
            articles=[{"directory": slug, "slug": slug}],
            outputs={f"articles/{slug}/index.html": case["html"]},
        )
        _result, receipt_path = run_gate(config)
        receipt = read_receipt(receipt_path)
        assert receipt["destination_projection"]["identity"] == corpus["identity"]
        inspected = receipt["route_bijection"]["inspected"]
        assert len(inspected) == 1
        expected = {
            **case["representations"],
            "raw-page-source": [case["html"]],
        }
        assert inspected[0]["representation_sha256"] == {
            name: representation_digest(values)
            for name, values in sorted(expected.items())
        }


def test_destination_projection_identity_mismatch_refuses(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    doc = yaml.safe_load(config.read_text(encoding="utf-8"))
    doc["destination_projection"]["expected_identity"]["parser_version"] = "wrong"
    write_yaml(config, doc)
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(
        finding["kind"] == "destination-projection-identity-mismatch"
        for finding in receipt["findings"]
    )


def test_destination_projection_must_return_the_closed_route_universe(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    identity = destination_fixture_corpus()["identity"]
    (root / "fixture_projection.py").write_text(
        "import json, sys\n"
        "json.load(sys.stdin)\n"
        f"print(json.dumps({{'schema': 1, 'identity': {identity!r}, 'documents': []}}))\n",
        encoding="utf-8",
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert any(
        finding["kind"] == "destination-projection-invalid"
        for finding in receipt["findings"]
    )


def test_engine_owned_unverified_remainder_cannot_be_erased_by_config(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    doc = yaml.safe_load(config.read_text(encoding="utf-8"))
    doc["unverified_remainder"] = "none"
    write_yaml(config, doc)
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert isinstance(receipt["unverified_remainder"], dict)
    assert receipt["unverified_remainder"]["engine_owned"]
    assert any(f["kind"] == "invalid-config" for f in receipt["findings"])


def test_clean_receipt_always_carries_structured_engine_owned_remainder(
    tmp_path: pathlib.Path,
) -> None:
    config = make_project(
        tmp_path / "project",
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    result, receipt_path = run_gate(config)
    assert result.returncode == 0
    remainder = read_receipt(receipt_path)["unverified_remainder"]
    assert remainder["engine_owned"]
    assert remainder["repository_declared"]


def test_additional_remainder_cannot_claim_that_nothing_is_unverified(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    doc = yaml.safe_load(config.read_text(encoding="utf-8"))
    doc["additional_unverified_remainder"] = ["none"]
    write_yaml(config, doc)
    result, receipt_path = run_gate(config)
    assert result.returncode == 1
    receipt = read_receipt(receipt_path)
    assert receipt["unverified_remainder"]["engine_owned"]
    assert any(f["kind"] == "invalid-config" for f in receipt["findings"])


def test_shipped_acceptance_manifest_is_consumable_by_the_engine(
    tmp_path: pathlib.Path,
) -> None:
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    (root / "acceptance.yaml").write_bytes((SKILL_ROOT / "acceptance-suite.yaml").read_bytes())
    result, _receipt_path = run_gate(config)
    assert result.returncode == 0, result.stdout + result.stderr


def test_repository_acceptance_template_is_shipped_and_consumable(
    tmp_path: pathlib.Path,
) -> None:
    template = SKILL_ROOT / "templates/acceptance-suite.example.yaml"
    assert template.is_file()
    root = tmp_path / "project"
    config = make_project(
        root,
        articles=[{"directory": "clean", "slug": "clean"}],
        outputs={"articles/clean/index.html": "<p>Clean.</p>"},
    )
    (root / "acceptance.yaml").write_bytes(template.read_bytes())
    result, _receipt_path = run_gate(config)
    assert result.returncode == 0, result.stdout + result.stderr
