"""Versioned report-only campaigns on the existing native receipt owner.

A notice selection is not acknowledgement, a report is not verified completion,
and neither grants permission to execute a campaign action. No scheduler exists.
"""

from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

CONFORMANCE = (
    Path(__file__).resolve().parents[2] / "synthesis-agent-conformance/scripts"
)
LIFECYCLE = Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle/scripts"
for folder in (CONFORMANCE, LIFECYCLE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
import record_transaction as records  # noqa: E402 - sibling owner path

MAX_CAMPAIGNS = 64
MAX_CATALOG_BYTES = 128 * 1024
MAX_NOTICE_BYTES = 4096
ACTIONS = {"refresh-and-report", "review-machine", "review-project-migration"}
CLIENTS = {"codex", "claude", "muse"}
UNAVAILABLE_NOTICE = (
    "Campaign review is unavailable; campaign selection and reporting remain "
    "refused. Inspect the campaign catalog and native receipt. This notice does "
    "not authorize campaign actions or establish acknowledgement/completion."
)


def _now(value=None):
    stamp = (
        datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value)
    )
    if stamp.tzinfo is None:
        raise ValueError("campaign timestamps require timezones")
    return stamp.astimezone(timezone.utc)


def _digest(value):
    return hashlib.sha256(records._json(value)).hexdigest()


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})", value
    ):
        raise ValueError("exact release X.Y.Z required")
    return tuple(map(int, value.split(".")))


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch("[a-z][a-z0-9-]{0,79}", value):
        raise ValueError("bounded campaign/project identifier required")
    return value


def catalog(state):
    path = state.config_dir / "campaigns.json"
    try:
        raw, _ = records._snapshot(path)
    except FileNotFoundError:
        return None
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("campaign catalog exceeds byte bound")
    data = json.loads(raw, object_pairs_hook=records._unique)
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "campaigns"}
        or type(data["schema"]) is not int
        or data["schema"] != 1
        or not isinstance(data["campaigns"], list)
        or len(data["campaigns"]) > MAX_CAMPAIGNS
    ):
        raise ValueError("invalid bounded campaign catalog")
    ids = set()
    required = {
        "id",
        "version",
        "not_before",
        "expires_at",
        "clients",
        "minimum_release",
        "maximum_release",
        "projects",
        "notice",
        "action",
        "mode",
    }
    for row in data["campaigns"]:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("unknown campaign fields")
        key = _identifier(row["id"])
        if key in ids:
            raise ValueError(
                "ambiguous campaign versions; one declared active version per ID required"
            )
        ids.add(key)
        if type(row["version"]) is not int or not 1 <= row["version"] <= 1000000:
            raise ValueError("positive bounded campaign version required")
        if row["mode"] != "report-only" or row["action"] not in ACTIONS:
            raise ValueError("campaign cannot grant execution authority")
        if (
            not isinstance(row["clients"], list)
            or not row["clients"]
            or any(c not in CLIENTS for c in row["clients"])
            or len(row["clients"]) != len(set(row["clients"]))
        ):
            raise ValueError("declared native clients required")
        if (
            not isinstance(row["projects"], list)
            or len(row["projects"]) > 128
            or len(row["projects"]) != len(set(row["projects"]))
        ):
            raise ValueError("bounded unique project applicability required")
        for project in row["projects"]:
            _identifier(project)
        if _now(row["expires_at"]) <= _now(row["not_before"]):
            raise ValueError("campaign expiry precedes applicability")
        if _version(row["maximum_release"]) <= _version(row["minimum_release"]):
            raise ValueError("empty release applicability range")
        if (
            not isinstance(row["notice"], str)
            or not row["notice"].strip()
            or len(row["notice"].encode()) > 1024
            or any(ord(c) < 32 and c not in "\n\t" for c in row["notice"])
        ):
            raise ValueError("bounded readable campaign notice required")
    return data


