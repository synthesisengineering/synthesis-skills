from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_retire_worktree import SCRIPT, CHECKPOINT_SCRIPT, _claim_row, _row_cells, add_feature_worktree, build_repo, git


def source_in_target(tmp_path):
    _, clone = build_repo(tmp_path)
    worktree = add_feature_worktree(tmp_path, clone)
    pm = worktree / "skills/synthesis-project-management"
    shutil.copytree(SCRIPT.parent, pm / "scripts", ignore=shutil.ignore_patterns("__pycache__", "test_*"))
    shutil.copytree(SCRIPT.parent.parent / "references", pm / "references")
    conformance = worktree / "skills/synthesis-agent-conformance/scripts"
    conformance.mkdir(parents=True)
    for name in ("native_transcript_identity.py", "client_binaries.py"):
        shutil.copy2(SCRIPT.parents[2] / "synthesis-agent-conformance/scripts" / name, conformance / name)
    guard = worktree / "skills/synthesis-repo-guard"
    guard.mkdir()
    shutil.copy2(CHECKPOINT_SCRIPT, guard / "checkpoint_sync.py")
    (worktree / "change.txt").write_text("synthetic work\n")
    git(worktree, "add", ".")
    git(worktree, "commit", "-qm", "synthetic source")
    git(worktree, "push", "-qu", "origin", "feature/demo")
    git(clone, "merge", "--quiet", "--no-edit", "feature/demo")
    git(clone, "push", "-q", "origin", "main")
    board = tmp_path / "coordination/active-sessions.md"
    row = _claim_row(board, {"SYNTHESIS_CLIENT_SESSION_REF": "codex:00000000-0000-4000-8000-000000000001"}, [f"{worktree} @ feature/demo", f"{clone} @ main"],
                     [str(worktree / "change.txt"), str(clone / "seed.txt")])
    env = dict(os.environ, SYNTHESIS_HOME=str(tmp_path / "synthesis-home"),
               SYNTHESIS_CLIENT_SESSION_REF="codex:00000000-0000-4000-8000-000000000001", SYNTHESIS_COORDINATION_SESSION=row["compact_id"],
               PYTHONDONTWRITEBYTECODE="1", CODEX_THREAD_ID="00000000-0000-4000-8000-000000000001")
    target_helper = pm / "scripts/retire_worktree.py"
    cmd = [sys.executable, str(target_helper), "--repository", str(clone),
           "--worktree", str(worktree), "--board", str(board)]
    return clone, worktree, board, row, env, cmd


def capture(tmp_path, name, command, env, cwd):
    result = subprocess.run(command, env=env, cwd=cwd, capture_output=True, text=True, timeout=60)
    (tmp_path / (name + ".stdout")).write_text(result.stdout)
    (tmp_path / (name + ".stderr")).write_text(result.stderr)
    (tmp_path / (name + ".json")).write_text(json.dumps({"command": command, "returncode": result.returncode}))
    return result


def test_authenticated_complete_source_can_retire_itself(tmp_path):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    positive = capture(tmp_path, "preflight", [sys.executable, str(Path(cmd[1]).with_name("coordination.py")),
                         "--board", str(board), "whoami", "--json"], env, clone)
    assert positive.returncode == 0, positive.stderr
    assert json.loads(positive.stdout)["row"]["session"] == row["compact_id"]
    (tmp_path / "board-before.md").write_bytes(board.read_bytes())
    result = capture(tmp_path, "retire", cmd, env, clone)
    (tmp_path / "board-after.md").write_bytes(board.read_bytes())
    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert _row_cells(board) == ([str(clone / "seed.txt")], [f"{clone} @ main"])


def test_source_dependency_set_matches_existing_runtime_payload_owner():
    """One closed release owner; the retirement subset may not silently drift."""
    import ast
    import retirement_runtime as runtime
    payload = SCRIPT.parents[2] / "synthesis-onboarding/scripts/runtime_payload.py"
    tree = ast.parse(payload.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_specs")
    names = next(ast.literal_eval(node.iter) for node in ast.walk(function)
                 if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple)
                 and any(isinstance(item, ast.Constant) and item.value == "coordination.py" for item in node.iter.elts))
    assert set(names) == set(runtime.COORDINATION_SCRIPTS)


