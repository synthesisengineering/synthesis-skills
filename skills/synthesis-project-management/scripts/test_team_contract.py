"""Neutral team contract: attribution must never impersonate host authorization."""

from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path
import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import team_contract as tc  # noqa: E402 - source-bound import follows path/bootstrap initialization


def contract():
    return {
        "schema": 1,
        "organization": "org-one",
        "deletion_unit": "unit-one",
        "revision": 1,
        "people": [
            {
                "id": "p-one",
                "kind": "human",
                "status": "active",
                "accounts": [
                    {"host": "git.example", "account_id": "101", "username": "alice"}
                ],
                "roles": ["editor"],
            },
            {
                "id": "p-two",
                "kind": "human",
                "status": "active",
                "accounts": [
                    {"host": "git.example", "account_id": "102", "username": "bob"}
                ],
                "roles": ["reviewer"],
            },
            {
                "id": "service-one",
                "kind": "service",
                "status": "active",
                "accounts": [],
                "roles": [],
                "custodians": ["p-one"],
            },
        ],
        "seats": [
            {
                "id": "role-one",
                "organization": "org-one",
                "deletion_unit": "unit-one",
                "occupancies": [
                    {
                        "person": "p-one",
                        "opened": "2026-09-01T00:00:00+00:00",
                        "closed": None,
                    }
                ],
                "covered_by": ["p-two"],
            }
        ],
        "repositories": [
            {
                "id": "repo-one",
                "organization": "org-one",
                "deletion_unit": "unit-one",
                "audience": "shared",
                "readers": ["p-one", "p-two"],
                "remote": "https://git.example/org-one/notes.git",
            }
        ],
        "entitlements": [
            {
                "id": "notes",
                "kind": "knowledge-base",
                "required": True,
                "roles": [],
                "repository": "repo-one",
            },
            {
                "id": "design",
                "kind": "skills",
                "required": False,
                "roles": ["designer"],
            },
        ],
        "policy": {
            "restriction_ids": ["no-secrets", "human-publication"],
            "approval_roles": {"publish": ["reviewer"]},
            "minimum_reader": 6,
        },
        "governance": {
            "channel": "stable",
            "version_pin": "4.149.9",
            "contribution": "review",
            "mirror_owner": "p-one",
            "private_namespace": "principal-id",
            "configuration_root": "user-owned",
        },
    }


def test_valid_contract_and_service_custody():
    assert tc.validate(contract()) == contract()


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["people"].append(copy.deepcopy(d["people"][0])),
        lambda d: d["people"][1]["accounts"][0].update(account_id="101"),
        lambda d: d["people"][2].update(custodians=[]),
        lambda d: d["seats"][0]["occupancies"][0].update(person="service-one"),
        lambda d: d["seats"][0]["occupancies"].append(
            {"person": "p-two", "opened": "2026-09-02T00:00:00+00:00", "closed": None}
        ),
        lambda d: d["seats"][0].update(organization="org-two"),
        lambda d: d["repositories"][0].update(
            remote="https://secret:password@git.example/org/notes.git"
        ),
        lambda d: d["policy"].update(minimum_reader=5),
    ],
)
def test_invalid_contract_refuses(change):
    d = contract()
    change(d)
    with pytest.raises(tc.TeamContractError):
        tc.validate(d)


@pytest.mark.parametrize(
    "client,ref",
    [
        ("codex", "codex:synthetic"),
        ("claude", "cc:synthetic"),
        ("claude", "ccd:local_synthetic"),
        ("muse", "muse:synthetic"),
        ("cursor", "cursor:synthetic"),
        ("copilot", "copilot:synthetic"),
    ],
)
def test_attribution_records_exact_axes_without_auth_claim(client, ref):
    result = tc.attribution(
        contract(),
        person="p-one",
        agent="synthetic-agent",
        client=client,
        machine="machine-one",
        native_ref=ref,
        standing_role="role-one",
    )
    assert result["principal"] == "p-one" and result["native_ref"] == ref
    assert (
        result["authority"] == "attribution-only"
        and result["host_acl_verified"] is False
    )


@pytest.mark.parametrize(
    "override",
    [
        {"person": "missing"},
        {"native_ref": "codex:bad\nref"},
        {"native_ref": "muse:synthetic", "client": "codex"},
        {"standing_role": "undefined"},
    ],
)
def test_identity_negative(override):
    values = dict(
        person="p-one",
        agent="agent",
        client="codex",
        machine="machine-one",
        native_ref="codex:synthetic",
        standing_role="role-one",
    )
    values.update(override)
    with pytest.raises(tc.TeamContractError):
        tc.attribution(contract(), **values)


def test_entitlement_exclusion_is_not_grant_or_error():
    result = tc.entitlement_plan(contract(), "p-one", requested=["notes"])
    assert result["selected"] == ["notes"] and result["excluded"] == ["design"]
    assert result["access_verified"] is False
    with pytest.raises(tc.TeamContractError):
        tc.entitlement_plan(contract(), "p-one", requested=["notes", "design"])


def test_retired_principal_refused_and_account_handles_do_not_bind():
    d = contract()
    d["people"][0]["status"] = "retired"
    with pytest.raises(tc.TeamContractError):
        tc.entitlement_plan(d, "p-one", requested=[])
    d = contract()
    d["people"][0]["accounts"][0]["username"] = "renamed"
    assert tc.account_principal(d, "git.example", "101") == "p-one"


