"""Causal controls for exact grouped release collection and finite execution."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
import release_check_groups as groups


def ids():
    return [
        groups.AP + "/test_" + name + ".py::test_one"
        for name in ("run_state", "native_codex", "evaluation", "brand_new_surface")
    ]


def test_complete_nonoverlapping_inventory_includes_new_tests():
    result = groups.partition(ids())
    assert [result[g] for g in ("state", "native", "evaluation", "core")] == [
        [n] for n in ids()
    ]
    assert result["native-control"] == []
    assert sorted(sum(result.values(), [])) == sorted(ids())


@pytest.mark.parametrize("bad", [[], ["outside.py::x"], ids() + ids()[:1]])
def test_invalid_collection_refused(bad):
    with pytest.raises(ValueError):
        groups.partition(bad)


def test_overlapping_rules_refused(monkeypatch):
    monkeypatch.setattr(groups, "NATIVE_PREFIXES", groups.STATE_PREFIXES)
    with pytest.raises(ValueError, match="overlapping"):
        groups.partition(ids())


def plugin(tmp_path):
    p = groups.InventoryPlugin("core", tmp_path / "report.json")
    p.full = ids()
    p.selected = [ids()[-1]]
    return p


def phase(p, node, when="call", outcome="passed"):
    p.pytest_runtest_logreport(
        SimpleNamespace(nodeid=node, when=when, outcome=outcome, duration=0.1)
    )


def finish(p):
    session = SimpleNamespace(exitstatus=0)
    p.pytest_sessionfinish(session, 0)
    return session


def test_positive_execution_covers_all_phases(tmp_path):
    p = plugin(tmp_path)
    for when in ("setup", "call", "teardown"):
        phase(p, p.selected[0], when)
    assert finish(p).exitstatus == 0
    assert json.loads(p.report.read_text())["errors"] == []


@pytest.mark.parametrize(
    "defect", ["omitted", "duplicate", "extra", "skipped", "failed", "teardown"]
)
def test_execution_counterexamples_remain_failure(tmp_path, defect):
    p = plugin(tmp_path)
    node = p.selected[0]
    for when in ("setup", "call", "teardown"):
        if defect == "omitted" and when == "call":
            continue
        phase(
            p,
            node,
            when,
            ("skipped" if defect == "skipped" else "failed")
            if when == "call" and defect in ("failed", "skipped")
            else "failed"
            if defect == "teardown" and when == "teardown"
            else "passed",
        )
    if defect == "duplicate":
        phase(p, node)
    if defect == "extra":
        phase(p, "extra")
    assert finish(p).exitstatus == 1


def test_source_hash_detects_mutation(tmp_path):
    (tmp_path / "source.py").write_text("one")
    before = groups.source_digest(tmp_path)
    (tmp_path / "source.py").write_text("two")
    assert groups.source_digest(tmp_path) != before


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory-link"])
def test_source_refuses_special_members_without_opening_them(tmp_path, kind):
    p = tmp_path / "member"
    if kind == "fifo":
        os.mkfifo(p)
    elif kind == "directory-link":
        p.symlink_to(tmp_path, target_is_directory=True)
    else:
        p.symlink_to("/no-such-fixture")
    with pytest.raises((ValueError, OSError)):
        groups.source_digest(tmp_path)


def test_source_size_limit_is_fail_closed(tmp_path, monkeypatch):
    (tmp_path / "source").write_bytes(b"xx")
    monkeypatch.setattr(groups, "MAX_SOURCE_BYTES", 1)
    with pytest.raises(ValueError, match="ceiling"):
        groups.source_digest(tmp_path)


def test_bounded_owner_timeout_and_pipe_closure(tmp_path):
    for script in (
        "import time;time.sleep(20)",
        "import os,time;os.close(1);os.close(2);time.sleep(20)",
    ):
        start = time.monotonic()
        r = groups.bounded_run([sys.executable, "-c", script], tmp_path, 0.15)
        assert r.returncode != 0 and time.monotonic() - start < 4


def test_bounded_owner_output_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "OUTPUT_BYTES", 1024)
    r = groups.bounded_run([sys.executable, "-c", "print('x'*2000)"], tmp_path, 1)
    assert r.returncode != 0 and "byte ceiling" in r.stdout and len(r.stdout) < 1200


def test_bounded_owner_preserves_required_environment(tmp_path):
    r = groups.bounded_run(
        [
            sys.executable,
            "-c",
            "import os;print(os.environ['SYNTHESIS_TEST_CHROMIUM'])",
        ],
        tmp_path,
        2,
        {"SYNTHESIS_TEST_CHROMIUM": "exact-chromium"},
    )
    assert r.returncode == 0 and r.stdout.strip() == "exact-chromium"


def test_bounded_owner_reaps_group_descendant(tmp_path):
    marker = tmp_path / "child.json"
    script = "import os,signal,time,json\npid=os.fork()\nif pid==0:\n signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)\nelse:\n open('child.json','w').write(json.dumps({'pid':pid,'group':os.getpgrp()}));time.sleep(30)\n"
    r = groups.bounded_run([sys.executable, "-c", script], tmp_path, 0.25)
    assert r.returncode != 0
    info = json.loads(marker.read_text())
    # Some Unix init implementations retain a killed orphan briefly as a zombie.
    status = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(info["pid"])],
        capture_output=True,
        text=True,
        timeout=2,
    )
    assert not status.stdout.strip() or status.stdout.strip().startswith("Z")


def test_nonzero_check_exit_remains_failure(tmp_path):
    assert (
        groups.bounded_run(
            [sys.executable, "-c", "raise SystemExit(7)"], tmp_path, 2
        ).returncode
        == 7
    )


def test_release_and_ci_require_each_group():
    import ast
    import yaml

    root = Path(__file__).resolve().parents[3]
    tree = ast.parse(
        (root / "skills/synthesis-skills-manager/scripts/release.py").read_text()
    )
    checks = dict(
        ast.literal_eval(
            next(
                n.value
                for n in tree.body
                if isinstance(n, ast.AnnAssign)
                and getattr(n.target, "id", "") == "REQUIRED_CHECKS"
            )
        )
    )
    ci = yaml.safe_load((root / ".github/workflows/validate.yml").read_text())
    commands = [s.get("run", "") for s in ci["jobs"]["source-checks"]["steps"]]
    for group in groups.GROUPS:
        command = [
            "python3",
            "skills/synthesis-skills-manager/scripts/release_check_groups.py",
            "--group",
            group,
        ]
        assert checks["pytest.autopilot." + group] == command
        assert "python skills/synthesis-skills-manager/scripts/release.py --repo-root . --source-checks-only" in commands
    assert groups.GROUP_SECONDS < groups.CHECK_SECONDS == 900


def synthetic_root(tmp_path):
    root = tmp_path / "source"
    directory = root / groups.AP
    directory.mkdir(parents=True)
    for name in (
        "run_state",
        "native_codex",
        "evaluation",
        "brand_new_surface",
        "native_cancellation",
        "managed_native_owner",
    ):
        (directory / ("test_" + name + ".py")).write_text(
            "def test_one():\n    assert True\n"
        )
    return root


def test_actual_pytest_groups_run_every_parameter_and_preserve_full_inventory(
    tmp_path, monkeypatch
):
    root = synthetic_root(tmp_path)
    (root / groups.AP / "test_brand_new_surface.py").write_text(
        'import pytest\n@pytest.mark.parametrize("x",[1,2,3])\ndef test_one(x):\n    assert x>0\n'
    )
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k never-matches")
    observed = []
    inventories = []
    for group in groups.GROUPS:
        code, payload = groups.run_group(root, group)
        assert code == 0, payload
        observed.extend(payload["selected"])
        inventories.append(payload["inventory"])
    assert len(observed) == 8 and len(set(observed)) == 8
    assert all(sorted(i) == sorted(observed) for i in inventories)


@pytest.mark.parametrize("defect", ["syntax", "mutation", "failure", "skip"])
def test_actual_pytest_refusal_and_mutation_are_failures(tmp_path, defect):
    root = synthetic_root(tmp_path)
    file = root / groups.AP / "test_brand_new_surface.py"
    file.write_text(
        {
            "syntax": "not legal python !",
            "mutation": 'from pathlib import Path\ndef test_one():\n    Path("unexpected-source").write_text("changed")\n',
            "failure": "def test_one():\n    assert False\n",
            "skip": 'import pytest\ndef test_one():\n    pytest.skip("cannot execute")\n',
        }[defect]
    )
    code, _ = groups.run_group(root, "core")
    assert code != 0


@pytest.mark.parametrize("outcome", ["passed", "failed", "skipped"])
def test_actual_unittest_subtests_keep_parent_inventory_and_adverse_outcomes(
    tmp_path, outcome
):
    root = synthetic_root(tmp_path)
    action = {
        "passed": "self.assertEqual(i, i)",
        "failed": "self.assertEqual(i, -1)",
        "skipped": 'self.skipTest("required subtest unavailable")',
    }[outcome]
    (root / groups.AP / "test_native_subtests.py").write_text(
        "import unittest\nclass Example(unittest.TestCase):\n"
        " def test_same_context(self):\n"
        "  for i in range(3):\n"
        '   with self.subTest(msg="repeated valid context"):\n'
        "    " + action + "\n"
    )
    code, payload = groups.run_group(root, "native")
    assert (code == 0) == (outcome == "passed"), payload
    node = groups.AP + "/test_native_subtests.py::Example::test_same_context"
    assert set(payload["phases"][node]) == {"setup", "call", "teardown"}
    if int(pytest.__version__.split(".")[0]) >= 9:
        rows = payload["subtests"][node]
        assert [r["ordinal"] for r in rows] == [1, 2, 3]
        assert all(r["outcome"] == outcome for r in rows)
    assert set(payload["phases"]) == set(payload["selected"])


def test_arbitrary_context_attribute_does_not_hide_duplicate_parent_phase(tmp_path):
    p = plugin(tmp_path)
    node = p.selected[0]
    for when in ("setup", "call", "teardown"):
        phase(p, node, when)
    p.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid=node,
            when="call",
            outcome="passed",
            duration=0.1,
            context={"pretend": "subtest"},
        )
    )
    assert finish(p).exitstatus == 1 and "duplicate execution phase" in p.errors


@pytest.mark.parametrize(
    "defect",
    ["unknown-parent", "before-setup", "after-call", "wrong-phase", "count-ceiling"],
)
def test_typed_subtests_cannot_escape_parent_or_resource_bounds(
    tmp_path, monkeypatch, defect
):
    subtests = pytest.importorskip(
        "_pytest.subtests", reason="typed subtest reports require pytest 9"
    )
    p = plugin(tmp_path)
    node = p.selected[0]
    if defect != "before-setup":
        phase(p, node, "setup")
    if defect == "after-call":
        phase(p, node, "call")
    if defect == "count-ceiling":
        monkeypatch.setattr(groups, "MAX_TESTS", 1)
    report = subtests.SubtestReport(
        nodeid="unselected" if defect == "unknown-parent" else node,
        location=("synthetic.py", 1, "fixture"),
        keywords={},
        outcome="passed",
        longrepr=None,
        when="teardown" if defect == "wrong-phase" else "call",
        context=subtests.SubtestContext(msg="fixture", kwargs={}),
    )
    for _ in range(3 if defect == "count-ceiling" else 1):
        p.pytest_runtest_logreport(report)
    # Complete a valid parent independently; only invalid child evidence must
    # make this otherwise passing execution fail.
    for when in ("setup", "call", "teardown"):
        if when not in p.phases.get(node, {}):
            phase(p, node, when)
    assert finish(p).exitstatus == 1
    if defect == "count-ceiling":
        assert len(p.subtests[node]) == 1
        assert p.errors.count("subtest inventory exceeds count ceiling") == 1
    else:
        assert "subtest outside selected parent call interval" in p.errors


def test_release_owner_refuses_changed_source_before_acceptance(tmp_path, monkeypatch):
    import release

    (tmp_path / "source").write_text("original")
    monkeypatch.setattr(
        release, "REQUIRED_CHECKS", (("fixture", [sys.executable, "-c", "pass"]),)
    )

    def mutation(*args, **kwargs):
        (tmp_path / "source").write_text("changed")
        return subprocess.CompletedProcess([], 0, "ok", "")

    monkeypatch.setattr(release, "bounded_run", mutation)
    monkeypatch.setattr(
        release,
        "consume_acceptance",
        lambda *a: pytest.fail("mutated source consumed acceptance"),
    )
    result = release.Result()
    assert release.run_required_checks(tmp_path, result, False) is None
    assert not result.steps[-1].ok and "source changed" in result.steps[-1].detail


def test_failed_required_check_preserves_diagnostic_output(
    tmp_path, monkeypatch, capsys
):
    import release

    (tmp_path / "source").write_text("unchanged")
    monkeypatch.setattr(release, "REQUIRED_CHECKS", (("fixture", ["fixture"]),))
    stdout = "FAILED fixture::meaningful_case\ncausal detail\n1 failed, 1473 passed\n"
    stderr = "separate diagnostic\n"
    monkeypatch.setattr(
        release,
        "bounded_run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, stdout, stderr),
    )
    monkeypatch.setattr(
        release,
        "consume_acceptance",
        lambda *a: pytest.fail("failed checks consumed acceptance"),
    )
    result = release.Result()
    assert release.run_required_checks(tmp_path, result, False) is None
    captured = capsys.readouterr().out
    assert stdout in captured and stderr in captured
    assert result.steps[-1].ok is False
    assert result.steps[-1].detail == "1 failed, 1473 passed"


def test_interruption_returns_failure_and_restores_signal_handlers(tmp_path):
    old = signal.getsignal(signal.SIGTERM)
    script = (
        "import os,signal,time\nos.kill(os.getppid(),signal.SIGTERM)\ntime.sleep(30)\n"
    )
    start = time.monotonic()
    result = groups.bounded_run([sys.executable, "-c", script], tmp_path, 2)
    assert result.returncode != 0 and "interrupted" in result.stdout
    assert time.monotonic() - start < 4 and signal.getsignal(signal.SIGTERM) == old


def test_unreadable_directory_cannot_disappear_from_source_inventory(
    tmp_path, monkeypatch
):
    source = tmp_path / "subdirectory"
    source.mkdir()
    (source / "guard.py").write_text("required")
    original = groups.os.scandir

    def unreadable(path):
        if isinstance(path, int) and os.fstat(path).st_ino == source.stat().st_ino:
            raise PermissionError("synthetic unreadable required directory")
        return original(path)

    monkeypatch.setattr(groups.os, "scandir", unreadable)
    with pytest.raises(PermissionError):
        groups.source_digest(tmp_path)


def test_executable_mode_is_part_of_source_input(tmp_path):
    source = tmp_path / "launch"
    source.write_text("same bytes")
    source.chmod(0o600)
    before = groups.source_digest(tmp_path)
    source.chmod(0o700)
    assert groups.source_digest(tmp_path) != before


def test_pathname_replacement_while_descriptor_is_open_refused(tmp_path, monkeypatch):
    source = tmp_path / "guard.py"
    source.write_text("original bytes")
    original = groups.os.read
    changed = False

    def replacement(fd, size):
        nonlocal changed
        if not changed:
            changed = True
            source.rename(tmp_path / "retained-original")
            source.write_text("replacement bytes")
        return original(fd, size)

    monkeypatch.setattr(groups.os, "read", replacement)
    with pytest.raises(ValueError, match="changed"):
        groups.source_digest(tmp_path)


def test_directory_replaced_by_symlink_cannot_redirect_scan(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    directory = root / "sub"
    directory.mkdir()
    (directory / "guard.py").write_text("required")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "different").write_text("foreign")
    original = groups.os.open
    swapped = False

    def replacement(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == "sub" and not swapped:
            swapped = True
            directory.rename(root / "retained-sub")
            directory.symlink_to(outside, target_is_directory=True)
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(groups.os, "open", replacement)
    with pytest.raises((OSError, ValueError)):
        groups.source_digest(root)


@pytest.mark.parametrize("injection", ["selection", "plugin"])
def test_common_owner_rejects_inherited_pytest_deselection(
    tmp_path, monkeypatch, injection
):
    (tmp_path / "test_required.py").write_text(
        "def test_passing():\n    assert True\ndef test_required_failing():\n    assert False\n"
    )
    (tmp_path / "hostile_plugin.py").write_text(
        'def pytest_collection_modifyitems(items):\n    items[:]=[item for item in items if "passing" in item.nodeid]\n'
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    if injection == "selection":
        monkeypatch.setenv("PYTEST_ADDOPTS", "-k passing")
    else:
        monkeypatch.setenv("PYTEST_PLUGINS", "hostile_plugin")
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    control = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, timeout=5
    )
    assert control.returncode == 0, control.stdout + control.stderr
    guarded = groups.bounded_run(command, tmp_path, 5)
    assert guarded.returncode == 1 and "test_required_failing" in guarded.stdout


def test_common_owner_ignores_poisoned_same_header_bytecode(tmp_path, monkeypatch):
    import importlib.util
    import py_compile

    source = tmp_path / "required_module.py"
    source.write_text("VALUE = 'wrong'\n")
    stamp = source.stat()
    # The plain control child explicitly uses the ordinary cache, even when
    # this test itself is running inside a required owner's private prefix.
    with monkeypatch.context() as ordinary_cache:
        ordinary_cache.setattr(sys, "pycache_prefix", None)
        cache = Path(importlib.util.cache_from_source(str(source)))
    py_compile.compile(
        str(source),
        cfile=str(cache),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
    )
    source.write_text("VALUE = 'right'\n")
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    command = [
        sys.executable,
        "-c",
        "import required_module;print(required_module.VALUE)",
    ]
    plain = dict(os.environ)
    plain.pop("PYTHONPYCACHEPREFIX", None)
    control = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, timeout=5, env=plain
    )
    assert control.returncode == 0 and control.stdout.strip() == "wrong"
    monkeypatch.delenv("PYTHONPYCACHEPREFIX", raising=False)
    guarded = groups.bounded_run(command, tmp_path, 5)
    assert guarded.returncode == 0 and guarded.stdout.strip() == "right"
    assert cache.exists(), "original untrusted cache must remain untouched"


def test_common_owner_uses_fresh_cache_each_time_and_preserves_dependency_env(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SYNTHESIS_TEST_CHROMIUM", "verified-browser")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    paths = []
    for _ in range(2):
        result = groups.bounded_run(
            [
                sys.executable,
                "-c",
                "import os,json;print(json.dumps({k:os.environ.get(k) for k in ('PYTHONPYCACHEPREFIX','PYTHONDONTWRITEBYTECODE','PYTHONPATH','SYNTHESIS_TEST_CHROMIUM','PYTEST_DISABLE_PLUGIN_AUTOLOAD')}))",
            ],
            tmp_path,
            5,
        )
        assert result.returncode == 0, result.stdout
        env = json.loads(result.stdout)
        assert (
            env["PYTHONPATH"] == str(tmp_path)
            and env["SYNTHESIS_TEST_CHROMIUM"] == "verified-browser"
        )
        assert (
            env["PYTHONDONTWRITEBYTECODE"] == "1"
            and env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        )
        paths.append(env["PYTHONPYCACHEPREFIX"])
    assert paths[0] != paths[1]
    assert all(not Path(p).exists() for p in paths)


@pytest.mark.parametrize(
    "order",
    [
        ("call", "setup", "teardown"),
        ("setup", "teardown", "call"),
        ("teardown", "setup", "call"),
    ],
)
def test_parent_lifecycle_order_is_required_for_execution_evidence(tmp_path, order):
    p = plugin(tmp_path)
    for when in order:
        phase(p, p.selected[0], when)
    assert finish(p).exitstatus == 1
    assert "execution phase outside parent lifecycle order" in p.errors


def test_subtest_does_not_make_teardown_before_call_valid(tmp_path):
    subtests = pytest.importorskip("_pytest.subtests")
    p = plugin(tmp_path)
    node = p.selected[0]
    phase(p, node, "setup")
    p.pytest_runtest_logreport(
        subtests.SubtestReport(
            nodeid=node,
            location=("synthetic.py", 1, "fixture"),
            keywords={},
            outcome="passed",
            longrepr=None,
            when="call",
            context=subtests.SubtestContext(msg="fixture", kwargs={}),
        )
    )
    phase(p, node, "teardown")
    phase(p, node, "call")
    assert finish(p).exitstatus == 1
    assert "execution phase outside parent lifecycle order" in p.errors


def test_designated_inapplicable_host_skip_keeps_ordered_setup_teardown(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(groups.sys, "platform", "linux")
    p = plugin(tmp_path)
    node = (
        groups.AP
        + "/test_evaluation_artifacts.py::test_mac_worker_cannot_fork_or_spawn_a_process_outside_the_deadline"
    )
    p.full = p.selected = [node]
    phase(p, node, "setup", "skipped")
    phase(p, node, "teardown")
    assert finish(p).exitstatus == 0


@pytest.mark.parametrize(
    "defect",
    ["failed-teardown", "skipped-teardown", "missing-teardown", "unexpected-call"],
)
def test_host_inapplicability_never_excuses_invalid_remaining_phases(
    tmp_path, monkeypatch, defect
):
    monkeypatch.setattr(groups.sys, "platform", "linux")
    p = plugin(tmp_path)
    node = (
        groups.AP
        + "/test_evaluation_artifacts.py::test_mac_worker_cannot_fork_or_spawn_a_process_outside_the_deadline"
    )
    p.full = p.selected = [node]
    phase(p, node, "setup", "skipped")
    if defect == "unexpected-call":
        phase(p, node, "call")
    if defect != "missing-teardown":
        phase(
            p,
            node,
            "teardown",
            {"failed-teardown": "failed", "skipped-teardown": "skipped"}.get(
                defect, "passed"
            ),
        )
    assert finish(p).exitstatus == 1


def test_failed_required_check_preserves_output_before_changed_source_refusal(
    tmp_path, monkeypatch, capsys
):
    import release

    source = tmp_path / "source"
    source.write_text("original")
    monkeypatch.setattr(release, "REQUIRED_CHECKS", (("fixture", ["fixture"]),))

    def failed_mutation(*args, **kwargs):
        source.write_text("changed")
        return subprocess.CompletedProcess(
            [], 7, "FIRST exact failing case\nsummary\n", "separate diagnostic\n"
        )

    monkeypatch.setattr(release, "bounded_run", failed_mutation)
    monkeypatch.setattr(
        release,
        "consume_acceptance",
        lambda *args: pytest.fail("changed source consumed acceptance"),
    )
    result = release.Result()
    assert release.run_required_checks(tmp_path, result, False) is None
    captured = capsys.readouterr().out
    assert "FIRST exact failing case" in captured and "separate diagnostic" in captured
    assert len(result.steps) == 1 and not result.steps[0].ok
    assert result.steps[0].detail == "source changed during required check"


def test_required_check_retains_canonical_private_custody(tmp_path, monkeypatch):
    temp = tmp_path / "temporary"
    temp.mkdir()
    alias = tmp_path / "aliased-temp"
    alias.symlink_to(temp, target_is_directory=True)
    monkeypatch.setattr(groups.tempfile, "tempdir", str(alias))
    monkeypatch.setenv("TMPDIR", str(alias))
    program = "import os,json,tempfile;from pathlib import Path;p=Path(tempfile.gettempdir());q=p/'retained-evidence';q.write_text('evidence');print(json.dumps({'temp':str(p),'cache':os.environ['PYTHONPYCACHEPREFIX'],'evidence':str(q)}))"
    result = groups.bounded_run([sys.executable, "-c", program], tmp_path, 5)
    assert result.returncode == 0, result.stdout
    row = json.loads(result.stdout)
    assert Path(row["temp"]) == Path(row["temp"]).resolve()
    assert Path(row["evidence"]).read_text() == "evidence"
    custody = Path(row["cache"]).parent
    assert custody.is_dir(), "check owner deleted its retained custody"
    assert json.loads((custody / "result.json").read_text())["returncode"] == 0


def test_required_pytest_has_exclusive_retained_basetemp(tmp_path):
    test = tmp_path / "test_evidence.py"
    test.write_text(
        "def test_capture(tmp_path):\n (tmp_path/'marker').write_text('retained')\n print('CAPTURE='+str(tmp_path))\n"
    )
    paths = []
    for _ in range(2):
        result = groups.bounded_run(
            [sys.executable, "-m", "pytest", str(test), "-q", "-s"], tmp_path, 10
        )
        assert result.returncode == 0, result.stdout
        line = next(x for x in result.stdout.splitlines() if x.startswith("CAPTURE="))
        path = Path(line.split("=", 1)[1])
        paths.append(path)
        assert "pytest-of-" not in str(path)
        assert (path / "marker").read_text() == "retained"
    assert paths[0] != paths[1]
    assert all((p / "marker").is_file() for p in paths)


def test_nested_group_retains_inventory_and_fixtures(tmp_path):
    root = synthetic_root(tmp_path)
    (root / groups.AP / "test_brand_new_surface.py").write_text(
        "def test_one(tmp_path):\n (tmp_path/'evidence').write_text('kept')\n"
    )
    code, payload = groups.run_group(root, "core")
    assert code == 0, payload
    custody = Path(payload["fixture_custody"])
    assert custody.is_dir()
    assert (custody / "inventory.json").is_file()
    assert list(custody.rglob("evidence"))


def test_actual_decision_filing_uses_canonical_temporary_boundary(
    tmp_path, monkeypatch
):
    root = Path(__file__).resolve().parents[3]
    temp = tmp_path / "temporary"
    temp.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(temp, target_is_directory=True)
    monkeypatch.setattr(groups.tempfile, "tempdir", str(alias))
    monkeypatch.setenv("TMPDIR", str(alias))
    target = root / "skills/synthesis-decision-packet/scripts/test_build_packet.py"
    result = groups.bounded_run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(target) + "::test_file_into_writes_dated_spec_and_page",
            "-q",
        ],
        root,
        15,
    )
    assert result.returncode == 0, result.stdout


def test_owned_pytest_cannot_remove_supplied_existing_directory(tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_text("keep")
    test = tmp_path / "test_one.py"
    test.write_text("def test_one(): assert True\n")
    result = groups.bounded_run(
        [sys.executable, "-m", "pytest", str(test), "-q", "--basetemp", str(foreign)],
        tmp_path,
        5,
    )
    assert result.returncode == 0, result.stdout
    assert (foreign / "sentinel").read_text() == "keep"
    assert result.args[-2] == "--basetemp" and Path(result.args[-1]).parent == Path(
        result.fixture_custody
    )


def test_owned_receipt_cannot_follow_replaced_custody(tmp_path):
    outside = tmp_path / "foreign"
    outside.mkdir()
    (outside / "sentinel").write_text("keep")
    program = (
        "import os;from pathlib import Path;p=Path(os.environ['TMPDIR']).parent;p.rename(p.with_name(p.name+'-retained'));p.symlink_to("
        + repr(str(outside))
        + ",target_is_directory=True)"
    )
    result = groups.bounded_run([sys.executable, "-c", program], tmp_path, 5)
    assert result.returncode != 0 and "custody" in result.stdout
    assert sorted(p.name for p in outside.iterdir()) == ["sentinel"]


def test_release_invocation_retains_separate_check_custody(tmp_path, monkeypatch):
    import release

    monkeypatch.setattr(
        release,
        "REQUIRED_CHECKS",
        tuple((str(i), [sys.executable, "-c", 'print("checked")']) for i in range(2)),
    )
    monkeypatch.setattr(release, "consume_acceptance", lambda *a: "synthetic accepted")
    calls = []
    real = release.bounded_run

    def record(*a, **kw):
        outcome = real(*a, **kw)
        calls.append(outcome)
        return outcome

    monkeypatch.setattr(release, "bounded_run", record)
    assert (
        release.run_required_checks(tmp_path, release.Result(), False)
        == "synthetic accepted"
    )
    roots = [Path(x.fixture_custody) for x in calls]
    assert (
        len(roots) == 2 and roots[0] != roots[1] and roots[0].parent == roots[1].parent
    )
    assert all((p / "result.json").is_file() for p in roots)


@pytest.mark.parametrize("code", [0, 7])
def test_check_result_and_original_output_survive_exit(tmp_path, code):
    result = groups.bounded_run(
        [sys.executable, "-c", f"print('original evidence');raise SystemExit({code})"],
        tmp_path,
        5,
    )
    assert result.returncode == code
    root = Path(result.fixture_custody)
    assert (root / "output.log").read_text() == "original evidence\n"
    receipt = json.loads((root / "result.json").read_text())
    assert receipt["returncode"] == code
    assert receipt["executed_command"] == result.args


def test_pytest_nested_owned_process_retains_distinct_custody(tmp_path):
    program = """import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import release_check_groups as g
