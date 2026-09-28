#!/usr/bin/env python3
"""Neutral organization contracts consumed by coordination and onboarding.

This module validates attribution and declared boundaries, not credentials or host
ACLs. It owns no claims, lease, scheduler, approval store or global configuration.
All transformations are pure; existing owners publish them under their own CAS.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timezone
from urllib.parse import urlsplit

MAX_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 4096
ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,95}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
CLIENT_SCHEMES = {
    "claude": {"cc", "ccd"},
    "codex": {"codex"},
    "muse": {"muse"},
    "cursor": {"cursor"},
    "copilot": {"copilot"},
}


class TeamContractError(ValueError):
    """Malformed, stale or unsupported declared team contract."""


def _object(value, required, optional=(), label="object"):
    if (
        not isinstance(value, dict)
        or set(value) - set(required) - set(optional)
        or set(required) - set(value)
    ):
        raise TeamContractError(
            f"{label}: exact required and allowed keys are not satisfied"
        )
    return value


def _id(value, label="identifier"):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise TeamContractError(f"{label}: expected an opaque bounded identifier")
    return value


def _list(value, label="collection"):
    if not isinstance(value, list) or len(value) > MAX_ITEMS:
        raise TeamContractError(f"{label}: expected a bounded list")
    return value


def _ids(value, label="identifiers"):
    items = [_id(item, label) for item in _list(value, label)]
    if len(items) != len(set(items)):
        raise TeamContractError(f"{label}: duplicate identity before aggregation")
    return items


def _entries(value, label):
    rows = _list(value, label)
    ids = []
    for row in rows:
        if not isinstance(row, dict):
            raise TeamContractError(f"{label}: entries must be objects")
        ids.append(_id(row.get("id"), label))
    if len(set(ids)) != len(ids):
        raise TeamContractError(f"{label}: duplicate identity before aggregation")
    return rows


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise TeamContractError(
            "timestamp must be an explicit timezone-bearing ISO value"
        )
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise ValueError("missing timezone")
        return moment.astimezone(timezone.utc)
    except ValueError as exc:
        raise TeamContractError(
            "timestamp must be an explicit timezone-bearing ISO value"
        ) from exc


def _policy(value):
    _object(
        value, {"restriction_ids", "approval_roles", "minimum_reader"}, label="policy"
    )
    _ids(value["restriction_ids"])
    if type(value["minimum_reader"]) is not int or value["minimum_reader"] < 6:
        raise TeamContractError(
            "team contracts require a reader that refuses unknown team schema"
        )
    roles = value["approval_roles"]
    if not isinstance(roles, dict) or len(roles) > MAX_ITEMS:
        raise TeamContractError("approval_roles must be a bounded object")
    for action, allowed in roles.items():
        _id(action)
        _ids(allowed)


def validate(document):
    """Validate every raw identity and reference before building any lookup map."""
    d = _object(
        document,
        {
            "schema",
            "organization",
            "deletion_unit",
            "revision",
            "people",
            "seats",
            "repositories",
            "entitlements",
            "policy",
            "governance",
        },
        label="team",
    )
    if (
        type(d["schema"]) is not int
        or d["schema"] != 1
        or type(d["revision"]) is not int
        or d["revision"] < 1
    ):
        raise TeamContractError("unsupported team schema or revision")
    _id(d["organization"])
    _id(d["deletion_unit"])
    people = _entries(d["people"], "people")
    person_ids = {p["id"] for p in people}
    humans = {
        p["id"]
        for p in people
        if p.get("kind") == "human" and p.get("status") == "active"
    }
    accounts = set()
    for p in people:
        _object(
            p, {"id", "kind", "status", "accounts", "roles"}, {"custodians"}, "person"
        )
        if p["kind"] not in {"human", "service"} or p["status"] not in {
            "active",
            "retired",
        }:
            raise TeamContractError("person kind/status invalid")
        _ids(p["roles"])
        for a in _list(p["accounts"], "accounts"):
            _object(a, {"host", "account_id", "username"}, label="account")
            host = a["host"]
            if not isinstance(host, str) or not re.fullmatch(
                r"[a-z0-9][a-z0-9.-]{0,252}", host
            ):
                raise TeamContractError("account host must be a canonical hostname")
            if not isinstance(a["account_id"], str) or not re.fullmatch(
                r"[A-Za-z0-9._:-]{1,128}", a["account_id"]
            ):
                raise TeamContractError("account requires immutable host account_id")
            if (
                not isinstance(a["username"], str)
                or not 1 <= len(a["username"]) <= 128
                or any(ord(c) < 32 for c in a["username"])
            ):
                raise TeamContractError("account username must be bounded display text")
            key = (host, a["account_id"])
            if key in accounts:
                raise TeamContractError("immutable account is assigned more than once")
            accounts.add(key)
        if p["kind"] == "service":
            custodians = _ids(p.get("custodians"))
            if not custodians or not set(custodians) <= humans:
                raise TeamContractError("service requires active human custodians")
        elif "custodians" in p:
            raise TeamContractError("human does not declare service custodians")
    for seat in _entries(d["seats"], "seats"):
        _object(
            seat,
            {"id", "organization", "deletion_unit", "occupancies", "covered_by"},
            label="standing role",
        )
        if (
            seat["organization"] != d["organization"]
            or seat["deletion_unit"] != d["deletion_unit"]
        ):
            raise TeamContractError(
                "standing role cannot cross organization/deletion-unit boundary"
            )
        if not set(_ids(seat["covered_by"])) <= humans:
            raise TeamContractError(
                "coverage must name active human principals; absence dates remain private"
            )
        previous_end = None
        for index, occupancy in enumerate(_list(seat["occupancies"], "occupancies")):
            _object(
                occupancy, {"person", "opened", "closed"}, {"brief_digest"}, "occupancy"
            )
            if (
                occupancy["person"] not in person_ids
                or next(p for p in people if p["id"] == occupancy["person"])["kind"]
                != "human"
            ):
                raise TeamContractError("only human principals occupy standing roles")
            begin = _time(occupancy["opened"])
            end = (
                _time(occupancy["closed"]) if occupancy["closed"] is not None else None
            )
            if (end is not None and end <= begin) or (
                index and (previous_end is None or begin < previous_end)
            ):
                raise TeamContractError("occupancy intervals overlap or run backward")
            if end is None and occupancy["person"] not in humans:
                raise TeamContractError(
                    "open occupancy requires active principal; offboarding must account for claims separately"
                )
            if "brief_digest" in occupancy and not HEX.fullmatch(
                str(occupancy["brief_digest"])
            ):
                raise TeamContractError("occupancy brief must bind exact source bytes")
            previous_end = end
    for repo in _entries(d["repositories"], "repositories"):
        _object(
            repo,
            {"id", "organization", "deletion_unit", "audience", "readers", "remote"},
            label="repository",
        )
        if (
            repo["organization"] != d["organization"]
            or repo["deletion_unit"] != d["deletion_unit"]
        ):
            raise TeamContractError("repository belongs to another deletion unit")
        readers = _ids(repo["readers"])
        if (
            not readers
            or not set(readers) <= person_ids
            or repo["audience"] not in {"shared", "private"}
        ):
            raise TeamContractError("repository audience/readers invalid")
        if repo["audience"] == "private" and len(readers) != 1:
            raise TeamContractError("private companion must name exactly one principal")
        parsed = urlsplit(repo["remote"]) if isinstance(repo["remote"], str) else None
        if (
            parsed is None
            or parsed.scheme not in {"https", "ssh"}
            or not parsed.hostname
            or (parsed.username is not None and parsed.scheme != "ssh")
            or parsed.password
            or parsed.query
            or parsed.fragment
            or ".." in parsed.path.split("/")
            or not parsed.path.strip("/")
        ):
            raise TeamContractError(
                "repository requires credential-free explicit logical remote"
            )
    for e in _entries(d["entitlements"], "entitlements"):
        _object(
            e, {"id", "kind", "required", "roles"}, {"repository"}, label="entitlement"
        )
        if (
            e["kind"] not in {"knowledge-base", "skills"}
            or type(e["required"]) is not bool
        ):
            raise TeamContractError("entitlement kind/required invalid")
        if e["kind"] == "knowledge-base":
            if e.get("repository") not in {r["id"] for r in d["repositories"]}:
                raise TeamContractError(
                    "knowledge entitlement must bind one declared logical repository"
                )
        elif "repository" in e:
            raise TeamContractError(
                "repository audience binding is specific to knowledge entitlements"
            )
        _ids(e["roles"])
    _policy(d["policy"])
    g = _object(
        d["governance"],
        {
            "channel",
            "version_pin",
            "contribution",
            "mirror_owner",
            "private_namespace",
            "configuration_root",
        },
        optional={"role_history", "departures"},
        label="governance",
    )
    if (
        g["channel"] not in {"stable", "edge"}
        or not isinstance(g["version_pin"], str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", g["version_pin"])
    ):
        raise TeamContractError(
            "shared releases require an explicit channel and exact release pin"
        )
    if (
        g["contribution"] not in {"review", "direct-main-audit"}
        or g["mirror_owner"] not in humans
        or g["private_namespace"] != "principal-id"
        or g["configuration_root"] != "user-owned"
    ):
        raise TeamContractError(
            "shared governance must name an active mirror owner and isolated user configuration"
        )
    for record in _entries(g.get("role_history", []), "role history"):
        _object(
            record,
            {
                "id",
                "person",
                "role",
                "scope",
                "backup",
                "opened",
                "closed",
                "accepted_work",
                "inventory_sha256",
                "appointed_by",
                "approval_digest",
                "native_ref",
            },
            {"replaces"},
            label="role record",
        )
        if (
            record["person"] not in person_ids
            or record["backup"] not in person_ids
            or record["appointed_by"] not in person_ids
            or record["person"] == record["backup"]
        ):
            raise TeamContractError("role history principal/backup identity is invalid")
        if record["role"] not in {
            "contributor",
            "repeat-contributor",
            "runtime-steward",
            "maintainer",
        }:
            raise TeamContractError("unsupported governed role")
        if not isinstance(record["native_ref"], str) or not re.fullmatch(
            r"[a-z][a-z0-9+.-]*:[A-Za-z0-9._:@-]{1,200}", record["native_ref"]
        ):
            raise TeamContractError("role attribution native reference invalid")
        _ids(record["scope"])
        _ids(record["accepted_work"])
        if (
            not record["scope"]
            or not record["accepted_work"]
            or not HEX.fullmatch(str(record["inventory_sha256"]))
            or not HEX.fullmatch(str(record["approval_digest"]))
        ):
            raise TeamContractError(
                "role history needs exact accepted evidence and scope"
            )
        begin = _time(record["opened"])
        if record["closed"] is not None and _time(record["closed"]) <= begin:
            raise TeamContractError("role history interval is invalid")
        if record["closed"] is None and (
            record["person"] not in humans or record["backup"] not in humans
        ):
            raise TeamContractError("open role needs current human occupants")

    records = {r["id"]: r for r in g.get("role_history", [])}
    for record in records.values():
        replaced = record.get("replaces")
        if replaced is not None:
            prior = records.get(replaced)
            if (
                not prior
                or prior["closed"] != record["opened"]
                or prior["role"] != record["role"]
                or set(prior["scope"]) != set(record["scope"])
            ):
                raise TeamContractError(
                    "role succession does not bind the exact closed predecessor"
                )
    for departure in _entries(g.get("departures", []), "departures"):
        _object(
            departure,
            {
                "id",
                "person",
                "at",
                "approved_by",
                "approval_digest",
                "native_ref",
                "observation_digest",
            },
            label="departure",
        )
        if (
            departure["person"] not in person_ids
            or departure["approved_by"] not in person_ids
        ):
            raise TeamContractError("departure attribution is unknown")
        _time(departure["at"])
        if (
            not HEX.fullmatch(str(departure["approval_digest"]))
            or not HEX.fullmatch(str(departure["observation_digest"]))
            or not isinstance(departure["native_ref"], str)
            or not 1 <= len(departure["native_ref"]) <= 224
        ):
            raise TeamContractError(
                "departure needs exact approval and native attribution"
            )

    # JSON bounds also reject non-JSON types and nonfinite numbers in unconsumed values.
    try:
        raw = json.dumps(d, allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise TeamContractError("team contract is not JSON") from exc
    if len(raw) > MAX_BYTES:
        raise TeamContractError("team contract exceeds byte bound")
    return copy.deepcopy(d)


def _principal(d, person):
    validate(d)
    row = next((p for p in d["people"] if p["id"] == person), None)
    if row is None or row["status"] != "active":
        raise TeamContractError("principal is absent or retired")
    return row


def effective_roles(d, person, *, scope=None, observed_at=None):
    """Bootstrap roles plus current exact-scope appointments; backup is not role."""
    p = _principal(d, person)
    roles = set(p["roles"])
    observed = _time(observed_at) if observed_at is not None else datetime.now(timezone.utc)
    for record in d["governance"].get("role_history", []):
        if (
            record["person"] == person
            and _time(record["opened"]) <= observed
            and (record["closed"] is None or observed < _time(record["closed"]))
            and scope is not None
            and scope in record["scope"]
        ):
            roles.add(record["role"])
    return sorted(roles)


def account_principal(d, host, account_id):
    validate(d)
    for person in d["people"]:
        if any(
            a["host"] == host and a["account_id"] == account_id
            for a in person["accounts"]
        ):
            return person["id"]
    raise TeamContractError("immutable host account has no declared principal")


def attribution(d, *, person, agent, client, machine, native_ref, standing_role=""):
    _principal(d, person)
    _id(machine)
    _id(agent)
    if (
        client not in CLIENT_SCHEMES
        or not isinstance(native_ref, str)
        or not re.fullmatch(r"[a-z][a-z0-9+.-]*:[A-Za-z0-9._:@-]{1,200}", native_ref)
        or native_ref.split(":", 1)[0] not in CLIENT_SCHEMES[client]
    ):
        raise TeamContractError(
            "native identity does not match the declared client adapter"
        )
    if standing_role:
        seat = next((s for s in d["seats"] if s["id"] == standing_role), None)
        eligible = set(seat["covered_by"]) if seat else set()
        if seat:
            eligible.update(
                o["person"] for o in seat["occupancies"] if o["closed"] is None
            )
        if person not in eligible:
            raise TeamContractError(
                "principal is neither the current occupant nor explicit cover for the standing role"
            )
    return {
        "principal": person,
        "agent": agent,
        "client": client,
        "machine": machine,
        "native_ref": native_ref,
        "standing_role": standing_role,
        "organization": d["organization"],
        "deletion_unit": d["deletion_unit"],
        "authority": "attribution-only",
        "host_acl_verified": False,
    }


def entitlement_plan(d, person, *, requested):
    _principal(d, person)
    requested = set(_ids(requested, "requested entitlements"))
    all_ids = {e["id"] for e in d["entitlements"]}
    if not requested <= all_ids:
        raise TeamContractError("unknown requested entitlement")
    selected, excluded = [], []
    for entry in d["entitlements"]:
        eligible = not entry["roles"] or bool(
            set(entry["roles"])
            & set(effective_roles(d, person, scope=entry.get("repository")))
        )
        if entry["kind"] == "knowledge-base":
            repository = next(
                r for r in d["repositories"] if r["id"] == entry["repository"]
            )
            eligible = eligible and person in repository["readers"]
        if entry["id"] in requested and not eligible:
            raise TeamContractError(
                "requested entitlement is outside declared roles; no ACL grant inferred"
            )
        if eligible and (entry["required"] or entry["id"] in requested):
            selected.append(entry["id"])
        else:
            excluded.append(entry["id"])
    return {
        "selected": selected,
        "excluded": excluded,
        "access_verified": False,
        "person_once": ["host-access-grant", "roster-enrollment"],
        "machine_each": [
            "native-authentication",
            "client-readiness",
            "configuration",
            "receipts",
        ],
    }


def transfer_occupancy(
    d, role, previous, successor, *, expected_revision, at, brief_digest
):
    _principal(d, previous)
    incoming = _principal(d, successor)
    if (
        type(expected_revision) is not int
        or expected_revision != d["revision"]
        or previous == successor
        or incoming["kind"] != "human"
        or not HEX.fullmatch(str(brief_digest))
    ):
        raise TeamContractError("stale or invalid standing-role transfer")
    out = copy.deepcopy(d)
    seat = next((s for s in out["seats"] if s["id"] == role), None)
    if (
        not seat
        or not seat["occupancies"]
        or seat["occupancies"][-1]["closed"] is not None
        or seat["occupancies"][-1]["person"] != previous
    ):
        raise TeamContractError("predecessor is not the exact open occupant")
    if _time(at) <= _time(seat["occupancies"][-1]["opened"]):
        raise TeamContractError("transfer must follow the existing occupancy")
    seat["occupancies"][-1]["closed"] = at
    seat["occupancies"].append(
        {
            "person": successor,
            "opened": at,
            "closed": None,
            "brief_digest": brief_digest,
        }
    )
    out["revision"] += 1
    return validate(out)


def reference_allowed(source, target):
    """May a source document expose a target's identity to every source reader?"""
    for repo in (source, target):
        _object(
            repo,
            {"id", "organization", "deletion_unit", "audience", "readers", "remote"},
            label="repository",
        )
        _ids(repo["readers"])
    return (
        source["organization"] == target["organization"]
        and source["deletion_unit"] == target["deletion_unit"]
        and set(source["readers"]) <= set(target["readers"])
        and not (source["audience"] == "shared" and target["audience"] == "private")
    )


