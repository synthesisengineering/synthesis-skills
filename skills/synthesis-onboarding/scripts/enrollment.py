"""Durable, exact-target rollback for additive organization generation.

Knowledge-base clones and source caches are retained as user data. Generated
outputs, selected skill copies, receipts and invite state are journaled before
mutation. A failed generation is moved into the journal, never deleted.
"""

from __future__ import annotations

import json
import errno
import os
import re
import shutil
import tempfile
import contextlib
import fcntl
import hashlib
import threading
from pathlib import Path

from system_contract import ContractError, atomic_write_json, json_digest, validate_desired_state

_engine_mutex = threading.RLock()
_engine_depth = {}


def engine_state_root(home):
    default = Path(os.environ.get("XDG_STATE_HOME", str(Path(home) / ".local/state"))) / "synthesis"
    return Path(os.environ.get("SYNTHESIS_ONBOARD_STATE_DIR", str(default)))


@contextlib.contextmanager
def engine_lock(root, *, read_only=False):
    root = Path(root)
    with _engine_mutex:
        if _engine_depth.get(str(root), 0):
            yield
            return
        regular_tree(root)
        lock_path = root / "engine.lock"
        regular_tree(lock_path)
        if read_only and not lock_path.exists():
            yield
            return
        if not read_only:
            root.mkdir(parents=True, exist_ok=True)
        with lock_path.open("rb" if read_only else "a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _engine_depth[str(root)] = 1
            try:
                yield
            finally:
                _engine_depth.pop(str(root), None)
                fcntl.flock(lock, fcntl.LOCK_UN)


def regular_tree(path: Path) -> None:
    for parent in (path, *path.parents):
        if parent.is_symlink():
            # macOS canonical system aliases are not user-selected links.
            aliases = {Path("/var"): Path("/private/var"), Path("/tmp"): Path("/private/tmp")}
            if parent in aliases and parent.resolve() == aliases[parent]:
                continue
            raise ContractError("enrollment refuses a symbolic-link target: %s" % path)
    if path.exists() and not (path.is_file() or path.is_dir()):
        raise ContractError("enrollment target is not a regular file or directory")
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_symlink() or not (child.is_file() or child.is_dir()):
                raise ContractError("enrollment target contains a non-regular entry")


def copy_verified(source, destination):
    """Stage and verify on the destination device before atomic activation."""
    regular_tree(source)
    regular_tree(destination)
    if destination.exists():
        raise ContractError("verified copy destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".enrollment-copy-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "payload"
        if source.is_dir():
            shutil.copytree(source, staged)
        else:
            shutil.copy2(source, staged)
        if EnrollmentJournal._fingerprint(source) != EnrollmentJournal._fingerprint(staged):
            raise ContractError("enrollment copy verification failed")
        os.replace(staged, destination)


def move_verified(source, destination):
    """Call only after the caller proves the exact receipt/journal target."""
    regular_tree(source)
    regular_tree(destination)
    if destination.exists():
        raise ContractError("enrollment archive destination already exists")
    try:
        os.replace(source, destination)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        copy_verified(source, destination)
        regular_tree(source)
        if EnrollmentJournal._fingerprint(source) != EnrollmentJournal._fingerprint(destination):
            raise ContractError("enrollment archive changed before retirement")
        if source.is_dir():
            shutil.rmtree(source)
        else:
            source.unlink()


class EnrollmentJournal:
    def __init__(self, root: Path):
        self.root = Path(root)
        regular_tree(self.root)
        self.path = self.root / "journal.json"
        self.data = json.loads(self.path.read_text())
        if self.data.get("schema_version") != 1 or self.data.get("transaction_id") != self.root.name:
            raise ContractError("invalid enrollment journal identity")
        if self.data.get("state") not in {"pending", "committed", "rolled-back"}:
            raise ContractError("invalid enrollment journal state")
        for entry in self.data["entries"]:
            if not re.fullmatch(r"[0-9]+", str(entry.get("slot", ""))):
                raise ContractError("invalid enrollment backup slot")

    def validate_scope(self, state, desired):
        """Re-derive capabilities from runtime inputs, never from journal claims."""
        proposed = validate_desired_state(self.data.get("proposed_desired"))
        entries = proposed.get("organizations") or []
        if len(entries) != 1 or entries[0].get("mode") != "additive":
            raise ContractError("enrollment journal must declare one additive organization")
        if json_digest(proposed) != self.data["proposed_desired_digest"]:
            raise ContractError("enrollment journal proposed state digest changed")
        workspaces = Path(os.environ.get("SYNTHESIS_WORKSPACES_ROOT", str(state.home / "workspaces")))
        receipts = engine_state_root(state.home) / "receipts.json"
        files = {str(p) for p in (state.desired_path, state.invites_path, receipts)}
        files.update(str(workspaces / entries[0]["workspace"] / name) for name in ("AGENTS.md", "CLAUDE.md"))
        parents = {str(state.home / (".claude" if c == "claude" else ".agents") / "skills") for c in desired["clients"]}
        if not set(self.data["skill_parents"]) <= parents:
            raise ContractError("enrollment journal claims an unselected skill target")
        for value in self.data["allowed_files"]:
            path = Path(value)
            if str(path) not in files:
                raise ContractError("enrollment journal claims a forbidden output")
        for entry in self.data["entries"]:
            self._target(entry["target"])

    @classmethod
    def create(cls, root, transaction_id, desired, *, files, skill_parents, proposed=None, purpose="enroll"):
        if not re.fullmatch(r"[a-f0-9]{32}", transaction_id):
            raise ContractError("invalid enrollment transaction identity")
        root = Path(root) / transaction_id
        regular_tree(root)
        if root.exists():
            raise ContractError("enrollment journal identity already exists")
        staging_root = root.parent / ".staging"
        regular_tree(staging_root)
        staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = {
            "schema_version": 1, "transaction_id": transaction_id,
            "purpose": purpose,
            "previous_desired_digest": json_digest(desired), "state": "pending",
            "proposed_desired_digest": json_digest(proposed),
            "proposed_desired": proposed,
            "allowed_files": [str(Path(p).absolute()) for p in files],
            "skill_parents": [str(Path(p).absolute()) for p in skill_parents],
            "entries": [], "retained_data": [],
        }
        # Only a complete identity is discoverable as a pending transaction.
        # Interrupted staging has authorized no target mutation and is retained
        # separately, never interpreted as an active journal.
        with tempfile.TemporaryDirectory(prefix=transaction_id + "-", dir=staging_root) as stage:
            atomic_write_json(Path(stage) / "journal.json", data)
            os.replace(stage, root)
        return cls(root)

    def _save(self):
        atomic_write_json(self.path, self.data)

    def _target(self, value):
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ContractError("enrollment target must be absolute and contained")
        allowed = str(path) in self.data["allowed_files"] or (
            str(path.parent) in self.data["skill_parents"]
            and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", path.name)
        )
        if not allowed:
            raise ContractError("enrollment target is outside its exact write set: %s" % path)
        regular_tree(path)
        return path

    def capture(self, target):
        target = self._target(target)
        if any(e["target"] == str(target) for e in self.data["entries"]):
            return
        slot = str(len(self.data["entries"]))
        backup = self.root / "before" / slot
        entry = {"target": str(target), "slot": slot, "existed": target.exists()}
        if target.exists():
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if target.is_dir():
                shutil.copytree(target, backup)
            else:
                shutil.copy2(target, backup)
            # Verification compares every byte, filename and mode before a
            # durable journal entry can authorize the mutation.
            entry["fingerprint"] = self._fingerprint(target)
            if entry["fingerprint"] != self._fingerprint(backup):
                raise ContractError("enrollment backup verification failed")
        self.data["entries"].append(entry)
        self._save()

    @staticmethod
    def _fingerprint(path):
        import hashlib
        entries = [path, *sorted(path.rglob("*"))] if path.is_dir() else [path]
        return [
            [str(p.relative_to(path)), p.stat().st_mode & 0o777,
             hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "directory"]
            for p in entries
        ]

    def retain(self, path):
        if str(path) not in self.data["retained_data"]:
            self.data["retained_data"].append(str(path))
            self._save()

    def rollback(self):
        if self.data["state"] == "rolled-back":
            return
        if self.data["state"] != "pending":
            raise ContractError("cannot roll back a committed enrollment journal")
        for entry in reversed(self.data["entries"]):
            if entry.get("restored"):
                continue
            target = self._target(entry["target"])
            backup = self.root / "before" / entry["slot"]
            failed = self.root / "failed" / entry["slot"]
            if entry["existed"]:
                regular_tree(backup)
                if not backup.exists() or self._fingerprint(backup) != entry.get("fingerprint"):
                    raise ContractError("enrollment rollback backup is missing or changed")
            if target.exists() and not failed.exists():
                failed.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                move_verified(target, failed)
            elif target.exists() and failed.exists() and self._fingerprint(target) == self._fingerprint(failed):
                # Interrupted cross-device retirement: the complete failed
                # generation is already archived. Finish its exact removal.
                self._target(target)
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if entry["existed"]:
                regular_tree(backup)
                if not backup.exists():
                    raise ContractError("enrollment rollback backup is missing")
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    copy_verified(backup, target)
                if self._fingerprint(target) != self._fingerprint(backup):
                    raise ContractError("enrollment rollback verification failed")
            elif target.exists():
                raise ContractError("enrollment rollback target changed during recovery")
            entry["restored"] = True
            self._save()
        self.data["state"] = "rolled-back"
        self._save()

    def commit(self):
        self.data["state"] = "committed"
        self._save()


def recover_enrollments(state):
    root = state.state_dir / "enrollments"
    if not root.exists():
        return
    regular_tree(root)
    transactions = {t["transaction_id"]: t for t in state.read_observation()["transactions"]}
    for path in sorted(root.iterdir()):
        if path.name == ".staging":
            continue
        journal = EnrollmentJournal(path)
        if journal.data["state"] != "pending":
            continue
        current = state.read_desired()
        if current is None:
            raise ContractError("enrollment journal has no existing desired installation")
        journal.validate_scope(state, current)
        transaction = transactions.get(path.name)
        if not transaction or transaction["command"] != "enroll" or transaction["desired_digest"] != journal.data["proposed_desired_digest"]:
            raise ContractError("enrollment journal is not bound to its transaction")
        if transaction and transaction["state"] == "committed":
            journal.commit()
        else:
            # The same desired-state lock is held by every caller. Never
            # guess ownership after an unrelated desired generation change.
            if json_digest(current) not in {journal.data["previous_desired_digest"], journal.data["proposed_desired_digest"]}:
                raise ContractError("interrupted enrollment has a different desired state; recovery required")
            journal.rollback()


def require_settled_enrollments(state):
    """Read-only diagnostic gate; mutation commands own crash recovery."""
    root = state.state_dir / "enrollments"
    if not root.exists():
        return
    regular_tree(root)
    for path in root.iterdir():
        if path.name == ".staging":
            continue
        if EnrollmentJournal(path).data["state"] == "pending":
            raise ContractError("unfinished enrollment requires recovery; run synthesis repair before diagnostic acceptance")


def validate_copy_scope(journal, root, home):
    if journal.data.get("purpose") != "org-copy" or journal.root.parent != Path(root) / "copy-transactions":
        raise ContractError("invalid organization-copy journal identity")
    if journal.data["allowed_files"] != [str(Path(root) / "receipts.json")]:
        raise ContractError("organization-copy journal claims an unrelated receipt")
    allowed = {str(Path(home) / c / "skills") for c in (".claude", ".agents")}
    if not set(journal.data["skill_parents"]) <= allowed:
        raise ContractError("organization-copy journal claims an unrelated runtime")
    for entry in journal.data["entries"]:
        journal._target(entry["target"])


def recover_copy_transactions(root, home, *, verify_only=False):
    directory = Path(root) / "copy-transactions"
    if not directory.exists():
        return
    regular_tree(directory)
    for path in directory.iterdir():
        if path.name == ".staging":
            continue
        journal = EnrollmentJournal(path)
        if journal.data["state"] != "pending":
            continue
        if verify_only:
            raise ContractError("unfinished organization copy requires synthesis repair")
        validate_copy_scope(journal, root, home)
        receipt = Path(root) / "receipts.json"
        original = next((e for e in journal.data["entries"] if e["target"] == str(receipt)), None)
        if original is None:
            if journal.data["entries"]:
                raise ContractError("organization-copy journal has no receipt binding")
            # Receipt capture is first. Its absence means no write capability
            # escaped create/capture, including a failed backup operation.
            journal.rollback()
            continue
        before = original.get("fingerprint", [[None, None, None]])[0][2]
        current = hashlib.sha256(receipt.read_bytes()).hexdigest() if receipt.exists() else None
        if current not in {before, journal.data.get("receipt_after_sha256")}:
            raise ContractError("organization-copy receipt changed outside its transaction")
        journal.rollback()


@contextlib.contextmanager
def organization_copy_transaction(receipts, paths, home):
    import uuid
    root = receipts.path.parent
    journal = EnrollmentJournal.create(root / "copy-transactions", uuid.uuid4().hex, None,
        files=[receipts.path], skill_parents=sorted({p.parent for p in paths}), purpose="org-copy")
    validate_copy_scope(journal, root, home)
    journal.capture(receipts.path)
    for path in paths:
        journal.capture(path)
    previous_data = json.loads(json.dumps(receipts.data))
    try:
        yield
        # Receipts.save uses this canonical encoding. Journal the expected
        # committed bytes before activation for crash-safe recovery.
        encoded = (json.dumps(receipts.data, indent=2, sort_keys=True) + "\n").encode("utf-8")
        journal.data["receipt_after_sha256"] = hashlib.sha256(encoded).hexdigest()
        journal._save()
        receipts.save()
        journal.commit()
    except BaseException:
        journal.rollback()
        receipts.data = previous_data
        raise
