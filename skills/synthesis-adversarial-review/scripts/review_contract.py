#!/usr/bin/env python3
"""Bounded review-package validation; existing ledgers retain decision ownership.

A structural pass binds exact files and references. It does not authenticate a
human, attest native execution, adjudicate evidence or authorize publication.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 4096
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_SECONDS = 10.0
PROFILES = {
    "editorial": (
        "principal-objective",
        "claims",
        "attribution",
        "required-content",
        "rendered-content",
        "url-identity",
        "publication",
    ),
    "code/control": (
        "principal-objective",
        "source",
        "tests",
        "security",
        "runtime",
        "recovery",
        "release",
    ),
    "research": (
        "principal-objective",
        "source-universe",
        "provenance",
        "methods",
        "counterevidence",
        "uncertainty",
    ),
    "operations/compliance": (
        "principal-objective",
        "authority",
        "scope",
        "effects",
        "recovery",
        "disclosure",
        "handoff",
    ),
}
KINDS = {"synthetic", "source", "native", "live-observation"}
METRICS = (
    "principal_sittings",
    "rereads",
    "duplicate_work",
    "elapsed_target_seconds",
    "severity_found",
    "repair_defects",
    "omitted_planes",
)


class ReviewContractError(ValueError):
    pass


def _shape(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or set(value) - set(required) - set(optional)
        or not set(required) <= set(value)
    ):
        raise ReviewContractError("record has missing or unsupported fields")
    return value


def _text(value, label="text"):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 16384
        or "\x00" in value
    ):
        raise ReviewContractError(f"invalid bounded {label}")
    return value


def _list(value):
    if not isinstance(value, list) or len(value) > MAX_ROWS:
        raise ReviewContractError("collection is not a bounded list")
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", value
    ):
        raise ReviewContractError("invalid identity")
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ReviewContractError("invalid SHA-256")
    return value


def _unique(rows, key="id"):
    seen = set()
    for item in _list(rows):
        if not isinstance(item, dict):
            raise ReviewContractError("record must be an object")
        identity = _id(item.get(key)) if key == "id" else _text(item.get(key))
        if identity in seen:
            raise ReviewContractError("duplicate identity before aggregation")
        seen.add(identity)
    return seen


def _relative(value):
    _text(value, "path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or str(path) != value
        or ".." in path.parts
        or "\\" in value
        or any(ord(c) < 32 for c in value)
    ):
        raise ReviewContractError("file reference is not a canonical relative path")
    return value


def _budget_check(budget, additional=0):
    if budget is None:
        return
    budget["bytes"] += additional
    if budget["bytes"] > MAX_TOTAL_BYTES or time.monotonic() > budget["deadline"]:
        raise ReviewContractError("review source read budget exceeded")


def read_bytes(root, relative, *, budget=None):
    _budget_check(budget)
    root = Path(root)
    path = root / _relative(relative)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ReviewContractError("evidence path contains a symbolic link")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > MAX_BYTES
            ):
                raise ReviewContractError(
                    "evidence is not a bounded singly linked regular file"
                )
            _budget_check(budget, before.st_size)
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
        final = path.lstat()
    except OSError as exc:
        raise ReviewContractError("evidence file is unavailable") from exc

    def identity(s):
        return (
            s.st_dev,
            s.st_ino,
            s.st_mode,
            s.st_uid,
            s.st_nlink,
            s.st_size,
            s.st_mtime_ns,
            s.st_ctime_ns,
        )

    if (
        identity(before) != identity(after)
        or identity(after) != identity(final)
        or len(raw) > MAX_BYTES
    ):
        raise ReviewContractError("evidence changed while read")
    for parent in path.parents:
        if parent.is_symlink():
            raise ReviewContractError("evidence ancestor changed to an alias")
    _budget_check(budget)
    return raw


def _files(root, rows, *, budget=None):
    _unique(rows, "path")
    if not rows:
        raise ReviewContractError("a source inventory must not be empty")
    for row in rows:
        _shape(row, {"path", "sha256"})
        if hashlib.sha256(
            read_bytes(root, row["path"], budget=budget)
        ).hexdigest() != _digest(row["sha256"]):
            raise ReviewContractError("source bytes differ from the bound snapshot")


def target_digest(target):
    return hashlib.sha256(
        json.dumps(
            target, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def validate(bundle, root):
    budget = {"bytes": 0, "deadline": time.monotonic() + MAX_SECONDS}
    _shape(
        bundle,
        {
            "schema",
            "target",
            "claims",
            "findings",
            "evidence",
            "decisions",
            "handoffs",
            "terminal_results",
        },
    )
    if type(bundle["schema"]) is not int or bundle["schema"] != 1:
        raise ReviewContractError("unknown review schema")
    target = _shape(
        bundle["target"], {"id", "domain", "principal_objective", "files", "planes"}
    )
    tid = _id(target["id"])
    _text(target["principal_objective"])
    domain = target["domain"]
    if domain not in PROFILES:
        raise ReviewContractError("unknown domain profile")
    planes = _list(target["planes"])
    if len(planes) != len(set(planes)) or not set(PROFILES[domain]) <= set(planes):
        raise ReviewContractError("domain plane matrix is incomplete or duplicated")
    for plane in planes:
        _id(plane)
    _files(root, target["files"], budget=budget)
    all_ids = {tid}
    for key in (
        "claims",
        "findings",
        "evidence",
        "decisions",
        "handoffs",
        "terminal_results",
    ):
        ids = _unique(bundle[key])
        if ids & all_ids:
            raise ReviewContractError("identities collide across record types")
        all_ids |= ids
        for row in bundle[key]:
            if row.get("target") != tid:
                raise ReviewContractError("record refers to another target")
    evidence = {row["id"]: row for row in bundle["evidence"]}

    def refs(values):
        _list(values)
        if (
            not values
            or any(not isinstance(v, str) for v in values)
            or len(values) != len(set(values))
            or not set(values) <= set(evidence)
        ):
            raise ReviewContractError(
                "evidence references are missing, duplicated or unresolved"
            )

    for row in evidence.values():
        _shape(row, {"id", "target", "kind", "producer", "method", "files", "scope"})
        if row["kind"] not in KINDS:
            raise ReviewContractError("unknown evidence kind")
        _id(row["producer"])
        _text(row["method"])
        _text(row["scope"])
        if (
            row["kind"] in {"native", "live-observation"}
            and row["method"] != "observed-execution"
        ):
            raise ReviewContractError(
                "synthetic or source checks cannot be called native observations"
            )
        _files(root, row["files"], budget=budget)
    for row in bundle["claims"]:
        _shape(row, {"id", "target", "plane", "text", "evidence"})
        if row["plane"] not in planes:
            raise ReviewContractError("claim plane is outside declared coverage")
        _text(row["text"])
        refs(row["evidence"])
    for row in bundle["findings"]:
        _shape(row, {"id", "target", "ledger_id", "plane", "evidence"})
        _id(row["ledger_id"])
        if row["plane"] not in planes:
            raise ReviewContractError("finding plane is outside declared coverage")
        refs(row["evidence"])
    decisions = {row["id"]: row for row in bundle["decisions"]}
    for row in decisions.values():
        _shape(
            row,
            {
                "id",
                "target",
                "owner_receipt",
                "target_digest",
                "action",
                "approver",
                "evidence",
            },
        )
        _text(row["owner_receipt"])
        _text(row["approver"])
        _id(row["action"])
        refs(row["evidence"])
        if row["target_digest"] != target_digest(target):
            raise ReviewContractError(
                "decision receipt belongs to another target snapshot"
            )
    for row in bundle["handoffs"]:
        _shape(row, {"id", "target", "target_digest", "reviewer", "evidence", "links"})
        _id(row["reviewer"])
        refs(row["evidence"])
        if row["target_digest"] != target_digest(target):
            raise ReviewContractError("handoff target drifted")
        if any(
            evidence[e]["producer"] == row["reviewer"]
            or evidence[e]["method"] == "copied-receipt"
            for e in row["evidence"]
        ):
            raise ReviewContractError(
                "a reused receipt is not independent reviewer derivation"
            )
        for link in _list(row["links"]):
            read_bytes(root, link, budget=budget)
    destinations = set()
    covered = set()
    expected_coverage = {
        (row["path"], plane) for row in target["files"] for plane in planes
    }
    for row in bundle["terminal_results"]:
        _shape(
            row,
            {
                "id",
                "target",
                "destination",
                "artifact",
                "plane",
                "phase",
                "status",
                "evidence",
                "approval",
            },
        )
        cell = (_relative(row["artifact"]), _id(row["plane"]))
        if cell not in expected_coverage:
            raise ReviewContractError(
                "terminal coverage names an unassigned artifact or plane"
            )
        covered.add(cell)
        key = (_text(row["destination"]), *cell, row["phase"])
        if (
            row["phase"] not in {"content", "control", "platform", "publication"}
            or key in destinations
            or row["status"]
            not in {"verified", "failed", "unverified", "not-authorized"}
        ):
            raise ReviewContractError(
                "terminal destination/phase/state is invalid or duplicate"
            )
        destinations.add(key)
        refs(row["evidence"])
        if row["status"] == "verified" and row["phase"] == "publication":
            decision = decisions.get(row["approval"])
            if (
                not decision
                or decision["action"] != "publish"
                or not any(
                    evidence[e]["kind"] == "live-observation" for e in row["evidence"]
                )
            ):
                raise ReviewContractError(
                    "publication requires exact owner approval and separate live observation"
                )
        elif row["approval"] is not None and row["approval"] not in decisions:
            raise ReviewContractError("unresolved approval reference")
    if covered != expected_coverage:
        raise ReviewContractError(
            "terminal coverage is missing assigned artifact-plane cells"
        )
    # Detect changes between separate references, as well as during each read.
    _files(root, target["files"], budget=budget)
    for row in evidence.values():
        _files(root, row["files"], budget=budget)
    _budget_check(budget)
    return {
        "coverage_complete": True,
        "domain": domain,
        "target_digest": target_digest(target),
        "validated": "structure-and-exact-source-bindings",
        "authority": "none",
        "unverified": [
            "truth-of-observations",
            "approver-authentication",
            "native-behavior",
            "publication-permission",
            "review-sufficiency",
        ],
    }


def discover_instruments(root, *, budget=None):
    _budget_check(budget)
    root = Path(root).absolute()
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ReviewContractError("instrument root is unavailable or aliased")
    discovered = set()
    visited = 0
    started = time.monotonic()
    def unavailable(error):
        raise ReviewContractError("instrument traversal is unreadable") from error

    for current, dirs, files in os.walk(root, followlinks=False, onerror=unavailable):
        for name in dirs + files:
            _budget_check(budget)
            visited += 1
            if visited > 16384 or time.monotonic() - started > 5:
                raise ReviewContractError(
                    "instrument traversal exceeds its finite entry/time bound"
                )
            path = Path(current) / name
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not (
                stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)
            ):
                raise ReviewContractError(
                    "instrument universe contains alias or special node"
                )
            if stat.S_ISREG(metadata.st_mode) and (
                metadata.st_mode & 0o111
                or path.suffix
                in {
                    ".py",
                    ".js",
                    ".mjs",
                    ".cjs",
                    ".c",
                    ".cc",
                    ".cpp",
                    ".sh",
                    ".bash",
                    ".zsh",
                }
            ):
                discovered.add(path.relative_to(root).as_posix())
            if len(discovered) > MAX_ROWS:
                raise ReviewContractError("instrument universe exceeds bound")
    _budget_check(budget)
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ReviewContractError("instrument root became aliased")
    return sorted(discovered)


def instrument_inventory(root, declarations):
    budget = {"bytes": 0, "deadline": time.monotonic() + MAX_SECONDS}
    root = Path(root).absolute()
    ids = _unique(declarations, "path")
    discovered = set(discover_instruments(root, budget=budget))
    if ids != discovered:
        raise ReviewContractError("unclassified or nonexistent executable instrument")
    def identity(path):
        try:
            s = path.lstat()
        except OSError as exc:
            raise ReviewContractError("instrument disappeared during inventory") from exc
        return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
                s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    captured = {}
    for row in declarations:
        _shape(row, {"path", "role", "sha256", "terminal"})
        if row["role"] not in {
            "producer",
            "validator",
            "test",
            "build",
            "fixture",
        } or row["terminal"] not in {"passed", "failed", "not-run", "not-applicable"}:
            raise ReviewContractError("instrument role or terminal outcome invalid")
        path = root / _relative(row["path"])
        captured[row["path"]] = identity(path)
        if hashlib.sha256(read_bytes(root, row["path"], budget=budget)).hexdigest() != _digest(
            row["sha256"]
        ):
            raise ReviewContractError("instrument byte identity changed")
        if identity(path) != captured[row["path"]]:
            raise ReviewContractError("instrument changed during inventory")
    # Exactly one bounded final source pass. It counts against the same total
    # byte/time budget; no freshness cache or unbounded retry is introduced.
    for row in declarations:
        if (identity(root / row["path"]) != captured[row["path"]]
                or hashlib.sha256(read_bytes(root, row["path"], budget=budget)).hexdigest()
                != row["sha256"]):
            raise ReviewContractError("instrument changed before inventory completion")
    if set(discover_instruments(root, budget=budget)) != discovered:
        raise ReviewContractError("instrument membership changed during inventory")
    for path, before in captured.items():
        _budget_check(budget)
        if identity(root / path) != before:
            raise ReviewContractError("instrument changed at inventory closure")
    _budget_check(budget)
    return sorted(declarations, key=lambda item: item["path"])


def content_checks(
    *, source, rendered, required, attributions, named_entities, ledger_entities
):
    """Mechanical candidates only; judgments remain with the reviewer."""
    _text(source)
    _text(rendered)
    issues = []
    if re.search(
        r"\b(?:TODO|TBD|FIXME)\b|\b(?:will|promise to)\s+(?:add|verify|source|prove)\b",
        source,
        re.I,
    ):
        issues.append("scaffold")
    if any(_text(term) not in rendered for term in _list(required)):
        issues.append("required-content")
    for item in _list(attributions):
        _shape(item, {"claim", "directive"})
        if not item["directive"] or _text(item["claim"]) not in rendered:
            issues.append("attribution-directive")
            break
    if any(_text(name) not in rendered for name in _list(named_entities)):
        issues.append("entity-presence")
    if any(
        name not in named_entities or name not in rendered
        for name in _list(ledger_entities)
    ):
        if "entity-presence" not in issues:
            issues.append("entity-presence")
    return issues


def scorecard(trials):
    _list(trials)
    result = {metric: None for metric in METRICS}
    for trial in trials:
        _shape(trial, set(METRICS))
        for metric in METRICS:
            value = trial[metric]
            values = (
                value.values()
                if metric == "severity_found" and isinstance(value, dict)
                else [value]
            )
            if metric == "severity_found" and not isinstance(value, dict):
                raise ReviewContractError("severity metric must be a count mapping")
            for number in values:
                if (
                    type(number) not in (int, float)
                    or not math.isfinite(number)
                    or number < 0
                ):
                    raise ReviewContractError(
                        "metric must be a finite nonnegative observation"
                    )
            if metric == "severity_found":
                previous = result[metric] or {}
                for severity, count in value.items():
                    _id(severity)
                    previous[severity] = previous.get(severity, 0) + count
                result[metric] = previous
            else:
                result[metric] = (result[metric] or 0) + value
    return {
        **result,
        "known_trials": len(trials),
        "comparative_superiority": "NOT_ESTABLISHED",
    }


def calibration(cases):
    """Diagnose the submitted controls, never the real target's correctness."""
    _unique(cases)
    if not cases:
        raise ReviewContractError(
            "calibration requires actual positive and negative controls"
        )
    kinds = set()
    for row in cases:
        _shape(row, {"id", "control", "expected", "observed"})
        if (
            row["control"] not in {"positive", "negative"}
            or row["expected"] not in {"pass", "fail"}
            or row["observed"] not in {"pass", "fail", "not-run", "error"}
        ):
            raise ReviewContractError("calibration case has an unknown disposition")
        if (row["control"] == "positive") != (row["expected"] == "pass"):
            raise ReviewContractError(
                "positive/negative control expectation is contradictory"
            )
        kinds.add(row["control"])
    valid = kinds == {"positive", "negative"} and all(
        row["expected"] == row["observed"] for row in cases
    )
    return {
        "status": "CALIBRATED_FIXTURE_ONLY" if valid else "INVALID_INSTRUMENT",
        "cases": len(cases),
        "target_correctness": "NOT_ESTABLISHED",
    }