@pytest.mark.parametrize("native", [
    {"SYNTHESIS_CLIENT_SESSION_REF": "codex:00000000-0000-4000-8000-000000000001"},
    {"SYNTHESIS_CLIENT_SESSION_REF": "muse:00000000-0000-4000-8000-000000000001"},
    {"SYNTHESIS_CLIENT_SESSION_REF": "test:caller", "CLAUDE_CODE_SESSION_ID": "native-claude-fixture"},
])
def test_native_clients_complete_own_source_without_bytecode_side_effects(tmp_path, native):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    # Allocate a fresh board for this exact native identity; never adopt the
    # existing Codex fixture seat or edit its sidecar.
    alternate = tmp_path / "alternate-board/active-sessions.md"
    alternate_row = _claim_row(alternate, native, [f"{target} @ feature/demo"], [str(target / "change.txt")])
    env.update(native, SYNTHESIS_COORDINATION_SESSION=alternate_row["compact_id"])
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    cmd[-1] = str(alternate)
    before = board.read_bytes()
    result = capture(tmp_path, "native-retire", cmd, env, clone)
    assert result.returncode == 0, result.stderr
    assert not target.exists()
    assert board.read_bytes() == before
    assert _row_cells(alternate) == ([], [])


@pytest.mark.parametrize("problem", ["missing", "symlink", "hardlink", "writable", "fifo"])
def test_bad_source_dependency_refuses_before_removal(tmp_path, problem):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    member = Path(cmd[1]).with_name("peer_addressing.py")
    saved = tmp_path / "retained-member.py"
    member.rename(saved)
    if problem == "symlink":
        member.symlink_to(saved)
    elif problem == "hardlink":
        os.link(saved, member)
    elif problem == "writable":
        shutil.copy2(saved, member)
        member.chmod(0o666)
    elif problem == "fifo":
        os.mkfifo(member)
    # Git's clean-tree check itself rejects several unsafe entries. It must
    # always leave the target and board untouched; direct stage tests below
    # cover source-member checks independently of that earlier guard.
    before = board.read_bytes()
    result = capture(tmp_path, "unsafe-source", cmd, env, clone)
    assert result.returncode != 0
    assert target.exists() and board.read_bytes() == before
    assert not list((tmp_path / "synthesis-home/repo-guard/retired-worktrees").glob("*.json"))


@pytest.mark.parametrize("problem", ["missing", "symlink", "hardlink", "writable", "fifo", "bytes", "extra", "directory-link"])
def test_retained_runtime_refuses_changed_members(tmp_path, problem):
    import retirement_runtime as runtime
    store = tmp_path / "store"
    digest = runtime.stage(SCRIPT.parent.parent, store)
    root = store / ("coordination-" + digest)
    member = root / "scripts/coordination.py"
    if problem == "extra":
        (root / "scripts/extra.py").write_text("raise RuntimeError('not authorized')")
    elif problem == "directory-link":
        scripts = root / "scripts"
        saved = tmp_path / "retained-scripts"
        scripts.rename(saved)
        scripts.symlink_to(saved, target_is_directory=True)
    elif problem == "writable":
        member.chmod(0o666)
    elif problem == "bytes":
        member.chmod(0o600)
        member.write_text("raise RuntimeError('changed source must never run')")
        member.chmod(0o400)
    else:
        saved = tmp_path / "retained-original.py"
        member.rename(saved)
        if problem == "symlink":
            member.symlink_to(saved)
        elif problem == "hardlink":
            os.link(saved, member)
        elif problem == "fifo":
            os.mkfifo(member)
    with pytest.raises((ValueError, OSError)):
        runtime.verify(store, digest)
    with pytest.raises((ValueError, OSError)):
        runtime.stage(SCRIPT.parent.parent, store)


@pytest.mark.parametrize("problem", ["wrong-native", "missing-identity", "wrong-selector", "board-alias"])
def test_native_preflight_refuses_wrong_owner_without_removing_target(tmp_path, problem):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    if problem == "wrong-native":
        env["SYNTHESIS_CLIENT_SESSION_REF"] = "codex:00000000-0000-4000-8000-000000000002"
    elif problem == "missing-identity":
        env.pop("SYNTHESIS_CLIENT_SESSION_REF")
    elif problem == "wrong-selector":
        env["SYNTHESIS_COORDINATION_SESSION"] = "s-0000-0000-0000"
    else:
        alias = tmp_path / "board-alias.md"
        alias.symlink_to(board)
        cmd[-1] = str(alias)
    before = board.read_bytes()
    result = capture(tmp_path, "wrong-owner", cmd, env, clone)
    assert result.returncode != 0
    assert target.exists() and board.read_bytes() == before


