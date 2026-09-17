"""Selection and reversible discovery bindings inside the existing reconciler.

Payloads are ordinary release-derived files outside client discovery roots.
Only selected skill entrypoints are linked into those roots. No plugin, hook,
service, workspace or instruction file is activated by this module.
"""
from __future__ import annotations

import ast
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import uuid

from system_contract import (ContractError, atomic_write_json, canonical_tree_digest,
                             default_desired_state, file_digest, json_digest,
                             public_source_identity, safe_identifier, active_release_descriptor, descriptor_fields,
                             release_descriptor_from_checkout, validate_release_descriptor, verify_materialized_release,
                             safe_relative_path, validate_modular_selection, utcnow)

RUNTIME_SKILLS = frozenset({"synthesis-onboarding", "synthesis-agent-conformance",
                           "synthesis-project-management", "synthesis-context-lifecycle",
                           "synthesis-repo-guard", "synthesis-skills-manager"})
NAME = re.compile(r"\bsynthesis-[a-z0-9][a-z0-9-]*\b")


def _regular(path, *, allow_missing=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ContractError("modular path must be absolute without traversal")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ContractError("modular path crosses a symlink: %s" % ancestor)
    if not path.exists():
        if allow_missing:
            return
        raise ContractError("modular path is missing: %s" % path)
    if not (path.is_file() or path.is_dir()):
        raise ContractError("modular path is not regular: %s" % path)


def _entry(path):
    _regular(path)
    if not path.is_file():
        raise ContractError("modular payload entry must be a regular file")
    return {"sha256": file_digest(path), "mode": 0o755 if path.stat().st_mode & stat.S_IXUSR else 0o644}


def _source_files(source, release_evidence=None):
    _regular(source)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    def git(*arguments):
        return subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(source), *arguments],
                              capture_output=True, env=env, timeout=30)
    top = git("rev-parse", "--show-toplevel")
    if top.returncode == 0 and Path(top.stdout.decode().strip()).resolve() == source.resolve():
        head = git("rev-parse", "HEAD^{commit}")
        listing = git("ls-tree", "-r", "-z", "--full-tree", "HEAD")
        untracked = git("ls-files", "--others", "--exclude-standard", "-z")
        index = git("diff-index", "--cached", "--quiet", "--no-ext-diff", "--no-textconv", "HEAD", "--")
        if head.returncode or listing.returncode or untracked.returncode or untracked.stdout or index.returncode:
            raise ContractError("modular source must be a committed clean release checkout")
        inventory = {}
        for record in listing.stdout.split(b"\0"):
            if not record:
                continue
            metadata, name_bytes = record.split(b"\t", 1)
            mode, kind, oid = metadata.split()
            if mode not in {b"100644", b"100755"} or kind != b"blob":
                raise ContractError("modular source contains a link or special object")
            name = name_bytes.decode()
            path = source / safe_relative_path(name)
            evidence = _entry(path)
            content = path.read_bytes()
            digest = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            if digest != oid.decode() or evidence["mode"] != (0o755 if mode == b"100755" else 0o644):
                raise ContractError("modular source bytes or modes are not committed")
            inventory[name] = evidence
        return dict(sorted(inventory.items())), {"kind": "git", "root": str(source.resolve()), "commit": head.stdout.decode().strip()}
    active = active_release_descriptor()
    if active is None:
        raise ContractError("modular source must be a verified release or committed source checkout")
    descriptor = descriptor_fields(active)
    if Path(active["release_root"]).resolve() != source.resolve():
        if release_evidence is None:
            raise ContractError("modular source is not the current verified release")
        validate_release_descriptor(release_evidence)
        if any(release_evidence[key] != descriptor[key] for key in ("commit", "version", "content_digest", "source_url")):
            raise ContractError("saved source proof differs from the independently active release")
        descriptor = release_evidence
    verify_materialized_release(source, descriptor)
    names = [p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()]
    return {name: _entry(source / safe_relative_path(name)) for name in sorted(names)}, {
        "kind": "release", "root": str(source.resolve()), "commit": active["commit"],
        "version": active["version"], "content_digest": active["content_digest"], "descriptor": descriptor}


