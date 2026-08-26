#!/usr/bin/env python3
"""Create and edit a fail-closed adversarial-review finding ledger.

The ledger is an engagement-owned YAML file. Every mutation validates the complete
document, requires an explicit expected prior state where one exists, writes atomically,
and verifies the bytes read back from disk. A missing finding, duplicate identity,
unrecognised state, or incomplete classification refuses without changing the file.

Commands:

    finding_ledger.py init --resources-root DIR --file FILE --engagement ID
        --principal-outcome TEXT --round-trip-budget N --proportionality TEXT
    finding_ledger.py record-crossing --resources-root DIR --file FILE
        --expected-count N
        --evidence TEXT
    finding_ledger.py add --resources-root DIR --file FILE --id ID --title TEXT --state STATE
        --classification CLASS --authority-label LABEL --provenance-id ID
        --enforcement-outcome TEXT --evidence TEXT [--follow-up-project ID]
    finding_ledger.py transition --resources-root DIR --file FILE --id ID --from-state STATE
        --to-state STATE --evidence TEXT
    finding_ledger.py validate --resources-root DIR --file FILE

Exit codes: 0 changed or valid, 1 refused, 2 invocation or dependency error.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import pathlib
import stat
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only on an incomplete runtime
    yaml = None


SCHEMA = 1
STATES = {
    "open",
    "challenged",
    "repaired-prose",
    "repaired-source",
    "repaired-verified",
    "conceded",
    "awaiting-principal",
}
CLASSIFICATIONS = {"ship-blocking", "ship-improving"}
AUTHORITY_LABELS = {"principal-rule", "agent-heuristic"}

# AGENT HEURISTIC: strict key sets make an unknown schema addition a refusal instead of
# letting one producer write a field that another silently ignores. A future extension
# increments SCHEMA and updates these sets deliberately.
TOP_KEYS = {"schema", "engagement", "findings"}
ENGAGEMENT_KEYS = {
    "id",
    "principal_outcome",
    "principal_courier_round_trips",
    "proportionality",
    "created_at",
}
FINDING_KEYS = {
    "id",
    "title",
    "state",
    "classification",
    "authority",
    "enforcement_outcome",
    "evidence",
    "history",
    "created_at",
}
OPTIONAL_FINDING_KEYS = {"follow_up_project"}
AUTHORITY_KEYS = {"label", "provenance_id"}
HISTORY_KEYS = {"at", "from", "to", "evidence"}
TRIP_HISTORY_KEYS = {"at", "evidence"}

# AGENT HEURISTIC: every successful ledger command repeats one common coverage
# boundary so a schema mutation cannot be mistaken for artifact acceptance.
UNVERIFIED_REMAINDER = (
    "not verified: artifact acceptance, review sufficiency, approval status, "
    "publication, or deployment"
)


class LedgerError(RuntimeError):
    """The requested ledger operation is unsafe or invalid."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def report_success(message: str) -> None:
    print(f"{message}; {UNVERIFIED_REMAINDER}")


def lexical_absolute(path: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.path.abspath(os.path.expanduser(str(path))))


def reject_symlink_components(path: pathlib.Path, label: str) -> None:
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise LedgerError(f"{label} contains a symlink component: {current}")


def validated_resources_root(path: pathlib.Path) -> pathlib.Path:
    root = lexical_absolute(path)
    reject_symlink_components(root, "resources root")
    if not root.is_dir():
        raise LedgerError(f"resources root is not a directory: {root}")
    return root


@contextmanager
def resources_lock(root: pathlib.Path):
    """Serialize the complete read/compare/write transaction on a stable inode."""

    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(root, flags)
    except OSError as exc:
        raise LedgerError(f"could not open resources root safely: {root}: {exc}") from exc
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise LedgerError(f"resources root is not a directory: {root}")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        reject_symlink_components(root, "resources root")
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f"{label} must be a non-empty string")
    return value.strip()


def exact_keys(value: dict, required: set[str], optional: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required - optional)
    if missing or extra:
        raise LedgerError(f"{label} keys invalid: missing={missing}, extra={extra}")


