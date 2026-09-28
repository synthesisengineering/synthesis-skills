"""Five product journeys and consented studies inside the onboarding owner.

Journeys orchestrate the existing modular reconciler. They do not create a new
installer, registry, native trust grant, or outcome authority. Study receipts are
local attestations, never proof that a human observation happened.
"""

from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import time
import uuid

import modular
from first_run_store import Store, decode, digest, home_identity, read_file
from system_contract import (
    ContractError,
    default_desired_state,
    json_digest,
    verify_outcome,
)

# The existing release capability catalog owns journey selection. Keeping names
# as data also prevents modular executable-dependency discovery from staging
# every unselected journey merely because this dispatcher can route it.
_CATALOG = json.loads(
    (
        Path(__file__).resolve().parents[1] / "references/release-capabilities.json"
    ).read_text()
)["first_run"]
JOURNEYS = _CATALOG["journeys"]
AUDIENCES = _CATALOG["audiences"]
MAX_EVENTS = 200
STEPS = (
    "understand",
    "trust",
    "install",
    "first-value",
    "update",
    "recovery",
    "handoff",
)
EVENTS = (
    "started",
    "completed",
    "failure",
    "hesitation",
    "unexplained-term",
    "command-copied",
)
TERMS = (
    "profile",
    "skill",
    "plugin",
    "hook",
    "trust",
    "workspace",
    "repository",
    "checkpoint",
    "source",
    "doctor",
    "receipt",
    "handoff",
    "connector",
    "consent",
    "other",
)
COMMANDS = (
    "journey-catalog",
    "journey-plan",
    "journey-apply",
    "journey-status",
    "journey-verify",
    "doctor",
    "update",
    "repair",
    "checkpoint",
    "resume",
    "other",
)


def _now():
    return int(time.time())


def _hash(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ContractError(label + " is outside its integer bounds")
    return value


def catalog():
    return {
        "schema_version": 1,
        "default": "portable-project",
        "journeys": deepcopy(JOURNEYS),
        "audiences": dict(AUDIENCES),
        "profile_owner": "modular",
        "clients": ["claude", "codex"],
        "boundary": "Selected skills only. Native plugins, hooks, services, organization enrollment and provider access are separate choices. Other clients require a supported modular binding before this command may select them.",
    }


def _identity(state, clients):
    result = {
        "home": home_identity(state),
        "paths": [str(state.config_dir), str(state.state_dir), str(state.cache_dir)],
        "trust_inputs": {},
    }
    paths = []
    if "claude" in clients:
        paths += [state.home / ".claude/settings.json"]
    if "codex" in clients:
        paths += [state.home / ".codex/config.toml", state.home / ".codex/hooks.json"]
    for path in paths:
        # Missing is a distinct snapshot, never evidence of trust acceptance.
        try:
            data, inode = read_file(path)
            result["trust_inputs"][str(path)] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "identity": inode,
            }
        except ContractError:
            # A missing parent is allowed only when its entire existing ancestry
            # is regular. Links and unreadable paths remain refusals.
            modular._regular(path, allow_missing=True)
            if path.exists():
                raise
            result["trust_inputs"][str(path)] = None
    return result


def plan(
    state,
    source,
    journey="portable-project",
    clients=None,
    *,
    stage_core=True,
    ttl=3600,
):
    if not isinstance(journey, str) or journey not in JOURNEYS:
        raise ContractError("unknown first-run journey")
    if (
        not isinstance(clients, list)
        or not clients
        or any(not isinstance(c, str) or c not in {"claude", "codex"} for c in clients)
        or len(set(clients)) != len(clients)
    ):
        raise ContractError(
            "journey needs explicitly confirmed supported modular clients"
        )
    if type(stage_core) is not bool:
        raise ContractError("dormant core selection must be boolean")
    _integer(ttl, 1, 86400, "plan lifetime")
    clients = sorted(clients)
    resolved = modular.resolve_selection(
        source, list(JOURNEYS[journey]["roots"]), stage_core
    )
    identity = _identity(state, clients)
    with Store(state).locked() as store, state.locked():
        previous = state.read_desired()
        existing = bool(
            previous
            and previous.get("enabled", True)
            and previous["profile"] != "modular"
        )
        if existing and not set(clients) <= set(previous["clients"]):
            raise ContractError(
                "first-run reuse cannot enroll an additional client; use the installation owner"
            )
        admitted_at = _now()
        body = {
            "schema_version": 1,
            "kind": "journey",
            "id": uuid.uuid4().hex,
            "created_at": admitted_at,
            "expires_at": admitted_at + ttl,
            "journey": journey,
            "clients": clients,
            "stage_core": stage_core,
            "selection_mode": "existing" if existing else "modular",
            "identity": identity,
            "prior_desired_digest": json_digest(previous),
            "source": resolved["source"],
            "source_digest": resolved["source_digest"],
            "roots": resolved["roots"],
            "visible_skills": resolved["skills"],
            "support_skills": resolved["support_skills"],
            "required_bytes": sum(
                (source / name).stat().st_size for name in resolved["required_files"]
            ),
            "optional_core_bytes": sum(
                (source / name).stat().st_size
                for name in resolved["optional_core_files"]
            ),
            "release_policy": (previous or {}).get("release")
            or {"channel": "stable", "version_pin": None},
            "consent": None,
            "state": "planned",
            "transaction_id": None,
            "doctor": None,
            "first_value": None,
        }
        body["plan_digest"] = digest(_plan_fields(body))
        store.write(body)
    return _view(body)


