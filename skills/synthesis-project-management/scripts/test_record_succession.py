"""Synthetic custody and obligation controls; no historical or native attestation."""

import hashlib
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts")
)
import context_edit
import record_transaction as rt
from test_run_admission import world as _world_fixture, write_board

world = _world_fixture


def api():
    import record_succession

    return record_succession


def ref(p, path, anchor=None):
    r = {"path": path, "sha256": hashlib.sha256((p / path).read_bytes()).hexdigest()}
    if anchor is not None:
        r["anchor"] = anchor
    return r


def example(world, kind="packet-retirement"):
    p = world["project"]
    a = p / "resources/artifacts"
    a.mkdir(parents=True)
    (p / "resources/archive/retired-decision-packets").mkdir(parents=True)
    (p / "CONTEXT.md").write_text("# Context\n\n## Next work\n\nRetained work.\n")
    (a / "queue.md").write_text(
        "# Queue\n\nO1: inspect evidence\nO2: principal review\n"
    )
    (a / "answers.md").write_text(
        "# Historical source\n\nQ1: principal chose inspect, execution still outstanding.\n"
    )
    inventory = {
        "rows": [{"id": "Q1", "label": "Inspect"}, {"id": "Q2", "label": "Review"}]
    }
    if kind == "packet-retirement":
        raw = (
            '<html>\r\n<script type="application/json" id="spec">'
            + json.dumps(inventory)
            + "</script>\r\n</html>\r\n"
        ).encode()
        name = "resources/artifacts/old-packet.html"
        (p / name).write_bytes(raw)
        fmt = "packet-html"
    else:
        name = "resources/artifacts/ideas.json"
        (p / name).write_text(json.dumps(inventory))
        fmt = "json-rows"
    request = {
        "schema": 1,
        "kind": kind,
        "inventory": dict(ref(p, name), format=fmt, declared_count=1),
        "items": [
            {
                "id": "Q1",
                "destination": ref(p, "resources/artifacts/queue.md", "O1:"),
                "decision": ref(p, "resources/artifacts/answers.md", "Q1:"),
                "proof": [],
                "obligations": [
                    {
                        "id": "O1",
                        "destination": ref(p, "resources/artifacts/queue.md", "O1:"),
                    }
                ],
            },
            {
                "id": "Q2",
                "destination": ref(p, "resources/artifacts/queue.md", "O2:"),
                "decision": None,
                "proof": [],
                "obligations": [
                    {
                        "id": "O2",
                        "destination": ref(p, "resources/artifacts/queue.md", "O2:"),
                    }
                ],
            },
        ],
        "context_anchor": "## Next work\n",
        "context_max_lines": 100,
    }
    return p, request


def apply(world, request, **kwargs):
    return api().apply(
        world["project"],
        request,
        board=world["board"],
        native_payload=world["actor"]["native_payload"],
        **kwargs,
    )


def test_exact_legacy_custody_and_unanswered_succession(world):
    p, q = example(world)
    old = (p / q["inventory"]["path"]).read_bytes()
    r = apply(world, q)
    assert r["status"] == "committed"
    receipt = json.loads((p / r["record"]).read_bytes())
    assert (p / receipt["archive"]["path"]).read_bytes() == old
    assert b"synthesis-packet-retired" in (p / q["inventory"]["path"]).read_bytes()
    assert receipt["unresolved_obligations"] == ["O1", "O2"]
    assert receipt["items"][1]["decision_status"] == "unanswered"
    assert receipt["inventory_count"] == 2 and not receipt["declared_count_matches"]
    assert (
        receipt["authorization_granted"] is False
        and receipt["completion_established"] is False
    )
    assert r["record"] in (p / "CONTEXT.md").read_text()
    assert api().validate_record(p, p / r["record"])["status"] == "committed"


def test_transfer_denominator_and_proof_are_independent(world):
    p, q = example(world, "transfer")
    r = api().review(p, q)
    assert r["identity_complete"] and r["proof_status"] == "missing"
    q["items"].pop()
    r = api().review(p, q)
    assert not r["identity_complete"] and r["missing_items"] == ["Q2"]
    with pytest.raises(ValueError, match="incomplete"):
        apply(world, q)
    assert not list((p / "resources/artifacts").glob("*-succession.json"))


