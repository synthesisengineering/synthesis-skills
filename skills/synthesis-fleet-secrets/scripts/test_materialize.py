#!/usr/bin/env python3
"""Tests for fleet secrets materialization (manifest in, files out).

All refs and values are fake. Materialization targets are confined to tmp
homes; the invoking user's real home is never touched.

    python3 -m pytest test_materialize.py -q
"""
from __future__ import annotations

import os
import pathlib
import stat
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import materialize as mat  # noqa: E402
import secrets_manifest as sm  # noqa: E402
import secrets_provider as sp  # noqa: E402


FAKE_REF = "op://ExampleVault/ExampleItem/api-key"
FAKE_VALUE = "FAKE-SECRET-VALUE-0001"


class FakeBackend(sp.SecretsBackend):
    name = "fake"

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {FAKE_REF: FAKE_VALUE})
        self.calls: list[str] = []

    def is_available(self) -> sp.BackendStatus:
        return sp.BackendStatus(name=self.name, available=True, detail="fake backend")

    def get(self, ref: str) -> str:
        self.calls.append(ref)
        return self._values[ref]


def manifest(*entries: sm.ManifestEntry) -> sm.SecretsManifest:
    return sm.SecretsManifest(
        schema_version=1, backend="onepassword", entries=entries, source=None
    )


def entry(ref: str = FAKE_REF, path: str = "~/.synthesis/example/x",
          mode: str = "0600") -> sm.ManifestEntry:
    return sm.ManifestEntry(ref=ref, path=path, mode=mode)


def test_dry_run_writes_nothing_and_fetches_nothing(tmp_path: pathlib.Path) -> None:
    backend = FakeBackend()
    report = mat.materialize_manifest(manifest(entry()), backend, home=tmp_path, dry_run=True)
    assert report.ok and report.dry_run
    assert len(report.actions) == 1
    assert backend.calls == []
    assert not (tmp_path / ".synthesis").exists()


def test_materialize_writes_file_with_owner_only_mode(tmp_path: pathlib.Path) -> None:
    report = mat.materialize_manifest(manifest(entry()), FakeBackend(), home=tmp_path)
    assert report.ok and not report.dry_run
    dest = tmp_path / ".synthesis/example/x"
    assert dest.read_text(encoding="utf-8") == FAKE_VALUE
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_materialize_honors_0400(tmp_path: pathlib.Path) -> None:
    mat.materialize_manifest(manifest(entry(mode="0400")), FakeBackend(), home=tmp_path)
    dest = tmp_path / ".synthesis/example/x"
    assert stat.S_IMODE(dest.stat().st_mode) == 0o400


def test_overwrite_backs_up_existing_file(tmp_path: pathlib.Path) -> None:
    dest = tmp_path / ".synthesis/example/x"
    dest.parent.mkdir(parents=True)
    dest.write_text("FAKE-PREVIOUS-VALUE", encoding="utf-8")
    dest.chmod(0o600)
    report = mat.materialize_manifest(manifest(entry()), FakeBackend(), home=tmp_path)
    assert report.ok
    assert dest.read_text(encoding="utf-8") == FAKE_VALUE
    assert report.actions[0].backup is not None
    backup = report.actions[0].backup
    assert backup is not None and backup.read_text(encoding="utf-8") == "FAKE-PREVIOUS-VALUE"
    assert stat.S_IMODE(backup.stat().st_mode) & 0o077 == 0


def test_no_backup_flag_skips_backup(tmp_path: pathlib.Path) -> None:
    dest = tmp_path / ".synthesis/example/x"
    dest.parent.mkdir(parents=True)
    dest.write_text("FAKE-PREVIOUS-VALUE", encoding="utf-8")
    dest.chmod(0o600)
    report = mat.materialize_manifest(manifest(entry()), FakeBackend(), home=tmp_path, backup=False)
    assert report.ok and report.actions[0].backup is None
    assert dest.read_text(encoding="utf-8") == FAKE_VALUE


