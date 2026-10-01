"""Explicit existing-format migration through resolver and record transactions.

A preview is not consent. Each selected project is a cooperative transaction;
sets report per-project outcomes and can resume their exact original intent.
Source prose is retained byte-for-byte. Native outcome acceptance is separate.
"""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
from datetime import datetime, timezone, timedelta
import yaml
import project_format as formats
import project_state
import record_transaction as records

MAX_PROJECTS = 128
MAX_SOURCES = 512
MAX_BYTES = 32 * 1024 * 1024
PLAN_SECONDS = 3600
READ_SECONDS = 30


def _digest(value):
    return hashlib.sha256(records._json(value)).hexdigest()


def _time(value=None):
    result = (
        datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value)
    )
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def _selection(selected):
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= MAX_PROJECTS
        or any(not isinstance(s, str) or not s for s in selected)
        or len(selected) != len(set(selected))
    ):
        raise ValueError("explicit bounded unique selected project IDs required")
    return sorted(selected)


def _yaml(raw):
    class Strict(yaml.SafeLoader):
        pass

    def pairs(loader, node, deep=False):
        return records._unique(
            [
                (
                    loader.construct_object(k, deep=True),
                    loader.construct_object(v, deep=True),
                )
                for k, v in node.value
            ]
        )

    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, pairs)
    return yaml.load(raw, Loader=Strict)


def _resolve(index, selected):
    raw, meta = records._snapshot(index)

    # Duplicate keys are rejected before the causal owner reads the index.
    data = _yaml(raw)
    rows = (
        data.get("projects")
        if isinstance(data, dict)
        else data
        if isinstance(data, list)
        else None
    )
    if not isinstance(rows, list) or len(rows) > 512:
        raise ValueError("bounded project registry required")
    ids = [r.get("id") if isinstance(r, dict) else None for r in rows]
    if any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("invalid or duplicate registry IDs")
    if set(selected) - set(ids):
        raise ValueError("selection is not in the exact registry")
    paths = []
    for name in selected:
        resolved = project_state.resolve_project(
            name,
            index,
            fetch=False,
            fast_forward_canonical=False,
            refresh_coordination=False,
        )
        if (
            resolved.status not in ("PASS", "LOCAL_RECOVERABLE")
            or not resolved.selected_path
        ):
            raise ValueError("causal project resolution refused: " + resolved.status)
        path = records._path(resolved.selected_path)
        if path.name != name:
            raise ValueError("registry selection and project identity differ")
        paths.append(path)
    if not records._matches(index, meta):
        raise ValueError("registry changed during resolution")
    return meta, paths


def _sources(project):
    deadline = time.monotonic() + READ_SECONDS
    files = [project / "CONTEXT.md", project / "REFERENCE.md"]
    directories = [project / "sessions"]
    for folder in (project / "sessions", project / "sessions/archive"):
        folder = records._path(folder, project)
        if not folder.exists():
            if folder.name == "sessions":
                raise ValueError("sessions directory missing")
            continue
        if not folder.is_dir():
            raise ValueError("invalid session directory")
        if folder not in directories:
            directories.append(folder)
        for path in sorted(folder.iterdir()):
            if time.monotonic() > deadline:
                raise ValueError("source inventory deadline exceeded")
            if path.name == "INDEX.md":
                continue
            if path.suffix == ".md":
                files.append(path)
            if len(files) > MAX_SOURCES:
                raise ValueError("source count exceeded")
    rows = []
    total = 0
    for path in files:
        raw, meta = records._snapshot(path)
        total += len(raw)
        if total > MAX_BYTES or time.monotonic() > deadline:
            raise ValueError("source read budget exceeded")
        rows.append({"path": str(path.relative_to(project)), **meta})
    return rows


def _check_sources(project, expected):
    if _sources(project) != expected:
        raise ValueError("preserved migration source changed")