def applicability(state, *, client, release, project=None, now=None):
    data = catalog(state)
    stamp = _now(now)
    rows = []
    if client not in CLIENTS:
        raise ValueError("unsupported native client")
    for row in (data or {}).get("campaigns", []):
        status = "applicable"
        if stamp < _now(row["not_before"]):
            status = "not-yet-applicable"
        elif stamp >= _now(row["expires_at"]):
            status = "expired"
        elif client not in row["clients"]:
            status = "other-client"
        elif row["projects"] and project is None:
            status = "unknown-project"
        elif row["projects"] and project not in row["projects"]:
            status = "other-project"
        else:
            try:
                version = _version(release)
            except ValueError:
                status = "unknown-release"
            else:
                if (
                    not _version(row["minimum_release"])
                    <= version
                    < _version(row["maximum_release"])
                ):
                    status = "other-release"
        rows.append(
            {
                "id": row["id"],
                "version": row["version"],
                "digest": _digest(row),
                "status": status,
                "notice": row["notice"],
                "action": row["action"],
            }
        )
    return {
        "schema": 1,
        "catalog_digest": _digest(data) if data is not None else None,
        "campaigns": rows,
        "execution_authorized": False,
        "acknowledged": False,
        "observed_at": stamp.isoformat(),
        "idle_sessions": "NOT_NOTIFIED",
    }


def native_project(state, payload):
    """Observe a project only through the existing exact native seat owner."""
    pm = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
    if str(pm) not in sys.path:
        sys.path.insert(0, str(pm))
    import run_admission

    board = records._path(
        Path(
            os.environ.get(
                "SYNTHESIS_COORDINATION_BOARD",
                str(state.home / ".synthesis/coordination/active-sessions.md"),
            )
        )
    )
    if not board.exists():
        return None
    try:
        bound = run_admission.native_binding(board, payload, readonly=True)
        return bound["project_id"]
    except (OSError, ValueError, RuntimeError):
        return None


def selection(state, receipt):
    if receipt.get("transcript_bound_at_record") is not True:
        return None
    project = native_project(state, receipt)
    result = applicability(
        state,
        client=receipt["client"],
        release=receipt.get("plugin_version"),
        project=project,
        now=receipt.get("recorded_at"),
    )
    result["native_project"] = project
    return result if result["catalog_digest"] is not None else None


def notice(state, payload, latest):
    """Read only an exact genuine event. No probe records acknowledgement."""
    import session_context as context

    session = payload.get("session_id")
    if not isinstance(session, str):
        return ""
    provenance = context.client_provenance(payload, session)
    if provenance is None:
        return ""
    client = provenance[0]
    from live_receipt import session_receipt_path

    path = session_receipt_path(latest, client, session)
    if path is None:
        return ""
    receipt, _ = records._read_json(path)
    if receipt.get("transcript_bound_at_record") is not True:
        return ""
    if receipt.get("campaign_notice_error") is not None:
        return UNAVAILABLE_NOTICE
    selected = receipt.get("campaign_notices")
    if not selected:
        return ""
    try:
        current = applicability(
            state,
            client=client,
            release=receipt.get("plugin_version"),
            project=native_project(state, payload),
        )
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        # Rechecking an optional notice cannot erase the already observed hook.
        # The direct catalog/report owners still raise rather than accept it.
        return UNAVAILABLE_NOTICE
    current_rows = {(r["id"], r["version"]): r for r in current["campaigns"]}
    result = []
    used = 0
    omitted = 0
    for row in selected["campaigns"]:
        if (
            row["status"] != "applicable"
            or current_rows.get((row["id"], row["version"])) != row
        ):
            continue
        line = f"Campaign {row['id']} v{row['version']} (report-only): {row['notice']}"
        if used + len(line.encode()) > MAX_NOTICE_BYTES - 240:
            omitted += 1
            continue
        result.append(line)
        used += len(line.encode()) + 1
    if omitted:
        result.append(
            f"{omitted} additional notices exceed the hook message bound; inspect the campaign report."
        )
    if result:
        result.append(
            "Notices do not authorize actions or prove acknowledgement/completion. Report through synthesis campaign report when handled."
        )
    return "\n".join(result)


