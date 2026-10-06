"""The engine's safety scenarios (v5 evaluation E55-E58, E60) under pytest.

The resolver and sanitizer suites stay standalone scripts (run_resolver.py,
run_poisoned.py, which rule 8 names); this file runs them, and drives the
executor against a stub IMAP connection with synthetic fixture config, so no
live mailbox or private rules are ever read.
"""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"


@pytest.mark.parametrize("runner", ["run_poisoned.py", "run_resolver.py"])
def test_standalone_suites_pass(runner):
    result = subprocess.run([sys.executable, str(TESTS / runner)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("imap:\n  host: imap.example.test\n  user_candidates:\n    - test@example.test\n")
    rules = tmp_path / "rules.yaml"
    rules.write_text("never_touch:\n  domains: [bank.example]\n"
                     "senders:\n  - {match: {domain: promo.example}, disposition: trash}\n"
                     "  - {match: {domain: letters.example}, disposition: newsletter}\n")
    monkeypatch.setenv("SYNTHESIS_INBOX_CONFIG", str(config))
    monkeypatch.setenv("SYNTHESIS_INBOX_RULES", str(rules))
    monkeypatch.syspath_prepend(str(SCRIPTS))
    for name in ("_lib", "icloud_apply", "icloud_plan"):
        sys.modules.pop(name, None)
    lib = importlib.import_module("_lib")
    return lib, importlib.import_module("icloud_apply"), importlib.import_module("icloud_plan")


class StubIMAP:
    """Sequence numbers deliberately differ from UIDs, as after an expunge."""

    def __init__(self, messages, has_move=True):
        self.messages = messages  # uid -> raw header bytes
        self.capabilities = (b"IMAP4REV1", b"MOVE") if has_move else (b"IMAP4REV1",)
        self.calls = []

    def uid(self, command, *args):
        self.calls.append((command,) + args)
        if command == "SEARCH":
            return "OK", [b" ".join(str(u).encode() for u in self.messages)]
        if command == "FETCH":
            wanted = [int(u) for u in args[0].split(",")]
            return "OK", [(f"{seq} (UID {u})".encode(), self.messages[u])
                          for seq, u in enumerate(wanted, start=1)]
        return "OK", [b""]

    def create(self, name):
        self.calls.append(("CREATE", name))

    def subscribe(self, name):
        self.calls.append(("SUBSCRIBE", name))

    def logout(self):
        self.calls.append(("LOGOUT",))


def _inbox():
    return {
        907: b"From: Promo <deals@promo.example>\r\nSubject: Sale\r\n",
        913: b"From: Weekly <news@letters.example>\r\nSubject: Issue 4\r\n",
        921: b"From: Bank <alerts@bank.example>\r\nSubject: Statement\r\n",
    }


def _run_apply(apply_mod, stub, monkeypatch, argv):
    monkeypatch.setattr(apply_mod, "connect", lambda readonly=True: (stub, "test@example.test"))
    monkeypatch.setattr(sys, "argv", ["icloud_apply.py"] + argv)
    apply_mod.main()


def test_dry_run_moves_nothing(engine, monkeypatch):  # E56
    _, apply_mod, _ = engine
    stub = StubIMAP(_inbox())
    _run_apply(apply_mod, stub, monkeypatch, ["all"])
    assert {c[0] for c in stub.calls} <= {"SEARCH", "FETCH", "LOGOUT"}


def test_apply_moves_by_uid_to_recoverable_mailboxes(engine, monkeypatch):  # E55, E57
    _, apply_mod, _ = engine
    stub = StubIMAP(_inbox())
    _run_apply(apply_mod, stub, monkeypatch, ["all", "--apply"])
    moves = [c for c in stub.calls if c[0] == "MOVE"]
    assert ("MOVE", "907", "Trash") in moves and ("MOVE", "913", "Newsletters") in moves
    assert all("921" not in c[1] for c in moves)  # never_touch stays
    assert not any(c[0] in ("STORE", "EXPUNGE") for c in stub.calls)


def test_without_move_capability_only_the_copied_uids_are_expunged(engine, monkeypatch):  # E55, E57
    _, apply_mod, _ = engine
    stub = StubIMAP(_inbox(), has_move=False)
    _run_apply(apply_mod, stub, monkeypatch, ["trash", "--apply"])
    tail = [c for c in stub.calls if c[0] in ("COPY", "STORE", "EXPUNGE")]
    assert tail == [("COPY", "907", "Trash"), ("STORE", "907", "+FLAGS", r"(\Deleted)"), ("EXPUNGE", "907")]


def test_planner_and_executor_share_one_resolver(engine):  # E58
    lib, apply_mod, plan_mod = engine
    assert apply_mod.resolve is lib.resolve and plan_mod.resolve is lib.resolve
    assert apply_mod.msg_fields is lib.msg_fields and plan_mod.msg_fields is lib.msg_fields


@pytest.fixture
def purge(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        "imap:\n  host: imap.example.test\n  user_candidates:\n    - test@example.test\n"
        "catchall:\n  domains: [catchall.example]\n  spare_recipients: [me@catchall.example]\n"
        "  spare_subject_keywords: [family.example]\n  google_subject_trash: [is being deleted]\n")
    rules = tmp_path / "rules.yaml"
    rules.write_text("class_defaults: {}\n")
    monkeypatch.setenv("SYNTHESIS_INBOX_CONFIG", str(config))
    monkeypatch.setenv("SYNTHESIS_INBOX_RULES", str(rules))
    monkeypatch.syspath_prepend(str(SCRIPTS))
    for name in ("_lib", "icloud_catchall_google_purge"):
        sys.modules.pop(name, None)
    return importlib.import_module("icloud_catchall_google_purge")


def test_catchall_purge_trashes_strangers_and_spares_the_owner(purge):  # E64
    assert purge.is_google_from("no-reply@accounts.google.com")
    assert purge.find_match(["made.up@catchall.example"], "Security alert") == "made.up@catchall.example"
    assert purge.find_match(["me@catchall.example"], "Security alert") is None
    assert purge.find_match(["made.up@catchall.example"], "Admin notice for family.example") is None
    assert purge.find_match(["someone@elsewhere.example"], "Security alert") is None


def test_lifecycle_rule_never_matches_workspace_or_billing_senders(purge):  # E64
    subject = "Your account is being deleted"
    assert purge.should_lifecycle_trash("no-reply@accounts.google.com", ["me@catchall.example"], subject) \
        == "me@catchall.example"
    for sender in ("workspace-noreply@google.com", "payments-noreply@google.com"):
        assert purge.should_lifecycle_trash(sender, ["made.up@catchall.example"], subject) is None
    assert purge.should_lifecycle_trash("no-reply@accounts.google.com", ["made.up@catchall.example"],
                                        subject + " (family.example)") is None
