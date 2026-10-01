from pathlib import Path
import sys
import hashlib
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/synthesis-adversarial-review/scripts"))
import review_contract as rc  # noqa: E402 - source-bound import follows path/bootstrap initialization


def test_f01_uniform_sixty_route_failure_is_invalid_instrument():
    cases = [
        {"id": f"p{i}", "control": "positive", "expected": "pass", "observed": "fail"}
        for i in range(30)
    ] + [
        {"id": f"n{i}", "control": "negative", "expected": "fail", "observed": "fail"}
        for i in range(30)
    ]
    assert rc.calibration(cases)["status"] == "INVALID_INSTRUMENT"
    cases[0]["observed"] = "pass"
    assert rc.calibration(cases)["status"] == "INVALID_INSTRUMENT"
    for c in cases:
        c["observed"] = c["expected"]
    assert rc.calibration(cases)["status"] == "CALIBRATED_FIXTURE_ONLY"


def test_f02_deletions_and_disposable_paths_are_distinct():
    state = rc.custody_scope(
        [
            {
                "path": "retained.md",
                "kind": "durable",
                "disposition": "deleted",
                "proof": "receipt-one",
            },
            {
                "path": "scratch.tmp",
                "kind": "disposable",
                "disposition": "removed",
                "proof": None,
            },
        ]
    )
    assert state["retained_obligations"] == ["retained.md"] and state[
        "disposable_paths"
    ] == ["scratch.tmp"]


def test_f03_exact_owner_ready_does_not_clear_foreign_owners():
    out = rc.lifecycle_scopes(
        {
            "exact_session": "REMOTE_READY",
            "aggregate": "OPEN",
            "communication": "DELIVERED",
            "continuity": "LOCAL_READY",
        }
    )
    assert out["exact_session"] == "REMOTE_READY" and out["aggregate"] == "OPEN"


def test_f04_board_delivery_does_not_establish_stop_checkpoint():
    out = rc.lifecycle_scopes(
        {
            "exact_session": "UNKNOWN",
            "aggregate": "UNKNOWN",
            "communication": "DELIVERED",
            "continuity": "UNKNOWN",
        }
    )
    assert out["continuity"] == "UNKNOWN"


def test_f05_corpus_change_invalidates_four_hundred_fifty_five_route_cache():
    prior = [
        {
            "id": str(i),
            "sha256": hashlib.sha256(str(i).encode()).hexdigest(),
            "status": "unpublished",
        }
        for i in range(455)
    ]
    old = rc.corpus_key(prior)
    after = [dict(x) for x in prior]
    for x in after[:30]:
        x["status"] = "published"
    assert rc.corpus_key(after) != old


def test_f06_each_destination_keeps_its_own_publication_outcome():
    expected = [{"id": str(i), "approved_sha256": "a" * 64} for i in range(4)]
    observed = [
        {"id": str(i), "live_sha256": "a" * 64, "observed": True} for i in range(3)
    ]
    result = rc.publication_diagnostics(expected, observed)
    assert [row["status"] for row in result] == ["BYTES_MATCHED"] * 3 + ["UNVERIFIED"]


def test_f07_git_success_cannot_stand_in_for_wrong_live_bytes():
    out = rc.publication_diagnostics(
        [{"id": "article", "approved_sha256": "a" * 64}],
        [{"id": "article", "live_sha256": "b" * 64, "observed": True}],
    )
    assert (
        out[0]["status"] == "APPROVAL_TARGET_CHANGED"
        and out[0]["authorization"] == "NOT_GRANTED"
    )


def test_f08_reviewer_must_derive_the_entire_declared_universe():
    with pytest.raises(rc.ReviewContractError):
        rc.independence(
            {
                "reviewer": "r",
                "executor": "e",
                "target_sha256": "a" * 64,
                "derived_files": ["one"],
                "required_files": ["one", "two"],
                "receipt_source": "copied",
            }
        )
    assert (
        rc.independence(
            {
                "reviewer": "r",
                "executor": "e",
                "target_sha256": "a" * 64,
                "derived_files": ["one", "two"],
                "required_files": ["one", "two"],
                "receipt_source": "own-observation",
            }
        )["native_truth"]
        == "UNVERIFIED"
    )


def test_f09_destination_relative_links_must_resolve_in_the_actual_copy(tmp_path):
    (tmp_path / "prompt.md").write_text("synthetic")
    with pytest.raises(rc.ReviewContractError):
        rc.read_bytes(tmp_path, "references/evidence.json")
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "evidence.json").write_text("{}")
    assert rc.read_bytes(tmp_path, "references/evidence.json") == b"{}"


def test_f10_generated_outputs_bind_actual_saved_bytes_and_explicit_deletions(tmp_path):
    (tmp_path / "actual.py").write_text('print("synthetic")\n')
    with pytest.raises(rc.ReviewContractError):
        rc.saved_outputs(
            tmp_path, [{"path": "named-but-absent.py", "sha256": "a" * 64}], []
        )
    sha = hashlib.sha256((tmp_path / "actual.py").read_bytes()).hexdigest()
    result = rc.saved_outputs(
        tmp_path,
        [{"path": "actual.py", "sha256": sha}],
        [
            {"path": "old-a.py", "disposition": "retained-original"},
            {"path": "old-b.py", "disposition": "deleted-with-receipt"},
        ],
    )
    assert result["saved"] == ["actual.py"] and len(result["prior_dispositions"]) == 2