def _declared_dependencies(skill):
    body = skill.read_text(encoding="utf-8")
    if not body.startswith("---\n") or "\n---" not in body[4:]:
        raise ContractError("skill frontmatter is missing: %s" % skill)
    header = body.split("---", 2)[1]
    match = re.search(r"(?m)^depends_on:\s*(\[[^\n]*\])\s*$", header)
    if match:
        try:
            result = ast.literal_eval(match[1])
        except (ValueError, SyntaxError) as exc:
            raise ContractError("invalid skill dependency list") from exc
    else:
        block = re.search(r"(?m)^depends_on:[ \t]*\n((?:[ \t]+-[^\n]*\n)+)", header)
        if not block:
            raise ContractError("skill needs an explicit dependency list: %s" % skill)
        result = [line.strip()[1:].strip().strip('\"\'') for line in block[1].splitlines()]
        if any(not re.fullmatch(r"synthesis-[a-z0-9-]+", item) for item in result):
            raise ContractError("invalid block skill dependency list")
    if not isinstance(result, list) or any(not isinstance(v, str) for v in result) or len(set(result)) != len(result):
        raise ContractError("skill dependency list is invalid")
    return result


def runtime_files(source):
    """Required CLI support, without unrelated SKILL.md entrypoints or hooks."""
    result = set()
    for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "LICENSE-APACHE", "LICENSE-CC0", "onboard.sh"):
        if (source / name).is_file():
            result.add(name)
    for skill in RUNTIME_SKILLS:
        directory = source / "skills" / skill
        for path in directory.rglob("*"):
            relative = path.relative_to(source)
            if not path.is_file() or "__pycache__" in relative.parts:
                continue
            if path.name.startswith("test_") or path.name == "SKILL.md" or "agents" in relative.parts or "tests" in relative.parts:
                continue
            # Runtime imports and data remain together; no service installer
            # or hook is executed merely because its bytes are available.
            result.add(relative.as_posix())
    return {name: _entry(source / name) for name in sorted(result)}