def _plan_fields(body):
    return {
        k: v
        for k, v in body.items()
        if k
        not in {
            "plan_digest",
            "consent",
            "state",
            "transaction_id",
            "doctor",
            "first_value",
        }
    }


def _read_journey(store, record_id):
    body = store.read("journey", record_id)
    fields = {
        "schema_version",
        "kind",
        "id",
        "created_at",
        "expires_at",
        "journey",
        "clients",
        "stage_core",
        "selection_mode",
        "identity",
        "prior_desired_digest",
        "source",
        "source_digest",
        "roots",
        "visible_skills",
        "support_skills",
        "required_bytes",
        "optional_core_bytes",
        "release_policy",
        "consent",
        "state",
        "transaction_id",
        "doctor",
        "first_value",
        "plan_digest",
    }
    if (
        set(body) != fields
        or not isinstance(body["journey"], str)
        or not isinstance(body["state"], str)
    ):
        raise ContractError("journey record fields are invalid")
    if (
        body["selection_mode"] not in {"modular", "existing"}
        or type(body["stage_core"]) is not bool
        or not isinstance(body["clients"], list)
        or not body["clients"]
        or any(
            not isinstance(c, str) or c not in {"claude", "codex"}
            for c in body["clients"]
        )
        or len(body["clients"]) != len(set(body["clients"]))
    ):
        raise ContractError("journey selection schema is invalid")
    _integer(body["created_at"], 1, 2**53, "journey creation time")
    _integer(
        body["expires_at"],
        body["created_at"] + 1,
        body["created_at"] + 86400,
        "journey expiry",
    )
    for name in ("required_bytes", "optional_core_bytes"):
        _integer(body[name], 0, 2**53, name)
    if body["consent"] is not None and (
        not isinstance(body["consent"], dict)
        or set(body["consent"]) != {"plan_digest", "recorded_at"}
        or body["consent"]["plan_digest"] != body["plan_digest"]
    ):
        raise ContractError("journey consent receipt is invalid")
    if body["state"] != "planned" and body["consent"] is None:
        raise ContractError("journey lost its explicit consent receipt")
    if (
        body.get("journey") not in JOURNEYS
        or body.get("state") not in {"planned", "consented", "installed", "inspected"}
        or body.get("plan_digest") != digest(_plan_fields(body))
    ):
        raise ContractError("journey plan integrity failed")
    if body.get("roots") != sorted(JOURNEYS[body["journey"]]["roots"]):
        raise ContractError("journey roots no longer match the release catalog")
    return body


def _view(body):
    return {
        **deepcopy(body),
        "task": JOURNEYS[body["journey"]]["task"],
        "next_action": "Review selection and writes, then approve the exact plan digest."
        if body["state"] == "planned"
        else "Run the selected skills on one supplied task, save its useful artifact, then verify its exact bytes. Native load/trust and genuine handoff remain independently verified.",
        "write_scope": (
            ["owned first-run receipts", "existing doctor observation receipts"]
            if body["selection_mode"] == "existing"
            else [
                "owned modular payload cache",
                "selected client skill discovery links",
                "owned onboarding desired state, transaction and first-run receipts",
            ]
        ),
        "native_live_loading": "not-certified",
        "provider_calls": 0,
    }


