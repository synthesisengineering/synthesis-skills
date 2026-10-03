#!/usr/bin/env python3
"""Declared repository fetch and arithmetic, without merge or divergence judgments.

This is the mechanical half of ritual code sync. Fast-forward/reconciliation
remains with authenticated claim-owning workflows. Offline counts are CACHED.
"""

from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import time

from ritual_workers import read_regular, strict_yaml, RitualWorkersError
from credential_paths import _local_git_metadata

MAX_SECONDS = 300
MAX_REPOS = 256


def _git(repo, args, *, remaining, strip=True):
    if remaining <= 0:
        raise TimeoutError("repository inventory reached its total time bound")
    path = (
        Path(__file__).resolve().parents[2]
        / "synthesis-project-management/scripts/coordination_process.py"
    )
    # The runtime payload owner also installs the same closure as flat siblings.
    local = Path(__file__).resolve().with_name("coordination_process.py")
    if local.is_file():
        path = local
    if path.is_symlink():
        raise ValueError("repository process owner must be an exact runtime file")
    spec = importlib.util.spec_from_file_location("_ritual_process_owner", path)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    command = ["/usr/bin/env"]
    for name in sorted(os.environ):
        if name.startswith("GIT_"):
            command.extend(["-u", name])
    command += [
        "GIT_TERMINAL_PROMPT=0",
        "GIT_OPTIONAL_LOCKS=0",
        "LC_ALL=C",
        "git",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repo),
        *args,
    ]
    result = owner.run(
        command, cwd=repo, timeout=min(30, remaining), output_bytes=1024 * 1024
    )
    if result.returncode:
        raise ValueError("Git observation/fetch failed; no remote-current claim")
    return result.stdout.strip() if strip else result.stdout


def _declaration(root):
    """Read the existing bounded workspace declaration without performing sync."""
    declaration = root / ".agents/repos.yaml"
    resolved = declaration.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("repository declaration resolves outside workspace")
    raw = read_regular(resolved, 2 * 1024 * 1024)
    document = strict_yaml(raw.decode("utf-8"))
    if not isinstance(document, dict) or not isinstance(
        document.get("repos"), (list, dict)
    ):
        raise ValueError("declared repository inventory is missing")
    rows = document["repos"]
    if isinstance(rows, dict):
        if any(
            not isinstance(v, dict) or ("name" in v and v["name"] != k)
            for k, v in rows.items()
        ):
            raise ValueError("ambiguous repository map")
        rows = [{"name": k, **v} for k, v in rows.items()]
    if not rows or len(rows) > MAX_REPOS:
        raise ValueError("repository inventory must be nonempty and bounded")
    names = []
    for row in rows:
        name = row.get("name") if isinstance(row, dict) else None
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name)
            or name in names
        ):
            raise ValueError(
                "invalid or duplicate repository identity before aggregation"
            )
        names.append(name)
    return declaration, resolved, raw, document, rows


def _remote_identity(value):
    """Credential-free full logical source; never include input in errors."""
    from urllib.parse import urlsplit
    if (not isinstance(value, str) or not value or len(value) > 4096
            or any(ord(c) <= 32 for c in value)):
        raise ValueError("repository remote is not bounded credential-free identity")
    if value.startswith("/"):
        path = Path(value)
        if ".." in path.parts or path.resolve() != path:
            raise ValueError("local remote must be an exact physical path")
        return {"local": str(path)}
    if re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_. /-]+", value):
        value = "ssh://" + value.replace(":", "/", 1)
    parsed = urlsplit(value)
    if (parsed.scheme not in {"https", "ssh"} or not parsed.hostname
            or parsed.password is not None
            or (parsed.username is not None and
                (parsed.scheme != "ssh" or parsed.username != "git"))
            or parsed.query or parsed.fragment or "%" in parsed.path
            or ".." in parsed.path.split("/") or not parsed.path.startswith("/")
            or not re.fullmatch(r"/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+/?", parsed.path)):
        raise ValueError("repository remote must identify a complete credential-free source")
    return {"host": parsed.hostname.lower(), "port": parsed.port,
            "path": parsed.path.rstrip("/").removesuffix(".git")}