def resolve_selection(source, roots, stage_core, release_evidence=None):
    source = Path(source)
    selection = validate_modular_selection({"roots": roots, "stage_core": stage_core})
    source_files, identity = _source_files(source, release_evidence)
    graph = {p.parent.name: _declared_dependencies(p) for p in (source / "skills").glob("*/SKILL.md")}
    for name, dependencies in graph.items():
        safe_identifier(name, "skill")
        if any(dependency not in graph for dependency in dependencies):
            raise ContractError("skill dependency is absent: %s" % name)
    try:
        tuple(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise ContractError("skill dependency cycle") from exc
    if any(name not in graph for name in roots):
        raise ContractError("requested skill is absent from this release; acquire the selected release before changing selection")
    visible = set()
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name not in visible:
            visible.add(name)
            pending.extend(graph[name])
    # Executable support is separate from visible skill dependencies. Existing
    # scripts locate sibling packages through Path(__file__).resolve(), so keep
    # their canonical release layout in this physically isolated payload.
    available = {p.name for p in (source / "skills").iterdir() if p.is_dir()}
    support = set(RUNTIME_SKILLS & available)
    pending = list(visible | support)
    examined = set()
    required = set(runtime_files(source))
    while pending:
        name = pending.pop()
        if name in examined:
            continue
        examined.add(name)
        prefix = "skills/%s/" % name
        for relative in source_files:
            if not relative.startswith(prefix):
                continue
            path = source / relative
            if name in visible or (path.name != "SKILL.md" and "/agents/" not in relative and
                                   not path.name.startswith("test_") and "/tests/" not in relative):
                required.add(relative)
            if path.suffix in {".py", ".sh"} and not path.name.startswith("test_"):
                linked = set(NAME.findall(path.read_text(errors="replace"))) & available
                new = linked - visible - support
                support.update(new)
                pending.extend(new)
    required_files = {name: source_files[name] for name in sorted(required)}
    optional = {name: entry for name, entry in source_files.items() if name not in required_files} if stage_core else {}
    return {**selection, "skills": sorted(visible), "support_skills": sorted(support - visible),
            "files": {**required_files, **optional}, "required_files": required_files,
            "optional_core_files": optional, "source": identity,
            "source_digest": json_digest(source_files)}


def verify_payload(root, inventory):
    _regular(root)
    observed = {}
    for path in root.rglob("*"):
        _regular(path)
        if path.is_file():
            observed[path.relative_to(root).as_posix()] = _entry(path)
    if observed != inventory:
        raise ContractError("modular payload membership, bytes or modes drifted")


def materialize_payload(source, target, inventory):
    source, target = Path(source), Path(target)
    _regular(source)
    _regular(target, allow_missing=True)
    if target == source or target in source.parents or source in target.parents:
        raise ContractError("modular source and payload overlap")
    if target.exists():
        verify_payload(target, inventory)
        return
    _regular(target.parent, allow_missing=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".modular-stage-", dir=target.parent) as temporary:
        stage = Path(temporary)
        for relative, expected in inventory.items():
            original = source / safe_relative_path(relative)
            if _entry(original) != expected:
                raise ContractError("modular source changed after resolution")
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
            destination.chmod(expected["mode"])
        verify_payload(stage, inventory)
        os.replace(stage, target)


def _receipt_path(state):
    return state.state_dir / "modular" / "receipt.json"


def validate_receipt(state, value):
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ContractError("modular receipt is invalid")
    expected = {"schema_version", "selection", "skills", "support_skills", "payload", "inventory", "source", "bindings", "optional_core_bytes"}
    if set(value) != expected or not isinstance(value["bindings"], dict) or not isinstance(value["source"], dict):
        raise ContractError("modular receipt fields are invalid")
    validate_modular_selection(value.get("selection"))
    for field in ("skills", "support_skills"):
        items = value[field]
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items) or len(set(items)) != len(items):
            raise ContractError("modular receipt skill inventory is invalid")
        for item in items:
            safe_identifier(item)
    if not set(value["selection"]["roots"]) <= set(value["skills"]):
        raise ContractError("modular receipt omits selected roots")
    inventory = value["inventory"]
    if not isinstance(inventory, dict) or not inventory:
        raise ContractError("modular receipt inventory is invalid")
    for relative, entry in inventory.items():
        safe_relative_path(relative)
        if not isinstance(entry, dict) or set(entry) != {"sha256", "mode"} or not re.fullmatch(r"[a-f0-9]{64}", str(entry["sha256"])) or type(entry["mode"]) is not int or entry["mode"] not in {0o644, 0o755}:
            raise ContractError("modular receipt file evidence is invalid")
    if type(value["optional_core_bytes"]) is not int or value["optional_core_bytes"] < 0:
        raise ContractError("modular receipt optional bytes are invalid")
    payload = Path(value.get("payload", ""))
    allowed = state.cache_dir / "modular" / "payloads"
    if payload.parent != allowed or not re.fullmatch(r"[a-f0-9]{64}", payload.name):
        raise ContractError("modular receipt payload is outside its owned cache")
    for path_text, target_text in value.get("bindings", {}).items():
        path, target = Path(path_text), Path(target_text)
        parents = {state.home / ".claude/skills", state.home / ".agents/skills"}
        if path.parent not in parents or path.name not in value["skills"] or target != payload / "skills" / path.name:
            raise ContractError("modular receipt claims an unowned binding")
    if payload.name != json_digest(inventory):
        raise ContractError("modular receipt inventory does not bind its payload")
    return value


def receipt(state):
    path = _receipt_path(state)
    _regular(path, allow_missing=True)
    if not path.exists():
        return None
    try:
        return validate_receipt(state, json.loads(path.read_text()))
    except (ValueError, TypeError, KeyError) as exc:
        raise ContractError("modular receipt is invalid: %s" % exc) from exc


def _link_value(path):
    _regular(path.parent, allow_missing=True)
    if path.is_symlink():
        return os.readlink(path)
    if path.exists():
        raise ContractError("foreign file occupies modular skill binding: %s" % path)
    return None


def _journal_path(state):
    return state.state_dir / "modular" / "pending.json"