def test_refuses_symlink_destination(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "elsewhere.txt"
    target.write_text("FAKE-ELSEWHERE", encoding="utf-8")
    link = tmp_path / ".synthesis/example/x"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    with pytest.raises(mat.MaterializeError, match="[Ss]ymlink"):
        mat.materialize_manifest(manifest(entry()), FakeBackend(), home=tmp_path)
    assert target.read_text(encoding="utf-8") == "FAKE-ELSEWHERE"


def test_refuses_escape_from_home(tmp_path: pathlib.Path) -> None:
    evil = sm.ManifestEntry(ref=FAKE_REF, path="~/../escape.txt", mode="0600")
    with pytest.raises(mat.MaterializeError, match="home"):
        mat.materialize_manifest(manifest(evil), FakeBackend(), home=tmp_path / "home")


def test_backend_failure_fails_closed_without_partial_write(tmp_path: pathlib.Path) -> None:
    other = "op://ExampleVault/OtherItem/token"
    backend = FakeBackend(values={FAKE_REF: FAKE_VALUE})  # `other` missing -> KeyError
    with pytest.raises(mat.MaterializeError, match="OtherItem"):
        mat.materialize_manifest(
            manifest(entry(), entry(ref=other, path="~/.synthesis/example/y")),
            backend, home=tmp_path,
        )


def test_verify_owner_only_posix_bits(tmp_path: pathlib.Path) -> None:
    locked = tmp_path / "locked"
    locked.write_text("x", encoding="utf-8")
    locked.chmod(0o600)
    assert mat.verify_owner_only(locked).ok
    locked.chmod(0o400)
    assert mat.verify_owner_only(locked).ok
    locked.chmod(0o644)
    verdict = mat.verify_owner_only(locked)
    assert not verdict.ok and "0644" in verdict.detail
    assert not mat.verify_owner_only(tmp_path / "missing").ok


def test_acl_parser_flags_non_owner_allow() -> None:
    dirty = (
        "-rw-------  1 example  staff  18 Sep 19 22:00 token\n"
        " 0: group:everyone allow read\n"
    )
    assert mat.parse_ls_le_acl(dirty, owner="example") is False
    deny_only = (
        "-rw-------  1 example  staff  18 Sep 19 22:00 token\n"
        " 0: group:everyone deny delete\n"
    )
    assert mat.parse_ls_le_acl(deny_only, owner="example") is True
    owner_allow = (
        "-rw-------  1 example  staff  18 Sep 19 22:00 token\n"
        " 0: user:example allow read,write\n"
    )
    assert mat.parse_ls_le_acl(owner_allow, owner="example") is True
    assert mat.parse_ls_le_acl("no acl lines here\n", owner="example") is True


def test_cli_dry_run_reports_without_values(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "schema_version": 1, "backend": "onepassword",
        "entries": [{"ref": FAKE_REF, "path": "~/.synthesis/example/x", "mode": "0600"}],
    }), encoding="utf-8")
    code = mat.main(["--manifest", str(manifest_path), "--home", str(tmp_path / "home"),
                     "--backend", "fake", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "dry-run" in out and FAKE_VALUE not in out


def test_cli_materialize_with_fake_backend(tmp_path: pathlib.Path) -> None:
    import yaml

    home = tmp_path / "home"
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "schema_version": 1, "backend": "onepassword",
        "entries": [{"ref": FAKE_REF, "path": "~/.synthesis/example/x",
                     "mode": "0600"}],
    }), encoding="utf-8")
    code = mat.main(["--manifest", str(manifest_path), "--home", str(home), "--backend", "fake"])
    assert code == 0
    dest = home / ".synthesis/example/x"
    assert dest.read_text(encoding="utf-8") == mat.FAKE_BACKEND_VALUE
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_cli_invalid_manifest_exits_nonzero(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("schema_version: 99\nbackend: nope\nentries: []\n", encoding="utf-8")
    code = mat.main(["--manifest", str(manifest_path), "--home", str(tmp_path)])
    assert code != 0
    assert FAKE_VALUE not in capsys.readouterr().out
