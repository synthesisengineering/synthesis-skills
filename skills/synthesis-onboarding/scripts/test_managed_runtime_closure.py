"""Actual activation-receipt owner binds managed permission dependencies."""

from pathlib import Path
import os
import pytest
import release_runtime as runtime
import system_contract
from test_release_runtime import active, replace

__all__ = ["active"]


@pytest.mark.parametrize(
    "script",
    [
        "synthesis-project-management/scripts/team_records.py",
        "synthesis-agent-conformance/scripts/conformance.py",
        "synthesis-agent-conformance/scripts/session_context.py",
    ],
)
@pytest.mark.parametrize(
    "dependency",
    [
        "managed_permissions.py",
        "managed_native.py",
        "native_protection.py",
        "native_codex_turn.py",
    ],
)
@pytest.mark.parametrize("change", ["missing", "same-size-tamper"])
def test_managed_helpers_verified_by_actual_runtime_owner(
    active, monkeypatch, script, dependency, change
):
    pointer, root, data = active
    relative = "synthesis-autopilot/scripts/" + dependency
    names = (script, *runtime.ENTRYPOINT_DEPENDENCIES[script])
    assert relative in names
    source = Path(__file__).resolve().parents[3]
    for name in names:
        p = root / "skills" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((source / "skills" / name).read_bytes())
    replace(pointer, data, content_digest=system_contract.canonical_tree_digest(root))
    verified = runtime.verified_release(pointer)
    verified["_verification_mode"] = runtime.VERIFICATION_MODE_RECEIPT
    hashes = {name: runtime.file_digest(root / "skills" / name) for name in names}
    monkeypatch.setattr(
        runtime, "_load_activation_receipt", lambda _: {"entrypoints": hashes}
    )
    assert runtime.command(verified, script, ["--help"])
    p = root / "skills" / relative
    if change == "missing":
        p.rename(p.with_suffix(".retained-original"))
    else:
        before = p.stat()
        raw = p.read_bytes()
        p.write_bytes(b" " + raw[1:])
        os.utime(p, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(runtime.RuntimeContractError):
        runtime.command(verified, script, ["--help"])
