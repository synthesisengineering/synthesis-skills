from pathlib import Path
import importlib.util
import json
import sys
import pytest

P = Path(__file__).resolve().parents[3]
ONBOARDING = P / "skills/synthesis-onboarding/scripts"
sys.path.insert(0, str(ONBOARDING))
import system_contract  # noqa: E402 - register sibling script path first

spec = importlib.util.spec_from_file_location(
    "review_message_guard",
    P / "skills/synthesis-message-guard/scripts/message_guard.py",
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
spec2 = importlib.util.spec_from_file_location(
    "review_contract_fixtures", ONBOARDING / "test_system_contract.py"
)
fixtures = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(fixtures)


@pytest.fixture
def local(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    state = home / ".synthesis/message-guard"
    state.mkdir(parents=True)
    config = state / "patterns.json"
    config.write_bytes(
        (P / "skills/synthesis-message-guard/patterns.example.json").read_bytes()
    )
    monkeypatch.setenv("MESSAGE_GUARD_CONFIG", str(config))
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(state))
    monkeypatch.delenv("MESSAGE_GUARD_CAPABILITIES", raising=False)
    return config, state


def test_actual_activation_refuses_unmigrated_existing_policy(local, tmp_path):
    config, state = local
    root = fixtures.release_repo(tmp_path)
    target = root / "skills/synthesis-message-guard/scripts/message_guard.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(Path(guard.__file__).read_bytes())
    fixtures.git(root, "add", "-A")
    fixtures.git(root, "commit", "-qm", "fixture guard")
    fixtures.git(root, "branch", "-f", "stable")
    fixtures.git(root, "tag", "-f", "v9.8.7")
    descriptor = system_contract.release_descriptor_from_checkout(
        root, "stable", "stable", "https://example.test/fixture.git"
    )
    release = fixtures.materialized_fixture(root, tmp_path)
    launcher = tmp_path / "bin/synthesis"
    active = tmp_path / "active.json"
    with pytest.raises(system_contract.ContractError, match="migration"):
        system_contract.activate_cli(release, descriptor, launcher, active)
    assert not active.exists() and not launcher.exists()


def test_preflight_rejects_implicit_old_policy(local):
    config, state = local
    data = json.loads(config.read_text())
    data.pop("email_policy", None)
    config.write_text(json.dumps(data))
    result = guard.migration_preflight()
    assert result["status"] == "REFUSED"
    assert result["policy_gaps"]
    assert not (state / "engine-migration.json").exists()


def test_preflight_unconfigured_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setenv("MESSAGE_GUARD_CONFIG", str(tmp_path / "absent.json"))
    monkeypatch.setenv("MESSAGE_GUARD_STATE_DIR", str(tmp_path / "state"))
    assert guard.migration_preflight()["status"] == "NOT_CONFIGURED"


def prepare_record(local):
    config, state = local
    cfg = json.loads(config.read_text())
    cfg["message_capabilities"] = [
        {"tool_names": ["fixture.send"], "channel": "human-text"}
    ]
    config.write_text(json.dumps(cfg))
    plan = guard.migration_preflight(plan=True)
    assert plan["status"] == "OWNER_REVIEW_REQUIRED", plan
    record = plan["required_record"]
    record["owner_review"] = {
        "source": "synthetic-fixture-owner-review",
        "reviewed_at": "2026-09-25T00:00:00+00:00",
    }
    (state / "engine-migration.json").write_text(json.dumps(record))
    return record


def test_owner_preflight_preserves_pending_and_asserts_no_native_or_provider_completion(
    local,
):
    config, state = local
    (state / "ledger").mkdir()
    pending = state / "ledger/legacy.json"
    pending.write_text('{"text_sha256":"old","source":"synthetic"}')
    before = pending.read_bytes()
    prepare_record(local)
    result = guard.migration_preflight()
    assert result["status"] == "READY_FOR_OWNER_ACTIVATION", result
    assert result["pending_count"] == 1
    assert pending.read_bytes() == before
    assert result["provider_drafts"] == "NOT_INSPECTED"
    assert result["native_catalog_coverage"] == "NOT_ESTABLISHED"
    assert result["message_authority_granted"] is False


@pytest.mark.parametrize(
    "change",
    [
        "config",
        "pending-added",
        "pending-edited",
        "engine-hash",
        "receipt-link",
        "ledger-link",
        "receipt-duplicate",
        "schema-bool",
    ],
)
def test_migration_refuses_stale_or_aliased_custody(local, tmp_path, change):
    config, state = local
    (state / "ledger").mkdir()
    pending = state / "ledger/original.json"
    pending.write_text("synthetic original")
    record = prepare_record(local)
    receipt = state / "engine-migration.json"
    if change == "config":
        config.write_text(config.read_text() + " ")
    elif change == "pending-added":
        (state / "ledger/new.json").write_text("new")
    elif change == "pending-edited":
        pending.write_text("changed")
    elif change == "engine-hash":
        record["engine_sha256"] = "0" * 64
        receipt.write_text(json.dumps(record))
    elif change == "receipt-link":
        raw = receipt.read_bytes()
        receipt.unlink()
        foreign = tmp_path / "foreign"
        foreign.write_bytes(raw)
        receipt.symlink_to(foreign)
    elif change == "ledger-link":
        pending.unlink()
        foreign = tmp_path / "foreign"
        foreign.write_text("synthetic original")
        pending.symlink_to(foreign)
    elif change == "receipt-duplicate":
        receipt.write_text(receipt.read_text()[:-1] + ',"schema":1}')
    else:
        record["schema"] = True
        receipt.write_text(json.dumps(record))
    result = guard.migration_preflight()
    assert result["status"] == "REFUSED", result
    assert pending.exists()


def test_actual_activation_requires_and_accepts_bound_owner_record(local, tmp_path):
    prepare_record(local)
    root = fixtures.release_repo(tmp_path)
    target = root / "skills/synthesis-message-guard/scripts/message_guard.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(Path(guard.__file__).read_bytes())
    fixtures.git(root, "add", "-A")
    fixtures.git(root, "commit", "-qm", "fixture guard")
    fixtures.git(root, "branch", "-f", "stable")
    fixtures.git(root, "tag", "-f", "v9.8.7")
    descriptor = system_contract.release_descriptor_from_checkout(
        root, "stable", "stable", "https://example.test/fixture.git"
    )
    release = fixtures.materialized_fixture(root, tmp_path)
    launcher = tmp_path / "bin/synthesis"
    active = tmp_path / "active.json"
    system_contract.activate_cli(release, descriptor, launcher, active)
    assert active.exists() and launcher.exists()


def test_owner_plan_does_not_write_a_receipt(local):
    config, state = local
    cfg = json.loads(config.read_text())
    cfg["message_capabilities"] = [
        {"tool_names": ["fixture.send"], "channel": "human-text"}
    ]
    config.write_text(json.dumps(cfg))
    before = {
        p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()
    }
    assert guard.migration_preflight(plan=True)["status"] == "OWNER_REVIEW_REQUIRED"
    assert {
        p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()
    } == before


def test_release_preflight_refuses_before_any_other_release_effect(local, monkeypatch):
    sys.path.insert(0, str(P / "skills/synthesis-skills-manager/scripts"))
    import release

    result = release.Result()

    def unexpected(*args, **kwargs):
        raise AssertionError("release progressed past migration refusal")

    monkeypatch.setattr(release, "source_version", unexpected)
    assert release.preflight(P, result, False) is None
    assert result.steps[0].name == "preflight.message-guard-migration"
    assert result.steps[0].ok is False


@pytest.mark.parametrize(
    "capability",
    [
        {"tool_names": ["fixture.email"], "channel": "email", "body_field": "body"},
        {
            "tool_names": ["fixture.email"],
            "channel": "email",
            "format_field": "body_format",
        },
    ],
)
def test_preflight_refuses_unusable_email_mapping(local, capability):
    config, state = local
    cfg = json.loads(config.read_text())
    cfg["message_capabilities"] = [capability]
    config.write_text(json.dumps(cfg))
    result = guard.migration_preflight(plan=True)
    assert result["status"] == "REFUSED"
    assert result["policy_gaps"]


def test_unsupported_fixed_plain_transport_is_explicit_without_weakening_default(local):
    config, state = local
    cfg = json.loads(config.read_text())
    apple = "mcp__apple-mail__send_email"
    gmail = "mcp__workspace-mcp__send_gmail_message"
    cfg["message_capabilities"] = [
        {
            "tool_names": [apple],
            "channel": "email",
            "body_field": "body",
            "fixed_format": "plain",
        },
        {
            "tool_names": [gmail],
            "channel": "email",
            "body_field": "body",
            "format_field": "body_format",
        },
    ]
    config.write_text(json.dumps(cfg))
    plan = guard.migration_preflight(plan=True)
    assert plan["status"] == "OWNER_REVIEW_REQUIRED", plan
    assert plan["unsupported_transports"][0]["tools"] == [apple]
    record = plan["required_record"]
    record["owner_review"] = {
        "source": "synthetic explicit unavailable-transport disposition",
        "reviewed_at": "2026-09-25T00:00:00Z",
    }
    (state / "engine-migration.json").write_text(json.dumps(record))
    ready = guard.migration_preflight()
    assert ready["status"] == "READY_FOR_OWNER_ACTIVATION", ready
    assert guard.email_policy(cfg)["default_format"] == "html"
    assert guard.email_format_failures(apple, {"body": "Synthetic paragraph."}, cfg)
    assert not guard.email_format_failures(
        gmail, {"body": "<p>Synthetic paragraph.</p>", "body_format": "html"}, cfg
    )