def _current(project):
    marker_raw, marker_meta = records._snapshot(project / formats.MARKER_NAME)
    marker = _yaml(marker_raw)
    if (
        not isinstance(marker, dict)
        or type(marker.get("format_version")) is not int
        or marker["format_version"] != 2
        or marker.get("id") != project.name
    ):
        raise ValueError(
            "current project marker is unsupported or belongs to another project"
        )
    state_raw, state_meta = records._snapshot(project / formats.STATE_NAME)
    state = json.loads(state_raw, object_pairs_hook=records._unique)
    if (
        not isinstance(state, dict)
        or type(state.get("schema")) is not int
        or formats.validate_state(state)
    ):
        raise ValueError("current project state schema is invalid")
    index_raw, index_meta = records._snapshot(project / "sessions" / formats.INDEX_NAME)
    if index_raw.decode() != formats._sessions_index(project):
        raise ValueError(
            "current sessions index is stale; use its existing refresh owner"
        )
    return [
        {"path": path, "identity": meta}
        for path, meta in [
            (formats.MARKER_NAME, marker_meta),
            (formats.STATE_NAME, state_meta),
            ("sessions/" + formats.INDEX_NAME, index_meta),
        ]
    ]


def _project_proposal(project, name, stamp):
    detected = formats.detect(project)
    if detected not in ("v1", "v2"):
        raise ValueError(
            "partial and unknown formats require an explicit supported migration"
        )
    action = "create-v2" if detected == "v1" else "verify-current"
    sources = _sources(project)
    if action == "verify-current":
        rows = _current(project)
    else:
        marker = formats.build_marker(name, 1)
        marker["migrated_at"] = stamp.isoformat()
        state = formats.build_state_skeleton(project)
        state["updated_at"] = stamp.isoformat()
        output = [
            (formats.MARKER_NAME, yaml.safe_dump(marker, sort_keys=False)),
            (
                formats.STATE_NAME,
                json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            ),
            ("sessions/" + formats.INDEX_NAME, formats._sessions_index(project)),
        ]
        rows = []
        for relative, text in output:
            path = records._path(project / relative, project)
            if path.exists():
                raise ValueError("additive destination already exists")
            rows.append(
                {
                    "path": relative,
                    "text": text,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "mode": 0o600,
                }
            )
    _check_sources(project, sources)
    return {
        "id": name,
        "path": str(project),
        "identity": [project.stat().st_dev, project.stat().st_ino],
        "from_format": 1 if action == "create-v2" else 2,
        "action": action,
        "source": sources,
        "outputs": rows,
    }


def propose(index, selected, *, target_format, now=None):
    if (
        type(target_format) is not int
        or target_format != formats.CURRENT_FORMAT
        or target_format != 2
    ):
        raise ValueError("only the implemented explicit v1-to-v2 format is available")
    selected = _selection(selected)
    index = records._path(index)
    index_meta, paths = _resolve(index, selected)
    stamp = _time(now)
    projects = []
    for name, project in zip(selected, paths):
        with records.managed(project):
            projects.append(_project_proposal(project, name, stamp))
    if not records._matches(index, index_meta):
        raise ValueError("registry changed during preview")
    plan = {
        "schema": 1,
        "operation": "project-format-migration",
        "index": str(index),
        "index_identity": index_meta,
        "selected": selected,
        "target_format": 2,
        "created_at": stamp.isoformat(),
        "expires_at": (stamp + timedelta(seconds=PLAN_SECONDS)).isoformat(),
        "projects": projects,
        "effect_boundary": "one cooperative project transaction at a time",
        "source_preserved": True,
        "authorization_granted": False,
        "native_acceptance": "UNVERIFIED",
    }
    if len(records._json(plan)) > records.MAX_MANIFEST_BYTES:
        raise ValueError("migration plan exceeds bounded request size")
    return {**plan, "digest": _digest(plan)}


