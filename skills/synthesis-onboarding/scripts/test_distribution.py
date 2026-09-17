"""Distribution packages are inert, integrity bound, and usable by npm/Bun."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

import pytest
import release_runtime
import bootstrap
from test_system_contract import git, release_repo
from test_modular import modular_source

ROOT = Path(__file__).resolve().parents[3]


def test_cached_activation_is_bound_to_package_source(tmp_path):
    source = fixture_source(tmp_path)
    script = source / 'skills/synthesis-onboarding/scripts/bootstrap.py'
    script.parent.mkdir(parents=True)
    script.write_text("print('VERIFIED_CACHED_SOURCE')\n")
    package = builder().build_package(source, tmp_path / 'package', commit='1' * 40)
    home = tmp_path / 'home'
    payload = home / '.cache/synthesis/modular/tools/payload'
    shutil.copytree(source, payload)
    receipt = home / '.local/state/synthesis/modular/tools/slopcheck.json'
    receipt.parent.mkdir(parents=True)
    environment = {key: value for key, value in os.environ.items() if not key.startswith(('SYNTHESIS_', 'XDG_', 'GIT_'))}
    environment.update(HOME=str(home), SYNTHESIS_HOME=str(home), SYNTHESIS_BOOTSTRAP_PYTHON=sys.executable)
    descriptor = {'version': '9.8.7', 'commit': '1' * 40, 'channel': 'pin', 'ref': 'v9.8.7',
                  'source_url': 'https://github.com/synthesisengineering/synthesis-skills'}
    def invoke():
        receipt.write_text(json.dumps({'stage_core': True, 'payload': str(payload), 'release_descriptor': {
            **descriptor, 'content_digest': release_runtime.tree_digest(payload)}}))
        return subprocess.run([str(package / 'bin/synthesis'), 'activate', '--profile', 'skills-only'],
                              env=environment, capture_output=True, text=True, timeout=30)
    good = invoke()
    assert good.returncode == 0 and 'VERIFIED_CACHED_SOURCE' in good.stdout, good.stderr
    (payload / script.relative_to(source)).write_text("print('UNVERIFIED_CACHED_SOURCE')\n")
    refused = invoke()
    assert refused.returncode == 2 and 'UNVERIFIED_CACHED_SOURCE' not in refused.stdout
    assert 'package source' in refused.stderr


def test_builder_digest_matches_materialized_git_tree_not_ignored_files(tmp_path):
    source = fixture_source(tmp_path)
    git(source, 'init', '-q')
    git(source, 'add', '.')
    git(source, 'commit', '-qm', 'fixture')
    commit = git(source, 'rev-parse', 'HEAD').strip()
    expected = release_runtime.tree_digest(source)
    (source / '__pycache__').mkdir()
    (source / '__pycache__/ignored.pyc').write_bytes(b'build-time bytecode')
    package = builder().build_package(source, tmp_path / 'package', commit=commit)
    assert json.loads((package / 'lib/release.json').read_text())['source_content_digest'] == expected


def test_active_receipt_alone_cannot_authorize_a_launcher(tmp_path):
    import hashlib
    package = builder().build_package(fixture_source(tmp_path), tmp_path / 'package', commit='1' * 40)
    home = tmp_path / 'home'
    receipt = home / '.local/state/synthesis/active-release.json'
    receipt.parent.mkdir(parents=True)
    launcher = home / 'unverified-launcher'
    launcher.write_text('#!/bin/sh\nprintf UNVERIFIED_LAUNCHER\n')
    launcher.chmod(0o755)
    receipt.write_text(json.dumps({'launcher': {'path': str(launcher), 'sha256': hashlib.sha256(launcher.read_bytes()).hexdigest()}}))
    environment = {key: value for key, value in os.environ.items() if not key.startswith(('SYNTHESIS_', 'XDG_', 'GIT_'))}
    environment.update(HOME=str(home), SYNTHESIS_HOME=str(home), SYNTHESIS_BOOTSTRAP_PYTHON=sys.executable)
    result = subprocess.run([str(package / 'bin/synthesis'), 'doctor'], env=environment, capture_output=True, text=True)
    assert result.returncode == 2 and 'UNVERIFIED_LAUNCHER' not in result.stdout


def test_package_acquisition_preserves_delegate_signal(tmp_path):
    import signal
    source = fixture_source(tmp_path)
    (source / 'onboard.sh').write_text('#!/bin/sh\nkill -TERM $$\n')
    package = builder().build_package(source, tmp_path / 'package', commit='1' * 40)
    environment = {key: value for key, value in os.environ.items() if not key.startswith(('SYNTHESIS_', 'XDG_', 'GIT_'))}
    environment.update(HOME=str(tmp_path / 'home'), SYNTHESIS_BOOTSTRAP_PYTHON=sys.executable)
    result = subprocess.run([str(package / 'bin/synthesis'), 'setup'], env=environment, capture_output=True, text=True)
    assert result.returncode == -signal.SIGTERM


def builder():
    spec = importlib.util.spec_from_file_location("distribution_builder", ROOT / "packages/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for client in ("claude", "codex"):
        path = root / ("." + client + "-plugin/plugin.json")
        path.parent.mkdir()
        path.write_text(json.dumps({"name": "synthesis-skills", "version": "9.8.7"}))
    (root / "onboard.sh").write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    (root / "LICENSE-APACHE").write_text("fixture license\n")
    return root


def test_package_policy_accepts_only_validated_python_families():
    for version in ("3.12.12", "3.13.7", "3.14.0"):
        release_runtime.validate_python_version(version, platform="darwin", policy="packaged-python-v1")
    for version in ("2.7.18", "3.11.0", "3.15.0", "3.14.0rc1"):
        with pytest.raises(release_runtime.RuntimeContractError):
            release_runtime.validate_python_version(version, policy="packaged-python-v1")


def test_package_pin_uses_current_absolute_interpreter_and_detects_drift(monkeypatch):
    monkeypatch.setenv("SYNTHESIS_RUNTIME_POLICY", "packaged-python-v1")
    pin = release_runtime.interpreter_pin()
    assert pin["policy"] == "packaged-python-v1"
    assert Path(pin["executable"]).resolve() == Path(sys.executable).resolve()
    monkeypatch.setenv("SYNTHESIS_RUNTIME_POLICY", "unknown")
    assert release_runtime.verify_interpreter(pin) == pin["executable"]
    with pytest.raises(release_runtime.RuntimeContractError):
        release_runtime.verify_interpreter({**pin, "sha256": "0" * 64})


def test_builder_is_inert_and_contains_no_optional_skill_payload(tmp_path):
    source = fixture_source(tmp_path)
    package = builder().build_package(source, tmp_path / "package", commit="1" * 40)
    manifest = json.loads((package / "package.json").read_text())
    assert manifest["name"] == "@synthesiswork/synthesis"
    assert manifest["version"] == "9.8.7"
    assert not manifest.get("scripts")
    assert not (package / "skills").exists()
    assert (package / "bin/synthesis").stat().st_mode & 0o111
    assert {x.name for x in package.iterdir()} == {"bin", "lib", "package.json", "README.md", "LICENSE"}


def test_launcher_help_and_version_do_not_enroll_or_touch_home(tmp_path):
    package = builder().build_package(fixture_source(tmp_path), tmp_path / "package", commit="1" * 40)
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "SYNTHESIS_BOOTSTRAP_PYTHON": sys.executable}
    for flag, expected in (("--version", "9.8.7"), ("--help", "--profile")):
        result = subprocess.run([str(package / "bin/synthesis"), flag], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert expected in result.stdout
        assert list(home.iterdir()) == []


def test_launcher_verifies_bootstrap_before_executing(tmp_path):
    package = builder().build_package(fixture_source(tmp_path), tmp_path / "package", commit="1" * 40)
    env = {**os.environ, "HOME": str(tmp_path / "home"), "SYNTHESIS_BOOTSTRAP_PYTHON": sys.executable}
    good = subprocess.run([str(package / "bin/synthesis"), "setup", "--profile", "skills-only"], env=env, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    assert good.stdout.splitlines() == ["setup", "--profile", "skills-only", "--pin", "9.8.7"]
    (package / "lib/onboard.sh").write_text("#!/bin/sh\nprintf poisoned\n")
    bad = subprocess.run([str(package / "bin/synthesis"), "setup"], env=env, capture_output=True, text=True)
    assert bad.returncode != 0 and "poisoned" not in bad.stdout
    assert "integrity" in bad.stderr


def test_actual_thin_tool_optout_never_acquires_or_writes_state(tmp_path):
    package = builder().build_package(fixture_source(tmp_path), tmp_path / "package", commit="1" * 40)
    # Any execution of acquisition, even a local one, must be observable failure.
    (package / "lib/onboard.sh").write_text("#!/bin/sh\nexit 99\n")
    home = tmp_path / "home"
    home.mkdir()
    preserved = home / ".local/state/synthesis/modular/tools/slopcheck.json"
    preserved.parent.mkdir(parents=True)
    preserved.write_text('"existing receipt sentinel"\n')
    before = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}
    traps = tmp_path / "traps"
    traps.mkdir()
    invoked = tmp_path / "forbidden-invocation"
    for name in ("git", "curl", "wget"):
        trap = traps / name
        trap.write_text("#!/bin/sh\necho forbidden > '" + str(invoked) + "'\nexit 99\n")
        trap.chmod(0o755)
    candidates = [sys.executable]
    if sys.platform == "darwin" and Path("/usr/bin/python3").is_file():
        candidates.append("/usr/bin/python3")  # Actual macOS Python 3.9 consumer.
    for python in candidates:
        env = {"HOME": str(home), "SYNTHESIS_HOME": str(home),
               "PATH": str(traps) + ":/usr/bin:/bin", "SYNTHESIS_BOOTSTRAP_PYTHON": python}
        result = subprocess.run([str(package / "bin/synthesis"), "stage-core", "--for-tool", "slopcheck",
                                 "--no-dormant-core", "--json"], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        output = json.loads(result.stdout)
        assert output["core_state"] == "declined" and output["optional_core_bytes"] == 0
        assert output["payload"] is None
        after = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}
        assert after == before
        assert not invoked.exists()
        assert not (home / ".cache").exists()
        assert not (home / ".agents").exists()
        assert not (home / ".claude").exists()


def test_tool_optout_rejects_unknown_tool_or_extra_arguments(tmp_path):
    package = builder().build_package(fixture_source(tmp_path), tmp_path / "package", commit="1" * 40)
    env = {"HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin", "SYNTHESIS_BOOTSTRAP_PYTHON": sys.executable}
    for args in (["stage-core", "--for-tool", "unknown", "--no-dormant-core"],
                 ["stage-core", "--for-tool", "slopcheck", "--no-dormant-core", "--unexpected"]):
        result = subprocess.run([str(package / "bin/synthesis"), *args], env=env, capture_output=True, text=True)
        assert result.returncode != 0
        assert not Path(env["HOME"]).exists()


def test_builder_refuses_overwrite_and_channel_metadata_has_real_checksums(tmp_path):
    module = builder()
    source = fixture_source(tmp_path)
    package = module.build_package(source, tmp_path / "package", commit="1" * 40)
    with pytest.raises(FileExistsError):
        module.build_package(source, package, commit="1" * 40)
    archive = module.make_archive(package, tmp_path / "synthesis-9.8.7.tar.gz")
    repeat = module.make_archive(package, tmp_path / "repeat.tar.gz")
    assert archive.read_bytes() == repeat.read_bytes()
    metadata = module.write_adapters(package, archive, tmp_path / "adapters")
    assert len(metadata["sha256"]) == 64
    formula = (tmp_path / "adapters/Formula/synthesis.rb").read_text()
    aur = (tmp_path / "adapters/aur/PKGBUILD").read_text()
    assert metadata["sha256"] in formula and metadata["sha256"] in aur
    assert "REPLACE" not in formula + aur
    assert "python@3.12" in formula
    assert "python<3.15" in aur


def test_portable_archive_executes_after_extraction_without_enrollment(tmp_path):
    import tarfile
    module = builder()
    package = module.build_package(fixture_source(tmp_path), tmp_path / "package", commit="1" * 40)
    archive = module.make_archive(package, tmp_path / "archive.tar.gz")
    dest = tmp_path / "extracted"
    dest.mkdir()
    with tarfile.open(archive) as packed:
        packed.extractall(dest, filter="data")
    home = tmp_path / "clean-home"
    home.mkdir()
    result = subprocess.run([str(dest / "synthesis/bin/synthesis"), "--help"], cwd=home,
        env={**os.environ, "HOME": str(home), "SYNTHESIS_BOOTSTRAP_PYTHON": sys.executable},
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--profile" in result.stdout
    assert list(home.iterdir()) == []


def test_release_projection_keeps_original_provenance_and_omits_optional_bytes(tmp_path):
    source = release_repo(tmp_path)
    (source / "optional.md").write_text("must not persist")
    git(source, "add", "optional.md")
    git(source, "commit", "-qm", "projection fixture")
    git(source, "branch", "-f", "stable", "HEAD")
    git(source, "tag", "-f", "v9.8.7")
    files = [str(p.relative_to(source)) for p in source.rglob("*") if p.is_file() and ".git" not in p.parts and p.name != "optional.md"]
    selection = {"roots": ["synthesis-example"], "skills": ["synthesis-example"], "support_skills": [], "stage_core": False}
    root, descriptor = bootstrap.materialize_release(source, tmp_path / "releases", channel="stable", ref="stable",
        source_url="https://example.test/synthesis-skills.git", projection_files=files, selection=selection)
    assert not (root / "optional.md").exists()
    projection = descriptor["projection"]
    assert projection["source_content_digest"] == descriptor["content_digest"]
    assert root.name == projection["content_digest"]
    assert projection["content_digest"] != descriptor["content_digest"]
    release_runtime.verify_projection(root, descriptor)
    (root / "unexpected").parent.chmod(0o755)
    (root / "unexpected").write_text("not in receipt")
    with pytest.raises(release_runtime.RuntimeContractError):
        release_runtime.verify_projection(root, descriptor)


@pytest.mark.parametrize("manager", ["npm", "bun"])
def test_real_package_manager_install_is_usable_without_install_scripts(tmp_path, manager):
    executable = shutil.which(manager)
    if executable is None or shutil.which("npm") is None:
        pytest.skip("package-manager consumer acceptance requires npm and " + manager)
    package = builder().build_package(fixture_source(tmp_path), tmp_path / "package", commit="1" * 40)
    home = tmp_path / "consumer"
    home.mkdir()
    prefix = tmp_path / "prefix"
    env = {**os.environ, "HOME": str(home), "SYNTHESIS_HOME": str(home),
           "SYNTHESIS_BOOTSTRAP_PYTHON": sys.executable, "npm_config_cache": str(tmp_path / "npm-cache"),
           "npm_config_userconfig": str(home / ".npmrc"), "BUN_INSTALL": str(prefix),
           "BUN_INSTALL_CACHE_DIR": str(tmp_path / "bun-cache")}
    subprocess.run([shutil.which("npm"), "pack", "--ignore-scripts", "--pack-destination", str(tmp_path)],
                   cwd=package, env=env, capture_output=True, check=True, timeout=30)
    archive = next(tmp_path.glob("*.tgz"))
    if manager == "npm":
        command = [executable, "install", "--global", "--prefix", str(prefix), "--ignore-scripts", "--no-audit", "--no-fund", str(archive)]
    else:
        command = [executable, "add", "--global", "--ignore-scripts", str(archive)]
    installed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
    assert installed.returncode == 0, installed.stderr
    run = subprocess.run([str(prefix / "bin/synthesis"), "--version"], cwd=home, env=env, capture_output=True, text=True, timeout=10)
    assert run.returncode == 0, run.stderr
    assert "9.8.7" in run.stdout
    assert not (home / ".synthesis").exists()
    assert not (home / ".claude").exists()
    assert not (home / ".codex").exists()
    assert not (home / ".local/state/synthesis").exists()


def projected_package_fixture(modular_source, tmp_path):
    source, home, environment = modular_source
    version = json.loads((source / ".claude-plugin/plugin.json").read_text())["version"]
    subprocess.run(["git", "-C", str(source), "tag", "v" + version], env=environment, check=True)
    launcher = home / ".local/bin/synthesis"
    active = home / ".local/state/synthesis/active-release.json"
    environment.update(SYNTHESIS_HOME=str(home), SYNTHESIS_RUNTIME_POLICY="packaged-python-v1")
    command = [sys.executable, "-B", str(source / "skills/synthesis-onboarding/scripts/bootstrap.py"),
        "--checkout", str(source), "--releases-dir", str(home / ".cache/synthesis/releases"),
        "--launcher", str(launcher), "--active-descriptor", str(active),
        "--channel", "pin", "--ref", "v" + version,
        "--source-url", "https://github.com/synthesisengineering/synthesis-skills.git", "--",
        "setup", "--profile", "modular", "--skill", "synthesis-writing-craft",
        "--clients", "codex", "--no-dormant-core", "--pin", version, "--json"]
    result = subprocess.run(command, cwd=home, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    descriptor = json.loads(active.read_text())
    generation = Path(descriptor["release_root"])
    assert descriptor["projection"]["selection"]["stage_core"] is False
    assert not (generation / "skills/synthesis-article-writing/SKILL.md").exists()
    package = builder().build_package(source, tmp_path / "active-package", commit=git(source, "rev-parse", "HEAD").strip())
    return environment, launcher, active, generation, package


def test_real_projected_cli_bootstrap_and_doctor(modular_source, tmp_path):
    environment, launcher, active, generation, package = projected_package_fixture(modular_source, tmp_path)
    home = modular_source[1]
    before = active.read_bytes()
    package_doctor = subprocess.run([str(package / "bin/synthesis"), "doctor", "--json"],
                                   cwd=home, env=environment, capture_output=True, text=True, timeout=60)
    assert package_doctor.returncode == 0, package_doctor.stdout + package_doctor.stderr
    # Observe real package entry/re-entry without replacing its verifier or CLI.
    # An alias may resolve to the same binary but lose a pinned venv's site paths.
    alias = tmp_path / "alternate-python-entry"
    alias.symlink_to(sys.executable)
    trace = tmp_path / "interpreter-entries.jsonl"
    driver = package / "lib/package_launcher.py"
    driver.write_text("import json,sys\nwith open(" + repr(str(trace)) + ", 'a') as log: log.write(json.dumps(sys.executable) + '\\n')\n" + driver.read_text())
    alias_environment = {**environment, "SYNTHESIS_BOOTSTRAP_PYTHON": str(alias)}
    alias_doctor = subprocess.run([str(package / "bin/synthesis"), "doctor", "--json"], cwd=home,
                                 env=alias_environment, capture_output=True, text=True, timeout=60)
    assert alias_doctor.returncode == 0, alias_doctor.stdout + alias_doctor.stderr
    entry = json.loads(subprocess.check_output([str(alias), "-I", "-B", "-c", "import json,sys; print(json.dumps(sys.executable))"], env=alias_environment, text=True))
    pinned = json.loads(before)["interpreter"]["executable"]
    expected_entries = [entry, pinned] if entry != pinned else [pinned]
    assert [json.loads(line) for line in trace.read_text().splitlines()] == expected_entries
    assert not (generation / "hooks/hooks.json").exists()
    assert not (home / ".codex/config.toml").exists()
    assert (home / ".agents/skills/synthesis-writing-craft/SKILL.md").exists()
    for operation in ("doctor", "repair"):
        checked = subprocess.run([str(launcher), operation, "--json"], cwd=home, env=environment,
                                 capture_output=True, text=True, timeout=60)
        assert checked.returncode == 0, checked.stdout + checked.stderr
    assert not (generation / "skills/synthesis-article-writing/SKILL.md").exists()
    assert active.read_bytes() == before, "interpreter re-entry must not repin the installation"


@pytest.mark.parametrize("damage", ["digest", "missing", "version", "pending", "launcher"])
def test_package_interpreter_handoff_refuses_drift(modular_source, tmp_path, damage):
    import hashlib
    environment, launcher, active, generation, package = projected_package_fixture(modular_source, tmp_path)
    descriptor = json.loads(active.read_text())
    marker = tmp_path / "unverified-launcher-ran"
    if damage == "digest":
        descriptor["interpreter"]["sha256"] = "0" * 64
    elif damage == "missing":
        descriptor["interpreter"]["executable"] = str(tmp_path / "missing-python")
        descriptor["interpreter"]["resolved_executable"] = str(tmp_path / "missing-python")
    elif damage == "version":
        descriptor["interpreter"]["version"] = "3.15.0"
    elif damage == "pending":
        active.with_name(active.name + ".activation-pending.json").write_text("{}")
    else:
        launcher.chmod(0o755)
        launcher.write_text("#!/bin/sh\necho unverified > " + str(marker) + "\n")
        descriptor["launcher"]["sha256"] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    active.write_text(json.dumps(descriptor))
    before = active.read_bytes()
    refused = subprocess.run([str(package / "bin/synthesis"), "doctor", "--json"], cwd=modular_source[1],
                             env=environment, capture_output=True, text=True, timeout=60)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert not marker.exists()
    assert active.read_bytes() == before


def test_real_tool_stage_bootstrap_never_activates_global_runtime(modular_source, tmp_path):
    source, home, environment = modular_source
    version = json.loads((source / ".claude-plugin/plugin.json").read_text())["version"]
    subprocess.run(["git", "-C", str(source), "tag", "v" + version], env=environment, check=True)
    environment.update(SYNTHESIS_HOME=str(home), SYNTHESIS_RUNTIME_POLICY="packaged-python-v1")
    active = home / ".local/state/synthesis/active-release.json"
    launcher = home / ".local/bin/synthesis"
    command = [sys.executable, "-B", str(source / "skills/synthesis-onboarding/scripts/bootstrap.py"),
        "--checkout", str(source), "--releases-dir", str(home / ".cache/synthesis/releases"),
        "--launcher", str(launcher), "--active-descriptor", str(active),
        "--channel", "pin", "--ref", "v" + version,
        "--source-url", "https://github.com/synthesisengineering/synthesis-skills.git", "--",
        "stage-core", "--for-tool", "slopcheck", "--pin", version, "--json"]
    for extra in (["--no-dormant-core"], []):
        result = subprocess.run(command + extra, cwd=home, env=environment, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        output = json.loads(result.stdout)
        assert output["core_state"] == ("declined" if extra else "staged")
        assert (output["optional_core_bytes"] == 0) is bool(extra)
        assert not active.exists() and not launcher.exists()
        assert not (home / ".config/synthesis/system-state.json").exists()
        assert not (home / ".agents").exists()
        assert not (home / ".claude").exists()


def test_package_activation_uses_verified_cached_core_without_acquisition(modular_source, tmp_path):
    import modular
    source, home, environment = modular_source
    # A deterministic stand-in for client enrollment isolates acquisition and
    # launcher activation. The normal CLI/doctor is exercised separately above.
    (source / "skills/synthesis-onboarding/scripts/synthesis_cli.py").write_text(
        "import argparse\ndef build_parser():\n"
        " p=argparse.ArgumentParser(); s=p.add_subparsers(dest='command',required=True)\n"
        " a=s.add_parser('activate'); a.add_argument('--profile'); return p\n"
        "if __name__ == '__main__': print('cached enrollment dispatch')\n")
    subprocess.run(["git", "-C", str(source), "add", "skills/synthesis-onboarding/scripts/synthesis_cli.py"], env=environment, check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "Fixture enrollment"], env=environment, check=True)
    version = json.loads((source / ".claude-plugin/plugin.json").read_text())["version"]
    subprocess.run(["git", "-C", str(source), "tag", "v" + version], env=environment, check=True)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], env=environment, text=True).strip()
    package = builder().build_package(source, tmp_path / "package", commit=commit)
    staged = modular.stage_tool_core(source, "slopcheck", True, home)
    assert staged["optional_core_bytes"] > 0
    # Any fallback acquisition fails the test before it could touch a network.
    (package / "lib/onboard.sh").write_text("#!/bin/sh\nexit 99\n")
    environment.update(SYNTHESIS_HOME=str(home), SYNTHESIS_BOOTSTRAP_PYTHON=sys.executable)
    result = subprocess.run([str(package / "bin/synthesis"), "activate", "--profile", "skills-only"],
        cwd=home, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cached enrollment dispatch" in result.stdout
    assert (home / ".local/state/synthesis/active-release.json").exists()
    assert not (home / ".cache/synthesis/acquisition").exists()