def _validate_current(state, source, body, *, check_prior=True):
    if _identity(state, body["clients"]) != body["identity"]:
        raise ContractError(
            "journey machine or trust inputs changed; make a new reviewed plan"
        )
    resolved = modular.resolve_selection(source, body["roots"], body["stage_core"])
    if (
        resolved["source"] != body["source"]
        or resolved["source_digest"] != body["source_digest"]
    ):
        raise ContractError("journey source changed; make a new reviewed plan")
    if (
        check_prior
        and json_digest(state.read_desired()) != body["prior_desired_digest"]
    ):
        raise ContractError("journey desired selection changed; no effect admitted")
    return resolved


def _expected_desired(body):
    policy = body["release_policy"]
    return default_desired_state(
        "modular",
        body["clients"],
        policy["channel"],
        policy.get("version_pin"),
        modular={"roots": body["roots"], "stage_core": body["stage_core"]},
    )


def _committed(state, body):
    observed = state.read_observation()
    desired = state.read_desired()
    if body["selection_mode"] == "existing":
        if json_digest(desired) != body["prior_desired_digest"]:
            raise ContractError("existing journey desired selection changed")
        matches = [
            row
            for row in observed["transactions"]
            if row["state"] == "committed"
            and row["generation"] == observed["generation"]
        ]
        if (
            len(matches) != 1
            or matches[0].get(
                "committed_desired_digest", matches[0].get("desired_digest")
            )
            != body["prior_desired_digest"]
        ):
            raise ContractError(
                "existing selection has no exact current committed generation"
            )
        return matches[0]
    matches = [
        row
        for row in observed["transactions"]
        if (row.get("details") or {}).get("first_run")
        == {"id": body["id"], "plan_digest": body["plan_digest"]}
        and row["state"] == "committed"
    ]
    if len(matches) > 1:
        raise ContractError("journey has ambiguous committed effects")
    if not matches:
        return None
    row = matches[0]
    expected = _expected_desired(body)
    if desired != expected or row.get("desired_digest") != json_digest(expected):
        raise ContractError("journey committed selection is no longer current")
    if row["generation"] != observed["generation"]:
        raise ContractError("journey committed generation is no longer current")
    saved = modular.receipt(state)
    if (
        not saved
        or saved["source"] != body["source"]
        or saved["selection"] != expected["modular"]
    ):
        raise ContractError("journey committed source or selection drifted")
    return row


def _diagnose(state, body, *, engine_runner=None):
    if body["selection_mode"] == "modular":
        return modular.inspect(state)
    import synthesis_cli

    class BoundedCapture(io.StringIO):
        def __init__(self):
            super().__init__()
            self.bytes_written = 0

        def write(self, text):
            size = len(text.encode("utf-8"))
            if self.bytes_written + size > 512 * 1024:
                raise ContractError(
                    "existing doctor output exceeds the first-run receipt limit"
                )
            self.bytes_written += size
            return super().write(text)

    output = BoundedCapture()
    with redirect_stdout(output):
        code = synthesis_cli.main(
            ["doctor", "--json"], state=state, engine_runner=engine_runner
        )
    if len(output.getvalue().encode()) > 512 * 1024:
        raise ContractError(
            "existing doctor output exceeds the first-run receipt limit"
        )
    try:
        report = json.loads(output.getvalue())
    except ValueError as exc:
        raise ContractError(
            "existing doctor did not return a structured report"
        ) from exc
    if not isinstance(report, dict) or not isinstance(report.get("planes"), dict):
        raise ContractError("existing doctor report is incomplete")
    return {**report, "status": "PASS" if code == 0 else "FAIL"}


def _task_prerequisites(report):
    return all(
        report.get("planes", {}).get(plane, {}).get("status") == "verified"
        for plane in ("desired", "resolved", "installed", "source-provenance")
    )