@pytest.mark.parametrize(
    "bad",
    [
        "extra",
        "duplicate",
        "empty-obligation",
        "hash",
        "anchor",
        "symlink",
        "authority",
        "unknown-field",
    ],
)
def test_refusals_do_not_retire_or_drop_work(world, bad):
    p, q = example(world)
    src = p / q["inventory"]["path"]
    old = src.read_bytes()
    if bad == "extra":
        q["items"].append(dict(q["items"][0], id="Q3"))
    elif bad == "duplicate":
        q["items"].append(q["items"][0])
    elif bad == "empty-obligation":
        q["items"][1]["obligations"] = []
    elif bad == "hash":
        q["items"][0]["destination"]["sha256"] = "0" * 64
    elif bad == "anchor":
        q["items"][0]["destination"]["anchor"] = "absent"
    elif bad == "symlink":
        q["items"][0]["destination"]["path"] = "resources/artifacts/link.md"
        (p / "resources/artifacts/link.md").symlink_to("queue.md")
    elif bad == "authority":
        write_board(world, claims=str(p / "CONTEXT.md"))
    elif bad == "unknown-field":
        q["authorization_granted"] = True
    with pytest.raises((ValueError, rt.RecordTransactionError, OSError)):
        apply(world, q)
    assert src.read_bytes() == old


def test_historical_ruling_presence_does_not_close_unmarked_packet(world):
    p, q = example(world)
    a = p / "resources/artifacts"
    (a / "2000-old-packet-rulings.json").write_text("{}")
    sys.path.insert(
        0,
        str(
            Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
        ),
    )
    import skill_outputs

    assert any(
        f.severity == "defect"
        for f in skill_outputs.verify_packet(p / q["inventory"]["path"])
    )


def test_mutable_destination_does_not_destroy_historical_custody(world):
    p, q = example(world)
    r = apply(world, q)
    (p / "resources/artifacts/queue.md").write_text(
        "# Queue\n\nO1: additional review\nO2: still open\n"
    )
    got = api().validate_record(p, p / r["record"])
    assert got["current_destinations"] == "changed-requires-review"
    assert got["completion_established"] is False


def test_transfer_can_preserve_provenance_after_original_source_changes(world):
    p, q = example(world, "transfer")
    r = apply(world, q)
    (p / q["inventory"]["path"]).write_text('{"rows":[{"id":"NEW"}]}')
    got = api().validate_record(p, p / r["record"])
    assert got["inventory_ids"] == ["Q1", "Q2"]


def test_obligation_destination_disappearance_is_not_retirement_success(world):
    p, q = example(world)
    r = apply(world, q)
    (p / "resources/artifacts/queue.md").unlink()
    with pytest.raises((OSError, ValueError, rt.RecordTransactionError)):
        api().validate_record(p, p / r["record"])


def test_narrative_answer_cannot_erase_its_remaining_work(world):
    p, q = example(world)
    q["items"][0]["obligations"] = []
    with pytest.raises(ValueError, match="obligation"):
        apply(world, q)


def test_completed_application_is_idempotent_without_rereading_retired_ui(world):
    p, q = example(world)
    first = apply(world, q)
    before = (p / "CONTEXT.md").read_bytes()
    second = apply(world, q)
    assert second["changed"] is False and second["record"] == first["record"]
    assert before == (p / "CONTEXT.md").read_bytes()


@pytest.mark.parametrize("position", [0, 1, 2])
def test_each_live_commit_interruption_uses_existing_recovery(
    world, monkeypatch, position
):
    p, q = example(world)
    real = rt.os.replace
    count = 0

    def interrupted(src, dst):
        nonlocal count
        if Path(dst).name in ("old-packet.html", "CONTEXT.md") or Path(
            dst
        ).name.endswith("-succession.json"):
            if count == position:
                raise OSError("synthetic interrupted live commit")
            count += 1
        return real(src, dst)

    with monkeypatch.context() as m:
        m.setattr(rt.os, "replace", interrupted)
        with pytest.raises(OSError):
            apply(world, q)
    with pytest.raises(rt.RecordTransactionError):
        api().review(p, q)
    context_edit.recover_transaction(
        p, board=world["board"], native_payload=world["actor"]["native_payload"]
    )
    records = list((p / "resources/artifacts").glob("*-succession.json"))
    assert len(records) == 1
    assert api().validate_record(p, records[0])["status"] == "committed"


