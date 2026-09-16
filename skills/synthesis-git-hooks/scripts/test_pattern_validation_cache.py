from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil

import pytest


ROOT = Path(__file__).resolve().parent
POLICY = """config_version: 2
tier_0_always:
  credentials:
    - 'AKIA[0-9A-Z]{16}'
tier_1_strict_only:
  markers:
    - 'private-marker'
allowlist_lines:
  - '^harmless example$'
check_commit_message: false
"""


def load():
    spec = importlib.util.spec_from_file_location("pattern_cache_fixture", ROOT / "_load_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    module = load()
    policy = tmp_path / "policy.yaml"
    policy.write_text(POLICY)
    cache = tmp_path / "cache"
    monkeypatch.setenv("SYNTHESIS_PATTERN_CACHE_DIR", str(cache))
    calls = []
    original = module._grep_validates

    def validate(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_grep_validates", validate)
    return module, policy, cache, calls


def test_exact_valid_policy_skips_only_redundant_pattern_validation(fixture):
    module, policy, cache, calls = fixture
    first = module.load_config(policy)
    assert len(calls) == 3
    calls.clear()
    assert module.load_config(policy) == first
    assert calls == []
    assert len(list(cache.glob("*.json"))) == 1


@pytest.mark.parametrize("change", ["bytes", "version", "source", "python", "locale", "grep"])
def test_cache_invalidates_every_validation_dependency(fixture, monkeypatch, tmp_path, change):
    module, policy, cache, calls = fixture
    if change == "source":
        source = tmp_path / "validator.py"
        source.write_bytes(Path(module.__file__).read_bytes())
        monkeypatch.setattr(module, "__file__", str(source))
    if change == "grep":
        real_grep = shutil.which("grep")
        directory = tmp_path / "bin"
        directory.mkdir()
        executable = directory / "grep"
        executable.write_text("#!/bin/sh\nexec " + shlex.quote(real_grep) + ' "$@"\n')
        executable.chmod(0o755)
        monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])
    module.load_config(policy)
    calls.clear()
    if change == "bytes":
        policy.write_text(POLICY + "# Same parsed config, different exact bytes.\n")
    elif change == "version":
        monkeypatch.setattr(module, "SIDECAR_VERSION", "fixture-next")
    elif change == "source":
        source.write_text(source.read_text() + "\n# validator changed\n")
    elif change == "python":
        monkeypatch.setattr(module.sys, "version", module.sys.version + " fixture-next")
    elif change == "locale":
        monkeypatch.setenv("LANGUAGE", "fixture-next")
    else:
        executable.write_text(executable.read_text() + "# executable changed\n")
    module.load_config(policy)
    assert len(calls) == 3


@pytest.mark.parametrize("damage", ["json", "schema", "checksum", "symlink", "permissions", "hardlink"])
def test_bad_cache_uses_real_validation_and_preserves_unsafe_targets(fixture, tmp_path, damage):
    module, policy, cache, calls = fixture
    module.load_config(policy)
    target = next(cache.glob("*.json"))
    foreign = tmp_path / "foreign"
    if damage == "json":
        target.write_text("{")
    elif damage == "symlink":
        foreign.write_text("retained")
        target.unlink()
        target.symlink_to(foreign)
    elif damage == "permissions":
        target.chmod(0o644)
    elif damage == "hardlink":
        os.link(target, foreign)
    else:
        value = json.loads(target.read_text())
        value[damage] = "invalid"
        if damage == "schema":
            import hashlib
            value.pop("checksum")
            value["checksum"] = hashlib.sha256(module._validation_json(value)).hexdigest()
        target.write_text(json.dumps(value))
    before = target.read_bytes()
    calls.clear()
    module.load_config(policy)
    assert len(calls) == 3
    assert target.read_bytes() == before
    if damage == "symlink":
        assert target.is_symlink() and foreign.read_text() == "retained"


def test_symlink_cache_directory_does_not_receive_writes(fixture, tmp_path):
    module, policy, cache, calls = fixture
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    cache.symlink_to(foreign, target_is_directory=True)
    module.load_config(policy)
    module.load_config(policy)
    assert len(calls) == 6
    assert list(foreign.iterdir()) == []


