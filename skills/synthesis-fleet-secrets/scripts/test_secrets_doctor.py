#!/usr/bin/env python3
"""Tests for the fleet secrets doctor.

All refs and values are fake. Doctor output must never contain a value —
every CLI test asserts the fake values are absent from stdout/stderr.

    python3 -m pytest test_secrets_doctor.py -q
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import secrets_doctor as doc  # noqa: E402
import secrets_manifest as sm  # noqa: E402
import secrets_provider as sp  # noqa: E402


FAKE_REF = "op://ExampleVault/ExampleItem/api-key"
FAKE_VALUE = "FAKE-SECRET-VALUE-0001"


class FakeBackend(sp.SecretsBackend):
    name = "fake"

    def __init__(self, values: dict[str, str] | None = None, available: bool = True) -> None:
        self._values = dict(values if values is not None else {FAKE_REF: FAKE_VALUE})
        self._available = available

    def is_available(self) -> sp.BackendStatus:
        return sp.BackendStatus(
            name=self.name, available=self._available,
            detail="fake backend" if self._available else "fake backend down",
        )

    def get(self, ref: str) -> str:
        return self._values[ref]


class UnavailableBackend(sp.SecretsBackend):
    name = "down"

    def is_available(self) -> sp.BackendStatus:
        return sp.BackendStatus(name=self.name, available=False, detail="signed out")

    def get(self, ref: str) -> str:
        raise sp.BackendUnavailableError("signed out")


def write_manifest(path: pathlib.Path) -> pathlib.Path:
    import yaml

    path.write_text(yaml.safe_dump({
        "schema_version": 1, "backend": "onepassword",
        "entries": [{"ref": FAKE_REF, "path": "~/.synthesis/example/x", "mode": "0600"}],
    }), encoding="utf-8")
    return path


def manifest() -> sm.SecretsManifest:
    return sm.SecretsManifest(
        schema_version=1, backend="onepassword",
        entries=(sm.ManifestEntry(ref=FAKE_REF, path="~/.synthesis/example/x", mode="0600"),),
        source=None,
    )


def test_backend_check_ok_and_fail() -> None:
    assert doc.check_backend_available(FakeBackend()).ok
    failed = doc.check_backend_available(UnavailableBackend())
    assert not failed.ok and "down" in failed.detail


def test_manifest_check_ok_and_fail(tmp_path: pathlib.Path) -> None:
    ok = doc.check_manifest_valid(write_manifest(tmp_path / "m.yaml"))
    assert ok.ok and "1 entr" in ok.detail
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 99\n", encoding="utf-8")
    failed = doc.check_manifest_valid(bad)
    assert not failed.ok
    missing = doc.check_manifest_valid(tmp_path / "absent.yaml")
    assert not missing.ok


def test_permissions_check_ok(tmp_path: pathlib.Path) -> None:
    dest = tmp_path / ".synthesis/example/x"
    dest.parent.mkdir(parents=True)
    dest.write_text(FAKE_VALUE, encoding="utf-8")
    dest.chmod(0o600)
    assert doc.check_permissions(manifest(), home=tmp_path).ok


def test_permissions_check_flags_missing_file(tmp_path: pathlib.Path) -> None:
    failed = doc.check_permissions(manifest(), home=tmp_path)
    assert not failed.ok and "not materialized" in failed.detail


def test_permissions_check_flags_loose_mode(tmp_path: pathlib.Path) -> None:
    dest = tmp_path / ".synthesis/example/x"
    dest.parent.mkdir(parents=True)
    dest.write_text(FAKE_VALUE, encoding="utf-8")
    dest.chmod(0o644)
    failed = doc.check_permissions(manifest(), home=tmp_path)
    assert not failed.ok and "0644" in failed.detail


def test_values_absent_ok_when_manifest_carries_only_refs(tmp_path: pathlib.Path) -> None:
    path = write_manifest(tmp_path / "m.yaml")
    check = doc.check_values_absent(path, sm.parse_manifest(path), FakeBackend())
    assert check.ok, check.detail


def test_values_absent_flags_leaked_value(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "m.yaml"
    path.write_text(
        "schema_version: 1\nbackend: onepassword\nentries:\n"
        "- {ref: %s, path: ~/.synthesis/example/x, mode: '0600', note: %s}\n"
        % (FAKE_REF, FAKE_VALUE),
        encoding="utf-8",
    )
    parsed = sm.SecretsManifest(
        schema_version=1, backend="onepassword",
        entries=(sm.ManifestEntry(ref=FAKE_REF, path="~/.synthesis/example/x", mode="0600"),),
        source=path,
    )
    failed = doc.check_values_absent(path, parsed, FakeBackend())
    assert not failed.ok and FAKE_REF in failed.detail
    assert FAKE_VALUE not in failed.detail


def test_values_absent_fails_closed_when_backend_down(tmp_path: pathlib.Path) -> None:
    path = write_manifest(tmp_path / "m.yaml")
    failed = doc.check_values_absent(path, sm.parse_manifest(path), UnavailableBackend())
    assert not failed.ok and "unavailable" in failed.detail


def test_values_absent_flags_empty_value(tmp_path: pathlib.Path) -> None:
    path = write_manifest(tmp_path / "m.yaml")
    failed = doc.check_values_absent(
        path, sm.parse_manifest(path), FakeBackend(values={FAKE_REF: ""}))
    assert not failed.ok and "empty" in failed.detail


def test_run_doctor_all_green(tmp_path: pathlib.Path) -> None:
    path = write_manifest(tmp_path / "m.yaml")
    dest = tmp_path / ".synthesis/example/x"
    dest.parent.mkdir(parents=True)
    dest.write_text(FAKE_VALUE, encoding="utf-8")
    dest.chmod(0o600)
    report = doc.run_doctor(path, FakeBackend(), home=tmp_path)
    assert [c.id for c in report] == ["backend-available", "manifest-valid",
                                      "permissions-correct", "values-absent"]
    assert all(c.ok for c in report)


def _git_available() -> bool:
    return shutil.which("git") is not None


@pytest.mark.skipif(not _git_available(), reason="git required")
def test_values_absent_scans_git_tracked_files(tmp_path: pathlib.Path) -> None:
    # Isolate from the developer's global git config and hooks: fixture
    # commits must never consult or trigger real coordination gates.
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_NOGLOBAL="1")

    def git(*args: str, cwd: pathlib.Path) -> None:
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args],
                       cwd=cwd, check=True, env=env, capture_output=True)

    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", str(repo), cwd=tmp_path)
    git("config", "user.email", "fixture@example.test", cwd=repo)
    git("config", "user.name", "fixture", cwd=repo)
    git("config", "commit.gpgsign", "false", cwd=repo)
    tracked = repo / "notes.txt"
    tracked.write_text("nothing secret here\n", encoding="utf-8")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "init", cwd=repo)
    path = write_manifest(tmp_path / "m.yaml")
    parsed = sm.parse_manifest(path)
    assert doc.check_values_absent(path, parsed, FakeBackend(), scan_roots=[repo]).ok
    tracked.write_text("leaked %s here\n" % FAKE_VALUE, encoding="utf-8")
    git("add", "-A", cwd=repo)
    git("commit", "-qm", "leak", cwd=repo)
    failed = doc.check_values_absent(path, parsed, FakeBackend(), scan_roots=[repo])
    assert not failed.ok and "notes.txt" in failed.detail
    assert FAKE_VALUE not in failed.detail


def test_cli_exit_zero_and_leak_free(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_manifest(tmp_path / "m.yaml")
    dest = tmp_path / ".synthesis/example/x"
    dest.parent.mkdir(parents=True)
    dest.write_text(FAKE_VALUE, encoding="utf-8")
    dest.chmod(0o600)
    code = doc.main(["--manifest", str(path), "--home", str(tmp_path), "--backend", "fake"])
    assert code == 0
    captured = capsys.readouterr()
    assert FAKE_VALUE not in captured.out and FAKE_VALUE not in captured.err


def test_cli_exit_nonzero_on_bad_manifest(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 99\n", encoding="utf-8")
    code = doc.main(["--manifest", str(bad), "--home", str(tmp_path), "--backend", "fake"])
    assert code != 0
    captured = capsys.readouterr()
    assert FAKE_VALUE not in captured.out and FAKE_VALUE not in captured.err
