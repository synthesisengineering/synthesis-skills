"""Independent packet-succession regressions using only synthetic projects."""

import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for skill in (
    "synthesis-project-management",
    "synthesis-context-lifecycle",
    "synthesis-decision-packet",
):
    sys.path.insert(0, str(ROOT / "skills" / skill / "scripts"))
_examples = importlib.import_module("test_record_succession")
example, bound_example, apply, api, ref = (
    _examples.example,
    _examples.bound_example,
    _examples.apply,
    _examples.api,
    _examples.ref,
)
world = importlib.import_module("test_run_admission").world
rt = importlib.import_module("record_transaction")


@pytest.mark.parametrize(
    "spelling",
    ["resources/artifacts/./old-packet.html", "resources//artifacts/old-packet.html"],
)
def test_alias_cannot_destroy_surviving_destination(world, spelling):
    p, q = example(world)
    page = p / q["inventory"]["path"]
    original = page.read_bytes()
    q["items"][0]["destination"] = ref(p, spelling, '"label": "Inspect"')
    q["items"][0]["obligations"][0]["destination"] = ref(
        p, spelling, '"label": "Inspect"'
    )
    with pytest.raises(ValueError):
        apply(world, q)
    assert page.read_bytes() == original, (
        "failed preflight retired the actual surviving destination"
    )


@pytest.mark.parametrize(
    "attrs",
    [
        'id="other" id="spec" type="application/json"',
        'id="spec" type="text/plain" type="application/json"',
    ],
)
def test_ambiguous_html_attributes_refuse_before_retirement(world, attrs):
    p, q = example(world)
    page = p / q["inventory"]["path"]
    raw = ("<script " + attrs + '>{"rows":[{"id":"Q1"},{"id":"Q2"}]}</script>').encode()
    page.write_bytes(raw)
    q["inventory"]["sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        apply(world, q)
    assert page.read_bytes() == raw


@pytest.mark.parametrize(
    "field,value", [("schema_version", 2.0), ("decided", True), ("total", 5.0)]
)
def test_bound_record_type_substitution_cannot_erase_obligation(world, field, value):
    p, q, record = bound_example(world)
    record[field] = value
    path = p / "resources/artifacts/bound-rulings.json"
    path.write_text(json.dumps(record, indent=2))
    for item in q["items"]:
        item["decision"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    page = p / q["inventory"]["path"]
    before = page.read_bytes()
    with pytest.raises(ValueError):
        apply(world, q)
    assert page.read_bytes() == before


def test_positive_exact_packet_and_live_queue_control(world):
    p, q = example(world)
    result = apply(world, q)
    observed = api().validate_record(p, p / result["record"])
    assert observed["unresolved_obligations"] == ["O1", "O2"]
    assert observed["current_destinations"] == "exact-observed-snapshot"
    assert observed["authorization_granted"] is False


def test_live_anchor_loss_remains_failed_after_queue_rewrite(world):
    p, q = example(world)
    result = apply(world, q)
    (p / "resources/artifacts/queue.md").write_text("O1: only one survives\n")
    with pytest.raises(ValueError):
        api().validate_record(p, p / result["record"])


def test_foreign_identity_cannot_reuse_completed_request(world):
    p, q = example(world)
    apply(world, q)
    original = (p / "CONTEXT.md").read_bytes()
    from test_run_admission import write_board

    write_board(world, native="01990000-0000-7000-8000-000000000099")
    with pytest.raises((ValueError, rt.RecordTransactionError)):
        apply(world, q)
    assert (p / "CONTEXT.md").read_bytes() == original