@pytest.mark.parametrize("signal_name", ["SIGTERM", "SIGINT"])
def test_real_interruption_retains_runtime_and_exact_owner_retry(tmp_path, signal_name):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    driver = tmp_path / "interrupt_driver.py"
    driver.write_text('''import importlib.util, os, signal, sys
from pathlib import Path
helper = Path(sys.argv.pop(1))
spec = importlib.util.spec_from_file_location("retire_fixture", helper)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module.run_reconciler
def interrupted(executable, args, *rest, **kwargs):
    if "--complete-worktree-retirement" in args:
        assert not Path(sys.argv[sys.argv.index("--worktree") + 1]).exists()
        os.kill(os.getpid(), getattr(signal, os.environ["FIXTURE_SIGNAL"]))
    return original(executable, args, *rest, **kwargs)
module.run_reconciler = interrupted
raise SystemExit(module.main())
''')
    interrupted = capture(tmp_path, "interrupted", [sys.executable, str(driver), *cmd[1:]],
                          dict(env, FIXTURE_SIGNAL=signal_name), clone)
    assert interrupted.returncode != 0 and not target.exists(), interrupted.stderr
    intents = list((tmp_path / "synthesis-home/repo-guard/retired-worktrees").glob("*.json"))
    assert len(intents) == 1
    intent = json.loads(intents[0].read_text())
    assert intent["state"] == "prepared" and intent["claims_runtime"]["session_uuid"] == row["session_uuid"]
    before = board.read_bytes()
    # The retry orchestrator has no coordination.py to fall back to. Its pinned
    # runtime, not any available live checkout, must perform the operation.
    retry = tmp_path / "retry/skills/synthesis-project-management/scripts"
    retry.mkdir(parents=True)
    for name in ("retire_worktree.py", "retirement_runtime.py"):
        shutil.copy2(SCRIPT.with_name(name), retry / name)
    retry_cmd = [sys.executable, str(retry / "retire_worktree.py"), *cmd[2:]]
    wrong = capture(tmp_path, "foreign-retry", retry_cmd,
                    dict(env, SYNTHESIS_CLIENT_SESSION_REF="codex:00000000-0000-4000-8000-000000000002"), clone)
    assert wrong.returncode != 0 and board.read_bytes() == before
    result = capture(tmp_path, "owned-retry", retry_cmd, env, clone)
    assert result.returncode == 0, result.stderr
    assert _row_cells(board) == ([str(clone / "seed.txt")], [f"{clone} @ main"])
    after = board.read_bytes()
    again = capture(tmp_path, "idempotent-retry", retry_cmd, env, clone)
    assert again.returncode == 0, again.stderr
    assert board.read_bytes() == after


def test_staged_runtime_store_alias_is_refused(tmp_path):
    import retirement_runtime as runtime
    real = tmp_path / "actual"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        runtime.stage(SCRIPT.parent.parent, alias)
    assert not list(real.iterdir())


def test_runtime_capacities_are_enforced(tmp_path, monkeypatch):
    import retirement_runtime as runtime
    monkeypatch.setattr(runtime, "MAX_TOTAL", 10)
    with pytest.raises(ValueError, match="aggregate capacity"):
        runtime.stage(SCRIPT.parent.parent, tmp_path / "store")
    assert not list((tmp_path / "store").iterdir())