def validate_document(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise LedgerError("ledger root must be a mapping")
    exact_keys(doc, TOP_KEYS, set(), "ledger")
    if doc["schema"] != SCHEMA:
        raise LedgerError(
            f"ledger schema {doc['schema']!r} is not supported; expected {SCHEMA}"
        )

    engagement = doc["engagement"]
    if not isinstance(engagement, dict):
        raise LedgerError("engagement must be a mapping")
    exact_keys(engagement, ENGAGEMENT_KEYS, set(), "engagement")
    nonempty(engagement["id"], "engagement.id")
    nonempty(engagement["principal_outcome"], "engagement.principal_outcome")
    nonempty(engagement["proportionality"], "engagement.proportionality")
    nonempty(engagement["created_at"], "engagement.created_at")
    trips = engagement["principal_courier_round_trips"]
    if not isinstance(trips, dict) or set(trips) != {"budget", "count", "history"}:
        raise LedgerError(
            "engagement.principal_courier_round_trips must contain budget, count, "
            "and history"
        )
    for key in ("budget", "count"):
        if isinstance(trips[key], bool) or not isinstance(trips[key], int) or trips[key] < 0:
            raise LedgerError(f"principal_courier_round_trips.{key} must be >= 0")
    if trips["count"] > trips["budget"]:
        raise LedgerError(
            "principal courier round-trip budget exceeded; the engagement is blocked"
        )
    trip_history = trips["history"]
    if not isinstance(trip_history, list):
        raise LedgerError("principal_courier_round_trips.history must be a list")
    if len(trip_history) != trips["count"]:
        raise LedgerError(
            "principal_courier_round_trips.count must equal the history length"
        )
    for index, event in enumerate(trip_history):
        label = f"principal_courier_round_trips.history[{index}]"
        if not isinstance(event, dict):
            raise LedgerError(f"{label} must be a mapping")
        exact_keys(event, TRIP_HISTORY_KEYS, set(), label)
        nonempty(event["at"], f"{label}.at")
        nonempty(event["evidence"], f"{label}.evidence")

    findings = doc["findings"]
    if not isinstance(findings, list):
        raise LedgerError("findings must be a list")
    seen: set[str] = set()
    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not isinstance(finding, dict):
            raise LedgerError(f"{label} must be a mapping")
        exact_keys(finding, FINDING_KEYS, OPTIONAL_FINDING_KEYS, label)
        finding_id = nonempty(finding["id"], f"{label}.id")
        if finding_id in seen:
            raise LedgerError(f"duplicate finding id: {finding_id}")
        seen.add(finding_id)
        nonempty(finding["title"], f"{label}.title")
        if finding["state"] not in STATES:
            raise LedgerError(f"{label}.state is not recognised: {finding['state']!r}")
        classification = finding["classification"]
        if classification not in CLASSIFICATIONS:
            raise LedgerError(f"{label}.classification is not recognised: {classification!r}")
        if classification == "ship-improving":
            nonempty(finding.get("follow_up_project"), f"{label}.follow_up_project")
        authority = finding["authority"]
        if not isinstance(authority, dict):
            raise LedgerError(f"{label}.authority must be a mapping")
        exact_keys(authority, AUTHORITY_KEYS, set(), f"{label}.authority")
        if authority["label"] not in AUTHORITY_LABELS:
            raise LedgerError(
                f"{label}.authority.label is not recognised: {authority['label']!r}"
            )
        nonempty(authority["provenance_id"], f"{label}.authority.provenance_id")
        nonempty(finding["enforcement_outcome"], f"{label}.enforcement_outcome")
        nonempty(finding["evidence"], f"{label}.evidence")
        nonempty(finding["created_at"], f"{label}.created_at")
        history = finding["history"]
        if not isinstance(history, list) or not history:
            raise LedgerError(f"{label}.history must be a non-empty list")
        previous_state: str | None = None
        for hindex, event in enumerate(history):
            hlabel = f"{label}.history[{hindex}]"
            if not isinstance(event, dict):
                raise LedgerError(f"{hlabel} must be a mapping")
            exact_keys(event, HISTORY_KEYS, set(), hlabel)
            nonempty(event["at"], f"{hlabel}.at")
            if event["from"] is not None and event["from"] not in STATES:
                raise LedgerError(f"{hlabel}.from is not recognised")
            if event["to"] not in STATES:
                raise LedgerError(f"{hlabel}.to is not recognised")
            nonempty(event["evidence"], f"{hlabel}.evidence")
            if hindex == 0:
                if event["from"] is not None:
                    raise LedgerError(f"{hlabel}.from must be null for the first event")
            elif event["from"] != previous_state:
                raise LedgerError(
                    f"{hlabel}.from does not match the previous terminal state"
                )
            if event["from"] is not None and event["from"] == event["to"]:
                raise LedgerError(f"{hlabel} must change state")
            previous_state = event["to"]
        if history[-1]["to"] != finding["state"]:
            raise LedgerError(
                f"{label}.state does not match its terminal history event"
            )
        if history[-1]["evidence"] != finding["evidence"]:
            raise LedgerError(
                f"{label}.evidence does not match its terminal history event"
            )
    return doc


def ensure_path(
    path: pathlib.Path, resources_root: pathlib.Path, *, must_exist: bool
) -> pathlib.Path:
    path = lexical_absolute(path)
    try:
        relative = path.relative_to(resources_root)
    except ValueError as exc:
        raise LedgerError(
            f"ledger path is outside the declared resources root: {path}"
        ) from exc
    if not relative.parts:
        raise LedgerError("ledger path must name a file beneath the resources root")
    reject_symlink_components(path, "ledger path")
    if path.suffix not in {".yaml", ".yml"}:
        raise LedgerError(f"ledger path must end in .yaml or .yml: {path}")
    if path.is_symlink():
        raise LedgerError(f"refusing a symlink ledger path: {path}")
    if must_exist and not path.is_file():
        raise LedgerError(f"ledger is not a file: {path}")
    if not must_exist and path.exists():
        raise LedgerError(f"ledger already exists: {path}")
    if not path.parent.is_dir():
        raise LedgerError(f"ledger parent is not a directory: {path.parent}")
    return path


def load(path: pathlib.Path, resources_root: pathlib.Path) -> dict:
    path = ensure_path(path, resources_root, must_exist=True)
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise LedgerError(f"could not parse {path}: {exc}") from exc
    return validate_document(doc)


def serialize(doc: dict) -> str:
    validate_document(doc)
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def atomic_write(
    path: pathlib.Path,
    doc: dict,
    resources_root: pathlib.Path,
    *,
    create: bool = False,
) -> None:
    path = ensure_path(path, resources_root, must_exist=not create)
    text = serialize(doc)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    )
    temporary = pathlib.Path(handle.name)
    try:
        with handle as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        written = path.read_text(encoding="utf-8")
        if written != text:
            raise LedgerError(f"post-write byte verification failed: {path}")
        validate_document(yaml.safe_load(written))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def command_init(args: argparse.Namespace) -> None:
    if args.round_trip_budget < 0:
        raise LedgerError("round-trip-budget must be >= 0")
    stamp = now()
    doc = {
        "schema": SCHEMA,
        "engagement": {
            "id": nonempty(args.engagement, "engagement"),
            "principal_outcome": nonempty(args.principal_outcome, "principal-outcome"),
            "principal_courier_round_trips": {
                "budget": args.round_trip_budget,
                "count": 0,
                "history": [],
            },
            "proportionality": nonempty(args.proportionality, "proportionality"),
            "created_at": stamp,
        },
        "findings": [],
    }
    atomic_write(args.file, doc, args.resources_root, create=True)
    report_success(f"initialized {args.file}")