def apply(state, source, record_id, consent, *, engine_runner=None):
    with Store(state).locked() as store:
        body = _read_journey(store, record_id)
        if consent != body["plan_digest"]:
            raise ContractError(
                "explicit consent must match the exact journey plan digest"
            )
        _validate_current(state, source, body, check_prior=False)
        if body["selection_mode"] == "existing":
            if body["consent"] is None and _now() >= body["expires_at"]:
                raise ContractError("journey plan expired before consent")
            with state.locked():
                _validate_current(state, source, body)
                committed = _committed(state, body)
            report = _diagnose(state, body, engine_runner=engine_runner)
            with state.locked():
                _validate_current(state, source, body)
                if (
                    _committed(state, body)["transaction_id"]
                    != committed["transaction_id"]
                ):
                    raise ContractError("existing generation changed during inspection")
                if (
                    body["consent"] is None
                    and not body["created_at"] <= _now() < body["expires_at"]
                ):
                    raise ContractError("journey consent expired during inspection")
                updated = {
                    **body,
                    "state": "inspected",
                    "transaction_id": committed["transaction_id"],
                    "consent": body["consent"]
                    or {"plan_digest": consent, "recorded_at": _now()},
                    "doctor": {
                        "checked_at": _now(),
                        "report": report,
                        "sha256": digest(report),
                    },
                }
                store.write(updated, expected=body)
            return _view(updated)
        with state.locked():
            pending = [
                row
                for row in state.read_observation()["transactions"]
                if row["state"] == "pending"
            ]
            own = {"id": body["id"], "plan_digest": body["plan_digest"]}
            if any(
                (row.get("details") or {}).get("first_run") != own for row in pending
            ):
                raise ContractError(
                    "another onboarding transaction needs its own recovery owner"
                )
            if pending:
                modular.recover(state)
            committed = _committed(state, body)
        if committed is None:
            if not body["created_at"] <= _now() < body["expires_at"]:
                raise ContractError(
                    "journey consent plan expired before effect admission"
                )
            _validate_current(state, source, body)
            if body["consent"] is None:
                updated = {
                    **body,
                    "consent": {"plan_digest": consent, "recorded_at": _now()},
                    "state": "consented",
                }
                store.write(updated, expected=body)
                body = updated

            def preflight():
                if not body["created_at"] <= _now() < body["expires_at"]:
                    raise ContractError(
                        "journey consent expired while waiting for the installer"
                    )
                _validate_current(state, source, body)
                if not body["created_at"] <= _now() < body["expires_at"]:
                    raise ContractError(
                        "journey consent expired during source verification"
                    )

            modular.setup(
                state,
                source,
                body["roots"],
                body["clients"],
                body["stage_core"],
                release=body["release_policy"],
                preflight=preflight,
                first_run={"id": record_id, "plan_digest": body["plan_digest"]},
            )
        with state.locked():
            _validate_current(state, source, body, check_prior=False)
            committed = _committed(state, body)
            if committed is None:
                raise ContractError(
                    "journey installation has no matching committed receipt"
                )
            doctor = modular.inspect(state)
            if doctor["status"] != "PASS":
                raise ContractError(
                    "journey installation diagnostic failed; effects retained for repair"
                )
            updated = {
                **body,
                "state": "installed",
                "transaction_id": committed["transaction_id"],
                "doctor": {
                    "checked_at": _now(),
                    "report": doctor,
                    "sha256": digest(doctor),
                },
            }
            store.write(updated, expected=body)
        return _view(updated)


def verify_first_value(
    state,
    source,
    record_id,
    artifact,
    expected_sha256,
    confirmed_useful,
    *,
    engine_runner=None,
):
    if confirmed_useful is not True:
        raise ContractError(
            "first value requires the user to confirm this artifact is useful"
        )
    with Store(state).locked() as store:
        body = _read_journey(store, record_id)
        if body["state"] not in {"installed", "inspected"}:
            raise ContractError("journey installation is not committed or inspected")
        doctor = _diagnose(state, body, engine_runner=engine_runner)
        with state.locked():
            _validate_current(state, source, body, check_prior=False)
            if _committed(state, body) is None:
                raise ContractError("journey installation receipt is absent")
            if not _task_prerequisites(doctor):
                raise ContractError(
                    "journey source/installation diagnostic failed; do not certify first value"
                )
            receipt = verify_outcome(
                "first-use-artifact-check",
                {
                    "source_class": "local-user-artifact",
                    "artifact": str(artifact),
                    "sha256": expected_sha256,
                },
                source,
            )
            receipt.update(
                journey=body["journey"],
                plan_digest=body["plan_digest"],
                transaction_id=body["transaction_id"],
                usefulness="user-attested",
                quality="not-independently-evaluated",
                native_loading="not-certified",
            )
            if body["first_value"] is not None:
                previous = {
                    k: v for k, v in body["first_value"].items() if k != "verified_at"
                }
                current = {k: v for k, v in receipt.items() if k != "verified_at"}
                if previous != current:
                    raise ContractError(
                        "first value already binds another artifact; receipt preserved"
                    )
                return deepcopy(body["first_value"])
            updated = {
                **body,
                "first_value": receipt,
                "doctor": {
                    "checked_at": _now(),
                    "report": doctor,
                    "sha256": digest(doctor),
                },
            }
            store.write(updated, expected=body)
        # Local custody never promotes the separate live-loaded/outcome planes.
        return receipt


