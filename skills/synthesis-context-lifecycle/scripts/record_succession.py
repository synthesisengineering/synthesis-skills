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
    def __init__(self, project, *, budget=None):
        self.budget = budget
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
        if self.budget is not None:
            self.budget['refs'] += 1
            if self.budget['refs'] > MAX_REFS or time.monotonic() > self.budget['deadline']:
                raise SuccessionError('aggregate material observation bound exceeded')
        if self.count > MAX_REFS or time.monotonic() > self.deadline:
            raise SuccessionError("bounded source observation exhausted")
        if path not in self.cache:
            raw, snapshot = rt._snapshot(target)
            self.total += len(raw)
            if self.budget is not None:
                self.budget['bytes'] += len(raw)
                if self.budget['bytes'] > MAX_SOURCE_BYTES:
                    raise SuccessionError('aggregate material byte bound exceeded')
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
    if not isinstance(request, dict):
        raise SuccessionError('succession request must be an object')
    if request.get('kind') == 'material-context':
        return _material_review(project, request, reader_type=reader_type)
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
                if request['kind'] == 'material-context':
                    # Historical custody can verify after inputs change; a new
                    # application of the old generation must still refuse.
                    _review(project, request)
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
            for ref in _material_refs(item):
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
        admission = rt._authority(project, board, native_payload, authority_paths)
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
        if request['kind'] == 'material-context':
            # Publish a discoverable prepared record before auxiliary custody.
            # It remains explicitly pending if preparation is interrupted.
            custody.sort(key=lambda pair: pair[0] != path)
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
            project, request_files, board=board, native_payload=native_payload,
            **({'source_custody': [{'file': source, 'expected': meta}
                for source, (_, meta) in reader.cache.items()
                if source not in {row['file'] for row in request_files}],
                'expected_claim_hash': admission['claim_hash']}
                if request['kind'] == 'material-context' else {})
        )
        validate_record(project, path)
        return {**result_commit, "record": record}


def validate_record(project, path, *, _budget=None, _navigation=None):
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
            def __init__(self, project):
                super().__init__(project, budget=_budget)

            def read(self, ref, **kwargs):
                exact(ref, {'path', 'sha256', 'anchor'}, {'path', 'sha256'})
                if not isinstance(ref['path'], str):
                    raise SuccessionError('custody source path must be a string')
                member = mapping.get(ref['path'])
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
        if value["kind"] != "material-context" and record not in rt._snapshot(Path(project) / "CONTEXT.md")[0].decode():
            raise SuccessionError("working context lost succession pointer")
        changed = False
        current = Reader(project, budget=_budget)
        for item in value["items"]:
            refs = list(_material_refs(item))
            for ref in refs:
                try:
                    raw = current.read(ref, anchor=True, _allow_changed_hash=True)
                    changed = changed or digest(raw) != ref['sha256']
                except (OSError, ValueError, RuntimeError):
                    if value['kind'] != 'material-context':
                        raise
                    changed = True
        if value['kind'] == 'material-context':
            live_refs = [value['inventory']]
            live_refs = [{k: r[k] for k in ('path', 'sha256')} for r in live_refs]
            live_refs += [r['source'] for r in value['selected_inputs'] if r['source'] is not None]
            if request['review'] is not None:
                live_refs.append(request['review'])
            if value.get('review_evidence'):
                live_refs += [value['review_evidence']['reviewer'], value['review_evidence']['plan'], *value['review_evidence']['earlier_decisions']]
            for ref in live_refs:
                try:
                    observed = current.read(ref, anchor='anchor' in ref, _allow_changed_hash=True)
                    changed = changed or digest(observed) != ref['sha256']
                except (OSError, ValueError, RuntimeError):
                    changed = True
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

# Material capture is a versioned succession contract, not a lifecycle ledger.
MATERIAL_ASPECTS = frozenset({'facts', 'rationale', 'condition', 'uncertainty'})
MATERIAL_KINDS = frozenset({'fact', 'decision', 'constraint', 'commitment', 'risk', 'question', 'amendment', 'cancellation', 'nonmaterial'})
MATERIAL_ACTIVE = frozenset({'open', 'amended', 'unknown'})


