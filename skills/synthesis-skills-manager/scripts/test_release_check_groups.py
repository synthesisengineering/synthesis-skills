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
    assert [result[g] for g in ("state", "native", "evaluation", "core")] == [[n] for n in ids()]
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
    commands = [s.get("run", "") for s in ci["jobs"]["conformance"]["steps"]]
    for group in groups.GROUPS:
        command = [
            "python3",
            "skills/synthesis-skills-manager/scripts/release_check_groups.py",
            "--group",
            group,
        ]
        assert checks["pytest.autopilot." + group] == command
        assert "python " + " ".join(command[1:]) in commands
    assert groups.GROUP_SECONDS < groups.CHECK_SECONDS == 900


def synthetic_root(tmp_path):
    root = tmp_path / "source"
    directory = root / groups.AP
    directory.mkdir(parents=True)
    for name in ("run_state", "native_codex", "evaluation", "brand_new_surface", "native_cancellation"):
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
    assert len(observed) == 7 and len(set(observed)) == 7
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


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_actual_timeout_retains_phase_evidence_without_acceptance(
    tmp_path, monkeypatch, phase
):
    root = tmp_path / "source"
    directory = synthetic(root)
    content = "import pytest,time\ndef test_first():\n    assert True\n"
    if phase == "setup":
        content += "@pytest.fixture\ndef slow():\n    time.sleep(10)\ndef test_second(slow):\n    assert True\n"
    elif phase == "call":
        content += "def test_second():\n    time.sleep(10)\n"
    else:
        content += "@pytest.fixture\ndef slow():\n    yield\n    time.sleep(10)\ndef test_second(slow):\n    assert True\n"
    (directory / "test_brand_new_surface.py").write_text(content)
    monkeypatch.setattr(groups, "GROUP_SECONDS", 1.5)
    start = time.monotonic()
    code, payload = groups.run_group(root, "core")
    assert code != 0 and time.monotonic() - start < 6
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
    (directory / "test_brand_new_surface.py").write_text(
        "import time\ndef test_failed():\n    assert False\ndef test_slow():\n    time.sleep(10)\n"
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

    def completed_without_inventory(command, cwd, timeout, env):
        result = original(command, cwd, timeout, env)
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
    nodes = [groups.AP + '/' + name + '::test_one' for name in (
        'test_native_cancellation.py', 'test_native_admission_freshness.py',
        'test_native_session_owner_chain.py', 'test_native_future_surface.py',
        'test_observation_bridge.py', 'test_future_unclassified.py')]
    result = groups.partition(nodes)
    assert set(result) == {'state', 'native', 'native-control', 'evaluation', 'core'}
    assert result['native-control'] == nodes[:3]
    assert result['native'] == nodes[3:5]
    assert result['core'] == nodes[5:]
    assert sorted(sum(result.values(), [])) == sorted(nodes)
    assert len(set(sum(result.values(), []))) == len(nodes)
    assert groups.CHECK_SECONDS == 900 and groups.GROUP_SECONDS == 880
    assert groups.ACCEPTANCE_SECONDS == 6000


@pytest.mark.parametrize("failure_phase", ["setup", "call", "teardown"])
def test_failure_detail_survives_later_process_cutoff(tmp_path, monkeypatch, failure_phase):
    root = tmp_path / "source"
    directory = synthetic(root)
    content = "import pytest,time\n"
    if failure_phase == "setup":
        content += "@pytest.fixture\ndef broken():\n    raise ValueError('retained-setup-marker')\ndef test_first(broken):\n    pass\n"
    elif failure_phase == "teardown":
        content += "@pytest.fixture\ndef broken():\n    yield\n    raise ValueError('retained-teardown-marker')\ndef test_first(broken):\n    pass\n"
    else:
        content += "def test_first():\n    raise ValueError('retained-call-marker')\n"
    content += "def test_second():\n    time.sleep(10)\n"
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


def test_failure_detail_is_stream_bounded_and_budget_never_resets(tmp_path, monkeypatch):
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
    assert third["status"] == "omitted" and third["reason"] == "diagnostic_budget_exhausted"
    assert p.failure_detail_bytes == 24
    assert groups.REPORT_BYTES == 4 * 1024 * 1024


def test_failure_detail_unicode_missing_and_renderer_refusal_are_explicit(tmp_path, monkeypatch):
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


def test_failure_detail_actual_subtest_keeps_parent_lifecycle_and_refuses_success(tmp_path):
    root = tmp_path / "source"
    directory = synthetic(root)
    (directory / "test_brand_new_surface.py").write_text(
        "def test_one(subtests):\n"
        "    with subtests.test(part='one'):\n"
        "        raise ValueError('retained-subtest-marker')\n"
    )
    code, payload = groups.run_group(root, "core")
    assert code != 0
    evidence = groups.read_progress(Path(payload["fixture_custody"]) / "inventory.progress.jsonl")
    rows = [r for r in evidence["events"] if r.get("kind") == "subtest"]
    assert len(rows) == 1 and rows[0]["outcome"] == "failed"
    assert "retained-subtest-marker" in rows[0]["failure"]["text"]
    assert evidence["authorizes_success"] is False