def compose_policy(layers):
    """Restrictions union; approval eligibility intersection. No allowance export."""
    if not _list(layers) or len(layers) > 32:
        raise TeamContractError("policy needs one to 32 ordered layers")
    restrictions, actions, floor = set(), {}, 6
    for layer in layers:
        _policy(layer)
        restrictions.update(layer["restriction_ids"])
        floor = max(floor, layer["minimum_reader"])
        for action, roles in layer["approval_roles"].items():
            actions[action] = (
                set(roles) if action not in actions else actions[action] & set(roles)
            )
    return {
        "restriction_ids": sorted(restrictions),
        "approval_roles": {k: sorted(v) for k, v in sorted(actions.items())},
        "minimum_reader": floor,
    }


def offboarding_check(d, person, sessions, *, host_acl_revoked):
    _principal(d, person)
    if type(host_acl_revoked) is not bool:
        raise TeamContractError(
            "ACL revocation evidence must be an explicit Boolean observation"
        )
    active = []
    for row in _list(sessions):
        _object(row, {"principal", "session", "status"}, label="session observation")
        if row["status"] not in {"active", "parked", "released", "complete"}:
            raise TeamContractError("unknown session disposition")
        if row["principal"] == person and row["status"] in {"active", "parked"}:
            active.append(_id(row["session"]))
    open_roles = [
        s["id"]
        for s in d["seats"]
        if any(o["person"] == person and o["closed"] is None for o in s["occupancies"])
    ]
    return {
        "ready": host_acl_revoked and not active and not open_roles,
        "active_sessions": active,
        "open_roles": open_roles,
        "host_acl_revoked": host_acl_revoked,
        "mutation": "none",
        "boundary": "caller-supplied observations; host ACL verification remains external",
    }


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TeamContractError("duplicate JSON member before aggregation")
        result[key] = value
    return result