def test_occupancy_transfer_is_one_value_and_preserves_claims():
    d = contract()
    before = copy.deepcopy(d)
    moved = tc.transfer_occupancy(
        d,
        "role-one",
        "p-one",
        "p-two",
        expected_revision=1,
        at="2026-09-26T23:00:00+00:00",
        brief_digest="a" * 64,
    )
    assert d == before and moved["revision"] == 2
    history = moved["seats"][0]["occupancies"]
    assert history[0]["closed"] == history[1]["opened"]
    assert history[1]["person"] == "p-two"
    assert "claims" not in moved
    with pytest.raises(tc.TeamContractError):
        tc.transfer_occupancy(
            d,
            "role-one",
            "p-two",
            "p-one",
            expected_revision=1,
            at="2026-09-26T23:00:00+00:00",
            brief_digest="a" * 64,
        )


def test_private_shared_reference_and_deletion_boundaries():
    shared = contract()["repositories"][0]
    private = {
        **shared,
        "id": "private-one",
        "audience": "private",
        "readers": ["p-one"],
    }
    assert tc.reference_allowed(private, shared)
    assert not tc.reference_allowed(shared, private)
    assert not tc.reference_allowed(
        shared, {**shared, "organization": "org-two", "deletion_unit": "unit-two"}
    )


def test_additive_policy_cannot_expand_approval_roles():
    base = contract()["policy"]
    personal = {
        "restriction_ids": ["no-client-name"],
        "approval_roles": {"publish": ["reviewer"]},
        "minimum_reader": 6,
    }
    merged = tc.compose_policy([base, personal])
    assert set(merged["restriction_ids"]) == {
        "no-secrets",
        "human-publication",
        "no-client-name",
    }
    extra = {**personal, "approval_roles": {"publish": ["editor"]}}
    assert tc.compose_policy([base, extra])["approval_roles"]["publish"] == []
    with pytest.raises(tc.TeamContractError):
        tc.compose_policy([base, {**personal, "allowances": ["human-publication"]}])


def test_offboarding_names_sessions_and_never_releases_them():
    result = tc.offboarding_check(
        contract(),
        "p-one",
        [
            {"principal": "p-one", "session": "s-one", "status": "active"},
            {"principal": "p-two", "session": "s-two", "status": "active"},
        ],
        host_acl_revoked=False,
    )
    assert result["ready"] is False and result["active_sessions"] == ["s-one"]
    assert result["host_acl_revoked"] is False


def test_bounded_source_read_rejects_duplicate_keys_and_links(tmp_path):
    p = tmp_path / "team.json"
    p.write_text(json.dumps(contract()))
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    assert tc.load(p, expected_digest=digest) == contract()
    p.write_text('{"schema":1,"schema":1}')
    with pytest.raises(tc.TeamContractError):
        tc.load(p)
    p.unlink()
    p.symlink_to(tmp_path / "missing")
    with pytest.raises(tc.TeamContractError):
        tc.load(p)


def _team_board(tmp_path):
    import coordination as c

    config = tmp_path / "team-contract.json"
    config.write_text(json.dumps(contract()))
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    board = tmp_path / "board.md"
    text = c.template().replace(
        "## Active sessions",
        f"Team-Contract: team-contract.json @ {digest}\n\n## Active sessions",
    )
    identity = c.new_identity([])
    row = c.Session(
        session_uuid=identity.session_uuid,
        compact_id=identity.compact_id,
        speakable_id=identity.speakable_id,
        legacy_id="",
        agent="agent",
        machine="machine-one",
        project="synthetic",
        started="2026-09-26T00:00:00+00:00",
        heartbeat="2026-09-26T00:00:00+00:00",
        mode="interactive",
        workspaces=[],
        goal="synthetic",
        claims=[],
        context_role="none",
        status="active",
        client_ref="codex:synthetic",
        person="p-one",
        standing_role="role-one",
    )
    text = c.replace_table(text, [row])
    board.write_text(text)
    return c, board, row, text


def test_team_board_roundtrip_and_authenticated_owner_checks_remain(tmp_path):
    c, board, row, text = _team_board(tmp_path)
    c.validate_team_transition(board, text, text)
    parsed = c.rows(text)[0]
    assert parsed.person == "p-one" and parsed.standing_role == "role-one"
    c.locked_update(board, lambda source: source)
    assert board.read_text() == text
    # Person/standing role do not grant native-session ownership.
    assert not c._caller_owns_record(
        parsed,
        c.SelfIdentity(client=c.CLIENT_CODEX, harness_session_id="another"),
        None,
    )


@pytest.mark.parametrize(
    "mutation", ["principal", "source-drift", "declaration-removal", "schema-loss"]
)
def test_team_board_refuses_entire_mutation_without_changing_original(
    tmp_path, mutation
):
    c, board, row, text = _team_board(tmp_path)
    if mutation == "principal":
        row.person = "missing"
        updated = c.replace_table(text, [row])
    elif mutation == "source-drift":
        (tmp_path / "team-contract.json").write_text(
            json.dumps({**contract(), "revision": 2})
        )
        updated = text + "\n"
    elif mutation == "declaration-removal":
        updated = "\n".join(
            line for line in text.splitlines() if not line.startswith("Team-Contract:")
        )
    else:
        with pytest.raises(ValueError, match="silent loss"):
            c.replace_table(text, [row], force_schema=5)
        return
    with pytest.raises(ValueError):
        c.locked_update(board, lambda _: updated)
    assert board.read_text() == text


def test_old_reader_refuses_team_schema_before_rewriting(tmp_path):
    import board_grammar

    c, board, row, text = _team_board(tmp_path)
    with pytest.raises(board_grammar.UnsupportedBoardSchemaError):
        board_grammar.ensure_writable_schema(text, supported=5)


def test_no_team_declaration_does_not_accept_unvalidated_label(tmp_path):
    c, board, row, text = _team_board(tmp_path)
    solo = c.replace_table(c.template(), [row])
    with pytest.raises(ValueError, match="explicitly enrolled"):
        c.validate_team_transition(board, solo, solo)
