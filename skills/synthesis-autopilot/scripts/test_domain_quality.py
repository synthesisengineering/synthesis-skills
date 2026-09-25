"""Synthetic domain contracts plus actual parser/consumer boundary checks.

Programmed judgments below are controls for the evaluator, never evidence of
a native model's semantic accuracy. The sandboxed consumer really executes.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import domain_quality as dq
from test_evidence_bridge import observed, record, append_claude_tool  # noqa: F401
from test_run_admission import world  # noqa: F401

BRIEF = "Write a lively note for a curious reader. The sample has five participants. No personal history is supplied."
SOUND = "Five people. One tiny sample, still enough to ask a better next question."
WRITING_DEFECTS = {
    "I interviewed all five hundred participants last winter.": "source_fidelity",
    "Five participants. Here is an unrelated recipe for cement.": "reader_purpose",
    "Five participants. Therefore nothing follows. Backup. Purple.": "structure",
    "Five participants. You are an idiot for asking a question.": "voice",
}


def add_document(context, identity, content, role="input"):
    path = context["project"] / (identity + ".txt")
    path.write_text(content)
    context["artifacts"][identity] = {"path": path.name, "digest": hashlib.sha256(content.encode()).hexdigest(), "role": role}
    return context["artifacts"][identity]["digest"]


def task_rubric(family="writing"):
    return {"schema_version": 1, "kind": "domain-rubric", "family": family, "criterion_id": "accept",
            "artifact_id": "draft", "task_artifact_id": "brief", "purpose": "Fulfill the supplied synthetic task for its reader",
            "criteria": [{"id": name, "dimension": name, "requirement": "Establish " + name + " for the supplied task",
                          "method": method, "evidence_artifact_ids": ["brief"],
                          **({"receipt_id": "actual-consumer", "check_id": "consumer-spec"} if method == "consumer" else {})}
                         for name, method in dq.DIMENSIONS[family].items()]}


def make_package(tmp_path, family="writing"):
    context = {"project": tmp_path, "artifacts": {}, "evidence": {}, "binding": {"session_uuid": "producer"},
               "state": {"run_id": "run-domain", "contract_digest": "a" * 64, "profile_digest": "b" * 64,
                         "contract": {"criteria": [{"id": "accept", "description": "Deliver a supported, useful note matching the supplied brief",
                                                     "artifact_ids": ["draft"], "required": True}]}}}
    add_document(context, "draft", SOUND, "output")
    add_document(context, "brief", BRIEF)
    rubric = task_rubric(family)
    rubric_digest = add_document(context, "rubric", json.dumps(rubric))
    labels = {dimension: "PASS" for dimension in dq.DIMENSIONS[family]}
    controls = [{"artifact_id": "sound", "artifact_digest": add_document(context, "sound", SOUND), "expected": labels}]
    defects = WRITING_DEFECTS if family == "writing" else {
        "Capacity is five hundred although the source says five.": "sources_verified",
        "Only the price question is answered; capacity is omitted.": "decisive_claims_verified",
        "The uncontrolled observation proves the intervention caused improvement.": "counterevidence_checked"}
    for index, (content, dimension) in enumerate(defects.items()):
        identity = "flaw-" + str(index)
        controls.append({"artifact_id": identity, "artifact_digest": add_document(context, identity, content),
                         "expected": {**labels, dimension: "FAIL"}})
    manifest = {"schema_version": 2, "domain": family, "rubric": "Synthetic task-specific domain rubric",
                "rubric_artifact_id": "rubric", "rubric_digest": rubric_digest, "controls": controls}
    add_document(context, "gold", json.dumps(manifest))
    return context, defects


def assessment(rubric, documents, target="draft", defect=None):
    """A labeled synthetic judgment for evaluator-contract tests only."""
    rows = []
    for requirement in rubric["criteria"]:
        ids = [target, *requirement["evidence_artifact_ids"]]
        evidence = [{"artifact_id": identity, "artifact_digest": documents[identity]["digest"],
                     "quote": documents[identity]["content"], "relation": "supports"} for identity in ids]
        failed = requirement["dimension"] == defect
        rows.append({"criterion_id": requirement["id"], "verdict": "FAIL" if failed else "PASS",
                     "reason": "Synthetic seeded defect is present" if failed else "Synthetic criterion is supported by the cited brief and output",
                     "evidence": evidence, "findings": [{"kind": "defect", "description": "Seeded substantive violation of " + defect,
                                                          "evidence_indices": [0, 1]}] if failed else []})
    return {"criteria": rows}


def complete_data(context, defects, *, target_assessment=None):
    package = dq.load_package(context, "gold", "accept", "draft")
    rubric, documents = package["rubric"], package["documents"]
    target = target_assessment or assessment(rubric, documents, defect=defects.get(documents["draft"]["content"]))
    controls = [{"artifact_id": row["artifact_id"], "artifact_digest": row["artifact_digest"],
                 "assessment": assessment(rubric, documents, row["artifact_id"], defects.get(documents[row["artifact_id"]]["content"]))}
                for row in package["manifest"]["controls"]]
    result = dq.derive(package, target, controls)
    return {"criterion_id": "accept", "artifact_id": "draft", "artifact_digest": documents["draft"]["digest"],
            "domain": rubric["family"], "rubric": package["manifest"]["rubric"], "method": "synthetic domain evaluator contract",
            "producer": "producer", "reviewer": "distinct-synthetic-reviewer", "independent": True,
            "observations": result["observations"], "calibrated": result["calibrated"],
            "passed": result["calibrated"] and result["observations"]["verdict"] == "PASS", "findings": [],
            "domain_review": {"assessment": target, "input_digests": package["input_digests"]},
            "calibration": {"manifest_id": "gold", "manifest_digest": package["manifest_digest"],
                "reviewer": "distinct-synthetic-reviewer", "rubric_artifact_id": "rubric",
                "rubric_digest": package["manifest"]["rubric_digest"], "observations": controls, "result": result["calibration_result"]}}


@pytest.mark.parametrize("family", list(dq.DIMENSIONS))
def test_each_family_requires_its_methods_and_every_dimension(family):
    rubric = task_rubric(family)
    assert dq.validate_rubric(rubric) == rubric
    missing = deepcopy(rubric); missing["criteria"].pop()
    with pytest.raises(ValueError, match="omits"):
        dq.validate_rubric(missing)
    wrong = deepcopy(rubric); wrong["criteria"][0]["method"] = "judgment"
    with pytest.raises(ValueError):
        dq.validate_rubric(wrong)


@pytest.mark.parametrize("family", ["writing", "research"])
def test_sound_and_seeded_defects_discriminate_on_declared_evidence(tmp_path, family):
    context, defects = make_package(tmp_path, family)
    data = complete_data(context, defects)
    assert dq.rederive_review(data, context) == "PASS"
    assert data["calibration"]["result"]["verdict"] == "PASS"
    assert len(data["calibration"]["result"]["controls"]) == len(dq.DIMENSIONS[family]) + 1
    for text, dimension in defects.items():
        add_document(context, "draft", text, "output")
        failed = complete_data(context, defects)
        assert dq.rederive_review(failed, context) == "FAIL"
        assert failed["observations"]["dimensions"][dimension] == "FAIL"


def test_sound_creative_voice_survives_style_only_rejection(tmp_path):
    context, defects = make_package(tmp_path)
    package = dq.load_package(context, "gold", "accept", "draft")
    raw = assessment(package["rubric"], package["documents"])
    voice = raw["criteria"][-1]
    voice.update(verdict="FAIL", reason="I prefer complete sentences",
                 findings=[{"kind": "preference", "description": "Prefer complete sentences; fragments sound informal", "evidence_indices": [0]}])
    data = complete_data(context, defects, target_assessment=raw)
    assert dq.rederive_review(data, context) == "PASS"
    assert data["observations"]["criteria"][-1]["asserted_verdict"] == "FAIL"
    assert data["domain_review"]["assessment"] == raw
    assert (tmp_path / "draft.txt").read_text() == SOUND


def test_explicit_contradiction_cannot_be_overridden_by_a_passing_vote(tmp_path):
    context, defects = make_package(tmp_path)
    add_document(context, "draft", "The sample has five hundred participants.", "output")
    package = dq.load_package(context, "gold", "accept", "draft")
    raw = assessment(package["rubric"], package["documents"])
    raw["criteria"][0]["evidence"][0]["relation"] = "contradicts"
    data = complete_data(context, defects, target_assessment=raw)
    assert raw["criteria"][0]["verdict"] == "PASS"
    assert dq.rederive_review(data, context) == "FAIL"


@pytest.mark.parametrize("mutation", ["missing-source", "unknown", "unexplained-rejection"])
def test_missing_or_unresolved_evidence_remains_unknown(tmp_path, mutation):
    context, defects = make_package(tmp_path)
    package = dq.load_package(context, "gold", "accept", "draft")
    raw = assessment(package["rubric"], package["documents"])
    if mutation == "missing-source": raw["criteria"][0]["evidence"].pop()
    if mutation == "unknown": raw["criteria"][0]["verdict"] = "UNKNOWN"
    if mutation == "unexplained-rejection": raw["criteria"][0]["verdict"] = "FAIL"
    data = complete_data(context, defects, target_assessment=raw)
    assert data["calibrated"] is True
    assert dq.rederive_review(data, context) == "UNKNOWN"
    assert data["passed"] is False


@pytest.mark.parametrize("mutation", ["omit", "duplicate", "quote", "digest", "foreign", "finding-index"])
def test_incomplete_or_invented_evidence_is_rejected(tmp_path, mutation):
    context, _ = make_package(tmp_path)
    package = dq.load_package(context, "gold", "accept", "draft")
    raw = assessment(package["rubric"], package["documents"])
    if mutation == "omit": raw["criteria"].pop()
    if mutation == "duplicate": raw["criteria"][-1] = deepcopy(raw["criteria"][0])
    if mutation == "quote": raw["criteria"][0]["evidence"][0]["quote"] = "Never present in any supplied artifact"
    if mutation == "digest": raw["criteria"][0]["evidence"][0]["artifact_digest"] = "f" * 64
    if mutation == "foreign": raw["criteria"][0]["evidence"][0]["artifact_id"] = "gold"
    if mutation == "finding-index": raw["criteria"][0]["findings"] = [{"kind": "defect", "description": "Unsupported rejection", "evidence_indices": [99]}]
    with pytest.raises(ValueError):
        dq.assess(package["rubric"], raw, package["documents"])


@pytest.mark.parametrize("mutation", ["dimension", "positive", "duplicate-bytes", "self-source", "boolean-schema"])
def test_calibration_requires_sound_and_each_dimensional_defect_before_review(tmp_path, mutation):
    context, _ = make_package(tmp_path)
    manifest = json.loads((tmp_path / "gold.txt").read_text())
    if mutation == "dimension": manifest["controls"] = manifest["controls"][:-1]
    if mutation == "positive": manifest["controls"] = manifest["controls"][1:]
    if mutation == "duplicate-bytes":
        body = (tmp_path / "sound.txt").read_text()
        manifest["controls"][1]["artifact_digest"] = add_document(context, "flaw-0", body)
    if mutation == "self-source": manifest["controls"][0]["artifact_id"] = "draft"
    if mutation == "boolean-schema": manifest["schema_version"] = True
    add_document(context, "gold", json.dumps(manifest))
    with pytest.raises(ValueError): dq.load_package(context, "gold", "accept", "draft")


@pytest.mark.parametrize("identity", ["draft", "brief", "rubric", "gold", "sound", "flaw-0"])
def test_every_current_artifact_is_reread_at_source_verification(tmp_path, identity):
    context, defects = make_package(tmp_path)
    data = complete_data(context, defects)
    (tmp_path / (identity + ".txt")).write_text("Changed after review")
    with pytest.raises(ValueError): dq.rederive_review(data, context)


@pytest.mark.parametrize("mutation", ["passed", "calibrated", "summary", "independence", "labels-visible"])
def test_rich_flags_cannot_replace_rederived_evidence(tmp_path, mutation):
    context, defects = make_package(tmp_path)
    data = complete_data(context, defects)
    request = {"artifact_digests": deepcopy(data["domain_review"]["input_digests"])}
    if mutation == "passed": data["passed"] = False
    if mutation == "calibrated": data["calibrated"] = False
    if mutation == "summary": data["observations"]["verdict"] = "UNKNOWN"
    if mutation == "independence": data["reviewer"] = data["producer"]
    if mutation == "labels-visible": request["artifact_digests"]["gold"] = context["artifacts"]["gold"]["digest"]
    with pytest.raises(ValueError): dq.rederive_review(data, context, request)


def test_no_tools_judgment_cannot_certify_execution_or_target_readback():
    for family in ("software", "data", "browser", "project"):
        rubric = task_rubric(family)
        documents = {identity: {"artifact_id": identity, "digest": hashlib.sha256(body.encode()).hexdigest(), "content": body}
                     for identity, body in (("brief", BRIEF), ("draft", SOUND))}
        result = dq.assess(rubric, assessment(rubric, documents), documents)
        assert result["verdict"] == "UNKNOWN"
        for name, method in dq.DIMENSIONS[family].items():
            assert result["dimensions"][name] == ("PASS" if method == "judgment" else "UNKNOWN")


def actual_consumer_fixture(tmp_path, reported=3):
    import consumer_checks
    import evidence_bridge
    context = {"project": tmp_path, "artifacts": {}, "evidence": {}, "binding": {"session_uuid": "producer"},
               "state": {"run_id": "run-data", "contract_digest": "a" * 64, "profile_digest": "b" * 64,
                         "contract": {"criteria": [{"id": "accept", "artifact_ids": ["draft"]}]}}}
    add_document(context, "brief", "Report mean over observed values, with coverage; never impute missing values.")
    add_document(context, "draft", json.dumps({"mean": reported}), "output")
    add_document(context, "source", json.dumps([2, None, 4, None]))
    program = tmp_path / "check.py"
    program.write_text('import json\nfrom pathlib import Path\nvalues=json.loads(Path("source.txt").read_text())\nobserved=[v for v in values if v is not None]\nprint(json.dumps({"reported_mean":json.loads(Path("draft.txt").read_text())["mean"],"recomputed_mean":sum(observed)/len(observed),"coverage":str(len(observed))+"/"+str(len(values))}))\n')
    context["artifacts"]["program"] = {"path": "check.py", "digest": hashlib.sha256(program.read_bytes()).hexdigest(), "role": "input"}
    add_document(context, "consumer-spec", json.dumps({"schema_version": 1, "kind": "python-consumer", "criterion_id": "accept",
        "artifact_id": "draft", "script_artifact_id": "program", "expected": {"reported_mean": 3, "recomputed_mean": 3.0, "coverage": "2/4"}, "argv": [], "timeout_seconds": 5}))
    actual = consumer_checks.observe(context, {"check_id": "consumer-spec"})
    assert actual["execution"]["sandbox_verified"] is True
    # The actual process result enters the same immutable event-source boundary
    # as run_state. This local fixture does not claim a live native session.
    record = {"id": "actual-consumer", "kind": "consumer-check", "artifact_id": "event:1", "bindings": {},
              "data": actual, "digest": dq.digest(actual), "observed_at": "fixture", "expires_at": "fixture"}
    context["evidence"]["actual-consumer"] = record
    context["state"]["observations"] = {"actual-consumer": {**record, "artifact_digests": actual["input_digests"]}}
    context["verify_receipt"] = lambda identity, kind, bindings: (
        kind == "consumer-check" and identity == "actual-consumer" and evidence_bridge._event_observation(record, context))
    rubric = task_rubric("data")
    for row in rubric["criteria"]:
        row["evidence_artifact_ids"].append("source")
    documents = {identity: dq._document(context, identity) for identity in ("brief", "source", "draft")}
    return context, rubric, documents, record


@pytest.mark.parametrize("reported,expected", [(3, "PASS"), (1.5, "FAIL")])
def test_real_sandboxed_consumer_catches_wrong_denominator(tmp_path, reported, expected):
    context, rubric, documents, _ = actual_consumer_fixture(tmp_path, reported)
    result = dq.assess(rubric, assessment(rubric, documents), documents, context=context)
    assert result["verdict"] == expected
    assert all(result["dimensions"][name] == expected for name, method in dq.DIMENSIONS["data"].items() if method == "consumer")


@pytest.mark.parametrize("identity", ["draft", "source", "brief"])
def test_consumer_rejects_different_assessed_documents_with_authentic_receipt(tmp_path, identity):
    import evidence_bridge
    context, rubric, documents, record = actual_consumer_fixture(tmp_path)
    immutable = deepcopy(record)
    body = {"draft": '{"mean":1.5}', "source": '[999,null,999,null]',
            "brief": "Count missing values as zero in the denominator."}[identity]
    documents[identity] = {"artifact_id": identity, "content": body,
                           "digest": hashlib.sha256(body.encode()).hexdigest()}
    assert evidence_bridge._event_observation(record, context) is True
    with pytest.raises(ValueError, match="registered"):
        dq.assess(rubric, assessment(rubric, documents), documents, context=context)
    assert record == immutable
    assert evidence_bridge._event_observation(record, context) is True


def test_consumer_cannot_certify_a_different_registered_target(tmp_path):
    context, rubric, documents, _ = actual_consumer_fixture(tmp_path)
    add_document(context, "other-output", '{"mean":1.5}', "output")
    documents["other-output"] = dq._document(context, "other-output")
    with pytest.raises(ValueError, match="target"):
        dq.assess(rubric, assessment(rubric, documents, "other-output"), documents,
                  context=context, target_id="other-output")


def test_consumer_requires_all_assessed_sources_in_execution_receipt(tmp_path):
    import evidence_bridge
    context, rubric, documents, record = actual_consumer_fixture(tmp_path)
    add_document(context, "later-source", "A newly introduced source was absent during execution.")
    documents["later-source"] = dq._document(context, "later-source")
    for row in rubric["criteria"]:
        row["evidence_artifact_ids"].append("later-source")
    assert evidence_bridge._event_observation(record, context) is True
    result = dq.assess(rubric, assessment(rubric, documents), documents, context=context)
    assert result["verdict"] == "UNKNOWN"
    assert all(result["dimensions"][name] == "UNKNOWN" for name, method in dq.DIMENSIONS["data"].items() if method == "consumer")


@pytest.mark.parametrize("identity", ["draft", "source", "brief", "program", "consumer-spec"])
def test_consumer_cannot_reuse_execution_after_registered_input_changes(tmp_path, identity):
    context, rubric, documents, record = actual_consumer_fixture(tmp_path)
    immutable = deepcopy(record)
    old = context["artifacts"][identity]
    path = tmp_path / old["path"]
    raw = path.read_bytes() + b"\n"
    path.write_bytes(raw)
    old["digest"] = hashlib.sha256(raw).hexdigest()
    if identity in documents:
        documents[identity] = dq._document(context, identity)
    result = dq.assess(rubric, assessment(rubric, documents), documents, context=context)
    assert result["verdict"] == "UNKNOWN"
    assert record == immutable


@pytest.mark.parametrize("case", ["valid", "unknown", "forged-pass", "source-changed", "source-quote", "visible-gold"])
def test_actual_native_source_verification_rederives_rich_review(observed, world, case):
    import native_review
    fixture, defects = make_package(world["project"])
    observed["artifacts"] = fixture["artifacts"]
    observed["state"]["contract"]["criteria"] = fixture["state"]["contract"]["criteria"]
    package = dq.load_package(observed, "gold", "accept", "draft")
    raw = assessment(package["rubric"], package["documents"])
    if case == "unknown": raw["criteria"][0]["verdict"] = "UNKNOWN"
    data = complete_data(observed, defects, target_assessment=raw)
    data["producer"] = observed["binding"]["native_ref"]
    data["reviewer"] = data["calibration"]["reviewer"] = "claude-agent:domain-call"
    if case == "forged-pass": data["observations"]["criteria"][0]["verdict"] = "UNKNOWN"
    if case == "source-quote": data["domain_review"]["assessment"]["criteria"][0]["evidence"][0]["quote"] = "Fabricated quotation"
    bindings = {key: observed["state"][key] for key in ("run_id", "contract_digest", "profile_digest")}
    request = {"schema_version": 1, "kind": "quality_observation", "bindings": bindings,
               "artifact_digests": deepcopy(data["domain_review"]["input_digests"]), "producer": data["producer"]}
    if case == "visible-gold": request["artifact_digests"]["gold"] = observed["artifacts"]["gold"]["digest"]
    response = {"schema_version": 1, "kind": "quality_observation", "bindings": bindings, "data": data}
    append_claude_tool(world, "Agent", {"prompt": json.dumps({"autopilot_review": request})},
                       {"autopilot_review": response}, "domain-call")
    receipt = record("quality_observation", {**data, "source": {"kind": "native-agent", "call_id": "domain-call"}}, observed)
    if case == "source-changed": (world["project"] / "brief.txt").write_text("Different primary source")
    assert native_review.verify_source(receipt, observed) is (case in {"valid", "unknown"})
