"""Exact project-artifact succession, owned by context_edit.

Receipts describe custody and declared item accounting, never action authority.
The existing record transaction owns live multi-file changes and crash recovery.
"""

from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import time

import record_transaction as rt

MAX_ITEMS = 256
MAX_REFS = 1024
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 256
MAX_ARTIFACT_ENTRIES = 4096
SCAN_SECONDS = 30
READ_SECONDS = 10
MARKER = "synthesis-packet-retired"


class SuccessionError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    try:
        return (
            json.dumps(
                value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
            )
            + "\n"
        ).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise SuccessionError("invalid bounded JSON value") from exc


def frozen_request(value):
    raw = encoded(value)
    if len(raw) > rt.MAX_MANIFEST_BYTES:
        raise SuccessionError("request exceeds bounded record capacity")
    return json.loads(raw, object_pairs_hook=rt._unique)


def canonical_digest(value):
    try:
        return digest(
            (
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
                + "\n"
            ).encode()
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise SuccessionError("invalid canonical source value") from exc


def runtime_spec(spec):
    value = dict(spec)
    title = str(spec.get("title", ""))
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "packet"
    value.setdefault("storage_key", slug)
    value.setdefault("filters", [])
    return value


def exact(value, fields, required=None):
    if (
        not isinstance(value, dict)
        or set(value) - set(fields)
        or not set(required or fields) <= set(value)
    ):
        raise SuccessionError("invalid or unknown succession fields")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value
    ):
        raise SuccessionError("bounded explicit item identity required")
    return value


class Reader:
    def __init__(self, project):
        self.project = rt._path(project)
        self.cache = {}
        self.total = 0
        self.count = 0
        self.deadline = time.monotonic() + READ_SECONDS

    def read(self, ref, *, anchor=False, _allow_changed_hash=False):
        exact(ref, {"path", "sha256", "anchor"}, {"path", "sha256"})
        path = ref["path"]
        sha = ref["sha256"]
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or path != Path(path).as_posix()
            or not isinstance(sha, str)
            or not re.fullmatch("[0-9a-f]{64}", sha)
        ):
            raise SuccessionError("exact project-relative source and sha256 required")
        target = rt._path(self.project / path, self.project)
        if rt.STORE in target.relative_to(self.project).parts:
            raise SuccessionError("transaction internals are not succession inputs")
        self.count += 1
        if self.count > MAX_REFS or time.monotonic() > self.deadline:
            raise SuccessionError("bounded source observation exhausted")
        if path not in self.cache:
            raw, snapshot = rt._snapshot(target)
            self.total += len(raw)
            if self.total > MAX_SOURCE_BYTES:
                raise SuccessionError("source byte bound exceeded")
            self.cache[path] = (raw, snapshot)
        raw, _ = self.cache[path]
        if not _allow_changed_hash and digest(raw) != sha:
            raise SuccessionError("source hash mismatch")
        if anchor or "anchor" in ref:
            text = ref.get("anchor")
            if (
                not isinstance(text, str)
                or not text
                or len(text) > 4096
                or raw.count(text.encode()) != 1
            ):
                raise SuccessionError("one exact provenance anchor required")
        return raw

    def unchanged(self):
        for path, (raw, meta) in self.cache.items():
            if time.monotonic() > self.deadline or not rt._matches(
                self.project / path, meta
            ):
                raise SuccessionError("source changed or observation expired")


class PacketInventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []
        self.active = False
        self.found = 0

    def handle_starttag(self, tag, attrs):
        if tag == "script" and any(k == "id" and v == "spec" for k, v in attrs):
            names = [name for name, _ in attrs]
            if len(names) != len(set(names)):
                raise SuccessionError("duplicate packet inventory attributes")
            if self.active or dict(attrs).get("type") != "application/json":
                raise SuccessionError("ambiguous packet inventory")
            self.found += 1
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def inventory(reader, item):
    exact(
        item,
        {"path", "sha256", "format", "declared_count", "spec"},
        {"path", "sha256", "format", "declared_count"},
    )
    if (
        type(item["declared_count"]) is not int
        or not 0 <= item["declared_count"] <= MAX_ITEMS
    ):
        raise SuccessionError("invalid declared inventory count")
    raw = reader.read({k: item[k] for k in ("path", "sha256")})
    text = raw.decode("utf-8")
    if item["format"] == "packet-html":
        parser = PacketInventory()
        parser.feed(text)
        parser.close()
        if parser.found != 1 or parser.active:
            raise SuccessionError(
                "legacy inventory UNKNOWN: need one complete embedded JSON spec"
            )
        data = json.loads("".join(parser.parts), object_pairs_hook=rt._unique)
    elif item["format"] == "json-rows":
        data = json.loads(text, object_pairs_hook=rt._unique)
    else:
        raise SuccessionError(
            "unsupported inventory: do not infer a denominator from prose"
        )
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("rows"), list)
        or not 1 <= len(data["rows"]) <= MAX_ITEMS
    ):
        raise SuccessionError("bounded source rows inventory required")
    ids = [
        identifier(row.get("id")) if isinstance(row, dict) else identifier(None)
        for row in data["rows"]
    ]
    if len(set(ids)) != len(ids):
        raise SuccessionError("duplicate source inventory identity")
    payload_digest = canonical_digest(data)
    if "spec" in item:
        if item["format"] != "packet-html":
            raise SuccessionError("filed spec belongs only to a packet inventory")
        original = json.loads(reader.read(item["spec"]), object_pairs_hook=rt._unique)
        if not isinstance(original, dict) or runtime_spec(original) != data:
            raise SuccessionError(
                "filed spec differs from the actual embedded inventory"
            )
        data = original
    return ids, data, payload_digest


def decision_status(raw, spec, row_id):
    """Use the existing recorder's exact-spec contract, never authenticate authors."""
    try:
        value = json.loads(raw, object_pairs_hook=rt._unique)
    except (ValueError, UnicodeError, RecursionError):
        return "historical-record-unverified"
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        return "historical-record-unverified"
    scripts = Path(__file__).resolve().parents[2] / "synthesis-decision-packet/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import record_rulings

    rulings = value.get("rulings")
    if not isinstance(rulings, list) or not 1 <= len(rulings) <= MAX_ITEMS:
        raise SuccessionError("bounded recorded rulings required")
    state = {}
    try:
        for row in rulings:
            if not isinstance(row, dict):
                raise SuccessionError("recorded ruling must be an object")
            rid = identifier(row.get("id"))
            if rid in state:
                raise SuccessionError("duplicate recorded ruling identity")
            state[rid] = {
                "choice": row.get("choice_value"),
                "note": row.get("note") or "",
                "bulk": row.get("accepted_in_bulk"),
            }
        expected = record_rulings.parse_summary(
            record_rulings.compose_summary(spec, state), spec
        )
        # Python equality conflates bool/int/float values. Canonical JSON keeps
        # those wire types distinct, including nested ruling and binding fields.
        if any(encoded(value.get(key)) != encoded(expected[key]) for key in expected):
            raise SuccessionError(
                "recorded ruling differs from exact spec, choices, or counts"
            )
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise SuccessionError("invalid bound ruling: " + str(exc)) from exc
    return (
        "bound-answer-unverified"
        if state.get(row_id, {}).get("choice") is not None
        else "unanswered"
    )