def status(state, source, record_id, *, engine_runner=None):
    with Store(state).locked() as store:
        body = _read_journey(store, record_id)
        result = _view(body)
        try:
            _validate_current(
                state, source, body, check_prior=body["state"] == "planned"
            )
            if body["state"] in {"installed", "inspected"}:
                if _committed(state, body) is None:
                    raise ContractError("committed journey receipt is absent")
                result["current_doctor"] = _diagnose(
                    state, body, engine_runner=engine_runner
                )
                if not _task_prerequisites(result["current_doctor"]):
                    raise ContractError("current installation diagnostic failed")
            if body["first_value"]:
                value = body["first_value"]
                verify_outcome(
                    "first-use-artifact-check",
                    {
                        "source_class": "local-user-artifact",
                        "artifact": value["artifact"],
                        "sha256": value["artifact_sha256"],
                    },
                    source,
                )
            result["status"] = "CURRENT"
        except ContractError as exc:
            result.update(status="STALE", reason=str(exc))
        return result


def study_protocol():
    body = {
        "schema_version": 1,
        "name": "local-onboarding-study",
        "version": 1,
        "audiences": dict(AUDIENCES),
        "journeys": list(JOURNEYS),
        "steps": list(STEPS),
        "required_cohorts": ["technical Mac user", "nondeveloper AI power user"],
        "additional_platforms": "Linux/WSL only under the actual supported contract; native Windows remains unsupported.",
        "fields": [
            "pseudonymous random record ID",
            "audience and journey",
            "synthetic or participant",
            "consent digest and time",
            "bounded structured observations",
            "local witness digest",
            "retention deadline",
        ],
        "excluded": [
            "names",
            "email",
            "raw commands",
            "paths",
            "prompts",
            "project content",
            "credentials",
            "audio",
            "screenshots",
            "telemetry",
        ],
        "max_events": MAX_EVENTS,
        "max_retention_days": 30,
        "events": list(EVENTS),
        "terms": list(TERMS),
        "commands": list(COMMANDS),
        "measurement": "Record time to understanding and useful artifact, every copied command as a digest, unexplained terms, permission/trust hesitation, update/failure recovery and uncoached client handoff. Do not infer any result from installation alone.",
        "provenance": "Direct observations and participant reports are labeled attestations bound to an operator-retained local witness digest; this recorder cannot prove a participant exists or that consent was actually obtained.",
        "consent": "Approve the exact single-use study plan digest, including sample, audience, journey, retention, machine identity and expiry; a protocol digest alone grants no capture authority.",
        "withdrawal": "Immediately replace captured observations with a withdrawal tombstone. External original witnesses remain under their separate owner and consent. Expiry stops capture and hides observations; explicit retention cleanup replaces them with an expiry tombstone.",
        "transmission": "none; no scheduler, provider, network or automatic capture",
    }
    return {**body, "digest": digest(body)}


def _study_identity(state):
    # Bind the exact local receipt owner without retaining a user's pathname.
    return {
        **{k: v for k, v in home_identity(state).items() if k != "path"},
        "state_root_sha256": hashlib.sha256(str(state.state_dir).encode()).hexdigest(),
    }


def study_plan(state, kind, audience, journey, retention_days, *, ttl=3600):
    if (
        not all(isinstance(v, str) for v in (kind, audience, journey))
        or kind not in {"synthetic", "participant"}
        or audience not in AUDIENCES
        or journey not in JOURNEYS
    ):
        raise ContractError("study selection is invalid")
    _integer(retention_days, 1, 30, "retention days")
    _integer(ttl, 1, 3600, "study consent plan lifetime")
    now = _now()
    body = {
        "schema_version": 1,
        "kind": "study-consent-plan",
        "id": uuid.uuid4().hex,
        "sample": kind,
        "audience": audience,
        "journey": journey,
        "retention_days": retention_days,
        "created_at": now,
        "expires_at": now + ttl,
        "protocol_digest": study_protocol()["digest"],
        "identity": _study_identity(state),
    }
    return {**body, "digest": digest(body)}


