"""First-use contracts through the actual onboarding CLI; no native installation."""

import importlib
import json

import pytest
import synthesis_cli


def test_real_cli_declares_journeys_and_study():
    parser = synthesis_cli.build_parser()
    assert (
        parser.parse_args(["journey", "catalog", "--json"]).journey_command == "catalog"
    )
    assert (
        parser.parse_args(["study", "protocol", "--json"]).study_command == "protocol"
    )


def test_original_five_journeys_and_seven_audiences_are_distinct():
    owner = importlib.import_module("first_run")
    assert set(owner.JOURNEYS) == {
        "portable-project",
        "engineering",
        "writing",
        "work-management",
        "organization",
    }
    assert len(owner.AUDIENCES) == 7
    assert owner.catalog()["default"] == "portable-project"


def test_study_requires_explicit_consent_before_capture(tmp_path):
    owner = importlib.import_module("first_run")
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    with pytest.raises(ContractError, match="consent"):
        owner.study_begin(
            state, "participant", "software-engineer", "portable-project", 7, "no"
        )
    assert not (state.state_dir / "first-run").exists()


def test_study_does_not_accept_raw_personal_content(tmp_path):
    owner = importlib.import_module("first_run")
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    selected = owner.study_plan(
        state, "synthetic", "software-engineer", "portable-project", 7
    )
    study = owner.study_begin(
        state,
        "synthetic",
        "software-engineer",
        "portable-project",
        7,
        selected["digest"],
        consent_plan=selected,
    )
    with pytest.raises(ContractError, match="fields"):
        owner.study_observe(state, study["id"], {"name": "Private Person"})
    assert (
        not json.dumps(owner.study_status(state, study["id"])).find("Private Person")
        >= 0
    )


@pytest.fixture
def journey_source(tmp_path, monkeypatch):
    from test_modular import modular_source

    source, home, env = modular_source.__wrapped__(tmp_path, monkeypatch)
    from system_contract import SystemState

    return source, SystemState(home), env


def _plan(source, state, journey="portable-project"):
    import first_run as owner

    return owner.plan(state, source, journey, ["codex"], stage_core=False)


def _install(source, state, journey="portable-project"):
    import first_run as owner

    planned = _plan(source, state, journey)
    return owner.apply(state, source, planned["id"], planned["plan_digest"])


def _cli(state, capsys, *args):
    assert (
        synthesis_cli.main(
            list(args) + ["--json"],
            state=state,
            engine_runner=lambda *a: pytest.fail("no native/full installer call"),
        )
        == 0
    )
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    "journey",
    ["portable-project", "engineering", "writing", "work-management", "organization"],
)
def test_each_real_journey_installs_exact_modular_selection(journey_source, journey):
    import first_run as owner
    import modular

    source, state, _ = journey_source
    planned = _plan(source, state, journey)
    assert planned["state"] == "planned" and state.read_desired() is None
    assert not (state.home / ".agents/skills").exists()
    installed = owner.apply(state, source, planned["id"], planned["plan_digest"])
    assert installed["state"] == "installed"
    assert installed["doctor"]["report"]["status"] == "PASS"
    assert installed["first_value"] is None
    assert installed["native_live_loading"] == "not-certified"
    assert set(p.name for p in (state.home / ".agents/skills").iterdir()) == set(
        planned["visible_skills"]
    )
    assert set(modular.receipt(state)["selection"]["roots"]) == set(
        owner.JOURNEYS[journey]["roots"]
    )
    for path in (
        state.home / ".codex/config.toml",
        state.home / ".claude/settings.json",
        state.home / "Library/LaunchAgents",
    ):
        assert not path.exists()
    before = state.observation_path.read_bytes()
    assert (
        owner.apply(state, source, planned["id"], planned["plan_digest"])[
            "transaction_id"
        ]
        == installed["transaction_id"]
    )
    assert state.observation_path.read_bytes() == before