def _identity(st):
    return (
        st.st_dev,
        st.st_ino,
        st.st_mode,
        st.st_uid,
        st.st_nlink,
        st.st_size,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )


def _parent_binding(path):
    """Open the lexical parent without aliases and retain its directory identity."""
    if len(path.parts) > 256 or ".." in path.parts:
        raise TeamContractError("team path is not bounded and canonical")
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    identities = []
    try:
        for component in (None, *path.parent.parts[1:]):
            if component is not None:
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
            info = os.fstat(descriptor)
            identities.append(
                (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)
            )
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


def read_source(path, *, expected_digest=None, limit=MAX_BYTES):
    """Bounded no-follow read; replaced, linked, or untrusted mutable bytes refuse."""
    if type(limit) is not int or not 0 < limit <= 4 * 1024 * 1024:
        raise TeamContractError("source byte bound invalid")
    p = Path(path).absolute()
    if expected_digest is not None and not HEX.fullmatch(str(expected_digest)):
        raise TeamContractError("expected team digest invalid")
    try:
        parent, binding = _parent_binding(p)
        try:
            fd = os.open(
                p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            try:
                before = os.fstat(fd)
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_uid != os.getuid()
                    or before.st_mode & 0o022
                    or before.st_size > limit
                ):
                    raise TeamContractError(
                        "team source is unsafe, foreign, multiply linked or oversized"
                    )
                raw = bytearray()
                while len(raw) <= limit:
                    part = os.read(fd, min(65536, limit + 1 - len(raw)))
                    if not part:
                        break
                    raw.extend(part)
                final_parent, final_binding = _parent_binding(p)
                try:
                    current = os.stat(
                        p.name, dir_fd=final_parent, follow_symlinks=False
                    )
                    if (
                        binding != final_binding
                        or len(raw) > limit
                        or _identity(before) != _identity(os.fstat(fd))
                        or _identity(before) != _identity(current)
                    ):
                        raise TeamContractError("team source changed while reading")
                finally:
                    os.close(final_parent)
            finally:
                os.close(fd)
        finally:
            os.close(parent)
        if (
            expected_digest is not None
            and hashlib.sha256(raw).hexdigest() != expected_digest
        ):
            raise TeamContractError("team source digest changed")
        return bytes(raw)
    except OSError as exc:
        raise TeamContractError("team source unavailable or unsafe") from exc


