"""Actual verified launcher consumer; no installation or key enrollment."""

from pathlib import Path
import pytest
import release_runtime as runtime
import system_contract
from test_release_runtime import active as runtime_active, replace


@pytest.fixture
def active(tmp_path, monkeypatch):
    return runtime_active.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize(
    "script,dependency",
    [
        (
            "synthesis-agent-conformance/scripts/conformance.py",
            "synthesis-agent-conformance/scripts/live_receipt.py",
        ),
        (
            "synthesis-agent-conformance/scripts/conformance.py",
            "synthesis-agent-conformance/scripts/signed_receipt.py",
        ),
        (
            "synthesis-agent-conformance/scripts/conformance.py",
            "synthesis-onboarding/scripts/system_contract.py",
        ),
        (
            "synthesis-agent-conformance/scripts/conformance.py",
            "synthesis-skills-manager/scripts/cache_guardian.py",
        ),
        (
            "synthesis-agent-conformance/scripts/provider_intake.py",
            "synthesis-agent-conformance/scripts/signed_receipt.py",
        ),
        (
            "synthesis-agent-conformance/scripts/provider_intake.py",
            "synthesis-decision-packet/scripts/build_packet.py",
        ),
        (
            "synthesis-agent-conformance/scripts/provider_intake.py",
            "synthesis-decision-packet/scripts/record_rulings.py",
        ),
    ],
)
@pytest.mark.parametrize("damage", ["missing", "tampered"])
def test_actual_receipt_mode_owner_refuses_missing_or_changed_signed_corpus_helpers(
    active, script, dependency, damage, monkeypatch
):
    pointer, root, data = active
    source = Path(__file__).resolve().parents[3]
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    for relative in names:
        target = root / "skills" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / "skills" / relative).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    # The exact positive owner path, not merely a map membership assertion.
    runtime.command(verified, script, ["--help"])
    target = root / "skills" / dependency
    if damage == "missing":
        target.unlink()
    else:
        target.write_text('raise RuntimeError("synthetic altered helper")\n')
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, ["--help"])


def test_physically_isolated_modular_corpus_packet_owner(tmp_path):
    import json
    import os
    import subprocess
    import sys
    import modular

    source = Path(__file__).resolve().parents[3]
    target = tmp_path / "runtime"
    modular.materialize_payload(source, target, modular.runtime_files(source))
    assert not (target / "skills/synthesis-decision-packet/SKILL.md").exists()
    request = {
        "schema": 1,
        "corpus_id": "fixture",
        "source_kind": "synthetic",
        "members": [{"id": "first", "text": "Synthetic portable condition."}],
    }
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(
                target / "skills/synthesis-agent-conformance/scripts/provider_intake.py"
            ),
            "corpus-packet",
        ],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=20,
        cwd=target,
        env={**os.environ, "PYTHONPATH": ""},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["spec_sha256"]
