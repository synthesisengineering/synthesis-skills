"""Actual verified command owner must bind the newly imported canonical parser."""

from pathlib import Path
import sys
import pytest

PUBLIC = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PUBLIC / "skills/synthesis-onboarding/scripts"))
import release_runtime as runtime  # noqa: E402 - exact source root bound above
import test_release_runtime as runtime_fixtures  # noqa: E402 - exact fixture owner
active = runtime_fixtures.active
replace = runtime_fixtures.replace
import system_contract  # noqa: E402 - exact source root bound above

SCRIPT = "synthesis-message-guard/scripts/message_guard.py"
HELPERS = tuple(
    "synthesis-project-management/scripts/" + name + ".py"
    for name in ("native_git", "claim_scope", "board_grammar", "coordination_schema")
)


def ready(active, monkeypatch):
    pointer, root, data = active
    for relative in (SCRIPT, *HELPERS):
        p = root / "skills" / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((PUBLIC / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {
        name: runtime.file_digest(root / "skills" / name) for name in (SCRIPT, *HELPERS)
    }
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    return verified, root


def test_pinned_peer_runtime_positive(active, monkeypatch):
    verified, root = ready(active, monkeypatch)
    assert runtime.command(verified, SCRIPT, ["--help"])[-1] == "--help"


@pytest.mark.parametrize("helper", HELPERS)
def test_peer_runtime_dependency_drift_refuses_before_command(
    active, monkeypatch, helper
):
    verified, root = ready(active, monkeypatch)
    p = root / "skills" / helper
    p.write_bytes(p.read_bytes() + b"\n# unapproved parser bytes\n")
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, SCRIPT, ["--help"])