def record_request(value):
    """Validate the record envelope before any consumer dispatches on kind.

    Full committed-field and custody validation remains validate_record's job.
    A malformed or unobserved record is never a healthy empty inventory.
    """
    if not isinstance(value, dict) or not isinstance(value.get('request'), dict):
        raise SuccessionError('succession record and request must be objects')
    request = value['request']
    if request.get('kind') not in ('material-context', 'transfer', 'packet-retirement'):
        raise SuccessionError('succession request needs a known string kind')
    if value.get('status') == 'prepared':
        # The existing transaction owner intentionally has no derived kind yet.
        exact(value, {'schema', 'status', 'request_sha256', 'request'})
        if type(value['schema']) is not int or value['schema'] != 1 or value['request_sha256'] != digest(encoded(request)):
            raise SuccessionError('prepared succession differs from its exact request')
    elif value.get('status') != 'committed' or value.get('kind') != request['kind']:
        raise SuccessionError('committed succession needs its matching kind and status')
    return request


def material_needs_reconciliation(report):
    """Current applicability only; no meaning verdict or action authority."""
    if report['record_integrity'] in ('INCOMPLETE', 'CHANGED_REQUIRES_REVIEW'):
        return True
    observed = bool(report['records'] or report['issues'])
    return observed and (
        report['record_integrity'] != 'VERIFIED_FOR_DECLARED_INPUTS'
        or report['association_reachability'] != 'REACHABLE'
        or report['input_coverage'] != 'VERIFIED_FOR_DECLARED_INPUTS'
    )


def _material_text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise SuccessionError('bounded nonempty ' + label + ' required')
    return value


def _material_refs(item):
    if item.get('destination') is not None:
        yield item['destination']
    if item.get('next_action') is not None:
        yield item['next_action']
    yield from item.get('aspects', {}).values()
    for obligation in item.get('obligations', []):
        yield obligation['destination']


