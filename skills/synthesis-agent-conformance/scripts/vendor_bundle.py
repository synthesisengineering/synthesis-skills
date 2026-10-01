#!/usr/bin/env python3
"""Prepare source-bound vendor review bundles without submitting or authorizing contact.

Readiness is recalculated from an exact public release and real local receipt
owners. An assembled draft is useful evidence but is never a submission grant.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import ssl
import stat
import sys
import tarfile
import time
import urllib.request
from urllib.parse import urlsplit
import zipfile

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from hermes_source import chain, identity, read_json, read_regular, unchanged  # noqa: E402
from signed_receipt import held_directory  # noqa: E402

MAX_FILES = 12000
MAX_TOTAL = 128 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
MAX_SECONDS = 30.0
OFFICIAL = {
    "openai": (
        "https://developers.openai.com/plugins/guides/submit-claude-plugin",
        ("codex", "claude"),
    ),
    "anthropic": (
        "https://code.claude.com/docs/en/plugin-marketplaces",
        ("claude", "codex"),
    ),
    "hermes": (
        "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks/",
        ("hermes",),
    ),
}
REQUIRED = (
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    "LICENSE-APACHE",
    "LICENSE-CC0",
    "SUPPORT.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
)
OMIT = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
PLACEHOLDER = re.compile(
    r"\[(?:VERSION|TODO|TBD|INSERT[^\]]*)\]|\b(?:TODO|TBD)\b|insert (?:release highlights|.+ here)|works perfectly in every harness",
    re.I,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def source_inventory(root):
    root = Path(root)
    deadline = time.monotonic() + MAX_SECONDS
    roots = chain(root)
    records = []
    snapshots = []
    directories = []
    total = 0
    visited = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        members = []
        with os.scandir(directory) as scan:
            for entry in scan:
                if entry.name in OMIT:
                    continue
                visited += 1
                if visited > MAX_FILES or time.monotonic() > deadline:
                    raise ValueError("source inventory resource bound reached")
                members.append(entry.name)
                path = Path(entry.path)
                st = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(st.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(st.st_mode):
                    raw, ident, parts = read_regular(
                        path,
                        limit=min(MAX_MEMBER, MAX_TOTAL - total),
                        deadline=deadline,
                    )
                    total += len(raw)
                    records.append(
                        {
                            "path": path.relative_to(root).as_posix(),
                            "mode": stat.S_IMODE(ident[2]),
                            "size": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                        }
                    )
                    snapshots.append((path, ident, parts))
                else:
                    raise ValueError("source contains links or special objects")
        directories.append((directory, sorted(members)))
    for path, ident, parts in snapshots:
        if identity(path.lstat()) != ident or not unchanged(parts):
            raise ValueError("source changed during inventory")
    for directory, members in directories:
        observed = []
        with os.scandir(directory) as scan:
            for item in scan:
                if item.name in OMIT:
                    continue
                if len(observed) > MAX_FILES:
                    raise ValueError("source membership exceeds bound")
                observed.append(item.name)
        if sorted(observed) != members:
            raise ValueError("source membership changed")
    if time.monotonic() > deadline or not unchanged(roots):
        raise ValueError("source inventory deadline or identity changed")
    return sorted(records, key=lambda item: item["path"])


def _safe_name(value):
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        raise ValueError("unsafe archive member")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe archive member")
    return path


def compare_release_archive(raw, inventory):
    if len(raw) > MAX_TOTAL:
        raise ValueError("release archive exceeds bound")
    expected = {v["path"]: v for v in inventory}
    observed = {}
    total = 0
    prefix = None
    deadline = time.monotonic() + MAX_SECONDS
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
        for number, item in enumerate(archive):
            if number >= MAX_FILES * 2 or time.monotonic() > deadline:
                raise ValueError("release archive resource bound reached")
            name = _safe_name(item.name)
            if prefix is None:
                prefix = name.parts[0]
            if name.parts[0] != prefix:
                raise ValueError("release archive root is ambiguous")
            if item.isdir():
                continue
            if not item.isfile() or len(name.parts) < 2:
                raise ValueError("nonregular release member")
            relative = PurePosixPath(*name.parts[1:]).as_posix()
            if relative in observed:
                raise ValueError("duplicate release member")
            if item.size < 0 or item.size > MAX_MEMBER or total + item.size > MAX_TOTAL:
                raise ValueError("release member exceeds byte bound")
            handle = archive.extractfile(item)
            content = handle.read(item.size + 1)
            if len(content) != item.size:
                raise ValueError("truncated release member")
            total += len(content)
            observed[relative] = (
                hashlib.sha256(content).hexdigest(),
                len(content),
                bool(item.mode & 0o111),
            )
    # GitHub source archives include exactly the tracked source; ignored caches
    # never count as released evidence. Extra/missing source invalidates equality.
    if set(observed) != set(expected):
        raise ValueError("release archive source membership differs")
    for path, record in expected.items():
        if observed[path] != (
            record["sha256"],
            record["size"],
            bool(record["mode"] & 0o111),
        ):
            raise ValueError("release archive source bytes or modes differ")
    return True


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urlsplit(newurl)
        if (
            u.scheme != "https"
            or u.hostname not in {"api.github.com", "codeload.github.com"}
            or u.username
            or u.password
        ):
            raise ValueError("release redirect escaped official source")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url, limit):
    # Fixed public repository URLs only; no credentials, auth session or model.
    opener = urllib.request.build_opener(
        _Redirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "synthesis-vendor-review",
            "Accept": "application/vnd.github+json",
        },
    )
    deadline = time.monotonic() + 20
    with opener.open(req, timeout=10) as response:
        data = bytearray()
        while True:
            if time.monotonic() > deadline:
                raise ValueError("public release read deadline exceeded")
            part = response.read(min(65536, limit + 1 - len(data)))
            if not part:
                break
            data.extend(part)
            if len(data) > limit:
                raise ValueError("public release response exceeds bound")
    return bytes(data)


def released_source(version, inventory):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("invalid release version")
    url = (
        "https://api.github.com/repos/synthesisengineering/synthesis-skills/releases/tags/v"
        + version
    )
    raw = _fetch(url, 1024 * 1024)
    metadata = json.loads(raw)
    if (
        metadata.get("tag_name") != "v" + version
        or metadata.get("draft") is not False
        or metadata.get("prerelease") is not False
        or not metadata.get("published_at")
    ):
        raise ValueError("public release is not a published stable release")
    source_url = (
        "https://api.github.com/repos/synthesisengineering/synthesis-skills/tarball/v"
        + version
    )
    archive = _fetch(source_url, MAX_TOTAL)
    compare_release_archive(archive, inventory)
    return {
        "status": "PASS",
        "url": url,
        "metadata_sha256": hashlib.sha256(raw).hexdigest(),
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "source_digest": digest(inventory),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def _native(client, entry, version, inventory, *, root=None, owner_context=None):
    if not isinstance(entry, dict) or set(entry) != {"receipt", "plugin_root"}:
        raise ValueError("native evidence requires exact receipt and installed plugin paths")
    if root is None or owner_context is None:
        return "UNKNOWN"
    from vendor_native import current_callback
    return current_callback(root, client, entry, version, inventory, owner_context)["status"]


def portable_observations(context, root, inventory):
    """Read-only P15 verification with explicitly selected external trust.

    The separate owner context is not accepted from a submitted receipt. Even a
    verified PASS remains a signer observation, never native/action authority.
    No signing key, registry write, enrollment or live client is involved.
    """
    if context is None:
        return {}
    from signed_receipt import (
        read_regular as held_read,
        strict_json,
        verify,
        verification_snapshot,
        revalidate_verified_inputs,
    )

    if not isinstance(context, dict) or not set(context) <= {"claude", "codex"}:
        raise ValueError("unsupported portable observation owner context")
    results = {}
    for client, selected in context.items():
        if not isinstance(selected, dict) or set(selected) != {
            "envelope",
            "trust",
            "bindings",
        }:
            raise ValueError(
                "explicit envelope, local trust and current bindings required"
            )
        paths = [Path(selected[key]) for key in ("envelope", "trust", "bindings")]
        raw = [held_read(path, owner=index > 0) for index, path in enumerate(paths)]
        envelope, trust, expected = map(strict_json, raw)
        if expected.get("client") != client:
            raise ValueError("portable observation client differs")
        onboarding = HERE.parents[1] / "synthesis-onboarding/scripts"
        if str(onboarding) not in sys.path:
            sys.path.insert(0, str(onboarding))
        from system_contract import canonical_tree_digest

        if expected.get("source_sha256") != canonical_tree_digest(root):
            raise ValueError("portable observation source differs")
        snapshot = verification_snapshot(envelope, trust, expected)
        result = verify(envelope, trust, expected)
        if any(
            held_read(path, owner=index > 0) != content
            for index, (path, content) in enumerate(zip(paths, raw))
        ):
            raise ValueError("portable observation input changed")
        if source_inventory(root) != inventory:
            raise ValueError("portable observation source changed")
        revalidate_verified_inputs(snapshot, envelope, trust, expected)
        results[client] = {
            "signature_verified": result["signature_verified"],
            "status": result["status"],
            "native_acceptance": False,
            "action_authority": False,
        }
    return results


def owner_report(root, command, arguments=()):
    """Invoke the exact existing owner, retaining only sanitized check outcomes."""
    scripts = HERE.parents[1] / "synthesis-project-management" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import coordination_process

    try:
        outcome = coordination_process.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(HERE / "conformance.py"),
                command,
                "--source-root",
                str(root),
                "--json",
                *arguments,
            ],
            cwd=root,
            timeout=30,
            output_bytes=1024 * 1024,
        )
        data = json.loads(outcome.stdout)
        checks = data.get("checks")
        if (
            not isinstance(checks, list)
            or not checks
            or any(not isinstance(v, dict) for v in checks)
        ):
            raise ValueError("conformance owner returned no checks")
        status = (
            "PASS" if outcome.returncode == 0 and data.get("ok") is True else "FAIL"
        )
        return {
            "status": status,
            "checks": [
                {
                    "name": v.get("name"),
                    "status": v.get("status"),
                    "required": v.get("required"),
                }
                for v in checks
            ],
            "output_sha256": hashlib.sha256(outcome.stdout.encode()).hexdigest(),
        }
    except coordination_process.EffectInterrupted:
        raise
    except (OSError, ValueError, RuntimeError, TimeoutError, ImportError) as exc:
        return {"status": "UNKNOWN", "reason": type(exc).__name__}


def source_conformance(root):
    # Source-only: no native catalog query, network, account or provider.
    return owner_report(root, "source")


def native_qualification(root, scope, vendor):
    """Explicit opt-in to existing native read-only owners, never implicit trust.

    The caller must separately authorize actual native query/qualification. No
    native process is launched by default and no model request is made here.
    """
    if vendor == "hermes":
        return {
            key: {"status": "UNSUPPORTED"}
            for key in ("hook-trust", "catalog-budget", "continuity.local")
        }
    keys = {"repo_root", "project", "active_project_file", "coordination_board"}
    if not isinstance(scope, dict) or set(scope) != keys:
        raise ValueError("native qualification requires an exact explicit scope")
    for key, value in scope.items():
        path = Path(value)
        if not path.is_absolute():
            raise ValueError("native qualification paths must be absolute")
        chain(
            path
            if key in {"repo_root", "project", "coordination_board"}
            else path.parent
        )
    common = [
        "--local",
        "--repo-root",
        scope["repo_root"],
        "--project",
        scope["project"],
        "--active-project-file",
        scope["active_project_file"],
        "--coordination-board",
        scope["coordination_board"],
    ]
    return {
        key: owner_report(root, command, common)
        for key, command in (
            ("hook-trust", "hook-trust"),
            ("catalog-budget", "catalog"),
            ("continuity.local", "continuity"),
        )
    }


def prepare(
    root, request, *, verify_release=False, verify_native=False, portable_context=None, native_context=None
):
    if (
        not isinstance(request, dict)
        or not {"schema", "vendor", "draft", "native", "official_sources"}
        <= set(request)
        or set(request)
        - {
            "schema",
            "vendor",
            "draft",
            "native",
            "official_sources",
            "qualification_scope",
        }
        or request["schema"] != 1
    ):
        raise ValueError("invalid vendor review request")
    vendor = request["vendor"]
    draft = request["draft"]
    native = request["native"]
    if vendor not in OFFICIAL:
        raise ValueError("unsupported vendor target")
    if (
        not isinstance(draft, str)
        or not 1 <= len(draft) <= 16000
        or PLACEHOLDER.search(draft)
        or any(ord(c) < 32 and c not in "\n\t" for c in draft)
    ):
        raise ValueError(
            "draft contains a placeholder, unbounded claim or invalid text"
        )
    if not isinstance(native, dict) or set(native) - set(OFFICIAL[vendor][1]):
        raise ValueError("unexpected native evidence clients")
    if native_context is not None and (
        not isinstance(native_context, dict) or set(native_context) - set(OFFICIAL[vendor][1])
    ):
        raise ValueError("unexpected admitted native context clients")
    if (
        not isinstance(request["official_sources"], list)
        or len(request["official_sources"]) > 32
    ):
        raise ValueError("invalid source references")
    captured_sources = []
    capture_bytes = 0
    for item in request["official_sources"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"url", "sha256", "observed_at", "path"}
            or not re.fullmatch("[a-f0-9]{64}", str(item["sha256"]))
        ):
            raise ValueError("source pin incomplete")
        parsed = urlsplit(item["url"])
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.hostname
            not in {
                "developers.openai.com",
                "learn.chatgpt.com",
                "code.claude.com",
                "hermes-agent.nousresearch.com",
                "github.com",
                "raw.githubusercontent.com",
            }
        ):
            raise ValueError("source URL is not an allowed public primary source")
        observed = datetime.fromisoformat(item["observed_at"])
        if (
            observed.tzinfo is None
            or not 0
            <= (datetime.now(timezone.utc) - observed).total_seconds()
            <= 30 * 86400
        ):
            raise ValueError("official source pin is stale or future")
        raw, _, _ = read_regular(Path(item["path"]), limit=1024 * 1024)
        capture_bytes += len(raw)
        if (
            capture_bytes > 4 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != item["sha256"]
        ):
            raise ValueError("official source capture is missing, changed or oversized")
        captured_sources.append(
            {key: item[key] for key in ("url", "sha256", "observed_at")}
        )
        captured_sources[-1]["text"] = raw.decode("utf-8")
    root = Path(root)
    inventory = source_inventory(root)
    names = {x["path"] for x in inventory}
    if set(REQUIRED) - names or not any(
        re.fullmatch(r"skills/[^/]+/SKILL.md", p) for p in names
    ):
        raise ValueError("required source/manifests/licenses/support are missing")
    manifests = [read_json(root / name) for name in REQUIRED[:2]]
    version = manifests[0].get("version")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(version)) or any(
        m.get("version") != version
        or m.get("name") != "synthesis-skills"
        or m.get("license") != "Apache-2.0 AND CC0-1.0"
        or not m.get("description")
        for m in manifests
    ):
        raise ValueError("plugin release identity/license is inconsistent")
    source_check = source_conformance(root)
    gates = {
        "source-conformance": source_check["status"],
        "release": "UNKNOWN",
        "captured-official-sources": "PASS"
        if request["official_sources"]
        else "UNKNOWN",
    }
    release = None
    if verify_release:
        try:
            release = released_source(version, inventory)
            gates["release"] = "PASS"
        except (OSError, ValueError, tarfile.TarError) as exc:
            release = {"status": "UNKNOWN", "reason": str(exc)[:200]}
    for client in OFFICIAL[vendor][1]:
        gates["native." + client] = (
            _native(client, native[client], version, inventory, root=root,
                    owner_context=(native_context or {}).get(client))
            if client in native
            else "UNKNOWN"
        )
    qualification = {
        key: {"status": "UNKNOWN", "reason": "native owner query not requested"}
        for key in ("hook-trust", "catalog-budget", "continuity.local")
    }
    if verify_native:
        qualification = native_qualification(
            root, request.get("qualification_scope"), vendor
        )
    gates.update({key: value["status"] for key, value in qualification.items()})
    # This is a local technical gate, not permission to communicate. Exact
    # outward approval and directory submission remain the existing user's gate.
    ready = all(v == "PASS" for v in gates.values())
    bundle = {
        "schema": 1,
        "vendor": vendor,
        "version": version,
        "source_digest": digest(inventory),
        "source_files": inventory,
        "draft": draft,
        "official_sources": captured_sources,
        "official_route": OFFICIAL[vendor][0],
        "license": "Apache-2.0 AND CC0-1.0",
        "support": "SUPPORT.md",
        "gates": gates,
        "status": "TECHNICAL_REVIEW_READY" if ready else "REVIEW_DRAFT",
        "technical_review_ready": ready,
        "submission_ready": False,
        "directory_evidence": {
            "installation_recording": "NOT_ATTACHED",
            "bidirectional_recording": "NOT_ATTACHED",
            "exact_outward_approval": "NOT_GRANTED",
        },
        "source_conformance": source_check,
        "portable_observations": portable_observations(
            portable_context, root, inventory
        ),
        "source_export": "WITHHELD_UNVERIFIED_PUBLIC_RELEASE",
        "native_qualification": qualification,
        "contact_authorized": False,
        "submission_authorized": False,
        "provider_cause": "UNKNOWN",
        "release_observation": release,
        "native_evidence_export": "Aggregate status only; no raw native histories or private paths.",
        "native_gate_scope": (
            "A PASS qualifies the admitted pre_llm_call context and pre_api_request consumption pair for exact current bytes; protected execution, recovery and desktop loading remain unverified."
            if vendor == "hermes" else
            "A PASS qualifies the admitted CLI SessionStart context callback for exact current bytes; desktop live loading and other hooks remain separate."
        ),
        "trust": "Users retain native permission and hook-trust decisions; no auto-accept or sandbox bypass.",
        "privacy": "This builder sends nothing. Explicit release verification reads only public GitHub. Harness/provider behavior has its own policy.",
    }
    # Reject a source change during evidence collection; readiness cannot outlive
    # the exact input it was calculated from.
    if source_inventory(root) != inventory:
        raise ValueError("source changed during review")
    bundle["bundle_digest"] = digest(bundle)
    return bundle


def export(root, bundle, destination, *, verify_release=False):
    """Publish a local draft; source bytes require a fresh public-release owner.

    A digest authenticates neither public disclosure eligibility nor native
    execution. Default drafts exclude all source filenames and source bytes.
    Caller-supplied PASS fields cannot authorize a full-source archive.
    """
    root, destination = Path(root), Path(destination)
    check = dict(bundle)
    claimed = check.pop("bundle_digest", None)
    if claimed != digest(check):
        raise ValueError("review bundle digest differs")
    if source_inventory(root) != bundle["source_files"]:
        raise ValueError("source changed after review")
    if bundle["gates"].get("release") == "PASS" and not verify_release:
        raise ValueError(
            "source export requires explicit fresh public release verification"
        )
    retained = dict(bundle)
    if verify_release:
        # Re-run the actual TLS/release/archive owner. Its result is not trusted
        # merely because a JSON bundle carries a previous PASS observation.
        released = released_source(bundle["version"], bundle["source_files"])
        retained["release_observation"] = released
        retained["source_export"] = "VERIFIED_PUBLIC_RELEASE"
    else:
        retained["source_files"] = []
        retained["source_export"] = "WITHHELD_UNVERIFIED_PUBLIC_RELEASE"
        retained["technical_review_ready"] = False
        retained["status"] = "REVIEW_DRAFT"
        # Names in source checks can include local-only skills. Preserve the
        # measured outcome and a digest, without exporting incidental names.
        checks = bundle["source_conformance"].get("checks", [])
        retained["source_conformance"] = {
            "status": bundle["source_conformance"]["status"],
            "check_count": len(checks),
            "checks_sha256": digest(checks),
        }
    retained.pop("bundle_digest", None)
    retained["bundle_digest"] = digest(retained)
    body = (json.dumps(retained, indent=2) + "\n").encode()
    if len(body) > MAX_MEMBER:
        raise ValueError("review metadata exceeds archive member bound")
    if not destination.is_absolute() or ".." in destination.parts:
        raise ValueError("absolute exact output path required")
    with held_directory(destination.parent) as (parent, recheck):
        recheck()
        fd = os.open(
            destination.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        try:
            opened = os.fstat(fd)
            recheck()
            with os.fdopen(fd, "wb", closefd=False) as target:
                with zipfile.ZipFile(
                    target, "w", compression=zipfile.ZIP_DEFLATED
                ) as archive:
                    info = zipfile.ZipInfo("review.json")
                    info.external_attr = (stat.S_IFREG | 0o600) << 16
                    archive.writestr(info, body)
                    for item in retained["source_files"]:
                        raw, _, _ = read_regular(root / item["path"], limit=MAX_MEMBER)
                        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                            raise ValueError("source changed during export")
                        recheck()
                        info = zipfile.ZipInfo("source/" + item["path"])
                        info.external_attr = (stat.S_IFREG | item["mode"]) << 16
                        archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED)
                target.flush()
                os.fsync(fd)
            named = os.stat(destination.name, dir_fd=parent, follow_symlinks=False)
            if (
                named.st_dev,
                named.st_ino,
                named.st_uid,
                named.st_mode,
                named.st_nlink,
            ) != (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_mode, 1):
                raise ValueError("archive output identity changed")
            recheck()
            if source_inventory(root) != bundle["source_files"]:
                raise ValueError("source changed during export")
            if os.fstat(fd).st_size > MAX_TOTAL:
                raise ValueError("archive output exceeds byte bound")
            verify_export(destination)
            recheck()
        finally:
            os.close(fd)
    return retained


def verify_export(path):
    raw, _, _ = read_regular(path, limit=MAX_TOTAL)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES + 1 or len({i.filename for i in members}) != len(
            members
        ):
            raise ValueError("archive membership invalid")
        total = 0
        for item in members:
            _safe_name(item.filename)
            total += item.file_size
            if (
                item.file_size > MAX_MEMBER
                or total > MAX_TOTAL
                or not stat.S_ISREG(item.external_attr >> 16)
            ):
                raise ValueError("archive kind/size invalid")
        bundle = json.loads(archive.read("review.json"))
        copy = dict(bundle)
        sha = copy.pop("bundle_digest", None)
        if (
            sha != digest(copy)
            or bundle.get("contact_authorized") is not False
            or bundle.get("submission_authorized") is not False
            or bundle.get("submission_ready") is not False
            or bundle.get("source_export")
            not in {"WITHHELD_UNVERIFIED_PUBLIC_RELEASE", "VERIFIED_PUBLIC_RELEASE"}
            or not re.fullmatch("[a-f0-9]{64}", str(bundle.get("source_digest")))
        ):
            raise ValueError("archive review identity invalid")
        if (
            bundle["source_export"] == "WITHHELD_UNVERIFIED_PUBLIC_RELEASE"
            and bundle["source_files"]
        ):
            raise ValueError("unverified source bytes in draft archive")
        if (
            bundle["source_export"] == "VERIFIED_PUBLIC_RELEASE"
            and digest(bundle["source_files"]) != bundle["source_digest"]
        ):
            raise ValueError("archive source inventory digest differs")
        seen = set()
        for row in bundle["source_files"]:
            if (
                not isinstance(row, dict)
                or set(row) != {"path", "mode", "size", "sha256"}
                or row["path"] in seen
                or _safe_name(row["path"]).as_posix() != row["path"]
                or type(row["mode"]) is not int
                or not 0 <= row["mode"] <= 0o777
                or type(row["size"]) is not int
                or not 0 <= row["size"] <= MAX_MEMBER
                or not re.fullmatch("[a-f0-9]{64}", str(row["sha256"]))
            ):
                raise ValueError("archive source inventory invalid")
            seen.add(row["path"])
        if {i.filename for i in members} != {
            "review.json",
            *("source/" + r["path"] for r in bundle["source_files"]),
        }:
            raise ValueError("archive source membership invalid")
        for item in bundle["source_files"]:
            content = archive.read("source/" + item["path"])
            if (
                stat.S_IMODE(
                    archive.getinfo("source/" + item["path"]).external_attr >> 16
                )
                != item["mode"]
                or len(content) != item["size"]
                or hashlib.sha256(content).hexdigest() != item["sha256"]
            ):
                raise ValueError("archive source content changed")
    return {
        "status": "CUSTODY_VERIFIED",
        "source_digest": bundle["source_digest"],
        "retained_technical_status": bundle["status"],
        "contact_authorized": False,
        "native_revalidation_required": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    build = sub.add_parser("prepare")
    build.add_argument("--source-root", required=True, type=Path)
    build.add_argument("--request", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--verify-release", action="store_true")
    build.add_argument(
        "--native-context", type=Path,
        help="Select existing admitted journal events; no native process or permission is created",
    )
    build.add_argument(
        "--portable-context",
        type=Path,
        help="Explicit separate local trust/bindings context; verifies portable signatures only",
    )
    build.add_argument(
        "--verify-native",
        action="store_true",
        help="Explicitly run existing local native trust, catalog and continuity queries; requires separate native authorization",
    )
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == "verify":
            result = verify_export(args.archive)
        else:
            result = prepare(
                args.source_root,
                read_json(args.request),
                verify_release=args.verify_release,
                verify_native=args.verify_native,
                native_context=read_json(args.native_context) if args.native_context else None,
                portable_context=read_json(args.portable_context)
                if args.portable_context
                else None,
            )
            result = export(
                args.source_root,
                result,
                args.output,
                verify_release=args.verify_release,
            )
            result = {
                "status": result["status"],
                "gates": result["gates"],
                "source_digest": result["source_digest"],
                "archive": str(args.output),
                "source_export": result["source_export"],
                "contact_authorized": False,
            }
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(
            json.dumps(
                {
                    "status": "REFUSED",
                    "reason": str(exc)[:500],
                    "contact_authorized": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