def _validate_study_plan(state, plan, *, fresh=True, current_protocol=True):
    from first_run_store import IDENTIFIER

    fields = {
        "schema_version",
        "kind",
        "id",
        "sample",
        "audience",
        "journey",
        "retention_days",
        "created_at",
        "expires_at",
        "protocol_digest",
        "identity",
        "digest",
    }
    if (
        not isinstance(plan, dict)
        or set(plan) != fields
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
    ):
        raise ContractError("study consent requires an exact selected plan")
    if (
        plan["kind"] != "study-consent-plan"
        or not isinstance(plan["id"], str)
        or not IDENTIFIER.fullmatch(plan["id"])
        or not all(isinstance(plan[k], str) for k in ("sample", "audience", "journey"))
        or plan["sample"] not in {"synthetic", "participant"}
        or plan["audience"] not in AUDIENCES
        or plan["journey"] not in JOURNEYS
    ):
        raise ContractError("study consent selection is invalid")
    _integer(plan["retention_days"], 1, 30, "consented retention days")
    _integer(plan["created_at"], 1, 2**53, "consent plan creation time")
    _integer(
        plan["expires_at"],
        plan["created_at"] + 1,
        plan["created_at"] + 3600,
        "consent plan expiry",
    )
    if plan["digest"] != digest({k: v for k, v in plan.items() if k != "digest"}):
        raise ContractError("study consent plan changed")
    if plan["identity"] != _study_identity(state):
        raise ContractError("study consent machine identity changed")
    if current_protocol and plan["protocol_digest"] != study_protocol()["digest"]:
        raise ContractError("study consent protocol changed")
    if fresh and not plan["created_at"] <= _now() < plan["expires_at"]:
        raise ContractError("study consent plan expired or clock moved backward")
    return plan


def study_begin(
    state, kind, audience, journey, retention_days, consent, *, consent_plan=None
):
    plan = _validate_study_plan(state, consent_plan, fresh=False)
    if consent != plan["digest"] or (kind, audience, journey, retention_days) != (
        plan["sample"],
        plan["audience"],
        plan["journey"],
        plan["retention_days"],
    ):
        raise ContractError(
            "explicit consent must bind this exact study selection and retention"
        )
    with Store(state).locked() as store:
        if store.exists("study", plan["id"]):
            previous = _read_study(store, plan["id"], state)
            if (
                previous["consent"]["plan_digest"] != consent
                or previous["state"] != "consented"
                or _now() >= previous["expires_at"]
            ):
                raise ContractError(
                    "study consent already consumed or withdrawn; create a fresh plan"
                )
            return deepcopy(previous)
        _validate_study_plan(state, plan)
        now = _now()
        body = {
            "schema_version": 1,
            "kind": "study",
            "id": plan["id"],
            "sample": kind,
            "audience": audience,
            "journey": journey,
            "state": "consented",
            "protocol_digest": plan["protocol_digest"],
            "consented_at": now,
            "expires_at": now + retention_days * 86400,
            "events": [],
            "identity": plan["identity"],
            "consent": {"plan_digest": consent, "plan": plan, "recorded_at": now},
        }
        _validate_study_plan(state, plan)
        store.write(body)
        return deepcopy(body)


