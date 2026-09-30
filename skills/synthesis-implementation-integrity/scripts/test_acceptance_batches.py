"""Actual closed-manifest runner regressions; all repositories and effects synthetic."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
import yaml

OWNER = Path(
    os.environ.get(
        "ACCEPTANCE_OWNER", str(Path(__file__).with_name("acceptance_suite.py"))
    )
)


def owner():
    spec = importlib.util.spec_from_file_location("acceptance_batch_owner", OWNER)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def corpus(root, code, cases=None):
    root.mkdir(exist_ok=True)
    (root / "test_cases.py").write_text(code)
    (root / "surface.py").write_text("value = 1\n")
    cases = cases or [{"id": "one", "fixture": "test_cases.py::test_one"}]
    for c in cases:
        c.setdefault("control_class", "acceptance-test")
        c.setdefault("motivating_defect", "exact phase evidence")
        c.setdefault("expected_status", "pass")
    document = {
        "schema": 1,
        "suite": "synthetic-batches",
        "membership": "closed",
        "production_entry_point": "surface.py",
        "enforcing_boundary": "synthetic release",
        "expected_status": "pass",
        "unverified_remainder": "No native acceptance",
        "changed_surfaces": [{"path": "surface.py", "cases": [c["id"] for c in cases]}],
        "cases": cases,
    }
    path = root / "manifest.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


def run(root, code, cases=None, env=None):
    path = corpus(root, code, cases)
    completed = subprocess.run(
        [
            sys.executable,
            str(OWNER),
            "run",
            "--manifest",
            str(path),
            "--repo-root",
            str(root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=40,
        env=env,
    )
    return completed, json.loads(completed.stdout)


@pytest.mark.parametrize(
    "code",
    [
        "import pytest\n@pytest.mark.skip(reason='not executed')\ndef test_one(): assert False\n",
        "import pytest\n@pytest.mark.xfail(reason='expected by pytest')\ndef test_one(): assert False\n",
        "import pytest\n@pytest.mark.xfail(reason='unexpected pass')\ndef test_one(): pass\n",
    ],
)
def test_skipped_and_xfail_are_never_acceptance(tmp_path, code):
    completed, result = run(tmp_path, code)
    assert completed.returncode != 0 and result["ok"] is False
    assert result["cases"][0]["matched"] is False


def test_duplicate_cases_reuse_one_exact_execution(tmp_path):
    code = "from pathlib import Path\ndef test_one():\n p=Path('calls.txt');p.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
    cases = [{"id": str(i), "fixture": "test_cases.py::test_one"} for i in range(12)]
    # A fixture deliberately writes outside source in the actual measurement;
    # this original control uses a separate fixed path below the pytest tmpdir.
    calls = tmp_path.parent / (tmp_path.name + "-calls.txt")
    code = code.replace("Path('calls.txt')", "Path(" + repr(str(calls)) + ")")
    completed, result = run(tmp_path, code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert calls.read_text() == "x"
    assert len(result["cases"]) == 12


def test_real_pass_and_expected_call_failure(tmp_path):
    cases = [
        {"id": "yes", "fixture": "test_cases.py::test_yes"},
        {"id": "no", "fixture": "test_cases.py::test_no", "expected_status": "fail"},
    ]
    completed, result = run(
        tmp_path,
        "def test_yes(): pass\ndef test_no(): assert False, 'causal call assertion'\n",
        cases,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert [c["status"] for c in result["cases"]] == ["passed", "failed"]


def test_expected_failure_does_not_accept_setup_failure(tmp_path):
    completed, result = run(
        tmp_path,
        "import pytest\n@pytest.fixture(autouse=True)\ndef broken(): raise RuntimeError('setup failed')\ndef test_one(): pass\n",
        [
            {
                "id": "negative",
                "fixture": "test_cases.py::test_one",
                "expected_status": "fail",
            }
        ],
    )
    assert completed.returncode != 0 and not result["ok"]


def test_parameter_expansion_and_overlapping_selectors(tmp_path):
    code = "import pytest\n@pytest.mark.parametrize('value',[1,2])\ndef test_one(value): assert value > 0\n"
    cases = [
        {"id": "all", "fixture": "test_cases.py::test_one"},
        {"id": "single", "fixture": "test_cases.py::test_one[1]"},
    ]
    completed, result = run(tmp_path, code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["cases"][0]["nodes"] == [
        "test_cases.py::test_one[1]",
        "test_cases.py::test_one[2]",
    ]
    assert result["cases"][1]["nodes"] == ["test_cases.py::test_one[1]"]
    assert len(result["execution"]["batches"]) == 1


def test_pytest_environment_and_config_cannot_deselect(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -k no_such_test\n")
    env = {
        **os.environ,
        "PYTEST_ADDOPTS": "--collect-only",
        "PYTEST_PLUGINS": "missing_plugin",
    }
    completed, result = run(tmp_path, "def test_one(): pass\n", env=env)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert result["cases"][0]["nodes"] == ["test_cases.py::test_one"]


@pytest.mark.parametrize(
    "code",
    [
        "broken Python !\n",
        'import pytest\n@pytest.fixture(autouse=True)\ndef fixture():\n yield\n raise RuntimeError("teardown")\ndef test_one(): pass\n',
    ],
)
def test_collection_and_teardown_fail_closed(tmp_path, code):
    completed, result = run(tmp_path, code)
    assert completed.returncode != 0 and not result["ok"]
    assert not result["cases"][0]["matched"]


def test_source_mutation_after_test_is_not_acceptance(tmp_path):
    completed, result = run(
        tmp_path,
        "from pathlib import Path\ndef test_one(): Path('surface.py').write_text('changed')\n",
    )
    assert completed.returncode != 0 and not result["ok"]
    assert result["execution"]["source_unchanged"] is False


def test_receipt_phase_and_inventory_tampering_refuses(tmp_path):
    import copy

    completed, result = run(tmp_path, "def test_one(): pass\n")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    module = owner()
    contract = result["execution"]["contract"]
    module.verify_execution(result, contract)
    for change in (
        "missing",
        "extra",
        "duplicate",
        "skip",
        "xfail",
        "polarity",
        "contract",
        "exit",
        "not_run",
    ):
        altered = copy.deepcopy(result)
        batch = altered["execution"]["batches"][0]
        inventory = batch["inventory"]
        if change == "missing":
            inventory["phases"].clear()
        elif change == "extra":
            inventory["phases"]["foreign"] = {}
        elif change == "duplicate":
            inventory["inventory"] *= 2
        elif change == "skip":
            inventory["phases"]["test_cases.py::test_one"]["call"]["outcome"] = (
                "skipped"
            )
        elif change == "xfail":
            inventory["phases"]["test_cases.py::test_one"]["call"]["wasxfail"] = (
                "reason"
            )
        elif change == "polarity":
            altered["cases"][0]["expected_status"] = "fail"
        elif change == "contract":
            altered["execution"]["contract"][0]["selector"] = "foreign.py::test_one"
        elif change == "exit":
            batch["returncode"] = 1
        else:
            altered["cases"] = []
        with pytest.raises((ValueError, KeyError)):
            module.verify_execution(altered, contract)


def test_timeout_retains_partial_phases_and_reaps_child(tmp_path, monkeypatch):
    module = owner()
    monkeypatch.setattr(module, "CASE_SECONDS", 1.0)
    pid = tmp_path.parent / (tmp_path.name + "-descendant.pid")
    code = (
        "import subprocess,sys,os\nfrom pathlib import Path\ndef test_one():\n"
        ' p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(120)"])\n'
        " Path(" + repr(str(pid)) + ").write_text(str(p.pid))\n p.wait()\n"
    )
    manifest = corpus(tmp_path, code)
    validated, errors = module.validate_manifest(manifest, tmp_path)
    assert not errors
    result, status = module.execute(validated, tmp_path)
    assert status == 1 and not result["ok"]
    batch = result["execution"]["batches"][0]
    assert batch["partial_execution"]["authorizes_success"] is False
    assert Path(batch["process_custody"], "result.json").is_file()
    assert pid.is_file(), "fixture must reach the actual descendant before deadline"
    proc = subprocess.run(
        ["ps", "-p", pid.read_text(), " -o".strip(), "stat="],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert not proc.stdout.strip() or proc.stdout.strip().startswith("Z")


def test_same_filename_different_directories_are_separate_batches(tmp_path):
    module = owner()
    contract = [
        {
            "id": str(i),
            "selector": f"{folder}/test_same.py::test_one",
            "expected_status": "pass",
        }
        for i, folder in enumerate(("one", "two"))
    ]
    assert len(module.batch_plan(contract)) == 2


def test_partial_progress_cannot_replace_final_inventory(tmp_path, monkeypatch):
    module = owner()
    real = module.checks.bounded_run

    def without_final(*a, **kw):
        result = real(*a, **kw)
        report = Path(a[3]["SYNTHESIS_RELEASE_TEST_REPORT"])
        report.rename(report.with_suffix(".retained.json"))
        return result

    monkeypatch.setattr(module.checks, "bounded_run", without_final)
    manifest = corpus(tmp_path, "def test_one(): pass\n")
    validated, errors = module.validate_manifest(manifest, tmp_path)
    assert not errors
    receipt, status = module.execute(validated, tmp_path)
    assert status == 1 and not receipt["ok"]
    assert (
        receipt["execution"]["batches"][0]["partial_execution"]["status"]
        == "DIAGNOSTIC_ONLY"
    )


@pytest.mark.parametrize("defect", ["collection", "removed", "doubled"])
def test_collection_inventory_cannot_hide_requested_nodes(tmp_path, defect):
    if defect == "collection":
        hook = "def pytest_collection_modifyitems(items): items.clear()\n"
    elif defect == "removed":
        hook = "def pytest_collection_modifyitems(items): items.pop()\n"
    else:
        hook = "def pytest_collection_modifyitems(items): items.extend(items[:1])\n"
    (tmp_path / "conftest.py").write_text(hook)
    completed, receipt = run(tmp_path, "def test_one(): pass\n")
    assert completed.returncode != 0 and not receipt["ok"]


def test_process_failure_cannot_masquerade_as_expected_test_failure(
    tmp_path, monkeypatch
):
    module = owner()
    real = module.checks.bounded_run

    def failed_owner(*args, **kwargs):
        result = real(*args, **kwargs)
        result.failure = "synthetic owner cleanup failure"
        return result

    monkeypatch.setattr(module.checks, "bounded_run", failed_owner)
    manifest = corpus(
        tmp_path,
        "def test_one(): assert False\n",
        [
            {
                "id": "negative",
                "fixture": "test_cases.py::test_one",
                "expected_status": "fail",
            }
        ],
    )
    validated, errors = module.validate_manifest(manifest, tmp_path)
    assert not errors
    receipt, code = module.execute(validated, tmp_path)
    assert code and not receipt["ok"]


def test_chunk_bound_preserves_every_case_and_selector():
    module = owner()
    contract = [
        {
            "id": str(i),
            "selector": f"test_same.py::test_{i % 70}",
            "expected_status": "pass",
        }
        for i in range(90)
    ]
    plan = module.batch_plan(contract)
    assert len(plan) == 9 and all(len(b["selectors"]) <= 8 for b in plan)
    assert [n for b in plan for n in b["selectors"]] == list(
        dict.fromkeys(c["selector"] for c in contract)
    )
    assert module.CASE_SECONDS == 300 and module.checks.ACCEPTANCE_SECONDS == 6000


def test_selected_virtualenv_survives_batch_process(tmp_path):
    import venv

    environment = tmp_path / "selected-environment"
    venv.EnvBuilder(with_pip=False, system_site_packages=True).create(environment)
    executable = environment / "bin/python"
    inspected = subprocess.run(
        [
            str(executable),
            "-c",
            'import sysconfig; print(sysconfig.get_path("purelib"))',
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    site = Path(inspected.stdout.strip())
    site.mkdir(parents=True, exist_ok=True)
    (site / "acceptance_sentinel.py").write_text("VALUE='selected environment'\n")
    root = tmp_path / "source"
    manifest = corpus(
        root,
        "import sys,acceptance_sentinel\ndef test_one():\n assert acceptance_sentinel.VALUE=='selected environment'\n assert sys.prefix=="
        + repr(str(environment))
        + "\n",
    )
    completed = subprocess.run(
        [
            str(executable),
            str(OWNER),
            "run",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(root),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["ok"]


def test_copied_release_owner_closure_and_missing_dependency_refusal(tmp_path):
    import shutil

    release_root = tmp_path / "verified-release"
    runner = (
        release_root
        / "skills/synthesis-implementation-integrity/scripts/acceptance_suite.py"
    )
    helper = (
        release_root / "skills/synthesis-skills-manager/scripts/release_check_groups.py"
    )
    runner.parent.mkdir(parents=True)
    helper.parent.mkdir(parents=True)
    shutil.copy2(OWNER, runner)
    canonical = (
        OWNER.parents[2] / "synthesis-skills-manager/scripts/release_check_groups.py"
    )
    shutil.copy2(canonical, helper)
    root = tmp_path / "fixture"
    manifest = corpus(root, "def test_one(): pass\n")
    command = [
        sys.executable,
        str(runner),
        "run",
        "--manifest",
        str(manifest),
        "--repo-root",
        str(root),
        "--json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=40)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["ok"]
    helper.rename(helper.with_suffix(".retained"))
    refused = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert refused.returncode != 0 and "release_check_groups" in refused.stderr
    # Neither release authoring nor acceptance acquires installed launcher authority.
    runtime_path = OWNER.parents[2] / "synthesis-onboarding/scripts/release_runtime.py"
    spec = importlib.util.spec_from_file_location(
        "acceptance_runtime_closure", runtime_path
    )
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    assert (
        "synthesis-implementation-integrity/scripts/acceptance_suite.py"
        not in runtime.PUBLIC_ENTRYPOINTS
    )
    assert (
        "synthesis-skills-manager/scripts/release.py" not in runtime.PUBLIC_ENTRYPOINTS
    )
    before = runtime.tree_digest(release_root)
    helper.write_text("# modified owner\n")
    assert runtime.tree_digest(release_root) != before


def test_actual_class_and_parameter_expansion_excludes_prefix_sibling(tmp_path):
    code = "import pytest\nclass TestClass:\n @pytest.mark.parametrize('value',[1,2])\n def test_one(self,value): assert value > 0\n def test_two(self): pass\nclass TestClassOther:\n def test_forbidden(self): assert False, 'prefix sibling must not run'\n"
    cases = [
        {"id": "class", "fixture": "test_cases.py::TestClass"},
        {"id": "method", "fixture": "test_cases.py::TestClass::test_one"},
        {"id": "parameter", "fixture": "test_cases.py::TestClass::test_one[1]"},
    ]
    completed, receipt = run(tmp_path, code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert receipt["cases"][0]["nodes"] == [
        "test_cases.py::TestClass::test_one[1]",
        "test_cases.py::TestClass::test_one[2]",
        "test_cases.py::TestClass::test_two",
    ]
    assert len(receipt["cases"][1]["nodes"]) == 2
    assert len(receipt["cases"][2]["nodes"]) == 1
    assert not any(
        "TestClassOther" in node
        for node in receipt["execution"]["batches"][0]["inventory"]["selected"]
    )


def test_actual_same_filename_directories_execute_in_distinct_batches(tmp_path):
    for name in ("one", "two"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "test_same.py").write_text("def test_one(): pass\n")
    cases = [
        {"id": name, "fixture": name + "/test_same.py::test_one"}
        for name in ("one", "two")
    ]
    completed, receipt = run(tmp_path, "def test_one(): pass\n", cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert len(receipt["execution"]["batches"]) == 2


@pytest.mark.parametrize(
    "code,expected,accepted",
    [
        (
            "import pytest\n@pytest.mark.xfail(strict=True,reason='unexpected')\ndef test_one(): pass\n",
            "fail",
            False,
        ),
        ("def test_one(): assert False\n", "fail", True),
        (
            "import pytest\n@pytest.mark.xfail(False,strict=True,reason='inactive')\ndef test_one(): pass\n",
            "pass",
            True,
        ),
        (
            "import pytest\n@pytest.mark.xfail(False,strict=True,reason='inactive')\ndef test_one(): assert False\n",
            "fail",
            True,
        ),
    ],
)
def test_strict_xpass_is_not_an_expected_call_failure(
    tmp_path, code, expected, accepted
):
    completed, result = run(
        tmp_path,
        code,
        [
            {
                "id": "strict-control",
                "fixture": "test_cases.py::test_one",
                "expected_status": expected,
            }
        ],
    )
    assert result["ok"] is accepted
    assert (completed.returncode == 0) is accepted


@pytest.mark.parametrize("hook_order", ["tryfirst", "trylast"])
@pytest.mark.parametrize("scope", ["function", "class"])
def test_original_collection_retains_required_expansions(tmp_path, hook_order, scope):
    calls = tmp_path.parent / (tmp_path.name + "-executed.txt")
    (tmp_path / "conftest.py").write_text(
        "import pytest\n@pytest.hookimpl(" + hook_order + "=True)\n"
        "def pytest_collection_modifyitems(items):\n"
        " items[:] = [i for i in items if not i.nodeid.endswith('[2]')]\n"
    )
    if scope == "function":
        code = (
            "import pytest\nfrom pathlib import Path\n"
            "@pytest.mark.parametrize('value',[1,2])\n"
            "def test_one(value):\n"
            " Path(" + repr(str(calls)) + ").write_text('executed')\n"
            " assert value == 1\n"
        )
        selector = "test_cases.py::test_one"
    else:
        code = (
            "import pytest\nfrom pathlib import Path\nclass TestScope:\n"
            " @pytest.mark.parametrize('value',[1,2])\n"
            " def test_one(self,value):\n"
            "  Path(" + repr(str(calls)) + ").write_text('executed')\n"
            "  assert value == 1\n"
        )
        selector = "test_cases.py::TestScope"
    completed, receipt = run(tmp_path, code, [{"id": "all", "fixture": selector}])
    assert completed.returncode != 0 and not receipt["ok"]
    assert not calls.exists(), "incomplete required collection must refuse before calls"
    inventory = receipt["execution"]["batches"][0]["inventory"]
    assert len(inventory["inventory"]) == 2
    assert any(n.endswith("[2]") for n in inventory["inventory"])


def test_original_collection_allows_unselected_filtering_and_selected_reordering(
    tmp_path,
):
    (tmp_path / "conftest.py").write_text(
        "import pytest\n@pytest.hookimpl(tryfirst=True)\n"
        "def pytest_collection_modifyitems(items):\n"
        " items[:] = list(reversed([i for i in items if not i.nodeid.endswith('[2]')]))\n"
    )
    code = (
        "import pytest\n@pytest.mark.parametrize('value',[1,2,3])\n"
        "def test_one(value): assert value in (1,3)\n"
    )
    cases = [
        {"id": "first", "fixture": "test_cases.py::test_one[1]"},
        {"id": "last", "fixture": "test_cases.py::test_one[3]"},
    ]
    completed, receipt = run(tmp_path, code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert receipt["ok"] is True
    inventory = receipt["execution"]["batches"][0]["inventory"]
    assert len(inventory["inventory"]) == 3
    assert inventory["selected"] == [c["fixture"] for c in cases]


@pytest.fixture(scope="module")
def real_subtest_batch(tmp_path_factory):
    pytest.importorskip("_pytest.subtests", reason="typed subtests require pytest 9")
    root = tmp_path_factory.mktemp("real-subtest-evidence")
    code = (
        "def test_one(subtests):\n with subtests.test(value=1):\n  assert True\n"
        "def test_two(subtests):\n with subtests.test(value=2):\n  assert True\n"
    )
    cases = [
        {"id": "one", "fixture": "test_cases.py::test_one"},
        {"id": "two", "fixture": "test_cases.py::test_two"},
    ]
    completed, receipt = run(root, code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert receipt["ok"] is True
    (root.parent / "subtest-positive.stdout").write_text(completed.stdout)
    (root.parent / "subtest-positive.stderr").write_text(completed.stderr)
    return receipt


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration", None),
        ("duration", True),
        ("duration", -1),
        ("duration", "0"),
        ("duration", float("nan")),
        ("duration", float("inf")),
        ("duration", float("-inf")),
        ("ordinal", True),
        ("ordinal", 1.0),
        ("ordinal", 0),
        ("ordinal", 2),
        ("ordinal", "1"),
        ("ordinal", None),
    ],
)
def test_actual_batch_subtest_schema_refuses_malformed_evidence(
    real_subtest_batch, field, value
):
    import copy

    module = owner()
    altered = copy.deepcopy(real_subtest_batch)
    row = altered["execution"]["batches"][0]["inventory"]["subtests"][
        "test_cases.py::test_one"
    ][0]
    if value is None:
        row.pop(field)
    else:
        row[field] = value
    with pytest.raises(ValueError, match="subtest"):
        module.verify_execution(altered, altered["execution"]["contract"])


def test_actual_batch_subtest_aggregate_matches_producer_bound(
    real_subtest_batch, monkeypatch
):
    import copy

    module = owner()
    receipt = copy.deepcopy(real_subtest_batch)
    # Two parents together exactly exhaust this synthetic finite ceiling.
    monkeypatch.setattr(module.checks, "MAX_TESTS", 2)
    rows = receipt["execution"]["batches"][0]["inventory"]["subtests"]
    rows["test_cases.py::test_one"][0]["duration"] = 0
    rows["test_cases.py::test_two"][0]["duration"] = 0.125
    module.verify_execution(receipt, receipt["execution"]["contract"])
    rows["test_cases.py::test_one"].append(
        {"ordinal": 2, "outcome": "passed", "duration": 0}
    )
    with pytest.raises(ValueError, match="count ceiling"):
        module.verify_execution(receipt, receipt["execution"]["contract"])


def test_module_bounded_eight_selector_partition_is_exhaustive():
    module = owner()
    contract = [
        {
            "id": f"case-{directory}-{i}",
            "selector": f"{directory}/test_cases.py::test_{i}",
            "expected_status": "pass",
        }
        for directory in ("one", "two")
        for i in range(19)
    ]
    contract.append({**contract[0], "id": "duplicate-reference"})
    plan = module.batch_plan(contract)
    assert len(plan) == 6
    selected = [selector for batch in plan for selector in batch["selectors"]]
    assert selected == list(dict.fromkeys(c["selector"] for c in contract))
    assert all(len(batch["selectors"]) <= 8 for batch in plan)
    assert all(
        len({s.split("::")[0] for s in batch["selectors"]}) == 1 for batch in plan
    )
    assert module.CASE_SECONDS == 300
    assert module.checks.ACCEPTANCE_SECONDS == 6000


def test_current_manifest_module_partition_keeps_every_case_and_polarity():
    module = owner()
    root = Path(__file__).resolve().parents[3]
    manifest = root / "skills/synthesis-implementation-integrity/acceptance-suite.yaml"
    validated, errors = module.validate_manifest(manifest, root)
    assert not errors
    contract = module.case_contract(validated, root)
    plan = module.batch_plan(contract)
    selectors = [s for batch in plan for s in batch["selectors"]]
    assert len(selectors) == len(set(selectors))
    assert set(selectors) == {case["selector"] for case in contract}
    assert all(len(batch["selectors"]) <= 8 for batch in plan)
    assert all(
        len({s.split("::")[0] for s in batch["selectors"]}) == 1 for batch in plan
    )
    assert all(case["expected_status"] in {"pass", "fail"} for case in contract)


def actual_diagnostic_run(tmp_path, code, cases=None):
    module = owner()
    root = tmp_path / "source"
    path = corpus(root, code, cases)
    contract, errors = module.validate_manifest(path, root)
    assert not errors
    plan = module.batch_plan(module.case_contract(contract, root))
    completed = module.checks.bounded_run(
        [
            sys.executable,
            str(OWNER),
            "run",
            "--manifest",
            str(path),
            "--repo-root",
            str(root),
            "--receipt",
        ],
        root,
        30,
    )
    target = module.checks.prepare_diagnostics_destination(tmp_path / "published", root)
    return module, root, completed, plan, target


def test_actual_runner_diagnostics_keep_private_failure_out_of_public_artifact(
    tmp_path,
):
    module, root, completed, plan, target = actual_diagnostic_run(
        tmp_path,
        "import pytest\n@pytest.mark.parametrize('value', [1], ids=['private-parameter-marker'])\ndef test_one(value): raise RuntimeError('private-failure-marker')\n",
    )
    assert completed.returncode != 0
    result = module.checks.capture_acceptance_diagnostics(
        completed, root, plan, {}, target
    )
    assert result["status"] == "RETAINED"
    raw = module.checks.decode_acceptance_receipt(completed.stdout)
    assert raw["ok"] is False
    public = json.loads((Path(target["path"]) / "diagnostics.json").read_text())
    assert public["batches"][0]["phases"]
    blob = json.dumps(public)
    assert (
        "private-parameter-marker" not in blob and "private-failure-marker" not in blob
    )
    assert str(tmp_path) not in blob
    local = Path(completed.fixture_custody) / "diagnostics/raw"
    assert any(
        b"private-failure-marker" in item.read_bytes() for item in local.iterdir()
    )
    assert public["authorizes_release"] is False


@pytest.mark.parametrize(
    "change",
    [
        "external",
        "symlink",
        "same_bytes_replaced",
        "inventory_changed",
        "progress_fifo",
    ],
)
def test_actual_runner_diagnostic_members_refuse_tamper(tmp_path, change):
    module, root, completed, plan, target = actual_diagnostic_run(
        tmp_path, "def test_one(): pass\n"
    )
    receipt = module.checks.decode_acceptance_receipt(completed.stdout)
    batch = receipt["execution"]["batches"][0]
    group = Path(batch["fixture_custody"])
    if change == "same_bytes_replaced":
        path = group / "inventory.json"
        data = path.read_bytes()
        path.rename(group / "retained-original.json")
        path.write_bytes(data)
    elif change == "inventory_changed":
        (group / "inventory.json").write_text("{}")
    elif change == "progress_fifo":
        path = group / "inventory.progress.jsonl"
        path.rename(group / "retained-progress.jsonl")
        os.mkfifo(path)
    elif change == "symlink":
        alias = group.with_name(group.name + "-alias")
        group.rename(alias)
        group.symlink_to(alias, target_is_directory=True)
    else:
        # Forge only the receipt's indexed path while keeping actual owner bytes pinned.
        receipt["execution"]["batches"][0]["fixture_custody"] = str(
            tmp_path / "foreign"
        )
        completed.stdout = module.checks.encode_acceptance_receipt(receipt)
    result = module.checks.capture_acceptance_diagnostics(
        completed, root, plan, {}, target
    )
    assert result["status"] == "REFUSED"


def test_actual_killed_batch_partial_phases_stay_diagnostic(tmp_path, monkeypatch):
    module = owner()
    # Reduce only the synthetic batch's wall budget, preserving the production ceiling.
    monkeypatch.setattr(module, "CASE_SECONDS", 2)
    root = tmp_path / "source"
    path = corpus(root, "import time\ndef test_one(): time.sleep(30)\n")
    validated, errors = module.validate_manifest(path, root)
    assert not errors
    result, status = module.execute(validated, root)
    assert status != 0 and result["ok"] is False
    batch = result["execution"]["batches"][0]
    assert batch["process_failure"]
    assert batch["partial_execution"]["authorizes_success"] is False
    assert not (Path(batch["fixture_custody"]) / "inventory.json").exists()


def test_actual_timeout_exports_partial_phases_without_acceptance(tmp_path):
    module = owner()
    root = tmp_path / "source"
    path = corpus(root, "import time\ndef test_one(): time.sleep(30)\n")
    validated, errors = module.validate_manifest(path, root)
    assert not errors
    plan = module.batch_plan(module.case_contract(validated, root))
    program = (
        "import importlib.util,json; from pathlib import Path; "
        + "s=importlib.util.spec_from_file_location('actual',"
        + repr(str(OWNER))
        + ");"
        + "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.CASE_SECONDS=2;"
        + "v,e=m.validate_manifest(Path("
        + repr(str(path))
        + "),Path("
        + repr(str(root))
        + "));"
        + "r,c=m.execute(v,Path("
        + repr(str(root))
        + "));print(m.checks.encode_acceptance_receipt(r));raise SystemExit(c)"
    )
    completed = module.checks.bounded_run([sys.executable, "-c", program], root, 20)
    assert completed.returncode != 0
    target = module.checks.prepare_diagnostics_destination(tmp_path / "public", root)
    result = module.checks.capture_acceptance_diagnostics(
        completed, root, plan, {}, target
    )
    assert result["status"] == "INCOMPLETE"
    report = json.loads((Path(target["path"]) / "diagnostics.json").read_text())
    assert report["batches"][0]["inventory"] == "MISSING"
    assert report["batches"][0]["phases"][0]["when"] == "setup"
    assert report["authorizes_release"] is False
    assert module.checks.decode_acceptance_receipt(completed.stdout)["ok"] is False


@pytest.mark.parametrize("kind", ["class", "parameters"])
@pytest.mark.parametrize("broad_first", [True, False])
def test_overlapping_selector_families_execute_once_across_batch_boundary(
    tmp_path, kind, broad_first
):
    calls = tmp_path / "observed-calls"
    write = f" p=Path({str(calls)!r});p.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
    if kind == "class":
        code = "from pathlib import Path\nclass TestFamily:\n"
        for i in range(8):
            code += f" def test_{i}(self):\n" + (" " + write if i == 7 else "  pass\n")
        broad = "test_cases.py::TestFamily"
        narrow = [f"{broad}::test_{i}" for i in range(8)]
    else:
        code = (
            "from pathlib import Path\nimport pytest\n"
            "@pytest.mark.parametrize('n',range(8))\ndef test_family(n):\n"
            " if n==7:\n" + " " + write
        )
        broad = "test_cases.py::test_family"
        narrow = [f"{broad}[{i}]" for i in range(8)]
    selectors = ([broad] + narrow) if broad_first else (narrow + [broad])
    cases = [{"id": str(i), "fixture": s} for i, s in enumerate(selectors)]
    completed, receipt = run(tmp_path / "source", code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert receipt["ok"] and calls.read_text() == "x"
    assert [c["id"] for c in receipt["cases"]] == [str(i) for i in range(9)]
    assert len(receipt["execution"]["batches"]) == 1
    batch = receipt["execution"]["batches"][0]
    assert batch["selectors"] == selectors
    assert batch["execution_selectors"] == [broad]
    assert len(batch["inventory"]["phases"]) == 8
    owner().verify_execution(receipt, receipt["execution"]["contract"])


def test_overlapping_reference_must_actually_collect_before_any_execution(tmp_path):
    marker = tmp_path / "must-not-run"
    code = f"from pathlib import Path\nclass TestFamily:\n def test_one(self): Path({str(marker)!r}).write_text('effect')\n"
    cases = [
        {"id": "all", "fixture": "test_cases.py::TestFamily"},
        {"id": "missing", "fixture": "test_cases.py::TestFamily::test_absent"},
    ]
    completed, receipt = run(tmp_path / "source", code, cases)
    assert completed.returncode != 0 and not receipt["ok"]
    assert not marker.exists()
    assert not any(c["matched"] for c in receipt["cases"])


def test_shared_execution_retains_individual_expected_polarity(tmp_path):
    code = "import pytest\n@pytest.mark.parametrize('n',range(9))\ndef test_value(n): assert n != 8\n"
    cases = [
        {"id": str(i), "fixture": f"test_cases.py::test_value[{i}]"} for i in range(8)
    ]
    cases.append(
        {"id": "all", "fixture": "test_cases.py::test_value", "expected_status": "fail"}
    )
    completed, receipt = run(tmp_path, code, cases)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert [c["status"] for c in receipt["cases"]] == ["passed"] * 8 + ["failed"]
    assert len(receipt["execution"]["batches"]) == 1


def test_execution_owner_evidence_cannot_be_removed_or_duplicated(tmp_path):
    import copy

    cases = [{"id": str(i), "fixture": f"test_cases.py::test_{i}"} for i in range(9)]
    completed, receipt = run(
        tmp_path, "".join(f"def test_{i}(): pass\n" for i in range(9)), cases
    )
    assert completed.returncode == 0
    module = owner()
    assert len(receipt["execution"]["batches"]) == 2
    for change in ("missing-owner", "duplicate-phase", "duplicate-batch"):
        forged = copy.deepcopy(receipt)
        batches = forged["execution"]["batches"]
        if change == "missing-owner":
            batches[0].pop("execution_selectors")
        elif change == "duplicate-phase":
            node = batches[0]["inventory"]["selected"][0]
            batches[1]["inventory"]["selected"].append(node)
            batches[1]["inventory"]["phases"][node] = batches[0]["inventory"]["phases"][
                node
            ]
        else:
            batches.append(copy.deepcopy(batches[0]))
        with pytest.raises(ValueError):
            module.verify_execution(forged, forged["execution"]["contract"])