def _review(project, request, *, reader_type=Reader):
    exact(
        request,
        {"schema", "kind", "inventory", "items", "context_anchor", "context_max_lines"},
    )
    if (
        type(request["schema"]) is not int
        or request["schema"] != 1
        or request["kind"] not in ("packet-retirement", "transfer")
    ):
        raise SuccessionError("unknown succession contract")
    if (
        not isinstance(request["context_anchor"], str)
        or not request["context_anchor"]
        or len(request["context_anchor"]) > 4096
    ):
        raise SuccessionError("context anchor required")
    if (
        type(request["context_max_lines"]) is not int
        or not 1 <= request["context_max_lines"] <= 150
    ):
        raise SuccessionError("explicit bounded context line budget required")
    reader = reader_type(project)
    ids, spec, payload_digest = inventory(reader, request["inventory"])
    if request["kind"] == "packet-retirement" and (
        request["inventory"]["format"] != "packet-html"
        or not request["inventory"]["path"].startswith("resources/artifacts/")
        or not request["inventory"]["path"].endswith(".html")
    ):
        raise SuccessionError("retirement requires the actual live artifact HTML")
    items = request["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise SuccessionError("bounded reconciliation items required")
    seen = set()
    obligations = set()
    out = []
    grades = []
    for row in items:
        exact(row, {"id", "destination", "decision", "proof", "obligations"})
        rid = identifier(row["id"])
        if rid in seen:
            raise SuccessionError("duplicate reconciliation identity")
        seen.add(rid)
        reader.read(row["destination"], anchor=True)
        decision = row["decision"]
        state = (
            decision_status(reader.read(decision, anchor=True), spec, rid)
            if decision is not None
            else "unanswered"
        )
        if not isinstance(row["proof"], list) or len(row["proof"]) > 16:
            raise SuccessionError("bounded proof sources required")
        for proof in row["proof"]:
            exact(proof, {"source", "kind"})
            if proof["kind"] not in ("primary", "narrative", "unknown"):
                raise SuccessionError("invalid claimed evidence kind")
            reader.read(proof["source"], anchor=True)
            grades.append(proof["kind"])
        obligations_here = row["obligations"]
        if not isinstance(obligations_here, list) or len(obligations_here) > MAX_ITEMS:
            raise SuccessionError("bounded obligations required")
        if state != "bound-answer-unverified" and not obligations_here:
            raise SuccessionError(
                "unanswered or unverified historical item requires surviving obligation"
            )
        for obligation in obligations_here:
            exact(obligation, {"id", "destination"})
            oid = identifier(obligation["id"])
            if oid in obligations:
                raise SuccessionError("duplicate obligation identity")
            obligations.add(oid)
            reader.read(obligation["destination"], anchor=True)
        out.append(
            {
                **row,
                "decision_status": state,
                "proof_status": "evidence-present-unverified"
                if row["proof"]
                else "missing",
                "readiness": "requires-owner-review",
            }
        )
    result = {
        "schema": 1,
        "kind": request["kind"],
        "inventory": request["inventory"],
        "inventory_ids": ids,
        "inventory_count": len(ids),
        "declared_count_matches": request["inventory"]["declared_count"] == len(ids),
        "reconciled_ids": sorted(seen),
        "missing_items": sorted(set(ids) - seen),
        "extra_items": sorted(seen - set(ids)),
        "identity_complete": set(ids) == seen,
        "items": out,
        "unresolved_obligations": sorted(obligations),
        "proof_status": (
            "missing"
            if not grades
            else "narrative-only"
            if set(grades) == {"narrative"}
            else "evidence-present-unverified"
        ),
        "authorization_granted": False,
        "completion_established": False,
        "obligation_coverage": "declared obligations only; unrecorded commitments are not established",
        "execution_status": "not-assessed",
        "readiness": "requires-owner-review",
        "request_sha256": digest(encoded(request)),
        "request": request,
        "inventory_coverage": "exact declared structured source; not arbitrary prose completeness",
    }
    if request["kind"] == "packet-retirement":
        # This digest binds an observed payload, not a newly invented generator signature.
        canonical = (
            json.dumps(
                spec,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
        result["retired_spec_sha256"] = digest(canonical)
        result["retired_payload_sha256"] = payload_digest
    reader.unchanged()
    return result, reader


def review(project, request):
    with rt.managed(project):
        return _review(project, frozen_request(request))[0]


def tombstone(record, archive):
    return (
        '<!doctype html>\n<meta charset="utf-8">\n<title>Retired decision interface</title>\n'
        f"<!-- {MARKER} record:{record} -->\n"
        "<h1>Documentary record</h1><p>This interface is retired. It collects no answers and grants no authority.</p>\n"
        f'<p><a href="../../{html.escape(archive, quote=True)}">Exact original bytes</a> · '
        f'<a href="{html.escape(Path(record).name, quote=True)}">Surviving obligations and provenance</a></p>\n'
    ).encode()


def _preserve(path, data):
    if path.exists() or path.is_symlink():
        if rt._snapshot(path)[0] != data:
            raise SuccessionError("existing custody differs; preserve and reconcile")
    else:
        rt._new_file(path, data)
        rt._sync_dir(path.parent)


def apply(project, request, *, board, native_payload, dry_run=False):
    import context_edit

    project = rt._path(project)
    request = frozen_request(request)
    with rt.managed(project, exclusive=True):
        request_sha = digest(encoded(request))
        record = f"resources/artifacts/{request_sha}-succession.json"
        path = rt._path(project / record, project)
        if path.exists():
            existing = rt._read_json(path)[0]
            if existing.get("status") == "committed":
                if existing.get("request") != request:
                    raise SuccessionError("existing succession request differs")
                rt._authority(
                    project, board, native_payload, [path, project / "CONTEXT.md"]
                )
                validate_record(project, path)
                return {"status": "committed", "record": record, "changed": False}
        result, reader = _review(project, request)
        if not result["identity_complete"]:
            raise SuccessionError("incomplete item identity reconciliation")
        result.update(status="committed", record=record)
        request_files = []
        custody = []
        if request["kind"] == "packet-retirement":
            source = request["inventory"]["path"]
            raw = reader.cache[source][0]
            archive = f"resources/archive/retired-decision-packets/{digest(raw)}.html"
            archive_path = rt._path(project / archive, project)
            if not archive_path.parent.is_dir():
                raise SuccessionError(
                    "existing exact documentary archive directory required"
                )
            result["archive"] = {"path": archive, "sha256": digest(raw)}
            page = tombstone(record, archive)
            result["tombstone_sha256"] = digest(page)
            custody.append((archive_path, raw))
            request_files.append(
                {
                    "file": source,
                    "edits": [
                        {
                            "op": "replace",
                            "anchor": raw.decode("utf-8"),
                            "replacement": page.decode(),
                        }
                    ],
                }
            )
        summary = (
            f"Succession record: [{request['kind']}]({record}). "
            f"{len(result['unresolved_obligations'])} declared obligations carried; execution and approval require owner verification.\n\n"
        )
        context = project / "CONTEXT.md"
        old, context_meta = rt._snapshot(context)
        edit = {
            "op": "insert-before",
            "anchor": request["context_anchor"],
            "text": summary,
        }
        after = context_edit._edit_in_memory(old.decode(), edit)
        context_edit._check_budget(after, request["context_max_lines"], context)
        context_edit._coherence_gate(context, old.decode(), after, False, False, False)
        future = {"CONTEXT.md": after.encode()}
        if request["kind"] == "packet-retirement":
            future[source] = page
        for item in result["items"]:
            for ref in [item["destination"]] + [
                o["destination"] for o in item["obligations"]
            ]:
                if (
                    ref["path"] in future
                    and future[ref["path"]].count(ref["anchor"].encode()) != 1
                ):
                    raise SuccessionError(
                        "retirement would remove or duplicate a surviving obligation destination"
                    )
        prepared = {
            "schema": 1,
            "status": "prepared",
            "request_sha256": result["request_sha256"],
            "request": request,
        }
        final = encoded(result)
        initial = encoded(prepared)
        snapshots = []
        custody_dir = rt._path(
            project / "resources/archive/succession-sources", project
        )
        if not custody_dir.parent.is_dir():
            raise SuccessionError("existing project archive parent required")
        for source, (raw, _) in reader.cache.items():
            target = (
                project / result["archive"]["path"]
                if result.get("archive") and source == request["inventory"]["path"]
                else custody_dir / (digest(raw) + ".bin")
            )
            snapshots.append(
                {
                    "source_path": source,
                    "archive_path": str(target.relative_to(project)),
                    "sha256": digest(raw),
                }
            )
            if target not in [p for p, _ in custody]:
                custody.append((target, raw))
        result["custody"] = snapshots
        final = encoded(result)
        if len(final) > rt.MAX_MANIFEST_BYTES:
            raise SuccessionError("succession record exceeds bound")
        custody.append((path, initial))
        authority_paths = (
            [p for p, _ in custody]
            + [project / f["file"] for f in request_files]
            + [context, custody_dir]
        )
        rt._authority(project, board, native_payload, authority_paths)
        reader.unchanged()
        if not rt._matches(context, context_meta):
            raise SuccessionError("context changed during preflight")
        if dry_run:
            return {
                "status": "dry-run",
                "record": record,
                "changed": False,
                "review": result,
            }
        if not custody_dir.exists():
            parent = os.open(
                rt._path(custody_dir.parent),
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            )
            try:
                os.mkdir(custody_dir.name, 0o700, dir_fd=parent)
                os.fsync(parent)
                info = os.stat(custody_dir.name, dir_fd=parent, follow_symlinks=False)
                current = rt._path(custody_dir).stat()
                if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                    raise SuccessionError("custody directory changed")
            finally:
                os.close(parent)
        for target, data in custody:
            _preserve(target, data)
        reader.unchanged()
        request_files.extend(
            [
                {
                    "file": record,
                    "edits": [
                        {
                            "op": "replace",
                            "anchor": initial.decode(),
                            "replacement": final.decode(),
                        }
                    ],
                },
                {
                    "file": "CONTEXT.md",
                    "edits": [edit],
                    "max_lines": request["context_max_lines"],
                },
            ]
        )
        for target in request_files:
            file = target["file"]
            target["expected_sha256"] = (
                digest(initial)
                if file == record
                else context_meta["sha256"]
                if file == "CONTEXT.md"
                else reader.cache[file][1]["sha256"]
            )
        result_commit = context_edit.apply_transaction(
            project, request_files, board=board, native_payload=native_payload
        )
        validate_record(project, path)
        return {**result_commit, "record": record}


def validate_record(project, path):
    project = rt._path(project)
    path = rt._path(path, project)
    with rt.managed(project):
        value, _ = rt._read_json(rt._path(path, rt._path(project)))
        if value.get("status") != "committed":
            raise SuccessionError(
                "succession is prepared or incomplete; recovery required"
            )
        request = value.get("request")
        if not isinstance(request, dict):
            raise SuccessionError("succession request missing")
        snapshots = value.get("custody")
        if not isinstance(snapshots, list) or not 1 <= len(snapshots) <= MAX_REFS:
            raise SuccessionError("bounded source custody missing")
        mapping = {}
        for member in snapshots:
            exact(member, {"source_path", "archive_path", "sha256"})
            if (
                not isinstance(member["source_path"], str)
                or member["source_path"] in mapping
            ):
                raise SuccessionError("duplicate custody source")
            if not isinstance(member["sha256"], str) or not re.fullmatch(
                "[0-9a-f]{64}", member["sha256"]
            ):
                raise SuccessionError("invalid custody hash")
            archive = member["archive_path"]
            allowed = (
                "resources/archive/succession-sources/" + member["sha256"] + ".bin"
            )
            retired = (
                "resources/archive/retired-decision-packets/"
                + member["sha256"]
                + ".html"
            )
            if archive not in (allowed, retired):
                raise SuccessionError("custody archive namespace mismatch")
            mapping[member["source_path"]] = member
        observed = set()

        class ArchivedReader(Reader):
            def read(self, ref, **kwargs):
                member = mapping.get(ref.get("path"))
                if member is None or member["sha256"] != ref.get("sha256"):
                    raise SuccessionError("missing or changed custody membership")
                observed.add(ref["path"])
                return super().read({**ref, "path": member["archive_path"]}, **kwargs)

        # Pass the reader explicitly rather than mutating module globals.
        verified, _ = _review_with_reader(project, request, ArchivedReader)
        if observed != set(mapping):
            raise SuccessionError("unreferenced custody members")
        allowed = set(verified) | {"status", "record", "custody"}
        if value.get("kind") == "packet-retirement":
            allowed |= {"archive", "tombstone_sha256"}
        if set(value) != allowed:
            raise SuccessionError("unknown or missing committed fields")
        for key in verified:
            if value.get(key) != verified[key]:
                raise SuccessionError("succession derived data changed")
        record = str(Path(path).relative_to(Path(project)))
        if (
            value.get("record") != record
            or Path(record).name != value["request_sha256"] + "-succession.json"
        ):
            raise SuccessionError("succession record path mismatch")
        if value["kind"] == "packet-retirement":
            source = mapping[request["inventory"]["path"]]
            if value.get("archive") != {
                "path": source["archive_path"],
                "sha256": source["sha256"],
            }:
                raise SuccessionError("retirement archive differs from exact custody")
            expected = tombstone(record, value["archive"]["path"])
            actual = rt._snapshot(Path(project) / request["inventory"]["path"])[0]
            if actual != expected or value.get("tombstone_sha256") != digest(actual):
                raise SuccessionError("retired interface or binding changed")
        if record not in rt._snapshot(Path(project) / "CONTEXT.md")[0].decode():
            raise SuccessionError("working context lost succession pointer")
        changed = False
        current = Reader(project)
        for item in value["items"]:
            refs = [item["destination"]] + [
                o["destination"] for o in item["obligations"]
            ]
            for ref in refs:
                raw = current.read(ref, anchor=True, _allow_changed_hash=True)
                changed = changed or digest(raw) != ref["sha256"]
        current.unchanged()
        return {
            **value,
            "current_destinations": "changed-requires-review"
            if changed
            else "exact-observed-snapshot",
        }


def _review_with_reader(project, request, reader_type):
    return _review(project, request, reader_type=reader_type)


def artifact_paths(project):
    folder = rt._path(Path(project) / "resources/artifacts", rt._path(project))
    if not folder.exists():
        return []
    deadline = time.monotonic() + READ_SECONDS
    result = []
    with os.scandir(folder) as entries:
        for entry in entries:
            if len(result) >= MAX_ARTIFACT_ENTRIES or time.monotonic() > deadline:
                raise SuccessionError("artifact enumeration bound exceeded")
            result.append(Path(entry.path))
    return sorted(result)


def records(project):
    paths = [p for p in artifact_paths(project) if p.name.endswith("-succession.json")]
    if len(paths) > MAX_RECORDS:
        raise SuccessionError("succession inventory bound exceeded")
    return paths


def packet_pages(project):
    return [
        p for p in artifact_paths(project) if "packet" in p.name and p.suffix == ".html"
    ]


def assert_active_spec(directory, spec_sha256, payload_sha256=None):
    directory = Path(directory)
    if directory.name != "artifacts" or directory.parent.name != "resources":
        return
    project = directory.parent.parent
    with rt.managed(project):
        deadline = time.monotonic() + SCAN_SECONDS
        for path in records(project):
            if time.monotonic() > deadline:
                raise SuccessionError("succession scan time bound exceeded")
            value = validate_record(project, path)
            if time.monotonic() > deadline:
                raise SuccessionError("succession scan time bound exceeded")
            if (
                value.get("retired_spec_sha256") == spec_sha256
                or payload_sha256 is not None
                and value.get("retired_payload_sha256") == payload_sha256
            ):
                raise SuccessionError(
                    "retired packet is documentary; build a new exact spec from surviving obligations"
                )
