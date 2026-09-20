#!/usr/bin/env python3
"""Tests for the fleet secrets provider (backends + provider interface).

All refs and values are fake. The fake `op` executable below returns canned
fake values; no real vault is ever contacted.

    python3 -m pytest test_secrets_provider.py -q
"""
from __future__ import annotations

import logging
import os
import pathlib
import stat
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import secrets_provider as sp  # noqa: E402


FAKE_REF = "op://ExampleVault/ExampleItem/api-key"
FAKE_VALUE = "FAKE-SECRET-VALUE-0001"

FAKE_OP_SCRIPT = """#!/bin/sh
# Fake `op` for tests: `whoami` probes sign-in, `read` returns a canned value.
if [ "$1" = "whoami" ]; then
  if [ -n "$FAKE_OP_SIGNED_OUT" ]; then echo "not signed in" >&2; exit 1; fi
  echo "fake-account-shorthand"
  exit 0
fi
if [ "$1" = "read" ]; then
  if [ "$2" = "%s" ]; then printf '%%s\\n' "%s"; exit 0; fi
  echo "item not found" >&2; exit 1
fi
echo "unexpected args" >&2; exit 2
""" % (FAKE_REF, FAKE_VALUE)


@pytest.fixture()
def fake_op(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    op = tmp_path / "bin" / "op"
    op.parent.mkdir(parents=True)
    op.write_text(FAKE_OP_SCRIPT, encoding="utf-8")
    op.chmod(0o755)
    monkeypatch.setenv("PATH", str(op.parent) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("FAKE_OP_SIGNED_OUT", raising=False)
    return op


def test_op_backend_available_when_signed_in(fake_op: pathlib.Path) -> None:
    status = sp.OnePasswordBackend().is_available()
    assert status.name == "onepassword"
    assert status.available is True


def test_op_backend_unavailable_when_op_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    status = sp.OnePasswordBackend().is_available()
    assert status.available is False
    assert "not found" in status.detail or "missing" in status.detail


def test_op_backend_unavailable_when_signed_out(
    fake_op: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_OP_SIGNED_OUT", "1")
    status = sp.OnePasswordBackend().is_available()
    assert status.available is False
    assert "sign" in status.detail


def test_op_backend_get_returns_value(fake_op: pathlib.Path) -> None:
    assert sp.OnePasswordBackend().get(FAKE_REF) == FAKE_VALUE


def test_op_backend_get_unknown_ref_fails_closed(fake_op: pathlib.Path) -> None:
    with pytest.raises(sp.SecretRefError, match="ExampleVault/Missing"):
        sp.OnePasswordBackend().get("op://ExampleVault/Missing/field")


def test_op_backend_get_rejects_malformed_ref_without_subprocess(
    fake_op: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("must not shell out for a malformed ref")

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(sp.SecretRefError, match=r"op://"):
        sp.OnePasswordBackend().get("not-a-ref")


def test_op_backend_get_missing_binary_fails_closed(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    with pytest.raises(sp.BackendUnavailableError):
        sp.OnePasswordBackend().get(FAKE_REF)


def test_provider_never_logs_values(
    fake_op: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    logging.getLogger().addHandler(caplog.handler)
    backend = sp.OnePasswordBackend()
    assert backend.get(FAKE_REF) == FAKE_VALUE
    status = backend.is_available()
    assert status.available is True
    with pytest.raises(sp.SecretRefError):
        backend.get("op://ExampleVault/Missing/field")
    assert FAKE_VALUE not in caplog.text


def test_age_sops_backend_is_a_documented_stub() -> None:
    backend = sp.AgeSopsBackend()
    status = backend.is_available()
    assert status.name == "age-sops"
    assert status.available is False
    with pytest.raises(NotImplementedError, match="[Ee]nrollment"):
        backend.get("example.enc.yaml#/service/token")


def test_provider_facade_delegates_get_and_materialize(
    fake_op: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    import secrets_manifest as sm

    provider = sp.SecretsProvider(sp.OnePasswordBackend())
    assert provider.get(FAKE_REF) == FAKE_VALUE
    manifest = sm.SecretsManifest(
        schema_version=1,
        backend="onepassword",
        entries=(sm.ManifestEntry(ref=FAKE_REF, path="~/.synthesis/example/x", mode="0600"),),
        source=None,
    )
    report = provider.materialize(manifest, home=tmp_path)
    dest = tmp_path / ".synthesis/example/x"
    assert dest.read_text(encoding="utf-8") == FAKE_VALUE
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    assert report.ok and len(report.actions) == 1