def custody_scope(paths):
    _unique(paths, "path")
    retained, disposable = [], []
    for row in paths:
        _shape(row, {"path", "kind", "disposition", "proof"})
        _relative(row["path"])
        if row["kind"] == "durable":
            if (
                row["disposition"] not in {"present", "deleted", "moved"}
                or not row["proof"]
            ):
                raise ReviewContractError(
                    "durable disposition requires its existing custody owner receipt"
                )
            _text(row["proof"])
            retained.append(row["path"])
        elif row["kind"] == "disposable" and row["disposition"] in {
            "present",
            "removed",
        }:
            disposable.append(row["path"])
        else:
            raise ReviewContractError("path has an unknown custody disposition")
    return {
        "retained_obligations": retained,
        "disposable_paths": disposable,
        "receipt_authentication": "UNVERIFIED",
        "ready": False,
    }


def lifecycle_scopes(states):
    _shape(states, {"exact_session", "aggregate", "communication", "continuity"})
    choices = {
        "exact_session": {"REMOTE_READY", "LOCAL_READY", "BLOCKED", "UNKNOWN"},
        "aggregate": {"READY", "OPEN", "BLOCKED", "UNKNOWN"},
        "communication": {"DELIVERED", "PENDING", "FAILED", "UNKNOWN"},
        "continuity": {"REMOTE_READY", "LOCAL_READY", "BLOCKED", "UNKNOWN"},
    }
    if any(states[key] not in allowed for key, allowed in choices.items()):
        raise ReviewContractError("unknown lifecycle scope status")
    return {**states, "verified_by_this_diagnostic": False}


