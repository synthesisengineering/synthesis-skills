#!/usr/bin/env python3
"""Materialize a secrets manifest: refs in, files out with enforced permissions.

For each entry the backend value is written to the declared path with the
declared owner-only mode. Existing files are backed up before overwrite
(unless ``--no-backup``). ``--dry-run`` reports planned actions without
fetching values or writing files.

Writes are atomic (temp file + rename in the destination directory) and each
result is permission-verified: POSIX mode bits must be owner-only, and on
macOS any ``allow`` ACL entry for a non-owner principal fails the write.

No value is ever printed, logged, or embedded in an error message.

Usage::

    python3 materialize.py --manifest PATH [--home DIR] [--backend NAME]
                           [--dry-run] [--no-backup]

``--backend`` defaults to the manifest's declared backend. ``fake`` selects a
fixture backend (tests only) that serves a canned fake value.
"""
from __future__ import annotations

import argparse
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import secrets_manifest as _manifest

FAKE_BACKEND_NAME = "fake"
FAKE_BACKEND_VALUE = "FAKE-SECRET-VALUE-0001"


class MaterializeError(RuntimeError):
    """Materialization failed. Never carries a secret value."""


@dataclass(frozen=True)
class PermissionVerdict:
    path: str
    posix_ok: bool
    acl_ok: bool | None  # None = ACL check not applicable on this platform
    detail: str

    @property
    def ok(self) -> bool:
        return self.posix_ok and self.acl_ok is not False


@dataclass(frozen=True)
class MaterializeAction:
    ref: str
    dest: Path
    mode: int
    operation: str  # "write", "overwrite", or "planned"
    backup: Path | None = None


@dataclass(frozen=True)
class MaterializeReport:
    actions: tuple[MaterializeAction, ...]
    dry_run: bool
    ok: bool = True

    def summary(self) -> str:
        lines = []
        for action in self.actions:
            line = "%s %s mode=%04o" % (action.operation, action.dest, action.mode)
            if action.backup is not None:
                line += " backup=%s" % action.backup
            lines.append(line)
        if self.dry_run:
            lines.append("dry-run: no files written, no values fetched")
        return "\n".join(lines)


def parse_ls_le_acl(text: str, *, owner: str) -> bool:
    """Return True when canned ``ls -le`` output grants no non-owner access.

    ``deny`` entries are ignored; an ``allow`` entry for any principal other
    than the file owner fails the check.
    """
    ace = re.compile(r"^\s*\d+:\s+(user|group):(\S+)\s+(allow|deny)\b", re.IGNORECASE)
    for line in text.splitlines():
        match = ace.search(line)
        if not match:
            continue
        kind, principal, decision = match.group(1).lower(), match.group(2), match.group(3).lower()
        if decision != "allow":
            continue
        if kind == "user" and principal == owner:
            continue
        return False
    return True


