"""Pin receipt bytes independently of the receipt producer's future implementation."""

import hashlib
import json
from pathlib import Path

import coordination


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "receipts"


def test_relocated_live_receipt_matches_frozen_binding(monkeypatch):
    frozen = json.loads((FIXTURES / "check-staged.json").read_text())
    source = json.loads((FIXTURES / "check-staged-input.json").read_text())
    session = coordination.Session(**source["session"])
    monkeypatch.setattr(coordination, "timestamp", lambda: frozen["issued_at"])
    actual = coordination._check_staged_receipt(
        board=Path(frozen["board"]), board_text=source["board_text"],
        session=session, repository=Path(frozen["repository"]),
        branch=frozen["branch"], staged_tree=frozen["staged_tree"],
        staged_paths=frozen["staged_paths"],
        enforcement_outcome=frozen["enforcement_outcome"],
        outside_paths=frozen["outside_paths"],
    )
    assert actual == frozen
    material = {k: v for k, v in actual.items() if k != "binding_sha256"}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    assert canonical == (FIXTURES / "check-staged.canonical.json").read_bytes()
    assert hashlib.sha256(canonical).hexdigest() == frozen["binding_sha256"]


def test_canonical_scalar_and_nesting_vectors():
    vectors = json.loads((FIXTURES / "canonical-vectors.json").read_text())
    assert len(vectors) >= 5
    for vector in vectors:
        encoded = json.dumps(vector["value"], sort_keys=True, separators=(",", ":")).encode()
        assert encoded == vector["canonical"].encode(), vector["name"]
        assert hashlib.sha256(encoded).hexdigest() == vector["sha256"], vector["name"]


def test_binding_excludes_only_top_level_binding_field():
    receipt = json.loads((FIXTURES / "check-staged.json").read_text())
    material = {k: v for k, v in receipt.items() if k != "binding_sha256"}
    material["staged_paths"] = list(reversed(material["staged_paths"]))
    changed = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(changed).hexdigest() != receipt["binding_sha256"]
    material["binding_sha256"] = receipt["binding_sha256"]
    with_binding = json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(with_binding).hexdigest() != receipt["binding_sha256"]
