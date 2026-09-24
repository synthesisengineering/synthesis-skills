"""Conformance must work without site packages and refuse dependency drift."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parent
SOURCE = SCRIPTS.parents[2]


def runtime():
    spec = importlib.util.spec_from_file_location("owned_yaml_test_runtime", SCRIPTS / "yaml_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_python(tmp_path, arguments):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    environment = {"HOME": str(home), "PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"}
    executable = os.environ.get("SYNTHESIS_TEST_CLEAN_PYTHON", sys.executable)
    return subprocess.run([executable, "-I", "-S", "-B", *arguments], cwd=home, env=environment,
                          capture_output=True, text=True, timeout=60)


def test_clean_python_source_conformance_needs_no_site_packages(tmp_path):
    absent = clean_python(tmp_path, ["-c", "import importlib.util; assert importlib.util.find_spec('yaml') is None"])
    assert absent.returncode == 0, absent.stderr
    result = clean_python(tmp_path, [str(SCRIPTS / "conformance.py"), "source", "--source-root", str(SOURCE), "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source.yaml-runtime" in result.stdout and "6.0.3" in result.stdout


def test_owned_yaml_preserves_ambient_module_and_refuses_object_tags(tmp_path):
    script = r'''import sys,types
sys.path.insert(0,sys.argv[1])
hostile=types.ModuleType('yaml')
hostile.__getattr__=lambda name: (_ for _ in ()).throw(AssertionError('ambient yaml accessed'))
sys.modules['yaml']=hostile
from yaml_runtime import load_yaml
before=list(sys.path)
module=load_yaml()
assert module.__version__=='6.0.3' and module.__with_libyaml__ is False
assert module.safe_load('mapping:\n  values: [one, two]\n')=={'mapping':{'values':['one','two']}}
try: module.safe_load('!!python/object/apply:os.system ["echo invalid"]')
except module.YAMLError: pass
else: raise AssertionError('unsafe object tag accepted')
assert sys.modules['yaml'] is hostile and list(sys.path)==before
print('OWNED_YAML_VERIFIED')
'''
    result = clean_python(tmp_path, ["-c", script, str(SCRIPTS)])
    assert result.returncode == 0 and "OWNED_YAML_VERIFIED" in result.stdout, result.stderr


@pytest.mark.parametrize("damage", ["missing", "content", "mode", "symlink", "extra", "manifest", "manifest-mode", "root-link"])
def test_owned_yaml_refuses_unverified_payload(tmp_path, damage):
    module = runtime()
    payload = tmp_path / "pyyaml"
    shutil.copytree(module.PAYLOAD, payload)
    target = payload / "yaml/constructor.py"
    if damage == "missing":
        target.unlink()
    elif damage == "content":
        target.write_text("raise AssertionError('unverified dependency executed')\n")
    elif damage == "mode":
        target.chmod(0o755)
    elif damage == "symlink":
        saved = tmp_path / "outside.py"
        saved.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(saved)
    elif damage == "extra":
        (payload / "unexpected.py").write_text("raise AssertionError('unverified extra executed')\n")
    elif damage == "manifest":
        (payload / "manifest.json").write_text("{}\n")
    elif damage == "manifest-mode":
        (payload / "manifest.json").chmod(0o755)
    else:
        link = tmp_path / "linked-payload"
        link.symlink_to(payload, target_is_directory=True)
        payload = link
    with pytest.raises(module.DependencyError):
        module.load_yaml(payload)


def test_owned_yaml_executes_verified_bytes_after_file_change(tmp_path, monkeypatch):
    module = runtime()
    payload = tmp_path / "pyyaml"
    shutil.copytree(module.PAYLOAD, payload)
    original = module.verified_bytes
    def snapshot_then_change(root):
        contents = original(root)
        (root / "yaml/constructor.py").write_text("raise AssertionError('unverified changed bytes executed')\n")
        return contents
    monkeypatch.setattr(module, "verified_bytes", snapshot_then_change)
    assert module.load_yaml(payload).safe_load("value: 42") == {"value": 42}
    monkeypatch.setattr(module, "verified_bytes", original)
    with pytest.raises(module.DependencyError):
        module.load_yaml(payload)


def test_owned_yaml_ignores_generated_bytecode_without_loading_it(tmp_path):
    module = runtime()
    payload = tmp_path / "pyyaml"
    shutil.copytree(module.PAYLOAD, payload)
    cache = payload / "yaml/__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "constructor.cpython-312.pyc").write_bytes(b"untrusted generated cache")
    assert module.load_yaml(payload).safe_load("value: true") == {"value": True}


@pytest.mark.parametrize("corrupt", [False, True])
def test_projected_conformance_keeps_owned_yaml_dependency(tmp_path, corrupt):
    sys.path.insert(0, str(SOURCE / "skills/synthesis-onboarding/scripts"))
    import modular
    inventory = modular.runtime_files(SOURCE)
    assert "skills/synthesis-agent-conformance/vendor/pyyaml/manifest.json" in inventory
    payload = tmp_path / "projected"
    modular.materialize_payload(SOURCE, payload, inventory)
    if corrupt:
        (payload / "skills/synthesis-agent-conformance/vendor/pyyaml/yaml/constructor.py").write_text(
            "raise AssertionError('unverified dependency executed')\n")
    result = clean_python(tmp_path, [str(payload / "skills/synthesis-agent-conformance/scripts/conformance.py"),
                                     "source", "--source-root", str(SOURCE), "--json"])
    assert result.returncode == (1 if corrupt else 0), result.stdout + result.stderr
    checked = next(item for item in json.loads(result.stdout)["checks"] if item["name"] == "source.yaml-runtime")
    assert checked["status"] == ("FAIL" if corrupt else "PASS")
    assert ("verification failed" if corrupt else "6.0.3") in checked["detail"]


@pytest.mark.parametrize("missing_native_helper", [False, True])
def test_projected_claim_identity_executes_its_native_git_dependency(tmp_path, missing_native_helper):
    sys.path.insert(0, str(SOURCE / "skills/synthesis-onboarding/scripts"))
    import modular
    payload = tmp_path / "projected"
    modular.materialize_payload(SOURCE, payload, modular.runtime_files(SOURCE))
    scripts = payload / "skills/synthesis-project-management/scripts"
    helper = scripts / "native_git.py"
    assert helper.is_file()
    if missing_native_helper:
        helper.unlink()
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "init", "-b", "main", str(repository)],
                   check=True, capture_output=True)
    script = r'''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import claim_scope,native_git
assert Path(native_git.__file__).parent==Path(sys.argv[1])
common,root=claim_scope.ClaimScopeResolver()._identity(sys.argv[2])
assert Path(root)==Path(sys.argv[2]).resolve()
assert Path(common)==Path(root)/'.git'
print(json.dumps({'status':'PASS','root':root}))
'''
    result = clean_python(tmp_path, ["-c", script, str(scripts), str(repository)])
    if missing_native_helper:
        assert result.returncode != 0
        assert "No module named 'native_git'" in result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["status"] == "PASS"