def _macos_acl_clean(path: Path) -> bool | None:
    """Check macOS ACLs via ``ls -le``. None when the check cannot run."""
    if sys.platform != "darwin":
        return None
    ls = shutil.which("ls")
    if ls is None:
        return None
    try:
        result = subprocess.run(
            [ls, "-le", str(path)], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        owner = pwd.getpwuid(path.stat().st_uid).pw_name
    except (OSError, KeyError):
        return False
    return parse_ls_le_acl(result.stdout, owner=owner)


def verify_owner_only(path: Path, *, check_acl: bool = True) -> PermissionVerdict:
    """Verify ``path`` is readable only by its owner (POSIX bits + ACL shape)."""
    label = str(path)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        return PermissionVerdict(label, False, None, "%s: cannot stat: %s" % (label, exc))
    posix_ok = (mode & 0o077) == 0
    detail = "%s: mode %04o %s" % (label, mode, "owner-only" if posix_ok else "too permissive")
    acl_ok: bool | None = None
    if check_acl:
        acl_ok = _macos_acl_clean(path)
        if acl_ok is False:
            detail += "; non-owner ACL entry present"
    return PermissionVerdict(label, posix_ok, acl_ok, detail)


def _resolve_dest(entry: _manifest.ManifestEntry, *, home: Path) -> Path:
    dest = _manifest.expand_entry_path(entry, home=home)
    # Defense in depth: the parser already rejects '..', but refuse any
    # resolved path that escapes the home it was anchored to.
    try:
        resolved = dest.resolve()
        anchored = home.resolve()
    except OSError as exc:
        raise MaterializeError("cannot resolve destination for ref %r: %s" % (entry.ref, exc))
    if resolved != anchored and anchored not in resolved.parents:
        raise MaterializeError(
            "ref %r destination %s escapes home %s" % (entry.ref, dest, home)
        )
    return dest


def materialize_manifest(
    manifest: _manifest.SecretsManifest,
    backend: object,
    *,
    home: Path | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> MaterializeReport:
    """Write every manifest entry via ``backend``. Fails closed, never logs values."""
    anchor = Path(home) if home is not None else Path.home()
    get = getattr(backend, "get", None)
    if not callable(get):
        raise MaterializeError("backend %r has no get(ref)" % (backend,))
    actions: list[MaterializeAction] = []
    if dry_run:
        for entry in manifest.entries:
            dest = _resolve_dest(entry, home=anchor)
            if dest.is_symlink():
                raise MaterializeError("ref %r destination %s is a symlink" % (entry.ref, dest))
            actions.append(MaterializeAction(
                ref=entry.ref, dest=dest, mode=int(entry.mode, 8),
                operation="planned", backup=None,
            ))
        return MaterializeReport(actions=tuple(actions), dry_run=True)
    for entry in manifest.entries:
        dest = _resolve_dest(entry, home=anchor)
        if dest.is_symlink():
            raise MaterializeError("ref %r destination %s is a symlink" % (entry.ref, dest))
        try:
            value = get(entry.ref)
        except KeyError as exc:
            raise MaterializeError("backend has no value for ref %r" % (entry.ref,)) from exc
        except Exception as exc:
            if isinstance(exc, (MaterializeError, NotImplementedError)):
                raise
            raise MaterializeError(
                "backend failed for ref %r: %s" % (entry.ref, exc)
            ) from exc
        if not isinstance(value, str) or not value:
            raise MaterializeError("backend returned no usable value for ref %r" % (entry.ref,))
        actions.append(_write_entry(entry, dest, value, backup=backup))
    return MaterializeReport(actions=tuple(actions), dry_run=False)


def _write_entry(
    entry: _manifest.ManifestEntry, dest: Path, value: str, *, backup: bool
) -> MaterializeAction:
    mode = int(entry.mode, 8)
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    operation = "write"
    if dest.exists():
        operation = "overwrite"
        if backup:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = dest.with_name("%s.bak-%s" % (dest.name, stamp))
            _copy_owner_only(dest, backup_path)
    _atomic_write(dest, value, mode)
    verdict = verify_owner_only(dest)
    if not verdict.ok:
        raise MaterializeError("post-write verification failed: %s" % verdict.detail)
    return MaterializeAction(
        ref=entry.ref, dest=dest, mode=mode, operation=operation, backup=backup_path
    )


def _copy_owner_only(src: Path, dst: Path) -> None:
    fd = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            with open(src, "rb") as reader:
                shutil.copyfileobj(reader, handle)
    except BaseException:
        try:
            dst.unlink()
        except OSError:
            pass
        raise
    os.chmod(dst, 0o600)


def _atomic_write(dest: Path, value: str, mode: int) -> None:
    fd, tmp_name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=".fleet-secret-", suffix=".tmp"
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, dest)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class _FakeBackend:
    """Fixture backend for tests and CLI smoke runs. Serves one canned value."""

    name = FAKE_BACKEND_NAME

    def is_available(self) -> object:
        import secrets_provider as provider

        return provider.BackendStatus(name=self.name, available=True, detail="fake backend")

    def get(self, ref: str) -> str:
        if not isinstance(ref, str) or not ref:
            raise ValueError("ref must be a non-empty string")
        return FAKE_BACKEND_VALUE


def _select_backend(name: str) -> object:
    if name == FAKE_BACKEND_NAME:
        return _FakeBackend()
    if name == "onepassword":
        import secrets_provider as provider

        return provider.OnePasswordBackend()
    if name == "age-sops":
        import secrets_provider as provider

        return provider.AgeSopsBackend()
    raise MaterializeError("unknown backend %r" % (name,))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize a fleet secrets manifest.")
    parser.add_argument("--manifest", required=True, help="path to the secrets manifest")
    parser.add_argument("--home", default=None, help="home directory to resolve ~/ paths (testing)")
    parser.add_argument("--backend", default=None, help="backend name (default: manifest's)")
    parser.add_argument("--dry-run", action="store_true", help="report planned actions only")
    parser.add_argument("--no-backup", action="store_true", help="overwrite without backup")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = _manifest.parse_manifest(args.manifest)
    except _manifest.ManifestError as exc:
        print("materialize: %s" % exc, file=sys.stderr)
        return 2
    try:
        backend = _select_backend(args.backend or manifest.backend)
    except MaterializeError as exc:
        print("materialize: %s" % exc, file=sys.stderr)
        return 2
    try:
        report = materialize_manifest(
            manifest, backend,
            home=Path(args.home) if args.home else None,
            dry_run=args.dry_run, backup=not args.no_backup,
        )
    except MaterializeError as exc:
        print("materialize: %s" % exc, file=sys.stderr)
        return 1
    except NotImplementedError as exc:
        print("materialize: %s" % exc, file=sys.stderr)
        return 1
    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