def recover(state, *, rollback=False, rollback_engine=None):
    journal = _journal_path(state)
    _regular(journal, allow_missing=True)
    if not journal.exists():
        return
    value = json.loads(journal.read_text())
    if value.get("schema_version") != 1:
        raise ContractError("modular recovery journal is invalid")
    prior = value.get("prior")
    new = validate_receipt(state, value.get("new"))
    if prior is not None:
        validate_receipt(state, prior)
    transaction_id = value.get("transaction_id")
    if not re.fullmatch(r"[a-f0-9]{32}", str(transaction_id)):
        raise ContractError("modular recovery lacks transaction authority")
    transactions = [item for item in state.read_observation()["transactions"] if item["transaction_id"] == transaction_id]
    if len(transactions) != 1:
        raise ContractError("modular recovery transaction is missing")
    transaction = transactions[0]
    recovery = transaction.get("recovery") or {}
    prepared = recovery.get("prepared_desired")
    if not rollback and transaction["state"] == "pending" and prepared is not None:
        if receipt(state) != new or (transaction.get("details") or {}).get("modular_receipt_digest") != json_digest(new):
            raise ContractError("prepared modular receipt changed")
        verify_payload(Path(new["payload"]), new["inventory"])
        if any(_link_value(Path(path)) != target for path, target in new["bindings"].items()):
            raise ContractError("prepared modular bindings changed")
        for path in (prior or {}).get("bindings", {}):
            if path not in new["bindings"] and _link_value(Path(path)) is not None:
                raise ContractError("prepared modular removal changed")
        transaction = state.finalize_prepared(transaction_id)
    if not rollback and transaction["state"] == "committed":
        desired = state.read_desired()
        if not desired or json_digest(desired) != transaction.get("committed_desired_digest") or receipt(state) != new:
            raise ContractError("committed modular transaction binding changed")
        verify_payload(Path(new["payload"]), new["inventory"])
        if any(_link_value(Path(path)) != target for path, target in new["bindings"].items()):
            raise ContractError("committed modular bindings changed")
        finish(state)
        return
    expected_before = (prior or {}).get("bindings", {})
    expected_after = new["bindings"]
    items = value.get("bindings")
    if not isinstance(items, list) or any(not isinstance(item, dict) or set(item) != {"path", "before", "after"} for item in items):
        raise ContractError("modular journal bindings are invalid")
    paths = [item["path"] for item in items]
    if any(not isinstance(path, str) for path in paths) or len(set(paths)) != len(paths) or set(paths) != set(expected_before) | set(expected_after):
        raise ContractError("modular journal binding membership differs from ownership receipts")
    for item in items:
        if item["before"] not in (None, expected_before.get(item["path"])) or item["after"] != expected_after.get(item["path"]):
            raise ContractError("modular journal exceeds before/after receipt authority")
    if not rollback and transaction["state"] == "pending":
        if recovery and state.read_desired() != recovery["prior_desired"]:
            raise ContractError("unprepared transaction cannot replace changed desired state")
        if state.read_observation()["transactions"][-1]["transaction_id"] != transaction_id:
            raise ContractError("modular rollback is no longer the latest transaction")
    allowed_parents = {state.home / ".claude/skills", state.home / ".agents/skills"}
    # Preflight every owned binding before any rollback mutation.
    for item in items:
        path = Path(item["path"])
        safe_identifier(path.name)
        if path.parent not in allowed_parents:
            raise ContractError("modular recovery target is outside client skill roots")
        for link in (item["before"], item["after"]):
            if link is not None:
                target = Path(link)
                if not target.is_relative_to(state.cache_dir / "modular/payloads") or target.name != path.name:
                    raise ContractError("modular recovery link escapes owned payloads")
        current = _link_value(path)
        if current not in {item["before"], item["after"], None}:
            raise ContractError("modular recovery preserves a concurrently replaced binding")
    if not rollback and transaction["state"] == "pending" and transaction["command"] in {"activate", "deactivate"}:
        if rollback_engine is None or not recovery:
            raise ContractError("interrupted broader integration requires verified engine recovery; journal retained")
        rollback_engine(recovery["prior_desired"], transaction)
    for item in items:
        path = Path(item["path"])
        current = _link_value(path)
        if current not in {item["before"], item["after"], None}:
            raise ContractError("modular binding changed during recovery")
        if current != item["before"]:
            if current is not None:
                path.unlink()
            if item["before"] is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(item["before"], target_is_directory=True)
    if prior is None:
        if _receipt_path(state).exists():
            _receipt_path(state).unlink()
    else:
        atomic_write_json(_receipt_path(state), prior)
    if not rollback and transaction["state"] == "pending":
        if recovery:
            current = state.read_desired()
            if current != recovery["prior_desired"]:
                raise ContractError("unprepared transaction cannot replace changed desired state")
        observation = state.read_observation()
        if observation["transactions"][-1]["transaction_id"] != transaction_id:
            raise ContractError("modular rollback is no longer the latest transaction")
        observation["transactions"][-1].update(state="aborted", error="interrupted operation recovered", finished_at=utcnow())
        observation["generation"] = transaction.get("previous_active_generation") or 0
        state._save_observation(observation)
    # Journal is retained as evidence; the pending name alone marks obligation.
    journal.rename(journal.with_name("recovered-%s.json" % uuid.uuid4().hex))