def _checkout_identity(repo, workspace):
    """Use the existing reciprocal worktree verifier and retain stable identities."""
    from hashlib import sha256
    if repo.resolve() != repo or not repo.is_dir():
        raise ValueError("repository must be an exact physical checkout")
    marker = repo / ".git"
    # The verifier bounds and checks this declaration again before use.
    if marker.is_file() and not marker.is_symlink():
        raw = read_regular(marker, 8192)
        match = re.fullmatch(rb"gitdir: ([^\r\n]+)\n?", raw)
        if match is None:
            raise ValueError("invalid checkout declaration")
        path = Path(match[1].decode("utf-8"))
        directory = Path(os.path.abspath(path if path.is_absolute() else repo / path))
    else:
        raw = b""; directory = marker
    if workspace is None:
        # An enrolled repository is independently bound by its pinned contract;
        # this scope only constrains local metadata, never grants source approval.
        workspace = Path(os.path.commonpath([repo, directory]))
        if workspace == Path("/"):
            raise ValueError("enrolled checkout metadata has no local common scope")
    before = _local_git_metadata(repo, workspace)
    common_file = directory / "commondir"
    common_raw = read_regular(common_file, 8192) if common_file.exists() else b""
    common = directory
    if common_raw:
        path = Path(common_raw.decode("utf-8").rstrip("\n"))
        common = Path(os.path.abspath(path if path.is_absolute() else directory / path))
    if _local_git_metadata(repo, workspace) != before:
        raise ValueError("checkout metadata changed while binding")
    def identity(path):
        info = path.stat()
        return [info.st_dev, info.st_ino]
    return {"checkout": str(repo), "checkout_identity": identity(repo),
            "git_directory": str(directory), "git_directory_identity": identity(directory),
            "common_directory": str(common), "common_directory_identity": identity(common),
            "gitfile_sha256": sha256(raw).hexdigest(),
            "commondir_sha256": sha256(common_raw).hexdigest()}