def corpus_key(entries):
    _unique(entries)
    for row in entries:
        _shape(row, {"id", "sha256", "status"})
        _digest(row["sha256"])
        if row["status"] not in {"unpublished", "published", "withdrawn"}:
            raise ReviewContractError("unknown corpus disposition")
    return hashlib.sha256(
        json.dumps(
            sorted(entries, key=lambda row: row["id"]),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def publication_diagnostics(approved_targets, observations):
    _unique(approved_targets)
    _unique(observations)
    for row in approved_targets:
        _shape(row, {"id", "approved_sha256"})
        _digest(row["approved_sha256"])
    known = {row["id"] for row in approved_targets}
    by_id = {}
    for row in observations:
        _shape(row, {"id", "live_sha256", "observed"})
        if row["id"] not in known or type(row["observed"]) is not bool:
            raise ReviewContractError(
                "observation has an unknown destination or truth value"
            )
        if row["live_sha256"] is not None:
            _digest(row["live_sha256"])
        by_id[row["id"]] = row
    out = []
    for target in approved_targets:
        row = by_id.get(target["id"])
        status = "UNVERIFIED"
        if row and row["observed"] and row["live_sha256"]:
            status = (
                "BYTES_MATCHED"
                if row["live_sha256"] == target["approved_sha256"]
                else "APPROVAL_TARGET_CHANGED"
            )
        out.append(
            {
                "id": target["id"],
                "status": status,
                "authorization": "NOT_GRANTED",
                "native_observation_authenticated": False,
            }
        )
    return out


def independence(record):
    _shape(
        record,
        {
            "reviewer",
            "executor",
            "target_sha256",
            "derived_files",
            "required_files",
            "receipt_source",
        },
    )
    _id(record["reviewer"])
    _id(record["executor"])
    _digest(record["target_sha256"])
    derived = record["derived_files"]
    required = record["required_files"]
    for collection in (derived, required):
        _list(collection)
        if (
            not collection
            or any(not isinstance(p, str) for p in collection)
            or len(collection) != len(set(collection))
        ):
            raise ReviewContractError(
                "independence needs the complete unique input universe"
            )
        for name in collection:
            _relative(name)
    if (
        record["reviewer"] == record["executor"]
        or record["receipt_source"] != "own-observation"
        or set(derived) != set(required)
    ):
        raise ReviewContractError("reviewer provenance is incomplete or inherited")
    return {"structural_independence": True, "native_truth": "UNVERIFIED"}


def saved_outputs(root, outputs, prior_dispositions):
    _files(root, outputs)
    _unique(prior_dispositions, "path")
    for row in prior_dispositions:
        _shape(row, {"path", "disposition"})
        _relative(row["path"])
        if row["disposition"] not in {
            "retained-original",
            "deleted-with-receipt",
            "moved-with-receipt",
        }:
            raise ReviewContractError("prior output custody must remain explicit")
    return {
        "saved": [row["path"] for row in outputs],
        "prior_dispositions": prior_dispositions,
        "historical_custody_authentication": "UNVERIFIED",
    }


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ReviewContractError("duplicate JSON key")
        result[key] = value
    return result


def main(argv=None):
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("--root", type=Path, required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--bundle")
    mode.add_argument("--inventory-manifest")
    mode.add_argument("--discover", action="store_true")
    p.add_argument("--doctor", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.discover:
            result = {
                "instruments": discover_instruments(args.root),
                "executed": 0,
                "authority": "none",
            }
        else:
            name = args.bundle or args.inventory_manifest
            data = json.loads(read_bytes(args.root, name), object_pairs_hook=_pairs)
            result = (
                validate(data, args.root)
                if args.bundle
                else {
                    "inventory": instrument_inventory(args.root, data),
                    "executed": 0,
                    "outcome_authentication": "UNVERIFIED",
                    "authority": "none",
                }
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print("review package refused: " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