def _material_review(project, request, *, reader_type=Reader):
    from datetime import datetime
    exact(request, {'schema', 'kind', 'phase', 'batch', 'inventory', 'items', 'review', 'context_anchor', 'context_max_lines'})
    if type(request['schema']) is not int or request['schema'] != 2 or request['kind'] != 'material-context' or request['phase'] not in ('capture', 'associate'):
        raise SuccessionError('unknown material context contract')
    _material_text(request['context_anchor'], 'context anchor')
    if type(request['context_max_lines']) is not int or not 1 <= request['context_max_lines'] <= 150:
        raise SuccessionError('explicit bounded context line budget required')
    reader = reader_type(project)
    batch = request['batch']
    exact(batch, {'id', 'predecessor', 'captured_at', 'observation', 'excluded'})
    identifier(batch['id'])
    _material_text(batch['captured_at'], 'capture time')
    when = datetime.fromisoformat(batch['captured_at'].replace('Z', '+00:00'))
    if when.tzinfo is None:
        raise SuccessionError('capture time needs an explicit offset; not inferred event time')
    exact(batch['observation'], {'scope', 'start', 'end', 'gaps'})
    if batch['observation']['scope'] != 'declared-inputs':
        raise SuccessionError('whole-session coverage is not observable from this record')
    for key in ('start', 'end'):
        if batch['observation'][key] is not None:
            _material_text(batch['observation'][key], 'observation locator')
    gaps = batch['observation']['gaps']
    if not isinstance(gaps, list) or len(gaps) > MAX_ITEMS:
        raise SuccessionError('bounded explicit observation gaps required')
    for gap in gaps:
        _material_text(gap, 'gap description')
    if not isinstance(batch['excluded'], list) or len(batch['excluded']) > MAX_ITEMS:
        raise SuccessionError('bounded excluded input accounting required')
    excluded = set()
    for row in batch['excluded']:
        exact(row, {'id', 'reason'})
        identity = identifier(row['id'])
        if identity in excluded:
            raise SuccessionError('duplicate excluded input identity')
        excluded.add(identity)
        _material_text(row['reason'], 'excluded scope reason')
    prior = None
    if batch['predecessor'] is not None:
        prior = json.loads(reader.read(batch['predecessor']), object_pairs_hook=rt._unique)
        record_request(prior)
        if prior.get('kind') != 'material-context' or prior.get('status') != 'committed':
            raise SuccessionError('predecessor must be an exact committed material succession record')
        if prior.get('phase') not in ('capture', 'associate'):
            raise SuccessionError('predecessor needs a known material phase')
        exact(prior.get('batch'), {'id', 'predecessor', 'captured_at', 'observation', 'excluded'})
        identifier(prior['batch']['id'])
        exact(prior.get('inventory'), {'path', 'sha256', 'format', 'declared_count'})
        if not isinstance(prior.get('items'), list) or len(prior['items']) > MAX_ITEMS:
            raise SuccessionError('predecessor needs bounded item objects')
        prior_ids = []
        for previous in prior['items']:
            if not isinstance(previous, dict):
                raise SuccessionError('predecessor item must be an object')
            prior_ids.append(identifier(previous.get('id')))
        if len(prior_ids) != len(set(prior_ids)):
            raise SuccessionError('predecessor item identities must be unique')
    ids, spec, _ = inventory(reader, request['inventory'])
    if prior is not None and prior.get('phase') == 'capture':
        if (request['phase'] != 'associate' or batch['id'] != prior['batch']['id']
                or request['inventory'] != prior['inventory']):
            raise SuccessionError('association must reconcile its exact captured input inventory')
    if request['inventory']['format'] != 'json-rows' or set(spec) != {'rows'}:
        raise SuccessionError('material inventory needs an exact JSON rows object')
    if request['inventory']['declared_count'] != len(ids) or set(ids) & excluded:
        raise SuccessionError('material input denominator differs from declared inventory')
    sources = {}
    unavailable = []
    for row in spec['rows']:
        exact(row, {'id', 'kind', 'source', 'availability', 'provenance', 'required_aspects', 'reason'})
        if not isinstance(row['kind'], str) or row['kind'] not in MATERIAL_KINDS:
            raise SuccessionError('unsupported material kind; credentials are not narrative custody')
        _material_text(row['reason'], 'selection or nonmaterial reason')
        exact(row['provenance'], {'origin', 'attribution', 'event_time', 'authority'})
        if row['provenance']['origin'] not in ('primary', 'quoted', 'relayed', 'unknown') or row['provenance']['authority'] != 'source-claim-not-current-authority':
            raise SuccessionError('source provenance never grants current principal authority')
        _material_text(row['provenance']['attribution'], 'attribution')
        if row['provenance']['event_time'] is not None:
            _material_text(row['provenance']['event_time'], 'reported event time')
        aspects = row['required_aspects']
        if not isinstance(aspects, list) or not all(isinstance(aspect, str) for aspect in aspects) or len(aspects) != len(set(aspects)) or set(aspects) - MATERIAL_ASPECTS:
            raise SuccessionError('unique declared material aspects required')
        if row['kind'] == 'nonmaterial' and aspects:
            raise SuccessionError('nonmaterial disposition must not hide declared material aspects')
        if row['availability'] == 'retained':
            # Whole-file references retain binary attachments without inventing
            # a text anchor or interpreting their content. Meaning stays unknown.
            reader.read(row['source'], anchor=isinstance(row['source'], dict) and 'anchor' in row['source'])
        elif row['availability'] == 'unavailable' and row['source'] is None:
            unavailable.append(row['id'])
        else:
            raise SuccessionError('source availability must preserve the actual limitation')
        sources[row['id']] = row
    rows = request['items']
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise SuccessionError('bounded material dispositions required')
    seen, out, missing_aspects = set(), [], []
    for row in rows:
        exact(row, {'id', 'status', 'destination', 'aspects', 'not_applicable', 'owner', 'next_action', 'supersedes', 'reason'})
        identity = identifier(row['id'])
        if identity in seen:
            raise SuccessionError('duplicate material disposition identity')
        seen.add(identity)
        if identity not in sources:
            raise SuccessionError('extra material disposition outside selected inputs')
        if not isinstance(row['status'], str) or row['status'] not in MATERIAL_ACTIVE | {'recorded', 'cancelled', 'retired', 'nonmaterial'}:
            raise SuccessionError('unsupported material status; absence is never completion')
        _material_text(row['reason'], 'disposition rationale')
        _material_text(row['owner'], 'owner or explicit UNKNOWN with reason')
        if not isinstance(row['aspects'], dict) or set(row['aspects']) - MATERIAL_ASPECTS or not isinstance(row['not_applicable'], dict) or set(row['not_applicable']) - MATERIAL_ASPECTS:
            raise SuccessionError('bounded aspect references and applicability reasons required')
        if set(row['aspects']) & set(row['not_applicable']):
            raise SuccessionError('an aspect cannot be both present and inapplicable')
        for reason in row['not_applicable'].values():
            _material_text(reason, 'aspect applicability reason')
        absent = set(sources[identity]['required_aspects']) - set(row['aspects'])
        # A declared source condition cannot be waived as an inapplicable field.
        missing_aspects.extend(identity + ':' + key for key in sorted(absent))
        if row['status'] == 'nonmaterial':
            if sources[identity]['kind'] != 'nonmaterial' or row['destination'] is not None or row['next_action'] is not None:
                raise SuccessionError('nonmaterial disposition cannot erase a selected material item')
        elif row['destination'] is None:
            missing_aspects.append(identity + ':destination')
        if row['status'] in MATERIAL_ACTIVE and row['next_action'] is None:
            missing_aspects.append(identity + ':next_action')
        for ref in _material_refs(row):
            reader.read(ref, anchor=True)
        if row['supersedes'] is not None:
            exact(row['supersedes'], {'record', 'id'})
            identifier(row['supersedes']['id'])
            if prior is None or row['supersedes']['record'] != batch['predecessor'] or row['supersedes']['id'] not in {r['id'] for r in prior['items']}:
                raise SuccessionError('amendment/cancellation must bind its exact predecessor item')
        out.append({**row, 'obligations': [{'id': identity, 'destination': row['next_action']}] if row['next_action'] is not None and row['status'] in MATERIAL_ACTIVE else []})
    if request['phase'] == 'capture' and (rows or request['review'] is not None):
        raise SuccessionError('capture is retained pending review, not an associated disposition')
    missing = sorted(set(ids) - seen)
    coverage = ('CAPTURED_PENDING' if request['phase'] == 'capture' else 'MISSING_MATERIAL' if missing or missing_aspects else 'SOURCE_UNAVAILABLE' if unavailable else 'VERIFIED_FOR_DECLARED_INPUTS')
    semantic = 'UNREVIEWED'
    review_evidence = None
    if request['review'] is not None:
        review_evidence = json.loads(reader.read(request['review']), object_pairs_hook=rt._unique)
        exact(review_evidence, {'schema', 'kind', 'inventory_sha256', 'dispositions_sha256', 'reviewer', 'plan', 'earlier_decisions', 'answers', 'limitations'})
        if type(review_evidence['schema']) is not int or review_evidence['schema'] != 1 or review_evidence['kind'] != 'material-meaning-review' or review_evidence['inventory_sha256'] != request['inventory']['sha256'] or review_evidence['dispositions_sha256'] != digest(encoded(rows)):
            raise SuccessionError('meaning review belongs to another input/destination generation')
        reader.read(review_evidence['reviewer'], anchor=True)
        reader.read(review_evidence['plan'], anchor=True)
        if not isinstance(review_evidence['earlier_decisions'], list) or len(review_evidence['earlier_decisions']) > MAX_ITEMS:
            raise SuccessionError('bounded earlier decision references required')
        for ref in review_evidence['earlier_decisions']:
            reader.read(ref, anchor=True)
        _material_text(review_evidence['limitations'], 'review limitations')
        answers = review_evidence['answers']
        if not isinstance(answers, list) or len(answers) != len(ids):
            raise SuccessionError('meaning review must account for each declared input')
        reviewed = set(); grades = set()
        dispositions = {row['id']: row for row in out}
        for answer in answers:
            exact(answer, {'id', 'question', 'source_refs', 'record_refs', 'assessment', 'reason'})
            identity = identifier(answer['id'])
            if identity in reviewed or identity not in sources:
                raise SuccessionError('meaning answer identity differs')
            reviewed.add(identity)
            if answer['assessment'] not in ('faithful', 'deficient', 'uncertain'):
                raise SuccessionError('a PASS flag is not meaning evidence')
            grades.add(answer['assessment'])
            _material_text(answer['question'], 'recovery question'); _material_text(answer['reason'], 'cited review reasoning')
            source = sources[identity]['source']
            source_paths = {source['path']} if source is not None else set()
            if identity not in dispositions:
                raise SuccessionError('meaning review needs a disposition for every input')
            destination_paths = {ref['path'] for ref in _material_refs(dispositions[identity])}
            for key, allowed in (('source_refs', source_paths), ('record_refs', destination_paths)):
                refs = answer[key]
                if not isinstance(refs, list) or len(refs) > 16:
                    raise SuccessionError('bounded review citations required')
                if sources[identity]['availability'] == 'retained' and sources[identity]['kind'] != 'nonmaterial' and not refs:
                    raise SuccessionError('review needs actual source and record citations')
                for ref in refs:
                    exact(ref, {'path', 'sha256', 'anchor'}, {'path', 'sha256'})
                    if not isinstance(ref['path'], str) or ref['path'] not in allowed:
                        raise SuccessionError('review citation outside its exact input/destination closure')
                    reader.read(ref, anchor=key != 'source_refs' or 'anchor' in ref)
        semantic = 'DEFICIENCIES_REPORTED' if 'deficient' in grades else 'REVIEW_EVIDENCE_PRESENT_UNVERIFIED'
    result = {'schema': 2, 'kind': 'material-context', 'phase': request['phase'], 'batch': batch,
        'inventory': request['inventory'], 'inventory_ids': ids, 'inventory_count': len(ids),
        'declared_count_matches': True, 'reconciled_ids': sorted(seen), 'missing_items': missing,
        'missing_aspects': sorted(missing_aspects), 'extra_items': [], 'unavailable_sources': unavailable,
        'identity_complete': request['phase'] == 'capture' or not missing and not missing_aspects,
        'items': out, 'selected_inputs': list(sources.values()), 'unresolved_obligations': sorted(r['id'] for r in out if r['status'] in MATERIAL_ACTIVE),
        'input_coverage': coverage, 'record_integrity': 'VERIFIED_FOR_DECLARED_INPUTS',
        'association_reachability': 'NOT_YET_APPLIED', 'semantic_review': semantic,
        'current_authority': 'NOT_ASSESSED', 'endpoint_recovery': 'UNKNOWN',
        'whole_session_coverage': 'UNKNOWN', 'historical_coverage': 'UNKNOWN',
        'authorization_granted': False, 'completion_established': False,
        'readiness': 'requires-meaning-review', 'request_sha256': digest(encoded(request)), 'request': request,
        'review_evidence': review_evidence, 'inventory_coverage': 'Declared bounded inputs only; source kind and reviewer statements are not authentication.'}
    reader.unchanged()
    return result, reader