def reconcile_bindings(state, value, transaction):
    validate_receipt(state, value)
    prior = receipt(state)
    previous = (prior or {}).get("bindings", {})
    desired = value.get("bindings", {})
    changes = []
    for name in sorted(set(previous) | set(desired)):
        path = Path(name)
        current = _link_value(path)
        if current is not None and current != previous.get(name):
            raise ContractError("foreign or changed modular binding is preserved: %s" % path)
        changes.append({"path": name, "before": current, "after": desired.get(name)})
    journal = _journal_path(state)
    atomic_write_json(journal, {"schema_version": 1, "transaction_id": transaction["transaction_id"], "prior": prior, "new": value, "bindings": changes})
    try:
        for item in changes:
            path = Path(item["path"])
            if _link_value(path) != item["before"]:
                raise ContractError("modular binding changed during reconciliation")
            if item["before"] == item["after"]:
                continue
            if item["before"] is not None:
                path.unlink()
            if item["after"] is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(item["after"], target_is_directory=True)
        atomic_write_json(_receipt_path(state), value)
    except BaseException:
        recover(state, rollback=True)
        raise


def finish(state, transaction_id=None):
    path = _journal_path(state)
    _regular(path, allow_missing=True)
    if path.exists():
        if transaction_id is not None and json.loads(path.read_text()).get("transaction_id") != transaction_id:
            return
        path.rename(path.with_name("completed-%s.json" % uuid.uuid4().hex))


def install_operation(state, source, desired, transaction):
    selection = desired["modular"]
    plan = resolve_selection(source, selection["roots"], selection["stage_core"])
    payload = state.cache_dir / "modular/payloads" / json_digest(plan["files"])
    bindings = {str(state.home / (".claude" if client == "claude" else ".agents") / "skills" / name):
                str(payload / "skills" / name) for client in desired["clients"] for name in plan["skills"]}
    # Detect foreign destinations before even staging this selection's files.
    previous = (receipt(state) or {}).get("bindings", {})
    for name in set(previous) | set(bindings):
        current = _link_value(Path(name))
        if current is not None and current != previous.get(name):
            raise ContractError("foreign modular destination is preserved: %s" % name)
    materialize_payload(source, payload, plan["files"])
    value = {"schema_version": 1, "selection": selection, "skills": plan["skills"],
             "support_skills": plan["support_skills"], "payload": str(payload),
             "inventory": plan["files"], "source": plan["source"], "bindings": bindings,
             "optional_core_bytes": sum((source / name).stat().st_size for name in plan["optional_core_files"])}
    reconcile_bindings(state, value, transaction)
    verify_payload(payload, plan["files"])
    return planes(desired, value)


def planes(desired, value, *, issues=None):
    issues = issues or []
    return {
        "desired": {"status": "verified", "sha256": json_digest(desired)},
        "resolved": {"status": "verified", "skills": value["skills"], "support_skills": value["support_skills"]},
        "installed": {"status": "defective" if issues else "verified", "issues": issues},
        "source-provenance": {"status": "verified", **value["source"]},
        "live-loaded": {"status": "not-observed", "detail": "Skill discovery bindings are installed. A fresh client must load the selected skill; no native SessionStart receipt is fabricated."},
        "outcome-verified": {"status": "not-requested"},
        "details": {"modular_receipt_digest": json_digest(value), "modular": {**value["selection"], "skills": value["skills"],
                     "support_skills": value["support_skills"], "optional_core_bytes": value["optional_core_bytes"],
                     "core_state": "staged" if value["selection"]["stage_core"] else "declined"}},
    }