@pytest.mark.parametrize(
    "bad",
    [
        "missing",
        "modified",
        "symlink",
        "extra-member",
        "false-approval",
        "missing-pointer",
        "tombstone",
    ],
)
def test_retired_custody_tampering_refuses(world, bad):
    p, q = example(world)
    r = apply(world, q)
    record = p / r["record"]
    body = json.loads(record.read_bytes())
    archive = p / body["archive"]["path"]
    if bad == "missing":
        archive.unlink()
    elif bad == "modified":
        archive.write_text("not the original bytes")
    elif bad == "symlink":
        archive.unlink()
        archive.symlink_to(p / "resources/artifacts/queue.md")
    elif bad == "extra-member":
        body["custody"].append(dict(body["custody"][0], source_path="invented"))
    elif bad == "false-approval":
        body["authorization_granted"] = True
    elif bad == "missing-pointer":
        (p / "CONTEXT.md").write_text("# unrelated\n")
    elif bad == "tombstone":
        (p / q["inventory"]["path"]).write_text("<html>active again</html>")
    if bad in ("extra-member", "false-approval"):
        record.write_text(json.dumps(body))
    with pytest.raises((OSError, ValueError, rt.RecordTransactionError)):
        api().validate_record(p, record)


@pytest.mark.parametrize("change", ["same-bytes-new-inode", "same-length", "chmod"])
def test_preflight_source_races_preserve_live_interface(world, monkeypatch, change):
    import os

    p, q = example(world)
    page = p / q["inventory"]["path"]
    original = page.read_bytes()
    real = rt._authority
    target = p / "resources/artifacts/queue.md"

    def race(*a, **kw):
        result = real(*a, **kw)
        if change == "chmod":
            os.chmod(target, 0o600)
        elif change == "same-length":
            target.write_bytes(target.read_bytes().replace(b"inspect", b"changed"))
        else:
            copy = target.with_suffix(".new")
            copy.write_bytes(target.read_bytes())
            copy.replace(target)
        return result

    monkeypatch.setattr(rt, "_authority", race)
    with pytest.raises(ValueError, match="changed"):
        apply(world, q)
    assert page.read_bytes() == original


@pytest.mark.parametrize(
    "bad",
    [
        "bool-schema",
        "unsupported-prose",
        "duplicate-source-id",
        "duplicate-json",
        "too-many-items",
        "oversize",
        "record-bound",
        "fifo",
    ],
)
def test_bounded_input_shape_refusal(world, monkeypatch, bad):
    import os

    p, q = example(world, "transfer")
    src = p / q["inventory"]["path"]
    if bad == "bool-schema":
        q["schema"] = True
    elif bad == "unsupported-prose":
        q["inventory"]["format"] = "prose"
    elif bad == "duplicate-source-id":
        src.write_text('{"rows":[{"id":"Q1"},{"id":"Q1"}]}')
    elif bad == "duplicate-json":
        src.write_text('{"rows":[],"rows":[{"id":"Q1"}]}')
    elif bad == "too-many-items":
        q["items"] *= 257
    elif bad == "oversize":
        monkeypatch.setattr(api(), "MAX_SOURCE_BYTES", 1)
    elif bad == "record-bound":
        monkeypatch.setattr(rt, "MAX_MANIFEST_BYTES", 1)
    elif bad == "fifo":
        src.unlink()
        os.mkfifo(src)
    if bad in ("duplicate-source-id", "duplicate-json"):
        q["inventory"]["sha256"] = hashlib.sha256(src.read_bytes()).hexdigest()
    with pytest.raises((OSError, ValueError, rt.RecordTransactionError)):
        apply(world, q)
    assert not list((p / "resources/artifacts").glob("*-succession.json"))


