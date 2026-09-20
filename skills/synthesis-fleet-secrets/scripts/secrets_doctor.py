#!/usr/bin/env python3
"""Fleet secrets doctor: backend, manifest, permissions, values-absent checks.

Checks (each fails closed)::

    backend-available    backend CLI present and signed in
    manifest-valid       manifest parses and validates
    permissions-correct  every materialized path exists and is owner-only
    values-absent        no backend value appears in the manifest or in
                         git-tracked files under --scan-root

The values-absent check fetches each value from the backend at runtime and
holds it in memory only; values are never printed, logged, or written. When
the backend is unavailable the check fails closed ("cannot verify") rather
than passing silently.

Usage::

    python3 secrets_doctor.py --manifest PATH [--home DIR] [--backend NAME]
                              [--scan-root DIR]...

``--backend`` defaults to the manifest's declared backend. ``fake`` selects a
fixture backend (tests only) serving a canned fake value.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import materialize as _materialize
import secrets_manifest as _manifest

BACKEND_CHECK = "backend-available"
MANIFEST_CHECK = "manifest-valid"
PERMISSIONS_CHECK = "permissions-correct"
VALUES_ABSENT_CHECK = "values-absent"


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    ok: bool
    detail: str


def check_backend_available(backend: object) -> DoctorCheck:
    probe = getattr(backend, "is_available", None)
    if not callable(probe):
        return DoctorCheck(BACKEND_CHECK, False, "backend %r has no availability probe" % (backend,))
    try:
        status = probe()
    except Exception as exc:
        return DoctorCheck(BACKEND_CHECK, False, "backend probe raised: %s" % exc)
    available = bool(getattr(status, "available", False))
    detail = str(getattr(status, "detail", ""))
    name = str(getattr(status, "name", getattr(backend, "name", "backend")))
    if available:
        return DoctorCheck(BACKEND_CHECK, True, "%s: %s" % (name, detail or "available"))
    return DoctorCheck(BACKEND_CHECK, False, "%s: %s" % (name, detail or "unavailable"))


def check_manifest_valid(manifest_path: str | Path) -> DoctorCheck:
    path = Path(manifest_path)
    try:
        manifest = _manifest.parse_manifest(path)
    except _manifest.ManifestError as exc:
        return DoctorCheck(MANIFEST_CHECK, False, "%s" % exc)
    return DoctorCheck(
        MANIFEST_CHECK, True,
        "%s: valid (%d entries, backend %s)" % (path, len(manifest.entries), manifest.backend),
    )


def check_permissions(
    manifest: _manifest.SecretsManifest, *, home: Path | None = None
) -> DoctorCheck:
    anchor = Path(home) if home is not None else Path.home()
    problems: list[str] = []
    for entry in manifest.entries:
        try:
            dest = _manifest.expand_entry_path(entry, home=anchor)
        except _manifest.ManifestError as exc:
            problems.append("ref %s: %s" % (entry.ref, exc))
            continue
        if not dest.exists():
            problems.append("ref %s: %s not materialized" % (entry.ref, dest))
            continue
        verdict = _materialize.verify_owner_only(dest)
        if not verdict.ok:
            problems.append("ref %s: %s" % (entry.ref, verdict.detail))
    if problems:
        return DoctorCheck(PERMISSIONS_CHECK, False, "; ".join(problems))
    return DoctorCheck(
        PERMISSIONS_CHECK, True,
        "%d materialized paths are owner-only" % len(manifest.entries),
    )


def check_values_absent(
    manifest_path: str | Path,
    manifest: _manifest.SecretsManifest,
    backend: object,
    *,
    scan_roots: list[Path] | None = None,
) -> DoctorCheck:
    path = Path(manifest_path)
    try:
        manifest_bytes = path.read_bytes()
    except OSError as exc:
        return DoctorCheck(VALUES_ABSENT_CHECK, False, "cannot read manifest %s: %s" % (path, exc))
    get = getattr(backend, "get", None)
    if not callable(get):
        return DoctorCheck(VALUES_ABSENT_CHECK, False, "backend %r has no get(ref)" % (backend,))
    values: dict[str, bytes] = {}
    for entry in manifest.entries:
        try:
            value = get(entry.ref)
        except Exception as exc:
            return DoctorCheck(
                VALUES_ABSENT_CHECK, False,
                "backend unavailable while verifying ref %s: %s" % (entry.ref, exc),
            )
        if not isinstance(value, str) or not value:
            return DoctorCheck(
                VALUES_ABSENT_CHECK, False,
                "backend returned an empty value for ref %s; cannot verify absence" % entry.ref,
            )
        encoded = value.encode("utf-8")
        if len(encoded) < 4:
            return DoctorCheck(
                VALUES_ABSENT_CHECK, False,
                "value for ref %s is too short to scan reliably" % entry.ref,
            )
        values[entry.ref] = encoded
    for ref, encoded in values.items():
        if encoded in manifest_bytes:
            return DoctorCheck(
                VALUES_ABSENT_CHECK, False,
                "manifest %s contains the value for ref %s" % (path, ref),
            )
    for root in scan_roots or []:
        hit = _scan_git_tracked_files(root, values)
        if hit is not None:
            return DoctorCheck(VALUES_ABSENT_CHECK, False, hit)
    scope = "manifest %s" % path
    if scan_roots:
        scope += " + git-tracked files under %s" % ", ".join(str(r) for r in scan_roots)
    return DoctorCheck(
        VALUES_ABSENT_CHECK, True,
        "%d values absent from %s" % (len(values), scope),
    )


def _scan_git_tracked_files(root: Path, values: dict[str, bytes]) -> str | None:
    git = shutil.which("git")
    if git is None:
        return "cannot scan %s: git not found" % root
    try:
        listing = subprocess.run(
            [git, "-C", str(root), "ls-files", "-z"],
            capture_output=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "cannot list tracked files under %s: %s" % (root, exc)
    if listing.returncode != 0:
        return "cannot list tracked files under %s: not a git checkout?" % root
    for name in listing.stdout.split(b"\0"):
        if not name:
            continue
        candidate = root / name.decode("utf-8", "surrogateescape")
        try:
            content = candidate.read_bytes()
        except OSError:
            continue
        for ref, encoded in values.items():
            if encoded in content:
                return "tracked file %s contains the value for ref %s" % (candidate, ref)
    return None


def run_doctor(
    manifest_path: str | Path,
    backend: object,
    *,
    home: Path | None = None,
    scan_roots: list[Path] | None = None,
) -> list[DoctorCheck]:
    """Run all checks in order. Values stay in memory; details never hold them."""
    path = Path(manifest_path)
    checks = [check_backend_available(backend), check_manifest_valid(path)]
    try:
        manifest = _manifest.parse_manifest(path)
    except _manifest.ManifestError:
        manifest = None
    if manifest is None:
        checks.append(DoctorCheck(PERMISSIONS_CHECK, False, "skipped: manifest invalid"))
        checks.append(DoctorCheck(VALUES_ABSENT_CHECK, False, "skipped: manifest invalid"))
        return checks
    checks.append(check_permissions(manifest, home=home))
    checks.append(check_values_absent(path, manifest, backend, scan_roots=scan_roots))
    return checks


def _select_backend(name: str) -> object:
    if name == _materialize.FAKE_BACKEND_NAME:
        return _materialize._FakeBackend()
    if name == "onepassword":
        import secrets_provider as provider

        return provider.OnePasswordBackend()
    if name == "age-sops":
        import secrets_provider as provider

        return provider.AgeSopsBackend()
    raise _materialize.MaterializeError("unknown backend %r" % (name,))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the fleet secrets doctor checks.")
    parser.add_argument("--manifest", required=True, help="path to the secrets manifest")
    parser.add_argument("--home", default=None, help="home directory to resolve ~/ paths (testing)")
    parser.add_argument("--backend", default=None, help="backend name (default: manifest's)")
    parser.add_argument("--scan-root", action="append", default=[],
                        help="git checkout whose tracked files to scan (repeatable)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    backend_name = args.backend
    if backend_name is None:
        try:
            backend_name = _manifest.parse_manifest(args.manifest).backend
        except _manifest.ManifestError:
            backend_name = "onepassword"
    try:
        backend = _select_backend(backend_name)
    except _materialize.MaterializeError as exc:
        print("doctor: %s" % exc, file=sys.stderr)
        return 2
    checks = run_doctor(
        args.manifest, backend,
        home=Path(args.home) if args.home else None,
        scan_roots=[Path(r) for r in args.scan_root],
    )
    failed = 0
    for check in checks:
        print("%s %s: %s" % ("ok" if check.ok else "FAIL", check.id, check.detail))
        if not check.ok:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