def test_real_cli_plan_apply_and_exact_artifact_receipt(journey_source, capsys):
    import hashlib

    source, state, _ = journey_source
    planned = _cli(
        state,
        capsys,
        "journey",
        "plan",
        "--journey",
        "writing",
        "--clients",
        "codex",
        "--no-dormant-core",
    )
    installed = _cli(
        state,
        capsys,
        "journey",
        "apply",
        "--id",
        planned["id"],
        "--consent",
        planned["plan_digest"],
    )
    artifact = state.home / "draft.md"
    artifact.write_text(
        "# Draft\n\nA user supplied sample, revised with their selected method.\n"
    )
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    receipt = _cli(
        state,
        capsys,
        "journey",
        "verify",
        "--id",
        planned["id"],
        "--artifact",
        str(artifact),
        "--sha256",
        checksum,
        "--confirmed-useful",
    )
    assert receipt["artifact_sha256"] == checksum
    assert receipt["transaction_id"] == installed["transaction_id"]
    assert receipt["usefulness"] == "user-attested"
    assert receipt["native_loading"] == "not-certified"
    assert (
        state.read_observation()["transactions"][-1]["outcome-verified"]["status"]
        == "not-requested"
    )
    report = _cli(state, capsys, "journey", "status", "--id", planned["id"])
    assert report["status"] == "CURRENT" and report["first_value"] == receipt


@pytest.mark.parametrize(
    "change", ["wrong-consent", "expired", "desired", "source", "trust", "home"]
)
def test_preflight_refuses_changed_or_unapproved_identity(
    journey_source, monkeypatch, change
):
    import first_run as owner
    from system_contract import ContractError, atomic_write_json, default_desired_state

    source, state, _ = journey_source
    planned = _plan(source, state)
    consent = planned["plan_digest"]
    if change == "wrong-consent":
        consent = "0" * 64
    if change == "expired":
        monkeypatch.setattr(owner, "_now", lambda: planned["expires_at"])
    if change == "desired":
        atomic_write_json(
            state.desired_path,
            default_desired_state("skills-only", ["codex"], "stable"),
        )
    if change == "source":
        (source / "README.md").write_text("changed committed source")
    if change == "trust":
        (state.home / ".codex").mkdir()
        (state.home / ".codex/config.toml").write_text('trust = "changed"\n')
    if change == "home":
        moved = state.home.with_name("prior-home")
        state.home.rename(moved)
        state.home.mkdir()
        # Retain the exact record while changing the machine anchor.
        import shutil

        shutil.copytree(moved / ".local", state.home / ".local")
    with pytest.raises(ContractError):
        owner.apply(state, source, planned["id"], consent)
    assert not (state.home / ".agents/skills").exists()


def test_expiry_is_rechecked_after_installer_lock(journey_source, monkeypatch):
    import first_run as owner
    import modular
    from system_contract import ContractError

    source, state, _ = journey_source
    planned = _plan(source, state)
    original = modular.setup

    def delayed(*a, **kw):
        monkeypatch.setattr(owner, "_now", lambda: planned["expires_at"])
        return original(*a, **kw)

    monkeypatch.setattr(modular, "setup", delayed)
    with pytest.raises(ContractError, match="expired"):
        owner.apply(state, source, planned["id"], planned["plan_digest"])
    assert state.read_desired() is None


def test_crash_after_commit_recovers_exact_transaction_without_replay(
    journey_source, monkeypatch
):
    import first_run as owner
    from first_run_store import Store

    source, state, _ = journey_source
    planned = _plan(source, state)
    original = Store.write

    def interrupted(self, body, **kw):
        if body.get("state") == "installed":
            raise KeyboardInterrupt("synthetic crash after commit")
        return original(self, body, **kw)

    monkeypatch.setattr(Store, "write", interrupted)
    with pytest.raises(KeyboardInterrupt):
        owner.apply(state, source, planned["id"], planned["plan_digest"])
    transactions = state.read_observation()["transactions"]
    assert len(transactions) == 1
    monkeypatch.setattr(Store, "write", original)
    monkeypatch.setattr(owner, "_now", lambda: planned["expires_at"] + 1)
    recovered = owner.apply(state, source, planned["id"], planned["plan_digest"])
    assert recovered["transaction_id"] == transactions[0]["transaction_id"]
    assert len(state.read_observation()["transactions"]) == 1