def inspect(state):
    desired = state.read_desired()
    value = receipt(state)
    if not desired or not value:
        raise ContractError("modular installation has no complete selection receipt")
    issues = []
    provenance_issues = []
    try:
        plan = resolve_selection(Path(value["source"]["root"]), value["selection"]["roots"], value["selection"]["stage_core"], value["source"].get("descriptor"))
        if plan["source"] != value["source"] or plan["files"] != value["inventory"] or plan["skills"] != value["skills"] or plan["support_skills"] != value["support_skills"]:
            raise ContractError("selection receipt is not derived from its independently verified source")
        optional_bytes = sum((Path(value["source"]["root"]) / name).stat().st_size for name in plan["optional_core_files"])
        if optional_bytes != value["optional_core_bytes"]:
            raise ContractError("optional core byte receipt differs from verified source")
        observation = state.read_observation()
        committed = [item for item in observation["transactions"] if item["state"] == "committed" and item["generation"] == observation["generation"]]
        if len(committed) != 1 or committed[0].get("committed_desired_digest") != json_digest(desired) or (committed[0].get("details") or {}).get("modular_receipt_digest") != json_digest(value):
            raise ContractError("selection and payload lack a matching committed transaction")
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        provenance_issues.append(str(exc))
    issues.extend(provenance_issues)
    expected_bindings = {str(state.home / (".claude" if client == "claude" else ".agents") / "skills" / name):
                         str(Path(value["payload"]) / "skills" / name)
                         for client in desired["clients"] for name in value["skills"]} if desired.get("enabled", True) else {}
    if desired.get("modular") != value["selection"] or value["bindings"] != expected_bindings:
        issues.append("selection receipt does not match the desired discovery bindings")
    if _journal_path(state).exists():
        issues.append("interrupted modular transaction; run synthesis repair")
    try:
        verify_payload(Path(value["payload"]), value["inventory"])
    except (ContractError, OSError) as exc:
        issues.append(str(exc))
    for name, target in value["bindings"].items():
        try:
            if _link_value(Path(name)) != target:
                issues.append("missing skill binding: %s" % name)
        except (ContractError, OSError) as exc:
            issues.append(str(exc))
    result = planes(desired, value, issues=issues)
    if provenance_issues:
        result["source-provenance"] = {"status": "unverified", "issues": provenance_issues}
        result["resolved"]["status"] = "unverified"
    if not desired.get("enabled", True):
        result["installed"] = {"status": "defective" if issues else "removed", "issues": issues}
        result["live-loaded"] = {"status": "not-applicable"}
    return {"status": "FAIL" if issues else "PASS", "planes": {k: v for k, v in result.items() if k != "details"},
            "modular": result["details"]["modular"],
            "next_action": "Run synthesis repair; foreign or edited files are preserved." if issues else
                           "Local installation verified. Load the selected skill in a fresh client; use synthesis activate to enable the broader ecosystem."}


def setup(state, source, roots, clients, stage_core, release=None, command="setup"):
    selection = validate_modular_selection({"roots": roots, "stage_core": stage_core})
    previous = state.read_desired()
    if previous and previous["profile"] != "modular" and previous.get("enabled", True):
        raise ContractError("an active full/catalog installation must be explicitly deactivated before modular setup")
    release = release or (previous or {}).get("release") or {"channel": "stable", "version_pin": None}
    desired = default_desired_state("modular", clients, release["channel"], release.get("version_pin"), modular=selection)
    with state.locked():
        recover(state)
        if state.read_desired() != previous:
            raise ContractError("desired selection changed during setup planning; retry")
        try:
            transaction = state.run_transaction(command, desired,
                lambda tx: install_operation(state, source, desired, tx), rollback=lambda _: recover(state, rollback=True), already_locked=True)
        except BaseException:
            raise
        finish(state)
    return transaction