def load_document(path, *, expected_digest=None):
    try:
        return json.loads(
            read_source(path, expected_digest=expected_digest),
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                TeamContractError("nonfinite JSON")
            ),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise TeamContractError("team source is not bounded unique JSON") from exc


def load(path, *, expected_digest=None):
    return validate(load_document(path, expected_digest=expected_digest))


# A registry explicitly enrolls its repository with one source-bound comment.
# The marker is not a permission grant and ordinary project IDs cannot select it.
REGISTRY_MARKER = re.compile(
    r"(?m)^# Synthesis-Team: ([a-z0-9][a-z0-9._-]{0,95}\.json) @ ([0-9a-f]{64}) / ([a-z0-9][a-z0-9._-]{0,95})[ \t]*$"
)


def registry_binding(index):
    """Inspect enrolled index bytes without exposing any project prose."""
    path = Path(index).absolute()
    raw = read_source(path, limit=4 * 1024 * 1024)
    text = raw.decode("utf-8")
    matches = REGISTRY_MARKER.findall(text)
    if (
        len(matches) != len(re.findall(r"(?m)^# Synthesis-Team:", text))
        or len(matches) > 1
    ):
        raise TeamContractError("team access: ambiguous registry enrollment")
    if not matches:
        # A dirty working copy cannot silently remove a tracked enrollment.
        # Git's committed record is read locally; no fetch or network occurs.
        from coordination_process import run as bounded_run

        base = ["git", "--no-optional-locks", "-C", str(path.parent)]
        tracked = bounded_run(
            base + ["ls-files", "--error-unmatch", "--", path.name],
            cwd=path.parent,
            timeout=5,
            output_bytes=4096,
        )
        if tracked.returncode == 0:
            head = bounded_run(base + ["rev-parse", "--verify", "HEAD^{commit}"],
                cwd=path.parent, timeout=5, output_bytes=4096)
            if head.returncode:
                symbolic = bounded_run(base + ["symbolic-ref", "-q", "HEAD"],
                    cwd=path.parent, timeout=5, output_bytes=4096)
                reference = symbolic.stdout.strip()
                if not reference.startswith("refs/heads/"):
                    raise TeamContractError("team enrollment committed source is unavailable")
                exists = bounded_run(base + ["show-ref", "--verify", "--quiet", reference],
                    cwd=path.parent, timeout=5, output_bytes=4096)
                if exists.returncode != 1:
                    raise TeamContractError("team enrollment committed source is unavailable")
                return None  # A genuine unborn branch has no committed enrollment.
            previous = bounded_run(
                base
                + ["grep", "-q", "-F", "# Synthesis-Team:", "HEAD", "--", path.name],
                cwd=path.parent,
                timeout=5,
                output_bytes=4096,
            )
            if previous.returncode not in (0, 1):
                raise TeamContractError(
                    "team enrollment committed source is unavailable"
                )
            if previous.returncode == 0:
                raise TeamContractError(
                    "team enrollment was removed from the working registry"
                )
        return None
    name, digest, repository = matches[0]
    d = load(path.parent / name, expected_digest=digest)
    row = next((v for v in d["repositories"] if v["id"] == repository), None)
    if row is None:
        raise TeamContractError("team access: undeclared repository")
    import subprocess

    result = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(path.parent),
            "remote",
            "get-url",
            "origin",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode or result.stdout.strip() != row["remote"]:
        raise TeamContractError(
            "team access: exact repository remote is unavailable or differs"
        )
    return {
        "document": d,
        "repository": row,
        "path": str(path.parent / name),
        "sha256": digest,
        "index_sha256": hashlib.sha256(raw).hexdigest(),
    }