def command_record_crossing(args: argparse.Namespace) -> None:
    doc = load(args.file, args.resources_root)
    trips = doc["engagement"]["principal_courier_round_trips"]
    if args.expected_count != trips["count"]:
        raise LedgerError(
            f"principal courier crossing count is {trips['count']}, not expected "
            f"{args.expected_count}; re-read the ledger before retrying"
        )
    if trips["count"] >= trips["budget"]:
        raise LedgerError(
            "principal courier round-trip budget would be exceeded; the engagement "
            "is blocked"
        )
    trips["count"] += 1
    trips["history"].append(
        {"at": now(), "evidence": nonempty(args.evidence, "evidence")}
    )
    atomic_write(args.file, doc, args.resources_root)
    report_success(
        "recorded principal courier crossing "
        f"{trips['count']}/{trips['budget']}"
    )


def command_add(args: argparse.Namespace) -> None:
    doc = load(args.file, args.resources_root)
    if any(item["id"] == args.id for item in doc["findings"]):
        raise LedgerError(f"finding id already exists: {args.id}")
    if args.classification == "ship-improving" and not args.follow_up_project:
        raise LedgerError(
            "ship-improving findings require --follow-up-project; they do not extend "
            "the current delivery"
        )
    stamp = now()
    finding = {
        "id": nonempty(args.id, "id"),
        "title": nonempty(args.title, "title"),
        "state": args.state,
        "classification": args.classification,
        "authority": {
            "label": args.authority_label,
            "provenance_id": nonempty(args.provenance_id, "provenance-id"),
        },
        "enforcement_outcome": nonempty(
            args.enforcement_outcome, "enforcement-outcome"
        ),
        "evidence": nonempty(args.evidence, "evidence"),
        "history": [
            {"at": stamp, "from": None, "to": args.state, "evidence": args.evidence}
        ],
        "created_at": stamp,
    }
    if args.follow_up_project:
        finding["follow_up_project"] = nonempty(
            args.follow_up_project, "follow-up-project"
        )
    doc["findings"].append(finding)
    atomic_write(args.file, doc, args.resources_root)
    report_success(f"added {args.id} as {args.classification}/{args.state}")


