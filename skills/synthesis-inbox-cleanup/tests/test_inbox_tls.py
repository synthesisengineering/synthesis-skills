"""Every IMAP connection the engine makes verifies the server's certificate and host name against a CA bundle no agent
can change, and never runs unverified.

2026-11-18: an operations seat ran the engine as the skill says, `python3 -s` on the runtime's copy. `-s` leaves out the
user's own site folder, where `pip3 install --user certifi` puts certifi, so `_ssl_context()` fell back to the
interpreter's default store; python.org's Python on macOS ships none, and every connection failed
CERTIFICATE_VERIFY_FAILED. Where certifi is not importable, or its bundle is one this user could rewrite, the context now
loads the operating system's own bundle (macOS's /etc/ssl/cert.pem), owned by root with every folder above it. The census,
alone of the scripts, opened its connection with imaplib's own default, which verifies nothing; it now connects through
the same `connect()`. No test here opens a network connection.
"""

import importlib
import os
import shutil
import ssl
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def lib(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("imap:\n  host: imap.example.test\n  user_candidates:\n    - test@example.test\n")
    rules = tmp_path / "rules.yaml"
    rules.write_text("senders:\n  - {match: {domain: promo.example}, disposition: trash}\n")
    monkeypatch.setenv("SYNTHESIS_INBOX_CONFIG", str(config))
    monkeypatch.setenv("SYNTHESIS_INBOX_RULES", str(rules))
    monkeypatch.syspath_prepend(str(SCRIPTS))
    for name in ("_lib", "icloud_census"):
        sys.modules.pop(name, None)
    monkeypatch.setitem(sys.modules, "certifi", None)  # as under `python3 -s`: not importable
    module = importlib.import_module("_lib")
    monkeypatch.setattr(module, "get_password", lambda: "not-a-real-password")
    return module


def _system_bundle():
    """The first of the operating system's bundles that root owns, with every folder above it, as the engine reads it."""
    for name in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        real = os.path.realpath(name)
        if os.path.isfile(real) and not os.stat(real).st_uid and not os.access(real, os.W_OK):
            return real
    pytest.skip("this machine has no root-owned CA bundle where the operating systems keep one")


def _loaded(monkeypatch, module) -> list:
    """Every cafile a context is made with, recorded as the real `create_default_context` makes it."""
    made, real = [], ssl.create_default_context

    def recorded(*args, **kwargs):
        made.append(kwargs.get("cafile"))
        return real(*args, **kwargs)
    monkeypatch.setattr(module.ssl, "create_default_context", recorded)
    return made


def _verifies(context) -> bool:
    return isinstance(context, ssl.SSLContext) and context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname


def test_without_certifi_the_context_verifies_against_the_root_owned_system_bundle(lib, monkeypatch):
    made = _loaded(monkeypatch, lib)
    context = lib._ssl_context()
    assert _verifies(context)
    assert made == [_system_bundle()], made


def test_a_bundle_this_user_can_rewrite_is_never_loaded(lib, monkeypatch, tmp_path):
    """A copy of the system's bundle where this user can write it, named first and handed in as certifi's, is passed over:
    an agent could add its own authority to it."""
    copy = tmp_path / "cacert.pem"
    shutil.copy(_system_bundle(), copy)
    monkeypatch.setitem(sys.modules, "certifi", types.SimpleNamespace(where=lambda: str(copy)))
    monkeypatch.setattr(lib, "SYSTEM_CA_FILES", (str(copy), *lib.SYSTEM_CA_FILES), raising=False)
    made = _loaded(monkeypatch, lib)
    assert _verifies(lib._ssl_context())
    assert made == [_system_bundle()], made


def test_with_no_bundle_it_can_trust_it_still_verifies_with_the_default_store(lib, monkeypatch, tmp_path):
    copy = tmp_path / "cacert.pem"
    shutil.copy(_system_bundle(), copy)
    monkeypatch.setattr(lib, "SYSTEM_CA_FILES", (str(copy), str(tmp_path / "missing.pem")), raising=False)
    made = _loaded(monkeypatch, lib)
    assert _verifies(lib._ssl_context())
    assert made == [None], made


class _Recorded:
    """An IMAP connection that records the TLS context it was opened with and holds an empty INBOX."""
    opened: list = []

    def __init__(self, host, port=993, ssl_context=None, **kwargs):
        _Recorded.opened.append((host, ssl_context))

    def login(self, user, password):
        return "OK", [b"Logged in"]

    def select(self, mailbox, readonly=False):
        return "OK", [b"0"]

    def search(self, charset, *criteria):
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]


@pytest.mark.parametrize("script", ["connect", "icloud_census"])
def test_every_connection_the_engine_opens_verifies(lib, monkeypatch, script):
    _Recorded.opened = []
    monkeypatch.setattr(lib.imaplib, "IMAP4_SSL", _Recorded)
    if script == "connect":
        lib.connect(readonly=True)
    else:
        census = importlib.import_module("icloud_census")
        monkeypatch.setattr(census, "get_password", lambda: "not-a-real-password", raising=False)
        census.main()
    assert [host for host, _ in _Recorded.opened] == ["imap.example.test"], _Recorded.opened
    assert all(_verifies(context) for _, context in _Recorded.opened), _Recorded.opened


def test_no_script_opens_its_own_imap_connection():
    """The one place a connection is opened is `_lib.connect`, with the verifying context: imaplib's own default
    verifies nothing."""
    opened = {p.name: p.read_text(encoding="utf-8").count("IMAP4_SSL(") for p in sorted(SCRIPTS.glob("*.py"))}
    assert {name: n for name, n in opened.items() if n} == {"_lib.py": 1}, opened
    assert "IMAP4_SSL(HOST, ssl_context=_ssl_context())" in (SCRIPTS / "_lib.py").read_text(encoding="utf-8")