def _read_study(store, record_id, state):
    body = store.read("study", record_id)
    required = {
        "schema_version",
        "kind",
        "id",
        "sample",
        "audience",
        "journey",
        "state",
        "protocol_digest",
        "consented_at",
        "expires_at",
        "events",
        "identity",
        "consent",
    }
    ended = {"erased_event_count", "erased_record_sha256", "ended_at"}
    if set(body) not in (required, required | ended) or not all(
        isinstance(body.get(k), str) for k in ("sample", "audience", "journey", "state")
    ):
        raise ContractError("study record fields are invalid")
    _integer(body["consented_at"], 1, 2**53, "study consent time")
    _integer(
        body["expires_at"],
        body["consented_at"] + 1,
        body["consented_at"] + 30 * 86400,
        "study expiry",
    )
    if (
        body.get("sample") not in {"synthetic", "participant"}
        or body.get("audience") not in AUDIENCES
        or body.get("journey") not in JOURNEYS
        or body.get("state") not in {"consented", "withdrawn", "expired"}
        or not isinstance(body.get("events"), list)
        or len(body["events"]) > MAX_EVENTS
    ):
        raise ContractError("study record schema is invalid")
    consent = body.get("consent")
    if (
        not isinstance(consent, dict)
        or set(consent) != {"plan_digest", "plan", "recorded_at"}
        or not isinstance(consent["plan"], dict)
        or consent["plan_digest"] != consent["plan"].get("digest")
    ):
        raise ContractError("study consent receipt is invalid")
    plan = _validate_study_plan(
        state, consent["plan"], fresh=False, current_protocol=False
    )
    if (
        plan["id"] != record_id
        or plan["sample"] != body["sample"]
        or plan["audience"] != body["audience"]
        or plan["journey"] != body["journey"]
        or plan["protocol_digest"] != body["protocol_digest"]
        or consent["recorded_at"] != body["consented_at"]
        or body["expires_at"] != body["consented_at"] + plan["retention_days"] * 86400
        or not plan["created_at"] <= body["consented_at"] < plan["expires_at"]
    ):
        raise ContractError("study consent does not bind the exact recorded selection")
    if body["state"] == "consented":
        if set(body) != required:
            raise ContractError("active study has unexpected erasure metadata")
    else:
        if set(body) != required | ended or body["events"]:
            raise ContractError("ended study has invalid erasure custody")
        _integer(body["erased_event_count"], 0, MAX_EVENTS, "erased event count")
        _integer(body["ended_at"], 1, 2**53, "study end time")
        if not _hash(body["erased_record_sha256"]):
            raise ContractError("ended study has invalid erased-record digest")
    seen = set()
    for event in body["events"]:
        # A checksum binds bytes, not their schema or privacy contract. Recovered
        # records use the same observation validator without requiring a past
        # observation to precede a potentially rolled-back current wall clock.
        checked = _observation(event, body, current_time=False)
        if checked["event_id"] in seen:
            raise ContractError("study record repeats an observation identity")
        seen.add(checked["event_id"])
    if body["identity"] != _study_identity(state):
        raise ContractError("study machine identity changed")
    return body