def _fresh_consent(plan, now=None):
    if not _time(plan["created_at"]) <= _time(now) <= _time(plan["expires_at"]):
        raise ValueError("migration plan expired or from future")


def _validate(plan, approval=None, *, fresh=False, now=None):
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != 1
        or type(plan["schema"]) is not int
        or plan.get("operation") != "project-format-migration"
        or type(plan.get("target_format")) is not int
        or plan["target_format"] != 2
    ):
        raise ValueError("unknown migration plan")
    actual = _digest({k: v for k, v in plan.items() if k != "digest"})
    if actual != plan.get("digest") or (approval is not None and approval != actual):
        raise ValueError("exact migration preview consent required")
    if len(records._json(plan)) > records.MAX_MANIFEST_BYTES:
        raise ValueError("migration plan exceeds bound")
    if fresh:
        _fresh_consent(plan, now)
    selected = _selection(plan["selected"])
    if (
        len(plan["projects"]) != len(selected)
        or [p["id"] for p in plan["projects"]] != selected
    ):
        raise ValueError("selection differs from preview")
    if not records._matches(Path(plan["index"]), plan["index_identity"]):
        raise ValueError("exact registry changed")
    for item in plan["projects"]:
        project = records._path(item["path"])
        if (
            project.name != item["id"]
            or [project.stat().st_dev, project.stat().st_ino] != item["identity"]
        ):
            raise ValueError("project directory changed")
        _check_sources(project, item["source"])
    return plan


def _intent(plan, item):
    return _digest({"plan": plan["digest"], "project": item["id"]})[:32]


def _completed(plan, item):
    project = Path(item["path"])
    if item.get("action") == "verify-current":
        if _current(project) != item["outputs"]:
            raise ValueError("current-format records changed after preview")
        return True
    if item.get("action") != "create-v2":
        raise ValueError("unsupported migration action")
    intent = _intent(plan, item)
    store = project / records.STORE
    if not store.exists():
        return False
    history = records._history(store)
    expected = history["completed"].get(intent)
    if expected is None:
        return False
    root = store / "completed" / intent
    manifest, raw = records._read_json(root / "manifest.json")
    commit, _ = records._read_json(root / "commit.json")
    if (
        records._digest(raw) != expected
        or commit != {"manifest_sha256": expected}
        or manifest.get("project") != str(project)
        or manifest.get("id") != intent
    ):
        raise ValueError("migration transaction custody differs")
    records._check_custody(project, root, manifest)
    if [
        {"path": x["path"], **x["before"]} for x in manifest.get("sources", [])
    ] != item["source"]:
        raise ValueError("migration source custody differs from reviewed inputs")
    rows = manifest.get("files", [])
    if len(rows) != len(item["outputs"]):
        raise ValueError("migration receipt target count differs")
    for saved, output in zip(rows, item["outputs"]):
        if (
            saved.get("path") != output["path"]
            or saved.get("before") is not None
            or saved.get("after", {}).get("sha256") != output["sha256"]
            or not records._matches(project / output["path"], saved["after"])
        ):
            raise ValueError(
                "migration final output or inode differs from original receipt"
            )
    return True


def _fresh_item(plan, item):
    # Derive output bytes again through the canonical existing format builders.
    derived = _project_proposal(
        Path(item["path"]), item["id"], _time(plan["created_at"])
    )
    if derived != item:
        raise ValueError("migration implementation or inputs changed")


def _record_apply(plan, item, board, native_payload, *, dry_run):
    requests = [
        {"file": o["path"], "create": {"text": o["text"], "mode": o["mode"]}}
        for o in item["outputs"]
    ]
    return records.apply(
        Path(item["path"]),
        requests,
        board=board,
        native_payload=native_payload,
        dry_run=dry_run,
        intent_id=_intent(plan, item),
        source_custody=[
            {
                "file": row["path"],
                "expected": {k: v for k, v in row.items() if k != "path"},
            }
            for row in item["source"]
        ],
    )