@pytest.mark.parametrize("phase", ["prepare", "complete"])
@pytest.mark.parametrize("corruption", ["bytes", "missing"])
def test_late_runtime_damage_remains_incomplete_and_never_adopts_live_source(tmp_path, phase, corruption):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    driver = tmp_path / "damage_driver.py"
    driver.write_text('''import importlib.util, json, os, sys
from pathlib import Path
helper = Path(sys.argv.pop(1))
spec = importlib.util.spec_from_file_location("retire_fixture", helper)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
original = module.run_reconciler
changed = False
def damage(executable, args, *rest, **kwargs):
    global changed
    result = original(executable, args, *rest, **kwargs)
    if not changed and "--" + os.environ["FIXTURE_PHASE"] + "-worktree-retirement" in args:
        changed = True
        intent = next(module.RETIREMENT_DIR.glob("*.json"))
        data = json.loads(intent.read_text())
        member = module.RETIREMENT_RUNTIME_DIR / ("coordination-" + data["claims_runtime"]["sha256"]) / "scripts/peer_addressing.py"
        retained = Path(os.environ["FIXTURE_RETAINED"])
        member.rename(retained)
        if os.environ["FIXTURE_CORRUPTION"] == "bytes":
            member.write_text("raise RuntimeError('untrusted altered runtime')")
            member.chmod(0o400)
    return result
module.run_reconciler = damage
raise SystemExit(module.main())
''')
    before = board.read_bytes()
    result = capture(tmp_path, "late-damage", [sys.executable, str(driver), *cmd[1:]],
        dict(env, FIXTURE_PHASE=phase, FIXTURE_CORRUPTION=corruption,
             FIXTURE_RETAINED=str(tmp_path / "retained-runtime-member.py")), clone)
    assert result.returncode != 0
    assert target.exists() is (phase == "prepare")
    assert board.read_bytes() == before
    intent_path = next((tmp_path / "synthesis-home/repo-guard/retired-worktrees").glob("*.json"))
    intent = json.loads(intent_path.read_text())
    assert intent["state"] == ("prepared" if phase == "prepare" else "completed")
    assert git(clone, "branch", "--list", "feature/demo").stdout.strip()
    # An intact current source is present in the main clone, but cannot mask
    # the damaged pinned runtime on retry.
    retry = [sys.executable, str(SCRIPT), *cmd[2:]]
    repeated = capture(tmp_path, "damage-retry", retry, env, clone)
    assert repeated.returncode != 0 and board.read_bytes() == before


def test_lifecycle_contention_refuses_boundedly_and_retry_completes(tmp_path):
    import fcntl
    import time
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    state = tmp_path / "synthesis-home/repo-guard"
    state.mkdir(parents=True)
    lock = (state / "lifecycle.lock").open("a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        before = board.read_bytes()
        started = time.monotonic()
        result = capture(tmp_path, "contended", cmd, env, clone)
        elapsed = time.monotonic() - started
        assert result.returncode != 0 and "lock is busy" in result.stderr
        assert 4 <= elapsed < 12
        assert target.exists() and board.read_bytes() == before
    finally:
        lock.close()
    completed = capture(tmp_path, "after-contention", cmd, env, clone)
    assert completed.returncode == 0, completed.stderr
    assert not target.exists()


def test_runtime_state_cannot_be_created_inside_retiring_target(tmp_path):
    clone, target, board, row, env, cmd = source_in_target(tmp_path)
    (target / ".gitignore").write_text(".retirement-state/\n")
    git(target, "add", ".gitignore")
    git(target, "commit", "-qm", "synthetic ignore rule")
    git(target, "push", "-q", "origin", "feature/demo")
    git(clone, "merge", "--quiet", "--no-edit", "feature/demo")
    git(clone, "push", "-q", "origin", "main")
    env["SYNTHESIS_HOME"] = str(target / ".retirement-state")
    before = board.read_bytes()
    result = capture(tmp_path, "inside-state", cmd, env, clone)
    assert result.returncode != 0
    assert target.exists(), "retirement must not erase its own retained runtime and intent"
    assert board.read_bytes() == before
    assert not (target / ".retirement-state").exists()


@pytest.mark.parametrize("problem", ["missing", "symlink", "hardlink", "writable", "fifo"])
def test_runtime_bootstrap_refuses_unsafe_owner(tmp_path, monkeypatch, problem):
    from test_retire_worktree import MODULE
    helper = tmp_path / "retire_worktree.py"
    helper.write_text("# synthetic helper location\n")
    owner = tmp_path / "retirement_runtime.py"
    sentinel = tmp_path / "must-not-execute"
    content = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('unsafe execution')\n"
    retained = tmp_path / "retained.py"
    retained.write_text(content)
    if problem == "symlink":
        owner.symlink_to(retained)
    elif problem == "hardlink":
        os.link(retained, owner)
    elif problem == "writable":
        owner.write_text(content)
        owner.chmod(0o666)
    elif problem == "fifo":
        os.mkfifo(owner)
    monkeypatch.setattr(MODULE, "__file__", str(helper))
    monkeypatch.setattr(MODULE, "_RETIREMENT_RUNTIME", None)
    with pytest.raises((ValueError, OSError)):
        MODULE.retirement_runtime_owner()
    assert not sentinel.exists()


def test_state_preflight_checks_actual_ancestor_identity(tmp_path, monkeypatch):
    from test_retire_worktree import MODULE
    target = tmp_path / "target"
    target.mkdir()
    monkeypatch.setattr(MODULE, "STATE_DIR", tmp_path / "different-spelling/new-state")
    original = os.path.samefile
    def same_identity(left, right):
        # Exercise filesystems that expose another spelling of an existing
        # ancestor. The decisive guard is directory identity, not string prefix.
        return True if Path(left) == tmp_path else original(left, right)
    monkeypatch.setattr(os.path, "samefile", same_identity)
    with pytest.raises(ValueError, match="outside the target"):
        MODULE.require_surviving_retirement_state(target)


def test_retained_runtime_covers_all_coordinator_python_imports():
    """Audit eager and lazy imports, including the cross-skill Muse resolver."""
    import ast
    import retirement_runtime as runtime
    modules = {Path(name).stem: runtime.source_member(SCRIPT.parent.parent, name)
               for name in runtime.MEMBERS if name.endswith('.py')}
    pending, visited = ['coordination'], set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        for node in ast.walk(ast.parse(modules[name].read_bytes())):
            imported = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                        else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for value in imported:
                dependency = value.split('.')[0]
                if dependency not in sys.stdlib_module_names and dependency != '__future__':
                    assert dependency in modules, (name, dependency)
                    pending.append(dependency)
    assert 'native_transcript_identity' in visited and 'project_recipient' in visited


def test_admission_reexports_canonical_lock_identity_without_duplicate_implementation():
    import ast
    import coordination_lock
    import run_admission
    assert run_admission.bounded_lock is coordination_lock.bounded_lock
    assert run_admission.AdmissionError is coordination_lock.AdmissionError
    nodes = ast.parse(Path(run_admission.__file__).read_text()).body
    assert not any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in
                   {'bounded_lock', 'AdmissionError'} for node in nodes)
    assert all((node.module or '').split('.')[0] in sys.stdlib_module_names | {'__future__'}
               for node in ast.parse(Path(coordination_lock.__file__).read_text()).body
               if isinstance(node, ast.ImportFrom))


