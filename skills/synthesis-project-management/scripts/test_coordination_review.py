"""Independent adversarial tests: exact persistence and positive retry provenance."""

import os
import importlib
import subprocess
import time
import sys
from pathlib import Path
import pytest

PM = Path(__file__).resolve().parent
sys.path.insert(0, str(PM))
C = importlib.import_module("coordination")
W = importlib.import_module("create_worktree")
S = importlib.import_module("claim_scope")
identity_from_uuid = importlib.import_module("coordination_schema").identity_from_uuid


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout


@pytest.fixture
def world(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(
        repo,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "Synthetic",
    )
    i = identity_from_uuid("00000000-0000-7000-8000-000000000001")
    own = C.Session(
        session_uuid=i.session_uuid,
        compact_id=i.compact_id,
        speakable_id=i.speakable_id,
        legacy_id="",
        agent="fixture",
        machine="local",
        client_ref="codex:00000000-0000-4000-8000-000000000011",
        project="synthetic",
        started=C.timestamp(),
        heartbeat=C.timestamp(),
        mode="interactive",
        workspaces=[],
        goal="synthetic",
        claims=[str(repo / "source")],
        context_role="none",
        status="active",
    )
    board = tmp_path / "board.md"
    board.write_text(C.replace_table(C.template(), [own]))
    monkeypatch.setenv("SYNTHESIS_CLIENT_SESSION_REF", own.client_ref)
    return board, own, repo


@pytest.mark.parametrize(
    "name",
    ["double  space", "tab\tspace", "marked`segment`", "piece<br>tail", "trailing "],
)
def test_unrepresentable_creation_token_refuses_without_board_mutation(world, name):
    board, own, repo = world
    before = board.read_bytes()
    target = repo.parent / name
    with pytest.raises(ValueError):
        W.reserve(board, own.compact_id, target, repo, fixture_deadline=time.time() + 120)
    assert board.read_bytes() == before
    assert not target.exists()


@pytest.mark.parametrize("name", ["ordinary", "one space", "unicodé", "piece<BR>tail"])
def test_representable_reservation_preserves_exact_path(world, name):
    board, own, repo = world
    target = repo.parent / name
    receipt = W.reserve(board, own.compact_id, target, repo, fixture_deadline=time.time() + 120)
    assert receipt["reservation"] in C.rows(board.read_text())[0].claims
    assert receipt["target"] == str(target)
    assert not target.exists()


@pytest.mark.parametrize(
    "kind", ["registry-link", "entry-link", "entry-file", "empty-directory"]
)
def test_registry_retry_requires_real_complete_added_registration(tmp_path, kind):
    common = tmp_path / "common"
    common.mkdir()
    (common / "config").write_text("[core]\n")
    scope = S.ClaimScopeResolver()
    before = scope._registry_stamp(str(common))
    registry = common / "worktrees"
    if kind == "registry-link":
        outside = tmp_path / "outside"
        outside.mkdir()
        registry.symlink_to(outside, target_is_directory=True)
        entry = outside / "added"
        entry.mkdir()
    elif kind == "entry-link":
        registry.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        entry = registry / "added"
        entry.symlink_to(outside, target_is_directory=True)
    elif kind == "entry-file":
        registry.mkdir()
        entry = registry / "added"
        entry.write_text("not a registration")
    else:
        registry.mkdir()
        entry = registry / "added"
        entry.mkdir()
    if kind not in ("entry-file", "empty-directory"):
        (entry / "gitdir").write_text("/synthetic/tree/.git\n")
        (entry / "commondir").write_text("../..\n")
    if kind == "entry-file":
        with pytest.raises(S.ClaimIdentityError):
            scope._registry_stamp(str(common))
        return  # Existing refusal is the correct negative control, not a defect.
    after = scope._registry_stamp(str(common))
    assert not S._registry_addition(before, after)


def test_real_worktree_addition_is_retry_positive(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(
        repo,
        "-c",
        "user.name=Synthetic",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--allow-empty",
        "-m",
        "Synthetic",
    )
    scope = S.ClaimScopeResolver()
    common = repo / ".git"
    before = scope._registry_stamp(str(common))
    git(repo, "worktree", "add", "-b", "linked", str(tmp_path / "linked"))
    after = scope._registry_stamp(str(common))
    assert S._registry_addition(before, after)


@pytest.mark.parametrize("signum", [15, 2])
def test_real_signal_interrupts_effect_instead_of_waiting_for_timeout(tmp_path, signum):
    import signal
    import time
    import json

    ready = tmp_path / "ready"
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0,"
        + repr(str(PM))
        + ')\nimport coordination_process as P\ntry:\n P.run([sys.executable,"-c",'
        + repr(
            "import time;from pathlib import Path;Path("
            + repr(str(ready))
            + ').write_text("ready");time.sleep(30)'
        )
        + "],cwd="
        + repr(str(tmp_path))
        + ',timeout=4)\nexcept BaseException as e:\n print(type(e).__name__+":"+str(e),flush=True)\n'
    )
    proc = subprocess.Popen(
        [sys.executable, str(driver)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        limit = time.monotonic() + 2
        while not ready.exists():
            assert proc.poll() is None and time.monotonic() < limit
            time.sleep(0.01)
        start = time.monotonic()
        os.kill(proc.pid, signum)
        out, _ = proc.communicate(timeout=6)
        elapsed = time.monotonic() - start
        (tmp_path / "receipt.json").write_text(
            json.dumps(
                {"output": out, "elapsed": elapsed, "returncode": proc.returncode}
            )
        )
        assert elapsed < 2, (elapsed, out)
        assert "interrupted by signal" in out and "time ceiling" not in out
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)


def test_repeated_cancellation_cannot_interrupt_owned_cleanup(tmp_path):
    import signal
    import time
    import json

    ready = tmp_path / "child.pid"
    driver = tmp_path / "driver.py"
    child = (
        "import os,signal,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path("
        + repr(str(ready))
        + ").write_text(str(os.getpid()));time.sleep(30)"
    )
    driver.write_text(
        "import sys\nsys.path.insert(0,"
        + repr(str(PM))
        + ')\nimport coordination_process as P\ntry:\n P.run([sys.executable,"-c",'
        + repr(child)
        + "],cwd="
        + repr(str(tmp_path))
        + ',timeout=4)\nexcept BaseException as e:\n print(type(e).__name__+":"+str(e),flush=True)\n'
    )
    proc = subprocess.Popen(
        [sys.executable, str(driver)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    child_pid = None
    try:
        limit = time.monotonic() + 2
        while not ready.exists():
            assert proc.poll() is None and time.monotonic() < limit
            time.sleep(0.01)
        child_pid = int(ready.read_text())
        start = time.monotonic()
        os.kill(proc.pid, signal.SIGTERM)
        time.sleep(0.05)
        os.kill(proc.pid, signal.SIGTERM)
        out, _ = proc.communicate(timeout=3)
        (tmp_path / "receipt.json").write_text(
            json.dumps(
                {
                    "output": out,
                    "elapsed": time.monotonic() - start,
                    "returncode": proc.returncode,
                    "child": child_pid,
                }
            )
        )
        assert "EffectInterrupted:coordination effect interrupted by signal" in out
        assert proc.returncode == 0
        with pytest.raises(ProcessLookupError):
            os.killpg(child_pid, 0)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)
        if child_pid:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