def _latest(state):
    return records._path(
        Path(
            os.environ.get(
                "SYNTHESIS_PUBLIC_SESSIONSTART_RECEIPT",
                str(
                    state.home
                    / ".synthesis/agent-conformance/live/public-sessionstart.json"
                ),
            )
        )
    )


def report(
    state, event_path, native_payload, *, campaign_id, campaign_version, outcome, detail
):
    import session_context as context

    if outcome not in (
        "acknowledged",
        "blocked",
        "reported-complete",
        "not-applicable",
    ):
        raise ValueError("explicit reported outcome required")
    if not isinstance(detail, str) or not detail.strip() or len(detail.encode()) > 4096:
        raise ValueError("bounded truthful report detail required")
    if type(campaign_version) is not int:
        raise ValueError("campaign version must be integer")
    event_path = records._path(event_path)
    receipt, raw = records._read_json(event_path)
    if (
        receipt.get("receipt_schema") != 2
        or receipt.get("hook_event_name") != "SessionStart"
        or receipt.get("transcript_bound_at_record") is not True
    ):
        raise ValueError("bound native event required")
    session = receipt.get("session_id")
    client = receipt.get("client")
    uuid.UUID(str(session))
    if (
        not isinstance(native_payload, dict)
        or native_payload.get("session_id") != session
        or context.client_provenance(native_payload, session)
        != (client, f"{client}-transcript")
    ):
        raise ValueError("report native identity does not match original event")
    if Path(str(native_payload.get("transcript_path", ""))) != Path(
        str(receipt.get("transcript_path", ""))
    ):
        raise ValueError("exact native transcript required")
    latest = _latest(state)
    expected = context.receipt_event_path(
        latest, client=client, session_id=session, event_id=receipt["receipt_event_id"]
    )
    if event_path != expected:
        raise ValueError("report requires the original native owner event path")
    selected = receipt.get("campaign_notices")
    current = applicability(
        state,
        client=client,
        release=receipt.get("plugin_version"),
        project=native_project(state, native_payload),
    )
    key = (_identifier(campaign_id), campaign_version)
    old = next(
        (
            r
            for r in (selected or {}).get("campaigns", [])
            if (r["id"], r["version"]) == key
        ),
        None,
    )
    new = next(
        (r for r in current["campaigns"] if (r["id"], r["version"]) == key), None
    )
    if old is None or new is None or old != new or new["status"] != "applicable":
        raise ValueError(
            "campaign changed, expired or was not applicable in this exact native event"
        )
    result = {
        "schema": 1,
        "native_event": str(event_path),
        "native_event_sha256": hashlib.sha256(raw).hexdigest(),
        "client": client,
        "session_id": session,
        "campaign_id": campaign_id,
        "campaign_version": campaign_version,
        "campaign_digest": new["digest"],
        "reported_outcome": outcome,
        "detail": detail,
        "verified_completion": False,
        "execution_authorized": False,
    }
    directory = records._path(event_path.parent / "campaign-reports")
    target = directory / (
        _digest({"event": receipt["receipt_event_id"], "campaign": new["digest"]})
        + ".json"
    )
    with context.receipt_registry_lock(latest):
        if records._read_json(event_path)[1] != raw:
            raise ValueError("native event changed during report")
        if not directory.exists():
            directory.mkdir(mode=0o700)
            records._sync_dir(directory.parent)
        records._path(directory)
        if target.exists():
            existing, _ = records._read_json(target)
            if existing != result:
                raise ValueError(
                    "conflicting report for exact native event/campaign; preserve original"
                )
            return existing
        records._new_file(target, records._json(result))
        records._sync_dir(directory)
    return result