def _material_navigation(project, record, budget):
    """Bounded forward Markdown links from ordinary resumption surfaces.

    This proves path reachability only. File text and link labels are never a
    semantic oracle, and external/private locators grant no read authority.
    """
    reader = Reader(project, budget=budget)
    queue = [('CONTEXT.md', 0), ('REFERENCE.md', 0)]
    seen = set(); skipped = 0
    while queue:
        path, depth = queue.pop(0)
        if path in seen:
            continue
        if len(seen) >= MAX_RECORDS:
            raise SuccessionError('material navigation entry bound exceeded')
        seen.add(path)
        target = rt._path(Path(project) / path, Path(project))
        if not target.exists():
            skipped += 1; continue
        raw, _ = rt._snapshot(target)
        reader.read({'path': path, 'sha256': digest(raw)})
        for link in re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', raw.decode('utf-8', errors='replace')):
            link = link.split('#', 1)[0]
            if not link or ':' in link or Path(link).is_absolute():
                skipped += 1; continue
            candidate = Path(os.path.normpath(str(Path(path).parent / link)))
            if '..' in candidate.parts:
                skipped += 1; continue
            if candidate.as_posix() == record:
                reader.unchanged()
                return {'status': 'REACHABLE', 'examined': len(seen), 'skipped': skipped}
            if candidate.suffix == '.md':
                if depth >= 4:
                    raise SuccessionError('material navigation depth bound exhausted; reachability remains unknown')
                queue.append((candidate.as_posix(), depth + 1))
    reader.unchanged()
    return {'status': 'PRESENT_BUT_UNREACHABLE', 'examined': len(seen), 'skipped': skipped}


