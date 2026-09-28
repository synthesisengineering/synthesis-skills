"""Declared machine review and exact repair through existing lifecycle owners.

Inventory is scope, never repair authority. Runtime mutation and recovery remain
with runtime_payload/EnrollmentJournal. Reports do not attest unlisted resources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone, timedelta

from system_contract import ContractError, SystemState as SystemState
from enrollment import engine_lock
import runtime_payload as runtime
from onboard import Receipts

LIFECYCLE = Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts"
PM = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
for _folder in (LIFECYCLE, PM):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))
import record_transaction as records  # noqa: E402 - sibling owner path

MAX_MEMBERS = 512
MAX_PROJECTS = 256
READ_SECONDS = 30
PLAN_SECONDS = 3600


def digest(value):
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def clone(value):
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode()
    if len(raw) > records.MAX_MANIFEST_BYTES:
        raise ContractError("declaration exceeds the manifest bound")
    return json.loads(raw)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value
    ):
        raise ContractError("bounded explicit identifier required")
    return value


def utc(value=None):
    now = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value)
    if now.tzinfo is None:
        raise ContractError("timezone-bearing time required")
    return now.astimezone(timezone.utc)


def read(path, *, missing=False):
    path = records._path(path)
    try:
        return records._snapshot(path)
    except FileNotFoundError:
        if missing:
            return None, None
        raise


def declaration(value):
    value = clone(value)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "components", "registries"}
        or type(value["schema"]) is not int
        or value["schema"] != 1
    ):
        raise ContractError("unknown declared machine inventory schema")
    if not all(isinstance(value[k], list) for k in ("components", "registries")):
        raise ContractError("declared inventories must be lists")
    if not 1 <= len(value["components"]) + len(value["registries"]) <= MAX_MEMBERS:
        raise ContractError("declared member count exceeds bound")
    ids = set()
    for row in value["components"] + value["registries"]:
        if not isinstance(row, dict):
            raise ContractError("inventory row must be an object")
        key = identifier(row.get("id"))
        if key in ids:
            raise ContractError("duplicate declared identity")
        ids.add(key)
    for row in value["registries"]:
        if set(row) != {"id", "path"}:
            raise ContractError("registry declares exact id and path")
        absolute(row["path"])
    return value


def absolute(value):
    if (
        not isinstance(value, str)
        or not Path(value).is_absolute()
        or str(Path(value)) != value
        or ".." in Path(value).parts
    ):
        raise ContractError("canonical absolute declared path required")
    return records._path(Path(value))


def json_read(path, *, missing=False):
    raw, meta = read(path, missing=missing)
    if raw is None:
        return None, meta
    if len(raw) > records.MAX_MANIFEST_BYTES:
        raise ContractError("JSON evidence exceeds bound")
    return json.loads(raw, object_pairs_hook=records._unique), meta


def project_ids(raw):
    import yaml

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
    value = yaml.load(raw, Loader=Strict)
    rows = (
        value.get("projects")
        if isinstance(value, dict)
        else value
        if isinstance(value, list)
        else None
    )
    if not isinstance(rows, list) or len(rows) > MAX_PROJECTS:
        raise ContractError("bounded project registry list required")
    ids = [
        identifier(row.get("id")) if isinstance(row, dict) else identifier(None)
        for row in rows
    ]
    if len(set(ids)) != len(ids):
        raise ContractError("duplicate registry project")
    return ids


def review(state, inventory, *, source_root, now=None):
    inv = declaration(inventory)
    deadline = time.monotonic() + READ_SECONDS
    results = []
    observed = []
    # Inspect saved planes without calling doctor/convergence/recovery or any writer.
    for row in inv["components"]:
        result = {
            "id": row["id"],
            "kind": row.get("kind"),
            "status": "UNKNOWN",
            "repair_authorized": False,
        }
        try:
            if time.monotonic() > deadline:
                raise ContractError("review time budget exhausted; member unscanned")
            if row.get("kind") == "runtime":
                if (
                    set(row) != {"id", "kind", "component"}
                    or row["component"] not in runtime.COMPONENTS
                ):
                    raise ContractError("unsupported runtime component declaration")
                entries = runtime.inventory(
                    source_root, state.home, state.state_dir, {row["component"]}
                )
                members = []
                for entry in entries:
                    raw, meta = read(entry.target, missing=True)
                    observed.append((entry.target, meta))
                    exact = (
                        meta is not None
                        and (meta["sha256"], meta["mode"]) == entry.fingerprint
                    )
                    members.append(
                        {
                            "path": str(entry.target),
                            "status": "CURRENT"
                            if exact
                            else "MISSING"
                            if meta is None
                            else "DRIFT",
                            "source_relative": entry.source_relative,
                            "expected_sha256": entry.fingerprint[0],
                            "observed_sha256": meta["sha256"] if meta else None,
                        }
                    )
                result.update(
                    members=members,
                    status="CURRENT"
                    if all(m["status"] == "CURRENT" for m in members)
                    else "DRIFT",
                )
            elif row.get("kind") == "service":
                if set(row) != {"id", "kind", "component"} or row["component"] != "console":
                    raise ContractError("service inventory requires exact Console owner")
                ownership = runtime.platform_ownership(state.home, state.state_dir)
                result.update(ownership=ownership, status="UNKNOWN")
                if not ownership["runtime_supported"]:
                    result.update(status="UNSUPPORTED", detail=ownership["service_requires"])
                else:
                    unit = absolute(ownership["console_unit"])
                    receipt = absolute(ownership["console_receipt"])
                    raw_unit, unit_meta = read(unit, missing=True)
                    saved, receipt_meta = json_read(receipt, missing=True)
                    observed.extend(((unit, unit_meta), (receipt, receipt_meta)))
                    if unit_meta is None and receipt_meta is None:
                        result.update(status="ABSENT", detail="No declared Console unit or ownership receipt; no service state was probed.")
                    elif (unit_meta is None or receipt_meta is None or not isinstance(saved, dict)
                          or set(saved) != {"schema_version", "target", "sha256", "mode"}
                          or type(saved["schema_version"]) is not int or saved["schema_version"] != 2
                          or saved["target"] != str(unit) or saved["sha256"] != unit_meta["sha256"]
                          or type(saved["mode"]) is not int or saved["mode"] != unit_meta["mode"]
                          or receipt_meta["mode"] != 0o600):
                        raise ContractError("Console service ownership is missing or differs; preserve it for the Console owner")
                    else:
                        result.update(status="OBSERVED", detail="Exact Console-owned unit bytes observed. Running/stopped state is UNKNOWN until the Console service owner queries the user manager.")
            elif row.get("kind") == "installation":
                if set(row) != {"id", "kind"}:
                    raise ContractError(
                        "installation declares only its ID and owner kind"
                    )
                for saved in (state.desired_path, state.observation_path):
                    _, meta = read(saved)
                    observed.append((saved, meta))
                desired = state.read_desired()
                observation = state.read_observation()
                committed = [
                    t
                    for t in observation["transactions"]
                    if t.get("state") == "committed"
                ]
                latest = committed[-1] if committed else {}
                planes = {
                    "desired": desired,
                    "resolved": latest.get("resolved"),
                    "installed": latest.get("installed"),
                    "source-provenance": latest.get("source-provenance"),
                    "live-loaded": latest.get("live-loaded"),
                    "outcome-verified": latest.get("outcome-verified"),
                }
                result.update(
                    status="OBSERVED",
                    saved_planes=planes,
                    live_claim="UNVERIFIED_SAVED_EVIDENCE",
                    detail="Saved lifecycle evidence is observed; this read-only review does not execute native or provider probes.",
                )
            elif row.get("kind") == "file":
                if set(row) != {"id", "kind", "path", "sha256"}:
                    raise ContractError(
                        "file declaration needs exact path and expected hash or null"
                    )
                expected = row["sha256"]
                if expected is not None and (
                    not isinstance(expected, str)
                    or not re.fullmatch("[a-f0-9]{64}", expected)
                ):
                    raise ContractError("invalid declared hash")
                path = absolute(row["path"])
                raw, meta = read(path, missing=True)
                observed.append((path, meta))
                result.update(
                    path=str(path),
                    sha256=meta["sha256"] if meta else None,
                    status="MISSING"
                    if meta is None
                    else "OBSERVED"
                    if expected is None
                    else "CURRENT"
                    if meta["sha256"] == expected
                    else "DRIFT",
                )
            else:
                result["detail"] = (
                    "unsupported component; declared member was not scanned"
                )
        except (OSError, ValueError, RuntimeError) as exc:
            result.update(status="UNKNOWN", detail=str(exc))
        results.append(result)
    import project_state
    import project_format

    for registry in inv["registries"]:
        row = {
            "id": registry["id"],
            "kind": "project-registry",
            "status": "UNKNOWN",
            "projects": [],
            "repair_authorized": False,
        }
        try:
            index = absolute(registry["path"])
            import team_contract

            team_contract.require_registry(index)
            raw, meta = read(index)
            observed.append((index, meta))
            ids = project_ids(raw)
            for project_id in ids:
                member = {"id": project_id, "status": "UNKNOWN"}
                try:
                    if time.monotonic() > deadline:
                        raise ContractError(
                            "review time budget exhausted; project unscanned"
                        )
                    resolved = project_state.resolve_project(
                        project_id,
                        index,
                        fetch=False,
                        fast_forward_canonical=False,
                        refresh_coordination=False,
                    )
                    member["resolver_status"] = resolved.status
                    if not resolved.selected_path:
                        raise ContractError(
                            "resolver could not causally select the project"
                        )
                    project = Path(resolved.selected_path)
                    member.update(
                        path=str(project),
                        format=project_format.detect(project),
                        status="OBSERVED",
                    )
                except (OSError, ValueError, RuntimeError) as exc:
                    member["detail"] = str(exc)
                row["projects"].append(member)
            row["status"] = (
                "OBSERVED"
                if all(p["status"] == "OBSERVED" for p in row["projects"])
                else "UNKNOWN"
            )
        except (OSError, ValueError, RuntimeError) as exc:
            row["detail"] = str(exc)
        results.append(row)
    for path, meta in observed:
        try:
            _, after = read(path, missing=True)
            if after != meta:
                raise ContractError("declared source changed while observed")
        except (OSError, ValueError, RuntimeError) as exc:
            results.append(
                {
                    "id": "observation-race",
                    "kind": "read-set",
                    "status": "UNKNOWN",
                    "detail": str(exc),
                    "repair_authorized": False,
                }
            )
            break
    unknown = sum(r["status"] in {"UNKNOWN", "OBSERVED"} for r in results)
    return {
        "schema": 1,
        "coverage": "declared-only",
        "inventory_digest": digest(inv),
        "declared": len(inv["components"]) + len(inv["registries"]),
        "results": results,
        "health": "UNKNOWN"
        if unknown
        else "DRIFT"
        if any(r["status"] != "CURRENT" for r in results)
        else "CURRENT",
        "repair_authorized": False,
        "unlisted_resources": "UNSCANNED",
        "observed_at": utc(now).isoformat(),
    }


def _selected(inv, selected):
    if (
        not isinstance(selected, list)
        or not selected
        or len(selected) != len(set(selected))
    ):
        raise ContractError("explicit unique repair selection required")
    rows = {r["id"]: r for r in inv["components"]}
    if set(selected) - set(rows):
        raise ContractError("repair selection is not declared")
    components = set()
    for name in selected:
        row = rows[name]
        if (
            set(row) != {"id", "kind", "component"}
            or row["kind"] != "runtime"
            or row["component"] not in runtime.COMPONENTS
        ):
            raise ContractError(
                "only existing release-derived runtime components are repairable"
            )
        components.add(row["component"])
    return components


def _repair_inputs(state, inv, selected, source_root):
    components = _selected(inv, selected)
    path = state.state_dir / "receipts.json"
    json_read(path)
    receipts = Receipts(path)
    plan = runtime.plan(
        source_root, state.home, state.state_dir, components, receipts.data
    )
    owned = runtime._owned_records(receipts.data)
    for entry, before in zip(plan.entries, plan.before):
        if not runtime._owned(entry, owned.get(str(entry.target)), before):
            raise ContractError(
                "repair needs an exact prior runtime ownership receipt; released bytes alone grant no repair authority"
            )
    return receipts, plan


def repair_plan(state, inventory, selected, *, source_root, now=None):
    inv = declaration(inventory)
    receipts, plan = _repair_inputs(state, inv, selected, source_root)
    stamp = utc(now)
    value = {
        "schema": 1,
        "operation": "runtime-repair",
        "inventory_digest": digest(inv),
        "selected": sorted(selected),
        "home": str(state.home),
        "source_root": str(Path(source_root).absolute()),
        "created_at": stamp.isoformat(),
        "expires_at": (stamp + timedelta(seconds=PLAN_SECONDS)).isoformat(),
        "receipt_digest": plan.receipt_digest,
        "receipt_before": list(plan.receipt_before) if plan.receipt_before else None,
        "targets": [
            {
                "path": str(e.target),
                "component": e.component,
                "source_relative": e.source_relative,
                "source_commit": e.source_commit,
                "before": list(b) if b else None,
                "after_sha256": e.fingerprint[0],
                "mode": e.mode,
            }
            for e, b in zip(plan.entries, plan.before)
        ],
        "authorization_granted": False,
    }
    return {**value, "digest": digest(value)}


def _repair_fresh(plan, now=None):
    if not utc(plan["created_at"]) <= utc(now) <= utc(plan["expires_at"]):
        raise ContractError("repair plan expired or from the future")


def repair_apply(
    state, inventory, plan, *, approval_digest, source_root, dry_run=False, now=None
):
    plan = clone(plan)
    if (
        not isinstance(plan, dict)
        or plan.get("digest") != approval_digest
        or digest({k: v for k, v in plan.items() if k != "digest"}) != approval_digest
    ):
        raise ContractError("exact proposed plan consent required")
    _repair_fresh(plan, now)
    inv = declaration(inventory)
    with engine_lock(state.state_dir, read_only=dry_run):
        _repair_fresh(plan, now)
        derived = repair_plan(
            state,
            inv,
            plan["selected"],
            source_root=source_root,
            now=plan["created_at"],
        )
        if derived != plan:
            raise ContractError("repair inputs changed since exact preview")
        receipts, runtime_plan = _repair_inputs(
            state, inv, plan["selected"], source_root
        )
        # Waiting and exact-input derivation consume time. Admit a new owner
        # operation only while this consent is still fresh under its lock.
        _repair_fresh(plan, now)
        if dry_run:
            return {"status": "dry-run", "changed": False, "digest": approval_digest}
        result = runtime.apply(runtime_plan, receipts)
        return {
            "status": "committed",
            "changed": bool(result["changed"]),
            "owner": "runtime_payload",
            "journal": result["journal"],
            "digest": approval_digest,
        }


def repair_recover(state, *, approve_recovery=False):
    if approve_recovery is not True:
        raise ContractError("explicit repair recovery required")
    return {
        "owner": "runtime_payload",
        "recovered": runtime.recover(state.home, state.state_dir),
        "new_repairs_authorized": False,
    }