def _observation(value, body, *, current_time=True):
    fields = {
        "event_id",
        "step",
        "event",
        "elapsed_ms",
        "observed_at",
        "provenance",
        "witness_sha256",
        "outcome",
        "term",
        "command",
        "command_sha256",
        "coaching",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(
            "study observation fields exclude raw or unspecified content"
        )
    if not all(
        isinstance(value[key], str)
        for key in ("step", "event", "outcome", "provenance", "coaching")
    ):
        raise ContractError("study observation vocabulary must be text")
    if any(
        value[key] is not None and not isinstance(value[key], str)
        for key in ("term", "command", "command_sha256")
    ):
        raise ContractError("study optional vocabulary must be text or null")
    from first_run_store import IDENTIFIER

    if not isinstance(value["event_id"], str) or not IDENTIFIER.fullmatch(
        value["event_id"]
    ):
        raise ContractError("study event ID is invalid")
    if (
        value["step"] not in STEPS
        or value["event"] not in EVENTS
        or value["outcome"] not in {"observed", "pass", "fail", "unknown"}
        or value["provenance"]
        not in {"direct-observation", "participant-report", "synthetic-fixture"}
        or value["coaching"] not in {"none", "provided", "unknown"}
    ):
        raise ContractError("study observation vocabulary is invalid")
    if (
        body["sample"] == "synthetic"
        and value["provenance"] != "synthetic-fixture"
        or body["sample"] == "participant"
        and value["provenance"] == "synthetic-fixture"
    ):
        raise ContractError("study sample and observation provenance differ")
    _integer(value["elapsed_ms"], 0, 86400000, "elapsed milliseconds")
    _integer(
        value["observed_at"],
        body["consented_at"],
        min(_now(), body["expires_at"] - 1)
        if current_time
        else body["expires_at"] - 1,
        "observation time",
    )
    if not _hash(value["witness_sha256"]):
        raise ContractError("study requires a bounded local witness digest")
    if value["event"] == "unexplained-term":
        if value["term"] not in TERMS:
            raise ContractError(
                "unexplained term must use the privacy-minimized vocabulary"
            )
    elif value["term"] is not None:
        raise ContractError("term is only valid for an unexplained-term observation")
    if value["event"] == "command-copied":
        if value["command"] not in COMMANDS or not _hash(value["command_sha256"]):
            raise ContractError(
                "copied command needs a declared kind and digest, not raw text"
            )
    elif value["command"] is not None or value["command_sha256"] is not None:
        raise ContractError(
            "command evidence only belongs to command-copied observations"
        )
    return deepcopy(value)


def study_observe(state, record_id, observation):
    with Store(state).locked() as store:
        body = _read_study(store, record_id, state)
        if body["state"] != "consented" or _now() >= body["expires_at"]:
            raise ContractError("study consent withdrawn or expired; capture refused")
        if body["protocol_digest"] != study_protocol()["digest"]:
            raise ContractError("study protocol changed; fresh consent is required")
        value = _observation(observation, body)
        matches = [
            event for event in body["events"] if event["event_id"] == value["event_id"]
        ]
        if matches:
            if matches != [value]:
                raise ContractError(
                    "study event identity already binds another observation"
                )
            return {
                "status": "RECORDED",
                "event_sha256": digest(value),
                "replayed": True,
            }
        if len(body["events"]) >= MAX_EVENTS:
            raise ContractError("study observation capacity reached")
        updated = {**body, "events": body["events"] + [value]}
        # Recheck expiry immediately before admitting the capture write.
        if _now() >= body["expires_at"]:
            raise ContractError("study consent expired before capture")
        store.write(updated, expected=body)
        return {"status": "RECORDED", "event_sha256": digest(value), "replayed": False}


def study_status(state, record_id):
    with Store(state).locked() as store:
        body = _read_study(store, record_id, state)
        if body["state"] == "consented" and _now() >= body["expires_at"]:
            return {
                "id": record_id,
                "state": "retention-due",
                "next_action": "Run study expire to erase only this owned captured record. External witnesses have separate custody.",
            }
        counts = {
            step: sum(e["step"] == step for e in body["events"]) for step in STEPS
        }
        return {
            **deepcopy(body),
            "counts": counts,
            "missing_observations": [s for s, n in counts.items() if not n],
            "qualification": "synthetic rehearsal only"
            if body["sample"] == "synthetic"
            else "locally recorded attestations; genuine participant acceptance requires separate review",
        }


def study_end(state, record_id, *, expired=False):
    with Store(state).locked() as store:
        body = _read_study(store, record_id, state)
        prepared = store.prepared("study", record_id)
        if body["state"] in {"withdrawn", "expired"}:
            store.erase_prepared(prepared)
            return deepcopy(body)
        if expired and _now() < body["expires_at"]:
            raise ContractError(
                "study retention has not expired; use explicit withdrawal"
            )
        updated = {
            **body,
            "state": "expired" if expired else "withdrawn",
            "events": [],
            "erased_event_count": len(body["events"]),
            "erased_record_sha256": digest(body),
            "ended_at": _now(),
        }
        store.write(updated, expected=body)
        store.erase_prepared(prepared)
        return deepcopy(updated)


def command(args, state, source, *, engine_runner=None):
    if args.command == "journey":
        action = args.journey_command
        if action == "catalog":
            return catalog()
        if action == "plan":
            return plan(
                state,
                source,
                args.journey,
                args.clients.split(","),
                stage_core=not args.no_dormant_core,
                ttl=args.ttl,
            )
        if action == "apply":
            return apply(
                state, source, args.id, args.consent, engine_runner=engine_runner
            )
        if action == "status":
            return status(state, source, args.id, engine_runner=engine_runner)
        return verify_first_value(
            state,
            source,
            args.id,
            args.artifact,
            args.sha256,
            args.confirmed_useful,
            engine_runner=engine_runner,
        )
    action = args.study_command
    if action == "protocol":
        return study_protocol()
    if action == "plan":
        return study_plan(
            state,
            args.sample,
            args.audience,
            args.journey,
            args.retention_days,
            ttl=args.ttl,
        )
    if action == "begin":
        data, _ = read_file(args.plan)
        selected = _validate_study_plan(state, decode(data), fresh=False)
        return study_begin(
            state,
            selected["sample"],
            selected["audience"],
            selected["journey"],
            selected["retention_days"],
            args.consent,
            consent_plan=selected,
        )
    if action == "observe":
        data, _ = read_file(args.input)
        return study_observe(state, args.id, decode(data))
    if action == "status":
        return study_status(state, args.id)
    return study_end(state, args.id, expired=action == "expire")
