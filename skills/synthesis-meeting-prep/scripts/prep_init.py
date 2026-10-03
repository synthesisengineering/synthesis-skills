#!/usr/bin/env python3
"""Scaffold workspace-owned private meeting profiles and migrate exact selections.

Every invocation names an approved private context repository and workspace.
There is no global-home, current-directory, or arbitrary --dir fallback.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

_CONTEXT = Path(__file__).resolve().parents[2] / "synthesis-context-lifecycle" / "scripts"
sys.path.insert(0, str(_CONTEXT))
import record_transaction as records  # noqa: E402 - existing bounded record owner

ENGINE_VERSION = "2.0.0"
PROFILE_PATH = Path("profiles/meeting-prep")
MAX_PROFILES = 128
MAX_TOTAL_BYTES = 32 * 1024 * 1024

RELATIONSHIPS = ("peer", "boss", "report", "skip", "external", "other")

PRINCIPAL_TEMPLATE = {
    "name": "",
    "role": "",
    "org": "",
    "goals_professional": [],
    "goals_personal": [],
    "authority": {
        "can_commit": "",
        "can_decide": "",
        "can_spend": "",
    },
    "known_positions": [],
    "tells_under_pressure": [],
}

READER_TEMPLATE = """\
# {name}

- relationship: {relationship}
- technical_depth: (how technical — delete and write: deep / working / non-technical)
- cares_about: (their current pressures, one per line)
- told_before: (what they have already been told)
- landed_last_time: (what worked in the last meeting)
- avoid_live: (topics to keep out of the room)
"""

INTERVIEW = """\
Created meeting-prep configuration under {root}.

Next, answer these once (edit the files directly):

1. principal.json: your professional and personal goals, what you can
   commit/decide/spend in a room, your known positions, and your
   tells under pressure.
2. readers/<id>.md: one file per person you meet regularly —
   relationship, technical depth, what they care about.
3. Run `prep_init.py add-reader` for each regular, or copy the template.

The skill degrades gracefully until this is filled in: it asks the
three questions it cannot proceed without and drafts anyway.
"""


def _absolute(path):
    if path is None or not Path(path).is_absolute():
        raise ValueError("an explicit absolute owner path is required")
    return records._path(Path(path))


def _git(path, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(path), *args], env=env,
                          capture_output=True, text=True, timeout=10, check=False)


def _owner(context_repo, workspace):
    if not isinstance(workspace, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", workspace):
        raise ValueError("an explicit stable workspace id is required")
    repo = _absolute(context_repo)
    if repo in (Path(repo.anchor), Path.home()) or not repo.is_dir():
        raise ValueError("owner must be a dedicated existing private context repository")
    actual = _git(repo, "rev-parse", "--show-toplevel")
    if actual.returncode or Path(actual.stdout.strip()) != repo:
        raise ValueError("context repository must be its exact Git checkout root")
    root = records._path(repo / PROFILE_PATH, repo)
    marker = records._path(root / ".owner.json", repo)
    if marker.exists():
        found, _ = records._read_json(marker)
        if type(found.get("schema")) is not int or found != {"schema": 1, "workspace": workspace}:
            raise ValueError("profile directory belongs to a different or ambiguous owner")
    elif root.exists() and any(root.iterdir()):
        raise ValueError("unbound existing profiles require an explicit migration selection")
    return repo, root


def default_root(context_repo=None, workspace=None) -> Path:
    """Resolve only the explicitly selected owner, never the caller's CWD/home."""
    return _owner(context_repo, workspace)[1]


def _mkdir(path):
    path = records._path(path)
    if path.exists():
        if not path.is_dir():
            raise ValueError("profile parent must be a directory")
        return
    _mkdir(path.parent)
    path.mkdir(mode=0o700)
    records._path(path)
    records._sync_dir(path.parent)


def _bind(repo, root, workspace):
    # Must be called under the existing repository-directory owner lock.
    _owner(repo, workspace)
    _mkdir(root)
    marker = root / ".owner.json"
    if not marker.exists():
        records._new_file(marker, records._json({"schema": 1, "workspace": workspace}))
        records._sync_dir(root)