def test_unwritable_cache_falls_back_to_real_validation(fixture, monkeypatch):
    module, policy, cache, calls = fixture
    monkeypatch.setattr(module.os, "link", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("fixture")))
    module.load_config(policy)
    module.load_config(policy)
    assert len(calls) == 6


def test_unwritable_existing_directory_forces_validation(fixture):
    module, policy, cache, calls = fixture
    module.load_config(policy)
    cache.chmod(0o500)
    calls.clear()
    try:
        module.load_config(policy)
        assert len(calls) == 3
    finally:
        cache.chmod(0o700)


def test_missing_grep_after_warm_cache_fails_closed(fixture, monkeypatch):
    module, policy, cache, calls = fixture
    module.load_config(policy)
    monkeypatch.setenv("PATH", "")
    calls.clear()
    with pytest.raises(SystemExit) as exc:
        module.load_config(policy)
    assert exc.value.code == 2
    assert len(calls) == 3


def test_loaded_validator_logic_is_part_of_identity(fixture, monkeypatch):
    module, policy, cache, calls = fixture
    module.load_config(policy)
    original = module.validate_all_patterns

    def changed(config, grep_executable=None):
        return original(config, grep_executable) + ["fixture validator rule changed"]

    monkeypatch.setattr(module, "validate_all_patterns", changed)
    with pytest.raises(SystemExit) as exc:
        module.load_config(policy)
    assert exc.value.code == 2


def test_invalid_policy_is_never_cached_or_allowed(fixture):
    module, policy, cache, calls = fixture
    policy.write_text(POLICY.replace("private-marker", "["))
    for _ in range(2):
        with pytest.raises(SystemExit) as exc:
            module.load_config(policy)
        assert exc.value.code == 2
    assert len(calls) == 6
    assert list(cache.glob("*.json")) == []


def test_changed_policy_cannot_borrow_prior_valid_result(fixture):
    module, policy, cache, calls = fixture
    module.load_config(policy)
    policy.write_text(POLICY.replace("private-marker", "["))
    with pytest.raises(SystemExit) as exc:
        module.load_config(policy)
    assert exc.value.code == 2


def test_direct_validation_for_doctor_stays_uncached(fixture):
    module, policy, cache, calls = fixture
    config = module.load_config(policy)
    calls.clear()
    assert module.validate_all_patterns(config) == []
    assert module.validate_all_patterns(config) == []
    assert len(calls) == 6


def test_concurrent_cache_publication_is_atomic(fixture):
    module, policy, cache, calls = fixture
    with ThreadPoolExecutor(max_workers=6) as pool:
        values = list(pool.map(lambda _: module.load_config(policy), range(12)))
    assert all(value == values[0] for value in values)
    calls.clear()
    assert module.load_config(policy) == values[0]
    assert calls == []
    assert len(list(cache.glob("*.json"))) == 1
    assert list(cache.glob("*.tmp")) == []


def test_warm_validation_cache_never_skips_credential_scanning(fixture, tmp_path):
    module, policy, cache, calls = fixture
    spec = importlib.util.spec_from_file_location("cache_hook_fixture", ROOT / "test_pre_commit.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    fixture_root = tmp_path / "hook"
    fixture_root.mkdir()
    repository, environment = helpers.repository(fixture_root)
    harmless = repository / "notes.txt"
    harmless.write_text("harmless note\n")
    assert helpers.run(repository, "git", "add", "notes.txt").returncode == 0
    first = helpers.run(repository, str(helpers.HOOK), env=environment)
    assert first.returncode == 0, first.stdout + first.stderr
    assert list(cache.glob("*.json"))
    harmless.write_text("AKIA" + "A" * 16 + "\n")
    assert helpers.run(repository, "git", "add", "notes.txt").returncode == 0
    second = helpers.run(repository, str(helpers.HOOK), env=environment)
    assert second.returncode != 0
    assert "SENSITIVE PATTERN DETECTED" in second.stdout