r=g.bounded_run([sys.executable,'-c',"print('nested')"],Path.cwd(),5)
print(json.dumps({'path':r.fixture_custody,'code':r.returncode}))
"""
    result = groups.bounded_run(
        [sys.executable, "-c", program, str(Path(groups.__file__).parent)], tmp_path, 10
    )
    assert result.returncode == 0, result.stdout
    row = json.loads(result.stdout)
    nested = Path(row["path"])
    outer = Path(result.fixture_custody)
    assert nested != outer and outer in nested.parents
    assert (nested / "result.json").is_file() and (outer / "result.json").is_file()


def synthetic(root):
    directory = root / groups.AP
    directory.mkdir(parents=True)
    (directory / "test_brand_new_surface.py").write_text(
        "def test_healthy():\n    assert True\n"
    )
    return directory


def test_controller_partition_remains_exhaustive():
    nodes = [
        groups.AP + "/" + n
        for n in (
            "test_controller.py::test_actual_next",
            "test_controller_recovery_readback.py::test_recover",
            "test_controller_leased_readback.py::test_cas",
            "test_brand_new_surface.py::test_one",
            "test_native_codex.py::test_one",
        )
    ]
    result = groups.partition(nodes)
    assert result["state"] == nodes[:3]
    assert result["core"] == [nodes[3]]
    assert sorted(sum(result.values(), [])) == sorted(nodes)
    assert groups.CHECK_SECONDS == 900 and groups.GROUP_SECONDS == 880


_PHASE_READY_SECONDS = 10


def _deadline_after_phase(monkeypatch, marker, readiness_seconds=_PHASE_READY_SECONDS):
    """Expire the real owner only after a child reaches the intended phase.

    This controls only the test subject's clock, never global time, subprocess
    execution, phase reports or cleanup. A separate real deadline fails an
    unreachable fixture. Independent wall-time/pipe/reaping tests remain real.
    """
    assert 0 < readiness_seconds <= _PHASE_READY_SECONDS and not marker.exists()
    original = groups.bounded_run
    real_monotonic = time.monotonic
    observed = {}

    def cutoff(command, cwd, timeout, env, **kwargs):
        started = real_monotonic()
        logical_start = started
        observed.update(phase_reached=False, readiness_expired=False)

        def now():
            if marker.is_file():
                observed["phase_reached"] = True
                return logical_start + timeout + 1
            if real_monotonic() - started >= readiness_seconds:
                observed["readiness_expired"] = True
                return logical_start + timeout + 1
            return logical_start

        with monkeypatch.context() as clock_patch:
            clock_patch.setattr(groups, "time", SimpleNamespace(monotonic=now))
            result = original(command, cwd, timeout, env, **kwargs)
        observed.update(result=result, real_seconds=real_monotonic() - started)
        assert observed["real_seconds"] < readiness_seconds + 4
        assert observed["phase_reached"], "fixture phase was not reached before its real readiness deadline"
        assert result.failure == "required check exceeded its unchanged wall-time ceiling"
        return result

    monkeypatch.setattr(groups, "bounded_run", cutoff)
    return observed


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_actual_timeout_retains_phase_evidence_without_acceptance(
    tmp_path, monkeypatch, phase
):
    root = tmp_path / "source"
    directory = synthetic(root)
    marker = tmp_path / "phase-ready"
    _deadline_after_phase(monkeypatch, marker)
    ready = f"    Path({str(marker)!r}).write_text('ready')\n    time.sleep(30)\n"
    content = "import pytest,time\nfrom pathlib import Path\ndef test_first():\n    assert True\n"
    if phase == "setup":
        content += "@pytest.fixture\ndef slow():\n" + ready + "def test_second(slow):\n    assert True\n"
    elif phase == "call":
        content += "def test_second():\n" + ready
    else:
        content += "@pytest.fixture\ndef slow():\n    yield\n" + ready + "def test_second(slow):\n    assert True\n"
    (directory / "test_brand_new_surface.py").write_text(content)
    monkeypatch.setattr(groups, "GROUP_SECONDS", 1.5)
    start = time.monotonic()
    code, payload = groups.run_group(root, "core")
    assert code != 0 and time.monotonic() - start < _PHASE_READY_SECONDS + 5
    partial = payload["partial_execution"]
    assert partial["status"] == "INCOMPLETE" and partial["authorizes_success"] is False
    events = partial["events"]
    node = groups.AP + "/test_brand_new_surface.py::test_first"
    assert [e["when"] for e in events if e.get("nodeid") == node] == [
        "setup",
        "call",
        "teardown",
    ]
    assert partial["timing"]["phase_seconds"]["call"] >= 0
    assert not (Path(payload["fixture_custody"]) / "inventory.json").exists()


def test_ordinary_complete_report_contains_timings_and_same_inventory(tmp_path):
    root = tmp_path / "source"
    synthetic(root)
    code, payload = groups.run_group(root, "core")
    assert code == 0 and payload["errors"] == []
    assert set(payload["phases"]) == set(payload["selected"])
    assert payload["timing"]["phase_seconds"]["call"] >= 0
    assert payload["timing"]["reporting_seconds"] >= 0
    partial = groups.read_progress(
        Path(payload["fixture_custody"]) / "inventory.progress.jsonl"
    )
    assert partial["status"] == "DIAGNOSTIC_ONLY"
    assert partial["authorizes_success"] is False


@pytest.mark.parametrize("fault", ["replace", "symlink", "mutate", "hardlink", "mode"])
def test_progress_custody_mutation_refuses_before_append(tmp_path, fault):
    p = groups.InventoryPlugin("core", tmp_path / "inventory.json")
    node = groups.AP + "/test_one.py::test_one"
    p.full = p.selected = [node]
    p.pytest_runtest_logreport(
        SimpleNamespace(nodeid=node, when="setup", outcome="passed", duration=0.01)
    )
    path = tmp_path / "inventory.progress.jsonl"
    original = path.read_bytes()
    if fault == "replace":
        path.rename(tmp_path / "original")
        path.write_bytes(original)
    elif fault == "symlink":
        path.rename(tmp_path / "original")
        path.symlink_to(tmp_path / "original")
    elif fault == "mutate":
        path.write_bytes(original + b"{}\n")
    elif fault == "hardlink":
        os.link(path, tmp_path / "alias")
    else:
        path.chmod(0o644)
    with pytest.raises((ValueError, OSError)):
        p.pytest_runtest_logreport(
            SimpleNamespace(nodeid=node, when="call", outcome="passed", duration=0.01)
        )
    assert path.read_bytes() in (original, original + b"{}\n")


def test_partial_trailing_frame_and_bound_are_explicit(tmp_path, monkeypatch):
    p = groups.InventoryPlugin("core", tmp_path / "inventory.json")
    node = groups.AP + "/test_one.py::test_one"
    p.full = p.selected = [node]
    p.pytest_runtest_logreport(
        SimpleNamespace(nodeid=node, when="setup", outcome="passed", duration=0.01)
    )
    path = tmp_path / "inventory.progress.jsonl"
    with path.open("ab") as stream:
        stream.write(b'{"interrupted"')
    partial = groups.read_progress(path)
    assert partial["trailing_incomplete"] and partial["authorizes_success"] is False
    monkeypatch.setattr(groups, "REPORT_BYTES", 1)
    with pytest.raises(ValueError):
        groups.read_progress(path)


def test_progress_reader_does_not_prevent_later_phase_append(tmp_path):
    p = plugin(tmp_path)
    node = p.selected[0]
    phase(p, node, "setup")
    before = groups.read_progress(p.progress)
    assert before["authorizes_success"] is False
    phase(p, node, "call")
    phase(p, node, "teardown")
    assert finish(p).exitstatus == 0


def test_progress_limit_refuses_without_final_acceptance(tmp_path, monkeypatch):
    p = plugin(tmp_path)
    monkeypatch.setattr(groups, "REPORT_BYTES", 4)
    with pytest.raises(ValueError, match="ceiling"):
        phase(p, p.selected[0], "setup")
    assert not p.report.exists()


def test_failed_call_is_retained_when_a_later_test_times_out(tmp_path, monkeypatch):
    root = tmp_path / "source"
    directory = synthetic(root)
    marker = tmp_path / "phase-ready"
    _deadline_after_phase(monkeypatch, marker)
    (directory / "test_brand_new_surface.py").write_text(
        "import time\nfrom pathlib import Path\ndef test_failed():\n    assert False\ndef test_slow():\n"
        + f"    Path({str(marker)!r}).write_text('ready')\n    time.sleep(30)\n"
    )
    monkeypatch.setattr(groups, "GROUP_SECONDS", 1.5)
    code, payload = groups.run_group(root, "core")
    assert code != 0
    evidence = payload["partial_execution"]
    assert (
        evidence["status"] == "INCOMPLETE" and evidence["authorizes_success"] is False
    )
    assert any(
        row.get("nodeid", "").endswith("::test_failed")
        and row.get("when") == "call"
        and row.get("outcome") == "failed"
        for row in evidence["events"]
    )


def test_completed_phase_journal_cannot_replace_required_final_inventory(
    tmp_path, monkeypatch
):
    root = synthetic_root(tmp_path)
    original = groups.bounded_run

    def completed_without_inventory(command, cwd, timeout, env, **kwargs):
        result = original(command, cwd, timeout, env, **kwargs)
        assert result.returncode == 0
        report = Path(env["SYNTHESIS_RELEASE_TEST_REPORT"])
        assert report.is_file()
        report.unlink()
        return result

    monkeypatch.setattr(groups, "bounded_run", completed_without_inventory)
    code, result = groups.run_group(root, "core")
    assert code != 0
    diagnostic = result["partial_execution"]
    assert diagnostic["status"] == "DIAGNOSTIC_ONLY"
    assert diagnostic["authorizes_success"] is False
    assert diagnostic["events"][-1]["kind"] == "sessionfinish"


@pytest.mark.parametrize("row", [[], 1, None, "not-an-object"])
def test_malformed_phase_object_is_refused(tmp_path, row):
    target = tmp_path / "inventory.progress.jsonl"
    target.write_text(json.dumps(row) + "\n")
    target.chmod(0o600)
    with pytest.raises(ValueError, match="invalid progress sequence"):
        groups.read_progress(target)


def test_diagnostic_clock_isolated_from_finite_product_deadline(tmp_path, monkeypatch):
    ticks = iter([0, 121])
    consumed = []

    def product_clock():
        value = next(ticks)
        consumed.append(value)
        return value

    with monkeypatch.context() as patch:
        patch.setattr(time, "monotonic", product_clock)
        p = groups.InventoryPlugin("core", tmp_path / "inventory.json")
        config = SimpleNamespace(
            hook=SimpleNamespace(pytest_deselected=lambda **kw: None)
        )
        for node in ids():
            p.pytest_itemcollected(SimpleNamespace(nodeid=node))
        p.pytest_collection_modifyitems(
            None, config, [SimpleNamespace(nodeid=n) for n in ids()]
        )
        for when in ("setup", "call", "teardown"):
            phase(p, p.selected[0], when)
        assert finish(p).exitstatus == 0
        assert consumed == []
        assert time.monotonic() == 0
        assert time.monotonic() == 121
    payload = json.loads(p.report.read_text())
    assert payload["errors"] == []
    assert 0 <= payload["timing"]["elapsed_seconds"] < 30
    assert groups.read_progress(p.progress)["authorizes_success"] is False


def test_diagnostic_metadata_isolated_from_product_filesystem_simulation(
    tmp_path, monkeypatch
):
    p = plugin(tmp_path)
    phase(p, p.selected[0], "setup")
    original_fstat = os.fstat
    original_lstat = Path.lstat
    fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_nlink",
        "st_gid",
    )

    def synthetic(info):
        return SimpleNamespace(st_uid=0, **{key: getattr(info, key) for key in fields})

    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", lambda fd: synthetic(original_fstat(fd)))
        patch.setattr(Path, "lstat", lambda path: synthetic(original_lstat(path)))
        phase(p, p.selected[0], "call")
        phase(p, p.selected[0], "teardown")
        assert finish(p).exitstatus == 0
    assert json.loads(p.report.read_text())["errors"] == []
    assert groups.read_progress(p.progress)["status"] == "DIAGNOSTIC_ONLY"


@pytest.mark.parametrize(
    "group,node",
    [
        (
            "native",
            "test_native_archive_stream.py::test_explicit_deadlines_refuse_without_inferred_completion",
        ),
        (
            "core",
            "test_ci_wiring.py::test_ci_sandbox_packaged_snapshot_does_not_trust_mutable_parent",
        ),
    ],
)
def test_actual_deadline_and_stat_tests_complete_under_diagnostic_plugin(
    tmp_path, group, node
):
    root = Path(__file__).resolve().parents[3]
    report = tmp_path / "inventory.json"
    script = (
        "import sys,pytest;from pathlib import Path;"
        "sys.path.insert(0," + repr(str(Path(groups.__file__).parent)) + ");"
        "import release_check_groups as g;"
        "p=g.InventoryPlugin(" + repr(group) + ",Path(" + repr(str(report)) + "));"
        "raise SystemExit(pytest.main("
        + repr(
            [
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(tmp_path / "pytest"),
                groups.AP + "/" + node,
            ]
        )
        + ",plugins=[p]))"
    )
    result = groups.bounded_run([sys.executable, "-c", script], root, 15)
    assert result.returncode == 0, result.stdout
    value = json.loads(report.read_text())
    assert value["selected"] == [groups.AP + "/" + node]
    assert value["errors"] == [] and value["exitstatus"] == 0
    assert set(value["phases"][groups.AP + "/" + node]) == {"setup", "call", "teardown"}


def test_diagnostic_primitives_do_not_call_mocked_product_io(tmp_path, monkeypatch):
    import builtins
    import hashlib
    import stat

    def product_only(*args, **kwargs):
        raise AssertionError("diagnostic consumed a product fixture primitive")

    with monkeypatch.context() as patch:
        for name in (
            "open",
            "close",
            "read",
            "write",
            "fstat",
            "stat",
            "lstat",
            "getuid",
            "getcwd",
            "fsync",
        ):
            patch.setattr(os, name, product_only)
        patch.setattr(time, "monotonic", product_only)
        patch.setattr(json, "dumps", product_only)
        patch.setattr(json, "loads", product_only)
        patch.setattr(hashlib, "sha256", product_only)
        patch.setattr(stat, "S_ISREG", product_only)
        patch.setattr(stat, "S_IMODE", product_only)
        patch.setattr(builtins, "open", product_only)
        p = plugin(tmp_path)
        for when in ("setup", "call", "teardown"):
            phase(p, p.selected[0], when)
        assert finish(p).exitstatus == 0
        diagnostic = groups.read_progress(p.progress)
        assert diagnostic["status"] == "DIAGNOSTIC_ONLY"
        assert diagnostic["authorizes_success"] is False
    assert json.loads(p.report.read_text())["errors"] == []


def test_actual_group_preserves_selected_virtualenv(tmp_path, monkeypatch):
    import venv

    selected = tmp_path / "selected-venv"
    venv.EnvBuilder(with_pip=False, symlinks=True, system_site_packages=True).create(
        selected
    )
    python = selected / "bin/python"
    assert python.is_symlink()
    env = dict(os.environ)
    initial = subprocess.run(
        [
            str(python),
            "-c",
            'import sys,sysconfig,pytest,json; print(json.dumps({"prefix":sys.prefix,"pytest":pytest.__version__,"site":sysconfig.get_path("purelib")}))',
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    identity = json.loads(initial.stdout)
    assert identity["prefix"] == str(selected)
    sentinel = Path(identity["site"]) / "synthesis_unique_venv_sentinel.py"
    sentinel.write_text('VALUE = "selected-environment-only"\n')
    root = tmp_path / "source"
    tests = root / groups.AP
    tests.mkdir(parents=True)
    for name in ("run_state", "native_codex", "evaluation"):
        (tests / f"test_{name}.py").write_text("def test_one():\n    assert True\n")
    (tests / "test_brand_new_surface.py").write_text(
        "import sys,pytest,synthesis_unique_venv_sentinel as marker\n"
        "def test_one():\n"
        f"    assert sys.prefix == {identity['prefix']!r}\n"
        f"    assert pytest.__version__ == {identity['pytest']!r}\n"
        '    assert marker.VALUE == "selected-environment-only"\n'
    )
    monkeypatch.setattr(sys, "executable", str(python))
    code, payload = groups.run_group(root, "core")
    assert code == 0, payload
    assert payload["selected"] == [groups.AP + "/test_brand_new_surface.py::test_one"]


def test_native_control_partition_preserves_all_tests_and_finite_bounds():
    nodes = [
        groups.AP + "/" + name + "::test_one"
        for name in (
            "test_native_cancellation.py",
            "test_native_admission_freshness.py",
            "test_native_session_owner_chain.py",
            "test_native_future_surface.py",
            "test_observation_bridge.py",
            "test_future_unclassified.py",
        )
    ]
    result = groups.partition(nodes)
    assert set(result) == {"state", "native", "native-control", "evaluation", "core", "timing"}
    assert result["native-control"] == nodes[:3]
    assert result["native"] == nodes[3:5]
    assert result["core"] == nodes[5:]
    assert sorted(sum(result.values(), [])) == sorted(nodes)
    assert len(set(sum(result.values(), []))) == len(nodes)
    assert groups.CHECK_SECONDS == 900 and groups.GROUP_SECONDS == 880
    assert groups.ACCEPTANCE_SECONDS == 6000


@pytest.mark.parametrize("failure_phase", ["setup", "call", "teardown"])
def test_failure_detail_survives_later_process_cutoff(
    tmp_path, monkeypatch, failure_phase
):
    root = tmp_path / "source"
    directory = synthetic(root)
    marker = tmp_path / "phase-ready"
    _deadline_after_phase(monkeypatch, marker)
    content = "import pytest,time\nfrom pathlib import Path\n"
    if failure_phase == "setup":
        content += "@pytest.fixture\ndef broken():\n    raise ValueError('retained-setup-marker')\ndef test_first(broken):\n    pass\n"
    elif failure_phase == "teardown":
        content += "@pytest.fixture\ndef broken():\n    yield\n    raise ValueError('retained-teardown-marker')\ndef test_first(broken):\n    pass\n"
    else:
        content += "def test_first():\n    raise ValueError('retained-call-marker')\n"
    content += f"def test_second():\n    Path({str(marker)!r}).write_text('ready')\n    time.sleep(30)\n"
    (directory / "test_brand_new_surface.py").write_text(content)
    monkeypatch.setattr(groups, "GROUP_SECONDS", 1.5)
    code, payload = groups.run_group(root, "core")
    assert code != 0
    evidence = payload["partial_execution"]
    assert evidence["status"] == "INCOMPLETE"
    assert evidence["authorizes_success"] is False
    failed = [row for row in evidence["events"] if row.get("outcome") == "failed"]
    assert len(failed) == 1 and failed[0]["when"] == failure_phase
    detail = failed[0]["failure"]
    assert detail["status"] == "complete"
    assert "retained-" + failure_phase + "-marker" in detail["text"]
    assert detail["bytes"] == len(detail["text"].encode("utf-8"))
    assert not (Path(payload["fixture_custody"]) / "inventory.json").exists()


def test_failure_detail_collection_is_retained_without_a_final_inventory(tmp_path):
    root = tmp_path / "source"
    directory = synthetic(root)
    (directory / "test_brand_new_surface.py").write_text(
        "raise RuntimeError('retained-collection-marker')\n"
    )
    code, payload = groups.run_group(root, "core")
    assert code != 0
    evidence = payload["partial_execution"]
    failures = [r for r in evidence["events"] if r.get("kind") == "collection-failure"]
    assert len(failures) == 1
    assert "retained-collection-marker" in failures[0]["failure"]["text"]
    assert evidence["authorizes_success"] is False


def test_failure_detail_is_stream_bounded_and_budget_never_resets(
    tmp_path, monkeypatch
):
    p = plugin(tmp_path)
    monkeypatch.setattr(groups, "FAILURE_DETAIL_BYTES", 16)
    monkeypatch.setattr(groups, "FAILURE_DETAIL_TOTAL_BYTES", 24)
    visited = []

    class LongTrace:
        def toterminal(self, writer):
            for index in range(1000):
                visited.append(index)
                writer.write("x" * 8)

    first = p._failure_detail(SimpleNamespace(longrepr=LongTrace()))
    assert first["status"] == "truncated" and first["bytes"] == 16
    assert len(visited) <= 3
    second = p._failure_detail(SimpleNamespace(longrepr="abcdefghijk"))
    assert second["status"] == "truncated" and second["bytes"] == 8
    third = p._failure_detail(SimpleNamespace(longrepr="must-not-appear"))
    assert (
        third["status"] == "omitted"
        and third["reason"] == "diagnostic_budget_exhausted"
    )
    assert p.failure_detail_bytes == 24
    assert groups.REPORT_BYTES == 4 * 1024 * 1024


def test_failure_detail_unicode_missing_and_renderer_refusal_are_explicit(
    tmp_path, monkeypatch
):
    p = plugin(tmp_path)
    monkeypatch.setattr(groups, "FAILURE_DETAIL_BYTES", 5)
    result = p._failure_detail(SimpleNamespace(longrepr="ééé"))
    assert result["status"] == "truncated" and result["text"] == "éé"
    assert result["bytes"] == 4
    assert p._failure_detail(SimpleNamespace())["status"] == "unavailable"

    class BrokenTrace:
        def toterminal(self, writer):
            raise RuntimeError("this is diagnostic rendering failure")

    failure = p._failure_detail(SimpleNamespace(longrepr=BrokenTrace()))
    assert failure["status"] == "unavailable" and failure["reason"] == "renderer_error"
    assert failure["error_type"] == "RuntimeError"


def test_failure_detail_actual_subtest_keeps_parent_lifecycle_and_refuses_success(
    tmp_path,
):
    root = tmp_path / "source"
    directory = synthetic(root)
    (directory / "test_brand_new_surface.py").write_text(
        "def test_one(subtests):\n"
        "    with subtests.test(part='one'):\n"
        "        raise ValueError('retained-subtest-marker')\n"
    )
    code, payload = groups.run_group(root, "core")
    assert code != 0
    evidence = groups.read_progress(
        Path(payload["fixture_custody"]) / "inventory.progress.jsonl"
    )
    rows = [r for r in evidence["events"] if r.get("kind") == "subtest"]
    assert len(rows) == 1 and rows[0]["outcome"] == "failed"
    assert "retained-subtest-marker" in rows[0]["failure"]["text"]
    assert evidence["authorizes_success"] is False


def diagnostic_fixture(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    completed = groups.bounded_run(
        [sys.executable, "-c", "print('private-output-sentinel')"], root, 5
    )
    return root, completed


def test_actual_diagnostic_custody_is_private_and_published_schema_is_closed(tmp_path):
    root, completed = diagnostic_fixture(tmp_path)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    receipt = groups.capture_acceptance_diagnostics(
        completed, root, [], {"transaction_id": "private-binding-sentinel"}, target
    )
    assert receipt["status"] == "INCOMPLETE"
    public = Path(target["path"])
    blob = b"".join(p.read_bytes() for p in public.iterdir() if p.is_file())
    assert b"private-output-sentinel" not in blob
    assert b"private-binding-sentinel" not in blob
    assert str(tmp_path).encode() not in blob
    raw = Path(completed.fixture_custody) / "diagnostics/raw/0000.bin"
    assert raw.read_text() == "private-output-sentinel\n"
    assert (raw.stat().st_mode & 0o777) == 0o600
    assert (
        json.loads((public / "manifest.json").read_text())["authorizes_release"]
        is False
    )


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "changed", "mode"])
def test_diagnostic_custody_refuses_unsafe_output_without_reading_foreign(
    tmp_path, kind
):
    root, completed = diagnostic_fixture(tmp_path)
    output = Path(completed.fixture_custody) / "output.log"
    foreign = tmp_path / "private"
    foreign.write_text("foreign-secret-sentinel")
    if kind == "changed":
        output.write_text("changed")
    elif kind == "mode":
        output.chmod(0o666)
    else:
        output.unlink()
        if kind == "symlink":
            output.symlink_to(foreign)
        elif kind == "hardlink":
            os.link(foreign, output)
        else:
            os.mkfifo(output)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    assert result["status"] == "REFUSED"
    assert foreign.read_text() == "foreign-secret-sentinel"
    assert b"foreign-secret-sentinel" not in b"".join(
        p.read_bytes() for p in Path(target["path"]).iterdir()
    )


def test_diagnostic_destination_requires_new_private_external_directory(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for target in [root / "nested", root, tmp_path]:
        with pytest.raises((OSError, ValueError)):
            groups.prepare_diagnostics_destination(target, root)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(foreign, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        groups.prepare_diagnostics_destination(alias / "child", root)
    assert list(foreign.iterdir()) == []


@pytest.mark.parametrize("budget", ["records", "bytes", "time"])
def test_diagnostics_finite_limits_refuse_without_acceptance(
    tmp_path, monkeypatch, budget
):
    root, completed = diagnostic_fixture(tmp_path)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    if budget == "records":
        monkeypatch.setattr(groups, "DIAGNOSTIC_RECORDS", 1)
    elif budget == "bytes":
        monkeypatch.setattr(groups, "DIAGNOSTIC_BYTES", 1)
    else:
        monkeypatch.setattr(groups, "DIAGNOSTIC_SECONDS", 0)
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    assert result["status"] == "REFUSED"
    assert result["authorizes_release"] is False


def test_diagnostic_destination_replacement_cannot_receive_export(tmp_path):
    root, completed = diagnostic_fixture(tmp_path)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    path = Path(target["path"])
    path.rename(tmp_path / "retained-destination")
    path.mkdir(mode=0o700)
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    assert result["status"] == "REFUSED"
    assert list(path.iterdir()) == []


def test_owned_receipt_cannot_index_foreign_batch_custody(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    foreign = tmp_path / "foreign-secret-directory"
    foreign.mkdir()
    (foreign / "selection.json").write_text("private-foreign-sentinel")
    plan = [{"id": "one", "selectors": ["test_public.py::test_one"]}]
    receipt = {
        "execution": {
            "batches": [
                {
                    **plan[0],
                    "fixture_custody": str(foreign),
                    "process_custody": str(foreign / "process"),
                }
            ]
        }
    }
    completed = groups.bounded_run(
        [sys.executable, "-c", "print(" + repr(groups.encode_acceptance_receipt(receipt)) + ")"], root, 5
    )
    original = groups.os.open

    def refuse_foreign(path, *args, **kwargs):
        assert str(path) not in {str(foreign), "foreign-secret-directory"}
        return original(path, *args, **kwargs)

    monkeypatch.setattr(groups.os, "open", refuse_foreign)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    result = groups.capture_acceptance_diagnostics(completed, root, plan, {}, target)
    assert result["status"] == "REFUSED"
    assert (
        "private-foreign-sentinel"
        not in (Path(target["path"]) / "diagnostics.json").read_text()
    )


def test_diagnostic_source_pin_refuses_replaced_parent_before_read(tmp_path):
    parent = tmp_path / "owned"
    parent.mkdir(mode=0o700)
    (parent / "inventory.json").write_text("{}")
    identity = groups.custody_identity(parent.stat())
    parent.rename(tmp_path / "old")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "inventory.json").write_text("private")
    parent.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(ValueError, match="alias"):
        groups.diagnostic_record(
            parent / "inventory.json", time.monotonic() + 5, identity
        )


def test_diagnostic_record_mutation_during_descriptor_read_refuses(
    tmp_path, monkeypatch
):
    root, completed = diagnostic_fixture(tmp_path)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    output = Path(completed.fixture_custody) / "output.log"
    inode = output.stat().st_ino
    original = groups.os.read
    changed = []

    def read_then_mutate(fd, count):
        data = original(fd, count)
        if not changed and groups.os.fstat(fd).st_ino == inode:
            changed.append(True)
            output.write_text("different-after-read")
        return data

    monkeypatch.setattr(groups.os, "read", read_then_mutate)
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    assert changed and result["status"] == "REFUSED"


def test_diagnostic_export_refuses_unindexed_destination_member(tmp_path):
    root, completed = diagnostic_fixture(tmp_path)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    path = Path(target["path"])
    (path / "unindexed.txt").write_text("private-unindexed-sentinel")
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    assert result["status"] == "REFUSED"
    assert not (path / "diagnostics.json").exists()
    assert (path / "unindexed.txt").read_text() == "private-unindexed-sentinel"


def test_public_member_replacement_at_manifest_write_is_withheld(tmp_path, monkeypatch):
    root, completed = diagnostic_fixture(tmp_path)
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    public = Path(target["path"])
    original = groups.os.open
    replaced = []

    def replace_at_manifest(path, flags, *args, **kwargs):
        if path == "manifest.json" and not replaced:
            replaced.append(True)
            (public / "diagnostics.json").rename(tmp_path / "original-diagnostics.json")
            (public / "diagnostics.json").write_text("private-replacement-sentinel")
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(groups.os, "open", replace_at_manifest)
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    assert replaced
    assert result["status"] == "REFUSED"
    assert result.get("export_closed", False) is False


@pytest.mark.parametrize("replacement", ["unchanged", "symlink", "directory", "mode"])
def test_diagnostic_destination_ancestry_is_bound_before_export(tmp_path, replacement):
    root, completed = diagnostic_fixture(tmp_path)
    holder = tmp_path / "parent"
    holder.mkdir()
    holder.chmod(0o755)
    target = groups.prepare_diagnostics_destination(holder / "public", root)
    if replacement in ("symlink", "directory"):
        holder.rename(tmp_path / "retained-parent")
        if replacement == "symlink":
            holder.symlink_to(tmp_path / "retained-parent", target_is_directory=True)
        else:
            holder.mkdir()
            (tmp_path / "retained-parent/public").rename(holder / "public")
    elif replacement == "mode":
        holder.chmod(0o700)
    result = groups.capture_acceptance_diagnostics(completed, root, [], {}, target)
    if replacement == "unchanged":
        assert result["status"] == "INCOMPLETE" and result["export_closed"]
    else:
        assert result["status"] == "REFUSED" and not result["export_closed"]
        assert not (holder / "public/diagnostics.json").exists()
    assert (
        Path(completed.fixture_custody) / "output.log"
    ).read_text() == "private-output-sentinel\n"


def selected_outer_execution(tmp_path, selectors, root=None):
    """Use the real acceptance plugin and its independently consumed receipt."""
    root = root or Path(__file__).resolve().parents[3]
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps(selectors))
    report = tmp_path / "inventory.json"
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n")
    env = dict(os.environ)
    env.update(
        SYNTHESIS_ACCEPTANCE_SELECTION=str(selection),
        SYNTHESIS_RELEASE_TEST_REPORT=str(report),
        PYTHONPATH=str(Path(groups.__file__).parent),
        TMPDIR=str(tmp_path),
    )
    modules = sorted({node.split("::", 1)[0] for node in selectors})
    result = groups.bounded_run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-c",
            str(config),
            "--rootdir",
            str(root),
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "-p",
            "release_check_groups",
            *modules,
        ],
        root,
        90,
        env,
    )
    return result, report


def test_outer_acceptance_keeps_nested_group_inventory(tmp_path):
    selector = (
        "skills/synthesis-skills-manager/scripts/test_release_check_groups.py::"
        "test_actual_pytest_groups_run_every_parameter_and_preserve_full_inventory"
    )
    result, report = selected_outer_execution(tmp_path, [selector])
    assert result.returncode == 0, result.stdout
    expanded, outcomes = groups.selection_results(
        groups.read_inventory(report), [selector]
    )
    assert expanded == {selector: [selector]}
    assert outcomes == {selector: "passed"}


@pytest.mark.parametrize("inherited", ["subset", "foreign", "malformed", "missing"])
def test_explicit_group_does_not_inherit_acceptance_selection(
    tmp_path, monkeypatch, inherited
):
    root = synthetic_root(tmp_path)
    directory = root / groups.AP
    (directory / "test_brand_new_surface.py").write_text(
        "def test_one():\n    assert True\ndef test_two():\n    assert True\n"
    )
    selection = tmp_path / "inherited.json"
    if inherited != "missing":
        selection.write_text(
            "not json"
            if inherited == "malformed"
            else json.dumps(
                [
                    groups.AP + "/test_brand_new_surface.py::test_one"
                    if inherited == "subset"
                    else "foreign.py::test_foreign"
                ]
            )
        )
    monkeypatch.setenv("SYNTHESIS_ACCEPTANCE_SELECTION", str(selection))
    code, payload = groups.run_group(root, "core")
    assert code == 0, payload
    assert payload["group"] == "core"
    assert payload["selected"] == [
        groups.AP + "/test_brand_new_surface.py::test_one",
        groups.AP + "/test_brand_new_surface.py::test_two",
    ]
    assert len(payload["inventory"]) == 6


@pytest.mark.parametrize("cohort", ["hosted-batch221", "additional-limits"])
def test_outer_acceptance_survives_own_limit_and_custody_controls(tmp_path, cohort):
    names = [
        "test_owned_pytest_cannot_remove_supplied_existing_directory",
        "test_owned_receipt_cannot_follow_replaced_custody",
        "test_partial_trailing_frame_and_bound_are_explicit",
        "test_pathname_replacement_while_descriptor_is_open_refused",
        "test_positive_execution_covers_all_phases",
        "test_progress_custody_mutation_refuses_before_append",
        "test_progress_limit_refuses_without_final_acceptance",
        "test_progress_reader_does_not_prevent_later_phase_append",
        "test_typed_subtests_cannot_escape_parent_or_resource_bounds",
        "test_failure_detail_is_stream_bounded_and_budget_never_resets",
    ]
    names = names[:8] if cohort == "hosted-batch221" else names[8:]
    selectors = [
        "skills/synthesis-skills-manager/scripts/test_release_check_groups.py::" + name
        for name in names
    ]
    result, report = selected_outer_execution(tmp_path, selectors)
    assert result.returncode == 0, result.stdout
    expanded, outcomes = groups.selection_results(
        groups.read_inventory(report), selectors
    )
    assert set(outcomes) == {node for nodes in expanded.values() for node in nodes}
    assert set(outcomes.values()) == {"passed"}
    assert len(expanded) == len(selectors)
    progress = groups.read_progress(report.with_suffix(".progress.jsonl"))
    assert progress["status"] == "DIAGNOSTIC_ONLY"
    assert progress["events"][-1]["kind"] == "sessionfinish"


def test_registered_observer_still_refuses_actual_custody_tampering(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "test_tamper.py").write_text(
        "def test_tamper(request):\n"
        "    observer = request.config.pluginmanager.get_plugin('release-inventory')\n"
        "    with observer.progress.open('ab') as stream:\n"
        "        stream.write(b'{}\\n')\n"
    )
    result, report = selected_outer_execution(
        tmp_path, ["test_tamper.py::test_tamper"], root
    )
    assert result.returncode != 0, result.stdout
    assert not report.exists()
    assert "progress custody changed" in result.stdout


@pytest.mark.parametrize("setting", ["python_files = test_good.py", "python_functions = test_good"])
def test_group_ignores_ancestor_collection_configuration(tmp_path, setting):
    root = tmp_path / "source"
    scripts = root / groups.AP
    scripts.mkdir(parents=True)
    (tmp_path / "pytest.ini").write_text("[pytest]\n" + setting + "\n")
    (scripts / "test_good.py").write_text("def test_good():\n    assert True\n")
    (scripts / "test_bad.py").write_text("def test_bad():\n    assert False, 'required failure'\n")
    code, payload = groups.run_group(root, "core")
    assert set(payload["selected"]) == {
        groups.AP + "/test_good.py::test_good",
        groups.AP + "/test_bad.py::test_bad",
    }
    assert code != 0


@pytest.mark.parametrize("outside_hook", [False, True])
def test_group_confines_conftest_and_keeps_in_root_fixtures(tmp_path, outside_hook):
    root = tmp_path / "source"
    scripts = root / groups.AP
    scripts.mkdir(parents=True)
    (root / "conftest.py").write_text(
        "import pytest\n@pytest.fixture\ndef scoped_value():\n    return 42\n"
    )
    for name, assertion in (("good", "assert scoped_value == 42"), ("bad", "assert False, 'required failure'")):
        (scripts / ("test_" + name + ".py")).write_text(
            "def test_" + name + "(scoped_value):\n    " + assertion + "\n"
        )
    if outside_hook:
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        (tmp_path / "conftest.py").write_text(
            "from pathlib import Path\n"
            "Path(__file__).with_name('ancestor-loaded').write_text('loaded')\n"
            "def pytest_ignore_collect(collection_path, config):\n"
            "    return collection_path.name == 'test_bad.py'\n"
        )
    code, payload = groups.run_group(root, "core")
    assert set(payload["selected"]) == {
        groups.AP + "/test_good.py::test_good",
        groups.AP + "/test_bad.py::test_bad",
    }
    assert code != 0
    assert not (tmp_path / "ancestor-loaded").exists()
    assert payload["phases"][groups.AP + "/test_good.py::test_good"]["call"]["outcome"] == "passed"


@pytest.mark.parametrize("case", ["retain-setup", "retain-call", "retain-teardown", "failed-call", "detail-setup", "detail-call", "detail-teardown"])
def test_phase_cutoff_retains_real_evidence_after_delayed_collection(tmp_path, monkeypatch, case):
    original = synthetic

    def delayed(root):
        directory = original(root)
        (directory / "conftest.py").write_text("import time\ntime.sleep(2)\n")
        return directory

    monkeypatch.setattr(sys.modules[__name__], "synthetic", delayed)
    if case.startswith("retain-"):
        test_actual_timeout_retains_phase_evidence_without_acceptance(tmp_path, monkeypatch, case.removeprefix("retain-"))
    elif case == "failed-call":
        test_failed_call_is_retained_when_a_later_test_times_out(tmp_path, monkeypatch)
    else:
        test_failure_detail_survives_later_process_cutoff(tmp_path, monkeypatch, case.removeprefix("detail-"))


def test_phase_cutoff_requires_readiness_without_changing_global_clock(tmp_path, monkeypatch):
    real_clock = time.monotonic
    original_time_module = groups.time
    observed = _deadline_after_phase(monkeypatch, tmp_path / "never-ready", readiness_seconds=0.2)
    started = real_clock()
    with pytest.raises(AssertionError, match="fixture phase was not reached"):
        groups.bounded_run([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 0.1, dict(os.environ))
    assert real_clock() - started < 4
    assert groups.time is original_time_module and time.monotonic is real_clock
    assert observed["phase_reached"] is False and observed["readiness_expired"] is True
    result = observed["result"]
    assert (
        result.returncode != 0
        and result.failure == "required check exceeded its unchanged wall-time ceiling"
    )
    with pytest.raises(ProcessLookupError):
        os.kill(result.process_id, 0)
    with pytest.raises(ProcessLookupError):
        os.killpg(result.process_id, 0)
    os.kill(os.getpid(), 0)


def receipt_frame(raw, **changes):
    """Construct hostile wire bytes independently of the production encoder."""
    import base64
    import hashlib
    import zlib

    envelope = {
        "receipt_transport": groups.RECEIPT_TRANSPORT,
        "payload_bytes": len(raw),
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "payload": base64.b64encode(zlib.compress(raw)).decode("ascii"),
    }
    envelope.update(changes)
    return json.dumps(envelope)


def test_acceptance_transport_is_lossless_for_evidence_and_failed_outcomes():
    payload = {
        "ok": False,
        "errors": ["original error"],
        "cases": [{"matched": False, "stdout": "complete\névidence\n"}],
        "execution": {"source_unchanged": False, "batches": []},
    }
    wire = groups.encode_acceptance_receipt(payload)
    assert groups.decode_acceptance_receipt(wire) == payload
    assert groups.decode_acceptance_receipt(wire.encode()) == payload
    assert groups.OUTPUT_BYTES == 8 * 1024 * 1024
    assert groups.RECEIPT_BYTES == 32 * 1024 * 1024


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "truncated",
        "base64",
        "deflate",
        "length",
        "digest",
        "trailing",
        "concatenated",
        "json",
        "duplicate",
        "nonfinite",
        "overflow-positive",
        "overflow-negative",
        "deep",
        "metadata-duplicate",
        "metadata-extra",
        "metadata-boolean",
        "unframed",
    ],
)
def test_acceptance_transport_rejects_ambiguous_or_corrupt_evidence(mutation):
    import base64
    import zlib

    raw = b'{"ok":false,"evidence":"all retained"}'
    wire = receipt_frame(raw)
    envelope = json.loads(wire)
    packed = base64.b64decode(envelope["payload"])
    if mutation == "missing":
        wire = ""
    elif mutation == "truncated":
        wire = wire[:-4]
    elif mutation == "base64":
        envelope["payload"] = "!invalid!"
    elif mutation == "deflate":
        envelope["payload"] = base64.b64encode(packed[:-1]).decode()
    elif mutation == "length":
        envelope["payload_bytes"] += 1
    elif mutation == "digest":
        envelope["payload_sha256"] = "0" * 64
    elif mutation in {"trailing", "concatenated"}:
        tail = b"trailing" if mutation == "trailing" else zlib.compress(raw)
        envelope["payload"] = base64.b64encode(packed + tail).decode()
    elif mutation == "json":
        wire = receipt_frame(b'{"ok":}')
    elif mutation == "duplicate":
        wire = receipt_frame(b'{"ok":false,"ok":true}')
    elif mutation == "nonfinite":
        wire = receipt_frame(b'{"value":NaN}')
    elif mutation in {"overflow-positive", "overflow-negative"}:
        value = b"1e999" if mutation == "overflow-positive" else b"-1e999"
        wire = receipt_frame(b'{"value":' + value + b"}")
    elif mutation == "deep":
        wire = receipt_frame(
            b'{"x":'
            + b"[" * (groups.RECEIPT_JSON_DEPTH + 1)
            + b"0"
            + b"]" * (groups.RECEIPT_JSON_DEPTH + 1)
            + b"}"
        )
    elif mutation == "metadata-duplicate":
        wire = wire[:-1] + ',"payload_bytes":1}'
    elif mutation == "metadata-extra":
        envelope["untrusted"] = True
    elif mutation == "metadata-boolean":
        envelope["payload_bytes"] = True
    elif mutation == "unframed":
        wire = raw.decode()
    if mutation in {
        "base64",
        "deflate",
        "length",
        "digest",
        "trailing",
        "concatenated",
        "metadata-extra",
        "metadata-boolean",
    }:
        wire = json.dumps(envelope)
    with pytest.raises(ValueError):
        groups.decode_acceptance_receipt(wire)


def test_acceptance_transport_checks_declared_cap_before_inflation(monkeypatch):
    wire = receipt_frame(b"{}", payload_bytes=groups.RECEIPT_BYTES + 1)

    def forbidden():
        pytest.fail("oversized declaration reached decompression")

    monkeypatch.setattr(groups.zlib, "decompressobj", forbidden)
    with pytest.raises(ValueError, match="metadata"):
        groups.decode_acceptance_receipt(wire)


def test_acceptance_transport_lying_length_cannot_expand_unbounded(monkeypatch):
    wire = receipt_frame(b'{"evidence":"' + b"x" * 1000000 + b'"}', payload_bytes=16)
    inflater = groups.zlib.decompressobj
    observed = []

    class LimitedInflater:
        def __init__(self):
            self.inner = inflater()

        def decompress(self, data, max_length):
            observed.append(max_length)
            result = self.inner.decompress(data, max_length)
            assert len(result) <= 17
            return result

    monkeypatch.setattr(groups.zlib, "decompressobj", LimitedInflater)
    with pytest.raises(ValueError, match="integrity"):
        groups.decode_acceptance_receipt(wire)
    assert observed == [17]


def test_acceptance_transport_producer_and_reader_refuse_both_ceilings(monkeypatch):
    import random

    monkeypatch.setattr(groups, "RECEIPT_BYTES", 128)
    with pytest.raises(ValueError, match="decoded byte ceiling"):
        groups.encode_acceptance_receipt({"evidence": "x" * 129})
    monkeypatch.setattr(groups, "RECEIPT_BYTES", 10000)
    monkeypatch.setattr(groups, "OUTPUT_BYTES", 512)
    with pytest.raises(ValueError, match="transport exceeds"):
        groups.encode_acceptance_receipt(
            {"evidence": random.Random(42).randbytes(3000).hex()}
        )
    with pytest.raises(ValueError, match="transport exceeds"):
        groups.decode_acceptance_receipt(" " * 513)


def test_acceptance_transport_nesting_is_bounded_without_counting_quoted_braces():
    payload = {"evidence": '\\"{}[]' * 1000}
    assert (
        groups.decode_acceptance_receipt(groups.encode_acceptance_receipt(payload))
        == payload
    )
    nested = {}
    for _ in range(groups.RECEIPT_JSON_DEPTH):
        nested = {"child": nested}
    with pytest.raises(ValueError, match="depth"):
        groups.encode_acceptance_receipt(nested)


def test_diagnostic_capture_above_two_thousand_records(tmp_path):
    """Synthetic pinned records exercise real custody, not test/release authority."""
    root = tmp_path / "source"
    root.mkdir()
    program = r"""