@pytest.mark.parametrize("damage", ["missing", "symlink", "hardlink", "writable", "fifo"])
def test_source_storage_detail_refuses_unsafe_member(tmp_path, damage):
    import retirement_runtime as runtime
    source = tmp_path / "source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    retained = tmp_path / "retained.py"
    sentinel = tmp_path / "must-not-execute"
    retained.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('unsafe')\n")
    target = scripts / "fleet_paths.py"
    if damage == "symlink":
        target.symlink_to(retained)
    elif damage == "hardlink":
        os.link(retained, target)
    elif damage == "writable":
        shutil.copy2(retained, target)
        target.chmod(0o666)
    elif damage == "fifo":
        os.mkfifo(target)
    with pytest.raises((OSError, ValueError)):
        runtime.source_storage_detail(source, tmp_path / "worktree", {}, "missing")
    assert not sentinel.exists()


def test_source_storage_detail_retains_canonical_text_and_module_custody(tmp_path):
    import retirement_runtime as runtime
    import fleet_paths
    source = tmp_path / "source"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(SCRIPT.with_name("fleet_paths.py"), scripts / "fleet_paths.py")
    name = "_synthesis_retirement_storage_owner"
    previous = object()
    original = sys.modules.get(name)
    sys.modules[name] = previous
    try:
        path = tmp_path / "missing"
        entry = {"HEAD": "synthetic", "branch": "fixture"}
        assert runtime.source_storage_detail(source, path, entry, "missing") == fleet_paths.missing_worktree_detail(path, entry, "missing")
        assert sys.modules[name] is previous
        assert not (scripts / "__pycache__").exists()
    finally:
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def test_retirement_wrong_resolved_root_is_structured_refusal(tmp_path, monkeypatch, capsys):
    import retire_worktree as owner
    _, clone = build_repo(tmp_path)
    target = add_feature_worktree(tmp_path, clone)
    original = owner.run
    def displaced(cwd, *arguments, **kwargs):
        result = original(cwd, *arguments, **kwargs)
        if Path(cwd) == target and arguments == ("rev-parse", "--show-toplevel"):
            return subprocess.CompletedProcess(result.args, 0, str(clone) + "\n", "")
        return result
    monkeypatch.setattr(owner, "run", displaced)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--repository", str(clone), "--worktree", str(target)])
    before = (target / ".git").read_bytes()
    assert owner.main() == 2
    assert "different or unavailable checkout" in capsys.readouterr().err
    assert target.exists() and (target / ".git").read_bytes() == before