def test_real_cli_review_apply_and_receipt(world, capsys):
    p, q = example(world, "transfer")
    request = p / "request.json"
    request.write_text(json.dumps(q))
    payload = p / "event.json"
    payload.write_text(json.dumps(world["actor"]["native_payload"]))
    assert (
        context_edit.main(
            ["review-succession", "--project", str(p), "--request", str(request)]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["identity_complete"] and not result["authorization_granted"]
    assert (
        context_edit.main(
            [
                "apply-succession",
                "--project",
                str(p),
                "--request",
                str(request),
                "--board",
                str(world["board"]),
                "--native-payload",
                str(payload),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "committed"


def test_retired_exact_spec_cannot_be_filed_again(world):
    p, q = example(world)
    r = apply(world, q)
    record = json.loads((p / r["record"]).read_bytes())
    sys.path.insert(
        0,
        str(Path(__file__).resolve().parents[2] / "synthesis-decision-packet/scripts"),
    )
    import build_packet

    with pytest.raises(ValueError, match="retired"):
        build_packet.assert_active_spec(
            p / "resources/artifacts", record["retired_spec_sha256"]
        )
    build_packet.assert_active_spec(p / "resources/artifacts", "0" * 64)


def test_source_kind_never_converts_complete_transfer_to_verified_proof(world):
    p, q = example(world, "transfer")
    q["items"][0]["proof"] = [
        {"kind": "primary", "source": ref(p, "resources/artifacts/answers.md", "Q1:")}
    ]
    result = api().review(p, q)
    assert (
        result["identity_complete"]
        and result["proof_status"] == "evidence-present-unverified"
    )
    assert (
        not result["authorization_granted"]
        and result["readiness"] == "requires-owner-review"
    )


def bound_example(world):
    p, q = example(world)
    sys.path.insert(
        0,
        str(Path(__file__).resolve().parents[2] / "synthesis-decision-packet/scripts"),
    )
    import record_rulings as rr
    from test_packet_causal import spec

    current = spec()
    raw = (
        '<script type="application/json" id="spec">'
        + json.dumps(current)
        + "</script>\n"
    ).encode()
    (p / q["inventory"]["path"]).write_bytes(raw)
    q["inventory"]["sha256"] = hashlib.sha256(raw).hexdigest()
    recorded = rr.parse_summary(
        rr.compose_summary(current, {"R-0": {"choice": "test"}}), current
    )
    answers = p / "resources/artifacts/bound-rulings.json"
    answers.write_text(json.dumps(recorded, indent=2))
    (p / "resources/artifacts/queue.md").write_text(
        "\n".join(f"O{i}: remains" for i in range(5)) + "\n"
    )
    q["items"] = []
    for i in range(5):
        q["items"].append(
            {
                "id": f"R-{i}",
                "destination": ref(p, "resources/artifacts/queue.md", f"O{i}:"),
                "decision": ref(
                    p, "resources/artifacts/bound-rulings.json", f'"id": "R-{i}"'
                ),
                "proof": [],
                "obligations": []
                if i == 0
                else [
                    {
                        "id": f"O{i}",
                        "destination": ref(p, "resources/artifacts/queue.md", f"O{i}:"),
                    }
                ],
            }
        )
    return p, q, recorded


def test_real_recorder_bound_answer_is_not_a_new_approval(world):
    p, q, _ = bound_example(world)
    r = apply(world, q)
    value = api().validate_record(p, p / r["record"])
    assert value["items"][0]["decision_status"] == "bound-answer-unverified"
    assert value["items"][1]["decision_status"] == "unanswered"
    assert value["unresolved_obligations"] == ["O1", "O2", "O3", "O4"]
    assert not value["completion_established"] and not value["authorization_granted"]


@pytest.mark.parametrize(
    "bad",
    ["stale-binding", "duplicate", "missing", "unknown-choice", "count", "unanswered"],
)
def test_invalid_bound_ruling_cannot_erase_obligations(world, bad):
    p, q, ruling = bound_example(world)
    if bad == "stale-binding":
        ruling["binding"]["spec_sha256"] = "0" * 64
    elif bad == "duplicate":
        ruling["rulings"][1] = ruling["rulings"][0]
    elif bad == "missing":
        ruling["rulings"].pop()
    elif bad == "unknown-choice":
        ruling["rulings"][0]["choice_value"] = "invented"
    elif bad == "count":
        ruling["decided"] = 99
    elif bad == "unanswered":
        q["items"][1]["obligations"] = []
    (p / "resources/artifacts/bound-rulings.json").write_text(
        json.dumps(ruling, indent=2)
    )
    for i, item in enumerate(q["items"]):
        item["decision"] = ref(
            p, "resources/artifacts/bound-rulings.json", f'"id": "R-{i}"'
        )
    with pytest.raises((OSError, ValueError, rt.RecordTransactionError)):
        apply(world, q)


def test_actual_generator_payload_defaults_cannot_bypass_retirement(world):
    p, q, _ = bound_example(world)
    import build_packet as bp
    from test_packet_causal import spec

    current = spec()
    (p / q["inventory"]["path"]).write_text(bp.build(current))
    q["inventory"]["sha256"] = hashlib.sha256(
        (p / q["inventory"]["path"]).read_bytes()
    ).hexdigest()
    # No filed original spec: preserve every item as still needing source review.
    for i, row in enumerate(q["items"]):
        row["decision"] = None
        row["obligations"] = [{"id": f"O{i}", "destination": row["destination"]}]
    apply(world, q)
    with pytest.raises(ValueError, match="retired"):
        bp.file_packet(
            current, bp.build(current), p / "resources/artifacts", "2026-09-26"
        )


def test_source_request_is_copied_before_authority_boundary(world, monkeypatch):
    p, q = example(world)
    original = json.loads(json.dumps(q))
    real = rt._authority

    def mutate(*a, **kw):
        q["items"][1]["obligations"] = []
        return real(*a, **kw)

    monkeypatch.setattr(rt, "_authority", mutate)
    r = apply(world, q)
    value = api().validate_record(p, p / r["record"])
    assert value["request"] == original and value["unresolved_obligations"] == [
        "O1",
        "O2",
    ]


def test_succession_enumeration_has_an_exact_member_bound(world, monkeypatch):
    p, q = example(world)
    monkeypatch.setattr(api(), "MAX_ARTIFACT_ENTRIES", 2, raising=False)
    with pytest.raises(ValueError, match="bound"):
        api().records(p)


def test_current_destination_reads_share_the_source_byte_bound(world, monkeypatch):
    p, q = example(world)
    r = apply(world, q)
    (p / "resources/artifacts/queue.md").write_text("O1:\nO2:\n" + "x" * 100000)
    monkeypatch.setattr(api(), "MAX_SOURCE_BYTES", 20000)
    with pytest.raises(ValueError, match="byte bound"):
        api().validate_record(p, p / r["record"])


def test_filed_canonical_spec_binds_actual_generated_payload(world):
    p, q, _ = bound_example(world)
    import build_packet as bp
    from test_packet_causal import spec

    current = spec()
    (p / q["inventory"]["path"]).write_text(bp.build(current))
    q["inventory"]["sha256"] = hashlib.sha256(
        (p / q["inventory"]["path"]).read_bytes()
    ).hexdigest()
    specpath = p / "resources/artifacts/input-spec.json"
    specpath.write_bytes(bp.canonical_spec_bytes(current))
    q["inventory"]["spec"] = ref(p, "resources/artifacts/input-spec.json")
    r = apply(world, q)
    value = api().validate_record(p, p / r["record"])
    assert value["retired_spec_sha256"] == bp.spec_digest(current)
    assert value["items"][0]["decision_status"] == "bound-answer-unverified"


def test_dry_run_leaves_no_new_custody_or_journal(world):
    p, q = example(world)
    before = {
        str(f.relative_to(p)): f.read_bytes() for f in p.rglob("*") if f.is_file()
    }
    result = apply(world, q, dry_run=True)
    assert result["status"] == "dry-run"
    assert before == {
        str(f.relative_to(p)): f.read_bytes() for f in p.rglob("*") if f.is_file()
    }


def test_unexpected_receipt_fields_are_not_silently_trusted(world):
    p, q = example(world)
    r = apply(world, q)
    path = p / r["record"]
    value = json.loads(path.read_bytes())
    value["all_work_complete"] = True
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="fields"):
        api().validate_record(p, path)


def test_prepared_custody_failure_can_resume_without_losing_any_bytes(
    world, monkeypatch
):
    p, q = example(world)
    real = rt._new_file
    seen = 0
    raw = (p / q["inventory"]["path"]).read_bytes()

    def fail(path, data, mode=0o600):
        nonlocal seen
        if Path(path).suffix == ".bin":
            seen += 1
            if seen == 1:
                raise OSError("synthetic archive write refusal")
        return real(path, data, mode)

    with monkeypatch.context() as m:
        m.setattr(rt, "_new_file", fail)
        with pytest.raises(OSError):
            apply(world, q)
    assert (p / q["inventory"]["path"]).read_bytes() == raw
    r = apply(world, q)
    assert api().validate_record(p, p / r["record"])["status"] == "committed"


def test_destination_that_retirement_would_remove_is_refused_before_effect(world):
    p, q = example(world)
    page = p / q["inventory"]["path"]
    before = page.read_bytes()
    q["items"][1]["destination"] = ref(p, q["inventory"]["path"], '"id": "Q2"')
    q["items"][1]["obligations"][0]["destination"] = q["items"][1]["destination"]
    with pytest.raises((OSError, ValueError, rt.RecordTransactionError)):
        apply(world, q)
    assert page.read_bytes() == before


def test_transaction_preflight_is_bound_to_the_reviewed_whole_source(
    world, monkeypatch
):
    p, q = example(world)
    page = p / q["inventory"]["path"]
    before = page.read_bytes()
    real = context_edit.apply_transaction

    def append_after_review(*a, **kw):
        page.write_bytes(before + b"<!-- foreign retained update -->\n")
        return real(*a, **kw)

    monkeypatch.setattr(context_edit, "apply_transaction", append_after_review)
    with pytest.raises((OSError, ValueError, rt.RecordTransactionError)):
        apply(world, q)
    assert page.read_bytes() == before + b"<!-- foreign retained update -->\n"


@pytest.mark.parametrize("expected", [None, "bad", "0" * 64, False])
def test_existing_transaction_rejects_invalid_explicit_review_precondition(
    world, expected
):
    p = world["project"]
    target = p / "plan.md"
    old = target.read_bytes()
    request = [
        {
            "file": "plan.md",
            "expected_sha256": expected,
            "edits": [
                {
                    "op": "replace",
                    "anchor": "Human-owned prose.",
                    "replacement": "Reviewed change.",
                }
            ],
        }
    ]
    with pytest.raises(rt.RecordTransactionError, match="reviewed source"):
        context_edit.apply_transaction(
            p,
            request,
            board=world["board"],
            native_payload=world["actor"]["native_payload"],
        )
    assert target.read_bytes() == old and not (p / rt.STORE).exists()


def test_two_actual_cli_applications_serialize_and_preserve_one_commit(world):
    import subprocess

    p, q = example(world, "transfer")
    request = p / "request.json"
    request.write_text(json.dumps(q))
    event = p / "event.json"
    event.write_text(json.dumps(world["actor"]["native_payload"]))
    args = [
        sys.executable,
        str(Path(context_edit.__file__)),
        "apply-succession",
        "--project",
        str(p),
        "--request",
        str(request),
        "--board",
        str(world["board"]),
        "--native-payload",
        str(event),
    ]
    children = []
    results = []
    try:
        children = [
            subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            for _ in range(2)
        ]
        for child in children:
            out, err = child.communicate(timeout=30)
            results.append((child.returncode, out, err))
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
    assert all(code == 0 for code, _, _ in results), results
    values = [json.loads(out) for _, out, _ in results]
    assert len({v["record"] for v in values}) == 1
    history = json.loads((p / rt.STORE / "history.json").read_bytes())
    assert len(history["completed"]) == 1
    assert api().validate_record(p, p / values[0]["record"])["status"] == "committed"


def test_doctor_reports_current_drift_without_invalidating_history(world):
    p, q = example(world)
    apply(world, q)
    (p / "resources/artifacts/queue.md").write_text(
        "O1: still present\nO2: changed work\n"
    )
    import skill_outputs

    findings = skill_outputs.scan_project(p)
    assert any(f.severity == "warning" and "readiness" in f.message for f in findings)
    assert not any(f.severity == "defect" for f in findings)


def test_fifo_packet_does_not_disappear_from_doctor_inventory(world):
    import os

    p, q = example(world)
    page = p / q["inventory"]["path"]
    page.unlink()
    os.mkfifo(page)
    import skill_outputs

    assert any(f.severity == "defect" for f in skill_outputs.scan_project(p))