def repository_identity(repository, *, enrolled=None):
    """Bind an actual checkout to configured or pinned enrolled source identity.

    This is local configuration authority, not a statement about remote ACLs.
    No remote text or parser diagnostics are returned in durable proof/errors.
    """
    import hashlib
    deadline = time.monotonic() + 10
    repo = Path(repository).absolute()
    parents = list(repo.parents)
    if len(parents) > 64:
        raise ValueError("workspace declaration search exceeds bound")
    declarations = [p for p in parents if os.path.lexists(p / ".agents/repos.yaml")]
    if len(declarations) > 1:
        raise ValueError("ambiguous configured workspace for repository")
    result = None
    if declarations:
        workspace = declarations[0]
        declaration, resolved, raw, document, rows = _declaration(workspace)
        if document.get("status") == "dormant":
            raise ValueError("configured workspace is dormant")
        info = resolved.stat()
        declaration_identity = [info.st_dev, info.st_ino, info.st_mode]
        workspace_info = workspace.stat()
        physical = _checkout_identity(repo, workspace)
        matches = []
        for row in rows:
            if time.monotonic() >= deadline:
                raise TimeoutError("repository source binding reached its finite deadline")
            name = row["name"]
            value = row.get("path", name)
            if not isinstance(value, str):
                raise ValueError("configured repository path must be text")
            declared = Path(value)
            declared = declared if declared.is_absolute() else workspace / declared
            if (".." in declared.parts or declared.resolve() != declared
                    or not declared.is_relative_to(workspace) or declared == workspace):
                raise ValueError("configured repository path is not workspace local")
            # Unrelated absent checkouts need no Git query or payload traversal.
            if not declared.is_dir():
                continue
            candidate = _checkout_identity(declared, workspace)
            if (candidate["common_directory"] == physical["common_directory"]
                    and candidate["common_directory_identity"] == physical["common_directory_identity"]):
                matches.append((row, candidate))
        if len(matches) != 1:
            raise ValueError("actual checkout needs one exact configured repository")
        row, primary = matches[0]
        if row.get("status") == "dormant":
            raise ValueError("configured repository is dormant")
        remotes = row.get("remotes")
        if not isinstance(remotes, dict) or not isinstance(remotes.get("origin"), str):
            raise ValueError("configured repository needs exact origin identity")
        expected = _remote_identity(remotes["origin"])
        result = {"name": row["name"], "declaration": str(declaration),
                  "declaration_source": str(resolved),
                  "declaration_sha256": hashlib.sha256(raw).hexdigest(),
                  "declaration_identity": declaration_identity,
                  "workspace_identity": [workspace_info.st_dev, workspace_info.st_ino],
                  "workspace_root": str(workspace),
                  "declared_checkout": primary["checkout"], "declared_physical": primary, "physical": physical}
        if "memory" in row:
            memory = row["memory"]
            if (not isinstance(memory, dict)
                    or set(memory) != {"family", "workspace", "source"}
                    or type(memory["family"]) is not str
                    or memory["family"] not in {"personal", "workspace"}
                    or type(memory["source"]) is not str
                    or memory["source"] not in {"knowledge", "private-skills"}
                    or (memory["family"] == "personal" and memory["workspace"] is not None)
                    or (memory["family"] == "workspace" and
                        (type(memory["workspace"]) is not str
                         or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,95}", memory["workspace"])))
                    or (memory["source"] == "private-skills" and memory["family"] != "personal")):
                raise ValueError("configured memory scope must be a closed explicit private source declaration")
            result["memory"] = dict(memory)
        if read_regular(resolved, 2 * 1024 * 1024) != raw or declaration.resolve(strict=True) != resolved:
            raise ValueError("repository declaration changed during binding")
    elif enrolled is not None:
        expected = _remote_identity(enrolled["repository"]["remote"])
        result = {"name": expected["path"].rsplit("/", 1)[-1],
                  "enrollment_sha256": enrolled["sha256"],
                  "enrollment_index_sha256": enrolled["index_sha256"],
                  "physical": _checkout_identity(repo, None)}
    else:
        raise ValueError("memory destination requires configured or enrolled repository identity")
    if enrolled is not None:
        if enrolled["repository"]["audience"] != "private":
            raise ValueError("shared enrollment cannot authorize a private memory source")
        memory = {"family": "workspace", "workspace": enrolled["document"]["deletion_unit"],
                  "source": "knowledge"}
        if declarations and result.get("memory") != memory:
            raise ValueError("configured memory scope differs from pinned enrollment")
        result["memory"] = memory
    observed = _git(repo, ["remote", "get-url", "--all", "origin"], remaining=deadline-time.monotonic(), strip=False)
    lines = observed.splitlines()
    if len(lines) != 1 or not lines[0]:
        raise ValueError("actual origin cardinality is not one")
    remote = lines[0]
    if _remote_identity(remote) != expected:
        raise ValueError("actual origin differs from approved full repository identity")
    if enrolled is not None and _remote_identity(enrolled["repository"]["remote"]) != expected:
        raise ValueError("configured and enrolled repository sources differ")
    result["remote_identity_sha256"] = hashlib.sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    # Close metadata/configuration CAS after the actual origin observation.
    if _checkout_identity(repo, declarations[0] if declarations else None) != result["physical"]:
        raise ValueError("checkout identity changed during source observation")
    if declarations and _checkout_identity(Path(result["declared_checkout"]), declarations[0]) != primary:
        raise ValueError("configured checkout changed during source observation")
    if declarations and (read_regular(resolved, 2 * 1024 * 1024) != raw
                         or declaration.resolve(strict=True) != resolved):
        raise ValueError("repository declaration changed during source observation")
    if declarations:
        info = resolved.stat()
        current = [info.st_dev, info.st_ino, info.st_mode]
        workspace_info = declarations[0].stat()
        if (current != result["declaration_identity"]
                or [workspace_info.st_dev, workspace_info.st_ino] != result["workspace_identity"]):
            raise ValueError("repository declaration identity changed during binding")
    if time.monotonic() >= deadline:
        raise TimeoutError("repository source binding reached its finite deadline")
    return result


def scan(workspace, *, fetch=False):
    root = Path(workspace).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("workspace must be an exact real directory")
    declaration, resolved, raw, document, rows = _declaration(root)
    report = {
        "schema": 1,
        "declared": len(rows),
        "fetched": fetch,
        "repositories": [],
        "authority": "observations-only",
        "fast_forward_performed": False,
    }
    started = time.monotonic()
    for entry in rows:
        row = {"name": entry["name"], "status": "UNREACHABLE", "branches": []}
        report["repositories"].append(row)
        choice = entry.get("ritual_sync", False)
        if (
            document.get("status") == "dormant"
            or entry.get("status") == "dormant"
            or choice in (False, "no", "false")
        ):
            row["status"] = "EXCLUDED"
            continue
        try:
            if choice not in (True, "yes", "true"):
                raise ValueError("ritual_sync must be explicitly yes or no")
            declared = entry.get("path", entry["name"])
            if not isinstance(declared, str):
                raise ValueError("repository path must be text")
            path = Path(declared)
            path = path if path.is_absolute() else root / path
            if (
                ".." in path.parts
                or path.resolve() != path
                or not path.is_relative_to(root)
                or path == root
            ):
                raise ValueError("foreign or linked repository path")
            _local_git_metadata(path, root)
            branches = entry.get("default_branches")
            if (
                not isinstance(branches, list)
                or not branches
                or len(branches) > 32
                or any(
                    not isinstance(b, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", b)
                    or ".." in b
                    or "@{" in b
                    for b in branches
                )
                or len(set(branches)) != len(branches)
            ):
                raise ValueError(
                    "default branches must be an explicit unique bounded list"
                )

            def run(args):
                return _git(
                    path, args, remaining=MAX_SECONDS - (time.monotonic() - started)
                )

            if fetch:
                run(["fetch", "--all", "--no-recurse-submodules"])
            for branch in branches:
                result = {
                    "branch": branch,
                    "status": "BLIND",
                    "ahead": None,
                    "behind": None,
                }
                row["branches"].append(result)
                try:
                    ref = "refs/heads/" + branch
                    before = run(["rev-parse", "--verify", ref])
                    upstream = run(["for-each-ref", "--format=%(upstream)", ref])
                    if (
                        not upstream
                        or not upstream.startswith("refs/")
                        or "\n" in upstream
                    ):
                        raise ValueError("declared branch has no exact upstream")
                    upstream_before = run(["rev-parse", "--verify", upstream])
                    if any(not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid)
                           for oid in (before, upstream_before)):
                        raise ValueError("branch observation has no exact object identity")
                    pair = run(
                        ["rev-list", "--left-right", "--count", before + "..." + upstream_before]
                    )
                    if not re.fullmatch(r"\d+\s+\d+", pair):
                        raise ValueError("ahead/behind result malformed")
                    ahead, behind = map(int, pair.split())
                    if (run(["rev-parse", "--verify", ref]) != before
                            or run(["rev-parse", "--verify", upstream]) != upstream_before
                            or run(["for-each-ref", "--format=%(upstream)", ref]) != upstream):
                        raise ValueError("local branch or upstream changed during observation")
                    result.update(
                        ahead=ahead,
                        behind=behind,
                        status="DECISION"
                        if ahead or behind
                        else ("CURRENT" if fetch else "CACHED"),
                    )
                except (ValueError, OSError, TimeoutError) as exc:
                    result["reason"] = str(exc)
            _local_git_metadata(path, root)
            states = {b["status"] for b in row["branches"]}
            row["status"] = (
                "BLIND"
                if "BLIND" in states
                else (
                    "DECISION"
                    if "DECISION" in states
                    else ("CURRENT" if fetch else "CACHED")
                )
            )
        except (ValueError, OSError, TimeoutError, RitualWorkersError) as exc:
            row["reason"] = str(exc)
    if (
        read_regular(resolved, 2 * 1024 * 1024) != raw
        or declaration.resolve(strict=True) != resolved
    ):
        raise ValueError("repository declaration changed while scanning")
    report["counts"] = {
        status: sum(r["status"] == status for r in report["repositories"])
        for status in (
            "CURRENT",
            "CACHED",
            "DECISION",
            "BLIND",
            "UNREACHABLE",
            "EXCLUDED",
        )
    }
    return report


def main(argv=None):
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("--workspace-root", required=True, type=Path)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--doctor", action="store_true")
    args = p.parse_args(argv)
    if args.doctor and args.fetch:
        p.error("--doctor is read-only; --fetch requires the ritual execution path")
    try:
        result = scan(args.workspace_root, fetch=args.fetch)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2 if result["counts"]["BLIND"] or result["counts"]["UNREACHABLE"] else 0
    except (OSError, ValueError, RitualWorkersError) as exc:
        print(json.dumps({"status": "UNKNOWN", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
