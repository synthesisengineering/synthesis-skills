"""Reconcile only explicit, release-derived shared runtime payloads.

Selection and actual hook/service wiring belong to the engine. This module
never selects a component from file existence, rewrites personal configuration,
installs a service, or executes an optional inbox installer. Callers supply the
components whose selection or independently verified wiring establishes scope.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from enrollment import EnrollmentJournal, engine_lock, regular_tree
from system_contract import (
    ContractError, atomic_write_bytes, json_digest,
    public_source_identity, utcnow, verify_materialized_release, verify_release_checkout,
)


COMPONENTS = frozenset({"git-hooks", "message-guard", "kernel", "day-end"})
INTRODUCED_DEPENDENCIES = {
    "skills/synthesis-daily-rituals/scripts/ritual_state.py": (
        "skills/synthesis-daily-rituals/scripts/day-end",
        "skills/synthesis-daily-rituals/scripts/day-end-nudge.sh",
    ),
}


@dataclass(frozen=True)
class Payload:
    component: str
    source_relative: str
    target: Path
    content: bytes
    mode: int
    source_commit: str

    @property
    def fingerprint(self):
        return hashlib.sha256(self.content).hexdigest(), self.mode


@dataclass(frozen=True)
class RuntimePlan:
    home: Path
    state_dir: Path
    entries: tuple[Payload, ...]
    before: tuple
    receipt_digest: str
    receipt_before: tuple | None


def _regular_file(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ContractError("runtime path must be absolute without traversal")
    regular_tree(path)
    if path.exists() and not path.is_file():
        raise ContractError("runtime target is not a regular file: %s" % path)


def _fingerprint(path):
    _regular_file(path)
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mode & 0o777


def _git(root, *args, allowed_failure=False):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args], capture_output=True,
                                timeout=30, check=False, env=environment)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError("runtime release Git evidence could not be read") from exc
    if result.returncode:
        if allowed_failure and result.returncode == 1:
            return None
        raise ContractError("runtime release Git evidence is unavailable")
    return result.stdout


def _specs(home, state_dir, components):
    components = set(components)
    if components - COMPONENTS:
        raise ContractError("unsupported runtime component: %s" % ", ".join(sorted(components - COMPONENTS)))
    result = []
    if "git-hooks" in components:
        for name in ("pre-commit", "commit-msg", "_load_config.py"):
            result.append(("git-hooks", "skills/synthesis-git-hooks/scripts/" + name,
                           home / ".synthesis/git-hooks" / name, 0o755))
        for name in ("coordination.py", "coordination_schema.py", "pointer_lock.py", "peer_addressing.py"):
            result.append(("git-hooks", "skills/synthesis-project-management/scripts/" + name,
                           home / ".synthesis/git-hooks" / name, 0o755))
        result.append(("git-hooks", "skills/synthesis-project-management/references/session-words-v1.txt.zlib.b85",
                       home / ".synthesis/references/session-words-v1.txt.zlib.b85", 0o644))
    if "message-guard" in components:
        result.append(("message-guard", "skills/synthesis-message-guard/scripts/message_guard.py",
                       home / ".synthesis/message-guard/message_guard.py", 0o755))
    if "kernel" in components:
        for name in ("kernel_sync.py", "whole_system.py"):
            result.append(("kernel", "skills/synthesis-onboarding/scripts/" + name, state_dir / "bin" / name, 0o755))
    if "day-end" in components:
        for name in ("day-end", "day-end-nudge.sh", "ritual_state.py"):
            result.append(("day-end", "skills/synthesis-daily-rituals/scripts/" + name,
                           home / ".synthesis/day-end/bin" / name, 0o755))
    return result


def inventory(source_root, home, state_dir, components, *, identity=None, allow_missing=False):
    """Exact released bytes; no generated policies, wiring, links or plists."""
    root, home, state_dir = Path(source_root), Path(home), Path(state_dir)
    identity = identity or public_source_identity(root)
    entries = []
    for component, relative, target, mode in _specs(home, state_dir, components):
        source = root / relative
        _regular_file(source)
        if allow_missing and not source.exists():
            continue
        content = source.read_bytes()
        if identity.get("kind") == "git":
            tree = _git(root, "ls-tree", identity["commit"], "--", relative).decode()
            if not tree.startswith(("100644 blob ", "100755 blob ")):
                raise ContractError("runtime source is not a tracked regular file: %s" % relative)
            if _git(root, "show", identity["commit"] + ":" + relative) != content:
                raise ContractError("runtime source has modified tracked bytes: %s" % relative)
        entries.append(Payload(component, relative, target, content, mode, identity["commit"]))
    if "git-hooks" in components:
        entries.append(Payload("git-hooks", "@git-hooks-source-path", home / ".synthesis/git-hooks/source-path",
                               (str(root / "skills/synthesis-git-hooks/scripts") + "\n").encode(), 0o644,
                               identity["commit"]))
    return tuple(entries)


def _pointer_matches(content, entries):
    """A stable source-pointer spelling may stay when its scoped bytes agree."""
    try:
        text = content.decode("utf-8")
        pointer = Path(text.rstrip("\n"))
        if text != str(pointer) + "\n" or not pointer.is_absolute() or ".." in pointer.parts:
            return False
        if pointer.parts[-3:] != ("skills", "synthesis-git-hooks", "scripts"):
            return False
        # This is a read-only source reference, not a writable destination.
        # The documented stable pointer is a symlink; resolve it, then prove
        # every referenced payload against the independently verified release.
        root = pointer.resolve(strict=True).parents[2]
        for entry in entries:
            if entry.component != "git-hooks" or entry.source_relative.startswith("@"):
                continue
            source = root / entry.source_relative
            _regular_file(source)
            if source.read_bytes() != entry.content:
                return False
        return True
    except (OSError, ValueError, ContractError):
        return False


def _owned_records(data):
    if not isinstance(data, dict) or not isinstance(data.get("generated_files", {}), dict):
        raise ContractError("runtime receipt mapping is invalid")
    value = data.get("runtime_payloads", {"schema_version": 1, "files": {}})
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("files"), dict):
        raise ContractError("runtime ownership inventory is invalid")
    return value["files"]


def _owned(entry, record, before):
    if not isinstance(record, dict):
        return False
    if record.get("component") != entry.component or record.get("source_relative") != entry.source_relative:
        return False
    if not re.fullmatch(r"[a-f0-9]{40}", str(record.get("source_commit", ""))):
        return False
    if not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", ""))):
        return False
    if type(record.get("mode")) is not int or not 0 <= record["mode"] <= 0o777:
        return False
    return before is None or before == (record["sha256"], record["mode"])


def pending(state_dir):
    """Read pending runtime identities; never recover from a diagnostic."""
    root = Path(state_dir) / "runtime-transactions"
    regular_tree(root)
    if not root.exists():
        return []
    result = []
    for path in sorted(root.iterdir()):
        if path.name == ".staging":
            continue
        journal = EnrollmentJournal(path)
        if journal.data.get("purpose") != "runtime-payload":
            raise ContractError("runtime journal purpose is invalid")
        if journal.data["state"] == "pending":
            result.append(path.name)
    return result


def _git_blob(root, commit, relative):
    tree = _git(root, "ls-tree", "-z", commit, "--", relative)
    if not tree:
        return None
    records = tree.rstrip(b"\0").split(b"\0")
    if len(records) != 1:
        raise ContractError("runtime Git blob identity is ambiguous")
    metadata, name = records[0].split(b"\t", 1)
    mode, kind, object_id = metadata.decode("ascii").split()
    if name.decode() != relative or mode not in {"100644", "100755"} or kind != "blob":
        raise ContractError("runtime history is not a tracked regular blob: %s" % relative)
    return _git(root, "cat-file", "blob", object_id)


def _git_manifest_version(root, commit):
    versions = []
    for client in ("claude", "codex"):
        raw = _git_blob(root, commit, "." + client + "-plugin/plugin.json")
        try:
            data = json.loads(raw) if raw is not None else None
        except (ValueError, UnicodeError) as exc:
            raise ContractError("runtime history plugin manifest is malformed") from exc
        if not isinstance(data, dict) or data.get("name") != "synthesis-skills":
            raise ContractError("runtime history requires both public plugin manifests")
        version = data.get("version")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
            raise ContractError("runtime history plugin version is invalid")
        versions.append(version)
    if versions[0] != versions[1]:
        raise ContractError("runtime history plugin manifests disagree")
    return versions[0]


def _released_match(entry, before, historical):
    if before is None:
        return False
    by_relative = {old.source_relative: old for old in historical}
    old = by_relative.get(entry.source_relative)
    if old is not None and before == old.fingerprint:
        return True
    if entry.source_relative == "@git-hooks-source-path" and before[1] == entry.mode:
        required = {relative for component, relative, _, _ in _specs(entry.target.parents[2], entry.target.parent, {"git-hooks"})}
        if required <= set(by_relative):
            return _pointer_matches(entry.target.read_bytes(), historical)
    return False


def _historical_git_payloads(repository, source_root, identity, entries, before, needed):
    """Read local immutable blobs; a caller supplies the one acquisition repo."""
    repository = Path(repository)
    if not repository.is_absolute() or ".." in repository.parts:
        raise ContractError("runtime history repository must be an absolute contained path")
    regular_tree(repository)
    if not repository.is_dir():
        raise ContractError("runtime history repository is missing")
    bare = _git(repository, "rev-parse", "--is-bare-repository").strip() == b"true"
    actual = _git(repository, "rev-parse", "--absolute-git-dir" if bare else "--show-toplevel").decode().strip()
    if Path(actual).resolve() != repository.resolve():
        raise ContractError("runtime history requires an exact repository root")
    commit = identity["commit"]
    if _git(repository, "rev-parse", "--verify", commit + "^{commit}").decode().strip() != commit:
        raise ContractError("runtime history current commit binding is invalid")
    if identity["kind"] == "git":
        if _git(repository, "rev-parse", commit + "^{tree}") != _git(Path(source_root), "rev-parse", commit + "^{tree}"):
            raise ContractError("runtime history current source tree differs")
    current_tag = None
    if identity["kind"] == "release":
        current_tag = "refs/tags/v" + identity["version"]
        if _git(repository, "rev-parse", "--verify", current_tag + "^{commit}").decode().strip() != commit:
            raise ContractError("runtime history current release tag differs")
        if _git_manifest_version(repository, commit) != identity["version"]:
            raise ContractError("runtime history current release manifests differ")
    for entry in entries:
        if not entry.source_relative.startswith("@") and _git_blob(repository, commit, entry.source_relative) != entry.content:
            raise ContractError("runtime history current payload differs from selected source")
    tags = _git(repository, "for-each-ref", "--format=%(refname)", "refs/tags").decode().splitlines()
    tags = [tag for tag in tags if re.fullmatch(r"refs/tags/v[0-9]+\.[0-9]+\.[0-9]+", tag)]
    tags.sort(key=lambda tag: tuple(map(int, tag.rsplit("/v", 1)[1].split("."))), reverse=True)
    for tag in tags:
        if not needed:
            break
        historical_commit = _git(repository, "rev-parse", "--verify", tag + "^{commit}").decode().strip()
        if _git(repository, "merge-base", "--is-ancestor", historical_commit, commit, allowed_failure=True) is None:
            continue
        wanted = {entries[position].source_relative for position in needed}
        if "@git-hooks-source-path" in wanted:
            wanted.update(entry.source_relative for entry in entries if entry.component == "git-hooks")
        historical = []
        for entry in entries:
            if entry.source_relative.startswith("@") or entry.source_relative not in wanted:
                continue
            content = _git_blob(repository, historical_commit, entry.source_relative)
            if content is not None:
                historical.append(replace(entry, content=content, source_commit=historical_commit))
        if not any(_released_match(entries[position], before[position], historical) for position in needed):
            continue
        if _git_manifest_version(repository, historical_commit) != tag.rsplit("/v", 1)[1]:
            raise ContractError("runtime historical tag and plugin versions disagree")
        if _git(repository, "rev-parse", "--verify", tag + "^{commit}").decode().strip() != historical_commit:
            raise ContractError("runtime historical tag changed during verification")
        if current_tag and _git(repository, "rev-parse", "--verify", current_tag + "^{commit}").decode().strip() != commit:
            raise ContractError("runtime current release tag changed during verification")
        yield tuple(historical)

def plan(source_root, home, state_dir, components, receipt_data, *, legacy_releases=(), legacy_git_root=None):
    """Prove the complete selected closure before touching any installed target.

    Legacy descriptors identify explicit immutable roots. The optional local
    acquisition repository supplies older tagged blobs bound to the current
    source commit; this function never fetches, checks out or scans other roots.
    Only the declared day-end helper may be newly introduced, and only when
    both already-present launcher anchors have independent released-byte proof.
    """
    home, state_dir = Path(home), Path(state_dir)
    if pending(state_dir):
        raise ContractError("runtime recovery is pending; run update or repair before acceptance")
    identity = public_source_identity(Path(source_root))
    entries = inventory(source_root, home, state_dir, components, identity=identity)
    records = _owned_records(receipt_data)
    accepted, snapshots, unresolved, additions, released = [], [], set(), set(), set()
    for position, entry in enumerate(entries):
        before = _fingerprint(entry.target)
        owned = _owned(entry, records.get(str(entry.target)), before)
        addition = before is None and not owned and entry.source_relative in INTRODUCED_DEPENDENCIES
        if before is None and not owned and not addition:
            raise ContractError("selected runtime payload is missing; restore its verified installation: %s" % entry.target)
        if before is not None and entry.source_relative == "@git-hooks-source-path":
            content = entry.target.read_bytes()
            if _pointer_matches(content, entries):
                entry = replace(entry, content=content)
        if before == entry.fingerprint:
            released.add(position)
        if addition:
            additions.add(position)
        elif not owned and before != entry.fingerprint:
            unresolved.add(position)
        accepted.append(entry)
        snapshots.append(before)
    required_anchors = set()
    by_relative = {entry.source_relative: position for position, entry in enumerate(accepted)}
    for position in additions:
        for relative in INTRODUCED_DEPENDENCIES[accepted[position].source_relative]:
            anchor = by_relative.get(relative)
            if anchor is None or snapshots[anchor] is None:
                raise ContractError("new runtime dependency requires both existing released day-end anchors")
            required_anchors.add(anchor)
    needed = unresolved | (required_anchors - released)

    def consume(historical):
        for position in list(needed):
            if _released_match(accepted[position], snapshots[position], historical):
                needed.remove(position)

    if needed and legacy_git_root is not None:
        for historical in _historical_git_payloads(legacy_git_root, source_root, identity, accepted, snapshots, needed):
            consume(historical)
            if not needed:
                break
    for root, descriptor in legacy_releases if needed else ():
        root = Path(root)
        if (root / ".git").exists():
            verify_release_checkout(root, descriptor)
        else:
            verify_materialized_release(root, descriptor)
        historical = inventory(root, home, state_dir, components,
            identity={"kind": "release", "commit": descriptor["commit"]}, allow_missing=True)
        consume(historical)
        if not needed:
            break
    if needed:
        raise ContractError("runtime payload is unowned or modified; release provenance required: %s" %
                            ", ".join(str(accepted[position].target) for position in sorted(needed)))
    return RuntimePlan(home, state_dir, tuple(accepted), tuple(snapshots), json_digest(receipt_data),
                       _fingerprint(state_dir / "receipts.json"))

def verify(runtime_plan, *, transaction_id=None):
    """Return currency per exact target without writing or acknowledging state."""
    results = []
    unresolved = [identity for identity in pending(runtime_plan.state_dir) if identity != transaction_id]
    if unresolved:
        results.append({"target": str(runtime_plan.state_dir / "runtime-transactions"),
                        "component": "recovery", "status": "pending", "detail": "interrupted runtime transaction requires recovery"})
    for entry in runtime_plan.entries:
        try:
            actual = _fingerprint(entry.target)
            status = "current" if actual == entry.fingerprint else "missing" if actual is None else "drift"
            detail = "release-derived bytes and mode match" if status == "current" else "runtime differs from selected release"
            if status == "current" and entry.source_relative == "@git-hooks-source-path" and not _pointer_matches(entry.content, runtime_plan.entries):
                status, detail = "drift", "runtime source reference no longer matches selected release"
        except (OSError, ContractError) as exc:
            status, detail = "unsafe", str(exc)
        results.append({"target": str(entry.target), "component": entry.component, "status": status, "detail": detail})
    return results


def _rollback(journal):
    """Restore only mutations we started, never newer external edits."""
    entries = journal.data["entries"]
    for entry in entries:
        journal._target(entry["target"])
    for entry in entries:
        if not entry.get("runtime_started"):
            continue
        current = _fingerprint(Path(entry["target"]))
        before = entry.get("runtime_before")
        after = entry.get("runtime_after")
        permitted = (tuple(before) if before else None, tuple(after) if after else None)
        if current is None and _fingerprint(journal.root / "failed" / entry["slot"]) in permitted:
            # A prior rollback may have archived the failed generation and
            # stopped before copying its verified backup back into place.
            # The journal's rollback re-verifies that backup before restoring.
            continue
        if current not in permitted:
            raise ContractError("runtime rollback refuses a concurrent target change: %s" % entry["target"])
    # The durable journal retains all backups. The generic rollback skips only
    # entries that this transaction never began to mutate.
    for entry in entries:
        if not entry.get("runtime_started"):
            entry["restored"] = True
    journal._save()
    journal.rollback()


def recover(home, state_dir):
    """Recover interrupted runtime transactions from an exact re-derived scope."""
    home, state_dir = Path(home), Path(state_dir)
    root = state_dir / "runtime-transactions"
    regular_tree(root)
    if not root.exists():
        return []
    recovered = []
    allowed = {str(p) for _, _, p, _ in _specs(home, state_dir, COMPONENTS)}
    allowed.update({str(home / ".synthesis/git-hooks/source-path"), str(state_dir / "receipts.json")})
    with engine_lock(state_dir):
        for path in sorted(root.iterdir()):
            if path.name == ".staging":
                continue
            journal = EnrollmentJournal(path)
            if journal.data.get("purpose") != "runtime-payload" or not set(journal.data["allowed_files"]) <= allowed or journal.data["skill_parents"]:
                raise ContractError("runtime recovery journal has an invalid scope")
            if journal.data["state"] == "pending":
                _rollback(journal)
                recovered.append(str(path))
    return recovered


def apply(runtime_plan, receipts, *, verify_after=None):
    """Commit payload and refresh authority after selected doctors pass.

    runtime_payloads authorizes future release-derived refresh, not removal.
    An independently configured shared runtime may be needed by other clients;
    enrollment therefore never adds a generated_files/uninstall claim. Existing
    conffile receipts keep their original removal authority and current hashes.
    """
    if Path(receipts.path) != runtime_plan.state_dir / "receipts.json":
        raise ContractError("runtime receipt path is outside the engine state directory")
    receipts.assert_current()
    before_data = copy.deepcopy(receipts.data)
    if json_digest(before_data) != runtime_plan.receipt_digest:
        raise ContractError("runtime receipt changed after preflight")
    entries = runtime_plan.entries
    proposed = copy.deepcopy(before_data)
    files = copy.deepcopy(_owned_records(proposed))
    for entry in entries:
        files[str(entry.target)] = {"component": entry.component, "source_relative": entry.source_relative,
                                    "source_commit": entry.source_commit, "sha256": entry.fingerprint[0], "mode": entry.mode}
        # Existing conffile ownership has another consumer in init/repair.
        # Advance that receipt only where it already owned this exact payload;
        # independent enrollment must not invent uninstall ownership.
        generated = proposed.get("generated_files", {}).get(str(entry.target))
        if generated is not None:
            if not isinstance(generated, dict):
                raise ContractError("generated runtime receipt is invalid")
            if generated.get("sha256") != entry.fingerprint[0]:
                generated.update(sha256=entry.fingerprint[0], written_at=utcnow(),
                                 runtime_source_commit=entry.source_commit)
    proposed["runtime_payloads"] = {"schema_version": 1, "files": files}
    changed = [entry for entry, before in zip(entries, runtime_plan.before) if entry.fingerprint != before]
    with engine_lock(runtime_plan.state_dir):
        if pending(runtime_plan.state_dir):
            raise ContractError("runtime recovery became pending after preflight")
        if _fingerprint(Path(receipts.path)) != runtime_plan.receipt_before:
            raise ContractError("runtime receipt changed after preflight")
        for entry, before in zip(entries, runtime_plan.before):
            if _fingerprint(entry.target) != before:
                raise ContractError("runtime target changed after preflight: %s" % entry.target)
        if not changed and proposed == before_data:
            if verify_after:
                if verify_after() is False:
                    raise ContractError("selected runtime doctor failed")
            if any(row["status"] != "current" for row in verify(runtime_plan)):
                raise ContractError("runtime payload changed during doctor verification")
            if _fingerprint(Path(receipts.path)) != runtime_plan.receipt_before:
                raise ContractError("runtime receipt changed during doctor verification")
            return {"changed": [], "enrolled": len(entries), "journal": None}
        receipt_path = Path(receipts.path)
        _regular_file(receipt_path)
        journal = EnrollmentJournal.create(runtime_plan.state_dir / "runtime-transactions", uuid.uuid4().hex,
                                           None, files=[e.target for e in changed] + [receipt_path],
                                           skill_parents=[], purpose="runtime-payload")
        try:
            snapshots = {e.target: before for e, before in zip(entries, runtime_plan.before)}
            snapshots[receipt_path] = runtime_plan.receipt_before
            for target in [e.target for e in changed] + [receipt_path]:
                journal.capture(target)
                record = next(e for e in journal.data["entries"] if e["target"] == str(target))
                original = record.get("fingerprint")
                captured = None if not original else (original[0][2], original[0][1])
                if captured != snapshots[target]:
                    raise ContractError("runtime target changed before capture: %s" % target)
            writes = [(e.target, e.content, e.mode) for e in changed]
            encoded = (json.dumps(proposed, indent=2, sort_keys=True) + "\n").encode()
            receipt_mode = runtime_plan.receipt_before[1] if runtime_plan.receipt_before is not None else 0o600
            receipt_after = (hashlib.sha256(encoded).hexdigest(), receipt_mode)
            writes.append((receipt_path, encoded, receipt_mode))
            for target, content, mode in writes:
                record = next(e for e in journal.data["entries"] if e["target"] == str(target))
                original = record.get("fingerprint")
                before = None if not original else (original[0][2], original[0][1])
                if _fingerprint(target) != before:
                    raise ContractError("runtime target changed during activation: %s" % target)
                after = (hashlib.sha256(content).hexdigest(), mode)
                record.update(runtime_started=True, runtime_before=before, runtime_after=after)
                journal._save()
                atomic_write_bytes(target, content, mode)
                if _fingerprint(target) != after:
                    raise ContractError("runtime write verification failed: %s" % target)
            if any(row["status"] != "current" for row in verify(runtime_plan, transaction_id=journal.root.name)):
                raise ContractError("runtime verification failed after activation")
            receipts.data = proposed
            if verify_after:
                if verify_after() is False:
                    raise ContractError("selected runtime doctor failed")
            if any(row["status"] != "current" for row in verify(runtime_plan, transaction_id=journal.root.name)):
                raise ContractError("runtime payload changed during doctor verification")
            if _fingerprint(receipt_path) != receipt_after:
                raise ContractError("runtime receipt changed during doctor verification")
            journal.commit()
        except BaseException:
            receipts.data = before_data
            _rollback(journal)
            raise
        # The journal is committed before acknowledging its new disk baseline.
        # A later independent edit must fail acknowledgement without attempting
        # to roll back a committed generation or overwrite that newer receipt.
        receipts.accept_runtime_write(runtime_plan.receipt_before, receipt_after)
    return {"changed": [str(e.target) for e in changed], "enrolled": len(entries), "journal": str(journal.root)}