import hashlib, json, os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import release_check_groups as g
parent = Path(os.environ['TMPDIR']).resolve()
batches = []
for index in range(336):
    group = parent / ('synthesis-release-check-' + str(index))
    group.mkdir(mode=0o700)
    process = group / 'synthesis-required-check-synthetic'
    process.mkdir(mode=0o700)
    selectors = ['test_public.py::test_one']
    events = [{'sequence': 0, 'kind': 'start'}] + [
        {'sequence': i + 1, 'kind': 'phase', 'nodeid': selectors[0],
         'when': when, 'outcome': 'passed', 'duration': 0.001}
        for i, when in enumerate(('setup', 'call', 'teardown'))]
    contents = {
        group / 'selection.json': json.dumps(selectors),
        group / 'pytest.ini': '[pytest]\n',
        group / 'inventory.json': '{}',
        group / 'inventory.progress.jsonl': ''.join(json.dumps(e) + '\n' for e in events),
        process / 'output.log': 'private-output-sentinel',
        process / 'result.json': '{}',
    }
    for path, data in contents.items():
        path.write_text(data)
        path.chmod(0o600)
    identity = g.custody_identity(group.stat())
    process_identity = g.custody_identity(process.stat())
    pins = {path.name: g.diagnostic_record(path, time.monotonic() + 10, identity)
            for path in contents if path.parent == group}
    process_pins = {path.name: g.diagnostic_record(path, time.monotonic() + 10, process_identity)
                    for path in contents if path.parent == process}
    batches.append({'id': str(index), 'selectors': selectors,
        'fixture_custody': str(group), 'process_custody': str(process),
        'custody_identity': identity, 'process_identity': process_identity,
        'diagnostic_records': pins, 'process_records': process_pins,
        'output_sha256': hashlib.sha256(b'private-output-sentinel').hexdigest(),
        'returncode': 0})