def test_failed_installer_retains_consent_and_recovers_without_foreign_overwrite(
    journey_source,
):
    import first_run as owner
    from system_contract import ContractError

    source, state, _ = journey_source
    planned = _plan(source, state)
    conflict = state.home / ".agents/skills/synthesis-checkpoint"
    conflict.mkdir(parents=True)
    retained = conflict / "SKILL.md"
    retained.write_text("foreign retained skill")
    with pytest.raises(ContractError):
        owner.apply(state, source, planned["id"], planned["plan_digest"])
    assert retained.read_text() == "foreign retained skill"
    assert owner.status(state, source, planned["id"])["state"] == "consented"
    conflict.rename(conflict.with_name("retained-foreign-skill"))
    recovered = owner.apply(state, source, planned["id"], planned["plan_digest"])
    assert recovered["state"] == "installed"
    assert (
        conflict.with_name("retained-foreign-skill") / "SKILL.md"
    ).read_text() == "foreign retained skill"
    assert [r["state"] for r in state.read_observation()["transactions"]] == [
        "aborted",
        "committed",
    ]


@pytest.mark.parametrize(
    "shape",
    [
        "symlink",
        "fifo",
        "empty",
        "oversize",
        "wrong-digest",
        "not-useful",
        "changed-after",
    ],
)
def test_artifact_negative_controls_preserve_first_value_boundary(
    journey_source, shape
):
    import os
    import hashlib
    import first_run as owner
    from system_contract import ContractError

    source, state, _ = journey_source
    installed = _install(source, state)
    artifact = state.home / "result.md"
    artifact.write_text("A saved real fixture plan.\n")
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if shape == "symlink":
        artifact.rename(state.home / "original.md")
        artifact.symlink_to(state.home / "original.md")
    if shape == "fifo":
        artifact.rename(state.home / "original.md")
        os.mkfifo(artifact)
    if shape == "empty":
        artifact.write_text(" \n")
    if shape == "oversize":
        artifact.write_bytes(b"x" * (1024 * 1024 + 1))
    if shape == "wrong-digest":
        checksum = "0" * 64
    if shape == "changed-after":
        owner.verify_first_value(
            state, source, installed["id"], artifact, checksum, True
        )
        artifact.write_text("Changed later.\n")
        assert owner.status(state, source, installed["id"])["status"] == "STALE"
        return
    with pytest.raises(ContractError):
        owner.verify_first_value(
            state, source, installed["id"], artifact, checksum, shape != "not-useful"
        )
    assert owner.status(state, source, installed["id"])["first_value"] is None


def test_existing_generation_live_outcome_guard_remains_strict(journey_source):
    from system_contract import ContractError

    source, state, _ = journey_source
    _install(source, state)
    with pytest.raises(ContractError, match="live-loaded"):
        state.record_outcome({"task_id": "first-use-artifact-check"})


def _study(tmp_path, sample="synthetic"):
    import first_run as owner
    from system_contract import SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    selected = owner.study_plan(state, sample, "software-engineer", "engineering", 1)
    body = owner.study_begin(
        state,
        sample,
        "software-engineer",
        "engineering",
        1,
        selected["digest"],
        consent_plan=selected,
    )
    return state, body