@contextmanager
def _owned(context_repo, workspace, *, create=False):
    repo, root = _owner(context_repo, workspace)
    with records.managed(repo, exclusive=True):
        _owner(repo, workspace)
        if create:
            _bind(repo, root, workspace)
        yield repo, root


def _absent(path):
    records._path(path)
    if os.path.lexists(path):
        # Inspect special/hardlinked input before issuing any overwrite remedy.
        records._snapshot(path)
        raise FileExistsError(f"profile exists; explicit content editing is required: {path}")


def _create(path, data):
    if len(data) > records.MAX_FILE_BYTES:
        raise ValueError("profile exceeds 8 MiB bound")
    _absent(path)
    _mkdir(path.parent)
    records._new_file(path, data)
    records._sync_dir(path.parent)
    actual, _ = records._snapshot(path)
    if actual != data:
        raise ValueError("profile readback differs; preserve the retained file")


def init_principal(context_repo, name, role, org, goals, *, workspace):
    with _owned(context_repo, workspace) as (repo, root):
        principal, template = root / "principal.json", root / "readers/_template.md"
        _absent(principal)
        _absent(template)
        payload = dict(PRINCIPAL_TEMPLATE, name=name, role=role, org=org, goals_professional=goals)
        data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()
        text = READER_TEMPLATE.format(name="(name)", relationship="(peer|boss|report|skip|external|other)").encode()
        if len(data) > records.MAX_FILE_BYTES:
            raise ValueError("profile exceeds 8 MiB bound")
        _bind(repo, root, workspace)
        _create(principal, data)
        _create(template, text)
        return {"workspace": workspace, "principal": str(principal), "template": str(template)}