def suspend(state, transaction):
    value = receipt(state)
    if not value:
        raise ContractError("modular activation has no saved selection")
    verify_payload(Path(value["payload"]), value["inventory"])
    reconcile_bindings(state, {**value, "bindings": {}}, transaction)
    return value


def restore(state, value=None):
    recover(state, rollback=True)


def disable(state):
    with state.locked():
        recover(state)
        desired = state.read_desired()
        if not desired or desired["profile"] != "modular":
            raise ContractError("no modular selection to uninstall")
        disabled = {**desired, "enabled": False}
        def operation(tx):
            value = receipt(state)
            if not value:
                raise ContractError("modular selection receipt is missing")
            removed = {**value, "bindings": {}}
            reconcile_bindings(state, removed, tx)
            result = planes(disabled, removed)
            result["installed"] = {"status": "removed"}
            result["live-loaded"] = {"status": "not-applicable"}
            return result
        result = state.run_transaction("uninstall", disabled, operation,
                                       rollback=lambda _: recover(state, rollback=True), already_locked=True)
        finish(state)
        return result


TOOLS = frozenset({"slopcheck", "console", "ownwords"})


def tool_receipts(state):
    directory = state.state_dir / "modular/tools"
    _regular(directory, allow_missing=True)
    results = []
    for path in directory.glob("*.json"):
        _regular(path)
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or set(value) != {"schema_version", "tool", "stage_core", "payload", "inventory", "source", "optional_core_bytes", "release_descriptor"} or value["schema_version"] != 1 or value["tool"] not in TOOLS or path.stem != value["tool"] or type(value["stage_core"]) is not bool:
            raise ContractError("tool staging receipt is invalid")
        if value["stage_core"]:
            payload = Path(value["payload"])
            if payload.parent != state.cache_dir / "modular/payloads" or payload.name != json_digest(value["inventory"]):
                raise ContractError("tool staging payload is outside its owned cache")
            verify_payload(payload, value["inventory"])
            if value["release_descriptor"] is not None:
                validate_release_descriptor(value["release_descriptor"])
                verify_materialized_release(payload, value["release_descriptor"])
        elif value["payload"] is not None or value["inventory"] or value["optional_core_bytes"] != 0:
            raise ContractError("declined tool staging retains an invalid payload declaration")
        results.append(value)
    return results


def stage_tool_core(source, tool, stage_core=True, home=None):
    from system_contract import SystemState
    if tool not in TOOLS or type(stage_core) is not bool:
        raise ContractError("tool staging requires a supported tool and boolean choice")
    source = Path(source)
    files, identity = _source_files(source)
    release_descriptor = None
    if identity["kind"] == "release":
        release_descriptor = descriptor_fields(active_release_descriptor())
        if release_descriptor.get("projection") and stage_core:
            raise ContractError("full dormant tool staging requires acquisition of the complete verified release")
    else:
        version = json.loads((source / ".claude-plugin/plugin.json").read_text())["version"]
        tag = subprocess.run(["git", "-C", str(source), "rev-parse", "--verify", "refs/tags/v" + version], capture_output=True, timeout=15)
        if tag.returncode == 0:
            release_descriptor = release_descriptor_from_checkout(source, "pin", "v" + version,
                                 "https://github.com/synthesisengineering/synthesis-skills.git")
    state = SystemState(home)
    with state.locked():
        tool_receipts(state)
        payload = None
        optional_bytes = 0
        if stage_core:
            payload = state.cache_dir / "modular/payloads" / json_digest(files)
            materialize_payload(source, payload, files)
            optional_bytes = sum((source / name).stat().st_size for name in files)
        value = {"schema_version": 1, "tool": tool, "stage_core": stage_core,
                 "payload": str(payload) if payload else None, "inventory": files if stage_core else {},
                 "source": identity, "optional_core_bytes": optional_bytes,
                 "release_descriptor": release_descriptor}
        path = state.state_dir / "modular/tools" / (tool + ".json")
        _regular(path, allow_missing=True)
        atomic_write_json(path, value)
    return {"status": "PASS", "tool": tool, "core_state": "staged" if stage_core else "declined",
            "optional_core_bytes": optional_bytes, "payload": value["payload"],
            "detail": "No client, hooks, services or workspace registration changed. Existing payloads remain preserved."}
