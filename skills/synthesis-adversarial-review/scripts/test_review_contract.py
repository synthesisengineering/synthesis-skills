from pathlib import Path
import sys
import copy
import hashlib
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-adversarial-review/scripts"))
import review_contract as rc  # noqa: E402 - source-bound import follows path/bootstrap initialization


def bundle(tmp_path, domain="code/control"):
    p = tmp_path / "artifact.txt"
    p.write_text("synthetic source\n")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    planes = list(rc.PROFILES[domain])
    return {
        "schema": 1,
        "target": {
            "id": "target-one",
            "domain": domain,
            "principal_objective": "Deliver the synthetic behavior",
            "files": [{"path": "artifact.txt", "sha256": sha}],
            "planes": planes,
        },
        "claims": [
            {
                "id": "claim-one",
                "target": "target-one",
                "plane": planes[0],
                "text": "Synthetic measured claim",
                "evidence": ["ev-one"],
            }
        ],
        "findings": [],
        "evidence": [
            {
                "id": "ev-one",
                "target": "target-one",
                "kind": "synthetic",
                "producer": "executor",
                "method": "independent-derivation",
                "files": [{"path": "artifact.txt", "sha256": sha}],
                "scope": "synthetic source",
            }
        ],
        "decisions": [],
        "handoffs": [],
        "terminal_results": [
            {
                "id": "coverage-" + str(i),
                "target": "target-one",
                "destination": "artifact.txt",
                "artifact": "artifact.txt",
                "plane": plane,
                "phase": "control",
                "status": "unverified",
                "evidence": ["ev-one"],
                "approval": None,
            }
            for i, plane in enumerate(planes)
        ],
    }


@pytest.mark.parametrize("domain", list(rc.PROFILES))
def test_exact_complete_profile(tmp_path, domain):
    b = bundle(tmp_path, domain)
    assert rc.validate(b, tmp_path)["domain"] == domain


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b["claims"].append(copy.deepcopy(b["claims"][0])),
        lambda b: b["evidence"][0].update(id="target-one"),
        lambda b: b["target"]["planes"].pop(),
        lambda b: b["claims"][0].update(evidence=["missing"]),
        lambda b: b["claims"][0].update(target="other"),
        lambda b: b["evidence"][0].update(kind="native", method="fixture"),
        lambda b: b["target"]["files"].append(copy.deepcopy(b["target"]["files"][0])),
    ],
)
def test_universe_or_authority_corruption_refuses(tmp_path, change):
    b = bundle(tmp_path)
    change(b)
    with pytest.raises(rc.ReviewContractError):
        rc.validate(b, tmp_path)


def test_handoff_refuses_source_drift_and_inherited_independence(tmp_path):
    b = bundle(tmp_path)
    b["handoffs"] = [
        {
            "id": "handoff-one",
            "target": "target-one",
            "target_digest": rc.target_digest(b["target"]),
            "reviewer": "reviewer",
            "evidence": ["ev-one"],
            "links": ["artifact.txt"],
        }
    ]
    assert rc.validate(b, tmp_path)
    b["evidence"][0]["method"] = "copied-receipt"
    with pytest.raises(rc.ReviewContractError):
        rc.validate(b, tmp_path)
    b["evidence"][0]["method"] = "independent-derivation"
    (tmp_path / "artifact.txt").write_text("changed")
    with pytest.raises(rc.ReviewContractError):
        rc.validate(b, tmp_path)


def test_terminal_cannot_infer_publication_or_hide_another_destination(tmp_path):
    b = bundle(tmp_path)
    b["terminal_results"] = [
        {
            "id": "terminal-one",
            "target": "target-one",
            "destination": "synthetic-site",
            "artifact": "artifact.txt",
            "plane": "release",
            "phase": "publication",
            "status": "verified",
            "evidence": ["ev-one"],
            "approval": None,
        }
    ]
    with pytest.raises(rc.ReviewContractError):
        rc.validate(b, tmp_path)


def test_inventory_requires_js_c_python_and_noncanonical_test_names(tmp_path):
    for name in [
        "engine.py",
        "blast_radius_validator_test.js",
        "native.c",
        "round28.mjs",
    ]:
        (tmp_path / name).write_text("synthetic")
    with pytest.raises(rc.ReviewContractError):
        rc.instrument_inventory(tmp_path, [])
    declared = [
        {
            "path": p.name,
            "role": "validator",
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "terminal": "passed",
        }
        for p in sorted(tmp_path.iterdir())
    ]
    assert len(rc.instrument_inventory(tmp_path, declared)) == 4
    declared.pop()
    with pytest.raises(rc.ReviewContractError):
        rc.instrument_inventory(tmp_path, declared)


def test_four_content_planes_are_independent():
    assert "scaffold" in rc.content_checks(
        source="TODO: promise proof later",
        rendered="clean",
        required=["proof"],
        attributions=[],
        named_entities=[],
        ledger_entities=[],
    )
    assert "required-content" in rc.content_checks(
        source="clean",
        rendered="clean",
        required=["proof"],
        attributions=[],
        named_entities=[],
        ledger_entities=[],
    )
    assert "attribution-directive" in rc.content_checks(
        source="clean",
        rendered="clean",
        required=[],
        attributions=[{"claim": "X approved", "directive": None}],
        named_entities=[],
        ledger_entities=[],
    )
    assert "entity-presence" in rc.content_checks(
        source="clean",
        rendered="clean",
        required=[],
        attributions=[],
        named_entities=["Absent Person"],
        ledger_entities=["Absent Person"],
    )
    assert (
        rc.content_checks(
            source="Evidence found",
            rendered="Evidence found",
            required=["Evidence"],
            attributions=[{"claim": "Evidence found", "directive": "directive-sha"}],
            named_entities=[],
            ledger_entities=[],
        )
        == []
    )


def test_measured_scorecard_never_invents_missing_values():
    measured = rc.scorecard(
        [
            {
                "principal_sittings": 1,
                "rereads": 3,
                "duplicate_work": 0,
                "elapsed_target_seconds": 10,
                "severity_found": {"high": 1},
                "repair_defects": 0,
                "omitted_planes": 0,
            }
        ]
    )
    assert measured["principal_sittings"] == 1 and measured["known_trials"] == 1
    with pytest.raises(rc.ReviewContractError):
        rc.scorecard([{"principal_sittings": -1}])
    assert rc.scorecard([])["principal_sittings"] is None


def test_missing_plane_cannot_hide_behind_complete_source(tmp_path):
    b = bundle(tmp_path)
    b["terminal_results"].pop()
    with pytest.raises(rc.ReviewContractError, match="coverage"):
        rc.validate(b, tmp_path)


def test_duplicate_terminal_identity_refuses(tmp_path):
    b = bundle(tmp_path)
    b["terminal_results"].append(copy.deepcopy(b["terminal_results"][0]))
    with pytest.raises(rc.ReviewContractError):
        rc.validate(b, tmp_path)