def apply(
    plan,
    *,
    approval_digest,
    board,
    native_payload,
    dry_run=False,
    now=None,
    selected_project=None,
):
    # Verified completed intents remain inspectable after consent expires.
    # Every not-yet-started project must independently admit fresh consent.
    _validate(plan, approval_digest)
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be boolean")
    if selected_project is not None and selected_project not in plan["selected"]:
        raise ValueError("execution selector is not in the approved project set")
    selected = [
        item
        for item in plan["projects"]
        if selected_project is None or item["id"] == selected_project
    ]
    outcomes = []
    # Preflight every selected target before the first target mutation. Later
    # outside changes can still leave an explicit, resumable partial set.
    for item in selected:
        project = Path(item["path"])
        with records.managed(project, exclusive=True):
            if not _completed(plan, item):
                _fresh_consent(plan, now)
                _fresh_item(plan, item)
                # Check genuine native authority for the complete requested
                # execution subset before performing its first effect.
                _record_apply(plan, item, board, native_payload, dry_run=True)
    for item in selected:
        project = Path(item["path"])
        with records.managed(project, exclusive=True):
            _check_sources(project, item["source"])
            if _completed(plan, item):
                outcomes.append(
                    {
                        "id": item["id"],
                        "status": "already-current"
                        if item["action"] == "verify-current"
                        else "already-committed",
                    }
                )
                continue
            _fresh_item(plan, item)
            # The whole-set preflight, lock wait and previous project may all
            # consume the remaining lifetime. Do not start the next owner
            # transaction on the strength of the earlier time check.
            _fresh_consent(plan, now)
            result = _record_apply(plan, item, board, native_payload, dry_run=dry_run)
            outcomes.append({"id": item["id"], **result})
    status = (
        "dry-run"
        if dry_run
        else "already-current"
        if all(r["status"] == "already-current" for r in outcomes)
        else "already-committed"
        if all(r["status"] == "already-committed" for r in outcomes)
        else "committed"
    )
    pending = [item["id"] for item in plan["projects"] if item not in selected]
    return {
        "status": "partial" if pending else status,
        "pending_projects": pending,
        "projects": outcomes,
        "native_acceptance": "UNVERIFIED",
        "source_preserved": True,
    }


def recover(plan, *, approval_digest, board, native_payload, selected_project=None):
    # Expiry blocks new effects, not completion of the exact durable commit.
    _validate(plan, approval_digest)
    if selected_project is not None and selected_project not in plan["selected"]:
        raise ValueError("recovery selector is not in the approved project set")
    selected = [
        item
        for item in plan["projects"]
        if selected_project is None or item["id"] == selected_project
    ]
    out = []
    for item in selected:
        project = Path(item["path"])
        with records._lock(project, exclusive=True):
            active = project / records.STORE / "active"
            if active.exists():
                manifest, _ = records._manifest(active, project)
                if manifest["id"] != _intent(plan, item):
                    raise ValueError("foreign pending transaction")
                out.append(
                    {
                        "id": item["id"],
                        **records.recover(
                            project, board=board, native_payload=native_payload
                        ),
                    }
                )
            elif _completed(plan, item):
                out.append({"id": item["id"], "status": "already-committed"})
            else:
                out.append({"id": item["id"], "status": "not-started"})
    return {
        "status": "committed"
        if len(selected) == len(plan["projects"])
        and all(r["status"] in ("committed", "already-committed") for r in out)
        else "incomplete",
        "projects": out,
        "pending_projects": [
            item["id"] for item in plan["projects"] if item not in selected
        ],
        "new_migrations_authorized": False,
    }


def verify(plan):
    _validate(plan)
    for item in plan["projects"]:
        with records.managed(Path(item["path"])):
            if not _completed(plan, item):
                raise ValueError("migration has no verified completed owner receipt")
    return {
        "status": "verified-derived-format",
        "native_acceptance": "UNVERIFIED",
        "source_preserved": True,
    }