def command_transition(args: argparse.Namespace) -> None:
    doc = load(args.file, args.resources_root)
    matches = [item for item in doc["findings"] if item["id"] == args.id]
    if len(matches) != 1:
        raise LedgerError(f"expected exactly one finding {args.id!r}, found {len(matches)}")
    finding = matches[0]
    if finding["state"] != args.from_state:
        raise LedgerError(
            f"{args.id} is {finding['state']!r}, not expected {args.from_state!r}; "
            "re-read the ledger before retrying"
        )
    if args.to_state == args.from_state:
        raise LedgerError("transition must change state")
    evidence = nonempty(args.evidence, "evidence")
    finding["state"] = args.to_state
    finding["evidence"] = evidence
    finding["history"].append(
        {
            "at": now(),
            "from": args.from_state,
            "to": args.to_state,
            "evidence": evidence,
        }
    )
    atomic_write(args.file, doc, args.resources_root)
    report_success(f"transitioned {args.id}: {args.from_state} -> {args.to_state}")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", allow_abbrev=False)
    init.add_argument("--resources-root", required=True, type=pathlib.Path)
    init.add_argument("--file", required=True, type=pathlib.Path)
    init.add_argument("--engagement", required=True)
    init.add_argument("--principal-outcome", required=True)
    init.add_argument("--round-trip-budget", required=True, type=int)
    init.add_argument("--proportionality", required=True)

    crossing = sub.add_parser("record-crossing", allow_abbrev=False)
    crossing.add_argument("--resources-root", required=True, type=pathlib.Path)
    crossing.add_argument("--file", required=True, type=pathlib.Path)
    crossing.add_argument("--expected-count", required=True, type=int)
    crossing.add_argument("--evidence", required=True)

    add = sub.add_parser("add", allow_abbrev=False)
    add.add_argument("--resources-root", required=True, type=pathlib.Path)
    add.add_argument("--file", required=True, type=pathlib.Path)
    add.add_argument("--id", required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--state", required=True, choices=sorted(STATES))
    add.add_argument("--classification", required=True, choices=sorted(CLASSIFICATIONS))
    add.add_argument("--authority-label", required=True, choices=sorted(AUTHORITY_LABELS))
    add.add_argument("--provenance-id", required=True)
    add.add_argument("--enforcement-outcome", required=True)
    add.add_argument("--evidence", required=True)
    add.add_argument("--follow-up-project")

    transition = sub.add_parser("transition", allow_abbrev=False)
    transition.add_argument("--resources-root", required=True, type=pathlib.Path)
    transition.add_argument("--file", required=True, type=pathlib.Path)
    transition.add_argument("--id", required=True)
    transition.add_argument("--from-state", required=True, choices=sorted(STATES))
    transition.add_argument("--to-state", required=True, choices=sorted(STATES))
    transition.add_argument("--evidence", required=True)

    validate = sub.add_parser("validate", allow_abbrev=False)
    validate.add_argument("--resources-root", required=True, type=pathlib.Path)
    validate.add_argument("--file", required=True, type=pathlib.Path)
    return ap


def main(argv: list[str] | None = None) -> int:
    if yaml is None:
        print("finding-ledger error: PyYAML is required", file=sys.stderr)
        return 2
    ap = parser()
    args = ap.parse_args(argv)
    try:
        args.resources_root = validated_resources_root(args.resources_root)
        args.file = lexical_absolute(args.file)
        with resources_lock(args.resources_root):
            if args.command == "init":
                command_init(args)
            elif args.command == "record-crossing":
                command_record_crossing(args)
            elif args.command == "add":
                command_add(args)
            elif args.command == "transition":
                command_transition(args)
            else:
                doc = load(args.file, args.resources_root)
                report_success(
                    f"valid {args.file}: schema {doc['schema']}, "
                    f"{len(doc['findings'])} finding(s)"
                )
    except LedgerError as exc:
        print(f"finding-ledger refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