print(g.encode_acceptance_receipt({'execution': {'batches': batches}}))
"""
    completed = groups.bounded_run(
        [sys.executable, "-c", program, str(Path(groups.__file__).parent)], root, 30
    )
    assert completed.returncode == 0, completed.stdout
    plan = [{"id": str(i), "selectors": ["test_public.py::test_one"]} for i in range(336)]
    target = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    started = time.monotonic()
    receipt = groups.capture_acceptance_diagnostics(completed, root, plan, {}, target)
    assert receipt["status"] == "RETAINED", receipt
    assert time.monotonic() - started < 10
    document = json.loads((Path(target["path"]) / "diagnostics.json").read_text())
    assert len(document["records"]) == 2018
    assert len(document["batches"]) == 336
    assert all(len(batch["phases"]) == 3 for batch in document["batches"])
    assert document["authorizes_release"] is False
    assert "private-output-sentinel" not in json.dumps(document)
    assert str(tmp_path) not in json.dumps(document)
    assert groups.DIAGNOSTIC_BYTES == 32 * 1024 * 1024
    assert groups.DIAGNOSTIC_SECONDS == 10


@pytest.mark.parametrize("path,line,expected", [
    ("test_cases.py", 4, 4), ("absolute", 4, 4),
    ("/private/foreign.py", 4, None), ("other.py", 4, None),
    ("test_cases.py", True, None), ("test_cases.py", -1, None),
    ("test_cases.py", 0, None), ("test_cases.py", 1000001, None),
    (["private"], 4, None), ("test_cases.py", "4", None),
])
def test_failure_site_binds_line_to_selected_source(tmp_path, path, line, expected):
    import hashlib

    p = groups.InventoryPlugin("fixture", tmp_path / "unused.json")
    if path == "absolute":
        path = str(p.source_root / "test_cases.py")
    report = SimpleNamespace(
        nodeid="test_cases.py::test_one[PRIVATE_PARAMETER]",
        longrepr=SimpleNamespace(reprcrash=SimpleNamespace(path=path, lineno=line)),
    )
    expected_site = None if expected is None else {
        "source_sha256": hashlib.sha256(b"test_cases.py").hexdigest(), "line": expected,
    }
    assert p._failure_site(report) == expected_site
    assert p._failure_site(SimpleNamespace(nodeid=report.nodeid, longrepr="private text")) is None


@pytest.mark.parametrize("subtest", [False, True, "helper"])
def test_failure_line_actual_export_retains_privacy_and_failed_outcome(tmp_path, subtest):
    import importlib.util

    integrity = Path(groups.__file__).resolve().parents[2] / "synthesis-implementation-integrity/scripts"
    spec = importlib.util.spec_from_file_location("failure_line_fixture_owner", integrity / "test_acceptance_batches.py")
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    owner = fixtures.owner()
    root = tmp_path / "source"
    code = (
        "def test_one(subtests):\n"
        "    with subtests.test(part='SYNTHETIC_PRIVATE_PARAMETER'):\n"
        "        assert False, 'SYNTHETIC_PRIVATE_MESSAGE'\n"
    ) if subtest is True else (
        "import pytest\n"
        "@pytest.mark.parametrize('value', [1], ids=['SYNTHETIC_PRIVATE_PARAMETER'])\n"
        "def test_one(value):\n"
        "    assert False, 'SYNTHETIC_PRIVATE_MESSAGE'\n"
    )
    if subtest == "helper":
        code = (
            "from private_helper import fail\n"
            "def test_one():\n"
            "    fail()\n"
        )
    manifest = fixtures.corpus(root, code)
    if subtest == "helper":
        (root / "private_helper.py").write_text(
            "def fail():\n"
            "    raise TimeoutError('SYNTHETIC_PRIVATE_HELPER_MESSAGE')\n"
        )
    value, errors = owner.validate_manifest(manifest, root)
    assert not errors
    plan = owner.batch_plan(owner.case_contract(value, root))
    completed = groups.bounded_run(
        [sys.executable, str(fixtures.OWNER), "run", "--manifest", str(manifest), "--repo-root", str(root), "--receipt"],
        root, 30, dict(os.environ, TMPDIR=str(tmp_path)),
    )
    assert completed.returncode == 1, completed.stdout
    assert groups.decode_acceptance_receipt(completed.stdout)["ok"] is False
    destination = groups.prepare_diagnostics_destination(tmp_path / "public", root)
    receipt = groups.capture_acceptance_diagnostics(completed, root, plan, {}, destination)
    assert receipt["status"] == "RETAINED", receipt
    public = json.loads((Path(destination["path"]) / "diagnostics.json").read_text())
    failed = [phase for batch in public["batches"] for phase in batch["phases"] if phase["outcome"] == "failed"]
    assert len(failed) == (2 if subtest is True else 1)
    detailed = [phase for phase in failed if phase["kind"] == ("subtest" if subtest is True else "phase")]
    assert len(detailed) == 1
    assert detailed[0]["failure_line"] == (4 if subtest is False else 3)
    if subtest is True:
        parent = [phase for phase in failed if phase["kind"] == "phase"]
        assert len(parent) == 1 and parent[0]["when"] == "call"
    assert public["authorizes_release"] is False
    blob = json.dumps(public)
    for private in ["SYNTHETIC_PRIVATE_PARAMETER", "SYNTHETIC_PRIVATE_MESSAGE", "SYNTHETIC_PRIVATE_HELPER_MESSAGE", "private_helper.py", str(root), str(tmp_path)]:
        assert private not in blob
    assert all("failure_line" not in phase for batch in public["batches"] for phase in batch["phases"] if phase["outcome"] != "failed")


def test_failure_site_bounded_selected_caller_and_exact_identity(tmp_path):
    import hashlib

    plugin = groups.InventoryPlugin("fixture", tmp_path / "unused.json")
    source = "test_cases.py"
    def location(path, line):
        return SimpleNamespace(path=path, lineno=line)
    def entry(path, line):
        return SimpleNamespace(reprfileloc=location(path, line))
    representation = SimpleNamespace(
        reprcrash=location("/private/helper.py", 99),
        reprtraceback=SimpleNamespace(reprentries=[
            entry(source, 4), entry(str(plugin.source_root / source), 8),
            entry("/private/helper.py", 99),
        ]),
    )
    report = SimpleNamespace(nodeid=source + "::test_one[PRIVATE]", longrepr=representation)
    expected = {"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "line": 8}
    assert plugin._failure_site(report) == expected
    representation.reprcrash = location(source, 12)
    assert plugin._failure_site(report) == dict(expected, line=12)
    representation.reprcrash = location("/private/helper.py", 99)
    entries = representation.reprtraceback
    entries.reprentries = [entry(source, 8)] * 128
    assert plugin._failure_site(report) == expected
    entries.reprentries.append(entry(source, 8))
    assert plugin._failure_site(report) is None
    for invalid in [None, iter([entry(source, 8)]), "private", {0: entry(source, 8)}]:
        entries.reprentries = invalid
        assert plugin._failure_site(report) is None
    for path, line in [("./test_cases.py", 8), ("other/test_cases.py", 8),
                       ("/private/test_cases.py", 8), (source, True),
                       (source, 0), (source, 1000001), (source, "8")]:
        entries.reprentries = (entry(path, line),)
        assert plugin._failure_site(report) is None


def test_onboarding_partition_is_exhaustive_ordered_and_admits_future_files():
    nodes = [groups.OB + '/test_' + name + '.py::test_one[' + str(i) + ']'
             for i, name in enumerate(('runtime_payload', 'release_runtime',
                 'instruction_new', 'team_new', 'native_new', 'brand_new'))]
    result = groups.partition(nodes)
    assert set(result) == set(groups.ONBOARDING_GROUPS)
    assert sum(result.values(), []).count(nodes[-1]) == 1
    assert result['onboarding-core'] == [nodes[-1]]
    assert sorted(sum(result.values(), [])) == sorted(nodes)
    for selected in result.values():
        assert selected == [node for node in nodes if node in selected]


@pytest.mark.parametrize('bad', ['mixed', 'outside', 'duplicate', 'overlap'])
def test_onboarding_collection_refuses_ambiguous_ownership(monkeypatch, bad):
    nodes = [groups.OB + '/test_runtime_payload.py::test_one']
    if bad == 'mixed':
        nodes += [ids()[0]]
    elif bad == 'outside':
        nodes += ['skills/foreign/test_one.py::test_one']
    elif bad == 'duplicate':
        nodes *= 2
    else:
        monkeypatch.setattr(groups, 'ONBOARDING_RULES', {
            **groups.ONBOARDING_RULES, 'onboarding-core': ('test_runtime_payload',)})
    with pytest.raises(ValueError):
        groups.partition(nodes)


@pytest.mark.parametrize('defect', ['none', 'reason', 'foreign', 'teardown', 'xfail'])
def test_onboarding_optional_skip_requires_exact_existing_contract(tmp_path, defect):
    node = groups.OB + '/test_distribution.py::test_real_package_manager_install_is_usable_without_install_scripts[bun]'
    if defect == 'foreign':
        node = groups.OB + '/test_other.py::test_one'
    p = groups.InventoryPlugin('onboarding-core', tmp_path/'report.json')
    p.full = p.selected = [node]
    phase(p, node, 'setup')
    p.pytest_runtest_logreport(SimpleNamespace(
        nodeid=node, when='call', outcome='skipped', duration=.1,
        wasxfail='expected' if defect == 'xfail' else None,
        longrepr=('source.py', 1, 'Skipped: wrong reason' if defect == 'reason' else
            'Skipped: package-manager consumer acceptance requires npm and bun')))
    phase(p, node, 'teardown', 'failed' if defect == 'teardown' else 'passed')
    assert finish(p).exitstatus == (0 if defect == 'none' else 1)
    receipt = json.loads(p.report.read_text())
    assert receipt['phases'][node]['call']['outcome'] == 'skipped'
    assert receipt['phases'][node]['call']['skip_reason'].startswith('Skipped: ')


def test_onboarding_actual_group_keeps_all_collection_and_future_parameters(tmp_path, monkeypatch):
    root = tmp_path/'source'; scripts = root/groups.OB; scripts.mkdir(parents=True)
    (scripts/'test_runtime_payload.py').write_text('def test_elsewhere(): assert True\n')
    (scripts/'test_brand_new.py').write_text('import pytest\n@pytest.mark.parametrize("n", [1,2])\ndef test_new(n): assert n\n')
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setenv('SYNTHESIS_ACCEPTANCE_SELECTION', str(tmp_path/'foreign-selection.json'))
    code, result = groups.run_group(root, 'onboarding-core')
    assert code == 0 and not result['errors']
    assert len(result['inventory']) == 3 and len(result['selected']) == 2
    assert all(set(row) == {'setup','call','teardown'} for row in result['phases'].values())


def test_ritual_first_failure_retains_traceback_and_success_is_exhaustive(tmp_path):
    import ast
    root = Path(__file__).resolve().parents[3]
    tree = ast.parse((root/'skills/synthesis-skills-manager/scripts/release.py').read_text())
    checks = dict(ast.literal_eval(next(n.value for n in tree.body
        if isinstance(n, ast.AnnAssign) and getattr(n.target,'id','') == 'REQUIRED_CHECKS')))
    command = checks['pytest.rituals-guard-hooks']
    assert command[-2:] == ['-q', '--maxfail=1']
    script = tmp_path/'test_example.py'
    script.write_text('def test_first(): assert False, "CAUSAL_FAILURE"\ndef test_second(): assert True\n')
    env = dict(os.environ, TMPDIR=str(tmp_path))
    failed = groups.bounded_run([sys.executable,'-m','pytest',str(script),*command[-2:]], tmp_path, 15, env)
    assert failed.returncode != 0 and 'CAUSAL_FAILURE' in failed.stdout
    assert '1 failed' in failed.stdout and 'stopping after 1 failures' in failed.stdout
    script.write_text('def test_first(): assert True\ndef test_second(): assert True\n')
    passed = groups.bounded_run([sys.executable,'-m','pytest',str(script),*command[-2:]], tmp_path, 15, env)
    assert passed.returncode == 0 and '2 passed' in passed.stdout


@pytest.mark.parametrize("selector,expected", [
    ("test_journal_storage.py", True),
    ("test_journal_storage.py::test_native_history_crosses_snapshot_limit_and_recovers_exactly", True),
    ("test_journal_storage.py::test_native_history_crosses_snapshot_limit_and_recovers_exactly[x]", True),
    ("test_journal_storage.py::test_atomic_append_replay_projection_rebuild_and_operator", True),
    ("test_journal_storage.py::test_atomic_append_replay_projection_rebuild_and_operator_extra", False),
    ("test_journal_storage.py::TestOther::test_atomic_append_replay_projection_rebuild_and_operator", False),
    ("test_journal_storage.py::test_operator_refuses_if_final_projection_read_exhausts_same_time_budget", False),
    ("test_managed_native_owner.py::test_any", True),
    ("test_managed_native_owner.py", True),
    ("nested/test_managed_native_owner.py::test_any", False),
    ("test_managed_native_owner_extra.py::test_any", False),
])
def test_timing_selector_is_exact_and_preserves_ordinary_deadline_controls(selector, expected):
    assert groups.is_timing_sensitive_selector(groups.AP + "/" + selector) is expected
    assert not groups.is_timing_sensitive_selector("foreign/" + selector)


def test_timing_partition_preserves_complete_ids_and_order():
    journal = groups.AP + "/test_journal_storage.py::"
    nodes = ids() + [journal + "test_native_history_crosses_snapshot_limit_and_recovers_exactly",
        journal + "test_atomic_append_replay_projection_rebuild_and_operator[x]",
        journal + "test_operator_refuses_if_final_projection_read_exhausts_same_time_budget",
        groups.AP + "/test_managed_native_owner.py::test_any"]
    split = groups.partition(nodes)
    assert split["timing"] == [nodes[4], nodes[5], nodes[7]]
    assert split["state"] == [nodes[0], nodes[6]]
    assert sum(len(v) for v in split.values()) == len(nodes)
    assert sorted(sum(split.values(), [])) == sorted(nodes)
    for name, selected in split.items():
        assert selected == [n for n in nodes if groups.group_for(n) == name]
    assert (groups.CHECK_SECONDS, groups.GROUP_SECONDS, groups.ACCEPTANCE_SECONDS) == (900, 880, 6000)


def test_registered_timing_classifier_is_bound_before_fixture_mutation(tmp_path, monkeypatch):
    observer = groups._registered_inventory("timing", tmp_path / "inventory.json")
    namespace = observer.pytest_collection_modifyitems.__func__.__globals__
    journal = groups.AP + "/test_journal_storage.py::test_native_history_crosses_snapshot_limit_and_recovers_exactly"
    monkeypatch.setattr(groups, "is_timing_sensitive_selector", lambda _: False)
    monkeypatch.setattr(groups, "AP", "foreign")
    assert namespace["group_for"](journal) == "timing"
    assert namespace["is_timing_sensitive_selector"].__globals__ is namespace


@pytest.mark.parametrize("cancel_before_timing", [False, True])
def test_actual_scheduler_drains_before_timing_and_preserves_parallel_ordinary_workers(cancel_before_timing):
    import threading
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    active = set()
    trace = []
    def worker(item, cancel):
        with lock:
            assert not active if item == "timing" else "timing" not in active
            active.add(item)
            trace.append(("start", item, sorted(active)))
        if item in ("a", "b"):
            barrier.wait(timeout=5)
            if cancel_before_timing and item == "b":
                assert cancel.wait(5)
        with lock:
            active.remove(item)
            trace.append(("end", item, sorted(active)))
        return item
    result = groups.bounded_map(["a", "b", "timing", "after"], worker, workers=2,
        exclusive_when=lambda item: item == "timing",
        stop_when=lambda value: cancel_before_timing and value == "a")
    assert any(e[0] == "start" and len(e[2]) == 2 for e in trace)
    assert not active
    if cancel_before_timing:
        assert result == ["a", "b", None, None]
        assert all(e[1] not in ("timing", "after") for e in trace)
    else:
        assert result == ["a", "b", "timing", "after"]
        timing = next(i for i, e in enumerate(trace) if e[:2] == ("start", "timing"))
        assert all(next(i for i,e in enumerate(trace) if e[:2] == ("end", n)) < timing for n in ("a", "b"))