def material_context(project):
    """Read-only shared coverage projection; no enrollment, receipt or policy activation."""
    started = time.monotonic()
    budget = {'refs': 0, 'bytes': 0, 'deadline': started + SCAN_SECONDS}
    result = {'schema': 1, 'input_coverage': 'UNKNOWN', 'record_integrity': 'UNKNOWN',
        'association_reachability': 'UNKNOWN', 'semantic_review': 'UNREVIEWED',
        'current_authority': 'NOT_ASSESSED', 'endpoint_recovery': 'UNKNOWN',
        'whole_session_coverage': 'UNKNOWN', 'historical_coverage': 'UNKNOWN',
        'authorization_granted': False, 'completion_established': False,
        'records': [], 'active_items': [], 'issues': [], 'examined_records': 0, 'skipped_records': 0,
        'navigation_examined': 0, 'navigation_skipped': 0}
    try:
        project = rt._path(project)
        with rt.managed(project):
            for path in records(project):
                if time.monotonic() > budget['deadline']:
                    raise SuccessionError('material scan deadline exhausted')
                raw, _ = rt._snapshot(path)
                budget['bytes'] += len(raw)
                if budget['bytes'] > MAX_SOURCE_BYTES:
                    raise SuccessionError('material scan byte bound exhausted')
                value = json.loads(raw, object_pairs_hook=rt._unique)
                request = record_request(value)
                name = str(path.relative_to(project))
                navigation = _material_navigation(project, name, budget)
                result['navigation_examined'] += navigation['examined']; result['navigation_skipped'] += navigation['skipped']
                if request['kind'] != 'material-context':
                    result['skipped_records'] += 1
                    if navigation['status'] != 'REACHABLE':
                        result['association_reachability'] = 'PRESENT_BUT_UNREACHABLE'
                        result['issues'].append({'record': name, 'kind': 'PRESENT_BUT_UNREACHABLE', 'detail': 'Retained succession lacks a forward resumption link; historical input coverage remains unknown.'})
                    continue
                result['examined_records'] += 1
                if value.get('status') != 'committed':
                    result['records'].append({'record': name, 'sha256': digest(raw), 'phase': 'prepared', 'input_coverage': 'CAPTURED_PENDING', 'semantic_review': 'UNREVIEWED', 'association_reachability': navigation['status']})
                    result['issues'].append({'record': name, 'kind': 'CAPTURED_PENDING', 'detail': 'Prepared material record requires existing transaction recovery or exact owner reconciliation.'})
                    continue
                checked = validate_record(project, path, _budget=budget, _navigation=navigation)
                result['records'].append({'record': name, 'sha256': digest(raw), 'phase': checked['phase'], 'batch': checked['batch'], 'items': checked['items'],
                    'input_coverage': checked['input_coverage'], 'record_integrity': checked['record_integrity'], 'semantic_review': checked['semantic_review'],
                    'current_destinations': checked['current_destinations'], 'association_reachability': navigation['status']})
                if navigation['status'] != 'REACHABLE':
                    result['issues'].append({'record': name, 'kind': 'PRESENT_BUT_UNREACHABLE', 'detail': 'Exact retained material exists but current resumption does not reach it.'})
                if checked['current_destinations'] != 'exact-observed-snapshot':
                    result['issues'].append({'record': name, 'kind': 'CHANGED_REQUIRES_REVIEW', 'detail': 'Current canonical bytes differ from the historically bound material review.'})
            selected = [r for r in result['records'] if r.get('phase') in {'capture', 'associate'}]
            succeeded = {r['batch']['predecessor']['path'] for r in selected if r['batch']['predecessor'] is not None}
            active_records = [r for r in selected if not (r['phase'] == 'capture' and r['record'] in succeeded)]
            superseded = {(item['supersedes']['record']['path'], item['supersedes']['id']) for r in active_records for item in r.get('items', []) if item.get('supersedes') is not None}
            supersessions = [(item['supersedes']['record']['path'], item['supersedes']['id']) for r in active_records for item in r.get('items', []) if item.get('supersedes') is not None]
            conflicting = len(supersessions) != len(superseded)
            result['active_items'] = [{'record': r['record'], **item} for r in active_records for item in r.get('items', []) if (r['record'], item['id']) not in superseded]
            active_records = [r for r in active_records if r['phase'] == 'capture' or not r.get('items') or any((r['record'], item['id']) not in superseded for item in r['items'])]
            if result['records']:
                result['record_integrity'] = 'VERIFIED_FOR_DECLARED_INPUTS'
                values = {r['input_coverage'] for r in active_records} | {r['input_coverage'] for r in result['records'] if r['phase'] == 'prepared'}
                if any(r['phase'] == 'prepared' for r in result['records']):
                    result['record_integrity'] = 'INCOMPLETE'
                result['input_coverage'] = next((v for v in ('MISSING_MATERIAL', 'CAPTURED_PENDING', 'SOURCE_UNAVAILABLE') if v in values), 'VERIFIED_FOR_DECLARED_INPUTS' if values else 'CAPTURED_PENDING')
                result['association_reachability'] = 'PRESENT_BUT_UNREACHABLE' if any(r['association_reachability'] != 'REACHABLE' for r in result['records']) else 'REACHABLE'
                result['semantic_review'] = 'DEFICIENCIES_REPORTED' if any(r['semantic_review'] == 'DEFICIENCIES_REPORTED' for r in active_records) else 'REVIEW_EVIDENCE_PRESENT_UNVERIFIED' if active_records and all(r['semantic_review'] == 'REVIEW_EVIDENCE_PRESENT_UNVERIFIED' for r in active_records) else 'UNREVIEWED'
                if any(r.get('current_destinations') == 'changed-requires-review' for r in active_records):
                    result['record_integrity'] = 'CHANGED_REQUIRES_REVIEW'; result['semantic_review'] = 'CHANGED_REQUIRES_REVIEW'
                if conflicting:
                    result['record_integrity'] = 'INCOMPLETE'
                    result['issues'].append({'kind': 'CURRENT_CONFLICT', 'detail': 'Multiple retained dispositions supersede the same item; current meaning requires reconciliation.'})
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        result['record_integrity'] = 'INCOMPLETE'
        result['issues'].append({'kind': 'INCOMPLETE', 'detail': str(exc)})
    result['resource_usage'] = {'reference_observations': budget['refs'], 'charged_bytes': budget['bytes'], 'elapsed_seconds': time.monotonic() - started,
        'limits': {'references': MAX_REFS, 'bytes': MAX_SOURCE_BYTES, 'records': MAX_RECORDS, 'seconds': SCAN_SECONDS}, 'model_usage': 'UNKNOWN'}
    return result


def material_projection(report):
    """Reference-only view for the existing optional recovery capsule.

    It binds the succession records, not a second copy of narrative or authority.
    Re-observe with material_context before relying on current applicability.
    """
    fields = ('schema', 'input_coverage', 'record_integrity', 'association_reachability',
        'semantic_review', 'current_authority', 'endpoint_recovery', 'whole_session_coverage',
        'historical_coverage', 'authorization_granted', 'completion_established',
        'examined_records', 'skipped_records', 'navigation_examined', 'navigation_skipped')
    return {**{key: report[key] for key in fields},
        'records': [{key: row[key] for key in ('record', 'sha256', 'phase', 'input_coverage',
            'record_integrity', 'semantic_review', 'association_reachability') if key in row}
            for row in report['records']],
        'issues': [{key: issue[key] for key in ('record', 'kind') if key in issue} for issue in report['issues']],
        'recovery_owner': 'record_succession.material_context', 'narrative_copied': False}