def add_reader(context_repo, reader_id, name, relationship, *, workspace):
    if relationship not in RELATIONSHIPS:
        raise ValueError("relationship must be one of " + ", ".join(RELATIONSHIPS))
    if not isinstance(reader_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", reader_id):
        raise ValueError("reader id must be alphanumeric (dashes/underscores ok)")
    with _owned(context_repo, workspace) as (repo, root):
        path = root / "readers" / (reader_id + ".md")
        _absent(path)
        data = READER_TEMPLATE.format(name=name, relationship=relationship).encode()
        if len(data) > records.MAX_FILE_BYTES:
            raise ValueError("profile exceeds 8 MiB bound")
        _bind(repo, root, workspace)
        _create(path, data)
        return {"workspace": workspace, "reader": str(path)}


def _profile_name(value):
    if value == "principal.json" or (isinstance(value, str) and re.fullmatch(r"readers/[A-Za-z0-9_][A-Za-z0-9_-]{0,63}\.md", value)):
        return value
    raise ValueError("migration paths must be exact principal/reader profile names")


def _identity(path):
    st = records._path(path).stat()
    return {"dev": st.st_dev, "ino": st.st_ino}


def _same(snapshot, expected):
    return all(snapshot.get(key) == expected.get(key) for key in ("dev", "ino", "mode", "bytes", "sha256"))


def _custody(row, root, runtime, legacy, custody):
    """Read-only validation of every resumable state before any apply writes."""
    src = records._path(legacy / row["path"], legacy)
    dst = records._path(root / row["path"], root)
    stage = records._path(runtime / "files" / row["path"], runtime)
    retained = records._path(custody / row["path"], custody)
    if row["status"] in ("prepared", "staged"):
        _, current = records._snapshot(src)
        if not _same(current, row["source"]):
            raise ValueError("source changed; preserve all migration evidence")
        if retained.exists():
            raise ValueError("unexpected retained source before the copy boundary")
        if not stage.exists():
            if row["status"] == "staged" or dst.exists():
                raise ValueError("staged custody is missing or destination is occupied")
            return
        linked = dst.exists() and os.path.samefile(stage, dst)
        _, staged = records._snapshot(stage, _links=2 if linked else 1)
        if (staged["sha256"] != row["source"]["sha256"]
                or (row["stage"] is not None and not _same(staged, row["stage"]))):
            raise ValueError("partial or changed stage retained; reconciliation required")
        if dst.exists() and not linked:
            raise ValueError("destination is not this migration's staged inode")
        if linked:
            records._snapshot(dst, _links=2)
        return
    linked = stage.exists()
    _, destination = records._snapshot(dst, _links=2 if linked else 1)
    if not _same(destination, row["destination"]):
        raise ValueError("destination changed; original custody is retained")
    if linked:
        _, staged = records._snapshot(stage, _links=2)
        if not _same(staged, row["stage"]) or not os.path.samefile(stage, dst):
            raise ValueError("stage custody changed; no removal")
    if row["status"] == "complete":
        if src.exists() or retained.exists() or linked:
            raise ValueError("source or stage reappeared after completion; no automatic deletion")
        return
    if src.exists() and retained.exists():
        raise ValueError("a source path reappeared; preserve both copies")
    current_path = src if src.exists() else retained
    if not current_path.exists():
        if row["status"] != "retained":
            raise ValueError("source custody is missing; reconciliation required")
        return
    _, current = records._snapshot(current_path)
    if not _same(current, row["source"]):
        raise ValueError("source custody changed; preserve all migration evidence")


def _plan(request):
    if not isinstance(request, dict) or set(request) != {"schema", "legacy_root", "context_repo", "workspace", "files"} or type(request["schema"]) is not int or request["schema"] != 1:
        raise ValueError("migration requires the closed schema-1 explicit owner map")
    repo, root = _owner(request["context_repo"], request["workspace"])
    legacy = _absolute(request["legacy_root"])
    if not legacy.is_dir() or legacy in (Path(legacy.anchor), Path.home()) or legacy.is_relative_to(repo) or repo.is_relative_to(legacy):
        raise ValueError("legacy profiles require a dedicated source outside the destination repository")
    if _git(legacy, "rev-parse", "--show-toplevel").returncode == 0:
        raise ValueError("tracked source custody requires the Git record owner, not this legacy migration")
    files = request["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_PROFILES:
        raise ValueError("migration selection must contain 1..128 exact profile entries")
    selected, seen, unresolved = [], set(), 0
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "workspace"}:
            raise ValueError("each migration entry needs exact path, sha256 and workspace")
        name = _profile_name(item["path"])
        if name in seen:
            raise ValueError("duplicate migration profile")
        seen.add(name)
        if item["workspace"] is not None and (not isinstance(item["workspace"], str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", item["workspace"])):
            raise ValueError("profile ownership must be an explicit workspace or null")
        if item["workspace"] != request["workspace"]:
            unresolved += 1
            continue
        if not isinstance(item["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", item["sha256"]):
            raise ValueError("selected profile needs its exact source SHA-256")
        selected.append(dict(item))
    if not selected:
        raise ValueError("no profile has the explicitly selected owner")
    binding = {"schema": 1, "legacy_root": str(legacy), "context_repo": str(repo),
               "workspace": request["workspace"], "files": selected}
    digest = hashlib.sha256(records._json(binding)).hexdigest()
    return repo, root, legacy, binding, digest, unresolved


def _journal(path, value):
    records._path(path)
    if path.exists():
        records._snapshot(path)
        records._replace_json(path, value)
    else:
        records._new_file(path, records._json(value))
        records._sync_dir(path.parent)


def migrate(request, *, apply=False):
    """Copy, verify, move source into retained custody, verify, then remove it.

    Cooperative operations hold both existing directory locks. A changed source
    moved at the atomic rename boundary is retained in custody and refused,
    never deleted. Unselected and unresolved profiles are not opened.
    """
    repo, root, legacy, binding, digest, unresolved = _plan(request)
    with ExitStack() as stack:
        for directory in sorted((repo, legacy), key=str):
            stack.enter_context(records.managed(directory, exclusive=True))
        _owner(repo, binding["workspace"])
        runtime = records._path(root / ".migrations" / digest, root)
        receipt = records._path(runtime / "receipt.json", runtime)
        custody = records._path(legacy / (".meeting-prep-migration-" + digest), legacy)
        existed = receipt.exists()
        if existed:
            state, _ = records._read_json(receipt)
            if (set(state) != {"schema", "plan", "repo_identity", "legacy_identity", "files"}
                    or type(state["schema"]) is not int or state["schema"] != 1 or state["plan"] != binding
                    or state["repo_identity"] != _identity(repo)
                    or state["legacy_identity"] != _identity(legacy)
                    or not isinstance(state["files"], list)
                    or len(state["files"]) != len(binding["files"])):
                raise ValueError("migration receipt does not bind this exact owner and selection")
        else:
            if runtime.exists() or custody.exists():
                raise ValueError("unreceipted migration custody exists; preserve it for reconciliation")
            state = {"schema": 1, "plan": binding, "repo_identity": _identity(repo),
                     "legacy_identity": _identity(legacy), "files": []}
            total = 0
            for item in binding["files"]:
                src, dst = legacy / item["path"], root / item["path"]
                raw, snapshot = records._snapshot(src)
                if snapshot["sha256"] != item["sha256"]:
                    raise ValueError("migration source hash differs from the explicit map")
                total += len(raw)
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("migration exceeds 32 MiB selected data")
                _absent(dst)
                state["files"].append({"path": item["path"], "source": snapshot,
                                       "destination": None, "stage": None, "status": "prepared"})
        for item, row in zip(binding["files"], state["files"]):
            if (not isinstance(row, dict) or set(row) != {"path", "source", "destination", "stage", "status"}
                    or row["path"] != item["path"] or not isinstance(row["source"], dict)
                    or row["source"].get("sha256") != item["sha256"]
                    or row["status"] not in ("prepared", "staged", "copied", "retained", "complete")):
                raise ValueError("migration receipt has an invalid file state")
            if ((row["status"] != "prepared" and row["stage"] is None)
                    or (row["status"] in ("copied", "retained", "complete") and row["destination"] is None)
                    or (row["status"] in ("prepared", "staged") and row["destination"] is not None)):
                raise ValueError("migration receipt has inconsistent custody")
            identities = [row["source"], *[row[k] for k in ("stage", "destination") if row[k] is not None]]
            for identity in identities:
                if (not isinstance(identity, dict)
                        or set(identity) != {"dev", "ino", "mode", "bytes", "sha256"}
                        or any(type(identity[k]) is not int or identity[k] < 0 for k in ("dev", "ino", "mode", "bytes"))
                        or identity["mode"] > 0o7777
                        or identity["bytes"] > records.MAX_FILE_BYTES
                        or not isinstance(identity["sha256"], str)
                        or not re.fullmatch("[0-9a-f]{64}", identity["sha256"])):
                    raise ValueError("migration receipt has an invalid file identity")
            for key in ("stage", "destination"):
                identity = row[key]
                if identity is not None and (identity["sha256"] != row["source"]["sha256"]
                        or identity["bytes"] != row["source"]["bytes"] or identity["mode"] != 0o600):
                    raise ValueError("migration copy identity does not bind the selected source")
            if row["destination"] is not None and not _same(row["stage"], row["destination"]):
                raise ValueError("migration copy identities name different staged objects")
        if sum(row["source"]["bytes"] for row in state["files"]) > MAX_TOTAL_BYTES:
            raise ValueError("migration exceeds 32 MiB selected data")
        for row in state["files"]:
            _custody(row, root, runtime, legacy, custody)
        if not apply:
            return {"workspace": binding["workspace"], "selected": len(state["files"]),
                    "unresolved": unresolved, "apply": False, "migration": digest,
                    "resume": existed, "receipt": str(receipt)}
        _bind(repo, root, binding["workspace"])
        _mkdir(runtime)
        if not existed:
            _journal(receipt, state)
        for row in state["files"]:
            src = records._path(legacy / row["path"], legacy)
            dst = records._path(root / row["path"], root)
            stage = records._path(runtime / "files" / row["path"], runtime)
            retained = records._path(custody / row["path"], custody)
            if row["status"] in ("prepared", "staged"):
                raw, current = records._snapshot(src)
                if not _same(current, row["source"]):
                    raise ValueError("source changed; preserve all migration evidence")
                _mkdir(stage.parent)
                if not stage.exists():
                    records._new_file(stage, raw)
                    records._sync_dir(stage.parent)
                links = 2 if dst.exists() and os.path.samefile(stage, dst) else 1
                copied, snap = records._snapshot(stage, _links=links)
                if copied != raw or (row["stage"] is not None and not _same(snap, row["stage"])):
                    raise ValueError("partial or changed stage retained; reconciliation required")
                row.update(stage=snap, status="staged")
                _journal(receipt, state)
                _mkdir(dst.parent)
                if not dst.exists():
                    os.link(stage, dst, follow_symlinks=False)
                    records._sync_dir(dst.parent)
                elif not os.path.samefile(stage, dst):
                    raise FileExistsError("destination is not this migration's staged inode")
                copied, snap = records._snapshot(dst, _links=2)
                if copied != raw or snap["ino"] != row["stage"]["ino"] or snap["dev"] != row["stage"]["dev"]:
                    raise ValueError("destination copy failed identity verification")
                row.update(destination=snap, status="copied")
                _journal(receipt, state)
            if stage.exists():
                staged, snap = records._snapshot(stage, _links=2)
                if not _same(snap, row["stage"]) or not os.path.samefile(stage, dst):
                    raise ValueError("stage custody changed; no removal")
                stage.unlink()
                records._sync_dir(stage.parent)
            copied, snap = records._snapshot(dst)
            if not _same(snap, row["destination"]):
                raise ValueError("destination changed; original custody is retained")
            if row["status"] == "complete":
                if os.path.lexists(src) or os.path.lexists(retained):
                    raise ValueError("source reappeared after completion; no automatic deletion")
                continue
            if not retained.exists() and src.exists():
                _, current = records._snapshot(src)
                if not _same(current, row["source"]):
                    raise ValueError("source changed before custody move")
                _mkdir(retained.parent)
                if os.path.lexists(retained):
                    raise FileExistsError("retained source slot is occupied")
                os.rename(src, retained)
                records._sync_dir(src.parent)
                records._sync_dir(retained.parent)
            if os.path.lexists(src):
                raise ValueError("a source path reappeared; preserve both copies")
            if retained.exists():
                _, current = records._snapshot(retained)
                if not _same(current, row["source"]):
                    raise ValueError("source changed at the move boundary; retained without deletion")
                row["status"] = "retained"
                _journal(receipt, state)
                _, verified = records._snapshot(dst)
                if not _same(verified, row["destination"]):
                    raise ValueError("destination changed before source deletion")
                retained.unlink()
                records._sync_dir(retained.parent)
            elif row["status"] != "retained":
                raise ValueError("source custody is missing; reconciliation required")
            row["status"] = "complete"
            _journal(receipt, state)
        return {"workspace": binding["workspace"], "selected": len(state["files"]),
                "unresolved": unresolved, "apply": True, "migration": digest,
                "complete": True, "receipt": str(receipt)}


def share_pack(context_repo, workspace, artifact, *, board, recipient, contributor,
               operation, before=None, private=False, ttl=900):
    repo, _ = _owner(context_repo, workspace)
    # A pre-existing workspace binding is required, never minted by sharing.
    marker = repo / PROFILE_PATH / ".owner.json"
    if not marker.is_file():
        raise ValueError("private workspace profiles must be explicitly bound first")
    pm = Path(__file__).resolve().parents[2] / "synthesis-project-management/scripts"
    sys.path.insert(0, str(pm))
    import coordination
    import team_contract
    if private is not True:
        raise ValueError("explicit approved private context required")
    team_contract.require_registry(repo / "projects/index.yaml", board=board)
    enrollment = team_contract.registry_binding(repo / "projects/index.yaml")
    if enrollment is not None and enrollment["repository"]["audience"] != "private":
        raise ValueError("shared/public repository is not a private prep destination")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.md", artifact):
        raise ValueError("literal prep artifact required")
    target = records._path(repo / "meeting-preps" / artifact, repo)
    if not target.parent.is_dir():
        raise ValueError("existing private prep folder required")
    if operation == "create":
        if os.path.lexists(target) or before is not None:
            raise ValueError("create grant requires absent artifact")
    elif operation == "append":
        _, snapshot = records._snapshot(target)
        if snapshot["sha256"] != before or snapshot["mode"] != 0o600:
            raise ValueError("append grant requires exact private preimage")
    return coordination.grant_prep_share(board, recipient, contributor, repo, workspace,
                                         artifact, operation, before, private=private, ttl=ttl)


def write_pack(context_repo, workspace, artifact, text, *, board, native_payload,
               grant_id, operation, before=None):
    repo, _ = _owner(context_repo, workspace)
    folder = records._path(repo / "meeting-preps", repo)
    if not folder.is_dir() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.md", artifact):
        raise ValueError("existing private prep folder and literal Markdown artifact required")
    payload = dict(native_payload, meeting_prep_share={"id": grant_id, "workspace": workspace})
    if operation == "create":
        request = {"file": artifact, "create": {"text": text, "mode": 0o600}}
    elif operation == "append":
        request = {"file": artifact, "expected_sha256": before,
                   "edits": [{"op": "append", "text": text}]}
    else:
        raise ValueError("prep operation must be create or append")
    return records.apply(folder, [request], board=board, native_payload=payload, intent_id=grant_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage explicitly owned private meeting profiles.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("resolve", "init", "add-reader"):
        p = sub.add_parser(command)
        p.add_argument("--context-repo", type=Path, required=True, help="approved private context repository root")
        p.add_argument("--workspace", required=True, help="stable owning workspace id")
        if command == "init":
            p.add_argument("--name", required=True); p.add_argument("--role", required=True)
            p.add_argument("--org", required=True); p.add_argument("--goals", default="")
        elif command == "add-reader":
            p.add_argument("--id", required=True); p.add_argument("--name", required=True)
            p.add_argument("--relationship", choices=RELATIONSHIPS, required=True)
    p = sub.add_parser("migrate", help="preflight an exact ownership/hash map; --apply performs the move")
    p.add_argument("--map", type=Path, required=True); p.add_argument("--apply", action="store_true")
    p = sub.add_parser("share-pack", help="authenticated recipient grants one private artifact contribution")
    p.add_argument("--context-repo", type=Path, required=True); p.add_argument("--workspace", required=True)
    p.add_argument("--artifact", required=True); p.add_argument("--board", type=Path, required=True)
    p.add_argument("--recipient", required=True); p.add_argument("--contributor", required=True)
    p.add_argument("--operation", choices=("create", "append"), required=True)
    p.add_argument("--before"); p.add_argument("--private", action="store_true", required=True)
    p.add_argument("--ttl", type=int, default=900)
    p = sub.add_parser("write-pack", help="consume exact sharing authority through the record transaction")
    p.add_argument("--context-repo", type=Path, required=True); p.add_argument("--workspace", required=True)
    p.add_argument("--artifact", required=True); p.add_argument("--board", type=Path, required=True)
    p.add_argument("--grant-id", required=True); p.add_argument("--native-payload", type=Path, required=True)
    p.add_argument("--operation", choices=("create", "append"), required=True)
    p.add_argument("--before"); p.add_argument("--text-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "share-pack":
            result = share_pack(args.context_repo, args.workspace, args.artifact, board=args.board,
                                recipient=args.recipient, contributor=args.contributor, operation=args.operation,
                                before=args.before, private=args.private, ttl=args.ttl)
        elif args.command == "write-pack":
            raw, _ = records._snapshot(args.text_file)
            result = write_pack(args.context_repo, args.workspace, args.artifact, raw.decode("utf-8"),
                                board=args.board, native_payload=records.read_request(args.native_payload),
                                grant_id=args.grant_id, operation=args.operation, before=args.before)
        elif args.command == "migrate":
            request = records.read_request(args.map)
            result = migrate(request, apply=args.apply)
        elif args.command == "resolve":
            result = {"workspace": args.workspace, "root": str(default_root(args.context_repo, args.workspace))}
        elif args.command == "init":
            result = init_principal(args.context_repo, args.name, args.role, args.org,
                                    [g.strip() for g in args.goals.split(";") if g.strip()], workspace=args.workspace)
        else:
            result = add_reader(args.context_repo, args.id, args.name, args.relationship, workspace=args.workspace)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"prep_init: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
