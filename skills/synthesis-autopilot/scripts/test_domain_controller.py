"""A7 fixture-first integration: synthetic judgments, real local consumers.

No test in this file qualifies a paid reviewer or a remote browser account.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import domain_quality as dq
from test_domain_quality import (actual_consumer_fixture, add_document, assessment,
                                 make_package, task_rubric)
from test_controller import engine, facade, world, request, start_request, invoke, state_of  # noqa: F401


def mixed_package(context, family):
    rubric = task_rubric(family)
    if "source" in context["artifacts"]:
        for row in rubric["criteria"]:
            row["evidence_artifact_ids"].append("source")
    rubric_digest = add_document(context, "rubric", json.dumps(rubric))
    labels = {key: "PASS" if method in {"source", "judgment"} else "UNKNOWN"
              for key, method in dq.DIMENSIONS[family].items()}
    sound = add_document(context, "sound", "Clear, task-specific, maintainable explanation with distinctive useful voice.")
    controls = [{"artifact_id": "sound", "artifact_digest": sound, "expected": labels}]
    for dimension, method in dq.DIMENSIONS[family].items():
        if method in {"source", "judgment"}:
            ident = "defect-" + dimension
            content = "Substantive seeded defect: " + dimension + "; required operator decision is hidden."
            controls.append({"artifact_id": ident, "artifact_digest": add_document(context, ident, content),
                             "expected": {**labels, dimension: "FAIL"}})
    add_document(context, "gold", json.dumps({"schema_version": 2, "domain": family,
        "rubric": "Task-specific mixed evidence", "rubric_artifact_id": "rubric",
        "rubric_digest": rubric_digest, "controls": controls}))
    context["state"]["contract"]["criteria"][0].setdefault("description", "Answer the actual operator question with evidence and useful explanation")
    package = dq.load_package(context, "gold", "accept", "draft")
    controls = [{"artifact_id": row["artifact_id"], "artifact_digest": row["artifact_digest"],
        "assessment": assessment(rubric, package["documents"], row["artifact_id"],
            next((key for key, value in row["expected"].items() if value == "FAIL"), None))}
        for row in package["manifest"]["controls"]]
    return package, controls


@pytest.mark.parametrize("family", list(dq.DIMENSIONS))
def test_all_six_families_route_to_existing_domain_owner(tmp_path, family):
    context, _ = make_package(tmp_path)
    package, controls = mixed_package(context, family)
    result = dq.derive(package, assessment(package["rubric"], package["documents"]), controls, context=context)
    assert result["calibrated"] is True
    assert result["observations"]["verdict"] == ("PASS" if family in {"writing", "research"} else "UNKNOWN")
    route = dq.family_route(family)
    assert route["owner_skill"] != "synthesis-autopilot"
    assert Path(route["method_path"]).is_file()
    prompt, _ = dq.review_prompt(package, {})
    assert route["guidance"] in prompt
    assert "Control outcomes do not certify execution or target readback" in prompt


@pytest.mark.parametrize("reported,expected", [(3, "PASS"), (1.5, "FAIL")])
@pytest.mark.parametrize("family", ["data", "software"])
def test_mixed_native_route_keeps_actual_consumer_verdict(tmp_path, reported, expected, family):
    context, _, _, _ = actual_consumer_fixture(tmp_path, reported)
    package, controls = mixed_package(context, family)
    result = dq.derive(package, assessment(package["rubric"], package["documents"]), controls, context=context)
    assert result["calibrated"] is True
    assert result["observations"]["verdict"] == expected
    for dimension, method in dq.DIMENSIONS[family].items():
        assert result["observations"]["dimensions"][dimension] == (expected if method == "consumer" else "PASS")


@pytest.mark.parametrize("reported,expected", [(3, "UNKNOWN"), (1.5, "FAIL")])
@pytest.mark.parametrize("adequacy", ["UNKNOWN", "FAIL"])
def test_execution_cannot_resolve_unknown_or_unexplained_method_adequacy(tmp_path, reported, expected, adequacy):
    context, _, _, _ = actual_consumer_fixture(tmp_path, reported)
    package, controls = mixed_package(context, "data")
    raw = assessment(package["rubric"], package["documents"])
    methods = {row["id"]: row["method"] for row in package["rubric"]["criteria"]}
    for row in raw["criteria"]:
        if methods[row["criterion_id"]] == "consumer":
            row.update(verdict=adequacy, reason="Adequacy for the required task remains unresolved", findings=[])
    result = dq.derive(package, raw, controls, context=context)
    assert result["calibrated"] is True
    assert result["observations"]["verdict"] == expected
    for dimension, method in dq.DIMENSIONS["data"].items():
        if method == "consumer":
            assert result["observations"]["dimensions"][dimension] == expected
    prompt, _ = dq.review_prompt(package, {})
    assert "method adequacy and task coverage" in prompt
    assert "never attests execution or target readback" in prompt


def test_current_project_readback_cannot_resolve_unknown_method_adequacy(tmp_path, monkeypatch):
    context, _ = make_package(tmp_path)
    package, controls = mixed_package(context, "project")
    raw = assessment(package["rubric"], package["documents"])
    readback = next(row["id"] for row in package["rubric"]["criteria"] if row["method"] == "readback")
    next(row for row in raw["criteria"] if row["criterion_id"] == readback).update(
        verdict="UNKNOWN", reason="Current ownership exists but task coverage is unresolved")
    # Isolated composition seam; actual ownership and released-seat behavior
    # are separately exercised by the admitted PM controller fixture below.
    monkeypatch.setattr(dq, "project_ownership_readback", lambda context: ("PASS", "Current owner seam"))
    result = dq.derive(package, raw, controls, context=context)
    assert result["observations"]["dimensions"]["ownership_integrity"] == "UNKNOWN"


@pytest.mark.parametrize("identity", ["source", "program", "consumer-spec", "draft"])
def test_mixed_review_rejects_stale_execution(tmp_path, identity):
    context, _, _, record = actual_consumer_fixture(tmp_path)
    package, controls = mixed_package(context, "data")
    immutable = deepcopy(record)
    path = tmp_path / context["artifacts"][identity]["path"]
    path.write_bytes(path.read_bytes() + b"\n")
    context["artifacts"][identity]["digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    package, controls = mixed_package(context, "data")
    result = dq.derive(package, assessment(package["rubric"], package["documents"]), controls, context=context)
    assert result["observations"]["verdict"] == "UNKNOWN"
    assert record == immutable


def test_calibration_cannot_claim_execution_for_blind_controls(tmp_path):
    context, _ = make_package(tmp_path)
    package, _ = mixed_package(context, "browser")
    manifest = package["manifest"]
    manifest["controls"][0]["expected"]["stored_target_state"] = "PASS"
    add_document(context, "gold", json.dumps(manifest))
    with pytest.raises(ValueError, match="execution|readback|nonsemantic|labels"):
        dq.load_package(context, "gold", "accept", "draft")


def test_browser_page_success_cannot_certify_account_or_preservation(tmp_path):
    context, _ = make_package(tmp_path)
    add_document(context, "draft", "Successfully saved to the correct account; all exclusions preserved", "output")
    package, controls = mixed_package(context, "browser")
    result = dq.derive(package, assessment(package["rubric"], package["documents"]), controls, context=context)
    assert result["calibrated"] is True
    assert result["observations"]["verdict"] == "UNKNOWN"
    assert all(result["observations"]["dimensions"][dimension] == "UNKNOWN"
               for dimension in ("target_identity", "stored_target_state", "excluded_item_preservation"))


def test_review_binds_the_actual_domain_owner_method_bytes(tmp_path, monkeypatch):
    from test_domain_quality import complete_data
    context, defects = make_package(tmp_path)
    data = complete_data(context, defects)
    assert data["domain_review"]["method_provenance"]["owner_skill"] == "synthesis-writing-craft"
    original = dq.family_route
    monkeypatch.setattr(dq, "family_route", lambda family: {**original(family), "method_digest": "f" * 64})
    with pytest.raises(ValueError, match="method|bindings|universe"):
        dq.rederive_review(data, context)


def test_review_receives_actual_consumer_program_and_can_reject_a_tautological_check(tmp_path):
    import consumer_checks
    import evidence_bridge
    context, _, _, record = actual_consumer_fixture(tmp_path, 1.5)
    program = tmp_path / "check.py"
    # A seeded false-acceptance implementation: fixed output hides the wrong
    # denominator. Actual execution passes its declared comparison; inspection
    # must still be able to reject the check's adequacy for the user outcome.
    program.write_text('print(\'{"reported_mean":3,"recomputed_mean":3.0,"coverage":"2/4"}\')\n')
    context["artifacts"]["program"]["digest"] = hashlib.sha256(program.read_bytes()).hexdigest()
    actual = consumer_checks.observe(context, {"check_id": "consumer-spec"})
    record.update(data=actual, digest=dq.digest(actual))
    context["state"]["observations"]["actual-consumer"] = {**record, "artifact_digests": actual["input_digests"]}
    assert evidence_bridge._event_observation(record, context) and actual["passed"] is True
    package, controls = mixed_package(context, "data")
    prompt, _ = dq.review_prompt(package, {})
    value = json.loads(prompt.split("\nREQUEST\n", 1)[1])
    assert {"program", "consumer-spec"} <= {row["artifact_id"] for row in value["sources"]}
    assert package["input_digests"]["program"] == context["artifacts"]["program"]["digest"]
    raw = assessment(package["rubric"], package["documents"])
    target = raw["criteria"][0]
    target["evidence"].append({"artifact_id": "program", "artifact_digest": package["documents"]["program"]["digest"],
                               "quote": program.read_text(), "relation": "contradicts"})
    target["findings"].append({"kind": "defect", "description": "Check prints fixed values without reading the reported mean", "evidence_indices": [2]})
    result = dq.derive(package, raw, controls, context=context)
    assert result["calibrated"] is True
    assert result["observations"]["verdict"] == "FAIL"


@pytest.mark.parametrize("family", list(dq.DIMENSIONS))
def test_ordinary_controller_exposes_family_requirements(facade, world, family):
    req = start_request(world)
    req["input"]["dimensions"]["domains"] = [family]
    response = invoke(facade, world, req)
    assert response["status"] == "READY", response
    route = response["coverage"]["domain_quality"][0]
    assert route["family"] == family
    assert set(route["dimensions"]) == set(dq.DIMENSIONS[family])
    assert route["criterion_ids"] == ["accept"]
    assert route["owner_skill"] != "synthesis-autopilot"
    assert route["qualified"] is False


def test_project_ownership_readback_uses_actual_admission_and_rejects_released_seat(facade, world):
    import run_state
    req = start_request(world)
    req["input"]["dimensions"]["domains"] = ["project"]
    response = invoke(facade, world, req)
    state = state_of(world, response)
    context = run_state.inspect_context(state, world["actor"], project=world["project"])
    context.update(state=state, project=world["project"], actor=world["actor"])
    assert dq.project_ownership_readback(context)[0] == "PASS", dq.project_ownership_readback(context)
    board = Path(world["actor"]["board"])
    original = board.read_text()
    board.write_text(original.replace("| active |", "| released |"))
    if board.read_text() == original:
        pytest.fail("synthetic active-seat positive control did not match")
    assert dq.project_ownership_readback(context)[0] == "UNKNOWN"


def test_finish_selection_does_not_erase_typed_review():
    import controller
    evidence = {"typed": {"data": {"domain_review": {}, "domain": "data"}},
                "plain": {"data": {"domain": "software"}}}
    assert controller._typed_quality(["plain", "typed"], evidence) == ["typed"]
    assert controller._typed_quality(["plain"], evidence) == []


def synthetic_native_judgment(client, prompt, **kwargs):
    """Programmed semantic judgments only; this never executes a native model."""
    value = json.loads(prompt.split("\nREQUEST\n", 1)[1])
    rubric = value["rubric"]
    documents = {row["artifact_id"]: row for row in [value["artifact"], *value["sources"], *value["controls"]]}
    controls = []
    for control in value["controls"]:
        defect = next((name for name in dq.DIMENSIONS[rubric["family"]]
                       if "Substantive seeded defect: " + name in control["content"]), None)
        controls.append({"artifact_id": control["artifact_id"], "artifact_digest": control["digest"],
                         "assessment": assessment(rubric, documents, control["artifact_id"], defect)})
    return {"response": {"bindings": value["bindings"], "artifact_digest": value["artifact_digest"],
        "assessment": assessment(rubric, documents), "controls": controls}, "session_id": "synthetic-domain-reviewer",
        "model": "synthetic-no-native-call", "usage": {"cost_usd": 0.1}, "stdout_digest": "c" * 64,
        "wall_seconds": 1, "returncode": 0, "tool_calls": [], "client": client}


def admitted_domain(facade, world, monkeypatch, family, *, reported=3, unsuitable=False, tautological=False):
    """Real controller, journal, PM admission and executed consumer; synthetic judge."""
    import run_state
    import native_review_observer
    from test_run_state import command
    req = start_request(world)
    req["input"]["dimensions"]["domains"] = [family]
    criterion = req["input"]["outcome_contract"]["criteria"][0]
    criterion.update(method="quality_observation", artifact_ids=["draft"], evidence_ids=["quality-slot"],
                     description="Report the mean over observed values with exact coverage and usable reasoning")
    if family == "writing":
        criterion["description"] = "Write a lively useful note for a curious reader about a five-person sample without inventing history"
    if family == "project":
        criterion["description"] = "Preserve every retained obligation and its source generation in a useful handoff"
    if family == "software":
        criterion["description"] = "The public CLI returns the mean of numeric arguments and exits 2 with a useful error for invalid input"
    req["input"]["resource_envelope"]["limits"].update(
        wall_millis={"limit": 120000, "enforcement": "hard"}, usd_micros={"limit": 1000000, "enforcement": "forecast"})
    response = invoke(facade, world, req)
    assert response["status"] == "READY", response
    state = state_of(world, response)
    response = invoke(facade, world, request("next", {"mode": "start"}, state))
    assert response["status"] == "READY", response
    state = state_of(world, response)
    records = [
        ("brief", "brief.txt", "Report the mean of observed values, exact missing-value coverage, and practical use.", "input"),
        ("source", "source.txt", "[2,null,4,null]", "input"),
        ("draft", "draft.txt", json.dumps({"mean": reported}), "output"),
        ("program", "check.py", 'import json\nfrom pathlib import Path\nv=json.loads(Path("source.txt").read_text())\nn=[x for x in v if x is not None]\nprint(json.dumps({"reported_mean":json.loads(Path("draft.txt").read_text())["mean"],"recomputed_mean":sum(n)/len(n),"coverage":str(len(n))+"/"+str(len(v))}))\n', "input")]
    expected = {"reported_mean": 3, "recomputed_mean": 3.0, "coverage": "2/4"}
    if family == "writing":
        from test_domain_quality import BRIEF, SOUND
        text = "The shimmering ocean invites a tranquil appreciation of color." if unsuitable else SOUND
        records = [("brief", "brief.txt", BRIEF, "input"),
            ("source", "source.txt", "The supplied sample has five people.", "input"),
            ("draft", "draft.txt", text, "output"),
            ("program", "check.py", 'import json\nfrom pathlib import Path\nprint(json.dumps({"nonempty":bool(Path("draft.txt").read_text().strip())}))\n', "input")]
        expected = {"nonempty": True}
    if family == "project":
        source = {"generation": "retained-7", "obligations": [{"id": "retained-work", "status": "pending"},
                   {"id": "native-qualification", "status": "blocked"}]}
        output = {"source_generation": "retained-7", "obligations": source["obligations"] if reported == 3 else source["obligations"][:1]}
        records = [("brief", "brief.txt", criterion["description"], "input"),
            ("source", "source.txt", json.dumps(source), "input"),
            ("draft", "draft.txt", json.dumps(output), "output"),
            ("program", "check.py", 'import json\nfrom pathlib import Path\ns=json.loads(Path("source.txt").read_text())\no=json.loads(Path("draft.txt").read_text())\nprint(json.dumps({"obligation_identity_and_status":s["obligations"]==o["obligations"],"source_generation":s["generation"]==o["source_generation"]}))\n', "input")]
        expected = {"obligation_identity_and_status": True, "source_generation": True}
    elif family == "software":
        app = 'import sys,json\ntry:\n    v=[float(x) for x in sys.argv[1].split(",")]\n    print(json.dumps({"mean":sum(v)/' + ('len(v)' if reported == 3 else '(len(v)*2)') + '}))\nexcept (ValueError,IndexError):\n    print("numeric arguments required",file=sys.stderr)\n    raise SystemExit(2)\n'
        # The existing consumer sandbox denies forking. Exercise the public
        # __main__ entry point in that real sandbox, observing arguments,
        # stdout, stderr and SystemExit without claiming a child-process run.
        check = 'import contextlib,io,json,runpy,sys\nfrom pathlib import Path\ns=json.loads(Path("source.txt").read_text())\ndef run(arg):\n    out,err=io.StringIO(),io.StringIO()\n    sys.argv=["app.py",arg]\n    code=0\n    with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):\n        try: runpy.run_path("app.py",run_name="__main__")\n        except SystemExit as exc: code=exc.code\n    return out.getvalue(),err.getvalue(),code\ng=run(s["good"])\nb=run(s["bad"])\nprint(json.dumps({"good":json.loads(g[0]),"good_exit":g[2],"adverse_exit":b[2],"adverse_error":b[1].strip()}))\n'
        records = [("brief", "brief.txt", criterion["description"], "input"),
            ("source", "source.txt", json.dumps({"good": "2,4", "bad": "not-a-number"}), "input"),
            ("draft", "app.py", app, "output"), ("program", "check.py", check, "input")]
        expected = {"good": {"mean": 3.0}, "good_exit": 0, "adverse_exit": 2, "adverse_error": "numeric arguments required"}
    if tautological:
        assert family == "data" and reported != 3
        records[-1] = ("program", "check.py", 'print(\'{"reported_mean":3,"recomputed_mean":3.0,"coverage":"2/4"}\')\n', "input")
    for identity, filename, content, role in records:
        path = world["project"] / filename; path.write_text(content)
        response = invoke(facade, world, request("record", {"kind": "artifact", "artifact_id": identity,
            "path": str(path), "role": role, "required": role == "output", "retention": "durable"}, state, "register-" + identity))
        assert response["status"] == "RECORDED", response
        state = state_of(world, response)
    response = invoke(facade, world, request("record", {"kind": "check", "observer_kind": "consumer-check", "arguments": {
        "criterion_id": "accept", "artifact_id": "draft", "script_artifact_id": "program",
        "expected": expected, "argv": [], "timeout_seconds": 5}}, state, "real-consumer"))
    assert response["status"] == "RECORDED", response
    state = state_of(world, response)
    execution = next(row for row in state["evidence"].values() if row["kind"] == "consumer-check")
    context = {**run_state.inspect_context(state, world["actor"]), "state": state,
               "project": world["project"], "actor": world["actor"]}
    package, _ = mixed_package(context, family)
    rubric = package["rubric"]
    for row in rubric["criteria"]:
        if row["method"] == "consumer":
            row.update(receipt_id=execution["id"], check_id=execution["data"]["check_id"])
    rubric_digest = add_document(context, "rubric", json.dumps(rubric))
    manifest = package["manifest"]; manifest["rubric_digest"] = rubric_digest
    add_document(context, "gold", json.dumps(manifest))
    # mixed_package creates only rubric and control inputs; register those real
    # files through the ordinary controller rather than editing journal state.
    for identity in sorted(set(context["artifacts"]) - set(state["artifacts"])):
        row = context["artifacts"][identity]
        response = invoke(facade, world, request("record", {"kind": "artifact", "artifact_id": identity,
            "path": str(world["project"] / row["path"]), "role": "input", "required": False,
            "retention": "durable"}, state, "register-" + identity))
        assert response["status"] == "RECORDED", response
        state = state_of(world, response)
    state = command(run_state, world, state, "workflow.reserve", {"reservation_id": "review",
        "amounts": {"wall_millis": 10000, "usd_micros": 500000}, "category": "verification"})
    def judgment(client, prompt, **kwargs):
        result = synthetic_native_judgment(client, prompt, **kwargs)
        if unsuitable or tautological:
            value = json.loads(prompt.split("\nREQUEST\n", 1)[1])
            docs = {row["artifact_id"]: row for row in [value["artifact"], *value["sources"], *value["controls"]]}
            result["response"]["assessment"] = assessment(value["rubric"], docs,
                defect="reader_purpose" if unsuitable else "coverage_and_missingness")
            if tautological:
                target = result["response"]["assessment"]["criteria"][0]
                program = docs["program"]
                target["evidence"].append({"artifact_id": "program", "artifact_digest": program["digest"],
                    "quote": program["content"], "relation": "contradicts"})
                target["findings"].append({"kind": "defect", "description": "Fixed values ignore the actual wrong denominator", "evidence_indices": [2]})
        return result
    monkeypatch.setattr(native_review_observer, "execute_native", judgment)
    response = invoke(facade, world, request("record", {"kind": "check", "observer_kind": "quality_observation", "arguments": {
        "mode": "native-cli", "client": "claude", "criterion_id": "accept", "artifact_id": "draft",
        "calibration_manifest_id": "gold", "reservation_id": "review", "timeout_seconds": 10,
        "max_cost_usd": 0.5}}, state, "synthetic-judge"))
    assert response["status"] == "RECORDED", response
    state = state_of(world, response)
    state = command(run_state, world, state, "workflow.settle", {"reservation_id": "review",
        "actual": {"wall_millis": 1000, "usd_micros": 100000}})
    return state


@pytest.mark.parametrize("family", list(dq.DIMENSIONS))
def test_six_family_controller_finish_uses_real_consumers_and_synthetic_semantics(facade, world, monkeypatch, family):
    state = admitted_domain(facade, world, monkeypatch, family)
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state))
    expected = "UNRESOLVED" if family == "browser" else "COMPLETED"
    assert response["status"] == expected, response
    final = state_of(world, response)
    quality = final["extensions"]["workflow"]["quality"]["accept"]
    assert quality["verdict"] == ("UNKNOWN" if family == "browser" else "PASS")
    assert all("domain_review" in final["evidence"][identity]["data"] for identity in quality["receipt_ids"])
    assert final["status"] == ("verifying" if family == "browser" else "completed")


@pytest.mark.parametrize("family", ["data", "software", "project"])
def test_failed_actual_consumer_blocks_controller_despite_passing_synthetic_judgment(facade, world, monkeypatch, family):
    state = admitted_domain(facade, world, monkeypatch, family, reported=1.5)
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state))
    assert response["status"] == "UNRESOLVED", response
    final = state_of(world, response)
    assert final["status"] != "completed"
    assert any(row["kind"] == "consumer-check" and row["data"]["passed"] is False for row in final["evidence"].values())


@pytest.mark.parametrize("identity", ["program", "consumer-spec"])
def test_controller_finish_rejects_changed_consumer_or_specification(facade, world, monkeypatch, identity):
    state = admitted_domain(facade, world, monkeypatch, "data")
    actual = next(row for row in state["evidence"].values() if row["kind"] == "consumer-check")
    target = "program" if identity == "program" else actual["data"]["check_id"]
    path = world["project"] / state["artifacts"][target]["path"]
    path.write_bytes(path.read_bytes() + b"\n")
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state, "stale-consumer-finish"))
    assert response["status"] == "UNRESOLVED", response
    assert state_of(world, response)["status"] != "completed"


def test_controller_rejects_well_formed_writing_that_misses_reader_purpose(facade, world, monkeypatch):
    state = admitted_domain(facade, world, monkeypatch, "writing", unsuitable=True)
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state))
    assert response["status"] == "UNRESOLVED", response
    final = state_of(world, response)
    assert final["extensions"]["workflow"]["quality"]["accept"]["verdict"] == "FAIL"
    assert any(row["kind"] == "consumer-check" and row["data"]["passed"] for row in final["evidence"].values())


def test_controller_keeps_semantic_failure_when_hard_coded_consumer_passes(facade, world, monkeypatch):
    state = admitted_domain(facade, world, monkeypatch, "data", reported=1.5, tautological=True)
    response = invoke(facade, world, request("finish", {"disposition": "completed"}, state))
    assert response["status"] == "UNRESOLVED", response
    final = state_of(world, response)
    assert final["extensions"]["workflow"]["quality"]["accept"]["verdict"] == "FAIL"
    assert any(row["kind"] == "consumer-check" and row["data"]["passed"] for row in final["evidence"].values())


def test_domain_method_digest_and_prompt_use_one_byte_snapshot(monkeypatch):
    original = Path.read_text
    def interleaved(self, *args, **kwargs):
        if self.name == "autopilot-data-quality.md":
            return "A different method version observed by a separate text read"
        return original(self, *args, **kwargs)
    # Model a method replacement between two filesystem reads without editing
    # shared source. One byte snapshot must supply both guidance and its hash.
    monkeypatch.setattr(Path, "read_text", interleaved)
    route = dq.family_route("data")
    raw = Path(route["method_path"]).read_bytes()
    assert route["guidance"] == raw.decode().strip()
    assert route["method_digest"] == hashlib.sha256(raw).hexdigest()
