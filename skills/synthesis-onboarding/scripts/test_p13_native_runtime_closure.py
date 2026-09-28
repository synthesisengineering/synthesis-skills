"""Real receipt owner checks every route importing the shared native identity."""
import pytest
import release_runtime as runtime
import system_contract
import test_release_runtime as fixtures
active = fixtures.active
replace = fixtures.replace


@pytest.mark.parametrize("script", [
    "synthesis-agent-conformance/scripts/conformance.py",
    "synthesis-agent-conformance/scripts/session_context.py",
    "synthesis-onboarding/scripts/synthesis_cli.py",
    "synthesis-repo-guard/checkpoint_sync.py",
    "synthesis-project-management/scripts/board_inbox.py",
    "synthesis-project-management/scripts/peer_send_gate.py",
    "synthesis-project-management/scripts/contribution_evidence.py",
    "synthesis-project-management/scripts/project_state.py",
])
def test_shared_native_helper_is_pinned_by_actual_receipt_owner(active, monkeypatch, script):
    pointer, root, data = active
    dependency = "synthesis-project-management/scripts/native_identity.py"
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    assert dependency in names
    for name in names:
        p = root / "skills" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("pass\n")
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes})
    runtime.verify_dependencies(verified, script)
    (root / "skills" / dependency).write_text('raise RuntimeError("unreviewed")\n')
    with pytest.raises(runtime.RuntimeContractError):
        runtime.verify_dependencies(verified, script)