def _event(body, **change):
    import uuid

    value = {
        "event_id": uuid.uuid4().hex,
        "step": "trust",
        "event": "hesitation",
        "elapsed_ms": 700,
        "observed_at": body["consented_at"],
        "provenance": "synthetic-fixture",
        "witness_sha256": "a" * 64,
        "outcome": "observed",
        "term": None,
        "command": None,
        "command_sha256": None,
        "coaching": "none",
    }
    return {**value, **change}


def test_study_exact_replay_and_withdrawal(tmp_path):
    import first_run as owner
    from system_contract import ContractError

    state, body = _study(tmp_path)
    event = _event(body)
    recorded = owner.study_observe(state, body["id"], event)
    assert recorded["replayed"] is False
    assert owner.study_observe(state, body["id"], event)["replayed"] is True
    with pytest.raises(ContractError, match="identity"):
        owner.study_observe(state, body["id"], {**event, "elapsed_ms": 701})
    status = owner.study_status(state, body["id"])
    assert status["counts"]["trust"] == 1
    assert "first-value" in status["missing_observations"]
    withdrawn = owner.study_end(state, body["id"])
    assert withdrawn["events"] == []
    assert withdrawn["state"] == "withdrawn" and withdrawn["erased_event_count"] == 1
    with pytest.raises(ContractError, match="withdrawn"):
        owner.study_observe(state, body["id"], event)
    assert owner.study_end(state, body["id"]) == withdrawn


@pytest.mark.parametrize(
    "change",
    [
        {"elapsed_ms": True},
        {"elapsed_ms": -1},
        {"elapsed_ms": 86400001},
        {"observed_at": 0},
        {"outcome": "complete and native verified"},
        {"provenance": "participant-report"},
        {"witness_sha256": "not evidence"},
        {"term": "raw private term"},
        {"command": "curl secret"},
        {"coaching": False},
        {"event_id": "../escape"},
        {"step": "unselected"},
        {"event": "unknown"},
    ],
)
def test_study_malformed_observations_refuse_without_capture(tmp_path, change):
    import first_run as owner
    from system_contract import ContractError

    state, body = _study(tmp_path)
    with pytest.raises(ContractError):
        owner.study_observe(state, body["id"], _event(body, **change))
    assert owner.study_status(state, body["id"])["events"] == []


def test_command_copy_and_unexplained_term_have_minimized_provenance(tmp_path):
    import first_run as owner

    state, body = _study(tmp_path)
    command = _event(
        body, event="command-copied", command="journey-plan", command_sha256="b" * 64
    )
    owner.study_observe(state, body["id"], command)
    term = _event(body, event="unexplained-term", term="profile")
    owner.study_observe(state, body["id"], term)
    assert len(owner.study_status(state, body["id"])["events"]) == 2


def test_expired_study_hides_observations_until_explicit_owned_erasure(
    tmp_path, monkeypatch
):
    import first_run as owner
    from system_contract import ContractError

    state, body = _study(tmp_path)
    owner.study_observe(state, body["id"], _event(body))
    path = state.state_dir / "first-run" / ("study-" + body["id"] + ".json")
    before = path.read_bytes()
    monkeypatch.setattr(owner, "_now", lambda: body["expires_at"])
    assert owner.study_status(state, body["id"])["state"] == "retention-due"
    assert path.read_bytes() == before
    with pytest.raises(ContractError):
        owner.study_observe(state, body["id"], _event(body))
    expired = owner.study_end(state, body["id"], expired=True)
    assert expired["events"] == [] and expired["state"] == "expired"


def test_protocol_change_requires_new_consent(tmp_path, monkeypatch):
    import first_run as owner
    from system_contract import ContractError

    state, body = _study(tmp_path)
    monkeypatch.setattr(owner, "study_protocol", lambda: {"digest": "0" * 64})
    with pytest.raises(ContractError, match="protocol"):
        owner.study_observe(state, body["id"], _event(body))


