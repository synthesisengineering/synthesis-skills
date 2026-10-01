"""Cross-field source contracts, bounded diagnostics and retained negative cases."""

from pathlib import Path
import hashlib
import json
import sys
import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_contract as rc
import protocol_acceptance as pa
from test_review_contract import bundle

SKILL = Path(__file__).resolve().parents[1]


def test_mandatory_domain_reference_cannot_be_omitted():
    text = (SKILL / "SKILL.md").read_text()
    assert not pa.review_errors(text)
    assert pa.review_errors(
        text.replace("references/domain-review-contract.md", "missing.md")
    )


def test_total_actual_reads_bounded(tmp_path, monkeypatch):
    b = bundle(tmp_path)
    monkeypatch.setattr(rc, "MAX_TOTAL_BYTES", 8)
    with pytest.raises(rc.ReviewContractError, match="budget"):
        rc.validate(b, tmp_path)


def test_unchanged_source_cannot_mask_evidence_drift(tmp_path, monkeypatch):
    b = bundle(tmp_path)
    proof = tmp_path / "proof.txt"
    proof.write_text("first")
    b["evidence"][0]["files"] = [
        {"path": "proof.txt", "sha256": hashlib.sha256(proof.read_bytes()).hexdigest()}
    ]
    original = rc._files
    calls = []

    def changing(root, rows, **kw):
        result = original(root, rows, **kw)
        calls.append(rows)
        if len(calls) == 2:
            proof.write_text("second")
        return result

    monkeypatch.setattr(rc, "_files", changing)
    with pytest.raises(rc.ReviewContractError, match="source bytes"):
        rc.validate(b, tmp_path)


def test_all_seven_schemas_match_real_records_and_reject_unknown_fields(tmp_path):
    b = bundle(tmp_path)
    b["findings"] = [
        {
            "id": "finding-one",
            "target": "target-one",
            "ledger_id": "existing-ledger-row",
            "plane": b["target"]["planes"][0],
            "evidence": ["ev-one"],
        }
    ]
    b["decisions"] = [
        {
            "id": "decision-one",
            "target": "target-one",
            "target_digest": rc.target_digest(b["target"]),
            "owner_receipt": "receipt.txt",
            "action": "review",
            "approver": "principal",
            "evidence": ["ev-one"],
        }
    ]
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
    assert rc.validate(b, tmp_path)["authority"] == "none"
    for name, key in [
        ("target", "target"),
        ("claim", "claims"),
        ("finding", "findings"),
        ("evidence", "evidence"),
        ("decision", "decisions"),
        ("handoff", "handoffs"),
        ("terminal-result", "terminal_results"),
    ]:
        schema = json.loads(
            (SKILL / "references/schemas" / f"{name}.schema.json").read_text()
        )
        validator = Draft202012Validator(schema)
        record = b[key] if name == "target" else b[key][0]
        assert not list(validator.iter_errors(record))
        assert list(validator.iter_errors({**record, "forged_authority": True}))
    # A schema is only shape validation; it cannot certify bytes or authority.
    b["evidence"][0]["files"][0]["sha256"] = "f" * 64
    with pytest.raises(rc.ReviewContractError):
        rc.validate(b, tmp_path)


def test_headline_change_reopens_unpublished_url_identity(tmp_path):
    b = bundle(tmp_path, "editorial")
    b["decisions"] = [
        {
            "id": "review-one",
            "target": "target-one",
            "target_digest": rc.target_digest(b["target"]),
            "owner_receipt": "existing-owner",
            "action": "review",
            "approver": "principal",
            "evidence": ["ev-one"],
        }
    ]
    assert rc.validate(b, tmp_path)
    (tmp_path / "artifact.txt").write_text("New title and unpublished URL identity")
    digest = hashlib.sha256((tmp_path / "artifact.txt").read_bytes()).hexdigest()
    b["target"]["files"][0]["sha256"] = digest
    b["evidence"][0]["files"][0]["sha256"] = digest
    with pytest.raises(rc.ReviewContractError, match="another target snapshot"):
        rc.validate(b, tmp_path)