def board_principal(board, *, native_payload=None):
    """Reuse current board/native owner checks; no human authentication inferred."""
    import coordination

    board = Path(board).absolute()
    text = coordination.passive_board_snapshot(board)
    rows = coordination.rows(text)
    coordination.validate_team_transition(board, text, text)
    if native_payload is not None:
        from native_identity import row_for_event
        from board_grammar import parse_table_rows

        row = row_for_event(parse_table_rows(text), native_payload, board=board)
        matches = [s for s in rows if row and s.session_uuid == row["session uuid"]]
    else:
        matches = [
            s
            for s in rows
            if coordination.active(s) and coordination._caller_owns_session(board, s)
        ]
    if (
        len(matches) != 1
        or not coordination.active(matches[0])
        or not matches[0].person
    ):
        raise TeamContractError(
            "team access: one current native-attributed principal is required"
        )
    marker = re.findall(
        r"(?m)^Team-Contract: ([a-z0-9][a-z0-9._-]{0,95}\.json) @ ([0-9a-f]{64})[ \t]*$",
        text,
    )
    if len(marker) != 1:
        raise TeamContractError("team access: board declaration is unavailable")
    d = load(board.parent / marker[0][0], expected_digest=marker[0][1])
    _principal(d, matches[0].person)
    return {
        "person": matches[0].person,
        "session_uuid": matches[0].session_uuid,
        "native_ref": matches[0].client_ref,
        "document": d,
        "sha256": marker[0][1],
        "board_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def managed_registry(index, *, board=None, native_payload=None):
    binding = registry_binding(index)
    if binding is None:
        return {"enrolled": False, "allowed": True}
    board = board or Path(
        os.environ.get("SYNTHESIS_COORDINATION_BOARD")
        or Path.home() / ".synthesis/coordination/active-sessions.md"
    )
    actor = board_principal(board, native_payload=native_payload)
    if actor["sha256"] != binding["sha256"]:
        raise TeamContractError(
            "team access: registry and native board declaration differ"
        )
    allowed = actor["person"] in binding["repository"]["readers"]
    if registry_binding(index) != binding:
        raise TeamContractError("team access: registry binding changed")
    if board_principal(board, native_payload=native_payload) != actor:
        raise TeamContractError("team access: native principal or board changed")
    return {
        "enrolled": True,
        "allowed": allowed,
        "person": actor["person"],
        "organization": binding["document"]["organization"],
        "deletion_unit": binding["document"]["deletion_unit"],
        "repository": binding["repository"]["id"],
        "sha256": binding["sha256"],
        "host_acl_verified": False,
    }


def require_registry(index, **kwargs):
    result = managed_registry(index, **kwargs)
    if not result["allowed"]:
        raise TeamContractError(
            "team access: principal is outside this repository audience"
        )
    return result


def require_reference(document, source_id, target_id):
    d = validate(document)
    values = {r["id"]: r for r in d["repositories"]}
    if (
        source_id not in values
        or target_id not in values
        or not reference_allowed(values[source_id], values[target_id])
    ):
        raise TeamContractError(
            "team reference: target identity is not available to every source reader"
        )
    return {"source": source_id, "target": target_id, "allowed": True}


def require_board_reference(index, board):
    """A shared board reference is visible to its whole declared human roster.

    This covers the actual project-address message owner, not arbitrary prose or
    external tools. A restricted label cannot be published to a wider roster.
    """
    binding = registry_binding(index)
    if binding is None:
        return {"enrolled": False}
    actor = board_principal(board)
    if actor["sha256"] != binding["sha256"]:
        raise TeamContractError("team reference: source declaration differs")
    audience = {
        p["id"]
        for p in actor["document"]["people"]
        if p["kind"] == "human" and p["status"] == "active"
    }
    if not audience <= set(binding["repository"]["readers"]):
        raise TeamContractError(
            "team reference: project identity is not available to every board reader"
        )
    if registry_binding(index) != binding:
        raise TeamContractError("team reference: enrolled source changed")
    if board_principal(board) != actor:
        raise TeamContractError("team reference: native principal or board changed")
    return {"enrolled": True, "allowed": True, "declaration_sha256": binding["sha256"]}


def publication_constraint(config, repository, *, expected=None):
    """Restrict the existing approval owner; never create a publish approval.

    Enrollment names the local operator's opaque principal. Host authentication
    and the exact human approval remain the existing owner's obligations.
    """
    declarations = config.get("team_contracts", [])
    if not isinstance(declarations, list) or len(declarations) > 32:
        raise TeamContractError("team publication: invalid enrollment inventory")
    matched = []
    for entry in declarations:
        _object(
            entry,
            {"repository", "path", "sha256", "person"},
            {"policy_layers"},
            "publication enrollment",
        )
        if entry["repository"] == str(Path(repository).resolve()):
            d = load(entry["path"], expected_digest=entry["sha256"])
            person = _principal(d, entry["person"])
            if person["kind"] != "human":
                raise TeamContractError(
                    "team publication requires a human approving principal"
                )
            policy = compose_policy([d["policy"], *entry.get("policy_layers", [])])
            roles = policy["approval_roles"].get("publish")
            if roles is None or not set(roles).intersection(person["roles"]):
                raise TeamContractError("team publication: no eligible approving role")
            # Unknown mandatory controls cannot be asserted as satisfied.
            if set(policy["restriction_ids"]) - {
                "human-publication",
                "no-rapid-redeploy",
            }:
                raise TeamContractError(
                    "team publication: mandatory restriction has no enforcing owner"
                )
            matched.append(
                {
                    "organization": d["organization"],
                    "deletion_unit": d["deletion_unit"],
                    "sha256": entry["sha256"],
                    "person": entry["person"],
                    "policy": policy,
                }
            )
    if len(matched) > 1:
        raise TeamContractError("team publication: duplicate enrolled repository")
    result = matched[0] if matched else None
    if expected is not None and result != expected:
        raise TeamContractError(
            "team publication: approval declaration, role or policy changed"
        )
    return result


def retire_principal(declaration, person, *, at, expected_revision, service_successors):
    d = validate(declaration)
    p = _principal(d, person)
    if (
        p["kind"] != "human"
        or expected_revision != d["revision"]
        or type(expected_revision) is not int
    ):
        raise TeamContractError(
            "offboarding requires exact active human and current revision"
        )
    moment = _time(at)
    out = copy.deepcopy(d)
    if not isinstance(service_successors, dict):
        raise TeamContractError("service custody replacements must be explicit")
    needed = {x["id"] for x in d["people"] if person in x.get("custodians", [])}
    if set(service_successors) != needed:
        raise TeamContractError("complete exact service succession inventory required")
    for row in out["people"]:
        if row["id"] == person:
            row["status"] = "retired"
        if row["id"] in needed:
            new = _ids(service_successors[row["id"]])
            row["custodians"] = new
            if person in new:
                raise TeamContractError(
                    "departed principal cannot retain service custody"
                )
    for seat in out["seats"]:
        seat["covered_by"] = [x for x in seat["covered_by"] if x != person]
        for occupancy in seat["occupancies"]:
            if occupancy["person"] == person and occupancy["closed"] is None:
                if moment <= _time(occupancy["opened"]):
                    raise TeamContractError("departure precedes occupancy")
                occupancy["closed"] = at
    for record in out["governance"].get("role_history", []):
        if record["closed"] is None and record["backup"] == person:
            raise TeamContractError(
                "accepted backup succession required before departure"
            )
        if record["person"] == person and record["closed"] is None:
            if moment <= _time(record["opened"]):
                raise TeamContractError("departure precedes appointment")
            record["closed"] = at
    if out["governance"]["mirror_owner"] == person:
        raise TeamContractError(
            "mirror ownership requires separate accepted succession before departure"
        )
    out["revision"] += 1
    return validate(out)


def observed_run_effects(sessions, *, board, deadline=None):
    """Read complete bounded project pages through the existing journal owner.

    Coverage is the exact retained coordination inventory. No host-wide or
    forgotten historical account coverage is inferred from these local records.
    """
    import coordination
    import coordination_process
    import sys
    import time

    projects = set()
    native_refs = {row.client_ref for row in sessions}
    seat_ids = {row.session_uuid for row in sessions}
    for row in sessions:
        if not row.workspaces or not ID.fullmatch(row.project):
            raise TeamContractError("offboarding project custody is not explicit")
        for workspace in row.workspaces:
            root, _branch = coordination.workspace_parts(workspace)
            candidate = Path(root).absolute() / "projects" / row.project
            if not candidate.is_dir():
                raise TeamContractError("retained project custody is missing or unavailable")
            projects.add(candidate)
    if sessions and not projects:
        raise TeamContractError("offboarding project history is unavailable")
    if len(projects) > 32:
        raise TeamContractError("offboarding project inventory exceeds bound")
    script = (
        Path(__file__).resolve().parents[2]
        / "synthesis-autopilot/scripts/operator_status.py"
    )
    deadline = min(deadline, time.monotonic() + 30) if deadline is not None else time.monotonic() + 30
    results, blockers = {}, []
    for project in sorted(projects):
        require_registry(project.parent / "index.yaml", board=board)
        cursor = None
        observed = {}
        initial_inventory = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TeamContractError(
                    "offboarding journal observation exhausted time bound"
                )
            argv = [
                sys.executable,
                "-I",
                "-B",
                str(script),
                "--project",
                str(project),
                "--limit",
                "32",
            ]
            if cursor is not None:
                argv += ["--cursor", cursor]
            receipt = coordination_process.run(
                argv, cwd=script.parent, timeout=min(10, remaining)
            )
            if receipt.returncode:
                raise TeamContractError(
                    "offboarding journal owner observation unavailable"
                )
            page = json.loads(receipt.stdout)
            paging = page["pagination"]
            if paging["total"] > 128 or paging["offset"] != len(observed):
                raise TeamContractError(
                    "offboarding journal inventory is incomplete or oversized"
                )
            if (
                initial_inventory is not None
                and paging["inventory_sha256"] != initial_inventory
            ):
                raise TeamContractError("offboarding journal inventory changed")
            initial_inventory = paging["inventory_sha256"]
            for run in page["runs"]:
                if (
                    run["currentness"] != "JOURNAL_VERIFIED_RECORDED_STATE"
                    or run["run_id"] in observed
                ):
                    raise TeamContractError(
                        "offboarding journal is corrupt, duplicated or unverified"
                    )
                observed[run["run_id"]] = run["journal_head"]
                if (
                    run["owner"]["native_ref"] in native_refs
                    or run["owner"]["session_uuid"] in seat_ids
                ):
                    unsettled = [
                        e["id"]
                        for e in run["effects"]
                        if e["status"] in {"prepared", "unknown", "retryable"}
                    ]
                    children = [c["id"] for c in run["children"] if c["unresolved"]]
                    if (
                        unsettled
                        or children
                        or run["recorded_status"]
                        not in {"completed", "incomplete", "cancelled"}
                    ):
                        blockers.append(
                            {
                                "run": run["run_id"],
                                "reason": "owned journal work or effects remain unresolved",
                                "effects": unsettled,
                                "children": children,
                            }
                        )
            cursor = paging["next_cursor"]
            if cursor is None:
                if len(observed) != paging["total"]:
                    raise TeamContractError(
                        "offboarding journal coverage is incomplete"
                    )
                break
        results[str(project)] = {
            "inventory_sha256": initial_inventory,
            "heads": observed,
        }
    return results, blockers


def _pending_names(pending):
    names = []
    for member in pending.iterdir():
        if len(names) == MAX_ITEMS:
            raise TeamContractError("pending-effect inventory exceeds bound")
        names.append(member.name)
    return sorted(names)


def _offboarding_native_custody(sessions, board, deadline):
    """Bind desktop host handles to retained native identities before effects."""
    import peer_addressing
    import time

    native_ids, sidecars, total = set(), {}, 0
    for row in sessions:
        if len(sidecars) >= MAX_ITEMS or time.monotonic() > deadline:
            raise TeamContractError("native custody observation exceeds bound")
        scheme, separator, value = row.client_ref.partition(":")
        if not separator or not value:
            raise TeamContractError("retained native identity is unavailable")
        if scheme != "ccd":
            native_ids.add(value)
            continue
        path = peer_addressing.seat_path(Path(board), row.session_uuid)
        raw = read_source(path, limit=65536)
        total += len(raw)
        if total > 8 * 1024 * 1024:
            raise TeamContractError("desktop sidecar custody exceeds byte bound")
        try:
            data = json.loads(raw, object_pairs_hook=_unique)
            seat = peer_addressing.seat_from_document(data, expected_uuid=row.session_uuid,
                                                       strict=True, source=path)
        except (ValueError, UnicodeError, RecursionError, TypeError) as exc:
            raise TeamContractError("desktop native custody is unverifiable") from exc
        if (seat is None or seat.client != peer_addressing.CLIENT_CLAUDE
                or seat.host_session_id != value or seat.compact_id != row.compact_id
                or seat.board_machine != row.machine
                or not peer_addressing.UUID_RE.fullmatch(seat.harness_session_id)):
            raise TeamContractError("desktop native custody does not bind retained seat")
        native_ids.add(seat.harness_session_id)
        sidecars[str(path)] = hashlib.sha256(raw).hexdigest()
    return native_ids, sidecars


def observed_offboarding(declaration, person, *, board, repo_guard_root):
    """Current owner observations only; no release, deletion or host revocation."""
    import coordination

    d = validate(declaration)
    _principal(d, person)
    text = coordination.passive_board_snapshot(Path(board))
    coordination.validate_team_transition(Path(board), text, text)
    sessions = coordination.rows(text)
    known = [x for x in sessions if x.person == person]
    blockers = [
        {"session": x.session_uuid, "reason": "owned claim still active"}
        for x in known
        if coordination.active(x)
    ]
    pending = Path(repo_guard_root).absolute() / "pending"
    parent, chain = _parent_binding(pending / "probe")
    os.close(parent)
    if pending.is_symlink() or not pending.is_dir():
        raise TeamContractError("pending-effect custody inventory unavailable")
    import time
    deadline = time.monotonic() + 30
    before = _pending_names(pending)
    total_bytes = 0
    native_ids, native_sidecars = _offboarding_native_custody(known, board, deadline)
    hashes = {}
    for name in before:
        if not re.fullmatch(r"[0-9a-f]{64}\.json", name):
            raise TeamContractError("unknown pending-effect inventory member")
        path = pending / name
        raw = read_source(path)
        total_bytes += len(raw)
        if total_bytes > 32 * 1024 * 1024 or time.monotonic() > deadline:
            raise TeamContractError("pending-effect observation exceeds byte or time bound")
        hashes[name] = hashlib.sha256(raw).hexdigest()
        try:
            value = json.loads(raw, object_pairs_hook=_unique,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise TeamContractError("pending effect is not bounded unique JSON") from exc
        if not isinstance(value, dict):
            raise TeamContractError("pending effect identity is unknown")
        native = value.get("session_id")
        if (
            not isinstance(native, str)
            or name != hashlib.sha256(native.encode()).hexdigest() + ".json"
        ):
            raise TeamContractError("pending effect identity is unknown")
        if native in native_ids:
            blockers.append(
                {"session": native, "reason": "outstanding attributed effects"}
            )
    if _pending_names(pending) != before:
        raise TeamContractError("pending effects changed during observation")
    for name, sha in hashes.items():
        read_source(pending / name, expected_digest=sha)
    journals, journal_blockers = observed_run_effects(known, board=board, deadline=deadline)
    blockers.extend(journal_blockers)
    if _pending_names(pending) != before:
        raise TeamContractError("pending effect inventory changed during journal observation")
    for name, sha in hashes.items():
        read_source(pending / name, expected_digest=sha)
    if time.monotonic() > deadline:
        raise TeamContractError("offboarding observation exhausted time bound")
    for path, sha in native_sidecars.items():
        read_source(Path(path), expected_digest=sha, limit=65536)
    if time.monotonic() > deadline:
        raise TeamContractError("offboarding native custody exhausted time bound")
    final, final_chain = _parent_binding(pending / "probe")
    os.close(final)
    if (
        chain != final_chain
        or coordination.passive_board_snapshot(Path(board)) != text
    ):
        raise TeamContractError("offboarding sources changed")
    return {
        "managed_ready": not blockers,
        "blockers": blockers,
        "person": person,
        "organization": d["organization"],
        "deletion_unit": d["deletion_unit"],
        "board_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "pending_sha256": hashes,
        "native_sidecar_sha256": native_sidecars,
        "journals": journals,
        "coverage": "EXACT_RETAINED_BOARD_PROJECTS",
        "host_revocation": "UNVERIFIED_EXTERNAL",
        "claims_released": False,
        "data_deleted": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--sha256")
    args = parser.parse_args(argv)
    try:
        data = load(args.file, expected_digest=args.sha256)
        print(
            json.dumps(
                {
                    "status": "VALID_CONTRACT",
                    "principals": len(data["people"]),
                    "standing_roles": len(data["seats"]),
                    "host_acl_verified": False,
                    "live_qualification": "NOT_EVALUATED",
                }
            )
        )
        return 0
    except TeamContractError as exc:
        print(json.dumps({"status": "INVALID_CONTRACT", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