def test_record_symlink_and_tamper_are_refused(tmp_path):
    import first_run as owner
    from system_contract import ContractError

    state, body = _study(tmp_path)
    path = state.state_dir / "first-run" / ("study-" + body["id"] + ".json")
    original = path.with_suffix(".retained")
    path.rename(original)
    path.symlink_to(original)
    with pytest.raises(ContractError):
        owner.study_status(state, body["id"])
    path.unlink()
    path.write_text(original.read_text().replace("engineering", "writing"))
    with pytest.raises(ContractError, match="integrity"):
        owner.study_status(state, body["id"])


def test_hard_exit_during_owned_modular_effect_recovers(journey_source):
    import subprocess
    import sys
    import first_run as owner

    source, state, env = journey_source
    planned = _plan(source, state)
    code = """import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import modular,first_run
from system_contract import SystemState
old=modular.reconcile_bindings
def crash(*a,**kw):
 old(*a,**kw)
 os._exit(23)
modular.reconcile_bindings=crash
first_run.apply(SystemState(Path(sys.argv[2])),Path(sys.argv[3]),sys.argv[4],sys.argv[5])
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(source / "skills/synthesis-onboarding/scripts"),
            str(state.home),
            str(source),
            planned["id"],
            planned["plan_digest"],
        ],
        env=env,
        cwd=state.home,
        capture_output=True,
        timeout=30,
    )
    assert child.returncode == 23, child.stderr
    pending = state.read_observation()["transactions"][-1]
    assert pending["state"] == "pending"
    assert pending["details"]["first_run"]["id"] == planned["id"]
    report = owner.apply(state, source, planned["id"], planned["plan_digest"])
    assert report["state"] == "installed"
    assert [r["state"] for r in state.read_observation()["transactions"]] == [
        "aborted",
        "committed",
    ]
    assert len(list((state.state_dir / "modular").glob("recovered-*.json"))) == 1


def test_existing_profile_is_inspected_without_reinstall(journey_source, monkeypatch):
    import first_run as owner
    import modular
    from system_contract import default_desired_state, ContractError

    source, state, _ = journey_source
    desired = default_desired_state("skills-only", ["codex"], "stable")
    existing = state.run_transaction("setup", desired, lambda _: {})
    before = state.desired_path.read_bytes()
    monkeypatch.setattr(
        modular,
        "setup",
        lambda *a, **k: pytest.fail("existing profile must not be reinstalled"),
    )
    planned = _plan(source, state)
    assert planned["selection_mode"] == "existing"
    calls = []

    def engine(args):
        calls.append(args)
        return 0

    result = owner.apply(
        state, source, planned["id"], planned["plan_digest"], engine_runner=engine
    )
    assert result["state"] == "inspected"
    assert result["transaction_id"] == existing["transaction_id"]
    assert state.desired_path.read_bytes() == before
    assert len(state.read_observation()["transactions"]) == 1
    assert calls and calls[0][0] == "doctor"
    assert (
        result["doctor"]["report"]["status"] == "FAIL"
    )  # No fabricated installation/native proof.
    artifact = state.home / "plan.md"
    artifact.write_text("A fixture plan.\n")
    import hashlib

    with pytest.raises(ContractError, match="diagnostic"):
        owner.verify_first_value(
            state,
            source,
            planned["id"],
            artifact,
            hashlib.sha256(artifact.read_bytes()).hexdigest(),
            True,
            engine_runner=engine,
        )


def test_prepared_study_capture_is_erased_on_withdrawal_and_retry(
    tmp_path, monkeypatch
):
    import os
    import first_run as owner
    import first_run_store as storage

    state, body = _study(tmp_path)
    original = os.replace

    def interrupt(*a, **kw):
        raise KeyboardInterrupt("crash after prepared capture")

    monkeypatch.setattr(storage.os, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        owner.study_observe(state, body["id"], _event(body))
    root = state.state_dir / "first-run"
    preparations = list(root.glob(".study-*.prepared-*"))
    assert len(preparations) == 1
    monkeypatch.setattr(storage.os, "replace", original)
    owner.study_end(state, body["id"])
    assert not list(root.glob(".study-*.prepared-*"))
    assert owner.study_end(state, body["id"])["state"] == "withdrawn"


def test_corrupt_or_foreign_preparation_cannot_be_erased(tmp_path):
    import first_run as owner
    from system_contract import ContractError

    state, body = _study(tmp_path)
    foreign = (
        state.state_dir
        / "first-run"
        / (".study-" + body["id"] + ".json.prepared-" + "f" * 32)
    )
    foreign.write_text("foreign bytes")
    with pytest.raises(ContractError):
        owner.study_end(state, body["id"])
    assert foreign.read_text() == "foreign bytes"
    assert owner.study_status(state, body["id"])["state"] == "consented"


def test_study_record_contains_no_home_path(tmp_path):
    import first_run as owner

    state, body = _study(tmp_path)
    assert str(state.home) not in json.dumps(body)
    assert str(state.home) not in json.dumps(owner.study_status(state, body["id"]))


def test_bounded_first_run_lock_preserves_other_owner(tmp_path, monkeypatch):
    import fcntl
    import os
    import first_run_store as storage
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    store = storage.Store(state)
    with store.locked():
        ticks = iter([0, 11])
        monkeypatch.setattr(storage.time, "monotonic", lambda: next(ticks))
        with pytest.raises(ContractError, match="busy"):
            with storage.Store(state).locked():
                pytest.fail("lock owner was bypassed")
        # Other owner's descriptor remains held.
        fd = os.open(store.path / "owner.lock", os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)


def test_runtime_payload_contains_first_run_owner_without_unselected_entrypoints(
    journey_source, tmp_path
):
    import subprocess
    import sys
    import modular

    source, state, env = journey_source
    planned = modular.resolve_selection(source, ["synthesis-checkpoint"], False)
    target = tmp_path / "isolated"
    modular.materialize_payload(source, target, planned["files"])
    assert (target / "skills/synthesis-onboarding/scripts/first_run.py").is_file()
    assert (target / "skills/synthesis-onboarding/scripts/first_run_store.py").is_file()
    assert not (target / "skills/synthesis-article-writing/SKILL.md").exists()
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(target / "skills/synthesis-onboarding/scripts/synthesis_cli.py"),
            "journey",
            "catalog",
            "--json",
        ],
        cwd=state.home,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["journeys"]) == 5


def test_existing_state_owner_lock_has_finite_refusal(tmp_path, monkeypatch):
    import fcntl
    import system_contract as contract

    home = tmp_path / "home"
    home.mkdir()
    state = contract.SystemState(home)
    original = fcntl.flock

    def busy(fd, flags):
        if flags & fcntl.LOCK_EX:
            raise BlockingIOError("synthetic busy owner")
        return original(fd, flags)

    monkeypatch.setattr(contract.fcntl, "flock", busy)
    if hasattr(contract, "time"):
        ticks = iter([0, 31])
        monkeypatch.setattr(contract.time, "monotonic", lambda: next(ticks))
    with pytest.raises(contract.ContractError, match="busy"):
        with state.locked():
            pytest.fail("busy owner admitted")


@pytest.mark.parametrize(
    "field,value",
    [
        ("retention_days", 30),
        ("audience", "ai-power-user"),
        ("journey", "writing"),
        ("sample", "participant"),
    ],
)
def test_study_consent_cannot_change_selection(tmp_path, field, value):
    import first_run as owner
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    selected = owner.study_plan(
        state, "synthetic", "software-engineer", "engineering", 1
    )
    changed = {**selected, field: value}
    with pytest.raises(ContractError, match="consent"):
        owner.study_begin(
            state,
            changed["sample"],
            changed["audience"],
            changed["journey"],
            changed["retention_days"],
            selected["digest"],
            consent_plan=changed,
        )
    assert not (state.state_dir / "first-run").exists()


def test_exact_study_consent_replay_does_not_renew_or_repeat_enrollment(tmp_path):
    import first_run as owner
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    selected = owner.study_plan(
        state, "synthetic", "software-engineer", "engineering", 1
    )

    def begin():
        return owner.study_begin(
            state,
            "synthetic",
            "software-engineer",
            "engineering",
            1,
            selected["digest"],
            consent_plan=selected,
        )

    first = begin()
    assert begin() == first
    owner.study_end(state, first["id"])
    with pytest.raises(ContractError, match="consumed"):
        begin()
    assert len(list((state.state_dir / "first-run").glob("study-*.json"))) == 1


def test_study_consent_expiry_while_waiting_for_lock_refuses_first_capture(
    tmp_path, monkeypatch
):
    from contextlib import contextmanager
    import first_run as owner
    from first_run_store import Store
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    selected = owner.study_plan(
        state, "synthetic", "software-engineer", "engineering", 1
    )
    original = Store.locked

    @contextmanager
    def delayed(self):
        with original(self) as store:
            monkeypatch.setattr(owner, "_now", lambda: selected["expires_at"])
            yield store

    monkeypatch.setattr(Store, "locked", delayed)
    with pytest.raises(ContractError, match="expired"):
        owner.study_begin(
            state,
            "synthetic",
            "software-engineer",
            "engineering",
            1,
            selected["digest"],
            consent_plan=selected,
        )
    assert not list((state.state_dir / "first-run").glob("study-*.json"))


def test_study_cli_uses_exact_selected_consent_and_local_only_observation(
    tmp_path, capsys
):
    import first_run as owner
    from system_contract import SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    selected = _cli(
        state,
        capsys,
        "study",
        "plan",
        "--sample",
        "synthetic",
        "--audience",
        "ai-power-user",
        "--journey",
        "writing",
        "--retention-days",
        "2",
    )
    path = tmp_path / "consent.json"
    path.write_text(json.dumps(selected))
    body = _cli(
        state,
        capsys,
        "study",
        "begin",
        "--plan",
        str(path),
        "--consent",
        selected["digest"],
    )
    assert body["sample"] == "synthetic" and body["consent"]["plan"] == selected
    event = _event(body)
    observation = tmp_path / "observation.json"
    observation.write_text(json.dumps(event))
    recorded = _cli(
        state,
        capsys,
        "study",
        "observe",
        "--id",
        body["id"],
        "--input",
        str(observation),
    )
    assert recorded["status"] == "RECORDED"
    status = _cli(state, capsys, "study", "status", "--id", body["id"])
    assert status["qualification"] == "synthetic rehearsal only"
    assert owner.study_end(state, body["id"])["events"] == []


def test_replaced_lock_cannot_admit_record_write(tmp_path):
    import uuid
    import first_run_store as storage
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    store = storage.Store(state)
    with store.locked():
        lock = store.path / "owner.lock"
        lock.rename(store.path / "retained-lock")
        lock.write_text("foreign lock")
        body = {"id": uuid.uuid4().hex, "kind": "study", "schema_version": 1}
        with pytest.raises(ContractError, match="lock"):
            store.write(body)
        assert lock.read_text() == "foreign lock"
        assert not (store.path / ("study-" + body["id"] + ".json")).exists()


def test_artifact_replacement_after_descriptor_read_is_refused(tmp_path, monkeypatch):
    import first_run_store as storage
    from system_contract import ContractError

    target = tmp_path / "artifact.md"
    target.write_text("original")
    original = storage.os.read
    replaced = False

    def read(fd, n):
        nonlocal replaced
        b = original(fd, n)
        if b and not replaced:
            replaced = True
            target.rename(tmp_path / "retained.md")
            target.write_text("replacement")
        return b

    monkeypatch.setattr(storage.os, "read", read)
    with pytest.raises(ContractError, match="changed"):
        storage.read_file(target)
    assert target.read_text() == "replacement"


def test_generic_protocol_acknowledgement_cannot_authorize_unbound_retention(tmp_path):
    import first_run as owner
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    generic_protocol = owner.study_protocol()
    with pytest.raises(ContractError, match="consent"):
        owner.study_begin(
            state,
            "participant",
            "ai-power-user",
            "writing",
            30,
            generic_protocol["digest"],
        )
    assert not (state.state_dir / "first-run").exists()


def test_replaced_store_ancestry_refuses_before_record_effect(tmp_path):
    import uuid
    import first_run_store as storage
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    store = storage.Store(state)
    record_id = uuid.uuid4().hex
    retained = tmp_path / "retained-first-run"
    with pytest.raises(ContractError, match="directory|ancestry"):
        with store.locked():
            store.path.rename(retained)
            store.path.mkdir()
            store.write({"id": record_id, "kind": "study", "schema_version": 1})
    assert not (retained / ("study-" + record_id + ".json")).exists()
    assert not (store.path / ("study-" + record_id + ".json")).exists()


def test_study_consent_cannot_be_reused_in_another_state_root(tmp_path, monkeypatch):
    import first_run as owner
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SYNTHESIS_HOME", str(home))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state-one"))
    original = SystemState()
    plan = owner.study_plan(
        original, "synthetic", "software-engineer", "engineering", 1
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state-two"))
    other = SystemState()
    with pytest.raises(ContractError, match="identity"):
        owner.study_begin(
            other,
            "synthetic",
            "software-engineer",
            "engineering",
            1,
            plan["digest"],
            consent_plan=plan,
        )
    assert not (other.state_dir / "first-run").exists()


def test_doctor_capture_stops_at_bound_instead_of_accumulating_then_refusing(
    monkeypatch,
):
    import first_run as owner
    from system_contract import ContractError

    reached = []

    def emit(*args, **kwargs):
        for _ in range(9):
            print("x" * 65536, end="")
        reached.append("after-limit")
        return 0

    monkeypatch.setattr(synthesis_cli, "main", emit)
    with pytest.raises(ContractError, match="output exceeds"):
        owner._diagnose(None, {"selection_mode": "existing"})
    assert reached == []


def test_journey_plan_lifetime_uses_one_admission_timestamp(tmp_path, monkeypatch):
    import first_run as owner
    from first_run_store import Store
    from system_contract import SystemState
    from test_modular import modular_source

    source, home, env = modular_source.__wrapped__(tmp_path, monkeypatch)
    state = SystemState(home)
    times = iter([1790000000, 1790000001])
    monkeypatch.setattr(owner, "_now", lambda: next(times))
    body = owner.plan(
        state, source, "portable-project", ["codex"], stage_core=False, ttl=86400
    )
    assert body["expires_at"] - body["created_at"] == 86400
    with Store(state).locked() as store:
        assert (
            owner._read_journey(store, body["id"])["plan_digest"] == body["plan_digest"]
        )


@pytest.mark.parametrize("component", ["record-directory", "state-directory", "home"])
def test_store_directory_mode_drift_refuses_before_record_effect(tmp_path, component):
    import uuid
    import stat
    import first_run_store as storage
    from system_contract import ContractError, SystemState

    home = tmp_path / "home"
    home.mkdir()
    state = SystemState(home)
    store = storage.Store(state)
    record_id = uuid.uuid4().hex
    with pytest.raises(ContractError, match="directory"):
        with store.locked():
            target = {
                "record-directory": store.path,
                "state-directory": state.state_dir,
                "home": home,
            }[component]
            target.chmod(
                0o755 if stat.S_IMODE(target.stat().st_mode) != 0o755 else 0o700
            )
            store.write({"id": record_id, "kind": "study", "schema_version": 1})
    assert not (store.path / ("study-" + record_id + ".json")).exists()
