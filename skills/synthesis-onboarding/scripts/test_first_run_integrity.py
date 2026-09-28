import json
import uuid
import pytest
import first_run as owner
import first_run_store as storage
from system_contract import SystemState, ContractError


@pytest.fixture
def study(tmp_path, monkeypatch):
    for key in (
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "SYNTHESIS_HOME",
    ):
        monkeypatch.delenv(key, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    plan = owner.study_plan(state, "synthetic", "ai-power-user", "writing", 1)
    body = owner.study_begin(
        state,
        "synthetic",
        "ai-power-user",
        "writing",
        1,
        plan["digest"],
        consent_plan=plan,
    )
    event = {
        "event_id": uuid.uuid4().hex,
        "step": "first-value",
        "event": "completed",
        "elapsed_ms": 900,
        "observed_at": body["consented_at"],
        "provenance": "synthetic-fixture",
        "witness_sha256": "a" * 64,
        "outcome": "pass",
        "term": None,
        "command": None,
        "command_sha256": None,
        "coaching": "none",
    }
    return state, plan, body, event


def replace_receipt(state, body):
    p = state.state_dir / "first-run" / ("study-" + body["id"] + ".json")
    p.write_text(json.dumps({"body": body, "sha256": storage.digest(body)}) + "\n")


def test_positive_exact_event_and_cold_withdrawal(study):
    state, plan, body, event = study
    assert owner.study_observe(state, body["id"], event)["replayed"] is False
    assert owner.study_observe(state, body["id"], event)["replayed"] is True
    other = SystemState(state.home)
    assert owner.study_status(other, body["id"])["events"] == [event]
    assert owner.study_end(other, body["id"])["events"] == []
    with pytest.raises(ContractError):
        owner.study_observe(state, body["id"], event)
    with pytest.raises(ContractError):
        owner.study_begin(
            state,
            "synthetic",
            "ai-power-user",
            "writing",
            1,
            plan["digest"],
            consent_plan=plan,
        )


@pytest.mark.parametrize(
    "mutation", ["extra-private-field", "wrong-provenance", "duplicate-event-id"]
)
def test_status_revalidates_retained_observation_schema(study, mutation):
    state, plan, body, event = study
    owner.study_observe(state, body["id"], event)
    p = state.state_dir / "first-run" / ("study-" + body["id"] + ".json")
    current = json.loads(p.read_text())["body"]
    if mutation == "extra-private-field":
        current["events"][0]["raw_command"] = "PRIVATE_FIXTURE_VALUE"
    elif mutation == "wrong-provenance":
        current["events"][0]["provenance"] = "participant-report"
    else:
        current["events"].append(dict(current["events"][0], elapsed_ms=901))
    replace_receipt(state, current)
    with pytest.raises(ContractError):
        owner.study_status(state, body["id"])


def test_positive_foreign_files_preserved_on_withdrawal(study):
    state, plan, body, event = study
    owner.study_observe(state, body["id"], event)
    foreign = state.state_dir / "first-run" / "foreign.keep"
    foreign.write_text("retained")
    assert owner.study_end(state, body["id"])["events"] == []
    assert foreign.read_text() == "retained"


def test_preparation_scan_refuses_directory_beyond_declared_bound(study, monkeypatch):
    state, plan, body, event = study
    owner.study_observe(state, body["id"], event)
    root = state.state_dir / "first-run"
    for i in range(storage.MAX_RECORDS + 5):
        (root / ("foreign-" + str(i))).write_text("retained")
    before = (root / ("study-" + body["id"] + ".json")).read_bytes()
    with pytest.raises(ContractError):
        owner.study_end(state, body["id"])
    assert (root / ("study-" + body["id"] + ".json")).read_bytes() == before
    assert len(list(root.glob("foreign-*"))) == storage.MAX_RECORDS + 5


def test_positive_expired_status_hides_observations(study, monkeypatch):
    state, plan, body, event = study
    owner.study_observe(state, body["id"], event)
    monkeypatch.setattr(owner, "_now", lambda: body["expires_at"])
    result = owner.study_status(state, body["id"])
    assert result["state"] == "retention-due" and "events" not in result
    with pytest.raises(ContractError):
        owner.study_observe(state, body["id"], event)
    assert owner.study_end(state, body["id"], expired=True)["events"] == []


def test_positive_foreign_preparation_refuses_erasure(study):
    state, plan, body, event = study
    root = state.state_dir / "first-run"
    p = root / (".study-" + body["id"] + ".json.prepared-" + "f" * 32)
    foreign = dict(body, id="e" * 32)
    p.write_text(json.dumps({"body": foreign, "sha256": storage.digest(foreign)}))
    before = p.read_bytes()
    with pytest.raises(ContractError):
        owner.study_end(state, body["id"])
    assert p.read_bytes() == before


def test_valid_withdrawal_after_clock_rollback_keeps_erasure_available(
    study, monkeypatch
):
    state, plan, body, event = study
    owner.study_observe(state, body["id"], event)
    monkeypatch.setattr(owner, "_now", lambda: body["consented_at"] - 1)
    result = owner.study_end(state, body["id"])
    assert result["events"] == []
    assert owner.study_status(state, body["id"])["state"] == "withdrawn"


def test_full_directory_can_erase_its_bounded_crash_preparation(study):
    state, plan, body, event = study
    root = state.state_dir / "first-run"
    for i in range(storage.MAX_RECORDS - 1):
        (root / ("foreign-" + str(i))).write_text("retained")
    prep = root / (".study-" + body["id"] + ".json.prepared-" + "f" * 32)
    prepared = dict(body, events=[event])
    prep.write_text(json.dumps({"body": prepared, "sha256": storage.digest(prepared)}))
    assert owner.study_end(state, body["id"])["state"] == "withdrawn"
    assert not prep.exists()
    assert len(list(root.glob("foreign-*"))) == storage.MAX_RECORDS - 1
